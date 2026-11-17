"""Verify both installed XP1 visibility producers and the common FIFO."""

import struct
import unittest
from unittest.mock import patch

import pefile

from civ6_host.runtime import xp1_wmd_fallout_visibility as wmd
from civ6_host.runtime.a0_family_source import A0FamilyProfile
from civ6_host.runtime.execution_images import _XP1_PROFILE
from civ6_host.runtime.native.native_deferred_empty_profile import resolve_empty_receiver_row
from test_xp1_game_history_events import Fixture
from test_xp1_turn_a0 import scalar


class XP1FalloutVisibilityTests(unittest.TestCase):
    def test_live_bindings_and_current_receiver(self):
        proof = wmd.source(_XP1_PROFILE)
        self.assertIn(wmd.SOURCE[1], wmd.source_dependencies(_XP1_PROFILE).values())
        fixture = Fixture()
        self.addCleanup(fixture.close)
        core = fixture.backend.core
        core._civ6_host_execution_image = _XP1_PROFILE
        image = pefile.PE(_XP1_PROFILE.path, fast_load=True)
        self.addCleanup(image.close)
        wmd.verify_live(core, lambda address, size: image.get_data(address - core._handle, size))
        with self.assertRaisesRegex(ValueError, 'fallout visibility source differs'):
            wmd.verify_live(core, lambda address, size: bytes(size))
        receiver = resolve_empty_receiver_row(wmd.RECORD_TYPE, execution_image=_XP1_PROFILE)
        self.assertEqual(receiver['handler_va'], '0x1400da250')
        self.assertEqual(receiver['handler_body_sha256'], proof['exe']['receiver_handler']['sha256'])

    def test_both_shapes_copy_coordinates_and_preserve_native_scope(self):
        f = Fixture()
        self.addCleanup(f.close)
        b = f.backend
        b.core._civ6_host_execution_image = _XP1_PROFILE
        b.captured_bundle.content_profile = {
            'gameplay_scripts': dict(wmd.source(_XP1_PROFILE)['capture']['gameplay_scripts']),
        }
        old = f.owner.foundation_event_profile
        f.owner.foundation_event_profile = f.owner._foundation_event_profile = A0FamilyProfile(
            {**old.record_types_by_kind, wmd.KIND: frozenset((wmd.RECORD_TYPE,))},
            {**old.record_sizes, wmd.RECORD_TYPE: wmd.RECORD_SIZE}, wmd.SOURCE[1])
        addr = 0xa50000
        position = struct.pack('<ii', -17, 32)
        f.memory.put(addr, position)
        direct = {wmd.SELECTOR: scalar(3, 0), wmd.VALUE: scalar(2, 2),
                  wmd.POSITION: struct.pack('<H6xQII', 0, addr, 8, 0x21000001)}
        decorated = {**direct, wmd.PLAYER: scalar(2, 3), wmd.VALUE: scalar(2, 0),
                     wmd.POSITION: struct.pack('<H6xQII', 13, addr, 8, 0x21000001)}
        with self.assertRaisesRegex(ValueError, 'blob envelope'):
            wmd.decode_fields({**direct, wmd.PLAYER: scalar(2, 3)}, f.read)
        with self.assertRaisesRegex(ValueError, 'selector or value'):
            wmd.decode_fields({**direct, wmd.VALUE: scalar(2, 1)}, f.read)
        # The fixture only provides the storage for the already-populated cache.
        with patch('civ6_host.runtime.xp1_visibility_cache_gate.require_internal_cache'):
            f.deferred.host_notification_counter = 1
            for sequence, (fields, flag, value) in enumerate(
                    ((direct, 0x20, 2), (decorated, 0x40, 0)), 1):
                self.assertEqual(f.owner.dispatch(wmd.KIND, fields, 0), 0)
                record = f.deferred.pending[-1]
                self.assertEqual(struct.unpack_from('<IIQ', record), (96, 0xc9, sequence))
                self.assertEqual(struct.unpack_from('<I', record, 72), (flag,))
                self.assertEqual(struct.unpack_from('<IiiI', record, 80), (sequence, -17, 32, value))
                self.assertEqual(f.deferred.host_metadata_counter, 1)
        f.memory.put(addr, bytes(8))
        self.assertEqual(f.deferred.drain(), 2)
        self.assertIsNone(f.owner._foundation_borrow)
        f.deferred.host_notification_counter = f.deferred.host_metadata_counter = 0
