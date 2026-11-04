"""Engine selection for the retained application-configuration mirror.

The EXE dispatcher/prelude semantics are common evidence. Core methods are
selected separately by binary identity, with no inferred offset translation.
This module does not admit a saved-game engine or claim full EXE equivalence.
"""
from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
import hashlib
import struct
from pathlib import Path

from .configuration_profiles import (
    BASE_CORE_SHA256, XP1_CORE_SHA256, XP2_CORE_SHA256, configuration_abi, require_owner_profile,
    application_source, _source, _body, _copy,
)


@dataclass(frozen=True)
class MirrorABI:
    configuration: object
    argument_vtable_rva: int
    argument_getter_rva: int
    phase_key_rva: int
    allocator_get_rva: int
    variant_assign_rva: int
    successor_rva: int
    game_proof_sha256: str
    dispatch_proof_sha256: str
    copy_proof_sha256: str
    snapshot_proof_sha256: str
    tree_proof_sha256: str
    prelude_proof_sha256: str
    lifetime_proof_sha256: str
    live_inspection_sha256: str | None
    records_proof_sha256: str

    @property
    def methods(self):
        if self.configuration.core_sha256 == BASE_CORE_SHA256:
            from .native.native_game_value_prelude_mutation import METHODS
            return MappingProxyType(METHODS)
        if self.configuration.core_sha256 == XP2_CORE_SHA256:
            from .xp2_application_mirror_source import source
            return MappingProxyType(source()['method_rvas'])
        return MappingProxyType(_xp1_prelude_methods())


_BASE=MirrorABI(configuration_abi(BASE_CORE_SHA256),0x81D838,0x74C640,0x8BCC7C,
    0x74E850,0x747AE0,0x73B410,
    'eeea976faf3f7f72bb43e5ebd383c9255867d4d135bd6bf7a21d1ee16e89db82',
    'a1d97e29ebc593a4ec1a802900f21f0ed5be984eae54b2a5ecd2071ce39d404f',
    '3abc69a0ad859801ca5003a619c2e186e6f6434fa7384e29e175b748e15b6fa5',
    'eeea976faf3f7f72bb43e5ebd383c9255867d4d135bd6bf7a21d1ee16e89db82',
    '252feb7c4316173ec44d0a0f6481f7bf1641600790965377a1c2c8418827fa73',
    '9f52d302477069a8d595541054af83168906afa338d25d49e00acf00b6802313',
    '063fae97f0a77129e780a3cbc2ad80b29836ef87f07c80aa351dae0b5d451e78',
    '1b63af26fed98ff944729ac81eb5f83e296dd5c89103efb43d033e43033dcf3b',
    '0421e7df0cc5152a987c25f8e8f8ce0562fbd1ec09328fb69045bf5c4805c1cf')

MIRROR_SOURCE=('work/host-extensions/application-mirror-static/application-mirror-xp1-source-v1.json',
               '4701a0efa6af81b847d18d3cdedecaa9d7b5a9ff26ddc427059e87eef299eab2')
PRELUDE_SOURCE=('work/host-extensions/application-prelude-static/application-prelude-xp1-source-v1.json',
                '78b45cecb5d3099fa036e0756f79481745b8200a1dae03f9f536e0b144b9be54')
CONFIGURATION_TRANSITION=(
    'work/host-extensions/application-prelude-static/configuration-xp2-transition/configuration-xp2-transition-v2.json',
    'e001e17addfd9c8e01ef1bd513dbed85182c4f4360bff155487ba76f4a1c7b9e')


def _xp1_abi():
    source();_prelude_document()
    return MirrorABI(require_owner_profile(configuration_abi(XP1_CORE_SHA256)),
        0x93FE28,0x84C290,0x9F3D44,0x84A340,0x8473E0,0x83AFA0,
        MIRROR_SOURCE[1],MIRROR_SOURCE[1],MIRROR_SOURCE[1],PRELUDE_SOURCE[1],
        PRELUDE_SOURCE[1],PRELUDE_SOURCE[1],_BASE.lifetime_proof_sha256,None,
        configuration_abi(XP1_CORE_SHA256).application_proof_sha256)


