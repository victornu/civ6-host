import copy
import unittest
from pathlib import Path
from civ6_host.contracts import network_turn
from civ6_host.contracts.unit_work_info import validate
from civ6_host.runtime import unit_work_info as info

FRAME=(b'work-info-v1|0|7\nO|O|10|2|3|32|2|2|HARVEST_RESOURCE|8|0\n'
       b'A|1|48617276657374\nD|1|4761696e203130\nR|1|5265736561726368206669727374\n'
       b'P|10|32|-1|0|1|1\n')


class WorkInformationTests(unittest.TestCase):
    def test_disabled_visible_details_and_pillaged_route_join_own_unit(self):
        catalog,data=info.parse(FRAME,0,7)
        obs=dict(player_id=0,turn=7,width=10,units=[dict(id=10,owner=0,x=2,y=3)],
                 plots=[dict(index=32,visible=True)])
        validate(data,0,7,work_catalog=catalog,observation=obs)
        self.assertEqual(data['offers'][0]['failure_reasons'],['Research first'])
        self.assertFalse(catalog['offers'][0]['legal'])
        self.assertTrue(data['targets'][0]['route_pillaged'])
        obs['units'][0]['owner']=1
        with self.assertRaises(ValueError):validate(data,0,7,work_catalog=catalog,observation=obs)

    def test_foreign_or_duplicate_details_refused(self):
        for frame in [FRAME.replace(b'A|1|',b'A|2|'),FRAME+b'A|1|41\n',
                      FRAME.replace(b'7\n',b'8\n',1),FRAME.replace(b'48617276657374',b'4A'),
                      FRAME.replace(b'8|0\n',b'8|1\n'),FRAME+b'P|10|32|-1|0|1|1\n']:
            with self.subTest(frame=frame):
                with self.assertRaises(ValueError):info.parse(frame,0,7)

    def test_offer_identity_and_private_target_injection_refused(self):
        catalog,data=info.parse(FRAME,0,7)
        changed=copy.deepcopy(data);changed['offers'][0]['action']['unit_id']=11
        # Copies cannot retain an alias into the authoritative catalogue.
        with self.assertRaises(ValueError):validate(changed,0,7,work_catalog=catalog)
        data['targets'].append(dict(data['targets'][0],unit_id=99))
        obs=dict(player_id=0,turn=7,width=10,units=[dict(id=10,owner=0,x=2,y=3)],plots=[dict(index=32,visible=True)])
        with self.assertRaises(ValueError):validate(data,0,7,work_catalog=catalog,observation=obs)

    def test_detailed_xp2_projection_joins_existing_state_and_retains_v16(self):
        from civ6_host.contracts import information
        from civ6_host.contracts.unit_work_state import PLOT_SCHEMA

        catalog, data = info.parse(FRAME, 0, 7)
        obs = dict(player_id=0, turn=7, width=10,
                   units=[dict(id=10, owner=0, x=2, y=3, moves=2)],
                   plots=[dict(index=32, x=2, y=3, visible=True)])
        state = dict(schema=PLOT_SCHEMA, player_id=0, turn=7,
                     units=[dict(data['targets'][0], charges=2, moves_token='2')])
        decisions = dict(schema=network_turn.CAPABILITY_UNIT_WORK_STATE_SCHEMA,
                         unit_work=catalog, unit_work_state=state)
        old = information.project('unit_work', obs, decisions)
        self.assertEqual(old['schema'], information.UNIT_WORK_CATALOGUE_GROUP_SCHEMA)
        self.assertNotIn('info', old)
        decisions.update(schema=network_turn.CAPABILITY_UNIT_WORK_INFO_SCHEMA, unit_work_info=data)
        current = information.project('unit_work', obs, decisions)
        self.assertEqual(current['schema'], information.UNIT_WORK_DETAILED_GROUP_SCHEMA)
        self.assertEqual(current['info']['offers'][0]['descriptions'], ['Gain 10'])
        data['targets'][0]['route_pillaged'] = False
        with self.assertRaisesRegex(ValueError, 'targets differ'):
            information.project('unit_work', obs, decisions)

    def test_v4_checkpoint_projection_preserves_actions_and_old_fields(self):
        catalog,data=info.parse(FRAME,0,7)
        old=dict(schema=network_turn.WORK_SCHEMA,base_schema='native',unit_work=catalog,
                 unit_work_state={'untouched':'historical'},candidates=[])
        old['decision_id']=network_turn.digest(old)
        current=dict(old,schema=network_turn.INFO_SCHEMA,unit_work_info=data)
        current['decision_id']=network_turn.digest({k:v for k,v in current.items() if k!='decision_id'})
        obs=dict(player_id=0,turn=7,width=10,units=[dict(id=10,owner=0,x=2,y=3)],plots=[dict(index=32,visible=True)])
        projected,transition=network_turn.checkpoint_catalogue(current,old,obs)
        self.assertEqual(projected,old)
        self.assertEqual(transition['added_public_fields'],['unit_work_info'])
        self.assertEqual(current['schema'],network_turn.INFO_SCHEMA)

    def test_native_lua_retains_result_details_without_extra_availability_calls(self):
        from lupa.lua51 import LuaRuntime
        from civ6_host.runtime.native.native_saved_unit_work import LUA
        lua=LuaRuntime(encoding=None)
        setup=b'''
local pid,turn=0,7
calls=0;localizations=0
Game={GetLocalPlayer=function() return 0 end,GetLocalObserver=function() return 0 end,GetCurrentGameTurn=function() return 7 end}
local u={GetOwner=function() return 0 end,GetID=function() return 10 end,GetMovesRemaining=function() return 2 end,GetX=function() return 2 end,GetY=function() return 3 end,GetBuildCharges=function() return 2 end}
local plot={GetIndex=function() return 32 end,GetImprovementType=function() return -1 end,IsImprovementPillaged=function() return false end,GetRouteType=function() return 1 end,IsRoutePillaged=function() return true end}
Map={GetPlot=function() return plot end}
Players={[0]={IsAlive=function() return true end,IsTurnActive=function() return true end,IsTurnActiveComplete=function() return true end,GetUnits=function() return {Members=function() return ipairs({u}) end} end}}
PlayersVisibility={[0]={IsVisible=function() return true end,IsRevealed=function() return true end}}
UnitOperationTypes={BUILD_IMPROVEMENT=1,PARAM_X=2,PARAM_Y=3,PARAM_IMPROVEMENT_TYPE=4}
InterfaceModeTypes={NONE=0};OperationResultsTypes={NO_TARGETS=9}
UnitOperationResults={IMPROVEMENTS='improvements',ACTION_NAME='name',FEATURE_TYPE='feature',ADDITIONAL_DESCRIPTION='description',FAILURE_REASONS='failure'}
GameInfo={Improvements={},Features={[3]={Name='Woods'}},UnitOperations={UNITOPERATION_HARVEST_RESOURCE={Hash=8,VisibleInUI=true}}}
UnitManager={CanStartOperation=function(unit,op,_,arg,results)
 calls=calls+1
 if op==1 then return false end
 if arg==true then return true end
 assert(op==8 and arg==false and results==9)
 return false,{name='Harvest',feature=3,description={'Gain 10'},failure={'Research first'}}
end}
Locale={Lookup=function(s) localizations=localizations+1;return s end}
'''
        raw=lua.execute(setup+LUA.encode()+b'\nlocal processing=true\n'+info.LUA.encode())
        catalog,data=info.parse(raw,0,7)
        self.assertEqual(lua.globals().calls,3) # 1 build visibility, 2 generic; no second metadata query
        self.assertEqual(lua.globals().localizations,4)
        self.assertEqual(data['offers'][0]['feature'],{'index':3,'name':'Woods'})
        self.assertEqual(data['offers'][0]['descriptions'],['Gain 10'])
        self.assertFalse(catalog['offers'][0]['legal'])


if __name__=='__main__':unittest.main()
