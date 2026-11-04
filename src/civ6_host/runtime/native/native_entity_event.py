"""Encoder for the statically verified EXE C50D66D6 deferred event.

The source callback 0x140157B30 enqueues a 0x70-byte record of type 0x19
through 0x1401275E0. This module only builds that record; it does not dispatch
callbacks or claim that its consumer has been implemented.
"""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import math
from pathlib import Path
import struct
from civ6_host.runtime.native.native_source_cache import load_pinned_json
EVENT_KIND = 3305989846
CALLBACK_RVA = 1407792
QUEUE_WRITER_RVA = 1209824
RECORD_SIZE = 112
RECORD_TYPE = 25
QUEUE_LIFETIME_PROOF_SHA256 = 'c282934897e9d773d83af732c85a2bc6d1750af62478d84bb0783741d4c67418'
UNDEFINED_RECORD_RANGES = ((84, 88), (100, 104))
_PROOF = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_entity_event.py')))).resolve().parents[1] / 'evidence/native-c50-queue-lifetime' / (QUEUE_LIFETIME_PROOF_SHA256 + '.json')

def verify_source_evidence():
    proof = load_pinned_json(_PROOF, QUEUE_LIFETIME_PROOF_SHA256)
    contract = proof.get('contract', {})
    if proof.get('schema') != 'civ6rl.native_c50_queue_lifetime.static.v1' or proof.get('kind') != EVENT_KIND or proof.get('native_execution') is not False or (proof.get('images') != {'exe_sha256': 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63'}) or (contract.get('record') != {'type': RECORD_TYPE, 'size': RECORD_SIZE, 'payload_offset': 80, 'payload_size': 24, 'undefined_ranges': UNDEFINED_RECORD_RANGES, 'allocation_zero_ranges': ((76, 80), (104, 112))}) or (contract.get('invalid_descriptor_sentinel_guard') is not False) or (contract.get('native_core_queries') != 0) or (contract.get('retained_interfaces') != 0) or (contract.get('records_per_callback') != 1) or (contract.get('writer_sequence') != {'storage_offset': 56, 'operation': 'atomic DWORD xadd1, stores old+1', 'cumulative_admission_limit': None}) or (proof.get('float_multiplier') != {'bytes': '00008043', 'va': '0x140fbf530', 'value': 256.0}) or (proof.get('verification', {}).get('all_captured_instructions_match_pinned_pe') is not True):
        raise RuntimeError('C50 queue lifetime/padding source contract changed')
    for name, expected in (('callback', 'd08bcb03d6265b8bb6dda5ed9bca250c6c8e2af718485bef87f821ff7fe2d84e'), ('writer', 'f8ebb56b37f9490d224c379751d9688731864ac724c3e5acacee344557e4381a')):
        if proof['captures'][name]['code_sha256'] != expected:
            raise RuntimeError('C50 queue producer body changed: ' + name)
    for name, expected in (('legacy_queue', 'a9f8b0e2e51f60ee0a24531c1f58e75abe524b709cf1c31b10f7a721d9f1c6f6'), ('empty_receiver', '8f93575f0641395046818b5d3af84cbb5ae113986b8f8411dd4bcee4c9d4e044')):
        if proof['parents'][name]['sha256'] != expected:
            raise RuntimeError('C50 parent evidence changed: ' + name)
    return proof

def _f32(value: float) -> float:
    return struct.unpack('<f', struct.pack('<f', value))[0]

def pack_coordinate_8_8(float32_bits: int) -> int:
    """Mirror the callback's floor-and-fraction*256 conversion for finite f32."""
    if type(float32_bits) is not int or not 0 <= float32_bits <= 4294967295:
        raise ValueError('Coordinate must be raw uint32 float bits')
    value = struct.unpack('<f', struct.pack('<I', float32_bits))[0]
    if not math.isfinite(value) or value < -2147483648.0 or value >= 2147483648.0:
        raise ValueError("Coordinate is outside the callback's verified conversion range")
    integer = math.trunc(value)
    whole = integer - (1 if float(integer) != value and value < 0.0 else 0)
    fraction = _f32(_f32(value - float(whole)) * 256.0)
    fraction_byte = math.trunc(fraction) & 255
    return (whole << 8 | fraction_byte) & 4294967295

def encode_c50_entity_event(sequence: int, normalized_descriptor: bytes, float32_bits: int, *, queue_metadata: int, stack_padding_word: int, stack_padding_tail_word: int) -> bytes:
    """Build the ring record copied by EXE 0x1401275E0.

    ``normalized_descriptor`` is owner:u16, fixed entity type 1:u16,
    identifier:u32. This is the descriptor accepted by the EXE callback, not
    the raw Core event blob. ``queue_metadata`` is the optional queue service
    result written by 0x1401275E0; a headless profile with no service passes 0.
    The separate C50 preprocessing hook is not modeled here; this encoder is
    only valid for that hook's absent/no-op profile.
    ``stack_padding_word`` and ``stack_padding_tail_word`` stand for the
    uninitialized callback DWORDs copied to record+0x54 and record+0x64.
    Neither is a native zero/default. The host may supply zero only after
    verifying that the actual empty receiver cannot read these bytes.
    """
    verify_source_evidence()
    if type(sequence) is not int or not 1 <= sequence <= 4294967295:
        raise ValueError('Sequence must be a nonzero uint32')
    if not isinstance(normalized_descriptor, (bytes, bytearray, memoryview)) or len(normalized_descriptor) != 8:
        raise ValueError('Normalized entity descriptor must be exactly eight bytes')
    if type(queue_metadata) is not int or not 0 <= queue_metadata <= 4294967295:
        raise ValueError('Queue metadata must be uint32')
    if type(stack_padding_word) is not int or not 0 <= stack_padding_word <= 4294967295:
        raise ValueError('Stack padding must be uint32')
    if type(stack_padding_tail_word) is not int or not 0 <= stack_padding_tail_word <= 4294967295:
        raise ValueError('Tail stack padding must be uint32')
    owner, entity_type, identifier = struct.unpack('<HHI', normalized_descriptor)
    if entity_type != 1:
        raise ValueError("C50 callback's normalized entity type must be 1")
    packed_coordinate = pack_coordinate_8_8(float32_bits)
    record = bytearray(RECORD_SIZE)
    struct.pack_into('<IIII', record, 0, RECORD_SIZE, RECORD_TYPE, sequence, queue_metadata)
    struct.pack_into('<IIHHIHHIHHIHHIHHIQI', record, 16, 4294967295, 4294967295, owner, 1, identifier, 65535, 0, 4294967295, 65535, 0, 4294967295, 65535, 0, 4294967295, 65535, 0, 4294967295, 0, 0)
    struct.pack_into('<IIIIII', record, 80, sequence, stack_padding_word, owner | entity_type << 16, identifier, packed_coordinate, stack_padding_tail_word)
    return bytes(record)
