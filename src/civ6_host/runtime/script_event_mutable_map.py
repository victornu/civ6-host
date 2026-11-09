"""Explicit XP2 AUX68 in/out ParameterMap transport.

The destination is borrowed for one synchronous callback. Its exact native
snapshot seeds the final Lua argument; protected C writes that same table back
into the supplied map. Installing this adapter does not admit native Load.
"""
from __future__ import annotations

import ctypes as C
from dataclasses import dataclass
import threading

from .configuration_profiles import XP2_CORE_SHA256, configuration_abi
from .native.native_aux_map_conversion import MAX_OPS, validate_transport
from .native.native_script_arguments import HKSArgument, pack_arguments
from .script_event_maps import (
    MAP_ARGUMENT_TYPES, MapTransport, has_maps, pack_maps, require_map_transport,
)

_HOST_REFUSAL_STATUSES = frozenset((-1960, -1601, -1602))


@dataclass(frozen=True)
class MutableMapResult:
    valid: bool
    truthiness: bool
    status: int
    phase: int
    error: str | None = None


def pack_mutable_map(arguments, seed):
    """Retain all buffers through the call and bound the combined operation count."""
    arguments = tuple(arguments)
    validate_transport(seed)
    if has_maps(arguments):
        packed, maps, buffers = pack_maps(arguments)
    else:
        packed, maps, buffers = pack_arguments(arguments), (MapTransport * 0)(), []
    seed_count = len(seed) // 16
    if seed_count + sum(item.count for item in maps) > MAX_OPS:
        raise ValueError('Aggregate mutable map transport budget exceeded')
    seed_buffer = C.create_string_buffer(seed, len(seed))
    buffers.append(seed_buffer)
    return packed, maps, seed_buffer, seed_count, buffers


def pack_mutable_map_strings(arguments, seed):
    from .script_event_strings import pack_strings
    validate_transport(seed)
    packed, maps, strings, buffers = pack_strings(arguments)
    seed_count = len(seed) // 16
    if seed_count + sum(item.count for item in maps) > MAX_OPS:
        raise ValueError('Aggregate mutable map transport budget exceeded')
    seed_buffer = C.create_string_buffer(seed, len(seed))
    buffers.append(seed_buffer)
    return packed, maps, strings, seed_buffer, seed_count, buffers


