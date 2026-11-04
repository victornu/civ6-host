"""Strict no-op contract for the witnessed absent EXE A0 scalar event."""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import hashlib
import json
import struct
from pathlib import Path
from civ6_host.runtime.native.native_host_event_registry import EXE_EVENT_CALLBACKS
from civ6_host.runtime.native.native_host_event_registry import EXE_EVENT_REGISTRAR_SHA256
ONE_SCALAR_KEYS = frozenset((2716180809,))
TWO_SCALAR_KEYS = frozenset((2716180809, 3606901732))
THREE_SCALAR_KEYS = frozenset((2716180809, 2717631346, 3606901732))
_EVIDENCE_SHA256 = 'c8a52642f234bddd0b9d82ef49a3248b4eaf294414557bca1772a172d7e729d5'
_REGISTRAR_SHA256 = '8c3a94ee3476876ccaddaead057ef1045befdddc65b644a6e7e4f0ab27c22f18'

def _verify_proof() -> None:
    path = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_absent_scalar_a0.py')))).resolve().parents[1] / 'evidence/native-absent-scalar-a0' / f'{_EVIDENCE_SHA256}.json'
    raw = _resolve_resource_path(path).read_bytes()
    actual = hashlib.sha256(raw).hexdigest()
    if actual != _EVIDENCE_SHA256:
        raise RuntimeError(f'Absent scalar A0 proof changed: {actual}')
    proof = json.loads(raw)
    if proof.get('schema') != 'civ6rl.native_absent_scalar_a0.v1' or proof.get('candidate', {}).get('kind') != '0x3f5e7f8d' or proof.get('registrar', {}).get('candidate_kind_absent') is not True or (proof.get('one_key_candidate', {}).get('candidate_kind_absent') is not True) or (proof.get('contract', {}).get('scope') != 'Any uint32 event kind absent from the complete pinned EXE registration set, with exactly the one-key A1E5A149 shape (tag 3), two-key A1E5A149/D6FCF3E4 shape (tags 3/2), or three-key A1E5A149/A1FBC372/D6FCF3E4 shape (tags 3/2/2), selector DWORD zero, uint32 payloads, zero ownership flags, and no other fields.'):
        raise RuntimeError('Absent scalar A0 proof no longer matches the admitted contract')
    if EXE_EVENT_REGISTRAR_SHA256 != _REGISTRAR_SHA256:
        raise RuntimeError('Absent scalar A0 proof refers to a different EXE callback registrar')

def _scalar_variant(raw: bytes, tag: int, label: str, *, value_must_be_zero: bool=False) -> int:
    if not isinstance(raw, (bytes, bytearray, memoryview)) or len(raw) != 24:
        raise ValueError(f'Invalid {label} scalar variant size')
    data = bytes(raw)
    value = struct.unpack_from('<I', data, 8)[0]
    if struct.unpack_from('<H', data)[0] != tag or (value_must_be_zero and value != 0) or struct.unpack_from('<I', data, 20)[0] != 0:
        raise ValueError(f'Unverified {label} scalar variant')
    return value

def validate_absent_scalar_a0(kind: int, raw_fields: dict[int, bytes]) -> dict[str, int | bool | str]:
    """Validate the proven absent-callback no-op scalar shape.

    The return documents the EXE resolver's missing-key result. It does not
    encode a queue record or claim that Core's preceding B0 work was absent.
    """
    if type(kind) is not int or not 0 <= kind <= 4294967295:
        raise ValueError('A0 event kind must be uint32')
    if kind in EXE_EVENT_CALLBACKS:
        raise ValueError('A0 event kind has a registered EXE callback')
    if not isinstance(raw_fields, dict) or set(raw_fields) not in (ONE_SCALAR_KEYS, TWO_SCALAR_KEYS, THREE_SCALAR_KEYS):
        raise ValueError('Unverified A0 scalar descriptor keys')
    _scalar_variant(raw_fields[2716180809], 3, 'A1E5A149', value_must_be_zero=True)
    if set(raw_fields) == THREE_SCALAR_KEYS:
        _scalar_variant(raw_fields[2717631346], 2, 'A1FBC372')
    if 3606901732 in raw_fields:
        _scalar_variant(raw_fields[3606901732], 2, 'D6FCF3E4')
    return {'kind': kind, 'callback_registered': False, 'callback_invoked': False, 'normalizer_result': 0, 'proof': 'native-absent-scalar-a0'}
_verify_proof()
