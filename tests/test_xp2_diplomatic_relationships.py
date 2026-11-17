from copy import deepcopy
import json
import unittest

from civ6_host.contracts import diplomacy_overview, information, network_turn
from civ6_host.runtime import xp2_diplomatic_relationships as relationships
import test_initial_diplomacy_capabilities as capability_fixture

try:
    from lupa.lua51 import LuaError, LuaRuntime
except ImportError:
    LuaRuntime = None


LUA = '''
viewer,targetID,turn=0,2,57
ours,theirs,stateIndex,allianceType=57,-1,1,-1
human,met=false,true
Game={GetLocalPlayer=function() return viewer end,
 GetLocalObserver=function() return viewer end,
 GetCurrentGameTurn=function() return turn end,
 GetGameDiplomacy=function() return {GetDenounceTimeLimit=function() return 30 end} end}
GameInfo={DiplomaticStates={
 {StateType='DIPLO_STATE_DENOUNCED'},
 {StateType='DIPLO_STATE_DECLARED_FRIEND'},
 {StateType='DIPLO_STATE_ALLIED'},
 {StateType='DIPLO_STATE_NEUTRAL'}}}
function actors()
 local actorDiplomacy={
  HasMet=function(_,id) assert(id==targetID); return met end,
  GetGrievancesAgainst=function(_,id) assert(id==targetID); return -25 end,
  GetDenounceTurn=function(_,id) assert(id==targetID); return ours end,
  GetDeclaredFriendshipTurn=function(_,id) assert(id==targetID); return 55 end,
  GetAllianceType=function(_,id) assert(id==targetID); return allianceType end,
  GetAllianceTurnsUntilExpiration=function(_,id) assert(id==targetID); return 19 end}
 local selectedDiplomacy={GetDenounceTurn=function(_,id) assert(id==viewer); return theirs end}
 Players={
  [viewer]={GetDiplomacy=function() return actorDiplomacy end},
  [targetID]={GetID=function() return targetID end,
   IsMajor=function() return true end,
   IsHuman=function() return human end,
   GetDiplomacy=function() assert(not human); return selectedDiplomacy end,
   GetDiplomaticAI=function() assert(not human);
    return {GetDiplomaticStateIndex=function(_,id) assert(id==viewer); return stateIndex end} end}}
end
'''


def frame(viewer=0, target=2):
    return dict(schema=diplomacy_overview.SCHEMA, player_id=viewer, turn=57,
                capability=True, paused=False, complete_action_space=False,
                targets=[dict(player_id=target, selections=[])])


class DiplomaticRelationshipsTests(unittest.TestCase):
    def test_native_rows_must_match_the_same_targets_and_exclude_extra_values(self):
        for raw in (b'[]', b'[{"player_id":3,"relationship":null}]',
                    b'[{"player_id":2,"relationship":null,"ai_mood":0}]',
                    b'[{"player_id":2,"relationship":{"state":"DIPLO_STATE_DENOUNCED","grievances":1,"expiration":null}}]'):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                relationships.parse(frame(), raw)

    @unittest.skipIf(LuaRuntime is None, 'Lua fixture unavailable')
    def test_signed_grievances_denunciation_order_and_alliance_tooltip(self):
        cases = [
            ('', 0, 2, 'denunciation', 31, 0),
            ('theirs=57', 0, 2, 'denunciation', 32, 0),
            ('ours=-1; theirs=57', 0, 2, 'denunciation', 32, 2),
            ('viewer=2; targetID=0', 2, 0, 'denunciation', 32, 2),
            ('stateIndex=2', 0, 2, 'friendship', 28, None),
            ('stateIndex=2; allianceType=1', 0, 2, 'alliance', 19, None),
        ]
        for setup, viewer, target, kind, turns, denouncer in cases:
            with self.subTest(setup=setup):
                lua = LuaRuntime()
                lua.execute(LUA + '\n' + setup + '\nactors()')
                before = frame(viewer, target)
                wire = lua.execute(relationships._source(before).decode('ascii')).encode('ascii')
                relationship, = relationships.parse(before, wire)['targets']
                self.assertEqual(relationship['relationship']['grievances'], -25)
                self.assertEqual(relationship['relationship']['expiration'], dict(
                    kind=kind, turns_remaining=turns, denouncer_player_id=denouncer))

    @unittest.skipIf(LuaRuntime is None, 'Lua fixture unavailable')
    def test_hidden_human_and_unmet_or_wrong_viewer(self):
        lua = LuaRuntime()
        lua.execute(LUA + '\nhuman=true\nactors()')
        before = frame()
        code = relationships._source(before).decode('ascii')
        row, = relationships.parse(before, lua.execute(code).encode('ascii'))['targets']
        self.assertIsNone(row['relationship'])
        lua.execute('met=false')
        with self.assertRaisesRegex(LuaError, 'met major'):
            lua.execute(code)
        lua.execute('viewer=1')
        with self.assertRaisesRegex(LuaError, 'player or turn'):
            lua.execute(code)

    def test_capability_checkpoint_projection_keeps_old_actions_and_rejects_foreign_expiration(self):
        capability_fixture.InitialDiplomacyCapabilityTests.setUpClass()
        fixture = capability_fixture.InitialDiplomacyCapabilityTests()
        saved, obs = fixture._active_v33()
        current = deepcopy(saved)
        overview = current['diplomacy_overview']
        wire = [dict(player_id=2, relationship=dict(state='DIPLO_STATE_DENOUNCED', grievances=-25,
                    expiration=dict(kind='denunciation', turns_remaining=31, denouncer_player_id=0)))]
        current['diplomacy_overview'] = relationships.parse(overview, json.dumps(wire).encode())
        fixture._redigest(current)
        fixture._validate(current, obs)
        projected, transition = network_turn.checkpoint_catalogue(
            current, saved, obs, core_sha256=capability_fixture.XP2_CORE)
        self.assertEqual(projected, saved)
        self.assertEqual(transition['added_public_fields'], ['diplomacy_overview.targets[].relationship'])
        self.assertEqual(transition['added_action_families'], [])
        readback = information.project('diplomacy', obs, current)
        self.assertEqual(readback['targets'][0]['relationship'], wire[0]['relationship'])
        readback['targets'][0]['relationship']['expiration']['denouncer_player_id'] = 63
        with self.assertRaises(ValueError):
            diplomacy_overview.validate(readback, obs['player_id'], obs['turn'])
        with self.assertRaises(ValueError):
            network_turn.checkpoint_catalogue(current, saved, obs, core_sha256=None)


if __name__ == '__main__':
    unittest.main()
