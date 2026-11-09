"""Isolated adapter-hook tests; no process, game, or native APIs are started."""
import importlib.util
from copy import deepcopy
import sys
import unittest
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock, patch


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'src/civ6_host/runtime/native/network_session.py'
sys.path.insert(0, str(ROOT / 'src'))


class FakeProtocol:
    def __init__(self):
        self.sequence = 4
        self.identity = SimpleNamespace(episode_id='ep', game_generation='native-ep')
        self.session = {'local_player_id': 0}
        self.catalogues = {1: dict(decision_id='d1', episode_id='ep',
            game_generation='native-ep', turn=7, candidates=[
                dict(candidate_id='c1', action=dict(kind='move', unit_id=10))])}
        self.commits = []
        self.accepted = []

    def commit_reply(self, request, response):
        self.commits.append((request, response))

    def accept_response(self, response):
        self.accepted.append(response)


class FakeNativeActionSession:
    def __init__(self, *args, **kwargs):
        self.constructor = (args, kwargs)
        self.protocol = FakeProtocol()
        self.nonce = 'n' * 32
        self.requests = []
        self.base_accepted = []

    def _owner(self):
        return None

    def request(self, request):
        self.requests.append(request)
        return request

    def _accepted_response(self, response):
        self.base_accepted.append(response)


def load_adapter():
    protocol_module = ModuleType('civ6_host.runtime.network_protocol')
    protocol_module.CLOSURE_SCHEMA = 'civ6-host.session.closure.v1'
    protocol_module.SCHEMA = 'civ6-host.session.v1'
    protocol_module.NetworkProtocol = type('NetworkProtocol', (), {})
    protocol_module.validate_network_response = lambda *args, **kwargs: None
    def player_id(value):
        if type(value) is not int or not 0 <= value < 64:
            raise ValueError('invalid player')
        return value
    protocol_module._player_id = player_id

    action_module = ModuleType('civ6_host.runtime.native.native_action_session')
    action_module.NativeActionSession = FakeNativeActionSession
    saved_module = ModuleType('civ6_host.runtime.native.native_saved_session')
    saved_module.ROOT = ROOT
    saved_module.MAX_STANDARD_STDOUT = 256 * 1024 * 1024
    name = '_isolated_network_session_adapter_test'
    spec = importlib.util.spec_from_file_location(name, SOURCE)
    module = importlib.util.module_from_spec(spec)
    patcher = patch.dict(sys.modules, {
        'civ6_host.runtime.network_protocol': protocol_module,
        'civ6_host.runtime.native.native_action_session': action_module,
        'civ6_host.runtime.native.native_saved_session': saved_module,
    })
    patcher.start()
    spec.loader.exec_module(module)
    return module, patcher


