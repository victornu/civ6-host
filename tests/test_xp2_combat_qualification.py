"""Pure qualification fixtures, including unchanged Native19 checkpoint metadata."""
from copy import deepcopy
import hashlib
import importlib
import json
import os
from pathlib import Path
import sys
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch

_LOCATION=Path(__file__).resolve().parents[1]
PRIVATE=_LOCATION.name=='qualification-candidate'
HOST=_LOCATION.parents[2] if PRIVATE else _LOCATION
HERE=_LOCATION if PRIVATE else HOST/'work/xp2-combat-public-preparation/qualification-candidate'
LAB=HOST.parent/'civ6-rl-lab'
PUBLIC=HERE.parent/'candidate'
sys.dont_write_bytecode=True
os.environ.setdefault('CIV6_HOST_RESOURCE_ROOT',str(LAB))
sys.path[:0]=([str(HERE/'tools')] if PRIVATE else [])+[str(HOST/'tools'),str(HOST/'src'),str(HOST/'tests')]
import civ6_host.contracts.network_turn as contract
import civ6_host.contracts.information as information
# Preserve module identity used by the portable client; only replace its staged
# definitions. Production integration copies these exact authored files.
if PRIVATE:
    for module,name in ((contract,'network_turn'),(information,'information')):
        source=HERE/f'src/civ6_host/contracts/{name}.py'
        exec(compile(source.read_text(),str(source),'exec'),module.__dict__)
import civ6_host.runtime as runtime
if PRIVATE:runtime.__path__[:0]=[str(HERE/'src/civ6_host/runtime')]
from civ6_host.runtime import xp2_unit_attack_source as xp2_source
from civ6_host.runtime import network_checkpoint as checkpoint
from civ6_host.runtime.configuration_profiles import XP1_CORE_SHA256 as XP1,XP2_CORE_SHA256 as XP2
from civ6_host.runtime.xp1_unit_attack_profile import precision_reference
from civ6_host.runtime.native.native_session_resume import semantic_decisions
from civ6_host.session_client import SessionClient
from civ6_host.runtime.information_store import InformationStore
from civ6_host.contracts.capability_unit_attacks import UNQUALIFIED_UNIT_ATTACKS
import test_capability_combat_precision as precision
import test_capability_unit_attacks as attack_fixtures
import test_unit_attack_integration as review_fixtures
import review_unit_attacks as attacks
import review_xp1_session as reviewer
import qualify_xp1_configuration as qualification
qualification.REPO=HOST
from unit_attack_preparation import select_offered_attack,combat_information_snapshot

NATIVE19=(('run-8076365c72ad4754b6308188e0d197f4','75298eb927dc8d639b3a7468454ed91036b51edde8cc1dc953f1914f23bf7e0c'),
          ('run-d2cb244e543c4ee4a6b610394ca3eb48','10327ade6b10d8565b9e3da3ebdcb4759c32171634da9acc50a63130099875f3'))

def metadata(index=0):
    name,sha=NATIVE19[index];path=LAB/'work/xp2-client-sessions'/name/'checkpoint/checkpoint.json'
    raw=path.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=sha:raise AssertionError('Retained Native19 metadata changed')
    return path,raw,json.loads(raw)

def future_catalogue(m):
    """Synthetic new combat fields; every historical field is actual metadata.

    These zero-offer fixtures prove comparison behavior, never native combat.
    """
    current=deepcopy(m['decisions']);o=m['observation']
    current['schema']=contract.CAPABILITY_COMBAT_READINESS_SCHEMA
    current['unit_attacks']=dict(player_id=o['player_id'],turn=o['turn'],width=o['width'],height=o['height'],
        units=[dict(unit_id=u['id'],unit_type=u['type'],x=u['x'],y=u['y'],damage=u['damage'],
                    moves=u['moves'],attacks_remaining=0) for u in o['units']],
        relationships=[],cities=[],offers=[])
    current['families']['unit_attack']=dict(status='queried_partial',candidate_ids=[],unqualified=list(UNQUALIFIED_UNIT_ATTACKS))
    current.pop('decision_id');current['decision_id']=contract.digest(current)
    return current