def _xp2_abi():
    from . import xp2_application_mirror_source as xp2
    xp2.source()
    configuration=require_owner_profile(configuration_abi(XP2_CORE_SHA256))
    return MirrorABI(configuration,0xabf918,0x9a5da0,0xb8c424,0x989d0,0x9a1320,0x994d90,
        *(xp2.SOURCE[1] for _ in range(6)),_BASE.lifetime_proof_sha256,None,
        configuration.application_proof_sha256)


def _prelude_document():
    proof=_source(PRELUDE_SOURCE)
    if (proof['schema']!='civ6-host.application-prelude-xp1-static.v1'
            or proof['native_execution'] is not False
            or proof['images']['xp1']['sha256']!=XP1_CORE_SHA256):
        raise ValueError('XP1 prelude source identity differs')
    groups=(proof['contract']['examined_provider_slots'],proof['contract']['helper_callees'])
    if any(v['instruction_shape_equal'] is not True or v['cfg_topology_equal'] is not True
           for group in groups for v in group.values()):
        raise ValueError('XP1 prelude function comparison is incomplete')
    _prelude_reference_pins(proof)
    return proof


def _configuration_reference_pins(ref):
    """An exact reviewed transition, not permission to rehash future code.

    The v1 document still identifies its original Python bytes. Keep those
    bytes separately, and authenticate the installed owner independently.
    The frozen comparison projects only the exact XP2 guards; every remaining
    executable AST node, including all Base/XP1 paths, is identical.
    """
    from .paths import resource_root
    from .resource_resolution import resolve_path
    proof=_source(CONFIGURATION_TRANSITION)
    old='2e1b1c3e6802104452c8d1bbbe3c3f8c50500e74a8b73987b285ac506c6e7cd7'
    new='40873fe5e142781861e45f52fbfd08b7c7ff2e426c0f5e46265782eec7f34594'
    if (proof['schema']!='civ6-host.application-prelude.configuration-transition.v2'
            or proof['prelude_sha256']!=PRELUDE_SOURCE[1]
            or proof['source_ref_name']!='configuration_profile'
            or dict(ref)!=dict(proof['historical_reference']) or ref['sha256']!=old
            or proof['preserved_source']['sha256']!=old
            or dict(proof['current_source'])!={
                'module':'src/civ6_host/runtime/configuration_profiles.py','sha256':new}
            or proof['native_execution'] is not False
            or proof['original_proof_modified'] is not False
            or proof['comparison']['base_and_xp1_branches_identical'] is not True
            or proof['comparison']['other_module_nodes_identical'] is not True):
        raise ValueError('Prelude configuration source transition differs')
    historical=resolve_path(resource_root()/proof['preserved_source']['path']).resolve()
    current=Path(__file__).with_name('configuration_profiles.py').resolve()
    pins={str(historical):old,str(current):new,
          str(resolve_path(resource_root()/CONFIGURATION_TRANSITION[0]).resolve()):CONFIGURATION_TRANSITION[1]}
    prior=proof['prior_transition']
    if prior['sha256']!='730bb88d528d9813a994bcc81b0ca2e6501aacbf5b324a17ae24e8033d7d889f':
        raise ValueError('Prelude prior configuration transition differs')
    _source((prior['path'],prior['sha256']))
    pins[str(resolve_path(resource_root()/prior['path']).resolve())]=prior['sha256']
    for path,expected in pins.items():
        if hashlib.sha256(Path(path).read_bytes()).hexdigest()!=expected:
            raise ValueError('Prelude source dependency changed: '+path)
    return pins


def _prelude_reference_pins(proof):
    # References include original Python, not just JSON. Historical code is
    # read as proof bytes only; it is never imported or treated as JSON.
    from .paths import resource_root
    from .resource_resolution import resolve_path
    pins={}
    for name,ref in proof['source_refs'].items():
        if name=='configuration_profile':
            pins.update(_configuration_reference_pins(ref))
            continue
        path=resolve_path(resource_root()/ref['path']).resolve()
        if path.suffix=='.json':
            _source((ref['path'],ref['sha256']))
        elif hashlib.sha256(path.read_bytes()).hexdigest()!=ref['sha256']:
            raise ValueError('Prelude source dependency changed: '+str(path))
        pins[str(path)]=ref['sha256']
    return pins


