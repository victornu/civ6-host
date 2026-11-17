"""World Rankings score gate, exact projection and native source pins."""

from copy import deepcopy
from hashlib import sha256
import json
from types import SimpleNamespace
import unittest

from civ6_host.contracts import information, network_turn
from civ6_host.runtime import world_score, xp1_saved_load, xp2_bbg_inputs, xp2_bundle_inputs
from civ6_host.runtime.execution_images import _PROFILE, _XP1_PROFILE
from civ6_host.runtime.paths import resource_root
from test_session_capabilities import seal


PRELUDE = b'''
local function major(id, team, score, civics, era)
    return {
        GetID = function() return id end,
        GetTeam = function() return team end,
        GetScore = function() assert(scoreTab); return score end,
        GetCategoryScore = function(_, index)
            if index == 0 then return civics end
            if index == 2 then return era end
            error('category concealed by official panel')
        end,
        IsAlive = function() return true end,
        IsMajor = function() return true end
    }
end
scoreTab=true
MP=true
scoreEnabled=false
Game = {
    GetLocalPlayer = function() return 0 end,
    GetLocalObserver = function() return currentObserver or 0 end,
    GetCurrentGameTurn = function() return 23 end,
    GetMaxGameTurns = function() return 500 end,
    IsVictoryEnabled = function(key) assert(key == 'VICTORY_SCORE'); return scoreEnabled end
}
GameConfiguration = {IsAnyMultiplayer = function() return MP end}
local owner=major(0, 4, 12, 2, 0)
owner.GetDiplomacy = function() return {HasMet = function(_, id) return id == 7 or metStranger == id end} end
Players = {[0] = owner}
PlayerManager = {GetAliveMajors = function()
    assert(scoreTab)
    return {owner, major(strangerID or 5, strangerTeam or 9, 29, 7, 2), major(7, 4, 14, 4, 1)}
end}
GameInfo = {ScoringCategories = setmetatable({
    [0]={Multiplier=1, CategoryType='CATEGORY_CIVICS'},
    [1]={Multiplier=0, CategoryType='CATEGORY_PILLAGE'},
    [2]={Multiplier=1, CategoryType='CATEGORY_ERA_SCORE'},
    [3]={Multiplier=0}
}, {})}
'''


class WorldScoreTests(unittest.TestCase):
    def lua(self):
        from lupa.lua51 import LuaRuntime
        lua = LuaRuntime(encoding=None)
        lua.execute(PRELUDE)
        return lua

    def test_multiplayer_scores_do_not_reveal_unmet_ids_or_teams(self):
        lua = self.lua()
        source = world_score.build_source(0, 23)
        raw = lua.execute(source)
        data = world_score.parse(raw, 0, 23)
        self.assertEqual(data['categories'], ['CATEGORY_CIVICS', 'CATEGORY_ERA_SCORE'])
        self.assertFalse(data['score_victory_enabled'])
        self.assertEqual(data['max_game_turns'], 500)
        self.assertEqual(data['teams'], [
            dict(score=29, players=[dict(player_id=None, score=29, category_scores=[7, 2])]),
            dict(score=26, players=[dict(player_id=7, score=14, category_scores=[4, 1]),
                                   dict(player_id=0, score=12, category_scores=[2, 0])]),
        ])
        lua.execute(b'strangerID=11; strangerTeam=14')
        self.assertEqual(lua.execute(source), raw)
        lua.execute(b'metStranger=11')
        known = world_score.parse(lua.execute(source), 0, 23)
        self.assertEqual(known['teams'][0]['players'][0]['player_id'], 11)

    def test_gate_and_perspective_precede_score_reads(self):
        from lupa.lua51 import LuaError
        lua = self.lua()
        source = world_score.build_source(0, 23)
        lua.execute(b'MP=false; scoreTab=false')
        self.assertIsNone(world_score.parse(lua.execute(source), 0, 23))
        lua.execute(b'scoreEnabled=true; scoreTab=true')
        self.assertTrue(world_score.parse(lua.execute(source), 0, 23)['score_victory_enabled'])
        lua.execute(b'currentObserver=5; scoreTab=false')
        with self.assertRaisesRegex(LuaError, 'stale world score'):
            lua.execute(source)

    def test_score_projects_from_a_native_checkpoint_without_changing_choices(self):
        root = resource_root()
        proof = json.loads((root/'evidence/host-xp1-stock-building-unit-purchase-save-reload-native.json').read_bytes())
        reference = proof['saved']['output_checkpoint']
        raw = (root/reference['path']).read_bytes()
        self.assertEqual(sha256(raw).hexdigest(), reference['sha256'])
        checkpoint = json.loads(raw)
        original = checkpoint['decisions']
        observation = checkpoint['observation']
        current = deepcopy(original)
        source = world_score.build_source(0, 23)
        current['world_score'] = world_score.parse(self.lua().execute(source), 0, 23)
        seal(current)
        published = information.project('world_score', observation, current)
        self.assertEqual(published, current['world_score'])
        self.assertIsNot(published, current['world_score'])
        projected, receipt = network_turn.checkpoint_world_score_projection(current, original, observation)
        self.assertEqual(projected, original)
        self.assertEqual(receipt['added_action_families'], [])

        existing = deepcopy(current)
        current['world_score']['max_game_turns'] += 1
        seal(current)
        projected, receipt = network_turn.checkpoint_world_score_projection(current, existing, observation)
        self.assertIsNone(receipt)
        self.assertNotEqual(projected, existing)
        current['world_score']['teams'][0]['players'][0]['team_id'] = 9
        seal(current)
        with self.assertRaisesRegex(ValueError, 'Invalid public player score'):
            network_turn.checkpoint_world_score_projection(current, original, observation)

    def test_exact_ui_and_binding_pins_for_both_images_and_bbg_replacement(self):
        import pefile
        from civ6_host.runtime.a0_family_source import verify_pinned_files

        for reference, image in ((xp1_saved_load.REFERENCE, _XP1_PROFILE),
                                 (xp2_bundle_inputs.REFERENCE, _PROFILE),
                                 (xp2_bbg_inputs.REFERENCE, _PROFILE)):
            with self.subTest(image=image.id, reference=reference[0]):
                pins = world_score.source_dependencies(reference, image)
                verify_pinned_files(pins)
                self.assertEqual(any(p.lower().endswith('worldrankings_bbg.lua') for p in pins),
                                 reference == xp2_bbg_inputs.REFERENCE)
                pe = pefile.PE(str(image.path), fast_load=True)
                try:
                    base = pe.OPTIONAL_HEADER.ImageBase
                    core = SimpleNamespace(_handle=base, _civ6_host_execution_image=image)
                    runtime = SimpleNamespace(read=lambda address, size: pe.get_data(address-base, size))
                    owner = SimpleNamespace(core=core, runtime=runtime)
                    saved = SimpleNamespace(backend=owner, inputs=SimpleNamespace(official_bundle=reference),
                                            continuation=SimpleNamespace(owner=owner))
                    world_score.bind(saved)
                    world_score.require_owner(saved)
                    runtime.read = lambda address, size: bytes(size)
                    with self.assertRaisesRegex(ValueError, 'native binding'):
                        world_score.bind(saved)
                finally:
                    pe.close()
        with self.assertRaisesRegex(ValueError, 'exact stock expansion'):
            world_score.source_dependencies(('other', 'a'*64), _PROFILE)
