"""Source-backed Gathering Storm selection for the shared religion choices."""

import struct
from . import xp2_religious_unit_operations_source as owner_source
from .a0_family_source import family_profile, verify_pinned_files
from .configuration_profiles import XP2_CORE_SHA256, _source
from .execution_images import _PROFILE
from .paths import resource_root
from .resource_resolution import resolve_path

SOURCE = (
    'work/x1trade/xp2-prophet-activation-source/'
    '02ef65a9a21426c56ca03377f9e7357ddc2f617c7ce055a0eeecbf2ee0aed228.json',
    '02ef65a9a21426c56ca03377f9e7357ddc2f617c7ce055a0eeecbf2ee0aed228',
)
ARCHIVE_SOURCE = (
    'work/x1trade/xp2-religious-chain-runtime-stage/'
    '3060c6160367b26f66e38590c96277a581b0a6fdfe35c5117fe4508a238e1b8a.json',
    '3060c6160367b26f66e38590c96277a581b0a6fdfe35c5117fe4508a238e1b8a',
)
_ENUMS = {
    'PlayerOperations.FOUND_RELIGION':0xa4daffb5,
    'PlayerOperations.ADD_BELIEF':0xf8828e24,
    'PlayerOperations.PARAM_RELIGION_TYPE':0x22a25b8b,
    'PlayerOperations.PARAM_BELIEF_TYPE':0xa44b2907,
    'PlayerOperations.PARAM_INSERT_MODE':0xac2fdc09,
    'PlayerOperations.VALUE_EXCLUSIVE':0x97fea5c6,
}
_MAIN_BINDINGS = {
    'Player.GetReligion':'0x6a9ee0',
    'PlayerReligion.GetReligionTypeCreated':'0x6b3780',
    'PlayerReligion.HasReligiousFoundingUnit':'0x6b3820',
    'PlayerReligion.GetNumBeliefsEarned':'0x6b3690',
    'PlayerReligion.GetHolyCityID':'0x6b3650',
    'Game.GetReligion':'0x69c170',
    'GameReligion.GetReligions':'0x6a0350',
}
_PLAN = {
    'prophet': 'prophet',
    'foundation': 'found_religion',
    'beliefs': 'add_belief',
}
_CITY = 0x305c2e09
_CAMERA = 0xb6b48d9c
_SPECIAL_EVENTS = {0xc1300ee7:'foundation',0xb3495127:'placement'}
_PLAYER_PARAMETER_KEYS = {
    0x9671c7d1:frozenset((0xa44b2907,0xac2fdc09)),
    _ENUMS['PlayerOperations.FOUND_RELIGION']:frozenset((0x22a25b8b,0xac2fdc09)),
    _ENUMS['PlayerOperations.ADD_BELIEF']:frozenset((0xa44b2907,0xac2fdc09)),
}
_PLAYER_HEADER = struct.Struct('<6I')
_PLAYER_ENTRY = struct.Struct('<IHH10sI')


def supports(reference,image):
    return owner_source.supports(reference,image)


def verify_source():
    proof = _source(SOURCE)
    image = proof['image']
    if (proof['schema'] != 'civ6-host.xp2-prophet-and-religion-chain-source.static.v1'
            or (image['profile_id'],image['sha256'],image['reference_abi_sha256']) !=
                (_PROFILE.id,_PROFILE.image_sha256,XP2_CORE_SHA256)
            or any(proof['scope'][name] is not False for name in (
                'native_execution','process_memory_read','product_modified','bbg_native_scope_qualified'))
            or proof['scope']['exact_stock_and_recovered_bbg751_sources'] is not True
            or {key:row['u32'] for key,row in proof['player_enums'].items()} != _ENUMS
            or any(proof['ui_bindings'][key]['callback_rva'] != rva
                   for key,rva in _MAIN_BINDINGS.items())
            or proof['city_no_callback']['kind'] != hex(_CITY)
            or proof['city_no_callback']['callers'] != ('0x66a8cf','0x6f5d50')
            or proof['installed_ui']['vanilla_religion_screen_not_replaced_in_selected_expansion_or_bbg_modinfo'] is not True):
        raise ValueError('Installed Gathering Storm religious chain source differs')
    slots = proof['callable_vtables']['prophet_operation']['target_rvas']
    if (slots[2],slots[8],slots[14:16]) != ('0x66a270','0x66a720',('0x3ef70','0x13230')):
        raise ValueError('Gathering Storm founding unit dispatcher differs')
    for row in proof['selected_capture_rows'].values():
        op = row['operation_definition']
        if ((op['type'],op['hash_u32'],op['ordinal'],op['visible_in_ui'],op['interface_mode']) !=
                ('UNITOPERATION_FOUND_RELIGION',0xc72fe8fb,15,True,None)):
            raise ValueError('Gathering Storm founding unit definition differs')
    return proof


