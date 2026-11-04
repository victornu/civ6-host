"""Pinned XP2 source selection for the existing capability and options owners.

Only metadata lives here. Private code bodies remain in the laboratory. The
97-row closed registry and explicit Performance settings do not admit a game.
"""
import hashlib
from pathlib import Path

from .configuration_profiles import _source, _body, _copy, configuration_abi
from .saved_load_profiles import XP2_CORE_SHA256
from .resource_resolution import resolve_path
from .native.native_source_cache import _freeze

SOURCE = ('work/host-extensions/xp2-load-options-capabilities/source-profile-v1.json',
          'd1b1e8e45d8a322f880c4a6679c3d0db5ccd0c10fcb5e74d59df9ee125cbb064')
CAPTURE_SHA = 'f816f181fafe52ab0de45b1694c4eeb64a38cd4d371e6c3db580c42a20550b36'
EXE_SHA = 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63'
SETTINGS = dict(MaxJobThreads=2, MaxGameCoreThreads=1, GameCoreReserveThreads=0,
                MaxGameCoreUnitMovementThreads=1, MaxGameCoreTradeRouteThreads=1)
KEYS = (0x7ec3df64, 0xc181eb6e, 0xe09781a7)


def source():
    p = _source(SOURCE)
    if (p['schema'] != 'civ6-host.xp2-load-options-capabilities-profile.v1'
            or p['native_execution'] is not False or p['core_sha256'] != XP2_CORE_SHA256
            or p['exe_sha256'] != EXE_SHA or p['source']['sha256'] != CAPTURE_SHA
            or p['host_global_rva'] != 0xb8aa80):
        raise ValueError('XP2 options/capability source identity differs')
    c, o, m = (p[k] for k in ('capabilities', 'performance_options', 'parameter_map'))
    abi = configuration_abi(XP2_CORE_SHA256)
    if (m['bytes'] != 88 or m['vtable_rva'] != abi.vtable_rva
            or m['constructor_rva'] != abi.constructor_rva or m['destructor_rva'] != abi.destructor_rva
            or m['lookup_rva'] != abi.lookup_rva or m['uint_setter_rva'] != abi.uint_setter_rva
            or m['get_rva'] != 0x99f680 or m['slots'] != {'0x58':0x99f570,'0x68':0x99f680,'0x130':0x99fee0}
            or c['host_slot'] != 0x168 or c['abi'] != 'uint32(host*, uint32 player, uint32 capability)'
            or tuple(c['result_domain']) != (0,1,2) or c['admitted_capability_count'] != 97
            or c['configuration']['mode_key_rva'] != 0xb8c44c
            or c['configuration']['root_key_rva'] != abi.root_key_rva
            or c['configuration']['allowed_mode'] != 0x0138409a):
        raise ValueError('XP2 capability/provider ABI differs')
    hashes = frozenset(r['hash_u32'] for r in c['catalogue_rows'])
    extension = c['closed_registry_extension']
    if (len(c['catalogue_rows']) != 97 or len(hashes) != 97
            or hashes != frozenset(c['admitted_capability_hashes'])
            or len(extension['additional_rows']) != 5 or extension['base_overlap_count'] != 92
            or tuple(extension['numeric_candidates']) != () or tuple(extension['restricted_hash_intersection']) != ()
            or extension['result_for_admitted_hash'] != 1 or extension['open_world_registry_supported'] is not False
            or (extension['fixed_input_count'],extension['present_input_count'],extension['absent_input_count']) != (65,35,30)):
        raise ValueError('XP2 capability closed registry extension differs')
    if (o['host_slot'] != 0x158 or o['abi'] != 'borrowed ParameterMap*(host*, uint32 domain)'
            or o['domain'] != 0xfbb4e6a9 or tuple(o['keys']) != KEYS
            or o['input_kind'] != 'explicit_host_configuration' or dict(o['settings']) != SETTINGS
            or o['derived']['effective_engine_threads'] != 3
            or {int(k):v for k,v in o['derived']['values'].items()} != dict.fromkeys(KEYS,1)
            or o['captured_gameplay_state'] is not False or o['automatic_hardware_detection_supported'] is not False):
        raise ValueError('XP2 explicit Performance policy differs')
    capture = _source((p['source']['path'], CAPTURE_SHA))
    if capture['images']['xp2']['sha256'] != XP2_CORE_SHA256 or capture['images']['exe']['sha256'] != EXE_SHA:
        raise ValueError('XP2 options/capability image source differs')
    return p


