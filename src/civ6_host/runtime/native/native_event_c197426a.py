"""Source-backed position-only encoder for deferred event C197426A."""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import struct
from pathlib import Path
from civ6_host.runtime.native.native_application_mirror import decode_scalar
EVENT_KIND, RECORD_TYPE, RECORD_SIZE = (3247915626, 155, 96)
BLOB_KEY, SELECTOR_KEY = (2353434172, 2716180809)
_PROOF_SHA256 = '338b8749cd0eb552c7914076213db0c7e01b43ab5e5820f13ef99ec5cb24e4b2'
_PROOF = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_event_c197426a.py')))).resolve().parents[1] / 'evidence/native-event-c197426a' / f'{_PROOF_SHA256}.json'
_WITNESS_SHA256 = '9a29a181d25da2e2e20b8348accecbde8b0d6dc527dae96957551b42d9792142'
_WITNESS = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_event_c197426a.py')))).resolve().parents[1] / 'evidence/native-event-c197426a-witness' / f'{_WITNESS_SHA256}.json'
EMPTY_RECEIVER_PROFILE = 'initialized-empty-row-0x9b'
PADDING_POLICY = 'zero-unread-empty-receiver-payload'

def verify_source_evidence() -> None:
    from civ6_host.runtime.native.native_source_cache import load_pinned_json
    proof = load_pinned_json(_PROOF, _PROOF_SHA256)
    callback_diffs = proof['full_body_comparison'].get('callback_differences', ())
    writer_diffs = proof['full_body_comparison'].get('writer_differences', ())
    expected_callback_diffs = ({'index': 8, 'kind': 'rip_target', 'candidate': ('0x1412c85d0',), 'template': ('0x1412c8330',)}, {'index': 25, 'kind': 'direct_call', 'candidate': 'call 0x140134dc0', 'template': 'call 0x140133980'})
    expected_writer_diffs = ({'index': 52, 'kind': 'record_type', 'candidate': 'mov dword ptr [rbx + 4], 0x9b', 'template': 'mov dword ptr [rbx + 4], 0x8d'},)
    if proof.get('schema') != 'civ6rl.native_event_c197426a.static.v1' or proof.get('exe_sha256') != 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63' or proof['registration'].get('callback_va') != '0x1401527c0' or (proof['captures']['callback'].get('raw_sha256') != 'c1a0ce94770b9bc074978d20bd59facd0218fe9abd24601bfcc9acf5bda14514') or (proof['captures']['writer'].get('raw_sha256') != 'f2a1655364b5227d691b7f6873f1021f6eb8ea13fb83105052138ec9b0ce2b89') or (proof['receiver_row'].get('event_name', {}).get('text') != 'GameCoreEvent::RouteRemovedFromMap') or (proof['receiver_row'].get('row_index') != '0x9b') or (len(callback_diffs) != len(expected_callback_diffs)) or any((dict(actual) != expected for actual, expected in zip(callback_diffs, expected_callback_diffs))) or (len(writer_diffs) != len(expected_writer_diffs)) or any((dict(actual) != expected for actual, expected in zip(writer_diffs, expected_writer_diffs))) or (proof.get('allocation_growth', {}).get('new_tail_initialization_proven') is not False):
        raise RuntimeError('Pinned C197426A producer/receiver evidence changed')
    from civ6_host.runtime.native.native_source_cache import load_pinned_json
    witness = load_pinned_json(_WITNESS, _WITNESS_SHA256)
    if witness.get('schema') != 'civ6rl.native_event_c197426a.witness.v1' or witness.get('source_evidence_sha256') != _PROOF_SHA256 or witness.get('event_kind') != '0xc197426a' or (witness.get('position_blob_hex') != '1c00000012000000'):
        raise RuntimeError('Pinned C197426A compact witness changed')

def decode_fields(fields: dict[int, bytes], read, *, normalizer_transform_present=False) -> dict:
    verify_source_evidence()
    if normalizer_transform_present is not False:
        raise ValueError('C197426A normalizer transform is not modeled')
    if not isinstance(fields, dict) or set(fields) != {BLOB_KEY, SELECTOR_KEY}:
        raise ValueError('Unverified C197426A input key set')
    selector = decode_scalar(fields[SELECTOR_KEY], 3)
    raw = fields[BLOB_KEY]
    if not isinstance(raw, (bytes, bytearray, memoryview)) or len(raw) != 24:
        raise ValueError('Incomplete C197426A position variant')
    tag = struct.unpack_from('<H', raw)[0]
    pointer, size, flags = struct.unpack_from('<QII', raw, 8)
    if tag != 0 or not pointer or size != 8 or (flags != 553648129):
        raise ValueError('Unverified C197426A position blob envelope')
    value = read(pointer, 8)
    if not isinstance(value, (bytes, bytearray, memoryview)) or len(value) != 8:
        raise ValueError('Incomplete C197426A position copy')
    return {'position_bytes': bytes(value), 'selector': selector}

def encode_record(sequence: int, fields: dict[int, bytes], read, *, thread_hook_present: bool, writer_metadata_callback_present: bool, normalizer_transform_present=False, empty_receiver_profile: str, padding_policy: str):
    """Create the exact 0x9b/0x60 event under the captured empty-row profile."""
    if thread_hook_present is not False or writer_metadata_callback_present is not False:
        raise ValueError('C197426A callback and writer service profiles must be absent')
    if empty_receiver_profile != EMPTY_RECEIVER_PROFILE:
        raise ValueError('C197426A receiver row profile is not verified')
    if padding_policy != PADDING_POLICY:
        raise ValueError('C197426A writer leaves record gaps unspecified; explicit zero/unread policy is required')
    if type(sequence) is not int or not 1 <= sequence <= 2147483647:
        raise ValueError('C197426A sequence must be a bounded positive integer')
    values = decode_fields(fields, read, normalizer_transform_present=normalizer_transform_present)
    record = bytearray(RECORD_SIZE)
    struct.pack_into('<IIII', record, 0, RECORD_SIZE, RECORD_TYPE, sequence, 0)
    struct.pack_into('<II', record, 16, 4294967295, 4294967295)
    for offset in (24, 32, 40, 48, 56):
        struct.pack_into('<HHI', record, offset, 65535, 0, 4294967295)
    struct.pack_into('<I', record, 80, sequence)
    record[84:92] = values['position_bytes']
    return bytes(record)
__all__ = ['EVENT_KIND', 'RECORD_TYPE', 'RECORD_SIZE', 'BLOB_KEY', 'SELECTOR_KEY', 'EMPTY_RECEIVER_PROFILE', 'PADDING_POLICY', 'decode_fields', 'encode_record', 'verify_source_evidence']
