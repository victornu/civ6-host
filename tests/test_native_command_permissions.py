"""Portable v39 composition on retained public replies; no native execution.

The permission values and denied-reader transformations are synthetic. All
unaffected ordinary fields in the principal fixture are retained native data.
"""
from copy import deepcopy
from types import SimpleNamespace as NS
import unittest

from civ6_host import SessionClient, InformationUnavailable
from civ6_host.contracts import information, network_turn as nt
import test_world_congress_review_client as previous
import test_world_congress_client as congress_fixture
from test_world_congress_contract import ballot_parameters


DENIED_FIELDS = (
    'production_queues', 'production_current', 'world_input', 'queued_orders',
    'unit_orders', 'unit_attacks', 'unit_upgrades', 'policies', 'policy_unlock',
    'government', 'envoys', 'trade_origins', 'city_shots', 'district_shots',
)
PRESERVED_FIELDS = (
    'choice_state', 'placements', 'placement_offers', 'placement_observation_scope',
    'placement_inventory', 'unit_promotions', 'unit_work', 'unit_work_state',
    'unit_work_info', 'strategic_resources', 'governors', 'diplomacy_overview',
    'trade_routes', 'espionage', 'spy_completion', 'world_congress',
    'world_congress_review', 'world_congress_review_status', 'turn_controls', 'turn_availability',
)


def permissions(value, strategic=True, tactical=True):
    return dict(player_id=value['player_id'], turn=value['turn'], sequence=value['sequence'],
                allow_strategic=strategic, allow_tactical=tactical)


def unavailable_readers(value):
    """Fixture only: model the runtime's explicit skipped reader results."""
    result=deepcopy(value)
    for field in DENIED_FIELDS: result[field]=None
    removed={r['candidate_id'] for r in result['candidates']
             if r['action']['kind'] in nt.STRATEGIC_READER_FAMILIES}
    result['candidates']=[r for r in result['candidates'] if r['candidate_id'] not in removed]
    for kind in result['families']:
        if kind in nt.STRATEGIC_READER_FAMILIES:
            result['families'][kind]=dict(status='unqualified',reason=nt.NATIVE_STRATEGIC_READER_UNAVAILABLE)
    previous.seal(result)
    return result


