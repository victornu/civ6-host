"""Source-bounded descriptor-only producer for EXE event99E85EC6."""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
from dataclasses import dataclass
from pathlib import Path
import struct
from civ6_host.runtime.native.native_application_mirror import decode_scalar
from civ6_host.runtime.native.native_host_events import copy_eight_byte_variant
from civ6_host.runtime.native.native_source_cache import load_pinned_json
EVENT_KIND, RECORD_TYPE, RECORD_SIZE = (2582142662, 104, 96)
SELECTOR_KEY, DESCRIPTOR_KEY = (2716180809, 594779970)
PINNED_EVIDENCE_SHA256 = 'bb363e13920412a44fde541151de7cc69047a9706773a7be939dc646ef4e687e'
_PROOF = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_event_99e85ec6.py')))).resolve().parents[1] / 'evidence/native-event-99e85ec6' / f'{PINNED_EVIDENCE_SHA256}.json'

def verify_source_evidence():
    proof = load_pinned_json(_PROOF, PINNED_EVIDENCE_SHA256)
    if proof.get('schema') != 'civ6rl.native_event_99e85ec6.static.v1' or proof['exe_sha256'] != 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63' or proof['registration']['callback_va'] != '0x140142180' or (proof['captures']['callback']['code_sha256'] != '67433c13b7016d3d8f9485fc8dcb52c5884a7c26ff0522be107bbda3140e32ae') or (proof['captures']['writer']['code_sha256'] != '44b4da6daaa12aacb5939374a86ec851da551c8dad679a5d086966075d74672f'):
        raise RuntimeError('Pinned99E85EC6 source identity changed')

@dataclass(frozen=True)
class EventFields:
    selector: int
    descriptor_bytes: bytes
    owner: int
    item_id: int

def _validate(fields):
    if not isinstance(fields, EventFields) or type(fields.descriptor_bytes) is not bytes or len(fields.descriptor_bytes) != 8 or (type(fields.owner) is not int) or (not 0 <= fields.owner <= 65535) or (struct.unpack_from('<H', fields.descriptor_bytes)[0] != fields.owner) or (type(fields.item_id) is not int) or (not 0 <= fields.item_id <= 4294967295) or (struct.unpack_from('<I', fields.descriptor_bytes, 4)[0] != fields.item_id) or (type(fields.selector) is not int) or (not 0 <= fields.selector <= 4294967295):
        raise ValueError('99E85EC6 requires exact decoded source fields')

def decode_fields(fields, read) -> EventFields:
    """Copy a safe typed descriptor; input WORD2 is ignored by the normalizer."""
    verify_source_evidence()
    if not isinstance(fields, dict) or set(fields) != {SELECTOR_KEY, DESCRIPTOR_KEY}:
        raise ValueError('99E85EC6 requires exactly two source-backed keys')
    descriptor = copy_eight_byte_variant(fields[DESCRIPTOR_KEY], read, expected_tag=1024)
    result = EventFields(decode_scalar(fields[SELECTOR_KEY], 3), descriptor, struct.unpack_from('<H', descriptor)[0], struct.unpack_from('<I', descriptor, 4)[0])
    _validate(result)
    return result

def encode_record(sequence, fields, *, normalizer_transform_present, per_thread_hook_present, writer_metadata_callback_present, padding_policy) -> bytes:
    """Encode a type68 record in the explicit absent-EXE-callback profile.

    The source initializes normalized type2 independently of input WORD2.
    A1 does not select a thread. No native query or counter state is involved.
    PayloadDWORD+4 has no source value and requires a diagnostic zero policy.
    """
    verify_source_evidence()
    _validate(fields)
    if normalizer_transform_present is not False or per_thread_hook_present is not False or writer_metadata_callback_present is not False:
        raise ValueError('99E85EC6 EXE transformation or registered callbacks are unsupported')
    if type(sequence) is not int or not 1 <= sequence <= 4294967295:
        raise ValueError('99E85EC6 requires a nonzero uint32 sequence')
    if padding_policy != 'headless-zero-uninitialized-stack':
        raise ValueError('99E85EC6 requires an explicit zero policy for stack padding')
    record = bytearray(RECORD_SIZE)
    struct.pack_into('<IIII', record, 0, RECORD_SIZE, RECORD_TYPE, sequence, 0)
    struct.pack_into('<II', record, 16, 4294967295, 4294967295)
    for offset in (24, 32, 40, 48, 56):
        struct.pack_into('<HHI', record, offset, 65535, 0, 4294967295)
    struct.pack_into('<I', record, 80, sequence)
    struct.pack_into('<HHI', record, 88, fields.owner, 2, fields.item_id)
    return bytes(record)
