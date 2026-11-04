"""Source-bounded city/unit notification, with both native metadata descriptors.

The Core owns the gameplay action. This adapter copies its borrowed descriptors
and admits only the dedicated host's actual empty receiver and absent hooks.
"""
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
from dataclasses import dataclass
from pathlib import Path
import struct
from civ6_host.runtime.native.native_application_mirror import decode_scalar
from civ6_host.runtime.native.native_deferred_empty_profile import validate_empty_profile_record
from civ6_host.runtime.native.native_host_events import copy_eight_byte_variant
from civ6_host.runtime.native.native_player_event_domains import validate_sequence
from civ6_host.runtime.native.native_source_cache import load_pinned_json
PROOF_SHA256 = 'f36f11c0e0b4ef70dc5073dc8cc0e081750292ead0f699e9f8c47baf6fea4ff7'
EVENT_KIND, CALLBACK_RVA, WRITER_RVA = (2979910027, 1308992, 1184352)
RECORD_TYPE, RECORD_SIZE = (276, 112)
CITY_KEY, UNIT_KEY, SELECTOR_KEY = (594779970, 4032072631, 2716180809)
PADDING_POLICY = 'zero-unread-empty-receiver-payload'

def verify_source_evidence():
    from civ6_host.runtime.native.native_host_event_registry import EXE_EVENT_CALLBACKS
    from civ6_host.runtime.native.native_deferred_empty_profile import B19DD18B_RECEIVER_SHA256
    root = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_event_b19dd18b.py')))).resolve().parents[1]
    proof = load_pinned_json(root / 'evidence/native-event-b19dd18b' / (PROOF_SHA256 + '.json'), PROOF_SHA256)
    contract = proof['contract']
    if proof['schema'] != 'civ6rl.native_event_b19dd18b.static.v1' or proof['images'] != {'exe_sha256': 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63', 'core_sha256': 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'} or EXE_EVENT_CALLBACKS.get(EVENT_KIND) != CALLBACK_RVA or (proof['captures']['callback']['code_sha256'] != '5761ebd7b7c8599c23ce19e5796badaa1523445c3d26b985593ed4202bc7c3e1') or (proof['captures']['writer']['code_sha256'] != 'f48c5d7b82f7a743eef1391cde1abffef65b37416a8fbcbced40e0a168ab7e82') or (proof['captures']['normalizer']['code_sha256'] != 'c757d2f0c927f36e058ff5e57350a80beac1db2a89d3940fcb5e89c05545f23e') or (proof['parents']['receiver']['sha256'] != B19DD18B_RECEIVER_SHA256) or (B19DD18B_RECEIVER_SHA256 != '69f66abb84d0f7d463d57b42dff29d20fd7ad8905c29ed3f9e1afe3b9524969b') or (set(contract['input_keys']) != {CITY_KEY, UNIT_KEY, SELECTOR_KEY}) or (contract['tags'] != {'23739F42': 1024, 'A1E5A149': 3, 'F0548BB7': 1024}) or (contract['scalar_flags'] != 0) or (contract['selector_domain'] != (0, 4294967295)) or (contract['descriptor_envelope'] != {'size': 8, 'flags': 553648129, 'nonnull_pointer': True}) or (contract['normalized_descriptor_types'] != {'23739F42': 2, 'F0548BB7': 1}) or (contract['descriptor_copy_order'] != (CITY_KEY, UNIT_KEY)) or (contract['owner_transport_domain'] != (0, 65535)) or (contract['id_transport_domain'] != (0, 4294967295)) or (contract['record'] != {'type': RECORD_TYPE, 'size': RECORD_SIZE, 'payload_offset': 80, 'payload_size': 24, 'metadata_flag': 0, 'undefined_ranges': ((84, 88),), 'allocation_zero_ranges': ((76, 80), (104, 112))}) or (proof['callback_comparison']['exact_matches'] != ('0x14013f940',)) or (proof['empty_receiver_source']['record_type'] != RECORD_TYPE) or (proof['empty_receiver_source']['record_size'] != RECORD_SIZE) or (proof['verification']['all_captured_instructions_match_pinned_pe'] is not True):
        raise RuntimeError('B19DD18B pinned source identity changed')
    return proof

