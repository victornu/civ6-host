"""C3183902 producer with source-sized native queries and diagnostic padding.

The explicit profile supports configuration owners 0..63 and live Core interfaces.
A produced deferred record is not proof of a completed gameplay action.
"""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import ctypes as C
import hashlib
import json
import struct
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from civ6_host.runtime.native.native_application_mirror import decode_scalar
from civ6_host.runtime.native.native_event_fa5b1159 import query_secondary_value
from civ6_host.runtime.native.native_event_fa5b1159 import read_player_civilization_type_id
from civ6_host.runtime.native.native_host_events import copy_eight_byte_variant
EVENT_KIND, CALLBACK_RVA, WRITER_RVA = (3273144578, 1328720, 1265424)
RECORD_TYPE, RECORD_SIZE, SNAPSHOT_SIZE = (156, 160, 64)
POSITION_KEY, SELECTOR_KEY = (2353434172, 2716180809)
IGNORED_KEY, VALUE_KEY, DESCRIPTOR_KEY = (2717631346, 3606901732, 4081310810)
DESCRIPTOR_TYPE = 3
EXE_SHA256 = 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63'
CORE_SHA256 = 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'
PINNED_EVIDENCE_SHA256 = '93e221326469d7a803e04e2f6b8f6f6eb931c10654c681f102e48d1bc6dc18a3'
_PROOF = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_event_c3183902.py')))).resolve().parents[1] / 'evidence/native-event-c3183902' / f'{PINNED_EVIDENCE_SHA256}.json'
_GUARD = bytes.fromhex('95a671db093264e85c873b402a17f6cd')
_HASH_ONE, _HASH_TWO = (1587009065, 1839557181)
_TABLES = {'outer': (7987232, ((184, 4382880), (168, 4382784))), 'player': (7992320, ((8, 4421040), (304, 4422336))), 'collection': (7993256, ((8, 4427952), (16, 4427984))), 'item': (7990216, ((8, 4406960), (32, 4372864), (48, 4407024), (88, 4407392), (112, 4407008))), 'map': (7991792, ((8, 4416608), (64, 4418176))), 'plot': (7994424, ((8, 4435728), (48, 4435888)))}

def verify_source_evidence():
    raw = _resolve_resource_path(_PROOF).read_bytes()
    if hashlib.sha256(raw).hexdigest() != PINNED_EVIDENCE_SHA256:
        raise RuntimeError('Pinned C3183902 source evidence changed')
    proof = json.loads(raw)
    if proof.get('schema') != 'civ6rl.native_event_c3183902.static.v1' or proof['images'] != {'exe_sha256': EXE_SHA256, 'gamecore_sha256': CORE_SHA256} or proof['inputs']['callback_va'] != '0x140144650' or (proof['captures']['0x140144650']['code_sha256'] != '6a450773b1592b8290a61705875de64372b624a04756a5bca40992c8d7ec27bc') or (proof['captures']['0x140134f10']['code_sha256'] != '73c589d312da1a286e0558c153b24f2689702fce8c2c36e6da7a88ff42694786'):
        raise RuntimeError('Pinned C3183902 source identity changed')

@dataclass(frozen=True)
class EventFields:
    position_bytes: bytes
    x: int
    y: int
    selector: int
    ignored_value: int
    value: int
    descriptor_bytes: bytes
    owner: int
    item_id: int

@dataclass(frozen=True)
class NativeValues:
    secondary_value: int
    civilization_id: int
    item_raw: int
    item_variant: bytes
    map_value: int
    snapshot_value8: int
    snapshot_value12: int
    snapshot_flag29: int
    item_hash_one: int
    item_hash_two: int

def _check_fields(fields):
    if not isinstance(fields, EventFields) or type(fields.position_bytes) is not bytes or len(fields.position_bytes) != 8 or (type(fields.x) is not int) or (type(fields.y) is not int) or (struct.unpack('<ii', fields.position_bytes) != (fields.x, fields.y)) or (type(fields.descriptor_bytes) is not bytes) or (len(fields.descriptor_bytes) != 8) or (type(fields.owner) is not int) or (not 0 <= fields.owner < 64) or (struct.unpack_from('<h', fields.descriptor_bytes)[0] != fields.owner) or (struct.unpack_from('<I', fields.descriptor_bytes, 4)[0] != fields.item_id):
        raise ValueError('C3183902 requires consistent source fields and a configuration owner 0..63')
    for value in (fields.selector, fields.ignored_value, fields.value, fields.item_id):
        if type(value) is not int or not 0 <= value <= 4294967295:
            raise ValueError('C3183902 scalar does not fit source DWORD')
    if fields.selector != 0:
        raise ValueError('C3183902 selector profile is limited to zero')

