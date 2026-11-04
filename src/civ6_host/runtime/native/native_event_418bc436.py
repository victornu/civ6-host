"""Source-bounded codec for EXE event kind 0x418BC436 (record 0x69)."""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
from dataclasses import dataclass
from pathlib import Path
import struct
from civ6_host.runtime.native.native_application_mirror import decode_scalar
from civ6_host.runtime.native.native_event_51c84cba import DESCRIPTOR_KEY
from civ6_host.runtime.native.native_event_51c84cba import SELECTOR_KEY
from civ6_host.runtime.native.native_host_events import copy_eight_byte_variant
from civ6_host.runtime.native.native_source_cache import load_pinned_json
EVENT_KIND, CALLBACK_VA, WRITER_VA = (1099678774, '0x140141690', '0x140130440')
RECORD_TYPE, RECORD_SIZE = (105, 112)
POSITION_KEY, VALUE_KEY = (2353434172, 3606901732)
OPTIONAL_KEY = 2717631346
CITY_CANDIDATE_PROOF_SHA256 = 'cee35d28ae1ea5c9a34d8c00067c09619b887804a093b06340680ae29117b7ea'
NORMALIZER_PROOF_SHA256 = '5737bd679a0eb0ca70a955e9f1b571e7f4dd79f3d0b8991e6f0ba4bcd8c2e294'
POSITION_PROOF_SHA256 = 'd579004ffcb9cebad2235aebd41f430a24bbbff2fca66386c90e9a08d032cc11'
NORMALIZATION_PROOF_SHA256 = 'f1f895339ab39d0e7819538da3eddf8d725575f059c9ef360ccd4dd3a44c7ad2'
MISSING_VALUE_PROOF_SHA256 = 'a706f90ece9b2202a740f228ca01c38458d7b85b07cf84a2a81abda5211f0c7e'
EXE_SHA256 = 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63'
_CITY_PROOF = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_event_418bc436.py')))).resolve().parents[1] / 'evidence/native-city-descriptor-candidates' / f'{CITY_CANDIDATE_PROOF_SHA256}.json'
_NORMALIZER_PROOF = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_event_418bc436.py')))).resolve().parents[1] / 'evidence/native-event-51c84cba' / f'{NORMALIZER_PROOF_SHA256}.json'
_POSITION_PROOF = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_event_418bc436.py')))).resolve().parents[1] / 'evidence/native-event-f4fe1b62' / f'{POSITION_PROOF_SHA256}.json'
_NORMALIZATION_PROOF = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_event_418bc436.py')))).resolve().parents[1] / 'evidence/native-event-418bc436-five-fields' / f'{NORMALIZATION_PROOF_SHA256}.json'
_MISSING_VALUE_PROOF = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_event_418bc436.py')))).resolve().parents[1] / 'evidence/native-event-418bc436-missing-value' / f'{MISSING_VALUE_PROOF_SHA256}.json'
_STACK_POLICY = 'headless-zero-uninitialized-stack'

