"""Source-selected XP2 position calls for storm and random-event records.

The retained B0 map facade is borrowed. Index conversion acquires a live map
facade from the borrowed outer context and releases that wrapper before return.
Only native calls compute coordinates or map indices. This module admits the
valid-index domain shared by EXE F1C00 and the official Map+68 method; it does
not substitute that method's sentinel branch for unchecked EXE arithmetic.
"""
from __future__ import annotations

from collections.abc import Callable
import ctypes as C
from dataclasses import dataclass
import struct

from .a0_family_source import _path, verify_pinned_files
from .configuration_profiles import _source
from .saved_load_profiles import XP2_CORE_SHA256

SOURCE = ('work/host-extensions/xp2-weather-position/source-profile-v1.json',
          '4dd137d1ee890d3fd650d61c808ae803a8631610b81a007117acc49d8c635280')
EXE_SHA256 = 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63'
OUTER_TABLE_RVA = 0xA101E8
MAP_TABLE_RVA = 0xA11698
_SLOTS = {'get_map': (OUTER_TABLE_RVA, 0xA8, 0x590300),
          'release_map': (MAP_TABLE_RVA, 8, 0x59A8D0),
          'index_to_position': (MAP_TABLE_RVA, 0x68, 0x59B440),
          'position_index': (MAP_TABLE_RVA, 0x90, 0x59B590)}
_GUARD = bytes.fromhex('cf49d408023a671d9860b32cf4dbbe5a')
Read = Callable[[int, int], bytes]


@dataclass(frozen=True)
class PositionIndexResult:
    """Exact native EAX and mutated pair; original callback pair stays separate."""
    index: int
    x: int
    y: int

    @property
    def position_bytes(self) -> bytes:
        return struct.pack('<ii', self.x, self.y)


def _rows(body):
    return body.get('instructions') or [row for fragment in body['fragments']
                                        for row in fragment['instructions']]


def source() -> dict:
    p = _source(SOURCE)
    if (p.get('schema') != 'civ6-host.xp2-weather-position.static.v1'
            or p.get('images') != {'core_sha256': XP2_CORE_SHA256,
                                   'exe_sha256': EXE_SHA256}
            or p.get('validation', {}).get('native_execution') is not False
            or p['validation'].get('process_memory_read') is not False
            or p.get('tables') != {'outer': OUTER_TABLE_RVA, 'map': MAP_TABLE_RVA}
            or set(p.get('slots', {})) != set(_SLOTS)):
        raise ValueError('XP2 weather position source identity differs')
    for name, (table, slot, target) in _SLOTS.items():
        row = p['slots'][name]
        if ((row['table_rva'], row['offset'], row['target_rva']) != (table, slot, target)
                or row['preferred_bytes'] != struct.pack('<Q', 0x180000000+target).hex()):
            raise ValueError('XP2 weather position selector differs: '+name)
    expected = {
        'exe_14d550': {'0x14014d70a': 'call qword ptr [r8 + 0x90]',
                       '0x14014d711': 'mov dword ptr [rbp + 7], eax'},
        'exe_14d290': {'0x14014d43a': 'call qword ptr [r8 + 0x90]',
                       '0x14014d441': 'mov dword ptr [rbp - 0x29], eax'},
        'exe_146d30': {'0x140146e70': 'mov edx, dword ptr [r14]',
                       '0x140146e77': 'call 0x1400f1c00',
                       '0x140146e87': 'mov ecx, dword ptr [rax]',
                       '0x140146e89': 'mov eax, dword ptr [rax + 4]'},
    }
    for name, required in expected.items():
        actual = {row['va']: row['text'] for row in _rows(p['callers'][name]['capture'])}
        if any(actual.get(va) != text for va, text in required.items()):
            raise ValueError('XP2 weather EXE position consumer differs')
    if [row['text'] for row in _rows(p['exe_functions']['0xf1c00'])] != [
            'mov eax, edx', 'cdq', 'idiv dword ptr [rip + 0x21e441f]',
            'mov dword ptr [rcx + 4], eax', 'mov rax, rcx',
            'mov dword ptr [rcx], edx', 'ret']:
        raise ValueError('EXE F1C00 signed-index contract differs')
    for ref in p['references'].values():
        _source((ref['path'], ref['sha256']))
    return p


def source_dependencies() -> dict[str, str]:
    p = source()
    rows = [dict(path=SOURCE[0], sha256=SOURCE[1]), *p['references'].values(),
            *p['extractors']]
    pins = {str(_path(row['path']).resolve()): row['sha256'] for row in rows}
    verify_pinned_files(pins)
    return pins


