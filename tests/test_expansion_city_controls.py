"""Offline XP2 owner, transport and FIFO tests using registered source proofs."""
from copy import deepcopy
import ctypes as C
import hashlib
import json
from pathlib import Path
import re
import struct
import sys
import unittest
from unittest.mock import patch

HOST=Path(__file__).resolve().parents[1]
PRIVATE=HOST/'work/expansion-city-controls-preparation'
from civ6_host.runtime import expansion_city_controls as adapter
from civ6_host.runtime import expansion_city_controls_profile as profile
from civ6_host.runtime.configuration_profiles import XP1_CORE_SHA256,XP2_CORE_SHA256,BASE_CORE_SHA256
from civ6_host.runtime import resource_resolution
from civ6_host.contracts import network_turn as contract
from civ6_host.runtime.event_argument_service import EventArgumentReader
from civ6_host.runtime.native import native_action_transport as action_calls,native_player_view as view_calls
from civ6_host.runtime.native import native_saved_city_focus1000 as focus,native_saved_citizens as citizens
from civ6_host.runtime.xp1_continuation import READY,ACTIVE
sys.path.insert(0,str(HOST/'tests'))
import test_xp2_checkpoint_composition as retained_graph
from test_xp1_turn_a0 import scalar

class Fixture(retained_graph.Fixture):
    def __init__(self):
        # Original fixture streams/graphs remain read-only; all its generated
        # JSON stays below the one authorized private output root.
        with patch.object(retained_graph,'LAB',PRIVATE/'fixture-output'):
            super().__init__()
        self.links={};self.commands={};self.next_address=0x79000000;self.citizen_no_change=False
        self.focus_flags=[(False,False)]*6
        self.citizen_rows=[dict(plot_id=1,x=1,y=0,occupied=True,locked=False,workers=None,capacity=None),
            dict(plot_id=2,x=2,y=0,occupied=False,locked=False,workers=0,capacity=2)]
        self.observation['cities']=[dict(id=5,x=0,y=0,population=1,owner=0,yields=dict(food=1,production=1,gold=1,science=1,culture=1,faith=0))]
        self.token.observation=deepcopy(self.observation)
        self.memory.put(self.memory.member+0x28,struct.pack('<iii',44,26,44*26))
        self.token.publisher.cache_map_snapshot=struct.pack('<iii',44,26,44*26)+self.token.publisher.cache_map_snapshot[12:]
        self.stack.enter_context(patch.object(action_calls,'virtual',self.virtual))
        self.stack.enter_context(patch.object(view_calls,'virtual',self.virtual))
        self.arguments.reader=EventArgumentReader(self.backend.core,core_sha256=XP2_CORE_SHA256,read=self.backend.runtime.read)
        self.owner.read=self.backend.runtime.read
        self.token.publisher.emit=self.emit
        from civ6_host.runtime.unit_operation_ui_profile import verify_live
        self.token.unit_source=verify_live(self.backend.core._handle,self.read,core_sha256=XP2_CORE_SHA256)
        from civ6_host.runtime.native.native_host import DiagnosticHost
        self.host._check=DiagnosticHost._check.__get__(self.host)
        self._cache_registry()
        adapter.enable(self.saved,dict(city_focus_diagnostic=True,city_management_diagnostic=True))

    def _cache_registry(self):
        base=self.backend.core._handle
        from civ6_host.runtime import xp2_preload_source as source
        for name in ('cache_outer198','cache_keyed_dispatch','b0_snapshot_emitter'):
            for f in source.body(name)['fragments']:self.memory.put(base+int(f['start_rva'],16),bytes.fromhex(f['raw_hex']))
        self.memory.q(base+0xa101e8+0x198,base+0x591920)
        kinds=(0xe808a01e,0x1d103404,0xc2f385c0,0x67001fe1)
        self.memory.put(base+0xb61e10,struct.pack('<QII',0x7c000000,1,len(kinds)))
        self.memory.put(0x7c000000,struct.pack('<QQ',0x7c001000,0x7c009999))
        for i,kind in enumerate(kinds):
            pointer=0x7c001000+i*0x100;vector=0x7c010000+i*0x100
            node=bytearray(48);struct.pack_into('<I',node,0,kind)
            struct.pack_into('<QQQ',node,8,vector,vector+32,vector+32)
            struct.pack_into('<Q',node,40,pointer+0x100 if i+1<len(kinds) else 0x7c009999)
            self.memory.put(pointer,node);self.memory.put(vector,struct.pack('<QQQQ',0,0,0x7d001000,0x7d002000))
        self.deferred.base=base;self.deferred.read=self.backend.runtime.read;self.deferred.cache_update_callback_pair=None

    def lua(self,pointer,source,name):
        pid,city,turn=0,5,1
        match=re.search(rb'local pid,cityID,turn=(\d+),(\d+),(\d+)',source)
        if match:pid,city,turn=map(int,match.groups())
        if name==b'@lan_session_humans':return b'0=1|1=0'
        if name==b'@lan_turn_activity':return b'1|0|0|0,1,1,0;1,0,0,0'
        if name==b'@native_player_observation':return json.dumps(self.observation).encode()
        if name==b'@explicit_city_focus_catalog1000':
            return ('city-focus1000-v1|%d|%d|%d\n'%(pid,turn,city)+'\n'.join(
                f'{n}|{i}|{int(f)}|{int(d)}' for i,(n,(f,d)) in enumerate(zip(focus.YIELDS,self.focus_flags)))).encode()
        if name==b'@explicit_city_citizens_catalog':
            return ('city-citizens-v1|%d|%d|%d\n'%(pid,turn,city)+'\n'.join(citizens._plot_wire(row) for row in self.citizen_rows)).encode()
        if name==b'@explicit_city_focus_request1000':
            index=int(re.search(rb'assert\(row.Index==(\d+)',source)[1])
            commands=[('focus',index,int(a),int(b)) for a,b in re.findall(rb'params\[cc.PARAM_FLAGS\]=(\d+);params\[cc.PARAM_YIELD_TYPE\]=row.Index;params\[cc.PARAM_DATA0\]=(\d+)',source)]
        elif name==b'@explicit_city_citizens_request':
            target=int(re.search(rb'if row.id==(\d+)',source)[1]);commands=[('citizen',target)]
        else:raise AssertionError('Unmodelled native Lua '+repr(name))
        for command in commands:
            # The native archive creation is the machine boundary. Its real
            # bounded capture/queue/receive/drain ownership runs below.
            payload=b'OFFLINE_CITY_ARCHIVE:'+json.dumps(command).encode();self.commands[payload]=command
            address=self.next_address;self.next_address+=0x1000
            self.memory.put(address,struct.pack('<QQ',self.backend.core._handle+self.token.transport.transport_abi.archive_vtable_rva,address+0x100))
            self.memory.put(address+0x100,payload);self.archive_size=len(payload)
            self.token.transport.capture(self.host.pointer,address)
        return b'submitted'

    def _script_runtime(self):
        super()._script_runtime()
        def evaluate(pointer,source,length,name,out,capacity,written):
            assert pointer in (self.prefix.ui_child.pointer,self.prefix.game_child.pointer)
            raw=self.lua(pointer,C.string_at(source,length),C.string_at(name));assert len(raw)<=capacity
            C.memmove(out,raw,len(raw));C.cast(written,C.POINTER(C.c_size_t))[0]=len(raw);return 0
        self.prefix.runtime.host.LAB_ScriptEvaluateText=retained_graph.NATIVE_CALLBACK(C.c_int,C.c_void_p,C.c_char_p,C.c_size_t,
            C.c_char_p,C.c_void_p,C.c_size_t,C.POINTER(C.c_size_t))(evaluate)

    def factory(self,result,*args):
        old=super().factory(result,*args)
        def bind(address):
            if callable(address):return old(address)
            a=self.token.transport.transport_abi;base=self.backend.core._handle
            from civ6_host.runtime.event_argument_source import reader_abi
            if address==base+reader_abi(XP2_CORE_SHA256).successor_rva:return self.links.__getitem__
            if address==base+a.view_ctor_rva:
                def ctor(ptr,data,size):
                    self.machine.append(('view_ctor',size));self.input_payload=C.string_at(data,size)
                    C.memmove(ptr,struct.pack('<Q',base+a.view_vtable_rva),8);return ptr
                return ctor
            if address==base+a.view_dtor_rva:return lambda ptr:self.machine.append(('view_dtor',))
            if address==base+0x591920:return lambda ctx,values:self.machine.append(('cache_dispatch',tuple(values)))
            return old(address)
        return bind

    def dispatch(self,kind,fields):
        a=self.arguments.reader.abi;base=self.backend.core._handle
        address=self.next_address;self.next_address+=0x1000;nodes=[address+0x100*(i+1) for i in range(len(fields))]
        self.memory.put(address,struct.pack('<Q',base+a.vtable_rva)+bytes(80))
        self.memory.q(address+56,nodes[0] if nodes else address+48)
        self.memory.put(address+80,struct.pack('<I',len(fields)))
        for i,((key,value),node) in enumerate(zip(sorted(fields.items()),nodes)):
            self.memory.put(node+32,struct.pack('<I',key));self.memory.put(node+40,value)
            self.links[node]=nodes[i+1] if i+1<len(nodes) else address+48
        return self.arguments.dispatch(self.host.pointer,kind,address)

    def fields(self):
        desc,pos,second=0x7b000000,0x7b000100,0x7b000200
        self.memory.put(desc,struct.pack('<HHI',0,1,5));self.memory.put(pos,struct.pack('<ii',0,0))
        self.memory.put(second,struct.pack('<HHI',0,3,17))
        blob=lambda tag,ptr:struct.pack('<H6xQII',tag,ptr,8,0x21000001)
        return {0xa1e5a149:scalar(3,0),0x23739f42:blob(1024,desc)},blob(0,pos),blob(1024,second)

    def callbacks(self,citizen):
        common,pos,second=self.fields()
        self.dispatch(0xe808a01e,common)
        for selector in (0x878f03af,0xe431107f,0x3afc843a,0x08618ce6,0x3a22caec,0xcdf04e2f):
            self.deferred.cache_update(self.host.pointer,0xe808a01e,(23<<32)|selector)
        self.deferred.cache_update(self.host.pointer,0x67001fe1,(24<<32)|0x77d19dc2)
        self.dispatch(0x1d103404,dict(common,**{})|{0xd6fcf3e4:scalar(2,729125427 if citizen else 1),0xa1fbc372:scalar(2,0),0xf343dc5a:second})
        if citizen:self.dispatch(0xc2f385c0,common|{0x8c468e3c:pos})
        before=(tuple(self.deferred.pending),self.deferred._sequence,self.deferred.consumed_count)
        self.dispatch(0x67001fe1,common|{0xd6fcf3e4:scalar(2,1),0xa1fbc372:scalar(2,0),0x8c468e3c:pos})
        assert before==(tuple(self.deferred.pending),self.deferred._sequence,self.deferred.consumed_count)

    def virtual(self,core,pointer,slot,rva,result,*args):
        a=self.token.transport.transport_abi;cache=self.token.publisher.cache_abi
        assert core is self.backend.core
        if rva==a.archive_size_rva:return lambda ptr:self.archive_size
        if rva==a.receive_rva:
            def receive(ctx,label,stream):
                self.machine.append(('receive',label));node,data=0x7a000000,0x7a001000
                self.memory.put(data,self.input_payload);self.memory.put(node,struct.pack('<QQI4xQQQ8x',self.sentinel,self.sentinel,label,data,data+len(self.input_payload),data+len(self.input_payload)))
                self.memory.put(self.sentinel,struct.pack('<QQ',node,node))
            return receive
        if rva==a.drain_rva:
            def drain(ctx):
                self.machine.append(('drain',));self.memory.put(self.sentinel,struct.pack('<QQ',self.sentinel,self.sentinel))
                command=self.commands[self.input_payload]
                if command[0]=='focus':
                    _,index,flag,data=command;values=list(self.focus_flags[index]);values[flag]=bool(data);self.focus_flags[index]=tuple(values)
                else:
                    row=next(r for r in self.citizen_rows if r['plot_id']==command[1])
                    # Native result simulation only; no assignment logic in product.
                    if self.citizen_no_change:pass
                    elif row['capacity'] is None:row['locked']=not row['locked']
                    else:row['workers']=(row['workers']+1)%3;row['occupied']=row['workers']>0
                self.callbacks(command[0]=='citizen')
            return drain
        if rva==cache.service_ensure_rva:return lambda service:self.machine.append(('ensure',))
        if rva==cache.service_owner_rva:return lambda service:int.from_bytes(self.read(service+8,8),'little')
        from civ6_host.runtime.xp1_cache_publication import publication_target
        if rva==publication_target(XP2_CORE_SHA256):return lambda ctx,desc,flag:self.machine.append(('publish',flag))
        raise AssertionError('Unmodelled native virtual '+hex(rva))

