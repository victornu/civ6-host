"""XP2 own-city religion observation over existing public predecessors."""
from copy import deepcopy
from itertools import product
import unittest

from civ6_host import InformationUnavailable, SessionClient
from civ6_host.contracts import city_religion, information, network_turn as network
from civ6_host.runtime.configuration_profiles import XP1_CORE_SHA256, XP2_CORE_SHA256
from test_session_capabilities import seal
from test_xp1_city_religion_details_public import details, DetailsBackend as XP1DetailsBackend
from test_xp1_city_religion import ReligionBackend as XP1MajorityBackend
from test_xp2_religious_chain_public import preceding, added as add_chain, validate, ChainBackend
from test_xp2_pantheon_public import added as add_pantheon
from test_xp2_religious_unit_operations_public import permissions_preceding
from test_placement_inventory_pillage_public import details as pillage_details


def added(value,obs,*,empty=False):
    current=deepcopy(value)
    network.add_xp2_city_religion_details(current,details(obs,mode='empty' if empty else 'populated'))
    return seal(current)


class Backend(ChainBackend):
    def __init__(self,*,waiting=False,strategic=True,enabled=True,empty=False):
        super().__init__(options=(False,False,False),unit_operations=False)
        self.prior,self.obs=permissions_preceding(state='waiting' if waiting else 'active',strategic=strategic)
        self.enabled,self.empty=enabled,empty

    def _reply(self,operation,sequence,**kwargs):
        response=super()._reply(operation,sequence,**kwargs)
        value=response['decisions']
        if value is not None:
            response['session']['active_human_player_ids']=[0,1] if value['turn_controls']['active'] else [1]
            # Retained fixtures stand in for fresh reads at this boundary.
            for group in ('native_command_permissions', 'world_congress', 'world_congress_review'):
                snapshot = value.get(group)
                if snapshot is not None:
                    snapshot['sequence'] = value['sequence']
            seal(value)
            if operation!='close' and self.enabled:
                response['decisions']=added(value,response['observation'],empty=self.empty)
        return response


