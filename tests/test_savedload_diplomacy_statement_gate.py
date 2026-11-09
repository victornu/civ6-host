"""Keep the XP2 type-132 SavedLoad route explicitly closed until source closes."""
import ctypes as C
import struct
import types
import unittest
from unittest.mock import Mock, patch

from civ6_host.runtime.a0_family_service import A0FamilyService
from civ6_host.runtime.configuration_profiles import XP2_CORE_SHA256
from civ6_host.runtime.deferred_service import DeferredService
from civ6_host.runtime.event_argument_service import EventArgumentService
from civ6_host.runtime.native.native_host import DiagnosticHost


PROFILE = dict(observer_registered=False, state_pointer_nonnull=True,
               pre_hook=None, post_hook=None, subscriber_count=0, state_flags=0)


class Host:
    _bind = DiagnosticHost._bind

    def __init__(self):
        self.vtable = (C.c_void_p * 64)()
        self.functions = []
        self.emit = Mock()
        self.pointer = 123
        for slot in (0xB0, 0xE8, 0xF0):
            self._bind(self.vtable, slot, None, [C.c_void_p], lambda _: None)

    def _check(self, pointer):
        if pointer != self.pointer:
            raise ValueError('Foreign receiver')

    def _fatal(self, *args, **kwargs):
        raise AssertionError((args, kwargs))


class SavedLoadDiplomacyStatementGateTests(unittest.TestCase):
    def setUp(self):
        self.host = Host()
        self.reader = types.SimpleNamespace(fields=Mock(), read=Mock(), close=Mock(),
                                            core_sha256=XP2_CORE_SHA256)
        for target in (
            'civ6_host.runtime.cache_update_profiles.verify_dispatch_live',
            'civ6_host.runtime.cache_update_profiles.verify_notification_live',
            'civ6_host.runtime.event_argument_source.verify_host_live',
        ):
            p = patch(target, return_value={})
            p.start()
            self.addCleanup(p.stop)
        reader_patch = patch(
            'civ6_host.runtime.event_argument_service.EventArgumentReader',
            return_value=self.reader)
        reader_patch.start()
        self.addCleanup(reader_patch.stop)
        self.deferred = DeferredService(
            self.host, types.SimpleNamespace(_handle=0x1000), 0x2000,
            core_sha256=XP2_CORE_SHA256, read=self.reader.read, emit=Mock(),
            optional_preprocessor=None, queue_metadata_service=None)
        self.arguments = EventArgumentService(
            self.host, self.deferred.core, 0x2000, self.deferred,
            core_sha256=XP2_CORE_SHA256, read=self.reader.read, emit=Mock(),
            normalizer_transform=None, dynamic_registrations=())
        self.a0 = self.arguments.install_consumers(
            receiver_state=dict(PROFILE), pre_turn_immediate_state=dict(PROFILE),
            entity_listener_count=0)

    def test_type132_remains_ordered_and_unanswered_when_xp2_binding_is_missing(self):
        record = bytearray(112)
        struct.pack_into('<III', record, 0, 112, 132, 1)
        head = bytes(record)
        self.deferred._enqueue(head)

        self.assertIs(self.a0.deferred, self.deferred)
        self.assertFalse(self.a0.handles_record(132))
        self.assertEqual(self.deferred.pending_diplomacy_statements, [])
        with self.assertRaisesRegex(
                RuntimeError,
                'XP2 RequestSession-to-FC731E25 producer binding.*field/post-hook profile'):
            self.deferred.drain()

        self.assertEqual(self.deferred.pending, [head])
        self.assertEqual((self.deferred.consumed_count, self.deferred.consumed_bytes), (0, 0))
        self.assertEqual(self.deferred.pending_diplomacy_statements, [])
        self.assertEqual(self.deferred.emit.call_count, 0)
        self.assertTrue(self.deferred._deferred_drain_poisoned)

