"""Narrow diagnostic encoder for EXE event 0x3182BC8E.

Only the observed D6 != 3 path and explicitly empty receiver profile are
represented. The D6 == 3 path performs additional native queries and emits
other records; it is deliberately rejected here.
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
EVENT_KIND, CALLBACK_VA, WRITER_VA = (830651534, '0x140141b00', '0x14012f850')
RECORD_TYPE, RECORD_SIZE = (96, 112)
DESCRIPTOR_KEY, SELECTOR_KEY = (594779970, 2716180809)
D6_KEY, A1FBC_KEY = (3606901732, 2717631346)
NORMALIZED_58_KEY = 955421384
EXE_SHA256 = 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63'
PINNED_EVIDENCE_SHA256 = '23c2afe5ee7772d0220251b903a0a602ea14e9e3608387f5e9b4e23ac8f2437c'
NORMALIZER_EVIDENCE_SHA256 = '5737bd679a0eb0ca70a955e9f1b571e7f4dd79f3d0b8991e6f0ba4bcd8c2e294'
_PROOF = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_event_3182bc8e.py')))).resolve().parents[1] / 'evidence/native-event-3182bc8e' / f'{PINNED_EVIDENCE_SHA256}.json'
_NORMALIZER_PROOF = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_event_3182bc8e.py')))).resolve().parents[1] / 'evidence/native-event-51c84cba' / f'{NORMALIZER_EVIDENCE_SHA256}.json'
_STACK_POLICY = 'headless-zero-uninitialized-stack'
_UNREAD_POLICY = 'zero-unread-empty-receiver-payload'

def verify_source_evidence() -> None:
    proof = load_pinned_json(_PROOF, PINNED_EVIDENCE_SHA256)
    callback = proof['captures']['callback']
    if proof.get('schema') != 'civ6rl.native_event_3182bc8e.static.v1' or proof.get('exe_sha256') != EXE_SHA256 or proof['registration']['kind'] != EVENT_KIND or (proof['registration']['callback_va'] != CALLBACK_VA) or (callback['code_sha256'] != 'a24894edb50dda75e23f69c6137b66348830f7ee6e7020a93ecb33eac0bb8f99') or (proof['captures']['writer_initial']['code_sha256'] != '459b376f43b0477bd45b699f9cc3a0a03d50af8fb5feb607c151979e5ceed340') or (proof['writer_headers']['writer_initial'] != {'size': RECORD_SIZE, 'type': RECORD_TYPE}) or (proof['instruction_guards']['callback'].get('0x140141bde') != 'jne 0x140141e65') or (proof['instruction_guards']['normalizer'].get('0x1401ca430') != 'cmp ecx, 0x38f292c8') or (proof['instruction_guards']['normalizer'].get('0x1401ca455') != 'mov dword ptr [rbp + 0x1f], eax') or (set(proof.get('witnesses', {})) != {'legacy_four_key', 'normalized_58_present'}) or (set(proof['witnesses']['normalized_58_present']['event'].get('fields', {})) != {'0x23739f42', '0x38f292c8', '0xa1e5a149', '0xa1fbc372', '0xd6fcf3e4'}) or ('38F292C8 to +0x58' not in proof['contract']['normalization']) or ('D6!=3 branches to the epilogue' not in proof['contract']['callback']):
        raise RuntimeError('Pinned 3182BC8E source identity or branch contract changed')
    norm = load_pinned_json(_NORMALIZER_PROOF, NORMALIZER_EVIDENCE_SHA256)
    if norm.get('schema') != 'civ6rl.native_event_51c84cba.static.v1' or norm.get('exe_sha256') != EXE_SHA256 or norm['captures']['normalizer']['code_sha256'] != 'c757d2f0c927f36e058ff5e57350a80beac1db2a89d3940fcb5e89c05545f23e':
        raise RuntimeError('Pinned shared-normalizer evidence changed')

@dataclass(frozen=True)
class EventFields:
    selector: int
    descriptor_bytes: bytes
    owner: int
    item_id: int
    d6_value: int
    a1fbc_value: int
    normalized_58: int | None = None

def _validate_fields(fields: EventFields) -> None:
    if not isinstance(fields, EventFields) or type(fields.selector) is not int or fields.selector != 0 or (type(fields.descriptor_bytes) is not bytes) or (len(fields.descriptor_bytes) != 8) or (type(fields.owner) is not int) or (not 0 <= fields.owner <= 65535) or (type(fields.item_id) is not int) or (not 0 <= fields.item_id <= 4294967295) or (struct.unpack_from('<H', fields.descriptor_bytes)[0] != fields.owner) or (struct.unpack_from('<I', fields.descriptor_bytes, 4)[0] != fields.item_id) or (type(fields.d6_value) is not int) or (not 0 <= fields.d6_value <= 4294967295) or (fields.d6_value == 3) or (type(fields.a1fbc_value) is not int) or (not 0 <= fields.a1fbc_value <= 4294967295) or (fields.normalized_58 is not None and (type(fields.normalized_58) is not int or not 0 <= fields.normalized_58 <= 4294967295)):
        raise ValueError('3182BC8E requires the exact witnessed D6!=3 field profile')

def decode_fields(fields: dict[int, bytes], read) -> EventFields:
    """Decode exactly the four observed normalizer inputs; copy the blob safely."""
    verify_source_evidence()
    if not isinstance(fields, dict) or set(fields) not in ({DESCRIPTOR_KEY, SELECTOR_KEY, D6_KEY, A1FBC_KEY}, {DESCRIPTOR_KEY, SELECTOR_KEY, D6_KEY, A1FBC_KEY, NORMALIZED_58_KEY}):
        raise ValueError('3182BC8E requires one of the two exact source-backed key sets')
    selector = decode_scalar(fields[SELECTOR_KEY], 3)
    if selector != 0:
        raise ValueError('3182BC8E selector profile only admits the observed zero value')
    descriptor = copy_eight_byte_variant(fields[DESCRIPTOR_KEY], read, expected_tag=1024)
    owner = struct.unpack_from('<H', descriptor)[0]
    item_id = struct.unpack_from('<I', descriptor, 4)[0]
    result = EventFields(selector, descriptor, owner, item_id, decode_scalar(fields[D6_KEY], 2), decode_scalar(fields[A1FBC_KEY], 2), decode_scalar(fields[NORMALIZED_58_KEY], 2) if NORMALIZED_58_KEY in fields else None)
    _validate_fields(result)
    return result

def encode_record(sequence: int, fields: EventFields, *, normalizer_transform_present: bool=False, thread_hook_present: bool=False, writer_metadata_callback_present: bool=False, padding_policy: str='zero', empty_receiver_profile: bool, undefined_normalized_value_policy: str) -> bytes:
    """Encode the unconditional first type-0x60 record for D6!=3 only.

    Normalized +0x58 is uninitialized by the common normalizer unless another
    key writes it. This explicit empty-receiver diagnostic policy sets it to
    zero only because the empty receiver does not inspect the payload. It is
    not a native default and must not be used as learner state.
    """
    verify_source_evidence()
    _validate_fields(fields)
    if normalizer_transform_present is not False or thread_hook_present is not False or writer_metadata_callback_present is not False:
        raise ValueError('3182BC8E transform/hook/metadata callback path is unsupported')
    if empty_receiver_profile is not True:
        raise ValueError('3182BC8E requires explicit empty receiver profile')
    if padding_policy != 'zero':
        raise ValueError('explicit zero policy required for unwritten callback staging bytes')
    if fields.normalized_58 is None:
        if undefined_normalized_value_policy != _UNREAD_POLICY:
            raise ValueError('legacy four-key profile requires explicit unread-empty policy')
    elif undefined_normalized_value_policy != 'native-initialized-field':
        raise ValueError('five-key profile requires native-initialized-field policy')
    if type(sequence) is not int or not 1 <= sequence <= 4294967295:
        raise ValueError('sequence must be a nonzero uint32')
    return _pack_initial_record(sequence, fields)

def _pack_initial_record(sequence: int, fields: EventFields) -> bytes:
    """Writer 12F850, after a caller has validated its admitted callback branch."""
    record = bytearray(RECORD_SIZE)
    struct.pack_into('<IIII', record, 0, RECORD_SIZE, RECORD_TYPE, sequence, 0)
    struct.pack_into('<IIHHI', record, 16, 4294967295, 4294967295, 65535, 0, 4294967295)
    for offset in (32, 40, 48, 56):
        struct.pack_into('<HHI', record, offset, 65535, 0, 4294967295)
    struct.pack_into('<Q', record, 64, 0)
    struct.pack_into('<I', record, 72, 0)
    struct.pack_into('<I', record, 80, sequence)
    struct.pack_into('<HHI', record, 88, fields.owner, 2, fields.item_id)
    struct.pack_into('<II', record, 96, fields.d6_value, fields.a1fbc_value)
    record[104] = 0
    struct.pack_into('<I', record, 108, 0 if fields.normalized_58 is None else fields.normalized_58)
    return bytes(record)
