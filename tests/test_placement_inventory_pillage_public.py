"""Additive placement pillage data; synthetic flags are not native evidence."""
from copy import deepcopy
from itertools import product
import unittest

from civ6_host import SessionClient
from civ6_host.contracts import network_turn as network, placement_inventory as inventory
from civ6_host.runtime.configuration_profiles import XP1_CORE_SHA256, XP2_CORE_SHA256
from test_capability_placement_inventory import PlacementInventoryContract, InventoryBackend
from test_session_capabilities import seal
from test_xp2_religious_chain_public import preceding, added as add_chain, validate as validate_xp2
from test_xp2_pantheon_public import added as add_pantheon


def details(value, *, pillaged=False):
    result=deepcopy(value)
    if result is not None:
        result['schema']=inventory.DETAILS_SCHEMA
        for row in result['rows']:
            row['pillaged']=pillaged if row['category']=='district' else None
    return result


class DetailsBackend(InventoryBackend):
    def _reply(self,operation,sequence,player,requested=None):
        value=super()._reply(operation,sequence,player,requested)
        if value['decisions'] is not None and 'placement_inventory' in value['decisions']:
            value['decisions']['placement_inventory']=details(value['decisions']['placement_inventory'],pillaged=True)
            seal(value['decisions'])
        return value