@dataclass(frozen=True)
class EventFields:
    city_owner: int
    city_id: int
    unit_owner: int
    unit_id: int

def _fields(fields):
    if not isinstance(fields, EventFields):
        raise ValueError('B19DD18B requires its decoded city and unit descriptors')
    for name, bound in (('city_owner', 65535), ('unit_owner', 65535), ('city_id', 4294967295), ('unit_id', 4294967295)):
        value = getattr(fields, name)
        if type(value) is not int or not 0 <= value <= bound:
            raise ValueError('B19DD18B descriptor out of transport range: ' + name)

def decode_fields(raw_fields, read):
    verify_source_evidence()
    if type(raw_fields) is not dict or set(raw_fields) != {CITY_KEY, UNIT_KEY, SELECTOR_KEY} or any((type(raw) is not bytes or len(raw) != 24 for raw in raw_fields.values())):
        raise ValueError('B19DD18B requires exactly three complete typed variants')
    decode_scalar(raw_fields[SELECTOR_KEY], 3)
    for key in (CITY_KEY, UNIT_KEY):
        raw = raw_fields[key]
        pointer, size, flags = struct.unpack_from('<QII', raw, 8)
        if struct.unpack_from('<H', raw)[0] != 1024 or size != 8 or flags != 553648129 or (not pointer):
            raise ValueError('B19DD18B descriptor variant is not source-backed')
    city = copy_eight_byte_variant(raw_fields[CITY_KEY], read, expected_tag=1024)
    unit = copy_eight_byte_variant(raw_fields[UNIT_KEY], read, expected_tag=1024)
    city_owner, _, city_id = struct.unpack('<HHI', city)
    unit_owner, _, unit_id = struct.unpack('<HHI', unit)
    fields = EventFields(city_owner, city_id, unit_owner, unit_id)
    _fields(fields)
    return fields

def encode_record(sequence, fields, *, normalizer_transform_present, per_thread_hook_present, writer_metadata_callback_present, entity_listener_count, padding_policy, empty_receiver_state):
    verify_source_evidence()
    validate_sequence(sequence)
    _fields(fields)
    if type(entity_listener_count) is not int or entity_listener_count != 0:
        raise ValueError('B19DD18B requires the actual empty entity-observer profile')
    if normalizer_transform_present is not False or per_thread_hook_present is not False or writer_metadata_callback_present is not False:
        raise ValueError('B19DD18B optional transform or hook is not implemented')
    if padding_policy != PADDING_POLICY:
        raise ValueError('B19DD18B requires explicit unread-gap handling')
    if type(empty_receiver_state) is not dict or set(empty_receiver_state) != {'observer_registered', 'state_pointer_nonnull', 'pre_hook', 'post_hook', 'subscriber_count', 'state_flags'}:
        raise ValueError('B19DD18B requires its actual complete empty receiver state')
    record = bytearray(RECORD_SIZE)
    struct.pack_into('<IIII', record, 0, RECORD_SIZE, RECORD_TYPE, sequence, 0)
    validate_empty_profile_record(record, **empty_receiver_state)
    record[16:24] = b'\xff' * 8
    for offset in (32, 40, 48):
        struct.pack_into('<HHI', record, offset, 65535, 0, 4294967295)
    city = struct.pack('<HHI', fields.city_owner, 2, fields.city_id)
    unit = struct.pack('<HHI', fields.unit_owner, 1, fields.unit_id)
    record[24:32], record[56:64] = (unit, city)
    struct.pack_into('<I', record, 80, sequence)
    record[88:96], record[96:104] = (city, unit)
    validate_empty_profile_record(record, **empty_receiver_state)
    return bytes(record)
