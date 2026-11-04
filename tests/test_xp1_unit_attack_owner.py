"""Real saved owner/continuation/transport/FIFO/publication; native calls are fixtures."""
from copy import deepcopy
import json
import struct
import unittest
from unittest.mock import patch

from test_xp1_unit_orders_owner import Fixture as OrderFixture
from test_xp1_world_input_owner import Fixture as WorldFixture
from test_session_capabilities import observation
from civ6_host.runtime import xp1_unit_attacks as adapter, xp1_unit_attack_profile as profile
from civ6_host.runtime.native import native_saved_combat as shared


class Fixture(OrderFixture):
    def __init__(self):
        super().__init__()
        obs=observation();obs['turn']=8;obs['units'][0].update(x=0,y=0,type=1)
        obs['plots']=[dict(index=1,x=1,y=0,visible=True,revealed=True,owner=1,
            terrain_type=0,feature_type=-1,water=False,impassable=False)]
        obs['visible_enemy_units']=[dict(owner=1,id=27,type=2,x=1,y=0,damage=0,visible=True)]
        self.observation=deepcopy(obs);self.token.observation=deepcopy(obs)
        self.attacks_left=1;self.no_effect=False;self.fail_after_receive=False;self.selected_operation='RANGE_ATTACK'
        self.city_target=False;self.city_damage=0
        self.stack.enter_context(patch.object(shared,'observe_player',self.observe_native))

    def units(self):
        return [dict(unit_id=u['id'],unit_type=u['type'],x=u['x'],y=u['y'],damage=u['damage'],
                     moves=u['moves'],attacks_remaining=self.attacks_left) for u in self.observation['units']]

    def evaluate(self,child,source,name,**kw):
        if child is not self.token.ui_child:raise AssertionError('Attack query uses foreign Lua child')
        if name==b'@explicit_combat_catalog':
            rows=[] if self.city_target else [dict(unit_id=17,operation=self.selected_operation,target_owner=1,target_id=27,x=1,y=0)]
            return json.dumps(dict(schema='civ6rl-combat-candidates-v1',player_id=0,turn=8,width=8,height=8,candidates=rows)).encode()
        if name==b'@explicit_visible_city_targets':
            cities=[] if not self.city_target else [dict(owner=1,city_id=77,district_id=78,plot_id=1,x=1,y=0,
                garrison_damage=self.city_damage,garrison_max=200,outer_damage=0,outer_max=100,defense_strength=20)]
            candidates=[] if not self.city_target or b'if false then' in source else [dict(unit_id=17,
                operation='RANGE_ATTACK',input_route='dedicated_ranged',target_owner=1,target_id=77,x=1,y=0)]
            return json.dumps(dict(player_id=0,turn=8,width=8,height=8,cities=cities,candidates=candidates)).encode()
        if name==b'@explicit_visible_combat_diplomacy':return b'[{"owner":1,"at_war":true}]'
        if name==b'@explicit_combat_units':
            return json.dumps(dict(player_id=0,turn=8,units=self.units())).encode()
        if name==b'@explicit_unit_attack_request':
            self.token.transport.pending.append(self.payload)
            self.emit('native_command_archive_queued',archive_hex=self.payload.hex(),bytes=len(self.payload),delivery_pending=True)
            return b'submitted'
        return super().evaluate(child,source,name,**kw)

    def virtual(self,core,pointer,slot,rva,result,*args):
        a=self.token.transport.transport_abi
        if rva==a.drain_rva:
            if core is not self.backend.core:raise AssertionError('Foreign attack core')
            def drain(ctx):
                self.machine.append(('drain',))
                if self.fail_after_receive:raise RuntimeError('fixture native combat did not return')
                self.memory.put(self.sentinel,struct.pack('<QQ',self.sentinel,self.sentinel))
                from civ6_host.runtime.native import native_event_15c35863 as event
                fields=event.encode_fields(event.EventFields(0,19,0x78002000))
                self.memory.put(0x78002000,struct.pack('<HHI',0,1,17))
                self.owner.dispatch(event.KIND,fields,0)
                if not self.no_effect:
                    self.observation['units'][0]['moves']=1
                    self.attacks_left=0
                    if self.city_target:self.city_damage=20
                    else:self.observation['visible_enemy_units'][0]['damage']=20
            return drain
        return WorldFixture.virtual(self,core,pointer,slot,rva,result,*args)

    def prepare(self):
        self.saved._running=True;self.set_active(False)
        return adapter.read(self.saved,self.token.observation)

    def execute_attack(self):
        choices=self.prepare();action=choices['actions'][0]
        self.saved._running=False
        return self.saved.execute(action)


