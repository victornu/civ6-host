"""Source/Lua and real saved-owner composition; native boundaries are doubles."""
from copy import deepcopy
from contextlib import closing, contextmanager
from hashlib import sha256
from pathlib import Path
import sqlite3
import struct
import unittest
from unittest.mock import patch

from lupa.lua51 import LuaRuntime, LuaError
from civ6_host.runtime import xp1_great_person_activation as adapter
from civ6_host.runtime import xp1_great_person_activation_source as source
from civ6_host.runtime.execution_images import _XP1_PROFILE
from civ6_host.runtime.resource_resolution import resolve_path
from civ6_host.runtime.saved_load_services import SavedLoadServices
from civ6_host.runtime.xp1_action_transport import SavedActionTransport
from civ6_host.runtime.deferred_service import DeferredService
from test_xp1_prophet_activation import Fixture as ExistingFixture
from test_xp1_world_input_owner import Fixture as TransportFixture


ENV=br'''
local units={}
for _,v in ipairs(ROWS) do
 local row=v
 local gp={GetIndividual=function()return row[4] end,GetClass=function()return row[5] end,
           GetActionCharges=function()return row[6] end}
 local u={GetOwner=function()return OWNER end,GetID=function()return row[1] end,
          GetX=function()return row[2] end,GetY=function()return row[3] end,
          GetGreatPerson=function()return gp end,
          GetMovesRemaining=function()error('GP command invented a movement filter') end}
 units[#units+1]=u
end
local player={IsAlive=function()return true end,IsTurnActive=function()return true end,
 IsTurnActiveComplete=function()return true end,
 GetUnits=function()return {Members=function()return ipairs(units) end} end}
local Players={[0]=player}
local Game={GetLocalPlayer=function()return 0 end,GetLocalObserver=function()return 0 end,
 GetCurrentGameTurn=function()return 8 end,IsAllowStrategicCommands=function(p)return p==0 end}
local GameInfo={UnitCommands={UNITCOMMAND_ACTIVATE_GREAT_PERSON={Hash=COMMAND_HASH,VisibleInUI=true}},
 GreatPersonIndividuals=setmetatable({},{__index=function()return {} end}),
 GreatPersonClasses=setmetatable({},{__index=function()return {} end})}
-- UnitCommandTypes has TYPE in the installed XP1 image without a GP activation alias.
local UnitCommandTypes={TYPE=-1572680103}
local InterfaceModeTypes={NONE=0};local DB={MakeHash=function()return 0 end}
local UnitManager={CanStartCommand=function(u,hash,visible,legal)
 assert(hash==374670040 and type(visible)=='boolean' and
        ((visible and legal==nil) or (not visible and legal==true)),'command ABI changed')
 return host_can_start(u:GetID(),visible) end,
 RequestCommand=function(u,hash,...)
 assert(hash==374670040 and select('#',...)==0,'GP command acquired parameters')
 host_request(u:GetID(),hash) end}
'''


