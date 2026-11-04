from copy import deepcopy
from hashlib import sha256
import json
from types import SimpleNamespace
import unittest

from civ6_host.contracts import network_turn, plot_purchases


class PlotPurchaseCatalogueTests(unittest.TestCase):
    def setUp(self):
        from civ6_host.runtime.paths import resource_root
        path = resource_root() / ('work/xp2-client-sessions/'
            'run-ed0e6ca1249b4374984ee38b48362593/checkpoint/checkpoint.json')
        if not path.is_file():
            self.skipTest('Retained private XP2 v19 witness required')
        raw = path.read_bytes()
        self.assertEqual(sha256(raw).hexdigest(),
                         'ca174f88f8490369b7b971ece232babe1e962de7a30929b692b9d53270a6f9ff')
        checkpoint = json.loads(raw)
        self.saved = checkpoint['decisions']
        self.observation = checkpoint['observation']
        self.live = deepcopy(self.saved)
        self.live['schema'] = network_turn.CAPABILITY_XP2_PLOT_PURCHASE_SCHEMA
        player, turn = self.live['player_id'], self.live['turn']
        city, = self.observation['cities']
        plots = [row for row in self.observation['plots'] if row['owner'] == -1][:2]
        actions = [dict(kind='purchase', city_id=city['id'], plot_id=plot['index'],
                        x=plot['x'], y=plot['y'], currency='YIELD_GOLD', price_token=price)
                   for plot, price in zip(plots, ('35', '200'))]
        offers = [dict(action=action, command_legal=True, can_afford=i == 0)
                  for i, action in enumerate(actions)]
        offers.sort(key=lambda row: row['action']['plot_id'])
        self.live['plot_purchases'] = [dict(player_id=player, turn=turn, city_id=city['id'], offers=offers)]
        candidate = dict(candidate_id=network_turn.digest(actions[0]), action=actions[0])
        self.live['candidates'].append(candidate)
        self.live['families']['purchase'] = dict(status='queried_partial',
            candidate_ids=[candidate['candidate_id']], unqualified=list(plot_purchases.GAPS))

    def validate(self, value):
        value.pop('decision_id', None)
        value['decision_id'] = network_turn.digest(value)
        identity = SimpleNamespace(episode_id=value['episode_id'], game_generation=value['game_generation'])
        network_turn.validate_capability_catalogue(value, identity, value['sequence'],
            value['turn'], player_id=value['player_id'], observation=self.observation)

    def test_v20_preserves_v19_checkpoint_and_its_current_skip_action(self):
        from civ6_host.runtime.configuration_profiles import XP1_CORE_SHA256, XP2_CORE_SHA256
        self.validate(self.live)
        before = deepcopy(self.live)
        projected, transition = network_turn.checkpoint_catalogue(
            self.live, self.saved, self.observation, core_sha256=XP2_CORE_SHA256)
        self.assertEqual(projected, self.saved)
        self.assertEqual(transition['added_action_families'], ['purchase'])
        self.assertEqual(self.live, before)
        with self.assertRaisesRegex(ValueError, 'requires Gathering Storm'):
            network_turn.checkpoint_catalogue(
                self.live, self.saved, self.observation, core_sha256=XP1_CORE_SHA256)

    def test_candidates_must_match_legal_affordable_own_city_offers(self):
        def expose_unaffordable(value):
            offer = next(row for row in value['plot_purchases'][0]['offers'] if not row['can_afford'])
            action = offer['action']
            key = network_turn.digest(action)
            value['candidates'].append(dict(candidate_id=key, action=action))
            value['families']['purchase']['candidate_ids'].append(key)

        for mutate in (expose_unaffordable,
                       lambda v: v['plot_purchases'][0].update(player_id=1),
                       lambda v: v['plot_purchases'][0]['offers'][0]['action'].update(x=0),
                       lambda v: v['families']['purchase'].update(unqualified=['faith_purchase'])):
            value = deepcopy(self.live)
            mutate(value)
            with self.subTest(mutation=mutate), self.assertRaises(ValueError):
                self.validate(value)

    def test_v21_projects_only_city_items_out_of_the_retained_v20_catalogue(self):
        from civ6_host.runtime.configuration_profiles import XP2_CORE_SHA256
        from civ6_host.runtime.paths import resource_root

        path = resource_root() / ('work/xp2-client-sessions/'
            'run-96e753c051b74178ba7cf98fb98914e1/checkpoint/checkpoint.json')
        if not path.is_file():
            self.skipTest('Retained private XP2 v20 witness required')
        raw = path.read_bytes()
        self.assertEqual(sha256(raw).hexdigest(),
                         '01ff46bae99407c4c32f7a63f23a70c944182a1bf4517f9cd07ed438cdb52c87')
        checkpoint = json.loads(raw)
        self.observation = checkpoint['observation']
        saved = checkpoint['decisions']
        live = deepcopy(saved)
        live['schema'] = network_turn.CAPABILITY_XP2_CITY_PURCHASE_SCHEMA
        city, = self.observation['cities']
        action = dict(kind='purchase', city_id=city['id'], category='unit', index=20,
                      hash=1872107673, item_type='UNIT_SCOUT', currency='YIELD_GOLD', price_token='60')
        live['city_purchases'] = [dict(player_id=live['player_id'], turn=live['turn'],
            city_id=city['id'], offers=[dict(action=action, command_legal=True, can_afford=True)])]
        key = network_turn.digest(action)
        live['candidates'].append(dict(candidate_id=key, action=action))
        live['families']['purchase']['candidate_ids'].append(key)
        live['families']['purchase']['unqualified'] = list(plot_purchases.CITY_GAPS)
        self.validate(live)
        projected, transition = network_turn.checkpoint_catalogue(
            live, saved, self.observation, core_sha256=XP2_CORE_SHA256)
        self.assertEqual(projected, saved)
        self.assertEqual(transition['added_action_families'], ['standard_gold_unit_building_purchase'])
        from civ6_host.contracts.information import project
        for group, expected in (('production', 'civ6-host.production-inputs.v2'),
                                ('combat', 'civ6-host.combat-inputs.v1'),
                                ('unit_work', 'civ6-host.unit-work-inputs.v3')):
            self.assertEqual(project(group, self.observation, live)['schema'], expected)
        for changed in (dict(currency='YIELD_FAITH'), dict(city_id=999999), dict(item_type='BUILDING_MONUMENT')):
            invalid = deepcopy(live)
            invalid['city_purchases'][0]['offers'][0]['action'].update(changed)
            with self.subTest(changed=changed), self.assertRaises(ValueError):
                self.validate(invalid)


class PlotPurchaseOwnerTests(unittest.TestCase):
    def test_live_binding_uses_the_composed_query_and_action_boundaries(self):
        from test_xp2_checkpoint_composition import Fixture
        from civ6_host.runtime.xp1_continuation import ACTIVE, READY
        from civ6_host.runtime.xp2_plot_purchases import _bind, _source

        fixture = Fixture.__new__(Fixture)
        self.addCleanup(fixture.close)
        fixture.__init__()
        self.assertIsNot(fixture.prefix.runtime, fixture.backend.runtime)
        base = fixture.backend.core._handle
        for table, slot, target in _source()[1]['tables'].values():
            fixture.memory.q(base + table + slot, base + target)
        with fixture.saved._attempt():
            _bind(fixture.saved, active=False)
            fixture.backend.stage, fixture.backend.busy = ACTIVE, True
            _bind(fixture.saved, active=True)
            fixture.backend.stage, fixture.backend.busy = READY, False
