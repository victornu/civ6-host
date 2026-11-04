"""Borrow XP1's native map values; mutations and storage stay in official code.

This adapter does not initialize a game or supply defaults. The diagnostic
caller must keep the context alive and admit its exact binary/source profile.
"""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import ctypes as C
import hashlib
import json
from pathlib import Path
import struct
CORE_SHA = '259b90a473a256aff6a7d621a4f3717e46f6921c59b9817475375c88b97e8c83'
CAPTURE_SHA = '82edc2745a0d45438a42151f7461b3c0f40facf2c754fc2abc3ab44b1e0d33d2'
PREFERRED_BASE = 6442450944

def source_profile(root):
    raw = _resolve_resource_path(_resolve_resource_path(Path(root)) / 'work/native-xp1-map-setup889/capture889.json').read_bytes()
    if hashlib.sha256(raw).hexdigest() != CAPTURE_SHA:
        raise ValueError('XP1 map setup source capture changed')
    proof = json.loads(raw)
    if proof['source']['sha256'] != CORE_SHA:
        raise ValueError('XP1 map setup binary identity changed')
    return proof

def _rows(body):
    return body.get('instructions', []) + [i for f in body.get('fragments', []) for i in f.get('instructions', [])]

def _read(read, address, size):
    if type(address) is not int or address <= 0 or (not 0 < size <= 6784):
        raise ValueError('Invalid bounded XP1 map read')
    raw = read(address, size)
    if type(raw) is not bytes or len(raw) != size:
        raise ValueError('Incomplete XP1 map memory copy')
    return raw

def verify_live(base, context, read, proof):
    """Validate native identities and code before following owned map pointers."""
    if type(base) is not int or base <= 0:
        raise ValueError('Invalid XP1 image base')
    outer, inner = struct.unpack('<QQ', _read(read, context, 16))
    contract = proof['contract']
    if outer != base + contract['outer_vtable_rva'] or not inner:
        raise ValueError('Unknown XP1 outer context')
    qword = lambda address: struct.unpack('<Q', _read(read, address, 8))[0]
    if qword(inner) != base + contract['inner_vtable_rva']:
        raise ValueError('Unknown XP1 inner context')
    for name, body in proof['live_bodies'].items():
        for ins in _rows(body):
            raw = bytes.fromhex(ins['bytes'])
            if _read(read, base + int(ins['va'], 16) - PREFERRED_BASE, len(raw)) != raw:
                raise ValueError('XP1 map executable bytes changed: ' + name)
    setup = inner + contract['setup_offset']
    descriptor = qword(setup + contract['descriptor_offset'])
    map_descriptor = qword(setup + contract['map_descriptor_offset'])
    normalized_map = qword(setup + contract['normalized_map_offset'])
    if not descriptor or descriptor != map_descriptor or (not normalized_map) or (descriptor == normalized_map):
        raise ValueError('XP1 map configuration ownership is not established')
    table = base + contract['configuration_vtable_rva']
    if qword(descriptor) != table or qword(normalized_map) != table:
        raise ValueError('Unknown XP1 map configuration object')
    for slot, rva in contract['slots'].items():
        if qword(table + int(slot, 16)) != base + rva:
            raise ValueError('XP1 map configuration virtual slot changed')
    return {'inner': inner, 'setup': setup, 'descriptor': descriptor, 'map': normalized_map}

