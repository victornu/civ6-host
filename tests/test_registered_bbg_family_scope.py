"""Join native family guards to a registered world, without running the game."""
import copy
import json
import os
from pathlib import Path
import unittest
from unittest.mock import patch

from civ6_host.runtime import xp2_bbg_inputs as bbg
from civ6_host.runtime import captured_session_profile as captured
from civ6_host.runtime import expansion_city_controls_profile as city
from civ6_host.runtime.execution_images import select, known_path
from civ6_host.runtime.paths import resource_root

ORIGIN = ('work/official-capture/bbg751-world-A-ui/manifest.json',
          '0438263e3e78b78233153afe0bc4e1ace6ac8e315aed21e4507f738bae8b285d')
REGISTRATION = json.dumps(dict(zip(('path','sha256'), ORIGIN)))
IMAGE = select('xp2-gamecore-current-092abfbb', core_path=known_path('xp2-gamecore-current-092abfbb'))


class RegisteredBBGFamilyScopeTests(unittest.TestCase):
    def setUp(self):
        if not (resource_root() / ORIGIN[0]).is_file():
            self.skipTest('Retained private current capture required')
        self.environment = patch.dict(os.environ, {bbg.CAPTURE_ENV:REGISTRATION})
        self.environment.start()
        self.addCleanup(self.environment.stop)

    def test_registered_scope_requires_explicit_exact_image(self):
        self.assertEqual(captured.require_bbg_capture(ORIGIN, execution_image=IMAGE), ORIGIN)
        with self.assertRaises(ValueError):
            captured.require_bbg_capture(ORIGIN)
        with self.assertRaises(ValueError):
            captured.require_bbg_capture((ORIGIN[0],'0'*64),execution_image=IMAGE)

    def test_historical_scope_is_not_relabelled_by_registration(self):
        self.assertEqual(captured.require_bbg_capture(bbg.REFERENCE), bbg.REFERENCE)
        _, _, source = city.verify_source(city.XP2_CORE_SHA256)
        self.assertEqual(source['image']['sha256'], IMAGE.reference_core_sha256)

    def test_current_city_gate_joins_both_actual_ui_witnesses(self):
        gate = city.bbg_gate(city.XP2_CORE_SHA256, ORIGIN, execution_image=IMAGE)
        self.assertEqual(gate['official_bundle'], dict(zip(('path','sha256'),ORIGIN)))
        self.assertEqual(gate['captured_gamecore_sha256'], IMAGE.image_sha256)
        self.assertEqual(len(gate['ui_witnesses']),2)
        self.assertFalse(gate['graphical_selected_city_state_qualified'])
        pins = city.source_dependencies(city.XP2_CORE_SHA256,official_bundle=ORIGIN,execution_image=IMAGE)
        for ref in gate['ui_witnesses']:
            self.assertEqual(pins[str(Path(ref['path']).resolve())],ref['sha256'])
        self.assertEqual(pins[IMAGE.path],IMAGE.image_sha256)

    def test_city_gate_refuses_an_unknown_or_disabled_control(self):
        from civ6_host.runtime.native import native_official_bundle as original
        actual = original._file
        def disabled(pin,*args,**kwargs):
            raw = actual(pin,*args,**kwargs)
            if str(pin['path']).endswith('ui-availability-before.json'):
                report=json.loads(raw)
                report['diagnostics']['ui_availability']['controls']['city_citizens']['disabled']['value']=True
                return json.dumps(report).encode()
            return raw
        with patch.object(original,'_file',side_effect=disabled):
            with self.assertRaisesRegex(ValueError,'MP/tutorial/visibility gate'):
                city.bbg_gate(city.XP2_CORE_SHA256,ORIGIN,execution_image=IMAGE)

    def test_current_city_gate_refuses_cross_capture_ui_receipts(self):
        capture = copy.deepcopy(bbg._complete_capture(ORIGIN))
        event = next(row for row in capture['bridge_events'] if row['kind']=='ui_availability')
        event['nonce']='f'*32
        with patch.object(bbg,'_complete_capture',return_value=capture):
            with self.assertRaisesRegex(ValueError,'bridge exchange'):
                city.bbg_gate(city.XP2_CORE_SHA256,ORIGIN,execution_image=IMAGE)


if __name__=='__main__':
    unittest.main()