class MutableMapResultDispatcher:
    """Source-bound, thread-owned dispatcher; a host refusal quarantines it."""

    def __init__(self, runtime, factory, core, *, core_sha256, read):
        from .xp2_mutable_map_profile import verify_runtime
        if core_sha256 != XP2_CORE_SHA256 or not callable(read) or factory is None:
            raise ValueError('Mutable map results require the explicit XP2 source profile')
        runtime.registry._check()
        factory.check()
        self.runtime, self.factory, self.core = runtime, factory, core
        self.registry, self.root, self.native = runtime.registry, runtime.root, runtime.host
        self.owner = getattr(runtime, 'service_owner', None)
        self.base, self.abi = core._handle, configuration_abi(core_sha256)
        self.thread, self.closed = threading.get_ident(), False
        self.poisoned, self.busy = False, False
        self._check()
        self._empty_root()
        require_map_transport(runtime)
        version = getattr(self.native, 'LAB_GameEventsMutableMapVersion', None)
        self.native_dispatch = getattr(self.native, 'LAB_GameEventsDispatchMutableMapResult', None)
        if not callable(version) or not callable(self.native_dispatch):
            raise ValueError('Native mutable map dispatcher exports are unavailable')
        version.argtypes, version.restype = [], C.c_int
        if version() != 1:
            raise ValueError('Unknown native mutable map result version')
        self.proof = verify_runtime(runtime, core, read)
        self.native_dispatch.argtypes = [
            C.c_void_p, C.c_char_p, C.POINTER(HKSArgument), C.c_size_t,
            C.POINTER(MapTransport), C.c_size_t, C.c_void_p, C.c_uint32,
            C.c_void_p, C.c_void_p, C.c_uint32,
            C.POINTER(C.c_uint8), C.POINTER(C.c_uint8),
            C.POINTER(C.c_uint32), C.POINTER(C.c_uint32),
        ]
        self.native_dispatch.restype = C.c_int

    def _check(self):
        runtime, factory = self.runtime, self.factory
        if (self.thread != threading.get_ident() or self.closed or self.poisoned
                or runtime.registry is not self.registry or runtime.root != self.root
                or self.registry.root != self.root or runtime.host is not self.native
                or not self.root or self.owner is None
                or getattr(runtime, 'service_owner', None) is not self.owner):
            raise ValueError('Mutable map runtime is closed, changed ownership or quarantined')
        self.registry._check()
        factory.check()
        if (type(self.base) is not int or not 0 < self.base < (1 << 47)
                or self.core._handle != self.base or factory.base != self.base
                or factory.abi != self.abi or self.abi.core_sha256 != XP2_CORE_SHA256):
            raise ValueError('Mutable map factory ABI or Core base differs')

    def _empty_root(self):
        if self.runtime.lua['gettop'](self.root) != 0:
            raise RuntimeError('Mutable map dispatch requires an empty root stack')

    def _protected_error(self, status):
        """Copy the bounded protected error before popping the owned root stack."""
        lua = self.runtime.lua
        top = lua['gettop'](self.root)
        try:
            if top != 1:
                raise RuntimeError('Mutable map protected error has an invalid root stack')
            kind, length = lua['type'](self.root, -1), C.c_size_t()
            pointer = lua['tolstring'](self.root, -1, C.byref(length)) if kind == 4 else None
            if kind == 4 and length.value and not pointer:
                raise RuntimeError('Mutable map protected error string is unavailable')
            message = (C.string_at(pointer, min(length.value, 4096)).decode('utf-8', 'replace')
                       if pointer else '')
        finally:
            lua['settop'](self.root, 0)
        self._empty_root()
        self.owner.emit('native_game_event_mutable_map_protected_error',
                        native_status=status, error=message, error_type=kind,
                        error_bytes=length.value, error_truncated=length.value > 4096,
                        protected_call_success=False, eligible_for_training=False)
        return message

    def dispatch(self, name, arguments, destination):
        """Return native validity, including the EXE's protected-error behavior."""
        try:
            self._check()
            if self.busy:
                raise RuntimeError('Mutable map dispatch reentered')
            if (type(name) is not bytes or not name or b'\x00' in name or len(name) > 255
                    or type(destination) is not int or not 0 < destination < (1 << 47)):
                raise ValueError('Unqualified mutable map event name or destination')
            arguments = tuple(arguments)
            for value in arguments:
                if isinstance(value, MAP_ARGUMENT_TYPES) and value.factory is not self.factory:
                    raise ValueError('Mutable map argument belongs to a different factory')
            self._empty_root()
            # A snapshot only: the caller's destination is never cloned or owned.
            seed = self.factory.snapshot(destination, names=True).transport
            from .script_event_strings import has_strings, StringTransport, require_string_transport
            if has_strings(arguments):
                require_string_transport(self.runtime)
                packed, maps, strings, seed_buffer, seed_count, buffers = pack_mutable_map_strings(arguments, seed)
                dispatch = self.native.LAB_GameEventsDispatchMutableMapStringsResult
                dispatch.argtypes = [C.c_void_p, C.c_char_p, C.POINTER(HKSArgument), C.c_size_t,
                    C.POINTER(MapTransport), C.c_size_t, C.POINTER(StringTransport), C.c_size_t,
                    C.c_void_p, C.c_uint32, C.c_void_p, C.c_void_p, C.c_uint32,
                    C.POINTER(C.c_uint8), C.POINTER(C.c_uint8),
                    C.POINTER(C.c_uint32), C.POINTER(C.c_uint32)]
                dispatch.restype = C.c_int
                string_parameters = (strings, len(strings))
            else:
                packed, maps, seed_buffer, seed_count, buffers = pack_mutable_map(arguments, seed)
                dispatch, string_parameters = self.native_dispatch, ()
            self.busy = True
            valid, truthiness = C.c_uint8(), C.c_uint8()
            refused, phase = C.c_uint32(), C.c_uint32()
            try:
                status = dispatch(
                    self.root, name, packed if len(packed) else None, len(packed),
                    maps if len(maps) else None, len(maps), *string_parameters, seed_buffer, seed_count,
                    destination, self.base, 2,
                    C.byref(valid), C.byref(truthiness), C.byref(refused), C.byref(phase))
            finally:
                self.busy = False
            if type(status) is not int:
                raise RuntimeError('Mutable map dispatcher returned an invalid status')
            # HKS can return a negative protected-call status (observed -100).
            # Only these explicit adapter/lock codes identify host refusals.
            host_refusal = status in _HOST_REFUSAL_STATUSES
            protected_error = status != 0 and not host_refusal
            error = (self._protected_error(status)
                     if protected_error or (host_refusal or refused.value)
                     and self.runtime.lua['gettop'](self.root) else None)
            if host_refusal or refused.value:
                self._empty_root()
                reason = f': {error}' if error is not None else ''
                raise RuntimeError(f'Mutable map native refusal: status={status}, refused={refused.value}, phase={phase.value}{reason}')
            self._empty_root()
            if (valid.value > 1 or truthiness.value > 1 or phase.value > 3
                    or valid.value and phase.value < 2
                    or truthiness.value and not valid.value
                    or protected_error and phase.value not in (1, 2)
                    or status == 0 and phase.value != 3):
                raise RuntimeError('Mutable map dispatcher returned inconsistent native results')
            return MutableMapResult(bool(valid.value), bool(truthiness.value), status, phase.value, error)
        except BaseException:
            self.poisoned = True
            raise

    def close(self):
        self._check()
        if self.busy:
            raise ValueError('Mutable map dispatch is still active')
        self._empty_root()
        self.closed = True


def source_dependencies():
    from .xp2_mutable_map_profile import source_dependencies as dependencies
    return dependencies()
