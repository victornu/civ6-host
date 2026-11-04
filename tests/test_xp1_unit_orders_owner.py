"""Actual owner/continuation/transport/A0/FIFO, with native memory/calls fixtures."""
from copy import deepcopy
import ctypes as C
import struct
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch
from test_xp1_world_input_owner import Fixture as WorldFixture
from test_xp1_unit_orders import LuaRuntime,LUA_SETUP
from civ6_host.runtime import xp1_unit_orders as adapter,xp1_unit_orders_profile as profile
from civ6_host.runtime.native import native_saved_unit_orders as shared


class Fixture(WorldFixture):
    def __init__(self):
        super().__init__()
        self.deferred.cache_core_sha256 = profile.XP1_CORE_SHA256
        self.lua=LuaRuntime(max_memory=4*1024*1024);self.lua.execute(LUA_SETUP)
        self.lua.globals().request_python=self.request
        self.order=None
        self.stack.enter_context(patch.object(shared,'observe_player',self.observe_native))
        # Real application storage guard and real capability metadata scope.
        from civ6_host.runtime.native import native_application_configuration as configuration
        from civ6_host.runtime.configuration_profiles import configuration_abi
        from civ6_host.runtime import xp1_load_capability as cap
        app=configuration.NativeApplicationConfiguration.__new__(configuration.NativeApplicationConfiguration)
        app.base=self.memory.base;app.context=self.backend.context;app.closed=False
        app.storage=C.create_string_buffer(len(configuration._GUARD)*2+configuration.STORAGE_SIZE)
        start=C.addressof(app.storage)
        C.memmove(start,configuration._GUARD,16)
        C.memmove(start+16+configuration.STORAGE_SIZE,configuration._GUARD,16)
        app._configuration_abi=configuration_abi(profile.XP1_CORE_SHA256)
        b=self.backend;b.owner=app;self.host.application_configuration=app
        b.core._civ6rl_application_configuration=app;self.token.lease.configuration_owner=app
        b.profile=NS(core_sha256=profile.XP1_CORE_SHA256)
        if b.captured_bundle.reference!=cap.REFERENCE:
            raise AssertionError('Order fixture changed its captured bundle')
        cap._bind_source_receipt(b)
        from civ6_host.runtime.unit_operation_ui_profile import verify_live
        self.token.unit_source=verify_live(b.core._handle,self.read,core_sha256=profile.XP1_CORE_SHA256)

    def evaluate(self,child,source,name,**kwargs):
        if name in (b'@explicit_unit_orders',b'@explicit_unit_order_request'):
            if child is not self.token.ui_child:raise AssertionError('Wrong order Lua child')
            return self.lua.execute(source.decode()).encode()
        return super().evaluate(child,source,name,**kwargs)

    def request(self,route,hash):
        self.order=(route,hash);self.token.transport.pending.append(self.payload)
        self.emit('native_command_archive_queued',archive_hex=self.payload.hex(),bytes=len(self.payload),delivery_pending=True)

    def virtual(self,core,pointer,slot,rva,result,*args):
        a=self.token.transport.transport_abi
        if rva==a.drain_rva:
            if core is not self.backend.core:raise AssertionError('Foreign Core')
            def drain(ctx):
                self.machine.append(('drain',));self.memory.put(self.sentinel,struct.pack('<QQ',self.sentinel,self.sentinel))
                descriptor=self.make_blob(struct.pack('<HHI',0,1,17),1024)
                from test_xp1_turn_a0 import scalar
                # Both pure producer branches absent from the earlier world
                # fixture execute on this actual A0 owner and consumed FIFO.
                if self.order[0]=='command':
                    fields={0xa1e5a149:scalar(3,0),0xf0548bb7:descriptor}
                    self.owner.dispatch(0xfc7db95e,fields,0)
                else:
                    from civ6_host.runtime.native import native_event_3d4006f2 as event
                    pointer=0x78002000;self.memory.put(pointer,struct.pack('<HHI',0,1,17))
                    self.owner.dispatch(0x3d4006f2,event.encode_fields(event.EventFields(0,0,pointer,False)),0)
                if self.order==('command',2):self.goal=None
                elif self.order==('command',1):self.lua.globals().activity=0
                else:self.lua.globals().activity=self.order[1]
            return drain
        return super().virtual(core,pointer,slot,rva,result,*args)

    def execute_order(self,item):
        self.saved._running=True;self.set_active(False)
        offers=adapter.read(self.saved,self.token.observation)
        action=next(a for a in offers['actions'] if a['item_type']==item)
        self.saved._running=False
        return self.saved.execute(action)