def _xp1_prelude_methods():
    proof=_prelude_document()
    expected={'constructor':0x844460,'allocate':0x836AF0,'hash':0x845FB0,'integer':0x845E90,
        'owned_map':0x8461F0,'allocator_set':0x845B90,'allocator_get':0x84A340,
        'finish':0x84A6D0,'delete':0x844830,'lookup':0x8454F0,'notify':0x84A8A0,'tree_next':0x83AFA0}
    if {k:int(v['xp1_target_rva'],16) for k,v in proof['core_functions'].items()}!=expected:
        raise ValueError('XP1 prelude method profile differs')
    return expected


def prelude_source(core_sha256):
    if core_sha256==XP2_CORE_SHA256:
        from .xp2_application_mirror_source import prelude_source as selected
        return selected()
    if core_sha256!=XP1_CORE_SHA256:raise ValueError('No expansion prelude source for this engine')
    proof=_prelude_document();methods=_xp1_prelude_methods()
    refs=proof['source_refs']
    owner_ref=refs['xp1_provider_owner'];owner=_source((owner_ref['path'],owner_ref['sha256']))
    functions={name:_body(row['xp1']) for name,row in proof['contract']['helper_callees'].items()}
    functions.update({row['name']:_body(row['xp1']) for row in proof['contract']['examined_provider_slots'].values()})
    for key in ('constructor','base_constructor','destructor','deleting_destructor','base_destructor','allocator_setter'):
        functions[key]=_body(owner['live_bodies'][key])
    functions.update(allocator_get=mirror_body('provider_allocator'),lookup=mirror_body('lookup'),
                     integer_setter=mirror_body('source_scalar_setter'))
    # Every directly invoked method must have its exact XP1 instruction body.
    starts={int(f['instructions'][0]['va'],16)-0x180000000
            for b in functions.values() for f in b['fragments']}
    if not set(methods.values())<=starts:
        raise ValueError('XP1 prelude still lacks a directly invoked function body')
    return {'core_functions':functions,'source_sha256':PRELUDE_SOURCE[1],
            'method_rvas':methods,'static_only':True}


def lifetime_source(core_sha256):
    abi=mirror_abi(core_sha256)
    if core_sha256 not in (XP1_CORE_SHA256,XP2_CORE_SHA256):raise ValueError('No expansion lifetime source for this engine')
    from .native.native_game_value_prelude_mutation import verify_lifetime_source
    common=_copy(verify_lifetime_source())
    # The retained borrowed-success path performs no Core release. Its Base
    # empty temporary destructor is not called by the shared algorithm. XP1
    # failure does not run speculative cleanup; process exit retains unknown
    # allocations. Actual owned-map destruction remains the provider's job.
    common['core_functions']={}
    common[('xp1' if core_sha256==XP1_CORE_SHA256 else 'xp2')+'_primitive_source_sha256']=abi.prelude_proof_sha256
    common['loaded_game_shutdown_qualified']=False
    return common


def snapshot_sources(core_sha256):
    if core_sha256 not in (XP1_CORE_SHA256,XP2_CORE_SHA256):raise ValueError('No expansion snapshot source for this engine')
    from .native.native_game_value_prelude_snapshot import _sources
    common,keys,fields,root_key=_sources()
    owned=application_source(core_sha256)
    if tuple(row['hash'] for row in owned['player_keys'])!=keys:
        raise ValueError('Expansion player-key namespace differs from the common EXE prelude')
    common=_copy(common)
    common['core_functions']={'property_lookup':mirror_body('lookup',core_sha256=core_sha256)}
    return common,keys,fields,root_key


def inventory_source(core_sha256):
    proof=prelude_source(core_sha256)
    if 'tree_successor' not in proof['core_functions']:
        raise ValueError('Expansion recursive target inventory lacks native successor')
    return proof


def verify_prelude_live(base,read,*,core_sha256=XP1_CORE_SHA256):
    if core_sha256==XP2_CORE_SHA256:
        from .xp2_application_mirror_source import verify_live
        return verify_live(base,read,prelude_only=True)
    if core_sha256!=XP1_CORE_SHA256:raise ValueError('Unknown expansion prelude engine')
    proof=prelude_source(XP1_CORE_SHA256)
    for name,body in proof['core_functions'].items():
        for fragment in body['fragments']:
            for instruction in fragment['instructions']:
                raw=bytes.fromhex(instruction['bytes'])
                if read(base+int(instruction['va'],16)-0x180000000,len(raw))!=raw:
                    raise ValueError('Loaded XP1 prelude instruction differs: '+name)


