"""Candidate source/route fixtures, without loading or executing GameCore.

The optional stock-Lua test removes only Civ's type annotations in the fixture
copy. Production Lua bytes are untouched. Native game getters are explicit
fixtures; the original official movement functions decide the route.
"""
import ast, copy, importlib.util, json, os, re, struct, sys
from pathlib import Path
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch

HERE=Path(__file__).resolve().parent
HOST=next(p for p in HERE.parents if (p/'src/civ6_host').is_dir())
LAB=HOST.parent/'civ6-rl-lab'
os.environ.setdefault('CIV6_HOST_RESOURCE_ROOT',str(LAB));sys.path.insert(0,str(HOST/'src'))
sys.path.append(str(LAB/'work/lua-test-deps'))
try:
    from lupa.lua51 import LuaRuntime
except ImportError:
    LuaRuntime=None
def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path);mod=importlib.util.module_from_spec(spec)
    sys.modules[name]=mod;spec.loader.exec_module(mod);return mod
profile_path=HERE/'xp1_world_input_profile.py'
if not profile_path.is_file():profile_path=HOST/'src/civ6_host/runtime/xp1_world_input_profile.py'
hook_path=HERE/'extraction_xp1_world_input.py'
if not hook_path.is_file():hook_path=HOST/'tools/extraction_xp1_world_input.py'
profile=load('civ6_host.runtime.xp1_world_input_profile',profile_path)
hook=load('world_input_extraction_fixture',hook_path)
from civ6_host.runtime.configuration_profiles import BASE_CORE_SHA256 as BASE, XP1_CORE_SHA256 as XP1
from civ6_host.runtime.native import native_world_input as original_world
from civ6_host.runtime.native import native_world_click as original_click
from civ6_host.runtime.native import native_saved_combat as original_combat

def transformed(module,original):
    raw=Path(original.__file__).read_text(encoding='utf-8')
    out=raw if '_WORLD_BASE_CORE_SHA256' in raw else hook.parameterize('civ6rl.'+module,raw)
    mod=NS(__name__='fixture_'+module);exec(compile(out,'<extraction:'+module+'>','exec'),mod.__dict__)
    return mod,out
world,WORLD=transformed('native_world_input',original_world)
click,CLICK=transformed('native_world_click',original_click)
combat,COMBAT=transformed('native_saved_combat',original_combat)

LUA_SETUP=r'''
sent,warQueries,canQueries=0,0,0
local unit={}
function unit:GetOwner()return 0 end
function unit:GetID()return 17 end
function unit:GetUnitType()return 3 end
function unit:GetComponentID()return {player=0,id=17} end
function unit:GetPlotId()return 0 end
function unit:GetX()return 0 end
function unit:GetY()return 0 end
function unit:GetRangedCombat()return ranged and 50 or 0 end
function unit:GetBombardCombat()return bombard and 50 or 0 end
function unit:GetCombat()return 20 end
Game={GetLocalPlayer=function()return 0 end,GetLocalObserver=function()return 0 end,
 GetCurrentGameTurn=function()return 8 end,IsAllowStrategicCommands=function()return true end}
local player={}
function player:IsAlive()return true end
function player:IsTurnActive()return true end
function player:IsTurnActiveComplete()return true end
function player:GetUnits()return {Members=function()return ipairs({unit}) end} end
Players={[0]=player}
GameInfo={Units={[3]={Domain=air and 'DOMAIN_AIR' or 'DOMAIN_LAND',IgnoreMoves=false}}}
Map={GetGridSize=function()return 4,3 end,GetPlotCount=function()return 12 end,
 GetPlotByIndex=function(i)return {GetIndex=function()return i end,
  GetX=function()return i%4 end,GetY=function()return math.floor(i/4) end} end}
PlayersVisibility={[0]={IsVisible=function()return visible end}}
CombatManager={IsAttackChangeWarState=function()warQueries=warQueries+1;return war and {9} or {} end}
UnitOperationTypes={MOVE_TO=19,RANGE_ATTACK=20,COASTAL_RAID=21,SWAP_UNITS=22,
 AIR_ATTACK=23,DEPLOY=24,PARAM_X=101,PARAM_Y=102,PARAM_MODIFIERS=103}
UnitOperationMoveModifiers={NONE=0,ATTACK=16,MOVE_IGNORE_UNEXPLORED_DESTINATION=16384}
UnitManager={CanStartOperation=function(u,op,nilarg,p)
 assert(u==unit and nilarg==nil and p[101]~=nil and p[102]~=nil)
 canQueries=canQueries+1;return op==enabled
end,RequestOperation=function(u,op,p)
 assert(u==unit);sent=sent+1;sentOp=op;sentX=p[101];sentY=p[102];sentModifiers=p[103]
end}
WarTypes={SURPRISE_WAR=0};LuaEvents={}
'''

