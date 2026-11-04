"""Source-bounded unit descriptor/position/raw-byte event 981A9186."""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
from dataclasses import dataclass
from pathlib import Path
import struct
from civ6_host.runtime.native.native_application_mirror import decode_scalar
from civ6_host.runtime.native.native_event_827289e6 import _copy_blob
from civ6_host.runtime.native.native_host_events import copy_eight_byte_variant
from civ6_host.runtime.native.native_source_cache import load_pinned_json
EVENT_KIND, RECORD_TYPE, RECORD_SIZE = (2551878022, 73, 112)
SELECTOR_KEY, DESCRIPTOR_KEY = (2716180809, 4032072631)
POSITION_KEY, BOOLEAN_KEY = (2353434172, 1849331523)
PINNED_EVIDENCE_SHA256 = 'f3857dedb48039eceffad76d5a47c3b8076b0ebe3975608c6999963232d6a6a3'
_PROOF = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_event_981a9186.py')))).resolve().parents[1] / 'evidence/native-event-981a9186' / f'{PINNED_EVIDENCE_SHA256}.json'

def verify_source_evidence():
    proof = load_pinned_json(_PROOF, PINNED_EVIDENCE_SHA256)
    if proof.get('schema') != 'civ6rl.native_event_981a9186.static.v1' or proof['exe_sha256'] != 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63' or proof['event_registration']['callback_va'] != '0x1401548f0' or (proof['event_registration']['kind'] != EVENT_KIND) or (proof['captures']['callbacks']['75']['code_sha256'] != 'cc7a57b7c18744a1def5e42e74c667944322c6a5d97b05a85a6e1800e9660592') or (proof['captures']['writers']['0x14012d300']['code_sha256'] != 'dbab085336f9240bbe05c16aaebbead2faf565f0f3e2427076e6cf8203e7ed12') or (proof['captures']['raw_byte_conversion_helper']['reachable_bytes_sha256'] != 'b34992484176208cbb449f2b79c3320d50d867a8fc2318aea9cada02ac34c218') or (proof['captures']['shared_normalizer']['code_sha256'] != 'c757d2f0c927f36e058ff5e57350a80beac1db2a89d3940fcb5e89c05545f23e'):
        raise RuntimeError('Pinned981A9186 source identity changed')

@dataclass(frozen=True)
class EventFields:
    selector: int
    descriptor_bytes: bytes
    owner: int
    item_id: int
    position_bytes: bytes
    raw_boolean_byte: int

def _validate(fields):
    if not isinstance(fields, EventFields) or type(fields.selector) is not int or (not 0 <= fields.selector <= 4294967295) or (type(fields.descriptor_bytes) is not bytes) or (len(fields.descriptor_bytes) != 8) or (type(fields.owner) is not int) or (not 0 <= fields.owner <= 65535) or (type(fields.item_id) is not int) or (not 0 <= fields.item_id <= 4294967295) or (struct.unpack_from('<H', fields.descriptor_bytes)[0] != fields.owner) or (struct.unpack_from('<I', fields.descriptor_bytes, 4)[0] != fields.item_id) or (type(fields.position_bytes) is not bytes) or (len(fields.position_bytes) != 8) or (type(fields.raw_boolean_byte) is not int) or (not 0 <= fields.raw_boolean_byte <= 255):
        raise ValueError('981A9186 requires exact descriptor, position, selector and raw-byte fields')

def decode_fields(fields, read) -> EventFields:
    """Copy only the four proven inputs; the mandatory boolean avoids an undefined byte."""
    verify_source_evidence()
    if not isinstance(fields, dict) or set(fields) != {SELECTOR_KEY, DESCRIPTOR_KEY, POSITION_KEY, BOOLEAN_KEY}:
        raise ValueError('981A9186 requires exactly four source-backed keys')
    descriptor = copy_eight_byte_variant(fields[DESCRIPTOR_KEY], read, expected_tag=1024)
    position = _copy_blob(fields[POSITION_KEY], read, 13, '981A9186 position')
    raw = fields[BOOLEAN_KEY]
    if type(raw) is not bytes or len(raw) != 24 or struct.unpack_from('<H', raw)[0] != 1 or (struct.unpack_from('<I', raw, 20)[0] != 0):
        raise ValueError('981A9186 boolean must be a direct tag1 variant with zero flags')
    result = EventFields(decode_scalar(fields[SELECTOR_KEY], 3), descriptor, struct.unpack_from('<H', descriptor)[0], struct.unpack_from('<I', descriptor, 4)[0], position, raw[8])
    _validate(result)
    return result

def encode_record(sequence, fields, *, normalizer_transform_present, per_thread_hook_present, writer_metadata_callback_present, padding_policy) -> bytes:
    """Encode writer12D300's type49/70 record with input identity in metadata.

    The normalizer supplies type1 independently of input WORD2. The callback
    reads the raw boolean variant separately and preserves its BYTE payload.
    No Core query or notification counter is read on this path.
    """
    verify_source_evidence()
    _validate(fields)
    if normalizer_transform_present is not False or per_thread_hook_present is not False or writer_metadata_callback_present is not False:
        raise ValueError('981A9186 EXE transformation or registered callbacks are unsupported')
    if type(sequence) is not int or not 1 <= sequence <= 4294967295:
        raise ValueError('981A9186 requires a nonzero uint32 sequence')
    if padding_policy != 'headless-zero-uninitialized-stack':
        raise ValueError('981A9186 requires an explicit zero policy for stack padding')
    record = bytearray(RECORD_SIZE)
    struct.pack_into('<IIII', record, 0, RECORD_SIZE, RECORD_TYPE, sequence, 0)
    struct.pack_into('<II', record, 16, 4294967295, 4294967295)
    for offset in (24, 32, 40, 48, 56):
        struct.pack_into('<HHI', record, offset, 65535, 0, 4294967295)
    struct.pack_into('<HHI', record, 24, fields.owner, 1, fields.item_id)
    struct.pack_into('<I', record, 80, sequence)
    struct.pack_into('<HHI', record, 88, fields.owner, 1, fields.item_id)
    record[96:104] = fields.position_bytes
    struct.pack_into('<I', record, 104, fields.selector)
    record[108] = fields.raw_boolean_byte
    return bytes(record)
