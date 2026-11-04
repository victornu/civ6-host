"""Source-scoped candidate record for EXE event 0x025F6CFD.

The encoder returns producer bytes only. Record type 0x101 has no verified
empty-receiver row in the current profile, so this module does not authorize
enqueueing the candidate or claim runtime equivalence.
"""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
from dataclasses import dataclass
from pathlib import Path
import struct
from civ6_host.runtime.native.native_application_mirror import decode_scalar
from civ6_host.runtime.native.native_source_cache import load_pinned_json
EVENT_KIND = 39808253
CALLBACK_RVA = 1352160
WRITER_RVA = 1175280
RECORD_SIZE, RECORD_TYPE = (112, 257)
BOOL_KEY, SELECTOR_KEY, DESCRIPTOR_KEY = (2023946566, 2716180809, 3937836634)
PINNED_EVIDENCE_SHA256 = '434e5bb317c7f822b12ca995c64ceb6103ddb45d0cd36f14ca03ca440d4eddef'
_PROOF = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_event_025f6cfd.py')))).resolve().parents[1] / 'evidence' / 'native-event-025f6cfd' / f'{PINNED_EVIDENCE_SHA256}.json'
_EXE_SHA256 = 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63'
_PADDING_POLICY = 'zero-uninitialized-record-candidate'

def verify_source_evidence():
    proof = load_pinned_json(_PROOF, PINNED_EVIDENCE_SHA256)
    captures = proof.get('captures', {})
    expected = {'callback': 'a1e2cf357d5873acb255c9707861be8cd7eab45718a787fea0c847587bed1a27', 'normalizer': 'c757d2f0c927f36e058ff5e57350a80beac1db2a89d3940fcb5e89c05545f23e', 'standard_enqueue_writer': '34eda7c66fdaa3406e0071cfe4f69182d5f9b143390b8306a37626f42219caf4'}
    if proof.get('schema') != 'civ6rl.native_event_025f6cfd.static.v1' or proof.get('images', {}).get('exe_sha256') != _EXE_SHA256 or proof.get('registration', {}).get('entry', {}).get('callback_va') != '0x14014a1e0' or any((captures.get(name, {}).get('code_sha256') != digest for name, digest in expected.items())):
        raise RuntimeError('Pinned 025F6CFD source identity changed')

@dataclass(frozen=True)
class EventFields:
    selector: int
    raw_boolean_byte: int
    descriptor_owner: int
    descriptor_type: int
    descriptor_id: int

def _uint(value, maximum, label):
    if type(value) is not int or not 0 <= value <= maximum:
        raise ValueError(f'025F6CFD {label} out of range')

def _variant(raw, label):
    if not isinstance(raw, bytes) or len(raw) != 24:
        raise ValueError(f'025F6CFD {label} requires a 24-byte source variant')
    return (struct.unpack_from('<H', raw)[0], struct.unpack_from('<I', raw, 20)[0])

def _validate(fields):
    if not isinstance(fields, EventFields):
        raise ValueError('025F6CFD requires decoded source fields')
    _uint(fields.selector, 4294967295, 'selector')
    _uint(fields.raw_boolean_byte, 255, 'boolean byte')
    _uint(fields.descriptor_owner, 65535, 'descriptor owner')
    _uint(fields.descriptor_type, 65535, 'descriptor type')
    _uint(fields.descriptor_id, 4294967295, 'descriptor id')
    if fields.selector != 0:
        raise ValueError('Only the observed 025F6CFD selector zero is admitted')

