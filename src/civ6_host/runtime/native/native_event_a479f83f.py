"""Source-ordered experience and conditional promotion notifications.

The real GameCore updates experience before entering this callback. These
serializers do not calculate experience or decide whether promotion is legal.
"""
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
from dataclasses import dataclass
from pathlib import Path
import struct
from civ6_host.runtime.native.native_application_mirror import decode_scalar
from civ6_host.runtime.native.native_host_events import copy_eight_byte_variant
from civ6_host.runtime.native.native_player_event_domains import validate_sequence
from civ6_host.runtime.native.native_source_cache import load_pinned_json
EVENT_KIND = 2759456831
EXPERIENCE_TYPE, EXPERIENCE_SIZE = (74, 96)
PROMOTION_TYPE, PROMOTION_SIZE = (79, 112)
SELECTOR_KEY, DESCRIPTOR_KEY = (2716180809, 4032072631)
PADDING_POLICY = 'zero-unread-experience-promotion-stack-gaps-empty-receivers'
PROOF_SHA256 = '8418c1bd1e52f720a8b557f199583c741eacece3acd59fcfff5bd3299b76d0ff'
ROOT = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_event_a479f83f.py')))).resolve().parents[1]

def verify_source_evidence():
    from civ6_host.runtime.native.native_deferred_empty_profile import A479_RECEIVERS_SHA256
    proof = load_pinned_json(ROOT / 'evidence/native-event-a479f83f' / (PROOF_SHA256 + '.json'), PROOF_SHA256)
    contract = proof['contract']
    if proof['schema'] != 'civ6rl.native_event_a479f83f.static.v1' or proof['images'] != {'exe_sha256': 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63', 'core_sha256': 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'} or proof['registry']['registration']['callback_va'] != '0x1401561b0' or (proof['registry']['registration']['kind'] != EVENT_KIND) or (proof['captures']['callback']['code_sha256'] != '867b3ab34d81515d1022e3dd4d27650cd519fde569d5f89d893ed0b31bc39403') or (proof['captures']['writer_4a']['code_sha256'] != '67bcf34be9f4bd6fe5d8c4a89dae21c183b02a4031562461bd2bad8d33ea5118') or (proof['captures']['writer_4f']['code_sha256'] != 'af30a992854feee0ae02ffd2ce7f95c660cee16694ba82818afaa0a13da0116d') or (proof['captures']['normalizer']['code_sha256'] != 'c757d2f0c927f36e058ff5e57350a80beac1db2a89d3940fcb5e89c05545f23e') or (proof['parents']['receiver']['sha256'] != A479_RECEIVERS_SHA256) or (set(contract['field_keys']) != {SELECTOR_KEY, DESCRIPTOR_KEY}) or (contract['input_profile'] != {'descriptor_borrowed_pointer_must_be_readable_for_8_bytes': True, 'descriptor_flags': 553648129, 'descriptor_size': 8, 'descriptor_tag': 1024, 'selector_flags': 0, 'selector_tag': 3, 'selector_uint32': True}) or (contract['record_4a']['type'] != EXPERIENCE_TYPE) or (contract['record_4a']['size'] != EXPERIENCE_SIZE) or (contract['record_4a']['undefined_ranges'] != ((84, 88),)) or (contract['record_4f']['type'] != PROMOTION_TYPE) or (contract['record_4f']['size'] != PROMOTION_SIZE) or (contract['record_4f']['undefined_ranges'] != ((84, 88), (100, 104))) or (contract['maps']['object_size'] != 88) or (contract['query_abi']['service_query_rva'] != 4442432) or (contract['query_abi']['implementation_rva'] != 627680) or (contract['result_lookup']['key'] != 827475943):
        raise RuntimeError('A479F83F callback source changed')
    return proof

@dataclass(frozen=True)
class EventFields:
    selector: int
    owner: int
    unit_id: int

def validate_fields(fields):
    if not isinstance(fields, EventFields) or any((type(v) is not int or not 0 <= v <= 4294967295 for v in (fields.selector, fields.unit_id))) or type(fields.owner) is not int or (not 0 <= fields.owner <= 65535):
        raise ValueError('A479F83F requires the raw selector, owner WORD and unit DWORD')

def decode_fields(raw_fields, read):
    verify_source_evidence()
    if type(raw_fields) is not dict or set(raw_fields) != {SELECTOR_KEY, DESCRIPTOR_KEY}:
        raise ValueError('A479F83F requires the exact two-field envelope')
    selector = decode_scalar(raw_fields[SELECTOR_KEY], 3)
    blob = copy_eight_byte_variant(raw_fields[DESCRIPTOR_KEY], read, expected_tag=1024)
    owner, unused_input_type, identifier = struct.unpack('<HHI', blob)
    return EventFields(selector, owner, identifier)

def validate_profile(*, normalizer_transform_present, experience_hook_present, promotion_hook_present, writer_metadata_callback_present, entity_listener_count, padding_policy, empty_receiver_state):
    from civ6_host.runtime.native.native_deferred_empty_profile import validate_empty_profile_record
    verify_source_evidence()
    if any((v is not False for v in (normalizer_transform_present, experience_hook_present, promotion_hook_present, writer_metadata_callback_present))):
        raise ValueError('A479F83F optional transform or callback services are not implemented')
    if type(entity_listener_count) is not int or entity_listener_count != 0:
        raise ValueError('A479F83F requires the actual empty entity listener profile')
    if padding_policy != PADDING_POLICY:
        raise ValueError('A479F83F requires its explicit unread stack-padding policy')
    if type(empty_receiver_state) is not dict or set(empty_receiver_state) != {'observer_registered', 'state_pointer_nonnull', 'pre_hook', 'post_hook', 'subscriber_count', 'state_flags'}:
        raise ValueError('A479F83F requires the complete receiver state')
    for size, kind in ((EXPERIENCE_SIZE, EXPERIENCE_TYPE), (PROMOTION_SIZE, PROMOTION_TYPE)):
        shape = bytearray(size)
        struct.pack_into('<II', shape, 0, size, kind)
        validate_empty_profile_record(shape, **empty_receiver_state)

def _encode(sequence, fields, size, kind):
    validate_sequence(sequence)
    validate_fields(fields)
    record = bytearray(size)
    struct.pack_into('<IIIIii', record, 0, size, kind, sequence, 0, -1, -1)
    struct.pack_into('<HHI', record, 24, fields.owner, 1, fields.unit_id)
    for offset in (32, 40, 48, 56):
        struct.pack_into('<HHI', record, offset, 65535, 0, 4294967295)
    struct.pack_into('<I', record, 80, sequence)
    struct.pack_into('<HHI', record, 88, fields.owner, 1, fields.unit_id)
    return record

def encode_experience(sequence, fields, **profile):
    validate_profile(**profile)
    return bytes(_encode(sequence, fields, EXPERIENCE_SIZE, EXPERIENCE_TYPE))

def encode_promotion(sequence, fields, promotion_index, **profile):
    validate_profile(**profile)
    if type(promotion_index) is not int or not 0 <= promotion_index <= 4294967295:
        raise ValueError('A479F83F promotion payload must preserve its DWORD bits')
    record = _encode(sequence, fields, PROMOTION_SIZE, PROMOTION_TYPE)
    struct.pack_into('<I', record, 96, promotion_index)
    return bytes(record)
