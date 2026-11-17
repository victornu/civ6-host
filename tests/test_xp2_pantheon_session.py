"""XP2 pantheon routing through existing owners; no native process execution."""
import ast
from contextlib import ExitStack, nullcontext
from copy import deepcopy
from dataclasses import replace
from itertools import product
import json
from pathlib import Path
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch

from civ6_host.contracts import network_turn as network
from civ6_host.runtime import xp1_pantheon as adapter, xp1_pantheon_source as source
from civ6_host.runtime import xp1_session_view as view, xp1_load_capability, xp1_session_inputs
from civ6_host.runtime.configuration_profiles import XP2_CORE_SHA256
from civ6_host.runtime.execution_images import _PROFILE, _XP1_PROFILE
from civ6_host.runtime.native.network_session import NativeNetworkSession
from civ6_host.runtime.paths import resource_root
from civ6_host.runtime.saved_load_services import SavedLoadServices
from civ6_host.runtime.source_build_identity import CURRENT_UNSIGNED_LOG_HOST_REFERENCE
from civ6_host.runtime.workers import network_worker as worker
from civ6_host.runtime.xp1_saved_load_owner import SavedLoadOwner
from civ6_host.runtime.xp1_continuation import SavedContinuation
from civ6_host.runtime.xp2_bundle_inputs import REFERENCE
from civ6_host.runtime import xp2_bbg_inputs
from test_xp1_network_session import Fixture as ParentFixture, reset_reply
from test_xp2_religious_chain_session import worker_preflight
from test_xp2_religious_unit_operations_session import Fixture
from test_xp2_religious_chain_public import preceding, added as add_chain, validate
from test_xp2_religious_unit_operations_public import permissions_preceding
from test_xp1_religion_beliefs_public import terminal_v11
from test_session_capabilities import seal
from test_xp2_pantheon_public import state