class NetworkSessionAdapterTests(unittest.TestCase):
    def test_espionage_requires_explicit_boolean_and_complete_trade_chain(self):
        module, patcher = load_adapter()
        self.addCleanup(patcher.stop)
        bundle = dict(path='work/capture/manifest.json', sha256='a' * 64)
        session = module.NativeNetworkSession(official_bundle=bundle)
        self.assertIs(session.espionage_diagnostic, False)
        for flag in (True, 1, None, 'true'):
            with self.subTest(flag=flag), self.assertRaisesRegex(ValueError, 'Espionage'):
                module.NativeNetworkSession(official_bundle=bundle, espionage_diagnostic=flag)

    def test_explicit_trace_budget_uses_shared_cap_without_changing_time_or_defaults(self):
        module, patcher = load_adapter()
        self.addCleanup(patcher.stop)
        bundle=dict(path='work/capture/manifest.json',sha256='a'*64)
        default=module.NativeNetworkSession(official_bundle=bundle)
        self.assertEqual(default.constructor[1]['stdout_limit_mib'],64)
        for budget in (128,256):
            session=module.NativeNetworkSession(official_bundle=bundle,
                lifetime_seconds=180,stdout_limit_mib=budget)
            self.assertEqual(session.constructor[1]['stdout_limit_mib'],budget)
            self.assertEqual(session.constructor[1]['lifetime_seconds'],180)
            self.assertIsNone(session.constructor[1]['episode_budget'])
        for budget in (0,257,True):
            with self.assertRaises(ValueError):
                module.NativeNetworkSession(official_bundle=bundle,stdout_limit_mib=budget)
        with self.assertRaises(ValueError):
            module.NativeNetworkSession(official_bundle=bundle,lifetime_seconds=181)

    def test_import_constructor_and_protocol_hooks_use_module_exports(self):
        module, patcher = load_adapter()
        self.addCleanup(patcher.stop)
        self.assertEqual(module.NativeNetworkSession.closure_schema,
                         'civ6-host.session.closure.v1')
        session = module.NativeNetworkSession(official_bundle={
            'path': 'work/capture/manifest.json', 'sha256': 'a' * 64})
        self.assertEqual(session.input_profile, 'lan')
        self.assertEqual(session.worker_name, 'network_worker.py')

        request, response = {'op': 'fixture'}, {'stage': 'fixture'}
        session._commit_response(request, response)
        self.assertEqual(session.protocol.commits, [(request, response)])
        session._accepted_response(dict(observation={'player_id': 1}))
        self.assertEqual(len(session.base_accepted), 1)
        self.assertEqual(len(session.protocol.accepted), 1)
        self.assertEqual(session._last_actor_id, 1)

        result = session.act(1, 'c1')
        self.assertEqual(result['player_id'], 1)
        self.assertEqual(result['sequence'], 5)
        with self.assertRaises(ValueError):
            session.act(True, 'c1')

    def test_command_defaults_to_last_actor_and_close_can_select_actor(self):
        module, patcher = load_adapter()
        self.addCleanup(patcher.stop)
        session = module.NativeNetworkSession(official_bundle={
            'path': 'work/capture/manifest.json', 'sha256': 'a' * 64})
        session._accepted_response(dict(observation={'player_id': 1}))
        request = session.command('poll')
        self.assertEqual((request['operation'], request['player_id'], request['sequence']),
                         ('poll', 1, 5))
        request = session.command('close', player_id=0)
        self.assertEqual((request['operation'], request['player_id'], request['sequence']),
                         ('close', 0, 5))

    def test_boardless_terminal_reply_sets_default_close_actor(self):
        module, patcher = load_adapter()
        self.addCleanup(patcher.stop)
        session = module.NativeNetworkSession(official_bundle={
            'path': 'work/capture/manifest.json', 'sha256': 'a' * 64})
        session._accepted_response(dict(observation={'player_id': 0}))
        session._accepted_response(dict(observation=None, outcome=dict(
            terminated=True, native_victory={'player_id': 1})))
        self.assertEqual(session.command('close')['player_id'], 1)


