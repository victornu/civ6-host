"""Source and client contract checks for the pinned GS city building reader."""

from copy import deepcopy
from dataclasses import replace
from hashlib import sha256
import json
from struct import pack
from types import SimpleNamespace
import unittest

from civ6_host.contracts import city_buildings, information, network_turn
from civ6_host.runtime import xp2_bbg_inputs, xp2_bundle_inputs, xp2_city_buildings
from civ6_host.runtime import xp2_great_works_inventory as works
from civ6_host.runtime import xp2_great_work_commands as commands
from civ6_host.runtime.configuration_profiles import XP2_CORE_SHA256, _source
from civ6_host.runtime.execution_images import _PROFILE, _XP1_PROFILE
from civ6_host.runtime.paths import resource_root

try:
    from lupa.lua51 import LuaError, LuaRuntime
except ImportError:
    LuaRuntime = None


class XP2CityBuildingsTests(unittest.TestCase):
    def test_exact_source_profiles_keep_separate_capture_pins(self):
        reader = xp2_city_buildings
        stock = xp2_bundle_inputs.REFERENCE
        bbg = xp2_bbg_inputs.REFERENCE
        stock_pins = reader.source_dependencies(_PROFILE, reference=stock)
        bbg_pins = reader.source_dependencies(_PROFILE, reference=bbg)
        self.assertIn(stock[1], stock_pins.values())
        self.assertNotIn(stock[1], bbg_pins.values())
        self.assertIn(bbg[1], bbg_pins.values())
        self.assertIn(reader.BBG_SOURCE[1], bbg_pins.values())
        self.assertIn(reader.SOURCE[1], stock_pins.values())
        self.assertIn(reader.SOURCE[1], bbg_pins.values())
        self.assertIn(works.THEME_SOURCE[1], stock_pins.values())
        self.assertIn(works.THEME_SOURCE[1], bbg_pins.values())
        self.assertTrue(works.dependencies(_PROFILE).items() <= stock_pins.items())
        self.assertTrue(works.dependencies(_PROFILE).items() <= bbg_pins.items())
        self.assertIn(reader.BBG_GREAT_WORK_SOURCE[1], bbg_pins.values())
        self.assertNotIn(reader.BBG_GREAT_WORK_SOURCE[1], stock_pins.values())
        profile = _source(reader.BBG_GREAT_WORK_SOURCE)
        self.assertIn(profile['files']['bbg_gameplay']['sha256'], bbg_pins.values())
        for row in profile['files']['script_copies']:
            self.assertIn(row['sha256'], bbg_pins.values())
        backend = SimpleNamespace(load_abi=SimpleNamespace(core_sha256=XP2_CORE_SHA256),
            core=SimpleNamespace(_civ6_host_execution_image=_PROFILE),
            captured_bundle=SimpleNamespace(reference=bbg))
        saved = SimpleNamespace(backend=backend, xp2_city_buildings=True)
        self.assertTrue(commands.enabled(saved))
        backend.captured_bundle.reference = stock
        self.assertTrue(commands.enabled(saved))
        backend.captured_bundle.reference = (bbg[0], '0' * 64)
        self.assertFalse(commands.enabled(saved))
        with self.assertRaises(ValueError):
            reader.source_dependencies(replace(_PROFILE), reference=bbg)
        with self.assertRaises(ValueError):
            reader.source_dependencies(_PROFILE, reference=(bbg[0], '0' * 64))

    def test_t76_buildings_transition_keeps_great_people_and_every_choice(self):
        root = resource_root()
        receipt = json.loads((root / 'evidence/host-xp2-bbg-religion-founding-save-t76-native.json').read_bytes())
        ref = receipt['checkpoint']
        data = (root / ref['path']).read_bytes()
        self.assertEqual(sha256(data).hexdigest(), ref['sha256'])
        saved = json.loads(data)
        observation, prior = saved['observation'], saved['decisions']
        people_schema = network_turn._XP2_GREAT_PEOPLE_ACTIONS_BASE_BY_SCHEMA[prior['schema']]
        base = network_turn._XP2_GREAT_PEOPLE_BASE_BY_SCHEMA[people_schema]
        self.assertEqual(observation['turn'], 76)

        current = deepcopy(prior)
        buildings = network_turn.XP2_CITY_BUILDINGS_SCHEMA_BY_BASE[base]
        people = network_turn.XP2_GREAT_PEOPLE_SCHEMA_BY_BASE[buildings]
        current['schema'] = network_turn.XP2_GREAT_PEOPLE_ACTIONS_SCHEMA_BY_BASE[people]
        current['city_buildings'] = dict(schema=city_buildings.SCHEMA, turn=76,
                                        player_id=observation['player_id'], rows=[])
        self.seal(current)
        identity = SimpleNamespace(episode_id=current['episode_id'], game_generation=current['game_generation'])
        network_turn.validate_capability_catalogue(current, identity, current['sequence'], 76,
            player_id=observation['player_id'], observation=observation)
        self.assertEqual(information.project('city_buildings', observation, current), current['city_buildings'])

        projected, transition = network_turn.checkpoint_catalogue(
            current, prior, observation, core_sha256=XP2_CORE_SHA256)
        self.assertEqual(projected, prior)
        self.assertEqual(transition['added_public_fields'], ['city_buildings'])
        self.assertEqual(transition['added_action_families'], [])
        self.assertEqual(network_turn.checkpoint_catalogue(
            current, current, observation, core_sha256=XP2_CORE_SHA256), (current, None))

        bbg_works = deepcopy(current)
        empty = dict(bbg_works['city_buildings'], schema=city_buildings.GREAT_WORK_TARGETS_SCHEMA,
                     great_work_move_targets=[], great_work_slots=[])
        bbg_works['city_buildings'] = commands.panel_with_commands(empty, available=False)
        network_turn.add_great_work_choices(bbg_works, bbg_works['city_buildings'])
        self.seal(bbg_works)
        projected, transition = network_turn.checkpoint_catalogue(
            bbg_works, current, observation, core_sha256=XP2_CORE_SHA256)
        self.assertEqual(projected, current)
        self.assertEqual(transition['added_action_families'], [city_buildings.GREAT_WORK_MOVE])

        current['great_people']['own_points'][0]['points_total'] += 1.0
        self.seal(current)
        projected, _ = network_turn.checkpoint_catalogue(
            current, prior, observation, core_sha256=XP2_CORE_SHA256)
        self.assertNotEqual(projected, prior)
        self.assertEqual(projected['candidates'], prior['candidates'])

    @unittest.skipIf(LuaRuntime is None, 'Lua 5.1 fixture unavailable')
    def test_great_work_slots_use_the_official_art_and_artifact_locks(self):
        lua = LuaRuntime()
        lua.execute(r'''
        observer=0
        created=31
        otherArtifact=-1
        artifactPlayer=1
        secondArt=-1
        secondArtist='artist'
        themedMuseum=0
        automatic=false
        Game={GetLocalPlayer=function() return 0 end,
              GetLocalObserver=function() return observer end,
              GetCurrentGameTurn=function() return 40 end,
              GetGreatWorkPlayer=function(idx) return idx==32 and 1 or artifactPlayer end}
        Map={GetGridSize=function() return 1,1 end, GetPlotCount=function() return 1 end}
        GlobalParameters={}
        Locale={Lookup=function(key) return key end}
        table.count=function(value) local n=0;for _ in pairs(value) do n=n+1 end;return n end
        local function rows(items)
            return function() local i=0;return function() i=i+1;return items[i] end end
        end
        local inventory={{31,-1},{32,-1},{}, {-1,-1}}
        local buildings={
            HasBuilding=function(_,idx) return idx~=3 end,
            GetNumGreatWorkSlots=function(_,idx) assert(idx~=3);return 2 end,
            GetGreatWorkSlotType=function(_,idx,slot) return idx==1 and 1 or 2 end,
            GetGreatWorkInSlot=function(_,idx,slot)
                if idx==1 and slot==1 then return secondArt end
                return idx==2 and slot==1 and otherArtifact or inventory[idx][slot+1]
            end,
            GetGreatWorkTypeFromIndex=function(_,idx) return idx end,
            GetTurnFromIndex=function(_,idx) assert(idx==31 or idx==34);return created end,
            GetCreatorNameFromIndex=function(_,idx) return idx==31 and 'artist' or secondArtist end,
            IsBuildingThemedCorrectly=function(_,idx) return idx==themedMuseum end,
            GetBuildingYieldFromGreatWorks=function(_,y,idx) return y==1 and (idx==4 and 0 or idx*2) or -1 end,
            GetBuildingTourismFromGreatWorks=function(_,religion,idx) return idx==2 and (religion and 2 or 3) or 0 end}
        local city={GetOwner=function() return 0 end, GetID=function() return 7 end,
                    GetBuildings=function() return buildings end}
        Players={[0]={
            GetCities=function() return {Members=function() return ipairs({city}) end} end,
            GetCulture=function() return {
                GetAutoThemedBuilding=function() return -1 end,
                IsAutoThemedEligible=function() return automatic end} end}}
        local definitions={}
        for idx,name in pairs({[1]='BUILDING_MUSEUM_ART',[2]='BUILDING_MUSEUM_ARTIFACT',[4]='BUILDING_TEST_4'}) do
            definitions[idx]={Index=idx, BuildingType=name,Hash=idx}
            definitions[name]=definitions[idx]
        end
        GameInfo={GameCapabilities={CAPABILITY_GREAT_WORKS_VIEW=true},
                  Buildings=definitions,
                  Building_GreatWorks=rows({
                      {BuildingType='BUILDING_MUSEUM_ART',ThemingBonusDescription='LOC_ART'},
                      {BuildingType='BUILDING_MUSEUM_ARTIFACT',ThemingBonusDescription='LOC_ARTIFACT'}}),
                  Yields=rows({{Index=1,YieldType='YIELD_CULTURE'},{Index=2,YieldType='YIELD_SCIENCE'}}),
                  GreatWorkSlotTypes={{GreatWorkSlotType='GREATWORKSLOT_ART'},
                                     {GreatWorkSlotType='GREATWORKSLOT_ARTIFACT'}},
                  GreatWorks={[31]={GreatWorkType='GREATWORK_PORTRAIT_EXAMPLE',
                                    GreatWorkObjectType='GREATWORKOBJECT_PORTRAIT'},
                              [32]={GreatWorkType='GREATWORK_ARTIFACT_EXAMPLE',
                                    GreatWorkObjectType='GREATWORKOBJECT_ARTIFACT',EraType='ERA_ANCIENT'},
                              [33]={GreatWorkType='GREATWORK_ARTIFACT_EXAMPLE_2',
                                    GreatWorkObjectType='GREATWORKOBJECT_ARTIFACT',EraType='ERA_ANCIENT'},
                              [34]={GreatWorkType='GREATWORK_PORTRAIT_EXAMPLE_2',
                                    GreatWorkObjectType='GREATWORKOBJECT_PORTRAIT'}}}
        GameInfo.GreatWork_ValidSubTypes=function()
            local i=0
            local rows={{GreatWorkSlotType='GREATWORKSLOT_ART',GreatWorkObjectType='GREATWORKOBJECT_PORTRAIT'},
                        {GreatWorkSlotType='GREATWORKSLOT_ARTIFACT',GreatWorkObjectType='GREATWORKOBJECT_ARTIFACT'}}
            return function() i=i+1; return rows[i] end
        end
        ''')
        obs = dict(player_id=0, turn=40, width=1, height=1,
            cities=[dict(id=7, owner=0)],
            plots=[dict(index=0, x=0, y=0, owner=0, visible=True, revealed=True)])
        inventory = dict(schema=city_buildings.SCHEMA, player_id=0, turn=40, rows=[
            dict(city_id=7, plot_id=0, index=i, hash=i, item_type=f'BUILDING_TEST_{i}',
                 complete=i != 3, pillaged=False) for i in range(1,5)])
        def evaluate(_child, script, _label, *, capacity):
            return lua.execute(script.decode('ascii')).encode('ascii')
        prefix = SimpleNamespace(ui_child=object(), runtime=SimpleNamespace(evaluate_text=evaluate))
        rules = works.rules(_PROFILE)
        profile = _source(xp2_city_buildings.BBG_GREAT_WORK_SOURCE)
        lua.globals().GlobalParameters.GREATWORK_ART_LOCK_TIME = profile['stock']['artwork_lock_turns']
        view = works.read(prefix, obs, inventory, rules)
        slots = view['great_work_slots']
        self.assertEqual([(row['building_index'],row['slot']) for row in slots],
                         [(1,0),(1,1),(2,0),(2,1),(4,0),(4,1)])
        self.assertEqual([row['work']['move_unlocked'] for row in slots if row['work']], [False,False])
        self.assertIsNone(slots[1]['work'])
        self.assertEqual(view['great_work_move_targets'], [])
        bonuses = view['great_work_building_bonuses']
        self.assertEqual([row['theme'] for row in bonuses],
                         [dict(state='progress',matching=1,slots=2),
                          dict(state='progress',matching=1,slots=2), None])
        self.assertEqual([row['yields'] for row in bonuses], [{'YIELD_CULTURE':2}, {'YIELD_CULTURE':4}, {}])
        self.assertEqual([row['tourism'] for row in bonuses], [0, 5, 0])
        lua.execute('created=37; otherArtifact=33')
        stock = works.read(prefix, obs, inventory, rules)
        self.assertFalse(stock['great_work_slots'][0]['work']['move_unlocked'])
        lua.globals().GlobalParameters.GREATWORK_ART_LOCK_TIME = profile['bbg']['artwork_lock_turns']
        view = works.read(prefix, obs, inventory, rules)
        self.assertEqual([row['work']['move_unlocked'] for row in view['great_work_slots'] if row['work']],
                         [True,True,True])
        self.assertEqual(
            [(move['source']['building_index'],move['source']['slot'],
              move['destination']['building_index'],move['destination']['slot'])
             for move in view['great_work_move_targets']],
            [(1,0,1,1),(2,0,2,1),(2,1,2,0)])
        self.assertEqual(view['great_work_building_bonuses'][1]['theme']['matching'], 1)
        lua.execute('secondArt=34')
        duplicate_artist = works.read(prefix, obs, inventory, rules)
        self.assertEqual(duplicate_artist['great_work_building_bonuses'][0]['theme']['matching'], 1)
        lua.execute("secondArtist='another'")
        distinct_artists = works.read(prefix, obs, inventory, rules)
        self.assertEqual(distinct_artists['great_work_building_bonuses'][0]['theme']['matching'], 2)
        lua.execute('secondArt=-1')
        lua.execute('artifactPlayer=2')
        different = works.read(prefix, obs, inventory, rules)
        self.assertEqual(different['great_work_building_bonuses'][1]['theme']['matching'], 2)
        lua.execute('artifactPlayer=1; automatic=true')
        automatic = works.read(prefix, obs, inventory, rules)
        self.assertEqual(automatic['great_work_building_bonuses'][1]['theme']['matching'], 2)
        self.assertEqual(automatic['great_work_building_bonuses'][2]['theme']['matching'], 0)
        lua.execute("Players[0].GetCulture=function() return {GetAutoThemedBuilding=function() return 4 end} end")
        rise_and_fall = works.read(prefix, obs, inventory, works.rules(_XP1_PROFILE))
        self.assertEqual(rise_and_fall['great_work_building_bonuses'][1]['theme']['matching'], 1)
        self.assertEqual(rise_and_fall['great_work_building_bonuses'][2]['theme']['matching'], 0)
        self.assertFalse(rise_and_fall['great_work_moves_available'])
        self.assertEqual(rise_and_fall['great_work_move_targets'], view['great_work_move_targets'])
        lua.execute("Players[0].GetCulture=function() return {GetAutoThemedBuilding=function() return -1 end,"
                    " IsAutoThemedEligible=function() return automatic end} end")
        lua.execute('themedMuseum=2')
        themed = works.read(prefix, obs, inventory, rules)
        self.assertEqual(themed['great_work_building_bonuses'][1]['theme'], {'state':'themed'})
        command_panel = commands.panel_with_commands(view, available=True)
        move, swap, reverse = city_buildings.great_work_actions(command_panel)
        self.assertEqual([item['work_index'] for item in (move, swap, reverse)], [31, 32, 33])
        self.assertEqual([item['target_work_index'] for item in (move, swap, reverse)], [None, 33, 32])
        self.assertEqual(city_buildings.great_work_actions(
            commands.panel_with_commands(view, available=False)), [])
        for action, source, destination in ((move, 0, 1), (swap, 2, 3)):
            after = deepcopy(view)
            slots = after['great_work_slots']
            slots[source]['work'], slots[destination]['work'] = slots[destination]['work'], slots[source]['work']
            commands.verify_effect(view, after, action)
            with self.assertRaisesRegex(RuntimeError, 'did not produce'):
                commands.verify_effect(view, view, action)
        params = commands.operation_parameters(0, swap)
        self.assertEqual(params, {
            0x0483191c:0, 0x262cb79e:7, 0xe5f2cf9b:7, 0x84dbad68:2,
            0xb18e6fa8:2, 0xdc6e26b0:32, 0x2baddf94:1})
        archive = pack('<6I', 0xc45de12f, 0, 0x291d387e, 2, 0x80000001, 7)
        archive += b''.join(pack('<IHH10xI', key, 0, 2, value)
                            for key, value in reversed(list(params.items())))
        self.assertEqual(commands.verify_archive(archive, 0, params), sha256(archive).hexdigest())
        with self.assertRaisesRegex(RuntimeError, 'header'):
            commands.verify_archive(archive, 1, params)
        with self.assertRaisesRegex(RuntimeError, 'selected target'):
            commands.verify_archive(archive, 0, params | {0x2baddf94: 0})
        core = SimpleNamespace(_civ6_host_execution_image=_PROFILE)
        permit = commands._Permit(commands._SEAL, core, 123, 0, tuple(params.items()))
        def authorize(player, selected, *, submit=True):
            return commands.authorize_request(permit, core, 123, player, commands.OPERATION,
                selected, core_sha256=XP2_CORE_SHA256, submit=submit, allow_empty=False)
        self.assertEqual(authorize(0, params), 'MOVE_GREAT_WORK')
        for player, selected in ((1, params), (0, params | {0x2baddf94: 0})):
            with self.assertRaisesRegex(ValueError, 'exact Great Work request permit'):
                authorize(player, selected)
        with self.assertRaisesRegex(ValueError, 'exact Great Work request permit'):
            authorize(0, params, submit=False)
        public = information.project('city_buildings', obs,
            {'schema': 'unused', 'city_buildings': view})
        self.assertEqual(public, view)
        public['great_work_slots'][0]['building_index'] = 3
        with self.assertRaisesRegex(ValueError, 'foreign'):
            city_buildings.validate(public,0,40,observation=obs)
        foreign = deepcopy(view)
        foreign['great_work_move_targets'][0]['destination']['city_id'] = 8
        with self.assertRaisesRegex(ValueError, 'Foreign'):
            city_buildings.validate(foreign,0,40,observation=obs)
        foreign = deepcopy(view)
        foreign['great_work_building_bonuses'][0]['city_id'] = 9
        with self.assertRaisesRegex(ValueError, 'foreign Great Work bonus building'):
            city_buildings.validate(foreign,0,40,observation=obs)
        lua.execute('GameInfo.GameCapabilities={}; GameInfo.GreatWorkSlotTypes=nil')
        disabled = works.read(prefix, obs, inventory, rules)
        self.assertEqual((disabled['great_work_slots'], disabled['great_work_move_targets']), ([], []))
        self.assertEqual(disabled['great_work_building_bonuses'], [])
        self.assertEqual(disabled['rows'], inventory['rows'])
        lua.execute('observer=1')
        with self.assertRaisesRegex(LuaError, 'perspective changed'):
            works.read(prefix, obs, inventory, rules)

    def test_stock_great_work_slots_upgrade_retained_city_building_catalogue(self):
        root = resource_root()
        proof = json.loads((root/'evidence/host-xp2-stock-city-buildings-t94-native.json').read_bytes())
        trace, = [row for row in proof['trace'] if row['path'].endswith('events.jsonl')]
        payload = (root/trace['path']).read_bytes()
        self.assertEqual((len(payload),sha256(payload).hexdigest()), (trace['bytes'],trace['sha256']))
        reset = next(json.loads(line) for line in payload.splitlines()
                     if line.startswith(b'{"stage": "official_session_response"'))
        self.assertEqual(reset['operation'],'reset')
        old, obs = reset['decisions'], reset['observation']
        current = deepcopy(old)
        panel = current['city_buildings']
        panel.update(schema=city_buildings.GREAT_WORKS_SCHEMA, great_work_slots=[])
        self.seal(current)
        self.assertEqual(information.project('city_buildings', obs, current),panel)
        projected, transition = network_turn.checkpoint_catalogue(
            current, old, obs, core_sha256=XP2_CORE_SHA256)
        self.assertEqual(projected, old)
        self.assertEqual(transition['added_public_fields'], ['city_buildings.great_work_slots'])
        v3 = deepcopy(current)
        v3['city_buildings'].update(schema=city_buildings.GREAT_WORK_TARGETS_SCHEMA,
                                    great_work_move_targets=[])
        self.seal(v3)
        for saved, fields in (
            (old, ['city_buildings.great_work_slots','city_buildings.great_work_move_targets']),
            (current, ['city_buildings.great_work_move_targets']),
        ):
            projected, transition = network_turn.checkpoint_catalogue(
                v3, saved, obs, core_sha256=XP2_CORE_SHA256)
            self.assertEqual(projected, saved)
            self.assertEqual(transition['added_public_fields'], fields)
        v4 = deepcopy(v3)
        v4['city_buildings'] = commands.panel_with_commands(v3['city_buildings'], available=True)
        network_turn.add_great_work_choices(v4, v4['city_buildings'])
        self.seal(v4)
        for saved, extra in (
                (old, ['city_buildings.great_work_slots', 'city_buildings.great_work_move_targets']),
                (current, ['city_buildings.great_work_move_targets']), (v3, [])):
            projected, transition = network_turn.checkpoint_catalogue(
                v4, saved, obs, core_sha256=XP2_CORE_SHA256)
            self.assertEqual(projected, saved)
            self.assertEqual(transition['added_public_fields'], extra + ['city_buildings.great_work_moves_available'])
            self.assertEqual(transition['added_action_families'], [city_buildings.GREAT_WORK_MOVE])
        v4['families'].pop(city_buildings.GREAT_WORK_MOVE)
        self.seal(v4)
        with self.assertRaisesRegex(ValueError, 'exact panel'):
            network_turn.checkpoint_catalogue(v4, v3, obs, core_sha256=XP2_CORE_SHA256)
        building = next(row for row in v3['city_buildings']['rows'] if row['complete'])
        origin = dict(city_id=building['city_id'], building_index=building['index'], slot=0)
        target = dict(origin, slot=1)
        v3['city_buildings']['great_work_slots'] = [
            dict(origin, slot_type='GREATWORKSLOT_WRITING', work=dict(index=12,
                type='GREATWORK_WRITING_EXAMPLE', object_type='GREATWORKOBJECT_WRITING', move_unlocked=True)),
            dict(target, slot_type='GREATWORKSLOT_WRITING', work=None)]
        v3['city_buildings']['great_work_move_targets'] = [dict(source=origin, destination=target)]
        self.seal(v3)
        v4 = deepcopy(v3)
        v4['city_buildings'] = commands.panel_with_commands(v3['city_buildings'], available=True)
        network_turn.add_great_work_choices(v4, v4['city_buildings'])
        self.seal(v4)
        candidate = v4['candidates'][-1]
        request = dict(decision_id=v4['decision_id'], candidate_id=candidate['candidate_id'])
        self.assertEqual(network_turn.select_capability(v4, request), candidate['action'])
        v5 = deepcopy(v4)
        v5['city_buildings'].update(schema=city_buildings.GREAT_WORK_OVERVIEW_SCHEMA,
            great_work_building_bonuses=[dict(city_id=origin['city_id'], building_index=origin['building_index'],
                                              theme=None, yields={'YIELD_CULTURE':2}, tourism=0)])
        self.seal(v5)
        projected, transition = network_turn.checkpoint_catalogue(v5, v4, obs, core_sha256=XP2_CORE_SHA256)
        self.assertEqual(projected, v4)
        self.assertEqual(transition['added_public_fields'], ['city_buildings.great_work_building_bonuses'])
        self.assertEqual(transition['added_action_families'], [])
        projected, _ = network_turn.checkpoint_catalogue(v4, v3, obs, core_sha256=XP2_CORE_SHA256)
        self.assertEqual(projected, v3)
        no_panel = dict(old, schema=network_turn._city_buildings_checkpoint_base(old['schema'], old['schema']))
        del no_panel['city_buildings']
        self.seal(no_panel)
        without_panel, transition = network_turn.checkpoint_catalogue(v4, no_panel, obs, core_sha256=XP2_CORE_SHA256)
        self.assertEqual(without_panel, no_panel)
        self.assertEqual(transition['added_action_families'], [city_buildings.GREAT_WORK_MOVE])
        pid, turn = obs['player_id'], obs['turn']
        unit_orders = dict(player_id=pid, turn=turn, offers=[], units=[
            dict(unit_id=unit['id'], activity_type=0, fortify_turns=0, ready=True)
            for unit in sorted(obs['units'], key=lambda row: row['id'])])
        secondary = network_turn.secondary_unit_catalogue(
            SimpleNamespace(episode_id=v4['episode_id'], game_generation=v4['game_generation']),
            v4['sequence'], turn, pid, v4['turn_controls'], unit_orders, observation=obs,
            city_panels={'city_buildings': v4['city_buildings']})
        self.assertIn(candidate, secondary['candidates'])
        self.assertEqual(secondary['families'][city_buildings.GREAT_WORK_MOVE]['candidate_ids'],
                         [candidate['candidate_id']])
        v4['candidates'][-1]['action']['work_index'] = 13
        self.seal(v4)
        with self.assertRaisesRegex(ValueError, 'exact panel'):
            network_turn.checkpoint_catalogue(v4, v3, obs, core_sha256=XP2_CORE_SHA256)
        panel['rows'][0]['pillaged'] = not panel['rows'][0]['pillaged']
        self.seal(current)
        projected, _ = network_turn.checkpoint_catalogue(current, old, obs, core_sha256=XP2_CORE_SHA256)
        self.assertNotEqual(projected, old)
        self.assertEqual(projected['candidates'], old['candidates'])

    @staticmethod
    def seal(value):
        value.pop('decision_id', None)
        value['decision_id'] = network_turn.digest(value)
