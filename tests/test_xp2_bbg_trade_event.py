"""Typed, lossless capture boundary for current XP2 BBG trade activity."""
import struct
import unittest
from types import SimpleNamespace

from civ6_host.runtime.a0_xp2_bbg_trade import (
    dispatch, consume, KIND, RECORD_TYPE, RECORD_SIZE,
    TURN_KIND, TURN_RECORD_TYPE, TURN_RECORD_SIZE,
)
from civ6_host.runtime.native.native_event_5d706996 import FIRST_KEY, SECOND_KEY, SELECTOR_KEY


def _variant(pointer):
    return struct.pack('<HHIQII', 1024, 0, 0, pointer, 8, 553648129)


class BBGTradeEventTests(unittest.TestCase):
    def _owner(self):
        owner = SimpleNamespace()
        owner._bbg_trade_image_id = 'xp2-gamecore-current-092abfbb'
        owner.bbg_trade_event_profile = SimpleNamespace(
            record_types_by_kind={KIND: {RECORD_TYPE}, TURN_KIND: {TURN_RECORD_TYPE}},
            record_sizes={RECORD_TYPE: RECORD_SIZE, TURN_RECORD_TYPE: TURN_RECORD_SIZE})
        owner._bbg_trade_max_pending = 2
        owner.pending = []
        owner._sequence = 0
        owner.read = lambda pointer, size: struct.pack('<HHI', *(
            (0, 65535, 0xFFFFFFFF) if pointer == 0x1000 else (7, 0, 0xFFFFFFFF)
        ))
        owner._enqueue = lambda record: (owner.pending.append(record), setattr(owner, '_sequence',
                                                                               owner._sequence + 1))
        return owner

    def test_callback_copies_typed_values_and_receiver_runs_only_at_fifo_consume(self):
        owner = self._owner()
        fields = {
            FIRST_KEY: _variant(0x1000), SECOND_KEY: _variant(0x2000),
            SELECTOR_KEY: struct.pack('<H6xI8xI', 3, 0xFFFFFFFF, 0),
        }
        self.assertEqual(dispatch(owner, KIND, fields, 0x9000), 0)
        record = owner.pending[0]
        self.assertEqual((len(record), int.from_bytes(record[4:8], 'little')),
                         (RECORD_SIZE, RECORD_TYPE))
        self.assertEqual(struct.unpack_from('<i', record, 88)[0], -1)
        self.assertEqual(struct.unpack_from('<h', record, 96)[0], 0)
        self.assertEqual(struct.unpack_from('<h', record, 104)[0], 7)
        self.assertEqual(struct.unpack_from('<i', record, 100)[0], -1)
        self.assertEqual(struct.unpack_from('<i', record, 108)[0], -1)
        calls = []
        owner._bbg_trade_receiver = owner._bbg_trade_callback = lambda *values: calls.append(values)
        owner._bbg_trade_backend = object()
        deferred = SimpleNamespace(_draining_empty_receivers=True, pending=owner.pending,
                                   consumed_count=0, consumed_bytes=0,
                                   consumed_digest=__import__('hashlib').sha256())
        owner.deferred = deferred
        consume(owner, record, 1)
        self.assertEqual(calls, [(1, -1, 0, -1, 7, -1)])
        self.assertEqual(deferred.pending, [])

    def test_capacity_refuses_without_dropping_or_reordering(self):
        owner = self._owner()
        owner._sequence = 2
        owner.pending = [b'first', b'second']
        with self.assertRaisesRegex(RuntimeError, 'capacity exhausted'):
            dispatch(owner, KIND, {}, 0x9000)
        self.assertEqual(owner.pending, [b'first', b'second'])
        self.assertEqual(owner._sequence, 2)

    def test_local_turn_begin_uses_same_fifo_and_consumed_sequence_once(self):
        owner = self._owner()
        fields = {
            SELECTOR_KEY: struct.pack('<H6xI8xI', 3, 0, 0),
            3606901732: struct.pack('<H6xI8xI', 2, 1, 0),
        }
        self.assertEqual(dispatch(owner, TURN_KIND, fields, 0x9000), 0)
        record = owner.pending[0]
        self.assertEqual((len(record), int.from_bytes(record[4:8], 'little')),
                         (TURN_RECORD_SIZE, TURN_RECORD_TYPE))
        seen = []
        owner._bbg_trade_backend = object()
        owner._bbg_turn_receiver = owner._bbg_turn_callback = lambda sequence: seen.append(sequence)
        deferred = SimpleNamespace(_draining_empty_receivers=True, pending=owner.pending,
                                   consumed_count=0, consumed_bytes=0,
                                   consumed_digest=__import__('hashlib').sha256())
        owner.deferred = deferred
        consume(owner, record, 1)
        self.assertEqual(seen, [1])
        self.assertEqual((deferred.consumed_count, deferred.consumed_bytes, deferred.pending),
                         (1, TURN_RECORD_SIZE, []))


if __name__ == '__main__':
    unittest.main()
