"""Two-bank diagnostic model of the source-pinned private ring.

The model starts from a fresh zero-filled bank pair and reproduces reservation
and flush bookkeeping for the explicit empty-receiver profile. It is a Python
snapshot model only: it does not call native code, reproduce trace wrappers,
or establish general listener/runtime equivalence.
"""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import struct
import threading
from types import MappingProxyType
from typing import Mapping
from civ6_host.runtime.native import native_event_1be52206 as producer54
from civ6_host.runtime.native import native_event_66ade3b3 as producer57
from civ6_host.runtime.native.native_private_ring_consumer import BANK_CAPACITY
from civ6_host.runtime.native.native_private_ring_consumer import DISPATCH_TABLE
from civ6_host.runtime.native.native_private_ring_consumer import EMPTY_RECEIVER_PROFILE
from civ6_host.runtime.native.native_private_ring_consumer import HandlerRowSnapshot
from civ6_host.runtime.native.native_private_ring_consumer import consume_empty_bank
from civ6_host.runtime.native.native_private_ring_consumer import verify_source_evidence
RECORD_SIZE = 128
TYPE_54 = 84
TYPE_57 = 87
_HANDLERS = {TYPE_54: 5369693840, TYPE_57: 5369694128}
_DESTRUCTOR = 5369667808
_LOGICAL_LIST_BASE = 123145302310912

def _source_empty_table_state() -> Mapping[int, HandlerRowSnapshot]:
    """Build the two explicitly initialized, logically allocated empty rows.

    The row/list bytes follow the pinned EXE initializers. Pointer values for
    the lists are stable model addresses; they do not point into this process
    or into an actual EXE allocation.
    """
    verify_source_evidence()
    result = {}
    for record_type, handler in _HANDLERS.items():
        row_address = DISPATCH_TABLE + record_type * 48
        list_address = _LOGICAL_LIST_BASE + record_type * 256
        row = bytearray(48)
        struct.pack_into('<QQQQQQ', row, 0, 0, 0, 0, list_address, handler, _DESTRUCTOR)
        listeners = bytearray(56)
        struct.pack_into('<Q', listeners, 0, 268435455)
        struct.pack_into('<QQQ', listeners, 8, 0, 0, 0)
        struct.pack_into('<I', listeners, 32, 0)
        struct.pack_into('<II', listeners, 36, 268435455, 268435455)
        listeners[48] = 0
        result[record_type] = HandlerRowSnapshot(row_address=row_address, row_bytes=bytes(row), list_address=list_address, list_bytes=bytes(listeners))
    return MappingProxyType(result)

