"""XP2 district damage/combat source selection for the existing EXE transport.

Queries and their item leases are preserved. The preceding 754 unit/district
notification keeps its initial A0 membership and its existing scalar codec.
"""
from dataclasses import dataclass
from functools import lru_cache
import hashlib
from types import MappingProxyType
from .configuration_profiles import XP2_CORE_SHA256, _source

SOURCE=('work/host-extensions/xp2-district-damage-static/source-profile-v1.json',
        'aaf4638cde90ddad03f2387637712da5f26827cac418a402404db154ba6f62b5')
KINDS=MappingProxyType({0xf74afc79:0x9f,0x47261a7d:0xa1})
SIZES=MappingProxyType({0x9f:144,0xa1:128})
SIBLING_KIND=0x754cbd1b
SIBLING_KEYS=frozenset((0xa1e5a149,0xf0548bb7,0xf343dc5a))
CALLBACKS=MappingProxyType({0xf74afc79:0x145120,0x47261a7d:0x144fd0,SIBLING_KIND:0x1573e0})
POLICY='shared-native-query-and-fifo'
_SHAPES={0xf74afc79:{0xa1e5a149:3,0xf343dc5a:1024,0xd6fcf3e4:2,0xa1fbc372:2},
         0x47261a7d:{0xa1e5a149:3,0xf343dc5a:1024},
         SIBLING_KIND:{0xa1e5a149:3,0xf0548bb7:1024,0xf343dc5a:1024}}
_EXE='e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63'


def _texts(p,name):
    base=0x180000000 if name.startswith('core_') else 0x140000000
    return {int(r['rva'],16) if 'rva' in r else int(r['va'],16)-base:r['text']
            for f in p['functions'][name]['capture']['fragments'] for r in f['instructions']}