def source_pins():
    from .paths import resource_root
    from .resource_resolution import resolve_path
    mirror=source();prelude=_prelude_document()
    refs=[{'path':r[0],'sha256':r[1]} for r in (MIRROR_SOURCE,PRELUDE_SOURCE)]
    refs.extend(mirror['references'].values())
    pins={str(resolve_path(resource_root()/r['path']).resolve()):r['sha256'] for r in refs}
    pins.update(_prelude_reference_pins(prelude))
    return pins


def source_dependencies(core_sha256=XP1_CORE_SHA256):
    """Run the selected mirror's source checks before any native worker starts."""
    if core_sha256==XP2_CORE_SHA256:
        from .xp2_application_mirror_source import source_dependencies as selected
        _xp2_abi().methods
        copy_source(core_sha256);dispatch_source(core_sha256)
        snapshot_sources(core_sha256);lifetime_source(core_sha256)
        pins=source_pins()  # Pinned common EXE algorithm ancestry is shared.
        pins.update(selected())
        return pins
    if core_sha256!=XP1_CORE_SHA256:
        raise ValueError('Expansion mirror dependencies require the exact XP1 engine')
    abi=_xp1_abi()
    abi.methods
    return source_pins()


def source():
    proof=_source(MIRROR_SOURCE)
    if (proof['schema']!='civ6_host.application_mirror_xp1.static.v1'
            or proof['native_execution'] is not False
            or proof['images']['xp1']['sha256']!=XP1_CORE_SHA256
            or proof['contract']['selector']['value']!=0x24084B20
            or any(c['all_normalized_instructions_identical'] is not True
                   for c in proof['comparisons'].values())):
        raise ValueError('XP1 application source contract differs')
    expected={'argument_vtable_rva':0x93FE28,'argument_getter_rva':0x84C290,
        'provider_vtable_rva':0x93F590,'lookup_rva':0x8454F0,
        'provider_allocator_rva':0x84A340,'variant_clone_assign_rva':0x8473E0,
        'variant_release_rva':0x847620,'outer_is_initialized_rva':0x4BD4A0,
        'inner_is_initialized_rva':0x3D1F0,'last_phase_key_rva':0x9F3D44,
        'last_phase_key':0x24084B20,'source_dispatch_rva':0x5174E0}
    if any(int(proof['profile'][k],16)!=v for k,v in expected.items()):
        raise ValueError('XP1 application address profile differs')
    if dict(proof['profile']['header'])!={'size':88,'vtable':0,'parent':8,'observer':16,'control':24,'allocator':32}:
        raise ValueError('XP1 application provider layout differs')
    for ref in proof['references'].values():_source((ref['path'],ref['sha256']))
    return proof


def _select(document,selector):
    for key in selector:document=document[key]
    return document


def mirror_body(name,*,core_sha256=XP1_CORE_SHA256):
    if core_sha256==XP2_CORE_SHA256:
        from .xp2_application_mirror_source import body
        return body(name)
    if core_sha256!=XP1_CORE_SHA256:raise ValueError('Unknown expansion mirror engine')
    proof=source();route=proof['profile']['live_body_sources'][name]
    if route['kind']=='local_body':
        return _body(_select(proof,route['selector']))
    if route['kind']!='referenced_body':raise ValueError('Unknown application body source')
    entry=proof['referenced_bodies'][route['key']]
    ref=proof['references'][entry['reference']]
    body=_body(_select(_source((ref['path'],ref['sha256'])),entry['selector']))
    instructions=[i for f in body['fragments'] for i in f['instructions']]
    raw=b''.join(bytes.fromhex(i['bytes']) for i in instructions)
    if (len(instructions)!=entry['instruction_count']
            or hashlib.sha256(raw).hexdigest()!=entry['instruction_bytes_sha256']):
        raise ValueError('Application referenced function differs: '+name)
    return body


