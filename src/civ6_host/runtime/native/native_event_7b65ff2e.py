"""Proof-gated adapter for EXE host event 0x7B65FF2E.

The callback/query body is source-identical to 0x5D0F4014; the queue writer
differs only in its record type. This module pins both event-specific proof
and the earlier shared-query proof before delegating any decoding or native
query work.
"""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import struct
from pathlib import Path
from typing import Mapping
from civ6_host.runtime.native.native_source_cache import load_pinned_json
from civ6_host.runtime.native import native_event_5d0f4014 as _shared
from civ6_host.runtime import improvement_change_profile as _improvement_source
EVENT_KIND = 2070282030
CALLBACK_RVA = 1386256
WRITER_RVA = 1264208
RECORD_SIZE = 128
RECORD_TYPE = 153
BLOB_KEY = 2353434172
SELECTOR_KEY = 2716180809
VALUE_KEY = 2717631346
TAIL_KEY = 3606901732
_FIELD_KEYS = frozenset((BLOB_KEY, SELECTOR_KEY, VALUE_KEY, TAIL_KEY))
PINNED_EVIDENCE_SHA256 = '24157becb7c25402cd2816aa2633b6f33bcb58c6740f10080234bda80cbd13ef'
_PROOF_PATH = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_event_7b65ff2e.py')))).resolve().parents[1] / 'evidence' / 'native-event-7b65ff2e' / f'{PINNED_EVIDENCE_SHA256}.json'
_EXE_SHA256 = 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63'
_CORE_SHA256 = 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'
_NORMALIZER_SHA256 = 'c757d2f0c927f36e058ff5e57350a80beac1db2a89d3940fcb5e89c05545f23e'
_CALLBACK_SHA256 = '79066d21c623e205039eefffcc38b88e643d1d48f59da78fc9c629e893771f51'
_WRITER_SHA256 = 'b7599b0da9cb003597e0068f0eb33033b816ff5e042b65fe566eeec9d7a4eff6'
_QUERY_SHA256 = '18109bf51803e359c32da882ce3ce204c6eff3fab1273e2d87d33571db697c0c'
_PRIOR_WRITER_SHA256 = 'b900721c6453038397e01d598e8b3ef234593bd324bab2c9bcca72b8cb434dda'
_EMPTY_EVIDENCE_SHA256 = '91b1319584cd30d3553115cf5688f98ad0604a61cc1eff42654d950fdf272f9c'
_EMPTY_EVIDENCE_PATH = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_event_7b65ff2e.py')))).resolve().parents[1] / 'evidence' / 'native-deferred-empty-handlers' / f'{_EMPTY_EVIDENCE_SHA256}.json'
_PADDING_POLICY = 'zero-unread-empty-receiver-payload'

def verify_source_evidence() -> None:
    """Validate this event's immutable capture and its shared-query ancestry."""
    proof = load_pinned_json(_PROOF_PATH, PINNED_EVIDENCE_SHA256)
    captures = proof.get('captures', {})
    registration = proof.get('registration', {})
    callback = captures.get('callback', {})
    writer = captures.get('writer', {})
    normalizer = captures.get('normalizer', {})
    query = captures.get('query', {})
    prior_callback = captures.get('prior_callback', {})
    prior_writer = captures.get('prior_writer', {})
    equivalence = proof.get('equivalence', {})
    empty_reference = proof.get('empty_receiver_reference', {})
    if proof.get('schema') != 'civ6rl.native_event_7b65ff2e.static.v1' or proof.get('exe_sha256') != _EXE_SHA256 or proof.get('core_sha256') != _CORE_SHA256 or (registration.get('kind') != '0x7b65ff2e') or (registration.get('callback_va') != '0x140152710') or (registration.get('sha256') != 'ec49b8df386e35cafc401986fb1512a89e19ebe7d94f8963684ac67505a1b0f5') or (callback.get('start_va') != '0x140152710') or (callback.get('end_va_exclusive') != '0x1401527c0') or (callback.get('total_length') != 176) or (callback.get('fragments', ())[0].get('raw_sha256') != _CALLBACK_SHA256) or (writer.get('start_va') != '0x140134a50') or (writer.get('end_va_exclusive') != '0x140134ba4') or (writer.get('total_length') != 340) or (writer.get('fragments', ())[0].get('raw_sha256') != _WRITER_SHA256) or (normalizer.get('start_va') != '0x1401ca2d0') or (normalizer.get('end_va_exclusive') != '0x1401ca7e5') or (normalizer.get('total_length') != 1301) or (normalizer.get('raw_sha256') != _NORMALIZER_SHA256) or (query.get('start_va') != '0x140147cc0') or (query.get('end_va_exclusive') != '0x140147f05') or (query.get('total_length') != 581) or (query.get('raw_sha256') != _QUERY_SHA256) or (prior_callback.get('fragments', ())[0].get('raw_sha256') != '1db7a14bc3c7efcbc6dd52a280eb7879c8870d0990dd07ba2990dea0c008adbc') or (prior_writer.get('fragments', ())[0].get('raw_sha256') != _PRIOR_WRITER_SHA256) or (equivalence.get('callbacks_equal_after_aliasing') is not True) or (equivalence.get('writer_only_change') != (('mov dword ptr [rbx + 4], 0x98', 'mov dword ptr [rbx + 4], 0x99'),)) or (equivalence.get('query_exact_body_sha256') != _QUERY_SHA256):
        raise RuntimeError('Pinned 7B65FF2E source identity or equivalence changed')
    if empty_reference.get('path') != 'evidence/native-deferred-empty-handlers/91b1319584cd30d3553115cf5688f98ad0604a61cc1eff42654d950fdf272f9c.json' or empty_reference.get('sha256') != _EMPTY_EVIDENCE_SHA256:
        raise RuntimeError('Pinned 7B65FF2E empty-receiver reference changed')
    empty = load_pinned_json(_EMPTY_EVIDENCE_PATH, _EMPTY_EVIDENCE_SHA256)
    if empty.get('schema') != 'civ6rl.native_deferred_empty_handlers.v1':
        raise RuntimeError('Pinned empty-receiver profile schema changed')
    row = next((r for r in empty.get('row_mapping', {}).get('rows', ()) if r.get('record_type') == '0x99'), None)
    receiver = proof.get('empty_receiver_reference', {}).get('row', {})
    if row is None or receiver.get('record_type') != '0x99' or row.get('handler_va') != receiver.get('handler_va') or (row.get('handler_body_sha256') != receiver.get('handler_body_sha256')):
        raise RuntimeError('Pinned empty-receiver profile no longer admits row 0x99')
    _shared.verify_source_evidence()

