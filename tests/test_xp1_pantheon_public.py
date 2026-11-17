"""Public XP1 pantheon choices, checked without executing GameCore."""
from copy import deepcopy
from types import SimpleNamespace
import unittest

from civ6_host import InformationUnavailable, ProtocolError, SessionClient
from civ6_host.contracts import information, network_turn, pantheon
from civ6_host.runtime.configuration_profiles import XP1_CORE_SHA256, XP2_CORE_SHA256
from civ6_host.runtime.native import native_pantheon_actions
from test_session_capabilities import seal
from test_xp1_city_religion import religion_fixture, ReligionBackend


def offered(obs):
    # The retained native parser is the independent wire-format reference.
    pid, turn = obs['player_id'], obs['turn']
    value = native_pantheon_actions.parse_catalog(
        f'catalog,{pid},{turn},4294967195,4294967193,4294967191,4294967190,2,4:2147483648,7:77'.encode(), pid, turn)
    value['choices'] = list(value['choices'])
    return value


def validate(obs, value):
    seal(value)
    identity = SimpleNamespace(episode_id=value['episode_id'],game_generation=value['game_generation'])
    return network_turn.validate_capability_catalogue(value,identity,value['sequence'],obs['turn'],
                                                     player_id=obs['player_id'],observation=obs)


class PantheonBackend(ReligionBackend):
    def _reply(self, operation, sequence, player, requested=None):
        value = super()._reply(operation,sequence,player,requested)
        if operation != 'close':
            network_turn.add_xp1_pantheon(value['decisions'],offered(value['observation']))
            seal(value['decisions'])
        return value


