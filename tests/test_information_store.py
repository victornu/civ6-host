import copy
import unittest
from uuid import UUID

from civ6_host.contracts import production_info988
from civ6_host.contracts.city_growth import SCHEMA as GROWTH_SCHEMA, TEXT_FIELDS
from civ6_host.contracts.production_inputs import project_quotes
from civ6_host.runtime.information_store import InformationStore


EPISODE = str(UUID(int=0x1234))
GENERATION = 'native-' + EPISODE
PRODUCTION_PIN = 'a' * 64
GROWTH_PIN = 'b' * 64


def observation(pid=0, turn=7, city_ids=(11,)):
    return dict(schema='civ6rl-player-observation-v1', player_id=pid, turn=turn,
                cities=[dict(id=cid, owner=pid, population=2) for cid in city_ids])


def native_quote(pid=0, turn=7, city_id=11):
    row = dict(city_id=city_id, category='building', index=1, hash=100,
        item_type='BUILDING_FIXTURE',
        raw=dict(cost=30, progress=4, turns_left=4, formation_type=None,
                 base_cost=None, base_cost_visible=False),
        public=dict(cost=30, progress=4, turns_left=4, never_completes=False,
                    cost_kind='production'))
    return dict(schema=production_info988.SCHEMA, player_id=pid, turn=turn,
        source_sha256=production_info988.PROOF_SHA256,
        ui_sha256=production_info988.PANEL_SHA256,
        tooltip_sha256=production_info988.TOOLTIP_SHA256, rows=[row])


def production_current(pid=0, turn=7, city_id=11):
    return dict(schema='civ6-host.current-production.v1', player_id=pid, turn=turn,
        cities=[dict(city_id=city_id, state='current', item=dict(category='building',
            index=1, hash=100, item_type='BUILDING_FIXTURE', name='Fixture',
            formation=None, progress=4, cost=30, turns_left=4, never_completes=False))])


def production_event(pid=0, sequence=1, turn=7, *, episode=EPISODE,
                     generation=GENERATION, pin=PRODUCTION_PIN, city_id=11):
    return dict(stage='native_production_administrative_readback',
        episode_id=episode, game_generation=generation, player_id=pid,
        sequence=sequence, turn=turn, source_sha256=pin, actor_channel=False,
        production=dict(player_id=pid, game_turn=turn, cities=[dict(city_id=city_id,
            owner_id=pid, queue_size=1, current_production_hash=100,
            previous_production_hash=0, production_yield=4,
            has_production_progress=True, turns_left=4, kind='B', item_index=1,
            cost=30, progress=4, formation=None)]),
        production_info=native_quote(pid, turn, city_id),
        public_production=production_current(pid, turn, city_id))


def growth_event(pid=0, sequence=1, turn=7, *, episode=EPISODE,
                 generation=GENERATION, pin=GROWTH_PIN, city_ids=(11,)):
    return dict(stage='native_city_growth_administrative_readback',
        episode_id=episode, game_generation=generation, player_id=pid,
        sequence=sequence, turn=turn, source_sha256=pin, actor_channel=False,
        cities=[dict(city_id=cid, food_stock=4.125, growth_threshold=20.0,
            food_surplus=2.3, turns_until_growth=7, turns_until_starvation=-1)
            for cid in city_ids])


def growth_public(pid=0, turn=7, city_id=11):
    display = {key: 'fixture' for key in TEXT_FIELDS}
    display['GrowthLongNum'] = 7
    return dict(schema=GROWTH_SCHEMA, player_id=pid, turn=turn, cities=[dict(
        city_id=city_id, population=2, occupied=False, housing=5.0, amenities=0.0,
        amenities_needed=1.0, happiness=3, display=display, starving=False,
        growth_icon=dict(color='StatGoodCSGlow', u=0, v=150))])


def response(pid=0, sequence=1, turn=7, *, episode=EPISODE,
             generation=GENERATION, city_ids=(11,), production=None, growth=None):
    obs = observation(pid, turn, city_ids)
    quote = native_quote(pid, turn, city_ids[0])
    current = production or production_current(pid, turn, city_ids[0])
    info = project_quotes(quote, pid, turn, observation=obs)
    candidate = dict(candidate_id='production-1', action=dict(kind='production',
        city_id=city_ids[0], category='building', index=1, hash=100,
        item_type='BUILDING_FIXTURE'))
    queue = dict(city_id=city_ids[0], entries=[dict(category='building', index=1, hash=100)])
    decisions = dict(production=current, production_info=info,
        production_queues=[queue], candidates=[candidate])
    if growth is not None:
        decisions['city_growth'] = growth
    return dict(stage='official_session_response', schema='civ6-host.network-decisions.v7',
        episode_id=episode, game_generation=generation, sequence=sequence,
        observation=obs, decisions=decisions)


