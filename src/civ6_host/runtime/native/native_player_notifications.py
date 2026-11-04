"""Bounded read-only extraction for the EXE 20f2116e player notification.

The helper follows the Core-owned player wrapper and its component, reads the
two source-defined uint32 getters, then releases both temporary interfaces.
It does not create or enqueue a notification; the caller owns that decision.
"""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
from civ6_host.runtime.player_notification_profiles import notification_abi
from civ6_host.runtime.player_notification_profiles import verify_player_wrapper
from civ6_host.runtime.player_notification_profiles import verify_component_wrapper
import ctypes as C
from contextlib import contextmanager
import struct
from civ6_host.runtime.native.native_player_event_domains import validate_player_query_input
PLAYER_MANAGER_VTABLE_RVA = 7987232
PLAYER_MANAGER_GET_PLAYER_SLOT = 184
PLAYER_MANAGER_GET_PLAYER_RVA = 4382880
PLAYER_VTABLE_RVA = 7992320
PLAYER_GET_COMPONENT_SLOT = 256
PLAYER_GET_COMPONENT_RVA = 4423520
PLAYER_RELEASE_SLOT = 8
PLAYER_RELEASE_RVA = 4421040
COMPONENT_VTABLE_RVA = 7993888
COMPONENT_GETTER_18_SLOT = 24
COMPONENT_GETTER_18_RVA = 4432064
COMPONENT_GETTER_10_SLOT = 16
COMPONENT_GETTER_10_RVA = 4432128
COMPONENT_RELEASE_SLOT = 8
COMPONENT_RELEASE_RVA = 4431952
_MAX_READ = 8

def _local_reader():
    kernel = C.WinDLL('kernel32', use_last_error=True)
    kernel.GetCurrentProcess.argtypes = []
    kernel.GetCurrentProcess.restype = C.c_void_p
    kernel.ReadProcessMemory.argtypes = [C.c_void_p, C.c_void_p, C.c_void_p, C.c_size_t, C.POINTER(C.c_size_t)]
    kernel.ReadProcessMemory.restype = C.c_int
    process = kernel.GetCurrentProcess()

    def read(address: int, size: int) -> bytes:
        if isinstance(address, bool) or not isinstance(address, int) or address <= 0:
            raise ValueError('Invalid native address')
        if isinstance(size, bool) or not isinstance(size, int) or (not 0 < size <= _MAX_READ):
            raise ValueError('Native interface inspection is limited to 8 bytes')
        buffer = C.create_string_buffer(size)
        count = C.c_size_t()
        if not kernel.ReadProcessMemory(process, C.c_void_p(address), buffer, size, C.byref(count)):
            raise C.WinError(C.get_last_error())
        if count.value != size:
            raise RuntimeError('Incomplete native memory copy')
        return buffer.raw
    return read

def _pointer(read, address: int) -> int:
    return struct.unpack('<Q', read(address, 8))[0]

def _verify_slot(read, vtable: int, slot: int, expected: int, label: str) -> None:
    observed = _pointer(read, vtable + slot)
    if observed != expected:
        raise ValueError(f'Unexpected {label} vtable slot +{slot:#x}')

def _native_calls(core_base: int, *, core_sha256='d7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'):
    abi = notification_abi(core_sha256)
    return {'get_player': C.WINFUNCTYPE(C.c_void_p, C.c_void_p, C.c_uint32)(core_base + abi.constants['PLAYER_MANAGER_GET_PLAYER_RVA']), 'get_component': C.WINFUNCTYPE(C.c_void_p, C.c_void_p)(core_base + abi.constants['PLAYER_GET_COMPONENT_RVA']), 'getter_18': C.WINFUNCTYPE(C.c_void_p, C.c_void_p, C.POINTER(C.c_uint32))(core_base + abi.constants['COMPONENT_GETTER_18_RVA']), 'getter_10': C.WINFUNCTYPE(C.c_void_p, C.c_void_p, C.POINTER(C.c_uint32))(core_base + abi.constants['COMPONENT_GETTER_10_RVA']), 'release_component': C.WINFUNCTYPE(None, C.c_void_p)(core_base + abi.constants['COMPONENT_RELEASE_RVA']), 'release_player': C.WINFUNCTYPE(None, C.c_void_p)(core_base + abi.constants['PLAYER_RELEASE_RVA'])}