def _raw(read: Read, address: int, size: int) -> bytes:
    result = read(address, size)
    if type(result) is not bytes or len(result) != size:
        raise ValueError('XP2 weather position requires an exact checked native read')
    return result


def _qword(read: Read, address: int) -> int:
    return struct.unpack('<Q', _raw(read, address, 8))[0]


def verify_live(base: int, read: Read) -> dict:
    """Check selected native bodies/slots against private source, without calls."""
    if type(base) is not int or base <= 0 or not callable(read):
        raise ValueError('XP2 weather position needs a relocated Core and checked reader')
    p = source()
    checked = {}
    for function in p['functions'].values():
        bodies = [function['body']] + [tail['body']
                    for tail in function['out_of_line_tail_jumps']]
        for body in bodies:
            for row in _rows(body):
                rva = int(row.get('rva', '0'), 16) or int(row['va'], 16)-0x180000000
                raw = bytes.fromhex(row['bytes'])
                if rva in checked and checked[rva] != raw:
                    raise ValueError('Conflicting XP2 position source instruction')
                if _raw(read, base+rva, len(raw)) != raw:
                    raise ValueError('XP2 weather position native method bytes differ')
                checked[rva] = raw
    for table, offset, target in _SLOTS.values():
        if _qword(read, base+table+offset) != base+target:
            raise ValueError('XP2 weather position native method slot differs')
    return {'source_sha256': SOURCE[1], 'core_sha256': XP2_CORE_SHA256,
            'checked_instructions': len(checked), 'checked_slots': len(_SLOTS),
            'native_calls_invoked': False}


def _base(core) -> int:
    base = getattr(core, '_handle', None)
    if type(base) is not int or base <= 0:
        raise ValueError('XP2 weather position requires the live Core handle')
    return base


def _api(api, expected, defaults):
    if api is None:
        return defaults()
    if (type(api) is not dict or set(api) != set(expected)
            or not all(callable(value) for value in api.values())):
        raise ValueError('XP2 weather position requires exactly the selected native operations')
    return api


def _buffer(pair: bytes):
    storage = C.create_string_buffer(_GUARD+pair+_GUARD, 40)
    return storage, C.addressof(storage)+16


def _output(storage) -> bytes:
    if storage.raw[:16] != _GUARD or storage.raw[24:] != _GUARD:
        raise BufferError('XP2 weather native position exceeded its eight-byte output')
    return bytes(storage.raw[16:24])


def query_native_position_index(core, facades, position: tuple[int, int] | list[int],
                                *, read: Read | None = None,
                                native_api: dict | None = None) -> PositionIndexResult:
    """Borrow retained B0+90, returning EAX and its normalized in/out pair.

    ``facades.backend`` must still own the same live XP2 context. The reader is
    either that backend's reader or the explicit checked fixture seam. The
    ``call_position_index`` seam receives target VA, borrowed facade and inout8
    address. This adapter never acquires or releases the retained B0 reference.
    """
    if (type(position) not in (tuple, list) or len(position) != 2
            or any(type(value) is not int or not -(1 << 31) <= value < 1 << 31
                   for value in position)):
        raise ValueError('XP2 weather position requires two signed DWORD coordinates')
    base = _base(core)
    backend = getattr(facades, 'backend', None)
    service = getattr(facades, 'cache_service', None)
    if (backend is None or type(service) is not int or service <= 0
            or getattr(backend, 'core_base', None) != base
            or getattr(getattr(backend, 'abi', None), 'core_sha256', None) != XP2_CORE_SHA256
            or not callable(getattr(backend, 'context_alive', None))
            or backend.context_alive() is not True):
        raise ValueError('XP2 weather position requires the retained live XP2 B0 owner')
    read = read if read is not None else getattr(backend, 'read', None)
    verify_live(base, read)
    wrapper = _raw(read, service, 32)
    table, live, cached, refs = struct.unpack_from('<QQQI', wrapper)
    if table != base+MAP_TABLE_RVA or bool(live) == bool(cached) or refs == 0:
        raise ValueError('XP2 weather retained map owner is invalid')
    owner = live or cached
    dimensions = _raw(read, owner+0x28, 0x1A)
    width, height, _ = struct.unpack_from('<iii', dimensions)
    if width <= 0 or height <= 0:
        raise ValueError('XP2 weather native map dimensions are invalid')
    api = _api(native_api, ('call_position_index',), lambda: {
        'call_position_index': lambda target, receiver, pair:
            C.WINFUNCTYPE(C.c_uint32, C.c_void_p, C.c_void_p)(target)(receiver, pair)})
    storage, output = _buffer(struct.pack('<ii', *position))
    value = api['call_position_index'](base+0x59B590, service, output)
    pair = _output(storage)
    if (type(value) is not int or not 0 <= value <= 0xFFFFFFFF):
        raise ValueError('XP2 weather position index must be the exact native EAX DWORD')
    if (_base(core) != base or getattr(facades, 'backend', None) is not backend
            or getattr(facades, 'cache_service', None) != service
            or backend.core_base != base or backend.context_alive() is not True
            or _raw(read, service, 32) != wrapper
            or _raw(read, owner+0x28, 0x1A) != dimensions
            or _qword(read, base+MAP_TABLE_RVA+0x90) != base+0x59B590):
        raise RuntimeError('XP2 weather retained position owner changed during the query')
    x, y = struct.unpack('<ii', pair)
    return PositionIndexResult(value, x, y)


