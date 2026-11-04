"""Source-scoped adapter for deferred event kind 0x8953F126.

Only the statically evidenced no-thread-hook/no-queue-hook host profile is
encoded. The shared TurnBeginAuxiliaryState owns the callback's separate
post-append controller-byte effect; this module only builds the queue record.
"""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import hashlib
import json
from pathlib import Path
import struct
EVENT_KIND = 2303979814
CALLBACK_RVA = 1359632
QUEUE_WRITER_RVA = 1297856
RECORD_TYPE = 15
RECORD_SIZE = 96
_EVIDENCE_SHA256 = '286814367668dda9f80ba28aa22bdca52fa670dae78413cb5a73969d361f4474'
_EVIDENCE_PATH = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_event_8953f126.py')))).resolve().parents[1] / 'evidence' / 'native-event-8953f126' / f'{_EVIDENCE_SHA256}.json'
SELECTOR_SHA256 = 'cf023c5d09baa5e5aed886af92a943cf3cf25ffd145fb529b5db5a8e04005956'
SELECTOR_PATH = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_event_8953f126.py')))).resolve().parents[1] / 'evidence/native-8953-selector' / (SELECTOR_SHA256 + '.json')

def verify_source_pin() -> None:
    """Fail closed if the immutable source capture is absent or changed."""
    raw = _resolve_resource_path(_EVIDENCE_PATH).read_bytes()
    if hashlib.sha256(raw).hexdigest() != _EVIDENCE_SHA256:
        raise RuntimeError('Pinned 0x8953F126 source evidence changed')
    report = json.loads(raw)
    if report.get('schema') != 'civ6rl.native_event_8953f126.static.v1' or report.get('event_kind') != '0x8953f126' or report.get('registration', {}).get('callback_va') != '0x14014bf10':
        raise RuntimeError('Pinned 0x8953F126 source evidence contract mismatch')
    from civ6_host.runtime.native.native_source_cache import load_pinned_json
    selector = load_pinned_json(SELECTOR_PATH, SELECTOR_SHA256)
    if selector['schema'] != 'civ6rl.8953_selector949.static.v1' or selector['parent']['sha256'] != _EVIDENCE_SHA256 or selector['contract']['selector_normalized_offset'] != 4 or (selector['contract']['selector_consumed_by_callback'] is not False) or (not selector['validation']['all_captured_instructions_match_pinned_pe']):
        raise RuntimeError('0x8953F126 unused selector source changed')
verify_source_pin()

def _variant(raw: bytes, tag: int, name: str) -> int:
    if not isinstance(raw, (bytes, bytearray, memoryview)) or len(raw) != 24:
        raise ValueError(f'Truncated 0x8953F126 {name} variant')
    if struct.unpack_from('<H', raw)[0] != tag:
        raise ValueError(f'Unverified 0x8953F126 {name} tag')
    if struct.unpack_from('<I', raw, 20)[0] != 0:
        raise ValueError(f'Unverified 0x8953F126 {name} flags')
    return struct.unpack_from('<I', raw, 8)[0]

def decode_fields(raw_fields: dict[int, bytes]) -> dict[str, int]:
    expected = {2716180809, 3606901732, 2717631346}
    if not isinstance(raw_fields, dict) or set(raw_fields) != expected:
        raise ValueError('Unverified 0x8953F126 Core argument keys')
    selector = _variant(raw_fields[2716180809], 3, 'selector')
    value = _variant(raw_fields[3606901732], 2, 'value')
    state = _variant(raw_fields[2717631346], 2, 'state')
    return {'selector': selector, 'value': value, 'state': state}

def encode_8953f126_record(sequence: int, selector: int, value: int, state: int, *, optional_callback_present: bool=False, queue_hook_present: bool=False, queue_metadata: int=0) -> bytes:
    """Build the callback's 0x60-byte type-0x0f EXE queue record.

    The callback stores ``value`` at payload+4 and ``state != 0`` at
    payload+8. The three trailing payload bytes are stack padding and are
    zero-filled by this host adapter. After append, the callback sets byte
    +0x0d on the lazy GameCoreController to zero; the shared turn-status
    state model owns that effect.
    """
    if optional_callback_present is not False:
        raise ValueError('0x8953F126 optional per-thread callback is not implemented')
    if queue_hook_present is not False:
        raise ValueError('0x8953F126 optional queue hook is not implemented')
    for label, item in (('sequence', sequence), ('selector', selector), ('value', value), ('state', state), ('queue metadata', queue_metadata)):
        if type(item) is not int or not 0 <= item <= 4294967295:
            raise ValueError(f'Invalid 0x8953F126 {label}')
    if sequence == 0:
        raise ValueError('0x8953F126 sequence must be nonzero')
    if queue_metadata != 0:
        raise ValueError('0x8953F126 nonzero queue metadata requires the queue hook')
    record = bytearray(RECORD_SIZE)
    struct.pack_into('<IIII', record, 0, RECORD_SIZE, RECORD_TYPE, sequence, queue_metadata)
    for offset in (16, 20, 28, 36, 44, 52, 60):
        struct.pack_into('<I', record, offset, 4294967295)
    for offset in (24, 32, 40, 48, 56):
        struct.pack_into('<H', record, offset, 65535)
    for offset in (26, 34, 42, 50, 58):
        struct.pack_into('<H', record, offset, 0)
    struct.pack_into('<Q', record, 64, 0)
    struct.pack_into('<I', record, 72, 6)
    struct.pack_into('<II', record, 80, sequence, value)
    record[88] = int(state != 0)
    return bytes(record)
__all__ = ['EVENT_KIND', 'CALLBACK_RVA', 'QUEUE_WRITER_RVA', 'decode_fields', 'encode_8953f126_record', 'verify_source_pin']
