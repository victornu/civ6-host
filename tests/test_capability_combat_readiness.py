"""Portable v11 consumers and strict, comparison-only checkpoint transitions."""
from contextlib import ExitStack
from copy import deepcopy
import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from civ6_host.contracts import network_turn as contract, information
from civ6_host.contracts import capability_unit_attacks as attacks
from civ6_host.runtime import network_checkpoint as checkpoint
from civ6_host.runtime import xp1_unit_attack_profile as profile
from civ6_host.session_client import SessionClient, InformationUnavailable
import test_capability_combat_precision as precision
from test_session_capabilities import seal


def omit_attacks(value, ids):
    """Build an older fixture, retaining all public state and historical order."""
    value['candidates']=[row for row in value['candidates'] if row['candidate_id'] not in ids]
    family=value['families']['unit_attack']
    family['candidate_ids']=[key for key in family['candidate_ids'] if key not in ids]
    value['unit_attacks']['offers']=[action for action in value['unit_attacks']['offers']
                                   if contract.digest(action) not in ids]
    return seal(value)


class ReadinessBackend(precision.CombatBackend):
    def _reply(self,operation,sequence,player,requested=None):
        result=super()._reply(operation,sequence,player,requested)
        if result['decisions'] is not None:
            raw=self.store.read('combat',result)
            result['decisions']['schema']=contract.CAPABILITY_COMBAT_READINESS_SCHEMA
            seal(result['decisions'])
            if raw is not None:self.store.ingest(raw)
            self.store.ingest(result)
        return result


