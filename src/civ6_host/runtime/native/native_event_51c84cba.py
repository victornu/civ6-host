"""Source-bounded descriptor/DWORD producer for EXE event51C84CBA."""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
from dataclasses import dataclass
from pathlib import Path
import struct
from civ6_host.runtime.native.native_application_mirror import decode_scalar
from civ6_host.runtime.native.native_host_events import copy_eight_byte_variant
from civ6_host.runtime.native.native_source_cache import load_pinned_json
EVENT_KIND, RECORD_TYPE, RECORD_SIZE = (1372081338, 103, 112)
SELECTOR_KEY, VALUE_KEY, DESCRIPTOR_KEY = (2716180809, 3606901732, 594779970)
PINNED_EVIDENCE_SHA256 = '5737bd679a0eb0ca70a955e9f1b571e7f4dd79f3d0b8991e6f0ba4bcd8c2e294'
_PROOF = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_event_51c84cba.py')))).resolve().parents[1] / 'evidence/native-event-51c84cba' / f'{PINNED_EVIDENCE_SHA256}.json'

def verify_source_evidence():
    proof = load_pinned_json(_PROOF, PINNED_EVIDENCE_SHA256)
    if proof.get('schema') != 'civ6rl.native_event_51c84cba.static.v1' or proof['exe_sha256'] != 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63' or proof['registration']['callback_va'] != '0x1401420d0' or (proof['captures']['callback']['code_sha256'] != '44915ae26d1bc22485f284f9e359c77c39984c8b4b01a2c637ca466ee4265f69') or (proof['captures']['writer']['code_sha256'] != '8d681f3401429f5c27bf285705f6a58258d91270161c2114a01380dd9d2ee57a'):
        raise RuntimeError('Pinned51C84CBA source identity changed')

@dataclass(frozen=True)
class EventFields:
    selector: int
    value: int
    descriptor_bytes: bytes
    owner: int
    item_id: int

def _validate(fields):
    if not isinstance(fields, EventFields) or type(fields.descriptor_bytes) is not bytes or len(fields.descriptor_bytes) != 8 or (type(fields.owner) is not int) or (not 0 <= fields.owner <= 65535) or (struct.unpack_from('<H', fields.descriptor_bytes)[0] != fields.owner) or (type(fields.item_id) is not int) or (not 0 <= fields.item_id <= 4294967295) or (struct.unpack_from('<I', fields.descriptor_bytes, 4)[0] != fields.item_id) or (type(fields.value) is not int) or (not 0 <= fields.value <= 4294967295) or (type(fields.selector) is not int) or (not 0 <= fields.selector <= 4294967295):
        raise ValueError('51C84CBA requires exact decoded source fields')

def decode_fields(fields, read) -> EventFields:
    """Copy the safe witnessed envelope; preserve live owner/id/DWORD values.

    The normalizer ignores the descriptor's input WORD+2 and independently
    initializes its type to2. A1 is typed input but does not select the thread.
    """
    verify_source_evidence()
    if not isinstance(fields, dict) or set(fields) != {SELECTOR_KEY, VALUE_KEY, DESCRIPTOR_KEY}:
        raise ValueError('51C84CBA requires exactly the three source-backed keys')
    descriptor = copy_eight_byte_variant(fields[DESCRIPTOR_KEY], read, expected_tag=1024)
    result = EventFields(decode_scalar(fields[SELECTOR_KEY], 3), decode_scalar(fields[VALUE_KEY], 2), descriptor, struct.unpack_from('<H', descriptor)[0], struct.unpack_from('<I', descriptor, 4)[0])
    _validate(result)
    return result

def encode_record(sequence, fields, *, normalizer_transform_present, per_thread_hook_present, writer_metadata_callback_present, padding_policy) -> bytes:
    """Produce the record in the explicit no-EXE-transform/callback profile.

    No native Core query or notification counter is involved. The sequence is
    supplied by the host queue and is written to both source-defined offsets.
    The two copied stack-padding DWORDs use the explicit diagnostic policy.
    """
    verify_source_evidence()
    _validate(fields)
    if normalizer_transform_present is not False or per_thread_hook_present is not False or writer_metadata_callback_present is not False:
        raise ValueError('51C84CBA EXE transformation or registered callbacks are unsupported')
    if type(sequence) is not int or not 1 <= sequence <= 4294967295:
        raise ValueError('51C84CBA requires a nonzero uint32 sequence')
    if padding_policy != 'headless-zero-uninitialized-stack':
        raise ValueError('51C84CBA requires an explicit zero policy for stack padding')
    record = bytearray(RECORD_SIZE)
    struct.pack_into('<IIII', record, 0, RECORD_SIZE, RECORD_TYPE, sequence, 0)
    struct.pack_into('<II', record, 16, 4294967295, 4294967295)
    for offset in (24, 32, 40, 48, 56):
        struct.pack_into('<HHI', record, offset, 65535, 0, 4294967295)
    struct.pack_into('<I', record, 80, sequence)
    struct.pack_into('<HHII', record, 88, fields.owner, 2, fields.item_id, fields.value)
    return bytes(record)