def copy_source(core_sha256):
    if core_sha256 not in (XP1_CORE_SHA256,XP2_CORE_SHA256):raise ValueError('No expansion copy source for this engine')
    abi=mirror_abi(core_sha256)
    # Reuse the owned-provider source as well; no second cloning algorithm.
    owned=application_source(core_sha256)
    functions={name:mirror_body(name,core_sha256=core_sha256) for name in (
        'variant_clone_assign','variant_release','provider_allocator','lookup')}
    for name in ('variant_clone_assign','variant_release','lookup'):
        if core_sha256==XP1_CORE_SHA256 and functions[name]!=owned['core_functions'][name]:
            raise ValueError('Application mirror lost its shared owner body join: '+name)
        if core_sha256==XP2_CORE_SHA256:
            # Retained owner fragments carry additional bounded-CFG metadata.
            # Require every actual owner instruction at the same native VA in
            # the complete mirror capture, including its bytes and decoding.
            actual={i['va']:(i['bytes'],i['text']) for f in functions[name]['fragments'] for i in f['instructions']}
            retained={i['va']:(i['bytes'],i['text']) for f in owned['core_functions'][name]['fragments'] for i in f['instructions']}
            if not retained or any(actual.get(va)!=row for va,row in retained.items()):
                raise ValueError('XP2 mirror lost its native owner instruction join: '+name)
    return {'core_functions':functions,'source_sha256':abi.copy_proof_sha256}


def dispatch_source(core_sha256):
    if core_sha256 not in (XP1_CORE_SHA256,XP2_CORE_SHA256):raise ValueError('No expansion dispatcher source for this engine')
    from .native.native_application_mirror_dispatch import verify_source_evidence
    common=verify_source_evidence()  # Exact common EXE branch, not a Base native call.
    selected=lambda name:mirror_body(name,core_sha256=core_sha256)
    common['game']={'core_functions':{'argument_getter':selected('argument_getter'),
                                    'property_lookup':selected('lookup')}}
    common['setup']={'core_functions':{'outer_initialized':selected('outer_is_initialized'),
                                     'inner_initialized':selected('inner_is_initialized')}}
    common[('xp1' if core_sha256==XP1_CORE_SHA256 else 'xp2')+'_source_sha256']=mirror_abi(core_sha256).dispatch_proof_sha256
    copy_source(core_sha256)
    return common


def verify_live(base,read,*,core_sha256=XP1_CORE_SHA256):
    """Verify selected instruction paths and active selector before publication."""
    if core_sha256==XP2_CORE_SHA256:
        from .xp2_application_mirror_source import verify_live as selected
        return selected(base,read)
    if core_sha256!=XP1_CORE_SHA256:raise ValueError('Unknown expansion mirror engine')
    source()
    names=('variant_clone_assign','variant_release','provider_allocator','lookup',
        'argument_getter','argument_constructor','argument_destructor','argument_hash_setter',
        'source_dispatch','source_player_dispatch','outer_is_initialized','inner_is_initialized',
        'selector_initializer','selector_hash','key_crc_loop','provider_notify','source_scalar_setter')
    count=0
    for name in names:
        for fragment in mirror_body(name)['fragments']:
            for instruction in fragment['instructions']:
                raw=bytes.fromhex(instruction['bytes'])
                if read(base+int(instruction['va'],16)-0x180000000,len(raw))!=raw:
                    raise ValueError('Loaded XP1 application instruction differs: '+name)
                count+=1
    for table,slot,target in ((0x93FE28,0x68,0x84C290),(0x93F590,0x58,0x8454F0),
                               (0x93F590,0x20,0x84A340),(0x8A8DF0,0x38,0x4BD4A0)):
        if read(base+table+slot,8)!=struct.pack('<Q',base+target):
            raise ValueError('Loaded XP1 application virtual target differs')
    if read(base+0x9F3D44,4)!=struct.pack('<I',0x24084B20):
        raise ValueError('Loaded XP1 LAST_TURN_PHASE_TYPE selector differs')
    if read(base+0x9D3F70,1)!=b'\1':
        raise ValueError('XP1 application notification publication is disabled')
    verify_prelude_live(base,read)
    return {'source_sha256':MIRROR_SOURCE[1],'instructions_checked':count,
            'selector':0x24084B20,'saved_game_load_admitted':False}


