"""Pinned descriptor-only encoder for native deferred event 0x9C3482F5."""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
from pathlib import Path
import struct
from civ6_host.runtime.native import native_event_d8adfd71 as descriptor_codec
from civ6_host.runtime.native.native_source_cache import load_pinned_json
EVENT_KIND, RECORD_TYPE, RECORD_SIZE = (2620687093, 76, 96)
SELECTOR_KEY, DESCRIPTOR_KEY = (descriptor_codec.SELECTOR_KEY, descriptor_codec.DESCRIPTOR_KEY)
PINNED_EVIDENCE_SHA256 = '74b8115348ee1cd299dfd02059051b5b1b93c60470a5762583dba99a2491a8fd'
_PROOF = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_event_9c3482f5.py')))).resolve().parents[1] / 'evidence/native-event-9c3482f5' / f'{PINNED_EVIDENCE_SHA256}.json'
_EXE_SHA256 = 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63'
EventFields = descriptor_codec.EventFields

def verify_source_evidence():
    proof = load_pinned_json(_PROOF, PINNED_EVIDENCE_SHA256)
    registration = proof.get('registration', {})
    captures = proof.get('captures', {})
    guards = proof.get('instruction_guards', {})
    expected_guards = {'callback': {'0x140156b38': 'movzx ecx, word ptr [rax + 8]', '0x140156b53': 'mov edx, dword ptr [rax + 0xc]', '0x140156b56': 'movzx eax, word ptr [rax + 0xa]', '0x140156b5a': 'mov word ptr [rbp - 0x56], ax', '0x140156b5e': 'mov eax, 1', '0x140156b6b': 'mov word ptr [rbp - 0x36], ax', '0x140156baf': 'call qword ptr [rax + 8]', '0x140156bd4': 'call 0x14012d8f0', '0x140156bf1': 'call 0x1409898c0'}, 'writer': {'0x14012d992': 'mov dword ptr [rbx], 0x60', '0x14012d998': 'mov dword ptr [rbx + 4], 0x4c', '0x14012d972': 'lock xadd dword ptr [rsi + 0x38], edi', '0x14012da4b': 'mov dword ptr [rcx + 0x34], esi', '0x14012daba': 'movups xmm0, xmmword ptr [r15]', '0x14012dad1': 'movups xmmword ptr [rax], xmm0', '0x14012dad4': 'mov dword ptr [rax], edi'}}
    if proof.get('schema') != 'civ6rl.native_event_9c3482f5.static.v1' or proof.get('exe_sha256') != _EXE_SHA256 or registration.get('kind') != EVENT_KIND or (registration.get('callback_va') != '0x140156af0') or (captures.get('callback', {}).get('code_sha256') != 'e184dff19fc040d440c600b5abdcceeb08fd2db7b5564ad72d645d54af22609d') or (captures.get('writer', {}).get('code_sha256') != 'b2285c8923c150da212932e044eab9e272a0e6b50cda688d0fe31af8171a7260') or (captures.get('normalizer', {}).get('code_sha256') != 'c757d2f0c927f36e058ff5e57350a80beac1db2a89d3940fcb5e89c05545f23e') or (proof.get('shared_descriptor_codec', {}).get('sha256') != descriptor_codec.PINNED_EVIDENCE_SHA256) or (proof['shared_descriptor_codec'].get('writer_instruction_count') != 137) or (guards != expected_guards):
        raise RuntimeError('Pinned 9C3482F5 callback/writer contract changed')
    descriptor_codec.verify_source_evidence()
    return proof

def decode_fields(fields, read) -> EventFields:
    """Validate exact normalized scalar/blob envelopes and copy the descriptor.

    The selector is normalized but not consumed by this callback. The native
    source type word is likewise ignored; owner and identifier are copied.
    """
    verify_source_evidence()
    if not isinstance(fields, dict) or set(fields) != {SELECTOR_KEY, DESCRIPTOR_KEY}:
        raise ValueError('9C3482F5 requires exactly selector and descriptor keys')
    return descriptor_codec.decode_fields(fields, read)

def encode_record(sequence: int, fields: EventFields, *, normalizer_transform_present: bool, per_thread_hook_present: bool, writer_metadata_callback_present: bool, padding_policy: str) -> bytes:
    """Encode the source-backed 0x4C header using the shared 0x60 layout."""
    verify_source_evidence()
    record = bytearray(descriptor_codec.encode_record(sequence, fields, normalizer_transform_present=normalizer_transform_present, per_thread_hook_present=per_thread_hook_present, writer_metadata_callback_present=writer_metadata_callback_present, padding_policy=padding_policy))
    struct.pack_into('<I', record, 4, RECORD_TYPE)
    return bytes(record)
