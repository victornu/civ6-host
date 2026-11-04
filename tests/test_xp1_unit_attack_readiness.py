"""Official readiness selection: installed shared Lua and composed owner, no DLL."""
import hashlib
import sys,unittest
from unittest.mock import patch

from civ6_host.runtime.paths import resource_root
sys.path.append(str(resource_root()/'work/lua-test-deps'))
from lupa.lua51 import LuaRuntime
from civ6_host.runtime import xp1_unit_attack_profile as profile
from civ6_host.runtime.native import native_combat_actions as units,native_saved_city_targets as cities
from civ6_host.runtime.configuration_profiles import XP1_CORE_SHA256 as XP1,BASE_CORE_SHA256 as BASE
from test_xp1_unit_attack_sources import city_harness
from test_xp1_unit_attack_owner import Fixture


CANDIDATE=dict(unit_id=17,operation='RANGE_ATTACK',target_owner=1,target_id=9,x=1,y=0)


def unit_setup(*,ready=True,melee=False,legal=True,owner_fixture=False):
    source=units.build_guard_case(core_sha256=XP1).split(b'local ok,result=pcall(function()',1)[0]
    before=b'IsReadyToSelect=function() return true end'
    assert source.count(before)==1
    source=source.replace(before,b'IsReadyToSelect=function() return '+(b'true' if ready else b'false')+b' end')
    source+=b'\nfixtureActor=actor;fixtureEnemy=enemy;fixturePlayer=player;fixtureForbidden=function()return forbidden end\n'
    source+=b"\nrequests=0;UnitManager.RequestOperation=function(u,op,p) assert(u==actor and (op=='RANGE_ATTACK' or op=='MOVE_TO') and p.x==1 and p.y==0);requests=requests+1 end\n"
    if melee:
        source+=b"local nativeCanStart=UnitManager.CanStartOperation;UnitManager.CanStartOperation=function(u,op,n,p) return op~='RANGE_ATTACK' and nativeCanStart(u,op,n,p) end\n"
    if not legal:source+=b'UnitManager.CanStartOperation=function()return false end\n'
    if owner_fixture:
        source=source.replace(b'GetID=function() return 9 end',b'GetID=function() return 27 end')
        source=source.replace(b'GetCurrentGameTurn=function() return 7 end',b'GetCurrentGameTurn=function() return 8 end')
        source=source.replace(b'GetGridSize=function() return 3,2 end',b'GetGridSize=function() return 8,8 end')
        source=source.replace(b'GetPlotCount=function() return 6 end',b'GetPlotCount=function() return 64 end')
        source=source.replace(b'return y*3+x end',b'return y*8+x end')
    return source


def city_setup(*,ready=True,extra=b''):
    source=city_harness()
    before=b'IsReadyToSelect=function()return true end'
    assert source.count(before)==1
    return source.replace(before,b'IsReadyToSelect=function()return '+(b'true' if ready else b'false')+b' end')+b'\n'+extra


