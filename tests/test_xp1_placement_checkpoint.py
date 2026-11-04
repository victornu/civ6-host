"""Host placement tracking across the real shared Save publisher/XP1 owner.

Machine calls/memory use the established composed Save fixture. Restoring the
synthetic produced manifest replaces only ancestry authentication (already
covered separately), never placement decoding, owner guards or XP1 boundary.
No GameCore executes and no native placement/Load compatibility is claimed.
"""
from copy import deepcopy
import json
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch

from test_xp1_session_checkpoint_owner import Fixture, LAB, provider
from civ6_host.runtime import network_checkpoint as checkpoint
from civ6_host.runtime.capture_profiles import LAN_PROFILE
from civ6_host.runtime.native import native_production_placement as placement


def choice(kind='district', *, player=0, city=23, plot=28):
    name, index, hash_ = (('DISTRICT_HOLY_SITE', 1, 201) if kind == 'district'
                          else ('BUILDING_ORACLE', 2, 202))
    raw = (f'placement-v1|{player}|{city}|8|catalog|1|1|2|3|4|5|6|7|8|9|8|8|1|'
           f'{kind}:{name}:{index}:{hash_}:place:{plot}:{plot%8}:{plot//8}').encode()
    return placement.choose(placement.parse_catalog(raw, player, city, 8), kind, index, plot)


def serialized(row, *, xp1=True):
    key = (row['player_id'], row['city_id'], row['plot_id']) if xp1 else (row['city_id'], row['plot_id'])
    return json.loads(json.dumps(dict(key=key, choice=row)))


