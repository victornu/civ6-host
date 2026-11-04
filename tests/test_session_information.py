"""Information queries preserve the exact session boundary and channel."""
import copy
import unittest

from civ6_host import InformationUnavailable, SessionClient
from civ6_host.client import ProtocolError, _digest
from test_economy_inputs import fixture
from test_session_client import Backend


class EconomyBackend(Backend):
    def _reply(self, operation, sequence, **kwargs):
        response = super()._reply(operation, sequence, **kwargs)
        obs, data = fixture()
        pid, turn = kwargs['pid'], self.turn
        obs.update(player_id=pid, turn=turn)
        obs['cities'] = [obs['cities'][0]]
        obs['cities'][0]['owner'] = pid
        for key in ('treasury', 'yield_display', 'research_info', 'research_progress'):
            data[key].update(player_id=pid, turn=turn)
        old = response['decisions']
        offers = old['candidates']
        if offers:
            offers += data.pop('candidates')
        else:
            data.pop('candidates')
        old.update(data)
        old['candidates'] = offers
        old['decision_id'] = _digest({k:v for k,v in old.items() if k != 'decision_id'})
        response['observation'] = obs
        return response


class SessionInformationTests(unittest.TestCase):
    def setUp(self):
        self.backend = EconomyBackend()
        self.client = SessionClient(self.backend, allow_administrative=True)
        self.client.reset()

    def test_public_and_admin_share_exact_identity_without_rpc(self):
        public = self.client.information('economy')
        admin = self.client.information('economy', channel='administrative')
        for key in ('episode_id','game_generation','sequence','player_id','turn',
                    'native_decision_id','source_contracts'):
            self.assertEqual(public[key], admin[key])
        self.assertEqual(public['schema'], 'civ6-host.information.v1')
        self.assertEqual(public['channel'], 'public')
        self.assertFalse(admin['data']['actor_channel'])
        self.assertEqual(public['data']['global_yields']['science'], 4.2)
        self.assertEqual(admin['data']['economy']['science'], 4.25)
        self.assertEqual(self.backend.calls, [])
        public['data']['treasury']['gold_balance'] = 1234
        admin['data']['treasury']['gold_balance'] = 4567
        self.assertEqual(self.client.information('economy')['data']['treasury']['gold_balance'], 25)

    def test_admin_requires_explicit_opt_in_and_denial_does_not_abort(self):
        backend = EconomyBackend()
        client = SessionClient(backend)
        client.reset()
        with self.assertRaises(PermissionError):
            client.information('economy', channel='administrative')
        self.assertEqual(backend.aborts, [])
        self.assertEqual(client.information('economy')['channel'], 'public')
        with self.assertRaises(ValueError):
            SessionClient(backend, allow_administrative=1)

    def test_native_turn_horizon_is_administrative_and_bound_to_reset(self):
        from civ6_host.runtime.information_store import InformationStore

        pin = 'a' * 64
        store = InformationStore({'turn_horizon': pin})
        self.backend.read_administrative = store.read
        view = self.client.view()
        event = dict(stage='xp2_saved_end_turn_observed', source_sha256=pin,
                     actor_channel=False, player_id=0, turn=view['observation']['turn'],
                     end_turn=251, **{key: view[key] for key in
                         ('episode_id', 'game_generation', 'sequence')})
        store.ingest(event)
        store.ingest(self.client._reply)
        data = self.client.information('turn_horizon', channel='administrative')['data']
        self.assertEqual(data, event)
        self.assertNotIn('end_turn', view['observation'])
        with self.assertRaises(ValueError):
            self.client.information('turn_horizon')
        self.client.observe(0)
        store.ingest(self.client._reply)
        with self.assertRaises(InformationUnavailable):
            self.client.information('turn_horizon', channel='administrative')

    def test_query_keeps_player_sequence_after_other_player_observation(self):
        original = self.client.information('economy', player_id=0)
        self.client.observe(1)
        self.assertEqual(self.client.information('economy', player_id=0), original)
        other = self.client.information('economy', player_id=1)
        self.assertEqual((other['player_id'], other['sequence']), (1, 1))

    def test_administrative_reader_cannot_change_cached_revision(self):
        initial = self.client.view()

        def mutate(group, response):
            response['sequence'] = False
            return None

        self.backend.read_administrative = mutate
        with self.assertRaisesRegex(ProtocolError, 'Administrative reader mutated'):
            self.client.information('turn_horizon', channel='administrative')
        self.assertEqual(self.client.view(), initial)
        self.assertIs(type(self.client.view()['sequence']), int)

    def test_failing_display_reader_cannot_change_cached_candidates(self):
        initial = self.client.view()

        def mutate_then_raise(response):
            response['decisions']['candidates'].clear()
            raise ValueError('fixture reader failed')

        self.backend._display_projection_enabled = True
        self.backend._read_player_display_projection = mutate_then_raise
        with self.assertRaisesRegex(ValueError, 'fixture reader failed'):
            self.client.view()
        self.backend._display_projection_enabled = False
        self.assertEqual(self.client.view(), initial)

    def test_old_turn_and_reset_do_not_return_stale_information(self):
        first = self.client.information('economy')
        self.backend.turn += 1
        self.client.observe(1)
        with self.assertRaises(InformationUnavailable):
            self.client.information('economy', player_id=0)
        self.client.reset()
        self.assertNotEqual(self.client.information('economy')['episode_id'], first['episode_id'])
        with self.assertRaises(InformationUnavailable):
            self.client.information('economy', player_id=1)

    def test_close_unavailable_group_and_waiting_are_explicit(self):
        with self.assertRaises(ValueError):
            self.client.information('unknown')
        with self.assertRaises(ValueError):
            self.client.information('economy', channel='omniscient')
        with self.assertRaises(InformationUnavailable):
            SessionClient(EconomyBackend()).information('economy')
        saved = copy.deepcopy(self.client._views[0])
        self.client._views[0]['decisions'].pop('treasury')
        with self.assertRaises(InformationUnavailable):
            self.client.information('economy')
        self.client._views[0] = saved
        self.client.close()
        with self.assertRaises(InformationUnavailable):
            self.client.information('economy')

    def test_historical_production_is_not_silently_relabelled_public(self):
        decisions = self.client._views[0]['decisions']
        decisions.update(production={'player_id':0,'game_turn':7,'cities':[]},
                         production_info={},production_queues=[])
        with self.assertRaises(InformationUnavailable):
            self.client.information('production')


if __name__ == '__main__':
    unittest.main()
