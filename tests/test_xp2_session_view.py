"""Shared expansion reader fixture with explicit unsupported families."""
import unittest
from unittest.mock import patch
from civ6_host.runtime import xp1_session_view as view
from civ6_host.runtime.captured_session_profile import select
from civ6_host.runtime.configuration_profiles import XP2_CORE_SHA256
from civ6_host.runtime.xp2_action_transport_source import SOURCE,CALLBACKS
from civ6_host.contracts import network_turn as contract
import test_xp1_session_view as fixtures


class XP2SessionView(unittest.TestCase):
    def setUp(self):
        self.fixture=f=fixtures.ReaderFixtures(methodName='runTest')
        self.addCleanup(f.doCleanups);f.setUp()
        s=f.saved;b=s.backend;selected=select(XP2_CORE_SHA256)
        b.load_abi.core_sha256=XP2_CORE_SHA256;s._engine_sha256=XP2_CORE_SHA256
        b._xp2_postload_requested=True;s.requested['post160_candidate']=True
        s.inputs.profile=selected.candidate.profile;s.inputs.official_bundle=selected.candidate.reference
        b.captured_bundle.reference=selected.candidate.reference
        s.network_reference['capture_manifest_sha256']=selected.candidate.reference[1]
        s.continuation.unit_source=dict(source_sha256=SOURCE[1],callbacks=dict(CALLBACKS))
        for observed in (f.observation,s.continuation.observation):
            observed['width']=44;observed['height']=26

    def test_world_and_unit_queries_use_common_reader_and_explicit_partial_contract(self):
        f=self.fixture
        session,observed,catalogue=view.read(f.saved,0,9)
        self.assertEqual(catalogue['schema'],contract.CAPABILITY_COMBAT_READINESS_SCHEMA)
        self.assertFalse(catalogue['complete_action_space'])
        self.assertEqual(catalogue['families']['found_city']['status'],'queried_complete')
        self.assertEqual(catalogue['families']['research']['status'],'queried_complete')
        self.assertEqual(catalogue['families']['unit_attack']['status'],'queried_partial')
        self.assertEqual(catalogue['placement_inventory']['rows'],[])
        self.assertIn('unit_attacks',catalogue)
        f.attacks.assert_called_once_with(f.saved,observed)
        f.inventory.assert_called_once_with(f.saved.prefix,0,1,observed,core_sha256=XP2_CORE_SHA256)
        f.placements.assert_called_once_with(f.saved,observed)
        f.world.assert_called_once_with(f.saved,observed)
        f.orders.assert_called_once_with(f.saved,observed)
        f.production_queues.assert_called_once_with(f.saved,observed)
        self.assertIn('world_input',catalogue)
        self.assertIn('queued_orders',catalogue)
        self.assertIn('unit_orders',catalogue)
        self.assertEqual(catalogue['production_queues'],[])
        self.assertEqual(catalogue['families']['queue_append']['status'],'queried_partial')
        self.assertEqual(catalogue['families']['queue_remove']['status'],'queried_complete')
        self.assertEqual(catalogue['families']['queue_swap']['status'],'queried_complete')
        self.assertEqual(catalogue['families']['production_placement']['status'],'queried_partial')
        self.assertEqual(catalogue['families']['production_resume']['status'],'queried_partial')
        self.assertEqual(catalogue['families']['world_select_unit']['status'],'queried_complete')
        self.assertEqual(catalogue['families']['world_plot_click']['status'],'queried_partial')
        self.assertEqual(catalogue['families']['unit_order']['status'],'queried_partial')
        f.timer.assert_called_once_with(f.saved.backend,core_sha256=XP2_CORE_SHA256)
        self.assertEqual((observed['width'],observed['height']),(44,26))
        contract.validate_capability_catalogue(catalogue,f.saved.continuation.identity,9,1,
            player_id=0,observation=observed)

    def test_closed_actions_do_not_query_or_fabricate_unit_choices(self):
        f=self.fixture
        _,observed,catalogue=view.read(f.saved,0,9,actions_closed=True)
        self.assertIsNone(catalogue['world_input'])
        self.assertIsNone(catalogue['queued_orders'])
        self.assertIsNone(catalogue['unit_orders'])
        self.assertIsNone(catalogue['production_queues'])
        f.world.assert_not_called();f.orders.assert_not_called();f.production_queues.assert_not_called()
        f.placements.assert_not_called()
        for kind in ('world_select_unit','world_deselect_unit','world_plot_click','unit_order',
                     'queue_append','queue_remove','queue_swap','production_placement','production_resume'):
            self.assertEqual(catalogue['families'][kind],dict(status='unqualified',reason='session_closed'))
        contract.validate_capability_catalogue(catalogue,f.saved.continuation.identity,9,1,
            player_id=0,actions_closed=True,observation=observed)

    def test_xp1_callback_receipt_cannot_be_reused_for_xp2(self):
        from civ6_host.runtime.unit_operation_ui_profile import SOURCE as XP1_SOURCE
        f=self.fixture;f.saved.continuation.unit_source['source_sha256']=XP1_SOURCE[1]
        with self.assertRaisesRegex(ValueError,'source receipt'):view.read(f.saved,0,0)
        self.assertFalse(f.queries)

    def test_every_published_choice_passes_the_command_family_gate(self):
        from civ6_host.runtime.xp1_continuation import SavedContinuation
        from civ6_host.contracts.capability_world_input import actions
        from test_capability_production_queue import entry
        f=self.fixture
        city=dict(id=5,x=3,y=4,owner=0,population=1,
            yields=dict(food=2,production=1,gold=0,science=1,culture=1,faith=0))
        from copy import deepcopy
        for obs in (f.observation,f.saved.continuation.observation):
            obs['cities']=[deepcopy(city)]
            obs['plots']=[dict(index=136,x=4,y=3,visible=True,revealed=True,terrain_type=0,
                feature_type=-1,owner=0,water=False,impassable=False)]
        f.choices.return_value[2]['production']=[dict(city_id=5,queue_size=2,kind='U',
            item_index=0,hash=100,formation=0)]
        offers=[dict(kind='queue_append',city_id=5,category='unit',index=10,hash=110,
            item_type='UNIT_SCOUT',mode='append')]
        offers.extend(dict(kind='queue_remove',city_id=5,position=i) for i in range(2))
        offers.extend(dict(kind='queue_swap',city_id=5,source_position=i,destination_position=j)
            for i in range(2) for j in range(2) if i!=j)
        f.production_queues.return_value=dict(production_queues=[dict(
            schema='civ6rl.production_queue.public.v2',player_id=0,turn=1,city_id=5,
            enabled=True,entries=[entry(i,i) for i in range(2)],offers=offers)],actions=offers)
        placement_offers=[dict(kind='production_placement',city_id=5,category='district',
            index=1,hash=201,item_type='DISTRICT_HOLY_SITE',mode='place',plot_id=136,x=4,y=3),
            dict(kind='production_resume',city_id=5,category='building',index=2,
            hash=202,item_type='BUILDING_ORACLE')]
        f.placements.return_value=dict(placement_offers=placement_offers,placements=[],
            placement_observation_scope='host_tracked',actions=placement_offers)
        def selected(saved,obs):
            result=f.world_reply(saved,obs)
            result['world_input']['selected_unit_id']=obs['units'][0]['id']
            result['actions']=actions(result['world_input'])
            return result
        continuation=SavedContinuation.__new__(SavedContinuation)
        continuation.owner=f.saved.backend
        marker=object();kinds=set();count=0
        with patch.object(SavedContinuation,'_transition',return_value=marker) as transition:
            for reader in (f.world_reply,selected):
                f.world.side_effect=reader
                _,_,catalogue=view.read(f.saved,0,9)
                for row in catalogue['candidates']:
                    kinds.add(row['action']['kind']);count+=1
                    with self.subTest(kind=row['action']['kind']):
                        self.assertIs(continuation.execute(row['action'],session=f.saved),marker)
            self.assertEqual(transition.call_count,count)
        self.assertTrue({'world_select_unit','world_plot_click','world_deselect_unit','unit_order',
            'queue_append','queue_remove','queue_swap','production_placement','production_resume'}<=kinds)


if __name__=='__main__':unittest.main()
