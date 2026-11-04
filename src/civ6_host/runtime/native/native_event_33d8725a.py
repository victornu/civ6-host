"""Source-scoped type-0x9A record encoder for the 0x33D8725A EXE callback.

This models the three-field and seven-field Core envelopes under the explicit
counter-zero/no-hook host profile. Positive optional indices require the real
Core map lookup; coordinates are never calculated or substituted here.
"""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import struct
from pathlib import Path
from civ6_host.runtime.native.native_source_cache import load_pinned_json
from civ6_host.runtime.native.native_event_827289e6 import query_optional_position
EVENT_KIND, CALLBACK_RVA = (869823066, 1386592)
RECORD_TYPE, RECORD_SIZE = (154, 128)
BLOB_KEY, SELECTOR_KEY, TAIL_KEY = (2353434172, 2716180809, 3606901732)
_PROOF_SHA256 = 'd9bc194eda20d9a7e054330e942d196fc3a0112db6a4d0b79821165c87cae92e'
_PROOF = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_event_33d8725a.py')))).resolve().parents[1] / 'evidence/native-event-33d8725a' / f'{_PROOF_SHA256}.json'
POSITIVE_PROOF_SHA256 = '1881a3beb1d4e9038871d20905ee19b2dc1da6b67db06efc61a29bd961a84292'
_POSITIVE_PROOF = _PROOF.parents[1] / 'native-event-33d8725a-positive' / f'{POSITIVE_PROOF_SHA256}.json'
_EXE_SHA256 = 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63'
_DEFAULT_PAIR = struct.pack('<HHI', 65535, 0, 4294967295)
OPTIONAL_VALUE_KEY, OPTIONAL_PAIR_KEY = (2717631346, 1532339015)
OPTIONAL_SCALAR_KEY, IGNORED_PLAYER_KEY = (955421384, 4033489650)
_BASIC_KEYS = {BLOB_KEY, SELECTOR_KEY, TAIL_KEY}
_EXTENDED_KEYS = _BASIC_KEYS | {OPTIONAL_VALUE_KEY, OPTIONAL_PAIR_KEY, OPTIONAL_SCALAR_KEY, IGNORED_PLAYER_KEY}

def verify_source_evidence() -> None:
    proof = load_pinned_json(_PROOF, _PROOF_SHA256)
    bodies = proof.get('captures', {})
    if proof.get('schema') != 'civ6rl.native_event_33d8725a.static.v2' or proof.get('images', {}).get('exe_sha256') != _EXE_SHA256 or proof.get('inputs', {}).get('callback_va') != hex(5368709120 + CALLBACK_RVA) or (bodies.get('callback', {}).get('code_sha256') != '73b7caa3694692b22f2f297794016292cec108ee71ac1c34792add012bad0682') or (bodies.get('record_writer', {}).get('code_sha256') != 'c4232f0337c99b37cf422b69b09543aef803c3c250448394d437318dcc16abe7') or (bodies.get('optional_variant_lookup', {}).get('code_sha256') != '3508a888d8362682654e408bccd9dda3d4cdddc13961264d873de6010676d27d') or (bodies.get('host_a0_normalizer', {}).get('code_sha256') != 'c757d2f0c927f36e058ff5e57350a80beac1db2a89d3940fcb5e89c05545f23e'):
        raise RuntimeError('Pinned 0x33D8725A callback/writer identity changed')

