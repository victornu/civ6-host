"""The pinned expansion UI supplies the growth display and its loyalty label."""

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
from types import SimpleNamespace
import unittest

from civ6_host.contracts import city_growth, information, network_turn
from civ6_host.runtime import expansion_city_growth as reader, xp2_bbg_inputs
from civ6_host.runtime.configuration_profiles import XP2_CORE_SHA256
from civ6_host.runtime.paths import resource_root
from test_city_growth import fixture


class ExpansionCityGrowthTests(unittest.TestCase):
    def test_pinned_ui_and_native_growth_bindings(self):
        import pefile

        verified = set()
        for reference, (image, _) in reader.CAPTURES.items():
            with self.subTest(profile=image.id, capture=reference):
                pins = reader.source_dependencies(reference, image)
                self.assertIn(reference[1], pins.values())
                self.assertIn(image.image_sha256, pins.values())
                if image.id in verified:
                    continue
                _, selected = reader._profile(reference, image)
                with pefile.PE(str(image.path), fast_load=True) as pe:
                    reader.verify_bindings(selected, 0, pe.get_data)
                    with self.assertRaises(ValueError):
                        reader.verify_bindings(selected, 0, lambda address, size: b'\0' * size)
                verified.add(image.id)
        with self.assertRaises(ValueError):
            reader.source_dependencies(('unknown', '0' * 64), image)

    def test_actual_expansion_panels_show_the_native_loyalty_penalty(self):
        for reference, (image, key) in reader.CAPTURES.items():
            if key == 'bbg':
                continue
            _, selected = reader._profile(reference, image)
            panel = Path(selected['overrides']['path']).read_text(encoding='utf-8-sig')
            with self.subTest(profile=image.id):
                public, private, _, lua = fixture(expansion_panel=panel, loyalty_modifier=0.75)
                self.assertEqual(public['schema'], city_growth.EXPANSION_SCHEMA)
                display = public['cities'][0]['display']
                self.assertEqual(display['OccupationLabel'], 'LOC_CULTURAL_IDENTITY_LOYALTY_WAVERING')
                self.assertEqual(display['OccupationMultiplier'], '-25.0%')
                self.assertEqual(display['GrowthLongNum'], 7)
                self.assertIn('food_stock', private[0])
                self.assertNotIn('food_stock', public['cities'][0])
                self.assertIsNone(lua.globals()[b'iModifiedFood'])
                neutral = fixture(expansion_panel=panel)[0]['cities'][0]['display']
                self.assertEqual(neutral['OccupationMultiplier'],
                                 'LOC_CULTURAL_IDENTITY_LOYALTY_NO_GROWTH_PENALTY')

    def test_t76_public_growth_transition_preserves_choices_and_scope(self):
        root = resource_root()
        receipt = json.loads((root / 'evidence/host-xp2-bbg-religion-founding-save-t76-native.json').read_bytes())
        ref = receipt['checkpoint']
        raw = (root / ref['path']).read_bytes()
        self.assertEqual(sha256(raw).hexdigest(), ref['sha256'])
        saved = json.loads(raw)
        observation, prior = saved['observation'], saved['decisions']
        image = reader.CAPTURES[xp2_bbg_inputs.REFERENCE][0]
        _, selected = reader._profile(xp2_bbg_inputs.REFERENCE, image)
        panel = Path(selected['overrides']['path']).read_text(encoding='utf-8-sig')
        growth = fixture(expansion_panel=panel)[0]
        example = growth['cities'][0]
        growth.update(player_id=observation['player_id'], turn=observation['turn'],
            cities=[dict(example, city_id=row['id'], population=row['population'])
                    for row in observation['cities']])
        current = deepcopy(prior)
        current['city_growth'] = growth
        current.pop('decision_id')
        current['decision_id'] = network_turn.digest(current)
        identity = SimpleNamespace(episode_id=current['episode_id'], game_generation=current['game_generation'])
        network_turn.validate_capability_catalogue(current, identity, current['sequence'], observation['turn'],
            player_id=observation['player_id'], observation=observation)
        self.assertEqual(information.project('growth', observation, current), growth)
        projected, transition = network_turn.checkpoint_catalogue(
            current, prior, observation, core_sha256=XP2_CORE_SHA256)
        self.assertEqual(projected, prior)
        self.assertEqual(transition['added_public_fields'], ['city_growth'])
        self.assertEqual(transition['added_action_families'], [])
        current['city_growth']['cities'][0]['population'] += 1
        current.pop('decision_id')
        current['decision_id'] = network_turn.digest(current)
        with self.assertRaises(ValueError):
            network_turn.checkpoint_catalogue(current, prior, observation, core_sha256=XP2_CORE_SHA256)