class AttackReadinessTests(unittest.TestCase):
    def test_exact_source_closure_and_fail_closed_transform(self):
        proof=profile.verify_readiness_source()
        self.assertEqual(set(proof['corrections']),{'unit_candidates','unit_request','city_source'})
        deps=profile.source_dependencies()
        for ref in [dict(path=profile.READINESS_SOURCE[0],sha256=profile.READINESS_SOURCE[1]),
                    *proof['official_sources'].values(),*proof['shared_original_sources']]:
            path=(resource_root()/ref['path']).resolve()
            self.assertEqual(deps[str(path)],ref['sha256'])
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),ref['sha256'])
        for kind,(old,new) in profile.READINESS_REPLACEMENTS.items():
            with patch.object(profile,'verify_readiness_source',side_effect=AssertionError('Base consulted XP1')):
                self.assertEqual(profile.selected_readiness_source(old.encode(),BASE,kind),old.encode())
            self.assertEqual(profile.selected_readiness_source(old.encode(),XP1,kind),new.encode())
            for source in (b'changed',old.encode()+old.encode()):
                with self.assertRaises(ValueError):profile.selected_readiness_source(source,XP1,kind)
        with self.assertRaises(ValueError):profile.selected_readiness_source(b'',XP1,'other')
        with self.assertRaises(ValueError):profile.selected_readiness_source(b'', 'foreign','unit_request')

    def test_unit_unready_native_legal_catalogue_and_request_all_routes(self):
        for melee,modifier in ((False,True),(False,False),(True,True)):
            with self.subTest(melee=melee,modifier=modifier):
                candidate=dict(CANDIDATE,operation='MOVE_TO' if melee else 'RANGE_ATTACK')
                outputs=[]
                for engine,ready in ((BASE,True),(XP1,True),(XP1,False)):
                    lua=LuaRuntime(encoding=None);lua.execute(unit_setup(ready=ready,melee=melee))
                    value=units.parse_candidates(lua.execute(units.candidate_source(0,7,
                        ranged_modifier=modifier,core_sha256=engine)),0,7,core_sha256=engine)
                    self.assertEqual(value['candidates'],[candidate]);outputs.append(value)
                    result=lua.execute(units.request_source(0,7,candidate,width=3,height=2,
                        ranged_modifier=modifier,core_sha256=engine))
                    self.assertEqual(result,b'submitted');self.assertEqual(lua.globals().requests,1)
                self.assertEqual(outputs[0],outputs[1]);self.assertEqual(outputs[1],outputs[2])
        lua=LuaRuntime(encoding=None);lua.execute(unit_setup(ready=False))
        self.assertEqual(units.parse_candidates(lua.execute(units.candidate_source(0,7)),0,7)['candidates'],[])
        with self.assertRaises(Exception):lua.execute(units.request_source(0,7,CANDIDATE,width=3,height=2))
        self.assertEqual(lua.globals().requests,0)

    def test_unready_unit_still_requires_native_legality_visibility_and_existence(self):
        changes={
            'native_false':b'UnitManager.CanStartOperation=function()return false end',
            'unit_hidden':b'PlayersVisibility[0].IsUnitVisible=function()return false end',
            'plot_hidden':b'PlayersVisibility[0].IsVisible=function()return false end',
            'plot_unrevealed':b'PlayersVisibility[0].IsRevealed=function()return false end',
            'unit_absent':b'Players[0].GetUnits=function()return {Members=function()return function()return nil end end}end',
            'target_changed':b'fixtureEnemy.GetID=function()return 99 end',
        }
        for change,setup in changes.items():
            with self.subTest(change=change):
                lua=LuaRuntime(encoding=None);lua.execute(unit_setup(ready=False))
                before=units.parse_candidates(lua.execute(units.candidate_source(0,7,core_sha256=XP1)),0,7,core_sha256=XP1)
                self.assertEqual(before['candidates'],[CANDIDATE])
                lua.execute(setup)
                result=units.parse_candidates(lua.execute(units.candidate_source(0,7,core_sha256=XP1)),0,7,core_sha256=XP1)
                self.assertNotIn(CANDIDATE,result['candidates'])
                with self.assertRaises(Exception):
                    lua.execute(units.request_source(0,7,CANDIDATE,width=3,height=2,core_sha256=XP1))
                self.assertEqual(lua.globals().requests,0)
                self.assertEqual(lua.globals().fixtureForbidden(),0)

    def test_unready_unit_keeps_session_perspective_activity_and_ownership_gates(self):
        changes=(b'Game.GetLocalPlayer=function()return 1 end',
                 b'Game.GetCurrentGameTurn=function()return 8 end',
                 b'fixturePlayer.IsAlive=function()return false end',
                 b'fixturePlayer.IsTurnActive=function()return false end',
                 b'fixturePlayer.IsTurnActiveComplete=function()return false end',
                 b'fixtureActor.GetOwner=function()return 1 end')
        for setup in changes:
            with self.subTest(setup=setup):
                lua=LuaRuntime(encoding=None);lua.execute(unit_setup(ready=False));lua.execute(setup)
                with self.assertRaises(Exception):lua.execute(units.candidate_source(0,7,core_sha256=XP1))
                with self.assertRaises(Exception):lua.execute(units.request_source(0,7,CANDIDATE,width=3,height=2,core_sha256=XP1))
                self.assertEqual(lua.globals().requests,0)

    def test_unready_city_target_catalogue_and_request_keep_routes_and_defenses(self):
        for route,ranged,modifier in (('dedicated_ranged',True,None),('world_plot',True,0),('world_plot',False,3)):
            with self.subTest(route=route,ranged=ranged):
                values=[]
                for engine,ready in ((BASE,True),(XP1,True),(XP1,False)):
                    lua=LuaRuntime(encoding=None);lua.execute(city_setup(ready=ready,
                        extra=b'' if ranged else b'ranged=false'))
                    value=cities.parse(lua.execute(cities.source(7,core_sha256=engine)),7,0);values.append(value)
                    row=next(r for r in value['candidates'] if r['input_route']==route)
                    action=dict(kind='unit_attack',unit_id=17,operation=row['operation'],input_route=route,plot_id=1,x=1,y=0)
                    self.assertEqual(lua.execute(cities.request_source(7,action,value['cities'][0],core_sha256=engine)),b'submitted')
                    self.assertEqual(lua.globals().requests,1);self.assertEqual(lua.globals().submittedModifier,modifier)
                    self.assertEqual(lua.globals().hiddenReads,0)
                self.assertEqual(values[0],values[1]);self.assertEqual(values[1],values[2])
        lua=LuaRuntime(encoding=None);lua.execute(city_setup(ready=False))
        self.assertEqual(cities.parse(lua.execute(cities.source(7)),7,0)['candidates'],[])

    def test_city_native_rejection_still_stops_request_after_published_offer(self):
        lua=LuaRuntime(encoding=None);lua.execute(city_setup(ready=False))
        value=cities.parse(lua.execute(cities.source(7,core_sha256=XP1)),7,0)
        row=value['candidates'][0]
        action=dict(kind='unit_attack',unit_id=17,operation=row['operation'],input_route=row['input_route'],plot_id=1,x=1,y=0)
        lua.execute(b'UnitManager.CanStartOperation=function()return false end')
        after=cities.parse(lua.execute(cities.source(7,core_sha256=XP1)),7,0)
        self.assertEqual(after['cities'],value['cities']);self.assertEqual(after['candidates'],[])
        with self.assertRaises(Exception):lua.execute(cities.request_source(7,action,value['cities'][0],core_sha256=XP1))
        self.assertEqual(lua.globals().requests,0)

    def test_unready_city_request_rechecks_visibility_identity_and_session_boundary(self):
        changes=(b'show=false',b'PlayersVisibility[0].IsRevealed=function()return false end',
                 b'damage=21',b'owner=0',b'cityID=56',b'observer=1',b'war=false',b'extraWar=true',
                 b'Game.GetLocalPlayer=function()return 1 end',b'Game.GetCurrentGameTurn=function()return 8 end',
                 b'Game.IsAllowStrategicCommands=function()return false end',
                 b'Players[0].IsAlive=function()return false end',
                 b'Players[0].IsTurnActive=function()return false end',
                 b'Players[0].IsTurnActiveComplete=function()return false end',
                 b'Players[0].GetUnits=function()return {Members=function()return function()return nil end end}end')
        for setup in changes:
            with self.subTest(setup=setup):
                lua=LuaRuntime(encoding=None);lua.execute(city_setup(ready=False))
                value=cities.parse(lua.execute(cities.source(7,core_sha256=XP1)),7,0)
                row=value['candidates'][0]
                action=dict(kind='unit_attack',unit_id=17,operation=row['operation'],input_route=row['input_route'],plot_id=1,x=1,y=0)
                lua.execute(setup)
                with self.assertRaises(Exception):lua.execute(cities.request_source(7,action,value['cities'][0],core_sha256=XP1))
                self.assertEqual(lua.globals().requests,0);self.assertEqual(lua.globals().hiddenReads,0)

    def test_composed_shared_apply_unready_has_no_cancel_or_extra_publication(self):
        f=Fixture();self.addCleanup(f.close)
        lua=LuaRuntime(encoding=None);lua.execute(unit_setup(ready=False,owner_fixture=True))
        evaluate=f.token.prefix.runtime.evaluate_text
        actual_lua=[];all_queries=[]
        def run(child,source,name,**kwargs):
            all_queries.append(name)
            if name==b'@explicit_combat_catalog':
                actual_lua.append(name);return lua.execute(source)
            if name==b'@explicit_unit_attack_request':
                self.assertEqual(lua.execute(source),b'submitted');actual_lua.append(name)
            return evaluate(child,source,name,**kwargs)
        with patch.object(f.token.prefix.runtime,'evaluate_text',run):
            result=f.execute_attack()
        self.assertEqual(result['effect']['status'],'completed')
        self.assertTrue(result['effect']['receipt']['effect']['target_visible_damage_increased'])
        self.assertEqual(lua.globals().requests,1)
        self.assertEqual(actual_lua.count(b'@explicit_unit_attack_request'),1)
        self.assertNotIn(b'@explicit_unit_order_request',all_queries)
        self.assertEqual((f.token.publication_count,f.token.sequence),(1,1))
        self.assertEqual(f.token.transport.pending,[]);self.assertEqual(f.deferred.pending,[])


if __name__=='__main__':unittest.main()
