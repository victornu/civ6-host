"""Source-bounded TradeRouteActivityChanged pair codec (D7)."""
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
from dataclasses import dataclass
from pathlib import Path
import struct
from civ6_host.runtime.native.native_application_mirror import decode_scalar
from civ6_host.runtime.native.native_player_event_domains import validate_sequence
from civ6_host.runtime.native.native_source_cache import load_pinned_json
EVENT_KIND, RECORD_TYPE, RECORD_SIZE = (1567648150, 215, 112)
FIRST_KEY, SECOND_KEY, SELECTOR_KEY = (594779970, 1416933332, 2716180809)
FIELD_KEYS = frozenset((FIRST_KEY, SECOND_KEY, SELECTOR_KEY))
PROOF_SHA256 = '5e1e283aea11f436b0e14885ba8a781291a35a1f0206697f4cf5df6435135c46'
NORMALIZER_PROOF_SHA256 = 'bb363e13920412a44fde541151de7cc69047a9706773a7be939dc646ef4e687e'
EXE_SHA256 = 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63'
CORE_SHA256 = 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'
CALLBACK_SHA256 = 'ca66831367ec2d9b6145529c5b6eadb858fc61bdeb10c8f2fe23d1697599fb38'
WRITER_SHA256 = '81c7715160039e72b9bbcfc29fb2af0c6e4ed6f145748c5ca6c1d39d69d9251a'
HANDLER_SHA256 = 'f75be9d7da809d71db55f7eca720f9aa642cf7d07eda0e2f9487404b4bf781ef'
PADDING_POLICY = 'zero-uninitialized-trade-route-descriptor-gaps-empty-receiver'

@dataclass(frozen=True)
class EventFields:
    selector: int
    first_owner: int
    first_id: int
    second_owner: int
    second_id: int

def verify_source_evidence():
    root = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_event_5d706996.py')))).resolve().parents[1]
    proof = load_pinned_json(root / 'evidence/native-event-5d706996' / (PROOF_SHA256 + '.json'), PROOF_SHA256)
    if proof.get('schema') != 'civ6rl.native_event_5d706996.static.v1' or proof.get('native_execution') is not False or proof.get('images') != {'exe_sha256': EXE_SHA256, 'core_sha256': CORE_SHA256} or (proof.get('registry', {}).get('binding', {}).get('callback_va') != '0x140153fc0') or (proof.get('captures', {}).get('callback', {}).get('code_sha256') != CALLBACK_SHA256) or (proof.get('captures', {}).get('writer', {}).get('code_sha256') != WRITER_SHA256) or (proof.get('parents', {}).get('normalizer99', {}).get('sha256') != NORMALIZER_PROOF_SHA256) or (proof.get('receiver', {}).get('record_type') != RECORD_TYPE) or (proof.get('receiver', {}).get('record_size') != RECORD_SIZE) or (proof.get('receiver', {}).get('name') != 'GameCoreEvent::TradeRouteActivityChanged') or (proof.get('receiver', {}).get('handler_sha256') != HANDLER_SHA256) or (proof.get('contract', {}).get('record', {}).get('uninitialized_ranges') != ((84, 88), (92, 96))):
        raise RuntimeError('5D706996 source identity changed')
    return proof

def receiver_row():
    receiver = verify_source_evidence()['receiver']
    return {'event_name': receiver['name'], 'handler_va': receiver['handler_va'], 'handler_body_sha256': receiver['handler_sha256'], 'record_sizes': {RECORD_SIZE}}

def _copy_descriptor(raw, reader):
    if type(raw) is not bytes or len(raw) != 24:
        raise ValueError('5D706996 descriptors must be complete 24-byte variants')
    pointer, size, flags = struct.unpack_from('<QII', raw, 8)
    if struct.unpack_from('<H', raw)[0] != 1024 or not pointer or size != 8 or (flags != 553648129):
        raise ValueError('5D706996 descriptor is outside its pinned borrowed-blob envelope')
    copied = reader(pointer, 8)
    if type(copied) not in (bytes, bytearray, memoryview) or len(copied) != 8:
        raise ValueError('5D706996 descriptor copy was incomplete')
    owner, _ignored_input_type, identifier = struct.unpack('<HHI', bytes(copied))
    return (owner, identifier)

