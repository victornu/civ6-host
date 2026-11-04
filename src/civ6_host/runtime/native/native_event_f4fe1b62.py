"""Bounded source model for EXE deferred host event 0xF4FE1B62.

The callback derives one DWORD by querying a Core plot-like interface. This
module never substitutes that value: callers must provide it from an exact,
successful native query before a record can be encoded.
"""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import hashlib
import json
import struct
import ctypes as C
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from civ6_host.runtime.native.native_application_mirror import decode_scalar
from civ6_host.runtime.native.native_host_events import copy_eight_byte_variant
EVENT_KIND = 4110293858
CALLBACK_RVA = 1360576
WRITER_RVA = 1275456
NORMALIZER_RVA = 1876688
RECORD_SIZE = 112
RECORD_TYPE = 180
POSITION_KEY = 2353434172
SELECTOR_KEY = 2716180809
VALUE_KEY = 3606901732
EXE_SHA256 = 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63'
PINNED_EVIDENCE_SHA256 = 'd579004ffcb9cebad2235aebd41f430a24bbbff2fca66386c90e9a08d032cc11'
OUTER_VTABLE = 7987232
OUTER_MAP_SLOT = 168
OUTER_MAP_GET = 4382784
MAP_VTABLE = 7991792
MAP_RELEASE_SLOT, MAP_RELEASE = (8, 4416608)
MAP_GET_PLOT_SLOT, MAP_GET_PLOT = (64, 4418176)
PLOT_VTABLE = 7994424
PLOT_RELEASE_SLOT, PLOT_RELEASE = (8, 4435728)
PLOT_VALUE_SLOT, PLOT_VALUE = (32, 4436736)

@dataclass(frozen=True)
class EventFields:
    position_bytes: bytes
    x: int
    y: int
    selector: int
    value: int

