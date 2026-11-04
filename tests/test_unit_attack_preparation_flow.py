"""Preparation orchestration with synthetic public replies, without an engine."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

HOST=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(HOST/'tools'))
from unit_attack_preparation import prepare


def view(sequence,turn,*,active,complete,can_unready=False):
    ready=active and complete and not can_unready
    force={'kind':'force_end_turn'}
    return dict(sequence=sequence,observation=dict(player_id=0,turn=turn,width=4,height=4,
        cities=[],plots=[]),decisions=dict(decision_id='fixture-'+str(sequence),
        turn_controls=dict(active=active,active_complete=complete,can_unready=can_unready),
        unit_attacks=dict(units=[],offers=[]) if ready else None,
        world_input=dict(selected_unit_id=None) if ready else None,
        candidates=[dict(candidate_id='force-'+str(sequence),action=force)] if ready else []))


class PreparationFlowTests(unittest.TestCase):
    def test_turn_number_advance_waits_for_native_ready_before_save(self):
        replies=[view(0,11,active=True,complete=True),
            view(1,11,active=False,complete=False,can_unready=True),
            view(2,12,active=False,complete=False),
            view(3,12,active=True,complete=False),
            view(4,12,active=True,complete=True)]
        original=deepcopy(replies);calls=[];created=[]
        case=self
        with tempfile.TemporaryDirectory(prefix='civ6-host-attack-flow-') as directory:
            root=Path(directory)

            class Backend:
                def __init__(self,**config):
                    case.assertTrue(config['checkpoint_on_close'])
                    self.config=deepcopy(config);self.run=root/'synthetic-run'
                    self.run.mkdir()
                    self._session=SimpleNamespace(started=time.perf_counter()-20,
                        lifetime_seconds=300,reset_timings_seconds={'fixture_parent':0.25})
                    self.report={'fixture_only':True};self.checkpoint=None
                    created.append(self)

            class Client:
                def __init__(self,backend):
                    self.backend=backend;self.index=0;self.command_result=None
                def reset(self):
                    calls.append(('reset',));return deepcopy(replies[0])
                def previous_reply_is_recorded(self):
                    path=self.backend.run/('public-%04d.json'%self.index)
                    case.assertTrue(path.is_file(),'Each public reply must be saved before the next input')
                    case.assertEqual(json.loads(path.read_text()),replies[self.index])
                def act(self,pid,decision_id,candidate_id):
                    self.previous_reply_is_recorded()
                    case.assertEqual((self.index,pid,decision_id,candidate_id),(0,0,'fixture-0','force-0'))
                    calls.append(('force_end_turn',11));self.index=1
                    self.command_result=dict(status='completed',reason=None,
                        requested_action={'kind':'force_end_turn'})
                    return deepcopy(replies[self.index])
                def poll(self,pid):
                    self.previous_reply_is_recorded();case.assertEqual(pid,0)
                    case.assertIn(self.index,(1,2,3))
                    self.index+=1;calls.append(('poll',replies[self.index]['observation']['turn']))
                    if self.index==4:self.backend._session.started=time.perf_counter()-240
                    return deepcopy(replies[self.index])
                def close(self,pid):
                    self.previous_reply_is_recorded()
                    case.assertEqual((self.index,pid),(4,0),
                        'T12 alone is insufficient: inactive and active-incomplete replies cannot be saved')
                    controls=replies[self.index]['decisions']['turn_controls']
                    case.assertTrue(controls['active'] and controls['active_complete'])
                    case.assertFalse(controls['can_unready'])
                    calls.append(('close_ready',12))
                    self.backend.checkpoint={'fixture_only':True,'turn':12}
                    return dict(sequence=5,observation=None,decisions=None)
                def abort(self):calls.append(('abort_cleanup',))

            config={'fixture_input':'retained-checkpoint','checkpoint':{'fixture_only':True,'turn':11}}
            before=deepcopy(config)
            with patch('civ6_host.SessionClient',Client),patch('civ6_host.runtime.backend.NetworkBackend',Backend):
                result=prepare(config,root/'output',total_seconds=300,max_lifetimes=1)
            self.assertEqual(result['status'],'partial_public_exploration_checkpoint_retained',result)
            self.assertEqual((result['poll_calls'],result['turns_advanced']),(3,1))
            self.assertEqual(calls,[('reset',),('force_end_turn',11),('poll',12),('poll',12),
                                   ('poll',12),('close_ready',12),('abort_cleanup',)])
            self.assertEqual(len(created),1);self.assertEqual(len(result['commands']),1)
            self.assertEqual(result['commands'][0]['requested_action'],{'kind':'force_end_turn'})
            self.assertEqual(result['checkpoint'],{'fixture_only':True,'turn':12})
            self.assertEqual(result['runs'][0]['reset_timings_seconds'],{'fixture_parent':0.25})
            self.assertGreater(result['runs'][0]['initial_native_remaining_seconds'],270)
            self.assertEqual(json.loads((root/'output/result.json').read_text()),result)
            self.assertEqual(sorted(p.name for p in created[0].run.glob('public-*.json')),
                             ['public-%04d.json'%n for n in range(6)])
            self.assertEqual((config,replies),(before,original))


if __name__=='__main__':unittest.main()
