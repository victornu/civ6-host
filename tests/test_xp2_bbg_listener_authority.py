"""Owned foreign-player callbacks retain the native gate, not public authority."""
from contextlib import nullcontext
import struct
from types import SimpleNamespace as NS
import unittest
from unittest.mock import Mock, patch

from civ6_host.runtime import xp2_script_operation as script
from civ6_host.runtime.configuration_profiles import XP2_CORE_SHA256
from civ6_host.runtime.xp2_bbg_amani import event_request
from civ6_host.runtime.xp2_bbg_trade_feedback import TradeFeedback


class ListenerAuthorityTests(unittest.TestCase):
    def fixture(self, *, archive=False, property_changed=False):
        pending, emitted = [], []
        deferred = NS(pending=[], _draining_empty_receivers=False,
                      drain_empty_receivers=Mock())
        consumer = NS(_bbg_amani_receiver=object(), _bbg_amani_property_scope=None,
                      active_kind=None, pending=[], deferred=deferred)
        def empty():
            if pending:
                raise ValueError('Native queue is not empty')
        transport = NS(pending=pending, require_empty_native_queue=empty,
                       deliver_one=Mock(side_effect=lambda: pending.pop(0)))
        owner = NS(load_abi=NS(core_sha256=XP2_CORE_SHA256), core=object(), context=123,
                   runtime=NS(read=Mock()), emit=lambda stage, **kw: emitted.append((stage, kw)))
        c = NS(check=Mock(), owner=owner, observation={'player_id': 0}, transport=transport,
               publishing=False, prefix=NS(deferred_events=deferred,
               event_arguments=NS(consumer=consumer)), ui_child=object())
        reader = NS(active=lambda: nullcontext())
        feedback = TradeFeedback(c, object(), reader)
        properties = iter([b'absent;11,4,9,0,0',
                           b'1,22,7,0;11,4,9,0,0' if property_changed else b'absent;11,4,9,0,0'])
        def evaluate(child, source, name, **kwargs):
            if name == b'@bbg751_amani_ui_event':
                self.assertEqual(source, b'return Civ6HostBBGAmani.assigned(7,22,1,1)')
                return b'1,22,7,0'
            self.assertEqual(name, b'@bbg751_amani_property_readback')
            self.assertIn(b'Players[1]', source)
            return next(properties)
        c.runtime = NS(evaluate_text=evaluate)
        def submit(core, context, player, parameters, **kwargs):
            self.assertEqual(player, 1)
            self.assertEqual(parameters[b'iGovernorOwnerID'], 1)
            self.assertEqual(consumer._bbg_amani_property_scope, (1, frozenset({(4,9)}), True))
            if archive:
                pending.append(struct.pack('<I', 3294486831) + b'owned-native-fixture')
            return {'request_invoked': True, 'native_parameters_verified': True,
                    'gameplay_outcome_verified': False}
        return feedback, c, emitted, submit

    def test_foreign_governor_owner_survives_record_and_native_noop(self):
        record = bytearray(112)
        struct.pack_into('<III', record, 0, 112, 223, 19)
        struct.pack_into('<I4xh2xiii', record, 80, 19, 7, 22, 1, 1)
        player, source = event_request(bytes(record), 19)
        self.assertEqual(player, 1)
        feedback, c, emitted, submit = self.fixture()
        feedback.governor(19, player, source)
        with patch.object(script, 'submit_script_operation', side_effect=submit) as native:
            self.assertEqual(feedback.flush(), [])
        native.assert_called_once()
        c.transport.deliver_one.assert_not_called()
        c.prefix.deferred_events.drain_empty_receivers.assert_not_called()
        self.assertEqual(emitted, [('xp2_bbg_amani_request_filtered', {
            'event_sequence': 19, 'player_id': 1, 'local_player_id': 0,
            'native_archive_delivered': False, 'native_effect_observed': False})])
        self.assertIsNone(c.prefix.event_arguments.consumer._bbg_amani_property_scope)

    def test_active_foreign_listener_can_deliver_without_becoming_a_public_action(self):
        feedback, c, emitted, submit = self.fixture(archive=True, property_changed=True)
        feedback.governor(19, 1, b'return Civ6HostBBGAmani.assigned(7,22,1,1)')
        with patch.object(script, 'submit_script_operation', side_effect=submit):
            feedback.flush()
        c.transport.deliver_one.assert_called_once()
        self.assertEqual(emitted[-1][0], 'xp2_bbg_amani_gameplay_delivered')
        self.assertEqual(emitted[-1][1]['player_id'], 1)
        self.assertEqual(c.observation, {'player_id': 0})

    def test_filtered_request_cannot_hide_a_property_change(self):
        feedback, c, emitted, submit = self.fixture(property_changed=True)
        feedback.governor(19, 1, b'return Civ6HostBBGAmani.assigned(7,22,1,1)')
        with patch.object(script, 'submit_script_operation', side_effect=submit):
            with self.assertRaisesRegex(RuntimeError, 'Filtered BBG governor'):
                feedback.flush()
        self.assertEqual(emitted, [])

    def test_local_script_path_still_refuses_a_foreign_player(self):
        _, c, _, _ = self.fixture()
        with patch.object(script, 'submit_script_operation') as native:
            with self.assertRaisesRegex(ValueError, 'active XP2 player view'):
                script.deliver_script_operation(c, 1, {b'OnStart':b'test'})
        native.assert_not_called()

    def test_listener_output_cannot_cross_its_native_event_owner(self):
        feedback, c, emitted, _ = self.fixture()
        feedback.governor(19, 0, b'return Civ6HostBBGAmani.assigned(7,22,1,1)')
        with patch.object(script, 'submit_script_operation') as native:
            with self.assertRaisesRegex(ValueError, 'current player authority'):
                feedback.flush()
        native.assert_not_called()
        self.assertEqual(emitted, [])


if __name__ == '__main__':
    unittest.main()
