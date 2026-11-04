"""UnitExitFormation with its optional source-normalized second unit.

An absent second descriptor preserves the normalizer's FFFF/type1/FFFFFFFF
sentinel. A present descriptor is copied into both metadata and payload.
"""
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
from dataclasses import dataclass
from pathlib import Path
import struct
from civ6_host.runtime.native.native_application_mirror import decode_scalar
from civ6_host.runtime.native.native_host_events import copy_eight_byte_variant
from civ6_host.runtime.native.native_source_cache import load_pinned_json
EVENT_KIND, RECORD_TYPE, RECORD_SIZE = (1169483000, 39, 112)
PINNED_EVIDENCE_SHA256 = 'e3c46cba1182fd6e895124118ff41a17d22ff314c4c9c5236a050b8443166676'
PROOF = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_event_45b4e4f8.py')))).resolve().parents[1] / 'evidence/native-event-45b4e4f8' / (PINNED_EVIDENCE_SHA256 + '.json')
PAIR_PROOF_SHA256 = '166a59b95d0cb0211293af9d7e72fb54675c89087e955c62f12687c466b4cfbf'
EMPTY_RECEIVER_PROFILE = 'unit-exit-formation-short-row-27-empty'
PADDING_POLICY = 'zero-unread-empty-receiver-payload'
SELECTOR_KEY, VALUE_KEY, UNIT_KEY, SECOND_KEY = (2716180809, 3606901732, 4032072631, 2270411553)
REQUIRED_KEYS = frozenset((SELECTOR_KEY, UNIT_KEY))
OPTIONAL_KEYS = frozenset((VALUE_KEY, SECOND_KEY))

@dataclass(frozen=True)
class EventFields:
    selector: int
    value: int | None
    owner: int
    unit_id: int
    normalized_unit_type: int = 1
    second_owner: int = 65535
    second_id: int = 4294967295

def verify_source_evidence():
    p = load_pinned_json(PROOF, PINNED_EVIDENCE_SHA256)
    if p.get('schema') != 'civ6rl.native_event_45b4e4f8.static.v1' or p.get('exe_sha256') != 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63' or p.get('core_sha256') != 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3' or (p.get('registry', {}).get('registration', {}).get('callback_va') != '0x140156080') or (p.get('receiver', {}).get('record_type') != RECORD_TYPE) or (p.get('receiver', {}).get('event_name') != 'GameCoreEvent::UnitExitFormation') or (p.get('contract', {}).get('profile') != 'short-three-key-activation-producer'):
        raise RuntimeError('UnitExitFormation source identity changed')
    for name, digest in {'callback': '55b353ab355113b4507d389fd259106fa215ad79513bd568d750a9a51c575459', 'writer': '911c9d05e564076834f9b6c8997a21d34aeb47c9ab30f504fbbcb018ebfd41fd', 'normalizer': 'c757d2f0c927f36e058ff5e57350a80beac1db2a89d3940fcb5e89c05545f23e', 'receiver_setup': '58393defd42d35b3617344a30b33fc79e48ebfe4f420866ba936ccdda3b50225', 'handler': '83bfa3193882112d58c2019100e3e668841f56f56bf310215bbad96ad16ba217'}.items():
        if p.get('captures', {}).get(name, {}).get('code_sha256') != digest:
            raise RuntimeError('UnitExitFormation complete source body changed: ' + name)
    return p

def verify_pair_source_evidence():
    verify_source_evidence()
    root = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_event_45b4e4f8.py')))).resolve().parents[1]
    proof = load_pinned_json(root / 'evidence/native-event-45b4e4f8-pair' / (PAIR_PROOF_SHA256 + '.json'), PAIR_PROOF_SHA256)
    expected_parents = {'legacy_short': PINNED_EVIDENCE_SHA256, 'complete_pair_alias': '654c7442299f8e02ef1261f5fa4067f46409959d9175ab028982b8576584e1c1', 'pair_normalization': '7bd71b81b11516427125c29ae96bffbbae878b87c0d3e1049716fc4547f5a12f', 'empty_receiver_profile': '8f93575f0641395046818b5d3af84cbb5ae113986b8f8411dd4bcee4c9d4e044'}
    contract = proof['contract']
    if proof['schema'] != 'civ6rl.native_event_45b4e4f8.pair.static.v1' or proof['images'] != {'exe_sha256': 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63', 'core_sha256': 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'} or proof['kind'] != EVENT_KIND or (proof['registry']['registration']['callback_va'] != '0x140156080') or ({name: p['sha256'] for name, p in proof['parents'].items()} != expected_parents) or (proof['captures']['callback']['code_sha256'] != '55b353ab355113b4507d389fd259106fa215ad79513bd568d750a9a51c575459') or (proof['captures']['writer']['code_sha256'] != '911c9d05e564076834f9b6c8997a21d34aeb47c9ab30f504fbbcb018ebfd41fd') or (proof['captures']['normalizer']['code_sha256'] != 'c757d2f0c927f36e058ff5e57350a80beac1db2a89d3940fcb5e89c05545f23e') or (set(contract['required_keys']) != REQUIRED_KEYS) or (set(contract['optional_keys']) != OPTIONAL_KEYS) or ({frozenset(keys) for keys in contract['input_fieldsets']} != {REQUIRED_KEYS, REQUIRED_KEYS | {VALUE_KEY}, REQUIRED_KEYS | {SECOND_KEY}, REQUIRED_KEYS | OPTIONAL_KEYS}) or (contract['tags'] != {'A1E5A149': 3, 'D6FCF3E4': 2, 'F0548BB7': 1024, '8753BB21': 1024}) or (contract['selector_consumed'] is not False) or (contract['value_consumed'] is not False) or (contract['native_defaults']['second_descriptor'] != {'owner': 65535, 'type': 1, 'id': 4294967295}) or (contract['borrowed_copy_order'] != ('8753BB21 second8 if present', 'F0548BB7 first8')) or (contract['record']['type'] != RECORD_TYPE) or (contract['record']['size'] != RECORD_SIZE) or (contract['record']['payload_size'] != 24) or (contract['record']['undefined_ranges'] != ((84, 88),)) or (contract['record']['allocation_zero_ranges'] != ((76, 80), (104, 112))) or (contract['native_queries'] != 0) or (contract['retained_interfaces'] != 0) or (contract['padding_policy'] != PADDING_POLICY) or (proof['empty_receiver_source']['event_name'] != 'GameCoreEvent::UnitExitFormation') or (proof['empty_receiver_source']['record_type'] != 39) or (proof['verification']['all_captured_instructions_match_pinned_pe'] is not True):
        raise RuntimeError('UnitExitFormation pair source identity changed')
    for parent in proof['parents'].values():
        load_pinned_json(root / parent['path'], parent['sha256'])
    return proof

