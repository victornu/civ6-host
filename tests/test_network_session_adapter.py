"""Isolated adapter-hook tests; no process, game, or native APIs are started."""
import importlib.util
import sys
import unittest
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import patch


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


if __name__ == '__main__':
    unittest.main()