class Fixture(ExistingFixture):
    def __init__(self):
        super().__init__()
        self.saved.xp1_great_person_activation=True
        self.command_hash=source.COMMAND_HASH
        self.gp={17:dict(x=0,y=0,individual_index=56,class_index=2,charges=2,visible=True,available=True),
                 18:dict(x=1,y=0,individual_index=81,class_index=4,charges=1,visible=False,available=False),
                 19:dict(x=2,y=0,individual_index=90,class_index=3,charges=0,visible=True,available=True)}
        self.choice=dict(kind='activate_great_person',unit_id=17,x=0,y=0)
        self.effect_mode='survive';self.emit_marker=True;self.marker_hash=source.COMMAND_HASH
        self.hide_on_request=False
        self.marker_owner=0;self.marker_unit=None;self.foreign_owner=0;self.break_archive=False
        self.work_owner=0;self.work_unit=None;self.work_position=(3,0);self.work_after_marker=False
        self.work_city_id=65536
        self.observation['cities']=[dict(id=65536,owner=0,x=3,y=0)]
        @contextmanager
        def plot(core,context,fields,**kwargs):
            if core is not self.backend.core:raise AssertionError('Foreign Great Work owner')
            yield dict(owner=0,city_id=self.work_city_id,district_id=0)
        self.stack.enter_context(patch('civ6_host.runtime.native.native_event_07c83dae.plot_snapshot',plot))
        self.update_observation()
        self.token.observation=deepcopy(self.observation)
        self.stack.enter_context(patch.object(adapter,'observe_player',self.observe_native))

    def update_observation(self):
        self.observation['units']=[dict(id=uid,owner=0,x=row['x'],y=row['y']) for uid,row in sorted(self.gp.items())]

    def evaluate(self,child,code,name,**kwargs):
        if name not in (b'@explicit_xp1_gp_activation_catalogue',b'@explicit_xp1_gp_activation_request'):
            return super().evaluate(child,code,name,**kwargs)
        if child is not self.token.ui_child:raise AssertionError('Foreign Lua owner')
        self.evaluations.append(name)
        rows=b'{'+b','.join(b'{'+','.join(str(v) for v in (uid,row['x'],row['y'],row['individual_index'],row['class_index'],row['charges'])).encode()+b'}'
                           for uid,row in sorted(self.gp.items()))+b'}'
        env=ENV.replace(b'ROWS',rows).replace(b'OWNER',str(self.foreign_owner).encode())
        env=env.replace(b'COMMAND_HASH',str(self.command_hash).encode('ascii'))
        lua=LuaRuntime(encoding=None)
        def legal(uid,visible):
            self.machine.append(('can_start',name,uid,visible))
            if self.hide_on_request and visible and name==b'@explicit_xp1_gp_activation_request':return False
            return self.gp[uid]['visible' if visible else 'available'] and not (
                self.deny_request and name==b'@explicit_xp1_gp_activation_request' and not visible)
        def request(uid,command):
            self.machine.append(('request',uid,command));self.requested_uid=uid
            self.token.transport.pending.append(struct.pack('<IHHIII',source.ARCHIVE_KIND,0,1,uid,7,
                                                            1 if self.break_archive else 0))
        lua.globals()[b'host_can_start']=legal;lua.globals()[b'host_request']=request
        return lua.execute(env+code)

    def virtual(self,core,pointer,slot,rva,result,*args):
        if rva!=self.token.transport.transport_abi.drain_rva:
            return TransportFixture.virtual(self,core,pointer,slot,rva,result,*args)
        def drain(ctx):
            self.machine.append(('drain',))
            self.memory.put(self.sentinel,struct.pack('<QQ',self.sentinel,self.sentinel))
            row=self.gp[self.requested_uid]
            if self.effect_mode=='consume':del self.gp[self.requested_uid]
            elif self.effect_mode=='survive':row['charges']-=1
            elif self.effect_mode not in ('unchanged','work'):raise AssertionError('Unknown fixture effect')
            self.update_observation()
            if self.effect_mode=='work' and not self.work_after_marker:self.create_work()
            if self.emit_marker:
                uid=self.requested_uid if self.marker_unit is None else self.marker_unit
                address=0x78002000
                self.memory.put(address,struct.pack('<HHI',self.marker_owner,1,uid))
                fields={0xa1e5a149:struct.pack('<H6xI12x',3,self.marker_hash),
                        0xf0548bb7:struct.pack('<H6xQII',1024,address,8,0x21000001)}
                self.owner.dispatch(0xfc7db95e,fields,0)
            if self.effect_mode=='work' and self.work_after_marker:self.create_work()
        return drain


    def create_work(self):
        position,descriptor=0x78003000,0x78003010
        self.memory.put(position,struct.pack('<ii',*self.work_position))
        uid=self.requested_uid if self.work_unit is None else self.work_unit
        self.memory.put(descriptor,struct.pack('<HHI',self.work_owner,1,uid))
        scalar=lambda value:struct.pack('<H6xI12x',2,value)
        fields={0x8c468e3c:struct.pack('<H6xQII',0,position,8,0x21000001),
                0xa1e5a149:struct.pack('<H6xI12x',3,0),0xa1fbc372:scalar(7),0xd6fcf3e4:scalar(11),
                0xf0548bb7:struct.pack('<H6xQII',1024,descriptor,8,0x21000001)}
        self.owner.dispatch(0x1a71e9f0,fields,0)