class UnitOrderOwnerTests(unittest.TestCase):
    def fixture(self):
        f=Fixture();self.addCleanup(f.close);return f

    def test_actual_saved_execute_all_six_orders_publish_and_invalidate_cache(self):
        f=self.fixture()
        names=('UNITOPERATION_SLEEP','UNITOPERATION_FORTIFY','UNITOPERATION_HEAL','UNITOPERATION_RELIGIOUS_HEAL',
               'UNITCOMMAND_WAKE','UNITCOMMAND_CANCEL')
        for index,item in enumerate(names,1):
            with self.subTest(item=item):
                if item=='UNITCOMMAND_CANCEL':f.goal=10;f.lua.globals().moves=0
                before=deepcopy(f.token.observation)
                result=f.execute_order(item);effect=result['effect'];receipt=effect['receipt']
                self.assertEqual(effect['status'],'completed');self.assertIsNone(effect['refusal_code'])
                self.assertEqual(result['observation_after'],effect['observation'])
                self.assertEqual(receipt['observation_before'],before)
                self.assertEqual(receipt['source_proof_sha256'],profile.SOURCE[1])
                self.assertTrue(receipt['native_archive_delivered'])
                self.assertEqual(f.token.publication_count,index);self.assertEqual(f.token.sequence,index)
                self.assertEqual(f.deferred.consumed_count,index);self.assertEqual(f.deferred.pending,[])
                self.assertFalse(f.saved._running);self.assertFalse(f.backend.busy)
                self.assertIsNone(f.token._xp1_unit_orders_catalogue);self.assertIsNone(f.token.explicit_unit_orders)
                if item=='UNITCOMMAND_CANCEL':
                    self.assertIsNone(f.goal);self.assertFalse(receipt['state_changed'])
                    self.assertEqual(receipt['cancel_source_proof_sha256'],profile.SOURCE[1])
        self.assertEqual(len([r for r in f.machine if r[0]=='publish']),6)

    def test_stale_catalogue_and_foreign_session_fail_before_native(self):
        for change in ('sequence','owner','catalogue','action'):
            with self.subTest(change=change):
                f=self.fixture();rows=adapter.read(f.saved,f.token.observation);f.set_active(True)
                action=deepcopy(rows['actions'][0])
                if change=='sequence':f.token.sequence+=1
                elif change=='owner':f.saved._backend=object()
                elif change=='catalogue':f.token.explicit_unit_orders['units'][0]['activity_type']=77
                else:action['unit_id']=True
                with self.assertRaises((ValueError,RuntimeError)):adapter.apply(f.saved,action,f.token.observation)
                self.assertEqual(f.machine,[]);self.assertEqual(f.token.transport.pending,[])
                f.close()

    def test_real_a0_refuses_unknown_listener_on_command_codec(self):
        f=self.fixture();rows=adapter.read(f.saved,f.token.observation)
        action=next(a for a in rows['actions'] if a['item_type']=='UNITCOMMAND_WAKE')
        f.owner.entity_listener_count=1;f.set_active(True)
        with self.assertRaisesRegex(RuntimeError,'receiver or registration profile changed'):
            adapter.apply(f.saved,action,f.token.observation)
        self.assertIsNone(f.token._xp1_unit_orders_catalogue)
        self.assertEqual(f.token.publication_count,0)


if __name__=='__main__':unittest.main()
