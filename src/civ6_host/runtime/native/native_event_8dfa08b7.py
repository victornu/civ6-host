"""Pinned native event 0x8DFA08B7: source-backed Unit descriptor record."""
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
from dataclasses import dataclass
from pathlib import Path
import struct
from civ6_host.runtime.native.native_source_cache import load_pinned_json
from civ6_host.runtime.native import native_event_a60328c5 as sibling
EVENT_KIND, RECORD_TYPE, RECORD_SIZE = (2381973687, 75, 112)
SELECTOR_KEY, VALUE_KEY, SECOND_KEY, UNIT_KEY = (sibling.SELECTOR_KEY, sibling.VALUE_KEY, sibling.SECOND_KEY, sibling.UNIT_KEY)
PINNED_EVIDENCE_SHA256 = 'abd3663db9bc5b095ec003f417434218263073d4dcb338722c58d357df20f20c'
_PROOF = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_event_8dfa08b7.py')))).resolve().parents[1] / 'evidence/native-event-8dfa08b7' / f'{PINNED_EVIDENCE_SHA256}.json'
EventFields = sibling.EventFields

def verify_source_evidence():
    proof = load_pinned_json(_PROOF, PINNED_EVIDENCE_SHA256)
    captures = proof.get('captures', {})
    guards = proof.get('instruction_guards', {})
    expected_guards = {'callback': {'0x140156c45': 'movzx eax, word ptr [r8 + 0xa]', '0x140156c4e': 'mov eax, dword ptr [r8 + 0x50]', '0x140156c55': 'mov eax, dword ptr [r8 + 0x54]', '0x140156c59': 'mov dword ptr [rbp - 0x60], ecx', '0x140156c73': 'movzx ecx, word ptr [rdx + 8]', '0x140156c77': 'mov edx, dword ptr [rdx + 0xc]', '0x140156c8a': 'mov word ptr [rbp - 0x36], ax', '0x140156cce': 'call qword ptr [rax + 8]', '0x140156cf3': 'call 0x14012d6f0', '0x140156d10': 'call 0x1409898c0'}, 'writer': {'0x14012d772': 'lock xadd dword ptr [rsi + 0x38], edi', '0x14012d792': 'mov dword ptr [rbx], 0x70', '0x14012d798': 'mov dword ptr [rbx + 4], 0x4b', '0x14012d84b': 'mov dword ptr [rcx + 0x34], esi', '0x14012d8ba': 'movups xmm0, xmmword ptr [r15]', '0x14012d8d1': 'movups xmmword ptr [rax], xmm0', '0x14012d8d4': 'movsd xmm1, qword ptr [r15 + 0x10]', '0x14012d8da': 'movsd qword ptr [rax + 0x10], xmm1', '0x14012d8df': 'mov dword ptr [rax], edi'}, 'handler': {'0x1400d7c14': 'call 0x1400dc0d0'}}
    shared = proof.get('shared_a603_codec', {})
    receiver = proof.get('receiver', {})
    if proof.get('schema') != 'civ6rl.native_event_8dfa08b7.static.v1' or proof.get('exe_sha256') != 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63' or proof.get('targets', {}).get('callback') != '0x140156c00' or (proof.get('targets', {}).get('writer') != '0x14012d6f0') or (captures.get('callback', {}).get('code_sha256') != 'b644af4b28405756d1bbb3379fe41226f0659746cd612655f98a851ad604d9e6') or (captures.get('writer', {}).get('code_sha256') != 'bf672ba28cd411b72ade80b45af56dea12fd3cd82f6899904d47ca065a3c3dde') or (captures.get('normalizer', {}).get('code_sha256') != 'c757d2f0c927f36e058ff5e57350a80beac1db2a89d3940fcb5e89c05545f23e') or (shared.get('sha256') != sibling.PINNED_EVIDENCE_SHA256) or (shared.get('all_upstream_capture_instruction_bytes_reverified') is not True) or (shared.get('callback_instruction_count') != 69) or (shared.get('writer_instruction_count') != 139) or (receiver.get('record_type') != '0x4b') or (receiver.get('record_size') != '0x70') or (guards != expected_guards):
        raise RuntimeError('Pinned 8DFA08B7 callback/writer identity changed')
    sibling.verify_source_evidence()
    return proof

def decode_fields(fields, read):
    verify_source_evidence()
    return sibling.decode_fields(fields, read)

def encode_record(sequence, fields, *, normalizer_transform_present, per_thread_hook_present, writer_metadata_callback_present, padding_policy):
    verify_source_evidence()
    encoded = bytearray(sibling.encode_record(sequence, fields, normalizer_transform_present=normalizer_transform_present, per_thread_hook_present=per_thread_hook_present, writer_metadata_callback_present=writer_metadata_callback_present, padding_policy=padding_policy))
    struct.pack_into('<I', encoded, 4, RECORD_TYPE)
    return bytes(encoded)