class CityControlsTests(unittest.TestCase):
    def fixture(self):
        f=Fixture.__new__(Fixture);self.addCleanup(f.close);f.__init__();return f
    def query(self,f):
        with f.saved._attempt():return adapter.read(f.saved,f.token.observation)
    def test_actual_owner_focus_cycle_and_citizen_specialist_group(self):
        f=self.fixture();before=deepcopy(f.token.observation)
        for flags,archives in (((False,False),1),((True,False),2),((False,True),1),((True,True),1)):
            with self.subTest(flags=flags):
                f.focus_flags[0]=flags;offers=self.query(f);action=offers['actions'][0]
                start=len([m for m in f.machine if m[0]=='receive'])
                result=f.saved.execute(action)
                self.assertEqual(result['action'],action);self.assertEqual(result['effect']['status'],'completed')
                self.assertEqual(len([m for m in f.machine if m[0]=='receive'])-start,archives)
                self.assertEqual(f.focus_flags[0],focus.transition(action)[1])
                self.assertEqual(result['jobs_before'],result['jobs_after'])
                self.assertEqual(f.token.observation,before)
        for plot in (1,1,2,2,2):
            offers=self.query(f);action=next(a for a in offers['actions'] if a['kind']=='city_citizen' and a['plot_id']==plot)
            result=f.saved.execute(action);self.assertEqual(result['effect']['receipt']['native_commands_delivered'],1)
        self.assertEqual(f.citizen_rows[1]['workers'],0)
        f.citizen_no_change=True;offers=self.query(f)
        action=next(a for a in offers['actions'] if a['kind']=='city_citizen')
        self.assertFalse(f.saved.execute(action)['effect']['receipt']['displayed_state_changed'])
        self.assertEqual(len({m[1][2] for m in f.machine if m[0]=='cache_dispatch'}),7)
        self.assertEqual(f.deferred.pending,[]);self.assertGreater(f.deferred.consumed_count,20)
        self.assertEqual((f.saved.phase,f.saved._running,f.backend.stage,f.backend.busy),('commands',False,READY,False))
        self.assertIsNone(f.backend._xp1_capability_source_scope)
        f.token.transport.require_empty_native_queue();f.backend.control(empty=True)
    def test_source_selection_correspondence_and_base_algorithms_unchanged(self):
        for core in (BASE_CORE_SHA256,XP1_CORE_SHA256,XP2_CORE_SHA256):
            p,s,selected=profile.verify_source(core);self.assertEqual(selected['image']['sha256'],core)
            self.assertTrue(s['callback_comparisons']['GetCitizens']['named_registration_pairs_verified'])
            self.assertIn('core_sha256',__import__('inspect').signature(focus.catalog).parameters)
        with self.assertRaises(ValueError):profile.verify_source('unknown')
        self.assertEqual(focus.verify_source()['core_sha256'],BASE_CORE_SHA256)
        self.assertEqual(citizens.verify_source()['core_sha256'],BASE_CORE_SHA256)
    def test_owner_pending_reentry_unknown_and_stale_refusals(self):
        for change in ('pending','owner','reader','sequence','reentry','unknown'):
            with self.subTest(change=change):
                f=self.fixture();offers=self.query(f);action=offers['actions'][0]
                if change=='pending':f.token.transport.pending.append(b'prior')
                elif change=='owner':f.saved._backend=object()
                elif change=='reader':f.arguments.reader.core=object()
                elif change=='sequence':f.token.sequence+=1
                elif change=='reentry':f.saved._running=True
                if change=='unknown':
                    with f.saved._attempt():
                        f.backend.stage,f.backend.busy=ACTIVE,True
                        with self.assertRaises((ValueError,RuntimeError)):f.dispatch(0x12345678,f.fields()[0])
                else:
                    with self.assertRaises((ValueError,RuntimeError)):f.saved.execute(action)
                self.assertEqual(f.machine,[])
                f.close()

