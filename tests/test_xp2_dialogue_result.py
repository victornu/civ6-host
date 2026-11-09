"""Fresh result queries under a retained modal; no DLL or cached-outcome stand-in."""
from contextlib import contextmanager,ExitStack
from types import SimpleNamespace as NS
import unittest
from unittest.mock import Mock,patch

from civ6_host.runtime import xp1_session_result as result
from civ6_host.runtime.xp1_saved_load_owner import SavedLoadOwner
from civ6_host.runtime.xp2_diplomacy import _SavedDialogueContext
from civ6_host.runtime.configuration_profiles import XP2_CORE_SHA256


class DialogueResultTests(unittest.TestCase):
    def fixture(self,stack):
        saved=object.__new__(SavedLoadOwner);saved._running=False;saved._check=Mock()
        core=NS();backend=NS(load_abi=NS(core_sha256=XP2_CORE_SHA256),core=core,
                             runtime=NS(read=Mock()),control=Mock())
        prefix=NS(runtime=NS(evaluate_text=Mock(return_value=b'fresh-native-facts')),
                  ui_child=object(),emit=Mock())
        continuation=NS(observation=dict(player_id=0,turn=25),check=Mock(),
                         transport=NS(require_empty_native_queue=Mock()))
        saved.backend,saved.prefix,saved.continuation,saved.core=backend,prefix,continuation,core
        context=_SavedDialogueContext(saved,object())
        def validate(owner):
            self.assertIs(owner,backend)
            self.assertFalse(saved._running,'Quiescent validation cannot run within an exclusive query')
        context.validate=Mock(side_effect=validate);saved._xp2_diplomacy=context
        @contextmanager
        def attempt():
            self.assertFalse(saved._running);saved._running=True
            try:yield
            finally:saved._running=False
        saved._attempt=attempt
        identity=NS(episode_id='episode',game_generation='generation')
        stack.enter_context(patch('civ6_host.runtime.native.native_episode_identity.require_episode',return_value=identity))
        stack.enter_context(patch.object(result,'verify_reader_source'))
        stack.enter_context(patch.object(result,'bind_owner',return_value=NS(owner=backend,core=core,core_sha256=XP2_CORE_SHA256)))
        native=dict(winner_present=True,winning_team=0,victory_type=3)
        stack.enter_context(patch('civ6_host.runtime.native.native_winning_team.parse',return_value=native))
        stack.enter_context(patch('civ6_host.runtime.native.native_winning_team.source',return_value=b'winner'))
        stack.enter_context(patch('civ6_host.runtime.native.native_episode_facts.build_source',return_value=b'facts'))
        stack.enter_context(patch('civ6_host.runtime.native.native_episode_facts.parse_facts',return_value=native))
        class Policy:
            def __init__(self,episode_id,*,core_sha256):
                self.episode_id=episode_id;self._core_sha256=core_sha256
            def observe(self,payload,player_id,turn):
                if payload!=b'fresh-native-facts':raise AssertionError('Native facts were replaced')
                return dict(native,player_id=player_id,current_game_turn=turn)
        stack.enter_context(patch('civ6_host.runtime.native.native_victory_episode.FirstOfficialVictory',Policy))
        return saved,backend,prefix,context

    def test_dialogue_queries_both_native_result_sources_and_revalidates_outside_query(self):
        with ExitStack() as stack:
            saved,backend,prefix,context=self.fixture(stack)
            observed=result.read(saved,player_id=0,allow_diplomacy=True)
            self.assertTrue(observed['winner_present'])
            self.assertEqual(prefix.runtime.evaluate_text.call_count,2)
            self.assertEqual([call.args[2] for call in prefix.runtime.evaluate_text.call_args_list],
                             [b'@xp1_session_winner',b'@xp1_session_episode_facts'])
            self.assertEqual(context.validate.call_count,2)
            self.assertEqual(backend.control.call_count,2)
            for call in backend.control.call_args_list:
                self.assertEqual(call.kwargs,dict(empty=True,allow_diplomacy=True))
            self.assertFalse(saved._running)

    def test_foreign_or_absent_context_refuses_before_any_result_query(self):
        for wrong in (None,NS(validate=Mock())):
            with self.subTest(context=wrong),ExitStack() as stack:
                saved,backend,prefix,context=self.fixture(stack)
                saved._xp2_diplomacy=wrong
                with self.assertRaisesRegex(ValueError,'exact retained saved context'):
                    result.read(saved,allow_diplomacy=True)
                prefix.runtime.evaluate_text.assert_not_called();backend.control.assert_not_called()


if __name__=='__main__':unittest.main()
