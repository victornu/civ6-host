"""Pantheon session routing only; no DLL load, process, or GameCore execution."""
import ast
from contextlib import nullcontext
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from lupa.lua51 import LuaRuntime  # Fixture dependency, loaded before worker import isolation.

from civ6_host.contracts import network_turn
from civ6_host.runtime import xp1_pantheon as adapter, xp1_pantheon_source as source
from civ6_host.runtime import xp1_session_view as view, xp1_load_capability
from civ6_host.runtime.configuration_profiles import XP1_CORE_SHA256, XP2_CORE_SHA256
from civ6_host.runtime.execution_images import _XP1_PROFILE
from civ6_host.runtime.native.network_session import NativeNetworkSession
from civ6_host.runtime.saved_load_services import SavedLoadServices
from civ6_host.runtime.xp1_saved_load_owner import SavedLoadOwner
from civ6_host.runtime.xp1_continuation import SavedContinuation
from civ6_host.runtime.workers import network_worker as worker
from test_xp1_network_session import Fixture as ParentFixture
from test_xp1_pantheon import Fixture as NativeBoundaryFixture
from test_xp1_pantheon_public import offered
from test_xp1_city_religion import religion_fixture


def worker_pantheon_preflight():
    """Execute the actual bounded pre-Load block, without earlier Load setup."""
    tree = ast.parse(Path(worker.__file__).read_text(encoding='utf-8'))
    function = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == '_open_xp1')
    blocks = [n for n in function.body if isinstance(n, ast.If)
              and isinstance(n.test, ast.Name) and n.test.id == 'xp1_pantheon']
    if len(blocks) != 1:
        raise AssertionError('Expected one exact worker pantheon preflight')
    wrapper = ast.parse('def check(xp1_pantheon, xp1_dedications, selected, occupation_image, closure):\n pass').body[0]
    wrapper.body = blocks
    module = ast.fix_missing_locations(ast.Module(body=[wrapper], type_ignores=[]))
    namespace = {'_Path': Path}
    exec(compile(module, str(worker.__file__), 'exec'), namespace)
    return namespace['check']