class XP2Backend(precision.CombatBackend):
    def __init__(self):
        super().__init__();self.store=InformationStore({'combat':xp2_source.SOURCE[1]});self.city_fixture=True
    def _reply(self,operation,sequence,player,requested=None):
        result=attack_fixtures.AttackBackend._reply(self,operation,sequence,player,requested)
        if result['decisions'] is not None:
            old=result['decisions']
            if old['unit_attacks'] is not None:old['unit_attacks']['cities'][0]['defense_strength']=22.5
            result['decisions']=precision.public(old,result['observation'])
            result['decisions']['schema']=contract.CAPABILITY_COMBAT_READINESS_SCHEMA
            from test_session_capabilities import seal
            seal(result['decisions'])
            if old['unit_attacks'] is not None:
                e=precision.event(result['observation'],result['decisions'],old['unit_attacks']['cities'])
                e['source_sha256']=xp2_source.SOURCE[1];self.store.ingest(e)
        self.store.ingest(result);return result

class TransitionTests(unittest.TestCase):
    def test_parent_and_child_native19_v8_fields_are_preserved_exactly(self):
        for index in range(2):
            path,raw,m=metadata(index);saved=deepcopy(m['decisions']);current=future_catalogue(m)
            original=deepcopy(current)
            projected,receipt=contract.checkpoint_catalogue(current,saved,m['observation'],core_sha256=XP2,
                combat_source_sha256=xp2_source.SOURCE[1],combat_readiness_source_sha256=xp2_source.SOURCE[1])
            self.assertEqual(projected,saved);self.assertEqual(current,original)
            self.assertEqual(receipt['added_public_fields'],['unit_attacks'])
            self.assertEqual(receipt['changed_action_families'],['unit_attack'])
            self.assertEqual(receipt['retained_unqualified_families'],['unit_attack'])
            self.assertEqual(receipt['readiness_source_sha256'],xp2_source.SOURCE[1])
            self.assertEqual(receipt['precision_source_sha256'],xp2_source.SOURCE[1])
            self.assertEqual(receipt['core_sha256'],XP2);self.assertTrue(receipt['historical_fields_unchanged'])
            self.assertEqual(path.read_bytes(),raw)

    def test_exact_engine_precision_readiness_and_historical_family_required(self):
        _,_,m=metadata();current=future_catalogue(m)
        good=dict(core_sha256=XP2,combat_source_sha256=xp2_source.SOURCE[1],combat_readiness_source_sha256=xp2_source.SOURCE[1])
        for key,value in (('core_sha256',XP1),('core_sha256','0'*64),('combat_source_sha256',None),
                          ('combat_source_sha256',precision.attacks.PUBLIC_PRECISION_SHA256),
                          ('combat_readiness_source_sha256',contract.COMBAT_READINESS_SOURCE_SHA256)):
            with self.subTest(key=key,value=value),self.assertRaises(ValueError):
                contract.checkpoint_catalogue(current,m['decisions'],m['observation'],**dict(good,**{key:value}))
        bad=deepcopy(m['decisions']);bad['families']['unit_attack']['reason']='another_reason'
        with self.assertRaises(ValueError):contract.checkpoint_catalogue(current,bad,m['observation'],**good)

    def test_actual_runtime_comparator_binds_live_core_and_keeps_native_flags(self):
        _,_,m=metadata();current=future_catalogue(m);events=[]
        owner=NS(inputs=NS(profile=NS(name=m['input_profile']),checkpoint=('retained','a'*64),official_bundle=m['source_official_bundle']),
            backend=NS(load_abi=NS(core_sha256=XP2)),emit=lambda stage,**row:events.append((stage,row)))
        with patch.object(checkpoint,'manifest',return_value=m):
            checkpoint.compare_decisions(owner,m['observation'],current)
            reloaded=lambda:[row for stage,row in events if stage=='official_lan_checkpoint_reloaded']
            self.assertEqual(len(reloaded()),1);event=reloaded()[0]
            self.assertFalse(event['public_decisions_equal']);self.assertTrue(event['saved_decision_fields_equal'])
            self.assertFalse(event['complete_state_compared']);self.assertFalse(event['strategic_training_ready'])
            for mode in ('live_engine','saved_engine','gold','queue','unit','family'):
                changed=deepcopy(current);obs=deepcopy(m['observation']);saved=deepcopy(m)
                if mode=='live_engine':owner.backend.load_abi.core_sha256=XP1
                elif mode=='saved_engine':saved['core_sha256']=XP1
                elif mode=='gold':obs['economy']['gold']+=1
                elif mode=='queue':changed['queued_orders']['units'][0]['plot_id']=1
                elif mode=='unit':changed['unit_orders']['units'][0]['ready']=not changed['unit_orders']['units'][0]['ready']
                else:changed['families']['other_human_actions']['reason']='hidden_change'
                changed.pop('decision_id');changed['decision_id']=contract.digest(changed)
                try:
                    with self.subTest(mode=mode),patch.object(checkpoint,'manifest',return_value=saved),self.assertRaises(ValueError):
                        checkpoint.compare_decisions(owner,obs,changed)
                finally:owner.backend.load_abi.core_sha256=XP2
            self.assertEqual(len(reloaded()),1)

