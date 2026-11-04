"""UnitActivate's two-key producer under the actual empty row49.

Missing position has a native zero initializer. Missing boolean does not: its
byte and the stack padding may be zeroed only as unread, unobserved payload.
"""
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
from dataclasses import dataclass
from pathlib import Path
import struct
from civ6_host.runtime.native import native_event_981a9186 as _full
from civ6_host.runtime.native.native_application_mirror import decode_scalar
from civ6_host.runtime.native.native_source_cache import load_pinned_json
EVENT_KIND, RECORD_TYPE, RECORD_SIZE = (2551878022, 73, 112)
CALLBACK_RVA, QUEUE_WRITER_RVA = (1394928, 1233664)
SELECTOR_KEY, DESCRIPTOR_KEY = (2716180809, 4032072631)
ACTIVATION_SELECTOR = 2765815733
PADDING_POLICY = 'zero-unread-empty-receiver-payload'
UNDEFINED_RECORD_RANGES = ((84, 88), (108, 112))
PINNED_EVIDENCE_SHA256 = 'dea3dfa82a9924acb6d740d10d8de9d1c5b8a5f9f5caa6cec17f5aec201ab428'
SELECTOR_PROOF_SHA256 = '7d7fdd4f0c5c2a571203ab88fd374b036cc1325015607dd6f96f0e8a1f703e4c'
_PROOF = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_event_981a9186_short.py')))).resolve().parents[1] / 'evidence/native-event-981a9186-short' / (PINNED_EVIDENCE_SHA256 + '.json')

def verify_source_evidence():
    proof = load_pinned_json(_PROOF, PINNED_EVIDENCE_SHA256)
    if proof.get('schema') != 'civ6rl.native_event_981a9186_short.static.v1' or proof.get('exe_sha256') != 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63' or proof.get('core_sha256') != 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3' or (proof.get('registry', {}).get('registration', {}).get('callback_va') != '0x1401548f0') or (proof.get('targets', {}).get('writer') != '0x14012d300') or (proof.get('original_four_field_source_sha256') != _full.PINNED_EVIDENCE_SHA256) or (proof.get('receiver', {}).get('row_va') != '0x1412c7660') or (proof.get('receiver', {}).get('record_type') != RECORD_TYPE) or (proof.get('receiver', {}).get('record_size') != RECORD_SIZE) or (proof.get('receiver', {}).get('event_name') != 'GameCoreEvent::UnitActivate') or (proof.get('map_lookup_slot', {}).get('target') != '0x180745d00') or (tuple(proof.get('contract', {}).get('undefined_record_ranges', ())) != UNDEFINED_RECORD_RANGES):
        raise RuntimeError('Short UnitActivate source contract changed')
    for name, digest in {'callback': 'cc7a57b7c18744a1def5e42e74c667944322c6a5d97b05a85a6e1800e9660592', 'writer': 'dbab085336f9240bbe05c16aaebbead2faf565f0f3e2427076e6cf8203e7ed12', 'normalizer': 'c757d2f0c927f36e058ff5e57350a80beac1db2a89d3940fcb5e89c05545f23e', 'receiver_setup': 'dd0f3163afdab8600bdbe558bb51a9f2cf40c71b77a2e9f898bda019206cac74', 'handler': 'ea20e68e0bb503eec504450e34ca1872b8c440e9a933a9c7ef42497c55d3dc79', 'subscriber_dispatch': '326ad0582020365181be9ed3b3e0f595e1bf834ef24f5afdf167d9ae56292bca'}.items():
        if proof.get('captures', {}).get(name, {}).get('code_sha256') != digest:
            raise RuntimeError('Short UnitActivate body changed: ' + name)
    return proof

def verify_selector_source_evidence():
    """The selector is transported unchanged; it does not select a writer."""
    old = verify_source_evidence()
    proof = load_pinned_json(_PROOF.parents[1] / 'native-event-981a9186-short-selectors' / (SELECTOR_PROOF_SHA256 + '.json'), SELECTOR_PROOF_SHA256)
    contract = proof['contract']
    if proof['schema'] != 'civ6rl.native_event_981a9186_short.selectors.static.v1' or proof['images'] != {'exe_sha256': old['exe_sha256'], 'core_sha256': old['core_sha256']} or proof['parents']['existing_short_shape']['sha256'] != PINNED_EVIDENCE_SHA256 or (proof['kind'] != EVENT_KIND) or (proof['registry']['registration']['callback_va'] != '0x1401548f0') or (proof['map_lookup_slot'] != old['map_lookup_slot']) or (proof['receiver'] != old['receiver']) or (set(contract['input_keys']) != {SELECTOR_KEY, DESCRIPTOR_KEY}) or (contract['tags'] != {'A1E5A149': 3, 'F0548BB7': 1024}) or (contract['scalar_flags'] != 0) or (contract['descriptor_envelope'] != {'tag': 1024, 'size': 8, 'flags': 553648129, 'nonnull_pointer': True}) or (contract['selector_domain'] != (0, 4294967295)) or (contract['selector_partition'] != ({'condition': 'all_uint32', 'record_count': 1, 'record_size': RECORD_SIZE, 'record_type': RECORD_TYPE},)) or (contract['selector_dataflow'] != {'branch_on_value': False, 'load_va': '0x140154950', 'store_va': '0x140154958', 'normalized_offset': 4, 'record_offset': 104}) or (contract['owner_transport_domain'] != (0, 65535)) or (contract['id_transport_domain'] != (0, 4294967295)) or (contract['normalized_descriptor_type'] != 1) or (contract['record'] != {'type': RECORD_TYPE, 'size': RECORD_SIZE, 'payload_offset': 80, 'payload_size': 32, 'metadata_flag': 0, 'native_initialized_position': (96, 104), 'undefined_ranges': UNDEFINED_RECORD_RANGES, 'allocation_zero_ranges': ((76, 80),)}) or (proof['verification']['all_captured_instructions_match_pinned_pe'] is not True):
        raise RuntimeError('Short UnitActivate selector source contract changed')
    for name in ('callback', 'writer', 'normalizer', 'resolver', 'receiver_setup', 'handler', 'subscriber_dispatch'):
        if proof['captures'][name]['code_sha256'] != old['captures'][name]['code_sha256']:
            raise RuntimeError('Short UnitActivate selector body changed: ' + name)
    return proof