class InformationStoreTests(unittest.TestCase):
    def setUp(self):
        self.store = InformationStore({'production': PRODUCTION_PIN, 'growth': GROWTH_PIN})

    def test_exact_response_seals_detached_snapshot(self):
        event = production_event()
        self.store.ingest(event)
        reply = response()
        self.store.ingest(reply)
        event['production']['cities'][0]['progress'] = 99
        snapshot = self.store.read('production', reply)
        self.assertEqual(snapshot, production_event())
        snapshot['production']['cities'][0]['progress'] = -1
        self.assertEqual(self.store.read('production', reply)['production']['cities'][0]['progress'], 4)

    def test_latest_evidence_is_replaced_per_player(self):
        first = production_event(pid=0, sequence=1)
        second = production_event(pid=1, sequence=2, city_id=11)
        self.store.ingest(first)
        self.store.ingest(second)
        self.store.ingest(response(pid=0, sequence=1))
        self.store.ingest(response(pid=1, sequence=2))
        self.assertIsNotNone(self.store.read('production', response(pid=0, sequence=1)))
        self.assertIsNotNone(self.store.read('production', response(pid=1, sequence=2)))
        replacement = production_event(pid=0, sequence=3)
        self.store.ingest(replacement)
        self.store.ingest(response(pid=0, sequence=3))
        self.assertIsNone(self.store.read('production', response(pid=0, sequence=1)))
        self.assertIsNotNone(self.store.read('production', response(pid=0, sequence=3)))

    def test_same_turn_different_sequence_does_not_join(self):
        event = production_event(sequence=4, turn=7)
        self.store.ingest(event)
        wrong = response(sequence=5, turn=7)
        self.store.ingest(wrong)
        self.assertIsNone(self.store.read('production', wrong))
        exact = response(sequence=4, turn=7)
        self.store.ingest(exact)
        self.assertIsNotNone(self.store.read('production', exact))

    def test_wrong_source_is_rejected(self):
        with self.assertRaises(ValueError):
            self.store.ingest(production_event(pin='c' * 64))

    def test_public_production_mismatch_never_seals_preaction_snapshot(self):
        self.store.ingest(production_event())
        altered = production_current()
        altered['cities'][0]['item']['progress'] = 5
        reply = response(production=altered)
        self.store.ingest(reply)
        self.assertIsNone(self.store.read('production', reply))

    def test_duplicate_own_cities_cannot_seal_growth(self):
        self.store.ingest(growth_event())
        reply = response(growth=dict(schema='civ6-host.city-growth.v1', player_id=0,
            turn=7, cities=[]))
        reply['observation']['cities'] = [dict(id=11, owner=0, population=2),
                                          dict(id=11, owner=0, population=2)]
        self.store.ingest(reply)
        self.assertIsNone(self.store.read('growth', reply))

    def test_nonfinite_growth_value_is_rejected_at_boundary(self):
        event = growth_event()
        event['cities'][0]['food_stock'] = float('nan')
        # JSON serialization rejects NaN before it can consume retained space.
        with self.assertRaises(ValueError):
            self.store.ingest(event)

    def test_growth_readback_joins_exact_response_without_transforming_raw_values(self):
        event = growth_event()
        reply = response(growth=growth_public())
        self.store.ingest(event)
        self.store.ingest(reply)
        self.assertEqual(self.store.read('growth', reply), event)

    def test_capacity_bounds_all_retained_payloads(self):
        small = InformationStore({'production': PRODUCTION_PIN}, max_bytes=128)
        with self.assertRaises(ValueError):
            small.ingest(production_event())
        self.assertIsNone(small.read('production', response()))

    def test_response_waiting_without_administrative_event_returns_none(self):
        reply = response()
        self.store.ingest(reply)
        self.assertIsNone(self.store.read('production', reply))

    def test_truncated_close_drops_pending_and_sealed_production(self):
        live_event = production_event(sequence=1)
        live_reply = response(sequence=1)
        self.store.ingest(live_event)
        self.store.ingest(live_reply)
        self.assertIsNotNone(self.store.read('production', live_reply))

        final_event = production_event(sequence=2)
        close_reply = response(sequence=2)
        close_reply['operation'] = 'close'
        close_reply['outcome'] = dict(terminated=False, truncated=True)
        close_reply['decisions']['candidates'] = []
        self.store.ingest(final_event)
        self.store.ingest(close_reply)
        self.assertIsNone(self.store.read('production', close_reply))
        self.assertIsNone(self.store.read('production', live_reply))

    def test_new_episode_and_explicit_clear_drop_all_groups(self):
        self.store.ingest(production_event())
        first = response()
        self.store.ingest(first)
        next_episode = str(UUID(int=0x5678))
        next_generation = 'native-' + next_episode
        reset = dict(stage='official_session_response', episode_id=next_episode,
            game_generation=next_generation, sequence=0, observation=None)
        self.store.ingest(reset)
        self.assertIsNone(self.store.read('production', first))
        self.store.ingest(production_event(episode=next_episode, generation=next_generation))
        current = response(episode=next_episode, generation=next_generation)
        self.store.ingest(current)
        self.assertIsNotNone(self.store.read('production', current))
        self.store.clear()
        self.assertIsNone(self.store.read('production', current))

    def test_initial_reset_response_seals_same_episode_sequence_zero_evidence(self):
        self.store.ingest(production_event())
        first = response()
        self.store.ingest(first)
        next_episode = str(UUID(int=0x9999))
        next_generation = 'native-' + next_episode
        self.store.ingest(production_event(sequence=0, episode=next_episode,
                                           generation=next_generation))
        self.store.ingest(growth_event(sequence=0, episode=next_episode,
                                       generation=next_generation))
        reset = response(sequence=0, episode=next_episode, generation=next_generation,
                         growth=growth_public())
        reset['operation'] = 'reset'
        self.store.ingest(reset)
        self.assertIsNone(self.store.read('production', first))
        self.assertIsNotNone(self.store.read('production', reset))
        self.assertIsNotNone(self.store.read('growth', reset))


if __name__ == '__main__':
    unittest.main()