@contextmanager
def query_player_notification_values(core_base: int, context: int, player_index: int, *, read=None, _calls=None, core_sha256='d7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'):
    """Retain native interfaces while the caller consumes the copied DWORDs.

    Returns named uint32 values; the EXE producer requests getter +0x18 first
    (record payload dword +0x0c), then +0x10 (payload +0x08).
    Yields None only when the real native lookup returns no player/component.
    Every uint32 input is passed unchanged to the original getter; its own
    unsigned comparison rejects indices >=65 before native table indexing.
    EXE154310 enqueues before releasing component/player: use the yielded
    values inside this context when reproducing that callback.
    The private `_calls` seam exists solely for pure unit tests.
    """
    abi = notification_abi(core_sha256)
    if isinstance(core_base, bool) or not isinstance(core_base, int) or core_base <= 0:
        raise ValueError('Invalid GameCore base')
    if isinstance(context, bool) or not isinstance(context, int) or context <= 0:
        raise ValueError('Invalid player-manager context')
    validate_player_query_input(player_index)
    read = read or _local_reader()
    calls = _native_calls(core_base, core_sha256=core_sha256) if _calls is None else _calls
    manager_vtable = _pointer(read, context)
    if manager_vtable != core_base + abi.constants['PLAYER_MANAGER_VTABLE_RVA']:
        raise ValueError('Unexpected native player-manager vtable')
    _verify_slot(read, manager_vtable, abi.constants['PLAYER_MANAGER_GET_PLAYER_SLOT'], core_base + abi.constants['PLAYER_MANAGER_GET_PLAYER_RVA'], 'player-manager')
    player = calls['get_player'](context, player_index)
    if not player:
        yield None
        return
    player = int(player)
    component = 0
    player_release_ready = False
    component_release_ready = False
    try:
        player_vtable = _pointer(read, player)
        if player_vtable != core_base + abi.constants['PLAYER_VTABLE_RVA']:
            raise ValueError('Unexpected native player wrapper vtable')
        _verify_slot(read, player_vtable, abi.constants['PLAYER_RELEASE_SLOT'], core_base + abi.constants['PLAYER_RELEASE_RVA'], 'player-wrapper release')
        _verify_slot(read, player_vtable, abi.constants['PLAYER_GET_COMPONENT_SLOT'], core_base + abi.constants['PLAYER_GET_COMPONENT_RVA'], 'player-wrapper component')
        player_release_ready = True
        if core_sha256 != 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3':
            player_live = verify_player_wrapper(read, core_base, player, core_sha256=core_sha256)
        result = calls['get_component'](player)
        if not result:
            yield None
            return
        component = int(result)
        component_vtable = _pointer(read, component)
        if component_vtable != core_base + abi.constants['COMPONENT_VTABLE_RVA']:
            raise ValueError('Unexpected native player-notification component vtable')
        _verify_slot(read, component_vtable, abi.constants['COMPONENT_RELEASE_SLOT'], core_base + abi.constants['COMPONENT_RELEASE_RVA'], 'notification-component release')
        _verify_slot(read, component_vtable, abi.constants['COMPONENT_GETTER_18_SLOT'], core_base + abi.constants['COMPONENT_GETTER_18_RVA'], 'notification getter +0x18')
        _verify_slot(read, component_vtable, abi.constants['COMPONENT_GETTER_10_SLOT'], core_base + abi.constants['COMPONENT_GETTER_10_RVA'], 'notification getter +0x10')
        component_release_ready = True
        if core_sha256 != 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3':
            verify_component_wrapper(read, core_base, component, player_live, core_sha256=core_sha256)
        getter_18 = C.c_uint32()
        getter_10 = C.c_uint32()
        out_18 = C.addressof(getter_18)
        out_10 = C.addressof(getter_10)
        returned_18 = calls['getter_18'](component, C.byref(getter_18))
        if not returned_18 or int(returned_18) != out_18:
            raise RuntimeError('Native getter +0x18 did not return its output pointer')
        returned_10 = calls['getter_10'](component, C.byref(getter_10))
        if not returned_10 or int(returned_10) != out_10:
            raise RuntimeError('Native getter +0x10 did not return its output pointer')
        yield {'getter_10_uint32': int(getter_10.value), 'getter_18_uint32': int(getter_18.value)}
    finally:
        if component_release_ready:
            calls['release_component'](component)
        if player_release_ready:
            calls['release_player'](player)

def get_native_player_notification_values(core_base, context, player_index, *, read=None, _calls=None, core_sha256='d7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'):
    """Standalone copied readback; producer callbacks must instead use the lease."""
    with query_player_notification_values(core_base, context, player_index, read=read, _calls=_calls, core_sha256=core_sha256) as values:
        return dict(values) if values is not None else None