@dataclass(frozen=True)
class EventFields:
    selector: int
    descriptor_bytes: bytes
    owner: int
    item_id: int

def decode_fields(raw_fields, read):
    """Copy the only borrowed field; create no absent boolean observation."""
    verify_selector_source_evidence()
    if type(raw_fields) is not dict or set(raw_fields) != {SELECTOR_KEY, DESCRIPTOR_KEY} or any((type(raw) is not bytes or len(raw) != 24 for raw in raw_fields.values())):
        raise ValueError('Short UnitActivate requires exactly two complete typed fields')
    selector = decode_scalar(raw_fields[SELECTOR_KEY], 3)
    raw = raw_fields[DESCRIPTOR_KEY]
    pointer, size, flags = struct.unpack_from('<QII', raw, 8)
    if struct.unpack_from('<H', raw)[0] != 1024 or not pointer or size != 8 or (flags != 553648129):
        raise ValueError('Short UnitActivate descriptor envelope is unsupported')
    copied = read(pointer, 8)
    if not isinstance(copied, (bytes, bytearray, memoryview)) or len(copied) != 8:
        raise ValueError('Short UnitActivate descriptor copy is incomplete')
    descriptor = bytes(copied)
    owner, _ignored_input_type, item_id = struct.unpack('<HHI', descriptor)
    return EventFields(selector, descriptor, owner, item_id)

def _validate_empty_receiver(state):
    from civ6_host.runtime.native.native_deferred_empty_profile import validate_empty_profile_record
    expected = dict(observer_registered=False, state_pointer_nonnull=True, pre_hook=None, post_hook=None, subscriber_count=0, state_flags=0)
    if type(state) is not dict or state != expected or any((type(state[k]) is not type(v) for k, v in expected.items())):
        raise ValueError('Short UnitActivate requires the actual empty receiver state')
    shape = bytearray(RECORD_SIZE)
    struct.pack_into('<II', shape, 0, RECORD_SIZE, RECORD_TYPE)
    row = validate_empty_profile_record(shape, **state)
    if row['record_type'] != RECORD_TYPE or row['record_size'] != RECORD_SIZE or row['event_name'] != 'GameCoreEvent::UnitActivate' or (row['handler_va'] != '0x1400d7b10'):
        raise ValueError('Short UnitActivate requires the proven empty row49')

def encode_record(sequence, raw_fields, read, *, normalizer_transform_present, entity_listener_count, per_thread_hook_present, writer_metadata_callback_present, empty_receiver_state, padding_policy):
    """Validate the real receiver before reading storage or filling unread bytes.

The caller retains queue/capacity/sequence ownership. No Core call is omitted;
the raw map lookup is known to return NULL because the exact keyset excludes
the boolean. The encoded boolean byte is never a native or gameplay value.
"""
    verify_source_evidence()
    if normalizer_transform_present is not False or per_thread_hook_present is not False or writer_metadata_callback_present is not False or (type(entity_listener_count) is not int) or (entity_listener_count != 0):
        raise ValueError('Short UnitActivate optional services are outside the profile')
    if type(sequence) is not int or not 1 <= sequence <= 4294967295:
        raise ValueError('Short UnitActivate sequence must be a nonzero DWORD')
    if type(padding_policy) is not str or padding_policy != PADDING_POLICY:
        raise ValueError('Short UnitActivate requires explicit unread payload policy')
    _validate_empty_receiver(empty_receiver_state)
    fields = decode_fields(raw_fields, read)
    packed = _full.EventFields(fields.selector, fields.descriptor_bytes, fields.owner, fields.item_id, bytes(8), 0)
    return _full.encode_record(sequence, packed, normalizer_transform_present=False, per_thread_hook_present=False, writer_metadata_callback_present=False, padding_policy='headless-zero-uninitialized-stack')
