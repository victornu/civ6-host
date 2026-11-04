import hashlib
import unittest
from types import SimpleNamespace

from civ6_host.runtime import network_ui
from civ6_host.runtime.capture_profiles import LAN_PROFILE
from civ6_host.runtime.native import native_world_input


class NetworkMapFeaturesTests(unittest.TestCase):
    def owner(self):
        return SimpleNamespace(inputs=SimpleNamespace(profile=LAN_PROFILE,
            configuration=b'configuration', official_bundle=('capture', 'a'*64)),
            world_input_diagnostic=False, unit_order_cancel_diagnostic=False,
            network_ui_admission=dict(schema='civ6-host.lan-ui-gates.v3',
                configuration_sha256=hashlib.sha256(b'configuration').hexdigest(),
                bundle_reference=('capture', 'a'*64), captured_tutorial_inactive=True,
                map_source_sha256=[r[1] for r in network_ui.MAP_SOURCES],
                map_features={name:True for name in network_ui.MAP_FEATURES},
                gold_capability=True))

    def test_map_features_need_separate_exact_admission(self):
        owner=self.owner()
        for name in network_ui.MAP_FEATURES:
            self.assertTrue(network_ui.feature_enabled(owner,name))
        self.assertTrue(network_ui.gate_available(owner,'plot_purchase'))
        self.assertFalse(owner.world_input_diagnostic)
        self.assertFalse(owner.unit_order_cancel_diagnostic)
        owner.network_ui_admission['schema']='civ6-host.lan-ui-gates.v2'
        self.assertFalse(network_ui.feature_enabled(owner,'world_input'))
        self.assertFalse(network_ui.gate_available(owner,'plot_purchase'))
        owner.network_ui_admission['schema']='civ6-host.lan-ui-gates.v3'
        owner.network_ui_admission['map_source_sha256'][0]='b'*64
        with self.assertRaises(ValueError):network_ui.feature_enabled(owner,'world_input')

    def test_loaded_identity_and_capability_are_not_assumed(self):
        owner=self.owner()
        owner.network_ui_admission['gold_capability']=False
        self.assertFalse(network_ui.gate_available(owner,'plot_purchase'))
        owner.inputs.configuration=b'different'
        with self.assertRaises(ValueError):network_ui.feature_enabled(owner,'unit_order_cancel')

    def test_legacy_explicit_opt_in_is_preserved_but_not_invented(self):
        owner=SimpleNamespace()
        self.assertFalse(network_ui.feature_enabled(owner,'world_input'))
        owner.world_input_diagnostic=True
        self.assertTrue(network_ui.feature_enabled(owner,'world_input'))
        owner.world_input_diagnostic=1
        with self.assertRaises(ValueError):network_ui.feature_enabled(owner,'world_input')
        with self.assertRaises(ValueError):network_ui.feature_enabled(owner,'unknown')

    def test_gold_predicate_requires_exact_native_readback(self):
        for result, expected in ((b'1',True),(b'0',False),(b'true',None),(b'',None)):
            owner=SimpleNamespace(prefix=SimpleNamespace(ui_child='ui',
                runtime=SimpleNamespace(evaluate_text=lambda *a, value=result, **k:value)))
            if expected is None:
                with self.assertRaises(ValueError):network_ui.gold_capability(owner)
            else:
                self.assertIs(network_ui.gold_capability(owner),expected)

    def test_world_clicks_use_all_coordinates_without_hidden_eligibility(self):
        state=dict(schema=native_world_input.SCHEMA,player_id=0,turn=1,width=4,height=3,
            units=[dict(unit_id=42,ignore_moves=False),dict(unit_id=43,ignore_moves=True)],
            selected_unit_id=42,war_prompt=None)
        actions=native_world_input.actions(state)
        self.assertEqual([a['plot_id'] for a in actions if a['kind']=='world_plot_click'],list(range(12)))
        self.assertEqual([a['unit_id'] for a in actions if a['kind']=='world_select_unit'],[42])
        state['war_prompt']=dict(attacking_player=0,defending_player=1,war_type=0)
        self.assertEqual(native_world_input.actions(state),[
            dict(kind='world_war_response',accept=False),dict(kind='world_war_response',accept=True)])

    def test_parent_accepts_source_admitted_cancel_without_diagnostic_override(self):
        from civ6_host.runtime.native.network_session import NativeNetworkSession
        from civ6_host.runtime.native.native_action_session import NativeActionSession
        session=object.__new__(NativeNetworkSession)
        session.unit_order_cancel_diagnostic=False
        session.movement_information_diagnostic=False
        session.official_bundle=('capture','a'*64)
        session.protocol=SimpleNamespace(decisions=None)
        response=dict(decisions=dict(schema='component-fixture',unit_orders=dict(offers=[
            dict(action=dict(item_type='UNITCOMMAND_CANCEL'))])))
        with self.assertRaisesRegex(ValueError,'Unit cancel differs'):
            NativeActionSession._accepted_response(session,response)
        session._lan_map_source_admission=dict(official_bundle=session.official_bundle,
            source_sha256=tuple(row[1] for row in network_ui.MAP_SOURCES))
        NativeActionSession._accepted_response(session,response)
        self.assertEqual(session.protocol.decisions,response['decisions'])
        self.assertFalse(session.unit_order_cancel_diagnostic)
        session.official_bundle=('another-capture','a'*64)
        with self.assertRaisesRegex(ValueError,'another bundle or source'):
            NativeActionSession._accepted_response(session,response)


if __name__=='__main__':
    unittest.main()