class NetworkEspionageWorkerTests(unittest.TestCase):
    def renewal(self):
        return dict(kind='spy_renew', unit_id=9, event_sequence=41, mission_id=7,
                    operation_type='UNITOPERATION_SPY_LISTENING_POST', operation_hash=17,
                    x=2, y=1, plot_id=5)

    def execute(self, action, effect):
        from civ6_host.runtime.workers import network_worker
        observed = dict(player_id=0, turn=73, width=3, height=2)
        result = dict(action=deepcopy(action), effect=deepcopy(effect))
        saved = SimpleNamespace(continuation=SimpleNamespace(observation=observed),
                                execute=Mock(return_value=result), emit=Mock())
        with patch('civ6_host.runtime.xp1_session_view.read', return_value=(
                    {}, observed, dict(candidates=[dict(action=action)]))), \
                patch('civ6_host.runtime.xp1_session_inputs._write_once'), \
                patch.object(network_worker, '_retain_xp2_diplomacy_if_ready', return_value=False):
            command = network_worker._execute_xp1(saved, action, 0, 9, 'unused-closure.json')
        saved.execute.assert_called_once_with(action)
        return command

    def effect(self, action, status):
        return dict(status=status,
                    refusal_code='native_spy_choice_unavailable' if status == 'refused' else None,
                    observation={'private': 'does not belong in the public command receipt'},
                    receipt=dict(action=deepcopy(action),
                                 native_archive_delivered=status != 'refused',
                                 native_effect_readback=status == 'completed',
                                 native_archive_sha256='a' * 64))

    def test_spy_worker_preserves_pending_and_submitted_without_claiming_effect(self):
        action = dict(kind='spy_cancel', unit_id=9)
        for status in ('completed', 'refused', 'submitted', 'pending'):
            with self.subTest(status=status):
                effect = self.effect(action, status)
                command = self.execute(action, effect)
                self.assertEqual(command, dict(status=status, reason=effect['refusal_code'],
                                               requested_action=action))

    def test_all_spy_action_kinds_require_archive_and_completed_effect_evidence(self):
        actions = [dict(kind='spy_travel', unit_id=9, city_owner=1, city_id=14, x=2, y=1),
                   dict(kind='spy_mission', unit_id=9, operation_hash=17,
                        operation_type='UNITOPERATION_SPY_STEAL_TECH_BOOST',
                        mode='start', x=2, y=1, plot_id=5),
                   dict(kind='spy_cancel', unit_id=9),
                   dict(kind='spy_escape', unit_id=9, district_index=4)]
        for action in actions:
            with self.subTest(action=action):
                self.assertEqual(self.execute(action, self.effect(action, 'completed'))['status'],
                                 'completed')
                for key, bad in (('native_archive_delivered', False),
                                 ('native_archive_delivered', 1),
                                 ('native_effect_readback', False),
                                 ('native_effect_readback', 1)):
                    effect = self.effect(action, 'completed')
                    effect['receipt'][key] = bad
                    with self.subTest(key=key, bad=bad), self.assertRaises(RuntimeError):
                        self.execute(action, effect)

    def test_pending_and_submitted_require_delivery_and_every_status_requires_exact_action(self):
        action = dict(kind='spy_cancel', unit_id=9)
        for status in ('submitted', 'pending'):
            effect = self.effect(action, status)
            effect['receipt']['native_archive_delivered'] = False
            with self.subTest(status=status), self.assertRaises(RuntimeError):
                self.execute(action, effect)
        for status in ('completed', 'refused', 'submitted', 'pending'):
            effect = self.effect(action, status)
            effect['receipt']['action']['unit_id'] = 10
            with self.subTest(status=status), self.assertRaises(RuntimeError):
                self.execute(action, effect)
        for effect in (dict(status='completed'), self.effect(action, 'unexpected'),
                       dict(self.effect(action, 'refused'), refusal_code=True)):
            with self.subTest(effect=effect), self.assertRaises(RuntimeError):
                self.execute(action, effect)

    def test_worker_refuses_espionage_without_trade_before_reading_native_closure(self):
        from civ6_host.runtime.workers import network_worker
        selected = SimpleNamespace(family='xp2-lan')
        with patch('civ6_host.runtime.captured_saved_load.select_load_closure',
                   return_value=selected), \
                patch('civ6_host.runtime.xp2_world_war.source_pin', return_value='a' * 64), \
                patch.object(Path, 'read_bytes', side_effect=AssertionError('must reject first')):
            for flag in (True, 1, None, 'true'):
                with self.subTest(flag=flag), self.assertRaisesRegex(ValueError, 'Espionage'):
                    network_worker._open_xp1(dict(espionage_diagnostic=flag),
                                            'unused-closure.json', Mock(), Mock())

    def test_renewal_preserves_only_qualified_statuses_and_native_evidence(self):
        action = self.renewal()
        for status in ('completed', 'pending', 'refused'):
            with self.subTest(status=status):
                self.assertEqual(self.execute(action, self.effect(action, status))['status'], status)
        with self.assertRaises(RuntimeError):
            self.execute(action, self.effect(action, 'submitted'))
        for status in ('completed', 'pending'):
            effect = self.effect(action, status)
            effect['receipt']['native_archive_delivered'] = False
            with self.subTest(status=status), self.assertRaises(RuntimeError):
                self.execute(action, effect)
        effect = self.effect(action, 'completed')
        effect['receipt']['native_effect_readback'] = False
        with self.assertRaises(RuntimeError):
            self.execute(action, effect)
        for status in ('completed', 'pending', 'refused'):
            effect = self.effect(action, status)
            effect['receipt']['action']['event_sequence'] += 1
            with self.subTest(status=status), self.assertRaises(RuntimeError):
                self.execute(action, effect)

    def test_dismissal_completes_only_local_presentation_without_an_archive(self):
        action = dict(kind='spy_completion_dismiss', event_sequence=41, mission_id=7)
        effect = dict(status='completed', refusal_code=None,
                      receipt=dict(action=deepcopy(action), local_presentation_completed=True,
                                   simulation_request_issued=False, native_archive_delivered=False,
                                   native_effect_readback=False))
        self.assertEqual(self.execute(action, effect),
                         dict(status='completed', reason=None, requested_action=action))
        for key, bad in (('local_presentation_completed', False),
                         ('local_presentation_completed', 1),
                         ('simulation_request_issued', True),
                         ('simulation_request_issued', 0),
                         ('native_archive_delivered', True),
                         ('native_archive_delivered', 0),
                         ('action', dict(action, mission_id=8))):
            invalid = deepcopy(effect)
            invalid['receipt'][key] = bad
            with self.subTest(key=key, bad=bad), self.assertRaises(RuntimeError):
                self.execute(action, invalid)
            invalid['receipt'].pop(key)
            with self.subTest(missing=key), self.assertRaises(RuntimeError):
                self.execute(action, invalid)
        for status in ('pending', 'submitted', 'refused'):
            with self.subTest(status=status), self.assertRaises(RuntimeError):
                self.execute(action, dict(effect, status=status))

    def test_completion_commands_bind_actual_map_and_require_xp2_espionage_group(self):
        from civ6_host.runtime import xp1_continuation as continuation
        from civ6_host.runtime.configuration_profiles import XP1_CORE_SHA256, XP2_CORE_SHA256
        observation = dict(player_id=0, turn=73, width=3, height=2)
        actions = [self.renewal(),
                   dict(kind='spy_completion_dismiss', event_sequence=41, mission_id=7)]
        for action in actions:
            continuation.validate_command(action, observation=observation)
            with self.assertRaises(ValueError):
                continuation.validate_command(action)
            for core, feedback, enabled in ((XP1_CORE_SHA256, object(), True),
                                            (XP2_CORE_SHA256, None, True),
                                            (XP2_CORE_SHA256, object(), False),
                                            (XP2_CORE_SHA256, object(), 1)):
                value = SimpleNamespace(
                    owner=SimpleNamespace(load_abi=SimpleNamespace(core_sha256=core)),
                    observation=observation, world_input_prompts={}, trade_feedback=feedback,
                    _transition=Mock())
                session = SimpleNamespace(espionage_diagnostic=enabled)
                with self.subTest(action=action, core=core, enabled=enabled), self.assertRaises(ValueError):
                    continuation.SavedContinuation.execute(value, action, session=session)
                value._transition.assert_not_called()
            value = SimpleNamespace(
                owner=SimpleNamespace(load_abi=SimpleNamespace(core_sha256=XP2_CORE_SHA256)),
                observation=observation, world_input_prompts={}, trade_feedback=object(),
                _transition=Mock(return_value='accepted'))
            session = SimpleNamespace(espionage_diagnostic=True)
            self.assertEqual(continuation.SavedContinuation.execute(value, action, session=session),
                             'accepted')
            value._transition.assert_called_once_with(action, session=session, pump=False)
        with self.assertRaises(ValueError):
            continuation.validate_command(self.renewal(), observation=dict(observation, width=4))


if __name__ == '__main__':
    unittest.main()
