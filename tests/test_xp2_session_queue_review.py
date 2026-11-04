"""Queue selector fixtures and retained XP1 interval replay; no native execution.

XP2 cases borrow typed queue payloads, then explicitly construct an XP2 owner
and empty job interval. They do not create or project a completed acceptance.
"""
import copy
import hashlib
import json
from pathlib import Path
import unittest
from unittest.mock import patch

import qualify_xp1_configuration as q
import review_xp1_session as review
import test_xp2_session_review as session
from civ6_host.runtime import xp1_action_job_ledger as jobs
from civ6_host.runtime import xp1_production_queue_profile as xp1_queue
from civ6_host.runtime import xp2_action_transport_source as unit_source
from civ6_host.runtime.configuration_profiles import XP1_CORE_SHA256,XP2_CORE_SHA256
from civ6_host.runtime.paths import resource_root

HOST=Path(__file__).resolve().parents[1]
RETAINED=HOST/'work/xp1-turn-integration/native-session16/native-review.json'
RETAINED_SHA='b8fd19ed998c8019ce21a661583ed4a0655d316828768116d36736cc4cb6dcda'


def read(path):return json.loads(Path(path).read_bytes())


class XP2QueueReviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from civ6_host.runtime import xp2_production_queue_source
        cls.queue_source=xp2_production_queue_source.SOURCE
        session.ExpansionSessionReviewTests.setUpClass()
        context=session.ExpansionSessionReviewTests
        cls.loaded=context.loaded;cls.report=context.report;cls.closure=context.closure
        raw=RETAINED.read_bytes()
        if hashlib.sha256(raw).hexdigest()!=RETAINED_SHA:raise AssertionError('Retained queue review changed')
        retained=json.loads(raw);cls.retained_run=Path(retained['runs'][0]['run']);cls.examples={}
        for command in retained['runs'][0]['ledger']['commands']:
            seq=command['protocol_sequence']
            if seq not in (2,10,11,12):continue
            raw=Path(command['receipt']['path']).read_bytes()
            if hashlib.sha256(raw).hexdigest()!=command['receipt']['sha256']:
                raise AssertionError('Retained queue receipt changed')
            interval=q.saved_load_events(cls.retained_run/'events.jsonl',allow_turn_updates=True,
                allow_production_queue=True,require_interval='unit_commands',command_sequence=seq)[1]['unit_commands_job_interval']
            cls.examples[seq]=(json.loads(raw),interval,command['ledger']['phase_receipt'])

    def fixture(self,seq=2):
        result,interval,_=copy.deepcopy(self.examples[seq])
        result.update(jobs_before=copy.deepcopy(self.loaded),jobs_after=copy.deepcopy(self.loaded),
            unit_source=dict(source_sha256=unit_source.SOURCE[1],core_sha256=XP2_CORE_SHA256,
                             callbacks=dict(unit_source.CALLBACKS)))
        receipt=result['effect']['receipt']
        receipt.update(source_proof_sha256=self.queue_source[1],public_source_proof_sha256=self.queue_source[1])
        interval['jobs']=[]
        self.sync_effect(result,interval)
        previous={k:copy.deepcopy(result[k]) for k in ('episode_id','game_generation')}
        previous.update(sequence=result['sequence']-1,publication_count=result['publication_count']-1,
                        observation=copy.deepcopy(result['observation_before']))
        return result,interval,previous

    @staticmethod
    def sync_effect(result,interval):
        interval['commands'][-1]=dict(stage='official_explicit_production_queue_effect',
                                     **copy.deepcopy(result['effect']['receipt']))

    def reconcile(self,result,interval,previous):
        prior=dict(ledger_provenance_authenticated=True,stdout_sha256=interval['stdout_sha256'],
                   last_line=interval['begin']['line']-1,final_jobs=result['jobs_before'])
        return q.saved_load_reconcile_later(self.report,self.closure['pins'],{},result,
            {'unit_commands_job_interval':interval},prior,phase='unit_commands',lifetime_seconds=420,
            previous_transition=previous,core_sha256=XP2_CORE_SHA256,session_supervision=True)

    def test_retained_xp1_append_swap_tail_remove_keep_exact_default_receipts(self):
        for seq,(result,interval,expected) in self.examples.items():
            with self.subTest(sequence=seq):
                actual=q.saved_load_validate_production_queue(result,interval,result['jobs_before'])
                self.assertEqual(actual,expected)
        self.assertEqual(hashlib.sha256(RETAINED.read_bytes()).hexdigest(),RETAINED_SHA)

    def test_xp2_offered_queue_actions_reach_shared_reconciliation_with_selected_job(self):
        for seq in self.examples:
            result,interval,previous=self.fixture(seq)
            review.validate_queue_public_transition(result,read(self.retained_run/f'public-{seq-1:04}.json'),
                                                     read(self.retained_run/f'public-{seq:04}.json'))
            with self.subTest(sequence=seq),patch.object(jobs,'reconcile_action_jobs',wraps=jobs.reconcile_action_jobs) as call:
                actual=self.reconcile(result,interval,previous)
                self.assertEqual(call.call_args.kwargs['victory_execute_rva'],0x536b00)
                phase=actual['phase_receipt']
                self.assertTrue(phase['jobs']['ledger_events_match_snapshot'])
                self.assertEqual(phase['source_proof_sha256'],self.queue_source[1])
                self.assertFalse(phase['network_ack_inferred'])
                self.assertEqual(actual['schema'],'civ6-host.xp2-unit_commands-job-ledger-authenticated.v1')

    def test_xp2_rejects_xp1_proofs_job_identity_unit_source_and_foreign_city(self):
        changes=('source_proof_sha256','public_source_proof_sha256','unit_source','core_sha',
                 'job_execute','job_source','city')
        for change in changes:
            result,interval,previous=self.fixture()
            if change.endswith('proof_sha256'):
                result['effect']['receipt'][change]=xp1_queue.SOURCE[1]
            elif change=='unit_source':result['unit_source']['core_sha256']=XP1_CORE_SHA256
            elif change=='city':result['effect']['receipt']['queue_after']['city_id']+=1
            else:
                key,value={'core_sha':('sha256',XP1_CORE_SHA256),'job_execute':('execute_rva',0x465110),
                           'job_source':('source_sha256',q.saved_load_review_profile(XP1_CORE_SHA256)['job']['source'][1])}[change]
                for name in ('jobs_before','jobs_after'):result[name]['core_identity'][key]=value
            self.sync_effect(result,interval)
            with self.subTest(change=change),self.assertRaises(ValueError):
                self.reconcile(result,interval,previous)

    def test_queue_group_requires_xp2_source_in_executed_closure(self):
        path=str((resource_root()/self.queue_source[0]).resolve())
        closure=copy.deepcopy(self.closure);closure['pins'][path]=self.queue_source[1]
        self.assertTrue(review.review_session_identity(closure,production_queue=True)['xp2'])
        for wrong in (None,xp1_queue.SOURCE[1]):
            altered=copy.deepcopy(closure)
            if wrong is None:altered['pins'].pop(path)
            else:altered['pins'][path]=wrong
            with self.subTest(proof=wrong),self.assertRaisesRegex(ValueError,'closure pin'):
                review.review_session_identity(altered,production_queue=True)
        # Earlier XP2 groups do not retroactively require the later queue pin.
        self.assertTrue(review.review_session_identity(self.closure)['xp2'])

    def test_xp2_queue_admission_keeps_offers_fifo_and_later_families_closed(self):
        for change in ('offer','receive','reorder','duplicate','diplomacy','attack'):
            result,interval,previous=self.fixture()
            if change=='offer':result['effect']['receipt']['queue_before']['offers']=[]
            elif change=='receive':interval['commands'].pop(1)
            elif change=='reorder':interval['commands'].insert(0,interval['commands'].pop())
            elif change=='duplicate':interval['commands'].insert(1,copy.deepcopy(interval['commands'][0]))
            else:result['action']['kind']='diplomacy_response' if change=='diplomacy' else 'unit_attack'
            if change=='offer':self.sync_effect(result,interval)
            with self.subTest(change=change),self.assertRaises(ValueError):
                self.reconcile(result,interval,previous)


if __name__=='__main__':unittest.main()
