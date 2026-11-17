import copy
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from civ6_host.contracts import diplomacy_decisions as public_diplomacy
from civ6_host.contracts import network_turn
from civ6_host.runtime.native.native_episode_identity import DiagnosticEpisodeIdentity
from civ6_host.runtime.native.native_saved_session_protocol import outcome
from civ6_host.runtime.native.native_victory_episode import POLICY_ID, PROOF_SHA256
from civ6_host.runtime.native.native_episode_facts import PROOF_SHA256 as FACTS_SHA
from civ6_host.runtime.network_protocol import SCHEMA as NETWORK_SCHEMA
from civ6_host.runtime.network_protocol import NetworkProtocol, validate_network_response
from civ6_host.session_client import SCHEMA as SESSION_SCHEMA, SessionClient
from civ6_host.client import _digest


def observation(player=0, turn=10):
    return dict(schema='civ6rl-player-observation-v1', player_id=player,
        turn=turn, width=1, height=1, plots=[], units=[], visible_enemy_units=[],
        cities=[], economy=dict(science=0, culture=0, gold=0, faith=0))


def player_map(obs):
    return dict(schema='civ6rl.saved_player_map933.v1', player_id=obs['player_id'],
        turn=obs['turn'], width=obs['width'], height=obs['height'], plots=[],
        visible_observation_id=_digest(obs), source='official_plot_tooltip_revealed_live_getters',
        historical_memory_proven=False, graphical_differential_proven=False,
        complete_player_observation=False)


def controls(player=0, *, active=False):
    return dict(schema=network_turn.TURN_CONTROLS_SCHEMA, player_id=player, turn=10,
        active=active, active_complete=False, can_unready=False, timer_elapsed=False)


def private_catalogue(identity, sequence, obs, choices=None):
    choices = choices or [dict(key='CHOICE_EXIT', disabled=False)]
    statement_sequence = 12
    session_id = 7
    dialogue = dict(session_id=session_id, statement_sequence=statement_sequence,
        from_player=1, to_player=0)
    candidates = []
    for row in choices:
        if row['disabled']:
            continue
        action = dict(kind='diplomacy_response', session_id=session_id,
            statement_sequence=statement_sequence, choice=row['key'])
        candidates.append(dict(candidate_id=public_diplomacy.digest(action), action=action))
    native_choices = [dict(key=row['key'], sort=index, text=row['key'], tooltip=None,
        diplomatic_action_type=None, disabled=row['disabled'])
        for index, row in enumerate(choices)]
    return dict(schema=public_diplomacy.BASE_SCHEMA, episode_id=identity.episode_id,
        game_generation=identity.game_generation, sequence=sequence, player_id=obs['player_id'],
        turn=obs['turn'], origin_turn=obs['turn'], player_map=player_map(obs),
        statement=dict(event_sequence=statement_sequence, fields=dict(AiReason=123, OpaquePayload='secret')),
        data=dict(session=dict(player_id=0, **dialogue), selections=native_choices,
                  raw_ai_reason=123, opaque_payload='secret'),
        candidates=candidates, unsupported=['existing_unqualified_family'],
        complete_action_space=False, source_sha256='private-source', ui_support_sha256='private-ui')


def public_catalogue(identity, sequence=0, *, obs=None, controls_value=None,
                     choices=None, display=None, closed=False):
    obs = obs or observation()
    return public_diplomacy.build(identity, sequence, obs,
        controls_value or controls(obs['player_id']),
        private_catalogue(identity, sequence, obs, choices),
        public_display=display,
        display_source_sha256=(public_diplomacy.PUBLIC_DISPLAY_SOURCE_SHA256
                               if display is not None else None),
        actions_closed=closed)


def public_display(choices):
    return dict(schema='civ6rl.diplomacy_public_display986.v2',
        speaker_leader='LEADER_TEST', statement_text='The treaty is refused.',
        reason_text='', selections=[dict(key=row['key'], text=row['key'],
            disabled=row['disabled'], tooltip=None) for row in choices])


