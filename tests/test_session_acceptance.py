import copy
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('session_acceptance',
    Path(__file__).resolve().parents[1] / 'tools/accept_session.py')
acceptance = importlib.util.module_from_spec(spec)
spec.loader.exec_module(acceptance)


class PublicExplorationTests(unittest.TestCase):
    def view(self):
        def move(x, y):
            return dict(action=dict(kind='move', unit_id=17,
                source_plot_id=27, source_x=7, source_y=2,
                destination_plot_id=y*10+x, destination_x=x, destination_y=y))
        plots=[dict(x=x,y=y,revealed=True,terrain_type='unused')
               for x in range(5,10) for y in range(5)]
        return dict(observation=dict(width=10, height=8,
            units=[dict(id=17,x=7,y=2)],
            plots=plots),
            decisions=dict(player_map=dict(plots=plots),
                           candidates=[move(6,2), move(7,4)]))

    def test_selects_public_frontier_over_minimum_x(self):
        view = self.view()
        action = acceptance.public_exploration_choice(view, {})
        self.assertEqual((action['destination_x'],action['destination_y']), (7,4))
        self.assertTrue(any(action is r['action'] for r in view['decisions']['candidates']))

    def test_does_not_use_hidden_details_or_modify_observation(self):
        view = self.view(); before = copy.deepcopy(view)
        expected = acceptance.public_exploration_choice(view,{})
        self.assertEqual(view,before)
        # Contents of an unrevealed tile, if accidentally present, do not affect
        # the selector. Runtime player-observation isolation remains separate.
        for marker in (1,999):
            changed = copy.deepcopy(view)
            changed['observation']['plots'].append(dict(x=7,y=6,revealed=False,
                owner=marker,terrain_type=marker,secret_units=[marker]))
            self.assertEqual(acceptance.public_exploration_choice(changed,{}),expected)

    def test_revisits_are_penalized_and_no_action_is_invented(self):
        view = self.view()
        action = acceptance.public_exploration_choice(view,{(17,47):2})
        self.assertEqual(action['destination_plot_id'],26)
        view['decisions']['candidates'] = []
        self.assertIsNone(acceptance.public_exploration_choice(view,{}))

    def test_explored_fog_is_not_mistaken_for_unknown_terrain(self):
        view=self.view()
        expected=acceptance.public_exploration_choice(view,{})
        view['observation']['plots']=[p for p in view['observation']['plots'] if p['y']<3]
        self.assertEqual(acceptance.public_exploration_choice(view,{}),expected)


if __name__ == '__main__':
    unittest.main()
