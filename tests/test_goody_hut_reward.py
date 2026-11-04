import hashlib
import struct
import unittest
from unittest.mock import Mock

from civ6_host.runtime import goody_hut_reward as event
from civ6_host.runtime.native.native_absent_305c2e09 import REGISTRY_PROFILE
from civ6_host.runtime.native.native_host_events import NativeDeferredHostEvents
from civ6_host.runtime.native.native_deferred_empty_profile import validate_empty_profile_record


EMPTY = dict(observer_registered=False, state_pointer_nonnull=True,
             pre_hook=None, post_hook=None, subscriber_count=0, state_flags=0)


def scalar(tag, value):
    raw = bytearray(24)
    struct.pack_into('<H', raw, 0, tag)
    struct.pack_into('<I', raw, 8, value)
    return bytes(raw)


def raw_fields(city=False):
    return {
        event.SELECTOR_KEY: scalar(3, 0),
        event.VALUE_KEY: scalar(2, 0xC04B8E18),
        event.SECOND_KEY: scalar(2, 0x030ACE7B),
        event.CITY_KEY if city else event.UNIT_KEY:
            struct.pack('<HHIQII', 0x400, 0, 1, 0x1000, 8, 0x21000001),
    }


class GoodyHutRewardTests(unittest.TestCase):
    def owner(self, blob=b'\x05\x00\x01\x00\x01\x00\x02\x00'):
        # Use the actual generic queue/dispatcher, without constructing a DLL.
        owner = NativeDeferredHostEvents.__new__(NativeDeferredHostEvents)
        owner.callback_registry_profile = REGISTRY_PROFILE
        owner.dynamic_event_registration_present = False
        owner.normalizer_transform_present = False
        owner.entity_listener_count = 0
        owner.empty_receiver_state = EMPTY.copy()
        owner.pending = []
        owner.limit = 2
        owner._sequence = 0
        owner.consumed_count = 0
        owner.consumed_bytes = 0
        owner.consumed_digest = hashlib.sha256()
        owner.read = Mock(return_value=blob)
        owner.emit = Mock()
        return owner

    def encode(self, fields, **changes):
        options = dict(normalizer_transform_present=False,
            per_thread_hook_present=False, writer_metadata_callback_present=False,
            entity_listener_count=0, empty_receiver_state=EMPTY.copy())
        options.update(changes)
        return event.encode_record(7, fields, **options)

    def test_native_unit_witness_is_owned_and_drained_once(self):
        owner = self.owner()
        self.assertEqual(owner._dispatch_fields(event.EVENT_KIND, raw_fields()), 0)
        owner.read.assert_called_once_with(0x1000, 8)
        record = owner.pending[0]
        self.assertEqual(struct.unpack_from('<4I', record), (0x70, 0x103, 1, 0))
        self.assertEqual(struct.unpack_from('<HHI', record, 0x18), (5, 1, 131073))
        self.assertEqual(struct.unpack_from('<I', record, 0x48), (4,))
        self.assertEqual(struct.unpack_from('<HHIII', record, 0x58),
                         (5, 1, 131073, 0xC04B8E18, 0x030ACE7B))
        owner.read.side_effect = AssertionError('Borrowed descriptor expired')
        self.assertEqual(owner._drain_empty_receivers_once(), 1)
        self.assertEqual(owner._drain_empty_receivers_once(), 0)
        self.assertEqual(owner.consumed_count, 1)
        self.assertEqual(owner.consumed_bytes, 0x70)
        self.assertFalse(owner.pending)
        enqueued = owner.emit.call_args_list[0].kwargs
        self.assertFalse(enqueued['native_internal_dispatch_repeated'])
        self.assertFalse(enqueued['payload_exposed_to_learner'])

    def test_city_input_retains_absent_unit_normalizer_slot(self):
        reader = Mock(return_value=struct.pack('<HHI', 5, 2, 123))
        fields = event.decode_fields(raw_fields(city=True), reader)
        record = self.encode(fields)
        self.assertEqual(struct.unpack_from('<HHI', record, 0x18),
                         (0xFFFF, 0, 0xFFFFFFFF))
        self.assertEqual(struct.unpack_from('<HHI', record, 0x58),
                         (0xFFFF, 1, 0xFFFFFFFF))
        self.assertEqual(record[0x4C:0x50] + record[0x54:0x58] + record[0x68:0x70],
                         bytes(16))

    def test_partial_absent_unit_has_empty_metadata_but_preserved_payload(self):
        for owner, identifier in ((0xFFFF, 3), (5, 0xFFFFFFFF)):
            with self.subTest(owner=owner, identifier=identifier):
                fields = event.decode_fields(raw_fields(),
                    lambda p, n: struct.pack('<HHI', owner, 1, identifier))
                record = self.encode(fields)
                self.assertEqual(struct.unpack_from('<HHI', record, 0x18),
                                 (0xFFFF, 0, 0xFFFFFFFF))
                self.assertEqual(struct.unpack_from('<HHI', record, 0x58),
                                 (owner, 1, identifier))

    def test_unproven_envelopes_are_refused_without_enqueue(self):
        cases = []
        fields = raw_fields(); fields.pop(event.UNIT_KEY); cases.append(fields)
        fields = raw_fields(); fields[event.CITY_KEY] = fields[event.UNIT_KEY]; cases.append(fields)
        fields = raw_fields(); fields[event.SELECTOR_KEY] = scalar(3, 1); cases.append(fields)
        fields = raw_fields(); fields[event.VALUE_KEY] = scalar(4, 1); cases.append(fields)
        fields = raw_fields(); fields[event.UNIT_KEY] = bytes(24); cases.append(fields)
        for fields in cases:
            with self.subTest(keys=list(fields)):
                owner = self.owner()
                with self.assertRaises(ValueError):
                    owner._dispatch_fields(event.EVENT_KIND, fields)
                self.assertFalse(owner.pending)
                self.assertEqual(owner._sequence, 0)

    def test_invalid_descriptor_copy_is_refused(self):
        for blob in (b'', bytes(7), struct.pack('<HHI', 5, 2, 123)):
            with self.subTest(blob=blob):
                with self.assertRaises(ValueError):
                    event.decode_fields(raw_fields(), lambda p, n: blob)

    def test_active_hooks_and_listeners_are_not_dropped(self):
        fields = event.decode_fields(raw_fields(), self.owner().read)
        cases = [dict(normalizer_transform_present=True),
                 dict(per_thread_hook_present=True),
                 dict(writer_metadata_callback_present=True),
                 dict(entity_listener_count=1), dict(padding_policy='native-default')]
        for key, value in [('observer_registered', True), ('pre_hook', 1),
                           ('post_hook', 1), ('subscriber_count', 1),
                           ('state_pointer_nonnull', False), ('state_flags', 1)]:
            cases.append(dict(empty_receiver_state=dict(EMPTY, **{key: value})))
        for options in cases:
            with self.subTest(options=options):
                with self.assertRaises(ValueError):
                    self.encode(fields, **options)

    def test_failed_consumer_preserves_pending_record(self):
        owner = self.owner()
        owner._dispatch_fields(event.EVENT_KIND, raw_fields())
        owner.empty_receiver_state['subscriber_count'] = 1
        with self.assertRaises(ValueError):
            owner._drain_empty_receivers_once()
        self.assertEqual(len(owner.pending), 1)
        self.assertEqual(owner.consumed_count, 0)

    def test_registry_and_queue_bounds_are_checked_before_borrowing(self):
        for field, value in [('dynamic_event_registration_present', True),
                             ('callback_registry_profile', 'unknown'), ('limit', 0)]:
            with self.subTest(field=field):
                owner = self.owner(); setattr(owner, field, value)
                with self.assertRaises((ValueError, RuntimeError)):
                    owner._dispatch_fields(event.EVENT_KIND, raw_fields())
                owner.read.assert_not_called()
                self.assertFalse(owner.pending)

    def test_unknown_record_is_still_refused(self):
        header = struct.pack('<II', 8, 0xFFFFFFFE)
        with self.assertRaises(ValueError):
            validate_empty_profile_record(header, **EMPTY)


if __name__ == '__main__':
    unittest.main()
