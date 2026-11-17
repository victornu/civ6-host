import unittest
from copy import deepcopy
from hashlib import sha256
import json
from types import SimpleNamespace
from unittest.mock import patch

from lupa.lua51 import LuaError, LuaRuntime

from civ6_host.runtime.native import native_saved_unit_work as work
from civ6_host.runtime import unit_work_info, xp2_lan_unit_work


FIXTURE = b"""
Game={GetLocalPlayer=function() return 0 end,GetLocalObserver=function() return 0 end,
 GetCurrentGameTurn=function() return 7 end}
local u={GetOwner=function() return 0 end,GetID=function() return 10 end,
 GetMovesRemaining=function() return 2 end,GetX=function() return 2 end,
 GetY=function() return 3 end,GetBuildCharges=function() return 2 end}
Players={[0]={IsAlive=function() return true end,IsTurnActive=function() return true end,
 IsTurnActiveComplete=function() return true end,
 GetUnits=function() return {Members=function() return ipairs({u}) end} end}}
PlayersVisibility={[0]={IsVisible=function(x,y) return not hidden or x==2 end,
 IsRevealed=function() return true end}}
local source={GetIndex=function() return 32 end}
local target={GetIndex=function() return 33 end,GetX=function() return 3 end,
 GetY=function() return 3 end}
Map={GetPlot=function(x,y) return x==2 and source or target end,
 GetPlotByIndex=function(id) assert(id==33);return target end,
 IsPlot=function(id) return id==33 end}
UnitOperationTypes={BUILD_IMPROVEMENT=1,BUILD_IMPROVEMENT_ADJACENT=5,
 PARAM_X=2,PARAM_Y=3,PARAM_IMPROVEMENT_TYPE=4}
UnitOperationResults={IMPROVEMENTS='improvements',PLOTS='plots'}
GameInfo={UnitOperations={},Improvements={[12]={Index=21,Hash=-42,
 ImprovementType='IMPROVEMENT_MOUNTAIN_ROAD'}}}
UnitManager={
 CanStartOperation=function(unit,op,_,arg,details)
  assert(unit==u)
  if op==1 then return false end
  assert(op==5)
  if details then assert(next(arg)==nil);return true,{improvements={12}} end
  assert(arg[2]==3 and arg[3]==3 and arg[4]==-42)
  return not refused
 end,
 GetOperationTargets=function(unit,op,arg)
  assert(unit==u and op==5 and arg[4]==-42 and arg[2]==nil and arg[3]==nil)
  return {plots={33}}
 end,
 RequestOperation=function(unit,op,arg)
  assert(unit==u and op==5 and arg[2]==3 and arg[3]==3 and arg[4]==-42)
  requests=(requests or 0)+1
 end}
"""


class AdjacentUnitWorkTest(unittest.TestCase):
    def setUp(self):
        self.lua = LuaRuntime(encoding=None)
        self.lua.execute(FIXTURE)

    def test_native_parameters_and_exact_revalidation(self):
        raw = self.lua.execute(work.catalog_source(0, 7, adjacent=True))
        action, = work.actions(work.parse_catalog(raw, 0, 7, adjacent=True))
        self.assertEqual((action['source_plot_id'], action['plot_id'], action['selector'],
                          action['index'], action['hash']), (32, 33, 12, 21, 2**32 - 42))
        with self.assertRaises(ValueError):
            work.parse_catalog(raw, 0, 7)
        self.assertEqual(self.lua.execute(work.request_source(action, 0, 7)), b'submitted')
        self.lua.execute(b'refused=true')
        with self.assertRaises(LuaError):
            self.lua.execute(work.request_source(action, 0, 7))
        self.assertEqual(self.lua.eval(b'requests'), 1)

    def test_disabled_by_default_and_hidden_target_refused(self):
        self.assertEqual(self.lua.execute(work.catalog_source(0, 7)), b'work-v1|0|7')
        self.lua.execute(b'hidden=true')
        with self.assertRaises(LuaError):
            self.lua.execute(work.catalog_source(0, 7, adjacent=True))

    def test_public_readback_uses_visibility_before_reading_work_details(self):
        self.lua.execute(b"""
local function plot(id, x, y, improvement, route, hidden)
 local p={
  GetIndex=function() return id end,GetX=function() return x end,GetY=function() return y end,
  GetImprovementType=function() assert(not hidden); return improvement end,
  GetRouteType=function() assert(not hidden); return route end,
  IsImprovementPillaged=function() assert(not hidden); return false end,
  IsRoutePillaged=function() assert(not hidden); return route>=0 end}
 return p
end
local source=plot(0,2,3,-1,1,false)
local target=plot(1,3,3,21,-1,false)
local hidden=plot(2,4,3,999,999,true)
local plots={[0]=source,target,hidden}
Map.GetPlot=function(x,y) return x==2 and source or target end
Map.GetPlotByIndex=function(id) return plots[id] end
Map.GetPlotCount=function() return 3 end
PlayersVisibility[0].IsVisible=function(_,x,y) return x~=4 end
""")
        raw = self.lua.execute(unit_work_info.source(0, 7, False, adjacent=True))
        catalog, info = unit_work_info.parse(raw, 0, 7, False, adjacent=True)
        self.assertFalse(catalog['enabled'])
        self.assertEqual([row['plot_id'] for row in info['visible_plots_with_work']], [0, 1])
        self.assertEqual(info['visible_plots_with_work'][1]['improvement'], 21)
        self.assertTrue(info['visible_plots_with_work'][0]['route_pillaged'])
        with self.assertRaises(ValueError):
            unit_work_info.parse(raw, 0, 7, False)

    def test_generic_repair_route_index_does_not_require_an_enum_alias(self):
        self.lua.execute(b"""
assert(UnitOperationTypes.REPAIR_ROUTE==nil)
GameInfo.UnitOperations.UNITOPERATION_REPAIR_ROUTE={Index=32,Hash=228327966}
""")
        prefix = SimpleNamespace(ui_child=object(), runtime=SimpleNamespace(
            evaluate_text=lambda child, code, label, **options: self.lua.execute(code)))
        action = dict(kind='terrain_operation', operation='REPAIR_ROUTE', hash=228327966)
        player = dict(player_id=0, turn=7)
        self.assertEqual(xp2_lan_unit_work._operation_index(prefix, player, action), 32)
        action['hash'] += 1
        with self.assertRaises(LuaError):
            xp2_lan_unit_work._operation_index(prefix, player, action)


