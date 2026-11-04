"""6E7EF927 source producer with a real, owned native Unit snapshot query."""
from __future__ import annotations
from civ6_host.runtime import turn_unit_event_profile as _turn_units
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import ctypes as C
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
import struct
from civ6_host.runtime.native.native_application_mirror import decode_scalar
from civ6_host.runtime.native.native_host_events import copy_eight_byte_variant
from civ6_host.runtime.native.native_source_cache import load_pinned_json
EVENT_KIND, RECORD_TYPE, RECORD_SIZE = (1853815079, 24, 128)
PINNED_EVIDENCE_SHA256 = '37259dee80086a7a854f828d37a3bcf2ca0069a13a85f4862800ac12f3b7a634'
_PROOF = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_event_6e7ef927.py')))).resolve().parents[1] / 'evidence/native-event-6e7ef927' / f'{PINNED_EVIDENCE_SHA256}.json'
NULL_UNIT_SCALAR = 1797587246
SNAPSHOT_SIZE = 184
_TABLES = {'outer': (7987232, {184: 4382880}), 'player': (7992320, {8: 4421040, 272: 4423648}), 'units': (7994008, {8: 4432576, 16: 4432608}), 'unit': (7995536, {16: 4440784, 184: 4440944})}

def verify_source_evidence():
    proof = load_pinned_json(_PROOF, PINNED_EVIDENCE_SHA256)
    if proof['schema'] != 'civ6rl.native_event_6e7ef927.static.v1' or proof['images'] != {'exe_sha256': 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63', 'core_sha256': 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'} or proof['registration']['callback_va'] != '0x1401576e0' or (proof['fstring_source']['sha256'] != 'e6e50202766a2077ef7d10f1a55e488a33cbc73cae80d6bdf1910ccfc2040345') or (proof['fstring_source']['document']['captures']['core_empty_getter']['start_va'] != '0x18073a1b0') or (proof['fstring_source']['document']['captures']['core_aligned_free_thunk']['start_va'] != '0x180737110') or (proof['empty_receiver']['row']['event_name'] != 'GameCoreEvent::UnitMoveComplete') or (proof['contract']['record'] != {'type': 24, 'size': 128, 'payload_size': 40, 'metadata_size': 60}):
        raise RuntimeError('6E7EF927 source contract changed')
    return proof

@dataclass(frozen=True)
class EventFields:
    selector: int
    descriptor_bytes: bytes
    owner: int
    item_id: int
    position_bytes: bytes

@dataclass(frozen=True)
class NativeValues:
    scalar: int
    unit_present: bool = True
    read_skipped_reason: str | None = None

def _validate(fields):
    if not isinstance(fields, EventFields) or type(fields.selector) is not int or (not 0 <= fields.selector <= 4294967295) or (type(fields.descriptor_bytes) is not bytes) or (len(fields.descriptor_bytes) != 8) or (type(fields.owner) is not int) or (not 0 <= fields.owner <= 63) or (type(fields.item_id) is not int) or (not 0 <= fields.item_id <= 4294967295) or (struct.unpack_from('<H', fields.descriptor_bytes)[0] != fields.owner) or (struct.unpack_from('<I', fields.descriptor_bytes, 4)[0] != fields.item_id) or (type(fields.position_bytes) is not bytes) or (len(fields.position_bytes) != 8):
        raise ValueError('6E7EF927 requires exact decoded unit identity and position')

def decode_fields(raw_fields, read):
    verify_source_evidence()
    if not isinstance(raw_fields, dict) or set(raw_fields) != {2716180809, 4032072631, 2353434172}:
        raise ValueError('6E7EF927 requires exactly A1,unit descriptor,position')
    descriptor = copy_eight_byte_variant(raw_fields[4032072631], read, expected_tag=1024)
    fields = EventFields(decode_scalar(raw_fields[2716180809], 3), descriptor, struct.unpack_from('<H', descriptor)[0], struct.unpack_from('<I', descriptor, 4)[0], copy_eight_byte_variant(raw_fields[2353434172], read, expected_tag=0))
    _validate(fields)
    return fields

