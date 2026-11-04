"""XP1 application descriptor: native deep copy into guarded outer storage.

The native non-deleting destructor owns nested values; Python owns only the
outer 0x58 bytes. Ambiguous ownership is quarantined for process termination.
"""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import ctypes as C
import hashlib, json, struct
from pathlib import Path
from civ6_host.runtime.native.native_xp1_map_setup import _read
from civ6_host.runtime.native.native_xp1_map_setup import _rows
from civ6_host.runtime.native.native_xp1_map_setup import PREFERRED_BASE
from civ6_host.runtime.native.native_xp1_map_setup import CORE_SHA
CAPTURE_SHA = '5815f54319950ac2f03dfc16dc90bdb11c525bce88d13f526c08025bda386a3d'
GUARD = b'\xd6' * 16
_QUARANTINE = []

class UnsafeOwnership(RuntimeError):
    """The isolated caller must terminate without attempting native cleanup."""

def source_profile(root):
    raw = _resolve_resource_path(_resolve_resource_path(Path(root)) / 'work/native-xp1-application-setup891/capture891.json').read_bytes()
    if hashlib.sha256(raw).hexdigest() != CAPTURE_SHA:
        raise ValueError('XP1 application source capture changed')
    proof = json.loads(raw)
    ref = proof['parent_player_capture']
    if proof['source']['sha256'] != CORE_SHA or hashlib.sha256(_resolve_resource_path(_resolve_resource_path(Path(root)) / ref['path']).read_bytes()).hexdigest() != ref['sha256']:
        raise ValueError('XP1 application source identity differs')
    return proof

def verify_code(borrower, proof):
    b = borrower.base
    read = borrower.read
    c = proof['contract']
    for body in proof['live_bodies'].values():
        for row in _rows(body):
            raw = bytes.fromhex(row['bytes'])
            if _read(read, b + int(row['va'], 16) - PREFERRED_BASE, len(raw)) != raw:
                raise ValueError('XP1 application executable bytes changed')
    for slot, rva in c['slots'].items():
        if struct.unpack('<Q', _read(read, b + c['configuration_vtable_rva'] + int(slot, 16), 8))[0] != b + rva:
            raise ValueError('XP1 application virtual slot changed')

def provider_snapshot(borrower, proof, pointer):
    c = proof['contract']
    read = borrower.read
    vt = borrower.base + c['configuration_vtable_rva']
    if type(pointer) is not int or pointer <= 0 or struct.unpack('<Q', _read(read, pointer, 8))[0] != vt:
        raise ValueError('Unknown XP1 application provider')
    mapkey = struct.unpack('<I', _read(read, borrower.base + c['map_key_rva'], 4))[0]
    keys = (borrower.state['root_key'], mapkey, *borrower.state['keys'])
    if len(set(keys)) != 66 or any((not k for k in keys)):
        raise ValueError('XP1 application keys uninitialized or aliased')
    values = []
    for key in keys:
        node = borrower._method(pointer, 88, C.c_void_p, (C.c_uint32,), key)
        raw = _read(read, node, 24)
        value = struct.unpack_from('<Q', raw, 8)[0]
        if struct.unpack_from('<H', raw)[0] != 10 or struct.unpack_from('<I', raw, 20)[0] != c['owned_map_flags'] or (not value) or (struct.unpack('<Q', _read(read, value, 8))[0] != vt):
            raise ValueError('XP1 application child lacks proven native ownership')
        values.append(value)
    if len(set((pointer, *values))) != 67:
        raise ValueError('XP1 application submaps alias')
    return {'descriptor': pointer, 'game': values[0], 'map': values[1], 'players': tuple(values[2:])}

def addresses(state):
    return {state['descriptor'], state['game'], state['map'], *state['players']}