def decode_fields(fields, read):
    verify_source_evidence()
    if not isinstance(fields, dict) or set(fields) != {POSITION_KEY, SELECTOR_KEY, IGNORED_KEY, VALUE_KEY, DESCRIPTOR_KEY}:
        raise ValueError('C3183902 requires exactly the five source-mapped fields')
    position = copy_eight_byte_variant(fields[POSITION_KEY], read, expected_tag=0)
    descriptor = copy_eight_byte_variant(fields[DESCRIPTOR_KEY], read, expected_tag=1024)
    x, y = struct.unpack('<ii', position)
    result = EventFields(position, x, y, decode_scalar(fields[SELECTOR_KEY], 3), decode_scalar(fields[IGNORED_KEY], 2), decode_scalar(fields[VALUE_KEY], 2), descriptor, struct.unpack_from('<h', descriptor)[0], struct.unpack_from('<I', descriptor, 4)[0])
    _check_fields(result)
    return result

def _profile(sequence, fields, notification_counter, notification_limit, per_thread_hook_present, writer_metadata_callback_present, padding_policy):
    verify_source_evidence()
    _check_fields(fields)
    if type(sequence) is not int or not 1 <= sequence <= 4294967295:
        raise ValueError('C3183902 sequence must be a nonzero uint32')
    if type(notification_counter) is not int or notification_counter != 0 or type(notification_limit) is not int or (notification_limit != 0) or (per_thread_hook_present is not False) or (writer_metadata_callback_present is not False):
        raise ValueError('Unsupported C3183902 counter/hook/writer-service profile')
    if padding_policy != 'headless-zero-uninitialized-stack':
        raise ValueError('Explicit zero policy for uninitialized callback stack bytes required')

def encode_record(sequence, fields, values, *, notification_counter, notification_limit, per_thread_hook_present, writer_metadata_callback_present, padding_policy):
    _profile(sequence, fields, notification_counter, notification_limit, per_thread_hook_present, writer_metadata_callback_present, padding_policy)
    if not isinstance(values, NativeValues):
        raise TypeError('NativeValues from all source queries required')
    for name in ('secondary_value', 'civilization_id'):
        value = getattr(values, name)
        if type(value) is not int or not -(1 << 31) <= value <= 4294967295:
            raise ValueError(f'Invalid C3183902 {name}')
    for name in ('item_raw', 'map_value', 'snapshot_value8', 'snapshot_value12', 'item_hash_one', 'item_hash_two'):
        value = getattr(values, name)
        if type(value) is not int or not 0 <= value <= 4294967295:
            raise ValueError(f'Invalid C3183902 {name}')
    if type(values.item_variant) is not bytes or len(values.item_variant) != 8 or type(values.snapshot_flag29) is not int or (not 0 <= values.snapshot_flag29 <= 255):
        raise ValueError('Invalid C3183902 descriptor or snapshot flag')
    payload = bytearray(80)
    struct.pack_into('<I', payload, 0, sequence)
    struct.pack_into('<HHI', payload, 8, fields.owner, DESCRIPTOR_TYPE, fields.item_id)
    payload[16:24] = fields.position_bytes
    struct.pack_into('<I', payload, 24, values.item_raw)
    payload[32:40] = values.item_variant
    struct.pack_into('<IIII', payload, 40, values.secondary_value & 4294967295, values.civilization_id & 4294967295, fields.value, values.map_value)
    payload[56] = values.snapshot_flag29
    struct.pack_into('<IIII', payload, 64, values.snapshot_value8, values.item_hash_one, values.snapshot_value12, values.item_hash_two)
    record = bytearray(RECORD_SIZE)
    struct.pack_into('<IIII', record, 0, RECORD_SIZE, RECORD_TYPE, sequence, 0)
    struct.pack_into('<II', record, 16, 4294967295, 4294967295)
    for offset in (24, 32, 40, 48, 56):
        struct.pack_into('<HHI', record, offset, 65535, 0, 4294967295)
    record[80:] = payload
    return bytes(record)

def _qword(read, address):
    raw = read(address, 8)
    if type(raw) is not bytes or len(raw) != 8:
        raise ValueError('C3183902 pointer read must return eight bytes')
    return struct.unpack('<Q', raw)[0]

