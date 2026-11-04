"""Source-backed project-completion branch with no position lookup (38F == -1).

This is host notification serialization, not a project or reward simulation.
The three yielded records must be enqueued in order; the retained native Game
getter is invoked only after the caller has enqueued the first record.
"""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
from pathlib import Path
import struct
from civ6_host.runtime.native.native_application_mirror import decode_scalar
from civ6_host.runtime.native.native_host_events import copy_eight_byte_variant
from civ6_host.runtime.native.native_source_cache import load_pinned_json
from civ6_host.runtime.native import native_event_3182bc8e as initial
PINNED_EVIDENCE_SHA256 = '913e7e6f538e1d298a636d3550bf7fe03ea5b860198270986340ab68a9a16b7f'
_PROOF = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_event_3182bc8e_project.py')))).resolve().parents[1] / 'evidence/native-event-3182bc8e-project.json'
STACK_POLICY = 'zero-unread-empty-receiver-payload'

def verify_source_evidence():
    initial.verify_source_evidence()
    proof = load_pinned_json(_PROOF, PINNED_EVIDENCE_SHA256)
    if proof.get('schema') != 'civ6rl.native_event_3182bc8e.project.static.v1' or proof['images']['exe']['sha256'] != initial.EXE_SHA256 or proof['base_proof']['sha256'] != initial.PINNED_EVIDENCE_SHA256 or (proof['captures']['callback']['code_sha256'] != 'a24894edb50dda75e23f69c6137b66348830f7ee6e7020a93ecb33eac0bb8f99') or (proof['captures']['writer_branch_a']['code_sha256'] != 'fe84282b9c51f08a493b2baf52a0d1192278dd47a52225afa6f524d4ce538c6e') or (proof['captures']['writer_branch_b']['code_sha256'] != 'bd4454ee6cd548eca814838965f66db941b3f7170a93965376313617e5e725fa') or (proof['source_instruction_guards']['callback']['0x140141c1f'] != 'je 0x140141cfe') or (proof['source_instruction_guards']['callback']['0x140141d61'] != 'call 0x1400f1420') or (proof['comparisons']['writers63_64_canonical_equal'] is not True):
        raise RuntimeError('Project-completion source contract changed')
    return proof

def _validate_fields(fields):
    if not isinstance(fields, initial.EventFields) or type(fields.selector) is not int or fields.selector != 0 or (type(fields.descriptor_bytes) is not bytes) or (len(fields.descriptor_bytes) != 8) or (type(fields.owner) is not int) or (not 0 <= fields.owner <= 65535) or (type(fields.item_id) is not int) or (not 0 <= fields.item_id <= 4294967295) or (struct.unpack_from('<H', fields.descriptor_bytes)[0] != fields.owner) or (struct.unpack_from('<I', fields.descriptor_bytes, 4)[0] != fields.item_id) or (type(fields.d6_value) is not int) or (fields.d6_value != 3) or (type(fields.a1fbc_value) is not int) or (not 0 <= fields.a1fbc_value <= 4294967295) or (type(fields.normalized_58) is not int) or (fields.normalized_58 != 4294967295):
        raise ValueError('Project notification requires selector0, D6=3 and initialized 38F=-1')

def decode_fields(raw_fields, read):
    verify_source_evidence()
    if type(raw_fields) is not dict or set(raw_fields) != {initial.DESCRIPTOR_KEY, initial.SELECTOR_KEY, initial.D6_KEY, initial.A1FBC_KEY, initial.NORMALIZED_58_KEY}:
        raise ValueError('Project notification requires exactly five source-backed fields')
    selector = decode_scalar(raw_fields[initial.SELECTOR_KEY], 3)
    d6 = decode_scalar(raw_fields[initial.D6_KEY], 2)
    a1fbc = decode_scalar(raw_fields[initial.A1FBC_KEY], 2)
    normalized_58 = decode_scalar(raw_fields[initial.NORMALIZED_58_KEY], 2)
    if selector != 0 or d6 != 3 or normalized_58 != 4294967295:
        raise ValueError('Project city/map lookup branch has not been admitted')
    blob = copy_eight_byte_variant(raw_fields[initial.DESCRIPTOR_KEY], read, expected_tag=1024)
    owner, _, item_id = struct.unpack('<HHI', blob)
    fields = initial.EventFields(selector, blob, owner, item_id, d6, a1fbc, normalized_58)
    _validate_fields(fields)
    return fields

def iter_records(sequence, fields, retained_game_getter, *, empty_receiver_profile, padding_policy, normalizer_transform_present=False, thread_hook_present=False, project_hook_present=False, narrative_hook_present=False, writer_metadata_callback_present=False):
    """Yield 60, call the actual F1420 equivalent, then yield 63 and 64.

    The caller must enqueue each yield before requesting the next. Unknown
    coordinates are the explicit native -9999 sentinels, never map guesses.
    Source-unwritten bytes are zero only for the verified empty receiver;
    those bytes and these notifications are not learner observations.
    """
    verify_source_evidence()
    _validate_fields(fields)
    if any((value is not False for value in (normalizer_transform_present, thread_hook_present, project_hook_present, narrative_hook_present, writer_metadata_callback_present))):
        raise ValueError('Project notification hook/transform/metadata path is unsupported')
    if empty_receiver_profile is not True or padding_policy != STACK_POLICY:
        raise ValueError('Explicit empty receiver and unread padding policy required')
    if type(sequence) is not int or not 1 <= sequence <= 4294967293:
        raise ValueError('Three consecutive nonzero uint32 sequence numbers required')
    if not callable(retained_game_getter):
        raise ValueError('Project notification requires the real retained Game getter')
    yield initial._pack_initial_record(sequence, fields)
    local_value = retained_game_getter()
    if type(local_value) is not int or not -(1 << 31) <= local_value < 1 << 31:
        raise ValueError('F1420 must return its native signed DWORD')
    signed_owner = struct.unpack('<h', fields.descriptor_bytes[:2])[0]
    metadata_flags = 22 if signed_owner == local_value else 6
    for offset, record_type in ((1, 99), (2, 100)):
        record = bytearray(128)
        current_sequence = sequence + offset
        struct.pack_into('<IIII', record, 0, 128, record_type, current_sequence, 0)
        struct.pack_into('<II', record, 16, 4294967295, 4294967295)
        for position in (24, 32, 40, 48, 56):
            struct.pack_into('<HHI', record, position, 65535, 0, 4294967295)
        struct.pack_into('<II', record, 64, 0, 0)
        struct.pack_into('<I', record, 72, metadata_flags)
        struct.pack_into('<I', record, 80, current_sequence)
        struct.pack_into('<HHI', record, 88, fields.owner, 2, fields.item_id)
        struct.pack_into('<IIii', record, 96, fields.a1fbc_value, fields.normalized_58, -9999, -9999)
        record[112] = 0
        yield bytes(record)
