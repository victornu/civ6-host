"""Native unit command notification; command execution remains in the Core."""
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
from dataclasses import dataclass
from pathlib import Path
import struct
from civ6_host.runtime.native.native_application_mirror import decode_scalar
from civ6_host.runtime.native.native_host_events import copy_eight_byte_variant
from civ6_host.runtime.native.native_player_event_domains import validate_sequence
from civ6_host.runtime.native.native_source_cache import load_pinned_json
EVENT_KIND, RECORD_TYPE, RECORD_SIZE = (4236097886, 72, 112)
SELECTOR_KEY, DESCRIPTOR_KEY = (2716180809, 4032072631)
D6_KEY, A1FBC_KEY = (3606901732, 2717631346)
PADDING_POLICY = 'zero-unread-unit-command-stack-gaps-empty-receiver'
PROOF_SHA256 = 'f6af9e306baaeb80411610c17bc6d51dfff8f793690751fd412263a4bf58f58c'
ROOT = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_event_fc7db95e.py')))).resolve().parents[1]

def verify_source_evidence():
    if not PROOF_SHA256:
        raise RuntimeError('FC7DB95E complete source proof has not been pinned')
    from civ6_host.runtime.native.native_deferred_empty_profile import UNIT_COMMAND_RECEIVER_SHA256
    from civ6_host.runtime.native.native_host_event_registry import EXE_EVENT_CALLBACKS
    proof = load_pinned_json(ROOT / 'evidence/native-event-fc7db95e' / (PROOF_SHA256 + '.json'), PROOF_SHA256)
    if proof['schema'] != 'civ6rl.native_event_fc7db95e.static.v1' or proof['images'] != {'exe_sha256': 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63', 'core_sha256': 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'} or EXE_EVENT_CALLBACKS.get(EVENT_KIND) != 1398912 or (proof['registry']['registration']['kind'] != EVENT_KIND) or (proof['registry']['registration']['callback_va'] != '0x140155880') or (proof['parents']['receiver']['sha256'] != UNIT_COMMAND_RECEIVER_SHA256) or (proof['captures']['callback']['code_sha256'] != '605f07b4866a169996a2a69e681dbd1fb1457222130b36a7cffb8be8bc890107') or (proof['captures']['writer']['code_sha256'] != 'a9ab1f0f4b5639c9b942c9db22b43141d1522abb93fe6055c57b53088f153456') or (proof['captures']['normalizer']['code_sha256'] != 'c757d2f0c927f36e058ff5e57350a80beac1db2a89d3940fcb5e89c05545f23e') or (set(proof['contract']['required_input_keys']) != {SELECTOR_KEY, DESCRIPTOR_KEY}) or (set(proof['contract']['optional_input_keys']) != {D6_KEY, A1FBC_KEY}) or (proof['contract']['tags'] != {'A1E5A149': 3, 'F0548BB7': 1024, 'D6FCF3E4': 2, 'A1FBC372': 2}) or (proof['contract']['optional_scalar_default']['A1FBC372'] != 0) or (proof['contract']['optional_scalar_default']['D6FCF3E4'] != 0) or (proof['contract']['descriptor_envelope'] != {'size': 8, 'flags': 553648129, 'nonnull_pointer': True}) or (proof['contract']['record']['type'] != RECORD_TYPE) or (proof['contract']['record']['size'] != RECORD_SIZE) or (proof['contract']['record']['payload_size'] != 32) or (proof['contract']['record']['metadata_flag'] != 0) or (proof['contract']['record']['undefined_ranges'] != ((84, 88), (108, 112))) or (proof['contract']['record']['allocation_zero_ranges'] != ((76, 80),)) or (proof['verification'] != {'instructions_rechecked': 6425, 'parent_instructions_rechecked': 13222, 'callback_scan_instructions_rechecked': 20696}):
        raise RuntimeError('FC7DB95E source identity changed')
    return proof

@dataclass(frozen=True)
class EventFields:
    selector: int
    owner: int
    unit_id: int
    d6_value: int
    a1fbc_value: int

def _validate_fields(fields):
    if not isinstance(fields, EventFields):
        raise ValueError('FC7DB95E requires its decoded command fields')
    if any((type(value) is not int or not 0 <= value <= 4294967295 for value in (fields.selector, fields.unit_id, fields.d6_value, fields.a1fbc_value))):
        raise ValueError('FC7DB95E selector, identifiers and scalars must be uint32')
    if type(fields.owner) is not int or not 0 <= fields.owner <= 65535:
        raise ValueError('FC7DB95E owner must be an exact WORD')

def decode_fields(raw_fields, read):
    verify_source_evidence()
    required = {SELECTOR_KEY, DESCRIPTOR_KEY}
    allowed = required | {D6_KEY, A1FBC_KEY}
    if type(raw_fields) is not dict or not required <= set(raw_fields) <= allowed or any((type(raw) is not bytes or len(raw) != 24 for raw in raw_fields.values())):
        raise ValueError('FC7DB95E requires its unit/selector and only the two optional scalars')
    selector = decode_scalar(raw_fields[SELECTOR_KEY], 3)
    d6 = decode_scalar(raw_fields[D6_KEY], 2) if D6_KEY in raw_fields else 0
    a1fbc = decode_scalar(raw_fields[A1FBC_KEY], 2) if A1FBC_KEY in raw_fields else 0
    descriptor = copy_eight_byte_variant(raw_fields[DESCRIPTOR_KEY], read, expected_tag=1024)
    owner, _ignored_type, unit_id = struct.unpack('<HHI', descriptor)
    result = EventFields(selector, owner, unit_id, d6, a1fbc)
    _validate_fields(result)
    return result

def encode_record(sequence, fields, *, normalizer_transform_present, per_thread_hook_present, writer_metadata_callback_present, entity_listener_count, padding_policy, empty_receiver_state):
    from civ6_host.runtime.native.native_deferred_empty_profile import validate_empty_profile_record
    verify_source_evidence()
    _validate_fields(fields)
    validate_sequence(sequence)
    if any((value is not False for value in (normalizer_transform_present, per_thread_hook_present, writer_metadata_callback_present))):
        raise ValueError('FC7DB95E requires its absent-service profile')
    if type(entity_listener_count) is not int or entity_listener_count != 0:
        raise ValueError('FC7DB95E requires actual empty entity listeners')
    if padding_policy != PADDING_POLICY:
        raise ValueError('FC7DB95E requires its explicit unread-stack policy')
    if type(empty_receiver_state) is not dict or set(empty_receiver_state) != {'observer_registered', 'state_pointer_nonnull', 'pre_hook', 'post_hook', 'subscriber_count', 'state_flags'}:
        raise ValueError('FC7DB95E requires the complete actual empty receiver state')
    record = bytearray(RECORD_SIZE)
    struct.pack_into('<IIII', record, 0, RECORD_SIZE, RECORD_TYPE, sequence, 0)
    struct.pack_into('<II', record, 16, 4294967295, 4294967295)
    for offset in (24, 32, 40, 48, 56):
        struct.pack_into('<HHI', record, offset, 65535, 0, 4294967295)
    struct.pack_into('<HHI', record, 24, fields.owner, 1, fields.unit_id)
    struct.pack_into('<I', record, 80, sequence)
    struct.pack_into('<HHI', record, 88, fields.owner, 1, fields.unit_id)
    struct.pack_into('<III', record, 96, fields.selector, fields.d6_value, fields.a1fbc_value)
    validate_empty_profile_record(record, **empty_receiver_state)
    return bytes(record)
