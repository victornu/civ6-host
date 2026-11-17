from copy import deepcopy
from struct import pack
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from civ6_host.contracts import city_buildings, information, network_turn
from civ6_host.runtime import xp1_city_buildings, xp1_session_view, xp2_dedications, xp2_great_works_inventory
from civ6_host.runtime import xp2_great_work_commands as commands
from civ6_host.runtime.configuration_profiles import XP1_CORE_SHA256, XP2_CORE_SHA256
from civ6_host.runtime.execution_images import _XP1_PROFILE
from civ6_host.runtime.native import native_player_observation, native_player_operation_request
from test_session_capabilities import seal
from test_xp1_dedications import expansion_catalogue
from test_xp2_city_religion_public import added as add_city_religion_details
from test_xp2_religious_chain_public import preceding, validate


class OwnCityBuildingTests(unittest.TestCase):
    def setUp(self):
        self.observation, self.prior = expansion_catalogue()
        self.actor, self.turn = (self.observation[k] for k in ('player_id','turn'))
        city, = self.observation['cities']
        self.city = city['id']
        self.plot = city['y']*self.observation['width']+city['x']
        self.observation['plots'] = [dict(index=self.plot,x=city['x'],y=city['y'],visible=True,
            revealed=True,owner=self.actor)]
        self.header = f'city-buildings-v1|{self.actor}|{self.turn}'.encode('ascii')

    def wire(self, city=None, plot=None):
        cid = self.city if city is None else city
        p = self.plot if plot is None else plot
        return self.header+f'\n{cid}|{p}|3|123|BUILDING_GRANARY|1|0\n{cid}|{p}|0|44|BUILDING_MONUMENT|1|1'.encode('ascii')

    def test_multiple_buildings_on_one_tile_and_detached_player_information(self):
        state = xp1_city_buildings.parse_readback(self.wire(),self.actor,self.turn,self.observation)
        self.assertEqual([r['index'] for r in state['rows']],[0,3])
        self.assertEqual([r['pillaged'] for r in state['rows']],[True,False])
        projected = information.project('city_buildings',self.observation,dict(city_buildings=state))
        self.assertEqual(projected,state)
        projected['rows'].clear()
        self.assertEqual(len(state['rows']),2)

    def test_foreign_city_and_hidden_plot_are_rejected(self):
        for raw in (self.wire(city=self.city+1),self.wire(plot=self.plot+1)):
            with self.assertRaisesRegex(ValueError,'unavailable plot'):
                xp1_city_buildings.parse_readback(raw,self.actor,self.turn,self.observation)
        source = xp1_city_buildings.readback_source(self.actor,self.turn,self.observation)
        self.assertIn(f'local ownVisible={{[{self.plot}]=true}}'.encode('ascii'),source)
        self.assertIn(b'GetPurchasedPlots(city)',source)
        self.assertIn(b'GetBuildingsAtLocation(plot)',source)

    def test_inventory_is_additive_to_an_older_checkpoint(self):
        obs, prior = expansion_catalogue()
        actor, turn = (obs[k] for k in ('player_id','turn'))
        state = xp2_dedications.parse_state(f'{actor}|{turn}|0|normal|0'.encode(),actor,turn)
        with patch.object(xp2_dedications,'catalogue',return_value=state):
            xp1_session_view._add_dedications(None,obs,prior,actions_closed=False,
                previous_schema=network_turn.CAPABILITY_XP1_UNIT_LEVIES_SCHEMA,
                target_schema=network_turn.CAPABILITY_XP1_DEDICATIONS_SCHEMA)
        seal(prior)
        current = deepcopy(prior)
        current['schema'] = network_turn.XP1_CITY_BUILDINGS_SCHEMA_BY_BASE[prior['schema']]
        current['city_buildings'] = dict(schema=city_buildings.SCHEMA,player_id=actor,turn=turn,rows=[])
        seal(current)
        projected, receipt = network_turn.checkpoint_catalogue(current,prior,obs,core_sha256=XP1_CORE_SHA256)
        self.assertEqual(projected,prior)
        self.assertEqual(receipt['added_public_fields'],['city_buildings'])

        overview = deepcopy(current)
        overview['city_buildings'].update(schema=city_buildings.GREAT_WORK_OVERVIEW_SCHEMA,
            great_work_slots=[], great_work_move_targets=[], great_work_building_bonuses=[],
            great_work_moves_available=False)
        network_turn.add_great_work_choices(overview, overview['city_buildings'])
        seal(overview)
        projected, receipt = network_turn.checkpoint_catalogue(overview,current,obs,core_sha256=XP1_CORE_SHA256)
        self.assertEqual(projected,current)
        self.assertIn('city_buildings.great_work_building_bonuses', receipt['added_public_fields'])
        projected, receipt = network_turn.checkpoint_catalogue(overview,prior,obs,core_sha256=XP1_CORE_SHA256)
        self.assertEqual(projected,prior)
        self.assertEqual(receipt['added_action_families'],[city_buildings.GREAT_WORK_MOVE])
        ready = deepcopy(overview)
        ready['city_buildings'].update(schema=city_buildings.GREAT_WORK_XP1_COMMANDS_SCHEMA,
                                       great_work_moves_available=True)
        network_turn.add_great_work_choices(ready, ready['city_buildings'])
        seal(ready)
        projected, receipt = network_turn.checkpoint_catalogue(ready, overview, obs, core_sha256=XP1_CORE_SHA256)
        self.assertEqual(projected, overview)
        self.assertEqual(receipt['added_action_variants'], [city_buildings.GREAT_WORK_MOVE])
        old_enabled = deepcopy(overview)
        old_enabled['city_buildings']['great_work_moves_available'] = True
        seal(old_enabled)
        with self.assertRaisesRegex(ValueError, 'no admitted command route'):
            network_turn.checkpoint_catalogue(old_enabled,current,obs,core_sha256=XP1_CORE_SHA256)

    def test_rise_and_fall_command_uses_its_own_scope_permit_and_observed_effect(self):
        pid, turn = self.actor, self.turn
        src, dest = (dict(city_id=self.city, building_index=0, slot=i) for i in (0,1))
        row = dict(index=91, type='GREATWORK_EXAMPLE', object_type='GREATWORKOBJECT_WRITING', move_unlocked=True)
        preview = dict(schema=city_buildings.GREAT_WORK_OVERVIEW_SCHEMA, player_id=pid, turn=turn,
            great_work_slots=[dict(src, work=row), dict(dest, work=None)],
            great_work_move_targets=[dict(source=src, destination=dest)], great_work_moves_available=False)
        after = deepcopy(preview)
        after['great_work_slots'][0]['work'] = None
        after['great_work_slots'][1]['work'] = row
        action, = city_buildings.great_work_actions(commands.panel_with_commands(preview, available=True))
        core = SimpleNamespace(_civ6_host_execution_image=_XP1_PROFILE)
        owner = SimpleNamespace(load_abi=SimpleNamespace(core_sha256=XP1_CORE_SHA256), core=core,
            context=33, runtime=SimpleNamespace(read=None), control=lambda **_: None,
            captured_bundle=SimpleNamespace(reference=xp1_city_buildings.REFERENCE))
        observation = dict(player_id=pid, turn=turn)
        pending, receipts = [], []
        token = SimpleNamespace(observation=observation, trade_feedback=None, publication_count=0,
            transport=SimpleNamespace(require_empty_native_queue=lambda: self.assertEqual(pending, [])))
        prefix = SimpleNamespace(runtime=object(), ui_child=object(),
            actions=SimpleNamespace(pending=pending, deliver_one=lambda: pending.pop(0)),
            deferred_events=SimpleNamespace(pending=[], drain_empty_receivers=lambda: None),
            view_publisher=SimpleNamespace(publish=lambda: setattr(token, 'publication_count', 1)))
        saved = SimpleNamespace(backend=owner, prefix=prefix, continuation=token, xp1_city_buildings=True,
            emit=lambda stage, **details: receipts.append((stage, details)))

        def request(bound_core, context, player, operation, parameters, *, core_sha256, read, great_work_permit):
            self.assertEqual(core_sha256, XP1_CORE_SHA256)
            self.assertEqual(commands.authorize_request(great_work_permit, bound_core, context, player,
                operation, parameters, core_sha256=core_sha256, submit=True, allow_empty=False),
                'MOVE_GREAT_WORK')
            archive = pack('<6I', 0xc45de12f, player, operation, 2, 0x80000001, len(parameters))
            pending.append(archive + b''.join(pack('<IHH10xI', key, 0, 2, value)
                                             for key,value in reversed(tuple(parameters.items()))))
            return dict(request_invoked=True, can_start=None)

        with (patch.object(commands, '_verify_live', return_value=True),
              patch.object(native_player_observation, 'observe_player', return_value=observation),
              patch.object(native_player_operation_request, 'request_player_operation', side_effect=request),
              patch.object(xp1_city_buildings, 'read', side_effect=[preview,after]) as read_inventory):
            public = commands.public_panel(saved, preview, can_act=True)
            self.assertEqual(public['schema'], city_buildings.GREAT_WORK_XP1_COMMANDS_SCHEMA)
            self.assertEqual(city_buildings.great_work_actions(public), [action])
            result = commands.apply(saved, action, observation)
        self.assertEqual(read_inventory.call_count, 2)
        self.assertEqual(result['status'], 'completed')
        self.assertEqual(receipts[0][0], 'native_xp1_great_work_move_effect')
        self.assertTrue(receipts[0][1]['native_effect_readback'])
        self.assertEqual(pending, [])

    def test_great_work_overview_uses_the_rise_and_fall_source_closure(self):
        pins = xp1_city_buildings.source_dependencies(_XP1_PROFILE)
        self.assertIn(xp2_great_works_inventory.XP1_OVERVIEW_SOURCE[1], pins.values())
        self.assertNotIn(xp2_great_works_inventory.THEME_SOURCE[1], pins.values())
        self.assertFalse(any(name.replace('\\','/').endswith('GreatWorksOverview_Expansion2.lua') for name in pins))
        self.assertEqual(len(xp2_great_works_inventory.theming_spans(_XP1_PROFILE)),22)

    def test_xp2_building_pillage_revision_preserves_previous_choices(self):
        base, obs = preceding(2, unit_operations=True)
        prior = add_city_religion_details(base, obs)
        city = obs['cities'][0]
        turn, actor = obs['turn'], obs['player_id']
        plot = next(row['index'] for row in obs['plots']
                    if row['visible'] and row['owner'] == actor
                    and (row['x'], row['y']) == (city['x'], city['y']))
        source = f"city-buildings-v1|{actor}|{turn}\n{city['id']}|{plot}|0|44|BUILDING_MONUMENT|1|1"
        current = deepcopy(prior)
        current['schema'] = network_turn.XP2_CITY_BUILDINGS_SCHEMA_BY_BASE[prior['schema']]
        current['city_buildings'] = xp1_city_buildings.parse_readback(source.encode('ascii'), actor, turn, obs)
        seal(current)
        validate(current, obs)
        shown = information.project('city_buildings', obs, current)
        self.assertTrue(shown['rows'][0]['pillaged'])
        self.assertEqual(information.project('city_religion', obs, current), prior['city_religion'])
        projected, receipt = network_turn.checkpoint_catalogue(current, prior, obs, core_sha256=XP2_CORE_SHA256)
        self.assertEqual(projected, prior)
        self.assertEqual(receipt['added_public_fields'], ['city_buildings'])
        self.assertEqual(receipt['added_action_families'], [])
        self.assertEqual(network_turn.checkpoint_catalogue(current, current, obs, core_sha256=XP2_CORE_SHA256),
                         (current, None))


if __name__ == '__main__':
    unittest.main()
