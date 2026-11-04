"""Shared result readers under fixtures; no native GameCore or XP1 win claim."""
import ast
import copy
import importlib.util
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import Mock, patch
from uuid import uuid4

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from civ6_host.runtime.configuration_profiles import XP1_CORE_SHA256,XP2_CORE_SHA256
from civ6_host.runtime import xp1_session_result as result_reader
from civ6_host.runtime import native as native_package
from civ6_host.runtime.native.native_episode_identity import DiagnosticEpisodeIdentity
from civ6_host.runtime.native.native_saved_session_protocol import outcome
from civ6_host.runtime.xp1_saved_load_owner import SavedLoadOwner
from civ6_host.runtime.network_protocol import NetworkProtocol,validate_network_response
from civ6_host.contracts.session_result import project_terminal_result
from test_session_capabilities import CapabilityBackend

spec=importlib.util.spec_from_file_location('result_extraction',ROOT/'tools/extraction_xp1_result_readers.py')
hook=importlib.util.module_from_spec(spec);spec.loader.exec_module(hook)
BASE=result_reader.BASE_CORE_SHA256


def load_reader(name):
    path=ROOT/'src/civ6_host/runtime/native'/f'{name}.py'
    raw=path.read_text(encoding='utf-8')
    tree=ast.parse(raw)
    selected=any(isinstance(node,ast.FunctionDef) and node.name in ('source','verify_source')
                 and any(arg.arg=='core_sha256' for arg in node.args.kwonlyargs) for node in tree.body)
    transformed=raw if selected else hook.parameterize('civ6rl.'+name,raw)
    module=ModuleType('civ6_host.runtime.native.'+name);module.__file__=str(path)
    exec(compile(transformed,str(path)+' <source-hook fixture>','exec'),module.__dict__)
    return module,transformed


class ResultReaderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.facts,cls.facts_source=load_reader('native_episode_facts')
        cls.winning,cls.winning_source=load_reader('native_winning_team')
        with patch.object(native_package,'native_episode_facts',cls.facts):
            cls.victory,cls.victory_source=load_reader('native_victory_episode')

    def setUp(self):
        self.episode=str(uuid4())
        self.identity=DiagnosticEpisodeIdentity(self.episode,'native-'+self.episode)
        for name,module in (('native_episode_facts',self.facts),('native_winning_team',self.winning),
                            ('native_victory_episode',self.victory)):
            p=patch.object(native_package,name,module,create=True);p.start();self.addCleanup(p.stop)
            p=patch.dict(sys.modules,{'civ6_host.runtime.native.'+name:module});p.start();self.addCleanup(p.stop)

    def policy(self,core=XP1_CORE_SHA256):
        return self.victory.FirstOfficialVictory(self.episode,core_sha256=core)

    def test_source_selection_preserves_exact_shared_lua_and_rejects_unknown_core(self):
        self.assertEqual(self.winning.source(),self.winning.source(core_sha256=XP1_CORE_SHA256))
        self.assertEqual(self.facts.build_source(0,1),self.facts.build_source(0,1,core_sha256=XP1_CORE_SHA256))
        self.assertEqual(self.victory.build_source(0,1),self.victory.build_source(0,1,core_sha256=XP1_CORE_SHA256))
        for call in (lambda:self.winning.source(core_sha256='unknown'),
                     lambda:self.facts.build_source(0,1,core_sha256='unknown'),
                     lambda:self.policy('unknown')):
            with self.assertRaises(ValueError):call()
        for name,source in (('native_episode_facts',self.facts_source),
                            ('native_winning_team',self.winning_source),
                            ('native_victory_episode',self.victory_source)):
            with self.subTest(name=name),self.assertRaises(ValueError):
                hook.parameterize('civ6rl.'+name,source)

    def test_base_provenance_and_policy_result_shape_remain_unchanged(self):
        facts=self.facts.parse_facts(b'episode-facts-v1|0|1|0|1|1|0',0,1)
        observed=self.policy(BASE).observe(b'episode-facts-v1|0|1|0|1|1|0',0,1)
        self.assertEqual(facts['source_proof_sha256'],self.facts.PROOF_SHA256)
        self.assertEqual(observed['source_proof_sha256'],self.victory.PROOF_SHA256)
        self.assertEqual(observed['facts_source_proof_sha256'],self.facts.PROOF_SHA256)
        self.assertNotIn('result_source_profile',observed)
        self.assertNotIn('native_terminal_transition_qualified',observed)

    def test_xp2_keeps_shared_reader_and_its_own_explicit_provenance(self):
        self.assertEqual(self.winning.source(core_sha256=XP2_CORE_SHA256),self.winning.source())
        self.assertEqual(self.facts.build_source(0,1,core_sha256=XP2_CORE_SHA256),self.facts.build_source(0,1))
        policy=self.policy(XP2_CORE_SHA256)
        first=policy.observe(b'episode-facts-v1|0|1|4|1|1|0',0,1)
        won=policy.observe(b'episode-facts-v1|0|2|4|1|1|2|4|-123',0,2)
        self.assertFalse(first['episode_terminated']);self.assertTrue(won['episode_terminated'])
        self.assertEqual(won['core_sha256'],XP2_CORE_SHA256)
        self.assertEqual(won['source_proof_sha256'],result_reader.source_reference(XP2_CORE_SHA256)[1])
        self.assertNotEqual(won['source_proof_sha256'],result_reader.SOURCE[1])
        self.assertEqual(won['result_source_profile'],'xp2-status-observation-v1')
        self.assertFalse(won['native_terminal_transition_qualified'])

    def test_absent_winner_does_not_turn_personal_death_into_terminal_result(self):
        result=self.policy().observe(b'episode-facts-v1|0|1|4|0|1|0',0,1)
        self.assertFalse(result['is_alive']);self.assertFalse(result['episode_terminated'])
        self.assertIsNone(result['winning_team']);self.assertIsNone(result['global_engine_terminal'])
        self.assertEqual(result['source_proof_sha256'],result_reader.SOURCE[1])
        self.assertFalse(result['native_write_before_notification_qualified'])
        self.assertFalse(result['native_terminal_transition_qualified'])

    def test_existing_policy_tracks_observed_transition_without_source_transition_claim(self):
        policy=self.policy()
        first=policy.observe(b'episode-facts-v1|0|1|4|1|1|0',0,1)
        won=policy.observe(b'episode-facts-v1|0|2|4|1|1|2|4|-123',0,2)
        self.assertFalse(first['episode_terminated']);self.assertTrue(won['episode_terminated'])
        self.assertTrue(won['absent_to_present_observed'])
        self.assertFalse(won['native_terminal_transition_qualified'])
        won['game_generation']=self.identity.game_generation
        projected=project_terminal_result(outcome(won,1,8),episode_id=self.episode,
            game_generation=self.identity.game_generation,player_id=0,turn=2)
        self.assertEqual(projected['status'],'won');self.assertEqual(projected['victory_type'],-123)
        self.assertNotIn('source_proof_sha256',projected)
        with self.assertRaisesRegex(ValueError,'changed/disappeared'):
            policy.observe(b'episode-facts-v1|0|2|4|1|1|0',0,2)

    def test_fact_arity_identity_and_types_keep_existing_refusals(self):
        for payload in (b'episode-facts-v1|1|1|0|1|1|0',b'episode-facts-v1|0|2|0|1|1|0',
                        b'episode-facts-v1|0|1|0|1|1|1',b'episode-facts-v1|0|1|0|2|1|0',
                        b'episode-facts-v1|0|1|0|1|1|2|-1|4'):
            with self.subTest(payload=payload),self.assertRaises(ValueError):
                self.facts.parse_facts(payload,0,1,core_sha256=XP1_CORE_SHA256)

    def native_reply(self):
        backend=CapabilityBackend();response=backend.reset()
        identity=backend.identity
        protocol=NetworkProtocol(identity,backend.protocol.nonce,initial_turn=1,core_sha256=XP1_CORE_SHA256)
        policy=self.victory.FirstOfficialVictory(identity.episode_id,core_sha256=XP1_CORE_SHA256)
        native=policy.observe(b'episode-facts-v1|0|1|0|1|1|0',0,1)
        native['game_generation']=identity.game_generation
        response['outcome']=outcome(native,0,protocol.limit)
        return backend,protocol,response

    def test_protocol_requires_explicit_matching_engine_and_preserves_outcome_checks(self):
        backend,protocol,response=self.native_reply()
        validate_network_response(response,protocol,'reset')
        with self.assertRaises(ValueError):validate_network_response(response,backend.protocol,'reset')
        for field,replacement in (('source_proof_sha256',self.victory.PROOF_SHA256),
                                  ('facts_source_proof_sha256',self.facts.PROOF_SHA256),
                                  ('native_terminal_transition_qualified',True),
                                  ('native_write_before_notification_qualified',True),
                                  ('core_sha256',BASE),('result_source_profile','other')):
            altered=copy.deepcopy(response);altered['outcome']['native_victory'][field]=replacement
            with self.subTest(field=field),self.assertRaises(ValueError):
                validate_network_response(altered,protocol,'reset')
        altered=copy.deepcopy(response);altered['outcome']['terminated']=True
        with self.assertRaises(ValueError):validate_network_response(altered,protocol,'reset')

    def owner_fixture(self,winner=b'none',facts=b'episode-facts-v1|0|1|0|1|1|0'):
        # Owner graph/native-code verification has its own tests. These explicit
        # fixtures check only the read orchestrator's child, source and bytes.
        saved=object.__new__(SavedLoadOwner)
        lua=SimpleNamespace(evaluate_text=Mock(side_effect=[winner,facts]))
        core=SimpleNamespace(_handle=0x100000)
        prefix=SimpleNamespace(runtime=lua,ui_child=object(),game_child=object(),emit=Mock(),
            _diagnostic_episode_identity=self.identity,quarantined=False)
        backend=SimpleNamespace(runtime=SimpleNamespace(read=object()),core=core,control=Mock(),
            load_abi=SimpleNamespace(core_sha256=XP1_CORE_SHA256),
            poisoned=False,busy=False,stage='xp1-continuation-ready')
        continuation=SimpleNamespace(check=Mock(),transport=SimpleNamespace(require_empty_native_queue=Mock()),
            observation=dict(player_id=0,turn=1),poisoned=False)
        saved.backend=saved._backend=backend;saved.prefix=prefix;saved.core=core
        saved.continuation=continuation;saved._check=Mock()
        saved._running=False;saved.poisoned=False;saved.phase='commands'
        binding=SimpleNamespace(owner=backend,core=core,core_sha256=XP1_CORE_SHA256)
        return saved,binding

    def test_read_uses_exact_backend_reader_and_ui_facts_with_no_gameplay_fallback(self):
        saved,binding=self.owner_fixture()
        with patch.object(result_reader,'bind_owner',return_value=binding) as bind:
            result=result_reader.read(saved,player_id=0)
        bind.assert_called_once_with(saved.backend,saved.core,saved.backend.runtime.read)
        calls=saved.prefix.runtime.evaluate_text.call_args_list
        self.assertEqual(len(calls),2)
        self.assertTrue(all(call.args[0] is saved.prefix.ui_child for call in calls))
        self.assertNotEqual(saved.prefix.ui_child,saved.prefix.game_child)
        self.assertFalse(result['winner_present']);self.assertFalse(saved.poisoned)
        self.assertEqual(result['game_generation'],self.identity.game_generation)
        self.assertEqual(saved.prefix._first_official_victory_policy._core_sha256,XP1_CORE_SHA256)

    def test_read_refuses_disagreement_and_foreign_player_without_fabricated_result(self):
        saved,binding=self.owner_fixture(winner=b'0,9')
        with patch.object(result_reader,'bind_owner',return_value=binding):
            with self.assertRaisesRegex(ValueError,'disagree'):result_reader.read(saved)
        self.assertTrue(saved.poisoned);saved.prefix.emit.assert_not_called()
        for player in (True,1):
            saved,binding=self.owner_fixture()
            with self.subTest(player=player),self.assertRaises(ValueError):result_reader.read(saved,player_id=player)
            saved.prefix.runtime.evaluate_text.assert_not_called()


if __name__=='__main__':unittest.main()