class XP1ApplicationConfiguration:

    def __init__(self, borrower, *, project_root):
        borrower._linked()
        self.borrower = borrower
        self.proof = source_profile(project_root)
        self.closed = False
        self.poisoned = False
        verify_code(borrower, self.proof)
        self.source = provider_snapshot(borrower, self.proof, borrower.state['descriptor'])
        self.storage = C.create_string_buffer(88 + 2 * len(GUARD))
        start = C.addressof(self.storage)
        self.pointer = start + len(GUARD)
        C.memmove(start, GUARD, len(GUARD))
        C.memmove(self.pointer + 88, GUARD, len(GUARD))
        if self.pointer in addresses(self.source):
            raise ValueError('XP1 application outer storage aliases source')
        try:
            result = borrower._invoke(self.proof['contract']['constructor_rva'], C.c_void_p, (C.c_void_p,), self.pointer)
            self._guard()
            if result != self.pointer or struct.unpack('<Q', _read(borrower.read, self.pointer, 8))[0] != borrower.base + 9696656:
                raise ValueError('XP1 application constructor returned wrong identity')
            result = borrower._invoke(self.proof['contract']['slots']['0x1d0'], C.c_void_p, (C.c_void_p, C.c_void_p), self.pointer, self.source['descriptor'])
            self._guard()
            if result != self.pointer:
                raise ValueError('XP1 application assign result differs')
            self.initial = provider_snapshot(borrower, self.proof, self.pointer)
            if addresses(self.initial) & addresses(self.source):
                raise ValueError('XP1 application copy aliases source ownership')
            if provider_snapshot(borrower, self.proof, self.source['descriptor']) != self.source:
                raise ValueError('XP1 application copy changed source topology')
        except BaseException as error:
            self.poisoned = True
            _QUARANTINE.append(self)
            raise UnsafeOwnership('Native XP1 copy ownership could not be established; terminate isolated process') from error

    def _guard(self):
        if self.closed or self.poisoned:
            raise RuntimeError('XP1 application owner closed or poisoned')
        if self.storage.raw[:16] != GUARD or self.storage.raw[-16:] != GUARD:
            raise ValueError('XP1 application exceeded guarded 0x58-byte storage')

    def snapshot(self):
        self._guard()
        verify_code(self.borrower, self.proof)
        state = provider_snapshot(self.borrower, self.proof, self.pointer)
        if addresses(state) & addresses(self.source):
            raise ValueError('XP1 application aliases source ownership')
        return state

    def close(self):
        if self.closed or self.poisoned:
            raise RuntimeError('XP1 application owner closed or poisoned')
        try:
            self._guard()
            verify_code(self.borrower, self.proof)
            state = self.snapshot()
            self.borrower._invoke(self.proof['contract']['destructor_rva'], None, (C.c_void_p,), self.pointer)
            self._guard()
        except BaseException as error:
            self.poisoned = True
            _QUARANTINE.append(self)
            raise UnsafeOwnership('Native XP1 destruction failed; terminate isolated process') from error
        self.closed = True
        return {'native_destructor_returned': True, 'outer_storage_freed_by_native': False, 'guards_intact': True, 'owned_submaps_before_close': len(addresses(state)) - 1}

def read_value(borrower, provider, key):
    """Read a known borrowed provider value; return pointers separately for isolation tests."""
    borrower.map._key(key)
    vt = struct.unpack('<Q', _read(borrower.read, provider, 8))[0]
    if vt != borrower.base + 9696656:
        raise ValueError('Unknown XP1 value provider')
    node = borrower._method(provider, 88, C.c_void_p, (C.c_uint32,), key)
    if not node:
        return (None, None)
    raw = _read(borrower.read, node, 24)
    tag = struct.unpack_from('<H', raw)[0]
    flags = struct.unpack_from('<I', raw, 20)[0]
    pointer = None
    if tag in (2, 3):
        if flags & 1 << 29:
            raise ValueError('XP1 scalar unexpectedly indirect')
        value = struct.unpack_from('<I', raw, 8)[0]
    elif tag in (5, 6):
        pointer = struct.unpack_from('<Q', raw, 8)[0]
        if not flags & 1 << 29 or not pointer:
            raise ValueError('XP1 text lacks native storage')
        stride = 1 if tag == 5 else 2
        data = bytearray()
        for offset in range(0, 256 if tag == 5 else 520, stride):
            unit = _read(borrower.read, pointer + offset, stride)
            if unit == b'\x00' * stride:
                break
            data.extend(unit)
        else:
            raise ValueError('XP1 text lacks bounded terminator')
        value = data.decode('ascii' if tag == 5 else 'utf-16-le', 'strict')
    else:
        raise ValueError('Unsupported XP1 diagnostic variant ' + str(tag))
    return ({'tag': tag, 'value': value}, pointer)
