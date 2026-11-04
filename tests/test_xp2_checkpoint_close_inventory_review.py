"""Read-only Native19 close-receipt joins; no engine or retained-file writes."""
from copy import deepcopy
import json
from pathlib import Path
import unittest
from unittest.mock import patch

import review_placement_inventory as review
import review_xp1_session as session_review
from civ6_host.runtime.configuration_profiles import XP1_CORE_SHA256, XP2_CORE_SHA256
from civ6_host.runtime.stdout_transport_profiles import session_records

HOST=Path(__file__).resolve().parents[1]
LAB=HOST.parent/'civ6-rl-lab'
RUNS=tuple(LAB/'work/xp2-client-sessions'/('run-'+name) for name in (
    '8076365c72ad4754b6308188e0d197f4','d2cb244e543c4ee4a6b610394ca3eb48','a5ebc53592a142c6b1b6955965f5ed0b'))


def public_views(run):
    result={}
    for path in sorted(run.glob('public-*.json')):
        value=json.loads(path.read_bytes());result[value['sequence']]=(path,value)
    return result


class XP2ClosingInventoryReview(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture_run=RUNS[0];cls.public=public_views(cls.fixture_run)
        cls.records=list(session_records(cls.fixture_run));last=max(cls.public)
        cls.closing_sequence=last+1
        cls.closure=json.loads((cls.fixture_run/'closure.json').read_bytes())
        cls.previous=[r for r in cls.records if r[2].get('stage')=='official_session_response'
                      and r[2].get('sequence')==last]
        cls.closing=[r for r in cls.records if r[2].get('stage')=='official_session_response'
                     and r[2].get('operation')=='close']

    def validate(self):
        return review.validate_inventory_readback(self.fixture_run,self.public,core_sha256=XP2_CORE_SHA256,
                                                  allow_authenticated_closing=True)

    def test_all_three_real_closes_are_separate_from_actual_public_revisions(self):
        for run,sequence in zip(RUNS,(10,2,2)):
            with self.subTest(run=run.name):
                public=public_views(run);before=deepcopy(public)
                r=review.validate_inventory_readback(run,public,core_sha256=XP2_CORE_SHA256,
                                                     allow_authenticated_closing=True)
                self.assertEqual(public,before)
                self.assertEqual(r['public_revision_count'],len(public))
                self.assertEqual({v['sequence'] for v in r['records']},set(public))
                self.assertEqual((r['closing_revision_count'],r['closing_event_count']),(1,1))
                closing=r['closing_records'][0];evidence=closing['closing_response']
                self.assertEqual(closing['sequence'],sequence);self.assertNotIn(sequence,public)
                self.assertEqual(closing['native']['inventory'],public[max(public)][1]['decisions']['placement_inventory'])
                self.assertTrue(evidence['network_protocol_validated'])
                self.assertFalse(evidence['client_public_view_fabricated'])
                self.assertEqual(evidence['native_lifetime_evidence']['schema'],'civ6-host.xp2-loaded-close-evidence.v1')
                self.assertTrue(evidence['native_lifetime_evidence']['native_unload_and_destroy_returned'])
                self.assertLess(evidence['preceding_native_response_line'],closing['lines'][0])
                self.assertLess(closing['lines'][0],evidence['close_begin_line'])

    def test_default_scope_and_unknown_revision_remain_refused(self):
        with self.assertRaisesRegex(ValueError,'unmatched revision'):
            review.validate_inventory_readback(self.fixture_run,self.public,core_sha256=XP2_CORE_SHA256)
        for core,option in ((XP1_CORE_SHA256,True),(None,True),(XP2_CORE_SHA256,1)):
            with self.subTest(core=core,option=option),self.assertRaisesRegex(ValueError,'explicit XP2 checkpoint'):
                review.validate_inventory_readback(self.fixture_run,self.public,core_sha256=core,allow_authenticated_closing=option)
        def unknown(run):
            for line,raw,e in self.records:
                if e.get('stage')=='native_placement_inventory_readback' and e.get('sequence')==self.closing_sequence:
                    e=dict(e,sequence=self.closing_sequence+1)
                yield line,raw,e
        with patch('civ6_host.runtime.stdout_transport_profiles.session_records',unknown):
            with self.assertRaisesRegex(ValueError,'unmatched revision'):self.validate()

    def test_real_protocol_refuses_foreign_or_malformed_close_responses(self):
        mutations={
            'nonce':lambda e:e.update(nonce='foreign'),
            'episode':lambda e:e.update(episode_id='foreign'),
            'generation':lambda e:e.update(game_generation='foreign'),
            'sequence':lambda e:e.update(sequence=e['sequence']+1),
            'boolean_sequence':lambda e:e.update(sequence=True),
            'schema':lambda e:e.update(schema='foreign'),
            'operation':lambda e:e.update(operation='observe'),
            'extra_field':lambda e:e.update(unreviewed=True),
            'observation':lambda e:e['observation'].update(width=1),
            'catalogue_schema':lambda e:e['decisions'].update(schema='foreign'),
            'inventory':lambda e:e['decisions']['placement_inventory'].update(turn=3),
            'automatic_choice':lambda e:e.update(automatic_choices_applied=True),
            'action_result':lambda e:e['command_result'].update(status='completed'),
            'offered_after_close':lambda e:e['decisions']['candidates'].append(dict(candidate_id='invented',action={'kind':'civic'})),
        }
        for name,mutate in mutations.items():
            with self.subTest(name=name):
                line,raw,event=self.closing[0];event=deepcopy(event);mutate(event)
                with self.assertRaises(ValueError):
                    review._closing_inventory_boundary(self.fixture_run,self.closure,self.public,self.previous,[(line,raw,event)],XP2_CORE_SHA256)

    def test_unique_native_response_and_preceding_public_join_are_required(self):
        for previous,closing in (([],self.closing),(self.previous,[]),
            (self.previous+self.previous,self.closing),(self.previous,self.closing+self.closing)):
            with self.subTest(counts=(len(previous),len(closing))),self.assertRaisesRegex(ValueError,'unique native close'):
                review._closing_inventory_boundary(self.fixture_run,self.closure,self.public,previous,closing,XP2_CORE_SHA256)
        for name in ('schema','sequence','inventory'):
            previous=deepcopy(self.previous);event=previous[0][2]
            if name=='schema':event['schema']='foreign'
            elif name=='sequence':event['sequence']=True
            else:event['decisions']['placement_inventory']['turn']=3
            with self.subTest(name=name),self.assertRaisesRegex(ValueError,'last actual public boundary'):
                review._closing_inventory_boundary(self.fixture_run,self.closure,self.public,previous,self.closing,XP2_CORE_SHA256)

    def test_closing_inventory_source_identity_value_and_physical_interval_are_required(self):
        mutations={
            'source':lambda line,e:(line,dict(e,source_proof_sha256='f'*64)),
            'scope':lambda line,e:(line,dict(e,host_tracking_used=True)),
            'native_mutation':lambda line,e:(line,dict(e,native_gameplay_mutated=True)),
            'extra_field':lambda line,e:(line,dict(e,unreviewed=True)),
            'episode':lambda line,e:(line,dict(e,episode_id='foreign')),
            'generation':lambda line,e:(line,dict(e,game_generation='foreign')),
            'player':lambda line,e:(line,dict(e,player_id=True)),
            'turn':lambda line,e:(line,dict(e,turn=True)),
            'inventory':lambda line,e:(line,dict(e,inventory=None)),
            'before_last_response':lambda line,e:(self.previous[0][0],e),
            'after_close_begins':lambda line,e:(self.closing[0][0],e),
        }
        for name,mutate in mutations.items():
            with self.subTest(name=name):
                def changed(run):
                    for line,raw,event in self.records:
                        if event.get('stage')=='native_placement_inventory_readback' and event.get('sequence')==self.closing_sequence:
                            line,event=mutate(line,deepcopy(event))
                        yield line,raw,event
                with patch('civ6_host.runtime.stdout_transport_profiles.session_records',changed):
                    with self.assertRaises(ValueError):self.validate()
        def missing(run):
            return (r for r in self.records if not (r[2].get('stage')=='native_placement_inventory_readback'
                    and r[2].get('sequence')==self.closing_sequence))
        with patch('civ6_host.runtime.stdout_transport_profiles.session_records',missing):
            with self.assertRaisesRegex(ValueError,'distinct readback receipt'):self.validate()

    def test_main_reviewer_defers_close_inventory_until_after_lifetime_reconciliation(self):
        import ast,inspect
        tree=ast.parse(inspect.getsource(session_review.review))
        calls=[n for n in ast.walk(tree) if isinstance(n,ast.Call)]
        inventory=next(n for n in calls if isinstance(n.func,ast.Name) and n.func.id=='validate_inventory_readback')
        lifetime=next(n for n in calls if isinstance(n.func,ast.Attribute) and n.func.attr=='saved_load_reconcile_later'
            and any(k.arg=='phase' and isinstance(k.value,ast.Constant) and k.value.value=='lifetime' for k in n.keywords))
        self.assertLess(lifetime.lineno,inventory.lineno)
        opt=next(k.value for k in inventory.keywords if k.arg=='allow_authenticated_closing')
        self.assertIsInstance(opt,ast.Name);self.assertEqual(opt.id,'xp2_checkpoint_group')


if __name__=='__main__':unittest.main()
