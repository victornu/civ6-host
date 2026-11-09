"""Staged cycle composition: native memory/callback input are fixture bytes.

Uses the actual SavedLoadOwner, SavedContinuation, A0 dispatcher, source guards,
empty receiver and native FIFO. No game image is loaded or executed.
"""
from copy import deepcopy
from dataclasses import replace
from contextlib import contextmanager, nullcontext
import hashlib
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch

from civ6_host.contracts import world_congress as contract
from civ6_host.runtime import empty_presentation_events as empty
from civ6_host.runtime import xp2_congress_presentation as presentation
from civ6_host.runtime import xp2_congress_cycle as cycle
from civ6_host.runtime.xp1_continuation import ACTIVE, READY
from civ6_host.runtime.xp1_saved_load_owner import SavedLoadOwner
from test_world_congress_contract import catalogue, ballot_parameters
from test_xp2_congress_presentation import CongressPresentationTests


def ballot(public, *, resolution_votes=2, discussion_votes=-2, option=2):
    params = ballot_parameters(public, resolution_votes=resolution_votes, discussion_votes=discussion_votes)
    for row in params['resolutions']:
        row.update(target_index=0, option=option)
    return contract.choose(public, dict(kind='congress_confirm_ballot', sequence=public['sequence']), params)


def review_for(public, action):
    from civ6_host.runtime.native.native_world_congress_review import SCHEMA
    local = dict(player_id=public['player_id'], label='Local leader')
    result = dict(schema=SCHEMA, player_id=public['player_id'],
        turn=public['turn'], sequence=public['sequence'], turn_segment=public['turn_segment'],
        history_kind='last_results', resolutions=[], discussions=[])
    by_hash = {row['resolution_hash']: row for row in public['resolutions'] or []}
    for choice in action['resolutions']:
        row = by_hash[choice['resolution_hash']]
        target = {k: row['targets'][choice['target_index']][k] for k in ('player_id','value','label')}
        a = choice['votes'] if choice['option'] == 1 else 0
        b = choice['votes'] if choice['option'] == 2 else 0
        result['resolutions'].append(dict(index=len(result['resolutions']), resolution_type=row['resolution_type'],
            name='Resolution', target_type=row['target_type'], chosen_option='A', chosen_label='Chosen',
            chosen_target=deepcopy(target), rejected_option='B', rejected_label='Rejected', is_new=False,
            votes_a=a, votes_b=b, tied=a==b, votes=[dict(voter=deepcopy(local), option=choice['option'],
                votes=choice['votes'], target=deepcopy(target), option_label='Selected')]))
    by_index = {row['index']: row for row in public['discussions'] or []}
    for choice in action['discussions']:
        row = by_index[choice['discussion_index']]
        count = choice['votes']
        result['discussions'].append(dict(index=len(result['discussions']), category_type='Emergency',
            category_name='Emergency', type_name=row['type_name'], name='Discussion', description='Description',
            target=deepcopy(row['target']), is_new=False, votes_up=max(0,count), votes_down=max(0,-count),
            passed=count>0, votes=[dict(voter=deepcopy(local), votes=count, reason='')]))
    return result


def own_review_targets(public, action, review, private):
    maps={r['resolution_hash']:r for r in private['resolution_targets']}
    value={key:review[key] for key in ('player_id','turn','sequence','turn_segment')}
    value['resolutions']=[dict(resolution_type=maps[r['resolution_hash']]['resolution_type'],
        target_type='PlayerType',option=r['option'],votes=r['votes'],
        target_player_id=maps[r['resolution_hash']]['targets'][r['target_index']])
        for r in action['resolutions'] if r['resolution_hash'] in maps]
    return value


