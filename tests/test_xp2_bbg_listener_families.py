"""Compose typed listener owners with native zero/one-archive admission."""
from contextlib import nullcontext
import struct
from types import SimpleNamespace as NS
import unittest
from unittest.mock import Mock, patch

from civ6_host.runtime import xp2_bbg_promotion as promotion
from civ6_host.runtime import xp2_script_operation as script
from civ6_host.runtime.configuration_profiles import XP2_CORE_SHA256
from civ6_host.runtime.xp2_bbg_trade_feedback import TradeFeedback, _requests


class ListenerFamilyAuthorityTests(unittest.TestCase):
    def fixture(self, *, archive=False):
        pending, emitted = [], []
        deferred = NS(pending=[], _draining_empty_receivers=False, drain_empty_receivers=Mock())
        consumer = NS(bbg_trade_event_profile=object(), _bbg_trade_expected_property=None,
                      _bbg_amani_receiver=object(), _bbg_amani_property_scope=None,
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
        feedback = TradeFeedback(c, object(), NS(active=lambda: nullcontext()))
        submitted = []
        def submit(core, context, player, parameters, **kwargs):
            submitted.append((player, parameters))
            self.assertEqual(player, 1)
            if parameters[b'OnStart'] == b'GameplaySetCSTrader':
                self.assertEqual(consumer._bbg_trade_expected_property, (1, 11))
                self.assertEqual(consumer._bbg_amani_property_scope, (1, frozenset({(4, 9)}), False))
            if archive:
                pending.append(struct.pack('<I', 3294486831) + b'owned-native-fixture')
            return {'request_invoked': True, 'native_parameters_verified': True,
                    'gameplay_outcome_verified': False}
        return feedback, c, emitted, submitted, submit

    def promotion_event(self, feedback):
        record = bytearray(112)
        struct.pack_into('<III', record, 0, 112, promotion.RECORD_TYPE, 19)
        struct.pack_into('<I4xh2xii', record, 80, 19, 1, 131073, 14)
        feedback.promotion(19, *promotion.event_request(bytes(record), 19))
        self.assertEqual(promotion.event_source(bytes(record), 19),
                         b'return Civ6HostBBGPromotion(1,131073,14)')

    def promotion_readbacks(self, feedback, after=b'14', request=b'1,131073'):
        xp = iter([b'14', after])
        def evaluate(source, name, **kwargs):
            if name == b'@bbg751_promotion_ui_event':
                self.assertEqual(source, b'return Civ6HostBBGPromotion(1,131073,14)')
                return request
            self.assertEqual(name, b'@bbg751_promotion_xp')
            self.assertIn(b'UnitManager.GetUnit(1, 131073)', source)
            return next(xp)
        feedback._evaluate = evaluate

    def test_foreign_promotion_preserves_event_owner_unit_and_native_noop(self):
        feedback, c, emitted, submitted, submit = self.fixture()
        self.promotion_event(feedback)
        self.promotion_readbacks(feedback)
        with patch.object(script, 'submit_script_operation', side_effect=submit):
            self.assertEqual(feedback.flush(), [])
        self.assertEqual(submitted, [(1, {b'OnStart': b'GameplayPromotionFixExp',
                                         b'iUnitPlayerID': 1, b'iUnitID': 131073})])
        self.assertEqual(emitted[-1][0], 'xp2_bbg_promotion_request_filtered')
        self.assertFalse(emitted[-1][1]['native_effect_observed'])
        c.transport.deliver_one.assert_not_called()
        self.assertEqual(c.observation, {'player_id': 0})

    def test_active_foreign_promotion_delivers_one_archive_and_reads_its_unit(self):
        feedback, c, emitted, _, submit = self.fixture(archive=True)
        self.promotion_event(feedback)
        self.promotion_readbacks(feedback, b'15')
        with patch.object(script, 'submit_script_operation', side_effect=submit):
            feedback.flush()
        c.transport.deliver_one.assert_called_once()
        self.assertEqual(emitted[-1][0], 'xp2_bbg_promotion_gameplay_delivered')
        self.assertEqual((emitted[-1][1]['player_id'], emitted[-1][1]['xp_after']), (1, 15))

    def test_promotion_rejects_owner_or_unit_substitution_before_native_submission(self):
        for request in (b'0,131073', b'1,131074'):
            with self.subTest(request=request):
                feedback, _, emitted, _, _ = self.fixture()
                self.promotion_event(feedback)
                self.promotion_readbacks(feedback, request=request)
                with patch.object(script, 'submit_script_operation') as native:
                    with self.assertRaisesRegex(ValueError, 'native event'):
                        feedback.flush()
                native.assert_not_called()
                self.assertEqual(emitted, [])

    def test_filtered_promotion_cannot_hide_an_experience_change(self):
        feedback, _, emitted, _, submit = self.fixture()
        self.promotion_event(feedback)
        self.promotion_readbacks(feedback, b'15')
        with patch.object(script, 'submit_script_operation', side_effect=submit):
            with self.assertRaisesRegex(RuntimeError, 'Filtered BBG promotion'):
                feedback.flush()
        self.assertEqual(emitted, [])

    def trade_readbacks(self, feedback, *, after=b'absent', changed_plot=False, buffered=False,
                        request=b'1,11,7'):
        properties = iter([b'7' if buffered else b'absent', after])
        def prop(player, city):
            self.assertEqual((player, city), (1, 11))
            return next(properties)
        feedback._property = prop
        states = iter([(None, {11: (False, False)}, {11: (4, 9)}),
                       (None, {11: (False, changed_plot)}, {11: (4, 9)})])
        def amani(player):
            self.assertEqual(player, 1)
            return next(states)
        feedback._amani_properties = amani
        def evaluate(source, name, **kwargs):
            self.assertEqual(name, b'@bbg751_trade_ui_event')
            self.assertEqual(source, b'return Civ6HostBBGTradeFeedback.turn_begin()' if buffered
                             else b'return Civ6HostBBGTradeFeedback.activity(0,1,11,7,22)')
            return request
        feedback._evaluate = evaluate

    def test_trade_uses_origin_not_selector_and_filtered_request_is_not_delivered(self):
        feedback, c, emitted, submitted, submit = self.fixture()
        feedback.activity(19, 0, 1, 11, 7, 22)
        self.trade_readbacks(feedback)
        with patch.object(script, 'submit_script_operation', side_effect=submit):
            self.assertEqual(feedback.flush(), [])
        self.assertEqual(submitted[0], (1, {b'OnStart': b'GameplaySetCSTrader',
            b'iOriginPlayerID': 1, b'iOriginCityID': 11, b'iTargetPlayerID': 7}))
        self.assertEqual(emitted[-1][0], 'xp2_bbg_trade_request_filtered')
        c.transport.deliver_one.assert_not_called()
        self.assertIsNone(c.prefix.event_arguments.consumer._bbg_trade_expected_property)
        self.assertIsNone(c.prefix.event_arguments.consumer._bbg_amani_property_scope)

    def test_active_foreign_trade_and_buffered_removal_keep_the_original_owner(self):
        for buffered, request, after in ((False, b'1,11,7', b'7'), (True, b'1,11,-7', b'')):
            with self.subTest(buffered=buffered):
                feedback, c, emitted, submitted, submit = self.fixture(archive=True)
                if buffered:
                    feedback.turn_begin(19)
                else:
                    feedback.activity(19, 0, 1, 11, 7, 22)
                self.trade_readbacks(feedback, after=after, buffered=buffered, request=request)
                with patch.object(script, 'submit_script_operation', side_effect=submit):
                    delivered = feedback.flush()
                c.transport.deliver_one.assert_called_once()
                self.assertEqual(submitted[0][0], 1)
                self.assertEqual(delivered[0]['origin_player_id'], 1)
                self.assertEqual(delivered[0]['trader_property_after'], after.decode('ascii'))
                self.assertEqual(emitted, [])
                self.assertEqual(c.observation, {'player_id': 0})

    def test_trade_rejects_owner_city_or_target_substitution(self):
        for request in (b'0,11,7', b'1,12,7', b'1,11,8'):
            with self.subTest(request=request):
                feedback, _, emitted, _, _ = self.fixture()
                feedback.activity(19, 0, 1, 11, 7, 22)
                self.trade_readbacks(feedback, request=request)
                with patch.object(script, 'submit_script_operation') as native:
                    with self.assertRaisesRegex(ValueError, 'native event'):
                        feedback.flush()
                native.assert_not_called()
                self.assertEqual(emitted, [])

    def test_filtered_trade_cannot_hide_trader_or_plot_property_changes(self):
        for after, changed_plot in ((b'7', False), (b'absent', True)):
            with self.subTest(after=after, changed_plot=changed_plot):
                feedback, _, emitted, _, submit = self.fixture()
                feedback.activity(19, 0, 1, 11, 7, 22)
                self.trade_readbacks(feedback, after=after, changed_plot=changed_plot)
                with patch.object(script, 'submit_script_operation', side_effect=submit):
                    with self.assertRaisesRegex(RuntimeError, 'Filtered BBG trade'):
                        feedback.flush()
                self.assertEqual(emitted, [])

    def test_filtered_trade_requests_still_count_toward_the_submission_bound(self):
        feedback, _, _, _, _ = self.fixture()
        feedback.turn_begin(19)
        feedback.turn_begin(20)
        feedback._evaluate = Mock(side_effect=[b'1,11,-7;1,11,-8', b'1,11,-9'])
        feedback._deliver = Mock(return_value=None)
        with patch('civ6_host.runtime.xp2_bbg_trade_feedback._CAPACITY', 2):
            with self.assertRaisesRegex(RuntimeError, 'delivery bound'):
                feedback.flush()
        self.assertEqual(feedback._deliver.call_count, 2)

    def test_buffered_request_parser_retains_owners_but_rejects_malformed_identities(self):
        self.assertEqual(_requests(b'1,11,-7;2,12,-8'), [(1, 11, -7), (2, 12, -8)])
        for raw in (b'-1,11,7', b'64,11,7', b'01,11,7', b'1,-1,7', b'1,11,32768'):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                _requests(raw)


if __name__ == '__main__':
    unittest.main()
