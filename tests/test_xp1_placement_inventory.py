"""Native-binding source guards and actual Lua collector on bounded fixtures.

The Lua globals below replace only official getter data. They are not a game
simulation and do not establish native execution of the new collector.
"""
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import hashlib
import sys
import unittest

HOST=Path(__file__).resolve().parents[1]
sys.path.append(str(HOST.parent/'civ6-rl-lab'/'work/lua-test-deps'))
from lupa.lua51 import LuaRuntime

from civ6_host.runtime import placement_inventory as inventory
from civ6_host.runtime import placement_inventory_profile as profile
from civ6_host.runtime.configuration_profiles import XP1_CORE_SHA256 as XP1, BASE_CORE_SHA256
from civ6_host.runtime.resource_resolution import resolve_path
from civ6_host.runtime.paths import resource_root


SETUP=r'''
state={pid=0,observer=0,turn=42,plotReads={},detailReads={},completionCalls=0,
       hidden={},unrevealed={},afterComplete=false,cityCounts=2}
local function forbidden() error('action/turn readiness/tracking API must not be read') end
local function district(index,required,internal)
 return {Index=index,Hash=index==1 and -1 or 1000+index,DistrictType='DISTRICT_TEST_'..index,
         RequiresPlacement=required,InternalOnly=internal}
end
local function building(index,required,wonder)
 return {Index=index,Hash=2000+index,BuildingType='BUILDING_TEST_'..index,
         RequiresPlacement=required,IsWonder=wonder}
end
GameInfo={Districts={[0]=district(0,false,false),[1]=district(1,true,false),
  [3]=district(3,true,false),[5]=district(5,true,true)},
 Buildings={[2]=building(2,true,true),[4]=building(4,false,true),
  [9]=building(9,true,false),[10]=building(10,false,false)}}
plots={
 [0]={owner=0,city=5,district=0},[1]={owner=0,city=5,district=1,id=7},
 [2]={owner=0,city=5,wonder=2},[3]={owner=0,city=9,district=3,id=8,complete=true},
 [4]={owner=0,city=9,wonder=4,complete=true},[5]={owner=0,city=5,district=5},
 [6]={owner=0,city=5},[7]={owner=1,city=17,district=1},[8]={owner=0},
 [9]={owner=0,city=5,wonder=9},[10]={owner=0,city=5,wonder=10}}
local function completeHook()
 state.completionCalls=state.completionCalls+1
 if state.afterComplete then state.afterComplete() end
end
cities={}
for _,id in ipairs({5,9,17}) do
 local cid=id
 local c={owner=id==17 and 1 or 0,id=cid}
 c.GetOwner=function() return c.owner end
 c.GetID=function() assert(c.owner==0,'foreign city ID read');return c.id end
 c.GetDistricts=function() return {IsComplete=function(_,kind,plot)
  local p=plots[plot];assert(p and p.city==cid and p.district==kind,'completion wrong city/type/plot')
  completeHook();return p.complete==true
 end} end
 c.GetBuildings=function() return {HasBuilding=function(_,kind)
  assert(kind==2 or kind==4 or kind==9,'HasBuilding must receive existing native type index')
  local result=false
  for _,p in pairs(plots) do if p.city==cid and p.wonder==kind then result=p.complete==true end end
  completeHook();return result
 end} end
 c.GetBuildQueue=forbidden
 cities[cid]=c
end
local player={GetCities=function() return {Members=function()
 local i=0;return function() i=i+1;if i<=state.cityCounts then return i,cities[i==1 and 5 or 9] end end
end} end,IsTurnActive=forbidden,IsTurnActiveComplete=forbidden,IsAlive=forbidden}
Players={[0]=player}
Game={GetLocalPlayer=function() return state.pid end,GetLocalObserver=function() return state.observer end,
 GetCurrentGameTurn=function() return state.turn end,IsAllowStrategicCommands=forbidden}
PlayersVisibility={[0]={IsVisible=function(_,x,y) return not state.hidden[y*4+x] end,
 IsRevealed=function(_,plot) return not state.unrevealed[plot] end}}
Map={GetGridSize=function() return 4,4 end,GetPlotCount=function() return 16 end,
 GetPlotByIndex=function(index)
  assert(not state.hidden[index] and not state.unrevealed[index],'hidden live plot lookup')
  state.plotReads[index]=(state.plotReads[index] or 0)+1
  local p=plots[index];assert(p,'unobserved plot lookup')
  local function detail()
   assert(p.owner==0 and p.city and cities[p.city].owner==0,'foreign/unassigned placement detail read')
   state.detailReads[index]=(state.detailReads[index] or 0)+1
  end
  return {index=index,GetIndex=function() return index end,GetX=function() return index%4 end,
   GetY=function() return math.floor(index/4) end,GetOwner=function() return p.owner end,
   GetDistrictType=function() detail();return p.district or -1 end,
   GetWonderType=function() detail();return p.wonder or -1 end,
   GetDistrictID=function() detail();assert(p.id,'filtered/absent district ID queried');return p.id end}
 end}
Cities={GetPlotPurchaseCity=function(plot) return cities[plots[plot.index].city] end}
CityManager={CanStartOperation=forbidden,RequestOperation=forbidden}
'''