class PantheonSessionTests(unittest.TestCase):
    def test_reduced_close_catalogue_is_retained_without_a_native_query(self):
        from test_session_capabilities import catalogue, observation
        identity=SimpleNamespace(episode_id='closed-fixture',game_generation='closed-fixture')
        decisions=catalogue(identity,queried=False,choices=False)
        before=deepcopy(decisions)
        saved=SavedLoadOwner.__new__(SavedLoadOwner)
        saved.explicit_pantheon={'stale': True}
        with patch.object(adapter,'catalogue',side_effect=AssertionError('Closed query')):
            view._add_xp1_pantheon(saved,observation(),decisions,actions_closed=True)
        self.assertEqual(decisions,before)
        self.assertIsNone(saved.explicit_pantheon)
        # A missing active predecessor remains an error, never a silent omission.
        with patch.object(adapter,'catalogue',return_value=offered(observation())):
            with self.assertRaisesRegex(ValueError,'preceding'):
                view._add_xp1_pantheon(saved,observation(),decisions)

    def fixture(self):
        f = NativeBoundaryFixture()
        self.addCleanup(f.close)
        f.saved.xp1_pantheon = True
        # The reused __new__ fixture predates these normal constructor fields.
        f.token.world_input_prompts = {}
        f.token.trade_feedback = None
        from civ6_host.runtime.unit_operation_ui_profile import verify_live
        f.token.unit_source = verify_live(f.backend.core._handle, f.backend.runtime.read,
            core_sha256=XP1_CORE_SHA256)
        return f

    def test_constructor_exact_option_profile_and_source_admission(self):
        with ParentFixture() as f:
            historical = f.session()
            self.assertIs(type(historical), NativeNetworkSession)
            self.assertFalse(historical.xp1_pantheon)
            self.assertIsNone(historical.execution_image)
            for flag in (1, 0, None, 'true'):
                with self.subTest(flag=flag), self.assertRaises(ValueError):
                    f.session(xp1_pantheon=flag)
            with self.assertRaisesRegex(ValueError, 'exact installed'):
                f.session(xp1_pantheon=True)
            with patch.object(source, 'ACTION_SOURCE', None), self.assertRaisesRegex(ValueError, 'dependencies'):
                f.session(xp1_pantheon=True, execution_image_profile=_XP1_PROFILE.id)
            current = f.session(xp1_pantheon=True, execution_image_profile=_XP1_PROFILE.id)
            self.assertIs(current.execution_image, _XP1_PROFILE)
            self.assertTrue(current.xp1_pantheon)
            self.assertEqual(f.spawns, [])

    def test_worker_source_preflight_preserves_exact_pins_before_load(self):
        check = worker_pantheon_preflight()
        selected = SimpleNamespace(reference=source.REFERENCE)
        pins = source.source_dependencies(_XP1_PROFILE)
        check(True, True, selected, _XP1_PROFILE, {'pins': pins})
        for image, dedications, reference, retained in (
                (None, True, source.REFERENCE, pins),
                (_XP1_PROFILE, False, source.REFERENCE, pins),
                (_XP1_PROFILE, True, ('foreign', '0'*64), pins),
                (_XP1_PROFILE, True, source.REFERENCE, {})):
            with self.subTest(image=image is None, admitted=dedications, pins=bool(retained)), self.assertRaises(ValueError):
                check(True, dedications, SimpleNamespace(reference=reference), image, {'pins': retained})
        with patch.object(source, 'ACTION_SOURCE', None), self.assertRaisesRegex(ValueError, 'dependencies'):
            check(True, True, selected, _XP1_PROFILE, {'pins': pins})
        check(False, False, None, None, {})

    def test_view_active_waiting_and_closed_keep_native_query_distinct(self):
        for mode in ('active', 'waiting', 'closed'):
            with self.subTest(mode=mode):
                observation, _, _, decisions = religion_fixture()
                saved = SavedLoadOwner.__new__(SavedLoadOwner)
                saved.explicit_pantheon = {'stale': True}
                if mode == 'waiting':
                    decisions['turn_controls'].update(active=False, active_complete=False)
                state = offered(observation)
                def read(actual, obs):
                    self.assertIs(actual, saved)
                    self.assertIs(obs, observation)
                    saved.explicit_pantheon = deepcopy(state)
                    return state
                with patch.object(adapter, 'catalogue', side_effect=read) as native_read:
                    view._add_xp1_pantheon(saved, observation, decisions, actions_closed=mode == 'closed')
                self.assertIn(decisions['schema'], network_turn.XP1_PANTHEON_SCHEMAS)
                pantheon_actions = [r['action'] for r in decisions['candidates'] if r['action']['kind'] == 'pantheon']
                if mode == 'active':
                    native_read.assert_called_once()
                    self.assertEqual(decisions['pantheon'], state)
                    self.assertEqual(pantheon_actions, adapter.actions(state))
                    self.assertEqual(decisions['families']['pantheon']['status'], 'queried_complete')
                else:
                    native_read.assert_not_called()
                    self.assertIsNone(saved.explicit_pantheon)
                    self.assertIsNone(decisions['pantheon'])
                    self.assertEqual(pantheon_actions, [])
                    self.assertEqual(decisions['families']['pantheon']['status'], 'unqualified')

    def test_real_continuation_routes_adapter_and_commits_matching_observation(self):
        for allowed in (True, False):
            with self.subTest(can_start=allowed):
                f = self.fixture()
                self.assertIs(type(f.saved), SavedLoadOwner)
                self.assertIs(type(f.backend.prefix), SavedLoadServices)
                self.assertIs(type(f.token), SavedContinuation)
                adapter.catalogue(f.saved, f.token.observation)
                f.can_start = allowed
                f.saved._running = False
                # The surrounding capability evidence scope belongs to the
                # established loaded-owner fixture, not this routing delivery.
                with patch.object(xp1_load_capability, 'capability_source_scope', return_value=nullcontext()):
                    result = f.saved.execute(f.choice)
                self.assertEqual(result['action'], f.choice)
                self.assertEqual(result['effect']['status'], 'completed' if allowed else 'refused')
                self.assertEqual(result['effect']['observation'], result['observation_after'])
                self.assertEqual(f.token.sequence, 1)
                self.assertFalse(f.backend.busy)
                self.assertFalse(f.saved.poisoned)
                self.assertEqual(f.token.transport.pending, [])
                f.close()

    def test_continuation_refuses_absent_option_foreign_engine_and_bad_action(self):
        for mutation in ('disabled', 'xp2', 'boolean'):
            with self.subTest(mutation=mutation):
                f = self.fixture()
                action = deepcopy(f.choice)
                if mutation == 'disabled':
                    f.saved.xp1_pantheon = False
                elif mutation == 'xp2':
                    f.backend.load_abi = SimpleNamespace(core_sha256=XP2_CORE_SHA256)
                else:
                    action['index'] = True
                with self.assertRaises(ValueError):
                    f.token.execute(action, session=f.saved)
                self.assertEqual(f.machine, [])
                f.close()

    def command_result(self, effect, *, available=True):
        f = self.fixture()
        action = dict(kind='pantheon', index=1, hash=1)
        result = dict(action=deepcopy(action), effect=deepcopy(effect))
        decisions = {'candidates': [dict(action=action)] if available else []}
        from civ6_host.runtime import xp1_session_inputs
        with (patch.object(view, 'read', return_value=({}, f.token.observation, decisions)),
              patch.object(f.saved, 'execute', return_value=result) as execute,
              patch.object(xp1_session_inputs, '_write_once', return_value={'fixture': True})):
            value = worker._execute_xp1(f.saved, action, 0, 0, Path(__file__).parent/'fixture-closure.json')
        return value, execute.call_count

    def test_worker_receipts_completed_refused_and_disappearing_offer(self):
        completed = dict(status='completed', selected_index=1, selected_hash=1, source_sha256=source.SOURCE[1])
        refused = dict(status='refused', refusal_code='native_pantheon_can_start_false',
            request=dict(can_start=False, request_invoked=False), source_sha256=source.SOURCE[1])
        for effect in (completed, refused):
            value, count = self.command_result(effect)
            self.assertEqual(value['status'], effect['status'])
            self.assertEqual(count, 1)
        value, count = self.command_result(completed, available=False)
        self.assertEqual(value['reason'], 'native_action_no_longer_available')
        self.assertEqual(count, 0)

    def test_worker_invalid_receipts_do_not_claim_native_completion(self):
        completed = dict(status='completed', selected_index=1, selected_hash=1, source_sha256=source.SOURCE[1])
        refused = dict(status='refused', refusal_code='native_pantheon_can_start_false',
            request=dict(can_start=False, request_invoked=False), source_sha256=source.SOURCE[1])
        bad = [None, [], dict(completed, source_sha256='0'*64),
               dict(completed, selected_index=True), dict(completed, selected_hash=True),
               dict(completed, selected_index=2), dict(completed, status='pending'),
               dict(refused, request=dict(can_start=0, request_invoked=False)),
               dict(refused, request=dict(can_start=False, request_invoked=True)),
               dict(refused, refusal_code='invented')]
        for effect in bad:
            with self.subTest(effect=effect), self.assertRaises(RuntimeError):
                self.command_result(effect)


if __name__ == '__main__':
    unittest.main()
