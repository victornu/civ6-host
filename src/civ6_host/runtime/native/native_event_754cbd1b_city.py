"""754CBD1B with FIRST unit and FIRST district; SECOND unit stays native sentinel.

The common normalizer copies the district even though this event callback does
not put that slot into the record. This is separate from the unit-pair contract.
"""
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
from dataclasses import dataclass
import struct
from civ6_host.runtime.native.native_application_mirror import decode_scalar
from civ6_host.runtime.native.native_host_events import copy_eight_byte_variant
from civ6_host.runtime.native import native_event_754cbd1b as unit_pair
from civ6_host.runtime.native.native_source_cache import load_pinned_json
ROOT = unit_pair.ROOT
EVENT_KIND, RECORD_TYPE, RECORD_SIZE = (unit_pair.EVENT_KIND, unit_pair.RECORD_TYPE, unit_pair.RECORD_SIZE)
SELECTOR_KEY, FIRST_KEY, DISTRICT_KEY = (2716180809, 4032072631, 4081310810)
FIELD_KEYS = frozenset((SELECTOR_KEY, FIRST_KEY, DISTRICT_KEY))
SOURCE_FIELD_PROFILE = 'first-unit-first-district'
PADDING_POLICY = unit_pair.PADDING_POLICY
PROOF_SHA256 = '1ebae31819231e78b093a7d27f51a8680f7d421a012bf205874e4e9769a49143'
PROOF_PATH = 'evidence/native-event-754cbd1b-city-variant/' + PROOF_SHA256 + '.json'
RECHECK_SHA256 = 'c93bce1dd84242d4f2ae7d762670928cf03e89836e770bffb418e34cffabf1b4'
RECHECK_PATH = 'work/native-754cbd1b-city-variant453-recheck.json'

def verify_source_evidence():
    unit_pair.verify_source_evidence()
    if PROOF_SHA256 == 'PENDING' or PROOF_PATH == 'PENDING':
        raise RuntimeError('754CBD1B district producer evidence has not been pinned')
    proof = load_pinned_json(ROOT / PROOF_PATH, PROOF_SHA256)
    recheck = load_pinned_json(ROOT / RECHECK_PATH, RECHECK_SHA256)
    expected_captures = {'core': {'kind_handler_107d80': '06110e37ef1c39d713c84a1c9551d293a14cb9d81dd45ad84d77d518b54f092b', 'type3_descriptor_helper_132660': 'f92ffbd0df6479c807bdb82d5e79e6d9d6202856576977f863d19dcdf347c4e3', 'descriptor_to_field_map_484640': '9318d8219200e4595fc0f76ee9e0a839863ad72f5fbe404b86e60608c4c6e41d', 'generic_event_producer_484eb0': '05947d1784ce1a8897426bb3cf0d06fc66328465d99333496548df703f381c8a'}, 'exe': {'normalizer_1ca2d0': 'c757d2f0c927f36e058ff5e57350a80beac1db2a89d3940fcb5e89c05545f23e', 'callback_1573e0': '9c4f52239e63883d8f928b3b1b34e4f439fc9328b770743bcc365633b5379035', 'resolver_1445f0': '5d0c3c7557f18ad896d84bb83b4c43b6fd47bbee1b25e73967ee78f1fe583d89', 'writer_127f30': '81077506dc33ae13434d627132415b305cd8e1977bd275011260b365baef4e3a'}}
    if proof['schema'] != 'civ6rl.native_event_754cbd1b_city_variant.static.v1' or proof['images'] != {'core_sha256': 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3', 'exe_sha256': 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63'} or proof['parents']['754_unit_pair_producer']['sha256'] != unit_pair.PROOF_SHA256 or (proof['binding']['kind'] != '0x754cbd1b') or (proof['binding']['registration']['kind'] != EVENT_KIND) or (proof['binding']['callback_va'] != '0x1401573e0') or any((proof['captures'][image][name]['code_sha256'] != digest for image, captures in expected_captures.items() for name, digest in captures.items())) or (proof['source_mapping']['normalizer']['defaults']['slot2_base_plus_0x10'] != {'owner': 65535, 'type': 1, 'id': 4294967295}) or (proof['source_mapping']['normalizer']['defaults']['slot5_base_plus_0x28'] != {'owner': 65535, 'type': 3, 'id': 4294967295}) or (proof['source_mapping']['core_second_descriptor']['type'] != 3) or (proof['source_mapping']['core_second_descriptor']['field_key'] != 'F343DC5A') or (type(proof['source_mapping']['selector_origin']['value']) is not int) or (proof['source_mapping']['selector_origin']['value'] != 0) or (proof['source_mapping']['callback_effect']['record_contract_parent'] != {'payload_bytes': 24, 'payload_offset': 80, 'record_size': 112, 'record_type': 30, 'writer_va': '0x140127F30'}):
        raise RuntimeError('754CBD1B district source identity or field mapping changed')
    rows = recheck['independent_recheck']['functions']
    if recheck['schema'] != 'civ6rl.native_event_754cbd1b_city_variant_recheck.static.v1' or recheck['proof']['sha256'] != PROOF_SHA256 or recheck['images'] != proof['images'] or (len(rows) != 12) or (recheck['independent_recheck']['captured_function_count'] != 12) or (recheck['independent_recheck']['decoded_instruction_count'] != 1587) or any((row['all_instruction_bytes_match_pinned_pe'] is not True or row['independent_redecode_matches'] is not True for row in rows.values())) or any((rows[image + '.' + name]['code_sha256'] != digest for image, captures in expected_captures.items() for name, digest in captures.items())):
        raise RuntimeError('754CBD1B district independent PE recheck changed')
    return proof

