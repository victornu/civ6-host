"""Bounded record codecs for three descriptor-only EXE callbacks.

The callback bodies prove a normalized descriptor layout, not the Lua/hash-key
mapping that creates it. This module therefore accepts only an already
normalized 0x20-byte descriptor and does not guess a raw source-field schema.
"""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
from dataclasses import dataclass
from pathlib import Path
import struct
from civ6_host.runtime.native.native_event_99e85ec6 import decode_fields as decode_99_fields
from civ6_host.runtime.native.native_source_cache import load_pinned_json
PROOF_SHA256 = 'cee35d28ae1ea5c9a34d8c00067c09619b887804a093b06340680ae29117b7ea'
NORMALIZER_PROOF_SHA256 = 'bb363e13920412a44fde541151de7cc69047a9706773a7be939dc646ef4e687e'
_PROOF = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_city_descriptor_events.py')))).resolve().parents[1] / 'evidence/native-city-descriptor-candidates' / f'{PROOF_SHA256}.json'
_EXE_SHA256 = 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63'
_NORMALIZER_PROOF = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_city_descriptor_events.py')))).resolve().parents[1] / 'evidence/native-event-99e85ec6' / f'{NORMALIZER_PROOF_SHA256}.json'
_MARKER = 1682424637
_STACK_PADDING_POLICY = 'headless-zero-uninitialized-stack'
SOURCE_SELECTOR_KEY = 2716180809
SOURCE_DESCRIPTOR_KEY = 594779970

@dataclass(frozen=True)
class EventSpec:
    kind: int
    callback_va: str
    writer_va: str
    record_size: int
    record_type: int
    callback_sha256: str
    writer_sha256: str
SPECS = {2075911904: EventSpec(2075911904, '0x140140f40', '0x140130830', 96, 108, '63e32607558086ada194cea608f9c76a9fa3104ee9fe468177fa52c8bdf896b6', '6ce95bb512a13ff97e6a3321375fdad03ccf4627ee2c9ef7cbce2897d9bd2eed'), 689003850: EventSpec(689003850, '0x140141530', '0x140130cc0', 96, 111, 'a5d9fca29a5dac95c743206c72ce767f451c9e2e77afb03fbf325c12ac464273', 'b7da5089ef0e32d3b2a4f2e737fb2ab7103c63e85e1dc57e85d27bd79b7b94ca'), 3727501331: EventSpec(3727501331, '0x140141800', '0x140131090', 96, 114, '6500fd3e9980f29556c982196cd30ec8758bd9d56f0907a0598a20612ffe10b6', '4af5ce7b1bcef4e70691c17200a44cb8daff9084a5a08057c4d98e47e0205856')}

def verify_source_evidence() -> None:
    proof = load_pinned_json(_PROOF, PROOF_SHA256)
    if proof.get('schema') != 'civ6rl.native-city-descriptor-candidates.static.v1' or proof.get('exe_sha256') != _EXE_SHA256:
        raise RuntimeError('Pinned city descriptor evidence identity changed')
    by_kind = {int(row['registration']['kind']): row for row in proof['captures']}
    if set(SPECS) - by_kind.keys():
        raise RuntimeError('Pinned evidence is missing a requested descriptor callback')
    for kind, spec in SPECS.items():
        row = by_kind[kind]
        if row['registration']['callback_va'] != spec.callback_va or row['writer_va'] != spec.writer_va or row['callback']['code_sha256'] != spec.callback_sha256 or (row['writer']['code_sha256'] != spec.writer_sha256) or (row['writer_record_header'] != {'size': spec.record_size, 'type': spec.record_type}) or (row['direct_call_targets'] != ('call qword ptr [rax + 8]', f'call {int(spec.writer_va, 16):#x}', 'call 0x1409898c0')):
            raise RuntimeError(f'Pinned source mismatch for kind {kind:#x}')
    normalizer = load_pinned_json(_NORMALIZER_PROOF, NORMALIZER_PROOF_SHA256)
    normalizer_guards = normalizer['instruction_guards']['normalizer']
    if normalizer.get('schema') != 'civ6rl.native_event_99e85ec6.static.v1' or normalizer['exe_sha256'] != _EXE_SHA256 or normalizer['captures']['normalizer']['code_sha256'] != 'c757d2f0c927f36e058ff5e57350a80beac1db2a89d3940fcb5e89c05545f23e' or (normalizer['common_normalizer_pin'] != '5737bd679a0eb0ca70a955e9f1b571e7f4dd79f3d0b8991e6f0ba4bcd8c2e294') or (normalizer_guards.get('0x1401ca420') != 'cmp ecx, 0x23739f42') or (normalizer_guards.get('0x1401ca34a') != 'mov word ptr [rbp - 0x1f], ax') or (normalizer_guards.get('0x1401ca472') != 'mov word ptr [rbp - 0x21], cx') or (normalizer_guards.get('0x1401ca476') != 'mov dword ptr [rbp - 0x1d], edx'):
        raise RuntimeError('Pinned shared normalizer mapping changed')

