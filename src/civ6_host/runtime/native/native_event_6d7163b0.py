"""Ordered 6D7163B0 native query passes selected by the original callback.

The caller preflights the complete selector-specific record plan and sequences.
Each synchronous enqueue happens while that pass's plot/district references
are still retained. No query result is cached across the two source passes.
"""
from __future__ import annotations
from civ6_host.runtime import placement_event_profile as _placement_events
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import ctypes as C
from dataclasses import dataclass
from pathlib import Path
import struct
from civ6_host.runtime.native.native_application_mirror import decode_scalar
from civ6_host.runtime.native.native_event_c3183902 import _guarded
from civ6_host.runtime.native.native_event_c3183902 import _checked_buffer
from civ6_host.runtime.native.native_event_fa5b1159 import query_secondary_value
from civ6_host.runtime.native.native_event_fa5b1159 import read_player_civilization_type_id
from civ6_host.runtime.native.native_host_events import copy_eight_byte_variant
from civ6_host.runtime.native.native_source_cache import load_pinned_json
EVENT_KIND, RECORD_TYPE, RECORD_SIZE = (1836147632, 157, 144)
SELECTOR = 3434534334
POSITION_KEY, SELECTOR_KEY, A1FBC_KEY, D6_KEY, DESCRIPTOR_KEY = (2353434172, 2716180809, 2717631346, 3606901732, 4081310810)
PROOF_SHA256 = 'ec07f3ed63488cd6aef905d870029a15072210ad5abd7f982298f4564b4825a1'
_PROOF = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_event_6d7163b0.py')))).resolve().parents[1] / 'evidence/native-event-6d7163b0' / f'{PROOF_SHA256}.json'
PADDING_POLICY = 'zero-unread-empty-receiver-payload'
SNAPSHOT_SIZE, MAX_VECTOR_ENTRIES = (64, 4096)
_EMPTY_KEYS = frozenset(('observer_registered', 'state_pointer_nonnull', 'pre_hook', 'post_hook', 'subscriber_count', 'state_flags'))
_TABLES = {'outer': (7987232, ((184, 4382880), (168, 4382784))), 'player': (7992320, ((8, 4421040), (304, 4422336))), 'collection': (7993256, ((8, 4427952), (16, 4427984))), 'item': (7990216, ((8, 4406960), (32, 4372864), (48, 4407024), (112, 4407008))), 'map': (7991792, ((8, 4416608), (64, 4418176))), 'plot': (7994424, ((8, 4435728), (48, 4435888)))}

def verify_source_evidence():
    proof = load_pinned_json(_PROOF, PROOF_SHA256)
    if proof.get('schema') != 'civ6rl.native_event_6d7163b0.static.v1' or proof['images'] != {'exe_sha256': 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63', 'core_sha256': 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'} or proof['registration']['callback_va'] != '0x140144b30' or (proof['captures']['callback']['code_sha256'] != '9aaaa6610ec54bf7dafbd3207ca12661d49eb090332f050d96861f09fc57f01e') or (proof['captures']['writer']['code_sha256'] != '4e5fb1479421c8e113ff289d9cf993a55303c81ea9aec7919d152b579166edb4') or (proof['contract']['admitted_selector'] != '0xccb6d5be') or (proof['empty_receiver_source']['row']['record_type'] != '0x9d'):
        raise RuntimeError('Pinned 6D7163B0 source identity changed')
    return proof

@dataclass(frozen=True)
class EventFields:
    position_bytes: bytes
    x: int
    y: int
    selector: int
    a1fbc_value: int
    d6_value: int
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
    snapshot_flag29: int
    vector_count: int
    vector_capacity: int

def _fields(fields):
    if not isinstance(fields, EventFields) or type(fields.position_bytes) is not bytes or len(fields.position_bytes) != 8 or (type(fields.x) is not int) or (type(fields.y) is not int) or (struct.unpack('<ii', fields.position_bytes) != (fields.x, fields.y)) or (type(fields.descriptor_bytes) is not bytes) or (len(fields.descriptor_bytes) != 8) or (type(fields.owner) is not int) or (not 0 <= fields.owner < 64) or (struct.unpack_from('<h', fields.descriptor_bytes)[0] != fields.owner) or (struct.unpack_from('<I', fields.descriptor_bytes, 4)[0] != fields.item_id) or any((type(value) is not int or not 0 <= value <= 4294967295 for value in (fields.selector, fields.a1fbc_value, fields.d6_value, fields.item_id))):
        raise ValueError('6D7163B0 requires consistent five-field input for owner0..63')
    from civ6_host.runtime.native.native_event_6d7163b0_selector import record_plan
    record_plan(fields.selector)