class XP2CityReligionPublicTests(unittest.TestCase):
    def test_exact_predecessors_and_independent_options_preserve_every_choice(self):
        mapping=network.XP2_CITY_RELIGION_DETAILS_SCHEMA_BY_BASE
        self.assertEqual(set(mapping),set(network.XP2_PANTHEON_SCHEMA_BY_BASE)|set(network.XP2_PANTHEON_SCHEMA_BY_BASE.values()))
        self.assertEqual(len(mapping),1280)
        self.assertFalse(set(mapping)&set(network.XP1_CITY_RELIGION_SCHEMAS))
        supported=set(network.SUPPORTED_SCHEMAS)
        memberships={name:set(getattr(network,name)) for name in (
            'PANTHEON_SCHEMAS','PROPHET_ACTIVATION_SCHEMAS','RELIGION_FOUNDING_SCHEMAS',
            'RELIGION_BELIEFS_SCHEMAS','RELIGIOUS_UNIT_OPERATIONS_SCHEMAS',
            'STOCK_TRADE_CAPABILITY_SCHEMAS','NATIVE_COMMAND_PERMISSIONS_SCHEMAS')}
        for base,new in mapping.items():
            self.assertEqual(network._capability_version(base),network._capability_version(new))
            self.assertIn(new,supported)
            for name,schemas in memberships.items():
                self.assertEqual(base in schemas,new in schemas,(name,base))
        predecessors=[preceding(index,unit_operations=True) for index in range(3)]
        for index,options,pantheon in product(range(3),product((False,True),repeat=3),(False,True)):
            prior,obs=predecessors[index]
            prior=add_chain(prior,obs,options=options)
            if pantheon:prior=add_pantheon(prior,obs)
            current=added(prior,obs);validate(current,obs)
            self.assertEqual(current['candidates'],prior['candidates'])
            self.assertEqual(current['families'],prior['families'])
            for key in set(prior)-{'schema','decision_id'}:self.assertEqual(current[key],prior[key])
            self.assertEqual(information.project('city_religion',obs,current),details(obs))
            with self.assertRaises(ValueError):network.add_xp2_city_religion_details(current,details(obs))

    def test_exact_own_roster_and_v2_fields_are_required_without_filtering(self):
        prior,obs=preceding(2)
        for fault in ('actor','turn','foreign_city','missing_city','unknown_field','fraction','v1','none'):
            current=added(prior,obs);value=current['city_religion']
            if fault=='actor':value['player_id']=True
            elif fault=='turn':value['turn']+=1
            elif fault=='foreign_city':value['cities'][0]['city_id']+=987654
            elif fault=='missing_city':value['cities'].pop()
            elif fault=='unknown_field':value['cities'][0]['outward_pressure']=0
            elif fault=='fraction':value['cities'][0]['religions'][0]['pressure_per_turn']=0.5
            elif fault=='v1':current['city_religion']=city_religion.project_majority(value,obs['player_id'],obs['turn'])
            else:current['city_religion']=None
            seal(current)
            with self.subTest(fault=fault),self.assertRaises(ValueError):validate(current,obs)
        current=added(prior,obs)
        current['city_religion']['cities'][0]['religions'][0].update(
            followers=-2147483648,pressure_per_turn=-8388608,lifetime_pressure=8388608)
        seal(current);validate(current,obs)
        shown=information.project('city_religion',obs,current)
        self.assertEqual(shown,current['city_religion'])
        for state in (None,city_religion.project_majority(details(obs),obs['player_id'],obs['turn'])):
            with self.assertRaises(ValueError):network.add_xp2_city_religion_details(deepcopy(prior),state)

    def test_checkpoint_removes_only_new_observation_and_composes_with_inventory_v2(self):
        prior,obs=preceding(2,unit_operations=True)
        prior=add_pantheon(add_chain(prior,obs),obs,'owned')
        current=added(prior,obs)
        projected,receipt=network.checkpoint_catalogue(current,prior,obs,core_sha256=XP2_CORE_SHA256)
        self.assertEqual(projected,prior)
        self.assertEqual(receipt['added_public_fields'],['city_religion'])
        self.assertEqual(receipt['added_action_families'],[])
        self.assertEqual(network.checkpoint_catalogue(current,current,obs,core_sha256=XP2_CORE_SHA256),(current,None))
        combined=deepcopy(current);combined['placement_inventory']=pillage_details(combined['placement_inventory']);seal(combined)
        projected,receipt=network.checkpoint_catalogue(combined,prior,obs,core_sha256=XP2_CORE_SHA256)
        self.assertEqual(projected,prior)
        self.assertEqual(receipt['added_public_fields'],['placement_inventory.rows[].pillaged','city_religion'])
        self.assertEqual(receipt['added_action_families'],[])
        changed=deepcopy(current);changed['city_religion']['cities'][0]['majority_religion']=99;seal(changed)
        self.assertIsNone(network.checkpoint_catalogue(changed,current,obs,core_sha256=XP2_CORE_SHA256)[1])
        self.assertNotEqual(changed,current)  # Same-version history remains strictly comparable.
        for core in (None,XP1_CORE_SHA256):
            with self.assertRaisesRegex(ValueError,'Gathering Storm'):
                network.checkpoint_catalogue(current,prior,obs,core_sha256=core)

    def test_client_information_active_waiting_permissions_empty_closed_and_xp1(self):
        for waiting,strategic,empty in product((False,True),repeat=3):
            backend=Backend(waiting=waiting,strategic=strategic,empty=empty)
            client=SessionClient(backend);frame=client.reset()
            shown=client.information('city_religion')
            self.assertEqual(shown['source_contracts']['city_religion'],city_religion.DETAILS_SCHEMA)
            self.assertEqual(shown['data'],details(frame['observation'],mode='empty' if empty else 'populated'))
            self.assertEqual(backend.calls,[])
            shown['data']['cities'].clear()
            self.assertEqual(client.information('city_religion')['data'],frame['decisions']['city_religion'])
            with self.assertRaises(InformationUnavailable):client.information('city_religion',player_id=1)
            client.observe(0)
            closed=client.close()
            self.assertEqual(closed['decisions']['schema'],network.CAPABILITY_COMBAT_READINESS_SCHEMA)
            self.assertNotIn('city_religion',closed['decisions'])
            with self.assertRaises(InformationUnavailable):client.information('city_religion')
        client=SessionClient(Backend(enabled=False));client.reset()
        with self.assertRaises(InformationUnavailable):client.information('city_religion')
        for backend,schema in ((XP1MajorityBackend(),city_religion.SCHEMA),
                               (XP1DetailsBackend(),city_religion.DETAILS_SCHEMA)):
            client=SessionClient(backend);client.reset()
            self.assertEqual(client.information('city_religion')['data']['schema'],schema)


if __name__=='__main__':unittest.main()
