from copy import deepcopy
from hashlib import sha256
import json
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from civ6_host.contracts import network_turn, unit_upgrades
from civ6_host.runtime import xp2_unit_upgrades
from civ6_host.runtime.configuration_profiles import XP2_CORE_SHA256


class UpgradeCatalogueTests(unittest.TestCase):
    observation = dict(player_id=0, turn=48, units=[dict(id=393217, owner=0)])
    offer = dict(unit_id=393217, hash=unit_upgrades.COMMAND, target_type=28, cost=60,
                 resource_type=4, resource_cost=10, legal=True)

    def test_resource_quote_is_bound_to_a_visible_owned_offer(self):
        line = b'393217|3544934848|28|60|1|4|10'
        wire = b'upgrades-v1|0|48\n' + line
        base, public = xp2_unit_upgrades._decode(wire, self.observation)
        self.assertEqual(public['offers'], [self.offer])
        self.assertNotIn('resource_cost', base['offers'][0])
        self.assertEqual(unit_upgrades.actions(public)[0]['resource_cost'], 10)
        for invalid in (line.replace(b'|4|10', b'|4|-'), line.replace(b'|4|10', b'|04|10'),
                        line.replace(b'393217', b'393218')):
            with self.assertRaises(ValueError):
                xp2_unit_upgrades._decode(b'upgrades-v1|0|48\n' + invalid, self.observation)
        _, disabled = xp2_unit_upgrades._decode(wire.replace(b'|1|4|', b'|0|4|'), self.observation)
        self.assertEqual(disabled['offers'][0]['resource_cost'], 10)
        self.assertEqual(unit_upgrades.actions(disabled), [])

    def test_changed_resource_quote_never_reaches_command_queue(self):
        base, catalogue = xp2_unit_upgrades._decode(
            b'upgrades-v1|0|48\n393217|3544934848|28|60|1|4|10', self.observation)
        saved = SimpleNamespace(explicit_unit_upgrades=base, xp2_unit_upgrades=catalogue)
        fresh = deepcopy(catalogue)
        fresh['offers'][0]['resource_cost'] = 11
        with patch.object(xp2_unit_upgrades, '_bind'), patch.object(
                xp2_unit_upgrades, '_query', return_value=(base, fresh)), patch.object(
                xp2_unit_upgrades.upgrades, 'apply') as submit:
            with self.assertRaisesRegex(RuntimeError, 'quote is stale'):
                xp2_unit_upgrades.apply(saved, unit_upgrades.actions(catalogue)[0], self.observation)
            submit.assert_not_called()

    def test_strategic_upgrade_records_both_native_stockpile_reads(self):
        before = dict(self.observation, economy={'gold': 160})
        after = dict(before, economy={'gold': 100}, units=[dict(id=420000, owner=0, type=28)])
        base, catalogue = xp2_unit_upgrades._decode(
            b'upgrades-v1|0|48\n393217|3544934848|28|60|1|4|10', before)
        runtime = SimpleNamespace(evaluate_text=Mock(
            side_effect=[b'0|48|4|13', b'0|48|4|3']))
        saved = SimpleNamespace(explicit_unit_upgrades=base, xp2_unit_upgrades=catalogue,
            prefix=SimpleNamespace(runtime=runtime, ui_child=object()), emit=Mock())
        action, = unit_upgrades.actions(catalogue)
        with patch.object(xp2_unit_upgrades, '_bind'), patch.object(
                xp2_unit_upgrades, '_query', return_value=(base, catalogue)), patch.object(
                xp2_unit_upgrades.upgrades, 'apply', return_value=after):
            self.assertEqual(xp2_unit_upgrades.apply(saved, action, before), after)
        self.assertEqual(runtime.evaluate_text.call_count, 2)
        self.assertEqual(saved.emit.call_args.kwargs['resource_before'], 13)
        self.assertEqual(saved.emit.call_args.kwargs['resource_after'], 3)
        runtime.evaluate_text.side_effect = [b'0|49|4|13', b'0|48|4|013']
        with self.assertRaisesRegex(ValueError, 'Foreign XP2 stockpile'):
            xp2_unit_upgrades._stockpile(saved, before, 4)
        with self.assertRaisesRegex(ValueError, 'Noncanonical XP2 stockpile'):
            xp2_unit_upgrades._stockpile(saved, before, 4)

    def test_v23_projects_back_to_retained_v22_and_checks_candidate_quotes(self):
        from civ6_host.runtime.paths import resource_root

        path = resource_root() / ('work/xp2-client-sessions/'
            'run-3efb829b9d62478592670593b6742cda/checkpoint/checkpoint.json')
        if not path.is_file():
            self.skipTest('Retained private XP2 v22 witness required')
        raw = path.read_bytes()
        self.assertEqual(sha256(raw).hexdigest(),
                         'bbdebec2e7abe6d2e2bade1a77d10206bd0e014bc11c45ed25c995fbd0d75888')
        checkpoint = json.loads(raw)
        saved, observation = checkpoint['decisions'], checkpoint['observation']
        current = deepcopy(saved)
        catalogue = dict(player_id=saved['player_id'], turn=saved['turn'], offers=[self.offer])
        action, = unit_upgrades.actions(catalogue)
        candidate_id = network_turn.digest(action)
        current['schema'] = network_turn.CAPABILITY_XP2_UNIT_UPGRADE_SCHEMA
        current['unit_upgrades'] = catalogue
        current['families']['upgrade_unit'] = dict(status='queried_complete', candidate_ids=[candidate_id])
        current['candidates'].append(dict(candidate_id=candidate_id, action=action))
        current.pop('decision_id')
        current['decision_id'] = network_turn.digest(current)
        projected, transition = network_turn.checkpoint_catalogue(
            current, saved, observation, core_sha256=XP2_CORE_SHA256)
        self.assertEqual(projected, saved)
        self.assertEqual(transition['added_action_families'], ['upgrade_unit'])
        wrong = deepcopy(current)
        wrong['unit_upgrades']['offers'][0]['resource_cost'] = 11
        wrong.pop('decision_id')
        wrong['decision_id'] = network_turn.digest(wrong)
        identity = SimpleNamespace(episode_id=wrong['episode_id'], game_generation=wrong['game_generation'])
        with self.assertRaisesRegex(ValueError, 'Upgrade candidates differ'):
            network_turn.validate_capability_catalogue(wrong, identity, wrong['sequence'], wrong['turn'],
                player_id=wrong['player_id'], observation=observation)
