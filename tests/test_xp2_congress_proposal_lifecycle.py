"""Composed ordinary Congress lifecycle; native memory/request results are fixtures."""
from contextlib import ExitStack
from copy import deepcopy
from dataclasses import replace
import json
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch

from civ6_host.contracts import world_congress as contract
from civ6_host.runtime import xp2_congress_cycle as cycle
from civ6_host.runtime import xp2_world_congress as world
from civ6_host.runtime import xp2_world_congress_popup as popup
from civ6_host.runtime import xp2_world_congress_source as source
from civ6_host.runtime.native import native_saved_world_congress as native
from civ6_host.runtime.native import native_player_operation_request as requests
from civ6_host.runtime.native import native_player_observation as observations
import test_xp2_congress_cycle as cycle_fixture
import test_xp2_congress_proposal_effect as effect_fixture
from test_world_congress_contract import catalogue


class ProposalLifecycleTests(unittest.TestCase):
    def graph(self, g=None, *, count=1, marker_already=False):
        helper=cycle_fixture.CycleTests()
        g=helper.graph() if g is None else g
        from civ6_host.runtime.configuration_profiles import XP2_CORE_SHA256
        from civ6_host.runtime.captured_session_profile import select
        from civ6_host.runtime.lan_load import _LAN_MODE,_SIMULTANEOUS_PHASE
        selected=select(XP2_CORE_SHA256)
        inputs=g.backend.inputs
        inputs.profile=selected.candidate.profile;inputs.official_bundle=selected.candidate.reference
        g.saved.inputs=g.backend.inputs=inputs
        g.backend.captured_bundle=NS(reference=selected.candidate.reference,inputs=inputs)
        g.saved.network_reference=dict(capture_manifest_sha256=selected.candidate.reference[1],
            state=dict(game_mode_u32=_LAN_MODE,turn_phase_u32=_SIMULTANEOUS_PHASE,player_id=0,observer_id=0),
            major_player_ids=(0,1),human_player_ids=(0,))
        g.saved.world_congress_diagnostic=True
        g.continuation.publication_count=0
        g.continuation.trade_feedback=NS(flush=lambda:[],check_checkpoint=lambda:None)
        memory=effect_fixture.attach_memory(g)
        memory.game=g.backend.bound_identity['game']
        memory.put(memory.base+0xb8aa68,'<Q',memory.game)
        memory.put(memory.game+0xc0,'<i',61)
        if marker_already:memory.put(memory.player+0x2c8,'<i',61)
        public=catalogue('ordinary')
        for index in range(1,count):
            row=deepcopy(public['proposals'][0]);row.update(index=index,target_key=index)
            public['proposals'].append(row)
        private=dict(enums=source.enum_values(),discussions={},
            proposals={i:dict(target=3+i,discussion_type=memory.hashes[1-i]) for i in range(count)},
            order=dict(resolutions=[],discussions=[],proposals=list(range(count))),
            popup=dict(capability=True,current_era=3,initial_era=2,has_emergency_proposals=True),
            resolution_targets=[])
        closed=deepcopy(public);closed['presentation']='closed'
        closed['offers']=dict(open=True,confirm_ballot=False,confirm_proposals=False,close=False)
        with helper.mode(g,active=True):popup.apply_open(g.saved,closed,private)
        envelope=dict(public=public,private=private)
        with helper.mode(g,active=False):public=world._public(g.saved,envelope)
        helper.observe(g,public)
        record=g.continuation._xp2_world_congress_catalogue
        g.continuation._xp2_world_congress_catalogue=replace(record,private=private)
        g.proposal_helper,g.proposal_memory,g.proposal_envelope=helper,memory,envelope
        g.proposal_public=public
        return g

    def apply(self,g,*,close=False,ignore_selection=False,ignore_looked=False,stop_request=None):
        helper,memory=g.proposal_helper,g.proposal_memory
        public=g.proposal_public
        kind='congress_close' if close else 'congress_confirm_proposals'
        parameters=None if close else dict(proposal_indices=list(range(len(public['proposals']))))
        action=contract.choose(public,dict(kind=kind,sequence=public['sequence']),parameters)
        timeline=[];packets={};counter=0
        own=[(0,2,0)];foreign=[(1,63,1)]
        memory.call_hook=lambda rva,args:timeline.append(('snapshot',len(g.prefix.actions.pending))) if rva==0x3bd000 else None
        enums=g.proposal_envelope['private']['enums']
        selection=enums['WORLD_CONGRESS_DISCUSSION_SELECTION'];looked=enums['WORLD_CONGRESS_LOOKED_AT_AVAILABLE']
        def request(core,context,pid,operation,values,**kwargs):
            nonlocal counter
            source.authorize_request(kwargs['congress_permit'],core,context,pid,operation,values,
                core_sha256=kwargs['core_sha256'],submit=True,allow_empty=kwargs['allow_empty'])
            timeline.append(('request',operation));counter+=1
            if counter==stop_request:return dict(request_invoked=True)
            archive=bytes([counter])*96
            packets[archive]=(operation,dict(values));g.prefix.actions.pending.append(archive)
            return dict(request_invoked=True)
        def deliver():
            archive=g.prefix.actions.pending.pop(0);operation,values=packets[archive]
            timeline.append(('deliver',operation))
            if operation==selection and not ignore_selection:
                key=values[enums['PARAM_DISCUSSION_TYPE']]
                own.append((0,values[enums['PARAM_OTHER_PLAYER']],memory.hashes.index(key)))
                memory.rows(own+foreign)
            elif operation==looked and not ignore_looked:memory.put(memory.player+0x2c8,'<i',61)
        def publish():
            timeline.append(('publish',None));g.continuation.publication_count+=1
        g.prefix.actions.deliver_one=deliver
        with ExitStack() as stack:
            stack.enter_context(helper.quiescent_control(g))
            stack.enter_context(helper.mode(g,active=True))
            stack.enter_context(patch.object(native,'query',return_value=deepcopy(g.proposal_envelope)))
            stack.enter_context(patch.object(requests,'request_player_operation',side_effect=request))
            stack.enter_context(patch.object(observations,'observe_player',return_value=deepcopy(g.continuation.observation)))
            stack.enter_context(patch.object(g.prefix.view_publisher,'publish',side_effect=publish))
            result=world.apply(g.saved,action,deepcopy(g.continuation.observation))
        return result,timeline

    def ready_after(self,g):
        helper=g.proposal_helper
        # The normal continuation increments revision only after _apply returns.
        g.continuation.sequence+=1
        with helper.mode(g,active=False):public=world._public(g.saved,g.proposal_envelope)
        helper.observe(g,public)
        record=g.continuation._xp2_world_congress_catalogue
        g.continuation._xp2_world_congress_catalogue=replace(record,private=g.proposal_envelope['private'])

    def checkpoint(self,g):
        with g.proposal_helper.quiescent_control(g),g.proposal_helper.mode(g,active=True):
            world.check_checkpoint(g.saved)

    def test_full_proposal_batch_observed_before_after_then_active_save_without_cycle(self):
        g=self.graph(count=2);result,timeline=self.apply(g)
        self.assertEqual(result['status'],'pending')
        self.assertEqual([v for k,v in timeline if k=='snapshot'],[0,0])
        self.assertLess(next(i for i,x in enumerate(timeline) if x[0]=='snapshot'),
                        next(i for i,x in enumerate(timeline) if x[0]=='request'))
        self.assertGreater(max(i for i,x in enumerate(timeline) if x[0]=='snapshot'),
                           max(i for i,x in enumerate(timeline) if x[0]=='deliver'))
        state=g.continuation._xp2_congress_cycles;entry=state.confirmations[0]
        self.assertIsNone(state.current);self.assertEqual(state.events,[])
        self.assertEqual(entry.result['result_status'],'exact_own_proposal_batch_state_observed')
        self.assertEqual(set(result['receipt']['own_proposal_result']),
            {'result_status','looked_effect','transport_acknowledged',
             'confirmation_resolved','checkpoint_release_qualified'})
        self.assertFalse(any(k in json.dumps(result['receipt']) for k in
            ('own_rows','expected_additions','target_player_id','type_index','marker_turn')))
        self.ready_after(g);self.checkpoint(g)
        receipt=json.loads(entry.retirement.payload)
        self.assertIsNone(receipt['review']);self.assertIsNone(receipt['finished_event'])
        proof=receipt['confirmations'][0]['own_proposal_readback']
        self.assertEqual(proof['looked_effect'],'changed')
        self.assertEqual(proof['expected_additions'],[dict(sender=0,target=3,type_index=1),dict(sender=0,target=4,type_index=0)])
        self.assertFalse(proof['transport_acknowledged'])
        self.assertFalse(receipt['native_save_reload_qualified'])

    def test_close_only_already_satisfied_marker_is_explicit_and_retirable(self):
        g=self.graph(marker_already=True);result,_=self.apply(g,close=True)
        self.assertEqual(result['receipt']['own_proposal_result']['looked_effect'],'already_satisfied')
        self.ready_after(g);self.checkpoint(g)
        entry=g.continuation._xp2_congress_cycles.confirmations[0]
        proof=json.loads(entry.retirement.payload)['confirmations'][0]['own_proposal_readback']
        self.assertEqual(proof['expected_additions'],[])
        self.assertEqual(proof['before']['own_rows'],proof['after']['own_rows'])
        self.assertFalse(proof['transport_acknowledged'])

    def test_delivered_handler_refusal_or_missing_marker_remains_unresolved(self):
        for failure in ('selection','looked'):
            with self.subTest(failure=failure):
                g=self.graph();result,_=self.apply(g,ignore_selection=failure=='selection',ignore_looked=failure=='looked')
                self.assertTrue(all(r['delivered'] for r in result['receipt']['native_journal']))
                entry=g.continuation._xp2_congress_cycles.confirmations[0]
                self.assertEqual(entry.result['result_status'],'unresolved')
                self.assertIsNotNone(entry.proposal_observation)
                self.ready_after(g)
                with self.assertRaisesRegex(ValueError,'not exactly observed'):self.checkpoint(g)
                self.assertIsNone(entry.retirement)

    def test_partial_delivery_never_retires_or_permits_model_continuation(self):
        g=self.graph(count=2);result,_=self.apply(g,stop_request=2)
        self.assertTrue(result['receipt']['partial_submission'])
        entry=g.continuation._xp2_congress_cycles.confirmations[0]
        self.assertEqual(entry.delivered,1);self.assertIsNotNone(entry.proposal_observation)
        with g.proposal_helper.mode(g,active=False),self.assertRaisesRegex(ValueError,'partial or interrupted'):
            world.check_model_admission(g.saved)
        with self.assertRaises(ValueError):self.checkpoint(g)
        self.assertIsNone(entry.retirement)

    def test_observed_proposal_does_not_clear_an_unresolved_ballot(self):
        helper=cycle_fixture.CycleTests();g,public=helper.started()
        previous=helper.begin(g,public,cycle_fixture.ballot(public))
        helper.deliver(g,previous,finished_during_last=True)
        g=self.graph(g);self.apply(g);self.ready_after(g)
        state=g.continuation._xp2_congress_cycles
        self.assertEqual(len(state.confirmations),2)
        self.assertEqual(state.confirmations[1].result['result_status'],'exact_own_proposal_batch_state_observed')
        with self.assertRaisesRegex(ValueError,'actual observed Review'):self.checkpoint(g)
        self.assertTrue(all(e.retirement is None for e in state.confirmations))


if __name__=='__main__':unittest.main()