class XP2PantheonSessionTests(unittest.TestCase):
    def test_parent_flag_and_exact_source_closure_then_worker_pins(self):
        flag = 'xp2_pantheon'
        with ParentFixture() as f:
            f.captured.reference = REFERENCE
            f.executable = resource_root() / CURRENT_UNSIGNED_LOG_HOST_REFERENCE[0]
            base = dict(input_profile='xp2-lan', official_bundle=dict(zip(('path', 'sha256'), REFERENCE)))
            self.assertIs(f.session(**base).xp2_pantheon, False)
            for value in (0, 1, None, 'true'):
                with self.assertRaises(ValueError): f.session(**base, xp2_pantheon=value)
            with self.assertRaises(ValueError): f.session(xp2_pantheon=True)
            with self.assertRaisesRegex(ValueError, 'exact admitted'): f.session(**base, xp2_pantheon=True)
            options = dict(base, execution_image_profile=_PROFILE.id, xp2_pantheon=True)
            with patch.object(source, 'require_actions', side_effect=ValueError('source refused')):
                with self.assertRaisesRegex(ValueError, 'source refused'): f.session(**options)
            current = f.session(**options)
            for other in ('xp1_pantheon', 'xp2_prophet_activation', 'xp2_religion_founding',
                          'xp2_religion_beliefs', 'xp2_religious_unit_operations'):
                self.assertIs(getattr(current, other), False)
            from civ6_host.runtime.xp1_session_result import result_provenance
            def reply(session):
                value = reset_reply(session)
                value['outcome']['native_victory'].update(result_provenance(XP2_CORE_SHA256))
                return value
            with patch.object(NativeNetworkSession, '_receive', reply): current.reset()
            path = current.run / 'closure.json'
            self.assertLess(path.stat().st_size, 8*1024*1024)
            closure = json.loads(path.read_text(encoding='utf-8'))
            self.assertIs(closure[flag], True)
            for path, digest in source.source_dependencies(_PROFILE, reference=REFERENCE).items():
                self.assertEqual(closure['pins'][str(Path(path).resolve())], digest)
            self.assertEqual(len(f.spawns), 1)  # OS launch is the existing double.
        check = worker_preflight(flag)
        for reference in (REFERENCE, xp2_bbg_inputs.REFERENCE):
            pins = source.source_dependencies(_PROFILE, reference=reference)
            check(True, NS(reference=reference, family='xp2-lan'), _PROFILE, dict(pins=pins))
            for image, family, ref, retained in ((None, 'xp2-lan', reference, pins),
                    (_XP1_PROFILE, 'xp2-lan', reference, pins), (replace(_PROFILE), 'xp2-lan', reference, pins),
                    (_PROFILE, 'xp1-lan', reference, pins), (_PROFILE, 'xp2-lan', ('foreign', '0'*64), pins),
                    (_PROFILE, 'xp2-lan', reference, {})):
                with self.assertRaises(ValueError): check(True, NS(reference=ref, family=family), image, dict(pins=retained))
        for value in (0, 1, None, 'true'):
            with self.assertRaises(ValueError): check(value, None, None, {})
        check(False, None, None, {})
        tree = ast.parse(Path(worker.__file__).read_text(encoding='utf-8'))
        assignment = [n for n in ast.walk(tree) if isinstance(n, ast.Assign)
                      and ast.unparse(n) == 'saved.xp2_pantheon = xp2_pantheon']
        self.assertEqual(len(assignment), 1)

    def test_view_getter_and_catalogue_cache_all_layers_and_checkpoint(self):
        saved = SavedLoadOwner.__new__(SavedLoadOwner)
        for index, options, mode in product(range(3), product((False, True), repeat=3), ('offered', 'owned')):
            prior, obs = preceding(index, unit_operations=True)
            prior = add_chain(prior, obs, options=options)
            value = deepcopy(prior); expected = state(obs, mode)
            calls = []
            def catalogue(actual, observation):
                self.assertIs(actual, saved); self.assertEqual(observation, obs)
                actual.explicit_pantheon = deepcopy(expected['catalogue'])
                calls.append('catalogue'); return deepcopy(expected['catalogue'])
            def index_reader(actual, observation):
                self.assertIs(actual, saved); self.assertEqual(observation, obs)
                calls.append('index'); return expected['pantheon_index']
            with patch.object(adapter, 'catalogue', catalogue), patch.object(adapter, 'read_pantheon_index', index_reader):
                view._add_xp2_pantheon(saved, obs, value)
            seal(value); validate(value, obs)
            self.assertEqual(value['pantheon'], expected)
            self.assertEqual(saved.explicit_pantheon, expected['catalogue'])
            self.assertEqual(calls, ['catalogue', 'index'])
            self.assertEqual(network.checkpoint_catalogue(value, prior, obs, core_sha256=XP2_CORE_SHA256)[0], prior)

    def test_view_unavailable_skips_both_queries_and_terminal_remains_reduced(self):
        saved = SavedLoadOwner.__new__(SavedLoadOwner)
        cases = [dict(state=phase) for phase in ('waiting', 'closed')]
        cases += [dict(strategic=False, tactical=tactical) for tactical in (False, True)]
        for case in cases:
            prior, obs = permissions_preceding(**case)
            saved.explicit_pantheon = {'stale': True}
            with (patch.object(adapter, 'catalogue', side_effect=AssertionError('unavailable catalogue')),
                  patch.object(adapter, 'read_pantheon_index', side_effect=AssertionError('unavailable index'))):
                view._add_xp2_pantheon(saved, obs, prior, actions_closed=case.get('state') == 'closed')
            seal(prior); validate(prior, obs, closed=case.get('state') == 'closed')
            self.assertIsNone(prior['pantheon']); self.assertIsNone(saved.explicit_pantheon)
        prior, obs = preceding(); terminal = terminal_v11(prior); before = deepcopy(terminal)
        with (patch.object(adapter, 'catalogue', side_effect=AssertionError('terminal query')),
              patch.object(adapter, 'read_pantheon_index', side_effect=AssertionError('terminal index'))):
            view._add_xp2_pantheon(saved, obs, terminal, actions_closed=True)
        self.assertEqual(terminal, before)

    def test_real_owner_continuation_worker_receipt_and_independent_flag(self):
        f = Fixture(); self.addCleanup(f.close)
        self.assertIs(type(f.saved), SavedLoadOwner)
        self.assertIs(type(f.token), SavedContinuation)
        self.assertIs(type(f.backend.prefix), SavedLoadServices)
        f.saved.xp2_pantheon = True; f.saved.xp1_pantheon = False
        action = dict(kind='pantheon', index=7, hash=77)
        effect = dict(status='completed', observation=deepcopy(f.token.observation),
                      selected_index=7, selected_hash=77, source_sha256=source.source_for(_PROFILE)[1])
        def apply(actual, selected, before):
            self.assertIs(actual, f.saved); self.assertEqual(selected, action)
            self.assertEqual(before, f.token.observation)
            self.assertTrue(actual._running)
            return deepcopy(effect)
        def execute(result=None):
            with ExitStack() as stack:
                stack.enter_context(patch.object(view, 'read', return_value=({}, deepcopy(f.token.observation),
                    dict(candidates=[dict(action=deepcopy(action))]))))
                stack.enter_context(patch.object(xp1_session_inputs, '_write_once', return_value={'fixture': True}))
                stack.enter_context(patch.object(xp1_load_capability, 'capability_source_scope', return_value=nullcontext()))
                stack.enter_context(patch.object(adapter, 'apply', side_effect=apply))
                if result is not None: stack.enter_context(patch.object(f.saved, 'execute', return_value=result))
                return worker._execute_xp1(f.saved, action, 0, 0, Path(__file__).parent/'fixture-closure.json')
        f.saved._running = False
        self.assertEqual(execute(), dict(status='completed', reason=None, requested_action=action))
        self.assertEqual(f.token.sequence, 1)
        self.assertFalse(f.backend.busy); self.assertFalse(f.saved.poisoned)
        self.assertEqual((f.token.transport.pending, f.deferred.pending), ([], []))
        for bad in (dict(effect, selected_index=True), dict(effect, selected_index=8),
                    dict(effect, selected_hash=78), dict(effect, source_sha256=source.SOURCE[1]),
                    dict(effect, status='refused', refusal_code='native_pantheon_can_start_false',
                         request=dict(can_start=False, request_invoked=False))):
            with self.assertRaises(RuntimeError): execute(dict(action=action, effect=bad))
        for flag in (False, 1):
            f.saved.xp2_pantheon = flag; f.saved.xp1_pantheon = True
            with self.assertRaises(ValueError): f.token.execute(action, session=f.saved)
        f.saved.xp2_pantheon = True; f.saved.xp1_pantheon = False
        f.token.check_close()


if __name__ == '__main__': unittest.main()
