"""Public additive composition and real SessionClient, without native calls."""
from copy import deepcopy
import json
from types import SimpleNamespace
import unittest

from civ6_host import InformationUnavailable, ProtocolError, SessionClient
from civ6_host.contracts import network_turn as network, religion_beliefs as contract
from civ6_host.runtime.configuration_profiles import XP1_CORE_SHA256, XP2_CORE_SHA256
from civ6_host.runtime.native import native_religion_observation as reader
from civ6_host.runtime.native import native_religion_beliefs as choices
from test_session_capabilities import seal
from test_xp1_city_religion import religion_fixture, ReligionBackend
from test_xp1_pantheon_public import offered as pantheon_offered


def state(obs, mode='offered'):
    pid,turn=obs['player_id'],obs['turn'];city=obs['cities'][0]['id']
    earned=1 if mode=='spent' else 2
    wire=(f'religion-observation-v1|{pid}|{turn}|3|1|{earned}|{pid}|2|{city}|1|3|{pid}|1|24'
          if mode!='absent' else f'religion-observation-v1|{pid}|{turn}|-1|1|0|-1|2|-1|0|-1|-1|0')
    own=contract.project_snapshot(reader.parse_observation(wire.encode(),pid,turn),pid,turn,observation=obs)
    sub=None
    if mode!='absent':
        wire=(f'not_due,{pid},{turn},3,1,1,no_unspent_belief' if mode=='spent' else
              f'catalog,{pid},{turn},3,2,1,1,{choices.ADD_BELIEF},{choices.PARAM_BELIEF_TYPE},'
              f'{choices.PARAM_INSERT_MODE},{choices.VALUE_EXCLUSIVE},1,2,o24,'
              'c34:888:BELIEF_CLASS_FOUNDER,c36:999:BELIEF_CLASS_ENHANCER')
        sub=json.loads(json.dumps(choices.parse_catalog(wire.encode(),pid,turn)))
    return dict(schema=contract.SCHEMA,player_id=pid,turn=turn,own=own,beliefs=sub)


def validate(obs, value, *, closed=False):
    seal(value)
    identity=SimpleNamespace(episode_id=value['episode_id'],game_generation=value['game_generation'])
    return network.validate_capability_catalogue(value,identity,value['sequence'],obs['turn'],
        player_id=obs['player_id'],observation=obs,actions_closed=closed)


def unavailable(value, *, closed=False):
    value['candidates']=[]
    for name in value['families']:
        if name!='other_human_actions':
            value['families'][name]=dict(status='unqualified',reason='session_closed' if closed else 'native_actor_waiting')
    for name in ('choice_state','world_input','queued_orders','unit_orders','unit_attacks','production_queues',
                 'placement_offers','placements','placement_observation_scope','captured_city','city_shots',
                 'district_shots','governors','envoys','city_state_envoys','city_state_levies','unit_levies','dedications',
                 'plot_purchases','city_purchases','production_current','production_info'):
        if name in value:value[name]=None
    value['turn_availability']={name:None for name in ('end_turn','force_end_turn','unready_turn')}
    if not closed:value['turn_controls'].update(active=False,active_complete=False)
    return value


def terminal_v11(value):
    # Exact retained terminal shape: v11, nonnull own observation, no optional
    # live family. Official trace contents are not copied into this fixture.
    keep={'schema','episode_id','game_generation','sequence','player_id','turn','turn_controls',
          'candidates','choice_state','turn_availability','world_input','queued_orders','unit_orders',
          'unit_attacks','production_queues','placement_offers','placements','placement_observation_scope',
          'placement_inventory','families','family_inventory_complete','complete_action_space','decision_id'}
    result=deepcopy({k:v for k,v in value.items() if k in keep})
    result['schema']=network.CAPABILITY_COMBAT_READINESS_SCHEMA
    names={'found_city','research','civic','production','end_turn','force_end_turn','unready_turn',
           'world_deselect_unit','world_plot_click','world_select_unit','queue_append','queue_remove',
           'queue_swap','production_placement','production_resume','unit_order','unit_attack','other_human_actions'}
    result['families']={k:v for k,v in result['families'].items() if k in names}
    return seal(unavailable(result,closed=True))


class BeliefsBackend(ReligionBackend):
    def __init__(self, *, mode='offered', pantheon=True, waiting=False):
        super().__init__();self.mode=mode;self.with_pantheon=pantheon;self.waiting=waiting

    def _reply(self,operation,sequence,player,requested=None):
        if operation=='close':
            value=super()._reply('observe',sequence,player,requested)
            closed=super()._reply('close',sequence,player,requested)
            value.update(operation='close',outcome=closed['outcome'])
            value['decisions']=terminal_v11(value['decisions'])
            return value
        value=super()._reply(operation,sequence,player,requested)
        dec,obs=value['decisions'],value['observation']
        if self.waiting:
            unavailable(dec);value['session']['active_human_player_ids']=[]
        if self.with_pantheon:
            network.add_xp1_pantheon(dec,None if self.waiting else pantheon_offered(obs))
        network.add_xp1_religion_beliefs(dec,None if self.waiting else state(obs,self.mode))
        seal(dec)
        return value