def source_dependencies():
    from .lan_capabilities import SOURCE_PINS as LAN_SOURCE_PINS
    from .native.native_host_capability_status import CATALOGUE_SHA256
    from .paths import resource_root
    p = source()
    refs = [dict(path=SOURCE[0],sha256=SOURCE[1]), p['source'], *p['references'].values()]
    refs.extend(dict(path=path, sha256=digest) for path, digest in LAN_SOURCE_PINS.values())
    refs.extend((
        dict(path=f'evidence/native-capability-catalogue/{CATALOGUE_SHA256}.json',
             sha256=CATALOGUE_SHA256),
        dict(path='evidence/native-game-mode.json',
             sha256='6eb08daedc9c59f09c8d38a53bac51372a866482ede3af9adeb84ae37dbf6ead'),
    ))
    # Values are pinned at the existing owner boundary, not on every callback.
    return {str(resolve_path(resource_root()/r['path']).resolve()):r['sha256'] for r in refs}


def verify_dependency(path, digest):
    if Path(path).suffix == '.json':
        _source((path,digest))
    elif hashlib.sha256(Path(path).read_bytes()).hexdigest() != digest:
        raise ValueError('XP2 options/capability dependency changed')


def _function(capture, p, name):
    if name in capture['functions']:
        row = capture['functions'][name]
    else:
        r = p['references']['preload_source']
        row = _source((r['path'],r['sha256']))['functions'][name]
    _body(row['body'])
    body = _copy(row['body'])
    for fragment in body['fragments']:
        for instruction in fragment['instructions']:
            if 'rva' in instruction:
                va = hex(0x180000000+int(instruction['rva'],16))
                if instruction.get('va',va) != va:
                    raise ValueError('XP2 source address representations disagree')
                instruction['va'] = va
    return body


def capability_profile():
    p = source(); c = p['capabilities']; conf = c['configuration']
    capture = _source((p['source']['path'],CAPTURE_SHA))
    names = ('capability_constructor','capability_catalogue_loader','capability_object_getter',
             'inner_capability_getter','capability_refresh_thunk','capability_cached_query',
             'capability_find','capability_vector_dedup','capability_vector_resize','setup_getter',
             'nullable_getter','nonnullable_getter','game_mode_initializer','player_configuration')
    proof = dict(catalogue_rows=c['catalogue_rows'], configuration_vtable_rva=conf['vtable_rva'],
                 slots={hex(slot):{'target_rva':conf[key]} for slot,key in ((0x58,'lookup_rva'),(0x68,'get_rva'))},
                 xp1_mode_key_initializer={'global_rva':conf['mode_key_rva']},
                 live_xp1_bodies={name:_function(capture,p,name) for name in names},
                 contract=dict(mode_required=conf['allowed_mode'],game_root_key=conf['root_key'],
                     game_root_key_rva=conf['root_key_rva'],mode_key=conf['mode_key'],
                     fixed_input_count=65,present_input_count=35,registry_domain=0x62d100f0),
                 selected_core_sha256=XP2_CORE_SHA256, source_reference=SOURCE)
    caller = dict(caller=_function(capture,p,'capability_refresh'),host_global_rva=p['host_global_rva'])
    return _freeze(proof),_freeze(caller)


def performance_profile():
    p = source(); capture = _source((p['source']['path'],CAPTURE_SHA)); m = p['parameter_map']
    consumers = {key:_function(capture,p,name) for key,name in (('unit','unit_pathing_option'),('trade','trade_pathing_option'))}
    # Preserve the existing owner/verifier shape; this is selected native code,
    # not rewriting XP1 instructions or normalizing an unidentified callee.
    contract = dict(map_vtable_rva=m['vtable_rva'],constructor_rva=m['constructor_rva'],
                    destructor_rva=m['destructor_rva'],slots=m['slots'],host_global_rva=p['host_global_rva'])
    owner = dict(contract=contract, xp1_consumer=consumers['unit'],
                 xp1_dispatch=_function(capture,p,'options_dispatch'),
                 xp1_numeric_setter=_function(capture,p,'set_uint32'),
                 xp1_owner_bodies={name:_function(capture,p,name) for name in ('map_constructor','map_base_constructor','map_destructor')},
                 xp1_getter_bodies={name:_function(capture,p,name) for name in ('nullable_getter','nonnullable_getter')},
                 profile=p['performance_options']['settings'],selected_core_sha256=XP2_CORE_SHA256)
    owner['xp1_owner_bodies']['trade_consumer'] = consumers['trade']
    return _freeze(dict(consumers=consumers,input_kind='explicit_host_configuration',source_reference=SOURCE)),_freeze(owner)


def performance_select(borrower, root, xp1_source):
    core = getattr(getattr(getattr(borrower,'backend',None),'profile',None),'core_sha256',None)
    if core == XP2_CORE_SHA256:
        return performance_profile()[1]
    from .saved_load_profiles import XP1_CORE_SHA256
    if core not in (None,XP1_CORE_SHA256):
        raise ValueError('Unknown Performance borrower profile')
    return xp1_source(root)
