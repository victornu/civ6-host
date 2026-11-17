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

    def test_purchase_quotes_keep_native_flags_and_actor_revision(self):
        from civ6_host.contracts import network_turn, plot_purchases

        view = self.client._views[0]
        decisions, observation = view['decisions'], view['observation']
        turn, city_id = observation['turn'], observation['cities'][0]['id']
        observation.update(width=16, height=9)
        tile = dict(kind='purchase', city_id=city_id, plot_id=17, x=1, y=1,
                    currency='YIELD_GOLD', price_token='35')
        gold = dict(kind='purchase', city_id=city_id, category='unit', index=3, hash=117,
                    item_type='UNIT_SCOUT', currency='YIELD_GOLD', price_token='60')
        faith = dict(gold, currency='YIELD_FAITH', price_token='70')

        def city(*offers):
            return [dict(player_id=0, turn=turn, city_id=city_id, offers=list(offers))]

        decisions['schema'] = network_turn.CAPABILITY_XP2_PLOT_PURCHASE_SCHEMA
        decisions['plot_purchases'] = city(dict(action=tile, command_legal=True, can_afford=False))
        result = self.client.information('purchase_quotes')
        self.assertNotIn('city_purchases', result['data'])
        self.assertEqual(result['data']['plot_purchases'], decisions['plot_purchases'])
        self.assertEqual(result['native_decision_id'], decisions['decision_id'])
        self.assertEqual(result['sequence'], view['sequence'])

        decisions['schema'] = network_turn.CAPABILITY_XP2_FAITH_PURCHASE_SCHEMA
        decisions['families'] = {'purchase': {'unqualified': list(plot_purchases.CITY_FAITH_GAPS)}}
        decisions['city_purchases'] = city(dict(action=gold, command_legal=True, can_afford=True),
                                          dict(action=faith, command_legal=False, can_afford=True))
        data = self.client.information('purchase_quotes', player_id=0)['data']
        self.assertEqual(data['city_purchases'], decisions['city_purchases'])
        data['city_purchases'].clear()
        self.assertEqual(len(self.client.information('purchase_quotes')['data']['city_purchases']), 1)

        with self.assertRaises(InformationUnavailable):
            self.client.information('purchase_quotes', channel='administrative')
        with self.assertRaises(InformationUnavailable):
            self.client.information('purchase_quotes', player_id=1)
        decisions['families']['purchase']['unqualified'] = list(plot_purchases.CITY_GAPS)
        with self.assertRaisesRegex(ProtocolError, 'allowed unit or building purchase'):
            self.client.information('purchase_quotes')
        observation['cities'][0]['owner'] = 1
        with self.assertRaisesRegex(ProtocolError, 'local city roster'):
            self.client.information('purchase_quotes')
        decisions['plot_purchases'] = None
        with self.assertRaises(InformationUnavailable):
            self.client.information('purchase_quotes')
        self.assertEqual(self.backend.calls, [])

    def test_captured_city_information_is_public_and_bound_to_the_cached_actor(self):
        cached = self.client._views[0]
        decisions, observation = cached['decisions'], cached['observation']
        city = observation['cities'][0]
        city.update(x=2, y=3)
        value = dict(player_id=0, turn=observation['turn'], directives=['LIBERATE_PREVIOUS_OWNER'],
            city=dict(city_id=city['id'], x=2, y=3, liberation_recipients={'LIBERATE_PREVIOUS_OWNER': 4}))
        decisions['captured_city'] = value
        public = self.client.information('captured_city')
        self.assertEqual(public['data'], value)
        self.assertEqual(public['sequence'], cached['sequence'])
        self.assertEqual(public['native_decision_id'], decisions['decision_id'])
        with self.assertRaises(InformationUnavailable):
            self.client.information('captured_city', channel='administrative')
        with self.assertRaises(InformationUnavailable):
            self.client.information('captured_city', player_id=4)
        decisions['captured_city'] = None
        with self.assertRaises(InformationUnavailable):
            self.client.information('captured_city')
        self.assertEqual(self.backend.calls, [])

    def test_world_score_is_public_detached_and_bound_to_the_cached_view(self):
        from civ6_host.contracts import network_turn, world_score

        cached = self.client._views[0]
        decisions, observation = cached['decisions'], cached['observation']
        decisions['schema'] = network_turn.CAPABILITY_XP1_CAPTURED_CITY_SCHEMA
        value = dict(schema=world_score.SCHEMA, player_id=0, turn=observation['turn'],
            score_victory_enabled=False, max_game_turns=500, categories=['CATEGORY_CIVICS'],
            teams=[dict(score=15, players=[dict(player_id=None, score=15, category_scores=[3])]),
                   dict(score=12, players=[dict(player_id=0, score=12, category_scores=[2])])])
        decisions['world_score'] = value
        result = self.client.information('world_score')
        self.assertEqual(result['source_contracts']['world_score'], world_score.SCHEMA)
        self.assertEqual(result['data'], value)
        self.assertEqual(result['sequence'], cached['sequence'])
        self.assertEqual(result['native_decision_id'], decisions['decision_id'])
        result['data']['teams'].clear()
        self.assertEqual(self.client.information('world_score')['data'], value)
        with self.assertRaises(InformationUnavailable):
            self.client.information('world_score', channel='administrative')
        self.assertEqual(self.backend.calls, [])

    def test_city_state_levy_information_retains_its_source_schema(self):
        from civ6_host.contracts import city_state_levies, network_turn

        cached = self.client._views[0]
        decisions = cached['decisions']
        decisions['schema'] = network_turn.CAPABILITY_XP1_CITY_STATE_LEVIES_SCHEMA
        value = dict(schema=city_state_levies.SCHEMA, player_id=0, turn=cached['observation']['turn'],
            military_enabled=True, city_states=[dict(player_id=12, can_levy=False,
                gold_cost=100, turn_limit=15, own_levy_active=False)])
        decisions['city_state_levies'] = value
        result = self.client.information('city_state_levies')
        self.assertEqual(result['source_contracts']['city_state_levies'], city_state_levies.SCHEMA)
        self.assertEqual(result['data'], value)
        result['data']['city_states'].clear()
        self.assertEqual(len(self.client.information('city_state_levies')['data']['city_states']), 1)
        self.assertEqual(self.backend.calls, [])

    def test_unit_levy_information_is_bound_to_the_cached_visible_roster(self):
        from civ6_host.contracts import city_state_levies, network_turn

        cached = self.client._views[0]
        decisions, observation = cached['decisions'], cached['observation']
        decisions['schema'] = network_turn.CAPABILITY_XP1_UNIT_LEVIES_SCHEMA
        unit_id = 589825
        observation['units'] = [dict(owner=0, id=unit_id)]
        value = dict(schema=city_state_levies.UNIT_SCHEMA, player_id=0, turn=observation['turn'],
                     units=[dict(owner=0, unit_id=unit_id, original_owner=12, turns_remaining=15)])
        decisions['unit_levies'] = value
        result = self.client.information('unit_levies')
        self.assertEqual(result['source_contracts']['unit_levies'], city_state_levies.UNIT_SCHEMA)
        self.assertEqual(result['data'], value)
        result['data']['units'].clear()
        self.assertEqual(len(self.client.information('unit_levies')['data']['units']), 1)
        observation['units'] = []
        with self.assertRaises(ProtocolError):
            self.client.information('unit_levies')
        self.assertEqual(self.backend.calls, [])

    def test_unit_advancement_information_is_public_detached_and_scoped(self):
        from civ6_host.contracts import network_turn, unit_upgrades

        view = self.client._views[0]
        observation, decisions = view['observation'], view['decisions']
        decisions['schema'] = network_turn.CAPABILITY_XP2_UNIT_UPGRADE_SCHEMA
        decisions['families'] = {kind: {'status': 'queried_complete'}
                                 for kind in ('promote_unit', 'upgrade_unit')}
        observation['units'] = [dict(owner=0, id=256)]
        identity = dict(player_id=0, turn=observation['turn'])
        promotion = dict(kind='promote_unit', unit_id=256, index=7, hash=3461640876,
                         item_type='PROMOTION_BATTLECRY')
        quote = dict(unit_id=256, hash=unit_upgrades.COMMAND, target_type=23, cost=30,
                     resource_type=None, resource_cost=None, legal=False)
        decisions['unit_promotions'] = dict(**identity, offers=[promotion],
            units=[dict(unit_id=256, experience_points=15, promotions=[])])
        decisions['unit_upgrades'] = dict(**identity, offers=[quote])
        for group in ('unit_promotions', 'unit_upgrades'):
            receipt = self.client.information(group)
            self.assertEqual(receipt['data'], decisions[group])
            self.assertEqual(receipt['native_decision_id'], decisions['decision_id'])
            self.assertEqual(receipt['sequence'], view['sequence'])
            self.assertEqual(receipt['source_contracts'], {'decision_catalogue': decisions['schema']})
            receipt['data']['offers'].clear()
            self.assertEqual(len(self.client.information(group)['data']['offers']), 1)
            with self.assertRaises(InformationUnavailable):
                self.client.information(group, channel='administrative')
        decisions['unit_upgrades'] = None
        with self.assertRaises(InformationUnavailable):
            self.client.information('unit_upgrades')
        observation['units'] = []
        with self.assertRaises(ProtocolError):
            self.client.information('unit_promotions')
        self.assertEqual(self.backend.calls, [])

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