def mirror_abi(core_sha256):
    if core_sha256 == BASE_CORE_SHA256:
        return _BASE
    if core_sha256 == XP1_CORE_SHA256:
        return _xp1_abi()
    if core_sha256 == XP2_CORE_SHA256:
        return _xp2_abi()
    raise ValueError('No qualified application-mirror ABI for this engine')


def owner_abi(owner, core_sha256):
    abi=mirror_abi(core_sha256)
    # Historical Base fixture owners predate the explicit engine field.
    actual=getattr(owner,'_configuration_abi',None)
    if actual is not abi.configuration and not (actual is None and core_sha256==BASE_CORE_SHA256):
        raise ValueError('Application mirror and configuration owner have different engine identities')
    return abi


def indexed_player(base,context,index,*,read,lookup,call,core_sha256):
    if core_sha256==BASE_CORE_SHA256:
        from .native.native_application_mirror_records import bounded_get_player_config
        return bounded_get_player_config(base,context,index,read=read,lookup=lookup)
    abi=mirror_abi(core_sha256)
    if type(index) is not int or not 0<=index<64:
        raise ValueError('Player record index is outside 0..63')
    from .native.native_configuration_finalization import _linked_snapshot
    # The shared reader validates the same fixed records, keys and submap
    # topology through the caller's checked native invocation path.
    state=_linked_snapshot(base,context,read,call,core_sha256=core_sha256)
    return {'index':index,'provider':state['descriptor'],'pointer':state['players'][index],
            'pointer_is_borrowed':True,'source_proof_sha256':abi.records_proof_sha256}


# Append to application_mirror_profiles.py; reuse its configuration owner/source helpers.
CIVILIZATION_SOURCE=('work/host-extensions/xp1-civilization-static/civilization-source-v1.json',
                     '1a4d856ae9d2742f4d01108c98246cbb9733f0f81bcf162826a76906557acacf')
XP2_CIVILIZATION_KEY_SOURCE=(
    'evidence/native-event-fa5b1159-query/e1816d452f11c2a1c85d26d14252cf99adbceaafd54d7a0b6500c0da2bf0b026.json',
    'e1816d452f11c2a1c85d26d14252cf99adbceaafd54d7a0b6500c0da2bf0b026')

