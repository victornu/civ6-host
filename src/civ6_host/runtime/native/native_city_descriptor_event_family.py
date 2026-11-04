"""Source-bounded codecs for three city-descriptor EXE notification records.

This module only builds records for the explicit empty-receiver profile. It
does not add event dispatch, execute a DLL, or assign semantics to descriptor
fields beyond their source offsets.
"""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
from dataclasses import dataclass
from pathlib import Path
import struct
from civ6_host.runtime.native.native_event_99e85ec6 import decode_fields as decode_normalized_source_fields
from civ6_host.runtime.native.native_source_cache import load_pinned_json
PROOF_SHA256 = 'da7f0481304e7efb27b0d5d164593073ec9a733a34050a8cc3e4dc6f95369b2b'
_PROOF = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_city_descriptor_event_family.py')))).resolve().parents[1] / 'evidence/native-city-descriptor-event-family' / f'{PROOF_SHA256}.json'
EXE_SHA256 = 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63'
NORMALIZER_PROOF_SHA256 = 'bb363e13920412a44fde541151de7cc69047a9706773a7be939dc646ef4e687e'
_MARKER = 1682424637
_PADDING_POLICY = 'headless-zero-uninitialized-stack-and-record-tail'
_EMPTY_PROFILE = 'empty-no-observer-zero-subscriber-v1'
SELECTOR_KEY = 2716180809
DESCRIPTOR_KEY = 594779970

@dataclass(frozen=True)
class EventSpec:
    kind: int
    event_name: str
    callback_va: str
    writer_va: str
    receiver_setup_va: str
    receiver_handler_va: str
    record_type: int
    record_size: int
    callback_sha256: str
    writer_sha256: str
SPECS = {3565292211: EventSpec(3565292211, 'GameCoreEvent::CityNameChanged', '0x140141750', '0x14012efe0', '0x1400cc6a0', '0x1400d8110', 89, 96, 'fa7bcc7a9fe0bd868b51983546632dc87dfeef295ceecc94670deb274994b0c8', '327c4da439559006a1f7b50f3b4d3806f41be07a8cac77b0ebcc74397c5abfb6'), 821819602: EventSpec(821819602, 'GameCoreEvent::CityPropertyChanged', '0x140142020', '0x14012f120', '0x1400cc760', '0x1400d8170', 90, 96, '2ef7e265fb2d65e7a67c80ab5c991c6d13aad7ebc47fc5c58b2f747046ab51ba', '4444b06e632ee5da5a834f9c57fc2bdb830f1ab4d4e0fbe309e5da1ce58fae07'), 1408378902: EventSpec(1408378902, 'GameCoreEvent::CityRemovedFromMap', '0x140142230', '0x14012f5c0', '0x1400cc9a0', '0x1400d8290', 93, 96, '159579d2ff8bd6f6133abd2ab3c176f62e91552ecc042a2cf15d714c2ea146d3', '8caccdd5d3dc2881767cd918e8abecff19c56fefc3835b98a88d34a97529b4d2')}

@dataclass(frozen=True)
class Descriptor:
    owner: int
    descriptor_type: int
    identifier: int
    source_bytes: bytes