class CombatReadinessTests(unittest.TestCase):
    def setUp(self):
        self.fixture=precision.CombatPrecisionTests();self.fixture.setUp()
        self.obs=self.fixture.obs
        self.current=deepcopy(self.fixture.current)
        self.current['schema']=contract.CAPABILITY_COMBAT_READINESS_SCHEMA;seal(self.current)
        self.added=[row for row in self.current['candidates'] if row['action']['kind']=='unit_attack'][:2]
        self.ids={row['candidate_id'] for row in self.added}
        self.v10=omit_attacks(deepcopy(self.fixture.current),self.ids)
        self.v9=omit_attacks(deepcopy(self.fixture.raw),self.ids)
        self.kw=dict(combat_readiness_source_sha256=contract.COMBAT_READINESS_SOURCE_SHA256,
                     combat_source_sha256=attacks.PUBLIC_PRECISION_SHA256,
                     combat_evidence=self.fixture.e)

    def compare(self,current,saved,observation=None):
        return contract.checkpoint_catalogue(current,saved,self.obs if observation is None else observation,**self.kw)

    def test_v11_public_precision_and_native_offers_preserve_all_v10_fields(self):
        self.fixture.f.validate(self.current)
        self.assertEqual(set(self.current),set(self.fixture.current))
        self.assertEqual(self.current['unit_attacks'],self.fixture.current['unit_attacks'])
        self.assertTrue(all(row['ready'] is False for row in self.current['unit_orders']['units']))
        info=information.project('combat',self.obs,self.current)
        self.assertEqual(info['unit_attacks']['offers'],self.current['unit_attacks']['offers'])
        self.assertIs(type(info['unit_attacks']['cities'][0]['defense_strength']),int)
        bad=deepcopy(self.current);bad['unit_attacks']['cities'][0]['defense_strength']=22.5;seal(bad)
        with self.assertRaisesRegex(ValueError,'displayed integer'):self.fixture.f.validate(bad)

    def test_v11_portable_client_and_information_need_neither_runtime_nor_resources(self):
        script='''import sys,importlib.abc,json
from types import SimpleNamespace
class Refuse(importlib.abc.MetaPathFinder):
 def find_spec(self,fullname,path=None,target=None):
  if fullname.startswith(('civ6_host.runtime','torch')):raise AssertionError(fullname)
sys.meta_path.insert(0,Refuse())
from civ6_host.session_client import SessionClient
from civ6_host.contracts import network_turn,information
current,obs=json.load(sys.stdin)
assert current['schema']==network_turn.CAPABILITY_COMBAT_READINESS_SCHEMA
identity=SimpleNamespace(episode_id=current['episode_id'],game_generation=current['game_generation'])
network_turn.validate_capability_catalogue(current,identity,current['sequence'],obs['turn'],player_id=obs['player_id'],observation=obs)
public=information.project('combat',obs,current)
assert public['unit_attacks']['offers']==current['unit_attacks']['offers']
assert type(public['unit_attacks']['cities'][0]['defense_strength']) is int
'''
        env=os.environ.copy();env.pop('CIV6_HOST_RESOURCE_ROOT',None)
        env['PYTHONPATH']=str(Path(__file__).resolve().parents[1]/'src')
        done=subprocess.run([sys.executable,'-c',script],input=json.dumps((self.current,self.obs)),
                            env=env,capture_output=True,text=True,timeout=10)
        self.assertEqual(done.returncode,0,done.stderr)

    def test_v10_v9_projection_removes_only_new_busy_attacks_without_mutation(self):
        for saved in (self.v10,self.v9):
            before=deepcopy((self.current,saved,self.fixture.e))
            projected,transition=self.compare(self.current,saved)
            self.assertEqual(projected,saved)
            self.assertEqual((self.current,saved,self.fixture.e),before)
            self.assertEqual(transition['added_unit_attack_candidates'],self.added)
            self.assertEqual(transition['readiness_source_sha256'],profile.READINESS_SOURCE[1])
            self.assertTrue(transition['historical_fields_unchanged'])
            for field in ('unit_orders','queued_orders','choice_state','placement_inventory'):
                self.assertEqual(projected[field],self.current[field])
            if saved is self.v9:
                self.assertTrue(transition['legacy_raw_values_compared_from_administrative_readback'])
                self.assertEqual(transition['precision_source_sha256'],attacks.PUBLIC_PRECISION_SHA256)
                self.assertEqual(projected['unit_attacks']['cities'][0]['defense_strength'],22.5)

    def test_readiness_proof_pin_is_mandatory_and_older_family_transitions_survive(self):
        for saved in (self.v10,self.v9):
            for pin in (None,'0'*64,attacks.PUBLIC_PRECISION_SHA256,True):
                with self.subTest(pin=pin,schema=saved['schema']),self.assertRaisesRegex(ValueError,'source pin'):
                    contract.checkpoint_catalogue(self.current,saved,self.obs,
                        **dict(self.kw,combat_readiness_source_sha256=pin))
        older=self.fixture.f.fixture.value()
        for schema in (contract.CAPABILITY_PLACEMENT_INVENTORY_SCHEMA,contract.CAPABILITY_PLACEMENT_SCHEMA,
                       contract.CAPABILITY_PRODUCTION_QUEUE_SCHEMA,contract.CAPABILITY_UNIT_ORDERS_SCHEMA):
            saved=older if older['schema']==schema else contract.checkpoint_catalogue(older,dict(schema=schema),self.obs)[0]
            projected,transition=self.compare(self.current,saved)
            self.assertEqual(projected,saved)
            self.assertIn('unit_attack',transition['added_action_families'])
            self.assertEqual(transition['readiness_source_sha256'],profile.READINESS_SOURCE[1])

    def test_v10_and_waiting_v9_need_no_raw_evidence_or_inverted_rounding(self):
        projected,_=contract.checkpoint_catalogue(self.current,self.v10,self.obs,
            combat_readiness_source_sha256=contract.COMBAT_READINESS_SOURCE_SHA256)
        self.assertEqual(projected,self.v10)
        raw=self.fixture.f.value(waiting=True)
        current=precision.public(raw,self.obs);current['schema']=contract.CAPABILITY_COMBAT_READINESS_SCHEMA;seal(current)
        projected,transition=contract.checkpoint_catalogue(current,raw,self.obs,
            combat_readiness_source_sha256=contract.COMBAT_READINESS_SOURCE_SHA256)
        self.assertEqual(projected,raw)
        self.assertIsNone(projected['unit_attacks'])
        self.assertEqual(transition['added_unit_attack_candidates'],[])
        self.assertFalse(transition['legacy_raw_values_compared_from_administrative_readback'])
        self.assertIsNone(transition['precision_source_sha256'])

    def test_projection_rejects_ready_units_missing_old_actions_and_nonattack_additions(self):
        current=deepcopy(self.current);saved=deepcopy(self.v10)
        for value in (current,saved):value['unit_orders']['units'][0]['ready']=True;seal(value)
        with self.assertRaisesRegex(ValueError,'outside not-ready'):self.compare(current,saved)
        for ready in (0,None):
            bad=deepcopy(self.current);bad['unit_orders']['units'][0]['ready']=ready;seal(bad)
            with self.subTest(ready=ready),self.assertRaises(ValueError):self.compare(bad,self.v10)
        historical=next(row for row in self.v10['candidates'] if row['action']['kind']=='unit_attack')
        bad=omit_attacks(deepcopy(self.current),{historical['candidate_id']})
        with self.assertRaisesRegex(ValueError,'lost a historical action'):self.compare(bad,self.v10)
        saved=deepcopy(self.v10)
        old=next(row for row in saved['candidates'] if row['action']['kind']=='unit_order')
        saved['candidates'].remove(old);saved['families']['unit_order']['candidate_ids'].remove(old['candidate_id'])
        saved['unit_orders']['offers']=[row for row in saved['unit_orders']['offers'] if row['action']!=old['action']];seal(saved)
        self.fixture.f.validate(saved)
        with self.assertRaisesRegex(ValueError,'outside not-ready'):self.compare(self.current,saved)

    def test_raw_sidecar_is_validated_against_original_v11_and_exact_identity(self):
        original=information.validate_administrative
        seen=[]
        def validate(group,event,response,**kwargs):
            self.assertIs(response['decisions'],self.current)
            self.assertEqual(response['decisions']['schema'],contract.CAPABILITY_COMBAT_READINESS_SCHEMA)
            seen.append(response['decisions']['decision_id'])
            return original(group,event,response,**kwargs)
        with patch.object(information,'validate_administrative',side_effect=validate):
            projected,_=self.compare(self.current,self.v9)
        self.assertEqual(seen,[self.current['decision_id']]);self.assertEqual(projected,self.v9)
        for key,value in (('episode_id','foreign'),('game_generation','foreign'),('sequence',1),
                          ('player_id',1),('turn',2),('source_sha256','0'*64),('actor_channel',True)):
            event=deepcopy(self.fixture.e);event[key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):
                contract.checkpoint_catalogue(self.current,self.v9,self.obs,**dict(self.kw,combat_evidence=event))
        for event in (None,dict(self.fixture.e,cities=[])):
            with self.assertRaises(ValueError):
                contract.checkpoint_catalogue(self.current,self.v9,self.obs,**dict(self.kw,combat_evidence=event))
        event=deepcopy(self.fixture.e);event['cities'][0]['defense_strength']=22+129/256
        projected,_=contract.checkpoint_catalogue(self.current,self.v9,self.obs,**dict(self.kw,combat_evidence=event))
        self.assertNotEqual(projected,self.v9) # Equal rounded display cannot hide different raw data.

    def test_gap_audit_metadata_remains_strict_for_both_historical_versions(self):
        gap='native_legal_targets_without_visible_witness'
        for saved in (self.v10,self.v9):
            old=deepcopy(saved);old['families']['unit_attack']['unqualified'].remove(gap);seal(old)
            retained=deepcopy(old);projected,transition=self.compare(self.current,old)
            self.assertEqual(projected,old);self.assertEqual(old,retained)
            self.assertEqual(transition['added_unqualified_routes'],['unit_attack.'+gap])
            bad=deepcopy(self.current);bad['families']['unit_attack']['unqualified'].remove(gap);seal(bad)
            with self.assertRaisesRegex(ValueError,'unqualified routes'):self.compare(bad,old)
            old['families']['unit_attack']['unqualified'].pop();seal(old)
            projected,_=self.compare(self.current,old)
            self.assertNotEqual(projected,old)

    def test_common_client_executes_busy_offer_and_separates_administrative_precision(self):
        backend=ReadinessBackend();backend.city_fixture=True
        client=SessionClient(backend,allow_administrative=True);view=client.reset()
        self.assertEqual(view['decisions']['schema'],contract.CAPABILITY_COMBAT_READINESS_SCHEMA)
        self.assertTrue(all(row['ready'] is False for row in view['decisions']['unit_orders']['units']))
        public=client.information('combat');admin=client.information('combat',channel='administrative')
        self.assertEqual(public['data']['unit_attacks']['cities'][0]['defense_strength'],23)
        self.assertEqual(admin['data']['cities'][0]['defense_strength'],22.5)
        row=next(row for row in view['decisions']['candidates'] if row['action']['kind']=='unit_attack')
        after=client.act(0,view['decisions']['decision_id'],row['candidate_id'])
        self.assertEqual(after['applied_action'],row['action'])
        self.assertEqual(client.information('combat',channel='administrative')['sequence'],after['sequence']);client.close()
        backend=ReadinessBackend(waiting=True);backend.city_fixture=True
        client=SessionClient(backend);view=client.reset()
        self.assertIsNone(view['decisions']['unit_attacks'])
        with self.assertRaises(InformationUnavailable):client.information('combat')
        self.assertTrue(contract.offered_forced_turn(view['decisions'],dict(kind='force_end_turn')));client.close()

    def test_checkpoint_caller_verifies_both_sources_then_compares_every_state_field(self):
        stages=[]
        owner=SimpleNamespace(inputs=SimpleNamespace(checkpoint=('checkpoint','a'*64),
            official_bundle=('capture','b'*64)),emit=lambda *args,**kwargs:stages.append(('emitted',kwargs)),
            combat_administrative_by_player={0:self.fixture.e})
        from civ6_host.runtime.configuration_profiles import XP1_CORE_SHA256
        from civ6_host.runtime.xp1_bundle_inputs import XP1_LAN_PROFILE
        owner.inputs.profile=XP1_LAN_PROFILE
        owner.backend=SimpleNamespace(load_abi=SimpleNamespace(core_sha256=XP1_CORE_SHA256))
        with ExitStack() as stack:
            stack.enter_context(patch.object(checkpoint,'manifest',return_value=dict(observation=self.obs,decisions=self.v10,core_sha256=XP1_CORE_SHA256)))
            source=stack.enter_context(patch.object(profile,'verify_source',side_effect=lambda:stages.append('source')))
            readiness=stack.enter_context(patch.object(profile,'verify_readiness_source',side_effect=lambda:stages.append('readiness')))
            checkpoint.compare_decisions(owner,self.obs,self.current)
            self.assertEqual(stages[:2],['source','readiness'])
            self.assertEqual(stages[2][1]['catalogue_transition']['readiness_source_sha256'],profile.READINESS_SOURCE[1])
            mutations=(lambda d,o:d['unit_orders']['units'][0].update(ready=True),
                lambda d,o:d['unit_orders']['units'][0].update(fortify_turns=0),
                lambda d,o:d['queued_orders']['units'][0].update(plot_id=1),
                lambda d,o:d['unit_attacks']['units'][0].update(attacks_remaining=0),
                lambda d,o:d['unit_attacks']['cities'][0].update(garrison_damage=3),
                lambda d,o:o['economy'].update(gold=o['economy']['gold']+1),
                lambda d,o:(d['unit_attacks']['units'][0].update(moves=0),o['units'][0].update(moves=0)))
            for mutate in mutations:
                current,obs=deepcopy(self.current),deepcopy(self.obs);mutate(current,obs);seal(current)
                with self.subTest(mutation=mutate),self.assertRaises(ValueError):
                    checkpoint.compare_decisions(owner,obs,current)
            with patch.object(profile,'READINESS_SOURCE',(profile.READINESS_SOURCE[0],'0'*64)):
                with self.assertRaisesRegex(ValueError,'source pin'):checkpoint.compare_decisions(owner,self.obs,self.current)
            readiness.reset_mock();source.side_effect=ValueError('source changed')
            with self.assertRaisesRegex(ValueError,'source changed'):checkpoint.compare_decisions(owner,self.obs,self.current)
            readiness.assert_not_called()


if __name__=='__main__':unittest.main()