def verify_positive_source_evidence() -> None:
    proof = load_pinned_json(_POSITIVE_PROOF, POSITIVE_PROOF_SHA256)
    if proof.get('schema') != 'civ6rl.native_event_33d8725a_positive.static.v1' or proof.get('images') != {'exe_sha256': _EXE_SHA256, 'core_sha256': 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'} or proof['sources']['33d_v2']['sha256'] != _PROOF_SHA256 or (proof['contract']['shared_map_query_pin'] != '30a78ad61e21b0003de294a0fbd787402835d29a9a89e7bf441418087a39fab1') or (proof['core_captures']['map_index_position']['code_sha256'] != 'a902d6f4fe75debb0860785ab922bbdbc926d04acdbe659f41c31eb417c80835') or (proof['outer_release_complete_leaf']['raw_hex'] != 'c20000') or (proof['slots']['outer_release']['target_va'] != '0x180153060') or (proof['contract']['record_changes'] != {'D6_dword_unchanged_at_record': 96, 'optional_position8_at_record': 100, 'original_position8_unchanged_at_record': 88, 'pair5B55_8_at_record': 112, 'scalar38F_dword_at_record': 108}):
        raise RuntimeError('Pinned33D8725A positive native query contract changed')

def _scalar(raw: bytes, tag: int, label: str) -> int:
    if type(raw) is not bytes or len(raw) != 24:
        raise ValueError(f'Incomplete FoundCity {label} variant')
    actual_tag, flags = (struct.unpack_from('<H', raw)[0], struct.unpack_from('<I', raw, 20)[0])
    if actual_tag != tag or flags != 0:
        raise ValueError(f'Unverified FoundCity {label} tag or ownership flags')
    return struct.unpack_from('<I', raw, 8)[0]

def _copy_blob(blob: bytes, read, tags: tuple[int, ...], label: str) -> bytes:
    if type(blob) is not bytes or len(blob) != 24:
        raise ValueError(f'Incomplete FoundCity {label} variant')
    tag, pointer, size, flags = struct.unpack_from('<H6xQII', blob)
    if tag not in tags or not pointer or size != 8 or (flags != 553648129):
        raise ValueError(f'Unverified FoundCity {label} blob envelope')
    value = read(pointer, 8)
    if type(value) is not bytes or len(value) != 8:
        raise ValueError(f'Incomplete FoundCity {label} bytes')
    return value

def decode_fields(fields: dict[int, bytes], read) -> dict:
    """Decode exact three/seven-key shapes without making any Core calls."""
    verify_source_evidence()
    if not isinstance(fields, dict) or set(fields) not in (_BASIC_KEYS, _EXTENDED_KEYS):
        raise ValueError('Unverified 0x33D8725A field set or partial optional fields')
    extended = set(fields) == _EXTENDED_KEYS
    selector = _scalar(fields[SELECTOR_KEY], 3, 'selector')
    if selector != 0:
        raise ValueError('Only the witnessed FoundCity selector zero is admitted')
    tail = _scalar(fields[TAIL_KEY], 2, 'tail')
    position = _copy_blob(fields[BLOB_KEY], read, (0, 13), 'position')
    x, y = struct.unpack('<ii', position)
    optional_index = _scalar(fields[OPTIONAL_VALUE_KEY], 2, 'optional index') if extended else None
    return {'position_bytes': position, 'x': x, 'y': y, 'selector': selector, 'descriptor_tail': tail, 'metadata_pair_bytes': _copy_blob(fields[OPTIONAL_PAIR_KEY], read, (1024,), 'optional pair') if extended else _DEFAULT_PAIR, 'optional_fields_absent': not extended, 'input_shape': 'extended-seven-field' if extended else 'basic-three-field', 'optional_index': optional_index, 'optional_scalar': _scalar(fields[OPTIONAL_SCALAR_KEY], 2, 'optional scalar') if extended else None, 'ignored_player': _scalar(fields[IGNORED_PLAYER_KEY], 2, 'ignored player') if extended else None}

def encode_record(sequence: int, decoded: dict, *, notification_counter: int, notification_limit: int, thread_hook_present: bool, writer_metadata_callback_present: bool, padding_policy: str, core=None, context=None, read=None, optional_native_api=None, core_sha256='d7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3') -> bytes:
    """Build the source layout only under explicitly absent-hook conditions.

    ``padding_policy='zero'`` is an explicit host diagnostic policy for the
    stack DWORD copied at payload+4. Queue metadata is zero only when the
    writer's optional +0x40 callback is explicitly absent.

    For a nonnegative optional index, EXE147F10 obtains and releases its map
    facade before the callback appends the record. The shared native adapter
    preserves that lifetime; absent/negative indices retain the source defaults.
    """
    verify_source_evidence()
    if type(sequence) is not int or not 1 <= sequence <= 4294967295:
        raise ValueError('Sequence must be a nonzero uint32')
    if not isinstance(decoded, dict) or type(decoded.get('position_bytes')) is not bytes or len(decoded['position_bytes']) != 8 or (type(decoded.get('x')) is not int) or (type(decoded.get('y')) is not int) or (struct.unpack('<ii', decoded['position_bytes']) != (decoded.get('x'), decoded.get('y'))) or (type(decoded.get('descriptor_tail')) is not int) or (not 0 <= decoded['descriptor_tail'] <= 4294967295) or (type(decoded.get('selector')) is not int) or (decoded['selector'] != 0) or (type(decoded.get('metadata_pair_bytes')) is not bytes) or (len(decoded['metadata_pair_bytes']) != 8):
        raise ValueError('Unverified FoundCity decoded input')
    if decoded.get('input_shape') == 'basic-three-field':
        if decoded.get('optional_fields_absent') is not True or decoded['metadata_pair_bytes'] != _DEFAULT_PAIR or any((decoded.get(key) is not None for key in ('optional_index', 'optional_scalar', 'ignored_player'))):
            raise ValueError('33D8725A basic input cannot inject optional fields')
    elif decoded.get('input_shape') == 'extended-seven-field':
        if decoded.get('optional_fields_absent') is not False or any((type(decoded.get(key)) is not int or not 0 <= decoded[key] <= 4294967295 for key in ('optional_index', 'optional_scalar', 'ignored_player'))):
            raise ValueError('33D8725A extended input requires all typed optional DWORDs')
    else:
        raise ValueError('33D8725A input shape is not source-backed')
    if type(notification_counter) is not int or notification_counter != 0:
        raise ValueError('Only the source-zero notification counter is supported')
    if type(notification_limit) is not int or notification_limit != 0:
        raise ValueError('Only the source-zero notification limit is supported')
    if thread_hook_present is not False or writer_metadata_callback_present is not False:
        raise ValueError('FoundCity per-thread or writer callback is not modeled')
    if padding_policy != 'zero':
        raise ValueError('Only explicit zero stack-padding policy is supported')
    optional_position = struct.pack('<ii', -9999, -9999)
    optional_scalar = 0
    index = decoded['optional_index']
    if index is not None and index < 2147483648:
        verify_positive_source_evidence()
        optional_position = query_optional_position(core, context, index, read=read, native_api=optional_native_api, core_sha256=core_sha256)
        if type(optional_position) is not bytes or len(optional_position) != 8:
            raise ValueError('33D8725A requires the complete native optional position')
        optional_scalar = decoded['optional_scalar']
    metadata = bytearray(60)
    struct.pack_into('<IIHHI', metadata, 0, 4294967295, 4294967295, 65535, 0, 4294967295)
    for offset in (16, 24, 32, 40):
        struct.pack_into('<HHI', metadata, offset, 65535, 0, 4294967295)
    struct.pack_into('<Q', metadata, 48, 0)
    struct.pack_into('<I', metadata, 56, 0)
    payload = bytearray(40)
    struct.pack_into('<I', payload, 0, sequence)
    payload[8:16] = decoded['position_bytes']
    struct.pack_into('<I', payload, 16, decoded['descriptor_tail'])
    payload[20:28] = optional_position
    struct.pack_into('<I', payload, 28, optional_scalar)
    payload[32:40] = decoded['metadata_pair_bytes']
    record = bytearray(RECORD_SIZE)
    struct.pack_into('<IIII', record, 0, RECORD_SIZE, RECORD_TYPE, sequence, 0)
    record[16:76] = metadata
    record[80:120] = payload
    return bytes(record)
__all__ = ['EVENT_KIND', 'RECORD_TYPE', 'decode_fields', 'encode_record', 'verify_source_evidence']
