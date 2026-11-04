"""Restricted encoder for the source-captured PlayerOperationComplete queue row."""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import struct
from pathlib import Path
from civ6_host.runtime.native.native_application_mirror import decode_scalar
from civ6_host.runtime.native.native_source_cache import load_pinned_json
EVENT_KIND = 94203074
CALLBACK_RVA = 1358880
QUEUE_WRITER_RVA = 1181696
RECORD_SIZE = 96
RECORD_TYPE = 270
CALLBACK_LOCAL_FLAG = 4
PIN = '2e67fbf1ad413c2075e504edd10562ce6527baed76bf8a04b0407ba289d62ac8'
PROOF = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_event_059d6cc2.py')))).resolve().parents[1] / 'evidence/native-event-059d6cc2' / f'{PIN}.json'

def verify_source():
    proof = load_pinned_json(PROOF, PIN)
    if proof['schema'] != 'civ6rl.native_event_059d6cc2.static.v1' or proof['registry']['registration']['callback_va'] != '0x14014bc20' or proof['source_layout']['record_type'] != '0x10e':
        raise RuntimeError('059D6CC2 source identity changed')

def decode_fields(fields):
    verify_source()
    if not isinstance(fields, dict) or set(fields) != {2716180809, 3606901732}:
        raise ValueError('059D6CC2 requires its exact scalar fields')
    player = decode_scalar(fields[3606901732], 2)
    operation = decode_scalar(fields[2716180809], 3)
    if type(player) is not int or not 0 <= player <= 63:
        raise ValueError('059D6CC2 player is outside the configured-player domain')
    return (player, operation)

def encode_research_record(sequence: int, player_id: int, operation: int, *, queue_metadata: int=0, hook_present: bool=False, writer_metadata_callback_present: bool=False, padding_policy='headless-zero-uninitialized-stack') -> bytes:
    """Encode only the captured no-hook, zero-writer-metadata profile.

    `operation` is preserved as an arbitrary uint32. The tail of the payload
    and all unassigned bytes are explicitly zero-filled.
    """
    verify_source()
    for label, value in (('sequence', sequence), ('player_id', player_id), ('operation', operation), ('queue_metadata', queue_metadata)):
        if type(value) is not int or not 0 <= value <= 4294967295:
            raise ValueError(f'{label} must be uint32')
    if sequence == 0:
        raise ValueError('sequence must be nonzero')
    if not 0 <= player_id <= 63:
        raise ValueError('player_id must be in the configured-player domain 0..63')
    if hook_present is not False or writer_metadata_callback_present is not False:
        raise ValueError('hook-present profile is not captured')
    if queue_metadata != 0:
        raise ValueError('nonzero writer metadata is not captured')
    if padding_policy != 'headless-zero-uninitialized-stack':
        raise ValueError('059D6CC2 requires its explicit zero padding profile')
    record = bytearray(RECORD_SIZE)
    struct.pack_into('<IIII', record, 0, RECORD_SIZE, RECORD_TYPE, sequence, 0)
    for offset in (16, 20, 28, 36, 44, 52, 60):
        struct.pack_into('<I', record, offset, 4294967295)
    for offset in (24, 32, 40, 48, 56):
        struct.pack_into('<H', record, offset, 65535)
    struct.pack_into('<II', record, 64, 0, 0)
    struct.pack_into('<I', record, 72, CALLBACK_LOCAL_FLAG)
    struct.pack_into('<III', record, 80, sequence, player_id, operation)
    return bytes(record)
__all__ = ['EVENT_KIND', 'CALLBACK_RVA', 'QUEUE_WRITER_RVA', 'RECORD_SIZE', 'RECORD_TYPE', 'CALLBACK_LOCAL_FLAG', 'encode_research_record']
