"""Bounded D857B21B position/unit/four-DWORD notification packing."""
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
EVENT_KIND, RECORD_TYPE, RECORD_SIZE = (3629625883, 147, 128)
POSITION_KEY, UNIT_KEY = (2353434172, 4032072631)
SELECTOR_KEY, VALUE_KEY, SECOND_KEY, EXTRA_KEY = (2716180809, 3606901732, 2717631346, 955421384)
_KEYS = {POSITION_KEY, UNIT_KEY, SELECTOR_KEY, VALUE_KEY, SECOND_KEY, EXTRA_KEY}
PROOF_SHA256 = 'd6cdcf4e3c114e3bfaebc3d054a989ba907eabc07abd833cd07ac14f96481ab0'
PADDING_POLICY = 'zero-unread-empty-receiver-payload'

def verify_source_evidence():
    if not PROOF_SHA256:
        raise RuntimeError('D857B21B complete source evidence is not yet pinned')
    from civ6_host.runtime.native.native_host_event_registry import EXE_EVENT_CALLBACKS
    from civ6_host.runtime.native.native_deferred_empty_profile import D857_RECEIVER_SHA256
    root = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_event_d857b21b.py')))).resolve().parents[1]
    proof = load_pinned_json(root / 'evidence/native-event-d857b21b' / (PROOF_SHA256 + '.json'), PROOF_SHA256)
    if proof['schema'] != 'civ6rl.native_event_d857b21b.static.v1' or proof['images'] != {'exe_sha256': 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63', 'core_sha256': 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'} or EXE_EVENT_CALLBACKS.get(EVENT_KIND) != 1347072 or (proof['parents']['receiver']['sha256'] != D857_RECEIVER_SHA256) or (proof['parents']['normalization_and_entity_observers']['sha256'] != '76fbbc97ae12a79799e828a832b7915fc39b555abcd4cd7b62ad74bf6722dd99') or (proof['parents']['position_normalization_and_core_caller']['sha256'] != 'd4d74903f64c7579fcece750f4d2d8323c0b8dd9c7cac35a32a87a58431365b1') or (set(proof['contract']['field_keys']) != _KEYS) or (proof['contract']['record']['type'] != RECORD_TYPE) or (proof['contract']['record']['size'] != RECORD_SIZE) or (proof['contract']['record']['payload_copy_size'] != 40) or (proof['contract']['record']['metadata_flag'] != 0) or (proof['verification'] != {'all_captured_instructions_match_pinned_pe': True, 'instructions_rechecked': 6864, 'parent_instructions_rechecked': 16103, 'callback_scan_instructions_rechecked': 20696}):
        raise RuntimeError('D857B21B pinned source identity changed')
    return proof

@dataclass(frozen=True)
class EventFields:
    position_bytes: bytes
    x: int
    y: int
    selector: int
    owner: int
    unit_id: int
    d6_value: int
    a1fbc_value: int
    scalar38f: int
    unit_type: int = 1

def _fields(fields):
    if not isinstance(fields, EventFields) or type(fields.position_bytes) is not bytes or len(fields.position_bytes) != 8 or (type(fields.x) is not int) or (type(fields.y) is not int) or (struct.unpack('<ii', fields.position_bytes) != (fields.x, fields.y)) or (type(fields.owner) is not int) or (not 0 <= fields.owner <= 65535) or (type(fields.unit_type) is not int) or (fields.unit_type != 1) or any((type(v) is not int or not 0 <= v <= 4294967295 for v in (fields.selector, fields.unit_id, fields.d6_value, fields.a1fbc_value, fields.scalar38f))):
        raise ValueError('D857B21B needs consistent coordinates, normalized unit and raw DWORDs')

def decode_fields(raw_fields, read):
    verify_source_evidence()
    if type(raw_fields) is not dict or set(raw_fields) != _KEYS or any((type(raw) is not bytes or len(raw) != 24 for raw in raw_fields.values())):
        raise ValueError('D857B21B requires exactly six typed fields')
    scalars = {key: decode_scalar(raw_fields[key], tag) for key, tag in ((SELECTOR_KEY, 3), (VALUE_KEY, 2), (SECOND_KEY, 2), (EXTRA_KEY, 2))}
    for key, expected_tag in ((POSITION_KEY, 0), (UNIT_KEY, 1024)):
        raw = raw_fields[key]
        tag = struct.unpack_from('<H', raw)[0]
        pointer, size, flags = struct.unpack_from('<QII', raw, 8)
        if tag != expected_tag or not pointer or size != 8 or (flags != 553648129):
            raise ValueError('D857B21B blob envelope is outside the proven profile')
    position = copy_eight_byte_variant(raw_fields[POSITION_KEY], read, expected_tag=0)
    descriptor = copy_eight_byte_variant(raw_fields[UNIT_KEY], read, expected_tag=1024)
    owner, _, identifier = struct.unpack('<HHI', descriptor)
    fields = EventFields(position, *struct.unpack('<ii', position), scalars[SELECTOR_KEY], owner, identifier, scalars[VALUE_KEY], scalars[SECOND_KEY], scalars[EXTRA_KEY])
    _fields(fields)
    return fields

def encode_record(sequence, fields, *, normalizer_transform_present, per_thread_hook_present, writer_metadata_callback_present, entity_listener_count, padding_policy, empty_receiver_state):
    verify_source_evidence()
    validate_sequence(sequence)
    _fields(fields)
    if normalizer_transform_present is not False or per_thread_hook_present is not False or writer_metadata_callback_present is not False:
        raise ValueError('D857B21B requires absent optional hooks/services')
    if type(entity_listener_count) is not int or entity_listener_count != 0:
        raise ValueError('D857B21B requires actual empty entity listeners')
    if padding_policy != PADDING_POLICY:
        raise ValueError('D857B21B requires explicit unread-gap handling')
    if type(empty_receiver_state) is not dict or set(empty_receiver_state) != {'observer_registered', 'state_pointer_nonnull', 'pre_hook', 'post_hook', 'subscriber_count', 'state_flags'}:
        raise ValueError('D857B21B requires the actual complete empty receiver state')
    record = bytearray(RECORD_SIZE)
    struct.pack_into('<IIII', record, 0, RECORD_SIZE, RECORD_TYPE, sequence, 0)
    validate_empty_profile_record(record, **empty_receiver_state)
    record[16:24] = b'\xff' * 8
    record[24:64] = bytes.fromhex('ffff0000ffffffff') * 5
    struct.pack_into('<I', record, 80, sequence)
    record[88:96] = fields.position_bytes
    struct.pack_into('<HHIIIII', record, 96, fields.owner, 1, fields.unit_id, fields.d6_value, fields.a1fbc_value, fields.selector, fields.scalar38f)
    return bytes(record)
