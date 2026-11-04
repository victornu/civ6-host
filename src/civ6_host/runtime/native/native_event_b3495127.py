"""B3495127 native player-facade queries and source-pinned C2 record."""
from __future__ import annotations
from civ6_host.runtime import faith_event_profile as _faith_events
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import ctypes as C
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
import struct
from civ6_host.runtime.native.native_application_mirror import decode_scalar
from civ6_host.runtime.native.native_source_cache import load_pinned_json
EVENT_KIND, RECORD_TYPE, RECORD_SIZE = (3007926567, 194, 96)
SELECTOR_KEY, PLAYER_KEY = (2716180809, 3606901732)
PINNED_EVIDENCE_SHA256 = '1c918a33a49cf6d1f43b9b6819da35fbb05f777ae88fd1c023a42b4db9800265'
_PROOF = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_event_b3495127.py')))).resolve().parents[1] / 'evidence/native-event-b3495127' / f'{PINNED_EVIDENCE_SHA256}.json'
_TABLES = {'outer': (7987232, {8: 1388640, 184: 4382880}), 'player': (7992320, {8: 4421040, 224: 4423072}), 'facade': (7993576, {8: 4429728, 16: 4429984, 24: 4429920})}

def verify_source_evidence():
    proof = load_pinned_json(_PROOF, PINNED_EVIDENCE_SHA256)
    if proof['schema'] != 'civ6rl.native_event_b3495127.static.v1' or proof['images']['exe_sha256'] != 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63' or proof['images']['core_sha256'] != 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3' or (proof['registration']['callback_va'] != '0x140146520') or (proof['registration']['kind'] != EVENT_KIND) or (proof['captures']['callback']['code_sha256'] != '0ba01d852ef462610473e49ad169c968d1675f7772a980e4587a16c7ffbe00b5') or (proof['captures']['writer']['code_sha256'] != '983448c23b4e5bfdb7a02f28bbb3e7d523031360dd0eb6d09f0510b645709f97'):
        raise RuntimeError('B3495127 source identity changed')
    for name, (table, slots) in _TABLES.items():
        row = proof['tables'][name]
        if int(row['table_rva'], 16) != table or any((int(row['slots'][hex(slot)]['target_rva'], 16) != target for slot, target in slots.items())):
            raise RuntimeError('B3495127 pinned native ABI changed')
    return proof

@dataclass(frozen=True)
class EventFields:
    selector: int
    player_id: int

@dataclass(frozen=True)
class NativeValues:
    slot10_dword: int
    slot18_dword: int

def _validate_fields(fields):
    if not isinstance(fields, EventFields) or type(fields.selector) is not int or (not 0 <= fields.selector <= 4294967295) or (type(fields.player_id) is not int) or (not 0 <= fields.player_id < 64):
        raise ValueError('B3495127 requires exact selector and configured player slot0..63')

def decode_fields(raw_fields) -> EventFields:
    verify_source_evidence()
    if not isinstance(raw_fields, dict) or set(raw_fields) != {SELECTOR_KEY, PLAYER_KEY}:
        raise ValueError('B3495127 requires exactly two source-backed scalar keys')
    if any((type(raw) is not bytes or len(raw) != 24 for raw in raw_fields.values())):
        raise ValueError('B3495127 requires complete byte variants')
    fields = EventFields(decode_scalar(raw_fields[SELECTOR_KEY], 3), decode_scalar(raw_fields[PLAYER_KEY], 2))
    _validate_fields(fields)
    return fields

def _profile(sequence, fields, normalizer_transform_present, per_thread_hook_present, writer_metadata_callback_present):
    verify_source_evidence()
    _validate_fields(fields)
    if type(sequence) is not int or not 1 <= sequence <= 4294967295:
        raise ValueError('B3495127 requires a nonzero uint32 queue sequence')
    if normalizer_transform_present is not False or per_thread_hook_present is not False or writer_metadata_callback_present is not False:
        raise ValueError('B3495127 transformation/hook/metadata service profile is unsupported')

def encode_record(sequence, fields, values, *, normalizer_transform_present, per_thread_hook_present, writer_metadata_callback_present):
    _profile(sequence, fields, normalizer_transform_present, per_thread_hook_present, writer_metadata_callback_present)
    if not isinstance(values, NativeValues) or any((type(v) is not int or not 0 <= v <= 4294967295 for v in (values.slot10_dword, values.slot18_dword))):
        raise ValueError('B3495127 requires two exact native DWORD results')
    record = bytearray(RECORD_SIZE)
    struct.pack_into('<IIII', record, 0, RECORD_SIZE, RECORD_TYPE, sequence, 0)
    record[16:24] = b'\xff' * 8
    record[24:64] = bytes.fromhex('ffff0000ffffffff') * 5
    struct.pack_into('<IIII', record, 80, sequence, fields.player_id, values.slot10_dword, values.slot18_dword)
    return bytes(record)

def _qword(read, pointer):
    raw = read(pointer, 8)
    if not isinstance(raw, (bytes, bytearray, memoryview)) or len(raw) != 8:
        raise ValueError('B3495127 incomplete pointer inspection')
    return struct.unpack('<Q', raw)[0]