def civilization_source(core_sha256):
    """Exact nonnullable getter plus the common EXE114D20 scalar contract."""
    if core_sha256==BASE_CORE_SHA256:
        from .native.native_application_property_copy import verify_source,PROOF_SHA256
        original=verify_source(core_sha256=BASE_CORE_SHA256)
        return {'core_functions':{'value_getter':original['core_functions']['value_getter']},
                'getter_rva':0x745dc0,'source_sha256':PROOF_SHA256}
    if core_sha256==XP2_CORE_SHA256:
        # The key is selected by the shared EXE initializer, not by a guessed
        # XP2 Core callsite. Bind that initializer and its literal to the exact
        # XP2 +0x68 provider getter before selecting either source.
        from . import xp2_application_mirror_source as xp2
        from .configuration_profiles import require_owner_profile
        app=xp2.source()
        key_proof=_source(XP2_CIVILIZATION_KEY_SOURCE)
        expected_exe='e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63'
        init=key_proof['captures']['exe']['civilization_type_id_key_initializer']
        literal=key_proof['captures']['exe']['civilization_type_id_key_literal']
        rows={i['va']:i for f in init['fragments'] for i in f['instructions']}
        crc_text='CIVILIZATION_TYPE_ID'
        import zlib
        key=zlib.crc32(crc_text.encode('ascii')) ^ 0xffffffff
        abi=require_owner_profile(configuration_abi(XP2_CORE_SHA256))
        getter=xp2.body('nonnullable_getter')
        getter_start=int(getter['fragments'][0]['start_rva'],16)
        if (key_proof['schema']!='civ6rl.native_event_fa5b1159_query.v1'
            or key_proof['images']['exe_sha256']!=expected_exe
            or key_proof['registration']['callback_va']!='0x140140ff0'
            or key_proof['query3_config_key']['initializer']!='EXE 0x1400052D0 hashes ASCII key CIVILIZATION_TYPE_ID via 0x1407A0DA0 and stores the DWORD at global 0x1422D7988.'
            or literal!={'va':'0x140fbaef8','text':crc_text}
            or tuple(rows.get('0x1400052d4',{}).get('rip_targets',()))!=('0x140fbaef8',)
            or rows.get('0x1400052db',{}).get('text')!='call 0x1407a0da0'
            or tuple(rows.get('0x1400052e0',{}).get('rip_targets',()))!=('0x1422d7988',)
            or key!=0xc7d7515b
            or abi.core_sha256!=XP2_CORE_SHA256 or abi.vtable_rva!=0xabf080
            or abi.vtable_rva!=configuration_abi(core_sha256).vtable_rva
            or getter_start!=0x99f680
            or app['contract']['provider_nonnullable_sentinel_rva']!=0xb90808):
            raise ValueError('XP2 civilization getter/EXE key source join differs')
        return {'core_functions':{'value_getter':getter},'getter_rva':0x99f680,
                'sentinel_rva':0xb90808,'variant_size':24,'key':key,
                'source_sha256':xp2.SOURCE[1],
                'exe_key_source_sha256':XP2_CIVILIZATION_KEY_SOURCE[1]}
    if core_sha256!=XP1_CORE_SHA256:raise ValueError('Unknown civilization getter engine')
    proof=_source(CIVILIZATION_SOURCE)
    expected={'vtable_rva':0x93f590,'slot':0x68,'getter_rva':0x845600,
              'sentinel_rva':0x9f7bd8,'variant_size':24,'key':3352777051}
    if (proof['schema']!='civ6_host.xp1_civilization_getter_source.v1'
        or proof['image']['sha256']!=XP1_CORE_SHA256 or proof['native_execution'] is not False
        or any(proof['profile'][name]!=value for name,value in expected.items())
        or proof['validation']['existing_getter_instructions_match_exact_xp1_pe'] is not True
        or configuration_abi(core_sha256).vtable_rva!=expected['vtable_rva']):
        raise ValueError('XP1 civilization getter source identity differs')
    deps={name:_source((ref['path'],ref['sha256'])) for name,ref in proof['references'].items()}
    body=deps['getter']['live_xp1_bodies']['0x68']
    if (deps['getter']['xp1_sha256']!=XP1_CORE_SHA256 or body['start_va']!='0x180845600'
        or body['length']!=0x49 or body['raw_sha256']!=proof['getter_body_sha256']
        or deps['common_read']['contract']['scalar_read_contract_114d20']!=proof['common_read_contract']):
        raise ValueError('Civilization getter/common decoder source join changed')
    return {'core_functions':{'value_getter':_body(body)},'getter_rva':expected['getter_rva'],
            'source_sha256':CIVILIZATION_SOURCE[1]}

def civilization_source_dependencies(core_sha256):
    """Private resource closure for this getter; no extra runtime implementation."""
    from .paths import resource_root
    from .resource_resolution import resolve_path
    if core_sha256==BASE_CORE_SHA256:
        reference=('evidence/native-application-property-copy/3abc69a0ad859801ca5003a619c2e186e6f6434fa7384e29e175b748e15b6fa5.json',
                   '3abc69a0ad859801ca5003a619c2e186e6f6434fa7384e29e175b748e15b6fa5')
        return {str(resolve_path(resource_root()/reference[0])):reference[1]}
    if core_sha256==XP2_CORE_SHA256:
        selected=civilization_source(core_sha256)
        from .xp2_application_mirror_source import source_dependencies as xp2_dependencies
        pins=xp2_dependencies()
        proof=_source(XP2_CIVILIZATION_KEY_SOURCE)
        pins[str(resolve_path(resource_root()/XP2_CIVILIZATION_KEY_SOURCE[0]).resolve())]=XP2_CIVILIZATION_KEY_SOURCE[1]
        if proof['images']['exe_sha256']!='e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63':
            raise ValueError('XP2 civilization EXE key image identity differs')
        return pins
    civilization_source(core_sha256)
    proof=_source(CIVILIZATION_SOURCE)
    refs=[{'path':CIVILIZATION_SOURCE[0],'sha256':CIVILIZATION_SOURCE[1]},*proof['references'].values()]
    return {str(resolve_path(resource_root()/ref['path'])):ref['sha256'] for ref in refs}
