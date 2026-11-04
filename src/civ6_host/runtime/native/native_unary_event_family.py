"""Fail-closed typed codec for the source-reviewed unary Core event subset.

Static shape is not runtime admission. Only event kinds with both a matching
EXE callback/writer and a Core literal producer through the typed descriptor
builder are exposed here.
"""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
from dataclasses import dataclass
import hashlib
import json
import re
import struct
from pathlib import Path
from types import MappingProxyType
_FAMILY_SHA256 = 'ca9c08c52ae703160d610a59e9303cc4ce60fddc96d463db64e02658cbade089'
_CONSUMERS_SHA256 = 'd3f08fdb3ee259c1b632f28a2aa9bc06b66789c5b3ed6b21c2a24594a61dc958'
_EXE_SHA256 = 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63'
_CORE_SHA256 = 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'
_FAMILY_PATH = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_unary_event_family.py')))).resolve().parents[1] / 'evidence/native-unary-event-family.json'
_CONSUMERS_PATH = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_unary_event_family.py')))).resolve().parents[1] / 'evidence/native-unary-event-consumers.json'
_EXPECTED_CORE_PRODUCERS = frozenset({3618854699, 4050067919, 619265832, 3555948358, 2480740111, 1817036228, 2813874785, 3224838482})

def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()

def _family_rows():
    family_raw = _resolve_resource_path(_FAMILY_PATH).read_bytes()
    consumers_raw = _resolve_resource_path(_CONSUMERS_PATH).read_bytes()
    if _sha(family_raw) != _FAMILY_SHA256:
        raise RuntimeError('unary family source evidence hash mismatch')
    if _sha(consumers_raw) != _CONSUMERS_SHA256:
        raise RuntimeError('unary Core consumer evidence hash mismatch')
    family = json.loads(family_raw)
    consumers = json.loads(consumers_raw)
    if family.get('schema') != 'civ6rl.native_unary_event_family.static.v1' or family.get('image', {}).get('sha256') != _EXE_SHA256 or len(family.get('accepted_candidates', [])) != 17:
        raise RuntimeError('unary family evidence is incomplete or changed')
    if consumers.get('schema') != 'civ6rl.native_unary_event_core_consumers.static.v1' or consumers.get('image', {}).get('sha256') != _CORE_SHA256 or consumers.get('family_source', {}).get('sha256') != _FAMILY_SHA256:
        raise RuntimeError('Core consumer evidence is incomplete or changed')
    consumer_by_kind = {int(row['event_kind'], 16): row for row in consumers['event_candidates']}
    if set(consumer_by_kind) != {int(r['kind'], 16) for r in family['accepted_candidates']}:
        raise RuntimeError('Core consumer rows do not match the callback family')
    found = frozenset((kind for kind, row in consumer_by_kind.items() if row['core_static_immediate_instruction_count'] > 0 and row['direct_generic_descriptor_builder_calls']))
    if found != _EXPECTED_CORE_PRODUCERS:
        raise RuntimeError('Core producer evidence subset changed')
    body_bundle = family.get('accepted_source_bodies', {})
    out = {}
    for item in family['accepted_candidates']:
        kind = int(item['kind'], 16)
        if kind not in found:
            continue
        writer_va = item.get('writer_va')
        writer = body_bundle.get(writer_va)
        if not writer:
            raise RuntimeError(f'missing complete writer body for {kind:#x}')
        inst = [row for frag in writer['fragments'] for row in frag['instructions']]
        sizes = [row for row in inst if row['text'] == 'mov dword ptr [rbx], 0x60']
        types = [row for row in inst if row['text'].startswith('mov dword ptr [rbx + 4], ')]
        seq_header = [row for row in inst if row['text'] == 'mov dword ptr [rbx + 8], edi']
        seq_payload = [row for row in inst if row['text'] == 'mov dword ptr [rax], edi']
        queue_counter = [row for row in inst if row['text'] == 'lock xadd dword ptr [rsi + 0x38], edi']
        if not len(sizes) == len(types) == len(seq_header) == len(seq_payload) == len(queue_counter) == 1:
            raise RuntimeError(f'writer layout proof incomplete for {kind:#x}')
        record_type = int(types[0]['text'].rsplit(', ', 1)[1], 16)
        if int(item['writer_instruction_count']) != len(inst):
            raise RuntimeError(f'writer count disagrees for {kind:#x}')
        callback = body_bundle.get(item['callback_va'])
        if not callback:
            raise RuntimeError(f'missing complete callback body for {kind:#x}')
        callback_inst = [row for frag in callback['fragments'] for row in frag['instructions']]
        flags = [row for row in callback_inst if re.fullmatch('mov dword ptr \\[rbp - 8\\], (?:0x[0-9a-f]+|[0-9]+)', row['text'])]
        if len(flags) != 1:
            raise RuntimeError(f'callback metadata flag is not uniquely captured for {kind:#x}')
        callback_flag = int(flags[0]['text'].rsplit(', ', 1)[1], 0)
        out[kind] = {'record_type': record_type, 'callback_flag': callback_flag, 'writer_va': writer_va, 'callback_va': item['callback_va'], 'callback_raw_sha256': item['callback_raw_sha256'], 'writer_raw_sha256': item['writer_raw_sha256']}
    if set(out) != _EXPECTED_CORE_PRODUCERS:
        raise RuntimeError('typed unary codec candidate set changed')
    return MappingProxyType(out)
