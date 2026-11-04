"""Read-only guards for a captured GameTurnComplete archive and its phase.

This module does not create messages, alter native state, or invoke handlers.
Delivery belongs to the public action transport and uses its already-owned
pending bytes before the next public GameUpdate.
"""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import hashlib
import json
import struct
from pathlib import Path
MESSAGE_KIND = 467357532
_PROOF_SHA = '6b8d8042119af7463613ab88ca3fd16dc798ba89fe72568730f4b58ee507652c'
_PROOF = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_game_turn_complete.py')))).resolve().parents[1] / 'evidence/native-game-turn-complete' / f'{_PROOF_SHA}.json'

def verify_source_evidence(*, core_sha256='d7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3') -> None:
    if core_sha256 != 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3':
        from civ6_host.runtime.xp1_turn_profile import turn_profile
        turn_profile(core_sha256)
        return
    raw = _resolve_resource_path(_PROOF).read_bytes()
    if hashlib.sha256(raw).hexdigest() != _PROOF_SHA:
        raise RuntimeError('Pinned GameTurnComplete evidence changed')
    proof = json.loads(raw)
    if proof.get('schema') != 'civ6rl.native_game_turn_complete.static.v1' or proof['core_sha256'] != 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3' or proof['message_vtable']['slots']['0x18'] != '0x18002c040' or (proof['bodies']['handler']['raw_sha256'] != 'd76180bf7ed68911311c75159612752dcf63988cac411423279ad6b31d09bff8'):
        raise RuntimeError('Pinned GameTurnComplete handler identity changed')

def decode_archive(payload: bytes, *, core_sha256='d7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3') -> dict[str, int]:
    verify_source_evidence(core_sha256=core_sha256)
    if not isinstance(payload, (bytes, bytearray, memoryview)) or len(payload) != 8:
        raise ValueError('GameTurnComplete requires exactly eight captured archive bytes')
    kind, player = struct.unpack('<II', payload)
    if kind != MESSAGE_KIND or not 0 <= player < 64:
        raise ValueError('Unverified GameTurnComplete type or player id')
    return {'message_kind': kind, 'player_id': player}

def validate_pre_update_loopback(payload: bytes, expected_player: int, flags, *, core_sha256='d7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3') -> dict:
    """Admit the captured completion only before leaving the observed end phase.

    Global801 makes the native message handler return before gameplay writes.
    The archive has no turn number: delayed delivery after phase transition is
    refused rather than reinterpreted as a new turn's completion.
    """
    decoded = decode_archive(payload, core_sha256=core_sha256)
    if type(expected_player) is not int or not 0 <= expected_player < 64:
        raise ValueError('GameTurnComplete expected player must be a native player id')
    if decoded['player_id'] != expected_player:
        raise ValueError('Captured GameTurnComplete player differs from the observed local player')
    if not isinstance(flags, (bytes, bytearray, tuple, list)) or len(flags) != 4:
        raise ValueError('GameTurnComplete requires all four observed processor bytes')
    if any((type(value) is not int for value in flags)) or tuple(flags) != (1, 1, 0, 0):
        raise ValueError('GameTurnComplete loopback phase changed; stale delivery refused')
    return {**decoded, 'native_handler_expected_to_ignore': True, 'delivery_before_public_update': True, 'contains_turn_number': False, 'eligible_for_training': False}
__all__ = ['MESSAGE_KIND', 'decode_archive', 'validate_pre_update_loopback', 'verify_source_evidence']
