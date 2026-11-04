"""Source-scoped record adapter for EXE event 0x87667464."""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
from dataclasses import dataclass
from pathlib import Path
import struct
from civ6_host.runtime.native.native_application_mirror import decode_scalar
from civ6_host.runtime.native.native_source_cache import load_pinned_json
EVENT_KIND = 2271638628
CALLBACK_RVA = 1321456
QUEUE_WRITER_RVA = 1280240
RECORD_SIZE, RECORD_TYPE = (96, 192)
SELECTOR_KEY, A1FBC_KEY, D6_KEY = (2716180809, 2717631346, 3606901732)
PINNED_EVIDENCE_SHA256 = '8ee63e1e120bb2877f4166f4b91321cbf0d342da9f5f5c5151e4d85fda3e38c3'
_PROOF = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_event_87667464.py')))).resolve().parents[1] / 'evidence' / 'native-event-87667464' / f'{PINNED_EVIDENCE_SHA256}.json'
_EXE_SHA256 = 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63'
_PADDING_POLICY = 'zero-unread-empty-subscriber-record'

def verify_source_evidence():
    proof = load_pinned_json(_PROOF, PINNED_EVIDENCE_SHA256)
    captures = proof.get('captures', {})
    if proof.get('schema') != 'civ6rl.native_event_87667464.static.v1' or proof.get('images', {}).get('exe_sha256') != _EXE_SHA256 or proof.get('registration', {}).get('entry', {}).get('callback_va') != '0x1401429f0' or (captures.get('callback', {}).get('code_sha256') != '540766a73998cee558b8f5eb10fe3ae79667fb536694419c60bcc1b3402bf39e') or (captures.get('group_ring_writer', {}).get('code_sha256') != '40f05f20bad1bea3be3c217f7275ebb5d37704998e817565381985dcc24262b0'):
        raise RuntimeError('Pinned 87667464 source identity changed')

@dataclass(frozen=True)
class EventFields:
    selector: int
    a1fbc_value: int
    d6_value: int

def _uint32(value, label):
    if type(value) is not int or not 0 <= value <= 4294967295:
        raise ValueError(f'87667464 {label} must be uint32')

def _validate(fields):
    if not isinstance(fields, EventFields):
        raise ValueError('87667464 requires decoded source fields')
    _uint32(fields.selector, 'selector')
    _uint32(fields.a1fbc_value, 'A1FBC value')
    _uint32(fields.d6_value, 'D6 value')
    if fields.selector != 0:
        raise ValueError('Only the source-witnessed 87667464 selector zero is admitted')

def decode_fields(raw_fields: dict[int, bytes]) -> EventFields:
    verify_source_evidence()
    if not isinstance(raw_fields, dict) or set(raw_fields) != {SELECTOR_KEY, A1FBC_KEY, D6_KEY}:
        raise ValueError('87667464 requires exactly A1E5A149, A1FBC372 and D6FCF3E4')
    result = EventFields(selector=decode_scalar(raw_fields[SELECTOR_KEY], 3), a1fbc_value=decode_scalar(raw_fields[A1FBC_KEY], 2), d6_value=decode_scalar(raw_fields[D6_KEY], 2))
    _validate(result)
    return result

def _source_record(sequence: int, fields: EventFields) -> bytes:
    """Encode callback/writer bytes; caller must separately prove empty receiver."""
    _validate(fields)
    if type(sequence) is not int or not 1 <= sequence <= 4294967295:
        raise ValueError('87667464 requires a nonzero uint32 ring sequence')
    record = bytearray(RECORD_SIZE)
    struct.pack_into('<IIII', record, 0, RECORD_SIZE, RECORD_TYPE, sequence, 0)
    for offset in (0, 4, 12, 20, 28, 36, 44):
        struct.pack_into('<I', record, 16 + offset, 4294967295)
    for offset in (8, 16, 24, 32, 40):
        struct.pack_into('<H', record, 16 + offset, 65535)
    for offset in (10, 18, 26, 34, 42):
        struct.pack_into('<H', record, 16 + offset, 0)
    struct.pack_into('<Q', record, 16 + 48, 0)
    struct.pack_into('<I', record, 16 + 56, 4)
    struct.pack_into('<IIII', record, 80, sequence, fields.d6_value, fields.a1fbc_value, 0)
    return bytes(record)

def encode_record(sequence: int, fields: EventFields, *, per_thread_hook_present: bool, queue_hook_present: bool, padding_policy: str, empty_receiver_state: dict | None) -> bytes:
    verify_source_evidence()
    _validate(fields)
    if per_thread_hook_present is not False or queue_hook_present is not False:
        raise ValueError('87667464 optional callback paths are unsupported')
    if padding_policy != _PADDING_POLICY:
        raise ValueError('87667464 requires the explicit empty-subscriber padding policy')
    if not isinstance(empty_receiver_state, dict) or set(empty_receiver_state) != {'observer_registered', 'state_pointer_nonnull', 'pre_hook', 'post_hook', 'subscriber_count', 'state_flags'}:
        raise ValueError('87667464 requires complete empty receiver state')
    record = _source_record(sequence, fields)
    from civ6_host.runtime.native.native_deferred_empty_profile import validate_empty_profile_record
    validate_empty_profile_record(record, **empty_receiver_state)
    return record
__all__ = ['EVENT_KIND', 'CALLBACK_RVA', 'QUEUE_WRITER_RVA', 'RECORD_SIZE', 'RECORD_TYPE', 'EventFields', 'decode_fields', 'encode_record', 'verify_source_evidence']