def verify_source_evidence() -> None:
    proof = load_pinned_json(_PROOF, PROOF_SHA256)
    if proof.get('schema') != 'civ6rl.native_city_descriptor_event_family.static.v1' or proof.get('exe_sha256') != EXE_SHA256 or proof.get('source_pins', {}).get('normalizer_proof_sha256') != NORMALIZER_PROOF_SHA256 or (proof.get('comparison_method', '') == ''):
        raise RuntimeError('Pinned city descriptor family identity changed')
    rows = {int(row['kind'], 16): row for row in proof.get('receiver_family', [])}
    if set(rows) != set(SPECS):
        raise RuntimeError('Pinned city descriptor family is incomplete')
    for kind, spec in SPECS.items():
        row = rows[kind]
        receiver = row['receiver']
        writer_texts = [ins['text'] for fragment in row.get('writer_full_body', {}).get('fragments', []) for ins in fragment.get('instructions', [])]
        try:
            copy_index = writer_texts.index('movups xmmword ptr [rax], xmm0')
        except ValueError as exc:
            raise RuntimeError('Pinned writer lacks the 16-byte payload copy') from exc
        if receiver.get('event_name') != spec.event_name or row.get('callback_va') != spec.callback_va or row.get('writer_va') != spec.writer_va or (int(row.get('record_type', '0'), 16) != spec.record_type) or (row.get('record_size') != spec.record_size) or (row.get('callback_code_sha256') != spec.callback_sha256) or (row.get('writer_code_sha256') != spec.writer_sha256) or (receiver.get('event_name') != spec.event_name) or (receiver.get('setup_va') != spec.receiver_setup_va) or (receiver.get('handler_va') != spec.receiver_handler_va) or (receiver.get('empty_state', {}).get('subscriber_count_state_plus_0x20') != 0) or (receiver.get('empty_state', {}).get('pre_hook_plus_0') is not None) or (receiver.get('empty_state', {}).get('post_hook_plus_8') is not None) or ('mov dword ptr [rax], edi' not in writer_texts[copy_index + 1:]) or ('overwrites record+0x50 with sequence' not in row.get('record_payload', '')):
            raise RuntimeError(f'Pinned source/receiver mismatch for {kind:#010x}')
    comparison = proof.get('body_comparisons', {})
    if set(comparison) != {'0x30fbf8d2', '0x53f22816'}:
        raise RuntimeError('Pinned instruction comparison is incomplete')
    for pair in comparison.values():
        if any((not item.get('normalized_instructions_equal') or not item.get('all_other_rip_targets_equal') for item in pair.values())):
            raise RuntimeError('Pinned family has an unreviewed instruction/global mismatch')
        cb_diffs = pair['callback']['rip_target_differences']
        if [d['index'] for d in cb_diffs] != [12] or pair['writer']['rip_target_differences']:
            raise RuntimeError('Unexpected hook-table or writer global difference')
    empty = proof.get('common_empty_dispatch', {})
    contract = empty.get('empty_branch_contract', {})
    if empty.get('proof_sha256') != '6af47df250e68d10902557a7ebc89c587beb8cd77c5630f3e189b6757bb4b7ff' or 'not dereferenced' not in contract.get('payload_reads', '') or 'count at state+0x20' not in contract.get('subscriber_loop', '') or ('count is zero' not in contract.get('subscriber_loop', '')) or (empty.get('use_limit', '').count('null') < 1):
        raise RuntimeError('Pinned empty receiver path no longer proves the payload skip')
    decode_normalized_source_fields

def decode_fields(kind: int, fields: dict[int, bytes], read) -> Descriptor:
    """Apply the shared, pinned raw shape and validate the callback descriptor."""
    verify_source_evidence()
    if type(kind) is not int or kind not in SPECS:
        raise ValueError('Unsupported city descriptor event kind')
    decoded = decode_normalized_source_fields(fields, read)
    descriptor = Descriptor(decoded.owner, 2, decoded.item_id, struct.pack('<HHI', decoded.owner, 2, decoded.item_id))
    _validate_descriptor(descriptor)
    return descriptor

def decode_normalized_descriptor(raw: bytes) -> Descriptor:
    """Decode the exact 0x20 normalized object consumed by the three callbacks."""
    verify_source_evidence()
    if type(raw) is not bytes or len(raw) != 32:
        raise ValueError('Normalized descriptor must be exactly 0x20 bytes')
    if struct.unpack_from('<I', raw, 0)[0] != _MARKER:
        raise ValueError('Unexpected normalized descriptor marker')
    owner = struct.unpack_from('<H', raw, 24)[0]
    descriptor_type = struct.unpack_from('<H', raw, 26)[0]
    identifier = struct.unpack_from('<I', raw, 28)[0]
    descriptor = Descriptor(owner, descriptor_type, identifier, struct.pack('<HHI', owner, descriptor_type, identifier))
    _validate_descriptor(descriptor)
    return descriptor

def _validate_descriptor(descriptor: Descriptor) -> None:
    if not isinstance(descriptor, Descriptor) or type(descriptor.owner) is not int or (not 0 <= descriptor.owner <= 65535) or (type(descriptor.descriptor_type) is not int) or (descriptor.descriptor_type != 2) or (type(descriptor.identifier) is not int) or (not 0 <= descriptor.identifier <= 4294967295) or (type(descriptor.source_bytes) is not bytes) or (len(descriptor.source_bytes) != 8) or (descriptor.source_bytes != struct.pack('<HHI', descriptor.owner, 2, descriptor.identifier)):
        raise ValueError('Unverified city descriptor fields')