class PlacementPillagePublicTests(unittest.TestCase):
    def setUp(self):
        self.fixture=PlacementInventoryContract();self.fixture.setUp()
        self.obs=self.fixture.obs

    def current(self, **kwargs):
        value=self.fixture.value(**kwargs)
        value['placement_inventory']=details(value['placement_inventory'])
        return seal(value)

    def test_explicit_v2_pillage_has_no_inferred_completion_or_building_value(self):
        legacy=self.fixture.value()['placement_inventory']
        original=deepcopy(legacy)
        for complete,pillaged in product((False,True),repeat=2):
            value=details(legacy,pillaged=pillaged)
            value['rows'][0]['complete']=complete
            self.assertIs(inventory.validate(value,self.obs['player_id'],self.obs['turn'],observation=self.obs),value)
            self.assertIs(value['rows'][0]['pillaged'],pillaged)
            self.assertIsNone(value['rows'][1]['pillaged'])
            projected=inventory.project_legacy(value,self.obs['player_id'],self.obs['turn'],observation=self.obs)
            expected=deepcopy(legacy);expected['rows'][0]['complete']=complete
            self.assertEqual(projected,expected)
            projected['rows'].clear()
            self.assertEqual(len(value['rows']),2)
        self.assertEqual(legacy,original)
        self.assertEqual(inventory.project_legacy(legacy,self.obs['player_id'],self.obs['turn'],observation=self.obs),legacy)

    def test_v1_v2_strict_types_identity_visibility_and_unknown_fields(self):
        original=self.current()
        for fault in ('integer','nil','text','missing','building_bool','unknown_schema',
                      'unknown_field','foreign_city','hidden_plot','duplicate'):
            value=deepcopy(original);data=value['placement_inventory'];row=data['rows'][0]
            if fault=='integer':row['pillaged']=1
            elif fault=='nil':row['pillaged']=None
            elif fault=='text':row['pillaged']='false'
            elif fault=='missing':del row['pillaged']
            elif fault=='building_bool':data['rows'][1]['pillaged']=False
            elif fault=='unknown_schema':data['schema']='civ6-host.placement-inventory.v3'
            elif fault=='unknown_field':row['repair_cost']=12
            elif fault=='foreign_city':row['city_id']=987654
            elif fault=='hidden_plot':row.update(plot_id=29,x=5)
            else:data['rows'].append(deepcopy(row))
            with self.subTest(fault=fault),self.assertRaises(ValueError):self.fixture.validate(value)
        v1=self.fixture.value();v1['placement_inventory']['rows'][0]['pillaged']=False
        with self.assertRaises(ValueError):self.fixture.validate(v1)
        value=self.current();value['placement_inventory']['schema']=inventory.SCHEMA
        with self.assertRaises(ValueError):self.fixture.validate(value)

    def test_checkpoint_same_network_schema_projects_only_new_pillage_fields(self):
        saved=self.fixture.value();current=self.current();snapshot=deepcopy(current)
        current['placement_inventory']['rows'][0]['pillaged']=True;seal(current)
        projected,receipt=network.checkpoint_catalogue(current,saved,self.obs,core_sha256=XP2_CORE_SHA256)
        self.assertEqual(projected,saved)
        self.assertEqual(receipt['source_schema'],receipt['target_schema'])
        self.assertEqual(receipt['added_public_fields'],['placement_inventory.rows[].pillaged'])
        self.assertEqual(receipt['added_action_families'],[])
        self.assertEqual(receipt['public_schema_upgrades'],[dict(field='placement_inventory',
            source_schema=inventory.SCHEMA,target_schema=inventory.DETAILS_SCHEMA)])
        self.assertEqual(current['candidates'],saved['candidates'])
        self.assertEqual(current['families'],saved['families'])
        self.assertIs(current['placement_inventory']['rows'][0]['pillaged'],True)
        changed=deepcopy(current);changed['placement_inventory']['rows'][0]['complete']=True;seal(changed)
        comparable,_=network.checkpoint_catalogue(changed,saved,self.obs,core_sha256=XP2_CORE_SHA256)
        self.assertNotEqual(comparable,saved)  # The actual checkpoint caller rejects this mismatch.
        comparable,transition=network.checkpoint_catalogue(current,snapshot,self.obs,core_sha256=XP2_CORE_SHA256)
        self.assertIs(comparable,current);self.assertIsNone(transition)
        self.assertNotEqual(comparable,snapshot)  # Existing v2 pillage must compare exactly.
        for core in (None,XP1_CORE_SHA256):
            with self.assertRaisesRegex(ValueError,'Gathering Storm'):
                network.checkpoint_catalogue(current,saved,self.obs,core_sha256=core)
        downgraded,transition=network.checkpoint_catalogue(saved,current,self.obs,core_sha256=XP2_CORE_SHA256)
        self.assertIs(downgraded,saved);self.assertIsNone(transition);self.assertNotEqual(downgraded,current)

    def test_checkpoint_composes_with_religious_options_without_new_network_schemas(self):
        for index in range(3):
            prior,obs=preceding(index,unit_operations=True)
            self.assertIsInstance(prior['placement_inventory'],dict)
            current=add_pantheon(add_chain(prior,obs),obs,'owned')
            preceding_schema=current['schema']
            current['placement_inventory']=details(current['placement_inventory'],pillaged=True)
            seal(current);validate_xp2(current,obs)
            self.assertEqual(current['schema'],preceding_schema)
            projected,receipt=network.checkpoint_catalogue(current,prior,obs,core_sha256=XP2_CORE_SHA256)
            self.assertEqual(projected,prior)
            self.assertEqual(receipt['added_public_fields'][-1],'placement_inventory.rows[].pillaged')
            self.assertEqual(receipt['added_action_families'],['activate_prophet','found_religion','add_belief','pantheon'])
            self.assertEqual(len(network.XP2_PANTHEON_SCHEMA_BY_BASE),640)

    def test_real_client_preserves_v2_frame_waiting_unknown_and_legacy(self):
        for waiting in (False,True):
            legacy=InventoryBackend(waiting=waiting);legacy.city_fixture=True
            old_client=SessionClient(legacy);old=old_client.reset()
            backend=DetailsBackend(waiting=waiting);backend.city_fixture=True
            client=SessionClient(backend);frame=client.reset()
            value=frame['decisions']['placement_inventory']
            self.assertEqual(value['schema'],inventory.DETAILS_SCHEMA)
            self.assertIs(value['rows'][0]['pillaged'],True)
            self.assertIsNone(value['rows'][1]['pillaged'])
            self.assertEqual(frame['decisions']['candidates'],old['decisions']['candidates'])
            self.assertEqual(frame['decisions']['families'],old['decisions']['families'])
            self.assertEqual(inventory.project_legacy(value,0,frame['observation']['turn'],observation=frame['observation']),
                             old['decisions']['placement_inventory'])
            choice=next(r for r in frame['decisions']['candidates']
                        if r['action']['kind']==('force_end_turn' if waiting else 'production_resume'))
            if waiting:backend.status='refused'
            frame=client.act(0,frame['decisions']['decision_id'],choice['candidate_id'])
            self.assertEqual(frame['decisions']['placement_inventory']['schema'],inventory.DETAILS_SCHEMA)
            client.close();old_client.close()
        for kwargs in ({'waiting':True},{'closed':True}):
            value=self.current(**kwargs,unavailable=True)
            self.fixture.validate(value,closed=kwargs.get('closed',False))
            self.assertIsNone(value['placement_inventory'])
        self.assertIsNone(inventory.project_legacy(None,0,self.obs['turn'],observation=self.obs))


if __name__=='__main__':unittest.main()
