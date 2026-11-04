"""Retained attack/reset replay through the real client; no engine or log edits."""
from contextlib import redirect_stdout
from copy import deepcopy
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

HOST=Path(__file__).resolve().parents[1];LAB=HOST.parent/'civ6-rl-lab'
os.environ.setdefault('CIV6_HOST_RESOURCE_ROOT',str(LAB))
sys.path[:0]=[str(HOST/'tools'),str(HOST/'src')]
from civ6_host import SessionClient,InformationUnavailable
from civ6_host.runtime.information_store import InformationStore
from civ6_host.runtime.stdout_transport_profiles import session_records
from civ6_host.runtime.xp1_unit_attack_profile import precision_reference
from civ6_host.runtime.configuration_profiles import XP2_CORE_SHA256
import accept_session
import review_xp1_session as review
import review_unit_attacks as attacks
import unit_attack_preparation as preparation

RUNS=tuple(LAB/'work/xp2-client-sessions'/('run-'+name) for name in
    ('b6b1a76d5d3f49a1b97631cfb0f063e5','fd62ca2f98e2486bb00f1feb13346901'))
ACCEPTANCE=RUNS[1]/'client-acceptance.json'
ARCHIVE=HOST/'work/xp2-combat-integration/attack-cycle/executed-sources.zip'


class ReplayCycle:
    """Only reads retained responses. Requests must exactly match the native log."""
    def __init__(self,root,data):
        self.root=root;self.data=data;self.index=-1;self.run=None;self.finished=True
        self.report=None;self.calls=[];self.aborts=[]
        self.store=InformationStore({'combat':precision_reference(XP2_CORE_SHA256)[1]})

    def response(self):
        for _,_,event in self.records:
            self.store.ingest(event)
            if event.get('stage')=='official_session_response':return deepcopy(event)
        raise AssertionError('No retained response for this exact request')

    def reset(self):
        if not self.finished:raise AssertionError('Reset crossed a live replay lifetime')
        self.index+=1
        if self.index>=len(self.data):raise AssertionError('No extra native replay lifetime')
        row=self.data[self.index];self.records=iter(row['records']);self.cursor=0
        self.run=self.root/('replay-'+str(self.index));self.run.mkdir()
        self.report=deepcopy(row['report']);self.finished=False
        self.store.clear();self.calls.append(('reset',self.index))
        result=self.response()
        if result['operation']!='reset':raise AssertionError('Retained reset operation differs')
        return result

    def request(self,request):
        commands=self.data[self.index]['commands']
        if self.cursor>=len(commands) or request!=commands[self.cursor]:
            raise AssertionError('Request differs from the actually captured native request')
        self.cursor+=1;result=self.response()
        self.calls.append((request['operation'],self.index))
        if result['operation']=='close':self.finished=True
        return result

    def abort(self,reason):self.aborts.append(reason)
    def read_administrative(self,group,response):
        if self.finished:raise AssertionError('Administrative read crossed close')
        self.calls.append(('cached_information',self.index,response['sequence']))
        return self.store.read(group,response)


