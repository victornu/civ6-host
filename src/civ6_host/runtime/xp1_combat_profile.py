"""XP1 source and ABI selection for the shared combat/experience producers."""
from dataclasses import dataclass
from functools import lru_cache
import re
from .configuration_profiles import BASE_CORE_SHA256,XP1_CORE_SHA256,XP2_CORE_SHA256,_source,_body

SOURCE=('work/host-extensions/xp1-combat-static/source-v2.json',
        '675c0a73ef9521f4105a56d7e7b3a3b741fbe658f4fbf54b60e8773692d5a875')


def rows(value):return tuple(r for f in _body(value)['fragments'] for r in f['instructions'])


@lru_cache(maxsize=1)
def verify_source():
    from .native import native_event_argument_tree as tree,native_event_a479f83f as xp
    from .native.native_host_event_registry import EXE_EVENT_CALLBACKS
    p=_source(SOURCE)
    if (p['schema']!='civ6-host.xp1-combat-producer.source.v1' or p['native_execution'] is not False
            or p['image']['sha256']!=XP1_CORE_SHA256
            or p['validation']['all_instruction_bytes_match_image'] is not True
            or p['validation']['all_virtual_targets_match_image'] is not True
            or EXE_EVENT_CALLBACKS.get(0x8256dbe1)!=0x142fe0
            or EXE_EVENT_CALLBACKS.get(xp.EVENT_KIND)!=0x1561b0):
        raise ValueError('XP1 combat source identity changed')
    for ref in p['references']:_source((ref['path'],ref['sha256']))
    original=tree.verify_source_evidence();xp.verify_source_evidence()
    if p['root_fields']!=original['contract']['root_builder']['fields']:
        raise ValueError('Combat root field contract changed')
    keys=lambda body:{int(m.group(1),16) for r in rows(body)
                      if (m:=re.fullmatch(r'mov edx, 0x([0-9a-f]+)',r['text']))}
    if keys(p['functions']['root_builder'])!={int(row['key'],16) for row in p['root_fields']}:
        raise ValueError('XP1 combat root builder keys differ')
    if keys(p['functions']['child_builder'])!=keys(original['captures']['child_map_builder']):
        raise ValueError('XP1 combat child builder keys differ')
    if dict(p['predicate'])!=dict(game_table=0x8a9a88,slot=0x130,target=0x4c3ed0,
                                  state_getter=0x28a450,state_global=0x9f5948):
        raise ValueError('XP1 combat predicate ABI changed')
    promotion=p['promotion']
    if (promotion['command']!=0xb4edd43f or promotion['result_key']!=0x315247e7
            or (promotion['outer_table'],promotion['service_table'],promotion['map_table'])!=(0x8a8df0,0x8ab1e8,0x93f590)
            or dict(promotion['methods'])!=dict(get_service=0x4bd300,release_outer=0x1843b0,
               map_ctor=0x844460,map_dtor=0x844580,map_lookup=0x845540,query=0x4cc8e0,release_service=0x4cc910)):
        raise ValueError('XP1 promotion query ABI changed')
    text={r['text'] for r in rows(p['functions']['promotion_service_query'])}
    if 'jmp 0x1800abc60' not in text:raise ValueError('XP1 promotion native implementation changed')
    return p


def ensure_source(core_sha256):
    if core_sha256==BASE_CORE_SHA256:return
    if core_sha256==XP2_CORE_SHA256:
        from .xp2_combat_event_source import verify_source as verify_xp2
        verify_xp2(core_sha256)
        return
    if core_sha256!=XP1_CORE_SHA256:raise ValueError('Unqualified combat engine')
    verify_source()


def source_sha(core_sha256,retained):
    ensure_source(core_sha256)
    if core_sha256==BASE_CORE_SHA256:return retained
    if core_sha256==XP2_CORE_SHA256:
        from .xp2_combat_event_source import SOURCE as xp2_source
        return xp2_source[1]
    return SOURCE[1]


def source_dependencies(core_sha256=XP1_CORE_SHA256, *, execution_image=None):
    if core_sha256==XP2_CORE_SHA256:
        from .xp2_combat_event_source import source_dependencies as xp2_dependencies
        return xp2_dependencies(execution_image=execution_image)
    if execution_image is not None:raise ValueError('Selected execution image requires XP2 combat ABI')
    if core_sha256!=XP1_CORE_SHA256:
        raise ValueError('Combat source dependencies require exact XP1 or XP2')
    from .paths import resource_root
    from .resource_resolution import resolve_path
    from .combat_map_profiles import source_dependencies as map_sources
    p=verify_source();refs=[dict(path=SOURCE[0],sha256=SOURCE[1]),p['image'],*p['references'],p['correction']['previous']]
    return {**map_sources(),**{str(resolve_path(resource_root()/r['path']).resolve()):r['sha256'] for r in refs}}


