"""Bounded codec for the exact 4D2A6519 city payload shape.

The prefix191/224 witnesses omit the raw key that initializes normalized+0x58.
That case can only be zero-filled for a proven empty receiver and must remain
diagnostic-only; it is not a native default or learner-visible value.
Absent A1FBC is different: source initialization explicitly zeroes its +0x54.
"""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
from dataclasses import dataclass
from pathlib import Path
import struct
from civ6_host.runtime.native.native_application_mirror import decode_scalar
from civ6_host.runtime.native.native_host_events import copy_eight_byte_variant
from civ6_host.runtime.native.native_source_cache import load_pinned_json
EVENT_KIND, CALLBACK_VA, WRITER_VA = (1294624025, '0x140141f60', '0x14012f9a0')
RECORD_TYPE, RECORD_SIZE = (97, 112)
DESCRIPTOR_KEY, SELECTOR_KEY = (594779970, 2716180809)
D6_KEY, A1FBC_KEY, VALUE_38F_KEY = (3606901732, 2717631346, 955421384)
EXE_SHA256 = 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63'
PINNED_EVIDENCE_SHA256 = '30e2b08d50d8197a92b7509489306a668910d1733dcccad8fd26521f988c63ed'
_PROOF = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_event_4d2a6519.py')))).resolve().parents[1] / 'evidence/native-event-4d2a6519' / f'{PINNED_EVIDENCE_SHA256}.json'
_STACK_POLICY = 'headless-zero-uninitialized-stack'
_UNREAD_POLICY = 'zero-unread-empty-receiver-payload'

def verify_source_evidence() -> None:
    proof = load_pinned_json(_PROOF, PINNED_EVIDENCE_SHA256)
    if proof.get('schema') != 'civ6rl.native_event_4d2a6519.static.v2' or proof['parent']['sha256'] != 'e0c5a9476ef0023fb2724187240bb9007e4c3098cd3b37ca7aa2d8f6e839ec0c' or proof.get('exe_sha256') != EXE_SHA256 or (proof['registration']['kind'] != EVENT_KIND) or (proof['registration']['callback_va'] != CALLBACK_VA) or (proof['captures']['callback']['code_sha256'] != 'b4d1f477c17ac5ffa1883d66351d1552c52ad43b78fb67786ed65016e5d4b8a0') or (proof['captures']['writer']['code_sha256'] != '446d052f66f9df2f334733a56857868424fab5146385111e48d67b6c674b15e1') or (proof['captures']['normalizer']['code_sha256'] != 'c757d2f0c927f36e058ff5e57350a80beac1db2a89d3940fcb5e89c05545f23e') or (proof['contract'].get('prefix191_limitation', '').find('omits 38F292C8') < 0):
        raise RuntimeError('Pinned 4D2A6519 source identity changed')

@dataclass(frozen=True)
class EventFields:
    selector: int
    descriptor_bytes: bytes
    owner: int
    item_id: int
    d6_value: int
    a1fbc_value: int
    value_38f: int | None

def _validate(fields: EventFields) -> None:
    if not isinstance(fields, EventFields) or type(fields.selector) is not int or (not 0 <= fields.selector <= 4294967295) or (type(fields.descriptor_bytes) is not bytes) or (len(fields.descriptor_bytes) != 8) or (type(fields.owner) is not int) or (not 0 <= fields.owner <= 65535) or (type(fields.item_id) is not int) or (not 0 <= fields.item_id <= 4294967295) or (struct.unpack_from('<H', fields.descriptor_bytes)[0] != fields.owner) or (struct.unpack_from('<H', fields.descriptor_bytes, 2)[0] != 2) or (struct.unpack_from('<I', fields.descriptor_bytes, 4)[0] != fields.item_id) or any((type(value) is not int or not 0 <= value <= 4294967295 for value in (fields.d6_value, fields.a1fbc_value))) or (fields.value_38f is not None and (type(fields.value_38f) is not int or not 0 <= fields.value_38f <= 4294967295)):
        raise ValueError('4D2A6519 requires exact decoded descriptor and scalar fields')