def verify_source_evidence() -> None:
    if not PINNED_EVIDENCE_SHA256:
        raise RuntimeError('F4FE1B62 static source evidence is not pinned')
    path = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_event_f4fe1b62.py')))).resolve().parents[1] / 'evidence' / 'native-event-f4fe1b62' / f'{PINNED_EVIDENCE_SHA256}.json'
    raw = _resolve_resource_path(path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != PINNED_EVIDENCE_SHA256:
        raise RuntimeError('Pinned F4FE1B62 evidence bytes changed')
    doc = json.loads(raw)
    if doc.get('schema') != 'civ6rl.native_event_f4fe1b62.v1' or doc.get('image', {}).get('exe_sha256') != EXE_SHA256 or doc.get('event', {}).get('kind') != '0xf4fe1b62' or (doc.get('event', {}).get('callback_va') != '0x14014c2c0') or (doc.get('writer_contract', {}).get('record_type') != '0xb4'):
        raise RuntimeError('F4FE1B62 source proof identity changed')

def _u32(value: int, label: str) -> int:
    if type(value) is not int or not 0 <= value <= 4294967295:
        raise ValueError(f'{label} must be uint32')
    return value

def decode_fields(fields: dict[int, bytes], read) -> EventFields:
    verify_source_evidence()
    if not isinstance(fields, dict) or set(fields) != {POSITION_KEY, SELECTOR_KEY, VALUE_KEY}:
        raise ValueError('F4FE1B62 requires exactly the position, A1E5, and D6 fields')
    selector = decode_scalar(fields[SELECTOR_KEY], 3)
    value = decode_scalar(fields[VALUE_KEY], 2)
    raw = copy_eight_byte_variant(fields[POSITION_KEY], read, expected_tag=0)
    x, y = struct.unpack('<ii', raw)
    return EventFields(raw, x, y, selector, value)

@contextmanager
def query_plot_value_lease(core, context: int, fields: EventFields, *, read=None, native_api=None, core_sha256='d7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'):
    """Query the plot and keep its reference through synchronous enqueue.

    The test seam injects callables only; all receiver vtables and slots are
    still checked against the pinned Core image. No EXE or DLL is launched.
    """
    OUTER_VTABLE = globals()['OUTER_VTABLE']
    OUTER_MAP_GET = globals()['OUTER_MAP_GET']
    MAP_VTABLE = globals()['MAP_VTABLE']
    MAP_RELEASE = globals()['MAP_RELEASE']
    MAP_GET_PLOT = globals()['MAP_GET_PLOT']
    PLOT_VTABLE = globals()['PLOT_VTABLE']
    PLOT_RELEASE = globals()['PLOT_RELEASE']
    PLOT_VALUE = globals()['PLOT_VALUE']
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
        PLOT_VALUE = _foundation_abi.rva('plot_owner')
        PLOT_VALUE_SLOT = _foundation_abi.slot('plot_owner')
    verify_source_evidence()
    if not isinstance(fields, EventFields):
        raise TypeError('fields must be decoded EventFields')
    if type(context) is not int or context <= 0:
        raise ValueError('A live Core outer-context address is required')
    if type(fields.x) is not int or type(fields.y) is not int:
        raise ValueError('Position requires signed native coordinates')
    if not -(1 << 31) <= fields.x < 1 << 31 or not -(1 << 31) <= fields.y < 1 << 31 or len(fields.position_bytes) != 8 or (struct.unpack('<ii', fields.position_bytes) != (fields.x, fields.y)):
        raise ValueError('Position bytes and signed coordinates disagree')
    base = int(core._handle)
    if read is None:
        from civ6_host.runtime.native.native_setup import local_reader
        read = local_reader()

    def slot(vtable, offset, target):
        actual = struct.unpack('<Q', read(base + vtable + offset, 8))[0]
        if actual != base + target:
            raise ValueError(f'Unexpected Core vtable slot {vtable:#x}+{offset:#x}')

    def check(obj, vtable, label):
        if not obj or struct.unpack('<Q', read(obj, 8))[0] != base + vtable:
            raise ValueError(f'Unexpected Core {label} wrapper')
    check(context, OUTER_VTABLE, 'outer')
    slot(OUTER_VTABLE, OUTER_MAP_SLOT, OUTER_MAP_GET)
    if native_api is None:
        outer_map = C.WINFUNCTYPE(C.c_void_p, C.c_void_p)(base + OUTER_MAP_GET)
        release_map = C.WINFUNCTYPE(None, C.c_void_p)(base + MAP_RELEASE)
        get_plot = C.WINFUNCTYPE(C.c_void_p, C.c_void_p, C.c_int32, C.c_int32)(base + MAP_GET_PLOT)
        release_plot = C.WINFUNCTYPE(None, C.c_void_p)(base + PLOT_RELEASE)
        get_value = C.WINFUNCTYPE(C.c_int32, C.c_void_p)(base + PLOT_VALUE)
    else:
        required = {'outer_map', 'release_map', 'get_plot', 'release_plot', 'get_value'}
        if not isinstance(native_api, dict) or set(native_api) != required:
            raise ValueError('Native F4FE test seam must provide the five exact entrypoints')
        outer_map, release_map, get_plot, release_plot, get_value = (native_api[name] for name in ('outer_map', 'release_map', 'get_plot', 'release_plot', 'get_value'))
    map_obj = outer_map(context)
    if not map_obj:
        raise ValueError("EXE callback's context+A8 map query returned null")
    map_validated = False
    try:
        check(map_obj, MAP_VTABLE, 'map')
        map_validated = True
        slot(MAP_VTABLE, MAP_RELEASE_SLOT, MAP_RELEASE)
        slot(MAP_VTABLE, MAP_GET_PLOT_SLOT, MAP_GET_PLOT)
        slot(PLOT_VTABLE, PLOT_RELEASE_SLOT, PLOT_RELEASE)
        slot(PLOT_VTABLE, PLOT_VALUE_SLOT, PLOT_VALUE)
        plot = get_plot(map_obj, fields.x, fields.y)
    finally:
        if map_validated:
            release_map(map_obj)
    if not plot:
        raise ValueError('EXE callback leaves its DWORD uninitialized for a null plot')
    plot_validated = False
    try:
        check(plot, PLOT_VTABLE, 'plot')
        plot_validated = True
        yield (int(get_value(plot)) & 4294967295)
    finally:
        if plot_validated:
            release_plot(plot)

def query_plot_value(*args, **kwargs) -> int:
    """Standalone diagnostic query; dispatchers must use query_plot_value_lease."""
    with query_plot_value_lease(*args, **kwargs) as value:
        return value

def encode_record(sequence: int, fields: EventFields, *, plot_value: int, plot_query_succeeded: bool, producer_hook_present: bool=False, writer_service_present: bool=False, padding_policy: str) -> bytes:
    """Encode the native B4 record only after the callback's plot query succeeds.

    The native callback leaves its plot DWORD uninitialized if the query chain
    returns null, so this function requires `plot_query_succeeded is True` and
    an explicit uint32 result. Its optional producer hook and writer service
    are refused. Unwritten writer bytes are zero-filled only under the named
    deterministic diagnostic policy.
    """
    verify_source_evidence()
    if type(sequence) is not int or not 1 <= sequence <= 4294967295:
        raise ValueError('sequence must be a nonzero uint32')
    if not isinstance(fields, EventFields):
        raise TypeError('fields must be decoded EventFields')
    if type(fields.position_bytes) is not bytes or len(fields.position_bytes) != 8:
        raise ValueError('position must preserve exactly eight native bytes')
    if struct.unpack('<ii', fields.position_bytes) != (fields.x, fields.y):
        raise ValueError('position bytes and coordinates disagree')
    _u32(fields.selector, 'selector')
    _u32(fields.value, 'value')
    _u32(plot_value, 'plot_value')
    if plot_query_succeeded is not True:
        raise ValueError('native plot query must have succeeded; null leaves a stack DWORD uninitialized')
    if producer_hook_present is not False or writer_service_present is not False:
        raise ValueError('optional callback paths are not modeled')
    if padding_policy != 'headless-zero-initialization':
        raise ValueError('explicit headless padding policy is required')
    record = bytearray(RECORD_SIZE)
    struct.pack_into('<IIHHI', record, 16, 4294967295, 4294967295, 65535, 0, 4294967295)
    for offset in (32, 40, 48, 56):
        struct.pack_into('<HHI', record, offset, 65535, 0, 4294967295)
    struct.pack_into('<Q', record, 64, 0)
    struct.pack_into('<I', record, 72, 0)
    struct.pack_into('<IIII', record, 0, RECORD_SIZE, RECORD_TYPE, sequence, 0)
    struct.pack_into('<I', record, 80, sequence)
    record[84:92] = fields.position_bytes
    struct.pack_into('<II', record, 92, plot_value, fields.value)
    return bytes(record)