class XP1ReligionBeliefsPublicTests(unittest.TestCase):
    def test_independent_wrappers_preserve_all_existing_families_and_projection(self):
        obs,_,_,city=religion_fixture()
        for include_pantheon in (False,True):
            prior=deepcopy(city)
            if include_pantheon:network.add_xp1_pantheon(prior,pantheon_offered(obs));seal(prior)
            value=deepcopy(prior);native=state(obs)
            network.add_xp1_religion_beliefs(value,state=native);validate(obs,value)
            self.assertEqual(value['candidates'][:-2],prior['candidates'])
            self.assertEqual({k:v for k,v in value['families'].items() if k!='add_belief'},prior['families'])
            self.assertEqual(value['schema'] in network.XP1_PANTHEON_SCHEMAS,include_pantheon)
            projected,receipt=network.checkpoint_catalogue(value,prior,obs,core_sha256=XP1_CORE_SHA256)
            self.assertEqual(projected,prior)
            self.assertEqual(receipt['added_public_fields'],['religion_beliefs'])
            self.assertEqual(receipt['added_action_families'],['add_belief'])
            projected,receipt=network.checkpoint_catalogue(value,city,obs,core_sha256=XP1_CORE_SHA256)
            self.assertEqual(projected,city)
            self.assertEqual(receipt['added_action_families'],(['pantheon'] if include_pantheon else [])+['add_belief'])
            with self.assertRaisesRegex(ValueError,'Rise and Fall'):
                network.checkpoint_catalogue(value,prior,obs,core_sha256=XP2_CORE_SHA256)
            changed=deepcopy(value);changed['choice_state']['research']['research']=123;seal(changed)
            self.assertNotEqual(network.checkpoint_catalogue(changed,prior,obs,core_sha256=XP1_CORE_SHA256)[0],prior)
            native['beliefs']['candidates'].clear()
            self.assertEqual(len(value['religion_beliefs']['beliefs']['candidates']),2)

    def test_client_information_offers_absence_spent_and_selection(self):
        for mode in ('offered','absent','spent'):
            backend=BeliefsBackend(mode=mode);client=SessionClient(backend,allow_administrative=True)
            frame=client.reset();info=client.information('religion_beliefs')
            self.assertEqual(info['data'],state(frame['observation'],mode))
            self.assertEqual(info['native_decision_id'],frame['decisions']['decision_id'])
            self.assertEqual(info['source_contracts'],dict(religion_beliefs=contract.SCHEMA,
                decision_catalogue=frame['decisions']['schema']))
            self.assertEqual(client.information('pantheon')['data'],pantheon_offered(frame['observation']))
            self.assertEqual(client.information('production')['data']['schema'],'civ6-host.production-inputs.v3')
            self.assertEqual(backend.calls,[])
            info['data']['own']['num_beliefs_earned']=999
            self.assertNotEqual(client.information('religion_beliefs')['data']['own']['num_beliefs_earned'],999)
            with self.assertRaises(InformationUnavailable):client.information('religion_beliefs',channel='administrative')
            with self.assertRaises(InformationUnavailable):client.information('religion_beliefs',player_id=1)
            if mode=='offered':
                offered=[row for row in frame['decisions']['candidates'] if row['action']['kind']=='add_belief']
                self.assertEqual([row['action'] for row in offered],contract.actions(state(frame['observation'])))
                client.act(0,frame['decisions']['decision_id'],offered[1]['candidate_id'])
            else:self.assertEqual(contract.actions(info['data']),[])
        legacy=SessionClient(ReligionBackend());legacy.reset()
        with self.assertRaises(InformationUnavailable):legacy.information('religion_beliefs')

    def test_waiting_and_reduced_v11_close_are_not_empty_belief_queries(self):
        waiting=SessionClient(BeliefsBackend(waiting=True));frame=waiting.reset()
        self.assertIsNone(frame['decisions']['religion_beliefs'])
        self.assertEqual(frame['decisions']['families']['add_belief']['status'],'unqualified')
        with self.assertRaises(InformationUnavailable):waiting.information('religion_beliefs')
        client=SessionClient(BeliefsBackend());client.reset();closed=client.close()
        self.assertIsNotNone(closed['observation'])
        self.assertEqual(closed['decisions']['schema'],network.CAPABILITY_COMBAT_READINESS_SCHEMA)
        self.assertNotIn('religion_beliefs',closed['decisions'])
        self.assertNotIn('pantheon',closed['decisions'])
        self.assertEqual(closed['decisions']['candidates'],[])
        with self.assertRaises(InformationUnavailable):client.information('religion_beliefs')
        with self.assertRaises(ValueError):network.add_xp1_religion_beliefs(closed['decisions'],None,actions_closed=True)

    def test_exact_offer_set_status_and_actor_are_validated(self):
        obs,_,_,prior=religion_fixture();value=deepcopy(prior)
        network.add_xp1_religion_beliefs(value,state(obs));validate(obs,value)
        for change in ('missing_offer','extra_offer','partial','schema','actor'):
            bad=deepcopy(value)
            if change=='missing_offer':bad['candidates'].pop();bad['families']['add_belief']['candidate_ids'].pop()
            elif change=='extra_offer':
                action=dict(kind='add_belief',index=99,hash=99,**{'class':'BELIEF_CLASS_WORSHIP'})
                key=network.digest(action);bad['candidates'].append(dict(candidate_id=key,action=action))
                bad['families']['add_belief']['candidate_ids'].append(key)
            elif change=='partial':bad['families']['add_belief'].update(status='queried_partial',unqualified=['omitted'])
            elif change=='schema':bad['schema']=prior['schema']
            else:bad['religion_beliefs']['player_id']=True
            with self.subTest(change=change),self.assertRaises(ValueError):validate(obs,bad)
        client=SessionClient(BeliefsBackend());client.reset()
        client._views[0]['decisions']['religion_beliefs']['turn']+=1
        with self.assertRaises(ProtocolError):client.information('religion_beliefs')


if __name__=='__main__':unittest.main()
