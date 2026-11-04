import copy
import json
import unittest
from civ6_host.contracts.city_growth import validate
from civ6_host.contracts import network_turn
from civ6_host.runtime import city_growth as growth


def fixture(**changes):
    from lupa.lua51 import LuaRuntime
    state=dict(food=4.12345,threshold=20,surplus=2.34,growing=7,starving=-1,occupied=False,
               housing=5,amenities=0,needed=1,happiness=3,happy_modifier=0,other_modifier=0,
               housing_modifier=1,occupation_modifier=1,food_yield=6.375,population=2)
    state.update(changes)
    lua=LuaRuntime(encoding=None)
    lua.globals().s=lua.table_from({k.encode():v for k,v in state.items()})
    setup=b'''
-- The official host context restricts dynamic loaders; keep the projection
-- lexical instead of depending on standalone Lua's environment functions.
loadstring=nil;setfenv=nil
Game={GetLocalPlayer=function() return 0 end,GetLocalObserver=function() return 0 end,GetCurrentGameTurn=function() return 7 end}
local g={GetFood=function() return s.food end,GetGrowthThreshold=function() return s.threshold end,GetFoodSurplus=function() return s.surplus end,
 GetTurnsUntilGrowth=function() return s.growing end,GetTurnsUntilStarvation=function() return s.starving end,
 GetHousing=function() return s.housing end,GetAmenities=function() return s.amenities end,GetAmenitiesNeeded=function() return s.needed end,
 GetHappiness=function() return s.happiness end,GetHappinessGrowthModifier=function() return s.happy_modifier end,
 GetOtherGrowthModifier=function() return s.other_modifier end,GetHousingGrowthModifier=function() return s.housing_modifier end,
 GetOccupationGrowthModifier=function() return s.occupation_modifier end}
local city={GetID=function() return 11 end,GetOwner=function() return 0 end,GetGrowth=function() return g end,
 GetPopulation=function() return s.population end,IsOccupied=function() return s.occupied end,GetYield=function() return s.food_yield end}
Players={[0]={GetCities=function() return {Members=function() return ipairs({city}) end} end}}
YieldTypes={FOOD=0};lookup_calls={}
Locale={Lookup=function(key,...)
 local args={...};lookup_calls[#lookup_calls+1]={key=key,args=args}
 if string.find(key,'{1',1,true) then return string.format('%.1f',args[1]) end
 return key
end}
'''
    lua.execute(setup)
    raw=lua.execute(growth.source(0,7))
    public,private=growth.parse(raw,0,7)
    return public,private,raw,lua


class CityGrowthTests(unittest.TestCase):
    def test_shipped_growth_projection_without_private_stock(self):
        public,private,raw,_=fixture()
        row=public['cities'][0]
        self.assertEqual(row['display']['GrowthLongNum'],7)
        self.assertEqual(row['display']['FoodNeededForGrowth'],'15.9')
        self.assertEqual(row['display']['FoodPerTurnNum'],'6.3')
        self.assertEqual(row['display']['NetFoodPerTurn'],'2.3')
        self.assertFalse(row['starving'])
        self.assertEqual(row['growth_icon']['v'],150)
        self.assertEqual(private[0]['food_stock'],4.12345)
        for key in ('food_stock','growth_threshold','food_surplus','turns_until_growth','turns_until_starvation'):
            self.assertNotIn('"'+key+'"',json.dumps(public))
        self.assertNotIn('4.12345',json.dumps(public))

    def test_starvation_zero_and_occupation_use_official_branches(self):
        p,_,_,_=fixture(growing=-1,starving=3,surplus=-2)
        row=p['cities'][0];self.assertTrue(row['starving']);self.assertEqual(row['display']['GrowthLongNum'],3)
        self.assertEqual(row['display']['HousingMultiplier'],'LOC_HUD_CITY_NOT_APPLICABLE')
        self.assertEqual(row['growth_icon']['v'],0)
        p,_,_,_=fixture(growing=-1,starving=-1,surplus=0)
        self.assertEqual(p['cities'][0]['display']['GrowthLongNum'],0)
        self.assertEqual(p['cities'][0]['growth_icon']['v'],100)
        p,_,_,_=fixture(occupied=True,occupation_modifier=0)
        row=p['cities'][0];self.assertEqual(row['display']['GrowthLongNum'],0)
        self.assertEqual(row['display']['TurnsUntilBornLost'],'LOC_HUD_CITY_GROWTH_OCCUPIED')
        self.assertEqual(row['growth_icon']['v'],100)

    def test_modifier_and_rounding_are_executed_from_shipped_function(self):
        p,_,_,lua=fixture(happy_modifier=10,other_modifier=.15,housing_modifier=.5)
        calls=[v for _,v in lua.globals().lookup_calls.items()]
        # Native data surplus 2.34 is first rounded to 2.3 by CitySupport.
        # The actual shipped panel rounds its modified food to 2.88 before housing.
        values=[c[b'args'][1] for c in calls if c[b'args'][1] is not None]
        self.assertIn(2.88,values);self.assertIn(1.44,values)

    def test_exact_own_city_roster_and_population_required(self):
        p,_,_,_=fixture();obs=dict(player_id=0,turn=7,cities=[dict(id=11,owner=0,population=2)])
        validate(p,0,7,observation=obs)
        for row in [dict(id=11,owner=1,population=2),dict(id=11,owner=0,population=3),dict(id=12,owner=0,population=2)]:
            with self.assertRaises(ValueError):validate(p,0,7,observation=dict(obs,cities=[row]))
        leaked=copy.deepcopy(p);leaked['cities'][0]['food_stock']=4.12345
        with self.assertRaises(ValueError):validate(leaked,0,7)

    def test_frame_rejects_foreign_duplicate_and_unknown_display(self):
        _,_,raw,_=fixture()
        for frame in [raw.replace(b'city-growth-v1|0|7',b'city-growth-v1|1|7'),
                      raw+b'\nV|11|FoodNeededForGrowth|string|31',
                      raw.replace(b'FoodNeededForGrowth',b'hidden_raw_stock')]:
            with self.assertRaises(ValueError):growth.parse(frame,0,7)

    def test_checkpoint_v5_projection_does_not_rewrite_old_fields(self):
        public,_,_,_=fixture()
        old=dict(schema=network_turn.INFO_SCHEMA,base_schema='native',candidates=[],unit_work_info={'unchanged':True})
        old['decision_id']=network_turn.digest(old)
        current=dict(old,schema=network_turn.GROWTH_SCHEMA,city_growth=public)
        current['decision_id']=network_turn.digest({k:v for k,v in current.items() if k!='decision_id'})
        obs=dict(player_id=0,turn=7,cities=[dict(id=11,owner=0,population=2)])
        projected,transition=network_turn.checkpoint_catalogue(current,old,obs)
        self.assertEqual(projected,old)
        self.assertEqual(transition['added_public_fields'],['city_growth'])


if __name__=='__main__':unittest.main()
