"""Real saved owner and command transport; only native memory/calls are fixtures."""
import ast
from copy import deepcopy
from pathlib import Path
import struct
import unittest
from test_xp1_unit_orders_owner import Fixture as OwnerFixture
from test_xp1_unit_orders import LuaRuntime
from test_xp1_turn_a0 import scalar
from civ6_host.runtime import xp1_production_placement as adapter
from civ6_host.runtime.configuration_profiles import XP1_CORE_SHA256 as XP1
from civ6_host.runtime.native import native_saved_placement as placed
from civ6_host.runtime.native import native_city_production_observation as production


# Extend the retained placement fixture only at its native API boundary. The
# production catalogue, requests, readbacks and parsers below are real adapters.
SETUP = r'''
turn=8
local current,previous,pending=0,0,nil
local progresses={[101]=0,[201]=0}
rowsBuilding[#rowsBuilding+1]={BuildingType='BUILDING_TEST_ORDINARY',Index=4,Hash=104,
 RequiresPlacement=false,IsWonder=false}
GameInfo.Buildings=info(rowsBuilding,'BuildingType')
for _,rows in ipairs({rowsBuilding,rowsDistrict}) do
 for _,r in ipairs(rows) do
  GameInfo[r.BuildingType and 'Buildings' or 'Districts'][r.Hash]=r
 end
end
rowsDistrict[1].OnePerCity=true
queue.GetCurrentProductionTypeHash=function() return current end
queue.GetPreviousProductionTypeHash=function() return previous end
queue.GetProductionYield=function() return 4 end
queue.HasProductionProgress=function() return (progresses[current] or 0)>0 end
queue.GetTurnsLeft=function() return 12 end
queue.GetBuildingCost=function() return 80 end
queue.GetDistrictCost=function() return 100 end
queue.GetBuildingProgress=function(_,index) return progresses[GameInfo.Buildings[index].Hash] or 0 end
queue.GetDistrictProgress=function(_,index) return progresses[GameInfo.Districts[index].Hash] or 0 end
cityBuildings.HasBuilding=function(_,id) return hasBuilding[id] or false end
city.GetDistricts=function() return {IsComplete=function() return false end} end
PlayersVisibility[0].IsVisible=function(_,x,y) return revealed[y*8+x] or false end
Map.GetGridSize=function() return 8,8 end
Map.GetPlotCount=function() return 64 end
Map.GetPlotByIndex=function(id)
 assert(revealed[id],'hidden plot getter');plotReads[id]=(plotReads[id] or 0)+1
 return {GetIndex=function() return id end,GetX=function() return id%8 end,
  GetY=function() return math.floor(id/8) end,GetOwner=function() return owner end,
  GetDistrictType=function() return id==3 and 0 or -1 end,
  GetDistrictID=function() return id==3 and 7 or -1 end,
  GetWonderType=function() return (id==2 or id==5) and 1 or -1 end}
end
Cities={GetPlotPurchaseCity=function() return city end}
CityManager.CanStartOperation=function(c,op,args,details)
 assert(c==city and op==7 and args[12]==90 and args[13]==0)
 local placing=args[17]~=nil
 assert(details==placing and countKeys(args)==(placing and 5 or 3))
 if placing then assert(args[17]>=0 and args[17]<8 and args[18]>=0 and args[18]<8) end
 return canStart
end
CityManager.RequestOperation=function(c,op,args)
 assert(c==city and op==7 and args[12]==90 and args[13]==0)
 submitCount=submitCount+1;pending=args;request_python()
end
function drain_placement_fixture()
 assert(pending);local a=pending;pending=nil
 previous=current;current=a[14] or a[16];queueSize=math.max(queueSize,1)
 if a[17]~=nil then placed[current]=true end
end
function seed_retained_progress(hash,value) progresses[hash]=value end
function fixture_requests() return submitCount end
_G.Game=Game;_G.GameInfo=GameInfo;_G.Players=Players;_G.PlayersVisibility=PlayersVisibility
_G.Map=Map;_G.CityManager=CityManager;_G.CityOperationTypes=CityOperationTypes
_G.CityOperationResults=CityOperationResults
'''


class Fixture(OwnerFixture):
    def __init__(self):
        super().__init__()
        self.lua=LuaRuntime(max_memory=4*1024*1024)
        self.lua.globals().request_python=self.placement_request
        prefix=placed.placement.guard_case().split(b'local function collect()\n',1)[0]
        self.lua.execute(prefix.decode()+SETUP)
        self.token.observation['cities']=[dict(id=5)]
        self.observation=deepcopy(self.token.observation)
        self.token.emit=self.emit;self.token.explicit_placements={}
        self.token._xp1_placement_catalogue=None

    def evaluate(self,child,source,name,**kwargs):
        if name.startswith((b'@explicit_placement',b'@explicit_placed_item',b'@explicit_production')):
            if child is not self.token.ui_child:raise AssertionError('Foreign placement UI child')
            return self.lua.execute(source.decode()).encode()
        return super().evaluate(child,source,name,**kwargs)

    def placement_request(self):
        self.token.transport.pending.append(self.payload)
        self.emit('native_command_archive_queued',archive_hex=self.payload.hex(),
                  bytes=len(self.payload),delivery_pending=True)

    def virtual(self,core,pointer,slot,rva,result,*args):
        if rva==self.token.transport.transport_abi.drain_rva:
            if core is not self.backend.core:raise AssertionError('Foreign placement Core')
            def drain(ctx):
                self.machine.append(('drain',))
                self.memory.put(self.sentinel,struct.pack('<QQ',self.sentinel,self.sentinel))
                self.lua.globals().drain_placement_fixture()
                # The new 6D family is exercised separately on the same owner
                # class by its source-profile tests, not mocked as a no-op here.
                from civ6_host.runtime.native import native_event_92492f56 as event
                descriptor=self.make_blob(struct.pack('<HHI',0,2,5),1024)
                fields={event.SELECTOR_KEY:scalar(3,0),event.DESCRIPTOR_KEY:descriptor,
                        event.D6_KEY:scalar(2,101),event.A1FBC_KEY:scalar(2,0)}
                self.owner.dispatch(event.EVENT_KIND,fields,0)
            return drain
        return super().virtual(core,pointer,slot,rva,result,*args)

    def offered(self):
        self.saved._running=True;self.set_active(False)
        self.token.explicit_production_snapshot=production.parse_production_snapshot(self.evaluate(
            self.token.ui_child,production.production_snapshot_source(0,core_sha256=XP1),
            b'@explicit_production_before'),0)
        return adapter.read(self.saved,self.token.observation)

    def execute(self,action):
        self.saved._running=False
        return self.saved.execute(action)