class InformationTests(unittest.TestCase):
    def test_actual_client_public_admin_rounding_and_offer_selection(self):
        backend=XP2Backend();client=SessionClient(backend,allow_administrative=True);view=client.reset()
        query=combat_information_snapshot(client,view)
        self.assertEqual(query['public']['data']['unit_attacks']['cities'][0]['defense_strength'],23)
        self.assertEqual(query['administrative']['data']['cities'][0]['defense_strength'],22.5)
        self.assertEqual(query['administrative']['data']['source_sha256'],xp2_source.SOURCE[1])
        action=select_offered_attack(view);self.assertIn(action,view['decisions']['unit_attacks']['offers'])
        reviewed=dict(episode_id=view['episode_id'],generation=view['game_generation'],sequence=view['sequence'],
            observation=view['observation'],decisions=view['decisions'])
        attacks.validate_information_query(query,reviewed,core_sha256=XP2)
        for key,value in (('source_sha256',precision.attacks.PUBLIC_PRECISION_SHA256),('actor_channel',True),('sequence',1)):
            bad=deepcopy(query);bad['administrative']['data'][key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):attacks.validate_information_query(bad,reviewed,core_sha256=XP2)
        row=next(row for row in view['decisions']['candidates'] if row['action']==action)
        after=client.act(view['observation']['player_id'],view['decisions']['decision_id'],row['candidate_id'])
        self.assertEqual(combat_information_snapshot(client,after)['public']['sequence'],after['sequence'])
        client.close()
        client=SessionClient(XP2Backend());view=client.reset()
        with self.assertRaises(PermissionError):client.information('combat',channel='administrative')
        client.close()

    def test_readback_reviewer_selects_closure_engine_and_rejects_cross_source(self):
        import tempfile
        backend=XP2Backend();client=SessionClient(backend,allow_administrative=True);view=client.reset()
        event=combat_information_snapshot(client,view)['administrative']['data']
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);p=precision_reference(XP2)
            (root/'closure.json').write_text(json.dumps(dict(input_profile='xp2-lan',pins={str((LAB/p[0]).resolve()):p[1]})))
            with patch('civ6_host.runtime.stdout_transport_profiles.session_records',return_value=[(1,b'',event)]):
                self.assertEqual(attacks.combat_readbacks(root,{0:(root/'public.json',view)},core_sha256=XP2),{0:event})
                with self.assertRaises(ValueError):attacks.combat_readbacks(root,{0:(root/'public.json',view)},core_sha256=XP1)
        client.close()

    def test_only_unique_public_offers_can_be_selected(self):
        client=SessionClient(XP2Backend());view=client.reset();before=deepcopy(view)
        action=select_offered_attack(view);self.assertEqual(view,before)
        for mode in ('missing','duplicate','empty'):
            bad=deepcopy(view)
            if mode=='empty':bad['decisions']['unit_attacks']['offers']=[]
            else:
                row=next(row for row in bad['decisions']['candidates'] if row['action']==action)
                if mode=='missing':bad['decisions']['candidates'].remove(row)
                else:bad['decisions']['candidates'].append(row)
            with self.subTest(mode=mode),self.assertRaises((ValueError,RuntimeError)):select_offered_attack(bad)
        client.close()

