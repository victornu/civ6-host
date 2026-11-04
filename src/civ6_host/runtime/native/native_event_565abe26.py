"""Native PantheonFounded queue adapter for the captured empty UI receiver."""
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
from pathlib import Path
import struct
from civ6_host.runtime.native.native_application_mirror import decode_scalar
from civ6_host.runtime.native.native_source_cache import load_pinned_json
EVENT_KIND = 1448787494
CALLBACK_RVA = 1354592
WRITER_RVA = 1281376
RECORD_SIZE, RECORD_TYPE = (96, 195)
SELECTOR_KEY, VALUE_KEY, D6_KEY = (2716180809, 2717631346, 3606901732)
PIN = '3a0e3112cda6817c2449ae5af75e46d71115e553d443be4c787f3e29e5b82f91'
PROOF = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_event_565abe26.py')))).resolve().parents[1] / 'evidence/native-event-565abe26' / f'{PIN}.json'

def verify_source():
    proof = load_pinned_json(PROOF, PIN)
    if proof['schema'] != 'civ6rl.native_event_565abe26.static.v1' or proof['images']['exe_sha256'] != 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63' or proof['registration']['entry']['kind'] != EVENT_KIND or (proof['registration']['entry']['callback_va'] != '0x14014ab60') or (proof['captures']['callback']['fragments'][0]['raw_sha256'] != 'fc66156d09fb2cc25f5c47db5c72972f8e7abb97c9e3b7c4af1b2db92509164f') or (proof['captures']['writer']['fragments'][0]['raw_sha256'] != '2e0eaafe2e8f72b079b40ab94cda4afdde9c2e5ec6baeb9bf2882eb68d4bca9c') or (proof['captures']['normalizer']['fragments'][0]['raw_sha256'] != 'c757d2f0c927f36e058ff5e57350a80beac1db2a89d3940fcb5e89c05545f23e') or (proof['contract']['record']['size'] != RECORD_SIZE) or (proof['contract']['record']['type'] != RECORD_TYPE) or (proof['contract']['record']['payload_size'] != 12) or (proof['contract']['record']['metadata_flag'] != 4) or (proof['consumer']['handler_va'] != '0x1400da8d0') or (proof['empty_receiver_reference']['sha256'] != '73f2e5d542ce2914094abe762f9a8f7234da9374f23c0ad41f3e22e183ec7cc8'):
        raise RuntimeError('PantheonFounded source proof changed')

def decode_fields(fields):
    """Preserve source DWORDs; never copy scalar storage padding."""
    verify_source()
    if type(fields) is not dict or set(fields) != {SELECTOR_KEY, VALUE_KEY, D6_KEY}:
        raise ValueError('PantheonFounded requires its exact three scalar fields')
    selector = decode_scalar(fields[SELECTOR_KEY], 3)
    value = decode_scalar(fields[VALUE_KEY], 2)
    d6 = decode_scalar(fields[D6_KEY], 2)
    return (selector, value, d6)

def encode_record(sequence, fields, *, empty_receiver_state, thread_hook_present=False, writer_metadata_callback_present=False):
    """Copy the initialized twelve-byte payload into a zero-allocated record."""
    _, value, d6 = decode_fields(fields)
    if type(sequence) is not int or not 1 <= sequence <= 4294967295:
        raise ValueError('PantheonFounded sequence must be a nonzero uint32')
    if thread_hook_present is not False or writer_metadata_callback_present is not False:
        raise ValueError('PantheonFounded hook-present paths are not supported')
    record = bytearray(RECORD_SIZE)
    struct.pack_into('<IIII', record, 0, RECORD_SIZE, RECORD_TYPE, sequence, 0)
    for offset in (16, 20, 28, 36, 44, 52, 60):
        struct.pack_into('<I', record, offset, 4294967295)
    for offset in (24, 32, 40, 48, 56):
        struct.pack_into('<H', record, offset, 65535)
    struct.pack_into('<I', record, 72, 4)
    struct.pack_into('<III', record, 80, sequence, d6, value)
    from civ6_host.runtime.native.native_deferred_empty_profile import validate_empty_profile_record
    validate_empty_profile_record(record, **empty_receiver_state)
    return bytes(record)
