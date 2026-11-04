"""Source-backed, bounded producer model for EXE event 0x359703A2.

This models the observed headless profile only: no per-thread hook and no
writer metadata callback. It emits the center plot followed by six native
neighbors, preserving the EXE's order and reused plot-value behavior.
"""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import ctypes as C
import struct
from pathlib import Path
from civ6_host.runtime.native.native_application_mirror import decode_scalar
from civ6_host.runtime.native.native_host_events import copy_eight_byte_variant
from civ6_host.runtime.native.native_source_cache import load_pinned_json
EVENT_KIND = 899089314
BLOB_KEY = 2353434172
SELECTOR_KEY = 2716180809
RECORD_TYPE = 183
RECORD_SIZE = 96
EXE_SHA256 = 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63'
PINNED_EVIDENCE_SHA256 = 'c0154cc9f7b6a0844ce352dbde95040bbaa2afbbffdf37c990644c7e0e7665a5'
OUTER_VTABLE, OUTER_MAP_SLOT, OUTER_MAP_GET = (7987232, 168, 4382784)
MAP_VTABLE, MAP_RELEASE_SLOT, MAP_RELEASE = (7991792, 8, 4416608)
MAP_GET_PLOT_SLOT, MAP_GET_PLOT = (64, 4418176)
MAP_NEIGHBOR_SLOT, MAP_NEIGHBOR_THUNK, MAP_NEIGHBOR_IMPL = (136, 4417408, 55520)
PLOT_VTABLE, PLOT_RELEASE_SLOT, PLOT_RELEASE = (7994424, 8, 4435728)
PLOT_VALUE_SLOT, PLOT_VALUE_THUNK = (48, 4435888)

def verify_source_evidence() -> None:
    if not PINNED_EVIDENCE_SHA256:
        raise RuntimeError('359703A2 source evidence has not been pinned')
    path = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_event_359703a2.py')))).resolve().parents[1] / 'evidence' / 'native-event-359703a2' / f'{PINNED_EVIDENCE_SHA256}.json'
    evidence = load_pinned_json(path, PINNED_EVIDENCE_SHA256)
    if evidence.get('image', {}).get('exe_sha256') != EXE_SHA256 or evidence.get('event', {}).get('kind') != '0x359703a2' or evidence.get('record', {}).get('type') != '0xb7':
        raise RuntimeError('359703A2 evidence identity changed')

def decode_fields(fields: dict[int, bytes], read) -> dict:
    verify_source_evidence()
    if set(fields) != {BLOB_KEY, SELECTOR_KEY}:
        raise ValueError('Unverified 0x359703A2 fields or optional hook metadata')
    if decode_scalar(fields[SELECTOR_KEY], 3) != 0:
        raise ValueError('Unverified 0x359703A2 selector')
    raw = copy_eight_byte_variant(fields[BLOB_KEY], read, expected_tag=0)
    x, y = struct.unpack('<ii', raw)
    return {'position_bytes': raw, 'x': x, 'y': y, 'selector': 0}