def _archive_source(proof):
    archive = _source(ARCHIVE_SOURCE)
    if (archive['schema'] != 'civ6-host.xp2-religion-archive-source.static.v1'
            or archive['parent']['sha256'] != SOURCE[1]
            or archive['image']['sha256'] != proof['image']['sha256']
            or archive['wire']['exact_extent'] != _PLAYER_HEADER.size+2*_PLAYER_ENTRY.size
            or archive['native_execution'] is not False or archive['process_memory_read'] is not False):
        raise ValueError('Gathering Storm religion map archive source differs')
    return archive


def _event_rows(proof, family=None):
    return tuple(row for row in proof['external_events']
                 if family is None or _PLAN[family] in row['action'].split(','))


def require_actions(family=None):
    """Check identified receivers against existing source profiles."""
    from .foundation_event_profile import event_profile
    from .native.native_absent_305c2e09 import verify_source_evidence as verify_city
    from .native.native_event_b6b48d9c import verify_source_evidence as verify_camera
    from .native.native_host_event_registry import EXE_EVENT_CALLBACKS
    from .xp2_initial_choice_source import source as player_operations_source
    from .xp2_placement_event_source import RECORDS

    proof = verify_source()
    if family in (None, 'foundation', 'beliefs'):
        # Numeric keys use the existing XP2 CanStart/Request ABI.
        player_operations_source('research')
        _archive_source(proof)
    if family in (None, 'prophet'):
        verify_camera()
        verify_city()
    profiles = {
        'shared':family_profile().record_types_by_kind,
        'foundation':event_profile(core_sha256=XP2_CORE_SHA256,
                                   execution_image=_PROFILE).record_types_by_kind,
        'placement':{kind:tuple(record for record,_ in rows) for kind,rows in RECORDS.items()},
    }
    for row in _event_rows(proof,family):
        kind,record = int(row['kind'],16),row['record']
        records = profiles[_SPECIAL_EVENTS.get(kind,'shared')].get(kind)
        if record is None:
            if kind not in (_CITY,_CAMERA) or kind in EXE_EVENT_CALLBACKS or records != frozenset():
                raise ValueError('Gathering Storm religion absent-receiver profile differs')
        elif records is None or record not in records:
            raise ValueError('Unqualified Gathering Storm religious notification: '+row['kind'])
    return proof


def source_dependencies(image, *, reference, family=None):
    from .xp2_initial_choice_source import source_dependencies as player_dependencies

    if not supports(reference,image):
        raise ValueError('Gathering Storm religion dependencies need the exact captured profile and image')
    proof = verify_source() if family == 'observation' else require_actions(family)
    profile,_ = owner_source._selection(reference)
    selected = proof['selected_capture_rows'][profile]
    pins = owner_source.source_dependencies(reference)
    ui = proof['installed_ui']
    rows = [dict(path=p,sha256=h) for p,h in (SOURCE,ARCHIVE_SOURCE)]
    rows.extend((*proof['source_refs'][1:],proof['image'],
            selected['database'],*selected['own_ui_host'].values(),ui['religion_screen'],
            *ui['unit_panel_delegation'][:4]))
    if profile == 'xp2-bbg751':
        rows.extend((*ui['unit_panel_delegation'][4:],proof['bbg']['selected_gameplay'],proof['bbg']['ui_bridge']))
    additional = {
        str(resolve_path(resource_root()/row['path']).resolve(strict=True)):row['sha256']
        for row in rows
    }
    groups = [additional]
    if family in (None,'foundation','beliefs'):
        groups.append(player_dependencies('research',execution_image=image))
    for group in groups:
        for path,digest in group.items():
            if pins.setdefault(path,digest) != digest:
                raise ValueError('Gathering Storm religion source dependency conflict')
    verify_pinned_files(pins)
    return pins