def v12_catalogue(f,sequence,*,closed=False):
    from civ6_host.contracts.capability_world_input import WORLD_KINDS
    from civ6_host.contracts.production_queue import FIELDS as QUEUES
    from civ6_host.contracts.placement import ACTION_FIELDS as PLACEMENTS
    kinds=('found_city','research','civic','production','end_turn','force_end_turn','unready_turn',
        *sorted(WORLD_KINDS),*QUEUES,*PLACEMENTS,'unit_order','unit_attack','other_human_actions')
    families={kind:dict(status='unqualified',reason='offline_unqueried_other_family') for kind in kinds}
    value=dict(schema=contract.CAPABILITY_CITY_CONTROLS_SCHEMA,
        episode_id=f.token.identity.episode_id,game_generation=f.token.identity.game_generation,sequence=sequence,
        player_id=0,turn=1,turn_controls=dict(schema=contract.TURN_CONTROLS_SCHEMA,player_id=0,turn=1,
            active=True,active_complete=True,can_unready=False,timer_elapsed=None),
        candidates=[],families=families,family_inventory_complete=False,complete_action_space=False,
        choice_state=(None if closed else dict(research=dict(research=None,civic=None),
            production=[dict(city_id=5,queue_size=0,kind='N',item_index=None,hash=0,formation=None)])),turn_availability=dict(end_turn=None,force_end_turn=None,unready_turn=None),
        world_input=None,queued_orders=None,unit_orders=None,unit_attacks=None,
        production_queues=None,placement_offers=None,placements=None,placement_observation_scope=None,placement_inventory=None,
        city_focus_catalogs=None,citizen_catalogs=None)
    if not closed:
        with f.saved._attempt():city=adapter.read(f.saved,f.token.observation)
        value.update(city_focus_catalogs=city['city_focus_catalogs'],citizen_catalogs=city['citizen_catalogs'])
        value['candidates']=[dict(candidate_id=contract.digest(a),action=a) for a in city['actions']]
    for kind,key in (('city_focus','city_focus_catalogs'),('city_citizen','citizen_catalogs')):
        families[kind]=(dict(status='unqualified',reason='session_closed') if closed else
            dict(status='queried_complete',candidate_ids=[r['candidate_id'] for r in value['candidates'] if r['action']['kind']==kind]))
    value['decision_id']=contract.digest(value)
    return value


