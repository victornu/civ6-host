"""Bounded diagnostic producer for EXE's private 1BE52206 command ring.

The original private-ring consumer is not implemented. Records are retained;
this adapter cannot authorize training or claim a complete EXE lifecycle.
"""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import hashlib
import json
import struct
import threading
from pathlib import Path
from civ6_host.runtime.native.native_application_mirror import decode_scalar
EVENT_KIND, RECORD_TYPE, RECORD_SIZE = (468001286, 84, 128)
BANK_CAPACITY = 4194304
SELECTOR_KEY, VALUE_KEY, DESCRIPTOR_KEY = (2716180809, 2717631346, 3606901732)
DIAGNOSTIC_PROFILE = 'fresh-zero-thread0-bank0-unconsumed-diagnostic'
_PROOF_SHA = 'c1686d4dfd287aab0fe306c06221802add2bf5a9f459ba414f69e5cde4e6c668'
_PROOF = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_event_1be52206.py')))).resolve().parents[1] / 'evidence/native-event-1be52206' / f'{_PROOF_SHA}.json'

def verify_source_evidence() -> None:
    raw = _resolve_resource_path(_PROOF).read_bytes()
    if hashlib.sha256(raw).hexdigest() != _PROOF_SHA:
        raise RuntimeError('Pinned 1BE52206 evidence changed')
    proof = json.loads(raw)
    if proof.get('schema') != 'civ6rl.native_event_1be52206.static.v1' or proof['image']['sha256'] != 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63' or proof['registration']['callback_va'] != '0x140154660' or (proof['ring_allocator']['va'] != '0x1404f07c0') or (proof['callback']['raw_sha256'] != '13a0fd4fa7f721e34589bae93bfd0db43d04ba8347fd161d4ea88b38e353fb93') or (proof['ring_allocator']['reachable_bytes_sha256'] != '540357626f9fc104afb966489cb0bbf1b0cd828c6b64225c71240ff362e1beb9') or (proof['initial_ring_storage']['all_ring_bytes_in_zero_filled_virtual_tail'] is not True):
        raise RuntimeError('Pinned 1BE52206 producer identity changed')

def decode_fields(fields: dict[int, bytes]) -> dict[str, int]:
    """Decode only the complete three-scalar input shape witnessed by Core."""
    verify_source_evidence()
    if not isinstance(fields, dict) or set(fields) != {SELECTOR_KEY, VALUE_KEY, DESCRIPTOR_KEY}:
        raise ValueError('Unverified 1BE52206 field set')
    if any((not isinstance(raw, (bytes, bytearray, memoryview)) for raw in fields.values())):
        raise ValueError('Unverified 1BE52206 variant bytes')
    return {'selector': decode_scalar(fields[SELECTOR_KEY], 3), 'value': decode_scalar(fields[VALUE_KEY], 2), 'descriptor': decode_scalar(fields[DESCRIPTOR_KEY], 2)}

class NativePrivateRing1BE52206:
    """Retain proven type54/type57 records without consumption or rotation.

    The profile is explicit: only this callback's records enter a newly zeroed
    diagnostic bank. Type57 is separately proved by native_event_66ade3b3.
    Other native producers and the original consumer are not
    modeled. A Python lock serializes reservations/copies; this does not claim
    the original multi-thread scheduler or its publication ordering.
    """
    consumer_validated = False
    training_eligible = False

    def __init__(self, *, profile: str):
        verify_source_evidence()
        if profile != DIAGNOSTIC_PROFILE:
            raise ValueError('1BE52206 requires the explicit unconsumed diagnostic profile')
        self.profile = profile
        self._cursor = 0
        self._records: list[bytes] = []
        self._lock = threading.Lock()

    @property
    def cursor(self) -> int:
        with self._lock:
            return self._cursor

    @property
    def record_count(self) -> int:
        with self._lock:
            return len(self._records)

    @property
    def records(self) -> tuple[bytes, ...]:
        with self._lock:
            return tuple(self._records)

    def append_fields(self, fields: dict[int, bytes], *, thread_selector: int=0, bank_index: int=0) -> bytes:
        """Apply allocator/header and callback stores, then retain exact bytes.

        The source allocator permits the reservation ending at exactly 4 MiB.
        On overflow it returns NULL, which the callback dereferences. Refuse
        that unsafe state before mutation; never silently drop or wrap it.
        """
        values = decode_fields(fields)
        return self._append_payload(RECORD_TYPE, struct.pack('<II', values['descriptor'], values['value']), thread_selector=thread_selector, bank_index=bank_index)

    def append_turn_complete_fields(self, fields: dict[int, bytes], *, thread_selector: int=0, bank_index: int=0) -> bytes:
        """Append 66ADE3B3's type57 after its standard deferred record."""
        from civ6_host.runtime.native.native_event_66ade3b3 import decode_fields as decode_turn_complete
        value = decode_turn_complete(fields)['value']
        return self._append_payload(87, struct.pack('<I', value), thread_selector=thread_selector, bank_index=bank_index)

    def _append_payload(self, record_type: int, payload: bytes, *, thread_selector: int, bank_index: int) -> bytes:
        if record_type not in (84, 87) or len(payload) != {84: 8, 87: 4}[record_type]:
            raise ValueError('Unproven private-ring producer layout')
        if type(thread_selector) is not int or thread_selector != 0:
            raise ValueError('Unmodeled 1BE52206 private-ring thread selector')
        if type(bank_index) is not int or bank_index != 0:
            raise ValueError('Unmodeled 1BE52206 private-ring bank rotation')
        with self._lock:
            if self._cursor != len(self._records) * RECORD_SIZE or self._cursor % RECORD_SIZE or self._cursor < 0:
                raise RuntimeError('Corrupt 1BE52206 diagnostic ring state')
            next_cursor = self._cursor + RECORD_SIZE
            if next_cursor > BANK_CAPACITY:
                raise ValueError('1BE52206 private ring full; consumer remains unimplemented')
            record = bytearray(RECORD_SIZE)
            struct.pack_into('<IIII', record, 0, RECORD_SIZE, record_type, 0, 0)
            record[16:16 + len(payload)] = payload
            result = bytes(record)
            self._records.append(result)
            self._cursor = next_cursor
            return result

    def diagnostic(self) -> dict:
        with self._lock:
            types = sorted({struct.unpack_from('<I', record, 4)[0] for record in self._records})
            return {'profile': self.profile, 'event_kinds': ['0x1be52206', '0x66ade3b3'], 'record_types': types, 'record_size': RECORD_SIZE, 'record_count': len(self._records), 'cursor': self._cursor, 'bank_capacity': BANK_CAPACITY, 'thread_selector': 0, 'bank_index': 0, 'consumer_validated': False, 'training_eligible': False, 'retained_without_consumption': True}
__all__ = ['EVENT_KIND', 'RECORD_TYPE', 'RECORD_SIZE', 'BANK_CAPACITY', 'DIAGNOSTIC_PROFILE', 'NativePrivateRing1BE52206', 'decode_fields', 'verify_source_evidence']
