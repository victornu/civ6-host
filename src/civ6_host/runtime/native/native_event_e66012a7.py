"""E66012A7 active-context producer with a native non-wonder query guard.

The native manager+14F8/+5400 context predicate is not inferred from headless
execution. The configured active-game profile preserves its conditional query;
the still-unimplemented wonder effects are refused without a training claim.
"""
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import ctypes as C
import hashlib
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
import struct
from civ6_host.runtime.native import native_event_07c83dae as snapshot
from civ6_host.runtime.native.native_application_mirror import decode_scalar
from civ6_host.runtime.native.native_feature_visibility_event import _copy_blob
from civ6_host.runtime.native.native_source_cache import load_pinned_json
EVENT_KIND = 3865055911
RECORD_TYPES, RECORD_SIZES = ((169, 166), (128, 144))
SELECTORS = frozenset((3434534334, 2046345331))
DIAGNOSTIC_ONLY = True
PINNED_EVIDENCE_SHA256 = '438979c637a2f619fe859ac783f9b0dc851bec20ff0089a2f222df482d3f2a60'
_PROOF = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_event_e66012a7.py')))).resolve().parents[1] / 'evidence/native-event-e66012a7' / f'{PINNED_EVIDENCE_SHA256}.json'

def verify_source_evidence():
    proof = load_pinned_json(_PROOF, PINNED_EVIDENCE_SHA256)
    if proof['schema'] != 'civ6rl.native_event_e66012a7.static.v2' or proof['registration']['callback_va'] != '0x14013fd70' or proof['images']['exe_sha256'] != snapshot.shared.EXE_SHA256 or (proof['images']['core_sha256'] != snapshot.shared.CORE_SHA256) or (proof['shared_snapshot']['sha256'] != snapshot.PINNED_EVIDENCE_SHA256) or ([r['type'] for r in proof['contract']['records']] != ['0xa9', '0xa6']) or (proof['eligible_for_training'] is not False):
        raise RuntimeError('E66012A7 source identity changed')
    return proof

@dataclass(frozen=True)
class EventFields:
    position_bytes: bytes
    x: int
    y: int
    descriptor_bytes: bytes
    owner: int
    identifier: int
    selector: int
    value: int
    second_value: int

def _fields(fields):
    if not isinstance(fields, EventFields) or type(fields.position_bytes) is not bytes or len(fields.position_bytes) != 8 or (type(fields.descriptor_bytes) is not bytes) or (len(fields.descriptor_bytes) != 8) or (type(fields.x) is not int) or (type(fields.y) is not int) or (struct.unpack('<ii', fields.position_bytes) != (fields.x, fields.y)) or (type(fields.owner) is not int) or (struct.unpack_from('<h', fields.descriptor_bytes)[0] != fields.owner) or (type(fields.identifier) is not int) or (struct.unpack_from('<I', fields.descriptor_bytes, 4)[0] != fields.identifier):
        raise ValueError('E66012A7 requires consistent current position and descriptor bytes')
    for value in (fields.selector, fields.value, fields.second_value):
        if type(value) is not int or not 0 <= value <= 4294967295:
            raise ValueError('E66012A7 scalar must be uint32')
    if fields.selector not in SELECTORS:
        raise ValueError('E66012A7 selector is outside the two-record profile')
    if fields.x <= -9999 or fields.y <= -9999:
        raise ValueError('E66012A7 second query coordinate branch is not admitted')

def decode_fields(raw_fields, read):
    verify_source_evidence()
    if not isinstance(raw_fields, dict) or set(raw_fields) != {594779970, 2353434172, 2716180809, 2717631346, 3606901732}:
        raise ValueError('E66012A7 requires exactly descriptor,position,selector,D6,A1FBC')
    selector = decode_scalar(raw_fields[2716180809], 3)
    value = decode_scalar(raw_fields[3606901732], 2)
    second = decode_scalar(raw_fields[2717631346], 2)
    position = _copy_blob(raw_fields[2353434172], read, 0)
    descriptor = _copy_blob(raw_fields[594779970], read, 1024)
    fields = EventFields(position, *struct.unpack('<ii', position), descriptor, struct.unpack_from('<h', descriptor)[0], struct.unpack_from('<I', descriptor, 4)[0], selector, value, second)
    _fields(fields)
    return fields