class NativePrivateRingProfile:
    """Source-bounded 2-bank model for native records 0x54 and 0x57.

    Cursor resets affect only the newly active bank. Bank bytes remain in place
    so later writes preserve bytes the EXE allocator/callback do not overwrite.
    The flush result reports a read offset and unchanged old cursor; it never
    pretends the native reader reset that cursor.
    """
    training_eligible = False

    def __init__(self, *, profile: str):
        verify_source_evidence()
        if profile != EMPTY_RECEIVER_PROFILE:
            raise ValueError('Private ring requires the explicit empty-receiver diagnostic profile')
        self.profile = profile
        self._banks = [bytearray(BANK_CAPACITY), bytearray(BANK_CAPACITY)]
        self._cursors = [0, 0]
        self._selector = 0
        self._highwater = 0
        self._table_state = _source_empty_table_state()
        self._lock = threading.RLock()
        self._poisoned = False
        self._flush_count = 0

    @property
    def selector(self) -> int:
        with self._lock:
            return self._selector

    @property
    def cursors(self) -> tuple[int, int]:
        with self._lock:
            return tuple(self._cursors)

    @property
    def highwater(self) -> int:
        with self._lock:
            return self._highwater

    @property
    def poisoned(self) -> bool:
        with self._lock:
            return self._poisoned

    @property
    def flush_count(self) -> int:
        with self._lock:
            return self._flush_count

    def bank_snapshot(self, bank_index: int) -> bytes:
        with self._lock:
            self._check_bank_index(bank_index)
            return bytes(self._banks[bank_index])

    def bank_prefix(self, bank_index: int, length: int | None=None) -> bytes:
        with self._lock:
            self._check_bank_index(bank_index)
            end = self._cursors[bank_index] if length is None else length
            if type(end) is not int or end < 0 or end > BANK_CAPACITY:
                raise ValueError('Invalid private-ring snapshot length')
            return bytes(self._banks[bank_index][:end])

    @staticmethod
    def _check_bank_index(bank_index: int) -> None:
        if type(bank_index) is not int or bank_index not in (0, 1):
            raise ValueError('Private-ring bank index must be 0 or 1')

    def _ensure_live(self) -> None:
        if self._poisoned:
            raise RuntimeError('Private ring is poisoned after a failed consumer validation')

    def append_fields(self, fields: dict[int, bytes]) -> bytes:
        values = producer54.decode_fields(fields)
        payload = struct.pack('<II', values['descriptor'], values['value'])
        return self._append(TYPE_54, payload)

    def append_turn_complete_fields(self, fields: dict[int, bytes]) -> bytes:
        values = producer57.decode_fields(fields)
        payload = struct.pack('<I', values['value'])
        return self._append(TYPE_57, payload)

    def _append(self, record_type: int, payload: bytes) -> bytes:
        if record_type not in _HANDLERS or len(payload) != (8 if record_type == TYPE_54 else 4):
            raise ValueError('Unproven private-ring producer record')
        with self._lock:
            self._ensure_live()
            bank_index = self._selector & 1
            cursor = self._cursors[bank_index]
            if cursor % RECORD_SIZE or cursor < 0 or cursor > BANK_CAPACITY - RECORD_SIZE:
                raise ValueError('Private ring full or cursor is invalid; no record was dropped')
            next_cursor = cursor + RECORD_SIZE
            bank = self._banks[bank_index]
            struct.pack_into('<IIII', bank, cursor, RECORD_SIZE, record_type, 0, 0)
            bank[cursor + 16:cursor + 16 + len(payload)] = payload
            self._cursors[bank_index] = next_cursor
            return bytes(bank[cursor:next_cursor])

    def flush(self):
        """Flip banks, reset only the new cursor, then validate/read old bank.

        On validation failure, the source-like selector/highwater/cursor flip
        remains visible and the profile becomes poisoned so later appends cannot
        overwrite a bank whose records were not accepted by this diagnostic
        consumer.
        """
        with self._lock:
            self._ensure_live()
            old_selector = self._selector
            old_bank = old_selector & 1
            next_selector = old_selector + 1 & 4294967295
            new_bank = next_selector & 1
            old_cursor = self._cursors[old_bank]
            self._selector = next_selector
            self._cursors[new_bank] = 0
            self._highwater = max(self._highwater, old_cursor)
            self._flush_count += 1
            try:
                return consume_empty_bank(memoryview(self._banks[old_bank])[:old_cursor], old_cursor, table_state=self._table_state, table_base=DISPATCH_TABLE, profile=EMPTY_RECEIVER_PROFILE)
            except Exception:
                self._poisoned = True
                raise

    def diagnostic(self) -> dict:
        with self._lock:
            return {'profile': self.profile, 'selector': self._selector, 'bank_cursors': list(self._cursors), 'highwater': self._highwater, 'flush_count': self._flush_count, 'poisoned': self._poisoned, 'receiver_profile': 'source-initialized-logical-empty-rows-0x54-and-0x57', 'consumer_mode': 'pure-snapshot-empty-list-accounting', 'native_wrapper_instrumentation_reproduced': False, 'training_eligible': False}
__all__ = ['RECORD_SIZE', 'BANK_CAPACITY', 'TYPE_54', 'TYPE_57', 'NativePrivateRingProfile']