class XP1MapSetup:

    def __init__(self, core, context, *, project_root, read=None, call=None):
        from civ6_host.runtime.native.native_setup import local_reader
        self.base, self.context = (core._handle, context)
        self.read = local_reader() if read is None else read
        self.call = call
        self.proof = source_profile(project_root)
        self.state = verify_live(self.base, context, self.read, self.proof)
        self.closed = False

    def _check(self):
        if self.closed:
            raise RuntimeError('XP1 map setup borrower is closed')
        if verify_live(self.base, self.context, self.read, self.proof) != self.state:
            raise RuntimeError('XP1 map object identities changed')

    def _invoke(self, slot, arg_types, *args):
        address = self.base + self.proof['contract']['slots'][hex(slot)]
        if self.call is not None:
            return self.call(address, C.c_void_p, (C.c_void_p, *arg_types), self.state['map'], *args)
        return C.WINFUNCTYPE(C.c_void_p, C.c_void_p, *arg_types)(address)(self.state['map'], *args)

    @staticmethod
    def _key(key):
        if type(key) is not int or not 0 <= key <= 4294967295:
            raise ValueError('Map key must fit uint32 exactly')

    def _variant(self, key, tag):
        value = self._invoke(104, (C.c_uint32,), key)
        raw = _read(self.read, value, 24)
        observed_tag = struct.unpack_from('<I', raw)[0]
        flags = struct.unpack_from('<I', raw, 20)[0]
        if observed_tag != tag:
            raise RuntimeError('Native map value has the wrong tag')
        return (raw, flags)

    def make_hash(self, name):
        if not isinstance(name, str) or not name or '\x00' in name:
            raise ValueError('Native hash name must be nonempty ASCII')
        encoded = name.encode('ascii', 'strict')
        if len(encoded) > 255:
            raise ValueError('Native hash name exceeds diagnostic bound')
        self._check()
        address = self.base + self.proof['contract']['make_hash_rva']
        if self.call is not None:
            value = self.call(address, C.c_uint32, (C.c_char_p,), encoded)
        else:
            value = C.WINFUNCTYPE(C.c_uint32, C.c_char_p)(address)(encoded)
        if type(value) is not int or not 0 <= value <= 4294967295:
            raise RuntimeError('Native hash returned a malformed value')
        if name == 'MAP_SCRIPT':
            observed = struct.unpack('<I', _read(self.read, self.base + self.proof['contract']['map_script_key_global_rva'], 4))[0]
            if observed != value or value != 1675134810:
                raise RuntimeError('Native MAP_SCRIPT global/hash disagree')
        return value

    def set_uint(self, key, value, *, hashed=False):
        self._key(key)
        if type(value) is not int or not 0 <= value <= 4294967295 or type(hashed) is not bool:
            raise ValueError('Map integer must fit uint32 and hash mode must be explicit')
        self._check()
        self._invoke(296 if hashed else 304, (C.c_uint32, C.c_uint32), key, value)
        raw, flags = self._variant(key, 3 if hashed else 2)
        observed = struct.unpack_from('<I', raw, 8)[0]
        if flags & 1 << 29 or observed != value:
            raise RuntimeError('XP1 map integer round-trip differs')
        return {'key': key, 'value': observed, 'tag': 3 if hashed else 2, 'roundtrip_verified': True}

    def set_utf16(self, key, text):
        self._key(key)
        if not isinstance(text, str) or not text or '\x00' in text:
            raise ValueError('Map text must be a nonempty string without NUL')
        encoded = text.encode('utf-16-le') + b'\x00\x00'
        if len(encoded) > 520:
            raise ValueError('Map text exceeds the 260 UTF-16-unit bound')
        self._check()
        buffer = C.create_string_buffer(encoded, len(encoded))
        self._invoke(256, (C.c_uint32, C.c_void_p), key, C.addressof(buffer))
        C.memset(C.addressof(buffer), 88, len(encoded))
        raw, flags = self._variant(key, 6)
        pointer = struct.unpack_from('<Q', raw, 8)[0]
        if not flags & 1 << 29 or not pointer:
            raise RuntimeError('XP1 UTF-16 value lacks native string storage')
        units = bytearray()
        for offset in range(0, 520, 2):
            unit = _read(self.read, pointer + offset, 2)
            if unit == b'\x00\x00':
                break
            units.extend(unit)
        else:
            raise RuntimeError('XP1 map text lacks bounded termination')
        observed = units.decode('utf-16-le')
        if observed != text:
            raise RuntimeError('XP1 map text round-trip differs')
        return {'key': key, 'value': observed, 'tag': 6, 'caller_buffer_overwritten': True, 'roundtrip_verified': True}

    def close(self):
        self.closed = True

    def read_map_path(self):
        """Use the same XP1 path readers consumed by native map resolution."""
        self._check()
        receiver = self.state['setup'] + self.proof['contract']['map_descriptor_offset']
        output = (C.c_uint16 * 260)()
        args = (C.c_void_p, C.c_void_p, C.c_uint32)
        address = self.base + self.proof['contract']['copy_map_path_rva']
        has_address = self.base + self.proof['contract']['has_map_path_rva']
        if self.call is not None:
            copied = self.call(address, C.c_bool, args, receiver, C.addressof(output), 260)
            present = self.call(has_address, C.c_bool, (C.c_void_p,), receiver)
        else:
            copied = C.WINFUNCTYPE(C.c_bool, *args)(address)(receiver, C.addressof(output), 260)
            present = C.WINFUNCTYPE(C.c_bool, C.c_void_p)(has_address)(receiver)
        units = list(output)
        if type(copied) is not bool or type(present) is not bool or 0 not in units:
            raise RuntimeError('XP1 map path native readback is malformed')
        text = bytes(output)[:units.index(0) * 2].decode('utf-16-le')
        return {'copy_returned': copied, 'has_path': present, 'value': text}
