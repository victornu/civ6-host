"""A479's real Unit command query, retaining its maps through record emission."""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import ctypes as C
from functools import lru_cache
import struct
from civ6_host.runtime.native.native_event_a479f83f import validate_fields
from civ6_host.runtime.native.native_event_a479f83f import verify_source_evidence
from civ6_host.runtime.native.native_setup import local_reader
from civ6_host.runtime import xp1_combat_profile as _combat_source
CORE_IMAGE_BASE = 6442450944
MAP_SIZE, MAP_VTABLE = (88, 8507296)
COMMAND, RESULT_KEY = (3035485247, 827475943)
GUARD = b'\xd7' * 16
METHODS = {'get_service': (4383232, C.c_void_p, (C.c_void_p,)), 'release_outer': (1388640, None, (C.c_void_p,)), 'map_ctor': (7621504, C.c_void_p, (C.c_void_p,)), 'map_dtor': (7621792, None, (C.c_void_p,)), 'map_lookup': (7625984, C.c_void_p, (C.c_void_p, C.c_uint32)), 'query': (4442432, C.c_uint8, (C.c_void_p, C.c_void_p, C.c_uint32, C.c_void_p, C.c_uint8, C.c_void_p)), 'release_service': (4442480, None, (C.c_void_p,))}
SLOTS = ((7987232, 224, 4383232), (7987232, 8, 1388640), (7995816, 16, 4442432), (7995816, 8, 4442480), (MAP_VTABLE, 96, 7625984))

def _read(read, address, length):
    if type(address) is not int or address <= 0 or (not 0 < length <= 4096):
        raise ValueError('Invalid bounded promotion query read')
    raw = read(address, length)
    if not isinstance(raw, (bytes, bytearray, memoryview)) or len(raw) != length:
        raise ValueError('Incomplete promotion query read')
    return bytes(raw)

def _qword(read, address):
    return struct.unpack('<Q', _read(read, address, 8))[0]

@lru_cache(maxsize=1)
def _method_fragments(*, core_sha256='d7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'):
    """Normalize only the seven complete, explicitly pinned native methods."""
    _layout = _combat_source.promotion_layout(core_sha256, METHODS, SLOTS)
    proof = verify_source_evidence()
    proof = _combat_source.promotion_proof(core_sha256, proof)
    source_names = {'get_service': 'outer_e0', 'release_outer': 'outer_release', 'map_ctor': 'map_constructor', 'map_dtor': 'map_destructor', 'map_lookup': 'map_lookup', 'query': 'service_query', 'release_service': 'service_release'}
    methods = []
    for name, (rva, _, _) in _layout.methods.items():
        capture = proof['core_functions'][source_names[name]]
        entry = capture.get('start_va', capture.get('entry_va'))
        if entry is None or int(entry, 16) != CORE_IMAGE_BASE + rva:
            raise RuntimeError('Promotion query source method entry changed')
        fragments = capture.get('fragments')
        instructions = tuple((i for f in fragments for i in f['instructions'])) if fragments else capture['instructions']
        code = {}
        for instruction in instructions:
            address = int(instruction['va'], 16) - CORE_IMAGE_BASE
            for offset, byte in enumerate(bytes.fromhex(instruction['bytes'])):
                at = address + offset
                if at in code and code[at] != byte:
                    raise RuntimeError('Promotion query source captures disagree')
                code[at] = byte
        if rva not in code:
            raise RuntimeError('Promotion query source lacks its entry instruction')
        parts = []
        for address, byte in sorted(code.items()):
            if not parts or parts[-1][0] + len(parts[-1][1]) != address:
                parts.append((address, bytearray()))
            parts[-1][1].append(byte)
        methods.append((rva, tuple(((address, bytes(raw)) for address, raw in parts))))
    return tuple(sorted(methods))

def verify_live_methods(base, read, *, core_sha256='d7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'):
    _layout = _combat_source.promotion_layout(core_sha256, METHODS, SLOTS)
    for entry, parts in _method_fragments(core_sha256=core_sha256):
        for rva, expected in parts:
            for offset in range(0, len(expected), 4096):
                chunk = expected[offset:offset + 4096]
                if _read(read, base + rva + offset, len(chunk)) != chunk:
                    raise ValueError(f'Promotion query native method changed at {entry:#x}')
    for table, offset, target in _layout.slots:
        if _qword(read, base + table + offset) != base + target:
            raise ValueError('Promotion query native virtual slot changed')

class _Storage:

    def __init__(self, size):
        self.size = size
        self.buffer = C.create_string_buffer(size + 32)
        self.pointer = C.addressof(self.buffer) + 16
        C.memmove(self.pointer - 16, GUARD, 16)
        C.memmove(self.pointer + size, GUARD, 16)
        self.closed = False

    def check(self):
        if self.buffer.raw[:16] != GUARD or self.buffer.raw[-16:] != GUARD:
            raise RuntimeError('Promotion query exceeded guarded native storage')

