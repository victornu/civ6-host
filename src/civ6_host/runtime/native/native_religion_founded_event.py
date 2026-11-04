"""Strict diagnostic codec for the native ReligionFounded C4 ring record.

The codec mirrors the pinned EXE callback/writer shape. It does not found a
religion, invoke a callback, or make the record learner-visible. Its empty
receiver and absent-hook requirements are explicit profile inputs.
"""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
from dataclasses import dataclass
from pathlib import Path
import struct
from civ6_host.runtime.native.native_application_mirror import decode_scalar
from civ6_host.runtime.native.native_source_cache import load_pinned_json
EVENT_KIND = 827191705
CALLBACK_VA = '0x140151970'
WRITER_VA = '0x140138f60'
RECORD_TYPE, RECORD_SIZE = (196, 96)
SELECTOR_KEY, PLAYER_KEY, RELIGION_KEY = (2716180809, 3606901732, 2717631346)
EXE_SHA256 = 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63'
CORE_SHA256 = 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'
PROOF_SHA256 = '3fdbd69e59aa94c50cb3bc783a01931551f2b13103f9712819b442ab913337fc'
_PROOF = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_religion_founded_event.py')))).resolve().parents[1] / 'evidence/native-religion-founded-notification' / f'{PROOF_SHA256}.json'
_PADDING_POLICY = 'zero-unwritten-record-padding'

def verify_source_evidence() -> None:
    proof = load_pinned_json(_PROOF, PROOF_SHA256)
    captures = proof.get('captures', {})
    if proof.get('schema') != 'civ6rl.native_religion_founded_notification.static.v1' or proof.get('images', {}).get('exe_sha256') != EXE_SHA256 or proof.get('images', {}).get('core_sha256') != CORE_SHA256 or (proof.get('core_emitter', {}).get('event_kind') != '0x314df199') or (proof.get('exe_callback', {}).get('va') != CALLBACK_VA) or (proof.get('ring_record', {}).get('writer_va') != WRITER_VA) or (proof.get('ring_record', {}).get('size') != '0x60') or (proof.get('ring_record', {}).get('type') != '0xc4') or (proof.get('receiver', {}).get('type_row_index') != '0xc4') or (proof.get('receiver', {}).get('event_literal_va') != '0x140fb5938') or (proof.get('receiver', {}).get('handler_va') != '0x1400da930') or (proof.get('admission', {}).get('codec_emitted') is not True) or (proof.get('ring_record', {}).get('record_payload', {}).get('unwritten_native_bytes') != ('+0x4c..+0x4f', '+0x5c..+0x5f')) or (captures.get('core_set_tag3_parameter', {}).get('complete_instruction_bytes_sha256') != '8c5bc7389d2a0f9fc953d6a792f09f3cf9388c0f828d50fa7bbfec7b71bcd37a') or (captures.get('core_set_tag2_parameter', {}).get('complete_instruction_bytes_sha256') != '439ae46d2853a5ceb11123a0e3a9683c160be0968b83c54f62fc6ed534dac387') or (captures.get('exe_normalizer', {}).get('complete_instruction_bytes_sha256') != 'c757d2f0c927f36e058ff5e57350a80beac1db2a89d3940fcb5e89c05545f23e') or (captures.get('exe_event_callback', {}).get('complete_instruction_bytes_sha256') != 'a303a2918d62550dc9daded5c4a406f51c323455288dc0ebcdb47d5da2fdfabb') or (captures.get('exe_ring_writer', {}).get('complete_instruction_bytes_sha256') != 'a4b05c3ca03f5cd3dd0460aaa75fcb92ad817cdd5cf1543ed56e10f8bb49341a'):
        raise RuntimeError('Pinned ReligionFounded callback/normalizer/writer evidence changed')

@dataclass(frozen=True)
class EventFields:
    selector: int
    player_id: int
    religion_index: int

def _validate_fields(fields: EventFields) -> None:
    if not isinstance(fields, EventFields) or any((type(value) is not int or not 0 <= value <= 4294967295 for value in (fields.selector, fields.player_id, fields.religion_index))):
        raise ValueError('ReligionFounded requires three decoded uint32 fields')

def decode_fields(raw_fields: dict[int, bytes]) -> EventFields:
    """Decode the exact Core event map; selector is required but not serialized."""
    verify_source_evidence()
    if not isinstance(raw_fields, dict) or set(raw_fields) != {SELECTOR_KEY, PLAYER_KEY, RELIGION_KEY}:
        raise ValueError('ReligionFounded requires exactly A1E5A149, D6FCF3E4 and A1FBC372')
    fields = EventFields(selector=decode_scalar(raw_fields[SELECTOR_KEY], 3), player_id=decode_scalar(raw_fields[PLAYER_KEY], 2), religion_index=decode_scalar(raw_fields[RELIGION_KEY], 2))
    _validate_fields(fields)
    return fields

def _validate_empty_receiver(state: dict) -> None:
    expected = {'observer_registered', 'state_pointer_nonnull', 'pre_hook', 'post_hook', 'subscriber_count', 'state_flags'}
    if not isinstance(state, dict) or set(state) != expected:
        raise ValueError('ReligionFounded requires the complete C4 receiver-state witness')
    if state['observer_registered'] is not False or state['state_pointer_nonnull'] is not True or state['pre_hook'] is not None or (state['post_hook'] is not None) or (type(state['subscriber_count']) is not int) or (state['subscriber_count'] != 0) or (type(state['state_flags']) is not int) or (state['state_flags'] != 0):
        raise ValueError('ReligionFounded C4 receiver is not in the pinned empty state')

def encode_record(sequence: int, raw_fields: dict[int, bytes], *, normalizer_transform_present: bool, thread_hook_present: bool, writer_metadata_callback_present: bool, padding_policy: str, empty_receiver_state: dict) -> bytes:
    """Encode one 0x60/C4 record under explicit no-transform/no-hook guards.

    Bytes +0x4c..+0x4f and +0x5c..+0x5f are not written by the native writer;
    zeroing them is a diagnostic padding policy, not a native-value claim.
    """
    verify_source_evidence()
    fields = decode_fields(raw_fields)
    if normalizer_transform_present is not False or thread_hook_present is not False or writer_metadata_callback_present is not False:
        raise ValueError('ReligionFounded transform and callback hooks must be explicitly absent')
    if padding_policy != _PADDING_POLICY:
        raise ValueError('ReligionFounded requires explicit zero-unwritten-record-padding policy')
    _validate_empty_receiver(empty_receiver_state)
    if type(sequence) is not int or not 1 <= sequence <= 4294967295:
        raise ValueError('ReligionFounded sequence must be a nonzero uint32')
    staged = bytearray(60)
    struct.pack_into('<II', staged, 0, 4294967295, 4294967295)
    for offset in (8, 16, 24, 32, 40):
        struct.pack_into('<HHI', staged, offset, 65535, 0, 4294967295)
    struct.pack_into('<Q', staged, 48, 0)
    struct.pack_into('<I', staged, 56, 4)
    record = bytearray(RECORD_SIZE)
    struct.pack_into('<IIII', record, 0, RECORD_SIZE, RECORD_TYPE, sequence, 0)
    record[16:76] = staged
    struct.pack_into('<III', record, 80, sequence, fields.player_id, fields.religion_index)
    return bytes(record)
__all__ = ['EVENT_KIND', 'CALLBACK_VA', 'WRITER_VA', 'RECORD_TYPE', 'RECORD_SIZE', 'SELECTOR_KEY', 'PLAYER_KEY', 'RELIGION_KEY', 'EventFields', 'verify_source_evidence', 'decode_fields', 'encode_record']