def _validate_fields(fields):
    if not isinstance(fields, EventFields):
        raise ValueError('5D706996 requires its decoded descriptor pair')
    if type(fields.selector) is not int or not 0 <= fields.selector <= 4294967295:
        raise ValueError('5D706996 selector must be a raw uint32')
    for value in (fields.first_owner, fields.second_owner):
        if type(value) is not int or not 0 <= value <= 65535:
            raise ValueError('5D706996 owners must be uint16')
    for value in (fields.first_id, fields.second_id):
        if type(value) is not int or not 0 <= value <= 4294967295:
            raise ValueError('5D706996 identifiers must be uint32')

def decode_fields(raw_fields, reader):
    verify_source_evidence()
    if type(raw_fields) is not dict or set(raw_fields) != FIELD_KEYS or any((type(raw) is not bytes or len(raw) != 24 for raw in raw_fields.values())):
        raise ValueError('5D706996 requires exactly two descriptors and one selector')
    selector = decode_scalar(raw_fields[SELECTOR_KEY], 3)
    for key in (FIRST_KEY, SECOND_KEY):
        raw = raw_fields[key]
        ptr, size, flags = struct.unpack_from('<QII', raw, 8)
        if struct.unpack_from('<H', raw)[0] != 1024 or not ptr or size != 8 or (flags != 553648129):
            raise ValueError('5D706996 has an unverified descriptor envelope')
    first_owner, first_id = _copy_descriptor(raw_fields[FIRST_KEY], reader)
    second_owner, second_id = _copy_descriptor(raw_fields[SECOND_KEY], reader)
    fields = EventFields(selector, first_owner, first_id, second_owner, second_id)
    _validate_fields(fields)
    return fields

def encode_record(sequence, fields, *, normalizer_transform_present, per_thread_hook_present, writer_metadata_callback_present, entity_listener_count, padding_policy, empty_receiver_state):
    verify_source_evidence()
    _validate_fields(fields)
    validate_sequence(sequence)
    if any((value is not False for value in (normalizer_transform_present, per_thread_hook_present, writer_metadata_callback_present))):
        raise ValueError('5D706996 requires absent optional transform and callbacks')
    if type(entity_listener_count) is not int or entity_listener_count != 0:
        raise ValueError('5D706996 requires zero entity listeners')
    if padding_policy != PADDING_POLICY:
        raise ValueError('5D706996 requires explicit zeroing of unread callback stack gaps')
    if type(empty_receiver_state) is not dict or set(empty_receiver_state) != {'observer_registered', 'state_pointer_nonnull', 'pre_hook', 'post_hook', 'subscriber_count', 'state_flags'}:
        raise ValueError('5D706996 requires the complete actual empty receiver state')
    record = bytearray(RECORD_SIZE)
    struct.pack_into('<IIII', record, 0, RECORD_SIZE, RECORD_TYPE, sequence, 0)
    struct.pack_into('<II', record, 16, 4294967295, 4294967295)
    for offset in (24, 32, 40, 48, 56):
        struct.pack_into('<HHI', record, offset, 65535, 0, 4294967295)
    struct.pack_into('<Q', record, 64, 0)
    struct.pack_into('<I', record, 72, 0)
    record[76:80] = bytes(4)
    struct.pack_into('<I', record, 80, sequence)
    struct.pack_into('<i', record, 88, fields.first_owner if fields.first_owner < 32768 else fields.first_owner - 65536)
    struct.pack_into('<HHI', record, 96, fields.first_owner, 2, fields.first_id)
    struct.pack_into('<HHI', record, 104, fields.second_owner, 2, fields.second_id)
    from civ6_host.runtime.native.native_deferred_empty_profile import validate_empty_profile_record
    validate_empty_profile_record(record, **empty_receiver_state)
    return bytes(record)
