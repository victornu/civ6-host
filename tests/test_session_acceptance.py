import copy
import importlib.util
import io
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

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


class RestoredBuilderAcceptanceTests(unittest.TestCase):
    def setUp(self):
        self.boundary = dict(observation=dict(player_id=0,
            plots=[dict(index=12, visible=True, owner=0, water=False, impassable=False)]),
            decisions=dict(unit_work_state=dict(units=[dict(unit_id=17, plot_id=10,
                charges=3, moves_token='2', improvement=-1)]),
                queued_orders=dict(units=[dict(unit_id=17, plot_id=None)]),
                world_input=dict(selected_unit_id=None), candidates=[]))
        self.actions = []
        self.effect = True
        self.unit = self.boundary['decisions']['unit_work_state']['units'][0]
        self.order = self.boundary['decisions']['queued_orders']['units'][0]
        self.farm = dict(kind='build_improvement', unit_id=17, plot_id=12, index=1, selector=1)

    def choose(self, kind, **parameters):
        self.actions.append(dict(kind=kind, **parameters))
        if kind == 'world_select_unit':
            self.boundary['decisions']['world_input']['selected_unit_id'] = parameters['unit_id']
        elif kind == 'world_plot_click':
            self.order['plot_id'] = parameters['plot_id']
        elif kind == 'build_improvement' and self.effect:
            self.unit.update(charges=2, improvement=parameters['index'], moves_token='0')

    def advance(self):
        self.actions.append(dict(kind='advance'))
        self.unit['plot_id'] = self.order['plot_id']
        self.order['plot_id'] = None
        self.boundary['decisions']['candidates'] = [dict(action=self.farm)]

    def run_witness(self, advance=None):
        return acceptance.exercise_restored_builder(lambda: self.boundary, self.choose,
            self.advance if advance is None else advance, unit_id=17, plot_id=12)

    def test_reuses_the_unit_honors_queued_movement_and_checks_effect(self):
        result = self.run_witness()
        self.assertEqual([a['kind'] for a in self.actions],
                         ['world_select_unit', 'world_plot_click', 'advance', 'build_improvement'])
        self.assertEqual(self.actions[-1], self.farm)
        self.assertEqual(result['starting']['charges'], 3)
        self.assertEqual(result['after']['charges'], 2)
        self.assertEqual(result['after']['improvement'], 1)
        self.assertEqual(result['advances'], 1)

    def test_failed_effect_and_unreachable_tile_do_not_qualify(self):
        with self.assertRaisesRegex(RuntimeError, 'within three turns'):
            self.run_witness(advance=lambda: None)
        self.assertEqual([a['kind'] for a in self.actions], ['world_select_unit', 'world_plot_click'])
        self.effect = False
        with self.assertRaisesRegex(RuntimeError, 'consume one charge'):
            self.run_witness()

    def test_unseen_plot_is_rejected_before_any_command(self):
        self.boundary['observation']['plots'][0]['visible'] = False
        with self.assertRaisesRegex(ValueError, 'visible owned'):
            self.run_witness()
        self.assertEqual(self.actions, [])

    def test_acceptance_retains_completed_save_if_second_process_is_refused(self):
        self.unit['plot_id'] = 12
        self.boundary['observation']['turn'] = 20
        self.boundary.update(episode_id='original', game_generation='generation', sequence=0)
        self.boundary['decisions'].update(decision_id='decision',
            candidates=[dict(action=self.farm, candidate_id='build')])

        def act(player, decision, candidate):
            self.assertEqual((player, decision, candidate), (0, 'decision', 'build'))
            self.choose(**self.farm)
            self.boundary['sequence'] = 1
            return copy.deepcopy(self.boundary)

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first_run = root/'first'
            first_run.mkdir()
            checkpoint = dict(path='work/fixture/new-checkpoint.json', sha256='b' * 64)
            config = root/'config.json'
            config.write_text(json.dumps(dict(input_profile='xp1-lan', xp1_unit_work=True,
                checkpoint=dict(path='work/fixture/source.json', sha256='a' * 64))), encoding='utf-8')
            producer = SimpleNamespace(run=first_run, report={'reaped': True}, checkpoint=checkpoint)
            blocked = SimpleNamespace(run=None)
            first_client = Mock(command_result={'status': 'completed'})
            first_client.reset.side_effect = lambda: copy.deepcopy(self.boundary)
            first_client.act.side_effect = act
            second_client = Mock()
            second_client.reset.side_effect = RuntimeError('Need memory before second process')
            args = ['accept_session', '--config', str(config), '--unit-work', '--restored-builder', '17', '12']
            with patch.object(acceptance.sys, 'argv', args), patch.object(acceptance.sys, 'stdout', io.StringIO()), \
                    patch('civ6_host.runtime.backend.NetworkBackend', side_effect=[producer, blocked]) as backend, \
                    patch('civ6_host.SessionClient', side_effect=[first_client, second_client]):
                self.assertEqual(acceptance.main(), 1)
            self.assertEqual(backend.call_args.kwargs['checkpoint'], checkpoint)
            self.assertFalse(backend.call_args.kwargs['checkpoint_on_close'])
            receipt = json.loads((first_run/'client-acceptance.json').read_bytes())
            self.assertEqual(receipt['output_checkpoint'], checkpoint)
            self.assertEqual(receipt['status'], 'refused')
            self.assertEqual(receipt['unit_work']['after']['charges'], 2)
            self.assertIn('Need memory before second process', receipt['error'])
            first_client.close.assert_called_once_with(0)
            second_client.abort.assert_called_once()


if __name__ == '__main__':
    unittest.main()