def verify_source_evidence() -> None:
    city = load_pinned_json(_CITY_PROOF, CITY_CANDIDATE_PROOF_SHA256)
    row = next((item for item in city['captures'] if item['registration']['kind'] == EVENT_KIND), None)
    if city.get('schema') != 'civ6rl.native-city-descriptor-candidates.static.v1' or city.get('exe_sha256') != EXE_SHA256 or row is None or (row['registration']['callback_va'] != CALLBACK_VA) or (row['writer_va'] != WRITER_VA) or (row['callback']['code_sha256'] != '0780281a22b1c94a9f5aa2acecb939c3ea014dde5fe7f1c5c27f98d74beec750') or (row['writer']['code_sha256'] != 'b019c7c8bc61edd1dd0d4fdf10841ded358a7307c07a63baabde8af5f297c6ec') or (row['writer_record_header'] != {'size': RECORD_SIZE, 'type': RECORD_TYPE}):
        raise RuntimeError('Pinned 418BC436 callback/writer identity changed')
    instructions = tuple((i['text'] for f in row['callback']['fragments'] for i in f['instructions']))
    required = ('mov rax, qword ptr [rdx + 0x48]', 'mov eax, dword ptr [rdx + 4]', 'mov eax, dword ptr [rdx + 0x50]', 'mov dword ptr [rsp + 0x20], 0', 'call 0x140130440')
    if any((text not in instructions for text in required)):
        raise RuntimeError('418BC436 callback field mapping changed')
    normalizer = load_pinned_json(_NORMALIZER_PROOF, NORMALIZER_PROOF_SHA256)
    if normalizer.get('schema') != 'civ6rl.native_event_51c84cba.static.v1' or normalizer.get('exe_sha256') != EXE_SHA256 or normalizer['captures']['normalizer']['code_sha256'] != 'c757d2f0c927f36e058ff5e57350a80beac1db2a89d3940fcb5e89c05545f23e':
        raise RuntimeError('Pinned shared normalizer identity changed')
    guards = normalizer['instruction_guards']['normalizer']
    norm_instructions = tuple((i['text'] for f in normalizer['captures']['normalizer']['fragments'] for i in f['instructions']))
    if 'cmp ecx, 0x8c468e3c' not in norm_instructions or guards.get('0x1401ca6c7') != 'cmp ecx, 0xd6fcf3e4' or guards.get('0x1401ca6ec') != 'mov dword ptr [rbp + 0x17], eax':
        raise RuntimeError('Pinned position/D6 normalizer branches changed')
    position = load_pinned_json(_POSITION_PROOF, POSITION_PROOF_SHA256)
    if position.get('schema') != 'civ6rl.native_event_f4fe1b62.v1' or position.get('image', {}).get('exe_sha256') != EXE_SHA256 or position.get('event', {}).get('callback_va') != '0x14014c2c0':
        raise RuntimeError('Pinned position-envelope proof identity changed')

