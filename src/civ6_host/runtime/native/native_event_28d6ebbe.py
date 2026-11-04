"""Source-bounded producer for EXE event28D6EBBE and its type9E record."""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import ctypes as C
from contextlib import contextmanager
from dataclasses import dataclass
import struct
from pathlib import Path
from civ6_host.runtime.native.native_application_mirror import decode_scalar
from civ6_host.runtime.native.native_host_events import copy_eight_byte_variant
from civ6_host.runtime.native.native_source_cache import load_pinned_json
from civ6_host.runtime.native.native_event_827289e6 import query_optional_position
EVENT_KIND, RECORD_TYPE, RECORD_SIZE = (685173694, 158, 144)
SELECTOR_KEY, VALUE_KEY, DESCRIPTOR_KEY = (2716180809, 3606901732, 4081310810)
OPTIONAL_VALUE_KEY, OPTIONAL_PAIR_KEY = (2717631346, 1532339015)
OPTIONAL_SCALAR_KEY, IGNORED_PLAYER_KEY = (955421384, 4033489650)
_BASIC_KEYS = {SELECTOR_KEY, VALUE_KEY, DESCRIPTOR_KEY}
_EXTENDED_KEYS = _BASIC_KEYS | {OPTIONAL_VALUE_KEY, OPTIONAL_PAIR_KEY, OPTIONAL_SCALAR_KEY, IGNORED_PLAYER_KEY}
PINNED_EVIDENCE_SHA256 = '8f43e7f814cff05e714cbe9d0329d571a3051213566c675814946320cf76b4f2'
_PROOF = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_event_28d6ebbe.py')))).resolve().parents[1] / 'evidence/native-event-28d6ebbe' / f'{PINNED_EVIDENCE_SHA256}.json'
POSITIVE_PROOF_SHA256 = 'f3cf82b25b45bd407284e31954ff8b9601b85f3b414ad72fb495b8c1dc421719'
_POSITIVE_PROOF = _PROOF.parents[1] / 'native-event-28d6ebbe-positive' / f'{POSITIVE_PROOF_SHA256}.json'
_EXE_SHA = 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63'
_CORE_SHA = 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'
_GUARD = bytes.fromhex('785dac043bed6209fabc552789031ca6')
_DEFAULT_PAIR = struct.pack('<HHI', 65535, 0, 4294967295)
_TABLES = {'outer': (7987232, ((184, 4382880),)), 'player': (7992320, ((8, 4421040), (304, 4422336))), 'collection': (7993256, ((8, 4427952), (16, 4427984))), 'item': (7990216, ((8, 4406960), (32, 4372864), (48, 4407024), (56, 4407328)))}

def verify_source_evidence():
    doc = load_pinned_json(_PROOF, PINNED_EVIDENCE_SHA256)
    if doc.get('schema') != 'civ6rl.native_event_28d6ebbe.static.v2' or doc['images'] != {'exe_sha256': _EXE_SHA, 'core_sha256': _CORE_SHA} or doc['registration']['callback_va'] != '0x1401453e0' or (doc['captures']['0x1401453e0']['code_sha256'] != '515e96fb37d1261f045f3415bb36d614e3310d0b47df3ca99cb80f7322ac45be') or (doc['captures']['0x1401351e0']['code_sha256'] != '4ae426bb732427766c28f3d564b446b788808b00a18102a5ecc37bd3e0cda42c') or (doc['captures']['0x140147f10']['code_sha256'] != '3508a888d8362682654e408bccd9dda3d4cdddc13961264d873de6010676d27d') or (doc['captures']['0x1401ca2d0']['code_sha256'] != 'c757d2f0c927f36e058ff5e57350a80beac1db2a89d3940fcb5e89c05545f23e'):
        raise RuntimeError('Pinned28D6EBBE source identity changed')

def verify_positive_source_evidence():
    doc = load_pinned_json(_POSITIVE_PROOF, POSITIVE_PROOF_SHA256)
    if doc.get('schema') != 'civ6rl.native_event_28d6ebbe_positive.static.v1' or doc.get('images') != {'exe_sha256': _EXE_SHA, 'core_sha256': _CORE_SHA} or doc['sources']['28d_v2']['sha256'] != PINNED_EVIDENCE_SHA256 or (doc['sources']['positive_query']['sha256'] != '1881a3beb1d4e9038871d20905ee19b2dc1da6b67db06efc61a29bd961a84292') or (doc['captures']['optional_query']['code_sha256'] != '3508a888d8362682654e408bccd9dda3d4cdddc13961264d873de6010676d27d') or (doc['contract']['record_changes'] != {'D6_dword_unchanged_at_record': 120, 'optional_position8_at_record': 124, 'pair5B55_8_at_record': 136, 'scalar38F_dword_at_record': 132}):
        raise RuntimeError('Pinned28D6EBBE positive query order or layout changed')