def decode_fields(raw_fields: dict[int, bytes], read) -> EventFields:
    """Decode the existing 4/5-key inputs or the source-proven 3-key input."""
    verify_source_evidence()
    required = {DESCRIPTOR_KEY, SELECTOR_KEY, D6_KEY}
    if not isinstance(raw_fields, dict) or set(raw_fields) not in (required, required | {A1FBC_KEY}, required | {A1FBC_KEY, VALUE_38F_KEY}):
        raise ValueError('4D2A6519 requires its exact witnessed three/four/five-key shape')
    descriptor = copy_eight_byte_variant(raw_fields[DESCRIPTOR_KEY], read, expected_tag=1024)
    result = EventFields(selector=decode_scalar(raw_fields[SELECTOR_KEY], 3), descriptor_bytes=descriptor, owner=struct.unpack_from('<H', descriptor)[0], item_id=struct.unpack_from('<I', descriptor, 4)[0], d6_value=decode_scalar(raw_fields[D6_KEY], 2), a1fbc_value=decode_scalar(raw_fields[A1FBC_KEY], 2) if A1FBC_KEY in raw_fields else 0, value_38f=decode_scalar(raw_fields[VALUE_38F_KEY], 2) if VALUE_38F_KEY in raw_fields else None)
    _validate(result)
    return result

def encode_record(sequence: int, fields: EventFields, *, normalizer_transform_present: bool, per_thread_hook_present: bool, writer_metadata_callback_present: bool, padding_policy: str, undefined_normalized_value_policy: str='refuse', empty_receiver_state: dict | None=None) -> bytes:
    """Encode the native 0x61 writer shape under an explicit bounded profile.

    If the raw 38F key was absent, normalized+0x58 is uninitialized. Zeroing
    its copied payload DWORD is allowed only for a validated empty receiver;
    returned bytes are then diagnostic-only, never learner state.
    """
    verify_source_evidence()
    _validate(fields)
    if normalizer_transform_present is not False or per_thread_hook_present is not False or writer_metadata_callback_present is not False:
        raise ValueError('4D2A6519 requires absent transform/hook/metadata callback paths')
    if type(sequence) is not int or not 1 <= sequence <= 4294967295:
        raise ValueError('4D2A6519 requires a nonzero uint32 sequence')
    if padding_policy != _STACK_POLICY:
        raise ValueError('4D2A6519 requires explicit zero policy for copied stack padding')
    if fields.value_38f is None:
        if undefined_normalized_value_policy != _UNREAD_POLICY:
            raise ValueError('normalized+0x58 is uninitialized; explicit empty-receiver policy required')
        if not isinstance(empty_receiver_state, dict) or set(empty_receiver_state) != {'observer_registered', 'state_pointer_nonnull', 'pre_hook', 'post_hook', 'subscriber_count', 'state_flags'}:
            raise ValueError('missing 38F requires complete empty receiver state')
    elif undefined_normalized_value_policy != 'refuse' or empty_receiver_state is not None:
        raise ValueError('undefined-value policy is only valid when raw 38F292C8 is absent')
    record = bytearray(RECORD_SIZE)
    struct.pack_into('<IIII', record, 0, RECORD_SIZE, RECORD_TYPE, sequence, 0)
    record[16:24] = b'\xff' * 8
    record[24:64] = bytes.fromhex('ffff0000ffffffff') * 5
    struct.pack_into('<Q', record, 64, 0)
    struct.pack_into('<I', record, 72, 0)
    struct.pack_into('<II', record, 80, sequence, 0)
    struct.pack_into('<I', record, 88, fields.d6_value)
    struct.pack_into('<I', record, 92, 0)
    record[96:104] = fields.descriptor_bytes
    struct.pack_into('<II', record, 104, fields.a1fbc_value, 0 if fields.value_38f is None else fields.value_38f)
    if fields.value_38f is None:
        from civ6_host.runtime.native.native_deferred_empty_profile import validate_empty_profile_record
        validate_empty_profile_record(record, **empty_receiver_state)
    return bytes(record)