def _scalar_fields(raw_fields):
    verify_source_evidence()
    if not isinstance(raw_fields, dict) or set(raw_fields) != {POSITION_KEY, SELECTOR_KEY, A1FBC_KEY, D6_KEY, DESCRIPTOR_KEY}:
        raise ValueError('6D7163B0 requires exactly its five witnessed fields')
    for key in (SELECTOR_KEY, A1FBC_KEY, D6_KEY):
        if not isinstance(raw_fields[key], (bytes, bytearray, memoryview)):
            raise ValueError('6D7163B0 scalar variants must contain bytes')
    return {key: decode_scalar(bytes(raw_fields[key]), 3 if key == SELECTOR_KEY else 2) for key in (SELECTOR_KEY, A1FBC_KEY, D6_KEY)}

def record_plan_from_fields(raw_fields):
    from civ6_host.runtime.native.native_event_6d7163b0_selector import record_plan
    return record_plan(_scalar_fields(raw_fields)[SELECTOR_KEY])

def decode_fields(raw_fields, read) -> EventFields:
    scalars = _scalar_fields(raw_fields)
    from civ6_host.runtime.native.native_event_6d7163b0_selector import record_plan
    selector = scalars[SELECTOR_KEY]
    record_plan(selector)
    position = copy_eight_byte_variant(raw_fields[POSITION_KEY], read, expected_tag=0)
    descriptor = copy_eight_byte_variant(raw_fields[DESCRIPTOR_KEY], read, expected_tag=1024)
    result = EventFields(position, *struct.unpack('<ii', position), selector, scalars[A1FBC_KEY], scalars[D6_KEY], descriptor, struct.unpack_from('<h', descriptor)[0], struct.unpack_from('<I', descriptor, 4)[0])
    _fields(result)
    return result

def _empty(record, state):
    if not isinstance(state, dict) or set(state) != _EMPTY_KEYS or type(state['state_flags']) is not int or (state['state_flags'] != 0):
        raise ValueError('6D7163B0 requires the complete empty receiver state with zero flags')
    from civ6_host.runtime.native.native_deferred_empty_profile import validate_empty_profile_record
    validate_empty_profile_record(record, **state)

def _profile(sequence, fields, normalizer_transform_present, per_thread_hook_present, writer_metadata_callback_present, padding_policy, empty_receiver_state):
    verify_source_evidence()
    _fields(fields)
    if type(sequence) is not int or not 1 <= sequence <= 4294967295:
        raise ValueError('6D7163B0 sequence must be a nonzero uint32')
    if normalizer_transform_present is not False or per_thread_hook_present is not False or writer_metadata_callback_present is not False:
        raise ValueError('6D7163B0 requires explicitly absent transform/hook/writer service')
    if padding_policy != PADDING_POLICY:
        raise ValueError('6D7163B0 requires explicit zero-unread-empty-receiver-payload policy')
    header_only = bytearray(RECORD_SIZE)
    struct.pack_into('<II', header_only, 0, RECORD_SIZE, RECORD_TYPE)
    _empty(header_only, empty_receiver_state)

def _values(values):
    if not isinstance(values, NativeValues):
        raise ValueError('6D7163B0 needs all native query results')
    if any((type(value) is not int or not -(1 << 31) <= value <= 4294967295 for value in (values.secondary_value, values.civilization_id))) or any((type(value) is not int or not 0 <= value <= 4294967295 for value in (values.item_raw, values.map_value))) or type(values.item_variant) is not bytes or (len(values.item_variant) != 8) or (type(values.snapshot_flag29) is not int) or (not 0 <= values.snapshot_flag29 <= 255) or (type(values.vector_count) is not int) or (type(values.vector_capacity) is not int) or (not 0 <= values.vector_count <= values.vector_capacity <= MAX_VECTOR_ENTRIES):
        raise ValueError('6D7163B0 native query result is outside its source width/bound')