def query_native_index_to_position(core, context: int, index: int, *,
                                   read: Read | None = None,
                                   native_api: dict | None = None) -> bytes:
    """Return the native eight-byte pair for one valid storm-vector index.

    The caller keeps ``context`` alive on its owning native thread. This call
    acquires outer+A8, verifies the live map belongs to context's current game,
    and releases only that new wrapper through +8. Both before and after the
    query, checked reads authenticate the owner and its width/count. A negative
    or out-of-range index is outside the F1C00/Map+68 shared domain and refused.
    The seam has exactly get_map(context), lookup_index(map,out8,index), and
    release_map(map); only lookup_index writes the pair.
    """
    if type(context) is not int or context <= 0:
        raise ValueError('XP2 weather position requires a borrowed outer context')
    if type(index) is not int or not 0 <= index <= 0x7FFFFFFF:
        raise ValueError('XP2 weather index must be a nonnegative signed DWORD')
    base = _base(core)
    if read is None:
        from .native.native_setup import local_reader
        read = local_reader()
    verify_live(base, read)

    def identity():
        if _base(core) != base or _qword(read, context) != base+OUTER_TABLE_RVA:
            raise RuntimeError('XP2 weather outer context identity changed')
        inner = _qword(read, context+8)
        if not inner:
            raise ValueError('XP2 weather outer context has no native owner')
        game = _qword(read, inner+0x60)
        if not game:
            raise ValueError('XP2 weather outer context has no native game')
        map_owner = _qword(read, game+0x248)
        if not map_owner:
            raise ValueError('XP2 weather native game has no live map')
        return inner, game, map_owner

    before = identity()
    api = _api(native_api, ('get_map', 'lookup_index', 'release_map'), lambda: {
        'get_map': C.WINFUNCTYPE(C.c_void_p, C.c_void_p)(base+0x590300),
        'lookup_index': C.WINFUNCTYPE(C.c_void_p, C.c_void_p, C.c_void_p, C.c_int32)(base+0x59B440),
        'release_map': C.WINFUNCTYPE(None, C.c_void_p)(base+0x59A8D0)})
    facade = api['get_map'](context)
    if type(facade) is not int or facade <= 0 or _qword(read, facade) != base+MAP_TABLE_RVA:
        raise ValueError('XP2 weather map acquisition returned an unauthenticated facade')
    try:
        wrapper = _raw(read, facade, 32)
        _, owner, cached, refs = struct.unpack_from('<QQQI', wrapper)
        if owner != before[2] or cached != 0 or refs != 1 or identity() != before:
            raise ValueError('XP2 weather acquired map has a different native owner')
        dimensions = _raw(read, owner+0x28, 12)
        width, height, count = struct.unpack('<iii', dimensions)
        if width <= 0 or height <= 0 or not 0 <= index < count:
            raise ValueError('XP2 weather index is outside the source-equivalent valid domain')
        storage, output = _buffer(bytes(8))
        returned = api['lookup_index'](facade, output, index)
        pair = _output(storage)
        if type(returned) is not int or returned != output:
            raise ValueError('XP2 weather map returned a different output pointer')
        if (identity() != before or _raw(read, facade, 32) != wrapper
                or _raw(read, owner+0x28, 12) != dimensions
                or _qword(read, base+MAP_TABLE_RVA+0x68) != base+0x59B440):
            raise RuntimeError('XP2 weather map owner changed during native conversion')
        return pair
    finally:
        if (_base(core) != base or _qword(read, facade) != base+MAP_TABLE_RVA
                or _qword(read, base+MAP_TABLE_RVA+8) != base+0x59A8D0):
            raise RuntimeError('XP2 weather map release identity changed')
        api['release_map'](facade)


__all__ = ['PositionIndexResult', 'query_native_position_index',
           'query_native_index_to_position', 'source', 'source_dependencies', 'verify_live']
