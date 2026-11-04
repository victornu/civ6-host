"""Two normalized unit descriptors, with only the first in event metadata."""
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
from dataclasses import dataclass
from pathlib import Path
import struct
from civ6_host.runtime.native.native_application_mirror import decode_scalar
from civ6_host.runtime.native.native_host_events import copy_eight_byte_variant
from civ6_host.runtime.native.native_player_event_domains import validate_sequence
from civ6_host.runtime.native.native_source_cache import load_pinned_json
EVENT_KIND, RECORD_TYPE, RECORD_SIZE = (1967963419, 30, 112)
SELECTOR_KEY, FIRST_KEY, SECOND_KEY = (2716180809, 4032072631, 2270411553)
FIELD_KEYS = frozenset((SELECTOR_KEY, FIRST_KEY, SECOND_KEY))
PADDING_POLICY = 'zero-unread-unit-pair-gap-empty-receiver'
PROOF_SHA256 = '7bd71b81b11516427125c29ae96bffbbae878b87c0d3e1049716fc4547f5a12f'
ROOT = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_event_754cbd1b.py')))).resolve().parents[1]

def verify_source_evidence():
    from civ6_host.runtime.native.native_host_event_registry import EXE_EVENT_CALLBACKS
    from civ6_host.runtime.native.native_deferred_empty_profile import UNIT_PAIR_RECEIVER_SHA256
    if not PROOF_SHA256:
        raise RuntimeError('754CBD1B complete source proof has not been pinned')
    proof = load_pinned_json(ROOT / 'evidence/native-event-754cbd1b' / (PROOF_SHA256 + '.json'), PROOF_SHA256)
    if proof['schema'] != 'civ6rl.native_event_754cbd1b.static.v1' or proof['images'] != {'exe_sha256': 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63', 'core_sha256': 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'} or EXE_EVENT_CALLBACKS.get(EVENT_KIND) != 1405920 or (proof['kind'] != EVENT_KIND) or (proof['registry']['registration']['callback_va'] != '0x1401573e0') or (proof['registry']['registration']['kind'] != EVENT_KIND) or (proof['parents']['receiver']['sha256'] != UNIT_PAIR_RECEIVER_SHA256) or (proof['captures']['callback']['code_sha256'] != '9c4f52239e63883d8f928b3b1b34e4f439fc9328b770743bcc365633b5379035') or (proof['captures']['writer']['code_sha256'] != '81077506dc33ae13434d627132415b305cd8e1977bd275011260b365baef4e3a') or (proof['captures']['normalizer']['code_sha256'] != 'c757d2f0c927f36e058ff5e57350a80beac1db2a89d3940fcb5e89c05545f23e') or (set(proof['contract']['input_keys']) != FIELD_KEYS) or (proof['contract']['tags'] != {'A1E5A149': 3, 'F0548BB7': 1024, '8753BB21': 1024}) or (proof['contract']['descriptor_envelope'] != {'size': 8, 'flags': 553648129, 'nonnull_pointer': True}) or (proof['contract']['record']['type'] != RECORD_TYPE) or (proof['contract']['record']['size'] != RECORD_SIZE) or (proof['contract']['record']['payload_size'] != 24) or (proof['contract']['record']['metadata_flag'] != 0) or (proof['contract']['record']['undefined_ranges'] != ((84, 88),)) or (proof['contract']['record']['allocation_zero_ranges'] != ((76, 80), (104, 112))) or (proof['validation']['all_captured_instructions_match_pinned_pe'] is not True):
        raise RuntimeError('754CBD1B source identity changed')
    return proof

@dataclass(frozen=True)
class EventFields:
    selector: int
    first_owner: int
    first_id: int
    second_owner: int
    second_id: int

def _validate_fields(fields):
    if not isinstance(fields, EventFields):
        raise ValueError('754CBD1B requires its decoded unit pair')
    for value in (fields.selector, fields.first_id, fields.second_id):
        if type(value) is not int or not 0 <= value <= 4294967295:
            raise ValueError('754CBD1B selector and identifiers must be uint32')
    for value in (fields.first_owner, fields.second_owner):
        if type(value) is not int or not 0 <= value <= 65535:
            raise ValueError('754CBD1B owners must be exact WORD values')

def decode_fields(raw_fields, read):
    verify_source_evidence()
    if type(raw_fields) is not dict or set(raw_fields) != FIELD_KEYS or any((type(raw) is not bytes or len(raw) != 24 for raw in raw_fields.values())):
        raise ValueError('754CBD1B requires exactly three complete typed fields')
    selector = decode_scalar(raw_fields[SELECTOR_KEY], 3)
    for key in (SECOND_KEY, FIRST_KEY):
        variant = raw_fields[key]
        pointer, size, flags = struct.unpack_from('<QII', variant, 8)
        if struct.unpack_from('<H', variant)[0] != 1024 or not pointer or size != 8 or (flags != 553648129):
            raise ValueError('754CBD1B unit descriptor is outside its borrowed blob profile')
    second = copy_eight_byte_variant(raw_fields[SECOND_KEY], read, expected_tag=1024)
    first = copy_eight_byte_variant(raw_fields[FIRST_KEY], read, expected_tag=1024)
    first_owner, _, first_id = struct.unpack('<HHI', first)
    second_owner, _, second_id = struct.unpack('<HHI', second)
    result = EventFields(selector, first_owner, first_id, second_owner, second_id)
    _validate_fields(result)
    return result

def encode_record(sequence, fields, *, normalizer_transform_present, per_thread_hook_present, writer_metadata_callback_present, entity_listener_count, padding_policy, empty_receiver_state):
    from civ6_host.runtime.native.native_deferred_empty_profile import validate_empty_profile_record
    verify_source_evidence()
    _validate_fields(fields)
    validate_sequence(sequence)
    if any((value is not False for value in (normalizer_transform_present, per_thread_hook_present, writer_metadata_callback_present))):
        raise ValueError('754CBD1B requires the absent-service profile')
    if type(entity_listener_count) is not int or entity_listener_count != 0:
        raise ValueError('754CBD1B requires actual empty entity listeners')
    if padding_policy != PADDING_POLICY:
        raise ValueError('754CBD1B requires its explicit unread-gap policy')
    if type(empty_receiver_state) is not dict or set(empty_receiver_state) != {'observer_registered', 'state_pointer_nonnull', 'pre_hook', 'post_hook', 'subscriber_count', 'state_flags'}:
        raise ValueError('754CBD1B requires the complete actual empty receiver state')
    record = bytearray(RECORD_SIZE)
    struct.pack_into('<IIII', record, 0, RECORD_SIZE, RECORD_TYPE, sequence, 0)
    struct.pack_into('<II', record, 16, 4294967295, 4294967295)
    for offset in (24, 32, 40, 48, 56):
        struct.pack_into('<HHI', record, offset, 65535, 0, 4294967295)
    struct.pack_into('<HHI', record, 24, fields.first_owner, 1, fields.first_id)
    struct.pack_into('<I', record, 80, sequence)
    struct.pack_into('<HHI', record, 88, fields.first_owner, 1, fields.first_id)
    struct.pack_into('<HHI', record, 96, fields.second_owner, 1, fields.second_id)
    validate_empty_profile_record(record, **empty_receiver_state)
    return bytes(record)