def encode_record(sequence, fields, values, *, normalizer_transform_present, per_thread_hook_present, writer_metadata_callback_present, padding_policy, empty_receiver_state) -> bytes:
    profile = dict(normalizer_transform_present=normalizer_transform_present, per_thread_hook_present=per_thread_hook_present, writer_metadata_callback_present=writer_metadata_callback_present, padding_policy=padding_policy, empty_receiver_state=empty_receiver_state)
    _profile(sequence, fields, **profile)
    _values(values)
    record = bytearray(RECORD_SIZE)
    struct.pack_into('<IIII', record, 0, RECORD_SIZE, RECORD_TYPE, sequence, 0)
    record[16:24] = b'\xff' * 8
    record[24:64] = bytes.fromhex('ffff0000ffffffff') * 5
    struct.pack_into('<I', record, 80, sequence)
    struct.pack_into('<HHI', record, 88, fields.owner, 3, fields.item_id)
    record[96:104] = fields.position_bytes
    struct.pack_into('<I', record, 104, values.item_raw)
    record[112:120] = values.item_variant
    struct.pack_into('<IIII', record, 120, values.secondary_value & 4294967295, values.civilization_id & 4294967295, fields.a1fbc_value, values.map_value)
    record[136] = values.snapshot_flag29
    _empty(record, empty_receiver_state)
    return bytes(record)

def _qword(read, address):
    raw = read(address, 8)
    if not isinstance(raw, (bytes, bytearray, memoryview)) or len(bytes(raw)) != 8:
        raise ValueError('6D7163B0 pointer read must contain eight bytes')
    return struct.unpack('<Q', bytes(raw))[0]

def _check_object(read, base, pointer, label, *, core_sha256='d7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'):
    table, slots = _placement_events.select_tables(core_sha256, _TABLES)[label]
    if type(pointer) is not int or not 0 < pointer < 1 << 63:
        raise ValueError(f'6D7163B0 null/invalid {label} facade')
    actual = _qword(read, pointer)
    if actual != base + table:
        raise ValueError(f'6D7163B0 {label} vtable {actual:#x} differs from {base + table:#x}')
    for offset, target in slots:
        if _qword(read, base + table + offset) != base + target:
            raise ValueError(f'6D7163B0 unexpected {label} method+{offset:#x}')

def _api(base, provided, *, core_sha256='d7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'):
    specs = {'get_player': (4382880, C.c_void_p, (C.c_void_p, C.c_int32)), 'release_player': (4421040, None, (C.c_void_p,)), 'player_collection': (4422336, C.c_void_p, (C.c_void_p,)), 'release_collection': (4427952, None, (C.c_void_p,)), 'collection_index': (4427984, C.c_void_p, (C.c_void_p, C.c_uint32)), 'release_item': (4406960, None, (C.c_void_p,)), 'item_raw': (4372864, C.c_uint32, (C.c_void_p,)), 'item_variant': (4407024, C.c_void_p, (C.c_void_p, C.c_void_p)), 'item_snapshot': (4407008, C.c_uint8, (C.c_void_p, C.c_void_p, C.c_uint32)), 'free_vector': (7565584, None, (C.c_void_p,)), 'outer_map': (4382784, C.c_void_p, (C.c_void_p,)), 'release_map': (4416608, None, (C.c_void_p,)), 'map_plot': (4418176, C.c_void_p, (C.c_void_p, C.c_int32, C.c_int32)), 'release_plot': (4435728, None, (C.c_void_p,)), 'plot_value': (4435888, C.c_uint32, (C.c_void_p,))}
    specs = _placement_events.select_specs(core_sha256, specs)
    if provided is not None:
        if not isinstance(provided, dict) or set(provided) != set(specs) or any((not callable(fn) for fn in provided.values())):
            raise ValueError('6D7163B0 test seam requires exactly fifteen native operations')
        return provided
    return {name: C.WINFUNCTYPE(restype, *args)(base + rva) for name, (rva, restype, args) in specs.items()}

def _snapshot_vector(snapshot):
    pointer, capacity = struct.unpack_from('<QI', snapshot, 40)
    count = struct.unpack_from('<I', snapshot, 56)[0]
    if count > capacity or capacity > MAX_VECTOR_ENTRIES or bool(pointer) != bool(capacity) or (pointer and (pointer % 16 or pointer + capacity * 8 >= 1 << 63)):
        raise ValueError('6D7163B0 native snapshot vector is outside the bounded source layout')
    return (pointer, capacity, count)

