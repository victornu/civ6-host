import hashlib
import copy
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from civ6_host.runtime import network_ui
from civ6_host.runtime.capture_profiles import LAN_PROFILE


class NetworkUiTests(unittest.TestCase):
    def test_city_controls_reject_unknown_disabled_and_compact_layout(self):
        false = {'status':'observed', 'value':False}
        controls = {name: dict(disabled=false, hidden=false) for name in
                    ('city_citizens', 'city_production', 'city_yields', 'production_queue_tab')}
        network_ui.validate_city_witness(dict(controls=controls))
        for name in controls:
            for field in ('disabled', 'hidden'):
                for state in ({'status':'unknown', 'reason':'not_observed'},
                              {'status':'observed', 'value':True}):
                    changed = copy.deepcopy(controls)
                    changed[name][field] = state
                    with self.assertRaises(ValueError):
                        network_ui.validate_city_witness(dict(controls=changed))

    def test_city_gate_requires_separate_source_receipt_and_exact_loaded_identity(self):
        owner = SimpleNamespace(inputs=SimpleNamespace(profile=LAN_PROFILE,
            configuration=b'config', official_bundle=('capture', 'a'*64)))
        owner.network_ui_admission = dict(schema='civ6-host.lan-ui-gates.v1',
            configuration_sha256=hashlib.sha256(b'config').hexdigest(),
            bundle_reference=owner.inputs.official_bundle,
            force_end_turn=True, captured_tutorial_inactive=True)
        for gate in network_ui.CITY_GATES:
            self.assertFalse(network_ui.gate_available(owner, gate))
        owner.network_ui_admission.update(schema='civ6-host.lan-ui-gates.v2',
            city_source_sha256=network_ui.CITY_SOURCE[1],
            gates={name: True for name in network_ui.CITY_GATES})
        from civ6_host.runtime.native.native_ui_profile import gate_admitted
        for gate in network_ui.CITY_GATES:
            self.assertTrue(gate_admitted(owner, gate))
        self.assertFalse(gate_admitted(owner, 'plot_purchase'))
        self.assertFalse(gate_admitted(owner, 'force_end_turn'))
        self.assertTrue(network_ui.force_available(owner))
        with self.assertRaises(ValueError):
            gate_admitted(owner, 'invented_gate')
        owner.network_ui_admission['captured_tutorial_inactive'] = False
        self.assertFalse(gate_admitted(owner, 'city_focus'))
        owner.network_ui_admission['captured_tutorial_inactive'] = True
        owner.inputs.configuration = b'changed'
        with self.assertRaises(ValueError):gate_admitted(owner, 'city_focus')
        owner.inputs.configuration = b'config'
        owner.network_ui_admission['city_source_sha256'] = 'b'*64
        with self.assertRaises(ValueError):gate_admitted(owner, 'city_focus')

    def test_unknown_or_active_tutorial_cannot_enable_forced_turn(self):
        false = {'status':'observed', 'value':False}
        ui = {'tutorial':dict(active=false, manager_active=false, overlay_enabled=false,
                             any_multiplayer={'status':'observed','value':True})}
        with patch('civ6_host.runtime.native.native_ui_availability.validate_response'):
            network_ui.validate_tutorial_witness(ui, player_id=0, turn=1)
            for value in ({'status':'observed','value':True},
                          {'status':'unknown','reason':'missing_api'}):
                ui['tutorial']['active'] = value
                with self.assertRaises(ValueError):
                    network_ui.validate_tutorial_witness(ui, player_id=0, turn=1)

    def test_profile_gate_cannot_be_reused_after_configuration_or_bundle_change(self):
        owner = SimpleNamespace(inputs=SimpleNamespace(profile=LAN_PROFILE,
            configuration=b'configuration', official_bundle=('capture','a'*64)))
        self.assertFalse(network_ui.force_available(owner))
        owner.network_ui_admission = dict(schema='civ6-host.lan-ui-gates.v1',
            configuration_sha256=hashlib.sha256(b'configuration').hexdigest(),
            bundle_reference=owner.inputs.official_bundle,
            force_end_turn=True, captured_tutorial_inactive=True)
        self.assertTrue(network_ui.force_available(owner))
        owner.inputs.configuration=b'other'
        with self.assertRaises(ValueError):network_ui.force_available(owner)
        owner.inputs.configuration=b'configuration'
        owner.inputs.official_bundle=('different','b'*64)
        with self.assertRaises(ValueError):network_ui.force_available(owner)

    def test_hotseat_gate_does_not_admit_lan(self):
        owner=SimpleNamespace(inputs=SimpleNamespace(profile=object()))
        with self.assertRaises(ValueError):network_ui.admit(owner)


if __name__ == '__main__':
    unittest.main()
