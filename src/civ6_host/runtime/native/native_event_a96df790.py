"""Source-bounded UnitAbilityGained producer for an empty EXE receiver.

The callback never initializes two DWORDs in its copied stack payload. This
adapter zeroes those unread bytes only under the explicit empty-row profile;
it does not represent them as native values or synthesize gameplay effects.
"""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
from dataclasses import dataclass
from pathlib import Path
import struct
from civ6_host.runtime.native import native_event_a60328c5 as _analog
from civ6_host.runtime.native.native_application_mirror import decode_scalar
from civ6_host.runtime.native.native_host_events import copy_eight_byte_variant
from civ6_host.runtime.native.native_source_cache import load_pinned_json
PINNED_EVIDENCE_SHA256 = 'db99eba76e6fd2cc1f1c455f688f71531dac8c5895100fb62c4d0b33fcc02710'
_PROOF = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_event_a96df790.py')))).resolve().parents[1] / 'evidence/native-event-a96df790' / f'{PINNED_EVIDENCE_SHA256}.json'
EVENT_KIND = 2842556304
RECORD_TYPE = 65
RECORD_SIZE = 112
SELECTOR_KEY = 2716180809
VALUE_KEY = 3606901732
UNIT_KEY = 4032072631
EMPTY_RECEIVER_PROFILE = 'unit-ability-gained-row-41-empty'
PADDING_POLICY = 'zero-unread-empty-receiver-payload'

def verify_source_evidence():
    proof = load_pinned_json(_PROOF, PINNED_EVIDENCE_SHA256)
    if proof.get('schema') != 'civ6rl.native_event_a96df790.static.v1' or proof.get('exe_sha256') != 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63' or proof.get('core_sha256') != 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3' or (proof.get('targets', {}).get('callback') != '0x1401546b0') or (proof.get('targets', {}).get('writer') != '0x14012c300'):
        raise RuntimeError('A96DF790 source identity changed')
    hashes = {'callback': 'a26c9cf3c06d897bdeafe2efc7548b94bec87220c6cbc8692218e48f54a2219e', 'writer': '06edf1490046d44bc5d7530d0a04e0006b70a7efd8f144a4bb8134bfe3455e0b', 'normalizer': 'c757d2f0c927f36e058ff5e57350a80beac1db2a89d3940fcb5e89c05545f23e', 'normalizer_dispatch': '5d0c3c7557f18ad896d84bb83b4c43b6fd47bbee1b25e73967ee78f1fe583d89', 'receiver_setup': 'ddbf666b05a4760eec72e1de6728d788cc1224f61934af45b239106b52619a92', 'handler': '655d3f02a1446417dae7aa9e9104e96960b458ce2f66f29eda2546518e3dee8e', 'subscriber_dispatch': '326ad0582020365181be9ed3b3e0f595e1bf834ef24f5afdf167d9ae56292bca'}
    for name, digest in hashes.items():
        if proof.get('captures', {}).get(name, {}).get('code_sha256') != digest:
            raise RuntimeError(f'A96DF790 {name} source body changed')
    receiver = proof['receiver']
    if receiver.get('record_type') != RECORD_TYPE or receiver.get('record_size') != RECORD_SIZE or receiver.get('event_name') != 'GameCoreEvent::UnitAbilityGained' or (receiver.get('row_va') != '0x1412c74e0') or (receiver.get('handler_va') != '0x1400d7810') or (proof['analog']['sha256'] != _analog.PINNED_EVIDENCE_SHA256):
        raise RuntimeError('A96DF790 receiver or reusable writer identity changed')
    return proof

@dataclass(frozen=True)
class EventFields:
    selector: int
    value: int
    owner: int
    unit_id: int
    normalized_unit_type: int = 1

def _validate_fields(fields):
    if not isinstance(fields, EventFields):
        raise ValueError('Expected decoded A96DF790 fields')
    for value in (fields.selector, fields.value, fields.unit_id):
        if type(value) is not int or not 0 <= value <= 4294967295:
            raise ValueError('A96DF790 scalar and unit id must be raw DWORDs')
    if type(fields.owner) is not int or not 0 <= fields.owner <= 65535:
        raise ValueError('A96DF790 owner must be a WORD')
    if type(fields.normalized_unit_type) is not int or fields.normalized_unit_type != 1:
        raise ValueError('A96DF790 normalizer supplies unit type 1')

def decode_fields(raw_fields, read):
    """Copy the exact witnessed envelope while its borrowed descriptor is live."""
    verify_source_evidence()
    if type(raw_fields) is not dict or set(raw_fields) != {SELECTOR_KEY, VALUE_KEY, UNIT_KEY} or any((type(cell) is not bytes or len(cell) != 24 for cell in raw_fields.values())):
        raise ValueError('Unverified A96DF790 field envelope')
    selector = decode_scalar(raw_fields[SELECTOR_KEY], 3)
    value = decode_scalar(raw_fields[VALUE_KEY], 2)
    blob = copy_eight_byte_variant(raw_fields[UNIT_KEY], read, expected_tag=1024)
    owner, _raw_type, unit_id = struct.unpack('<HHI', blob)
    fields = EventFields(selector, value, owner, unit_id)
    _validate_fields(fields)
    return fields

def _validate_empty_receiver(state):
    expected = {'profile': EMPTY_RECEIVER_PROFILE, 'record_type': RECORD_TYPE, 'event_name': 'GameCoreEvent::UnitAbilityGained', 'pre_hook': None, 'post_hook': None, 'subscriber_count': 0, 'subscriber_list_empty': True, 'deferred_flag': 0}
    if type(state) is not dict or state != expected or any((type(state[key]) is not type(value) for key, value in expected.items())):
        raise ValueError('A96DF790 requires the exact initialized-empty 0x41 receiver profile')

def encode_record(sequence, fields, *, normalizer_transform_present, per_thread_hook_present, writer_metadata_callback_present, empty_receiver_state, padding_policy):
    """Encode one record; dispatcher owns pre-read guards and queue reservation."""
    verify_source_evidence()
    _validate_fields(fields)
    if type(sequence) is not int or not 1 <= sequence <= 4294967295:
        raise ValueError('A96DF790 sequence must be a nonzero DWORD')
    if normalizer_transform_present is not False or per_thread_hook_present is not False or writer_metadata_callback_present is not False:
        raise ValueError('A96DF790 optional callback service is outside the admitted profile')
    _validate_empty_receiver(empty_receiver_state)
    if type(padding_policy) is not str or padding_policy != PADDING_POLICY:
        raise ValueError('A96DF790 requires explicit zeroing of unread empty-receiver payload')
    record = bytearray(_analog.encode_record(sequence, _analog.EventFields(fields.selector, fields.value, 0, fields.owner, fields.unit_id), normalizer_transform_present=False, per_thread_hook_present=False, writer_metadata_callback_present=False, padding_policy='headless-zero-uninitialized-stack'))
    struct.pack_into('<I', record, 4, RECORD_TYPE)
    return bytes(record)
