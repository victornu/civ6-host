"""Public choice groups, immutable retained v1, and no raw precision leakage."""
from copy import deepcopy
from types import SimpleNamespace as NS
import unittest
from unittest.mock import Mock, patch

from civ6_host.contracts import network_turn as contract
from civ6_host.contracts.capability_choices import project_state, validate_state
from civ6_host.runtime.xp1_continuation import validate_command, validate_unit_command
from civ6_host.runtime.workers.network_worker import _execute_xp1
from test_session_capabilities import catalogue, observation, seal


class ChoiceContracts(unittest.TestCase):
    def test_shared_telemetry_keeps_kind_in_payload_without_argument_collision(self):
        import ast
        from pathlib import Path
        from civ6_host.runtime import xp1_saved_load_composition as composition
        tree=ast.parse(Path(composition.__file__).read_text())
        owner=next(n for n in tree.body if isinstance(n,ast.FunctionDef)
                   and n.name=='compose_saved_load_services')
        emit=next(n for n in owner.body if isinstance(n,ast.FunctionDef) and n.name=='emit')
        backend=NS(emit=Mock());namespace={'backend':backend}
        exec(compile(ast.Module(body=[emit],type_ignores=[]),'<actual-shared-emitter>','exec'),namespace)
        namespace['emit']('native_player_research_catalog_observed',kind='research',event_name='choice')
        backend.emit.assert_called_once_with('native_player_research_catalog_observed',
                                            kind='research',gameplay_event_name='choice')
        with self.assertRaisesRegex(ValueError,'Ambiguous'):
            namespace['emit']('event',kind='civic',event_name='one',gameplay_event_name='two')

    def setUp(self):
        self.identity = NS(episode_id='same-episode', game_generation='same-generation')
        self.obs = observation()
        self.obs['cities'] = [dict(id=3, x=3, y=4, owner=0, population=1,
            yields=dict(food=2, production=1, gold=1, science=1, culture=1, faith=0))]
        self.value = catalogue(self.identity)
        self.value['schema'] = contract.CAPABILITY_CHOICES_SCHEMA
        self.value['choice_state'] = dict(research=dict(research=1, civic=None), production=[dict(
            city_id=3, queue_size=0, kind='N', item_index=None, hash=0, formation=None)])
        for kind in ('research', 'civic', 'production'):
            action = (dict(kind=kind, index=2, hash=31) if kind != 'production' else
                dict(kind='production', city_id=3, category='unit', index=21,
                     hash=123, item_type='UNIT_WARRIOR'))
            candidate = dict(candidate_id=contract.digest(action), action=action)
            self.value['candidates'].append(candidate)
            self.value['families'][kind] = dict(status='queried_complete',
                                               candidate_ids=[candidate['candidate_id']])
        self.value['families']['production'].update(status='queried_partial',
                                                    unqualified=['placement', 'queue_editing'])
        seal(self.value)

    def validate(self, value):
        return contract.validate_capability_catalogue(seal(value), self.identity, 0, 1,
                                                       player_id=0, observation=self.obs)

    def test_all_explicit_choices_roundtrip_same_protocol_contract(self):
        self.validate(self.value)
        for row in self.value['candidates']:
            action = contract.select_capability(self.value, dict(
                decision_id=self.value['decision_id'], candidate_id=row['candidate_id']))
            validate_command(action)
            self.assertEqual(action, row['action'])
        with self.assertRaises(ValueError):
            validate_unit_command(self.value['candidates'][-1]['action'])
        legacy = catalogue(self.identity)
        contract.validate_capability_catalogue(legacy,self.identity,0,1,player_id=0,
                                               observation=observation())

    def test_partial_is_not_promoted_and_legacy_cannot_claim_new_actions(self):
        mutations = [lambda v:v['families']['production'].update(status='queried_complete'),
            lambda v:v['families']['production'].update(unqualified=[]),
            lambda v:v.update(schema=contract.CAPABILITY_SCHEMA),
            lambda v:v['choice_state']['production'][0].update(city_id=9),
            lambda v:v['choice_state']['production'][0].update(progress=0.125),
            lambda v:v['choice_state']['research'].update(civic=True),
            lambda v:v['candidates'][-1]['action'].update(city_id=9)]
        for mutate in mutations:
            bad = deepcopy(self.value); mutate(bad)
            with self.subTest(mutation=mutate), self.assertRaises(ValueError):
                self.validate(bad)

    def test_projection_excludes_raw_precise_values_without_inventing_public_estimates(self):
        native = dict(cities=[dict(city_id=3,queue_size=1,kind='U',item_index=21,
            current_production_hash=-1,formation=0,production_yield=123456,
            previous_production_hash=100,progress=123,cost=17,turns_left=8)])
        result = project_state(dict(research=None,civic=0),native)
        validate_state(result,{3})
        self.assertEqual(result['production'][0]['hash'],0xffffffff)
        self.assertFalse({'progress','cost','turns_left','production_yield'} & set(result['production'][0]))
        with self.assertRaises(ValueError): validate_state(result,{3},unavailable=True)

    def test_replacement_refuses_if_queue_changed_before_submission(self):
        action = self.value['candidates'][-1]['action']
        saved = NS(continuation=NS(explicit_production_snapshot={'old':1}), execute=Mock())
        def reread(*args):
            saved.continuation.explicit_production_snapshot={'new':2}
            return {}, {}, dict(candidates=[dict(action=action)])
        with patch('civ6_host.runtime.xp1_session_view.read',side_effect=reread):
            result=_execute_xp1(saved,action,0,3,'unused.json')
        self.assertEqual(result['reason'],'native_production_state_changed')
        saved.execute.assert_not_called()

    def test_unit_order_revalidation_refuses_only_when_native_offer_is_gone(self):
        action=dict(kind='unit_order',unit_id=17,route='command',
                    item_type='UNITCOMMAND_CANCEL',hash=123)
        saved=NS(continuation=NS(explicit_unit_orders={'old':1}),execute=Mock())
        def reread(*args):
            saved.continuation.explicit_unit_orders={'new':2}
            return {},{},dict(candidates=[])
        with patch('civ6_host.runtime.xp1_session_view.read',side_effect=reread):
            result=_execute_xp1(saved,action,0,3,'unused.json')
        self.assertEqual(result['reason'],'native_action_no_longer_available')
        saved.execute.assert_not_called()

    def test_unit_order_worker_requires_matching_native_effect_receipt(self):
        action=dict(kind='unit_order',unit_id=17,route='command',
                    item_type='UNITCOMMAND_CANCEL',hash=123)
        validate_command(action)
        saved=NS(continuation=NS(explicit_unit_orders={'same':1},observation=self.obs),
                 execute=Mock(),emit=Mock())
        saved.execute.return_value=dict(action=action,effect=dict(status='completed',
            observation=self.obs,receipt=dict(action=action)))
        def reread(*args):
            # A changed public catalogue does not make a still-legal explicit
            # unit command stale. The native adapter uses this fresh catalogue.
            saved.continuation.explicit_unit_orders={'refreshed':2}
            return {},self.obs,dict(candidates=[dict(action=action)])
        with patch('civ6_host.runtime.xp1_session_view.read',side_effect=reread), patch(
                'civ6_host.runtime.xp1_session_inputs._write_once',return_value={'fixture':True}):
            result=_execute_xp1(saved,action,0,3,'fixture/closure.json')
            self.assertEqual(result,dict(status='completed',reason=None,requested_action=action))
            saved.execute.assert_called_once_with(action)
            saved.execute.return_value['effect']['receipt']['action']=dict(action,unit_id=18)
            with self.assertRaisesRegex(RuntimeError,'matching native delivery'):
                _execute_xp1(saved,action,0,4,'fixture/closure.json')


if __name__ == '__main__': unittest.main()