class CityClientAndSourceTests(CityControlsTests):
    # Existing owner group runs once in its own class; this subclass shares only
    # fixture/source setup, not inherited test replay.
    test_actual_owner_focus_cycle_and_citizen_specialist_group=None
    test_source_selection_correspondence_and_base_algorithms_unchanged=None
    test_owner_pending_reentry_unknown_and_stale_refusals=None

    def test_existing_session_client_and_protocol_execute_composed_choices(self):
        from test_session_capabilities import CapabilityBackend
        from civ6_host.runtime.network_protocol import NetworkProtocol,validate_network_response
        from civ6_host.session_client import SessionClient
        from uuid import uuid4
        f=self.fixture()
        class Backend(CapabilityBackend):
            def _reply(self,operation,sequence,player,requested=None):
                result=super()._reply(operation,sequence,player,requested)
                if result['decisions'] is not None:
                    result['observation']=deepcopy(f.token.observation)
                    result['decisions']=v12_catalogue(f,sequence)
                return result
            def reset(self):
                self.identity=f.token.identity;self.protocol=NetworkProtocol(self.identity,uuid4().hex,initial_turn=1)
                self.consumed=set();response=self._reply('reset',0,0)
                validate_network_response(response,self.protocol,'reset');self.protocol.accept_response(response);return response
            def request(self,request):
                self.calls.append(deepcopy(request));operation=self.protocol.validate(request)
                selected=self.protocol.selected(request) if operation=='act' else None
                if selected is not None:f.saved.execute(selected)
                response=self._reply(operation,request['sequence'],request['player_id'],selected)
                validate_network_response(response,self.protocol,operation,request=request)
                self.protocol.commit_reply(request,response);self.protocol.accept_response(response);return response
        backend=Backend();client=SessionClient(backend);view=client.reset()
        for kind in ('city_focus','city_citizen'):
            decisions=view['decisions'];choice=next(r for r in decisions['candidates'] if r['action']['kind']==kind)
            view=client.act(0,decisions['decision_id'],choice['candidate_id'])
            self.assertEqual(client.command_result,dict(status='completed',reason=None,requested_action=choice['action']))
        self.assertEqual(backend.aborts,[]);self.assertEqual(f.token.sequence,2)

    def test_v12_portable_validation_and_no_implicit_checkpoint_transition(self):
        import os,subprocess
        f=self.fixture();value=v12_catalogue(f,0);obs=deepcopy(f.token.observation)
        contract.validate_capability_catalogue(value,f.token.identity,0,1,player_id=0,observation=obs)
        old=deepcopy(value);old['schema']=contract.CAPABILITY_COMBAT_READINESS_SCHEMA
        for key in ('city_focus_catalogs','citizen_catalogs'):old.pop(key)
        for kind in ('city_focus','city_citizen'):old['families'].pop(kind)
        old['candidates']=[];old.pop('decision_id');old['decision_id']=contract.digest(old)
        contract.validate_capability_catalogue(old,f.token.identity,0,1,player_id=0,observation=obs)
        projected,transition=contract.checkpoint_catalogue(value,old,obs,core_sha256=XP2_CORE_SHA256)
        self.assertIs(projected,value);self.assertIsNone(transition);self.assertNotEqual(projected,old)
        same,transition=contract.checkpoint_catalogue(value,deepcopy(value),obs,core_sha256=XP2_CORE_SHA256)
        self.assertEqual(same,value);self.assertIsNone(transition)
        closed=v12_catalogue(f,1,closed=True)
        contract.validate_capability_catalogue(closed,f.token.identity,1,1,player_id=0,observation=obs,actions_closed=True)
        for fault in ('omitted','invented','foreign','hidden_precision','waiting'):
            bad=deepcopy(value)
            if fault=='omitted':bad['candidates'].pop()
            elif fault=='invented':bad['city_focus_catalogs'][0]['city_id']=55
            elif fault=='foreign':bad['citizen_catalogs'][0]['player_id']=1
            elif fault=='hidden_precision':bad['citizen_catalogs'][0]['plots'][0]['workers']=1
            else:bad['turn_controls']['active']=False;bad['turn_controls']['active_complete']=False
            bad.pop('decision_id');bad['decision_id']=contract.digest(bad)
            with self.subTest(fault=fault),self.assertRaises(ValueError):
                contract.validate_capability_catalogue(bad,f.token.identity,0,1,player_id=0,observation=obs)
        script="""import sys,importlib.abc,json
from types import SimpleNamespace
class Refuse(importlib.abc.MetaPathFinder):
 def find_spec(self,name,path=None,target=None):
  if name.startswith(('civ6_host.runtime','torch')):raise AssertionError(name)
sys.meta_path.insert(0,Refuse())
from civ6_host.session_client import SessionClient
from civ6_host.contracts import network_turn
value,obs=json.load(sys.stdin)
network_turn.validate_capability_catalogue(value,SimpleNamespace(episode_id=value['episode_id'],game_generation=value['game_generation']),value['sequence'],obs['turn'],player_id=obs['player_id'],observation=obs)
"""
        env=os.environ.copy();env.pop('CIV6_HOST_RESOURCE_ROOT',None);env['PYTHONPATH']=str(HOST/'src')
        done=subprocess.run([sys.executable,'-c',script],input=json.dumps((value,obs)),env=env,capture_output=True,text=True,timeout=10)
        self.assertEqual(done.returncode,0,done.stderr)

    def test_actual_configuration_selects_sources_without_changing_defaults(self):
        from civ6_host.runtime.native.network_session import NativeNetworkSession
        from civ6_host.runtime.captured_session_profile import for_family
        private_ref=PRIVATE/'configuration-fixture-reference.json'
        private_ref.write_text('{"offline_reference_only":true}',encoding='utf8')
        for family in ('xp1-lan','xp2-lan'):
            selected=for_family(family)
            kwargs=dict(input_profile=family,official_bundle=dict(zip(('path','sha256'),selected.candidate.reference)),
                prepared_capture=dict(path=str(private_ref),sha256=hashlib.sha256(private_ref.read_bytes()).hexdigest()))
            for enabled in (False,True):
                session=NativeNetworkSession(**kwargs,city_focus_diagnostic=enabled,city_management_diagnostic=enabled)
                from civ6_host.runtime.native.native_official_bundle import DATABASE_PROFILE
                closure=dict(pins={},input_profile=family,official_bundle=kwargs['official_bundle'],
                    database_profile=DATABASE_PROFILE,initial_turn=1)
                session._configure_closure(closure)
                self.assertIs(closure.get('city_focus_diagnostic',False),enabled)
                self.assertIs(closure.get('city_management_diagnostic',False),enabled)
                city_path=str(resource_resolution.resolve_path(
                    retained_graph.LAB/profile.SOURCE[0]).resolve())
                self.assertEqual(city_path in closure['pins'],enabled)
                if enabled:self.assertEqual(closure['pins'][city_path],profile.SOURCE[1])
            for flags in (dict(city_focus_diagnostic=True,city_management_diagnostic=1),
                          dict(city_focus_diagnostic=False,city_management_diagnostic=True)):
                with self.assertRaises(ValueError):NativeNetworkSession(**kwargs,**flags)

    def test_shared_lua_focus_manage_and_actual_aux_callback_on_same_runtime(self):
        import ast
        sys.path.insert(0,str(HOST.parents[1]/'work/lua-test-deps'))
        from lupa.lua51 import LuaRuntime
        from types import SimpleNamespace as NS
        # Reuse only the retained pure Lua fixture literal. Its module imports
        # and its unrelated runner/learner tests are never executed.
        original=retained_graph.LAB/'tests/test_native_city_focus1000.py'
        tree=ast.parse(original.read_text(encoding='utf8'))
        harness=next(ast.literal_eval(n.value) for n in tree.body if isinstance(n,ast.Assign)
            and any(isinstance(target,ast.Name) and target.id=='HARNESS' for target in n.targets))
        for core in (XP1_CORE_SHA256,XP2_CORE_SHA256):
            for flags in ((False,False),(True,False),(False,True),(True,True)):
                lua=LuaRuntime(encoding=None);lua.execute(harness.encode());mode=lua.globals()[b'mode']
                mode[b'favored'][10],mode[b'ignored'][10]=flags
                action=dict(kind='city_focus',city_id=7,yield_type='YIELD_FOOD',yield_index=10,favored=flags[0],disfavored=flags[1])
                selected=focus.request_source(action,0,3,core_sha256=core)
                self.assertEqual(selected,focus.request_source(action,0,3))
                self.assertEqual(lua.execute(selected),b'submitted')
                expected=focus.transition(action)[0]
                self.assertEqual(tuple((mode[b'requests'][i][b'flags'],mode[b'requests'][i][b'data'])
                    for i in range(1,len(mode[b'requests'])+1)),expected)
            lua=LuaRuntime(encoding=None);lua.execute(harness.encode())
            lua.execute(b"""
CityCommandTypes={MANAGE=729125427,PARAM_MANAGE_CITIZEN=1041406338,PARAM_X=11,PARAM_Y=12}
CityCommandResults={PLOTS=21,CITIZENS=22,MAX_CITIZENS=23,LOCKED_CITIZENS=24}
Map={GetGridSize=function()return 3,2 end,GetPlotCount=function()return 6 end,
 GetPlotByIndex=function(i)return {GetIndex=function()return i end,GetX=function()return i%3 end,GetY=function()return math.floor(i/3) end}end}
result={[21]={0,1,2},[22]={0,1,2},[23]={0,1,2},[24]={0,1,0}}
CityManager.GetCommandTargets=function(c,command,params)
 assert(c==city and command==729125427 and params[1041406338]~=nil)
 return result
end
CityManager.RequestCommand=function(c,command,params)
 assert(c==city and command==729125427 and params[1041406338]~=nil)
 assert(params[11]==2 and params[12]==0);mode.requests[#mode.requests+1]=params
end
""")
            value=citizens.parse_catalog(lua.execute(citizens.catalog_source(0,7,3,core_sha256=core)),0,7,3)
            self.assertEqual([(r['workers'],r['capacity']) for r in value['plots']],[(None,None),(None,None),(2,2)])
            chosen=citizens.actions(value)[2]
            self.assertEqual(lua.execute(citizens.request_source(chosen,0,3,core_sha256=core)),b'submitted')
            self.assertEqual(len(lua.globals()[b'mode'][b'requests']),1)
            lua.execute(b'result[22][2]=nil')
            with self.assertRaises(Exception):lua.execute(citizens.catalog_source(0,7,3,core_sha256=core))
        # Same actual SavedLoadServices/NativeScriptRuntime/registered UI child;
        # only native ParameterMap memory and DLL install calls are fixture data.
        f=self.fixture()
        from civ6_host.runtime.native.native_aux_map_adapter import NativeAuxMapAdapter
        from civ6_host.runtime.native import native_aux_map_conversion as decoder
        from civ6_host.runtime.aux_map_profiles import profile_for_sha
        # Fixture-only map bytes on the existing graph; no private Python
        # module is imported or executed after the runtime import boundary.
        abi=profile_for_sha(XP2_CORE_SHA256);map_pointer=0x7e000000
        header=bytearray(84);struct.pack_into('<Q',header,0,f.backend.core._handle+abi.vtable_rva)
        struct.pack_into('<QQQ',header,48,map_pointer+48,0x7e001000,0x7e001000)
        struct.pack_into('<I',header,80,4);f.memory.put(map_pointer,header)
        for index,key in enumerate((21,22,23,24)):
            node=0x7e001000+index*0x100;vector=0x7e010000+index*0x1000
            raw=bytearray(64)
            struct.pack_into('<QQQ',raw,0,node+0x100 if index<3 else 0,0,node-0x100 if index else map_pointer+48)
            struct.pack_into('<I',raw,32,key);raw[40:64]=struct.pack('<H6xQII',11,vector,0,0x11000000)
            f.memory.put(node,raw);f.memory.put(vector+40,struct.pack('<QQ',vector+0x100,vector+0x148))
            f.memory.put(vector+0x100,b''.join(scalar(2,i if key!=24 else 0) for i in range(3)))
        # Reuse the already-authored HOST pure opcode oracle alone. Loading
        # its full historical decoder test module would violate the real
        # runtime's private-Python import boundary after config admission.
        oracle_tree=ast.parse((HOST/'tests/test_aux_map_profiles.py').read_text(encoding='utf8'))
        oracle=next(n for n in oracle_tree.body if isinstance(n,ast.FunctionDef) and n.name=='evaluate')
        namespace=dict(m=decoder,struct=struct)
        exec(compile(ast.Module(body=[oracle],type_ignores=[]),str(HOST/'tests/test_aux_map_profiles.py'),'exec'),namespace)
        evaluate=namespace['evaluate']
        def install(*args):return 1
        def version():return 2
        host=NS(LAB_AuxMapInstall=install,LAB_AuxMapTransportVersion=version)
        aux=NativeAuxMapAdapter(host,f.prefix.runtime,f.backend.core,C.addressof(f.host.aux_object),f.emit,
            read=f.read,core_sha256=XP2_CORE_SHA256,allow_nested_maps=True)
        aux.install();self.addCleanup(aux.close)
        pointer,count=C.c_void_p(),C.c_uint32()
        self.assertEqual(aux._snapshot_callback(C.addressof(f.host.aux_object),f.prefix.ui_child.pointer,
            map_pointer,0,C.pointer(pointer),C.pointer(count)),1)
        self.assertEqual(evaluate(C.string_at(pointer.value,count.value*16)),{21:{1:0,2:1,3:2},22:{1:0,2:1,3:2},23:{1:0,2:1,3:2},24:{1:0,2:0,3:0}})
        self.assertEqual(aux._snapshot_callback(C.addressof(f.host.aux_object),0xdeadbeef,
            map_pointer,0,C.pointer(pointer),C.pointer(count)),0)
        self.assertEqual((pointer.value,count.value),(None,0))

    def test_v12_combat_information_preserves_existing_public_contract(self):
        from test_capability_combat_readiness import CombatReadinessTests
        from civ6_host.contracts import information
        case=CombatReadinessTests();case.setUp();self.addCleanup(case.doCleanups)
        value=deepcopy(case.current);value.pop('decision_id');value['schema']=contract.CAPABILITY_CITY_CONTROLS_SCHEMA
        value.update(city_focus_catalogs=None,citizen_catalogs=None)
        value['families'].update({kind:dict(status='unqualified',reason='offline_unqueried_city_family')
            for kind in ('city_focus','city_citizen')})
        value['decision_id']=contract.digest(value)
        identity=__import__('types').SimpleNamespace(episode_id=value['episode_id'],game_generation=value['game_generation'])
        contract.validate_capability_catalogue(value,identity,value['sequence'],case.obs['turn'],
            player_id=case.obs['player_id'],observation=case.obs)
        self.assertEqual(information.project('combat',case.obs,value),information.project('combat',case.obs,case.current))

    def test_production_bound_os_reader_identity_and_city_snapshot_boundary(self):
        from types import SimpleNamespace as NS
        from civ6_host.runtime.native.native_checkpoint_provider import _Runtime
        f=self.fixture();self.query(f)
        self.assertEqual(adapter.catalogue_snapshot(f.saved),(f.token._expansion_city_controls_catalogue.focus,
            f.token._expansion_city_controls_catalogue.citizens))
        runtime=_Runtime.__new__(_Runtime);runtime.memory=NS(read=f.read)
        runtime.kernel=NS(GetCurrentThreadId=lambda:f.backend.thread[1])
        # This is a new fixture attachment, using the production reader class.
        del f.backend._expansion_city_controls_source;del f.arguments._expansion_city_controls_source
        f.backend.runtime=runtime;f.arguments.reader.read=runtime.read
        first=profile.bind_owner(f.saved);self.assertIs(profile.bind_owner(f.saved),first)
        other=_Runtime.__new__(_Runtime);other.memory=runtime.memory;other.kernel=runtime.kernel
        f.arguments.reader.read=other.read
        with self.assertRaises(ValueError):profile.bind_owner(f.saved)

    def test_existing_absent_event_shape_and_live_source_refusals(self):
        for case in ('extra_field','descriptor','reentrant','code'):
            with self.subTest(case=case):
                f=self.fixture();common,pos,_=f.fields()
                fields=common|{0xd6fcf3e4:scalar(2,1),0xa1fbc372:scalar(2,0),0x8c468e3c:pos}
                if case=='code':
                    p=profile.verify_source(XP2_CORE_SHA256)[2];body=next(iter(p['functions'].values()))
                    fragment=body['fragments'][0];rva=int(fragment['start_rva'],16) if 'start_rva' in fragment else int(fragment['start_va'],16)-0x180000000
                    raw=bytearray.fromhex(fragment['raw_hex']);raw[0]^=1
                    f.memory.put(f.backend.core._handle+rva,raw)
                    with self.assertRaises(ValueError):profile.verify_live(f.backend.core._handle,f.read,XP2_CORE_SHA256)
                    continue
                if case=='extra_field':fields[1]=scalar(2,0)
                elif case=='descriptor':fields[0x23739f42]=scalar(2,0)
                else:f.arguments.depth=1
                with f.saved._attempt():
                    f.backend.stage,f.backend.busy=ACTIVE,True
                    before=(tuple(f.deferred.pending),f.deferred._sequence,f.deferred.consumed_count)
                    with self.assertRaises((ValueError,RuntimeError)):f.dispatch(0x67001fe1,fields)
                    self.assertEqual(before,(tuple(f.deferred.pending),f.deferred._sequence,f.deferred.consumed_count))
                f.close()

if __name__=='__main__':unittest.main()