@dataclass(frozen=True)
class EventFields:
    selector: int
    value: int
    descriptor_bytes: bytes
    owner: int
    item_id: int
    input_shape: str = 'basic-three-field'
    optional_index: int | None = None
    optional_scalar: int | None = None
    ignored_player: int | None = None
    metadata_pair_bytes: bytes = _DEFAULT_PAIR

    @property
    def optional_fields_absent(self):
        return self.input_shape == 'basic-three-field'

@dataclass(frozen=True)
class NativeValues:
    item_variant: bytes
    item_raw: int
    position_bytes: bytes
    optional_position_bytes: bytes | None = None

def _fields(fields):
    if not isinstance(fields, EventFields) or type(fields.descriptor_bytes) is not bytes or len(fields.descriptor_bytes) != 8 or (type(fields.owner) is not int) or (not 0 <= fields.owner < 64) or (struct.unpack_from('<h', fields.descriptor_bytes)[0] != fields.owner) or (type(fields.item_id) is not int) or (not 0 <= fields.item_id <= 4294967295) or (struct.unpack_from('<I', fields.descriptor_bytes, 4)[0] != fields.item_id) or (type(fields.selector) is not int) or (fields.selector != 0) or (type(fields.value) is not int) or (not 0 <= fields.value <= 4294967295):
        raise ValueError('28D6EBBE requires a source descriptor, owner0..63, selector0 and DWORD value')
    if type(fields.metadata_pair_bytes) is not bytes or len(fields.metadata_pair_bytes) != 8:
        raise ValueError('28D6EBBE requires an exact eight-byte optional pair')
    optional = (fields.optional_index, fields.optional_scalar, fields.ignored_player)
    if fields.input_shape == 'basic-three-field':
        if fields.metadata_pair_bytes != _DEFAULT_PAIR or any((value is not None for value in optional)):
            raise ValueError('28D6EBBE basic input cannot inject optional fields')
    elif fields.input_shape == 'extended-seven-field':
        if any((type(value) is not int or not 0 <= value <= 4294967295 for value in optional)):
            raise ValueError('28D6EBBE extended input requires typed optional DWORDs')
    else:
        raise ValueError('28D6EBBE input shape is not source-backed')

def decode_fields(fields, read):
    verify_source_evidence()
    if not isinstance(fields, dict) or set(fields) not in (_BASIC_KEYS, _EXTENDED_KEYS):
        raise ValueError('28D6EBBE requires exactly three or seven fields; partial optional keys are refused')
    extended = set(fields) == _EXTENDED_KEYS
    descriptor = copy_eight_byte_variant(fields[DESCRIPTOR_KEY], read, expected_tag=1024)
    result = EventFields(decode_scalar(fields[SELECTOR_KEY], 3), decode_scalar(fields[VALUE_KEY], 2), descriptor, struct.unpack_from('<h', descriptor)[0], struct.unpack_from('<I', descriptor, 4)[0], 'extended-seven-field' if extended else 'basic-three-field', decode_scalar(fields[OPTIONAL_VALUE_KEY], 2) if extended else None, decode_scalar(fields[OPTIONAL_SCALAR_KEY], 2) if extended else None, decode_scalar(fields[IGNORED_PLAYER_KEY], 2) if extended else None, copy_eight_byte_variant(fields[OPTIONAL_PAIR_KEY], read, expected_tag=1024) if extended else _DEFAULT_PAIR)
    _fields(result)
    return result

def _profile(sequence, fields, notification_counter, notification_limit, per_thread_hook_present, writer_metadata_callback_present, padding_policy):
    verify_source_evidence()
    _fields(fields)
    if fields.optional_index is not None and fields.optional_index < 2147483648:
        verify_positive_source_evidence()
    if type(sequence) is not int or not 1 <= sequence <= 4294967295:
        raise ValueError('28D6EBBE requires a nonzero uint32 sequence')
    if type(notification_counter) is not int or notification_counter != 0 or type(notification_limit) is not int or (notification_limit != 0) or (per_thread_hook_present is not False) or (writer_metadata_callback_present is not False):
        raise ValueError('28D6EBBE counter/hook/writer-service profile is unsupported')
    if padding_policy != 'headless-zero-uninitialized-stack':
        raise ValueError('28D6EBBE requires an explicit zero policy for stack padding')

