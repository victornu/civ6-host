import copy
import unittest
from types import SimpleNamespace

from civ6_host.contracts import network_turn
from civ6_host.contracts.unit_work_state import validate
from civ6_host.runtime.unit_work_state import parse, source


class UnitWorkStateTests(unittest.TestCase):
    def setUp(self):
        self.state=parse(b'unit-work-state-v1|0|2\nU|9|3|2|0',0,2)
        self.obs=dict(player_id=0,turn=2,width=10,
                      units=[dict(id=9,owner=0,x=3,y=0,moves=0)])
        self.work=dict(player_id=0,turn=2,enabled=True,offers=[])

    def test_exhausted_own_unit_still_exposes_its_real_charges(self):
        validate(self.state,0,2,observation=self.obs,work_catalog=self.work)
        self.assertEqual(self.state['units'][0]['charges'],2)
        self.assertEqual(self.state['units'][0]['moves_token'],'0')

    def test_state_cannot_smuggle_other_units_positions_or_private_fields(self):
        for edit in (lambda s:s['units'][0].update(unit_id=10),
                     lambda s:s['units'][0].update(plot_id=4),
                     lambda s:s['units'][0].update(enemy_gold=50),
                     lambda s:s['units'][0].update(charges=True),
                     lambda s:s['units'][0].update(moves_token='nan'),
                     lambda s:s['units'].append(copy.deepcopy(s['units'][0]))):
            changed=copy.deepcopy(self.state);edit(changed)
            with self.assertRaises(ValueError):
                validate(changed,0,2,observation=self.obs)

    def test_offer_must_match_current_charges_and_movement(self):
        self.work['offers']=[dict(action=dict(self.state['units'][0]),legal=False)]
        validate(self.state,0,2,observation=self.obs,work_catalog=self.work)
        self.work['offers'][0]['action']['charges']=3
        with self.assertRaisesRegex(ValueError,'another charge'):
            validate(self.state,0,2,observation=self.obs,work_catalog=self.work)

    def test_native_reader_chunk_includes_zero_move_units(self):
        from lupa.lua51 import LuaRuntime
        lua=LuaRuntime(encoding=None)
        prelude=b'''
local u={GetOwner=function() return 0 end,GetID=function() return 9 end,
 GetX=function() return 3 end,GetY=function() return 0 end,
 GetMovesRemaining=function() return 0 end,GetBuildCharges=function() return 2 end}
Game={GetLocalPlayer=function() return 0 end,GetLocalObserver=function() return 0 end,
 GetCurrentGameTurn=function() return 2 end}
Players={[0]={IsAlive=function() return true end,IsTurnActive=function() return true end,
 IsTurnActiveComplete=function() return true end,
 GetUnits=function() return {Members=function() return ipairs({u}) end} end}}
PlayersVisibility={[0]={IsVisible=function() return true end,IsRevealed=function() return true end}}
Map={GetPlot=function(x,y)
 assert(x==3 and y==0)
 return {GetIndex=function() return 3 end,GetImprovementType=function() return 1 end,
  IsImprovementPillaged=function() return false end,GetRouteType=function() return -1 end,
  IsRoutePillaged=function() return false end}
end}
UnitOperationTypes={BUILD_IMPROVEMENT=1,PARAM_X=2,PARAM_Y=3,PARAM_IMPROVEMENT_TYPE=4}
'''
        raw=lua.execute(prelude+source(0,2))
        self.assertEqual(parse(raw,0,2),self.state)
        terrain = parse(lua.execute(prelude + source(0, 2, include_plot=True)),
                        0, 2, include_plot=True)
        self.assertEqual(terrain['units'][0], dict(self.state['units'][0], improvement=1,
            improvement_pillaged=False, route=-1, route_pillaged=False))
        self.obs['plots'] = [{'index': 3, 'visible': True}]
        validate(terrain, 0, 2, observation=self.obs, include_plot=True)
        self.obs['plots'][0]['visible'] = False
        with self.assertRaisesRegex(ValueError, 'outside the player visibility'):
            validate(terrain, 0, 2, observation=self.obs, include_plot=True)

    def catalogue(self):
        value=dict(schema=network_turn.WORK_SCHEMA,base_schema='fixture',
            episode_id='episode',game_generation='generation',sequence=0,player_id=0,turn=2,
            player_map={},candidates=[],unsupported=[],complete_action_space=False,
            unit_work=self.work,unit_work_state=self.state,
            turn_controls=dict(schema=network_turn.TURN_CONTROLS_SCHEMA,player_id=0,turn=2,
                active=True,active_complete=True,can_unready=False,timer_elapsed=False))
        value['decision_id']=network_turn.digest(value)
        return value

    def test_v4_wrapper_preserves_legacy_action_catalogue_and_version_boundary(self):
        value=self.catalogue();identity=SimpleNamespace(episode_id='episode',game_generation='generation')
        legacy=network_turn.validate_catalogue(value,identity,0,2,player_id=0)
        self.assertNotIn('unit_work_state',legacy)
        self.assertEqual(legacy['unit_work'],self.work)
        value['schema']=network_turn.SCHEMA
        value['decision_id']=network_turn.digest({k:v for k,v in value.items() if k!='decision_id'})
        with self.assertRaisesRegex(ValueError,'requires network-decisions.v4'):
            network_turn.validate_catalogue(value,identity,0,2,player_id=0)

    def test_checkpoint_transition_only_adds_verified_public_state(self):
        current=self.catalogue();saved={k:v for k,v in current.items() if k not in ('unit_work_state','decision_id')}
        saved['schema']=network_turn.SCHEMA;saved['decision_id']=network_turn.digest(saved)
        before=copy.deepcopy(saved)
        comparable,transition=network_turn.checkpoint_catalogue(current,saved,self.obs)
        self.assertEqual(comparable,saved)
        self.assertEqual(saved,before)
        self.assertEqual(transition['added_public_fields'],['unit_work_state'])
        current['unit_work_state']['units'][0]['plot_id']=5
        with self.assertRaises(ValueError):network_turn.checkpoint_catalogue(current,saved,self.obs)


if __name__=='__main__':unittest.main()
