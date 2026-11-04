"""Strict no-EXE-callback result for Core event 0xB6B48D9C.

Core's internal work is outside this adapter. The pinned EXE registry has no
callback for this kind, and its shared resolver returns zero on absent keys;
this module validates that host-side no-op outcome without constructing a
deferred record.
"""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import hashlib
import json
import struct
from dataclasses import dataclass
from pathlib import Path
EVENT_KIND = 3065286044
FIELD_SELECTOR = 2716180809
FIELD_VALUE_B = 2717631346
FIELD_VALUE = 3606901732
EXE_SHA256 = 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63'
CORE_SHA256 = 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'
REGISTRY_SHA256 = 'ec49b8df386e35cafc401986fb1512a89e19ebe7d94f8963684ac67505a1b0f5'
PINNED_EVIDENCE_SHA256 = '5b34ac4145e50f3693e67dd5288f653c538720509b5dbc051bf092a4b28e7883'
PINNED_NORMALIZER_SHA256 = 'c757d2f0c927f36e058ff5e57350a80beac1db2a89d3940fcb5e89c05545f23e'

@dataclass(frozen=True)
class ValidatedAbsentHostCallback:
    event_kind: int
    selector: int
    value_b: int
    value: int
    host_record: None = None
    exe_callback_registered: bool = False

def verify_source_evidence() -> None:
    path = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_event_b6b48d9c.py')))).resolve().parents[1] / 'evidence' / 'native-event-b6b48d9c' / f'{PINNED_EVIDENCE_SHA256}.json'
    raw = _resolve_resource_path(path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != PINNED_EVIDENCE_SHA256:
        raise RuntimeError('Pinned B6B48D9C evidence bytes changed')
    doc = json.loads(raw)
    if doc.get('images', {}).get('exe_sha256') != EXE_SHA256 or doc.get('images', {}).get('core_sha256') != CORE_SHA256 or doc.get('event', {}).get('kind') != hex(EVENT_KIND) or (doc.get('exe_registry', {}).get('sha256') != REGISTRY_SHA256) or (doc.get('exe_registry', {}).get('registration_count') != 317) or (doc.get('exe_registry', {}).get('kind_registered') is not False) or (doc.get('body_sha256', {}).get('normalizer') != PINNED_NORMALIZER_SHA256):
        raise RuntimeError('B6B48D9C absent-callback source contract changed')

def _read_scalar(raw, expected_tag: int, label: str, *, expected_value: int | None=None) -> int:
    if not isinstance(raw, (bytes, bytearray, memoryview)) or len(raw) != 24:
        raise ValueError(f'Truncated B6B48D9C {label} variant')
    tag = struct.unpack_from('<H', raw, 0)[0]
    value = struct.unpack_from('<I', raw, 8)[0]
    flags = struct.unpack_from('<I', raw, 20)[0]
    if tag != expected_tag or (expected_value is not None and value != expected_value) or flags != 0:
        raise ValueError(f'Unverified B6B48D9C {label} tag/value/flags')
    return value

def decode_fields(raw_fields: dict[int, bytes]) -> ValidatedAbsentHostCallback:
    """Validate Prefix108's exact three scalar fields; no record is emitted."""
    verify_source_evidence()
    if not isinstance(raw_fields, dict) or set(raw_fields) != {FIELD_SELECTOR, FIELD_VALUE_B, FIELD_VALUE}:
        raise ValueError('Unverified B6B48D9C descriptor keys')
    selector = _read_scalar(raw_fields[FIELD_SELECTOR], 3, 'selector', expected_value=0)
    value_b = _read_scalar(raw_fields[FIELD_VALUE_B], 2, 'value B')
    value = _read_scalar(raw_fields[FIELD_VALUE], 2, 'value')
    return ValidatedAbsentHostCallback(EVENT_KIND, selector, value_b, value)