def _check_object(read, base, pointer, label, *, core_sha256='d7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'):
    if core_sha256 not in ('d7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3', '259b90a473a256aff6a7d621a4f3717e46f6921c59b9817475375c88b97e8c83', '324c51e9ea3531758842e16c69e6cddbefbb226c5b675c3d6e60111646c2e98c'):
        raise ValueError('Unqualified facade engine')
    from civ6_host.runtime.foundation_facade_profiles import query_abi, verify_xp1_once, select_tables
    from civ6_host.runtime.provenance import resource_root
    _foundation_abi = query_abi(core_sha256, None if core_sha256 == 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3' else resource_root())
    _TABLES = globals()['_TABLES']
    if core_sha256 != 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3':
        _TABLES = select_tables(core_sha256, _TABLES, resource_root())
    vt, slots = _TABLES[label]
    if not pointer or _qword(read, pointer) != base + vt:
        raise ValueError(f'Unexpected C3183902 {label} vtable')
    for slot, target in slots:
        if _qword(read, base + vt + slot) != base + target:
            raise ValueError(f'Unexpected C3183902 {label} method +{slot:#x}')

def _api(base, api, *, core_sha256='d7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'):
    if core_sha256 not in ('d7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3', '259b90a473a256aff6a7d621a4f3717e46f6921c59b9817475375c88b97e8c83', '324c51e9ea3531758842e16c69e6cddbefbb226c5b675c3d6e60111646c2e98c'):
        raise ValueError('Unqualified facade engine')
    from civ6_host.runtime.foundation_facade_profiles import query_abi, verify_xp1_once, select_tables
    from civ6_host.runtime.provenance import resource_root
    _foundation_abi = query_abi(core_sha256, None if core_sha256 == 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3' else resource_root())
    specs = {'get_player': (_foundation_abi.rva('get_player'), C.c_void_p, (C.c_void_p, C.c_int32)), 'release_player': (_foundation_abi.rva('release_player'), None, (C.c_void_p,)), 'player_collection': (_foundation_abi.rva('player_districts'), C.c_void_p, (C.c_void_p,)), 'release_collection': (_foundation_abi.rva('release_collection'), None, (C.c_void_p,)), 'collection_index': (_foundation_abi.rva('district_by_id'), C.c_void_p, (C.c_void_p, C.c_uint32)), 'release_item': (_foundation_abi.rva('release_district'), None, (C.c_void_p,)), 'item_raw': (_foundation_abi.rva('district_type'), C.c_uint32, (C.c_void_p,)), 'item_variant': (_foundation_abi.rva('district_city_descriptor'), C.c_void_p, (C.c_void_p, C.c_void_p)), 'item_hash': (_foundation_abi.rva('district_hash'), C.c_uint32, (C.c_void_p, C.c_uint32)), 'item_snapshot': (_foundation_abi.rva('district_snapshot70'), C.c_uint8, (C.c_void_p, C.c_void_p, C.c_uint32)), 'free_vector': (_foundation_abi.rva('free_snapshot_vector'), None, (C.c_void_p,)), 'outer_map': (_foundation_abi.rva('outer_map'), C.c_void_p, (C.c_void_p,)), 'release_map': (_foundation_abi.rva('release_map'), None, (C.c_void_p,)), 'map_plot': (_foundation_abi.rva('get_plot'), C.c_void_p, (C.c_void_p, C.c_int32, C.c_int32)), 'release_plot': (_foundation_abi.rva('release_plot'), None, (C.c_void_p,)), 'plot_value': (_foundation_abi.rva('plot_value'), C.c_uint32, (C.c_void_p,))}
    if api is not None:
        if not isinstance(api, dict) or set(api) != set(specs):
            raise ValueError('C3183902 test seam requires all sixteen source operations')
        return api
    return {name: C.WINFUNCTYPE(restype, *args)(base + rva) for name, (rva, restype, args) in specs.items()}

def _guarded(size):
    buffer = C.create_string_buffer(len(_GUARD) + size + len(_GUARD))
    C.memmove(C.addressof(buffer), _GUARD, len(_GUARD))
    C.memmove(C.addressof(buffer) + len(_GUARD) + size, _GUARD, len(_GUARD))
    return (buffer, C.addressof(buffer) + len(_GUARD))

def _checked_buffer(buffer, size):
    raw = bytes(buffer.raw)
    if raw[:len(_GUARD)] != _GUARD or raw[len(_GUARD) + size:] != _GUARD:
        raise RuntimeError('C3183902 native output exceeded source-sized buffer')
    return raw[len(_GUARD):len(_GUARD) + size]

@contextmanager
def produce_record_lease(sequence, core, context, fields, *, expected_civilization_hash, notification_counter, notification_limit, per_thread_hook_present, writer_metadata_callback_present, padding_policy, read=None, native_api=None, secondary_query_api=None, config_record_lookup=None, config_value_lookup=None, key_hash=None, core_sha256='d7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'):
    """Keep the item and plot alive through the caller's synchronous enqueue.

    A borrowed outer context replaces the EXE's temporary outer references.
    The native snapshot is 0x40 bytes including a zeroed 24-byte vector. Its
    allocation is freed through Core's own aligned-free thunk, exactly the
    allocator pair used by vector growth. Output guards protect both ends.
    """
    if core_sha256 not in ('d7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3', '259b90a473a256aff6a7d621a4f3717e46f6921c59b9817475375c88b97e8c83', '324c51e9ea3531758842e16c69e6cddbefbb226c5b675c3d6e60111646c2e98c'):
        raise ValueError('Unqualified facade engine')
    profile = dict(notification_counter=notification_counter, notification_limit=notification_limit, per_thread_hook_present=per_thread_hook_present, writer_metadata_callback_present=writer_metadata_callback_present, padding_policy=padding_policy)
    _profile(sequence, fields, **profile)
    base = int(core._handle)
    if base <= 0 or type(context) is not int or context <= 0:
        raise ValueError('C3183902 requires a live relocated Core context')
    if expected_civilization_hash is not None and (type(expected_civilization_hash) is not int or not 0 <= expected_civilization_hash <= 4294967295):
        raise ValueError('Expected civilization hash must be uint32 or absent')
    if read is None:
        from civ6_host.runtime.native.native_setup import local_reader
        read = local_reader()
    _check_object(read, base, context, 'outer', core_sha256=core_sha256)
    api = _api(base, native_api, core_sha256=core_sha256)
    secondary = query_secondary_value(core, context, fields.owner, read=read, native_api=secondary_query_api, core_sha256=core_sha256)
    civilization = read_player_civilization_type_id(core, context, fields.owner, expected_hash=expected_civilization_hash, read=read, record_lookup=config_record_lookup, value_lookup=config_value_lookup, key_hash=key_hash, core_sha256=core_sha256)
    item = plot = 0
    item_checked = plot_checked = False
    try:
        player = api['get_player'](context, fields.owner)
        _check_object(read, base, player, 'player', core_sha256=core_sha256)
        try:
            collection = api['player_collection'](player)
            _check_object(read, base, collection, 'collection', core_sha256=core_sha256)
            try:
                item = api['collection_index'](collection, fields.item_id)
            finally:
                api['release_collection'](collection)
        finally:
            api['release_player'](player)
        _check_object(read, base, item, 'item', core_sha256=core_sha256)
        item_checked = True
        if not _qword(read, item + 8):
            raise ValueError('C3183902 snapshot requires a live item owner')
        snapshot, output = _guarded(SNAPSHOT_SIZE)
        vector = 0
        try:
            api['item_snapshot'](item, output, 0)
            snap = _checked_buffer(snapshot, SNAPSHOT_SIZE)
            candidate, capacity = struct.unpack_from('<QI', snap, 40)
            count = struct.unpack_from('<I', snap, 56)[0]
            if count > capacity or bool(capacity) != bool(candidate) or (candidate and candidate % 16):
                raise ValueError('C3183902 native snapshot vector is malformed')
            vector = candidate
            hash_one = int(api['item_hash'](item, _HASH_ONE))
            hash_two = int(api['item_hash'](item, _HASH_TWO))
            variant, variant_out = _guarded(8)
            returned = api['item_variant'](item, variant_out)
            descriptor = _checked_buffer(variant, 8)
            if returned != variant_out:
                raise ValueError('C3183902 item descriptor returned an unexpected output pointer')
            raw = int(api['item_raw'](item))
        finally:
            api['free_vector'](vector)
        map_object = api['outer_map'](context)
        _check_object(read, base, map_object, 'map', core_sha256=core_sha256)
        try:
            plot = api['map_plot'](map_object, fields.x, fields.y)
        finally:
            api['release_map'](map_object)
        _check_object(read, base, plot, 'plot', core_sha256=core_sha256)
        plot_checked = True
        map_value = int(api['plot_value'](plot))
        values = NativeValues(secondary, civilization, raw, descriptor, map_value, struct.unpack_from('<I', snap, 8)[0], struct.unpack_from('<I', snap, 12)[0], snap[29], hash_one, hash_two)
        yield encode_record(sequence, fields, values, **profile)
    finally:
        try:
            if plot_checked:
                api['release_plot'](plot)
        finally:
            if item_checked:
                api['release_item'](item)

def produce_record(*args, **kwargs):
    """Standalone diagnostic encoder; dispatchers must use produce_record_lease."""
    with produce_record_lease(*args, **kwargs) as record:
        return record
