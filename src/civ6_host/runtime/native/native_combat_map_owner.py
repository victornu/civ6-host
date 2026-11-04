"""Own a native copy of a borrowed combat map.

Only outer guarded storage belongs to Python. The original Core constructor,
assignment and destructor manage every nested allocation. This does not admit
the combat callback or its deferred cleanup schedule.
"""
from __future__ import annotations
from civ6_host.runtime.configuration_profiles import BASE_CORE_SHA256 as _COMBAT_MAP_BASE_CORE_SHA256
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import ctypes as C
from pathlib import Path
import struct
from civ6_host.runtime.native.native_source_cache import load_pinned_json
from civ6_host.runtime.native.native_configuration_finalization import _invoke
from civ6_host.runtime.native.native_configuration_finalization import _read
from civ6_host.runtime.native.native_configuration_finalization import _qword
from civ6_host.runtime.native.native_setup import local_reader
PROOF_SHA256 = '21e45dc5adc360fc3371aa373e4b20ccb397f3ab7c7c0038fa4e6cb56de6d84e'
ROOT = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_combat_map_owner.py')))).resolve().parents[1]
VTABLE_RVA, CTOR_RVA, ASSIGN_RVA, DTOR_RVA = (8507296, 7621504, 7649872, 7621792)
SIZE = 88
GUARD = b'\xb6' * 16

def verify_source_evidence(*, core_sha256=_COMBAT_MAP_BASE_CORE_SHA256):
    if core_sha256 != _COMBAT_MAP_BASE_CORE_SHA256:
        from civ6_host.runtime.combat_map_profiles import owner_source
        return owner_source(core_sha256)
    if not PROOF_SHA256:
        raise RuntimeError('Native combat map ownership proof is not pinned')
    proof = load_pinned_json(ROOT / 'evidence/native-event-8256dbe1' / (PROOF_SHA256 + '.json'), PROOF_SHA256)
    if proof['schema'] != 'civ6rl.native_event_8256dbe1.static.v1' or proof['kind'] != 2186730465 or proof['images'] != {'exe_sha256': 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63', 'core_sha256': 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'} or (proof['copy_primitive_comparisons']['map_assign']['equal_code_bytes'] is not True):
        raise RuntimeError('Native combat map ownership source changed')
    expected = {'map_constructor': CTOR_RVA, 'map_assign': ASSIGN_RVA, 'map_destructor': DTOR_RVA}
    if any((int(proof['core_captures'][name]['start_va'], 16) != 6442450944 + rva for name, rva in expected.items())):
        raise RuntimeError('Native combat map entry points changed')
    registry = proof['contract']['registry']
    if registry['initial_next_id'] != 1 or registry['node_size'] != 32 or registry['sentinel_offset'] != 8 or (registry['node_fields']['0x14'] != 'refcountDWORD') or (registry['node_fields']['0x18'] != 'owned map pointer'):
        raise RuntimeError('Native combat registry source changed')
    return proof

def verify_live_primitives(base, read, *, core_sha256=_COMBAT_MAP_BASE_CORE_SHA256):
    if core_sha256 != _COMBAT_MAP_BASE_CORE_SHA256:
        from civ6_host.runtime.combat_map_profiles import verify_live
        return verify_live(base, read, core_sha256=core_sha256)
    proof = verify_source_evidence()
    for name in ('map_constructor', 'map_assign', 'map_copy', 'map_destructor', 'variant_clone_construct', 'variant_clone_assign', 'variant_release'):
        for fragment in proof['core_captures'][name]['fragments']:
            expected = b''.join((bytes.fromhex(i['bytes']) for i in fragment['instructions']))
            address = base + int(fragment['start_va'], 16) - 6442450944
            for offset in range(0, len(expected), 4096):
                chunk = expected[offset:offset + 4096]
                if _read(read, address + offset, len(chunk)) != chunk:
                    raise ValueError('Native combat copy code changed: ' + name)
    if _qword(read, base + VTABLE_RVA + 464) != base + ASSIGN_RVA:
        raise ValueError('Native combat map assignment slot changed')
    if _qword(read, base + VTABLE_RVA + 376) != base + 7622816:
        raise ValueError('Native combat map deep-copy slot changed')

