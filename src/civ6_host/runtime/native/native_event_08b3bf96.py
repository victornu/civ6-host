"""DiplomacyMeetMajorMinor: proven 133D serialization with its own row82."""
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
from pathlib import Path
import struct
from civ6_host.runtime.native import native_event_133d411c as sibling
from civ6_host.runtime.native.native_deferred_empty_profile import validate_empty_profile_record
from civ6_host.runtime.native.native_source_cache import load_pinned_json
EVENT_KIND, RECORD_TYPE, RECORD_SIZE = (145997718, 130, 96)
SELECTOR_KEY, VALUE_KEY, SECOND_KEY, UNIT_KEY = (sibling.SELECTOR_KEY, sibling.VALUE_KEY, sibling.SECOND_KEY, sibling.UNIT_KEY)
EventFields = sibling.EventFields
PROOF_SHA256 = 'd3d9f682412a1220e5b5d1788b4e497d4af6cf939b98ed7c4693fa958b944b66'
ROOT = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_event_08b3bf96.py')))).resolve().parents[1]

def verify_source_evidence():
    if not PROOF_SHA256:
        raise RuntimeError('08B3BF96 complete source proof has not been pinned')
    proof = load_pinned_json(ROOT / 'evidence/native-event-08b3bf96' / (PROOF_SHA256 + '.json'), PROOF_SHA256)
    if proof.get('schema') != 'civ6rl.native_event_08b3bf96.static.v1' or proof.get('images') != {'exe_sha256': 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63', 'core_sha256': 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'} or proof.get('captures', {}).get('callback', {}).get('code_sha256') != '6b1acf35c78be0975d7c9c24abb47564dc559ae3e0880755bcfd6ed75aac9465' or (proof.get('captures', {}).get('writer', {}).get('code_sha256') != '1c5bdbc6b369b08ec5751c932df5e75bd73e6e724aeea68b47923c6447b29935'):
        raise RuntimeError('08B3BF96 source identity changed')
    sibling.verify_source_evidence()
    return proof

def decode_fields(raw_fields, read):
    verify_source_evidence()
    return sibling.decode_fields(raw_fields, read)

def encode_record(sequence, fields, *, normalizer_transform_present, per_thread_hook_present, writer_metadata_callback_present, entity_listener_count, empty_receiver_state):
    verify_source_evidence()
    if normalizer_transform_present is not False or per_thread_hook_present is not False or writer_metadata_callback_present is not False:
        raise ValueError('08B3BF96 optional hook/transform paths are not admitted')
    if type(entity_listener_count) is not int or entity_listener_count != 0:
        raise ValueError('08B3BF96 requires the actual empty entity listener profile')
    if type(empty_receiver_state) is not dict or set(empty_receiver_state) != {'observer_registered', 'state_pointer_nonnull', 'pre_hook', 'post_hook', 'subscriber_count', 'state_flags'}:
        raise ValueError('08B3BF96 requires the complete empty receiver state')
    shape = bytearray(RECORD_SIZE)
    struct.pack_into('<II', shape, 0, RECORD_SIZE, RECORD_TYPE)
    validate_empty_profile_record(shape, **empty_receiver_state)
    record = bytearray(sibling._encode_source_record(sequence, fields))
    struct.pack_into('<I', record, 4, RECORD_TYPE)
    validate_empty_profile_record(record, **empty_receiver_state)
    return bytes(record)
