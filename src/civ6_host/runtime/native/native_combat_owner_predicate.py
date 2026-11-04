"""Call the retained Game facade's original predicate used by EXE F16E0."""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import ctypes as C
from civ6_host.runtime.native.native_combat_map_owner import verify_source_evidence
from civ6_host.runtime.native.native_configuration_finalization import _qword
from civ6_host.runtime.native.native_configuration_finalization import _read
from civ6_host.runtime import xp1_combat_profile as _combat_source
GAME_VTABLE = 7990488
SLOT, TARGET = (304, 4411040)
TARGET_SHA256 = 'c054c1940392b4f125115cd29ff67dd9251aa26ed635f383bdb6ff092c858ac0'
STATE_GETTER, STATE_GLOBAL = (2234592, 9168872)

def _invoke(target, receiver, signed_owner):
    return int(C.WINFUNCTYPE(C.c_uint8, C.c_void_p, C.c_int32)(target)(receiver, signed_owner))

def query_owner(facades, signed_owner, read, *, invoke=None, core_sha256='d7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'):
    proof = verify_source_evidence()
    _game_table, _target, _state_getter, _state_global, proof = _combat_source.predicate_selection(core_sha256, (GAME_VTABLE, TARGET, STATE_GETTER, STATE_GLOBAL), proof)
    if core_sha256 == 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3' and (proof['core_captures']['game_owner_predicate']['code_sha256'] != TARGET_SHA256 or proof['vtable_slots']['retained_game+0x130']['target_va'] != '0x180434ea0' or proof['leaves']['core_game_state_getter']['raw_hex'] != '488b0501cf6900c3'):
        raise RuntimeError('Combat owner predicate source changed')
    if type(signed_owner) is not int or not -32768 <= signed_owner <= 32767:
        raise ValueError('Combat owner must be the sign-extended native WORD')
    if facades is None or facades._closed or (not facades.backend.context_alive()):
        raise RuntimeError('Combat owner predicate requires a retained live Game facade')
    base, receiver = (facades.backend.core_base, facades.game_facade)
    if not receiver or _qword(read, receiver) != base + _game_table:
        raise ValueError('Combat owner predicate has the wrong Game facade')
    target = _qword(read, base + _game_table + SLOT)
    if target != base + _target:
        raise ValueError('Combat owner predicate virtual slot changed')
    body = proof['core_captures']['game_owner_predicate']
    for fragment in body['fragments']:
        expected = b''.join((bytes.fromhex(i['bytes']) for i in fragment['instructions']))
        address = base + int(fragment['start_va'], 16) - 6442450944
        if _read(read, address, len(expected)) != expected:
            raise ValueError('Combat owner predicate native code changed')
    state_getter = bytes.fromhex(proof['leaves']['core_game_state_getter']['raw_hex'])
    if _read(read, base + _state_getter, 8) != state_getter:
        raise ValueError('Combat native state getter changed')
    if not _qword(read, base + _state_global):
        raise RuntimeError('Combat predicate native GameState is unavailable')
    if not facades.backend.context_alive():
        raise RuntimeError('Combat predicate context expired before native call')
    result = (_invoke if invoke is None else invoke)(target, receiver, signed_owner)
    if type(result) is not int or result not in (0, 1):
        raise ValueError('Combat predicate did not return its native Boolean')
    return bool(result)