class GPActivationTests(unittest.TestCase):
    def fixture(self):
        f=Fixture();self.addCleanup(f.close);return f


    def test_real_unit_command_definition_does_not_require_a_lua_enum_alias(self):
        db = source.verify_source()['observed_database']
        path = resolve_path(Path(db['path']))
        self.assertEqual(sha256(path.read_bytes()).hexdigest(), db['sha256'])
        with closing(sqlite3.connect(path.as_uri() + '?mode=ro&immutable=1', uri=True)) as conn:
            rows = conn.execute(
                'SELECT t.Hash,u.VisibleInUI,u.InterfaceMode,t.Kind FROM UnitCommands AS u '
                'JOIN Types AS t ON t.Type=u.CommandType WHERE u.CommandType=?',
                ('UNITCOMMAND_ACTIVATE_GREAT_PERSON',),
            ).fetchall()
        self.assertEqual(len(rows), 1)
        command_hash, visible, mode, kind = rows[0]
        self.assertEqual((visible, mode, kind), (1, None, 'KIND_UNITCOMMAND'))

        f = self.fixture()
        f.command_hash = command_hash
        self.assertEqual(adapter.catalogue(f.saved, f.token.observation)['operation'], command_hash)
        f.set_active(True)
        result = adapter.apply(f.saved, f.choice, f.token.observation)
        self.assertEqual(result['status'], 'completed')
        self.assertIn(('request', f.choice['unit_id'], command_hash), f.machine)

        bad = self.fixture()
        bad.command_hash = command_hash + 1
        with self.assertRaisesRegex(LuaError, 'GP command hash differs'):
            adapter.catalogue(bad.saved, bad.token.observation)
        self.assertEqual(bad.machine, [])

    def test_source_dependencies_live_complete_spans_tables_and_wrong_image(self):
        proof=source.require_actions()
        self.assertEqual(len(proof['code_spans']),30)
        pins=source.source_dependencies(_XP1_PROFILE)
        from civ6_host.runtime import xp1_great_work_source as works
        self.assertIn(works.UNIT_PRODUCER_SOURCE[1],pins.values())
        self.assertIn(source.EFFECT_SOURCE[1],pins.values())
        self.assertIn(source.COMPLETION_SOURCE[1],pins.values())
        with self.assertRaises(ValueError):source.source_dependencies(None)
        f=self.fixture()
        value=source.verify_live(f.memory.base,f.read,image=_XP1_PROFILE)
        self.assertGreaterEqual(value['complete_spans'],31)
        for key in ('apply','legality','UI_GreatPerson_table','post_command_notification'):
            row=proof['code_spans'][key]['fragments'][0]
            address=f.memory.base+int(row['rva'],16);raw=f.read(address,row['length'])
            f.memory.put(address,bytes([raw[0]^1])+raw[1:])
            with self.subTest(body=key),self.assertRaisesRegex(ValueError,'Live Great Person'):
                source.verify_live(f.memory.base,f.read,image=_XP1_PROFILE)
            f.memory.put(address,raw)
        row=proof['callable_vtables']['activation_command'];address=f.memory.base+int(row['rva'],16)
        raw=f.read(address,row['length']);f.memory.put(address,bytes([raw[0]^1])+raw[1:])
        with self.assertRaisesRegex(ValueError,'vtable'):
            source.verify_live(f.memory.base,f.read,image=_XP1_PROFILE)

    def test_actual_lua_catalogue_flags_full_signed_charges_and_clone(self):
        f=self.fixture()
        f.gp[17]['charges']=-2147483648
        value=adapter.catalogue(f.saved,f.token.observation)
        self.assertEqual(value['operation'],source.COMMAND_HASH)
        self.assertEqual([r['unit_id'] for r in value['units']],[17,18,19])
        self.assertEqual(value['units'][0]['charges'],-2147483648)
        self.assertFalse(value['units'][1]['visible'])
        self.assertEqual(adapter.actions(value),[f.choice,dict(f.choice,unit_id=19,x=2)])
        value['units'].clear();self.assertEqual(len(f.saved.explicit_great_person_activation['units']),3)
        f.gp[17].update(visible=False,available=True)
        value=adapter.catalogue(f.saved,f.token.observation)
        self.assertTrue(value['units'][0]['available']);self.assertNotIn(f.choice,adapter.actions(value))
        f.gp.clear();f.update_observation();f.token.observation=deepcopy(f.observation)
        self.assertEqual(adapter.catalogue(f.saved,f.token.observation)['units'],[])

    def test_real_owners_empty_command_archive_fifo_and_both_presence_results(self):
        for mode,uid in (('survive',17),('consume',17),('unchanged',19),('work',19)):
            with self.subTest(mode=mode,uid=uid):
                f=self.fixture();f.effect_mode=mode
                action=dict(f.choice,unit_id=uid,x=f.gp[uid]['x'])
                initial=adapter.catalogue(f.saved,f.token.observation)
                self.assertIs(type(f.saved.prefix),SavedLoadServices)
                self.assertIs(type(f.token.transport),SavedActionTransport);self.assertIs(type(f.deferred),DeferredService)
                f.set_active(True)
                result=adapter.apply(f.saved,action,f.token.observation)
                self.assertEqual(result['status'],'submitted' if mode=='unchanged' else 'completed')
                self.assertEqual(result['reason'],adapter.UNCONFIRMED if mode=='unchanged' else None)
                self.assertIs(result['receipt']['effect_confirmed'],mode!='unchanged')
                self.assertEqual(result['unit_consumed'],mode=='consume')
                self.assertEqual(result['charges_after'],None if mode=='consume' else 1 if mode=='survive' else 0)
                self.assertTrue(result['receipt']['native_command_processed'])
                self.assertEqual(result['receipt']['parameters'],{})
                self.assertEqual(result['receipt']['normalized_command_index'],7)
                self.assertEqual(result['source_sha256'],source.SOURCE[1])
                self.assertEqual(f.deferred.consumed_count,2 if mode=='work' else 1)
                self.assertEqual(f.deferred.pending,[]);self.assertEqual(f.token.transport.pending,[])
                self.assertEqual(f.token.publication_count,1)
                self.assertEqual(len([r for r in f.machine if r[0]=='request']),1)
                f.close()

    def test_only_new_matching_work_before_exact_marker_confirms_unchanged_unit(self):
        for mode in ('owner','unit','position','city','after_marker'):
            with self.subTest(mode=mode):
                f=self.fixture();f.effect_mode='work';f.choice.update(unit_id=19,x=2)
                if mode=='owner':f.work_owner=1
                elif mode=='unit':f.work_unit=18
                elif mode=='position':f.work_position=(2,0)
                elif mode=='city':f.work_city_id=65537
                else:f.work_after_marker=True
                adapter.catalogue(f.saved,f.token.observation);f.set_active(True)
                result=adapter.apply(f.saved,f.choice,f.token.observation)
                self.assertEqual((result['status'],result['reason']),('submitted',adapter.UNCONFIRMED))
                self.assertEqual(result['receipt']['great_work_records'],[])
                self.assertEqual((f.deferred.pending,f.token.transport.pending),([],[]))
                self.assertEqual(f.deferred.consumed_count,2);f.close()

    def test_work_receipt_cannot_attribute_the_legacy_sentinel_to_a_unit(self):
        from civ6_host.runtime.native import native_event_great_work as codec
        cities=[dict(id=65536,owner=0,x=2,y=0)]
        for uid in (0,19,0xfffffffe,0xffffffff):
            raw=codec.encode_record(2,dict(position_bytes=struct.pack('<ii',2,0),x=2,y=0,
                selector=0,source_value=7,descriptor_tail=11),struct.pack('<HHI',0,1,uid),
                dict(owner=0,city_id=65536,district_id=0))
            self.assertIs(adapter._work_record(raw,0,uid,cities,1,3),uid!=0xffffffff)
            self.assertFalse(adapter._work_record(raw,0,uid,cities,2,3))
            self.assertFalse(adapter._work_record(raw,0,uid,cities,0,2))

    def test_native_refusal_before_request_or_final_recheck_has_no_archive(self):
        for mode in ('fresh','request'):
            f=self.fixture();adapter.catalogue(f.saved,f.token.observation)
            if mode=='fresh':f.gp[17]['available']=False
            else:f.deny_request=True
            f.set_active(True);result=adapter.apply(f.saved,f.choice,f.token.observation)
            self.assertEqual(result['status'],'refused');self.assertEqual(result['refusal_code'],adapter.REFUSED)
            self.assertEqual(result['request'],dict(can_start=False,request_invoked=False))
            self.assertEqual(result['observation'],f.token.observation)
            self.assertFalse(any(r[0]=='request' for r in f.machine))
            self.assertEqual(f.token.transport.pending,[]);self.assertEqual(f.deferred.pending,[])
            self.assertEqual(f.token.publication_count,0);f.close()

    def test_wrong_owner_stale_position_identity_and_action_refuse_before_request(self):
        for mode in ('disabled','owner','image','position','individual','charges','visibility','request_visibility','turn','action'):
            f=self.fixture();adapter.catalogue(f.saved,f.token.observation);action=deepcopy(f.choice)
            f.set_active(True)
            if mode=='disabled':f.saved.xp1_great_person_activation=False
            elif mode=='owner':f.saved._backend=object()
            elif mode=='image':f.backend.core._civ6_host_execution_image=None
            elif mode=='position':f.gp[17]['x']=3
            elif mode=='individual':f.gp[17]['individual_index']=200
            elif mode=='charges':f.gp[17]['charges']=99
            elif mode=='visibility':f.gp[17]['visible']=False
            elif mode=='request_visibility':f.hide_on_request=True
            elif mode=='turn':f.saved.explicit_great_person_activation['current_game_turn']=9
            else:action['unit_id']=True
            with self.subTest(mode=mode),self.assertRaises((ValueError,RuntimeError,LuaError)):
                adapter.apply(f.saved,action,f.token.observation)
            self.assertFalse(any(r[0]=='request' for r in f.machine));f.close()

    def test_archive_corruption_and_missing_or_foreign_postmarker_never_complete(self):
        for mode in ('archive','no_marker','wrong_hash','wrong_owner','wrong_unit'):
            f=self.fixture();adapter.catalogue(f.saved,f.token.observation)
            if mode=='archive':f.break_archive=True
            elif mode=='no_marker':f.emit_marker=False
            elif mode=='wrong_hash':f.marker_hash=source.COMMAND_HASH+1
            elif mode=='wrong_owner':f.marker_owner=1
            else:f.marker_unit=18
            f.set_active(True)
            with self.subTest(mode=mode),self.assertRaises(RuntimeError):
                adapter.apply(f.saved,f.choice,f.token.observation)
            self.assertEqual(f.token.publication_count,0);f.close()


if __name__=='__main__':unittest.main()