@dataclass(frozen=True)
class NormalizedDescriptor:
    """The callback's checked marker plus fields at +0x18/+0x1A/+0x1C."""
    descriptor_word: int
    descriptor_type: int
    descriptor_dword: int

def decode_normalized_descriptor(raw: bytes) -> NormalizedDescriptor:
    """Read only the exact normalized fields used by each callback.

    No assertion is made about ignored bytes in the 0x20-byte caller object.
    Raw Lua keys/tags use decode_event_fields; this function accepts only the
    normalizer's exact resulting object.
    """
    verify_source_evidence()
    if type(raw) is not bytes or len(raw) != 32:
        raise ValueError('normalized descriptor must be exactly 0x20 bytes')
    marker = struct.unpack_from('<I', raw, 0)[0]
    if marker != _MARKER:
        raise ValueError('unexpected normalized descriptor marker')
    return NormalizedDescriptor(descriptor_word=struct.unpack_from('<H', raw, 24)[0], descriptor_type=struct.unpack_from('<H', raw, 26)[0], descriptor_dword=struct.unpack_from('<I', raw, 28)[0])

def decode_event_fields(kind: int, fields: dict, read) -> NormalizedDescriptor:
    """Decode the only source-backed raw shape shared by these three kinds.

    The pinned 99E85EC6 normalizer proof establishes the shared generic
    transform: A1E5A149/tag3 is a scalar and 23739F42/tag0x400 is an 8-byte
    blob. At 0x1401CA420 it compares the key 23739F42; the matched branch
    reads blob WORD0 and DWORD4, stores them at normalized +0x18/+0x1C, and
    initializes normalized WORD+0x1A to2. Each admitted callback independently
    checks marker 0x6447C33D and reads exactly those normalized offsets. The
    scalar's value is validated by the shared parser and then discarded here;
    it does not select a thread. This API rejects every other kind/key/tag
    profile, including 0x23739F1F.
    """
    verify_source_evidence()
    if type(kind) is not int or kind not in SPECS:
        raise ValueError('raw source mapping is admitted only for the three pinned kinds')
    if type(fields) is not dict or set(fields) != {SOURCE_SELECTOR_KEY, SOURCE_DESCRIPTOR_KEY}:
        raise ValueError('city descriptor mapping requires exactly keys A1E5A149 and 23739F42')
    decoded = decode_99_fields(fields, read)
    result = NormalizedDescriptor(decoded.owner, 2, decoded.item_id)
    _validate_descriptor(result)
    return result

def _validate_descriptor(value: NormalizedDescriptor) -> None:
    if not isinstance(value, NormalizedDescriptor) or type(value.descriptor_word) is not int or (not 0 <= value.descriptor_word <= 65535) or (type(value.descriptor_type) is not int) or (not 0 <= value.descriptor_type <= 65535) or (type(value.descriptor_dword) is not int) or (not 0 <= value.descriptor_dword <= 4294967295):
        raise ValueError('invalid normalized descriptor fields')

def encode_record(kind: int, sequence: int, descriptor: NormalizedDescriptor, *, normalizer_transform_present: bool, per_thread_hook_present: bool, writer_metadata_callback_present: bool, padding_policy: str) -> bytes:
    """Encode one source-bounded record under the explicit no-hook profile.

    The callback copies a 16-byte local object into record+0x50, then its
    writer overwrites the first DWORD with the queue sequence. The local
    DWORD at +4 has no source initialization, so zeroing it is an explicit
    diagnostic policy. Metadata gap +0x4C..+0x4F is in the writer's zero-filled
    newly reserved record extent.
    """
    verify_source_evidence()
    spec = SPECS.get(kind) if type(kind) is int else None
    if spec is None:
        raise ValueError('unsupported descriptor event kind')
    _validate_descriptor(descriptor)
    if normalizer_transform_present is not False or per_thread_hook_present is not False or writer_metadata_callback_present is not False:
        raise ValueError('EXE transform, per-thread hook, or writer callback is unsupported')
    if type(sequence) is not int or not 1 <= sequence <= 4294967295:
        raise ValueError('sequence must be a nonzero uint32')
    if padding_policy != _STACK_PADDING_POLICY:
        raise ValueError('explicit zero policy required for uninitialized stack bytes')
    record = bytearray(spec.record_size)
    struct.pack_into('<IIII', record, 0, spec.record_size, spec.record_type, sequence, 0)
    struct.pack_into('<II', record, 16, 4294967295, 4294967295)
    for offset in (24, 32, 40, 48, 56):
        struct.pack_into('<HHI', record, offset, 65535, 0, 4294967295)
    struct.pack_into('<IIHHI', record, 80, sequence, 0, descriptor.descriptor_word, descriptor.descriptor_type, descriptor.descriptor_dword)
    return bytes(record)
