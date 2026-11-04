"""Exact source-backed codec for route-removal host kind 0x67E685CA / D6."""
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
from pathlib import Path
import struct
KIND = 1743160778
RECORD_TYPE = 214
RECORD_SIZE = 96
POSITION_KEY, SELECTOR_KEY, VALUE_KEY = (2353434172, 2716180809, 3606901732)
PROOF_SHA256 = 'ff79a47e0977ec86f59e4b25ef6622d0742eb10038ff1a4602105883943fcc14'
EXE_SHA256 = 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63'
CALLBACK_SHA256 = '1bcffdfe25faf4af754697f00ae8a9bc164d4fc1dc2e22f09c199e204eb5cc24'
WRITER_SHA256 = 'e1c96bf5b8c13432b76837a0fe8c6370cc2a1caeab19868981a0ab7f380f941c'
HANDLER_SHA256 = '302139c8535e3c9c8125e7af07a831a63eba57d36bfbfc8d99c519bad1be9d52'

def verify_source_evidence():
    from civ6_host.runtime.native.native_source_cache import load_pinned_json
    root = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_trade_route_position_events.py')))).resolve().parents[1]
    proof = load_pinned_json(root / 'evidence/native-trade-route-position-events' / (PROOF_SHA256 + '.json'), PROOF_SHA256)
    if proof.get('schema') != 'civ6rl.native_trade_route_position_events.static.v1' or proof.get('native_execution') is not False or proof.get('images', {}).get('exe_sha256') != EXE_SHA256 or (proof.get('registry', {}).get('binding', {}).get('callback_va') != '0x140154270') or (proof.get('captures', {}).get('callback', {}).get('code_sha256') != CALLBACK_SHA256) or (proof.get('captures', {}).get('writer', {}).get('code_sha256') != WRITER_SHA256) or (proof.get('receiver', {}).get('handler_sha256') != HANDLER_SHA256) or (proof.get('receiver', {}).get('row_index') != RECORD_TYPE) or (proof.get('receiver', {}).get('name') != 'GameCoreEvent::TradeRouteRemovedFromMap') or (proof.get('contract', {}).get('payload') != {'sequence': 80, 'D6': 84, 'position': 88}):
        raise RuntimeError('67E685CA/D6 source identity changed')
    return proof

def receiver_row():
    receiver = verify_source_evidence()['receiver']
    return {'event_name': receiver['name'], 'handler_va': receiver['handler_va'], 'handler_body_sha256': receiver['handler_sha256'], 'record_sizes': {RECORD_SIZE}}

def decode_fields(raw_fields, reader):
    verify_source_evidence()
    from civ6_host.runtime.native.native_position_value_event_family import decode_fields as decode_position_value
    if type(raw_fields) is not dict or set(raw_fields) != {POSITION_KEY, SELECTOR_KEY, VALUE_KEY}:
        raise ValueError('67E685CA requires its exact three-field descriptor')
    return decode_position_value(raw_fields, reader)

def encode_record(sequence, fields, *, normalizer_transform_present, per_thread_hook_present, writer_metadata_callback_present, entity_listener_count, empty_receiver_state):
    verify_source_evidence()
    from civ6_host.runtime.native.native_player_event_domains import validate_sequence
    from civ6_host.runtime.native.native_position_value_event_family import EventFields
    from civ6_host.runtime.native.native_position_value_event_family import _fields
    from civ6_host.runtime.native.native_position_value_event_family import encode_record as encode_family
    if normalizer_transform_present is not False or per_thread_hook_present is not False or writer_metadata_callback_present is not False:
        raise ValueError('67E685CA requires the pinned absent-hook/service profile')
    if type(entity_listener_count) is not int or entity_listener_count != 0:
        raise ValueError('67E685CA requires zero entity listeners')
    if type(empty_receiver_state) is not dict or set(empty_receiver_state) != {'observer_registered', 'state_pointer_nonnull', 'pre_hook', 'post_hook', 'subscriber_count', 'state_flags'}:
        raise ValueError('67E685CA requires the complete receiver state')
    validate_sequence(sequence)
    _fields(fields)
    if not isinstance(fields, EventFields):
        raise ValueError('67E685CA requires source-decoded position/value fields')
    record = bytearray(encode_family(2980214136, sequence, fields, normalizer_transform_present=False, per_thread_hook_present=False, writer_metadata_callback_present=False, entity_listener_count=0, empty_receiver_state=empty_receiver_state))
    struct.pack_into('<I', record, 4, RECORD_TYPE)
    struct.pack_into('<I', record, 84, fields.value)
    record[88:96] = fields.position_bytes
    from civ6_host.runtime.native.native_deferred_empty_profile import validate_empty_profile_record
    validate_empty_profile_record(record, **empty_receiver_state)
    return bytes(record)