def _profile(first_sequence, fields, active_context_present, normalizer_transform_present, thread_hook_present, writer_metadata_callback_present, padding_policy):
    verify_source_evidence()
    _fields(fields)
    if active_context_present is not True:
        raise ValueError('E66012A7 requires explicit active matching manager context; headless is not an absence proof')
    if normalizer_transform_present is not False or thread_hook_present is not False or writer_metadata_callback_present is not False:
        raise ValueError('E66012A7 requires explicitly absent transforms/hooks/metadata callbacks')
    if type(first_sequence) is not int or not 1 <= first_sequence <= 4294967294:
        raise ValueError('E66012A7 requires room for two consecutive nonzero uint32 sequences')
    if padding_policy != 'zero':
        raise ValueError('E66012A7 requires explicit zero source stack padding')

def _encode(index, sequence, fields, values):
    ranges = {'owner': (-128, 127), 'city_id': (0, 4294967295), 'district_id': (0, 4294967295), 'flag148': (0, 255)}
    if not isinstance(values, dict) or set(values) != set(ranges):
        raise ValueError('E66012A7 requires complete native snapshot values')
    for name, (low, high) in ranges.items():
        if type(values[name]) is not int or not low <= values[name] <= high:
            raise ValueError('InvalidE66012A7 native value ' + name)
    record = bytearray(RECORD_SIZES[index])
    struct.pack_into('<IIII', record, 0, len(record), RECORD_TYPES[index], sequence, 0)
    record[16:24] = b'\xff' * 8
    record[24:64] = bytes.fromhex('ffff0000ffffffff') * 5
    struct.pack_into('<I', record, 80, sequence)
    record[88:96] = fields.position_bytes
    struct.pack_into('<HHI', record, 96, fields.owner & 65535, 2, fields.identifier)
    struct.pack_into('<HHI', record, 104, values['owner'] & 65535, 3, values['district_id'])
    record[112] = values['flag148']
    struct.pack_into('<I', record, 116, fields.value)
    if index == 0:
        struct.pack_into('<I', record, 120, fields.second_value)
    else:
        struct.pack_into('<iI', record, 120, fields.owner, fields.second_value)
    return bytes(record)

def encode_records(first_sequence, fields, first_values, second_values, *, active_context_present, normalizer_transform_present, thread_hook_present, writer_metadata_callback_present, padding_policy):
    _profile(first_sequence, fields, active_context_present, normalizer_transform_present, thread_hook_present, writer_metadata_callback_present, padding_policy)
    return (_encode(0, first_sequence, fields, first_values), _encode(1, first_sequence + 1, fields, second_values))