def first_result_value(variant_pointer, read):
    """Mirror the native typed-array test and read only its first DWORD.

    Missing or incompatible variants produce the source's initialized FFFFFFFF.
    A nonnull typed array whose first element cannot be read is refused.
    """
    if not variant_pointer:
        return 4294967295
    raw = _read(read, variant_pointer, 24)
    flags = struct.unpack_from('<I', raw, 20)[0]
    if not flags & 536870912 or struct.unpack_from('<H', raw)[0] != 2 or (not flags & 16777215):
        return 4294967295
    data = struct.unpack_from('<Q', raw, 8)[0]
    return struct.unpack('<I', _read(read, data, 4))[0]

def query_and_emit_promotion(core, context, fields, record_sink, *, read=None, native_api=None, core_sha256='d7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'):
    """Run after the experience record; emit a promotion before releasing maps.

    Unknown or interrupted native ownership is retained on the exception for
    fatal worker teardown. It is never retried or cleaned up by guessing.
    """
    _layout = _combat_source.promotion_layout(core_sha256, METHODS, SLOTS)
    verify_source_evidence()
    validate_fields(fields)
    base = getattr(core, '_handle', None)
    if type(base) is not int or base <= 0 or type(context) is not int or (context <= 0) or (not callable(record_sink)):
        raise ValueError('Promotion query requires a live Core/context and record sink')
    read = local_reader() if read is None else read
    verify_live_methods(base, read, core_sha256=core_sha256)
    if _qword(read, context) != base + _layout.outer_table or _qword(read, context + 8) == 0:
        raise ValueError('Promotion query requires the live original outer context')
    if native_api is None:
        api = {name: C.WINFUNCTYPE(restype, *args)(base + rva) for name, (rva, restype, args) in _layout.methods.items()}
    else:
        if type(native_api) is not dict or set(native_api) != set(_layout.methods) or any((not callable(value) for value in native_api.values())):
            raise ValueError('Promotion query test API requires every exact source operation')
        api = native_api
    storage = []
    service = 0
    try:
        service = api['get_service'](context)
        api['release_outer'](context)
        if not service:
            return {'service_present': False, 'query_executed': False, 'raw_native_result': None, 'promotion_index': None, 'promotion_record_emitted': False, 'native_maps_destroyed': 0, 'service_released': False}
        if _qword(read, service) != base + _layout.service_table:
            raise ValueError('Promotion query returned an unknown command service')
        for _ in range(2):
            item = _Storage(MAP_SIZE)
            storage.append(item)
            result = api['map_ctor'](item.pointer)
            item.check()
            if result != item.pointer or _qword(read, item.pointer) != base + _layout.map_table or _read(read, item.pointer + 80, 4) != bytes(4):
                raise RuntimeError('Promotion parameter map constructor contract changed')
        descriptor = _Storage(8)
        storage.append(descriptor)
        descriptor_bytes = struct.pack('<HHI', fields.owner, 1, fields.unit_id)
        C.memmove(descriptor.pointer, descriptor_bytes, 8)
        args, results = storage[:2]
        raw_result = api['query'](service, descriptor.pointer, COMMAND, args.pointer, 1, results.pointer)
        for item in storage:
            item.check()
        if type(raw_result) is not int or not 0 <= raw_result <= 255:
            raise ValueError('Promotion query must return the actual native AL byte')
        if C.string_at(descriptor.pointer, 8) != descriptor_bytes:
            raise RuntimeError('Promotion query unexpectedly changed its unit descriptor')
        for item in (args, results):
            if _qword(read, item.pointer) != base + _layout.map_table:
                raise RuntimeError('Promotion query replaced a native map identity')
        value = None
        if raw_result:
            variant = api['map_lookup'](results.pointer, RESULT_KEY)
            for item in storage:
                item.check()
            value = first_result_value(variant, read)
            record_sink(value)
        for item in (results, args):
            item.check()
            if _qword(read, item.pointer) != base + _layout.map_table:
                raise RuntimeError('Promotion map changed before its native destructor')
            api['map_dtor'](item.pointer)
            item.check()
            item.closed = True
        if _qword(read, service) != base + _layout.service_table:
            raise RuntimeError('Promotion command service changed before release')
        api['release_service'](service)
    except BaseException as exc:
        exc.native_promotion_storage = storage
        exc.native_promotion_service = service
        raise
    return {'service_present': True, 'query_executed': True, 'raw_native_result': raw_result, 'promotion_index': value, 'promotion_record_emitted': bool(raw_result), 'native_maps_destroyed': 2, 'service_released': True}
