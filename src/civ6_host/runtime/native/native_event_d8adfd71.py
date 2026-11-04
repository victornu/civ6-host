"""Descriptor-only D8ADFD71 callback under the explicit absent-hook profile."""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
from dataclasses import dataclass
from pathlib import Path
import struct
from civ6_host.runtime.native.native_application_mirror import decode_scalar
from civ6_host.runtime.native.native_host_events import copy_eight_byte_variant
from civ6_host.runtime.native.native_source_cache import load_pinned_json
EVENT_KIND, RECORD_TYPE, RECORD_SIZE = (3635281265, 29, 96)
SELECTOR_KEY, DESCRIPTOR_KEY = (2716180809, 4032072631)
PINNED_EVIDENCE_SHA256 = 'e8e24e46ff1014c55b18cfe4cfc82d9c0c0286ffd4179da12d077c6a8a15ef71'
_PROOF = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_event_d8adfd71.py')))).resolve().parents[1] / 'evidence/native-event-d8adfd71' / f'{PINNED_EVIDENCE_SHA256}.json'

def verify_source_evidence():
    proof = load_pinned_json(_PROOF, PINNED_EVIDENCE_SHA256)
    if proof.get('schema') != 'civ6rl.native_event_d8adfd71.static.v1' or proof['exe_sha256'] != 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63' or proof['registration']['callback_va'] != '0x1401588f0' or (proof['registration']['kind'] != EVENT_KIND) or (proof['captures']['callback']['code_sha256'] != 'e20277265ad407055083285b8f5b770a31fd626c21fabed98de680fc798d5d40') or (proof['captures']['writer']['code_sha256'] != 'c93fd7426379963a8337504bf51777518d02b7a5a9ab9b08f3cef97747354a8a') or (proof['captures']['normalizer']['code_sha256'] != 'c757d2f0c927f36e058ff5e57350a80beac1db2a89d3940fcb5e89c05545f23e'):
        raise RuntimeError('Pinned D8ADFD71 source identity changed')

@dataclass(frozen=True)
class EventFields:
    selector: int
    descriptor_bytes: bytes
    owner: int
    item_id: int

def _validate(fields):
    if not isinstance(fields, EventFields) or type(fields.selector) is not int or (not 0 <= fields.selector <= 4294967295) or (type(fields.descriptor_bytes) is not bytes) or (len(fields.descriptor_bytes) != 8) or (type(fields.owner) is not int) or (not 0 <= fields.owner <= 65535) or (type(fields.item_id) is not int) or (not 0 <= fields.item_id <= 4294967295) or (struct.unpack_from('<H', fields.descriptor_bytes)[0] != fields.owner) or (struct.unpack_from('<I', fields.descriptor_bytes, 4)[0] != fields.item_id):
        raise ValueError('D8ADFD71 requires exact decoded descriptor and selector fields')

def decode_fields(fields, read) -> EventFields:
    verify_source_evidence()
    if not isinstance(fields, dict) or set(fields) != {SELECTOR_KEY, DESCRIPTOR_KEY}:
        raise ValueError('D8ADFD71 requires exactly two source-backed keys')
    descriptor = copy_eight_byte_variant(fields[DESCRIPTOR_KEY], read, expected_tag=1024)
    result = EventFields(decode_scalar(fields[SELECTOR_KEY], 3), descriptor, struct.unpack_from('<H', descriptor)[0], struct.unpack_from('<I', descriptor, 4)[0])
    _validate(result)
    return result

def encode_record(sequence, fields, *, normalizer_transform_present, per_thread_hook_present, writer_metadata_callback_present, padding_policy) -> bytes:
    """Copy native identity into metadata and payload; source type WORD is ignored.

    A1 is normalized but unread by this callback. No Core query, notification
    counter or cache gate is used. Only padding receives the explicit policy.
    """
    verify_source_evidence()
    _validate(fields)
    if normalizer_transform_present is not False or per_thread_hook_present is not False or writer_metadata_callback_present is not False:
        raise ValueError('D8ADFD71 EXE transformation or registered callbacks are unsupported')
    if type(sequence) is not int or not 1 <= sequence <= 4294967295:
        raise ValueError('D8ADFD71 requires a nonzero uint32 sequence')
    if padding_policy != 'headless-zero-uninitialized-stack':
        raise ValueError('D8ADFD71 requires an explicit zero policy for stack padding')
    record = bytearray(RECORD_SIZE)
    struct.pack_into('<IIII', record, 0, RECORD_SIZE, RECORD_TYPE, sequence, 0)
    struct.pack_into('<II', record, 16, 4294967295, 4294967295)
    for offset in (24, 32, 40, 48, 56):
        struct.pack_into('<HHI', record, offset, 65535, 0, 4294967295)
    struct.pack_into('<HHI', record, 24, fields.owner, 1, fields.item_id)
    struct.pack_into('<I', record, 80, sequence)
    struct.pack_into('<HHI', record, 88, fields.owner, 1, fields.item_id)
    return bytes(record)
