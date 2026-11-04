"""Source-pinned 89FACDC3 adapter for the shared city-descriptor callback."""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
from pathlib import Path
from civ6_host.runtime.native import native_event_8ee31e6f as shared
from civ6_host.runtime.native.native_source_cache import load_pinned_json
EVENT_KIND = 2314915267
RECORD_TYPE = 112
RECORD_SIZE = 96
PINNED_EVIDENCE_SHA256 = '5af6ee63b0be598b6a3741081d3b1f90828d7b4d3567acb81fee7f1a91e4a2ac'
_PROOF = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_event_89facdc3.py')))).resolve().parents[1] / 'evidence/native-event-89facdc3' / f'{PINNED_EVIDENCE_SHA256}.json'

def verify_source_evidence() -> None:
    proof = load_pinned_json(_PROOF, PINNED_EVIDENCE_SHA256)
    source = proof['shared_callback_writer_source']
    if proof.get('schema') != 'civ6rl.native_event_89facdc3.static.v1' or proof.get('exe_sha256') != 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63' or proof['registration'].get('kind') != EVENT_KIND or (proof['registration'].get('callback_va') != '0x140157630') or (source.get('callback_code_sha256') != '803dd29507b2c263ac82075f7014d16195af651c4a9877382d8a731883c1375e') or (source.get('writer_va') != '0x140130e00') or (source.get('writer_code_sha256') != 'a6c8fb5c5bee08a26840f82ce2b0d81d5951feab0997608b16a85600738e56c2') or (proof['contract']['writer'] != {'record_size': '0x60', 'record_type': '0x70', 'payload_offset': '0x50', 'payload_size': '0x10'}):
        raise RuntimeError('Pinned 89FACDC3 source identity changed')
    shared.verify_source_evidence()

def decode_fields(fields: dict, read):
    """Decode the exact three-key 89FACDC3 raw shape using its shared source codec."""
    verify_source_evidence()
    return shared.decode_fields(fields, read)

def encode_record(sequence: int, fields, *, normalizer_transform_present, per_thread_hook_present, writer_metadata_callback_present, padding_policy) -> bytes:
    """Encode the shared callback's city descriptor record for this event kind."""
    verify_source_evidence()
    return shared.encode_record(sequence, fields, normalizer_transform_present=normalizer_transform_present, per_thread_hook_present=per_thread_hook_present, writer_metadata_callback_present=writer_metadata_callback_present, padding_policy=padding_policy)
