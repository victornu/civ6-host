"""Official GreatWorkCreated notification: native plot snapshot, original FIFO."""
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
from contextlib import contextmanager
from pathlib import Path
import struct
from civ6_host.runtime.native.native_source_cache import load_pinned_json
EVENT_KIND, RECORD_TYPE, RECORD_SIZE = (443673072, 220, 160)
PROOF_SHA256 = '123a32d1f9de091d72a04787f061a460a55a7c0f277305c7acc9dc11c0dd95a6'
PROOF_PATH = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_event_great_work.py')))).resolve().parents[1] / 'evidence/native-event1a71e9f0' / (PROOF_SHA256 + '.json')

def verify_source():
    p = load_pinned_json(PROOF_PATH, PROOF_SHA256)
    if p['schema'] != 'civ6rl.native_event1a71e9f0.static.v1' or p['images']['exe_sha256'] != 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63' or p['images']['core_sha256'] != 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3' or (p['contract']['kind'] != EVENT_KIND) or (p['contract']['record_type'] != RECORD_TYPE) or (p['contract']['record_size'] != RECORD_SIZE) or (p['contract']['native_flag148_called'] is not False):
        raise RuntimeError('GreatWorkCreated source identity differs')
    return p

def receiver_row():
    p = verify_source()
    r = p['receiver']['receiver']
    row = r['row']
    if row['record_type'] != RECORD_TYPE or row['record_size'] != RECORD_SIZE or row['event_name']['text'] != 'GameCoreEvent::GreatWorkCreated' or (tuple(row['handler_direct_call_sequence']) != ('call 0x14098a780', 'call 0x1400dc0d0', 'call 0x14098a7b0')) or (RECORD_TYPE in r['token_hooked_record_types']):
        raise RuntimeError('GreatWorkCreated empty receiver differs')
    return dict(event_name=row['event_name']['text'], handler_va=row['handler_va'], handler_body_sha256=row['handler_body_sha256'], record_sizes={RECORD_SIZE})

def decode_fields(raw_fields, read):
    from civ6_host.runtime.native.native_event_5d0f4014 import decode_fields as common
    from civ6_host.runtime.native.native_host_events import copy_eight_byte_variant
    verify_source()
    if type(raw_fields) is not dict or set(raw_fields) != {2353434172, 2716180809, 2717631346, 3606901732, 4032072631}:
        raise ValueError('GreatWorkCreated field set differs')
    fields = common({k: v for k, v in raw_fields.items() if k != 4032072631}, read)
    descriptor = copy_eight_byte_variant(raw_fields[4032072631], read, expected_tag=1024)
    return (fields, descriptor)

def encode_record(sequence, fields, descriptor, values):
    from civ6_host.runtime.native.native_event_07c83dae import _fields
    verify_source()
    _fields(fields)
    if type(sequence) is not int or not 1 <= sequence <= 2147483647:
        raise ValueError('GreatWorkCreated sequence differs')
    if type(descriptor) is not bytes or len(descriptor) != 8:
        raise ValueError('GreatWorkCreated descriptor differs')
    if type(values) is not dict or set(values) != {'owner', 'city_id', 'district_id'} or type(values['owner']) is not int or (not -128 <= values['owner'] <= 127) or any((type(values[k]) is not int or not 0 <= values[k] <= 4294967295 for k in ('city_id', 'district_id'))):
        raise ValueError('GreatWorkCreated requires actual native snapshot values')
    record = bytearray(RECORD_SIZE)
    struct.pack_into('<IIII', record, 0, RECORD_SIZE, RECORD_TYPE, sequence, 0)
    record[16:24] = b'\xff' * 8
    record[24:64] = bytes.fromhex('ffff0000ffffffff') * 5
    struct.pack_into('<I', record, 80, sequence)
    record[88:96] = fields['position_bytes']
    struct.pack_into('<HHI', record, 96, values['owner'] & 65535, 2, values['city_id'])
    struct.pack_into('<HHI', record, 104, 65535, 3, 4294967295)
    struct.pack_into('<Ii', record, 116, fields['source_value'], values['owner'])
    struct.pack_into('<I', record, 136, fields['descriptor_tail'])
    record[144:152] = descriptor
    return bytes(record)

@contextmanager
def produce_record_lease(sequence, core, context, fields, descriptor, *, read=None, native_api=None, normalizer_transform_present, thread_hook_present, writer_metadata_callback_present, padding_policy, empty_receiver_state):
    from civ6_host.runtime.native.native_deferred_empty_profile import validate_empty_profile_record
    from civ6_host.runtime.native.native_event_07c83dae import plot_snapshot
    verify_source()
    if normalizer_transform_present is not False or thread_hook_present is not False or writer_metadata_callback_present is not False or (padding_policy != 'zero-unread-empty-receiver'):
        raise ValueError('GreatWorkCreated hooks or source padding profile not qualified')
    shape = encode_record(sequence, fields, descriptor, dict(owner=0, city_id=0, district_id=0))
    validate_empty_profile_record(shape, **empty_receiver_state)
    with plot_snapshot(core, context, fields, read=read, native_api=native_api, include_flag148=False) as values:
        record = encode_record(sequence, fields, descriptor, values)
        validate_empty_profile_record(record, **empty_receiver_state)
        yield record
