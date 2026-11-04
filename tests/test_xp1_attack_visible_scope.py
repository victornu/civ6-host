"""Installed shared Lua, exact saved-owner scope and retained Base equivalence; no DLL."""
import ast
from contextlib import contextmanager
from copy import deepcopy
import json
from pathlib import Path
import sys,unittest,hashlib
from unittest.mock import patch

HOST=Path(__file__).resolve().parents[1]
from civ6_host.runtime.paths import resource_root
LAB=resource_root()
sys.path.append(str(LAB/'work/lua-test-deps'))
from lupa.lua51 import LuaRuntime
from test_xp1_unit_attack_owner import Fixture
from civ6_host.runtime.configuration_profiles import XP1_CORE_SHA256 as XP1,BASE_CORE_SHA256 as BASE
from civ6_host.runtime import xp1_attack_visible_scope, xp1_unit_attacks
from civ6_host.runtime.native import native_combat_actions, native_saved_city_targets, native_saved_combat
from civ6_host.runtime.provenance import historical_source_file


@contextmanager
def modules():
    # These are the installed extracted modules, without replacing their bodies.
    yield dict(native_combat_actions=native_combat_actions,
        native_saved_city_targets=native_saved_city_targets,native_saved_combat=native_saved_combat,
        xp1_attack_visible_scope=xp1_attack_visible_scope,xp1_unit_attacks=xp1_unit_attacks)


def harness(width=8,height=8,visible=2,extra=''):
    tree=ast.parse((LAB/'tests/test_native_city_targets936.py').read_text())
    value=next(ast.literal_eval(n.value) for n in tree.body if isinstance(n,ast.Assign)
        and any(isinstance(x,ast.Name) and x.id=='HARNESS' for x in n.targets))
    value=value.replace('return 7 end','return 8 end')
    value+=f'''
mapCalls=0;cityCalls=0;visCalls=0
Map.GetGridSize=function()return {width},{height} end
Map.GetPlotCount=function()return {width*height} end
Map.GetPlotByIndex=function(index)
 mapCalls=mapCalls+1
 return {{GetX=function()return index%{width} end,GetY=function()return math.floor(index/{width})end,
          GetIndex=function()return index end}}
end
PlayersVisibility[0].IsVisible=function(_,x,y)visCalls=visCalls+1;return show and y*{width}+x<{visible} end
PlayersVisibility[0].IsRevealed=function(_,i)return show and i<{visible} end
local oldCity=CityManager.GetCityAt
CityManager.GetCityAt=function(x,y)
 cityCalls=cityCalls+1
 if x==1 and y==0 then return oldCity(x,y) end
 assert(y*{width}+x<{visible},'hidden city read')
end
'''+extra
    return value.encode('ascii')