def produce_records(first_sequence, core, context, fields, *, enqueue_record, expected_civilization_hash, normalizer_transform_present, per_thread_hook_present, writer_metadata_callback_present, padding_policy, empty_receiver_state, read=None, native_api=None, secondary_query_api=None, config_record_lookup=None, config_value_lookup=None, key_hash=None, core_sha256='d7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3') -> tuple:
    """Run the full source plan, enqueueing each record with retained sources.

    The dispatcher must preflight capacity for the plan and its consecutive sequences
    before calling. This function never retries or rolls back the first record
    if the second query/enqueue fails. Callbacks must enqueue synchronously.
    A borrowed validated outer context replaces EXE temporary outer references;
    every returned player/collection/item/map/plot wrapper is handled per pass.
    """
    profile = dict(normalizer_transform_present=normalizer_transform_present, per_thread_hook_present=per_thread_hook_present, writer_metadata_callback_present=writer_metadata_callback_present, padding_policy=padding_policy, empty_receiver_state=empty_receiver_state)
    _profile(first_sequence, fields, **profile)
    from civ6_host.runtime.native.native_event_6d7163b0_selector import record_plan
    from civ6_host.runtime.native.native_event_6d7163b0_selector import produce_auxiliary_record
    plan = record_plan(fields.selector)
    if first_sequence + len(plan) - 1 > 4294967295:
        raise ValueError('6D7163B0 source record plan exceeds nonzero uint32 sequences')
    for record_type, record_size in plan:
        shape = bytearray(record_size)
        struct.pack_into('<II', shape, 0, record_size, record_type)
        _empty(shape, empty_receiver_state)
    if not callable(enqueue_record):
        raise ValueError('6D7163B0 needs a synchronous enqueue callback')
    if expected_civilization_hash is not None and (type(expected_civilization_hash) is not int or not 0 <= expected_civilization_hash <= 4294967295):
        raise ValueError('6D7163B0 expected civilization hash must be uint32 or absent')
    base = int(core._handle)
    if not 0 < base < 1 << 63 or type(context) is not int or context <= 0:
        raise ValueError('6D7163B0 needs a live relocated Core context')
    if read is None:
        from civ6_host.runtime.native.native_setup import local_reader
        read = local_reader()
    _placement_events.verify_once(core, read, core_sha256)
    _check_object(read, base, context, 'outer', core_sha256=core_sha256)
    api = _api(base, native_api, core_sha256=core_sha256)
    results = []
    for pass_index in range(sum((record_type == RECORD_TYPE for record_type, _ in plan))):
        sequence = first_sequence + pass_index
        _profile(sequence, fields, **profile)
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
                raise ValueError('6D7163B0 snapshot requires a live district owner')
            snapshot, output = _guarded(SNAPSHOT_SIZE)
            vector = None
            try:
                api['item_snapshot'](item, output, 0)
                snap = _checked_buffer(snapshot, SNAPSHOT_SIZE)
                vector, capacity, count = _snapshot_vector(snap)
                variant, variant_out = _guarded(8)
                returned = api['item_variant'](item, variant_out)
                descriptor = _checked_buffer(variant, 8)
                if returned != variant_out:
                    raise ValueError('6D7163B0 district descriptor returned an unexpected output pointer')
                raw = api['item_raw'](item)
                flag = snap[29]
            finally:
                if vector is None:
                    try:
                        vector, _, _ = _snapshot_vector(_checked_buffer(snapshot, SNAPSHOT_SIZE))
                    except (ValueError, RuntimeError):
                        pass
                if vector is not None:
                    api['free_vector'](vector)
            map_object = api['outer_map'](context)
            _check_object(read, base, map_object, 'map', core_sha256=core_sha256)
            try:
                plot = api['map_plot'](map_object, fields.x, fields.y)
            finally:
                api['release_map'](map_object)
            _check_object(read, base, plot, 'plot', core_sha256=core_sha256)
            plot_checked = True
            plot_value = api['plot_value'](plot)
            values = NativeValues(secondary, civilization, raw, descriptor, plot_value, flag, count, capacity)
            record = encode_record(sequence, fields, values, **profile)
            enqueue_record(record, pass_index, values)
            results.append(values)
        finally:
            try:
                if plot_checked:
                    api['release_plot'](plot)
            finally:
                if item_checked:
                    api['release_item'](item)
    if plan[-1][0] == 163:
        auxiliary = produce_auxiliary_record(first_sequence + 1, core, context, fields, results[-1], enqueue_record=enqueue_record, read=read, native_api=native_api, **profile, core_sha256=core_sha256)
        results.append(auxiliary)
    return tuple(results)
__all__ = ['EVENT_KIND', 'RECORD_TYPE', 'RECORD_SIZE', 'PROOF_SHA256', 'PADDING_POLICY', 'EventFields', 'NativeValues', 'decode_fields', 'encode_record', 'produce_records', 'verify_source_evidence', 'record_plan_from_fields']