UNARY_EVENT_SOURCES = _family_rows()

@dataclass(frozen=True)
class UnaryCoreDescriptor:
    event_kind: int
    selector: int
    value: int

@dataclass(frozen=True)
class UnaryQueueRecord:
    event_kind: int
    sequence: int
    value: int
    queue_metadata: int = 0

def source_for(event_kind: int) -> dict:
    try:
        return UNARY_EVENT_SOURCES[event_kind]
    except (KeyError, TypeError):
        raise ValueError(f'Event kind is outside the source-backed unary Core subset: {event_kind!r}') from None

def _read_variant(raw, expected_tag: int, field_name: str) -> int:
    if not isinstance(raw, (bytes, bytearray, memoryview)) or len(raw) != 24:
        raise ValueError(f'{field_name} variant must be exactly 24 bytes')
    if struct.unpack_from('<H', raw, 0)[0] != expected_tag:
        raise ValueError(f'{field_name} variant tag mismatch')
    if struct.unpack_from('<I', raw, 20)[0] != 0:
        raise ValueError(f'{field_name} variant flags must be zero')
    return struct.unpack_from('<I', raw, 8)[0]

def decode_core_fields(event_kind: int, raw_fields: dict[int, bytes]) -> UnaryCoreDescriptor:
    """Decode only exact A1E5(tag 3)/D6FC(tag 2) uint32 descriptors, selector zero."""
    source_for(event_kind)
    if not isinstance(raw_fields, dict) or set(raw_fields) != {2716180809, 3606901732}:
        raise ValueError('Core descriptor keys must be exactly A1E5A149 and D6FCF3E4')
    selector = _read_variant(raw_fields[2716180809], 3, 'A1E5A149')
    value = _read_variant(raw_fields[3606901732], 2, 'D6FCF3E4')
    if selector != 0:
        raise ValueError('Only selector zero has a source-backed unary payload contract')
    return UnaryCoreDescriptor(event_kind, selector, value)

def _uint32(value, label: str) -> int:
    if type(value) is not int or not 0 <= value <= 4294967295:
        raise ValueError(f'{label} must be uint32')
    return value

def _metadata_template() -> bytes:
    metadata = bytearray(64)
    for offset in (0, 4, 12, 20, 28, 36, 44):
        struct.pack_into('<I', metadata, offset, 4294967295)
    for offset in (8, 16, 24, 32, 40):
        struct.pack_into('<H', metadata, offset, 65535)
    for offset in (10, 18, 26, 34, 42):
        struct.pack_into('<H', metadata, offset, 0)
    struct.pack_into('<Q', metadata, 48, 0)
    return bytes(metadata)
_METADATA = _metadata_template()

def encode_queue_record(event_kind: int, sequence: int, value: int, *, queue_metadata: int=0, optional_callback_present: bool | None=None, queue_hook_present: bool | None=None) -> bytes:
    """Encode one reviewed record using the already-incremented queue sequence.

    Both absent-hook flags are mandatory assertions; unknown hook state fails
    closed rather than creating a record with guessed callback metadata.
    """
    source = source_for(event_kind)
    sequence = _uint32(sequence, 'sequence')
    value = _uint32(value, 'payload value')
    queue_metadata = _uint32(queue_metadata, 'queue metadata')
    if sequence == 0:
        raise ValueError('sequence must be nonzero')
    if optional_callback_present is not False or queue_hook_present is not False:
        raise ValueError('both optional event hooks must be explicitly confirmed absent')
    if queue_metadata != 0:
        raise ValueError('nonzero queue metadata requires the unimplemented queue hook')
    record = bytearray(96)
    struct.pack_into('<IIII', record, 0, 96, source['record_type'], sequence, 0)
    record[16:80] = _METADATA
    struct.pack_into('<I', record, 72, source['callback_flag'])
    struct.pack_into('<II', record, 80, sequence, value)
    return bytes(record)

def encode_core_fields(event_kind: int, sequence: int, raw_fields: dict[int, bytes], **kwargs) -> bytes:
    descriptor = decode_core_fields(event_kind, raw_fields)
    return encode_queue_record(event_kind, sequence, descriptor.value, **kwargs)

def decode_queue_record(event_kind: int, raw: bytes) -> UnaryQueueRecord:
    source = source_for(event_kind)
    if not isinstance(raw, (bytes, bytearray, memoryview)) or len(raw) != 96:
        raise ValueError('queue record must be exactly 0x60 bytes')
    if struct.unpack_from('<II', raw, 0) != (96, source['record_type']):
        raise ValueError('queue record size/type mismatch')
    sequence, metadata = struct.unpack_from('<II', raw, 8)
    payload_sequence, value = struct.unpack_from('<II', raw, 80)
    if sequence == 0 or payload_sequence != sequence:
        raise ValueError('queue/header payload sequence mismatch')
    expected_metadata = bytearray(_METADATA)
    struct.pack_into('<I', expected_metadata, 56, source['callback_flag'])
    if metadata != 0 or bytes(raw[16:80]) != bytes(expected_metadata):
        raise ValueError('queue metadata does not match the reviewed D3 callback template')
    return UnaryQueueRecord(event_kind, sequence, value, metadata)
