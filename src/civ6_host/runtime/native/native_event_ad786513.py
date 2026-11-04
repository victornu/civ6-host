"""AD786513 transport; gameplay remains in the native producer.

Only the witnessed city/unit/selector envelope and an explicitly empty
receiver are admitted. Borrowed descriptors never outlive the dispatch.
"""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
from dataclasses import dataclass
from pathlib import Path
import struct
from civ6_host.runtime.native.native_application_mirror import decode_scalar
from civ6_host.runtime.native.native_host_event_registry import EXE_EVENT_CALLBACKS
from civ6_host.runtime.native.native_source_cache import load_pinned_json
EVENT_KIND, RECORD_TYPE, RECORD_SIZE = (2910348563, 277, 96)
CITY_KEY, UNIT_KEY, SELECTOR_KEY = (594779970, 4032072631, 2716180809)
PADDING_POLICY = 'zero-unread-empty-receiver-payload'
PROOF_SHA256 = '675eca1aae49a3d1b99df4396780ee24f01149c89dd32d579c9156f78e486e3d'
_PROOF = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_event_ad786513.py')))).resolve().parents[1] / 'evidence/native-event-ad786513' / (PROOF_SHA256 + '.json')
_RECEIVER_KEYS = frozenset(('observer_registered', 'state_pointer_nonnull', 'pre_hook', 'post_hook', 'subscriber_count', 'state_flags'))

def verify_source_evidence():
    proof = load_pinned_json(_PROOF, PROOF_SHA256)
    contract = proof['contract']
    if proof['schema'] != 'civ6rl.native_event_ad786513.static.v1' or proof['kind'] != EVENT_KIND or EXE_EVENT_CALLBACKS.get(EVENT_KIND) != 1308704 or (proof['registry']['registration']['callback_va'] != '0x14013f820') or (proof['images'] != {'exe_sha256': 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63', 'core_sha256': 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'}) or (proof['contract']['record']['type'] != RECORD_TYPE) or (proof['contract']['record']['size'] != RECORD_SIZE) or (proof['contract']['record']['metadata_city_offset'] != 56) or (contract['input_keys'] != (CITY_KEY, SELECTOR_KEY, UNIT_KEY)) or (contract['tags'] != {'23739F42': 1024, 'A1E5A149': 3, 'F0548BB7': 1024}) or (contract['selector_profile'] != 0) or (contract['borrowed_copy_order'] != (CITY_KEY, UNIT_KEY)) or (contract['normalization'] != {'city_destination': 24, 'unit_destination': 8, 'selector_destination': 4, 'city_type': 2, 'unit_type': 1, 'pointed_type_word_consumed': False}) or (contract['record']['undefined_ranges'] != ((84, 88),)) or (contract['record']['allocation_zero_ranges'] != ((76, 80),)) or (contract['optional_services'] != {'normalizer_transform_present': False, 'per_thread_hook_present': False, 'writer_metadata_callback_present': False, 'entity_listener_count': 0}) or (proof['parents']['receiver']['sha256'] != '92e1d152d256e6029ed8e025af1ae9546fcfe106b7ce638741b2f5c6e0de6710') or (proof['empty_receiver_source']['event_name'] != 'GameCoreEvent::BarbarianRaidStarted') or (proof['captures']['callback']['code_sha256'] != 'fc4ca001f986617739ea511ceb171a9f89e4463647301be42acc2ce546566a49') or (proof['captures']['writer']['code_sha256'] != '5b352ce3d9ef2ed4c730ef45465d7537f3d051374e3f7cb0c5e79a46ed039b39') or (proof['captures']['normalizer']['code_sha256'] != 'c757d2f0c927f36e058ff5e57350a80beac1db2a89d3940fcb5e89c05545f23e') or (proof['verification']['all_captured_instructions_match_pinned_pe'] is not True):
        raise RuntimeError('AD786513 source identity or transport contract changed')
    return proof

@dataclass(frozen=True)
class EventFields:
    selector: int
    city: bytes
    unit: bytes

def _validate(fields):
    if not isinstance(fields, EventFields) or type(fields.selector) is not int or fields.selector != 0 or any((type(blob) is not bytes or len(blob) != 8 for blob in (fields.city, fields.unit))) or (struct.unpack_from('<H', fields.city, 2)[0] != 2) or (struct.unpack_from('<H', fields.unit, 2)[0] != 1):
        raise ValueError('AD786513 requires normalized city/unit descriptors and selector zero')

def decode_fields(raw_fields, read):
    verify_source_evidence()
    if type(raw_fields) is not dict or set(raw_fields) != {CITY_KEY, UNIT_KEY, SELECTOR_KEY} or any((type(raw) is not bytes or len(raw) != 24 for raw in raw_fields.values())):
        raise ValueError('AD786513 requires exactly three complete typed fields')
    selector = decode_scalar(raw_fields[SELECTOR_KEY], 3)
    if selector != 0:
        raise ValueError('AD786513 only admits its witnessed selector zero')
    pointers = []
    for key in (CITY_KEY, UNIT_KEY):
        raw = raw_fields[key]
        pointer, size, flags = struct.unpack_from('<QII', raw, 8)
        if struct.unpack_from('<H', raw)[0] != 1024 or not pointer or size != 8 or (flags != 553648129):
            raise ValueError('AD786513 descriptor envelope is outside the source profile')
        pointers.append(pointer)
    normalized = []
    for pointer, forced_type in zip(pointers, (2, 1)):
        copied = read(pointer, 8)
        if not isinstance(copied, (bytes, bytearray, memoryview)) or len(copied) != 8:
            raise ValueError('AD786513 descriptor read is incomplete')
        owner, _ignored_type, identifier = struct.unpack('<HHI', copied)
        normalized.append(struct.pack('<HHI', owner, forced_type, identifier))
    result = EventFields(selector, *normalized)
    _validate(result)
    return result

def encode_record(sequence, fields, *, normalizer_transform_present, per_thread_hook_present, writer_metadata_callback_present, entity_listener_count, empty_receiver_state, padding_policy):
    verify_source_evidence()
    _validate(fields)
    if normalizer_transform_present is not False or per_thread_hook_present is not False or writer_metadata_callback_present is not False or (type(entity_listener_count) is not int) or (entity_listener_count != 0):
        raise ValueError('AD786513 needs the explicit absent-service and empty-listener profile')
    if type(sequence) is not int or not 1 <= sequence <= 4294967295:
        raise ValueError('AD786513 sequence must be a nonzero uint32')
    if padding_policy != PADDING_POLICY or type(empty_receiver_state) is not dict or set(empty_receiver_state) != _RECEIVER_KEYS:
        raise ValueError('AD786513 needs its explicit empty receiver and padding policy')
    record = bytearray(RECORD_SIZE)
    struct.pack_into('<IIII', record, 0, RECORD_SIZE, RECORD_TYPE, sequence, 0)
    from civ6_host.runtime.native.native_deferred_empty_profile import validate_empty_profile_record
    validate_empty_profile_record(record, **empty_receiver_state)
    struct.pack_into('<II', record, 16, 4294967295, 4294967295)
    for offset in (24, 32, 40, 48):
        struct.pack_into('<HHI', record, offset, 65535, 0, 4294967295)
    record[56:64] = fields.city
    struct.pack_into('<I', record, 80, sequence)
    record[88:96] = fields.city
    return bytes(record)