def verify_live(base,read):
    from .xp1_religious_unit_operations_source import _verify_spans

    proof = verify_source()
    spans = [span for body in proof['code_spans'].values() for span in body['fragments']]
    spans.extend(proof['data_spans'].values())
    spans.extend(row[key] for group in ('ui_bindings','player_enums')
                 for row in proof[group].values() for key in ('registration','literal'))
    archive = _archive_source(proof)
    spans.extend(span for body in archive['spans'].values() for span in body['fragments'])
    _verify_spans(base,read,spans)
    map_table = base+int(archive['vtable']['rva'],16)
    for slot,target in archive['vtable']['slots'].items():
        expected = (base+int(target,16)).to_bytes(8,'little')
        if read(map_table+int(slot,16),8) != expected:
            raise ValueError('Live Gathering Storm religion archive serializer table differs')
    for row in proof['callable_vtables'].values():
        expected = b''.join((base+int(target,16)).to_bytes(8,'little') for target in row['target_rvas'])
        if read(base+int(row['rva'],16),len(expected)) != expected:
            raise ValueError('Live Gathering Storm religion callable table differs')


def bind_prefix(prefix, *, family=None, action=False):
    from .xp1_saved_load_logger import XP2_SOURCE as logger_source

    owner_source.bind_prefix(prefix)
    backend,consumer = prefix.backend,prefix.event_arguments.consumer
    core = backend.core
    life = (core,core._handle,prefix,prefix.runtime)
    previous = getattr(prefix,'_xp2_religious_chain_lifetime',None)
    if previous is None:
        verify_live(core._handle,backend.runtime.read)
        prefix._xp2_religious_chain_lifetime = life
    elif previous != life:
        raise ValueError('Gathering Storm religion source belongs to another saved lifetime')
    if action:
        proof = require_actions(family)
        if (consumer._foundation_backend is not backend
                or getattr(backend,'_xp2_load_logger_activation',{}).get('source_sha256') != logger_source[1]):
            raise ValueError('Gathering Storm religion needs its own notification and logger owners')
        prefix.actions.require_transition()
        for row in _event_rows(proof,family):
            kind,record = int(row['kind'],16),row['record']
            if not consumer.handles_kind(kind) or (record is not None and not consumer.handles_record(record)):
                raise ValueError('Gathering Storm religion notification owner is missing: '+row['kind'])


def verify_player_archive(payload,pid,operation,parameters):
    """Authenticate the selected numeric archive before giving it to the Core FIFO."""
    if (type(payload) is not bytes or type(pid) is not int or not 0 <= pid < 64
            or type(operation) is not int or operation not in _PLAYER_PARAMETER_KEYS
            or type(parameters) is not dict or set(parameters) != _PLAYER_PARAMETER_KEYS[operation]
            or any(type(key) is not int or type(value) is not int or not 0 <= value <= 0xffffffff
                   for key,value in parameters.items())
            or parameters[0xac2fdc09] != 0x97fea5c6
            or len(payload) != _PLAYER_HEADER.size+2*_PLAYER_ENTRY.size
            or _PLAYER_HEADER.unpack_from(payload) != (0xc45de12f,pid,operation,0,0x80000001,2)):
        raise ValueError('Gathering Storm religion player-operation archive header differs')
    actual = {}
    for key,name_length,tag,variant_flags,value in _PLAYER_ENTRY.iter_unpack(payload[_PLAYER_HEADER.size:]):
        if name_length != 0 or tag != 2 or variant_flags != bytes(10) or key in actual:
            raise ValueError('Gathering Storm religion player-operation archive entry differs')
        actual[key] = value
    if actual != parameters:
        raise ValueError('Gathering Storm religion player-operation archive values differ')