def decode_fields(raw_fields, read):
    verify_pair_source_evidence()
    if type(raw_fields) is not dict or not REQUIRED_KEYS <= set(raw_fields) or (not set(raw_fields) <= REQUIRED_KEYS | OPTIONAL_KEYS) or any((type(raw) is not bytes or len(raw) != 24 for raw in raw_fields.values())):
        raise ValueError('45B4E4F8 requires its source-bounded unit field envelope')
    selector = decode_scalar(raw_fields[SELECTOR_KEY], 3)
    value = decode_scalar(raw_fields[VALUE_KEY], 2) if VALUE_KEY in raw_fields else None
    for key in (SECOND_KEY, UNIT_KEY):
        if key not in raw_fields:
            continue
        raw = raw_fields[key]
        pointer, size, flags = struct.unpack_from('<QII', raw, 8)
        if struct.unpack_from('<H', raw)[0] != 1024 or not pointer or size != 8 or (flags != 553648129):
            raise ValueError('45B4E4F8 descriptor is outside its borrowed blob profile')
    second_owner, second_id = (65535, 4294967295)
    if SECOND_KEY in raw_fields:
        second = copy_eight_byte_variant(raw_fields[SECOND_KEY], read, expected_tag=1024)
        second_owner, _, second_id = struct.unpack('<HHI', second)
    first = copy_eight_byte_variant(raw_fields[UNIT_KEY], read, expected_tag=1024)
    owner, _, unit_id = struct.unpack('<HHI', first)
    return EventFields(selector, value, owner, unit_id, 1, second_owner, second_id)

def encode_record(sequence, fields, *, normalizer_transform_present, per_thread_hook_present, writer_metadata_callback_present, entity_listener_count, empty_receiver_state, padding_policy):
    verify_pair_source_evidence()
    expected = dict(profile=EMPTY_RECEIVER_PROFILE, record_type=RECORD_TYPE, event_name='GameCoreEvent::UnitExitFormation', pre_hook=None, post_hook=None, subscriber_count=0, subscriber_list_empty=True, deferred_flag=0)
    if type(empty_receiver_state) is not dict or empty_receiver_state != expected or any((type(empty_receiver_state[k]) is not type(v) for k, v in expected.items())):
        raise ValueError('UnitExitFormation requires the initialized-empty row27')
    if normalizer_transform_present is not False or per_thread_hook_present is not False or writer_metadata_callback_present is not False or (type(entity_listener_count) is not int) or (entity_listener_count != 0):
        raise ValueError('UnitExitFormation optional service is outside the selected profile')
    if type(padding_policy) is not str or padding_policy != PADDING_POLICY:
        raise ValueError('UnitExitFormation requires explicit empty-receiver padding policy')
    if type(sequence) is not int or not 1 <= sequence <= 4294967295:
        raise ValueError('UnitExitFormation sequence must be a nonzero DWORD')
    if not isinstance(fields, EventFields):
        raise ValueError('Unverified UnitExitFormation fields')
    for value in (fields.selector, fields.unit_id, fields.second_id):
        if type(value) is not int or not 0 <= value <= 4294967295:
            raise ValueError('Expected raw DWORD')
    if fields.value is not None and (type(fields.value) is not int or not 0 <= fields.value <= 4294967295):
        raise ValueError('Optional 45B4E4F8 scalar must be a raw DWORD')
    if type(fields.owner) is not int or not 0 <= fields.owner <= 65535 or type(fields.second_owner) is not int or (not 0 <= fields.second_owner <= 65535) or (type(fields.normalized_unit_type) is not int) or (fields.normalized_unit_type != 1):
        raise ValueError('Unverified normalized unit descriptor')
    r = bytearray(RECORD_SIZE)
    struct.pack_into('<IIII', r, 0, RECORD_SIZE, RECORD_TYPE, sequence, 0)
    struct.pack_into('<IIHHI', r, 16, 4294967295, 4294967295, fields.owner, 1, fields.unit_id)
    struct.pack_into('<HHI', r, 32, fields.second_owner, 1, fields.second_id)
    for off in (40, 48, 56):
        struct.pack_into('<HHI', r, off, 65535, 0, 4294967295)
    struct.pack_into('<I', r, 80, sequence)
    struct.pack_into('<HHI', r, 88, fields.owner, 1, fields.unit_id)
    struct.pack_into('<HHI', r, 96, fields.second_owner, 1, fields.second_id)
    return bytes(r)