class CycleTests(unittest.TestCase):
    def graph(self, *, enabled=True):
        fixture = CongressPresentationTests()
        original = empty.enable
        def install(owner, backend, source):
            result = original(owner, backend, source)
            if source is presentation and enabled:
                cycle.enable(backend)
            return result
        with patch.object(empty, 'enable', install):
            g = fixture.graph()
        g.continuation.sequence = 0
        g.continuation.observation = dict(player_id=0, turn=61)
        g.continuation.publishing = False
        g.continuation.trade_feedback = None
        g.prefix.actions.pending = []
        g.native_queue_empty = True
        def require_native_empty():
            if not g.native_queue_empty or g.prefix.actions.pending:
                raise ValueError('fixture native receive queue is not empty')
        g.prefix.actions.require_empty_native_queue = require_native_empty
        requested = dict(post160_candidate=True, unit_commands_candidate=True)
        saved = SavedLoadOwner._allocate(requested, g.event.emit)
        saved.backend = saved._backend = g.backend
        saved.prefix, saved.core, saved.host = g.prefix, g.backend.core, g.backend.host
        saved.context, saved.inputs = g.backend.context, g.backend.inputs
        saved.receipt = g.backend.raw_load_result = object()
        saved._engine_sha256 = g.backend.load_abi.core_sha256
        saved.continuation, saved.phase, saved._running = g.continuation, 'commands', True
        g.backend._saved_stage_owner = saved
        g.backend._xp2_postload_requested = True
        g.saved = saved
        return g

    @contextmanager
    def mode(self, g, *, active):
        old = g.backend.stage, g.backend.busy
        g.backend.stage = ACTIVE if active else READY
        g.backend.busy = active
        try:
            yield
        finally:
            g.backend.stage, g.backend.busy = old

    def observe(self, g, public):
        with self.mode(g, active=False):
            cycle.observe_catalogue(g.saved, public)
        from civ6_host.runtime.xp2_world_congress import _Catalogue
        c = g.continuation
        c._xp2_world_congress_catalogue = _Catalogue(g.saved,g.backend,c,g.prefix,c.identity,
            c.sequence,deepcopy(c.observation),deepcopy(public),{})
        c.explicit_world_congress = deepcopy(public)

    @contextmanager
    def quiescent_control(self, g):
        # Native control snapshot inputs are supplied by this fixture; queue
        # guards and the real saved owner/record/popup checks still run.
        with patch.object(g.backend,'control',return_value=dict(pending_count=0)) as control:
            yield control

    def read_result(self, g, public, action):
        outside=catalogue('ordinary',sequence=4);outside['turn_segment']=0
        outside['presentation']='closed';outside['offers']['confirm_proposals']=False
        self.observe(g,outside)
        review=review_for(public,action);review.update(sequence=4,turn_segment=0)
        with self.mode(g,active=False):
            permit=cycle.prepare_review_readback(g.saved)
            return cycle.observe_review(g.saved,review,permit=permit)

    def event(self, g, kind):
        fields = CongressPresentationTests().fields(kind, 0)
        with self.mode(g, active=True):
            return g.owner.dispatch(kind, fields, 0)

    def started(self):
        g = self.graph()
        self.observe(g, catalogue('ordinary'))
        self.event(g, presentation.STAGE1)
        public = catalogue()
        self.observe(g, public)
        return g, public

    def begin(self, g, public, action, *, partial=False, private=None):
        plan = contract.empty_phase_plan(public) if action['kind']=='automatic_congress_empty_phase' else contract.operation_plan(public, action)
        operations = [row['kind'] for row in plan['operations']] + ['end_turn']
        if partial:
            operations = operations[:1]
        journal = [dict(operation=kind, archive_sha256=hashlib.sha256(str(i).encode()).hexdigest(),
                        delivered=False, native_request=None) for i,kind in enumerate(operations)]
        legacy = dict(scope=(public['player_id'],public['turn'],public['turn_segment'],public['stage']),
                      action=deepcopy(action), journal=journal, partial_submission=partial)
        g.continuation._xp2_world_congress_confirmation = legacy
        with self.mode(g, active=True):
            return cycle.begin_confirmation(g.saved, public, action, plan, legacy, private=private)

    def private_form(self, g, public, *, hidden_target=7):
        private=dict(resolution_targets=[dict(resolution_hash=r['resolution_hash'],
            resolution_type=r['resolution_type'],target_type='PlayerType',
            targets=[t['player_id'] if t['player_id'] is not None else hidden_target for t in r['targets']])
            for r in public['resolutions'] or [] if r['target_type']=='PlayerType'])
        record=g.continuation._xp2_world_congress_catalogue
        g.continuation._xp2_world_congress_catalogue=replace(record,private=private)
        return private

    def deliver(self, g, entry, *, finished_during_last=False):
        for i, row in enumerate(entry.legacy['journal']):
            # The native callback is synchronous inside deliver_one; the archive
            # delivered flag is committed only after that native call returns.
            if finished_during_last and i == len(entry.legacy['journal']) - 1:
                self.event(g, presentation.FINISHED)
            row['delivered'] = True
            with self.mode(g, active=True):
                cycle.record_delivery(g.saved, entry, i)

    def test_explicit_profile_leaves_historical_empty_omission_unchanged(self):
        g = self.graph(enabled=False)
        for kind in (presentation.STAGE1,presentation.STAGE3,presentation.FINISHED):
            self.event(g,kind)
        self.assertFalse(hasattr(g.continuation,'_xp2_congress_cycles'))
        self.assertEqual((g.owner._sequence,g.owner.pending),(0,[]))
        with self.assertRaisesRegex(ValueError,'not admitted'):
            self.observe(g,catalogue())
        with self.assertRaisesRegex(ValueError,'prepared'):
            cycle.enable(g.backend)

    def test_actual_callback_order_preserves_fifo_and_never_releases_checkpoint(self):
        g, public = self.started()
        pending = bytes(range(96)); g.owner.pending.append(pending)
        before = (g.owner._sequence,tuple(g.owner.pending),g.owner.host_notification_counter,g.owner.host_metadata_counter)
        action = ballot(public); entry = self.begin(g,public,action)
        state = g.continuation._xp2_congress_cycles
        self.assertTrue(entry.cycle.entry_known)
        self.assertEqual(cycle._match_current(state,entry,review_for(public,action))['reason'],
                         'partial_or_incomplete_archive_delivery')
        self.event(g,presentation.STAGE3)
        self.deliver(g,entry,finished_during_last=True)
        result = cycle._match_current(state,entry,review_for(public,action))
        self.assertEqual(result['result_status'],'exact_current_cycle_ballot_result_observed')
        self.assertFalse(result['transport_acknowledged'])
        self.assertFalse(result['confirmation_resolved'])
        self.assertEqual((g.owner._sequence,tuple(g.owner.pending),g.owner.host_notification_counter,
                          g.owner.host_metadata_counter),before)
        self.assertIs(g.owner.pending[0],pending)
        with self.mode(g,active=False), self.assertRaisesRegex(ValueError,'ordinary closed'):
            cycle.check_checkpoint(g.saved)
        self.assertIs(g.continuation._xp2_world_congress_confirmation,entry.legacy)

    def test_phase_and_stage3_alone_do_not_finish_a_confirmation(self):
        g,public=self.started();action=ballot(public);entry=self.begin(g,public,action)
        self.deliver(g,entry);self.event(g,presentation.STAGE3)
        self.observe(g,catalogue('ordinary'))
        report=cycle._match_current(g.continuation._xp2_congress_cycles,entry,review_for(public,action))
        self.assertEqual(report['reason'],'finished_not_observed_after_confirmation')
        with self.mode(g,active=False):
            self.assertIsNone(cycle.prepare_review_readback(g.saved))

    def test_loaded_active_phase_stays_unknown_even_after_repeated_stage1(self):
        g=self.graph();public=catalogue();self.observe(g,public)
        self.event(g,presentation.STAGE1)
        action=ballot(public);entry=self.begin(g,public,action)
        self.deliver(g,entry,finished_during_last=True)
        report=cycle._match_current(g.continuation._xp2_congress_cycles,entry,review_for(public,action))
        self.assertEqual(report['reason'],'cycle_entry_not_observed')
        self.observe(g,catalogue('ordinary'))
        with self.mode(g,active=False):
            self.assertIsNone(cycle.prepare_review_readback(g.saved))

    def test_intervening_cycle_and_generation_cannot_reuse_the_same_results(self):
        g,public=self.started();action=ballot(public);entry=self.begin(g,public,action)
        self.deliver(g,entry,finished_during_last=True)
        self.observe(g,catalogue('ordinary'));self.event(g,presentation.STAGE1)
        report=cycle._match_current(g.continuation._xp2_congress_cycles,entry,review_for(public,action))
        self.assertEqual(report['reason'],'cycle_superseded_or_ambiguous')
        state=g.continuation._xp2_congress_cycles;state.generation='foreign'
        with self.mode(g,active=False),self.assertRaisesRegex(ValueError,'generation'):
            cycle.check_checkpoint(g.saved)

    def test_partial_and_interrupted_delivery_remain_across_scope_changes(self):
        for partial in (False,True):
            g,public=self.started();entry=self.begin(g,public,ballot(public),partial=partial)
            if partial:self.deliver(g,entry)
            self.event(g,presentation.FINISHED);self.observe(g,catalogue('ordinary'))
            self.event(g,presentation.STAGE2)
            with self.mode(g,active=True),self.assertRaisesRegex(ValueError,'partial or interrupted'):
                cycle.guard(g.saved,active=True)
            self.assertIs(g.continuation._xp2_congress_cycles.confirmations[0],entry)

    def test_previous_complete_delivery_is_retained_when_a_new_scope_confirms(self):
        g,public=self.started();entry=self.begin(g,public,ballot(public));self.deliver(g,entry)
        self.event(g,presentation.STAGE2)
        second=catalogue('special',sequence=4);second['turn_segment']+=1
        self.observe(g,second)
        newer=self.begin(g,second,ballot(second));self.deliver(g,newer)
        self.assertEqual(g.continuation._xp2_congress_cycles.confirmations,[entry,newer])
        self.assertIsNot(g.continuation._xp2_world_congress_confirmation,entry.legacy)
        with self.mode(g,active=False),self.assertRaises(ValueError):cycle.check_checkpoint(g.saved)

    def test_malformed_callback_does_not_create_a_completion(self):
        g,public=self.started();state=g.continuation._xp2_congress_cycles
        before=deepcopy(state.events)
        with self.assertRaises(ValueError):g.owner.dispatch(presentation.FINISHED,{},0)
        self.assertEqual(state.events,before)
        self.assertIsNone(state.current.finished)

    def test_exact_matching_includes_every_vote_target_identity_and_direction(self):
        public=catalogue();action=ballot(public);expected=cycle._expected(public,action)
        review=review_for(public,action)
        self.assertEqual(cycle.match_ballot(expected,review)['result_status'],'exact_ballot_matches')
        variants=[]
        for field,value in [('option',1),('votes',3),('votes',True)]:
            changed=deepcopy(review);changed['resolutions'][0]['votes'][0][field]=value;variants.append(changed)
        changed=deepcopy(review);changed['resolutions'][0]['votes'][0]['target'].update(player_id=7,value='7');variants.append(changed)
        changed=deepcopy(review);changed['discussions'][0]['votes'][0]['votes']=2;variants.append(changed)
        changed=deepcopy(review);changed['discussions']=[];variants.append(changed)
        changed=deepcopy(review);changed['resolutions'].append(deepcopy(changed['resolutions'][0]));variants.append(changed)
        changed=deepcopy(review);changed['discussions'].append(deepcopy(changed['discussions'][0]));variants.append(changed)
        changed=deepcopy(review);changed['player_id']=True;variants.append(changed)
        for changed in variants:
            self.assertEqual(cycle.match_ballot(expected,changed)['result_status'],'unresolved')
        # UI labels and the aggregate winner cannot replace the exact own vote.
        review['resolutions'][0]['chosen_option']='OTHER';review['resolutions'][0]['votes'][0]['target']['label']='Translated'
        self.assertEqual(cycle.match_ballot(expected,review)['result_status'],'exact_ballot_matches')

    def test_default_state_matches_but_hidden_or_nonunique_identity_is_unresolved(self):
        public=catalogue();action=ballot(public,resolution_votes=1,discussion_votes=-1,option=1)
        result=cycle.match_ballot(cycle._expected(public,action),review_for(public,action))
        self.assertEqual(result['result_status'],'exact_ballot_matches')
        self.assertEqual(result['nondefault_witnesses'],0)
        self.assertEqual(result['vote_origin'],'submitted_or_automatic_fill_indeterminate')
        self.assertFalse(result['transport_acknowledged'])
        self.assertIn(dict(kind='congress_confirm_ballot',sequence=public['sequence']),contract.actions(public))
        action['resolutions'][0]['target_index']=1
        self.assertEqual(cycle.match_ballot(cycle._expected(public,action),review_for(public,action))['reason'],
                         'hidden_or_unsupported_resolution_target')
        public=catalogue('special');public['discussions'].append(deepcopy(public['discussions'][0]))
        public['discussions'][1]['index']=1
        action=ballot(public)
        self.assertEqual(cycle.match_ballot(cycle._expected(public,action),review_for(public,action))['reason'],
                         'hidden_or_ambiguous_discussion_identity_without_sender')
        public=catalogue();public['resolutions'].append(deepcopy(public['resolutions'][0]))
        public['resolutions'][1]['resolution_hash']-=1
        action=ballot(public)
        self.assertEqual(cycle.match_ballot(cycle._expected(public,action),review_for(public,action))['reason'],
                         'ambiguous_resolution_type')

    def test_mutated_delivered_archive_or_action_refuses(self):
        for change in ('digest','delivered','action'):
            g,public=self.started();entry=self.begin(g,public,ballot(public));self.deliver(g,entry)
            if change=='digest':entry.legacy['journal'][0]['archive_sha256']='f'*64
            elif change=='delivered':entry.legacy['journal'][0]['delivered']=False
            else:entry.legacy['action']['sequence']+=1
            with self.mode(g,active=True),self.assertRaisesRegex(ValueError,'mutated or is foreign'):
                cycle.guard(g.saved,active=True)

    def test_conditional_hook_uses_real_review_parser_without_query_or_settlement(self):
        g,public=self.started();action=ballot(public);entry=self.begin(g,public,action)
        self.deliver(g,entry,finished_during_last=True)
        outside=catalogue('ordinary',sequence=4);outside['turn_segment']=0
        self.observe(g,outside)
        review=review_for(public,action)
        review.update(sequence=4,turn_segment=0)
        # The real staged parser is used. Any query from this hook is forbidden.
        from civ6_host.runtime.native import native_world_congress_review as reader
        with patch.object(reader,'query',side_effect=AssertionError('unexpected native query')):
            with self.mode(g,active=False):
                permit=cycle.prepare_review_readback(g.saved)
                self.assertIsNotNone(permit)
                result=cycle.observe_review(g.saved,review,permit=permit)
            self.assertEqual(result[0]['result_status'],'exact_current_cycle_ballot_result_observed')
            self.assertFalse(result[0]['confirmation_resolved'])
            for change in ('sequence','segment','duplicate_voter'):
                bad=deepcopy(review)
                if change=='sequence':bad['sequence']=3
                elif change=='segment':bad['turn_segment']=1
                else:
                    votes=bad['resolutions'][0]['votes'];votes.append(deepcopy(votes[0]))
                with self.mode(g,active=False),self.assertRaises(ValueError):
                    permit=cycle.prepare_review_readback(g.saved)
                    cycle.observe_review(g.saved,bad,permit=permit)
            with self.mode(g,active=False):permit=cycle.prepare_review_readback(g.saved)
            self.event(g,presentation.STAGE3)
            with self.mode(g,active=False),self.assertRaisesRegex(ValueError,'permit'):
                cycle.observe_review(g.saved,review,permit=permit)
        with self.mode(g,active=False),self.assertRaises(ValueError):cycle.check_checkpoint(g.saved)
        g.continuation.sequence+=1
        with self.mode(g,active=False),self.assertRaisesRegex(ValueError,'current catalogue revision'):
            cycle.prepare_review_readback(g.saved)

    def test_exact_observed_ballot_retires_at_actual_active_save_guard(self):
        from civ6_host.runtime import xp2_world_congress as world
        g,public=self.started();action=ballot(public);entry=self.begin(g,public,action)
        self.deliver(g,entry,finished_during_last=True)
        self.read_result(g,public,action)
        with self.quiescent_control(g) as control,self.mode(g,active=True):
            world.check_checkpoint(g.saved)
            control.assert_called_once_with(empty=True)
        state=g.continuation._xp2_congress_cycles
        self.assertIsNone(g.continuation._xp2_world_congress_confirmation)
        self.assertIs(entry.retirement,state.retirements[0])
        import json
        receipt=json.loads(entry.retirement.payload)
        self.assertTrue(receipt['pending_confirmation_retired'])
        self.assertTrue(receipt['checkpoint_admission_eligible'])
        self.assertFalse(receipt['transport_acknowledged'])
        self.assertFalse(receipt['native_save_reload_qualified'])
        self.assertEqual(len(receipt['confirmations'][0]['archives']),len(entry.planned))
        emitted=[r for name,r in g.event.emitted if name=='congress_observed_ballots_retired']
        self.assertEqual(len(emitted),1)
        self.assertEqual(emitted[0]['receipt_sha256'],entry.retirement.sha256)
        # A repeated Save check does not retire twice or infer a new occurrence.
        with self.mode(g,active=True):world.check_checkpoint(g.saved)
        self.assertEqual(len(state.retirements),1)
        entry.legacy['journal'][0]['delivered']=False
        with self.mode(g,active=True),self.assertRaisesRegex(ValueError,'mutated'):
            world.check_checkpoint(g.saved)
        reloaded=self.graph();self.observe(reloaded,public)
        self.assertFalse(reloaded.continuation._xp2_congress_cycles.current.entry_known)
        self.assertEqual(reloaded.continuation._xp2_congress_cycles.confirmations,[])

    def test_retirement_requires_exact_result_fresh_scope_and_all_empty_queues(self):
        cases=('native','actions','deferred','feedback','publishing','revision','callback','record','result')
        for case in cases:
            with self.subTest(case=case):
                g,public=self.started();action=ballot(public,option=1,resolution_votes=1,discussion_votes=-1)
                entry=self.begin(g,public,action)
                self.deliver(g,entry,finished_during_last=True)
                self.read_result(g,public,action)
                if case=='native':g.native_queue_empty=False
                elif case=='actions':g.prefix.actions.pending.append(b'archive')
                elif case=='deferred':g.prefix.deferred_events.pending.append(bytes(96))
                elif case=='feedback':
                    def refuse():raise ValueError('pending feedback')
                    g.continuation.trade_feedback=NS(check_checkpoint=refuse)
                elif case=='publishing':g.continuation.publishing=True
                elif case=='revision':g.continuation.sequence+=1
                elif case=='callback':self.event(g,presentation.STAGE3)
                elif case=='record':g.continuation.explicit_world_congress['current_favor']+=1
                else:
                    # Merely assigning a successful report is never evidence.
                    g.continuation._xp2_congress_cycles.observed_review=None
                    entry.result=dict(result_status='exact_current_cycle_ballot_result_observed')
                with self.quiescent_control(g),self.mode(g,active=True),self.assertRaises(ValueError):
                    cycle.retire_observed_confirmations(g.saved)
                self.assertIsNone(entry.retirement)
                self.assertIs(g.continuation._xp2_world_congress_confirmation,entry.legacy)
                self.assertFalse(g.continuation._xp2_congress_cycles.retirements)

    def test_default_only_unmatched_and_failed_admin_write_keep_pending(self):
        for case in ('mismatch','admin_failure'):
            with self.subTest(case=case):
                g,public=self.started()
                action=ballot(public,option=1,resolution_votes=1,discussion_votes=-1)
                entry=self.begin(g,public,action);self.deliver(g,entry,finished_during_last=True)
                outside=catalogue('ordinary',sequence=4);outside['turn_segment']=0
                outside['presentation']='closed';outside['offers']['confirm_proposals']=False;self.observe(g,outside)
                review=review_for(public,action);review.update(sequence=4,turn_segment=0)
                if case=='mismatch':
                    row=review['resolutions'][0];row['votes'][0]['option']=2
                    row['votes_a'],row['votes_b']=row['votes_b'],row['votes_a']
                with self.mode(g,active=False):
                    permit=cycle.prepare_review_readback(g.saved)
                    cycle.observe_review(g.saved,review,permit=permit)
                failure=patch.object(g.saved,'emit',side_effect=OSError('admin write failed')) if case=='admin_failure' else nullcontext()
                with self.quiescent_control(g),self.mode(g,active=True),failure,self.assertRaises((ValueError,OSError)):
                    cycle.retire_observed_confirmations(g.saved)
                self.assertIsNone(entry.retirement)
                self.assertIs(g.continuation._xp2_world_congress_confirmation,entry.legacy)

    def test_default_only_human_ballots_pass_active_save_without_individual_ack(self):
        from civ6_host.runtime import xp2_world_congress as world
        import json
        for stage,signed_vote in (('regular',-1),('special',-1),('special',1)):
            with self.subTest(stage=stage,votes=signed_vote):
                g=self.graph();self.observe(g,catalogue('ordinary'))
                self.event(g,presentation.STAGE1 if stage=='regular' else presentation.STAGE2)
                public=catalogue(stage);self.observe(g,public)
                action=ballot(public,option=1,resolution_votes=1,discussion_votes=signed_vote)
                entry=self.begin(g,public,action)
                with self.mode(g,active=False):
                    self.assertIsNone(cycle.prepare_review_readback(g.saved))
                self.deliver(g,entry,finished_during_last=True)
                reports=self.read_result(g,public,action)
                self.assertEqual(reports[0]['nondefault_witnesses'],0)
                with self.quiescent_control(g),self.mode(g,active=True):
                    world.check_checkpoint(g.saved)
                receipt=json.loads(entry.retirement.payload)
                result=receipt['confirmations'][0]['result']
                self.assertEqual(result['result_status'],'exact_current_cycle_ballot_result_observed')
                self.assertEqual(result['vote_origin'],'submitted_or_automatic_fill_indeterminate')
                self.assertFalse(result['transport_acknowledged'])
                self.assertFalse(receipt['transport_acknowledged'])
                self.assertFalse(receipt['native_save_reload_qualified'])
                self.assertIsNone(g.continuation._xp2_world_congress_confirmation)

    def test_regular_ballot_and_source_empty_special_retire_together(self):
        for case in ('valid','partial','choices','form','phase'):
            with self.subTest(case=case):
                g,public=self.started();action=ballot(public);entry=self.begin(g,public,action)
                self.deliver(g,entry)
                self.event(g,presentation.STAGE2)
                special=catalogue('special',sequence=4);special['turn_segment']+=1
                special['discussions']=[];special['offers']['confirm_ballot']=False
                self.observe(g,special)
                marker=dict(kind='automatic_congress_empty_phase',sequence=4)
                automatic=self.begin(g,special,marker,partial=case=='partial')
                self.deliver(g,automatic,finished_during_last=True)
                reports=self.read_result(g,public,action)
                if case=='valid':
                    self.assertEqual([r['result_status'] for r in reports],
                        ['exact_current_cycle_ballot_result_observed','exact_current_cycle_empty_phase_finished_observed'])
                    with self.quiescent_control(g),self.mode(g,active=True):
                        receipt=cycle.retire_observed_confirmations(g.saved)
                    self.assertEqual(len(receipt['confirmations']),2)
                    self.assertEqual([r['operation'] for r in receipt['confirmations'][1]['archives']],
                                     ['congress_submit','end_turn'])
                    self.assertIs(entry.retirement,automatic.retirement)
                else:
                    if case=='choices':automatic.empty_form['discussions']=deepcopy(catalogue('special')['discussions'])
                    elif case=='form':automatic.empty_form['sequence']+=1
                    elif case=='phase':automatic.cycle.phase_events[presentation.STAGE2]=automatic.armed_at+1
                    with self.quiescent_control(g),self.mode(g,active=True),self.assertRaises(ValueError):
                        cycle.retire_observed_confirmations(g.saved)
                    self.assertIsNone(entry.retirement);self.assertIsNone(automatic.retirement)

    def test_empty_only_retires_without_review_or_vote_witness(self):
        from civ6_host.runtime.native import native_world_congress_review as reader
        for case in ('valid','unknown','unfinished'):
            with self.subTest(case=case):
                g=self.graph()
                if case!='unknown':self.observe(g,catalogue('ordinary'))
                self.event(g,presentation.STAGE2)
                special=catalogue('special');special['discussions']=[]
                special['offers']['confirm_ballot']=False;self.observe(g,special)
                entry=self.begin(g,special,dict(kind='automatic_congress_empty_phase',sequence=3))
                self.deliver(g,entry,finished_during_last=case!='unfinished')
                outside=catalogue('ordinary',sequence=4);outside['presentation']='closed'
                outside['offers']['confirm_proposals']=False;self.observe(g,outside)
                with patch.object(reader,'query',side_effect=AssertionError('empty phase must not query Review')):
                    with self.mode(g,active=False):self.assertIsNone(cycle.prepare_review_readback(g.saved))
                    if case=='valid':
                        with self.quiescent_control(g),self.mode(g,active=True):
                            receipt=cycle.retire_observed_confirmations(g.saved)
                        self.assertIsNone(receipt['review']);self.assertIsNone(receipt['review_sha256'])
                        self.assertEqual(receipt['confirmations'][0]['result']['result_status'],
                                         'exact_current_cycle_empty_phase_finished_observed')
                        self.assertFalse(receipt['transport_acknowledged'])
                    else:
                        with self.quiescent_control(g),self.mode(g,active=True),self.assertRaises(ValueError):
                            cycle.retire_observed_confirmations(g.saved)
                        self.assertIsNone(entry.retirement)

    def test_masked_target_uses_only_owned_administrative_mapping_and_retires(self):
        from civ6_host.runtime import xp2_world_congress as world
        import json
        g,public=self.started();action=ballot(public,option=1,resolution_votes=1,discussion_votes=-1)
        action['resolutions'][0]['target_index']=1
        private=self.private_form(g,public)
        before=deepcopy(public)
        self.assertEqual(contract.operation_plan(public,action)['operations'][0]['target_index'],1)
        entry=self.begin(g,public,action,private=private)
        self.deliver(g,entry,finished_during_last=True)
        outside=catalogue('ordinary',sequence=4);outside['turn_segment']=0
        outside['presentation']='closed';outside['offers']['confirm_proposals']=False;self.observe(g,outside)
        review=review_for(public,action);review.update(sequence=4,turn_segment=0)
        actor_review=deepcopy(review)
        administrative=own_review_targets(public,action,review,private)
        with self.mode(g,active=False):
            permit=cycle.prepare_review_readback(g.saved)
            reports=cycle.observe_review(g.saved,review,permit=permit,administrative=administrative)
        self.assertEqual(reports[0]['result_status'],'exact_current_cycle_ballot_result_observed')
        self.assertNotIn('target_player_id',json.dumps(reports))
        self.assertEqual(public,before);self.assertEqual(review,actor_review)
        self.assertIsNone(review['resolutions'][0]['votes'][0]['target']['player_id'])
        # The sealed observation owns its copy, not the caller's mutable dict.
        administrative['resolutions'][0]['target_player_id']=8
        with self.quiescent_control(g),self.mode(g,active=True):world.check_checkpoint(g.saved)
        receipt=json.loads(entry.retirement.payload)
        self.assertEqual(receipt['review_administrative']['resolutions'][0]['target_player_id'],7)
        self.assertEqual(receipt['confirmations'][0]['expected_ballot']['resolutions'][0]['target'],['player',7])
        self.assertEqual(receipt['review'],actor_review)
        self.assertFalse(receipt['transport_acknowledged'])

    def test_private_target_match_rejects_absence_mismatch_and_foreign_readback(self):
        g,public=self.started();private=self.private_form(g,public)
        action=ballot(public);action['resolutions'][0]['target_index']=1
        expected=cycle._expected(public,action,private)
        review=review_for(public,action)
        administrative=own_review_targets(public,action,review,private)
        self.assertEqual(cycle.match_ballot(expected,review)['result_status'],'unresolved')
        bad=deepcopy(administrative);bad['resolutions'][0]['target_player_id']=8
        self.assertEqual(cycle.match_ballot(expected,review,administrative=bad)['result_status'],'unresolved')
        for case in ('player','turn','sequence','segment','duplicate','missing','vote','option','type','bool'):
            bad=deepcopy(administrative)
            if case in ('player','turn','sequence','segment'):
                key={'player':'player_id','segment':'turn_segment'}.get(case,case);bad[key]+=1
            elif case=='duplicate':bad['resolutions'].append(deepcopy(bad['resolutions'][0]))
            elif case=='missing':bad['resolutions']=[]
            elif case=='vote':bad['resolutions'][0]['votes']+=1
            elif case=='option':bad['resolutions'][0]['option']=1
            elif case=='type':bad['resolutions'][0]['resolution_type']='FOREIGN_TYPE'
            else:bad['resolutions'][0]['target_player_id']=True
            with self.subTest(case=case),self.assertRaises(ValueError):
                cycle.match_ballot(expected,review,administrative=bad)

    def test_private_form_must_be_exact_owner_and_preserve_public_target_order(self):
        g,public=self.started();private=self.private_form(g,public);action=ballot(public)
        with self.assertRaisesRegex(ValueError,'exact current catalogue owner'):
            self.begin(g,public,action,private=deepcopy(private))
        for case in ('visible','count','type','hash','duplicate','bool'):
            bad=deepcopy(private);row=bad['resolution_targets'][0]
            if case=='visible':row['targets'][0]=9
            elif case=='count':row['targets'].pop()
            elif case=='type':row['resolution_type']='FOREIGN_TYPE'
            elif case=='hash':row['resolution_hash']-=1
            elif case=='duplicate':bad['resolution_targets'].append(deepcopy(row))
            else:row['targets'][1]=True
            with self.subTest(case=case),self.assertRaises(ValueError):cycle._expected(public,action,bad)
        action['resolutions'][0]['target_index']=1
        private['resolution_targets'][0]['targets'][1]=-1
        expected=cycle._expected(public,action,private)
        self.assertEqual(expected['ambiguities'],[])
        review=review_for(public,action)
        administrative=own_review_targets(public,action,review,private)
        self.assertEqual(administrative['resolutions'][0]['target_player_id'],-1)
        self.assertEqual(cycle.match_ballot(expected,review,administrative=administrative)['result_status'],
                         'exact_ballot_matches')


if __name__=='__main__':unittest.main()
