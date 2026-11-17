"""Exercise the secondary public Congress views on the composed LAN owner."""

from copy import deepcopy
from struct import pack
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from civ6_host.contracts import network_turn, world_congress, world_congress_review
from civ6_host.contracts.information import project
from civ6_host.runtime import network_checkpoint, player_views, xp1_session_checkpoint, xp2_congress_cycle, xp2_lan_congress
from civ6_host.runtime import xp2_lan_unit_commands, xp2_world_congress_source
from civ6_host.runtime.native import native_player_operation_request
from civ6_host.runtime.native.native_session_resume import semantic_decisions
from test_world_congress_active_effects import catalogue as effects
from test_world_congress_contract import catalogue as congress
from test_world_congress_contract import ballot_parameters
from test_xp2_congress_cycle import own_review_targets, review_for
from test_xp2_congress_proposal_effect import attach_memory
from test_xp2_lan_governors import SecondaryGovernorFixture
from test_xp2_lan_trade import TradeFixture


class SecondaryCongressTests(TestCase):
    def fixture(self, f=None, *, ballots=False, proposals=False):
        if f is None:
            f = TradeFixture(stock=True)
        self.addCleanup(f.close)
        f.saved.world_congress_diagnostic = True
        f.saved.world_congress_review_diagnostic = True
        f.backend._xp2_world_congress_review_requested = True
        f.token.explicit_world_congress = {'primary': 'preserved'}
        f.token._xp2_congress_cycles = object()
        self.cycle = f.token._xp2_congress_cycles
        self.stage = 'ordinary'
        self.foreign = False
        self.effect_duration = 6
        self.segment_change = False
        self.ballot_review = None
        self.changed_target = False
        self.foreign_archive = False
        self.ignore_looked = False
        self.proposals_offered = proposals
        f.stack.enter_context(patch.object(xp2_lan_congress, 'source_dependencies'))
        f.stack.enter_context(patch.object(xp2_lan_congress, 'verify_live'))
        f.stack.enter_context(patch.object(xp2_lan_congress.xp2_world_congress_review, 'source_dependencies'))
        f.stack.enter_context(patch.object(xp2_lan_congress.xp2_world_congress_review, '_empty'))

        def query(prefix, pid, turn, sequence, backend):
            self.assertEqual((prefix, f.player, pid, turn, backend), (f.saved.prefix, 1, 1, 8, f.backend))
            public = congress(self.stage, pid=0 if self.foreign else pid, turn=turn, sequence=sequence)
            public.update(presentation='closed', offers=dict.fromkeys(public['offers'], False))
            self.form = deepcopy(public)
            self.private = {'internal_target': 63,
                'popup': dict(capability=proposals, current_era=3, initial_era=2,
                              has_emergency_proposals=self.proposals_offered and self.stage == 'ordinary')}
            if self.stage == 'ordinary' and proposals and not self.proposals_offered:
                public['proposals'] = []
            if ballots or proposals:
                resolutions = [dict(resolution_hash=row['resolution_hash'], resolution_type=row['resolution_type'],
                    target_type='PlayerType', targets=[pid, 62 if self.changed_target else 63])
                    for row in public['resolutions'] or []]
                self.private.update(enums=xp2_world_congress_source.enum_values(), resolution_targets=resolutions,
                    discussions=[dict(sender=2, target=pid)] if public['discussions'] else [],
                    order=dict(resolutions=[r['resolution_hash'] for r in resolutions],
                               discussions=[0] if public['discussions'] else [], proposals=[]))
            if self.proposals_offered and self.stage == 'ordinary':
                self.private['proposals'] = {0: dict(target=3, discussion_type=self.memory.hashes[1])}
                self.private['order']['proposals'] = [0]
            return dict(public=public, private=deepcopy(self.private))

        def results(prefix, pid, turn, sequence, *, backend, environment, admission, projection=None,
                    administrative=False):
            self.assertEqual((prefix, f.player, pid, turn, backend), (f.saved.prefix, 1, 1, 8, f.backend))
            self.assertIs(environment, xp2_lan_congress.xp2_congress_review_configuration)
            self.assertEqual(admission['private'], self.private)
            if self.stage != 'ordinary':
                return None
            segment = admission['public']['turn_segment'] + int(self.segment_change)
            if projection is xp2_lan_congress.native_world_congress_active_effects:
                result = effects(pid, turn, sequence, segment)
                result['resolutions'][0]['turns_left'] = self.effect_duration
                result['meeting_turns_left'] = self.effect_duration - 1
                return result
            self.assertIsNone(projection)
            if self.ballot_review is not None:
                form, action, private = self.ballot_review
                review = review_for(dict(form, turn=turn, sequence=sequence, turn_segment=segment), action)
                if administrative:
                    return dict(public=review, private=own_review_targets(form, action, review, private))
                return review
            self.assertFalse(administrative)
            return dict(schema=world_congress_review.SCHEMA, player_id=pid, turn=turn, sequence=sequence,
                        turn_segment=segment, history_kind='last_results', resolutions=[], discussions=[])

        self.query = f.stack.enter_context(patch.object(xp2_lan_congress.native_saved_world_congress,
                                                      'query', side_effect=query))
        self.results = f.stack.enter_context(patch.object(xp2_lan_congress.native_world_congress_review,
                                                        'query', side_effect=results))
        if ballots:
            self.stage = 'regular'
            f.stack.enter_context(patch.object(xp2_congress_cycle, 'enabled', return_value=True))
            del f.token._xp2_congress_cycles
            self.state = xp2_congress_cycle._state(f.backend, f.token, f.saved.prefix, f.token.identity)
            self.cycle = xp2_congress_cycle._new_cycle(self.state, True)
            self.state.events.append((xp2_congress_cycle.STAGE1, None))
            self.cycle.phase_events[xp2_congress_cycle.STAGE1] = 1
        if proposals:
            graph = SimpleNamespace(saved=f.saved, backend=f.backend, prefix=f.saved.prefix,
                                    continuation=f.token, memory=f.memory)
            self.memory = attach_memory(graph, actor=1)
            self.memory.game = f.token.lease.identity['game']
            self.memory.put(self.memory.base + 0xb8aa68, '<Q', self.memory.game)
            self.memory.put(self.memory.game + 0xc0, '<i', 8)
            self.memory.rows([(0, 63, 0), (1, 2, 0)])

        if ballots or proposals:
            self.packets = []
            issued = {}

            def request(core, context, player, operation, parameters, *, core_sha256, allow_empty, congress_permit):
                self.assertEqual((core, context, f.player, player), (f.backend.core, f.backend.context, 1, 1))
                name = xp2_world_congress_source.authorize_request(congress_permit, core, context, player,
                    operation, parameters, core_sha256=core_sha256, submit=True, allow_empty=allow_empty)
                sender = 0 if self.foreign_archive and len(self.packets) == 1 else player
                data = pack('<5I', 0xc45de12f, sender, operation, 2, 0x80000001 if parameters else 0)
                if parameters:
                    data += pack('<I', len(parameters))
                    data += b''.join(pack('<IHH10xI', k, 0, 2, v) for k, v in sorted(parameters.items()))
                f.token.transport.pending.append(data)
                self.packets.append(name)
                issued[data] = name
                return dict(request_invoked=True)

            def end_turn(player, *, player_ids):
                self.assertEqual((f.player, player), (1, 1))
                self.assertIn(player, player_ids)
                f.token.transport.pending.append(pack('<III', 0xd7c02786, player, 0xb6fa1284))
                self.packets.append('ACTION_ENDTURN')

            f.stack.enter_context(patch.object(native_player_operation_request, 'request_player_operation',
                                               side_effect=request))
            f.stack.enter_context(patch.object(f.saved.prefix.actions, 'request_end_turn', side_effect=end_turn))
            if proposals:
                deliver = f.saved.prefix.actions.deliver_one

                def apply_proposal():
                    archive = f.token.transport.pending[0]
                    deliver()
                    if issued[archive] == 'WORLD_CONGRESS_DISCUSSION_SELECTION':
                        self.memory.rows([(0, 63, 0), (1, 2, 0), (1, 3, 1)])
                        self.proposals_offered = False
                    elif issued[archive] == 'WORLD_CONGRESS_LOOKED_AT_AVAILABLE' and not self.ignore_looked:
                        self.memory.put(self.memory.player + 0x2c8, '<i', 8)

                f.stack.enter_context(patch.object(f.saved.prefix.actions, 'deliver_one', side_effect=apply_proposal))
        return f

    def vote(self, f, choices, sequence):
        return self.choose(f, choices, sequence, xp2_lan_congress.BALLOT,
                           ballot_parameters(choices['world_congress'], resolution_votes=2))

    def choose(self, f, choices, sequence, kind, parameters=None):
        form = choices['world_congress']
        candidate, = [row for row in world_congress.actions(form) if row['kind'] == kind]
        action = world_congress.choose(form, candidate, parameters)
        selection = dict(decision_id=choices['decision_id'], candidate_id=network_turn.digest(candidate))
        if parameters is not None:
            selection['parameters'] = parameters
        request = dict(operation='act', player_id=1, sequence=sequence, selection=selection)
        _, session, observation, current, receipt = xp2_lan_unit_commands.read_reply(
            f.saved, f.protocol, request, (0, 1))
        network_turn.validate_catalogue(current, f.token.identity, sequence, 8, player_id=1, observation=observation)
        f.protocol.catalogues[1], f.protocol.observations[1], f.protocol.session = current, observation, session
        return action, current, receipt

    def test_three_public_views_belong_to_the_secondary_revision_without_offering_a_command(self):
        f = self.fixture()
        observation, decisions, command = f.reply(11)
        form = project('world_congress', observation, decisions)
        review = project('world_congress_review', observation, decisions)
        active = project('world_congress_active_effects', observation, decisions)
        for value in (form, review, active):
            self.assertEqual((value['player_id'], value['turn'], value['sequence']), (1, 8, 11))
            self.assertNotIn('private', value)
        self.assertIsNone(active['resolutions'][0]['chosen_target']['player_id'])
        self.assertEqual(command['status'], 'none')
        self.assertEqual(self.results.call_count, 2)
        self.assertEqual(f.player, 0)
        self.assertEqual(f.token.explicit_world_congress, {'primary': 'preserved'})
        self.assertIs(f.token._xp2_congress_cycles, self.cycle)
        for kind in world_congress.CANDIDATE_FIELDS:
            self.assertEqual(decisions['families'][kind]['status'], 'unqualified')
        self.assertFalse(any(row['action']['kind'] in world_congress.CANDIDATE_FIELDS
                             for row in decisions['candidates']))

    def test_voting_returns_public_form_and_reports_other_screens_unavailable(self):
        f = self.fixture()
        self.stage = 'regular'
        observation, decisions, _ = f.reply(7)
        form = project('world_congress', observation, decisions)
        self.assertTrue(form['in_session'])
        self.assertTrue(form['resolutions'])
        self.assertFalse(world_congress.actions(form))
        self.assertEqual(decisions['world_congress_review_status'], 'review_ui_unavailable')
        self.assertEqual(decisions['world_congress_active_effects_status'], 'active_effects_ui_unavailable')
        edited = deepcopy(decisions)
        edited['world_congress']['offers']['confirm_ballot'] = True
        body = {key: value for key, value in edited.items() if key != 'decision_id'}
        edited['decision_id'] = network_turn.digest(body)
        with self.assertRaisesRegex(ValueError, 'differs from its offers'):
            network_turn.validate_catalogue(edited, f.token.identity, 7, 8, player_id=1, observation=observation)

    def test_ballot_uses_the_secondary_fifo_and_waits_for_its_finished_review(self):
        f = self.fixture(ballots=True)
        _, before, _ = f.reply(1)
        original_private = deepcopy(self.private)
        action, after, receipt = self.vote(f, before, 2)
        self.assertEqual(receipt['status'], 'pending')
        self.assertEqual(receipt['requested_action'], action)
        self.assertEqual(self.packets, ['WORLD_CONGRESS_RESOLUTION_VOTE', 'WORLD_CONGRESS_DISCUSSION_VOTE',
                                       'WORLD_CONGRESS_SUBMIT_TURN', 'ACTION_ENDTURN'])
        self.assertEqual(sum(row[0] == 'receive' for row in f.machine), 4)
        self.assertFalse(world_congress.actions(after['world_congress']))
        self.assertEqual((f.player, f.token.explicit_world_congress), (0, {'primary': 'preserved'}))
        with self.assertRaisesRegex(ValueError, 'pending secondary Congress result'):
            xp2_lan_congress.check_checkpoint(f.saved)
        self.stage = 'ordinary'
        self.ballot_review = before['world_congress'], action, original_private
        f.reply(3)
        self.assertTrue(xp2_lan_congress._ballots(f.token, 1))
        self.state.events.append((xp2_congress_cycle.FINISHED, None))
        self.cycle.finished = 2
        observation, finished, _ = f.reply(4)
        result = project('world_congress_review', observation, finished)
        self.assertIsNone(result['resolutions'][0]['votes'][0]['target']['player_id'])
        self.assertEqual(xp2_lan_congress._ballots(f.token, 1), ())
        xp2_lan_congress.check_checkpoint(f.saved)

    def test_unseen_opaque_target_change_refuses_before_native_request(self):
        f = self.fixture(ballots=True)
        _, before, _ = f.reply(1)
        self.changed_target = True
        _, _, receipt = self.vote(f, before, 2)
        self.assertEqual(receipt['reason'], 'native_secondary_congress_form_changed')
        self.assertEqual(self.packets, [])

    def test_foreign_sender_aborts_the_whole_batch_before_delivery(self):
        f = self.fixture(ballots=True)
        _, before, _ = f.reply(1)
        self.foreign_archive = True
        with self.assertRaisesRegex(RuntimeError, 'differs from the acting player'):
            self.vote(f, before, 2)
        self.assertFalse(any(row[0] == 'receive' for row in f.machine))

    def test_secondary_proposal_uses_its_owned_popup_and_actual_own_state_comparison(self):
        f = self.fixture(proposals=True)
        _, ordinary, _ = f.reply(1)
        _, opened, receipt = self.choose(f, ordinary, 2, 'congress_open')
        self.assertEqual(receipt['status'], 'completed')
        self.assertEqual(opened['world_congress']['presentation'], 'available_proposals')
        self.assertEqual(self.packets, [])
        with self.assertRaisesRegex(ValueError, 'Close the secondary Congress popup'):
            xp2_lan_congress.check_checkpoint(f.saved)
        _, after, receipt = self.choose(f, opened, 3, 'congress_confirm_proposals', {'proposal_indices': [0]})
        self.assertEqual(receipt['status'], 'completed')
        self.assertEqual(self.packets, ['WORLD_CONGRESS_DISCUSSION_SELECTION', 'WORLD_CONGRESS_LOOKED_AT_AVAILABLE'])
        self.assertEqual(after['world_congress']['presentation'], 'closed')
        self.assertEqual(after['world_congress']['proposals'], [])
        self.assertEqual((f.player, f.token.explicit_world_congress), (0, {'primary': 'preserved'}))
        self.assertEqual([args for rva,args in self.memory.native_calls if rva == 0x26c770], [(1,), (1,)])
        xp2_lan_congress.check_checkpoint(f.saved)

    def test_secondary_close_with_missing_marker_is_pending_and_cannot_be_resent(self):
        f = self.fixture(proposals=True)
        _, ordinary, _ = f.reply(1)
        _, opened, _ = self.choose(f, ordinary, 2, 'congress_open')
        self.ignore_looked = True
        _, after, receipt = self.choose(f, opened, 3, 'congress_close')
        self.assertEqual(receipt['status'], 'pending')
        self.assertEqual(receipt['reason'], 'native_secondary_congress_proposal_unresolved')
        self.assertEqual(self.packets, ['WORLD_CONGRESS_LOOKED_AT_AVAILABLE'])
        self.assertEqual(world_congress.actions(after['world_congress']), [])
        with self.assertRaisesRegex(ValueError, 'proposal effects remain unverified'):
            xp2_lan_congress.check_checkpoint(f.saved)

    def test_opening_congress_refuses_a_previously_offered_governor_edit(self):
        f = self.fixture(SecondaryGovernorFixture('appoint_governor'))
        outside, _ = f.reply(1)
        selected, = [row for row in outside['candidates'] if row['action']['kind'] == 'appoint_governor']
        action = selected['action']
        self.stage = 'regular'

        inside, refused = f.reply(2, action)
        self.assertEqual(refused, dict(status='refused', reason='native_congress_screen_read_only',
                                      requested_action=action))
        self.assertEqual(f.requests, [])
        self.assertFalse(f.applied)
        self.assertEqual(f.player, 0)
        self.assertEqual(inside['governors'], outside['governors'])
        self.assertEqual(inside['families'][action['kind']]['candidate_ids'], [])
        self.assertEqual(inside['candidates'], [row for row in outside['candidates']
            if row['action']['kind'] not in network_turn.CONGRESS_READ_ONLY_KINDS])

        self.stage = 'ordinary'
        ordinary, _ = f.reply(3)
        self.assertIn(selected, ordinary['candidates'])
        _, completed = f.reply(4, action)
        self.assertEqual(completed['status'], 'completed')
        self.assertEqual(len(f.requests), 1)

    def test_foreign_form_and_changed_results_segment_are_refused(self):
        for attr, error in (('foreign', 'Foreign Congress'), ('segment_change', 'crossed native turn segment')):
            with self.subTest(attr=attr):
                f = self.fixture()
                setattr(self, attr, True)
                with self.assertRaisesRegex(ValueError, error):
                    f.reply(1)
                self.assertEqual(f.player, 0)
                f.close()

    def test_checkpoint_preserves_exact_scope_and_ignores_only_public_revision(self):
        f = self.fixture()
        boundary = xp1_session_checkpoint.boundary(f.saved)
        options = dict(decision_players=(1,))
        now = player_views.checkpoint_view_digests(f.saved, boundary, (0, 1), **options)
        old = player_views.checkpoint_view_digests(f.saved, boundary, (0, 1), congress_mode='off', **options)
        form = player_views.checkpoint_view_digests(f.saved, boundary, (0, 1), congress_mode='catalogue', **options)
        _, decisions, _ = f.reply(12)
        comparable = semantic_decisions(decisions)
        for field in ('world_congress', 'world_congress_review', 'world_congress_active_effects'):
            self.assertEqual(comparable[field].pop('sequence'), 12)
        self.assertEqual(now['players'][1]['decisions_sha256'], network_turn.digest(comparable))
        self.assertEqual(now['congress_mode'], 'review')
        self.assertEqual(form['congress_mode'], 'catalogue')
        self.assertNotIn('congress_mode', old)
        self.assertNotEqual(now['players'][1]['decisions_sha256'], form['players'][1]['decisions_sha256'])
        state = dict(observation=f.token.observation, decisions={}, host_placement_tracking=[],
                     host_world_selection=None, network_boundary=boundary)
        f.saved.inputs.checkpoint = ('work/fixture/checkpoint.json', 'a' * 64)
        f.token.sequence += 1
        for views in (now, old, form):
            with patch.object(network_checkpoint, 'manifest', return_value=dict(state, checkpoint_public_views=views)):
                self.assertTrue(callable(network_checkpoint.prepare_owner(f.saved, f.token.observation)))
        self.effect_duration -= 1
        with patch.object(network_checkpoint, 'manifest', return_value=dict(state, checkpoint_public_views=now)):
            with self.assertRaisesRegex(ValueError, 'public decision catalogue differs'):
                network_checkpoint.prepare_owner(f.saved, f.token.observation)

    def test_checkpoint_rebinds_secondary_ballot_only_after_both_public_comparisons(self):
        source = self.fixture(ballots=True)
        _, public, _ = source.reply(11)
        self.assertTrue(public['world_congress']['offers']['confirm_ballot'])
        form = source.token._xp2_lan_congress_forms[1]
        boundary = xp1_session_checkpoint.boundary(source.saved)
        views = player_views.checkpoint_view_digests(source.saved, boundary, (0, 1), decision_players=(1,))
        self.assertIs(source.token._xp2_lan_congress_forms[1], form)
        binding = views['players'][1]['congress_ballot']
        self.assertEqual(set(binding), {'turn', 'turn_segment', 'stage', 'private_sha256'})
        self.assertEqual(binding['private_sha256'], network_turn.digest(form.private))
        primary = dict(episode_id='old', game_generation='old', sequence=11,
                       decision_id='old', candidates=[], turn=8)
        comparisons = dict(schema=network_checkpoint.SCHEMA_V2,
            observation=deepcopy(source.token.observation), decisions=primary, host_placement_tracking=[],
            host_world_selection=None, network_boundary=boundary, checkpoint_public_views=views)
        source.close()

        restored = self.fixture(ballots=True)
        self.state.events.clear()
        self.state.cycles.clear()
        self.state.current = None
        restored.saved.inputs.checkpoint = ('work/fixture/checkpoint.json', 'a' * 64)
        _, precheck, _ = restored.reply(1)
        self.assertFalse(precheck['world_congress']['offers']['confirm_ballot'])
        with patch.object(network_checkpoint, 'manifest', return_value=comparisons):
            first_reply = network_checkpoint.prepare_owner(restored.saved, restored.token.observation)
            _, still_unbound, _ = restored.reply(2)
            self.assertFalse(still_unbound['world_congress']['offers']['confirm_ballot'])
            next_primary = dict(primary, episode_id='new', game_generation='new', decision_id='new', sequence=0)
            with patch.object(network_turn, 'checkpoint_catalogue', side_effect=lambda current, *_, **__: (current, None)):
                with self.assertRaisesRegex(ValueError, 'public decision catalogue differs'):
                    first_reply(restored.token.observation, dict(next_primary, turn=9))
                self.assertFalse(hasattr(restored.token, '_xp2_lan_congress_restored'))
                first_reply(restored.token.observation, next_primary)
        self.assertEqual(self.state.events, [])
        self.assertFalse(self.state.current.entry_known)
        _, loaded, _ = restored.reply(3)
        self.assertTrue(loaded['world_congress']['offers']['confirm_ballot'])
        self.assertEqual(loaded['world_congress']['sequence'], 3)
        action, _, result = self.vote(restored, loaded, 4)
        self.assertEqual(result['requested_action'], action)
        self.assertEqual(result['status'], 'pending')
        self.assertEqual(len(self.packets), 4)

    def test_checkpoint_refuses_changed_hidden_target_before_arming_ballot(self):
        source = self.fixture(ballots=True)
        boundary = xp1_session_checkpoint.boundary(source.saved)
        views = player_views.checkpoint_view_digests(source.saved, boundary, (0, 1), decision_players=(1,))
        manifest = dict(schema=network_checkpoint.SCHEMA_V2, observation=deepcopy(source.token.observation),
                        decisions={}, host_placement_tracking=[], host_world_selection=None,
                        network_boundary=boundary, checkpoint_public_views=views)
        source.close()
        restored = self.fixture(ballots=True)
        self.state.events.clear()
        self.state.cycles.clear()
        self.state.current = None
        restored.saved.inputs.checkpoint = ('work/fixture/checkpoint.json', 'a' * 64)
        self.changed_target = True
        with patch.object(network_checkpoint, 'manifest', return_value=manifest):
            with self.assertRaisesRegex(ValueError, 'ballot phase or native choices differ'):
                network_checkpoint.prepare_owner(restored.saved, restored.token.observation)
        self.assertFalse(hasattr(restored.token, '_xp2_lan_congress_restored'))
        self.assertEqual(self.packets, [])