def bind_owner(backend,core,read,*,execution_image=None):
    backend.check_thread()
    if backend.core is core and backend.load_abi.core_sha256==XP2_CORE_SHA256:
        from .xp2_combat_event_source import bind_owner as bind_xp2
        if execution_image is None:
            execution_image=getattr(core,'_civ6_host_execution_image',None)
        return bind_xp2(backend,core,read,execution_image=execution_image)
    if execution_image is not None:raise ValueError('Selected execution image requires XP2 combat ABI')
    if backend.core is not core or backend.load_abi.core_sha256!=XP1_CORE_SHA256:
        raise ValueError('Combat source requires its exact XP1 owner')
    p=verify_source();identity=(core,core._handle,SOURCE[1])
    if getattr(backend,'_xp1_combat_source',None)==identity:return p
    for name,body in p['functions'].items():
        for fragment in _body(body)['fragments']:
            expected=b''.join(bytes.fromhex(r['bytes']) for r in fragment['instructions'])
            address=core._handle+int(fragment.get('start_va',fragment['instructions'][0]['va']),16)-0x180000000
            for offset in range(0,len(expected),4096):
                chunk=expected[offset:offset+4096]
                if read(address+offset,len(chunk))!=chunk:raise ValueError('XP1 combat live code changed: '+name)
    for table,slot,target in p['slots']:
        if read(core._handle+table+slot,8)!=(core._handle+target).to_bytes(8,'little'):
            raise ValueError('XP1 combat virtual target changed')
    backend._xp1_combat_source=identity
    return p


def predicate_selection(core_sha256,retained,proof):
    if core_sha256==XP2_CORE_SHA256:
        from .xp2_combat_event_source import predicate_selection as select_xp2
        return select_xp2(core_sha256,retained,proof)
    ensure_source(core_sha256)
    if core_sha256==BASE_CORE_SHA256:return (*retained,proof)
    p=verify_source();a=p['predicate'];body=_body(p['functions']['predicate'])
    getter=b''.join(bytes.fromhex(r['bytes']) for r in rows(p['functions']['state_getter']))
    selected={'core_captures':{'game_owner_predicate':body},
              'leaves':{'core_game_state_getter':{'raw_hex':getter.hex()}}}
    return a['game_table'],a['target'],a['state_getter'],a['state_global'],selected


@dataclass(frozen=True)
class PromotionLayout:
    methods:object
    slots:tuple
    map_table:int
    outer_table:int
    service_table:int


def promotion_layout(core_sha256,methods,slots):
    if core_sha256==BASE_CORE_SHA256:return PromotionLayout(methods,slots,0x81cfa0,0x79e020,0x7a01a8)
    if core_sha256==XP2_CORE_SHA256:
        from .xp2_combat_event_source import promotion_layout as select_xp2
        return select_xp2(core_sha256,methods,slots)
    ensure_source(core_sha256);p=verify_source()['promotion']
    if set(methods)!=set(p['methods']):raise ValueError('Promotion operation set changed')
    selected={name:(p['methods'][name],result,args) for name,(_,result,args) in methods.items()}
    return PromotionLayout(selected,tuple(p['slots']),p['map_table'],p['outer_table'],p['service_table'])


def promotion_proof(core_sha256,retained):
    if core_sha256==BASE_CORE_SHA256:return retained
    if core_sha256==XP2_CORE_SHA256:
        from .xp2_combat_event_source import promotion_proof as select_xp2
        return select_xp2(core_sha256,retained)
    ensure_source(core_sha256);f=verify_source()['functions']
    aliases={'outer_e0':'promotion_outer_e0','outer_release':'promotion_outer_release',
      'map_constructor':'promotion_map_constructor','map_destructor':'promotion_map_destructor',
      'map_lookup':'promotion_map_lookup','service_query':'promotion_service_query',
      'service_release':'promotion_service_release'}
    selected={}
    for name,key in aliases.items():
        body=_body(f[key])
        body['start_va']=body['fragments'][0]['instructions'][0]['va']
        selected[name]=body
    return {'core_functions':selected}


def validate_child_fields(core_sha256,values,scalar_keys):
    ensure_source(core_sha256)
    if core_sha256==XP2_CORE_SHA256:
        from .xp2_combat_event_source import validate_child_fields as validate_xp2
        return validate_xp2(core_sha256,values,scalar_keys)
    from .native.native_event_8256dbe1 import CHILD_SCALAR_KEYS
    from .native.native_combat_argument_snapshot import CHILD_BLOBS
    from .native.native_application_mirror import decode_scalar
    expected=set(CHILD_SCALAR_KEYS)|set(CHILD_BLOBS)
    if (type(values) is not dict or set(values)!=expected
            or frozenset(scalar_keys)!=frozenset(CHILD_SCALAR_KEYS)):
        raise ValueError('Combat child map is not the retained fourteen-field scalar/blob envelope')
    for key in CHILD_SCALAR_KEYS:
        decode_scalar(values[key],2)
    for key,tag in CHILD_BLOBS.items():
        raw=values[key]
        if type(raw) is not bytes or len(raw)!=24 or int.from_bytes(raw[:2],'little')!=tag:
            raise ValueError('Combat child blob differs from the retained native envelope')
        pointer=int.from_bytes(raw[8:16],'little')
        size=int.from_bytes(raw[16:20],'little')
        flags=int.from_bytes(raw[20:24],'little')
        if not pointer or size!=8 or flags!=553648129:
            raise ValueError('Combat child blob ownership differs from the retained native envelope')
    return None


def administrative_snapshot_policy(core_sha256):
    ensure_source(core_sha256)
    if core_sha256==XP2_CORE_SHA256:
        from .xp2_combat_event_source import administrative_snapshot_policy as policy_xp2
        return policy_xp2(core_sha256)
    return {}