def query_plot_words(core, context, position: dict, *, read=None, native_api=None, core_sha256='d7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3') -> list[dict]:
    """Run the exact native center + six-neighbor read path.

    The initial center plot must exist because the EXE leaves its local DWORD
    uninitialized on a null center. Null neighbors retain the last DWORD,
    matching the callback. Coordinates come only from the native +0x88 method.
    """
    OUTER_VTABLE = globals()['OUTER_VTABLE']
    OUTER_MAP_GET = globals()['OUTER_MAP_GET']
    MAP_VTABLE = globals()['MAP_VTABLE']
    MAP_RELEASE = globals()['MAP_RELEASE']
    MAP_GET_PLOT = globals()['MAP_GET_PLOT']
    PLOT_VTABLE = globals()['PLOT_VTABLE']
    PLOT_RELEASE = globals()['PLOT_RELEASE']
    MAP_NEIGHBOR_THUNK = globals()['MAP_NEIGHBOR_THUNK']
    PLOT_VALUE_THUNK = globals()['PLOT_VALUE_THUNK']
    PLOT_VALUE_SLOT = globals()['PLOT_VALUE_SLOT']
    if core_sha256 != 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3':
        from civ6_host.runtime.foundation_facade_profiles import query_abi
        from civ6_host.runtime.provenance import resource_root
        _foundation_abi = query_abi(core_sha256, resource_root())
        OUTER_VTABLE = _foundation_abi.table('outer')
        OUTER_MAP_GET = _foundation_abi.rva('outer_map')
        MAP_VTABLE = _foundation_abi.table('map')
        MAP_RELEASE = _foundation_abi.rva('release_map')
        MAP_GET_PLOT = _foundation_abi.rva('get_plot')
        PLOT_VTABLE = _foundation_abi.table('plot')
        PLOT_RELEASE = _foundation_abi.rva('release_plot')
        MAP_NEIGHBOR_THUNK = _foundation_abi.rva('neighbor')
        PLOT_VALUE_THUNK = _foundation_abi.rva('plot_value')
        PLOT_VALUE_SLOT = _foundation_abi.slot('plot_value')
    verify_source_evidence()
    if type(position.get('x')) is not int or type(position.get('y')) is not int:
        raise ValueError('Position requires signed native coordinates')
    for coordinate in (position['x'], position['y']):
        if not -(1 << 31) <= coordinate < 1 << 31:
            raise ValueError('Coordinate outside signed int32')
    position_bytes = position.get('position_bytes')
    if type(position_bytes) is not bytes or len(position_bytes) != 8 or struct.unpack('<ii', position_bytes) != (position['x'], position['y']):
        raise ValueError('Position bytes disagree with native input coordinates')
    base = int(core._handle)
    if read is None:
        from civ6_host.runtime.native.native_setup import local_reader
        read = local_reader()

    def slot(vtable, offset, target):
        if int.from_bytes(read(base + vtable + offset, 8), 'little') != base + target:
            raise ValueError(f'Unexpected Core vtable slot {vtable:#x}+{offset:#x}')

    def check(obj, vtable):
        if not obj or int.from_bytes(read(obj, 8), 'little') != base + vtable:
            raise ValueError('Unexpected Core map/plot wrapper')
    check(context, OUTER_VTABLE)
    slot(OUTER_VTABLE, OUTER_MAP_SLOT, OUTER_MAP_GET)
    if native_api is None:
        outer_map = C.WINFUNCTYPE(C.c_void_p, C.c_void_p)(base + OUTER_MAP_GET)
        release_map = C.WINFUNCTYPE(None, C.c_void_p)(base + MAP_RELEASE)
        get_plot = C.WINFUNCTYPE(C.c_void_p, C.c_void_p, C.c_int32, C.c_int32)(base + MAP_GET_PLOT)
        neighbor = C.WINFUNCTYPE(C.c_void_p, C.c_void_p, C.c_void_p, C.c_void_p, C.c_uint32)(base + MAP_NEIGHBOR_THUNK)
        release_plot = C.WINFUNCTYPE(None, C.c_void_p)(base + PLOT_RELEASE)
        get_value = C.WINFUNCTYPE(C.c_uint32, C.c_void_p)(base + PLOT_VALUE_THUNK)
    else:
        required = {'outer_map', 'release_map', 'get_plot', 'neighbor', 'release_plot', 'get_value'}
        if set(native_api) != required:
            raise ValueError('Native map/plot test seam must provide all six entrypoints')
        outer_map, release_map, get_plot, neighbor, release_plot, get_value = (native_api[k] for k in ('outer_map', 'release_map', 'get_plot', 'neighbor', 'release_plot', 'get_value'))
    map_obj = outer_map(context)
    if not map_obj:
        raise ValueError('Native map is unavailable')
    try:
        check(map_obj, MAP_VTABLE)
        slot(MAP_VTABLE, MAP_RELEASE_SLOT, MAP_RELEASE)
        slot(MAP_VTABLE, MAP_GET_PLOT_SLOT, MAP_GET_PLOT)
        slot(MAP_VTABLE, MAP_NEIGHBOR_SLOT, MAP_NEIGHBOR_THUNK)
        slot(PLOT_VTABLE, PLOT_RELEASE_SLOT, PLOT_RELEASE)
        slot(PLOT_VTABLE, PLOT_VALUE_SLOT, PLOT_VALUE_THUNK)

        def plot_word(x, y):
            plot = get_plot(map_obj, x, y)
            if not plot:
                return None
            try:
                check(plot, PLOT_VTABLE)
                return int(get_value(plot)) & 4294967295
            finally:
                release_plot(plot)
        center = (position['x'], position['y'])
        value = plot_word(*center)
        if value is None:
            raise ValueError('Native callback leaves center value uninitialized for a null plot')
        rows = [{'direction': None, 'x': center[0], 'y': center[1], 'plot_value': value}]
        for direction in range(6):
            output = C.create_string_buffer(24)
            input_xy = C.create_string_buffer(position['position_bytes'], 8)
            C.memset(C.addressof(output), 165, 24)
            returned = neighbor(map_obj, C.addressof(output), C.addressof(input_xy), direction)
            if returned != C.addressof(output):
                raise ValueError('Native map neighbor returned an unexpected output pointer')
            if output.raw[8:] != b'\xa5' * 16:
                raise ValueError('Native neighbor method wrote beyond its proven 8-byte output')
            x, y = struct.unpack_from('<ii', output.raw, 0)
            neighbor_value = plot_word(x, y)
            if neighbor_value is not None:
                value = neighbor_value
            rows.append({'direction': direction, 'x': x, 'y': y, 'plot_value': value})
        return rows
    finally:
        release_map(map_obj)

