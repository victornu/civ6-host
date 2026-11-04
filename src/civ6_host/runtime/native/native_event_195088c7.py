"""Source-backed ResourceAddedToMap producer with a required Core query."""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import struct
from pathlib import Path
from civ6_host.runtime.native.native_application_mirror import decode_scalar
from civ6_host.runtime.native.native_feature_visibility_event import _query_plot_snapshot_word
from civ6_host.runtime.native.native_source_cache import load_pinned_json
EVENT_KIND, RECORD_TYPE, RECORD_SIZE = (424708295, 138, 96)
BLOB_KEY, SELECTOR_KEY = (2353434172, 2716180809)
_PROOF_SHA = 'e580afb23eba8366117ae51ac2127088210367b354bdfcc8e1c33bd44970acdb'
_PROOF = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_event_195088c7.py')))).resolve().parents[1] / 'evidence/native-event-195088c7' / f'{_PROOF_SHA}.json'
SCOPE_PROOF_SHA256 = '8bc470668bbe26352825de6af0a06400922385d06fcfc3e8b295f4bd1be86c39'

def verify_notification_scope(notification_counter: int, metadata_counter: int) -> None:
    """Admit this counter-independent producer, without applying B5 arithmetic.

    Its callback and writer never read N/M. The writer creates default metadata
    even inside a notification scope, and both counters remain unchanged.
    """
    proof = load_pinned_json(_resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_event_195088c7.py')))).resolve().parents[1] / 'evidence/native-resource-added-scope' / (SCOPE_PROOF_SHA256 + '.json'), SCOPE_PROOF_SHA256)
    if proof.get('schema') != 'civ6rl.native_resource_added_scope.static.v1' or proof.get('kind') != EVENT_KIND or proof['contract']['supported_event_kinds'] != (EVENT_KIND,) or (proof['contract']['record_type'] != RECORD_TYPE) or (proof['contract']['record_flag'] != 0) or (proof['contract']['counter_effect'] != 'preserve-N-and-M'):
        raise RuntimeError('Pinned ResourceAddedToMap scope contract changed')
    for value in (notification_counter, metadata_counter):
        if type(value) is not int or not 0 <= value <= 4294967295:
            raise ValueError('ResourceAddedToMap scope counters must be exact uint32')

def verify_source_evidence() -> None:
    proof = load_pinned_json(_PROOF, _PROOF_SHA)
    if proof.get('schema') != 'civ6rl.native_event_195088c7.static.v1' or proof['images']['exe_sha256'] != 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63' or proof['images']['core_sha256'] != 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3' or (proof['registration']['callback_va'] != '0x140152100') or (proof['captures']['callback']['raw_sha256'] != '97d04c69ac7ab310d2fb346dd1189480e391cfb0892cb63c3491c6439be467a1') or (proof['captures']['writer']['raw_sha256'] != '41fa005ad4bf9d747c83e38bec473dd4eb86148e3b69ebbf3d7823022f796312') or (proof['captures']['query']['raw_sha256'] != '7a937a6e0b18883da97b99ea7f44ef58370cfe38e1428a093d392e3b9abf5acd'):
        raise RuntimeError('Pinned 195088C7 callback/writer/query identity changed')

def decode_fields(fields: dict[int, bytes], read) -> dict:
    """Copy the live eight-byte position and decode its two signed DWORDs."""
    verify_source_evidence()
    if not isinstance(fields, dict) or set(fields) != {BLOB_KEY, SELECTOR_KEY}:
        raise ValueError('Unverified 195088C7 input fields')
    selector = decode_scalar(fields[SELECTOR_KEY], 3)
    raw = fields[BLOB_KEY]
    if not isinstance(raw, (bytes, bytearray, memoryview)) or len(raw) != 24:
        raise ValueError('Incomplete 195088C7 blob variant')
    tag = struct.unpack_from('<H', raw)[0]
    pointer, size, flags = struct.unpack_from('<QII', raw, 8)
    if tag != 0 or not pointer or size != 8 or (flags != 553648129):
        raise ValueError('Unverified 195088C7 blob envelope')
    value = read(pointer, 8)
    if not isinstance(value, (bytes, bytearray, memoryview)) or len(value) != 8:
        raise ValueError('Incomplete 195088C7 pointed value')
    x, y = struct.unpack('<ii', value)
    return {'position_bytes': bytes(value), 'x': x, 'y': y, 'selector': selector}

def _validate_position(position: dict) -> None:
    if not isinstance(position, dict) or type(position.get('position_bytes')) is not bytes or len(position['position_bytes']) != 8 or (type(position.get('x')) is not int) or (type(position.get('y')) is not int) or (struct.unpack('<ii', position['position_bytes']) != (position['x'], position['y'])):
        raise ValueError('Unverified 195088C7 decoded position')

def query_plot_word(core, context, position: dict, *, read=None, native_api=None, core_sha256='d7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3') -> int:
    """Read snapshot WORD+4 through native Core wrappers, matching EXE147C10.

    Returns -1 only on the source-proven null map/plot paths. For a live plot,
    the result is the signed native word copied from underlying plot+0x40.
    Both newly owned interfaces are released in source order.
    """
    verify_source_evidence()
    _validate_position(position)
    return _query_plot_snapshot_word(core, context, position, word_offset=4, read=read, native_api=native_api, core_sha256=core_sha256)

def encode_record(sequence: int, position: dict, plot_word: int, *, thread_hook_present: bool, writer_metadata_callback_present: bool) -> bytes:
    """Encode default metadata and the complete initialized 16-byte payload."""
    verify_source_evidence()
    if thread_hook_present is not False or writer_metadata_callback_present is not False:
        raise ValueError('195088C7 registered native callbacks are not modeled')
    if type(sequence) is not int or not 1 <= sequence <= 2147483647:
        raise ValueError('195088C7 sequence must be a bounded positive integer')
    _validate_position(position)
    if type(plot_word) is not int or not -32768 <= plot_word <= 32767:
        raise ValueError('195088C7 query result must be a signed native int16')
    record = bytearray(RECORD_SIZE)
    struct.pack_into('<IIII', record, 0, RECORD_SIZE, RECORD_TYPE, sequence, 0)
    struct.pack_into('<II', record, 16, 4294967295, 4294967295)
    for offset in (24, 32, 40, 48, 56):
        struct.pack_into('<HHI', record, offset, 65535, 0, 4294967295)
    struct.pack_into('<I', record, 80, sequence)
    record[84:92] = position['position_bytes']
    struct.pack_into('<i', record, 92, plot_word)
    return bytes(record)
__all__ = ['EVENT_KIND', 'RECORD_TYPE', 'decode_fields', 'query_plot_word', 'encode_record', 'verify_source_evidence', 'verify_notification_scope', 'SCOPE_PROOF_SHA256']