@contextmanager
def _district_type_hash(core, context, owner, identifier, *, read=None, native_api=None, core_sha256='d7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'):
    """Keep district/service references alive through the native hash guard."""
    if core_sha256 not in ('d7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3', '259b90a473a256aff6a7d621a4f3717e46f6921c59b9817475375c88b97e8c83', '324c51e9ea3531758842e16c69e6cddbefbb226c5b675c3d6e60111646c2e98c'):
        raise ValueError('Unqualified facade engine')
    from civ6_host.runtime.foundation_facade_profiles import query_abi, verify_xp1_once, select_tables
    from civ6_host.runtime.provenance import resource_root
    _foundation_abi = query_abi(core_sha256, None if core_sha256 == 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3' else resource_root())
    proof = verify_source_evidence()
    if type(owner) is not int or not -128 <= owner <= 127 or type(identifier) is not int or (not 0 <= identifier <= 4294967295):
        raise ValueError('E66012A7 district descriptor must come from the native snapshot')
    base = int(core._handle)
    if read is None:
        from civ6_host.runtime.native.native_setup import local_reader
        read = local_reader()
    if native_api is None:
        if core_sha256 == 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3':
            for pin in proof['core_district_query']['runtime_code_pins']:
                if hashlib.sha256(read(base + int(pin['rva'], 16), pin['size'])).hexdigest() != pin['sha256']:
                    raise ValueError('E66012A7 district query Core code changed')
        else:
            verify_xp1_once(core, base, read, resource_root(), core_sha256=core_sha256)
        api = {'get_player': C.WINFUNCTYPE(C.c_void_p, C.c_void_p, C.c_int32)(base + _foundation_abi.rva('get_player')), 'get_collection': C.WINFUNCTYPE(C.c_void_p, C.c_void_p)(base + _foundation_abi.rva('player_districts')), 'get_district': C.WINFUNCTYPE(C.c_void_p, C.c_void_p, C.c_uint32)(base + _foundation_abi.rva('district_by_id')), 'release_player': C.WINFUNCTYPE(None, C.c_void_p)(base + _foundation_abi.rva('release_player')), 'release_collection': C.WINFUNCTYPE(None, C.c_void_p)(base + _foundation_abi.rva('release_collection')), 'release_district': C.WINFUNCTYPE(None, C.c_void_p)(base + _foundation_abi.rva('release_district')), 'snapshot78': C.WINFUNCTYPE(C.c_uint64, C.c_void_p, C.c_void_p)(base + _foundation_abi.rva('district_snapshot78')), 'outer_service': C.WINFUNCTYPE(C.c_void_p, C.c_void_p)(base + _foundation_abi.rva('outer_service')), 'get_type_hash': C.WINFUNCTYPE(C.c_uint32, C.c_void_p, C.c_uint32)(base + _foundation_abi.rva('service_district_type_hash')), 'release_service': C.WINFUNCTYPE(None, C.c_void_p)(base + _foundation_abi.rva('release_service'))}
    else:
        api = native_api
        if not isinstance(api, dict) or set(api) != {'get_player', 'get_collection', 'get_district', 'release_player', 'release_collection', 'release_district', 'snapshot78', 'outer_service', 'get_type_hash', 'release_service'} or any((not callable(f) for f in api.values())):
            raise ValueError('E66012A7 district seam requires all ten native operations')

    def check(pointer, table, slots):
        if not pointer or int.from_bytes(read(pointer, 8), 'little') != base + table:
            raise ValueError('UnexpectedE66012A7 native district interface')
        for offset, target in slots:
            if int.from_bytes(read(base + table + offset, 8), 'little') != base + target:
                raise ValueError('E66012A7 district virtual slot changed')
    check(context, _foundation_abi.table('outer'), ((184, _foundation_abi.rva('get_player')), (256, _foundation_abi.rva('outer_service'))))
    player = api['get_player'](context, owner)
    if not player:
        yield None
        return
    district = 0
    player_validated = False
    try:
        check(player, _foundation_abi.table('player'), ((8, _foundation_abi.rva('release_player')), (304, _foundation_abi.rva('player_districts'))))
        player_validated = True
        collection = api['get_collection'](player)
        if not collection:
            raise ValueError('E66012A7 null collection would be dereferenced by the source')
        collection_validated = False
        try:
            check(collection, _foundation_abi.table('district_collection'), ((8, _foundation_abi.rva('release_collection')), (16, _foundation_abi.rva('district_by_id'))))
            collection_validated = True
            district = api['get_district'](collection, identifier)
        finally:
            if collection_validated:
                api['release_collection'](collection)
    finally:
        if player_validated:
            api['release_player'](player)
    if not district:
        yield None
        return
    district_validated = False
    try:
        check(district, _foundation_abi.table('district'), ((8, _foundation_abi.rva('release_district')), (120, _foundation_abi.rva('district_snapshot78'))))
        district_validated = True
        if not int.from_bytes(read(district + 8, 8), 'little'):
            raise ValueError('E66012A7 district+78 requires a live underlying object')
        size, guard = (20, b'\x9b' * 16)
        storage = C.create_string_buffer(len(guard) * 2 + size)
        output = C.addressof(storage) + len(guard)
        C.memmove(C.addressof(storage), guard, len(guard))
        C.memset(output, 165, size)
        C.memmove(output + size, guard, len(guard))
        api['snapshot78'](district, output)
        if storage.raw[:16] != guard or storage.raw[-16:] != guard:
            raise ValueError('E66012A7 district snapshot exceeded its0x14-byte output')
        type_index = struct.unpack('<I', C.string_at(output + 12, 4))[0]
        service = api['outer_service'](context)
        if not service:
            raise ValueError('E66012A7 null type service would be dereferenced by the source')
        service_validated = False
        try:
            check(service, _foundation_abi.table('type_service'), ((8, _foundation_abi.rva('release_service')), (224, _foundation_abi.rva('service_district_type_hash'))))
            service_validated = True
            value = api['get_type_hash'](service, type_index)
            if type(value) is not int or not 0 <= value <= 4294967295:
                raise ValueError('E66012A7 native district type hash must be uint32')
            yield {'type_index': type_index, 'type_hash': value}
        finally:
            if service_validated:
                api['release_service'](service)
    finally:
        if district_validated:
            api['release_district'](district)

def produce_records(first_sequence, core, context, fields, *, active_context_present, normalizer_transform_present, thread_hook_present, writer_metadata_callback_present, padding_policy='zero', read=None, native_api=None, district_query_api=None, diagnostics=None, record_sink=None, wonder_handler=None, core_sha256='d7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'):
    """Perform both source queries separately and return orderedA9,A6 records.

    First plot lives throughA9 encoding; second plot is released beforeA6
    encoding. Active-context CCB6/progress>=100 performs its third plot query,
    district snapshot and native type hash lookup. Wonder effects require an
    explicitly supplied source-backed handler. With record_sink, enqueueing
    follows source query/release order; any later failure is fatal, never a
    rollback or permission to retry the action in this native context.
    """
    if core_sha256 not in ('d7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3', '259b90a473a256aff6a7d621a4f3717e46f6921c59b9817475375c88b97e8c83', '324c51e9ea3531758842e16c69e6cddbefbb226c5b675c3d6e60111646c2e98c'):
        raise ValueError('Unqualified facade engine')
    _profile(first_sequence, fields, active_context_present, normalizer_transform_present, thread_hook_present, writer_metadata_callback_present, padding_policy)
    if diagnostics is not None and type(diagnostics) is not list:
        raise ValueError('E66012A7 diagnostics sink must be a list')
    if record_sink is not None and (not callable(record_sink)):
        raise ValueError('E66012A7 record sink must be callable')
    if wonder_handler is not None and (not callable(wonder_handler) or record_sink is None):
        raise ValueError('E66012A7 wonder handler requires a source-ordered record sink')
    query_fields = dict(position_bytes=fields.position_bytes, x=fields.x, y=fields.y, selector=fields.selector, source_value=fields.second_value, descriptor_tail=fields.value)
    with snapshot.plot_snapshot(core, context, query_fields, read=read, native_api=native_api, core_sha256=core_sha256) as first_values:
        first = _encode(0, first_sequence, fields, first_values)
        if record_sink is not None:
            record_sink(first)
    with snapshot.plot_snapshot(core, context, query_fields, read=read, native_api=native_api, core_sha256=core_sha256) as second_values:
        second_values = dict(second_values)
    second = _encode(1, first_sequence + 1, fields, second_values)
    if record_sink is not None:
        record_sink(second)
    additional = ()
    if fields.selector == 3434534334 and C.c_int32(fields.second_value).value >= 100:
        with snapshot.plot_snapshot(core, context, query_fields, read=read, native_api=native_api, core_sha256=core_sha256) as third_values:
            with _district_type_hash(core, context, third_values['owner'], third_values['district_id'], read=read, native_api=district_query_api, core_sha256=core_sha256) as result:
                if diagnostics is not None:
                    diagnostics.append({'active_context_present': True, 'district_owner': third_values['owner'], 'district_identifier': third_values['district_id'], 'district_present': result is not None, 'native_type_index': None if result is None else result['type_index'], 'native_type_hash': None if result is None else result['type_hash']})
                if result is not None and result['type_hash'] == 1660007689:
                    if core_sha256 == '324c51e9ea3531758842e16c69e6cddbefbb226c5b675c3d6e60111646c2e98c':
                        from civ6_host.runtime.xp2_wonder_completion import source
                        source()
                    elif core_sha256 != 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3':
                        raise ValueError('XP1 wonder AE/AF/application effects require a separately qualified handler')
                    if wonder_handler is None:
                        raise ValueError('E66012A7 native wonder hash0x62F1B509 requires AE/AF and application effects')
                    additional = wonder_handler(first_sequence + 2, fields, dict(third_values), record_sink)
                    if type(additional) is not tuple or len(additional) != 2 or [struct.unpack_from('<I', r, 4)[0] for r in additional] != [174, 175]:
                        raise ValueError('E66012A7 wonder handler returned an invalid ordered pair')
    return (first, second) + additional