class ReviewerTests(unittest.TestCase):
    def test_partial_xp2_save_receipt_remains_partial_and_source_archive_bound(self):
        import tempfile,zipfile
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);run=root/'run';run.mkdir();tool=root/'tools/unit_attack_preparation.py';tool.parent.mkdir()
            raw=(HERE/'tools/unit_attack_preparation.py').read_bytes();tool.write_bytes(raw);sha=hashlib.sha256(raw).hexdigest()
            (run/'closure.json').write_text(json.dumps(dict(input_profile='xp2-lan',pins={str(tool):sha})))
            reference={'path':'fixture-checkpoint','sha256':'a'*64}
            value=dict(status='partial_public_exploration_checkpoint_retained',training=False,public_selector=True,
                commands=[],runs=[dict(run=str(run),report={'fixture':True},checkpoint=reference,
                    reset_timings_seconds={},initial_native_remaining_seconds=800)],input_checkpoint=None,
                turns_advanced=0,poll_calls=0,selector_sha256=sha,combat_information=[],checkpoint=reference,seconds=100,
                stop_reason='no_action_or_turn_progress_in_this_lifetime')
            archive=root/'source.zip'
            with zipfile.ZipFile(archive,'w') as out:out.writestr('tools/unit_attack_preparation.py',raw)
            before=deepcopy(value)
            with patch.object(qualification,'REPO',root):
                projected,proof=reviewer.project_preparer_receipt(value,archive)
                self.assertEqual(projected['status'],'native_unit_attack_preparation_checkpoint_saved')
                self.assertEqual(proof['original_status'],value['status']);self.assertTrue(proof['projection_only'])
                self.assertNotIn('offered_attacks',projected);self.assertEqual(value,before)
                (run/'closure.json').write_text(json.dumps(dict(input_profile='xp1-lan',pins={str(tool):sha})))
                with self.assertRaises(ValueError):reviewer.project_preparer_receipt(value,archive)

    def test_qualified_900_second_xp2_ceiling_is_selected_not_applied_to_xp1(self):
        report=dict(exit_code=90,normal_destroy_called=True,reaped=True,job_assigned=True,
            error=None,timed_out=False,timeout_seconds=900,memory_limit_bytes=512*1024*1024,
            stdout_limit_bytes=64*1024*1024,source_unchanged={'source':True})
        qualification.saved_load_validate_supervision(report,{'source':'pin'},lifetime_seconds=900,
            session=True,core_sha256=XP2)
        with self.assertRaises(ValueError):qualification.saved_load_validate_supervision(report,{'source':'pin'},
            lifetime_seconds=900,session=True,core_sha256=XP1)
        self.assertEqual(reviewer.review_lifetime_seconds(dict(input_profile='xp2-lan',lifetime_seconds=900),report),900)
        with self.assertRaises(ValueError):reviewer.review_lifetime_seconds(dict(input_profile='xp1-lan',lifetime_seconds=900),report)

    def test_explicit_1800_second_continuation_preserves_other_supervision_guards(self):
        report=dict(exit_code=90,normal_destroy_called=True,reaped=True,job_assigned=True,
            error=None,timed_out=False,timeout_seconds=1800,memory_limit_bytes=512*1024*1024,
            stdout_limit_bytes=64*1024*1024,source_unchanged={'source':True})
        closure=dict(input_profile='xp2-lan',lifetime_seconds=1800)
        qualification.saved_load_validate_supervision(report,{'source':'pin'},lifetime_seconds=1800,
            session=True,core_sha256=XP2)
        self.assertEqual(reviewer.review_lifetime_seconds(closure,report),1800)
        for changed in (dict(report,timeout_seconds=900),dict(report,memory_limit_bytes=768*1024*1024),
                        dict(report,reaped=False),dict(report,source_unchanged={'source':False})):
            with self.subTest(changed=changed),self.assertRaises(ValueError):
                qualification.saved_load_validate_supervision(changed,{'source':'pin'},lifetime_seconds=1800,
                    session=True,core_sha256=XP2)
        for engine,placement in ((XP1,False),(XP2,True)):
            with self.subTest(engine=engine,placement=placement),self.assertRaises(ValueError):
                qualification.saved_load_validate_supervision(report,{'source':'pin'},lifetime_seconds=1800,
                    session=True,core_sha256=engine,placement_preparation=placement)
        with self.assertRaises(ValueError):
            reviewer.review_lifetime_seconds(closure,dict(report,timeout_seconds=900))

    def test_native_attack_effect_transport_and_job_review_use_actual_xp2_sources(self):
        result,interval,jobs=review_fixtures.fixture()
        result['effect']['receipt']['source_proof_sha256']=xp2_source.SOURCE[1]
        interval['commands'][-1]['source_proof_sha256']=xp2_source.SOURCE[1]
        from civ6_host.runtime.xp2_world_input_source import SOURCE as queued
        interval['commands'][-2]['queued_source_sha256']=queued[1]
        original=deepcopy(result)
        with patch('civ6_host.runtime.xp1_action_job_ledger.reconcile_action_jobs',return_value={'fixture':'jobs'}) as ledger:
            proof=attacks.validate_native_attack(result,interval,jobs,transport=qualification.saved_load_validate_turn_transport,core_sha256=XP2)
            self.assertEqual(proof['source_proof_sha256'],xp2_source.SOURCE[1])
            self.assertEqual(ledger.call_args.kwargs['victory_execute_rva'],0x536b00)
            with self.assertRaises(ValueError):attacks.validate_native_attack(result,interval,jobs,transport=qualification.saved_load_validate_turn_transport,core_sha256=XP1)
        self.assertEqual(result,original)

    def test_native19_closure_cannot_be_relabelled_as_executing_new_combat_sources(self):
        path,_,_=metadata();closure=json.loads((path.parent.parent/'closure.json').read_bytes())
        with self.assertRaisesRegex(ValueError,'source/input'):
            reviewer.review_session_identity(closure,combat=True)

    def test_all_modified_files_parse_and_latest_save_review_preimage_is_exact(self):
        import ast
        pins=json.loads((HERE/'baseline-pins.json').read_bytes())
        self.assertEqual(pins['tools/review_xp1_session.py'],'c96ca9d267ed88de1a9c6768435a69a995bb992a8a015b46ec54b2cff22e6653')
        for name in pins:ast.parse((HERE/name).read_text(encoding='utf-8'))
        source=(HERE/'tools/qualify_xp1_configuration.py').read_text(encoding='utf-8')
        self.assertIn('transport=saved_load_validate_turn_transport,core_sha256=core_sha256)',source)

