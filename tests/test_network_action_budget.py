"""Protocol/pipe fixtures, not a native large-map qualification."""
import copy
import io
import json
import queue
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from civ6_host.contracts import action_budget, network_turn
from civ6_host.runtime.native import native_world_input as world
from civ6_host.runtime.native.native_saved_session import NativeSavedSession
from civ6_host.runtime.native.network_session import NativeNetworkSession


class NetworkActionBudgetTests(unittest.TestCase):
    def state(self, width=128, height=128):
        return dict(schema=world.SCHEMA, player_id=0, turn=1, width=width,
                    height=height, units=[dict(unit_id=7, ignore_moves=False)],
                    selected_unit_id=7, war_prompt=None)

    def catalogue(self, schema=network_turn.SCHEMA):
        state = self.state()
        rows = [dict(action=a, candidate_id=network_turn.digest(a))
                for a in world.actions(state)]
        value = dict(schema=schema, base_schema='capacity-fixture-only',
            episode_id='episode', game_generation='generation', sequence=0,
            player_id=0, turn=1, player_map={}, candidates=rows,
            turn_controls=dict(schema=network_turn.TURN_CONTROLS_SCHEMA,
                player_id=0, turn=1, active=True, active_complete=True,
                can_unready=False, timer_elapsed=False), world_input=state,
            unsupported=[], complete_action_space=False)
        if schema in network_turn.WORK_SCHEMAS:
            value['unit_work_state']=dict(schema='civ6-host.unit-work-state.v1',player_id=0,turn=1,units=[])
        if schema in network_turn.INFO_SCHEMAS:
            value['unit_work']=dict(player_id=0,turn=1,offers=[])
            value['unit_work_info']=dict(schema='civ6-host.unit-work-info.v1',player_id=0,turn=1,offers=[],targets=[])
        if schema in network_turn.GROWTH_SCHEMAS:
            value['city_growth']=dict(schema='civ6-host.city-growth.v1',player_id=0,turn=1,cities=[])
        if schema == network_turn.PRODUCTION_SCHEMA:
            from civ6_host.contracts import production_inputs as production
            value['production']=dict(schema=production.CURRENT_SCHEMA,player_id=0,turn=1,cities=[])
            value['production_info']=dict(schema=production.INFO_SCHEMA,player_id=0,turn=1,rows=[],
                source_sha256=production.legacy.PROOF_SHA256,ui_sha256=production.legacy.PANEL_SHA256,
                tooltip_sha256=production.legacy.TOOLTIP_SHA256)
        value['decision_id'] = network_turn.digest(value)
        return value

    def test_all_declared_map_coordinates_fit_without_pruning(self):
        state = self.state()
        actions = world.actions(state)
        self.assertEqual(len(actions), 16386)
        action_budget.validate_action_count(actions, world_input=state, map_coordinates=True)
        rows = [dict(action=a, candidate_id=str(i)) for i, a in enumerate(actions)]
        world.validate_candidates(state, rows)
        with self.assertRaisesRegex(ValueError, 'Legacy'):
            action_budget.validate_action_count(actions, world_input=state)

    def test_coordinate_budget_cannot_expand_ordinary_actions_or_geometry(self):
        state = self.state()
        with self.assertRaisesRegex(ValueError, 'Ordinary'):
            action_budget.validate_action_count([dict(kind='skip_unit')] * 4097,
                world_input=state, map_coordinates=True)
        with self.assertRaisesRegex(ValueError, 'geometry'):
            action_budget.validate_action_count([dict(kind='world_plot_click')] * 16385,
                world_input=state, map_coordinates=True)
        with self.assertRaisesRegex(ValueError, 'selected unit'):
            action_budget.validate_action_count([dict(kind='world_plot_click')],
                world_input=dict(state, selected_unit_id=None), map_coordinates=True)

    def test_v3_admits_large_map_while_v1_v2_keep_old_budget(self):
        value = self.catalogue()
        identity = SimpleNamespace(episode_id='episode', game_generation='generation')
        rebuilt = network_turn.validate_catalogue(value, identity, 0, 1, player_id=0)
        self.assertEqual(rebuilt['candidates'], value['candidates'])
        for schema in (network_turn.PREVIOUS_SCHEMA, network_turn.LEGACY_SCHEMA):
            old = copy.deepcopy(value)
            old['schema'] = schema
            old['decision_id'] = network_turn.digest({k:v for k,v in old.items() if k != 'decision_id'})
            with self.assertRaisesRegex(ValueError, 'Legacy'):
                network_turn.validate_catalogue(old, identity, 0, 1, player_id=0)

    def test_old_small_catalogues_remain_accepted(self):
        identity = SimpleNamespace(episode_id='episode', game_generation='generation')
        for schema in network_turn.SUPPORTED_SCHEMAS:
            # Capability catalogues have explicit family queries, not this
            # legacy full-catalogue envelope; their budget fixtures are separate.
            if network_turn.is_capability_catalogue({'schema':schema}):
                continue
            value = self.catalogue(schema)
            value['world_input'] = self.state(4, 3)
            value['candidates'] = [dict(action=a, candidate_id=network_turn.digest(a))
                                   for a in world.actions(value['world_input'])]
            value['decision_id'] = network_turn.digest({k:v for k,v in value.items() if k != 'decision_id'})
            network_turn.validate_catalogue(value, identity, 0, 1, player_id=0)

    def read_pipe(self, cls, payload, total_limit, *, line_limit=None):
        session = object.__new__(cls)
        errors = []
        session._fail = lambda reason, error: errors.append((reason, error))
        session.responses = queue.Queue()
        if line_limit is not None:
            session.event_line_limit_bytes = line_limit
        with tempfile.TemporaryDirectory() as directory:
            session.run = Path(directory)
            session._read_stream(io.BytesIO(payload), 'events.jsonl', total_limit, True)
        return session.responses, errors

    def test_real_stream_reader_delivers_full_coordinate_reply_above_legacy_limit(self):
        value = self.catalogue()
        payload = (json.dumps(dict(stage='official_session_response', decisions=value))+'\n').encode()
        self.assertGreater(len(payload), NativeSavedSession.event_line_limit_bytes)
        self.assertLess(len(payload), NativeNetworkSession.event_line_limit_bytes)
        responses, errors = self.read_pipe(NativeNetworkSession, payload, 128*1024*1024)
        self.assertFalse(errors)
        self.assertEqual(responses.get_nowait()['decisions'], value)
        responses, errors = self.read_pipe(NativeSavedSession, payload, 128*1024*1024)
        self.assertTrue(errors)
        self.assertTrue(responses.empty())

    def test_native_pipe_still_enforces_line_and_aggregate_budgets(self):
        payload = (json.dumps(dict(stage='official_session_response', fixture='x'*256))+'\n').encode()
        for total, line in ((1024, 128), (128, 1024)):
            responses, errors = self.read_pipe(NativeNetworkSession, payload, total, line_limit=line)
            self.assertTrue(errors)
            self.assertTrue(responses.empty())
        self.assertEqual(NativeSavedSession.event_line_limit_bytes, 1024*1024)
        self.assertEqual(NativeNetworkSession.event_line_limit_bytes, 16*1024*1024)


if __name__ == '__main__':
    unittest.main()
