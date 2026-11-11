"""Source/budget selection and retained receipt replay only; no native execution."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import accept_session as accept
import qualify_xp1_configuration as q
import review_xp1_session as review
import review_placement_inventory as inventory
import test_xp2_session_review as sessions
import test_xp1_placement_inventory_review as inv_fixtures
from civ6_host.runtime import xp1_action_job_ledger as jobs
from civ6_host.runtime import xp1_production_placement_profile as xp1_placement
from civ6_host.runtime import placement_inventory_profile as xp1_inventory
from civ6_host.runtime import xp2_action_transport_source as unit_source
from civ6_host.runtime.configuration_profiles import XP1_CORE_SHA256,XP2_CORE_SHA256
from civ6_host.runtime.paths import resource_root

HOST=Path(__file__).resolve().parents[1]
RETAINED=HOST/'work/xp1-production-placement/client-acceptance01/review.json'
RETAINED_SHA='03e29e1fd04a78e65c068b76b70facd4e57606fa345666577ee0a05c7837baa0'


class XP2PlacementReview(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from civ6_host.runtime import xp2_production_placement_source,xp2_placement_inventory_source
        cls.placement=xp2_production_placement_source;cls.inventory=xp2_placement_inventory_source
        sessions.ExpansionSessionReviewTests.setUpClass();context=sessions.ExpansionSessionReviewTests
        cls.loaded=context.loaded;cls.report=context.report;cls.closure=context.closure
        raw=RETAINED.read_bytes()
        if hashlib.sha256(raw).hexdigest()!=RETAINED_SHA:raise AssertionError('Original placement review changed')
        retained=json.loads(raw);cls.examples=[]
        for row in retained['runs'][0]['ledger']['commands']:
            if row['action']['kind']=='production':continue
            raw=Path(row['receipt']['path']).read_bytes()
            if hashlib.sha256(raw).hexdigest()!=row['receipt']['sha256']:raise AssertionError('Original placement receipt changed')
            interval=q.saved_load_events(Path(retained['runs'][0]['run'])/'events.jsonl',allow_turn_updates=True,
                allow_placements=True,require_interval='unit_commands',command_sequence=row['protocol_sequence'])[1]['unit_commands_job_interval']
            cls.examples.append((json.loads(raw),interval,row['ledger']['phase_receipt']))

    def fixture(self,resume):
        result,interval,_=copy.deepcopy(self.examples[int(resume)])
        result.update(jobs_before=copy.deepcopy(self.loaded),jobs_after=copy.deepcopy(self.loaded),
            unit_source=dict(source_sha256=unit_source.SOURCE[1],core_sha256=XP2_CORE_SHA256,callbacks=dict(unit_source.CALLBACKS)))
        interval['jobs']=[]
        for event in interval['commands']:
            if event['stage']=='official_explicit_placement_progress':event['source_proof_sha256']=self.placement.SOURCE[1]
        previous={k:result[k] for k in ('episode_id','game_generation')}
        previous.update(sequence=result['sequence']-1,publication_count=result['publication_count']-1,observation=result['observation_before'])
        return result,interval,previous

    def reconcile(self,result,interval,previous):
        prior=dict(ledger_provenance_authenticated=True,stdout_sha256=interval['stdout_sha256'],
                   last_line=interval['begin']['line']-1,final_jobs=result['jobs_before'])
        return q.saved_load_reconcile_later(self.report,self.closure['pins'],{},result,
            {'unit_commands_job_interval':interval},prior,phase='unit_commands',lifetime_seconds=420,
            previous_transition=previous,core_sha256=XP2_CORE_SHA256,session_supervision=True)

    def test_retained_xp1_place_resume_unchanged_and_xp2_selects_actual_job_source(self):
        for resume,(original,interval,expected) in enumerate(self.examples):
            self.assertEqual(q.saved_load_validate_placement(original,interval,original['jobs_before']),expected)
            result,events,previous=self.fixture(resume)
            with patch.object(jobs,'reconcile_action_jobs',wraps=jobs.reconcile_action_jobs) as call:
                actual=self.reconcile(result,events,previous)
                self.assertEqual(call.call_args.kwargs['victory_execute_rva'],0x536b00)
                self.assertEqual(actual['phase_receipt']['source_proof_sha256'],self.placement.SOURCE[1])
                self.assertFalse(actual['phase_receipt']['network_ack_inferred'])

    def test_xp2_resume_rejects_xp1_progress_source_job_and_missing_reads(self):
        for change in ('progress_source','job','unit','read'):
            result,interval,previous=self.fixture(True)
            if change=='progress_source':interval['commands'][0]['source_proof_sha256']=xp1_placement.SOURCE[1]
            elif change=='job':
                for name in ('jobs_before','jobs_after'):result[name]['core_identity']['execute_rva']=0x465110
            elif change=='unit':result['unit_source']['core_sha256']=XP1_CORE_SHA256
            else:interval['commands'].pop(0)
            with self.subTest(change=change),self.assertRaises(ValueError):self.reconcile(result,interval,previous)

    def test_placement_source_pin_and_extended_budgets_are_explicit_xp2_preparation_only(self):
        closure=copy.deepcopy(self.closure);path=str((resource_root()/self.placement.SOURCE[0]).resolve())
        closure['pins'][path]=self.placement.SOURCE[1]
        self.assertTrue(review.review_session_identity(closure,placement=True)['xp2'])
        closure['pins'][path]=xp1_placement.SOURCE[1]
        with self.assertRaisesRegex(ValueError,'closure pin'):review.review_session_identity(closure,placement=True)
        for seconds,total in ((600,840),(900,1200)):
            prep=dict(max_turns=12,total_group_seconds=total)
            if total==1200:prep['reset_reserve_seconds']=180
            closure.update(input_profile='xp2-lan',lifetime_seconds=seconds,checkpoint_on_close=False,network_checkpoint=None)
            report=dict(self.report,timeout_seconds=seconds)
            with self.subTest(seconds=seconds):
                self.assertEqual(review.review_lifetime_seconds(closure,report,placement_preparation=prep),seconds)
                q.saved_load_validate_supervision(report,self.closure['pins'],lifetime_seconds=seconds,session=True,placement_preparation=True)
                # Ordinary XP2 sessions already admit these exact budgets;
                # the extra preparation selection still has its own guards.
                self.assertEqual(review.review_lifetime_seconds(closure,report),seconds)
                with self.assertRaises(ValueError):q.saved_load_validate_supervision(report,self.closure['pins'],lifetime_seconds=seconds,session=True)
                closure['input_profile']='xp1-lan'
                with self.assertRaises(ValueError):review.review_lifetime_seconds(closure,report,placement_preparation=prep)
                with self.assertRaisesRegex(ValueError,'selected XP2'):
                    q.saved_load_reconcile_jobs(report,self.closure['pins'],{}, {},lifetime_seconds=seconds,
                        core_sha256=XP1_CORE_SHA256,session_supervision=True,placement_preparation=True)
        closure['input_profile']='xp2-lan'
        for change in ({'total_group_seconds':840},{'reset_reserve_seconds':179},{'total_group_seconds':1201}):
            with self.subTest(change=change),self.assertRaises(ValueError):
                review.review_lifetime_seconds(closure,report,placement_preparation=dict(prep,**change))
        with self.assertRaises(ValueError):
            q.saved_load_validate_supervision(dict(report,timeout_seconds=901),self.closure['pins'],
                lifetime_seconds=901,session=True,placement_preparation=True)

    def test_xp2_v8_inventory_joins_exact_source_and_public_copy(self):
        path,sha=inventory._source_reference(XP2_CORE_SHA256)
        view=inv_fixtures.view('explicit-inventory-fixture',0,placed=True)
        event=inv_fixtures.event(view);event['source_proof_sha256']=sha
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);public=root/'public-0000.json';public.write_text(json.dumps(view))
            (root/'supervisor.json').write_text(json.dumps(dict(stdout_native_records=[])))
            def check(record,source_sha=sha,family='xp2-lan'):
                (root/'closure.json').write_text(json.dumps(dict(input_profile=family,pins={path:source_sha},stdout_limit_bytes=67108864)))
                (root/'events.jsonl').write_text(json.dumps(record)+'\n')
                return inventory.validate_inventory_readback(root,{0:(public,view)},core_sha256=XP2_CORE_SHA256)
            actual=check(event);self.assertEqual(actual['source_proof_sha256'],self.inventory.SOURCE[1])
            self.assertFalse(actual['host_tracking_used']);self.assertFalse(actual['native_tracking_empty_witness'])
            with self.assertRaises(ValueError):check(dict(event,source_proof_sha256=xp1_inventory.SOURCE[1]))
            with self.assertRaises(ValueError):check(event,source_sha=xp1_inventory.SOURCE[1])
            with self.assertRaises(ValueError):check(event,family='xp1-lan')
            altered=copy.deepcopy(event);altered['inventory']['rows']=[]
            with self.assertRaises(ValueError):check(altered)

    def test_captured_xp2_database_binds_astrology_to_actual_public_offer(self):
        run=resource_root()/'work/xp2-client-sessions/run-6274a7ff1fb74899a8e9bc17b8b26bf3'
        closure=json.loads((run/'closure.json').read_bytes());view=json.loads((run/'public-0000.json').read_bytes())
        identity=accept.placement_preparation_identity(closure)
        self.assertEqual(identity['action_hash'],2325542178)
        self.assertEqual(identity['target_type'],'DISTRICT_HOLY_SITE')
        actual=[r['action'] for r in view['decisions']['candidates'] if r['action']['kind']=='research'
                and r['action']['hash']==identity['action_hash']]
        self.assertEqual(actual,[dict(kind='research',index=4,hash=2325542178)])
        self.assertEqual(view['observation']['cities'],[])
        self.assertNotIn('placement_offers',view['decisions'])


if __name__=='__main__':unittest.main()
