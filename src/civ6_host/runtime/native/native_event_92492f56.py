"""Source-pinned city descriptor and two-DWORD 92492F56 producer."""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
from dataclasses import dataclass
from pathlib import Path
import struct
from civ6_host.runtime.native.native_application_mirror import decode_scalar
from civ6_host.runtime.native.native_host_events import copy_eight_byte_variant
from civ6_host.runtime.native.native_source_cache import load_pinned_json
EVENT_KIND, RECORD_TYPE, RECORD_SIZE = (2454269782, 98, 112)
SELECTOR_KEY, DESCRIPTOR_KEY = (2716180809, 594779970)
D6_KEY, A1FBC_KEY = (3606901732, 2717631346)
PINNED_EVIDENCE_SHA256 = '43c92c26b4353668543506f2b8e901cedfd69738822d959af69e8656f61194cc'
_PROOF = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_event_92492f56.py')))).resolve().parents[1] / 'evidence/native-event-92492f56' / f'{PINNED_EVIDENCE_SHA256}.json'

def verify_source_evidence():
    proof = load_pinned_json(_PROOF, PINNED_EVIDENCE_SHA256)
    if proof.get('schema') != 'civ6rl.native_event_92492f56.static.v2' or proof['exe_sha256'] != 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63' or proof['registration']['callback_va'] != '0x140141ea0' or (proof['registration']['kind'] != EVENT_KIND) or (proof['captures']['callback']['code_sha256'] != '5e5c76cd798d82fc4c16836fff9c716dbf818a1513acd1b3d4cb0b194c7ca1b7') or (proof['captures']['writer']['code_sha256'] != 'd0f13f1397ee665feacc4c83204ccf7db8bbdba9da090aa5d3383f103d31d399') or (proof['captures']['normalizer']['code_sha256'] != 'c757d2f0c927f36e058ff5e57350a80beac1db2a89d3940fcb5e89c05545f23e'):
        raise RuntimeError('Pinned 92492F56 source identity changed')

@dataclass(frozen=True)
class EventFields:
    selector: int
    descriptor_bytes: bytes
    owner: int
    item_id: int
    d6_value: int
    a1fbc_value: int

def _validate(fields):
    if not isinstance(fields, EventFields) or type(fields.selector) is not int or (not 0 <= fields.selector <= 4294967295) or (type(fields.descriptor_bytes) is not bytes) or (len(fields.descriptor_bytes) != 8) or (type(fields.owner) is not int) or (not 0 <= fields.owner <= 65535) or (type(fields.item_id) is not int) or (not 0 <= fields.item_id <= 4294967295) or (struct.unpack_from('<H', fields.descriptor_bytes)[0] != fields.owner) or (struct.unpack_from('<I', fields.descriptor_bytes, 4)[0] != fields.item_id) or any((type(value) is not int or not 0 <= value <= 4294967295 for value in (fields.d6_value, fields.a1fbc_value))):
        raise ValueError('92492F56 requires exact decoded descriptor and scalar fields')

def decode_fields(fields, read) -> EventFields:
    verify_source_evidence()
    required = {SELECTOR_KEY, DESCRIPTOR_KEY, D6_KEY}
    if not isinstance(fields, dict) or set(fields) not in (required, required | {A1FBC_KEY}):
        raise ValueError('92492F56 requires exactly three keys with optional fourth A1FBC')
    descriptor = copy_eight_byte_variant(fields[DESCRIPTOR_KEY], read, expected_tag=1024)
    result = EventFields(decode_scalar(fields[SELECTOR_KEY], 3), descriptor, struct.unpack_from('<H', descriptor)[0], struct.unpack_from('<I', descriptor, 4)[0], decode_scalar(fields[D6_KEY], 2), decode_scalar(fields[A1FBC_KEY], 2) if A1FBC_KEY in fields else 0)
    _validate(result)
    return result

def encode_record(sequence, fields, *, normalizer_transform_present, per_thread_hook_present, writer_metadata_callback_present, padding_policy) -> bytes:
    """Copy city identity and two DWORD bit patterns with writer default metadata.

    A1 is normalized but unread; normalized+58 is never read. A1FBC is
    copied without a Core query. Its absence preserves source-zero normalized
    +54, initialized by the QWORD store at1CA3B6, rather than substituting for
    a raw-field lookup. Record+54..57 is explicit diagnostic stack
    padding; +68..6F is zero from the writer's allocation loop, outside the
    0x18-byte copied payload. No notification counter or cache gate is read.
    """
    verify_source_evidence()
    _validate(fields)
    if normalizer_transform_present is not False or per_thread_hook_present is not False or writer_metadata_callback_present is not False:
        raise ValueError('92492F56 EXE transformation or registered callbacks are unsupported')
    if type(sequence) is not int or not 1 <= sequence <= 4294967295:
        raise ValueError('92492F56 requires a nonzero uint32 sequence')
    if padding_policy != 'headless-zero-uninitialized-stack':
        raise ValueError('92492F56 requires an explicit zero policy for stack padding')
    record = bytearray(RECORD_SIZE)
    struct.pack_into('<IIII', record, 0, RECORD_SIZE, RECORD_TYPE, sequence, 0)
    struct.pack_into('<II', record, 16, 4294967295, 4294967295)
    for offset in (24, 32, 40, 48, 56):
        struct.pack_into('<HHI', record, offset, 65535, 0, 4294967295)
    struct.pack_into('<I', record, 80, sequence)
    struct.pack_into('<HHI', record, 88, fields.owner, 2, fields.item_id)
    struct.pack_into('<II', record, 96, fields.d6_value, fields.a1fbc_value)
    return bytes(record)