class PrimaryAdjacentCheckpointTest(unittest.TestCase):
    def test_retained_bbg_primary_view_compares_across_the_additive_work_revision(self):
        from civ6_host.contracts import information, network_turn, unit_work
        from civ6_host.runtime import unit_work_state, xp1_session_view
        from civ6_host.runtime.configuration_profiles import XP2_CORE_SHA256
        from civ6_host.runtime.paths import resource_root
        from test_session_capabilities import seal

        root = resource_root()
        proof = json.loads((root / 'evidence/host-current-bbg751-world-a-builder.json').read_text(encoding='utf-8'))
        ref = proof['qualification']['checkpoint_out']
        raw = (root / ref['path']).read_bytes()
        self.assertEqual(sha256(raw).hexdigest(), ref['sha256'])
        checkpoint = json.loads(raw)
        observed, legacy = checkpoint['observation'], checkpoint['decisions']
        old_work, old_state, old_info = (legacy[key] for key in ('unit_work', 'unit_work_state', 'unit_work_info'))
        uid = next(unit['id'] for unit in observed['units'] if unit['moves'] > 0)
        status = next(row for row in old_state['units'] if row['unit_id'] == uid)
        source = next(plot for plot in observed['plots'] if plot['index'] == status['plot_id'])
        destination = next(plot for plot in observed['plots'] if plot['visible']
                           and abs(plot['x'] - source['x']) == 1 and plot['y'] == source['y'])
        # Add a software offer to exercise the public contract, not game legality.
        action = dict(kind=unit_work.ADJACENT_KIND, unit_id=uid, charges=status['charges'],
                      moves_token=status['moves_token'], x=destination['x'], y=destination['y'],
                      plot_id=destination['index'], source_x=source['x'], source_y=source['y'],
                      source_plot_id=source['index'], index=21, hash=4294967254,
                      item_type='IMPROVEMENT_MOUNTAIN_ROAD', selector=12)
        new_work = deepcopy(old_work)
        new_work['offers'].append(dict(action=action, legal=True))
        new_info = deepcopy(old_info)
        new_info.update(schema='civ6-host.unit-work-info.v2', visible_plots_with_work=[
            {key: val for key, val in row.items() if key != 'unit_id'}
            for row in sorted(old_info['targets'], key=lambda row: row['plot_id']) if row['improvement'] >= 0])
        new_info['offers'].append(dict(action=action, legal=True, action_name=None, feature=None,
                                       descriptions=[], failure_reasons=[]))
        current = deepcopy(legacy)
        core = object()
        saved = SimpleNamespace(prefix=object(), _xp2_adjacent_work_core=core, backend=SimpleNamespace(core=core))
        with patch.object(unit_work_info, 'read_catalog', return_value=(new_work, new_info)) as read, \
                patch.object(unit_work_state, 'observe', return_value=old_state):
            xp1_session_view._add_unit_work(saved, observed, current, actions_closed=False)
            self.assertTrue(read.call_args.kwargs['adjacent'])
        seal(current)
        comparable, receipt = network_turn.checkpoint_catalogue(
            current, legacy, observed, core_sha256=XP2_CORE_SHA256)
        self.assertEqual(comparable, legacy)
        self.assertEqual(receipt['added_action_families'], [unit_work.ADJACENT_KIND])
        self.assertEqual(network_turn.select_capability(current, {
            'decision_id': current['decision_id'], 'candidate_id': network_turn.digest(action)}), action)
        self.assertEqual(information.project('unit_work', observed, current)['info'], new_info)
        hidden = deepcopy(observed)
        next(plot for plot in hidden['plots'] if plot['index'] == destination['index'])['visible'] = False
        with self.assertRaisesRegex(ValueError, 'visible source or target'):
            information.project('unit_work', hidden, current)
        changed = deepcopy(current)
        changed['unit_work_info']['visible_plots_with_work'][0]['improvement'] = 21
        seal(changed)
        comparable, receipt = network_turn.checkpoint_catalogue(changed, current, observed, core_sha256=XP2_CORE_SHA256)
        self.assertIsNone(receipt)
        self.assertNotEqual(comparable, current)
