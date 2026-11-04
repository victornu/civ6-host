"""Bounded diagnostic encoder for EXE GameCoreEvent::CacheUpdate records.

The producer only requires its optional preprocessing callback to be absent.
Receiver registration is a separate contract; the compatibility empty-profile
entry point additionally checks that profile, but does not drain a native queue.
"""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import hashlib
import json
import struct
from pathlib import Path
_PROOF_SHA256 = '285af8d61de7f623338ec4c0647b15dabcfe6fccd60e51237fcb600f9d38c5a9'
_PROOF_PATH = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_cache_update_event.py')))).resolve().parents[1] / 'evidence' / 'native-host-b0-cache-update.json'
_RECORD_TYPE = 275
_RECORD_SIZE = 112

def _proof() -> dict:
    from civ6_host.runtime.native.native_source_cache import load_pinned_json
    doc = load_pinned_json(_PROOF_PATH, _PROOF_SHA256)
    if doc.get('schema') != 'civ6rl.native_host_b0_cache_update.static.v1':
        raise RuntimeError('Unsupported CacheUpdate source proof')
    if doc.get('images', {}).get('exe_sha256') != 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63':
        raise RuntimeError('CacheUpdate proof refers to an unexpected EXE')
    row = doc.get('cache_update_row', {})
    if row.get('record_type') != '0x113' or row.get('event_name') != 'GameCoreEvent::CacheUpdate':
        raise RuntimeError('CacheUpdate receiver row proof changed')
    init = row.get('static_empty_initialization', {})
    expected = {'pre_hook_row_plus_0': None, 'post_hook_row_plus_8': None, 'subscriber_count_state_plus_0x20': 0, 'subscriber_array_state_plus_8': 0, 'busy_and_deferred_remove_flag_bits_state_plus_0x30_masked_with_0xfc': 0}
    if any((init.get(key) != value for key, value in expected.items())):
        raise RuntimeError('CacheUpdate source initialization no longer proves an empty row')
    return doc

def decode_host_b0_scalar(value: int) -> tuple[int, int]:
    """Split the scalar passed in R8 into the low/high DWORDs; never dereference it."""
    if type(value) is not int or not 0 <= value <= 18446744073709551615:
        raise ValueError('Host +B0 R8 input must be a uint64 scalar')
    return (value & 4294967295, value >> 32)

def encode_cache_update_record(sequence: int, context_arg: int, packed_event: int, append_metadata: int, *, host_callback_pair: tuple[int, int] | None, receiver_state_pointer: bool, pre_hook: int | None, post_hook: int | None, subscriber_count: int, state_flags: int) -> bytes:
    """Build the observed 0x70 type-0x113 record under an explicit empty profile.

    Unspecified allocation bytes are zeroed as a diagnostic normalization. The
    caller supplies the metadata getter result because this helper does not call
    the native interface at group+0x40.
    """
    if receiver_state_pointer is not True:
        raise ValueError('CacheUpdate receiver state allocation is not usable')
    if pre_hook is not None or post_hook is not None:
        raise ValueError('CacheUpdate pre/post hooks require their native callback path')
    if type(subscriber_count) is not int or subscriber_count != 0:
        raise ValueError('CacheUpdate subscribers are not empty')
    if type(state_flags) is not int or state_flags & 3:
        raise ValueError('CacheUpdate busy/deferred-removal flags are active')
    return encode_cache_update_producer(sequence, context_arg, packed_event, append_metadata, host_callback_pair=host_callback_pair)

def encode_cache_update_producer(sequence, context_arg, packed_event, append_metadata, *, host_callback_pair):
    """Encode the source producer independently of the deferred subscriber list.

    EXE1CA220/1C90F0 only consult the optional preprocessing callback pair and
    queue metadata getter. They do not read the eventual row subscriber count.
    """
    if type(sequence) is not int or not 1 <= sequence <= 4294967295:
        raise ValueError('Sequence must be a nonzero uint32')
    if type(context_arg) is not int or not 0 <= context_arg <= 4294967295:
        raise ValueError('Host +B0 second argument must be uint32')
    if type(append_metadata) is not int or not 0 <= append_metadata <= 4294967295:
        raise ValueError('Queue metadata getter result must be uint32')
    if host_callback_pair is not None:
        raise ValueError('Host +B0 callback pair is present; its function has unmodeled side effects')
    selector, callback_id = decode_host_b0_scalar(packed_event)
    record = bytearray(_RECORD_SIZE)
    struct.pack_into('<IIII', record, 0, _RECORD_SIZE, _RECORD_TYPE, sequence, append_metadata)
    for offset in (16, 20, 28, 36, 44, 52, 60):
        struct.pack_into('<I', record, offset, 4294967295)
    for offset in (24, 32, 40, 48, 56):
        struct.pack_into('<H', record, offset, 65535)
    for offset in (26, 34, 42, 50, 58):
        struct.pack_into('<H', record, offset, 0)
    struct.pack_into('<Q', record, 64, 0)
    struct.pack_into('<I', record, 72, 0)
    struct.pack_into('<IIIII', record, 80, 0, context_arg, 0, selector, callback_id)
    struct.pack_into('<I', record, 80, sequence)
    return bytes(record)
_SOURCE_PROOF = _proof()