class ContinuousPreparationTests(unittest.TestCase):
    def exercise(self,*,offer_after_two_turns):
        import tempfile,time
        from test_unit_attack_preparation_flow import view
        from unit_attack_preparation import prepare
        case=self;calls=[]
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            class Backend:
                def __init__(self,**config):
                    self.run=root/'run';self.run.mkdir();self.checkpoint=None;self.report={'fixture':True}
                    self._session=NS(lifetime_seconds=900,started=time.perf_counter()-1,reset_timings_seconds={})
            class Client:
                def __init__(self,backend):self.backend=backend;self.index=0;self.command_result=None
                def reply(self):
                    turn=11+self.index//2 if offer_after_two_turns else 11
                    ready=not offer_after_two_turns or self.index%2==0
                    result=view(self.index,turn,active=ready,complete=ready)
                    if offer_after_two_turns and self.index==4:
                        action=dict(kind='unit_attack',unit_id=17,operation='MOVE_TO',input_route='enemy_flag',plot_id=1,x=1,y=0)
                        result['decisions']['unit_attacks']['offers']=[action]
                        result['decisions']['candidates'].append(dict(candidate_id='attack',action=action))
                    return result
                def reset(self):calls.append('reset');return self.reply()
                def act(self,*args):
                    calls.append('act');self.index+=1;self.command_result=dict(status='completed',requested_action=dict(kind='force_end_turn'))
                    return self.reply()
                def poll(self,*args):calls.append('poll');self.index+=1;return self.reply()
                def close(self,*args):
                    calls.append('close');self.backend.checkpoint={'fixture':True,'turn':self.reply()['observation']['turn']}
                    return dict(sequence=self.index+1,observation=None,decisions=None)
                def abort(self):calls.append('abort')
            with patch('civ6_host.SessionClient',Client),patch('civ6_host.runtime.backend.NetworkBackend',Backend):
                result=prepare(dict(input_profile='xp2-lan'),root/'output',total_seconds=900,max_lifetimes=1)
            case.assertEqual(calls.count('reset'),1);case.assertEqual(calls.count('close'),1)
            case.assertEqual(len(result['runs']),1)
            return result,calls

    def test_two_turns_one_load_exact_counter_and_stop_on_public_offer(self):
        result,calls=self.exercise(offer_after_two_turns=True)
        self.assertEqual(result['status'],'native_unit_attack_checkpoint_prepared_pending_review')
        self.assertEqual(result['turns_advanced'],2)
        self.assertEqual(calls,['reset','act','poll','act','poll','close','abort'])
        self.assertEqual(result['checkpoint']['turn'],13)

    def test_48_decision_cap_saves_ready_partial_without_an_extra_load(self):
        result,calls=self.exercise(offer_after_two_turns=False)
        self.assertEqual(result['status'],'partial_public_exploration_checkpoint_retained')
        self.assertEqual(calls.count('act'),48);self.assertEqual(calls.count('poll'),0)
        self.assertEqual(result['turns_advanced'],0)

def load_tests(loader,tests,pattern):
    # One ordinary unittest group, reusing retained pure fixtures. No new runner.
    if not PRIVATE:return tests
    suite=unittest.TestSuite([tests])
    for name in ('test_unit_attack_preparation_flow','test_capability_combat_readiness'):
        module=importlib.import_module(name)
        exec(compile((HERE/'tests'/f'{name}.py').read_text(encoding='utf-8'),str(HOST/'tests'/f'{name}.py'),'exec'),module.__dict__)
    for name in ('test_unit_attack_integration','test_unit_attack_preparation_flow','test_capability_combat_precision',
                 'test_capability_combat_readiness','test_network_checkpoint',
                 'test_xp1_placement_checkpoint.PlacementCheckpointTests.test_real_comparison_accepts_explicit_v7_upgrade_without_rewriting_v5_v6',
                 'test_xp1_preparer_review'):
        suite.addTests(loader.loadTestsFromName(name))
    return suite

if __name__=='__main__':unittest.main(verbosity=2)
