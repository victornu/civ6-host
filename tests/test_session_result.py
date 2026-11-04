"""Terminal transport regressions; fixtures do not qualify a native LAN win."""
import copy
import unittest

from civ6_host import SessionClient
from civ6_host.client import ProtocolError, _digest
from civ6_host.contracts.session_result import project_terminal_result, SCHEMA
from test_session_client import Backend


class TerminalBackend(Backend):
    terminal = False
    terminal_with_board = False
    truncate_without_board = False
    winner = 1
    result_player = None

    def _reply(self, *args, **kwargs):
        response = super()._reply(*args, **kwargs)
        pid = response['observation']['player_id']
        if self.terminal:
            if self.terminal_with_board:
                decisions = response['decisions']
                decisions['candidates'] = []
                decisions['decision_id'] = _digest({k: v for k, v in decisions.items() if k != 'decision_id'})
            else:
                response['observation'] = response['decisions'] = None
            response['outcome'] = dict(terminated=True, truncated=False,
                reason='official_native_victory', native_victory=dict(
                    schema='civ6rl.native_victory_episode.observation.v1',
                    policy_id='first-official-native-victory-v1',
                    episode_id=response['episode_id'], game_generation=response['game_generation'],
                    player_id=pid if self.result_player is None else self.result_player,
                    current_game_turn=self.turn, team_id=pid, is_alive=True, was_ever_alive=True,
                    episode_terminated=True, winner_present=True,
                    winning_team=self.winner, victory_type=3,
                    winner_matches_player_team=self.winner == pid,
                    private_extra={'must_not_escape': 999}))
        elif self.truncate_without_board:
            response['observation'] = response['decisions'] = None
            response['outcome'].update(truncated=True, reason='diagnostic_round_limit')
        return response


class SessionResultTests(unittest.TestCase):
    def setUp(self):
        self.backend = TerminalBackend()
        self.client = SessionClient(self.backend)

    def test_terminal_without_board_replaces_live_view_and_clears_other_catalogues(self):
        initial = self.client.reset()
        self.client.observe(1)
        self.backend.terminal = True
        ended = self.client.poll(0)
        self.assertTrue(ended['outcome']['terminated'])
        self.assertIsNone(ended['observation'])
        self.assertIsNone(ended['decisions'])
        self.assertEqual(ended['sequence'], 2)
        result = ended['outcome']['result']
        self.assertEqual(result, dict(schema=SCHEMA, player_id=0, turn=1,
            team_id=0, status='lost', winning_team=1, victory_type=3, is_alive=True))
        self.assertNotIn('native_victory', ended['outcome'])
        self.assertNotIn('private_extra', result)
        self.assertEqual(self.client.view(), ended)
        with self.assertRaisesRegex(RuntimeError,'No cached actor view'):
            self.client.view(1)
        before = len(self.backend.calls)
        with self.assertRaisesRegex(RuntimeError,'Session ended'):
            self.client.act(0, initial['decisions']['decision_id'], '0-move')
        with self.assertRaisesRegex(RuntimeError,'Session ended'):
            self.client.poll(0)
        self.assertEqual(len(self.backend.calls),before)

    def test_terminal_reset_close_and_fresh_reset_without_stale_result(self):
        self.backend.terminal=True
        self.backend.winner=0
        ended=self.client.reset()
        self.assertEqual(ended['outcome']['result']['status'],'won')
        closed=self.client.close(0)
        self.assertTrue(closed['outcome']['terminated'])
        self.assertEqual(closed['sequence'],1)
        self.backend.terminal=False
        fresh=self.client.reset()
        self.assertNotEqual(fresh['episode_id'],ended['episode_id'])
        self.assertEqual(fresh['sequence'],0)
        self.assertFalse(fresh['outcome']['terminated'])
        self.assertNotIn('result',fresh['outcome'])
        self.assertTrue(fresh['decisions']['candidates'])

    def test_close_cannot_retract_or_replace_a_result(self):
        for still_terminal in (False, True):
            with self.subTest(still_terminal=still_terminal):
                self.backend.terminal = True
                self.backend.winner = 0
                self.client.reset()
                self.backend.terminal = still_terminal
                self.backend.winner = 1
                with self.assertRaisesRegex(ProtocolError, 'Official result (disappeared|changed)'):
                    self.client.close(0)

    def test_display_session_returns_terminal_result_without_raw_board(self):
        self.backend._display_projection_enabled = True
        self.backend.terminal = self.backend.terminal_with_board = True
        self.backend.winner = 0
        view = self.client.reset()
        self.assertEqual(view['outcome']['result']['status'], 'won')
        self.assertIsNone(view['observation'])
        self.assertIsNone(view['decisions'])
        self.assertEqual(self.client.close(0)['outcome']['result'], view['outcome']['result'])

    def test_result_must_belong_to_the_requested_actor_even_without_observation(self):
        self.client.reset()
        self.backend.terminal=True
        self.backend.result_player=1
        with self.assertRaisesRegex(ProtocolError,'another actor'):
            self.client.poll(0)
        self.assertEqual(self.backend.aborts,['session_client_exchange_failed'])

    def test_truncation_replaces_live_cache_without_fabricating_loss(self):
        self.client.reset()
        self.backend.truncate_without_board=True
        view=self.client.poll(0)
        self.assertTrue(view['outcome']['truncated'])
        self.assertFalse(view['outcome']['terminated'])
        self.assertIsNone(view['decisions'])
        self.assertNotIn('result',view['outcome'])

    def test_global_result_does_not_turn_an_uncompleted_command_into_success(self):
        for status in ('refused','submitted','pending'):
            self.backend.terminal=False
            initial=self.client.reset()
            self.backend.next_status=status
            self.backend.terminal=True
            view=self.client.act(0,initial['decisions']['decision_id'],'0-move')
            self.assertEqual(view['outcome']['result']['status'],'lost')
            self.assertIsNone(view['applied_action'])
            self.assertEqual(self.client.command_result['status'],status)

    def test_terminal_summary_rejects_inconsistent_native_facts(self):
        self.backend.terminal=True
        response=self.backend.reset()
        expected=dict(episode_id=response['episode_id'],game_generation=response['game_generation'],
                      player_id=0,turn=1)
        for field,value in [('team_id',False),('winner_matches_player_team',True),
                            ('winner_present',False),('current_game_turn',True),
                            ('victory_type',3.0),('winning_team',-1)]:
            outcome=copy.deepcopy(response['outcome'])
            outcome['native_victory'][field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):
                project_terminal_result(outcome,**expected)


if __name__=='__main__':unittest.main()