class WorldInputTests(unittest.TestCase):
    def test_source_and_live_byte_guards_cover_ui_plot_not_coordinate_type(self):
        proof=profile.verify_source();self.assertEqual(len(proof['bindings']),14)
        self.assertEqual(proof['bindings']['Plot.GetX']['registrar_rva'],'0x19f80')
        from civ6_host.runtime.xp1_status_profiles import _instruction_spans
        base=0x250000000;memory={};reads=[]
        for rva,raw in _instruction_spans(proof):
            memory.update({base+rva+i:b for i,b in enumerate(raw)})
        for name,row in proof['bindings'].items():
            raw=name.split('.')[1].encode()+b'\0';address=base+int(row['name_va'],16)-0x180000000
            memory.update({address+i:b for i,b in enumerate(raw)})
        def read(address,size):reads.append((address,size));return bytes(memory[address+i] for i in range(size))
        count=profile.verify_live(base,read);self.assertLess(count,100)
        memory[base+profile.CALLBACKS['UnitManager.GetQueuedDestination']]^=1
        with self.assertRaisesRegex(ValueError,'instructions changed'):profile.verify_live(base,read)
        with self.assertRaises(ValueError):profile.verify_source(BASE)

    def test_shared_base_bytes_unchanged_and_xp1_keyword_propagation(self):
        self.assertEqual(world.catalog_source(0,8),original_world.catalog_source(0,8))
        self.assertEqual(click.request_source(0,8,17,6),original_click.request_source(0,8,17,6))
        self.assertEqual(combat.queued_destination_source(0,8,17),original_combat.queued_destination_source(0,8,17))
        for text,fn,callnames in ((WORLD,'apply',{'observe','click.request_source','click.parse_request_result','queued_destination'}),
             (WORLD,'observe',{'catalog_source'}),(COMBAT,'queued_destination',{'queued_destination_source'})):
            tree=ast.parse(text);body=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name==fn)
            calls=[n for n in ast.walk(body) if isinstance(n,ast.Call) and ast.unparse(n.func) in callnames]
            self.assertEqual(len(calls),len(callnames))
            for call in calls:self.assertEqual([(k.arg,ast.unparse(k.value)) for k in call.keywords if k.arg=='core_sha256'],[('core_sha256','core_sha256')])
        with patch.object(original_combat.native,'_uint',wraps=original_combat.native._uint):
            self.assertEqual(combat.queued_destination_source(0,8,17,core_sha256=XP1),original_combat.queued_destination_source(0,8,17))

    def test_catalogue_is_own_roster_and_entire_public_grid_including_zero_moves(self):
        state=dict(schema=world.SCHEMA,player_id=0,turn=8,width=4,height=3,
          units=[dict(unit_id=17,ignore_moves=False),dict(unit_id=19,ignore_moves=True)],selected_unit_id=17,war_prompt=None)
        choices=world.actions(state)
        self.assertEqual([v['plot_id'] for v in choices if v['kind']=='world_plot_click'],list(range(12)))
        self.assertEqual([v['unit_id'] for v in choices if v['kind']=='world_select_unit'],[17])
        source=world.catalog_source(0,8,core_sha256=XP1)
        self.assertNotIn(b'GetMovesRemaining',source);self.assertNotIn(b'IsVisible',source)
        owner=NS(world_input_prompts={0:{'attacking_player':0}})
        with self.assertRaisesRegex(ValueError,'war confirmation'):world.observe(owner,{'player_id':0,'turn':8},core_sha256=XP1)

    @unittest.skipUnless(LuaRuntime,'Stock Lua interpreter unavailable; source/owner tests remain separate')
    def test_actual_official_lua_route_refuses_before_transmission_without_hidden_details(self):
        rows=[('move',{},6,'request',1,19),('same_plot',{},0,'noop',0,None),
          ('ranged',{'ranged':True,'enabled':20},6,'unsupported',0,None),
          ('bombard',{'bombard':True,'enabled':20},6,'unsupported',0,None),
          ('raid',{'enabled':21},6,'unsupported',0,None),('swap',{'enabled':22},6,'unsupported',0,None),
          ('air_attack',{'air':True,'enabled':23},6,'unsupported',0,None),
          ('deploy',{'air':True,'enabled':24},6,'unsupported',0,None),
          ('air_noop',{'air':True},6,'noop',0,None),
          ('visible_war',{'visible':True,'war':True},6,'unsupported',0,None),
          ('hidden_target',{'visible':False,'war':True},6,'request',1,19)]
        for name,values,dest,status,sent,op in rows:
                with self.subTest(route=name):
                    declarations=';'.join(k+'='+('true' if v is True else 'false' if v is False else str(v)) for k,v in values.items())+'\n'
                    raw=click.request_source(0,8,17,dest,core_sha256=XP1).decode('utf8')
                    # Civ's Lua grammar adds variable/parameter type annotations.
                    # Only the test copy is normalized for stock Lua 5.1.
                    raw=re.sub(r':\s*(?:number|table|string|boolean)\b','',raw)
                    script=declarations+LUA_SETUP+'\nlocal function run()\n'+raw+'\nend\nreturn run(),sent,warQueries\n'
                    raw_result,sent_count,war_count=LuaRuntime(max_memory=4*1024*1024).execute(script)
                    parsed=click.parse_request_result(raw_result.encode(),0,8,17,dest,core_sha256=XP1)
                    self.assertEqual(parsed['status'],status);self.assertEqual(sent_count,sent)
                    self.assertEqual(parsed.get('operation'),op)
                    if status=='unsupported':
                        self.assertFalse(parsed['native_callback_invoked'])
                        self.assertFalse({'operation','parameters','defender_player_id','war_type'}&parsed.keys())
                        with self.assertRaises(ValueError):click.parse_request_result(raw_result.encode(),0,8,17,dest)
                    if name=='hidden_target':self.assertEqual(war_count,0)

    def test_shared_apply_unsupported_preserves_state_but_is_not_gameplay_success(self):
        # Equal state proves non-mutation only. The client must retain this as
        # unavailable capability/refusal, never promote it to completed/noop.
        from civ6_host.runtime.native import native_player_observation as observations
        before=dict(player_id=0,turn=8,width=4,height=3,units=[dict(id=17)])
        state=dict(schema=world.SCHEMA,player_id=0,turn=8,width=4,height=3,
            units=[dict(unit_id=17,ignore_moves=False)],selected_unit_id=17,war_prompt=None)
        receipt=','.join(['unsupported','0','8','17','6','4','3','-','-','-','-','-',original_click._SOURCE_HASH]).encode()
        native_reads=[];emitted=[];snapshots=[]
        def evaluate(child,source,name,**kw):
            native_reads.append(name)
            if name==b'@world_input_own_units':return json.dumps(state['units']).encode()
            if name==b'@official_world_click':return receipt
            if name==b'@explicit_own_queued_destination':return b'none'
            self.fail('Unexpected native call '+str(name))
        owner=NS(prefix=NS(runtime=NS(evaluate_text=evaluate),ui_child=object(),
                actions=NS(pending=[]),deferred_events=NS(pending=[])),
            explicit_world_input=copy.deepcopy(state),world_input_selections={0:17},world_input_prompts={},
            control=lambda **kw:None,emit=lambda stage,**data:emitted.append((stage,data)))
        def snap(actual,phase):self.assertIs(actual,owner);snapshots.append(phase);return {'jobs':0}
        action=dict(kind='world_plot_click',unit_id=17,plot_id=6,x=2,y=1)
        # Only native reads/control are fixtures. Shared source, parser, apply,
        # candidate membership, receipt and UI-only state invariants execute.
        with patch('civ6_host.runtime.native.native_world_click',click),patch.object(original_combat,'queued_destination',combat.queued_destination),\
             patch.object(observations,'observe_player',return_value=copy.deepcopy(before)):
            result=world.apply(owner,action,8,before,core_sha256=XP1,snapshot_reader=snap)
        self.assertEqual(result,before);self.assertEqual(snapshots,['before','after'])
        self.assertFalse(emitted[-1][1]['archive_delivered']);self.assertEqual(owner.world_input_prompts,{})
        self.assertEqual(owner.prefix.actions.pending,[])
        self.assertEqual(emitted[-1][1]['request']['status'],'unsupported')

    def test_newly_reused_pure_movement_callbacks_on_real_a0_and_fifo(self):
        # The five native-query Unit/Improvement branches are already qualified
        # in native-session06. Exercise the additional pure producer branches
        # observed in the retained Base movement intervals on the actual A0.
        sys.path.insert(0,str(HOST/'work/xp1-action-integration/transport-tests'))
        import test_found_unit_a0 as fixture
        from civ6_host.runtime.a0_family_source import family_profile
        fixture.PROFILE=family_profile();f=fixture.Fixture()
        memory={0x70000000:struct.pack('<HHI',0,1,17),0x70000010:struct.pack('<II',2,1)}
        reads=[]
        def read(address,size):
            reads.append((address,size));self.assertEqual(size,8);return memory[address]
        f.owner.read=f.arguments.reader.read=read
        def blob(tag,address):return struct.pack('<I4xQII',tag,address,8,553648129)
        s=fixture.scalar;sel=2716180809;unit=4032072631;value=3606901732;second=2717631346
        desc=blob(1024,0x70000000);position=blob(0,0x70000010)
        pair={sel:s(3,0),unit:desc,value:s(2,19),second:s(2,0)}
        cases=[(0x15c35863,{sel:s(3,0),value:s(2,19),unit:desc},67),
               (0xa60328c5,pair,70),(0x383669f1,{sel:s(3,0),unit:desc},71),
               (0xe992f3cd,{sel:s(3,0),unit:desc},26),(0xcb0345f1,pair,69),
               (0xbe121408,{2353434172:position,1198250499:s(1,0),3332537204:s(1,1),360746564:s(3,0),unit:desc},23),
               (0xf26f3acf,{sel:s(3,0),3937836634:desc},256),
               (0x9ad1c020,{sel:s(3,0),3937836634:desc},258),
               (0x1f943311,{sel:s(3,0),2353434172:position},287),
               (0x8fef0d8e,{sel:s(3,0)},288)]
        for kind,fields,record in cases:
            with self.subTest(kind=hex(kind)):
                self.assertEqual(f.owner.dispatch(kind,fields,0),0)
                self.assertEqual(int.from_bytes(f.deferred.pending[-1][4:8],'little'),record)
                self.assertIsNone(f.owner.active_kind)
        self.assertEqual(len(f.deferred.pending),10)
        self.assertEqual(f.deferred.drain(),10);self.assertEqual(f.deferred.consumed_count,10)
        self.assertEqual(f.deferred.pending,[]);self.assertEqual((f.owner.host_notification_counter,f.owner.host_metadata_counter),(0,0))
        self.assertTrue(reads);f.owner.close();self.assertTrue(f.owner.closed)

if __name__=='__main__':unittest.main()