class XP2AttackPostCloseReader(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data=[];cls.originals={}
        for run in RUNS:
            commands=[json.loads(line) for line in (run/'commands.jsonl').read_text().splitlines()
                      if line.strip() and line.strip()!='go']
            cls.data.append(dict(records=list(session_records(run)),commands=commands,
                                 report=json.loads((run/'supervisor.json').read_bytes())))
            for name in ('events.jsonl','commands.jsonl','supervisor.json','public-0000.json'):
                p=run/name;cls.originals[p]=hashlib.sha256(p.read_bytes()).hexdigest()
        cls.originals[ACCEPTANCE]=hashlib.sha256(ACCEPTANCE.read_bytes()).hexdigest()
        cls.acceptance=json.loads(ACCEPTANCE.read_bytes())

    @classmethod
    def tearDownClass(cls):
        for path,sha in cls.originals.items():
            if hashlib.sha256(path.read_bytes()).hexdigest()!=sha:
                raise AssertionError('Retained native evidence was modified: '+str(path))

    def test_corrected_actual_acceptance_flow_queries_three_boundaries_before_close(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);backend=ReplayCycle(root,self.data)
            config=HOST/'work/xp2-combat-integration/attack-cycle/client-config.json'
            calls=[];original=preparation.combat_information_snapshot
            def snapshot(client,view):
                self.assertIs(type(client),SessionClient)
                calls.append((backend.index,view['sequence'],backend.finished))
                return original(client,view)
            argv=['accept_session.py','--config',str(config),'--capability-cycle','--unit-attack-group']
            with patch('civ6_host.runtime.backend.NetworkBackend',return_value=backend),patch.object(sys,'argv',argv),\
                    patch.object(preparation,'combat_information_snapshot',side_effect=snapshot),redirect_stdout(io.StringIO()):
                self.assertEqual(accept_session.main(),0)
            result=json.loads((backend.run/'client-acceptance.json').read_bytes())
            self.assertEqual(result['status'],'native_capability_unit_attack_group_reset_verified')
            self.assertEqual(calls,[(0,0,False),(0,1,False),(1,0,False)])
            self.assertEqual(result['combat_information'][:2],self.acceptance['combat_information'])
            self.assertEqual([c for c in backend.calls if c[0] in ('reset','act','close')],
                             [('reset',0),('act',0),('close',0),('reset',1),('close',1)])
            self.assertEqual(len(result['combat_information']),3)

    def test_real_client_refuses_the_original_query_after_retained_close(self):
        with tempfile.TemporaryDirectory() as folder:
            backend=ReplayCycle(Path(folder),[self.data[1]])
            client=SessionClient(backend,allow_administrative=True);fresh=client.reset()
            self.assertEqual(preparation.combat_information_snapshot(client,fresh)['public']['sequence'],0)
            client.close(0);before=list(backend.calls)
            with self.assertRaisesRegex(InformationUnavailable,'active session first'):
                preparation.combat_information_snapshot(client,fresh)
            self.assertEqual(backend.calls,before)

    def test_exact_refusal_projection_preserves_original_and_rejects_other_input(self):
        before=ACCEPTANCE.read_bytes()
        projected,receipt=review.project_post_close_combat_query_refusal(ACCEPTANCE,ARCHIVE)
        self.assertEqual(ACCEPTANCE.read_bytes(),before)
        self.assertEqual(self.acceptance['status'],'refused')
        self.assertEqual(projected['status'],'native_capability_unit_attack_group_reset_verified')
        self.assertEqual(projected['combat_information'],self.acceptance['combat_information'])
        self.assertFalse(receipt['reset_combat_query_live_executed'])
        self.assertFalse(receipt['native_responses_modified']);self.assertFalse(receipt['supervisors_modified'])
        self.assertEqual({r['path'] for r in receipt['source_transitions']},
            {'tools/accept_session.py','tools/review_xp1_session.py','tools/review_unit_attacks.py'})
        with tempfile.TemporaryDirectory() as folder:
            other=Path(folder)/'acceptance.json';value=deepcopy(self.acceptance)
            value['error']="InformationUnavailable('another failure')";other.write_text(json.dumps(value))
            with self.assertRaisesRegex(ValueError,'exact retained acceptance'):
                review.project_post_close_combat_query_refusal(other,ARCHIVE)
        with self.assertRaisesRegex(ValueError,'did not complete'):
            review.review(ACCEPTANCE,ARCHIVE)  # explicit replay option remains mandatory

    def test_reconstructed_query_uses_exact_native_reset_and_sidecar_with_explicit_provenance(self):
        sidecar=next(event for _,_,event in self.data[1]['records']
            if event.get('stage')=='native_combat_administrative_readback' and event.get('sequence')==0)
        replay=attacks.replay_reset_combat_information(RUNS[1],sidecar)
        self.assertEqual(replay['classification'],'reconstructed_client_information_query_from_retained_native_reset')
        self.assertFalse(replay['live_query_executed']);self.assertFalse(replay['native_calls_during_replay'])
        self.assertFalse(replay['native_response_fabricated']);self.assertFalse(replay['original_files_modified'])
        self.assertEqual(replay['query']['administrative']['data'],sidecar)
        view=json.loads((RUNS[1]/'public-0000.json').read_bytes())
        normalized=dict(view,generation=view['game_generation'])
        attacks.validate_information_query(replay['query'],normalized,core_sha256=XP2_CORE_SHA256)
        changed=deepcopy(sidecar);changed['sequence']=99
        with self.assertRaisesRegex(ValueError,'unique retained native reset/sidecar0'):
            attacks.replay_reset_combat_information(RUNS[1],changed)
