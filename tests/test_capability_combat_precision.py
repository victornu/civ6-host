"""v10 official public precision and exact administrative boundary separation."""
from copy import deepcopy
from types import SimpleNamespace
from uuid import UUID
import unittest

from civ6_host.contracts import network_turn as contract, capability_unit_attacks as attacks
from civ6_host.contracts import information
from civ6_host.runtime.information_store import InformationStore
from civ6_host.session_client import SessionClient, InformationUnavailable
import test_capability_unit_attacks as attack_tests
from test_session_capabilities import seal


def public(value,obs):
    result=deepcopy(value);result['schema']=contract.CAPABILITY_COMBAT_PUBLIC_SCHEMA
    if result['unit_attacks'] is not None:
        result['unit_attacks']=attacks.project_public(value['unit_attacks'],
            observation=obs,queued_orders=value['queued_orders'])
    return seal(result)


def response(obs,dec):
    return dict(stage='official_session_response',operation='observe',
        episode_id=dec['episode_id'],game_generation=dec['game_generation'],sequence=dec['sequence'],
        observation=deepcopy(obs),decisions=deepcopy(dec))


def event(obs,dec,raw):
    return dict(stage='native_combat_administrative_readback',episode_id=dec['episode_id'],
        game_generation=dec['game_generation'],sequence=dec['sequence'],player_id=obs['player_id'],
        turn=obs['turn'],source_sha256=attacks.PUBLIC_PRECISION_SHA256,actor_channel=False,
        cities=deepcopy(raw))


class CombatBackend(attack_tests.AttackBackend):
    def __init__(self,**kw):
        self.store=InformationStore({'combat':attacks.PUBLIC_PRECISION_SHA256})
        super().__init__(**kw)
    def _reply(self,operation,sequence,player,requested=None):
        result=super()._reply(operation,sequence,player,requested)
        if result['decisions'] is not None:
            old=result['decisions']
            if old['unit_attacks'] is not None:
                old['unit_attacks']['cities'][0]['defense_strength']=22.5
                seal(old)
            result['decisions']=public(old,result['observation'])
            if old['unit_attacks'] is not None:
                self.store.ingest(event(result['observation'],result['decisions'],old['unit_attacks']['cities']))
        self.store.ingest(result)
        return result
    def read_administrative(self,group,result):return self.store.read(group,result)