class PublicDiplomacyContractTests(unittest.TestCase):
    def setUp(self):
        episode = str(uuid4())
        self.identity = DiagnosticEpisodeIdentity(episode, 'native-' + episode)
        self.obs = observation()

    def test_build_redacts_private_fields_and_validates_public_display(self):
        choices = [dict(key='CHOICE_POSITIVE', disabled=False),
                   dict(key='CHOICE_EXIT', disabled=True)]
        value = public_catalogue(self.identity, choices=choices,
                                 display=public_display(choices))
        self.assertEqual(value['schema'], public_diplomacy.SCHEMA)
        self.assertEqual(value['choices'], choices)
        self.assertEqual(value['public_display_source_sha256'],
                         public_diplomacy.PUBLIC_DISPLAY_SOURCE_SHA256)
        for private in ('statement', 'data', 'source_sha256', 'ui_support_sha256'):
            self.assertNotIn(private, value)
        self.assertNotIn(public_diplomacy.PUBLIC_DISPLAY_GAP, value['unsupported'])
        network_turn.validate_catalogue(value, self.identity, 0, 10, player_id=0,
            observation=self.obs)

    def test_missing_display_requires_explicit_gap_marker(self):
        value = public_catalogue(self.identity)
        self.assertIsNone(value['public_display'])
        self.assertIsNone(value['public_display_source_sha256'])
        self.assertIn(public_diplomacy.PUBLIC_DISPLAY_GAP, value['unsupported'])
        network_turn.validate_catalogue(value, self.identity, 0, 10, player_id=0,
            observation=self.obs)

    def test_friendship_reply_projects_only_the_native_public_outcome(self):
        choices = [dict(key='CHOICE_EXIT', disabled=False)]
        private = private_catalogue(self.identity, 0, self.obs, choices)
        session = private['data']['session']
        display = public_display(choices)
        for statement, subtype, expected in (
                ('DECLARE_FRIEND', 'AI_ACCEPT_DEAL', 'accepted'),
                ('DECLARE_FRIEND', 'AI_REFUSE_DEAL', 'rejected'),
                ('DECLARE_FRIEND', 'NONE', None),
                ('DIPLOMATIC_DELEGATION', 'AI_REFUSE_DEAL', None)):
            with self.subTest(statement=statement, subtype=subtype):
                session.update(statement_type=statement, statement_subtype=subtype)
                value = public_diplomacy.build(self.identity, 0, self.obs, controls(), private,
                    public_display=display,
                    display_source_sha256=public_diplomacy.PUBLIC_DISPLAY_SOURCE_SHA256)
                self.assertEqual(value.get('friendship_response'), expected)
                self.assertEqual(value['schema'], public_diplomacy.FRIENDSHIP_RESPONSE_SCHEMA
                                 if expected else public_diplomacy.SCHEMA)
                self.assertEqual(value['candidates'], private['candidates'])
                self.assertNotIn('statement_subtype', value['dialogue'])
                network_turn.validate_catalogue(value, self.identity, 0, 10, player_id=0,
                    observation=self.obs)
                if expected:
                    value['friendship_response'] = {'outcome': expected, 'reason': 'private'}
                    value['decision_id'] = public_diplomacy.digest(
                        {key: item for key, item in value.items() if key != 'decision_id'})
                    with self.assertRaisesRegex(ValueError, 'Invalid public friendship response'):
                        network_turn.validate_catalogue(value, self.identity, 0, 10, player_id=0,
                            observation=self.obs)

    def test_closed_catalogue_has_no_candidates(self):
        value = public_catalogue(self.identity, closed=True)
        self.assertEqual(value['candidates'], [])
        network_turn.validate_catalogue(value, self.identity, 0, 10, player_id=0,
            observation=self.obs, actions_closed=True)

    def test_received_promise_exposes_only_the_offered_responses(self):
        keys = ['CHOICE_POSITIVE', 'CHOICE_NEGATIVE', 'CHOICE_IGNORE']
        choices = [dict(key=key, disabled=key == 'CHOICE_IGNORE') for key in keys]
        private = private_catalogue(self.identity, 0, self.obs, choices)
        native_session = private['data']['session']
        native_session.update(statement_type='WARNING_DONT_SETTLE_NEAR_ME', statement_subtype='NONE')
        display = public_display(choices)
        pin = public_diplomacy.PUBLIC_DISPLAY_SOURCE_SHA256
        value = public_diplomacy.build(self.identity, 0, self.obs, controls(), private,
                                       public_display=display, display_source_sha256=pin)
        self.assertEqual(value['schema'], public_diplomacy.RECEIVED_PROMISE_SCHEMA)
        self.assertEqual(value['promise_request'], native_session['statement_type'])
        self.assertEqual(value['choices'], choices)
        self.assertEqual([row['action']['choice'] for row in value['candidates']], keys[:2])
        network_turn.validate_catalogue(value, self.identity, 0, 10, player_id=0,
                                        observation=self.obs)
        for invalid in (dict(statement_subtype='NEGATIVE'), dict(from_player=0, to_player=1),
                        dict(statement_type='DENOUNCE')):
            foreign = copy.deepcopy(private)
            foreign['data']['session'].update(invalid)
            with self.subTest(invalid=invalid), self.assertRaisesRegex(ValueError, 'choice'):
                public_diplomacy.build(self.identity, 0, self.obs, controls(), foreign,
                                       public_display=display, display_source_sha256=pin)

    def test_empty_deal_draft_discloses_only_the_counterparty_and_close(self):
        private = private_catalogue(self.identity, 0, self.obs)
        draft = dict(target_player_id=1, item_count=0, pending=False)
        private['data']['deal_draft'] = draft
        private['unsupported'].append(public_diplomacy.DEAL_DRAFT_GAP)
        value = public_diplomacy.build(self.identity, 0, self.obs, controls(), private)
        self.assertEqual(value['schema'], public_diplomacy.DEAL_DRAFT_SCHEMA)
        self.assertEqual(value['deal_draft'], draft)
        self.assertEqual([row['action']['choice'] for row in value['candidates']], ['CHOICE_EXIT'])
        self.assertNotIn('data', value)
        network_turn.validate_catalogue(value, self.identity, 0, 10, player_id=0,
            observation=self.obs)
        for delta in (dict(target_player_id=2), dict(item_count=False), dict(item_count=1),
                      dict(pending=True), dict(ai_value=100)):
            private['data']['deal_draft'] = dict(draft, **delta)
            with self.subTest(delta=delta), self.assertRaisesRegex(ValueError, 'empty deal draft'):
                public_diplomacy.build(self.identity, 0, self.obs, controls(), private)

    def test_peace_draft_exposes_two_locked_terms_and_only_the_qualified_exit(self):
        private = private_catalogue(self.identity, 0, self.obs)
        private['data']['deal_draft'] = dict(target_player_id=1, item_count=2, pending=False)
        terms = [dict(direction=side, duration=10, locked=True) for side in ('outgoing', 'incoming')]
        private['data']['deal_peace'] = terms
        private['unsupported'].append(public_diplomacy.DEAL_PEACE_NEGOTIATION_GAP)
        value = public_diplomacy.build(self.identity, 0, self.obs, controls(), private)
        self.assertEqual(value['schema'], public_diplomacy.DEAL_PEACE_SCHEMA)
        self.assertEqual(value['deal_peace'], terms)
        self.assertEqual([row['action']['choice'] for row in value['candidates']], ['CHOICE_EXIT'])
        network_turn.validate_catalogue(value, self.identity, 0, 10, player_id=0,
                                        observation=self.obs)
        for invalid in (terms[:1], list(reversed(terms)), [dict(terms[0], locked=False), terms[1]]):
            private['data']['deal_peace'] = invalid
            with self.subTest(invalid=invalid), self.assertRaisesRegex(ValueError, 'locked peace terms'):
                public_diplomacy.build(self.identity, 0, self.obs, controls(), private)

    def test_validator_rejects_private_fields_stale_identity_and_wrong_source(self):
        original = public_catalogue(self.identity, display=public_display(
            [dict(key='CHOICE_EXIT', disabled=False)]))
        cases = []
        extra = copy.deepcopy(original); extra['statement'] = {'AiReason': 8}; cases.append(extra)
        stale = copy.deepcopy(original); stale['dialogue']['session_id'] += 1
        stale['decision_id'] = public_diplomacy.digest({k:v for k,v in stale.items() if k!='decision_id'}); cases.append(stale)
        wrong_statement = copy.deepcopy(original); wrong_statement['statement_source_sha256'] = 'f' * 64
        wrong_statement['decision_id'] = public_diplomacy.digest({k:v for k,v in wrong_statement.items() if k!='decision_id'}); cases.append(wrong_statement)
        wrong_display = copy.deepcopy(original); wrong_display['public_display_source_sha256'] = 'f' * 64
        wrong_display['decision_id'] = public_diplomacy.digest({k:v for k,v in wrong_display.items() if k!='decision_id'}); cases.append(wrong_display)
        changed_display = copy.deepcopy(original); changed_display['public_display']['selections'][0]['key'] = 'CHOICE_POSITIVE'
        changed_display['decision_id'] = public_diplomacy.digest({k:v for k,v in changed_display.items() if k!='decision_id'}); cases.append(changed_display)
        wrong_choice = copy.deepcopy(original); wrong_choice['candidates'][0]['action']['choice'] = 'CHOICE_POSITIVE'
        wrong_choice['candidates'][0]['candidate_id'] = public_diplomacy.digest(wrong_choice['candidates'][0]['action'])
        wrong_choice['decision_id'] = public_diplomacy.digest({k:v for k,v in wrong_choice.items() if k!='decision_id'}); cases.append(wrong_choice)
        for value in cases:
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    network_turn.validate_catalogue(value, self.identity, 0, 10,
                        player_id=0, observation=self.obs)
        with self.assertRaisesRegex(ValueError, 'sequence'):
            network_turn.validate_catalogue(original, self.identity, 1, 10,
                player_id=0, observation=self.obs)
        missing_gap = public_catalogue(self.identity)
        missing_gap['unsupported'].remove(public_diplomacy.PUBLIC_DISPLAY_GAP)
        missing_gap['decision_id'] = public_diplomacy.digest(
            {k:v for k,v in missing_gap.items() if k!='decision_id'})
        with self.assertRaisesRegex(ValueError, 'marked unqualified'):
            network_turn.validate_catalogue(missing_gap, self.identity, 0, 10,
                player_id=0, observation=self.obs)

    def test_public_reply_composes_with_network_protocol_and_inactive_act(self):
        protocol, response = self._network_fixture()
        with patch('civ6_host.runtime.network_protocol.player_map.validate'):
            validate_network_response(response, protocol, 'reset')
            protocol.accept_response(response)
            action = protocol.catalogues[0]['candidates'][0]['action']
            request = dict(schema=NETWORK_SCHEMA, nonce=protocol.nonce,
                episode_id=self.identity.episode_id,
                game_generation=self.identity.game_generation, sequence=1,
                operation='act', player_id=0,
                selection=dict(decision_id=protocol.catalogues[0]['decision_id'],
                    candidate_id=protocol.catalogues[0]['candidates'][0]['candidate_id']))
            self.assertEqual(protocol.validate(request), 'act')
            self.assertEqual(protocol.selected(request), action)
            reply = self._network_reply(protocol, 'act', 1, status='refused', selected=action)
            validate_network_response(reply, protocol, 'act', request=request)

    def test_deal_gold_amount_is_bound_at_protocol_boundary(self):
        protocol, response = self._network_fixture()
        choices = [dict(key='CHOICE_EXIT',disabled=False),
                   dict(key=public_diplomacy.SET_GOLD,disabled=False),
                   dict(key=public_diplomacy.FINALIZE,disabled=True)]
        native = private_catalogue(self.identity, 0, self.obs, choices)
        native['data']['deal_draft'] = dict(target_player_id=1, item_count=0, pending=False)
        native['data']['deal_gold'] = dict(amount=0, max_amount=147, response='none', finalize=None)
        native['unsupported'].append(public_diplomacy.DEAL_OTHER_TERMS_GAP)
        value = public_diplomacy.build(self.identity, 0, self.obs, controls(), native)
        self.assertEqual(value['schema'], public_diplomacy.DEAL_GOLD_SCHEMA)
        response['decisions'] = value
        with patch('civ6_host.runtime.network_protocol.player_map.validate'):
            validate_network_response(response, protocol, 'reset')
            protocol.accept_response(response)
            candidate = value['candidates'][1]
            selection = dict(decision_id=value['decision_id'],candidate_id=candidate['candidate_id'])
            request = dict(schema=NETWORK_SCHEMA, nonce=protocol.nonce,
                episode_id=self.identity.episode_id, game_generation=self.identity.game_generation,
                sequence=1, operation='act', player_id=0, selection=selection)
            for invalid in (None, {'amount': False}, {'amount': 0}, {'amount': 148}, {'amount': 17.0}):
                request['selection'] = dict(selection, parameters=invalid)
                with self.subTest(parameters=invalid), self.assertRaises(ValueError):
                    protocol.selected(request)
            request['selection'] = dict(selection, parameters={'amount': 147})
            self.assertEqual(protocol.validate(request), 'act')
            self.assertEqual(protocol.selected(request), dict(candidate['action'], amount=147))

    def test_settled_deal_stays_observable_and_only_offers_exit(self):
        from civ6_host.runtime.xp2_deal_gold import offer_choices

        gold = dict(amount=0,max_amount=3,response='settled',finalize=None)
        choices = [dict(key=key,disabled=disabled) for key,disabled in offer_choices(False,gold)]
        private = private_catalogue(self.identity,0,self.obs,choices)
        private['data']['deal_draft'] = dict(target_player_id=1,item_count=0,pending=False)
        private['data']['deal_gold'] = gold
        private['unsupported'].append(public_diplomacy.DEAL_OTHER_TERMS_GAP)
        decision = public_diplomacy.build(self.identity,0,self.obs,controls(),private)
        self.assertEqual(decision['deal_gold'],gold)
        self.assertEqual([row['action']['choice'] for row in decision['candidates']], ['CHOICE_EXIT'])
        with self.assertRaises(ValueError):
            public_diplomacy.resolve_gold_amount(
                decision,dict(choice=public_diplomacy.SET_GOLD),dict(amount=1))

    def test_recurring_gold_uses_its_own_limit_and_keeps_the_lump_sum(self):
        from civ6_host.runtime.xp2_deal_gold import offer_choices

        gold = dict(amount=90,max_amount=93,response='accepted',finalize='accept')
        recurring = dict(amount=3,max_amount=8,duration=30)
        choices = [dict(key=key,disabled=disabled) for key,disabled in offer_choices(False,gold,recurring)]
        private = private_catalogue(self.identity,0,self.obs,choices)
        private['data'].update(deal_draft=dict(target_player_id=1,item_count=2,pending=False),
                               deal_gold=gold,deal_recurring_gold=recurring)
        private['unsupported'].append(public_diplomacy.DEAL_OTHER_TERMS_GAP)
        decision = public_diplomacy.build(self.identity,0,self.obs,controls(),private)
        self.assertEqual(decision['schema'], public_diplomacy.DEAL_RECURRING_GOLD_SCHEMA)
        _, lump, recurring_edit, _ = (row['action'] for row in decision['candidates'])
        resolve = public_diplomacy.resolve_gold_amount
        self.assertEqual(resolve(decision,lump,{'amount':92}), dict(lump,amount=92))
        self.assertEqual(resolve(decision,recurring_edit,{'amount':0}), dict(recurring_edit,amount=0))
        for invalid in ({'amount':9}, {'amount':3}, {'amount':1,'duration':29}):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                resolve(decision,recurring_edit,invalid)

    def test_bilateral_gold_scope_uses_each_inventory_limit(self):
        from civ6_host.runtime.xp2_deal_gold import offer_choices

        offered = (dict(amount=0,max_amount=5,response='accepted',finalize='accept'),
                   dict(amount=6,max_amount=9,duration=30))
        requested = (dict(amount=13,max_amount=20), dict(amount=0,max_amount=0,duration=30))
        choices = [dict(key=key,disabled=disabled) for key,disabled in offer_choices(False,*offered,*requested)]
        private = private_catalogue(self.identity,0,self.obs,choices)
        private['data'].update(deal_draft=dict(target_player_id=1,item_count=2,pending=False),
                               **dict(zip(public_diplomacy.GOLD_TERM_FIELDS.values(), (*offered,*requested))))
        private['unsupported'].append(public_diplomacy.DEAL_OTHER_TERMS_GAP)
        value = public_diplomacy.build(self.identity,0,self.obs,controls(),private)
        self.assertEqual(value['schema'], public_diplomacy.DEAL_BILATERAL_GOLD_SCHEMA)
        actions = {row['action']['choice']: row['action'] for row in value['candidates']}
        resolve = public_diplomacy.resolve_gold_amount
        want = actions[public_diplomacy.SET_REQUESTED_GOLD]
        self.assertEqual(resolve(value,want,{'amount':20}), dict(want,amount=20))
        self.assertNotIn(public_diplomacy.SET_REQUESTED_RECURRING_GOLD, actions)
        with self.assertRaises(ValueError):
            resolve(value,actions[public_diplomacy.SET_GOLD],{'amount':20})

    def test_resource_parameters_are_bound_to_the_visible_inventory_row(self):
        from civ6_host.runtime.xp2_deal_gold import offer_choices

        terms = (dict(amount=0,max_amount=5,response='none',finalize='propose'),
                 dict(amount=0,max_amount=9,duration=30), dict(amount=0,max_amount=20),
                 dict(amount=0,max_amount=0,duration=30))
        outgoing = dict(direction='outgoing',resource_index=4,resource_type='RESOURCE_SILK',
                        class_type='RESOURCECLASS_LUXURY',amount=0,max_amount=1,duration=None,available=True)
        incoming = dict(outgoing,direction='incoming',resource_index=42,resource_type='RESOURCE_IRON',
                        class_type='RESOURCECLASS_STRATEGIC',amount=1,max_amount=0,duration=30,available=False)
        rows = [outgoing,incoming]
        raw = offer_choices(False,*terms)
        raw[-1:-1] = public_diplomacy.resource_choices(rows, settled=False)
        choices = [dict(key=key,disabled=disabled) for key,disabled in raw]
        private = private_catalogue(self.identity,0,self.obs,choices)
        private['data'].update(deal_draft=dict(target_player_id=1,item_count=1,pending=False), deal_resources=rows,
                               **dict(zip(public_diplomacy.GOLD_TERM_FIELDS.values(),terms)))
        private['unsupported'].append(public_diplomacy.DEAL_OTHER_TERMS_GAP)
        value = public_diplomacy.build(self.identity,0,self.obs,controls(),private)
        self.assertEqual(value['schema'],public_diplomacy.DEAL_RESOURCE_SCHEMA)
        actions = {row['action']['choice']:row['action'] for row in value['candidates']}
        give, take = (actions[choice] for choice in public_diplomacy.RESOURCE_CHOICES)
        resolve = public_diplomacy.resolve_gold_amount
        self.assertEqual(resolve(value,give,dict(resource_index=4,amount=1)),dict(give,resource_index=4,amount=1))
        self.assertEqual(resolve(value,take,dict(resource_index=42,amount=0)),dict(take,resource_index=42,amount=0))
        for action, index, amount in ((take,4,1),(take,42,2),(give,4,2),(give,False,1),(give,4,True)):
            with self.subTest(index=index,amount=amount), self.assertRaises(ValueError):
                resolve(value,action,dict(resource_index=index,amount=amount))
        raw[-3:-1] = public_diplomacy.resource_choices(rows, settled=False, can_edit=False)
        choices = [dict(key=key,disabled=disabled) for key,disabled in raw]
        limited = private_catalogue(self.identity,0,self.obs,choices)
        limited['data'].update({key:private['data'][key] for key in (*public_diplomacy.GOLD_TERM_FIELDS.values(),
                                                                   'deal_draft','deal_resources')})
        limited['unsupported'].extend((public_diplomacy.DEAL_OTHER_TERMS_GAP, public_diplomacy.DEAL_RESOURCE_WRITE_GAP))
        read_only = public_diplomacy.build(self.identity,0,self.obs,controls(),limited)
        self.assertEqual(read_only['deal_resources'],rows)
        self.assertTrue(all(row['action']['choice'] not in public_diplomacy.RESOURCE_CHOICES
                            for row in read_only['candidates']))
        with self.assertRaises(ValueError):
            resolve(read_only,give,dict(resource_index=4,amount=1))

    def test_negotiation_offer_and_result_are_public_without_wire_fields(self):
        from civ6_host.runtime.xp2_deal_gold import offer_choices

        modal = public_diplomacy
        for response, finalize, available, has_items in (
                ('rejected',None,True,True), ('adjusted','accept',False,True),
                ('adjusted',None,False,False), ('equalize_failed',None,False,True)):
            with self.subTest(response=response, has_items=has_items):
                terms = (dict(amount=3 if has_items else 0,max_amount=8,response=response,finalize=finalize),
                         dict(amount=0,max_amount=2,duration=30), dict(amount=int(has_items),max_amount=10),
                         dict(amount=0,max_amount=0,duration=30))
                raw = offer_choices(False, *terms)
                raw[-1:-1] = [*modal.resource_choices([], settled=False), (modal.EQUALIZE, not available)]
                private = private_catalogue(self.identity,0,self.obs,[dict(key=k,disabled=d) for k,d in raw])
                private['data'].update(deal_draft=dict(target_player_id=1,item_count=2*int(has_items),pending=False),
                                       deal_resources=[], deal_equalize=available,
                                       **dict(zip(modal.GOLD_TERM_FIELDS.values(),terms)))
                private['unsupported'].append(modal.DEAL_OTHER_TERMS_GAP)
                public = modal.build(self.identity,0,self.obs,controls(),private)
                self.assertEqual(public['schema'],modal.DEAL_NEGOTIATION_SCHEMA)
                self.assertEqual(public['deal_gold']['response'],response)
                self.assertEqual(public['deal_requested_gold']['amount'],int(has_items))
                self.assertNotIn('secret', json.dumps(public))
                actions = {r['action']['choice']:r['action'] for r in public['candidates']}
                self.assertEqual(modal.EQUALIZE in actions, available)
                self.assertEqual(modal.FINALIZE in actions, finalize is not None)
                if available:
                    action = actions[modal.EQUALIZE]
                    self.assertEqual(modal.resolve_gold_amount(public,action,None),action)
                    with self.assertRaises(ValueError):
                        modal.resolve_gold_amount(public,action,{'amount':1})
                forged = copy.deepcopy(public)
                forged['deal_equalize'] = not available
                forged['decision_id'] = modal.digest({k:v for k,v in forged.items() if k!='decision_id'})
                with self.assertRaises(ValueError):
                    modal.validate(forged,self.identity,0,self.obs['turn'],player_id=0,observation=self.obs)

    def test_peace_confirmation_depends_on_native_acceptance_and_locked_items(self):
        from civ6_host.runtime.xp2_deal_gold import offer_choices

        modal = public_diplomacy
        treaty = [dict(direction=side,duration=0,locked=True) for side in ('outgoing','incoming')]
        borders = [dict(direction=side,duration=None,available_duration=None) for side in ('outgoing','incoming')]
        for response, finalizer, equalize in (
                ('rejected',None,True), ('adjusted','accept',False), ('settled',None,False), ('none','accept',False)):
            with self.subTest(response=response):
                settled = response=='settled'
                gold = (dict(amount=0 if settled else 5,max_amount=17,response=response,finalize=finalizer),
                        dict(amount=0,max_amount=0,duration=30), dict(amount=0,max_amount=0),
                        dict(amount=0,max_amount=0,duration=30))
                raw = offer_choices(False,*gold)
                raw[-1:-1] = [*modal.resource_choices([],settled=settled),
                              *modal.open_borders_choices(borders,settled=settled), (modal.EQUALIZE,not equalize)]
                private = private_catalogue(self.identity,0,self.obs,[dict(key=k,disabled=d) for k,d in raw])
                private['data'].update(deal_draft=dict(target_player_id=1,item_count=0 if settled else 3,pending=False),
                    deal_peace=treaty,deal_open_borders=borders,deal_resources=[],deal_equalize=equalize,
                    **dict(zip(modal.GOLD_TERM_FIELDS.values(),gold)))
                private['unsupported'].append(modal.DEAL_OTHER_TERMS_GAP)
                if response=='none':
                    with self.assertRaisesRegex(ValueError,'Malformed public gold deal'):
                        modal.build(self.identity,0,self.obs,controls(),private)
                    continue
                public = modal.build(self.identity,0,self.obs,controls(),private)
                self.assertEqual(public['schema'],modal.DEAL_PEACE_NEGOTIATION_SCHEMA)
                actions = {row['action']['choice'] for row in public['candidates']}
                self.assertEqual(modal.FINALIZE in actions, finalizer=='accept')
                self.assertEqual(modal.EQUALIZE in actions, equalize)
                if settled:
                    self.assertEqual(actions, {'CHOICE_EXIT'})
                    self.assertEqual(public['deal_peace'], treaty)

    def test_native_demand_only_exposes_counterparty_terms_and_submission(self):
        from civ6_host.runtime.xp2_deal_gold import offer_choices
        modal = public_diplomacy
        for response, finalize in (('none','demand'),('rejected',None),('settled',None)):
            terms = (dict(amount=0,max_amount=0,response=response,finalize=finalize),
                     dict(amount=0,max_amount=0,duration=30),dict(amount=1,max_amount=10),
                     dict(amount=0,max_amount=3,duration=30))
            raw = offer_choices(False,*terms,demand=True)
            raw[-1:-1] = modal.resource_choices([],settled=response!='none')
            private = private_catalogue(self.identity,0,self.obs,[dict(key=k,disabled=d) for k,d in raw])
            private['data'].update(deal_draft=dict(target_player_id=1,item_count=1,pending=False),
                                   deal_demand=True, deal_resources=[],
                                   **dict(zip(modal.GOLD_TERM_FIELDS.values(),terms)))
            private['unsupported'].append(modal.DEAL_OTHER_TERMS_GAP)
            public = modal.build(self.identity,0,self.obs,controls(),private)
            self.assertEqual(public['schema'],modal.DEAL_DEMAND_SCHEMA)
            keys = {row['action']['choice'] for row in public['candidates']}
            self.assertNotIn(modal.EQUALIZE,keys)
            self.assertNotIn(modal.SET_GOLD,keys)
            self.assertEqual(modal.FINALIZE in keys,response=='none')
            if response!='none':
                self.assertEqual(keys,{'CHOICE_EXIT'})

    def _network_fixture(self):
        protocol = NetworkProtocol(self.identity, 'a' * 32, initial_turn=10)
        return protocol, self._network_reply(protocol, 'reset', 0)

    def _network_reply(self, protocol, operation, sequence, *, status='none', selected=None):
        obs = dict(player_id=0, turn=10)
        decisions = public_catalogue(self.identity, sequence, obs=self.obs,
            controls_value=controls(active=False))
        native = dict(schema='civ6rl.native_victory_episode.observation.v1',
            episode_id=self.identity.episode_id, game_generation=self.identity.game_generation,
            policy_id=POLICY_ID, source_proof_sha256=PROOF_SHA256,
            facts_source_proof_sha256=FACTS_SHA, player_id=0,
            observation_only=True, eligible_for_training=False, exposed_to_learner=False,
            global_engine_terminal=None, engine_halted=None, episode_terminated=False,
            winner_present=False, current_game_turn=10)
        requested = selected if operation == 'act' else None
        return dict(stage='official_session_response', schema=NETWORK_SCHEMA,
            nonce=protocol.nonce, episode_id=self.identity.episode_id,
            game_generation=self.identity.game_generation, sequence=sequence,
            operation=operation, observation=obs, rounds=0,
            outcome=outcome(native, 0, protocol.limit), automatic_choices_applied=False,
            action_interface_complete=False, strategic_training_ready=False,
            decisions=decisions, applied_action=None, session=dict(game_mode='LAN',
                turn_phase='TURNPHASE_SIMULTANEOUS', turn=10, local_player_id=0,
                human_player_ids=[0], active_human_player_ids=[]),
            command_result=dict(status=status, reason=None, requested_action=requested))

    def test_session_client_reset_and_inactive_dialogue_response(self):
        class Backend:
            def __init__(self):
                self.episode = None
                self.nonce = None
                self.sequence = 0
                self.aborts = []

            def _reply(self, operation, sequence, action=None):
                current = SimpleNamespace(episode_id=self.episode,
                    game_generation='native-' + self.episode)
                return self_owner._client_reply(self, current, operation, sequence, action)

            def reset(self):
                self.episode = str(uuid4()); self.nonce = uuid4().hex
                return self._reply('reset', 0)

            def request(self, request):
                self.sequence = request['sequence']
                prior = client._views[request['player_id']]['decisions']
                action = next(row['action'] for row in prior['candidates']
                    if row['candidate_id'] == request['selection']['candidate_id'])
                return self._reply('act', self.sequence, action)

            def abort(self, reason):
                self.aborts.append(reason)

        self_owner = self
        backend = Backend()
        client = SessionClient(backend)
        initial = client.reset()
        action = initial['decisions']['candidates'][0]['action']
        result = client.act(0, initial['decisions']['decision_id'],
                            initial['decisions']['candidates'][0]['candidate_id'])
        self.assertEqual(result['decisions']['schema'], public_diplomacy.SCHEMA)
        self.assertEqual(backend.aborts, [])

    def _client_reply(self, backend, identity, operation, sequence, action=None):
        obs = observation()
        decisions = public_catalogue(identity, sequence, obs=obs,
            controls_value=controls(active=False))
        return dict(stage='official_session_response', schema=SESSION_SCHEMA,
            nonce=backend.nonce, episode_id=backend.episode,
            game_generation='native-' + backend.episode, sequence=sequence,
            operation=operation, observation=obs, rounds=0,
            outcome=dict(terminated=False, truncated=False, reason=None),
            automatic_choices_applied=False, action_interface_complete=False,
            strategic_training_ready=False, decisions=decisions, applied_action=None,
            session=dict(game_mode='LAN', turn_phase='TURNPHASE_SIMULTANEOUS', turn=10,
                local_player_id=0, human_player_ids=[0], active_human_player_ids=[]),
            command_result=dict(status='refused' if action else 'none', reason=None,
                requested_action=action))

    def test_remote_client_validates_public_dialogue_without_native_resources(self):
        backend=SimpleNamespace(episode=self.identity.episode_id,nonce='a'*32)
        reply=self._client_reply(backend,self.identity,'reset',0)
        environment=dict(os.environ)
        for key in tuple(environment):
            if key.startswith(('CIV6_HOST_','CIV6RL_')):environment.pop(key)
        environment['PYTHONPATH']=str(Path(__file__).resolve().parents[1]/'src')
        code='''import json,sys
from civ6_host.session_client import SessionClient
class Backend:
 def reset(self):return json.load(sys.stdin)
 def abort(self,reason):raise AssertionError(reason)
view=SessionClient(Backend()).reset()
assert view['decisions']['schema']=='civ6-host.network-diplomacy-decisions.v1'
assert not any(name.startswith('civ6_host.runtime') for name in sys.modules)
'''
        result=subprocess.run([sys.executable,'-P','-c',code],env=environment,
            input=json.dumps(reply),text=True,capture_output=True,timeout=20)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)


if __name__ == '__main__':
    unittest.main()