def encode_record(sequence, fields, values, *, notification_counter, notification_limit, per_thread_hook_present, writer_metadata_callback_present, padding_policy):
    _profile(sequence, fields, notification_counter, notification_limit, per_thread_hook_present, writer_metadata_callback_present, padding_policy)
    if not isinstance(values, NativeValues) or type(values.item_variant) is not bytes or len(values.item_variant) != 8 or (type(values.position_bytes) is not bytes) or (len(values.position_bytes) != 8) or (type(values.item_raw) is not int) or (not 0 <= values.item_raw <= 4294967295):
        raise ValueError('28D6EBBE requires all exact native query results')
    positive = fields.optional_index is not None and fields.optional_index < 2147483648
    if positive:
        if type(values.optional_position_bytes) is not bytes or len(values.optional_position_bytes) != 8:
            raise ValueError('28D6EBBE positive index requires the exact native optional position')
        optional_position = values.optional_position_bytes
        optional_scalar = fields.optional_scalar
    else:
        if values.optional_position_bytes is not None:
            raise ValueError('28D6EBBE absent or negative optional index cannot inject query results')
        optional_position = struct.pack('<ii', -9999, -9999)
        optional_scalar = 0
    record = bytearray(RECORD_SIZE)
    struct.pack_into('<IIII', record, 0, RECORD_SIZE, RECORD_TYPE, sequence, 0)
    struct.pack_into('<II', record, 16, 4294967295, 4294967295)
    for offset in (24, 32, 40, 48, 56):
        struct.pack_into('<HHI', record, offset, 65535, 0, 4294967295)
    payload = bytearray(64)
    struct.pack_into('<I', payload, 0, sequence)
    struct.pack_into('<HHI', payload, 8, fields.owner, 3, fields.item_id)
    payload[16:24] = values.position_bytes
    struct.pack_into('<I', payload, 24, values.item_raw)
    payload[32:40] = values.item_variant
    struct.pack_into('<I', payload, 40, fields.value)
    payload[44:52] = optional_position
    struct.pack_into('<I', payload, 52, optional_scalar)
    payload[56:64] = fields.metadata_pair_bytes
    record[80:] = payload
    return bytes(record)

def _qword(read, address):
    raw = read(address, 8)
    if type(raw) is not bytes or len(raw) != 8:
        raise ValueError('Incomplete28D6 pointer read')
    return struct.unpack('<Q', raw)[0]

