import copy
from types import SimpleNamespace
import unittest

from civ6_host.contracts import diplomacy_overview as overview, network_turn


def fixture():
    def selection(key, **changes):
        return dict(key=key, disabled=False, supported=True, text=None,
                    tooltip=None, diplomatic_action_type=None, **changes)
    return dict(schema=overview.SCHEMA, player_id=0, turn=1,
        capability=True, paused=False, complete_action_space=False,
        targets=[dict(player_id=2, selections=[selection('CHOICE_DECLARE_FRIENDSHIP')])])


class OverviewContractTests(unittest.TestCase):
    def catalogue(self):
        data = fixture()
        actions = overview.candidates(data)
        catalogue = dict(schema=network_turn.SCHEMA, base_schema='fixture',
            episode_id='episode', game_generation='generation', sequence=0,
            player_id=0, turn=1, player_map={}, unsupported=['diplomacy_deals'],
            complete_action_space=False, diplomacy_overview=data,
            candidates=[dict(candidate_id=network_turn.digest(a),action=a) for a in actions],
            turn_controls=dict(schema=network_turn.TURN_CONTROLS_SCHEMA,
                player_id=0,turn=1,active=True,active_complete=True,
                can_unready=False,timer_elapsed=False))
        catalogue['decision_id'] = network_turn.digest(catalogue)
        return catalogue

    def validate(self, value, **kw):
        value['decision_id'] = network_turn.digest({k:v for k,v in value.items() if k!='decision_id'})
        return network_turn.validate_catalogue(value,
            SimpleNamespace(episode_id='episode',game_generation='generation'),
            0,1,player_id=0,**kw)

    def test_initial_choices_are_verified_and_removed_from_legacy_schema(self):
        data = self.catalogue()
        legacy = self.validate(data)
        self.assertEqual(legacy['candidates'],[])
        self.assertNotIn('diplomacy_overview',legacy)
        self.assertEqual(len(data['candidates']),1)
        self.assertEqual(legacy['schema'],'fixture')

    def test_unavailable_or_substituted_choice_is_rejected(self):
        for modify in (
            lambda c:c['diplomacy_overview'].__setitem__('paused',True),
            lambda c:c['diplomacy_overview']['targets'][0]['selections'][0].__setitem__('disabled',True),
            lambda c:c['diplomacy_overview']['targets'][0]['selections'][0].__setitem__('supported',False),
            lambda c:c['candidates'][0]['action'].__setitem__('target_player_id',3),
            lambda c:c.__setitem__('schema',network_turn.LEGACY_SCHEMA),
            lambda c:c.pop('diplomacy_overview'),
        ):
            data = self.catalogue(); modify(data)
            with self.assertRaises(ValueError):self.validate(data)

    def test_closed_catalogue_retains_explanations_without_executable_choices(self):
        data=self.catalogue();data['candidates']=[]
        self.validate(data,actions_closed=True)
        self.assertEqual(len(data['diplomacy_overview']['targets']),1)

    def test_duplicate_or_foreign_target_is_rejected(self):
        for other in (0,False,64,2):
            data=fixture()
            row=copy.deepcopy(data['targets'][0]);row['player_id']=other
            data['targets'].append(row)
            with self.assertRaises(ValueError):overview.validate(data,0,1)


if __name__ == '__main__':
    unittest.main()
