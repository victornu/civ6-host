"""ImprovementChanged transport using the original 1477A0 native query."""
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
from dataclasses import dataclass
from pathlib import Path
import struct
from civ6_host.runtime.native import native_event_a625c726 as shared
from civ6_host.runtime.native.native_application_mirror import decode_scalar
from civ6_host.runtime.native.native_deferred_empty_profile import validate_empty_profile_record
from civ6_host.runtime.native.native_host_events import copy_eight_byte_variant
from civ6_host.runtime.native.native_player_event_domains import validate_sequence
from civ6_host.runtime.native.native_source_cache import load_pinned_json
from civ6_host.runtime import improvement_change_profile as _improvement_source
EVENT_KIND, RECORD_TYPE, RECORD_SIZE = (816720445, 144, 144)
POSITION_KEY, SELECTOR_KEY = (2353434172, 2716180809)
PROOF_SHA256 = 'd54836daeec1c83378bbe12fc2545a1231f4e71a80901e8b0c7e4df721d4a009'
PADDING_POLICY = shared.PADDING_POLICY
NativeValues = shared.NativeValues

def verify_source_evidence():
    from civ6_host.runtime.native.native_deferred_empty_profile import THIRTY_AE_RECEIVER_SHA256
    from civ6_host.runtime.native.native_host_event_registry import EXE_EVENT_CALLBACKS
    root = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_event_30ae2a3d.py')))).resolve().parents[1]
    proof = load_pinned_json(root / 'evidence/native-event-30ae2a3d' / (PROOF_SHA256 + '.json'), PROOF_SHA256)
    if proof['schema'] != 'civ6rl.native_event_30ae2a3d.static.v1' or proof['images'] != {'exe_sha256': 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63', 'core_sha256': 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'} or EXE_EVENT_CALLBACKS.get(EVENT_KIND) != 1347520 or (proof['parents']['shared_plot_query']['sha256'] != shared.PROOF_SHA256) or (THIRTY_AE_RECEIVER_SHA256 != '547aa179ba9e21336a8e14ddb159306501a418588ddf3c45377445eab23c10c2') or (proof['parents']['receiver']['sha256'] != THIRTY_AE_RECEIVER_SHA256) or (proof['contract']['record'] != {'type': RECORD_TYPE, 'size': RECORD_SIZE, 'payload_offset': 80, 'payload_size': 56, 'metadata_flag': 0, 'undefined_ranges': ((84, 88),), 'allocation_zero_ranges': ((76, 80), (136, 144))}) or (set(proof['contract']['input_keys']) != {POSITION_KEY, SELECTOR_KEY}) or (proof['writer_comparison']['equal_after_only_header_type_normalization'] is not True) or (proof['writer_comparison']['writer_instruction_count'] != 95) or (proof['complete_callback_family_scan']['matches'] != ('0x140148fc0',)) or (proof['complete_callback_family_scan']['callback_count'] != 312) or (proof['captures']['query_helper']['code_sha256'] != '7f3c375ea2bcd67df0cc9db91a9b851a65c1f22891edf40aa72695de05a6b4f6') or (proof['verification']['all_captured_instructions_match_pinned_pe'] is not True):
        raise RuntimeError('30AE2A3D native producer proof changed')
    shared.verify_source_evidence()
    return proof

@dataclass(frozen=True)
class EventFields:
    position_bytes: bytes
    x: int
    y: int
    selector: int

def _fields(fields):
    if not isinstance(fields, EventFields) or type(fields.position_bytes) is not bytes or len(fields.position_bytes) != 8 or (type(fields.x) is not int) or (type(fields.y) is not int) or (struct.unpack('<ii', fields.position_bytes) != (fields.x, fields.y)) or (type(fields.selector) is not int) or (not 0 <= fields.selector <= 4294967295):
        raise ValueError('30AE2A3D requires a consistent native position and DWORD selector')

def decode_fields(raw_fields, read):
    verify_source_evidence()
    if type(raw_fields) is not dict or set(raw_fields) != {POSITION_KEY, SELECTOR_KEY} or any((type(raw) is not bytes or len(raw) != 24 for raw in raw_fields.values())):
        raise ValueError('30AE2A3D requires exactly position and selector variants')
    selector = decode_scalar(raw_fields[SELECTOR_KEY], 3)
    position = copy_eight_byte_variant(raw_fields[POSITION_KEY], read, expected_tag=0)
    fields = EventFields(position, *struct.unpack('<ii', position), selector)
    _fields(fields)
    return fields

def _profile(sequence, fields, *, normalizer_transform_present, thread_hook_present, writer_metadata_callback_present, entity_listener_count, padding_policy, empty_receiver_state):
    verify_source_evidence()
    _fields(fields)
    validate_sequence(sequence)
    if normalizer_transform_present is not False or thread_hook_present is not False or writer_metadata_callback_present is not False:
        raise ValueError('30AE2A3D requires absent optional transforms and callbacks')
    if type(entity_listener_count) is not int or entity_listener_count != 0:
        raise ValueError('30AE2A3D requires the closed empty entity listener profile')
    if padding_policy != PADDING_POLICY:
        raise ValueError('30AE2A3D requires the explicit unread payload gap policy')
    if type(empty_receiver_state) is not dict or set(empty_receiver_state) != {'observer_registered', 'state_pointer_nonnull', 'pre_hook', 'post_hook', 'subscriber_count', 'state_flags'}:
        raise ValueError('30AE2A3D requires its actual complete empty receiver state')
    shape = bytearray(RECORD_SIZE)
    struct.pack_into('<II', shape, 0, RECORD_SIZE, RECORD_TYPE)
    validate_empty_profile_record(shape, **empty_receiver_state)

def encode_record(sequence, fields, values, *, normalizer_transform_present, thread_hook_present, writer_metadata_callback_present, entity_listener_count, padding_policy, empty_receiver_state):
    _profile(sequence, fields, normalizer_transform_present=normalizer_transform_present, thread_hook_present=thread_hook_present, writer_metadata_callback_present=writer_metadata_callback_present, entity_listener_count=entity_listener_count, padding_policy=padding_policy, empty_receiver_state=empty_receiver_state)
    record = shared.pack_plot_snapshot_record(RECORD_TYPE, sequence, fields.position_bytes, values)
    validate_empty_profile_record(record, **empty_receiver_state)
    return record

def produce_record(sequence, core, context, fields, *, expected_civilization_hashes=None, normalizer_transform_present, thread_hook_present, writer_metadata_callback_present, entity_listener_count, padding_policy, empty_receiver_state, core_sha256='d7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3', **query_options):
    _improvement_source.ensure_source(core_sha256)
    profile = dict(normalizer_transform_present=normalizer_transform_present, thread_hook_present=thread_hook_present, writer_metadata_callback_present=writer_metadata_callback_present, entity_listener_count=entity_listener_count, padding_policy=padding_policy, empty_receiver_state=empty_receiver_state)
    _profile(sequence, fields, **profile)
    values = shared.query_native_values_at_position(core, context, fields.position_bytes, expected_civilization_hashes=expected_civilization_hashes, **query_options, core_sha256=core_sha256)
    return encode_record(sequence, fields, values, **profile)