class CombatPrecisionTests(unittest.TestCase):
    def setUp(self):
        self.f=attack_tests.UnitAttackContract();self.f.setUp();self.obs=self.f.obs
        base=self.f
        while hasattr(base,'fixture'):base=base.fixture
        episode=str(UUID(int=0x123456))
        base.identity=SimpleNamespace(episode_id=episode,game_generation='native-'+episode)
        self.raw=self.f.value();self.raw['unit_attacks']['cities'][0]['defense_strength']=22.5;seal(self.raw)
        self.current=public(self.raw,self.obs)
        self.e=event(self.obs,self.current,self.raw['unit_attacks']['cities'])
        self.r=response(self.obs,self.current)

    def test_projection_uses_ui_rounding_without_native_offer_or_action_changes(self):
        for native,display in ((22.0,22),(22+127/256,22),(22.5,23),(22+129/256,23)):
            raw=deepcopy(self.raw['unit_attacks']);raw['cities'][0]['defense_strength']=native
            before=deepcopy(raw);p=attacks.project_public(raw,observation=self.obs,
                                                       queued_orders=self.raw['queued_orders'])
            self.assertEqual(p['cities'][0]['defense_strength'],display)
            self.assertIs(type(p['cities'][0]['defense_strength']),int)
            self.assertEqual(raw,before);self.assertEqual(p['offers'],raw['offers'])
            self.assertEqual(p['units'],raw['units']);self.assertEqual(p['relationships'],raw['relationships'])
        self.f.validate(self.current)
        self.assertEqual(self.current['candidates'],self.raw['candidates'])
        self.assertEqual(self.current['families'],self.raw['families'])
        another=deepcopy(self.raw);another['unit_attacks']['cities'][0]['defense_strength']=22+129/256
        self.assertEqual(public(another,self.obs),self.current)

    def test_v9_remains_exact_and_v10_rejects_raw_or_extra_precision(self):
        self.f.validate(self.raw)
        bad=deepcopy(self.current);bad['unit_attacks']['cities'][0]['defense_strength']=22.5;seal(bad)
        with self.assertRaisesRegex(ValueError,'displayed integer'):self.f.validate(bad)
        for key,value in (('defense_strength',23.0),('garrison_damage',2.0),('outer_max',True)):
            bad=deepcopy(self.current);bad['unit_attacks']['cities'][0][key]=value;seal(bad)
            with self.assertRaises(ValueError):self.f.validate(bad)
        for native in (22.001,1<<24):
            bad=deepcopy(self.raw['unit_attacks']);bad['cities'][0]['defense_strength']=native
            with self.assertRaises(ValueError):attacks.project_public(bad)
        with self.assertRaisesRegex(ValueError,'Historical raw'):
            information.project('combat',self.obs,self.raw)

    def test_administrative_store_seals_only_exact_identity_projection_and_source(self):
        store=InformationStore({'combat':attacks.PUBLIC_PRECISION_SHA256})
        store.ingest(self.e);self.assertIsNone(store.read('combat',self.r))
        store.ingest(self.r);value=store.read('combat',self.r)
        self.assertEqual(value,self.e);value['cities'][0]['defense_strength']=99
        self.assertEqual(store.read('combat',self.r),self.e)
        for key,change in (('sequence',1),('player_id',1),('turn',2),('source_sha256','0'*64),('actor_channel',True)):
            bad=deepcopy(self.e);bad[key]=change
            with self.subTest(key=key),self.assertRaises(ValueError):
                information.validate_administrative('combat',bad,self.r,attacks.PUBLIC_PRECISION_SHA256)
        for key,change in (('owner',2),('plot_id',38),('defense_strength',24.5),('raw_extra',1)):
            bad=deepcopy(self.e);bad['cities'][0][key]=change
            with self.subTest(key=key),self.assertRaises(ValueError):
                information.validate_administrative('combat',bad,self.r,attacks.PUBLIC_PRECISION_SHA256)
        next_response=deepcopy(self.r);next_response['sequence']+=1
        store.ingest(next_response);self.assertIsNone(store.read('combat',self.r))
        store.clear();self.assertIsNone(store.read('combat',self.r))

    def test_checkpoint_v9_uses_exact_raw_evidence_and_v8_needs_no_inverted_rounding(self):
        current_before,old_before=deepcopy(self.current),deepcopy(self.raw)
        with self.assertRaises(ValueError):contract.checkpoint_catalogue(self.current,self.raw,self.obs)
        projected,transition=contract.checkpoint_catalogue(self.current,self.raw,self.obs,
            combat_evidence=self.e,combat_source_sha256=attacks.PUBLIC_PRECISION_SHA256)
        self.assertEqual(projected,self.raw)
        self.assertTrue(transition['legacy_raw_values_compared_from_administrative_readback'])
        self.assertEqual(transition['precision_source_sha256'],attacks.PUBLIC_PRECISION_SHA256)
        altered=deepcopy(self.e);altered['cities'][0]['defense_strength']=22+129/256
        compared,_=contract.checkpoint_catalogue(self.current,self.raw,self.obs,
            combat_evidence=altered,combat_source_sha256=attacks.PUBLIC_PRECISION_SHA256)
        self.assertNotEqual(compared,self.raw) # Same display cannot satisfy exact old raw equality.
        for key,val in (('sequence',1),('source_sha256','0'*64),('actor_channel',True)):
            altered=deepcopy(self.e);altered[key]=val
            with self.assertRaises(ValueError):contract.checkpoint_catalogue(self.current,self.raw,self.obs,
                combat_evidence=altered,combat_source_sha256=attacks.PUBLIC_PRECISION_SHA256)
        older=self.f.fixture.value()
        projected,_=contract.checkpoint_catalogue(self.current,older,self.obs)
        self.assertEqual(projected,older)
        for schema in (contract.CAPABILITY_PLACEMENT_SCHEMA,contract.CAPABILITY_PRODUCTION_QUEUE_SCHEMA,
                       contract.CAPABILITY_UNIT_ORDERS_SCHEMA):
            target,_=contract.checkpoint_catalogue(older,dict(schema=schema),self.obs)
            projected,_=contract.checkpoint_catalogue(self.current,target,self.obs)
            self.assertEqual(projected,target)
        self.assertEqual((self.current,self.raw),(current_before,old_before))

    def test_client_public_and_opt_in_admin_remain_separate_through_actions(self):
        backend=CombatBackend();backend.city_fixture=True
        client=SessionClient(backend,allow_administrative=True);view=client.reset()
        public_info=client.information('combat');admin=client.information('combat',channel='administrative')
        self.assertEqual(public_info['data']['unit_attacks']['cities'][0]['defense_strength'],23)
        self.assertEqual(admin['data']['cities'][0]['defense_strength'],22.5)
        self.assertFalse(admin['data']['actor_channel'])
        for key in ('episode_id','game_generation','sequence','player_id','turn','native_decision_id'):
            self.assertEqual(public_info[key],admin[key])
        self.assertNotIn('source_sha256',view['decisions']['unit_attacks'])
        selected=next(r for r in view['decisions']['candidates'] if r['action']['kind']=='unit_attack')
        after=client.act(0,view['decisions']['decision_id'],selected['candidate_id'])
        self.assertEqual(after['applied_action'],selected['action'])
        self.assertEqual(client.information('combat',channel='administrative')['sequence'],after['sequence'])
        client.close()
        backend=CombatBackend();backend.city_fixture=True;client=SessionClient(backend);client.reset()
        with self.assertRaises(PermissionError):client.information('combat',channel='administrative')
        self.assertEqual(client.information('combat')['channel'],'public');client.close()

    def test_checkpoint_gap_audit_is_explicit_and_does_not_weaken_live_validation(self):
        added='native_legal_targets_without_visible_witness'
        for old in (self.current,self.raw):
            saved=deepcopy(old);saved['families']['unit_attack']['unqualified'].remove(added);seal(saved)
            retained=deepcopy(saved)
            with self.assertRaisesRegex(ValueError,'unqualified routes'):self.f.validate(saved)
            kw=({} if old['schema']==self.current['schema'] else
                dict(combat_evidence=self.e,combat_source_sha256=attacks.PUBLIC_PRECISION_SHA256))
            compared,transition=contract.checkpoint_catalogue(self.current,saved,self.obs,**kw)
            self.assertEqual(compared,saved);self.assertEqual(saved,retained)
            self.assertEqual(transition['added_unqualified_routes'],['unit_attack.'+added])
            mutated=deepcopy(self.current);mutated['unit_attacks']['units'][0]['moves']=0
            mutated_obs=deepcopy(self.obs);mutated_obs['units'][0]['moves']=0;seal(mutated)
            # The extra audit item must not conceal an actual state difference.
            if not kw:
                different,_=contract.checkpoint_catalogue(mutated,saved,mutated_obs)
                self.assertNotEqual(different,saved)
        self.f.validate(self.current)

    def test_waiting_null_remains_unqualified_and_migrates_without_fake_raw(self):
        raw=self.f.value(waiting=True);current=public(raw,self.obs);self.f.validate(current)
        self.assertIsNone(current['unit_attacks'])
        compared,transition=contract.checkpoint_catalogue(current,raw,self.obs)
        self.assertEqual(compared,raw);self.assertFalse(transition['legacy_raw_values_compared_from_administrative_readback'])
        backend=CombatBackend(waiting=True);backend.city_fixture=True
        client=SessionClient(backend,allow_administrative=True);view=client.reset()
        with self.assertRaises(InformationUnavailable):client.information('combat')
        row=next(r for r in view['decisions']['candidates'] if r['action']=={'kind':'force_end_turn'})
        self.assertTrue(contract.offered_forced_turn(view['decisions'],row['action']));client.close()


if __name__=='__main__':unittest.main()