def decode_fields(raw_fields: dict[int, bytes], read) -> dict:
    """Decode the exact four-key source shape using the proven shared normalizer."""
    verify_source_evidence()
    if not isinstance(raw_fields, dict) or set(raw_fields) != _FIELD_KEYS:
        raise ValueError('7B65FF2E requires exactly the four source-witnessed keys')
    return _shared.decode_fields(raw_fields, read)

def _receiver_state(value: Mapping) -> dict:
    keys = {'observer_registered', 'state_pointer_nonnull', 'pre_hook', 'post_hook', 'subscriber_count', 'state_flags'}
    if not isinstance(value, Mapping) or set(value) != keys:
        raise ValueError('7B65FF2E requires complete empty-receiver state')
    return dict(value)

def validate_profile(*, normalizer_transform_present: bool, thread_hook_present: bool, writer_metadata_callback_present: bool, padding_policy: str, empty_receiver_state: Mapping) -> dict:
    """Require the exact modeled profile and verify row 0x99 before querying."""
    verify_source_evidence()
    if normalizer_transform_present is not False:
        raise ValueError('7B65FF2E normalizer transforms are unsupported')
    if thread_hook_present is not False:
        raise ValueError('7B65FF2E per-thread hook is unsupported')
    if writer_metadata_callback_present is not False:
        raise ValueError('7B65FF2E queue metadata callback is unsupported')
    if padding_policy != _PADDING_POLICY:
        raise ValueError('7B65FF2E requires the explicit empty-receiver padding policy')
    state = _receiver_state(empty_receiver_state)
    from civ6_host.runtime.native.native_deferred_empty_profile import validate_empty_profile_record
    header = bytearray(RECORD_SIZE)
    struct.pack_into('<IIII', header, 0, RECORD_SIZE, RECORD_TYPE, 1, 0)
    return validate_empty_profile_record(header, **state)

def query_descriptor(core, context, position: dict, *, normalizer_transform_present: bool, thread_hook_present: bool, writer_metadata_callback_present: bool, padding_policy: str, empty_receiver_state: Mapping, read=None, native_api=None, core_sha256='d7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3') -> dict:
    """Validate profile first, then run the proven source 0x147CC0 query."""
    _improvement_source.ensure_source(core_sha256)
    verify_source_evidence()
    validate_profile(normalizer_transform_present=normalizer_transform_present, thread_hook_present=thread_hook_present, writer_metadata_callback_present=writer_metadata_callback_present, padding_policy=padding_policy, empty_receiver_state=empty_receiver_state)
    return _shared.query_descriptor(core, context, position, read=read, native_api=native_api, core_sha256=core_sha256)

def encode_record(sequence: int, position: dict, descriptor: dict, *, normalizer_transform_present: bool, thread_hook_present: bool, writer_metadata_callback_present: bool, padding_policy: str, empty_receiver_state: Mapping) -> bytes:
    """Encode the proven 5D payload/metadata and the 7B-specific type 0x99."""
    verify_source_evidence()
    state = _receiver_state(empty_receiver_state)
    validate_profile(normalizer_transform_present=normalizer_transform_present, thread_hook_present=thread_hook_present, writer_metadata_callback_present=writer_metadata_callback_present, padding_policy=padding_policy, empty_receiver_state=state)
    if padding_policy != _PADDING_POLICY:
        raise ValueError('7B65FF2E padding policy mismatch')
    record = bytearray(_shared.encode_record(sequence, position, descriptor, thread_hook_present=False, writer_metadata_callback_present=False, padding_policy='zero'))
    struct.pack_into('<I', record, 4, RECORD_TYPE)
    from civ6_host.runtime.native.native_deferred_empty_profile import validate_empty_profile_record
    validate_empty_profile_record(record, **state)
    return bytes(record)
__all__ = ['EVENT_KIND', 'CALLBACK_RVA', 'WRITER_RVA', 'RECORD_SIZE', 'RECORD_TYPE', 'BLOB_KEY', 'SELECTOR_KEY', 'VALUE_KEY', 'TAIL_KEY', 'decode_fields', 'query_descriptor', 'encode_record', 'validate_profile', 'verify_source_evidence']