def _verify(p):
    from .xp2_turn_event_profile import fragments
    from .native.native_host_event_registry import EXE_EVENT_CALLBACKS
    from .foundation_facade_profiles import query_abi
    from .paths import resource_root
    if (p['schema']!='civ6-host.xp2-district-damage.source.v1'
            or p['native_execution'] is not False or p['process_memory_read'] is not False
            or p['images']['core']['sha256']!=XP2_CORE_SHA256 or p['images']['exe']['sha256']!=_EXE
            or p['contract']['policy']!=POLICY or p['contract']['omission_admitted'] is not False
            or p['contract']['core_internal_dispatch_before_host'] is not True
            or p['contract']['normalizer_return']!=0
            or set(p['families'])!={hex(k) for k in CALLBACKS}
            or set(p['contract']['new_membership'])!={hex(k) for k in KINDS}):
        raise ValueError('XP2 district source identity or transport contract changed')
    for body in p['functions'].values():
        raw=b''.join(raw for _,raw in fragments(body))
        if (len(raw)!=body['bytes'] or hashlib.sha256(raw).hexdigest()!=body['sha256']
                or body['complete_unwind'] is not True
                or body['capture']['boundary_method']!='complete-runtime-function-chained-unwind-root-v2'):
            raise ValueError('XP2 district complete body changed')
    # The retained EXE virtual callsites, not guessed Core function names, are
    # the authority for the selected player/collection/district slot contract.
    required={
      'exe_0x147640':{0x147670:'call qword ptr [rax + 0xb8]',0x147689:'call qword ptr [rax + 0x130]',
        0x14769b:'call qword ptr [rax + 0x10]',0x1476a7:'call qword ptr [rax + 8]',0x1476b0:'call qword ptr [rax + 8]'},
      'exe_0x145120':{0x1451af:'call 0x140147640',0x1451c7:'call qword ptr [rax + 0x30]',
        0x1451e9:'call qword ptr [rax + 0x38]',0x1451f9:'call qword ptr [rax + 0x20]',
        0x145208:'call qword ptr [rax + 0x58]',0x145254:'call 0x1401353f0',0x145281:'call qword ptr [rax + 8]'},
      'exe_0x144fd0':{0x145054:'call 0x140147640',0x145074:'call qword ptr [rax + 0x30]',
        0x145095:'call qword ptr [rax + 0x20]',0x1450e4:'call 0x1401356b0',0x145111:'call qword ptr [rax + 8]'},
      'core_0x193000':{0x19302b:'cmp ebp, 0x5e97d629',0x193033:'cmp ebp, 0x6da56a3d',
        0x19306b:'cmp ebx, esi',0x193072:'je 0x1801930d1',0x193093:'mov dword ptr [rsp + 0x20], 0xf74afc79',
        0x1930a0:'mov dword ptr [rsp + 0x24], ebp',0x1930a4:'mov r9d, ebx',0x1930a7:'mov r8d, esi',
        0x1930ae:'mov eax, 3',0x1930cc:'call 0x1805fb9d0'},
      'core_0x1915f0':{0x191620:'movsx r8d, byte ptr [rax + 0x1c]',0x191625:'mov eax, 3',
        0x19162a:'mov word ptr [rdi + 2], ax',0x19162e:'mov eax, dword ptr [rbx + 0xa0]',
        0x191639:'mov dword ptr [rdi + 4], eax',0x19163f:'mov word ptr [rdi], r8w'},
      'core_0x15fc10':{0x15fda7:'mov eax, 1',0x15fdac:'mov qword ptr [rsp + 0x30], 0x754cbd1b',
        0x15fdb5:'mov word ptr [rbp + 0x122], ax',0x15fdc8:'call 0x1801915f0',0x15fddc:'call 0x1805fae50',
        0x16011d:'mov dword ptr [rbp + 0x110], 0x47261a7d',0x16012a:'mov dword ptr [rbp + 0x114], 0x599feed4',
        0x160134:'call 0x1801915f0',0x160143:'call 0x1805fb000'},
      'core_0x5fb9d0':{0x5fba21:'mov edx, 0xa1e5a149',0x5fba26:'call 0x1809a0000',
        0x5fba49:'cmp ax, 3',0x5fba4f:'mov edx, 0xf343dc5a',0x5fba8b:'mov r8d, 0x400',
        0x5fba91:'mov dword ptr [rsp + 0x20], 8',0x5fba99:'call qword ptr [rax + 0xb0]',
        0x5fbaa7:'mov edx, 0xd6fcf3e4',0x5fbaac:'call 0x18099fee0',
        0x5fbab9:'mov edx, 0xa1fbc372',0x5fbabe:'call 0x18099fee0'},
      'core_0x5fb000':{0x5fb052:'cmp ax, 3',0x5fb058:'mov edx, 0xf343dc5a',
        0x5fb094:'mov r8d, 0x400',0x5fb09a:'mov dword ptr [rsp + 0x20], 8',
        0x5fb0b5:'mov edx, 0xa1e5a149',0x5fb0ba:'call 0x1809a0000',0x5fb103:'or eax, 0xffffffff'},
      'core_0x5fae50':{0x5fae95:'mov edx, 0xa1e5a149',0x5fae9a:'call 0x1809a0000',0x5faeaa:'call 0x1805fa5e0'},
      'core_0x5fa5e0':{0x5fa604:'mov esi, 0xf0548bb7',0x5fa60e:'mov r14d, 0xf343dc5a',
        0x5fa614:'cmp ax, 1',0x5fa636:'mov edx, 0xf0548bb7',0x5fa64c:'mov esi, 0x8753bb21',
        0x5fa732:'cmp ax, 3',0x5fa738:'mov edx, r14d',0x5fa749:'mov r8d, 0x400',
        0x5fa75a:'mov dword ptr [rsp + 0x20], 8',0x5fa762:'call qword ptr [rax + 0xb0]'},
      'core_0x9a0000':{0x9a0079:'mov dword ptr [rbx], 3',0x9a008f:'mov dword ptr [rsp + 0x30], 3'},
      'core_0x99fee0':{0x99ff59:'mov dword ptr [rbx], 2',0x99ff6f:'mov dword ptr [rsp + 0x30], 2'},
      'exe_0x1ca2d0':{0x1ca74b:'cmp ecx, 0xf343dc5a',0x1ca77f:'mov word ptr [rbp - 0x11], cx',
        0x1ca783:'mov dword ptr [rbp - 0xd], edx',0x1ca7bd:'call 0x1401445f0',0x1ca7ca:'xor eax, eax'},
      'exe_0x1573e0':{0x1574de:'call 0x140127f30',0x1574fb:'call 0x1409898c0'},
    }
    for name,rows in required.items():
        actual=_texts(p,name)
        if any(actual.get(address)!=text for address,text in rows.items()):
            raise ValueError('XP2 district typed producer/query correspondence changed: '+name)
    for name in ('core_0x5fb9d0','core_0x5fb000','core_0x5fae50'):
        text=list(_texts(p,name).values())
        if not text.index('call 0x18007c670')<text.index('call qword ptr [rax + 0xa0]')<text.index('call 0x18099e5d0'):
            raise ValueError('XP2 district internal dispatch/map lifetime order changed')
    specifications={0xf74afc79:(0x1353f0,0x9f,144),0x47261a7d:(0x1356b0,0xa1,128),SIBLING_KIND:(0x127f30,0x1e,112)}
    for kind,(writer,record,size) in specifications.items():
        family=p['families'][hex(kind)]
        if (EXE_EVENT_CALLBACKS.get(kind)!=CALLBACKS[kind] or family['callback_rva']!=hex(CALLBACKS[kind])
                or (family['writer_rva'],family['record_type'],family['record_size'])!=(hex(writer),record,size)
                or {int(k,16):v for k,v in family['fields'].items()}!=_SHAPES[kind]):
            raise ValueError('XP2 district callback/typed-field/record membership changed')
        if not {'mov dword ptr [rbx], '+hex(size),'mov dword ptr [rbx + 4], '+hex(record)} <= set(_texts(p,'exe_'+hex(writer)).values()):
            raise ValueError('XP2 district FIFO writer identity changed')
    sibling=p['families'][hex(SIBLING_KIND)]
    if (sibling['selector']!=0 or tuple(sibling['normalized_second_unit'])!=(65535,1,4294967295)
            or sibling['extra_query'] is not False or sibling['notification_counters_read'] is not False
            or sibling['notification_counters_written'] is not False):
        raise ValueError('XP2 district sibling normalized sentinel/counter contract changed')
    abi=query_abi(XP2_CORE_SHA256,resource_root())
    operations={'get_player':('outer',0xb8),'release_player':('player',8),'player_districts':('player',0x130),
        'release_collection':('district_collection',8),'district_by_id':('district_collection',0x10),
        'release_district':('district',8),'district_city_descriptor':('district',0x30),
        'district_type':('district',0x20),'district_position':('district',0x38),'district_hash':('district',0x58)}
    if set(p['query_operations'])!=set(operations):raise ValueError('XP2 district query family changed')
    for name,(table,slot) in operations.items():
        actual=dict(abi.operations[name],table_rva=abi.table(table))
        if (dict(p['query_operations'][name])!=actual or actual['table']!=table or actual['slot']!=slot):
            raise ValueError('XP2 district EXE-authoritative query slot changed')
    return p