class NativeCombatMapOwner:

    def __init__(self, core, source, *, read=None, call=None, core_sha256=_COMBAT_MAP_BASE_CORE_SHA256):
        from civ6_host.runtime.combat_map_profiles import profile_for_sha
        self.core_sha256 = core_sha256
        self.abi = profile_for_sha(core_sha256)
        self.core = core
        self.base, self.source = (core._handle, source)
        self.read, self.call = (local_reader() if read is None else read, call)
        self.closed = self.poisoned = False
        if type(self.base) is not int or self.base <= 0 or type(source) is not int or (source <= 0):
            raise ValueError('Native combat copy requires live native pointers')
        verify_live_primitives(self.base, self.read, core_sha256=core_sha256)
        if _qword(self.read, source) != self.base + self.abi.vtable_rva:
            raise ValueError('Combat source is not the pinned native map')
        self.source_count = struct.unpack('<I', _read(self.read, source + 80, 4))[0]
        if self.source_count > 64:
            raise ValueError('Native combat root exceeds the diagnostic field budget')
        self.storage = C.create_string_buffer(SIZE + 2 * len(GUARD))
        start = C.addressof(self.storage)
        C.memmove(start, GUARD, len(GUARD))
        C.memmove(start + len(GUARD) + SIZE, GUARD, len(GUARD))
        self.pointer = start + len(GUARD)
        if self.pointer == source:
            raise ValueError('Native combat clone cannot alias its source')
        try:
            result = _invoke(call, self.base + self.abi.constructor_rva, C.c_void_p, self.pointer)
            if result != self.pointer:
                raise RuntimeError('Combat map constructor did not return its receiver')
            self._check()
            if _qword(self.read, self.pointer) != self.base + self.abi.vtable_rva:
                raise ValueError('Combat map constructor installed an unexpected vtable')
            result = _invoke(call, self.base + self.abi.assign_rva, C.c_void_p, self.pointer, (C.c_void_p,), source)
            if result != self.pointer:
                raise RuntimeError('Combat map assignment did not return its receiver')
            self._check()
            if _qword(self.read, self.pointer) != self.base + self.abi.vtable_rva or struct.unpack('<I', _read(self.read, self.pointer + 80, 4))[0] != self.source_count or struct.unpack('<I', _read(self.read, source + 80, 4))[0] != self.source_count:
                raise ValueError('Combat map copy changed its root identity or field count')
        except Exception as exc:
            self.poisoned = True
            exc.native_combat_map_owner = self
            raise

    def _check(self):
        if self.closed or self.poisoned:
            raise RuntimeError('Native combat map is closed or poisoned')
        if self.storage.raw[:16] != GUARD or self.storage.raw[-16:] != GUARD:
            self.poisoned = True
            raise RuntimeError('Native combat map exceeded its guarded storage')

    def close(self):
        if self.closed:
            return
        self._check()
        try:
            if _qword(self.read, self.pointer) != self.base + self.abi.vtable_rva:
                raise ValueError('Combat map identity changed before destruction')
            _invoke(self.call, self.base + self.abi.destructor_rva, None, self.pointer)
            self._check()
        except Exception as exc:
            self.poisoned = True
            exc.native_combat_map_owner = self
            raise
        self.closed = True

class CombatMapRegistry:
    """Source ID/refcount behavior, without choosing a cleanup scheduling point."""

    def __init__(self, *, limit=64, core_sha256=_COMBAT_MAP_BASE_CORE_SHA256):
        self.core_sha256 = core_sha256
        verify_source_evidence(core_sha256=core_sha256)
        if type(limit) is not int or not 1 <= limit <= 4096:
            raise ValueError('Invalid combat registry resource budget')
        self.limit, self.next_id = (limit, 1)
        self.entries = {}
        self.poisoned = False

    def insert(self, owner):
        if getattr(owner, 'core_sha256', _COMBAT_MAP_BASE_CORE_SHA256) != self.core_sha256:
            raise ValueError('Combat registry owner belongs to another engine')
        if self.poisoned or len(self.entries) >= self.limit:
            raise RuntimeError('Combat registry is poisoned or full')
        if owner.closed or owner.poisoned or any((item[0] is owner for item in self.entries.values())):
            raise ValueError('Combat registry requires a distinct live owned map')
        if self.next_id in self.entries or not 1 <= self.next_id < 4294967295:
            raise RuntimeError('Combat registry ID wrap/collision is outside this profile')
        token = self.next_id
        self.entries[token] = (owner, 1)
        self.next_id += 1
        return token

    def lookup(self, token):
        self._validate_token(token)
        item = self.entries.get(token)
        return None if item is None else item[0]

    def _validate_token(self, token):
        if self.poisoned:
            raise RuntimeError('Combat registry is poisoned')
        if type(token) is not int or not 0 <= token <= 4294967295:
            raise ValueError('Combat token must be uint32')

    def release(self, token):
        self._validate_token(token)
        item = self.entries.get(token)
        if item is None:
            return 0
        owner, references = item
        remaining = references - 1
        if remaining:
            self.entries[token] = (owner, remaining)
            return remaining
        try:
            owner.close()
        except Exception:
            self.poisoned = True
            raise
        del self.entries[token]
        return 0

    def clear(self):
        if self.poisoned:
            raise RuntimeError('Combat registry is poisoned')
        for token, (owner, _) in tuple(self.entries.items()):
            try:
                owner.close()
            except Exception:
                self.poisoned = True
                raise
            del self.entries[token]
