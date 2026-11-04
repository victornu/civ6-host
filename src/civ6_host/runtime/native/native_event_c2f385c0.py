"""Pinned descriptor/position event codec for EXE kind C2F385C0."""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
from dataclasses import dataclass
from pathlib import Path
import struct
from civ6_host.runtime.native import native_event_99e85ec6 as descriptor_codec
from civ6_host.runtime.native.native_feature_visibility_event import _copy_blob
from civ6_host.runtime.native.native_source_cache import load_pinned_json
EVENT_KIND, RECORD_TYPE, RECORD_SIZE = (3270739392, 106, 112)
CALLBACK_RVA, QUEUE_WRITER_RVA = (1320816, 1246608)
SELECTOR_KEY, DESCRIPTOR_KEY, POSITION_KEY = (2716180809, 594779970, 2353434172)
EXE_SHA256 = 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63'
PINNED_CANDIDATE_SHA256 = 'cee35d28ae1ea5c9a34d8c00067c09619b887804a093b06340680ae29117b7ea'
PINNED_FB_SHA256 = '5e2d307d15a46674745220b3ee11fb8f113348d85dbeb47cf63e5d0e846dff3b'
PINNED_REGISTRY_SHA256 = 'ec49b8df386e35cafc401986fb1512a89e19ebe7d94f8963684ac67505a1b0f5'
_ROOT = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_event_c2f385c0.py')))).resolve().parents[1]
_CANDIDATE = _ROOT / 'evidence/native-city-descriptor-candidates' / f'{PINNED_CANDIDATE_SHA256}.json'
_FB_PROOF = _ROOT / 'evidence/native-event-fb5f1edb' / f'{PINNED_FB_SHA256}.json'
_REGISTRY = _ROOT / 'evidence/native-host-event-registry.json'

def verify_source_evidence() -> None:
    candidate = load_pinned_json(_CANDIDATE, PINNED_CANDIDATE_SHA256)
    if candidate.get('exe_sha256') != EXE_SHA256:
        raise RuntimeError('C2F385C0 candidate EXE identity changed')
    selected = [row for row in candidate.get('captures', []) if row.get('callback', {}).get('start_va') == '0x140142770']
    if len(selected) != 1:
        raise RuntimeError('Pinned C2F385C0 callback capture missing or ambiguous')
    row = selected[0]
    if row.get('writer_va') != '0x140130590' or row['callback'].get('code_sha256') != '5fcfab1a54a96fc31311fdfe511a9c512d4df8bca01f157f15994b74c5475c28' or row['writer'].get('code_sha256') != '0e701421645fb028dd50fd2472cfe7e30dbee5b9ae2cd906c3f8324ff2ad5a90' or (row.get('writer_record_header') != {'size': RECORD_SIZE, 'type': RECORD_TYPE}):
        raise RuntimeError('Pinned C2F385C0 source layout changed')
    registry = load_pinned_json(_REGISTRY, PINNED_REGISTRY_SHA256)
    registrations = [r for r in registry['registrations'] if (int(r['kind'], 0) if isinstance(r['kind'], str) else r['kind']) == EVENT_KIND]
    if len(registrations) != 1 or registrations[0].get('callback_va') != '0x140142770':
        raise RuntimeError('Pinned C2F385C0 registration changed')
    fb = load_pinned_json(_FB_PROOF, PINNED_FB_SHA256)
    if fb.get('schema') != 'civ6rl.native_event_fb5f1edb.static.v1' or fb.get('exe_sha256') != EXE_SHA256 or fb.get('registration', {}).get('callback_va') != '0x1401423a0' or (fb.get('contract', {}).get('record_size') != RECORD_SIZE) or (fb.get('contract', {}).get('record_type') != 107) or (fb.get('contract', {}).get('input_keys') != ('0xa1e5a149', '0x23739f42', '0x8c468e3c')):
        raise RuntimeError('FB5F1EDB comparison proof changed')
    descriptor_codec.verify_source_evidence()

@dataclass(frozen=True)
class EventFields:
    descriptor: descriptor_codec.EventFields
    position_bytes: bytes

    @property
    def owner(self) -> int:
        return self.descriptor.owner

def decode_fields(raw_fields: dict[int, bytes], read) -> EventFields:
    verify_source_evidence()
    if not isinstance(raw_fields, dict) or set(raw_fields) != {SELECTOR_KEY, DESCRIPTOR_KEY, POSITION_KEY}:
        raise ValueError('C2F385C0 requires exactly selector, descriptor and position keys')
    position = _copy_blob(raw_fields[POSITION_KEY], read, 0)
    desc = descriptor_codec.decode_fields({SELECTOR_KEY: raw_fields[SELECTOR_KEY], DESCRIPTOR_KEY: raw_fields[DESCRIPTOR_KEY]}, read)
    return EventFields(desc, position)

def encode_record(sequence: int, fields: EventFields, *, normalizer_transform_present: bool, per_thread_hook_present: bool, writer_metadata_callback_present: bool, padding_policy: str) -> bytes:
    verify_source_evidence()
    if not isinstance(fields, EventFields) or type(fields.position_bytes) is not bytes or len(fields.position_bytes) != 8:
        raise ValueError('C2F385C0 requires an exact eight-byte position')
    if normalizer_transform_present is not False or per_thread_hook_present is not False or writer_metadata_callback_present is not False:
        raise ValueError('C2F385C0 supports only the pinned absent-callback profile')
    if type(sequence) is not int or not 1 <= sequence <= 4294967295:
        raise ValueError('C2F385C0 sequence must be a nonzero uint32')
    if padding_policy != 'headless-zero-uninitialized-stack':
        raise ValueError('C2F385C0 requires an explicit zero policy for uninitialized padding')
    record = bytearray(descriptor_codec.encode_record(sequence, fields.descriptor, normalizer_transform_present=False, per_thread_hook_present=False, writer_metadata_callback_present=False, padding_policy=padding_policy))
    record.extend(bytes(RECORD_SIZE - len(record)))
    struct.pack_into('<II', record, 0, RECORD_SIZE, RECORD_TYPE)
    record[96:104] = fields.position_bytes
    return bytes(record)
__all__ = ['EVENT_KIND', 'RECORD_TYPE', 'RECORD_SIZE', 'CALLBACK_RVA', 'QUEUE_WRITER_RVA', 'EventFields', 'decode_fields', 'encode_record', 'verify_source_evidence']