def observe_fixture(f,width=8,height=8,visible=2):
    obs=deepcopy(f.token.observation);obs.update(width=width,height=height)
    prototype=obs['plots'][0]
    obs['plots']=[dict(prototype,index=i,x=i%width,y=i//width) for i in range(visible)]
    f.observation=deepcopy(obs);f.token.observation=deepcopy(obs)
    f.saved._running=True;f.set_active(False)
    return f.token.observation


class VisibleCityTests(unittest.TestCase):
    def fixture(self):
        f=Fixture();self.addCleanup(f.close);return f

    def run_lua(self,source,setup):
        lua=LuaRuntime(encoding=None);lua.execute(setup)
        result=json.loads(lua.execute(source))
        return result,tuple(lua.globals()[key] for key in (b'mapCalls',b'cityCalls',b'visCalls',b'requests',b'hiddenReads'))

    def test_paired_original_lua_preserves_city_values_offers_and_gates(self):
        cases=(('',2),('ranged=false',2),('ranged=false;coastal=true',2),
               ('ranged=false;swap=true',2),('war=false',2),('extraWar=true',2),
               ('owner=0',2),('show=false',0),
               ('Players[1]:GetDistricts():FindID(99).GetDefenseStrength=function()return 30+129/256 end',2))
        with modules() as m:
            for extra,visible in cases:
                with self.subTest(extra=extra):
                    f=self.fixture();obs=observe_fixture(f,visible=visible)
                    original=m['native_saved_city_targets'].source(8,player_id=0,core_sha256=XP1)
                    with m['xp1_attack_visible_scope'].capture(f.saved,obs) as token:
                        scoped=m['native_saved_city_targets'].source(8,player_id=0,core_sha256=XP1,visible_scope=token)
                        legacy,c1=self.run_lua(original,harness(visible=visible,extra=extra))
                        actual,c2=self.run_lua(scoped,harness(visible=visible,extra=extra))
                    self.assertEqual(actual,legacy);self.assertEqual(c1[0],64);self.assertEqual(c2[0],visible)
                    self.assertEqual(c1[1],c2[1]);self.assertEqual(c1[3:],(0,0));self.assertEqual(c2[3:],(0,0))
                    self.assertEqual(f.machine,[]);self.assertEqual(f.token.publication_count,0)
                    f.close()

    def test_full_map_3404_to_complete_visible27_without_dropping_native_queries(self):
        with modules() as m:
            f=self.fixture();obs=observe_fixture(f,92,37,27)
            original=m['native_saved_city_targets'].source(8,player_id=0,core_sha256=XP1)
            with m['xp1_attack_visible_scope'].capture(f.saved,obs) as token:
                scoped=m['native_saved_city_targets'].source(8,player_id=0,core_sha256=XP1,visible_scope=token)
                legacy,c1=self.run_lua(original,harness(92,37,27))
                actual,c2=self.run_lua(scoped,harness(92,37,27))
            self.assertEqual(actual,legacy)
            self.assertEqual((c1[0],c2[0]),(3404,27));self.assertEqual((c1[1],c2[1]),(27,27))
            self.assertEqual((c1[2],c2[2]),(3404,27))

    def test_live_visibility_coordinate_and_perspective_changes_refuse(self):
        with modules() as m:
            f=self.fixture();obs=observe_fixture(f)
            with m['xp1_attack_visible_scope'].capture(f.saved,obs) as token:
                source=m['native_saved_city_targets'].source(8,player_id=0,core_sha256=XP1,visible_scope=token)
                for extra in ('show=false','observer=1',
                    'Map.GetPlotByIndex=function(i)return {GetX=function()return 7 end,GetY=function()return 0 end}end',
                    "local old=CityManager.GetCityAt;CityManager.GetCityAt=function(x,y)local c=old(x,y);Game.GetCurrentGameTurn=function()return 9 end;return c end"):
                    with self.subTest(extra=extra):
                        lua=LuaRuntime(encoding=None);lua.execute(harness(extra=extra))
                        with self.assertRaises(Exception):lua.execute(source)
                        self.assertEqual(lua.globals()[b'requests'],0)

    def test_owner_scope_rejects_partial_foreign_stale_and_expired_inputs(self):
        with modules() as m:
            scope=m['xp1_attack_visible_scope'];f=self.fixture();obs=observe_fixture(f)
            partial=deepcopy(obs);partial['plots'].pop()
            with self.assertRaises(ValueError):
                with scope.capture(f.saved,partial):pass
            with self.assertRaises(TypeError):scope._VisibleScope()
            with scope.capture(f.saved,obs) as token:
                for change in ('sequence','publication','observation','prefix','base','list'):
                    with self.subTest(change=change):
                        seq,pub,snapshot=f.token.sequence,f.token.publication_count,deepcopy(f.token.observation)
                        prefix=f.token.prefix;engine=XP1;selected=token
                        if change=='sequence':f.token.sequence+=1
                        elif change=='publication':f.token.publication_count+=1
                        elif change=='observation':f.token.observation['plots'].pop()
                        elif change=='prefix':prefix=object()
                        elif change=='base':engine=BASE
                        else:selected=list(token.plots)
                        with self.assertRaises((ValueError,TypeError)):
                            scope.check(selected,prefix,8,0,engine)
                        f.token.sequence=seq;f.token.publication_count=pub;f.token.observation=snapshot
            with self.assertRaises(ValueError):scope.check(token,f.token.prefix,8,0,XP1)
            self.assertEqual(f.machine,[]);self.assertEqual(f.token.transport.pending,[])

    def test_composed_installed_owner_read_uses_scope_then_expires_it(self):
        with modules() as m:
            f=self.fixture();obs=observe_fixture(f);original_evaluate=f.token.prefix.runtime.evaluate_text
            seen=[]
            def evaluate(child,source,name,**kw):
                if name==b'@explicit_visible_city_targets':
                    self.assertIn(b'for _,scopedPlot in ipairs',source)
                    self.assertIn(b'{{0,0,0},{1,1,0}}',source);seen.append(name)
                return original_evaluate(child,source,name,**kw)
            with patch.object(f.token.prefix.runtime,'evaluate_text',evaluate):
                result=m['xp1_unit_attacks'].read(f.saved,obs)
            self.assertEqual(len(seen),1);self.assertTrue(result['actions'])
            self.assertIsNone(f.token._xp1_attack_visible_scope)
            self.assertEqual(f.token.publication_count,0);self.assertEqual(f.machine,[])

    def test_default_base_lua_and_command_revalidation_bodies_are_unchanged(self):
        targets={'native_combat_actions':('candidate_source','request_source'),
                 'native_saved_combat':('apply','unit_state_source'),
                 'native_saved_city_targets':('request_source',)}
        installed={'native_combat_actions':native_combat_actions,
                   'native_saved_combat':native_saved_combat,
                   'native_saved_city_targets':native_saved_city_targets}
        for name,symbols in targets.items():
            old=ast.parse(base_source(name))
            actual=ast.parse(Path(installed[name].__file__).read_text())
            functions=lambda tree:{n.name:n for n in tree.body if isinstance(n,ast.FunctionDef)}
            for symbol in symbols:
                self.assertEqual(ast.dump(without_engine_selection(functions(old)[symbol])),
                    ast.dump(without_engine_selection(functions(actual)[symbol])),name+':'+symbol)
        for engine in (BASE,XP1):
            source=native_saved_city_targets.source(8,player_id=0,core_sha256=engine)
            self.assertIn(b'for index=0,count-1 do',source)
            self.assertNotIn(b'scopedPlot',source)
        self.assertEqual(native_saved_city_targets.source(8,core_sha256=BASE).replace(
                         b'if u:IsReadyToSelect() then',b'do',1),
                         native_saved_city_targets.source(8,core_sha256=XP1))
        self.assertEqual(lua_constant_original(),native_saved_city_targets._LUA)

    def test_hidden_target_gap_is_explicit_and_existing_gaps_are_retained(self):
        from civ6_host.contracts.capability_unit_attacks import UNQUALIFIED_UNIT_ATTACKS
        required={'war_confirmation','air_attacks','nonadjacent_enemy_flag_melee',
            'world_plot_unit_targeting','coastal_raid_and_swap','other_unit_attack_operations',
            'operation_lifecycle_only_readback','native_legal_targets_without_visible_witness'}
        self.assertLessEqual(required,set(UNQUALIFIED_UNIT_ATTACKS))


def lua_constant_original():
    tree=ast.parse(base_source('native_saved_city_targets'))
    return next(ast.literal_eval(n.value) for n in tree.body if isinstance(n,ast.Assign)
        and any(isinstance(x,ast.Name) and x.id=='_LUA' for x in n.targets))


BASE_SOURCE_SHA={'native_combat_actions': 'b84faa3ad8fcd00f8ef8d5fbd4039c09ca9680befccb6f745e8e583cb418d778', 'native_saved_combat': '6b6ad59399d17c2b75e885de8c0b5af15e544192d67a84f0bc36cd53e85c4658', 'native_saved_city_targets': 'ad0c45176369268dfe89e7274b7274a6c8a1acdc405f6cd1912cbf7d391c078e'}

def base_source(name):
    path=Path(historical_source_file('civ6rl/'+name+'.py'))
    raw=path.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=BASE_SOURCE_SHA[name]:
        raise ValueError('Retained Base attack source changed: '+name)
    return raw.decode('utf-8')


def without_engine_selection(node):
    # Remove only the already-qualified engine selector/provenance wrappers.
    # Any extra gameplay/native-call/body change remains visible to comparison.
    class Selected(ast.NodeTransformer):
        def visit_FunctionDef(self,n):
            pairs=[(arg,value) for arg,value in zip(n.args.kwonlyargs,n.args.kw_defaults)
                   if arg.arg!='core_sha256']
            n.args.kwonlyargs=[arg for arg,_ in pairs];n.args.kw_defaults=[value for _,value in pairs]
            return self.generic_visit(n)
        def visit_Call(self,n):
            self.generic_visit(n)
            if isinstance(n.func,ast.Name) and n.func.id=='selected_readiness_source':
                if (len(n.args)!=3 or n.keywords or ast.unparse(n.args[1])!='core_sha256'
                        or not isinstance(n.args[2],ast.Constant)
                        or n.args[2].value not in ('unit_candidates','unit_request','city_source')):
                    raise ValueError('Unexpected readiness selector wrapper')
                return n.args[0]
            if isinstance(n.func,ast.Name) and n.func.id in ('selected_proof','selected_queued_proof'):
                if len(n.args)!=2 or n.keywords:raise ValueError('Unexpected proof wrapper')
                return n.args[0]
            n.keywords=[k for k in n.keywords if k.arg!='core_sha256']
            return n
        def visit_ImportFrom(self,n):
            if n.module=='civ6_host.runtime.xp1_unit_attack_profile':
                if {a.name for a in n.names} not in (
                        {'selected_proof','selected_queued_proof'},{'selected_readiness_source'}):
                    raise ValueError('Unexpected engine helper import')
                return None
            if n.module and n.module.startswith('civ6_host.runtime.native'):
                n.module=n.module.replace('civ6_host.runtime.native','civ6rl',1)
            elif n.level==1 and n.module and n.module.startswith('native_'):
                n.module='civ6rl.'+n.module;n.level=0
            return n
    return ast.fix_missing_locations(Selected().visit(deepcopy(node)))


if __name__=='__main__':unittest.main()