def _profile(sequence, fields, normalizer_transform_present, per_thread_hook_present, writer_metadata_callback_present, padding_policy):
    verify_source_evidence()
    _validate(fields)
    if type(sequence) is not int or not 1 <= sequence <= 4294967295:
        raise ValueError('6E7EF927 requires a nonzero uint32 sequence')
    if normalizer_transform_present is not False or per_thread_hook_present is not False or writer_metadata_callback_present is not False:
        raise ValueError('6E7EF927 requires explicitly absent transform/hook/writer callbacks')
    if padding_policy != 'headless-zero-uninitialized-stack':
        raise ValueError('6E7EF927 requires explicit zero source stack padding')

def encode_record(sequence, fields, values, *, normalizer_transform_present, per_thread_hook_present, writer_metadata_callback_present, padding_policy='headless-zero-uninitialized-stack'):
    _profile(sequence, fields, normalizer_transform_present, per_thread_hook_present, writer_metadata_callback_present, padding_policy)
    if not isinstance(values, NativeValues) or type(values.scalar) is not int or (not 0 <= values.scalar <= 4294967295) or (type(values.unit_present) is not bool):
        raise ValueError('6E7EF927 requires the exact native snapshot scalar')
    if values.unit_present:
        if values.read_skipped_reason is not None:
            raise ValueError('Present unit cannot skip snapshot')
    elif values.scalar != NULL_UNIT_SCALAR or values.read_skipped_reason not in ('player-null', 'unit-null'):
        raise ValueError('6E7EF927 NULL-unit scalar must be its source-initialized constant')
    record = bytearray(RECORD_SIZE)
    struct.pack_into('<IIII', record, 0, RECORD_SIZE, RECORD_TYPE, sequence, 0)
    record[16:24] = b'\xff' * 8
    record[24:64] = bytes.fromhex('ffff0000ffffffff') * 5
    struct.pack_into('<HHI', record, 24, fields.owner, 1, fields.item_id)
    struct.pack_into('<I', record, 72, 1)
    struct.pack_into('<I', record, 80, sequence)
    struct.pack_into('<HHI', record, 88, fields.owner, 1, fields.item_id)
    record[96:104] = fields.position_bytes
    struct.pack_into('<I', record, 112, values.scalar)
    return bytes(record)

def _qword(read, address):
    raw = read(address, 8)
    if len(raw) != 8:
        raise ValueError('6E7EF927 truncated pointer read')
    return struct.unpack('<Q', raw)[0]

def _check(read, base, pointer, label, *, core_sha256='d7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'):
    table, slots = _turn_units.select_tables(core_sha256, _TABLES)[label]
    actual = _qword(read, pointer) if pointer else 0
    if not pointer or actual != base + table:
        raise ValueError(f'Unexpected 6E7EF927 {label}: pointer={pointer or 0:#x}, vtable={actual:#x}')
    for slot, target in slots.items():
        if _qword(read, base + table + slot) != base + target:
            raise ValueError('6E7EF927 changed ' + label + ' slot')

def _api(base, native_api, *, core_sha256='d7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'):
    entries = {'get_player': (4382880, C.c_void_p, (C.c_void_p, C.c_int32)), 'release_player': (4421040, None, (C.c_void_p,)), 'player_units': (4423648, C.c_void_p, (C.c_void_p,)), 'release_units': (4432576, None, (C.c_void_p,)), 'units_index': (4432608, C.c_void_p, (C.c_void_p, C.c_uint32)), 'release_unit': (4440784, C.c_void_p, (C.c_void_p, C.c_uint32)), 'unit_snapshot': (4440944, None, (C.c_void_p, C.c_void_p, C.c_uint32)), 'string_empty': (7578032, C.c_void_p, ()), 'string_free': (7565584, None, (C.c_void_p,))}
    entries = _turn_units.select_specs(core_sha256, entries)
    if native_api is not None:
        if not isinstance(native_api, dict) or set(native_api) != set(entries):
            raise ValueError('6E7EF927 requires all nine source operations in the test seam')
        return native_api
    return {name: C.WINFUNCTYPE(restype, *args)(base + rva) for name, (rva, restype, args) in entries.items()}