class PlacementOwnerTests(unittest.TestCase):
    def fixture(self):
        f=Fixture();self.addCleanup(f.close);return f

    def test_both_placement_families_replace_and_resume_with_retained_progress(self):
        for category in ('district','building'):
            with self.subTest(category=category):
                f=self.fixture()
                offered=f.offered()
                action=next(a for a in offered['actions'] if a['kind']=='production_placement' and a['category']==category)
                first=f.execute(action);receipt=first['effect']['receipt']
                self.assertEqual(receipt['action'],action)
                self.assertTrue(receipt['effect']['new_placement_verified'])
                self.assertEqual(list(f.token.explicit_placements),[(0,5,action['plot_id'])])
                f.offered()
                ordinary=dict(kind='production',city_id=5,category='building',index=4,hash=104,item_type='BUILDING_TEST_ORDINARY')
                f.execute(ordinary)
                # An explicit fixture input, not a native turn or construction
                # claim: ensure resumption does not discard nonzero progress.
                f.lua.globals().seed_retained_progress(action['hash'],17)
                offered=f.offered()
                resume=next(a for a in offered['actions'] if a['kind']=='production_resume' and a['hash']==action['hash'])
                end=f.execute(resume);effect=end['effect'];receipt=effect['receipt']
                self.assertEqual(receipt['progress_before'],17)
                self.assertEqual(receipt['progress_after'],17)
                self.assertEqual(receipt['placements_before'],receipt['placements_after'])
                self.assertEqual(effect['observation'],end['observation_after'])
                self.assertEqual(f.token.sequence,3);self.assertEqual(f.token.publication_count,3)
                self.assertEqual(f.deferred.consumed_count,3)
                self.assertIsNone(f.token._xp1_placement_catalogue)
                self.assertEqual(f.token.transport.pending,[])

    def test_stale_or_foreign_placement_refuses_before_request(self):
        for change in ('sequence','owner','production','tracking','action'):
            with self.subTest(change=change):
                f=self.fixture();offers=f.offered();action=deepcopy(offers['actions'][0]);f.set_active(True)
                if change=='sequence':f.token.sequence+=1
                elif change=='owner':f.saved._backend=object()
                elif change=='production':f.token.explicit_production_snapshot={}
                elif change=='tracking':f.token.explicit_placements={(0,5,2):{}}
                else:action['city_id']=True
                with self.assertRaises((ValueError,RuntimeError)):adapter.apply(f.saved,action,f.token.observation)
                self.assertEqual(f.machine,[]);self.assertEqual(f.lua.globals().fixture_requests(),0)

    def test_shared_lua_uses_selected_engine_without_changing_base_chunks(self):
        from civ6_host.runtime.native import native_district_completion as district,native_wonder_completion as wonder
        from civ6_host.contracts import placement as portable
        base=placed.placement.catalog_source(0,5,8,visible_only=True,replace_current=True)
        self.assertEqual(base,placed.placement.catalog_source(0,5,8,visible_only=True,replace_current=True,core_sha256=XP1))
        f=self.fixture();f.offered()
        for category in ('district','building'):
            catalogue=placed.catalog(f.token.prefix,5,8,core_sha256=XP1)
            choice=next(placed.placement.choose(catalogue,r['kind'],r['index'],r['plot_id'])
                        for r in catalogue['candidates'] if r['kind']==category and r['mode']=='place')
            for fn in (placed.placement.request_source,placed.placement.effect_source):
                self.assertEqual(fn(choice),fn(choice,core_sha256=XP1))
            reader=district if category=='district' else wonder
            self.assertEqual(reader.readback_source(choice,8),reader.readback_source(choice,8,core_sha256=XP1))
        for name in ('_player_id','validate_action','validate_offers','validate_progress'):
            self.assertIs(getattr(placed,name),getattr(portable,name))
        # Explicitly reject an accidental Base fall-through through a shared helper.
        from extraction_xp1_placements import MODULES
        import importlib
        for old,targets in MODULES.items():
            module=importlib.import_module(old.replace('civ6rl','civ6_host.runtime.native'))
            for node in ast.parse(Path(module.__file__).read_text()).body:
                if not isinstance(node,ast.FunctionDef) or node.name not in targets:continue
                for call in ast.walk(node):
                    if not isinstance(call,ast.Call):continue
                    key=ast.unparse(call.func)
                    if key in (*targets,'base_preamble','_selection_source','placement.catalog_source',
                               'placement._selection_source','reader.readback_source'):
                        self.assertEqual([(k.arg,ast.unparse(k.value)) for k in call.keywords if k.arg=='core_sha256'],
                                         [('core_sha256','core_sha256')])


if __name__=='__main__':unittest.main()