def _check(read, base, pointer, name, *, core_sha256='d7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'):
    table, slots = _faith_events.select_tables(core_sha256, _TABLES)[name]
    actual = _qword(read, pointer) if pointer else 0
    if not pointer or actual != base + table:
        raise ValueError(f'Unexpected B3495127 {name}: pointer={pointer or 0:#x}, vtable={actual:#x}')
    for slot, target in slots.items():
        if _qword(read, base + table + slot) != base + target:
            raise ValueError('B3495127 changed ' + name + ' interface slot')

def _api(base, native_api, *, core_sha256='d7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'):
    entries = {'get_player': (4382880, C.c_void_p, (C.c_void_p, C.c_int32)), 'release_context': (1388640, None, (C.c_void_p,)), 'release_player': (4421040, None, (C.c_void_p,)), 'get_facade': (4423072, C.c_void_p, (C.c_void_p,)), 'release_facade': (4429728, None, (C.c_void_p,)), 'get_slot18': (4429920, C.c_void_p, (C.c_void_p, C.c_void_p)), 'get_slot10': (4429984, C.c_void_p, (C.c_void_p, C.c_void_p))}
    entries = _faith_events.select_specs(core_sha256, entries)
    if native_api is not None:
        if not isinstance(native_api, dict) or set(native_api) != set(entries):
            raise ValueError('B3495127 test seam requires all seven native operations')
        return native_api
    return {name: C.WINFUNCTYPE(result, *args)(base + rva) for name, (rva, result, args) in entries.items()}

@contextmanager
def produce_record_lease(sequence, core, context, fields, *, normalizer_transform_present, per_thread_hook_present, writer_metadata_callback_present, read=None, native_api=None, query_diagnostic=None, core_sha256='d7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'):
    """Yield a record while keeping the EXE-retained facade/player alive.

    The original callback calls the native writer before releasing either
    reference. A dispatcher should enqueue inside this context. Source-defined
    absent context/player/facade paths yield None and produce no queue record.
    """
    profile = dict(normalizer_transform_present=normalizer_transform_present, per_thread_hook_present=per_thread_hook_present, writer_metadata_callback_present=writer_metadata_callback_present)
    _profile(sequence, fields, **profile)
    if query_diagnostic is not None and (not isinstance(query_diagnostic, dict)):
        raise ValueError('B3495127 query diagnostic must be a dictionary')
    base = int(core._handle)
    if base <= 0 or type(context) is not int or context < 0:
        raise ValueError('B3495127 requires valid Core base/context addresses')

    def absent(reason):
        if query_diagnostic is not None:
            query_diagnostic.update(record_produced=False, read_skipped_reason=reason, native_getters_executed=False)
    if not context:
        absent('context-null')
        yield None
        return
    if read is None:
        from civ6_host.runtime.native.native_setup import local_reader
        read = local_reader()
    _check(read, base, context, 'outer', core_sha256=core_sha256)
    api = _api(base, native_api, core_sha256=core_sha256)
    try:
        player = api['get_player'](context, fields.player_id)
    finally:
        api['release_context'](context)
    player_checked = facade_checked = False
    try:
        if not player:
            absent('player-null')
            yield None
            return
        _check(read, base, player, 'player', core_sha256=core_sha256)
        player_checked = True
        if not (_qword(read, player + 8) or _qword(read, player + 16)):
            raise ValueError('B3495127 player has neither source-backed owner pointer')
        facade = api['get_facade'](player)
        if not facade:
            absent('facade-null')
            yield None
            return
        try:
            _check(read, base, facade, 'facade', core_sha256=core_sha256)
            facade_checked = True
            if not (_qword(read, facade + 8) or _qword(read, facade + 16)):
                raise ValueError('B3495127 facade has neither source-backed owner pointer')
            output = C.create_string_buffer(4 + 16)
            address = C.addressof(output)
            C.memset(address + 4, 165, 16)

            def query(name):
                returned = api[name](facade, address)
                if returned != address:
                    raise RuntimeError('B3495127 getter returned an unexpected output pointer')
                if output.raw[4:] != b'\xa5' * 16:
                    raise RuntimeError('B3495127 getter exceeded its four-byte output')
                return struct.unpack_from('<I', output)[0]
            slot18 = query('get_slot18')
            slot10 = query('get_slot10')
            result = encode_record(sequence, fields, NativeValues(slot10, slot18), **profile)
            if query_diagnostic is not None:
                query_diagnostic.update(record_produced=True, read_skipped_reason=None, native_getters_executed=True, output_bytes=4, slot10_dword=slot10, slot18_dword=slot18)
            yield result
        finally:
            if facade_checked:
                api['release_facade'](facade)
    finally:
        if player_checked:
            api['release_player'](player)

def produce_record(sequence, core, context, fields, **kwargs):
    """Compatibility wrapper; releases references before returning the bytes.

    Queue dispatchers should use ``produce_record_lease`` and enqueue inside
    its context to preserve the original callback/writer lifetime ordering.
    """
    with produce_record_lease(sequence, core, context, fields, **kwargs) as record:
        return record