@dataclass(frozen=True)
class EventFields:
    selector: int
    first_owner: int
    first_id: int
    district_owner: int
    district_id: int

def _validate_fields(fields):
    if type(fields) is not EventFields or type(fields.selector) is not int or fields.selector != 0:
        raise ValueError('754CBD1B district profile requires the exact source selector zero')
    for value in (fields.first_owner, fields.district_owner):
        if type(value) is not int or not 0 <= value <= 65535:
            raise ValueError('754CBD1B descriptor owner must be an exact WORD')
    for value in (fields.first_id, fields.district_id):
        if type(value) is not int or not 0 <= value <= 4294967295:
            raise ValueError('754CBD1B descriptor identifier must be an exact DWORD')

def decode_fields(raw_fields, read):
    verify_source_evidence()
    if type(raw_fields) is not dict or set(raw_fields) != FIELD_KEYS or any((type(raw) is not bytes or len(raw) != 24 for raw in raw_fields.values())):
        raise ValueError('754CBD1B district profile requires exactly A1, F054 and F343')
    selector = decode_scalar(raw_fields[SELECTOR_KEY], 3)
    if selector != 0:
        raise ValueError('754CBD1B district producer selector must be zero')
    for key in (FIRST_KEY, DISTRICT_KEY):
        raw = raw_fields[key]
        pointer, size, flags = struct.unpack_from('<QII', raw, 8)
        if struct.unpack_from('<H', raw)[0] != 1024 or pointer == 0 or size != 8 or (flags != 553648129):
            raise ValueError('754CBD1B district descriptor is outside the borrowed profile')
    first = copy_eight_byte_variant(raw_fields[FIRST_KEY], read, expected_tag=1024)
    district = copy_eight_byte_variant(raw_fields[DISTRICT_KEY], read, expected_tag=1024)
    first_owner, _, first_id = struct.unpack('<HHI', first)
    district_owner, _, district_id = struct.unpack('<HHI', district)
    result = EventFields(selector, first_owner, first_id, district_owner, district_id)
    _validate_fields(result)
    return result

def encode_record(sequence, fields, **profile):
    verify_source_evidence()
    _validate_fields(fields)
    descriptors = unit_pair.EventFields(fields.selector, fields.first_owner, fields.first_id, 65535, 4294967295)
    return unit_pair.encode_record(sequence, descriptors, **profile)