@contextmanager
def produce_record_lease(sequence, core, context, fields, *, normalizer_transform_present, per_thread_hook_present, writer_metadata_callback_present, padding_policy='headless-zero-uninitialized-stack', read=None, native_api=None, query_diagnostic=None, core_sha256='d7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'):
    """Yield the encoded record while retaining a resolved Unit until context exit.

    NULL player/unit preserves the source constant. A NULL collection or cached
    unit without its live +0x10 pointer refuses before snapshot invocation.
    Player and collection references are released after lookup. Any FString
    allocated by snapshot is cleaned before encoding, matching the source.
    """
    profile = dict(normalizer_transform_present=normalizer_transform_present, per_thread_hook_present=per_thread_hook_present, writer_metadata_callback_present=writer_metadata_callback_present, padding_policy=padding_policy)
    _profile(sequence, fields, **profile)
    if query_diagnostic is not None and (not isinstance(query_diagnostic, dict)):
        raise ValueError('6E7EF927 diagnostic must be a dictionary')
    base = int(core._handle)
    if base <= 0 or type(context) is not int or context <= 0:
        raise ValueError('6E7EF927 requires live Core context')
    if read is None:
        from civ6_host.runtime.native.native_setup import local_reader
        read = local_reader()
    _check(read, base, context, 'outer', core_sha256=core_sha256)
    api = _api(base, native_api, core_sha256=core_sha256)
    string_freed = False

    def encode(values):
        result = encode_record(sequence, fields, values, **profile)
        if query_diagnostic is not None:
            query_diagnostic.update(unit_present=values.unit_present, read_skipped_reason=values.read_skipped_reason, snapshot_bytes=SNAPSHOT_SIZE if values.unit_present else 0, snapshot_scalar=values.scalar, native_snapshot_executed=values.unit_present, fstring_cleanup_completed=values.unit_present, fstring_heap_buffer_freed=string_freed)
        return result
    unit = 0
    unit_checked = False
    try:
        player = api['get_player'](context, fields.owner)
        if not player:
            yield encode(NativeValues(NULL_UNIT_SCALAR, False, 'player-null'))
            return
        _check(read, base, player, 'player', core_sha256=core_sha256)
        try:
            units = api['player_units'](player)
            _check(read, base, units, 'units', core_sha256=core_sha256)
            try:
                unit = api['units_index'](units, fields.item_id)
            finally:
                api['release_units'](units)
        finally:
            api['release_player'](player)
        if not unit:
            yield encode(NativeValues(NULL_UNIT_SCALAR, False, 'unit-null'))
            return
        _check(read, base, unit, 'unit', core_sha256=core_sha256)
        unit_checked = True
        if not _qword(read, unit + _turn_units.unit_live_offset(core_sha256)):
            raise ValueError('6E7EF927 snapshot requires the live Unit pointer at+10')
        storage = C.create_string_buffer(SNAPSHOT_SIZE + 16)
        address = C.addressof(storage)
        C.memset(address + SNAPSHOT_SIZE, 165, 16)
        struct.pack_into('<ii', storage, 0, -9999, -9999)
        empty = api['string_empty']()
        if type(empty) is not int or empty <= 8:
            raise RuntimeError('Native Core FString empty initializer returned an invalid pointer')
        struct.pack_into('<Q', storage, 16, empty)
        try:
            api['unit_snapshot'](unit, address, 0)
            if C.string_at(address + SNAPSHOT_SIZE, 16) != b'\xa5' * 16:
                raise RuntimeError('Native Unit snapshot exceeded its source storage')
            scalar = struct.unpack_from('<I', storage, 28)[0]
        finally:
            data = struct.unpack_from('<Q', storage, 16)[0]
            if data <= 8:
                raise RuntimeError('Native Unit snapshot left an invalid FString pointer')
            if data != empty:
                api['string_free'](data - 8)
                string_freed = True
        yield encode(NativeValues(scalar))
    finally:
        if unit_checked:
            api['release_unit'](unit, 1)

def produce_record(sequence, core, context, fields, *, normalizer_transform_present, per_thread_hook_present, writer_metadata_callback_present, padding_policy='headless-zero-uninitialized-stack', read=None, native_api=None, query_diagnostic=None, core_sha256='d7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'):
    """Compatibility wrapper returning bytes after closing the native Unit lease.

    Callers that enqueue synchronously and need source-order lifetime should use
    ``produce_record_lease`` and keep the enqueue inside its ``with`` block.
    """
    with produce_record_lease(sequence, core, context, fields, normalizer_transform_present=normalizer_transform_present, per_thread_hook_present=per_thread_hook_present, writer_metadata_callback_present=writer_metadata_callback_present, padding_policy=padding_policy, read=read, native_api=native_api, query_diagnostic=query_diagnostic, core_sha256=core_sha256) as record:
        return record