def validate_profile(*, empty_receiver_profile: str, observer_registered: bool, receiver_state_pointer_nonnull: bool, receiver_pre_hook_present: bool, receiver_post_hook_present: bool, receiver_subscriber_count: int, receiver_state_flags: int, per_thread_hook_present: bool, writer_metadata_callback_present: bool, normalizer_transform_present: bool, padding_policy: str) -> None:
    if empty_receiver_profile != _EMPTY_PROFILE:
        raise ValueError('Only the explicit empty no-observer receiver profile is supported')
    if observer_registered is not False or receiver_state_pointer_nonnull is not True:
        raise ValueError('Observer or missing native subscriber state requires a different path')
    if receiver_pre_hook_present is not False or receiver_post_hook_present is not False or type(receiver_subscriber_count) is not int or (receiver_subscriber_count != 0) or (type(receiver_state_flags) is not int) or receiver_state_flags & 3:
        raise ValueError('Receiver is not in the source-proven empty dispatch state')
    if per_thread_hook_present is not False or writer_metadata_callback_present is not False:
        raise ValueError('Optional producer callbacks are not modeled')
    if normalizer_transform_present is not False:
        raise ValueError('Transformed descriptors are not modeled by this raw-field codec')
    if padding_policy != _PADDING_POLICY:
        raise ValueError('Explicit stack and record-tail zeroing policy is required')

def encode_record_with_fields(kind: int, sequence: int, raw_fields: dict[int, bytes], read, *, empty_receiver_profile: str, observer_registered: bool, receiver_state_pointer_nonnull: bool, receiver_pre_hook_present: bool, receiver_post_hook_present: bool, receiver_subscriber_count: int, receiver_state_flags: int, per_thread_hook_present: bool, writer_metadata_callback_present: bool, normalizer_transform_present: bool, padding_policy: str) -> tuple[bytes, Descriptor]:
    """Decode raw fields once and create the exact writer record layout."""
    verify_source_evidence()
    spec = SPECS.get(kind) if type(kind) is int else None
    if spec is None:
        raise ValueError('Unsupported city descriptor event kind')
    if type(sequence) is not int or not 1 <= sequence <= 4294967295:
        raise ValueError('Sequence must be a nonzero uint32')
    validate_profile(empty_receiver_profile=empty_receiver_profile, observer_registered=observer_registered, receiver_state_pointer_nonnull=receiver_state_pointer_nonnull, receiver_pre_hook_present=receiver_pre_hook_present, receiver_post_hook_present=receiver_post_hook_present, receiver_subscriber_count=receiver_subscriber_count, receiver_state_flags=receiver_state_flags, per_thread_hook_present=per_thread_hook_present, writer_metadata_callback_present=writer_metadata_callback_present, normalizer_transform_present=normalizer_transform_present, padding_policy=padding_policy)
    descriptor = decode_fields(kind, raw_fields, read)
    return (_encode_record(spec, sequence, descriptor), descriptor)

def encode_record(kind: int, sequence: int, raw_fields: dict[int, bytes], read, **profile) -> bytes:
    record, _ = encode_record_with_fields(kind, sequence, raw_fields, read, **profile)
    return record

def _encode_record(spec: EventSpec, sequence: int, descriptor: Descriptor) -> bytes:
    _validate_descriptor(descriptor)
    record = bytearray(spec.record_size)
    struct.pack_into('<IIII', record, 0, spec.record_size, spec.record_type, sequence, 0)
    struct.pack_into('<IIHHI', record, 16, 4294967295, 4294967295, 65535, 0, 4294967295)
    for offset in (32, 40, 48, 56):
        struct.pack_into('<HHI', record, offset, 65535, 0, 4294967295)
    struct.pack_into('<Q', record, 64, 0)
    struct.pack_into('<I', record, 72, 0)
    struct.pack_into('<II', record, 80, sequence, 0)
    record[88:96] = descriptor.source_bytes
    return bytes(record)
__all__ = ['Descriptor', 'EventSpec', 'SPECS', 'decode_fields', 'decode_normalized_descriptor', 'encode_record', 'encode_record_with_fields', 'validate_profile', 'verify_source_evidence']