class XP1PantheonPublicTests(unittest.TestCase):
    def test_native_wire_identity_and_not_due_are_preserved(self):
        obs,*_ = religion_fixture()
        value = offered(obs)
        self.assertIs(pantheon.validate(value,obs['player_id'],obs['turn']),value)
        self.assertEqual(pantheon.actions(value),[
            dict(kind='pantheon',index=4,hash=2147483648),dict(kind='pantheon',index=7,hash=77)])
        for reason in ('already_has_pantheon','cannot_create'):
            raw=f"not_due,{obs['player_id']},{obs['turn']},{reason}".encode()
            state=native_pantheon_actions.parse_catalog(raw,obs['player_id'],obs['turn'])
            self.assertIs(pantheon.validate(state,obs['player_id'],obs['turn']),state)
            self.assertEqual(pantheon.actions(state),[])

    def test_foreign_ambiguous_and_hidden_fields_refuse(self):
        obs,*_ = religion_fixture()
        for change in ('actor','turn','bool_index','negative_hash','duplicate_hash','order','extra','keys'):
            value=offered(obs)
            if change=='actor':value['player_id']+=1
            elif change=='turn':value['current_game_turn']+=1
            elif change=='bool_index':value['choices'][0]['index']=True
            elif change=='negative_hash':value['choices'][0]['hash']=-1
            elif change=='duplicate_hash':value['choices'][1]['hash']=value['choices'][0]['hash']
            elif change=='order':value['choices'].reverse()
            elif change=='extra':value['hidden_belief_weights']=[99]
            else:value['insert_key']=value['parameter_key']
            with self.subTest(change=change),self.assertRaises(ValueError):
                pantheon.validate(value,obs['player_id'],obs['turn'])

    def test_all_choices_round_trip_without_filtering_or_mutating_history(self):
        obs,_,_,before=religion_fixture()
        value=deepcopy(before);native=offered(obs)
        network_turn.add_xp1_pantheon(value,native);validate(obs,value)
        self.assertEqual(value['candidates'][:-2],before['candidates'])
        selected=network_turn.select_capability(value,dict(decision_id=value['decision_id'],
            candidate_id=value['candidates'][-1]['candidate_id']))
        self.assertEqual(selected,dict(kind='pantheon',index=7,hash=77))
        projected,receipt=network_turn.checkpoint_catalogue(value,before,obs,core_sha256=XP1_CORE_SHA256)
        self.assertEqual(projected,before)
        self.assertEqual(receipt['added_public_fields'],['pantheon'])
        self.assertEqual(receipt['added_action_families'],['pantheon'])
        self.assertEqual(network_turn.checkpoint_catalogue(value,value,obs,core_sha256=XP1_CORE_SHA256),(value,None))
        with self.assertRaisesRegex(ValueError,'Rise and Fall'):
            network_turn.checkpoint_catalogue(value,before,obs,core_sha256=XP2_CORE_SHA256)
        native['choices'].clear()
        self.assertEqual(len(value['pantheon']['choices']),2)
        changed=deepcopy(value);changed['choice_state']['research']['research']=123;seal(changed)
        self.assertNotEqual(network_turn.checkpoint_catalogue(changed,before,obs,core_sha256=XP1_CORE_SHA256)[0],before)

    def test_missing_choice_and_fabricated_query_status_refuse(self):
        obs,_,_,before=religion_fixture()
        original=deepcopy(before);network_turn.add_xp1_pantheon(original,offered(obs));validate(obs,original)
        for change in ('remove','extra','partial','old_schema','missing_state'):
            value=deepcopy(original)
            if change=='remove':
                value['candidates'].pop();value['families']['pantheon']['candidate_ids'].pop()
            elif change=='extra':
                row=dict(action=dict(kind='pantheon',index=9,hash=99))
                row['candidate_id']=network_turn.digest(row['action'])
                value['candidates'].append(row);value['families']['pantheon']['candidate_ids'].append(row['candidate_id'])
            elif change=='partial':
                value['families']['pantheon'].update(status='queried_partial',unqualified=['arbitrary_filter'])
            elif change=='old_schema':value['schema']=before['schema']
            else:del value['pantheon']
            with self.subTest(change=change),self.assertRaises(ValueError):validate(obs,value)

    def test_unqueried_boundary_is_not_an_empty_native_catalogue(self):
        obs,_,_,before=religion_fixture()
        with self.assertRaises(ValueError):network_turn.add_xp1_pantheon(deepcopy(before),None)
        with self.assertRaises(ValueError):
            network_turn.add_xp1_pantheon(deepcopy(before),offered(obs),actions_closed=True)
        value=deepcopy(before);network_turn.add_xp1_pantheon(value,None,actions_closed=True)
        self.assertIsNone(value['pantheon'])
        self.assertEqual(value['families']['pantheon'],dict(status='unqualified',reason='session_closed'))
        self.assertEqual(value['candidates'],before['candidates'])

    def test_client_information_and_selection_are_at_the_same_boundary(self):
        backend=PantheonBackend();client=SessionClient(backend,allow_administrative=True)
        frame=client.reset();result=client.information('pantheon')
        self.assertEqual(result['data'],offered(frame['observation']))
        self.assertEqual(result['native_decision_id'],frame['decisions']['decision_id'])
        self.assertEqual(result['source_contracts'],{'decision_catalogue':frame['decisions']['schema']})
        self.assertEqual(backend.calls,[])
        result['data']['choices'].clear()
        self.assertEqual(len(client.information('pantheon')['data']['choices']),2)
        with self.assertRaises(InformationUnavailable):client.information('pantheon',channel='administrative')
        with self.assertRaises(InformationUnavailable):client.information('pantheon',player_id=1)
        self.assertEqual(client.information('production')['data']['schema'],'civ6-host.production-inputs.v3')
        self.assertEqual(client.information('city_religion')['data']['cities'][0]['majority_religion'],-1)
        action=frame['decisions']['candidates'][-1]
        client.act(frame['observation']['player_id'],frame['decisions']['decision_id'],action['candidate_id'])
        client._views[0]['decisions']['pantheon']['player_id']=1
        with self.assertRaises(ProtocolError):client.information('pantheon')
        legacy=SessionClient(ReligionBackend());legacy.reset()
        with self.assertRaises(InformationUnavailable):legacy.information('pantheon')


if __name__=='__main__':unittest.main()