def _check(read, base, pointer, label, *, core_sha256='d7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'):
    if core_sha256 not in ('d7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3', '259b90a473a256aff6a7d621a4f3717e46f6921c59b9817475375c88b97e8c83', '324c51e9ea3531758842e16c69e6cddbefbb226c5b675c3d6e60111646c2e98c'):
        raise ValueError('Unqualified facade engine')
    from civ6_host.runtime.foundation_facade_profiles import query_abi, verify_xp1_once, select_tables
    from civ6_host.runtime.provenance import resource_root
    _foundation_abi = query_abi(core_sha256, None if core_sha256 == 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3' else resource_root())
    _TABLES = globals()['_TABLES']
    if core_sha256 != 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3':
        _TABLES = select_tables(core_sha256, _TABLES, resource_root())
    table, slots = _TABLES[label]
    if not pointer or _qword(read, pointer) != base + table:
        raise ValueError(f'Unexpected28D6 {label} facade')
    for offset, target in slots:
        if _qword(read, base + table + offset) != base + target:
            raise ValueError(f'Unexpected28D6 {label} method')

def _api(base, api, *, core_sha256='d7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'):
    if core_sha256 not in ('d7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3', '259b90a473a256aff6a7d621a4f3717e46f6921c59b9817475375c88b97e8c83', '324c51e9ea3531758842e16c69e6cddbefbb226c5b675c3d6e60111646c2e98c'):
        raise ValueError('Unqualified facade engine')
    from civ6_host.runtime.foundation_facade_profiles import query_abi, verify_xp1_once, select_tables
    from civ6_host.runtime.provenance import resource_root
    _foundation_abi = query_abi(core_sha256, None if core_sha256 == 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3' else resource_root())
    entries = {'get_player': (_foundation_abi.rva('get_player'), C.c_void_p, (C.c_void_p, C.c_int32)), 'release_player': (_foundation_abi.rva('release_player'), None, (C.c_void_p,)), 'player_collection': (_foundation_abi.rva('player_districts'), C.c_void_p, (C.c_void_p,)), 'release_collection': (_foundation_abi.rva('release_collection'), None, (C.c_void_p,)), 'collection_index': (_foundation_abi.rva('district_by_id'), C.c_void_p, (C.c_void_p, C.c_uint32)), 'release_item': (_foundation_abi.rva('release_district'), None, (C.c_void_p,)), 'item_variant': (_foundation_abi.rva('district_city_descriptor'), C.c_void_p, (C.c_void_p, C.c_void_p)), 'item_raw': (_foundation_abi.rva('district_type'), C.c_uint32, (C.c_void_p,)), 'item_position': (_foundation_abi.rva('district_position'), C.c_void_p, (C.c_void_p, C.c_void_p))}
    if api is not None:
        if not isinstance(api, dict) or set(api) != set(entries):
            raise ValueError('28D6 test seam requires the exact nine source operations')
        return api
    return {name: C.WINFUNCTYPE(restype, *args)(base + rva) for name, (rva, restype, args) in entries.items()}

def _out8(function, item):
    buffer = C.create_string_buffer(_GUARD + bytes(8) + _GUARD, 40)
    output = C.addressof(buffer) + 16
    result = function(item, output)
    if buffer.raw[:16] != _GUARD or buffer.raw[24:] != _GUARD:
        raise RuntimeError('28D6 native output exceeded its source eight-byte extent')
    if result != output:
        raise ValueError('28D6 native output pointer differs from the source return contract')
    return bytes(buffer.raw[16:24])

@contextmanager
def produce_record_lease(sequence, core, context, fields, *, notification_counter, notification_limit, per_thread_hook_present, writer_metadata_callback_present, padding_policy, read=None, native_api=None, optional_native_api=None, core_sha256='d7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'):
    """Keep the indexed native item alive through synchronous record enqueue.

    EXE147F10's positive optional query completes and releases its map before
    acquiring the player/collection/item. Absent or negative indices make no map
    query. The callback copies 5B55 separately from the optional position/scalar.
    Both pointer-returning outputs are source-sized eight-byte guarded buffers.
    """
    if core_sha256 not in ('d7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3', '259b90a473a256aff6a7d621a4f3717e46f6921c59b9817475375c88b97e8c83', '324c51e9ea3531758842e16c69e6cddbefbb226c5b675c3d6e60111646c2e98c'):
        raise ValueError('Unqualified facade engine')
    profile = dict(notification_counter=notification_counter, notification_limit=notification_limit, per_thread_hook_present=per_thread_hook_present, writer_metadata_callback_present=writer_metadata_callback_present, padding_policy=padding_policy)
    _profile(sequence, fields, **profile)
    base = int(core._handle)
    if base <= 0 or type(context) is not int or context <= 0:
        raise ValueError('Live Core context required')
    if read is None:
        from civ6_host.runtime.native.native_setup import local_reader
        read = local_reader()
    _check(read, base, context, 'outer', core_sha256=core_sha256)
    api = _api(base, native_api, core_sha256=core_sha256)
    optional_position = None
    if fields.optional_index is not None and fields.optional_index < 2147483648:
        optional_position = query_optional_position(core, context, fields.optional_index, read=read, native_api=optional_native_api, core_sha256=core_sha256)
        if type(optional_position) is not bytes or len(optional_position) != 8:
            raise ValueError('28D6EBBE requires the complete native optional position')
    item = 0
    item_checked = False
    try:
        player = api['get_player'](context, fields.owner)
        _check(read, base, player, 'player', core_sha256=core_sha256)
        try:
            collection = api['player_collection'](player)
            _check(read, base, collection, 'collection', core_sha256=core_sha256)
            try:
                item = api['collection_index'](collection, fields.item_id)
            finally:
                api['release_collection'](collection)
        finally:
            api['release_player'](player)
        _check(read, base, item, 'item', core_sha256=core_sha256)
        item_checked = True
        if not _qword(read, item + 8):
            raise ValueError('28D6 diagnostic requires a live item owner')
        variant = _out8(api['item_variant'], item)
        raw = int(api['item_raw'](item))
        position = _out8(api['item_position'], item)
        yield encode_record(sequence, fields, NativeValues(variant, raw, position, optional_position), **profile)
    finally:
        if item_checked:
            api['release_item'](item)

def produce_record(*args, **kwargs):
    """Standalone diagnostic encoder; dispatchers must use produce_record_lease."""
    with produce_record_lease(*args, **kwargs) as record:
        return record
