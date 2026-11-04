"""Call the pinned native plot UI value/flag query through owned Core facades.

This is a direct Core host call, not a Lua binding and not a visibility policy.
The caller supplies exactly the 8-byte pair descriptor used by the pinned EXE
caller. Only the two EXE-proven null-facade branches produce zero defaults.
"""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import ctypes as C
import hashlib
import json
from pathlib import Path
from typing import Callable
from civ6_host.runtime.native.native_setup import local_reader
EVIDENCE_SHA256 = '89460ff9afeba049d974ffd5ad1e5d044fce7cd74a42c8b56f7aeef01b305eb3'
EVIDENCE_PATH = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_plot_ui_query.py')))).resolve().parents[1] / 'evidence' / 'native-plot-ui-query' / f'{EVIDENCE_SHA256}.json'
CORE_SHA256 = 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'
EXE_SHA256 = 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63'
OUTER_VTABLE_RVA = 7987232
OUTER_POSITION_GETTER_SLOT = 144
OUTER_POSITION_GETTER_RVA = 4382432
GAME_FACADE_VTABLE_RVA = 7990488
GAME_FACADE_RELEASE_SLOT = 8
GAME_FACADE_RELEASE_RVA = 4409168
GAME_FACADE_POSITION_QUERY_SLOT = 88
GAME_FACADE_POSITION_QUERY_RVA = 4410848
POSITION_FACADE_VTABLE_RVA = 7995096
POSITION_FACADE_RELEASE_SLOT = 8
POSITION_FACADE_RELEASE_RVA = 4440288
POSITION_VALUE_SLOT = 120
POSITION_VALUE_RVA = 4440320
POSITION_FLAG_SLOT = 112
POSITION_FLAG_RVA = 4440368

def _verify_static_evidence(core_base: int) -> dict:
    raw = _resolve_resource_path(EVIDENCE_PATH).read_bytes()
    if hashlib.sha256(raw).hexdigest() != EVIDENCE_SHA256:
        raise RuntimeError('Native plot UI query source proof hash mismatch')
    evidence = json.loads(raw.decode('utf-8'))
    if evidence.get('schema') != 'civ6rl.native_plot_ui_query.static.v1':
        raise RuntimeError('Unexpected native plot UI query proof schema')
    if evidence.get('images', {}).get('core_sha256') != CORE_SHA256:
        raise RuntimeError('Native plot UI query proof is for another GameCore')
    if evidence.get('images', {}).get('exe_sha256') != EXE_SHA256:
        raise RuntimeError('Native plot UI query proof is for another EXE')
    parent = evidence.get('parent_proof', {})
    if (parent.get('event_kind'), parent.get('callback_va'), parent.get('query_va')) != ('0x5d0f4014', '0x140152660', '0x140147cc0'):
        raise RuntimeError('Native plot UI query proof has another source caller')
    if type(core_base) is not int or core_base <= 0:
        raise ValueError('A non-null loaded GameCore image base is required')
    return evidence

def _qword(read: Callable[[int, int], bytes], address: int) -> int:
    raw = read(address, 8)
    if type(raw) is not bytes or len(raw) != 8:
        raise ValueError('Native pointer read must return exactly 8 bytes')
    return int.from_bytes(raw, 'little')

def _check_slot(read, vtable: int, slot: int, target: int, core_base: int) -> None:
    actual = _qword(read, vtable + slot)
    expected = core_base + target
    if actual != expected:
        raise ValueError(f'Unverified native plot UI method at vtable+{slot:#x}')

def _invoke(core, read, call, receiver, slot, target, result_type, arg_types, *arguments):
    vtable = _qword(read, receiver)
    _check_slot(read, vtable, slot, target, int(core._handle))
    address = int(core._handle) + target
    if call is not None:
        return call(address, result_type, tuple(arg_types), receiver, *arguments)
    function = C.WINFUNCTYPE(result_type, C.c_void_p, *arg_types)(address)
    return function(receiver, *arguments)