def observation():
    return dict(player_id=0,turn=42,width=4,height=4,
        plots=[dict(index=i,x=i%4,y=i//4,owner=1 if i==7 else 0,visible=True,revealed=True)
               for i in range(11)],cities=[dict(id=5,owner=0),dict(id=9,owner=0)])


class Fixture:
    def __init__(self):
        self.lua=LuaRuntime(max_memory=4*1024*1024)
        self.lua.execute(SETUP)
        self.observation=observation()
        self.child=object()
        self.calls=[]

    def evaluate_text(self,child,source,name,*,capacity):
        assert child is self.child and name==b'@native_placement_inventory'
        self.calls.append(dict(name=name,capacity=capacity))
        raw=self.lua.execute(source.decode('ascii')).encode('ascii')
        assert len(raw)<capacity
        return raw

    def read(self):
        # The prefix contains no owner, continuation or explicit_placements.
        prefix=SimpleNamespace(runtime=self,ui_child=self.child)
        return inventory.read(prefix,0,42,self.observation,core_sha256=XP1)


class InventoryTests(unittest.TestCase):
    def test_untracked_incomplete_complete_and_metadata_filters(self):
        f=Fixture();before=deepcopy(f.observation);result=f.read()
        self.assertEqual(f.observation,before)
        self.assertEqual([(r['city_id'],r['category'],r['plot_id'],r['complete']) for r in result['rows']],
            [(5,'building',2,False),(5,'building',9,False),(5,'district',1,False),
             (9,'building',4,True),(9,'district',3,True)])
        self.assertEqual(result['rows'][2]['hash'],4294967295)
        self.assertEqual(result['rows'][2]['district_id'],7)
        self.assertIsNone(result['rows'][0]['district_id'])
        self.assertNotIn('placement_turn',str(result))
        self.assertEqual(f.lua.eval('state.completionCalls'),5)
        self.assertIsNone(f.lua.eval('state.detailReads[7]'))
        self.assertIsNone(f.lua.eval('state.detailReads[8]'))
        self.assertEqual(f.calls,[dict(name=b'@native_placement_inventory',capacity=5760)])

    def test_hidden_or_unrevealed_stops_before_lookup(self):
        for condition in ('hidden','unrevealed'):
            with self.subTest(condition=condition):
                f=Fixture();f.lua.execute('state.'+condition+'[1]=true')
                with self.assertRaises(Exception):f.read()
                self.assertIsNone(f.lua.eval('state.plotReads[1]'))
                self.assertEqual(f.lua.eval('state.completionCalls'),0)

    def test_foreign_city_and_stale_owner_stop_before_details(self):
        for mutation in ('plots[1].owner=1','plots[1].city=17','cities[5].owner=1',
                         'cities[5].id=12','state.cityCounts=1'):
            with self.subTest(mutation=mutation):
                f=Fixture();f.lua.execute(mutation)
                with self.assertRaises(Exception):f.read()
                self.assertEqual(f.lua.eval('state.completionCalls'),0)

    def test_stale_perspective_turn_and_mutation_during_completion(self):
        for mutation in ('state.pid=1','state.observer=1','state.turn=43',
                         'state.afterComplete=function() plots[1].district=3 end',
                         'state.afterComplete=function() plots[1].id=19 end',
                         'state.afterComplete=function() plots[1].owner=1 end',
                         'state.afterComplete=function() plots[1].city=9 end'):
            with self.subTest(mutation=mutation):
                f=Fixture();f.lua.execute(mutation)
                with self.assertRaises(Exception):f.read()

    def test_native_sentinel_and_metadata_identity(self):
        f=Fixture();f.lua.execute('plots[1].district=nil;plots[2].wonder=nil')
        self.assertEqual(len(f.read()['rows']),3)
        for mutation in ('plots[1].district=-2','plots[2].wonder=-2','plots[1].district=999',
                         'plots[1].id=-1','GameInfo.Districts[1].Index=7',
                         "GameInfo.Districts[1].DistrictType='BUILDING_WRONG'",
                         'GameInfo.Buildings[2].IsWonder=1',
                         'cities[5].GetBuildings=function() return {HasBuilding=function() return nil end} end'):
            with self.subTest(mutation=mutation):
                f=Fixture();f.lua.execute(mutation)
                with self.assertRaises(Exception):f.read()

    def test_empty_native_inventory_and_empty_own_cities(self):
        f=Fixture()
        f.lua.execute('for _,p in pairs(plots) do p.district=nil;p.wonder=nil end')
        self.assertEqual(f.read()['rows'],[])
        f.observation['cities']=[];f.lua.execute('state.cityCounts=0')
        for row in f.observation['plots']:row['owner']=-1
        f.lua.execute('for _,p in pairs(plots) do p.owner=-1 end')
        self.assertEqual(f.read()['rows'],[])

    def test_parser_refuses_malformed_duplicate_foreign_and_hidden_rows(self):
        f=Fixture();source=inventory.readback_source(0,42,f.observation)
        raw=f.lua.execute(source.decode()).encode()
        parsed=inventory.parse_readback(raw,0,42,f.observation)
        self.assertEqual(len(parsed['rows']),5)
        lines=raw.split(b'\n')
        variants=[raw+b'\n',raw.replace(b'|0|42|',b'|1|42|',1),
            raw.replace(b'5|building|2|',b'05|building|2|',1),
            raw.replace(b'|0|-',b'|true|-',1),
            b'\n'.join([lines[0],lines[2],lines[1],*lines[3:]]),
            b'\n'.join([lines[0],lines[1],lines[1],*lines[3:]]),
            raw.replace(b'5|building|2|',b'17|building|2|',1),
            raw.replace(b'|2|2|0|0|-',b'|7|3|1|0|-',1)]
        for value in variants:
            with self.subTest(value=value[:100]),self.assertRaises(ValueError):
                inventory.parse_readback(value,0,42,f.observation)

    def test_invalid_inputs_and_engine_are_rejected_before_evaluation(self):
        for mutation in (lambda o:o.update(turn=43),lambda o:o['plots'][0].update(visible=False),
                         lambda o:o['plots'][0].update(index=1),lambda o:o['cities'].append(o['cities'][0]),
                         lambda o:o['cities'][0].update(owner=1),lambda o:o.update(width=0)):
            f=Fixture();mutation(f.observation)
            with self.assertRaises(ValueError):f.read()
            self.assertEqual(f.calls,[])
        with self.assertRaises(ValueError):inventory.readback_source(0,42,observation(),core_sha256=BASE_CORE_SHA256)


class SourceTests(unittest.TestCase):
    def test_selected_source_dependencies_and_live_instruction_guards(self):
        sys.path.insert(0,str(resource_root()/'tools'))
        from extract_phase31_next_export import pefile
        p=profile.verify_source()
        self.assertEqual(len(p['bindings']),24)
        dependencies=profile.source_dependencies()
        for path,sha in dependencies.items():
            with Path(path).open('rb') as stream:
                self.assertEqual(hashlib.file_digest(stream,'sha256').hexdigest(),sha,path)
        image=pefile.PE(str(resolve_path(resource_root()/p['image']['path'])),fast_load=True)
        self.addCleanup(image.close)
        base=int(p['image']['base'],16)
        read=lambda address,count:image.get_data(address-base,count)
        self.assertGreater(profile.verify_live(base,read),0)
        def damaged(address,count):return bytes(count)
        with self.assertRaises(ValueError):profile.verify_live(base,damaged)
        with self.assertRaises(ValueError):profile.verify_source(BASE_CORE_SHA256)


if __name__=='__main__':unittest.main()
