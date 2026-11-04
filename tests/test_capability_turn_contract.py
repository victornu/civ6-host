"""Turn capability v3 joins provider booleans without inventing native gates."""
from copy import deepcopy
from types import SimpleNamespace
import unittest
from civ6_host.contracts import network_turn as contract
from test_session_capabilities import catalogue,observation,seal,CapabilityBackend,SessionClient

KINDS=('end_turn','force_end_turn','unready_turn')


class TurnCapabilities(unittest.TestCase):
    def setUp(self):
        self.identity=SimpleNamespace(episode_id='turn-episode',game_generation='turn-generation')
        self.obs=observation()

    def value(self,*,waiting=False,closed=False,availability=(False,True,None)):
        value=catalogue(self.identity,queried=not (waiting or closed))
        value['schema']=contract.CAPABILITY_TURNS_SCHEMA
        value['choice_state']=(None if waiting or closed else
            dict(research=dict(research=None,civic=None),production=[]))
        if waiting:value['turn_controls'].update(active_complete=False,can_unready=True)
        if closed:availability=(None,None,None)
        value['turn_availability']=dict(zip(KINDS,availability))
        for kind,available in value['turn_availability'].items():
            if available is None:
                family=dict(status='unqualified',reason='native_query_unavailable')
            else:
                rows=[]
                if available:
                    action=dict(kind=kind);rows.append(dict(candidate_id=contract.digest(action),action=action))
                value['candidates'].extend(rows)
                family=dict(status='queried_complete',candidate_ids=[r['candidate_id'] for r in rows])
            value['families'][kind]=family
        return seal(value)

    def validate(self,value,*,closed=False):
        return contract.validate_capability_catalogue(seal(value),self.identity,0,1,
            player_id=0,actions_closed=closed,observation=self.obs)

    def test_all_three_turn_shapes_and_selection_are_exact_and_schema_local(self):
        value=self.value(availability=(True,True,True));self.validate(value)
        for row in value['candidates']:
            selected=contract.select_capability(value,dict(decision_id=value['decision_id'],candidate_id=row['candidate_id']))
            self.assertEqual(selected,row['action'])
        self.assertIs(contract.LATEST_SCHEMA,contract.PRODUCTION_SCHEMA)
        self.assertFalse(value['complete_action_space']);self.assertFalse(value['family_inventory_complete'])
        for schema in (contract.CAPABILITY_SCHEMA,contract.CAPABILITY_CHOICES_SCHEMA):
            bad=deepcopy(value);bad['schema']=schema
            with self.subTest(schema=schema),self.assertRaises(ValueError):self.validate(bad)

    def test_waiting_allows_native_turn_queries_without_rederiving_legality(self):
        for availability in ((True,False,True),(False,False,False),(None,None,None)):
            value=self.value(waiting=True,availability=availability);self.validate(value)
            self.assertIsNone(value['choice_state'])
        # Native providers own these booleans; the contract adds no active,
        # can_unready, timer or strategic predicate beyond identity/shape.
        value=self.value(waiting=True,availability=(True,True,True))
        value['turn_controls'].update(active=False,can_unready=False,timer_elapsed=True)
        self.validate(value)
        for kind in ('found_city','research','civic','production'):
            bad=self.value(waiting=True)
            family=dict(status='queried_complete',candidate_ids=[])
            if kind=='production':family.update(status='queried_partial',unqualified=['placement'])
            bad['families'][kind]=family
            with self.subTest(kind=kind),self.assertRaisesRegex(ValueError,'acting boundary'):self.validate(bad)

    def test_false_is_completed_empty_and_none_is_unqualified_never_substituted(self):
        self.validate(self.value())
        mutations=(lambda v:v['turn_availability'].update(end_turn=None),
            lambda v:v['turn_availability'].update(end_turn=True),
            lambda v:v['turn_availability'].update(force_end_turn=False),
            lambda v:v['turn_availability'].update(unready_turn=False),
            lambda v:v['families']['unready_turn'].update(reason=' '),
            lambda v:v['families'].update(end_turn=dict(status='unqualified',reason='query_skipped')),
            lambda v:v['families']['force_end_turn'].update(status='queried_partial',unqualified=['unknown']))
        for mutate in mutations:
            value=self.value();mutate(value)
            with self.subTest(mutation=mutate),self.assertRaises(ValueError):self.validate(value)

    def test_strict_availability_types_keys_and_required_family_coverage(self):
        for wrong in (0,1,1.0,'true',[],{}):
            value=self.value();value['turn_availability']['end_turn']=wrong
            with self.subTest(value=wrong),self.assertRaises(ValueError):self.validate(value)
        for mutate in (lambda v:v['turn_availability'].pop('unready_turn'),
                lambda v:v['turn_availability'].update(extra=False),
                lambda v:v['families'].pop('end_turn'),
                lambda v:v.pop('turn_availability')):
            value=self.value();mutate(value)
            with self.subTest(mutation=mutate),self.assertRaises(ValueError):self.validate(value)

    def test_turn_candidates_have_only_kind_exact_digest_and_one_per_true_family(self):
        for mutate in (lambda v:v['candidates'][-1]['action'].update(player_id=0),
                lambda v:v['candidates'][-1]['action'].update(forced=True),
                lambda v:v['candidates'][-1].update(candidate_id='0'*64),
                lambda v:v['candidates'].append(deepcopy(v['candidates'][-1])),
                lambda v:v['families']['force_end_turn'].update(candidate_ids=[]),
                lambda v:v.update(turn=2),lambda v:v.update(player_id=True),
                lambda v:v.update(game_generation='other'),lambda v:v.update(family_inventory_complete=True)):
            value=self.value();mutate(value)
            with self.subTest(mutation=mutate),self.assertRaises(ValueError):self.validate(value)

    def test_closed_requires_all_unqualified_and_none_not_completed_empty(self):
        self.validate(self.value(closed=True),closed=True)
        for mutate in (lambda v:v['turn_availability'].update(end_turn=False),
                lambda v:v['families'].update(end_turn=dict(status='queried_complete',candidate_ids=[])),
                lambda v:v.update(choice_state=dict(research=dict(research=None,civic=None),production=[]))):
            value=self.value(closed=True);mutate(value)
            with self.subTest(mutation=mutate),self.assertRaises(ValueError):self.validate(value,closed=True)

    def test_v1_and_v2_retained_shapes_are_unchanged(self):
        value=catalogue(self.identity);self.validate(value)
        v2=deepcopy(value);v2['schema']=contract.CAPABILITY_CHOICES_SCHEMA
        v2['choice_state']=dict(research=dict(research=None,civic=0),production=[])
        self.validate(v2)
        for old in (value,v2):
            bad=deepcopy(old);bad['turn_availability']=dict.fromkeys(KINDS,None)
            with self.assertRaises(ValueError):self.validate(bad)

    def test_inactive_force_crosses_real_portable_client_and_server_without_applied_claim(self):
        fixture=self
        class WaitingBackend(CapabilityBackend):
            def _reply(self,operation,sequence,player,requested=None):
                response=super()._reply(operation,sequence,player,requested)
                fixture.identity=self.identity
                dec=fixture.value(waiting=True,availability=(False,True,False))
                dec.update(sequence=sequence)
                dec['turn_controls'].update(active=False,can_unready=False)
                response['decisions']=seal(dec)
                response['session']['active_human_player_ids']=[]
                return response
        backend=WaitingBackend();backend.status='submitted';client=SessionClient(backend)
        view=client.reset()
        for _ in range(2):
            dec=view['decisions']
            selected=next(row for row in dec['candidates'] if row['action']=={'kind':'force_end_turn'})
            view=client.act(0,dec['decision_id'],selected['candidate_id'])
            self.assertEqual(client.command_result['status'],'submitted')
            self.assertIsNone(view['applied_action'])
            self.assertFalse(view['decisions']['turn_controls']['active'])
        self.assertEqual(len(backend.calls),2)
        self.assertEqual(backend.aborts,[])

    def test_forced_exception_requires_the_exact_offered_v3_action(self):
        value=self.value(waiting=True)
        self.assertTrue(contract.offered_forced_turn(value,{'kind':'force_end_turn'}))
        for action in ({'kind':'end_turn'},{'kind':'force_end_turn','player_id':0}):
            self.assertFalse(contract.offered_forced_turn(value,action))
        value['turn_availability']['force_end_turn']=False
        self.assertFalse(contract.offered_forced_turn(value,{'kind':'force_end_turn'}))
        value['turn_availability']['force_end_turn']=True;value['candidates']=[]
        self.assertFalse(contract.offered_forced_turn(value,{'kind':'force_end_turn'}))
        value['schema']=contract.CAPABILITY_CHOICES_SCHEMA
        self.assertFalse(contract.offered_forced_turn(value,{'kind':'force_end_turn'}))

if __name__=='__main__':unittest.main()
