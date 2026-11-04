"""DiplomacyMeetMajors: reuse the proven descriptor/two-DWORD transport.

Core's internal dispatch has already run. Only EXE row83 serialization and its
verified empty receiver profile are reproduced; no meeting rule is implemented.
"""
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
from pathlib import Path
import struct
from civ6_host.runtime.native import native_event_133d411c as sibling
from civ6_host.runtime.native.native_deferred_empty_profile import validate_empty_profile_record
from civ6_host.runtime.native.native_source_cache import load_pinned_json
EVENT_KIND, RECORD_TYPE, RECORD_SIZE = (2301564700, 131, 96)
SELECTOR_KEY, VALUE_KEY, SECOND_KEY, UNIT_KEY = (sibling.SELECTOR_KEY, sibling.VALUE_KEY, sibling.SECOND_KEY, sibling.UNIT_KEY)
EventFields = sibling.EventFields
PROOF_SHA256 = '7b1f3b0e5e0ec8da6ad9a6801ccbd7f61314117f7cc75055c14d4146708dcad2'
ROOT = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_event_892f171c.py')))).resolve().parents[1]

def verify_source_evidence():
    proof = load_pinned_json(ROOT / 'evidence/native-event-892f171c' / (PROOF_SHA256 + '.json'), PROOF_SHA256)
    if proof.get('schema') != 'civ6rl.native_event_892f171c.static.v1' or proof.get('images') != {'exe_sha256': 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63', 'core_sha256': 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'} or proof['captures']['callback']['code_sha256'] != '76965bdcb6e4534a8e4f7ed8f0e0ddd52e5bf0ea88615168c67bad2b3152922d' or (proof['captures']['writer']['code_sha256'] != 'e9345dd56acda0657d5a3fcff5cac300a6d2272709666f38c326a1861b63b963'):
        raise RuntimeError('892F171C source identity changed')
    sibling.verify_source_evidence()
    return proof

def decode_fields(raw_fields, read):
    verify_source_evidence()
    return sibling.decode_fields(raw_fields, read)

def encode_record(sequence, fields, *, normalizer_transform_present, per_thread_hook_present, writer_metadata_callback_present, entity_listener_count, empty_receiver_state):
    verify_source_evidence()
    if normalizer_transform_present is not False or per_thread_hook_present is not False or writer_metadata_callback_present is not False:
        raise ValueError('892F171C optional service paths are not admitted')
    if type(entity_listener_count) is not int or entity_listener_count != 0:
        raise ValueError('892F171C requires actual empty entity listeners')
    if type(empty_receiver_state) is not dict or set(empty_receiver_state) != {'observer_registered', 'state_pointer_nonnull', 'pre_hook', 'post_hook', 'subscriber_count', 'state_flags'}:
        raise ValueError('892F171C requires the complete receiver state')
    shape = bytearray(RECORD_SIZE)
    struct.pack_into('<II', shape, 0, RECORD_SIZE, RECORD_TYPE)
    validate_empty_profile_record(shape, **empty_receiver_state)
    record = bytearray(sibling._encode_source_record(sequence, fields))
    struct.pack_into('<I', record, 4, RECORD_TYPE)
    validate_empty_profile_record(record, **empty_receiver_state)
    return bytes(record)
