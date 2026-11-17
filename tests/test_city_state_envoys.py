import unittest

from civ6_host.contracts import city_state_envoys, information, network_turn
from civ6_host.runtime import xp1_city_state_envoys

try:
    from lupa.lua51 import LuaError, LuaRuntime
except ImportError:
    LuaRuntime = None


class CityStateEnvoyTests(unittest.TestCase):
    def test_wire_refuses_duplicate_foreign_unsorted_or_oversized_values(self):
        for raw in (b'1:17|12:2', b'0:18|12:2', b'0:17|0:2', b'0:17|12:2|12:3',
                    b'0:17|13:2|12:1', b'0:17|12:2147483648', b'0:17|12:02',
                    b'0:17|12:-1', b'0:17|12:2:3'):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                xp1_city_state_envoys.parse(raw, 0, 17)

    def test_public_projection_uses_the_explicit_schema_and_detaches_the_count(self):
        native = xp1_city_state_envoys.parse(b'0:17|12:2', 0, 17)
        base = dict(schema=network_turn.CAPABILITY_XP1_GOVERNORS_SCHEMA, decision_id='previous',
                    candidates=[{'action': {'kind': 'force_end_turn'}}])
        obs = dict(player_id=0, turn=17)
        current = network_turn.upgrade_xp1_city_state_envoys_catalogue(base, native)
        self.assertEqual(current['candidates'], base['candidates'])
        self.assertEqual(base['decision_id'], 'previous')
        self.assertNotIn('city_state_envoys', base)
        data = information.project('city_state_envoys', obs, current)
        self.assertEqual(data['schema'], city_state_envoys.SCHEMA)
        data['city_states'][0]['own_envoys'] = 0
        self.assertEqual(current['city_state_envoys']['city_states'][0]['own_envoys'], 2)
        with self.assertRaises(ValueError):
            information.project('city_state_envoys', obs, dict(base, city_state_envoys=native))

    @unittest.skipIf(LuaRuntime is None, 'Lua 5.1 test runtime unavailable')
    def test_native_reader_never_reads_unmet_counts_and_binds_the_observer(self):
        lua = LuaRuntime(encoding=None)
        lua.execute(b"""
observer=0
Game={GetLocalPlayer=function() return 0 end,
      GetLocalObserver=function() return observer end,
      GetCurrentGameTurn=function() return 17 end}
GameInfo={GameCapabilities={CAPABILITY_CITY_STATES_VIEW={}}}
local diplomacy={HasMet=function(_,id) return id~=13 end}
Players={[0]={GetDiplomacy=function() return diplomacy end}}
local function minor(id, receives, count)
 return {
  GetID=function() return id end,
  GetInfluence=function()
   assert(id~=13, 'unmet city-state influence queried')
   return {
    CanReceiveInfluence=function() return receives end,
    GetTokensReceived=function(_,pid)
     assert(receives and pid==0)
     return count
    end
   }
  end
 }
end
PlayerManager={GetAliveMinors=function()
 return {minor(15,true,0),minor(13,true,12),minor(12,true,2),minor(14,false,8)}
end}
""")
        source = xp1_city_state_envoys.query_source(0, 17)
        self.assertEqual(lua.execute(source), b'0:17|12:2|15:0')
        lua.execute(b'observer=1')
        with self.assertRaises(LuaError):
            lua.execute(source)

    @unittest.skipIf(LuaRuntime is None, 'Lua 5.1 test runtime unavailable')
    def test_levy_query_uses_met_targets_and_native_button_predicate(self):
        from civ6_host.contracts import city_state_levies
        from civ6_host.runtime import xp1_city_state_levies as adapter

        lua = LuaRuntime(encoding=None)
        lua.execute(b"""
Game={GetLocalPlayer=function() return 0 end,
      GetLocalObserver=function() return 0 end,
      GetCurrentGameTurn=function() return 22 end,
      IsAllowStrategicCommands=function() return true end}
enabled=true
GameCapabilities={HasCapability=function() return enabled end}
local own={CanGiveTokensToPlayer=function() return false end,
           CanLevyMilitary=function(_,id) return id==12 end,
           GetLevyMilitaryCost=function(_,id) assert(id==12); return 310 end}
local function minor(id, active)
 return {GetID=function() return id end, IsAlive=function() return true end,
   GetInfluence=function()
    assert(id~=13,'unmet city-state was inspected')
    return {CanReceiveInfluence=function() return true end,
      GetTokensReceived=function(_,pid) assert(pid==0); return 4 end,
      GetLevyTurnCounter=function() return active and 0 or -1 end,
      GetSuzerain=function() return 0 end,
      GetLevyTurnLimit=function() assert(not active); return 30 end}
   end}
end
Players={[0]={IsAlive=function() return true end, IsTurnActive=function() return true end,
  IsTurnActiveComplete=function() return true end, GetInfluence=function() return own end,
  GetDiplomacy=function() return {HasMet=function(_,id) return id~=13 end} end},
  [12]=minor(12,false),[13]=minor(13,false),[14]=minor(14,true)}
PlayerManager={GetAliveMinors=function() return {Players[14],Players[13],Players[12]} end}
""")
        query = adapter.query_source(0, 22)
        state = adapter.parse(lua.execute(query), 0, 22)
        self.assertEqual(state['city_states'], [
            dict(player_id=12, can_levy=True, gold_cost=310, turn_limit=30, own_levy_active=False),
            dict(player_id=14, can_levy=False, gold_cost=None, turn_limit=None, own_levy_active=True)])
        self.assertEqual(city_state_levies.actions(state),
                         [dict(kind='levy_city_state_military', target_player_id=12)])
        lua.execute(b'enabled=false')
        self.assertEqual(city_state_levies.actions(adapter.parse(lua.execute(query), 0, 22)), [])

    def test_levy_effect_requires_charge_and_new_controlled_units(self):
        from civ6_host.runtime import xp1_city_state_levies as adapter

        before = dict(player_id=0, turn=22, economy={'gold': 1038.25}, units=[{'id': 1}])
        after = dict(before, economy={'gold': 728.25}, units=[{'id': 1}, {'id': 7}])
        target = dict(player_id=12, own_levy_active=True, can_levy=False)
        self.assertEqual(adapter._verify_effect(before, after, target, 310)['controlled_unit_ids'], [7])
        for bad in (dict(after, economy=before['economy']), dict(after, units=before['units'])):
            with self.subTest(bad=bad), self.assertRaises(RuntimeError):
                adapter._verify_effect(before, bad, target, 310)

    @unittest.skipIf(LuaRuntime is None, 'Lua 5.1 test runtime unavailable')
    def test_unit_levy_flags_use_official_sources_only_on_public_units(self):
        from civ6_host.runtime import xp1_city_state_levies as adapter

        lua = LuaRuntime(encoding=None)
        lua.execute(b"""
observer=0
Game={GetLocalPlayer=function() return 0 end,GetLocalObserver=function() return observer end,
      GetCurrentGameTurn=function() return 22 end}
local function unit(owner,id,x,original,properties)
 return {GetOwner=function() return owner end,GetID=function() return id end,
  GetX=function() return x end,GetY=function() return 0 end,IsDelayedDeath=function() return false end,
  GetCombat=function() return 20 end,GetOriginalOwner=function() return original end,
  GetProperty=function(_,key) return properties[key] end}
end
local hidden=setmetatable({},{__index=function() error('hidden unit data queried') end})
local function units(rows)
 return {GetUnits=function() return {FindID=function(_,id)
  assert(id~=5,'unit looked up behind fog')
  return assert(rows[id])
 end} end}
end
Players={[0]=units({[3]=unit(0,3,0,12,{}),[4]=unit(0,4,1,0,{})}),
 [1]=units({[5]=hidden,[6]=hidden,[4294967295]=unit(1,4294967295,2,13,{LEVY_TURN=20,LEVY_DURATION=2})}),
 [12]={GetInfluence=function() return {GetLevyTurnCounter=function() return 2 end,
  GetSuzerain=function() return 0 end,GetLevyTurnLimit=function() return 15 end} end}}
PlayersVisibility={[0]={IsVisible=function(_,x) return x~=3 end,
                        IsUnitVisible=function(_,u) return u~=hidden end}}
""")
        obs = dict(player_id=0, turn=22, width=5, height=1,
                   units=[dict(owner=0,id=3,x=0,y=0),dict(owner=0,id=4,x=1,y=0)],
                   visible_enemy_units=[dict(owner=1,id=5,x=3,y=0,visible=True),
                                        dict(owner=1,id=6,x=4,y=0,visible=True),
                                        dict(owner=1,id=4294967295,x=2,y=0,visible=True)])
        source = adapter.unit_query_source(obs)
        flags = adapter.parse_unit_flags(lua.execute(source), obs)
        self.assertEqual(flags['units'], [
            dict(owner=0, unit_id=3, original_owner=12, turns_remaining=13),
            dict(owner=1, unit_id=4294967295, original_owner=13, turns_remaining=0)])
        lua.execute(b'observer=1')
        with self.assertRaises(LuaError):
            lua.execute(source)
        for raw in (b'0:23', b'0:22|1:7:12:1', b'0:22|0:3:0:1', b'0:22|0:3:12:1|0:3:12:1'):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                adapter.parse_unit_flags(raw, obs)
