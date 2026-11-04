"""Source-checked same-queue record encoder for the 36C9B2B4 event pair.

The raw-field producer and host adapter live in native_36c9b2b4.py and
native_host_events.py. This codec only packs the captured metadata and
payload bytes after the required effects and native lookups have completed.
"""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import hashlib
import json
from pathlib import Path
from typing import Mapping
PROOF_SHA256 = 'fd13cd7420166e587746f062eec5fac1f96fdb52037b74aadfb9503f92bcc0cd'
QUEUE_RESOLUTION_SHA256 = 'b1cd3ac286354156f3498f4a35a0e205fc729af7402197655218cc3298ed074b'
PROOF_PATH = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_36c9b2b4_pair_codec.py')))).resolve().parents[1] / 'evidence' / 'native-36c9b2b4-receiver-pair' / f'{PROOF_SHA256}.json'
QUEUE_RESOLUTION_PATH = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_36c9b2b4_pair_codec.py')))).resolve().parents[1] / 'evidence' / 'native-36c9b2b4-queue-resolution' / f'{QUEUE_RESOLUTION_SHA256}.json'
ZERO_PADDING_POLICY = 'zero-unread-empty-receiver-payload'
EMPTY_RECEIVER_STATE = {'observer_registered': False, 'state_pointer_nonnull': True, 'pre_hook': None, 'post_hook': None, 'subscriber_count': 0, 'state_flags': 0}

def verify_source_evidence() -> Mapping:
    raw = _resolve_resource_path(PROOF_PATH).read_bytes()
    if hashlib.sha256(raw).hexdigest() != PROOF_SHA256:
        raise RuntimeError('36C9B2B4 receiver-pair proof hash changed')
    doc = json.loads(raw)
    if doc.get('schema') != 'civ6rl.native_event_36c9b2b4_receiver_pair.static.v1' or doc.get('image', {}).get('sha256') != 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63' or doc.get('receiver_initializer', {}).get('direct_setup_calls') != 325 or (set(doc.get('receiver_initializer', {}).get('rows', {})) != {'0x78', '0x79'}) or (doc.get('decision', {}).get('safe_event_admission') is not False):
        raise RuntimeError('36C9B2B4 source contract changed or admitted unexpectedly')
    queue_raw = _resolve_resource_path(QUEUE_RESOLUTION_PATH).read_bytes()
    if hashlib.sha256(queue_raw).hexdigest() != QUEUE_RESOLUTION_SHA256:
        raise RuntimeError('36C9B2B4 queue-resolution proof hash changed')
    queue = json.loads(queue_raw)
    cb = queue.get('callback_queue_arguments', {})
    calls = cb.get('ordered_calls', [])
    if queue.get('schema') != 'civ6rl.native_36c9b2b4_queue_resolution.static.v1' or cb.get('queue_base') != '0x1412C6820 + index*0x90' or cb.get('lock_member') != '0x1412C6870 + index*0x90 = queue_base + 0x50' or (len(calls) != 2) or ([row.get('type') for row in calls] != ['0x78', '0x79']) or any(('same queue_base' not in row.get('this_register', '') for row in calls[1:])) or (queue.get('consumer', {}).get('drain_va') != '0x14006e050'):
        raise RuntimeError('36C9B2B4 shared-queue/order proof changed')
    return doc

def _u32(value: object, label: str) -> int:
    if type(value) is not int or not 0 <= value <= 4294967295:
        raise ValueError(f'{label} must be a uint32')
    return value

def _bytes(value: object, size: int, label: str) -> bytes:
    if not isinstance(value, bytes) or len(value) != size:
        raise ValueError(f'{label} must be exactly {size} bytes')
    return value

def _is_exact_empty_receiver(value: object) -> bool:
    if type(value) is not dict or set(value) != set(EMPTY_RECEIVER_STATE):
        return False
    return type(value['observer_registered']) is bool and value['observer_registered'] is False and (type(value['state_pointer_nonnull']) is bool) and (value['state_pointer_nonnull'] is True) and (value['pre_hook'] is None) and (value['post_hook'] is None) and (type(value['subscriber_count']) is int) and (value['subscriber_count'] == 0) and (type(value['state_flags']) is int) and (value['state_flags'] == 0)

def encode_pair(*, sequence_78: int, metadata_payload: bytes, payload_78: bytes, payload_79: bytes, normalizer_transform_present: bool, per_thread_hook_present: bool, writer_metadata_callback_present: bool, entity_listener_count: int, empty_receiver_state_78: Mapping, empty_receiver_state_79: Mapping, padding_policy: str) -> tuple[bytes, bytes]:
    """Encode the two 0x70 record envelopes from caller-supplied native bytes.

    Both writers append to one queue and use its shared sequence counter.
    This structural draft therefore encodes the second sequence as the first
    plus one. Unwritten gaps/tails are zeroed only under the explicit,
    source-matched empty-receiver policy.
    """
    verify_source_evidence()
    sequence_78 = _u32(sequence_78, 'sequence_78')
    if sequence_78 == 4294967295:
        raise ValueError('the second same-queue sequence would overflow uint32')
    sequence_79 = sequence_78 + 1
    metadata_payload = _bytes(metadata_payload, 60, 'metadata_payload')
    payload_78 = _bytes(payload_78, 20, 'payload_78')
    payload_79 = _bytes(payload_79, 20, 'payload_79')
    if type(normalizer_transform_present) is not bool or normalizer_transform_present:
        raise ValueError('normalizer transform is unsupported')
    if type(per_thread_hook_present) is not bool or per_thread_hook_present:
        raise ValueError('per-thread hook must be absent')
    if type(writer_metadata_callback_present) is not bool or writer_metadata_callback_present:
        raise ValueError('writer metadata callback must be absent')
    if type(entity_listener_count) is not int or entity_listener_count != 0:
        raise ValueError("only the host's explicit zero-listener profile is supported")
    if padding_policy != ZERO_PADDING_POLICY:
        raise ValueError('unwritten record bytes require the explicit empty-profile policy')
    if not _is_exact_empty_receiver(empty_receiver_state_78):
        raise ValueError('type 0x78 receiver is not the exact empty state')
    if not _is_exact_empty_receiver(empty_receiver_state_79):
        raise ValueError('type 0x79 receiver is not the exact empty state')

    def one(record_type: int, sequence: int, payload: bytes) -> bytes:
        record = bytearray(112)
        record[0:4] = 112 .to_bytes(4, 'little')
        record[4:8] = record_type.to_bytes(4, 'little')
        record[8:12] = sequence.to_bytes(4, 'little')
        record[12:16] = b'\x00' * 4
        record[16:76] = metadata_payload
        record[80:100] = payload
        record[80:84] = sequence.to_bytes(4, 'little')
        record[68:72] = b'\x00' * 4
        return bytes(record)
    return (one(120, sequence_78, payload_78), one(121, sequence_79, payload_79))
