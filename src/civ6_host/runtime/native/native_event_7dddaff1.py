"""DiplomacyDeclareWar notification, common empty-subscriber receiver only."""
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
from pathlib import Path
import struct
from civ6_host.runtime.native.native_application_mirror import decode_scalar
from civ6_host.runtime.native.native_source_cache import load_pinned_json
EVENT_KIND, RECORD_TYPE, RECORD_SIZE = (2111680497, 127, 112)
PROOF_SHA256 = '38e5cbae984cf0a594a104064845834342f1249403bdd3e7b158667213c3dc61'
PADDING_POLICY = 'zero-unread-empty-receiver-payload'
ROOT = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_event_7dddaff1.py')))).resolve().parents[1]

def verify_source_evidence():
    p = load_pinned_json(ROOT / 'evidence/native-event-7dddaff1' / (PROOF_SHA256 + '.json'), PROOF_SHA256)
    from civ6_host.runtime.native.native_host_event_registry import EXE_EVENT_CALLBACKS
    if p['schema'] != 'civ6rl.native_event_7dddaff1.static.v1' or EXE_EVENT_CALLBACKS[EVENT_KIND] != 1326224 or p['captures']['callback']['code_sha256'] != '4053736f0f475c93560491bf591e6d48d8424109d25b50fc1cff9f5754cf0411' or (p['captures']['writer']['code_sha256'] != 'b7fe4064e5529eb96a6b02a4dd187031f4affd1fe5d5c4db8ee20e24de7b93f6') or (p['contract']['defined_payload'] != {'sequence': 80, 'D6': 88, 'A1FBC': 92, 'zero_qword': 104}) or (p['contract']['undefined_ranges'] != ((84, 88), (96, 104))) or (p['contract']['selector_consumed'] is not False) or (p['contract']['padding_policy'] != PADDING_POLICY):
        raise RuntimeError('DeclareWar source contract changed')
    load_pinned_json(ROOT / p['parent']['path'], p['parent']['sha256'])
    return p

def receiver_row():
    p = verify_source_evidence()
    r = p['receiver']
    if r['record_type'] != RECORD_TYPE or r['record_size'] != RECORD_SIZE or r['name'] != 'GameCoreEvent::DiplomacyDeclareWar' or (r['row_va'] != '0x1412c8080') or (r['handler_va'] != '0x1400d8e90') or (r['handler_sha256'] != '25d8aa6153b5e1030aa0ff115c72d351433049b79896f4fa912c279c85356c40') or (r['pre_hook'] is not None) or (r['post_hook'] is not None) or (r['subscriber_count'] != 0) or (r['subscriber_array'] != 0) or (r['state_flags_low2'] != 0):
        raise RuntimeError('DeclareWar receiver contract changed')
    return dict(event_name=r['name'], handler_va=r['handler_va'], handler_body_sha256=r['handler_sha256'], record_sizes={RECORD_SIZE})

def decode_fields(raw_fields):
    verify_source_evidence()
    if type(raw_fields) is not dict or set(raw_fields) != {2716180809, 3606901732, 2717631346}:
        raise ValueError('DeclareWar requires exact scalar envelope')
    return tuple((decode_scalar(raw_fields[k], tag) for k, tag in ((2716180809, 3), (3606901732, 2), (2717631346, 2))))

def encode_record(sequence, fields, *, normalizer_transform_present, per_thread_hook_present, writer_metadata_callback_present, padding_policy, empty_receiver_state):
    from civ6_host.runtime.native.native_deferred_empty_profile import validate_empty_profile_record
    verify_source_evidence()
    if type(fields) is not tuple or len(fields) != 3 or any((type(v) is not int or not 0 <= v <= 4294967295 for v in fields)) or (type(sequence) is not int) or (not 1 <= sequence <= 2147483647):
        raise ValueError('DeclareWar exact scalar/sequence profile required')
    if normalizer_transform_present is not False or per_thread_hook_present is not False or writer_metadata_callback_present is not False or (padding_policy != PADDING_POLICY):
        raise ValueError('DeclareWar populated callbacks or unknown padding policy')
    if type(empty_receiver_state) is not dict or set(empty_receiver_state) != {'observer_registered', 'state_pointer_nonnull', 'pre_hook', 'post_hook', 'subscriber_count', 'state_flags'}:
        raise ValueError('DeclareWar requires actual complete receiver state')
    record = bytearray(RECORD_SIZE)
    struct.pack_into('<4I', record, 0, RECORD_SIZE, RECORD_TYPE, sequence, 0)
    validate_empty_profile_record(record, **empty_receiver_state)
    struct.pack_into('<2I', record, 16, 4294967295, 4294967295)
    for offset in (24, 32, 40, 48, 56):
        struct.pack_into('<HHI', record, offset, 65535, 0, 4294967295)
    struct.pack_into('<I', record, 80, sequence)
    struct.pack_into('<2I', record, 88, fields[1], fields[2])
    validate_empty_profile_record(record, **empty_receiver_state)
    return bytes(record)