@lru_cache(maxsize=1)
def source():
    from .native import native_event_f74afc79 as damage,native_event_47261a7d as combat,native_event_754cbd1b_city as sibling
    p=_verify(_source(SOURCE))
    damage.verify_source_evidence();combat.verify_source_evidence();sibling.verify_source_evidence()
    return p


verify_source=source


def source_dependencies():
    from .paths import resource_root
    from .resource_resolution import resolve_path
    from .a0_family_source import verify_pinned_files
    from .foundation_facade_profiles import source_dependencies as query_dependencies
    p=source();pins=query_dependencies(core_sha256=XP2_CORE_SHA256)
    for ref in [dict(path=SOURCE[0],sha256=SOURCE[1]),p['generator'],*p['references'].values(),*p['images'].values()]:
        path=str(resolve_path(resource_root()/ref['path']).resolve())
        if path in pins and pins[path]!=ref['sha256']:raise ValueError('XP2 district source dependency conflict')
        pins[path]=ref['sha256']
    verify_pinned_files(pins)
    return pins


def core_fragments():
    from .xp2_turn_event_profile import fragments
    for body in source()['functions'].values():
        if body['image']=='xp2':
            for address,raw in fragments(body):yield address-0x180000000,raw


def verify_live(base,read):
    count=0
    for rva,raw in core_fragments():
        for offset in range(0,len(raw),4096):
            expected=raw[offset:offset+4096];actual=read(base+rva+offset,len(expected))
            if type(actual) is not bytes or actual!=expected:raise ValueError('XP2 district live source bytes changed')
            count+=1
    return count