def query_plot_ui(core, context: int, position_bytes: bytes, read=None, call=None, *, core_sha256='d7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3') -> dict[str, int]:
    """Return the native per-position QWORD and byte from the public facade.

    ``position_bytes`` must be precisely the 8 bytes consumed by the EXE
    source (two DWORDs). The context is borrowed. Both returned wrappers are
    owned and released in reverse acquisition order. The optional ``call``
    seam is for tests; production should leave it unset.
    """
    if core_sha256 not in ('d7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3', '259b90a473a256aff6a7d621a4f3717e46f6921c59b9817475375c88b97e8c83', '324c51e9ea3531758842e16c69e6cddbefbb226c5b675c3d6e60111646c2e98c'):
        raise ValueError('Unqualified facade engine')
    from civ6_host.runtime.foundation_facade_profiles import query_abi, verify_xp1_once, select_tables
    from civ6_host.runtime.provenance import resource_root
    _foundation_abi = query_abi(core_sha256, None if core_sha256 == 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3' else resource_root())
    if type(context) is not int or context <= 0:
        raise ValueError('A non-null borrowed Core context is required')
    if type(position_bytes) is not bytes or len(position_bytes) != 8:
        raise ValueError('Position descriptor must be exactly 8 bytes')
    base = int(core._handle)
    _verify_static_evidence(base)
    read = local_reader() if read is None else read
    outer_vtable = _qword(read, context)
    if outer_vtable != base + _foundation_abi.table('outer'):
        raise ValueError('Unexpected GameCore outer context')
    _check_slot(read, outer_vtable, OUTER_POSITION_GETTER_SLOT, _foundation_abi.rva('outer_game'), base)
    game = _invoke(core, read, call, context, OUTER_POSITION_GETTER_SLOT, _foundation_abi.rva('outer_game'), C.c_void_p, ())
    if not game:
        return {'value_u64': 0, 'flag_u8': 0}
    game = int(game)
    game_safe_to_release = False
    try:
        game_vtable = _qword(read, game)
        if game_vtable != base + _foundation_abi.table('game'):
            raise ValueError('Unexpected owned Game facade')
        _check_slot(read, game_vtable, GAME_FACADE_RELEASE_SLOT, _foundation_abi.rva('release_game'), base)
        game_safe_to_release = True
        _check_slot(read, game_vtable, GAME_FACADE_POSITION_QUERY_SLOT, _foundation_abi.rva('position_service'), base)
        position_facade = _invoke(core, read, call, game, GAME_FACADE_POSITION_QUERY_SLOT, _foundation_abi.rva('position_service'), C.c_void_p, ())
        if not position_facade:
            return {'value_u64': 0, 'flag_u8': 0}
        position_facade = int(position_facade)
        interface_safe_to_release = False
        try:
            interface_vtable = _qword(read, position_facade)
            if interface_vtable != base + _foundation_abi.table('position'):
                raise ValueError('Unexpected owned position-query facade')
            _check_slot(read, interface_vtable, POSITION_FACADE_RELEASE_SLOT, _foundation_abi.rva('release_position'), base)
            interface_safe_to_release = True
            _check_slot(read, interface_vtable, POSITION_VALUE_SLOT, _foundation_abi.rva('position_value'), base)
            _check_slot(read, interface_vtable, POSITION_FLAG_SLOT, _foundation_abi.rva('position_flag'), base)
            if _qword(read, position_facade + 8) == 0:
                raise RuntimeError('Position-query facade has no owner; native getters would dereference it')
            descriptor = C.create_string_buffer(position_bytes, 8)
            descriptor_pointer = C.addressof(descriptor)
            if C.string_at(descriptor_pointer, 8) != position_bytes:
                raise RuntimeError('Position descriptor storage changed')
            value = _invoke(core, read, call, position_facade, POSITION_VALUE_SLOT, _foundation_abi.rva('position_value'), C.c_uint64, (C.c_void_p,), descriptor_pointer)
            flag = _invoke(core, read, call, position_facade, POSITION_FLAG_SLOT, _foundation_abi.rva('position_flag'), C.c_uint8, (C.c_void_p,), descriptor_pointer)
            return {'value_u64': int(value), 'flag_u8': int(flag)}
        finally:
            if interface_safe_to_release:
                _invoke(core, read, call, position_facade, POSITION_FACADE_RELEASE_SLOT, _foundation_abi.rva('release_position'), None, ())
    finally:
        if game_safe_to_release:
            _invoke(core, read, call, game, GAME_FACADE_RELEASE_SLOT, _foundation_abi.rva('release_game'), None, ())