def decode_fields(raw_fields: dict[int, bytes], pointer_payloads: dict[int, dict]) -> EventFields:
    verify_source_evidence()
    if not isinstance(raw_fields, dict) or set(raw_fields) != {BOOL_KEY, SELECTOR_KEY, DESCRIPTOR_KEY}:
        raise ValueError('025F6CFD requires exactly 78A2F946, A1E5A149 and EAB69E5A')
    if not isinstance(pointer_payloads, dict) or set(pointer_payloads) != {DESCRIPTOR_KEY}:
        raise ValueError('025F6CFD requires the observed descriptor pointer payload')
    selector = decode_scalar(raw_fields[SELECTOR_KEY], 3)
    bool_tag, bool_flags = _variant(raw_fields[BOOL_KEY], '78A2F946')
    if bool_tag != 1 or bool_flags & 536870912:
        raise ValueError('025F6CFD bool converter only admits tag 1 without pointer flag')
    raw_boolean_byte = raw_fields[BOOL_KEY][8]
    desc_tag, desc_flags = _variant(raw_fields[DESCRIPTOR_KEY], 'EAB69E5A')
    if desc_tag != 1024 or not desc_flags & 536870912:
        raise ValueError('025F6CFD descriptor must be the source-read tag-0x400 pointer variant')
    pointer = struct.unpack_from('<Q', raw_fields[DESCRIPTOR_KEY], 8)[0]
    if pointer == 0:
        raise ValueError('025F6CFD source dereferences a null descriptor pointer')
    payload = pointer_payloads[DESCRIPTOR_KEY]
    if not isinstance(payload, dict) or set(payload) != {'bytes_hex', 'byte_count'}:
        raise ValueError('025F6CFD descriptor payload must be an exact bounded capture')
    raw = payload['bytes_hex']
    if type(payload['byte_count']) is not int or payload['byte_count'] != 8:
        raise ValueError('025F6CFD descriptor payload must be exactly 8 bytes')
    if not isinstance(raw, str) or len(raw) != 16:
        raise ValueError('025F6CFD descriptor payload has invalid hexadecimal size')
    try:
        descriptor = bytes.fromhex(raw)
    except ValueError as exc:
        raise ValueError('025F6CFD descriptor payload is not hexadecimal') from exc
    if len(descriptor) != 8:
        raise ValueError('025F6CFD descriptor payload must be exactly 8 bytes')
    owner, descriptor_type, descriptor_id = struct.unpack('<HHI', descriptor)
    fields = EventFields(selector, raw_boolean_byte, owner, descriptor_type, descriptor_id)
    _validate(fields)
    return fields

def encode_record_candidate(sequence: int, fields: EventFields, *, normalizer_transform_present: bool, per_thread_hook_present: bool, writer_callback_present: bool, padding_policy: str) -> bytes:
    """Encode callback/writer bytes, without claiming receiver admission."""
    verify_source_evidence()
    _validate(fields)
    if normalizer_transform_present is not False or per_thread_hook_present is not False or writer_callback_present is not False:
        raise ValueError('025F6CFD transform/hook callbacks are unsupported')
    if padding_policy != _PADDING_POLICY:
        raise ValueError('025F6CFD requires explicit diagnostic-only padding policy')
    _uint(sequence, 4294967295, 'sequence')
    if sequence == 0:
        raise ValueError('025F6CFD requires a nonzero writer sequence')
    record = bytearray(RECORD_SIZE)
    struct.pack_into('<IIII', record, 0, RECORD_SIZE, RECORD_TYPE, sequence, 0)
    for offset in (0, 4, 12, 20, 28, 36, 44):
        struct.pack_into('<I', record, 16 + offset, 4294967295)
    for offset in (8, 16, 24, 32, 40):
        struct.pack_into('<H', record, 16 + offset, 65535)
    for offset in (10, 18, 26, 34, 42):
        struct.pack_into('<H', record, 16 + offset, 0)
    struct.pack_into('<Q', record, 64, 0)
    struct.pack_into('<I', record, 72, 4)
    struct.pack_into('<I', record, 80, sequence)
    struct.pack_into('<HHI', record, 88, fields.descriptor_owner, fields.descriptor_type, fields.descriptor_id)
    record[96] = fields.raw_boolean_byte
    return bytes(record)
__all__ = ['EVENT_KIND', 'CALLBACK_RVA', 'WRITER_RVA', 'RECORD_SIZE', 'RECORD_TYPE', 'BOOL_KEY', 'SELECTOR_KEY', 'DESCRIPTOR_KEY', 'EventFields', 'decode_fields', 'encode_record_candidate', 'verify_source_evidence']