def verify_normalization_source_evidence():
    """Verify the additional scalar against the complete pinned native bodies."""
    verify_source_evidence()
    proof = load_pinned_json(_NORMALIZATION_PROOF, NORMALIZATION_PROOF_SHA256)
    contract = proof.get('contract', {})
    extra = contract.get('extra_field', {})
    if proof.get('schema') != 'civ6rl.native_event_418bc436.five_fields.static.v1' or proof.get('kind') != EVENT_KIND or proof.get('native_execution') is not False or (proof.get('images') != {'exe_sha256': EXE_SHA256, 'core_sha256': 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'}) or (contract.get('input_keys') != tuple(sorted((DESCRIPTOR_KEY, POSITION_KEY, SELECTOR_KEY, OPTIONAL_KEY, VALUE_KEY)))) or (contract.get('tags') != {'23739F42': 1024, '8C468E3C': 0, 'A1E5A149': 3, 'A1FBC372': 2, 'D6FCF3E4': 2}) or (contract.get('scalar_flags') != 0) or (contract.get('scalar_domain') != (0, 4294967295)) or (contract.get('borrowed_copy_order') != ('23739F42 city8', '8C468E3C position8')) or (extra.get('key') != OPTIONAL_KEY) or (extra.get('normalized_offset') != 84) or (extra.get('callback_reads_field') is not False) or (extra.get('branch_on_value') is not False) or (extra.get('record_effect') != 'none') or (extra.get('query_effect') != 'none') or (contract.get('record') != {'size': 112, 'type': 105, 'payload_offset': 80, 'payload_size': 32, 'record_count': 1, 'undefined_ranges': ((84, 88),), 'allocation_zero_ranges': ((76, 80),)}) or (proof.get('verification', {}).get('all_captured_instructions_match_pinned_pe') is not True):
        raise RuntimeError('Pinned CityMadePurchase five-field contract changed')
    for name, expected in (('callback', '0780281a22b1c94a9f5aa2acecb939c3ea014dde5fe7f1c5c27f98d74beec750'), ('writer', 'b019c7c8bc61edd1dd0d4fdf10841ded358a7307c07a63baabde8af5f297c6ec'), ('normalizer', 'c757d2f0c927f36e058ff5e57350a80beac1db2a89d3940fcb5e89c05545f23e')):
        if proof['captures'][name]['code_sha256'] != expected:
            raise RuntimeError('CityMadePurchase native body identity changed: ' + name)
    for name, expected in (('existing_callback_writer', CITY_CANDIDATE_PROOF_SHA256), ('existing_normalizer', NORMALIZER_PROOF_SHA256), ('existing_position', POSITION_PROOF_SHA256), ('entity_observers', '8e221c6ff8a02f77293ef9ce8f62d38cc9b39a545bde8e1740199a630318dd3e'), ('receiver', '8f93575f0641395046818b5d3af84cbb5ae113986b8f8411dd4bcee4c9d4e044')):
        if proof['parents'][name]['sha256'] != expected:
            raise RuntimeError('CityMadePurchase parent evidence identity changed: ' + name)
    return proof

def verify_missing_value_source_evidence():
    """Pin the one exact absent-D6 shape to its native zero-initialized slot."""
    verify_normalization_source_evidence()
    proof = load_pinned_json(_MISSING_VALUE_PROOF, MISSING_VALUE_PROOF_SHA256)
    shape = sorted((DESCRIPTOR_KEY, POSITION_KEY, SELECTOR_KEY))
    if proof.get('schema') != 'civ6rl.native_event_418bc436_missing_value920.v1' or proof.get('source_proof', {}).get('sha256') != NORMALIZATION_PROOF_SHA256 or proof.get('exact_shape') != tuple((f'0x{k:08x}' for k in shape)) or (proof.get('contract') != {'missing_d6_value': 0, 'optional_A1FBC372': 'remains absent/unreported', 'only_admitted_shape': tuple((f'0x{k:08x}' for k in shape)), 'preserves_existing_four_and_five_key_shapes': True, 'no_general_missing_value_or_extra_key_admission': True}) or (proof.get('normalizer', {}).get('normalized_d6_offset') != 80) or (proof.get('normalizer', {}).get('stack_location') != 'rbp+0x17') or (proof.get('normalizer', {}).get('instruction') != 'mov qword ptr [rbp + 0x17], r13') or (proof.get('normalizer', {}).get('initial_r13_zero', {}).get('instruction') != 'xor r13d, r13d') or (proof.get('witness', {}).get('fields') is None) or (set(proof['witness']['fields']) != set(proof['exact_shape'])) or (proof.get('witness', {}).get('result_substituted') is not False) or (proof.get('witness', {}).get('eligible_for_training') is not False):
        raise RuntimeError('Pinned missing-D6 source/witness contract changed')
    return proof

@dataclass(frozen=True)
class EventFields:
    selector: int
    value: int
    position_bytes: bytes
    descriptor_bytes: bytes
    owner: int
    item_id: int
    optional_value: int | None = None

def _validate(fields: EventFields) -> None:
    if not isinstance(fields, EventFields) or type(fields.selector) is not int or (not 0 <= fields.selector <= 4294967295) or (type(fields.value) is not int) or (not 0 <= fields.value <= 4294967295) or (type(fields.position_bytes) is not bytes) or (len(fields.position_bytes) != 8) or (type(fields.descriptor_bytes) is not bytes) or (len(fields.descriptor_bytes) != 8) or (type(fields.owner) is not int) or (not 0 <= fields.owner <= 65535) or (type(fields.item_id) is not int) or (not 0 <= fields.item_id <= 4294967295) or (struct.unpack_from('<H', fields.descriptor_bytes)[0] != fields.owner) or (struct.unpack_from('<I', fields.descriptor_bytes, 4)[0] != fields.item_id) or (fields.optional_value is not None and (type(fields.optional_value) is not int or not 0 <= fields.optional_value <= 4294967295)):
        raise ValueError('418BC436 requires exact source-decoded fields')

def decode_fields(fields: dict[int, bytes], read) -> EventFields:
    """Admit source-proved shapes and preserve native city→position copy order.

    A1FBC372 is normalized to DWORD+54. This callback never reads that slot;
    its presence does not add a query or change the record payload.
    """
    verify_normalization_source_evidence()
    expected = {SELECTOR_KEY, DESCRIPTOR_KEY, POSITION_KEY, VALUE_KEY}
    missing_value_shape = {SELECTOR_KEY, DESCRIPTOR_KEY, POSITION_KEY}
    if type(fields) is not dict or set(fields) not in (expected, expected | {OPTIONAL_KEY}, missing_value_shape):
        raise ValueError('418BC436 requires the exact three-key source profile or four/five-key normalized shape')
    if set(fields) == missing_value_shape:
        verify_missing_value_source_evidence()
    if any((type(raw) is not bytes or len(raw) != 24 for raw in fields.values())):
        raise ValueError('418BC436 requires complete bytes variants')
    selector = decode_scalar(fields[SELECTOR_KEY], 3)
    value = decode_scalar(fields[VALUE_KEY], 2) if VALUE_KEY in fields else 0
    optional_value = decode_scalar(fields[OPTIONAL_KEY], 2) if OPTIONAL_KEY in fields else None
    for key, tag in ((DESCRIPTOR_KEY, 1024), (POSITION_KEY, 0)):
        raw = fields[key]
        pointer, size, flags = struct.unpack_from('<QII', raw, 8)
        if struct.unpack_from('<H', raw)[0] != tag or size != 8 or flags != 553648129 or (not pointer):
            raise ValueError('418BC436 requires the source-backed nonnull eight-byte envelope')
    descriptor = copy_eight_byte_variant(fields[DESCRIPTOR_KEY], read, expected_tag=1024)
    position = copy_eight_byte_variant(fields[POSITION_KEY], read, expected_tag=0)
    result = EventFields(selector, value, position, descriptor, struct.unpack_from('<H', descriptor)[0], struct.unpack_from('<I', descriptor, 4)[0], optional_value)
    _validate(result)
    return result

def encode_record(sequence: int, fields: EventFields, *, normalizer_transform_present: bool, per_thread_hook_present: bool, writer_metadata_callback_present: bool, padding_policy: str) -> bytes:
    """Encode type0x69 in the explicit absent-transform/callback profile."""
    verify_normalization_source_evidence()
    _validate(fields)
    if normalizer_transform_present is not False or per_thread_hook_present is not False or writer_metadata_callback_present is not False:
        raise ValueError('418BC436 transform, per-thread hook, or writer callback is unsupported')
    if type(sequence) is not int or not 1 <= sequence <= 4294967295:
        raise ValueError('418BC436 requires a nonzero uint32 sequence')
    if padding_policy != _STACK_POLICY:
        raise ValueError('418BC436 requires explicit zero policy for uninitialized local bytes')
    record = bytearray(RECORD_SIZE)
    struct.pack_into('<IIII', record, 0, RECORD_SIZE, RECORD_TYPE, sequence, 0)
    struct.pack_into('<II', record, 16, 4294967295, 4294967295)
    for offset in (24, 32, 40, 48, 56):
        struct.pack_into('<HHI', record, offset, 65535, 0, 4294967295)
    struct.pack_into('<I', record, 80, sequence)
    struct.pack_into('<HHI', record, 88, fields.owner, 2, fields.item_id)
    record[96:104] = fields.position_bytes
    struct.pack_into('<II', record, 104, fields.selector, fields.value)
    return bytes(record)
