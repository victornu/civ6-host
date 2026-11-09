"""Exercise the installed current policy route on the shared A0 owner and FIFO."""
import hashlib
import json
import struct
import unittest
from pathlib import Path
from types import SimpleNamespace

import test_a0_family_service as shared
from civ6_host.runtime import a0_policy_unlock as policy
from civ6_host.runtime import a0_policy_unlock_current as current
from civ6_host.runtime.a0_family_source import family_profile
from civ6_host.runtime.execution_images import select
from civ6_host.runtime.native.native_core_context_profiles import profile_for_core
from civ6_host.runtime.native.native_deferred_empty_profile import resolve_empty_receiver_row
from civ6_host.runtime.paths import resource_root


class CurrentPolicyNotificationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.profile = family_profile()
        source = resource_root() / current.PROFILE_REF[0]
        core_path = Path(json.loads(source.read_text(encoding='utf-8'))['core_producer']['path'])
        cls.image = select(current.CURRENT_PROFILE_ID, core_path=core_path)
        cls.context_profile = profile_for_core(core_path, mode='context', execution_image=cls.image)
        cls.proof = current.source(cls.image)

    def setUp(self):
        image = self.image
        host, deferred, arguments, owner, reader, *_ = shared.A0FamilyServiceTests.fixture(
            self, image.reference_core_sha256,
        )
        self.host, self.deferred, self.arguments, self.owner, self.reader = (
            host, deferred, arguments, owner, reader,
        )
        self.backend = SimpleNamespace(
            stage='prepared', prefix=None, check_thread=lambda: None,
            load_abi=SimpleNamespace(core_sha256=image.reference_core_sha256),
            _xp1_commands_requested=True, host=host, core=deferred.core,
            context=deferred.context, profile=self.context_profile,
        )
        owner._foundation_backend = self.backend
        deferred.core._civ6_host_execution_image = image
        producer = self.proof['core_producer']
        self.raw = bytes.fromhex(producer['raw_hex'])
        self.address = deferred.core._handle + int(producer['rva'], 16)
        reader.read.side_effect = self.read_producer

    def read_producer(self, address, size):
        self.assertEqual((address, size), (self.address, len(self.raw)))
        return self.raw

    def dispatch(self, player):
        self.reader.fields.return_value = {
            current.SELECTOR_KEY: shared.scalar(3, 0),
            current.PLAYER_KEY: shared.scalar(2, player),
        }
        return self.arguments.dispatch(self.host.pointer, current.KIND, 0x9000)

    def test_current_profile_dispatches_and_consumes_two_records_in_order(self):
        pins = dict(policy.source_dependencies(execution_image=self.image))
        source_path = (resource_root() / current.PROFILE_REF[0]).resolve()
        self.assertEqual(pins[str(source_path)], current.PROFILE_SHA256)
        self.assertEqual(self.context_profile.core_sha256, current.CURRENT_CORE_SHA256)
        self.assertEqual(self.context_profile.source_core_sha256, self.image.reference_core_sha256)
        policy.enable(self.owner, self.backend)
        for seq, (notification, metadata, player) in enumerate(((0, 0, 5), (2, 7, 17)), 1):
            self.deferred.host_notification_counter = notification
            self.deferred.host_metadata_counter = metadata
            self.assertEqual(self.dispatch(player), 0)
            record = self.deferred.pending[-1]
            self.assertEqual(struct.unpack_from('<IIII', record), (96, 208, seq, 0))
            self.assertEqual(struct.unpack_from('<I', record, 80), (seq,))
            self.assertEqual(record[84:96], bytes(12))
            self.assertEqual((self.deferred.host_notification_counter, self.deferred.host_metadata_counter),
                             (notification, metadata))
        recorded = tuple(self.deferred.pending)
        self.assertEqual(self.deferred.drain(), 2)
        self.assertFalse(self.deferred.pending)
        self.assertEqual(self.deferred.consumed_count, 2)
        self.assertEqual(self.deferred.consumed_digest.digest(), hashlib.sha256(b''.join(recorded)).digest())
        self.assertEqual(self.deferred.drain(), 0)
        self.reader.read.assert_called_once_with(self.address, len(self.raw))
        receipts = [call.kwargs for call in self.deferred.emit.call_args_list
                    if call.args == ('native_deferred_empty_record_consumed',)]
        self.assertEqual([(row['sequence'], row['handler_va']) for row in receipts],
                         [(1, '0x1400da550'), (2, '0x1400da550')])

    def test_current_policy_does_not_admit_obsolescence_producer(self):
        policy.enable(self.owner, self.backend)
        self.assertEqual(resolve_empty_receiver_row(207)['handler_va'], '0x1400dad50')
        self.assertEqual(current.receiver_row(self.image)['handler_va'], '0x1400da550')
        self.assertEqual((policy.KIND, policy.RECORD_TYPE), (current.KIND, 208))
        self.owner.active_kind = 0xd127ff37
        try:
            with self.assertRaisesRegex(ValueError, 'Unqualified current-image record-207 producer'):
                self.owner._enqueue(struct.pack('<II88x', 96, 207))
        finally:
            self.owner.active_kind = None
        self.assertFalse(self.deferred.pending)

    def test_wrong_live_producer_is_refused_before_enabling(self):
        self.reader.read.side_effect = None
        self.reader.read.return_value = bytes(len(self.raw))
        with self.assertRaisesRegex(ValueError, 'Live current Core policy producer differs'):
            policy.enable(self.owner, self.backend)
        self.assertFalse(self.owner.handles_kind(current.KIND))
        self.assertFalse(self.deferred.pending)