def encode_record(sequence: int, row: dict, *, hook_present=False, writer_metadata_callback_present=False, padding_policy='zero') -> bytes:
    verify_source_evidence()
    if type(sequence) is not int or not 1 <= sequence <= 4294967295:
        raise ValueError('Sequence must be a nonzero uint32')
    if hook_present is not False or writer_metadata_callback_present is not False:
        raise ValueError('Optional native callbacks require source-backed behavior')
    if padding_policy != 'zero':
        raise ValueError('Only explicit zero padding is supported')
    x, y, value = (row.get('x'), row.get('y'), row.get('plot_value'))
    if any((type(v) is not int for v in (x, y, value))):
        raise ValueError('Record requires native x/y and plot DWORD')
    if not (-2147483648 <= x <= 2147483647 and -2147483648 <= y <= 2147483647 and (0 <= value <= 4294967295)):
        raise ValueError('Record field outside native integer width')
    record = bytearray(RECORD_SIZE)
    struct.pack_into('<IIHHI', record, 16, 4294967295, 4294967295, 65535, 0, 4294967295)
    for offset in (32, 40, 48, 56):
        struct.pack_into('<HHI', record, offset, 65535, 0, 4294967295)
    struct.pack_into('<QI', record, 64, 0, 0)
    struct.pack_into('<IIII', record, 0, RECORD_SIZE, RECORD_TYPE, sequence, 0)
    struct.pack_into('<I', record, 80, sequence)
    struct.pack_into('<Q', record, 84, x & 4294967295 | (y & 4294967295) << 32)
    struct.pack_into('<I', record, 92, value)
    return bytes(record)

def encode_records(first_sequence: int, rows: list[dict], **kwargs) -> list[bytes]:
    verify_source_evidence()
    if len(rows) != 7:
        raise ValueError('The source callback emits exactly seven ordered records')
    if type(first_sequence) is not int or first_sequence < 1 or first_sequence + 6 > 4294967295:
        raise ValueError('Seven consecutive uint32 sequence values required')
    return [encode_record(first_sequence + i, row, **kwargs) for i, row in enumerate(rows)]