def verify_once(core,read):
    from .foundation_facade_profiles import verify_xp1_once
    from .paths import resource_root
    base=core._handle;key=(base,SOURCE[1])
    if getattr(core,'_xp2_district_damage_verified',None)==key:return
    verify_xp1_once(core,base,read,resource_root(),core_sha256=XP2_CORE_SHA256)
    verify_live(base,read)
    core._xp2_district_damage_verified=key


@lru_cache(maxsize=1)
def event_profile():
    from .a0_family_source import A0FamilyProfile
    from .native.native_deferred_empty_profile import resolve_empty_receiver_row
    p=source()
    for record in (*SIZES,0x1e):
        expected=p['receiver_rows'][hex(record)];actual=resolve_empty_receiver_row(record)
        if (actual is None or set(actual['record_sizes'])!={expected['record_size']}
                or actual['handler_va']!=hex(0x140000000+int(expected['handler_rva'],16))
                or actual['handler_body_sha256']!=expected['handler_body_sha256']):
            raise ValueError('XP2 district receiver row changed')
    return A0FamilyProfile(MappingProxyType({kind:frozenset((record,)) for kind,record in KINDS.items()}),SIZES,SOURCE[1])


@dataclass(frozen=True)
class VerifiedSource:
    owner:object
    core:object
    base:int
    proof_sha256:str


def bind_owner(owner,core,read):
    owner.check_thread()
    if owner.core is not core or owner.load_abi.core_sha256!=XP2_CORE_SHA256:
        raise ValueError('XP2 district source owner mismatch')
    old=getattr(owner,'_xp2_district_damage_source',None)
    if old is not None and (type(old) is not VerifiedSource or old.owner is not owner or old.core is not core
            or old.base!=core._handle or old.proof_sha256!=SOURCE[1]):
        raise ValueError('XP2 district source lifetime changed')
    source_dependencies();verify_once(core,read)
    if old is None:owner._xp2_district_damage_source=VerifiedSource(owner,core,core._handle,SOURCE[1])
    return event_profile()


def decode_fields(kind,fields,read):
    import struct
    from .native import native_event_f74afc79 as damage,native_event_47261a7d as combat,native_event_754cbd1b_city as sibling
    source()
    if (type(kind) is not int or kind not in _SHAPES or type(fields) is not dict or set(fields)!=set(_SHAPES[kind])
            or any(type(k) is not int or type(raw) is not bytes or len(raw)!=24
                   or struct.unpack_from('<H',raw)[0]!=_SHAPES[kind][k] for k,raw in fields.items())):
        raise ValueError('XP2 district typed argument shape differs')
    return {0xf74afc79:damage,0x47261a7d:combat,SIBLING_KIND:sibling}[kind].decode_fields(fields,read)


def validate_sibling_owner(owner,raw_fields):
    """Qualify only the already-registered 754 unit/district scalar branch."""
    from .a0_family_service import A0FamilyService
    from .xp1_continuation import SavedContinuation
    if type(owner) is not A0FamilyService:raise ValueError('XP2 district sibling needs the actual A0 owner')
    owner._check()
    backend=owner._foundation_backend;token=owner._foundation_borrow
    receipt=getattr(backend,'_xp2_district_damage_source',None)
    if (backend is None or type(token) is not SavedContinuation or token.owner is not backend
            or getattr(backend,'_xp1_continuation',None) is not token or owner.active_kind!=SIBLING_KIND
            or backend.load_abi.core_sha256!=XP2_CORE_SHA256 or backend.core is not owner.deferred.core
            or owner.arguments.reader.core_sha256!=XP2_CORE_SHA256 or owner.deferred.cache_core_sha256!=XP2_CORE_SHA256
            or backend.context!=owner.deferred.context or backend.host is not owner.arguments.host
            or owner.district_damage_profile is not event_profile()
            or type(receipt) is not VerifiedSource or receipt.owner is not backend or receipt.core is not backend.core
            or receipt.base!=backend.core._handle or receipt.proof_sha256!=SOURCE[1]):
        raise ValueError('XP2 district sibling source or continuation owner changed')
    token.check(active=True)
    decode_fields(SIBLING_KIND,raw_fields,owner.read)
    return SOURCE[1]


__all__=['SOURCE','KINDS','SIZES','CALLBACKS','POLICY','SIBLING_KIND','SIBLING_KEYS','source','verify_source',
    'source_dependencies','core_fragments','verify_live','verify_once','event_profile','bind_owner','VerifiedSource',
    'decode_fields','validate_sibling_owner']