class NativeCommandPermissionsTests(unittest.TestCase):
    def retained_v38(self, state='active'):
        response=previous.retained(state);old=response['decisions']
        response['decisions']=nt.upgrade_review_catalogue(old,
            previous.history(old) if old['world_congress'] is not None else None,response['observation'])
        return response

    def denied(self):
        response=self.retained_v38();old=deepcopy(response['decisions'])
        response['decisions']=nt.upgrade_command_permissions_catalogue(
            unavailable_readers(old),permissions(old,False),response['observation'])
        return response,old

    def test_permitted_upgrade_preserves_native_fields_and_all_candidate_ids(self):
        response=self.retained_v38();old=response['decisions'];before=deepcopy(old)
        for tactical in (True,False):
            current=nt.upgrade_command_permissions_catalogue(old,permissions(old,True,tactical),response['observation'])
            self.assertEqual(old,before)
            self.assertEqual(current['candidates'],old['candidates'])
            self.assertEqual(current['families'],old['families'])
            for key in old:
                if key not in ('schema','decision_id'):self.assertEqual(current[key],old[key])
            self.assertNotEqual(current['decision_id'],old['decision_id'])
            previous.validate(current,response['observation'])
            self.assertFalse(current['complete_action_space'])

    def test_denied_reader_groups_do_not_change_activity_or_unrelated_native_data(self):
        response,old=self.denied();value=response['decisions']
        self.assertTrue(value['turn_controls']['active'])
        self.assertTrue(value['turn_controls']['active_complete'])
        self.assertFalse(nt.is_waiting(value['turn_controls']))
        for field in DENIED_FIELDS:self.assertIsNone(value[field])
        for field in PRESERVED_FIELDS:self.assertEqual(value[field],old[field],field)
        self.assertIsNotNone(value['choice_state'])
        self.assertIsNotNone(value['trade_routes'])
        self.assertIsNotNone(value['espionage'])
        self.assertIsNotNone(value['spy_completion'])
        expected=[r for r in old['candidates'] if r['action']['kind'] not in nt.STRATEGIC_READER_FAMILIES]
        self.assertEqual(value['candidates'],expected)
        previous.validate(value,response['observation'])

    def test_reader_policy_is_exact_and_tactical_is_not_a_strategy_filter(self):
        response,old=self.denied();value=response['decisions']
        for family in nt.STRATEGIC_READER_FAMILIES:
            self.assertTrue(nt.family_query_unavailable(value,family),family)
        for family in ('research','civic','production','city_focus','city_citizen','promote_unit',
                       'make_trade_route','spy_travel','spy_renew','appoint_governor',
                       'diplomacy_initiate','congress_confirm_ballot'):
            self.assertFalse(nt.family_query_unavailable(value,family),family)
        alternative=deepcopy(value);alternative['native_command_permissions']['allow_tactical']=False
        previous.seal(alternative);previous.validate(alternative,response['observation'])
        self.assertEqual(alternative['candidates'],value['candidates'])
        with self.assertRaisesRegex(ValueError,'Conflicting'):
            nt.family_query_unavailable(value,'found_city',native_command_permissions=permissions(old))

    def test_false_permission_cannot_publish_a_successful_empty_query_or_old_state(self):
        response,old=self.denied();value=response['decisions']
        for field in DENIED_FIELDS:
            if old[field] is None:continue
            bad=deepcopy(value);bad[field]=deepcopy(old[field]);previous.seal(bad)
            with self.subTest(field=field),self.assertRaisesRegex(ValueError,'reader'):
                previous.validate(bad,response['observation'])
        bad=deepcopy(value);bad['families']['found_city']=dict(status='queried_complete',candidate_ids=[])
        previous.seal(bad)
        with self.assertRaisesRegex(ValueError,'coupled reader'):previous.validate(bad,response['observation'])

    def test_unaffected_information_cannot_be_silently_removed(self):
        response,_=self.denied()
        for field in ('choice_state','unit_promotions','governors','diplomacy_overview',
                      'trade_routes','espionage','spy_completion','world_congress'):
            bad=deepcopy(response['decisions']);bad[field]=None;previous.seal(bad)
            with self.subTest(field=field),self.assertRaises(ValueError):previous.validate(bad,response['observation'])

    def test_permissions_reject_foreign_stale_hidden_and_nonboolean_fields(self):
        response=self.retained_v38();old=response['decisions']
        for key,value in (('player_id',1),('turn',old['turn']+1),('sequence',old['sequence']+1),
                          ('allow_strategic',1),('allow_tactical',None),('hidden_ballots',[])):
            bad=permissions(old);bad[key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):
                nt.upgrade_command_permissions_catalogue(old,bad,response['observation'])
        bad=permissions(old);bad.pop('allow_tactical')
        with self.assertRaises(ValueError):nt.upgrade_command_permissions_catalogue(old,bad,response['observation'])

    def test_checkpoint_removes_only_metadata_and_refuses_incomparable_old_reader_fields(self):
        response=self.retained_v38();old=response['decisions']
        current=nt.upgrade_command_permissions_catalogue(old,permissions(old),response['observation'])
        projected,transition=nt.checkpoint_catalogue(current,old,response['observation'],core_sha256=nt._XP2_COMBAT_CORE)
        self.assertEqual(projected,old)
        self.assertEqual(transition['added_public_fields'],['native_command_permissions'])
        denied,_=self.denied()
        with self.assertRaisesRegex(ValueError,'no comparable historical query'):
            nt.checkpoint_catalogue(denied['decisions'],old,denied['observation'],core_sha256=nt._XP2_COMBAT_CORE)

    def test_congress_complete_ballot_stays_available_with_independent_permissions(self):
        congress_fixture.WorldCongressClientTests.setUpClass()
        old,observation=congress_fixture.WorldCongressClientTests()._v37()
        old=nt.upgrade_review_catalogue(old,None,observation,status='review_ui_unavailable')
        current=nt.upgrade_command_permissions_catalogue(unavailable_readers(old),permissions(old,False),observation)
        selected=next(r for r in current['candidates'] if r['action']['kind']=='congress_confirm_ballot')
        expected=next(r for r in old['candidates'] if r['action']['kind']=='congress_confirm_ballot')
        self.assertEqual(selected,expected)
        action=nt.select_capability(current,dict(decision_id=current['decision_id'],
            candidate_id=selected['candidate_id'],parameters=ballot_parameters(current['world_congress'])))
        self.assertEqual(action['kind'],'congress_confirm_ballot')
        previous.validate(current,observation)

    def test_information_remains_public_cached_and_explicitly_partial(self):
        response,_=self.denied();backend=previous.ReplayBackend(response);client=SessionClient(backend)
        client.reset()
        result=client.information('native_command_permissions')['data']
        self.assertEqual(result,response['decisions']['native_command_permissions'])
        result['allow_strategic']=True
        self.assertFalse(client.information('native_command_permissions')['data']['allow_strategic'])
        trade=client.information('trade')['data']
        self.assertEqual(trade['schema'],'civ6-host.trade-inputs.v2')
        self.assertEqual(trade['routes'],response['decisions']['trade_routes'])
        self.assertIsNone(trade['origins'])
        self.assertEqual(trade['origins_status'],nt.NATIVE_STRATEGIC_READER_UNAVAILABLE)
        for group in ('espionage','spy_completion','world_congress','strategic_resources'):
            self.assertIsNotNone(client.information(group)['data'])
        for group in ('production','combat'):
            with self.subTest(group=group),self.assertRaisesRegex(InformationUnavailable,'reader_unavailable'):
                client.information(group)
        self.assertEqual(backend.calls,[])

    def test_historical_v38_requires_old_groups_and_does_not_gain_permission_metadata(self):
        response=self.retained_v38();value=response['decisions'];previous.validate(value,response['observation'])
        self.assertEqual(information.project('trade',response['observation'],value)['schema'],'civ6-host.trade-inputs.v1')
        bad=unavailable_readers(value)
        with self.assertRaises(ValueError):previous.validate(bad,response['observation'])
        bad=deepcopy(value);bad['native_command_permissions']=permissions(value);previous.seal(bad)
        with self.assertRaises(ValueError):previous.validate(bad,response['observation'])

    def test_waiting_and_closed_keep_actual_controls_without_inferred_permission_flags(self):
        response=self.retained_v38('waiting');old=response['decisions']
        for strategic in (True,False):
            current=nt.upgrade_command_permissions_catalogue(old,permissions(old,strategic),response['observation'])
            self.assertEqual(current['turn_controls'],old['turn_controls'])
            self.assertEqual(current['candidates'],old['candidates'])
            self.assertIsNone(current['world_congress'])
            previous.validate(current,response['observation'])
        congress_fixture.WorldCongressClientTests.setUpClass()
        closed,observation=congress_fixture.WorldCongressClientTests()._v37('close')
        closed=nt.upgrade_review_catalogue(closed,None,observation)
        current=nt.upgrade_command_permissions_catalogue(closed,permissions(closed,False),observation,actions_closed=True)
        previous.validate(current,observation,closed=True)
        self.assertEqual(current['turn_controls'],closed['turn_controls'])
        self.assertEqual(current['candidates'],[])


if __name__=='__main__':unittest.main()