class PlacementCheckpointTests(unittest.TestCase):
    def setUp(self):
        provider._STATES.clear()
        self.addCleanup(provider._STATES.clear)

    def fixture(self):
        f = Fixture()
        self.addCleanup(f.close)
        return f

    def manifest(self, f, rows):
        from civ6_host.runtime.xp1_session_checkpoint import boundary
        return dict(observation=deepcopy(f.token.observation), host_placement_tracking=deepcopy(rows),
                    host_world_selection=17, network_boundary=boundary(f.saved))

    def restore(self, f, manifest):
        with patch.object(checkpoint, 'manifest', return_value=manifest) as retained:
            checkpoint.prepare_owner(f.saved, f.token.observation)
        retained.assert_called_once_with(f.saved.inputs.checkpoint,
                                         official_bundle=f.saved.inputs.official_bundle)

    def test_real_save_publisher_and_xp1_restore_preserve_actor_key_and_native_arguments(self):
        f = self.fixture()
        originals = [choice(), choice('building', city=24, plot=29)]
        expected = {(v['player_id'], v['city_id'], v['plot_id']): v for v in originals}
        f.token.explicit_placements = deepcopy(expected)
        result = f.save()
        self.assertEqual(f.machine, [('configuration',), ('save',)])
        manifest = json.loads((LAB / result['manifest']['path']).read_bytes())
        self.assertEqual(manifest['host_placement_tracking'], [serialized(v) for v in originals])
        self.assertTrue(all(type(row['choice']['arguments']) is list
                            for row in manifest['host_placement_tracking']))
        f.token.explicit_placements = {}; f.token.world_input_selections = {}
        f.saved.inputs.checkpoint = (result['manifest']['path'], result['manifest']['sha256'])
        self.restore(f, manifest)
        self.assertEqual(f.token.explicit_placements, expected)
        self.assertEqual(f.token.world_input_selections, {0: 17})
        self.assertFalse(hasattr(f.saved, 'explicit_placements'))
        self.assertFalse(f.saved._running); self.assertFalse(f.saved.poisoned)
        for row in f.token.explicit_placements.values():
            placement._validate_choice(row)
            self.assertIs(type(row['arguments']), tuple)
        manifest['host_placement_tracking'][0]['choice']['arguments'][0][1] += 1
        self.assertEqual(f.token.explicit_placements, expected)

    def test_invalid_actor_shape_types_duplicate_arguments_and_bounds_never_commit(self):
        f = self.fixture()
        kept = {(0, 99, 30): choice(city=99, plot=30)}
        f.token.explicit_placements = deepcopy(kept); f.token.world_input_selections = {0: 999}
        good = self.manifest(f, [serialized(choice())])
        for fault in ('actor', 'legacy_pair', 'boolean', 'float', 'tuple', 'mismatch',
                      'duplicate', 'arguments', 'row_extra', 'oversized'):
            with self.subTest(fault=fault):
                m = deepcopy(good); row = m['host_placement_tracking'][0]
                if fault == 'actor': row.update(serialized(choice(player=1)))
                elif fault == 'legacy_pair': row['key'] = row['key'][1:]
                elif fault == 'boolean': row['key'][0] = False
                elif fault == 'float': row['key'][1] = 23.0
                elif fault == 'tuple': row['key'] = tuple(row['key'])
                elif fault == 'mismatch': row['key'][2] += 1
                elif fault == 'duplicate': m['host_placement_tracking'].append(deepcopy(row))
                elif fault == 'arguments': row['choice']['arguments'].reverse()
                elif fault == 'row_extra': row['other_player'] = 1
                else: m['host_placement_tracking'] = [deepcopy(row) for _ in range(257)]
                with self.assertRaises(ValueError): self.restore(f, m)
                self.assertEqual(f.token.explicit_placements, kept)
                self.assertEqual(f.token.world_input_selections, {0: 999})
        self.assertEqual(f.machine, [])

    def test_failed_real_xp1_boundary_or_foreign_owner_cannot_publish_tracking(self):
        f = self.fixture(); good = self.manifest(f, [serialized(choice())])
        f.token.explicit_placements = {}; f.token.world_input_selections = {0: 999}
        wrong = deepcopy(good); wrong['network_boundary']['session']['turn'] += 1
        with self.assertRaisesRegex(ValueError, 'boundary differs'): self.restore(f, wrong)
        self.assertEqual(f.token.explicit_placements, {})
        self.assertEqual(f.token.world_input_selections, {0: 999})
        foreign = NS(inputs=f.saved.inputs, continuation=f.token)
        with patch.object(checkpoint, 'manifest', return_value=good):
            with self.assertRaisesRegex(TypeError, 'SavedLoadOwner'):
                checkpoint.prepare_owner(foreign, f.token.observation)
        self.assertEqual(f.token.explicit_placements, {})
        self.assertEqual(f.token.world_input_selections, {0: 999})
        self.assertEqual(f.machine, [])

    def test_base_double_keys_and_empty_historical_tracking_remain_supported(self):
        session = dict(game_mode='LAN', turn_phase='TURNPHASE_SIMULTANEOUS', turn=8,
                       local_player_id=0, human_player_ids=[0], active_human_player_ids=[0])
        controls = dict(active=True, active_complete=True, can_unready=False, timer_elapsed=False)
        o = dict(player_id=0, turn=8)
        owner = NS(inputs=NS(profile=LAN_PROFILE, checkpoint=('work/fixture.json','a'*64),
                            official_bundle=('work/capture.json','b'*64)),
                   network_turn_rows={0:dict(active=True),1:dict(active=False)},
                   turn_continuation=None, world_input_prompts={}, control=lambda **kw:None,
                   explicit_placements={}, world_input_selections={})
        m = dict(observation=o, host_placement_tracking=[serialized(choice(), xp1=False)],
                 host_world_selection=17, network_boundary=dict(session=session,controls=controls))
        with patch.object(checkpoint,'manifest',return_value=m), \
             patch('civ6_host.runtime.network_owner.state',return_value=session), \
             patch('civ6_host.runtime.network_turns.controls',return_value=controls):
            checkpoint.prepare_owner(owner, o)
            self.assertEqual(owner.explicit_placements, {(23,28): choice()})
            m['host_placement_tracking'][0]['key'] = [0,23,28]
            with self.assertRaises(ValueError): checkpoint.prepare_owner(owner, o)
            self.assertEqual(owner.explicit_placements, {(23,28): choice()})
            m['host_placement_tracking'] = []
            checkpoint.prepare_owner(owner, o)
            self.assertEqual(owner.explicit_placements, {})

    def test_real_comparison_accepts_explicit_v7_upgrade_without_rewriting_v5_v6(self):
        from test_capability_placement import PlacementContract
        from test_session_capabilities import seal
        from civ6_host.contracts import network_turn as contract, placement as wire
        from civ6_host.contracts import production_queue as queue
        f = PlacementContract(); f.setUp()
        current = f.value(); observation = f.fixture.obs
        for schema in (contract.CAPABILITY_UNIT_ORDERS_SCHEMA,
                       contract.CAPABILITY_PRODUCTION_QUEUE_SCHEMA):
            with self.subTest(schema=schema):
                old = deepcopy(current)
                old['schema'] = schema
                for field in ('placements','placement_offers','placement_observation_scope'):
                    old.pop(field)
                new_kinds = set(wire.ACTION_FIELDS)
                if schema == contract.CAPABILITY_UNIT_ORDERS_SCHEMA:
                    old.pop('production_queues'); new_kinds.update(queue.FIELDS)
                for kind in new_kinds: old['families'].pop(kind)
                old['candidates'] = [row for row in old['candidates'] if row['action']['kind'] not in new_kinds]
                seal(old)
                f.fixture.validate(old)
                frozen = deepcopy(old)
                records = []
                owner = NS(inputs=NS(checkpoint=('work/fixture.json','a'*64),
                                     official_bundle=('work/capture.json','b'*64)),
                           emit=lambda event,**value:records.append((event,value)))
                manifest = dict(observation=deepcopy(observation), decisions=old)
                with patch.object(checkpoint, 'manifest', return_value=manifest):
                    checkpoint.compare_decisions(owner, observation, current)
                    receipt = records[-1][1]
                    self.assertFalse(receipt['public_decisions_equal'])
                    self.assertTrue(receipt['saved_decision_fields_equal'])
                    self.assertEqual(receipt['catalogue_transition']['source_schema'], schema)
                    self.assertEqual(receipt['catalogue_transition']['target_schema'], contract.CAPABILITY_PLACEMENT_SCHEMA)
                    self.assertEqual(old, frozen)
                    self.assertEqual(len(records),1)
                    old['candidates'][0]['action']['fixture_hidden_change'] = True
                    with self.assertRaisesRegex(ValueError, 'catalogue differs'):
                        checkpoint.compare_decisions(owner, observation, current)
                    self.assertEqual(len(records),1)


if __name__ == '__main__': unittest.main()