class UnitAttackOwnerTests(unittest.TestCase):
    def fixture(self):
        f=Fixture();self.addCleanup(f.close);return f

    def test_shared_apply_uses_real_owner_transport_fifo_and_one_publication(self):
        f=self.fixture();before=deepcopy(f.token.observation)
        result=f.execute_attack();effect=result['effect'];receipt=effect['receipt']
        self.assertEqual(effect['status'],'completed');self.assertIsNone(effect['refusal_code'])
        self.assertEqual(receipt['source_proof_sha256'],profile.SOURCE[1])
        self.assertTrue(receipt['native_defender_selection']);self.assertFalse(receipt['automatic_choices_applied'])
        self.assertEqual(receipt['observation_before'],before)
        self.assertEqual(receipt['observation_after'],result['observation_after'])
        self.assertTrue(receipt['effect']['target_visible_damage_increased'])
        self.assertFalse(receipt['effect']['selected_defender_claimed'])
        self.assertFalse(receipt['effect']['death_or_capture_inferred_from_absence'])
        self.assertEqual((f.token.publication_count,f.token.sequence,f.deferred.consumed_count),(1,1,1))
        self.assertEqual(f.token.transport.pending,[]);self.assertEqual(f.deferred.pending,[])
        self.assertIsNone(f.token._xp1_unit_attack_catalogue)
        self.assertIsNone(f.token.explicit_combat_units);self.assertIsNone(f.token.explicit_combat_cities)
        self.assertFalse(f.saved._running);self.assertFalse(f.backend.busy)
        self.assertEqual(len([r for r in f.machine if r[0]=='publish']),1)

    def test_stale_or_foreign_catalogues_refuse_before_native_delivery(self):
        for change in ('sequence','owner','units','cities','action','observation'):
            with self.subTest(change=change):
                f=self.fixture();choices=f.prepare();action=deepcopy(choices['actions'][0]);before=deepcopy(f.token.observation)
                f.set_active(True)
                if change=='sequence':f.token.sequence+=1
                elif change=='owner':f.saved._backend=object()
                elif change=='units':f.token.explicit_combat_units[0]['attacks_remaining']=99
                elif change=='cities':f.token.explicit_combat_cities.append({})
                elif change=='action':action['unit_id']=True
                else:before['turn']+=1
                with self.assertRaises((ValueError,RuntimeError)):adapter.apply(f.saved,action,before)
                self.assertEqual(f.machine,[]);self.assertEqual(f.token.transport.pending,[])
                f.close()

    def test_shared_city_target_branch_preserves_native_defenses_and_source(self):
        f=self.fixture();f.city_target=True
        f.observation['visible_enemy_units']=[];f.token.observation=deepcopy(f.observation)
        result=f.execute_attack();receipt=result['effect']['receipt'];effect=receipt['effect']
        self.assertEqual(receipt['city_target_source_sha256'],profile.SOURCE[1])
        self.assertEqual(effect['visible_targets_before'],[])
        self.assertEqual(effect['visible_cities_before'][0]['garrison_damage'],0)
        self.assertEqual(effect['visible_cities_after'][0]['garrison_damage'],20)
        self.assertFalse(effect['city_ownership_changed']);self.assertFalse(effect['selected_defender_claimed'])
        self.assertEqual(f.token.publication_count,1)

    def test_uncertain_native_failure_poisons_without_publication_or_replay(self):
        f=self.fixture();f.fail_after_receive=True
        with self.assertRaisesRegex(RuntimeError,'native combat did not return'):f.execute_attack()
        self.assertTrue(f.saved.poisoned and f.backend.poisoned)
        self.assertEqual(f.token.publication_count,0);self.assertIsNone(f.token._xp1_unit_attack_catalogue)
        deliveries=len(f.machine)
        with self.assertRaises((ValueError,RuntimeError)):adapter.read(f.saved,f.token.observation)
        self.assertEqual(len(f.machine),deliveries)

    def test_xp1_no_effect_cannot_fall_through_to_retained_base_lifecycle(self):
        f=self.fixture();f.no_effect=True
        with self.assertRaises((ValueError,RuntimeError)):f.execute_attack()
        self.assertTrue(f.saved.poisoned);self.assertIsNone(f.token._xp1_unit_attack_catalogue)
        self.assertEqual(f.token.publication_count,1)
        self.assertFalse(any(stage=='official_explicit_unit_attack_effect' for stage,_ in f.emitted))


if __name__=='__main__':unittest.main()
