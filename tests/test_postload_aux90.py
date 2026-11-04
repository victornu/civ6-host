"""Transport/binding unit tests only; native HKS qualification remains required."""
import ctypes as C
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from civ6_host.runtime.native.native_host import DiagnosticHost
from civ6_host.runtime.native.native_script_runtime import NativeScriptRuntime
from civ6_host.runtime.script_event_service import ScriptEventService
from civ6_host.runtime import postload160_source as source


class Host:
    _bind=DiagnosticHost._bind
    _unsupported=DiagnosticHost._unsupported

    def __init__(self):
        self.aux_vtable=(C.c_void_p*32)()
        self.aux_object=(C.c_void_p*2)(C.addressof(self.aux_vtable),1)
        self.pointer=0x90000
        self.functions=[];self.emit=Mock()
        for slot in (*ScriptEventService.SLOTS,0x90):
            self._bind(self.aux_vtable,slot,None,[C.c_void_p],self._unsupported('auxiliary',slot))

    def _fatal(self,*args,**kwargs):
        raise AssertionError((args,kwargs))


class Aux90TransportTests(unittest.TestCase):
    def runtime(self,outcome=4,status=0,stacks=(0,0)):
        runtime=NativeScriptRuntime.__new__(NativeScriptRuntime)
        runtime.root=0x10000
        def native(root,category,name,arguments,output):
            output._obj.value=outcome
            return status
        runtime.host=SimpleNamespace(LAB_Aux90DispatchCategoryNull=Mock(side_effect=native))
        runtime.lua={'gettop':Mock(side_effect=stacks)}
        runtime._status=Mock()
        return runtime

    def test_observed_absence_and_call_are_distinct_with_exact_null_signature(self):
        for number,label in ((1,'category_nil'),(2,'event_nil'),(3,'call_nil'),(4,'call_returned')):
            with self.subTest(outcome=label):
                runtime=self.runtime(number)
                self.assertEqual(runtime.dispatch_aux_event_category_null(b'AutoPlayStart',category=2),label)
                dispatch=runtime.host.LAB_Aux90DispatchCategoryNull
                args=dispatch.call_args.args
                self.assertEqual(args[:4],(0x10000,2,b'AutoPlayStart',None))
                self.assertEqual(dispatch.argtypes,[C.c_void_p,C.c_uint32,C.c_char_p,C.c_void_p,C.POINTER(C.c_uint32)])
                self.assertIs(dispatch.restype,C.c_int)

    def test_unknown_category_nonnull_arguments_and_bad_names_fail_before_native(self):
        for name,options in ((b'AutoPlayStart',dict(category=3)),(b'AutoPlayStart',dict(category=True)),
                (b'AutoPlayStart',dict(category=2,arguments=0x10000)),
                (b'Auto\0Play',dict(category=2)),(b'\xff',dict(category=2)),(b'x'*256,dict(category=2))):
            runtime=self.runtime()
            with self.subTest(name=name,options=options),self.assertRaises(ValueError):
                runtime.dispatch_aux_event_category_null(name,**options)
            runtime.host.LAB_Aux90DispatchCategoryNull.assert_not_called()

    def test_missing_export_unknown_outcome_and_nonempty_stack_refuse(self):
        runtime=self.runtime();runtime.host=SimpleNamespace()
        with self.assertRaisesRegex(ValueError,'export is unavailable'):
            runtime.dispatch_aux_event_category_null(b'AutoPlayStart',category=2)
        runtime=self.runtime(0)
        with self.assertRaisesRegex(RuntimeError,'unknown outcome'):
            runtime.dispatch_aux_event_category_null(b'AutoPlayStart',category=2)
        for stacks in ((1,),(0,1)):
            runtime=self.runtime(stacks=stacks)
            with self.assertRaisesRegex(RuntimeError,'stack'):
                runtime.dispatch_aux_event_category_null(b'AutoPlayStart',category=2)

    def test_hks_error_is_not_changed_to_success_or_absence(self):
        runtime=self.runtime(0,status=-7)
        runtime._status.side_effect=RuntimeError('protected HKS failure')
        with self.assertRaisesRegex(RuntimeError,'protected HKS failure'):
            runtime.dispatch_aux_event_category_null(b'AutoPlayStart',category=2)


class Aux90OwnerTests(unittest.TestCase):
    def fixture(self,name=b'AutoPlayStart'):
        host=Host();base=0x200000000;address=0xA0000
        executable=SimpleNamespace(LAB_Aux90DispatchCategoryNull=Mock())
        runtime=SimpleNamespace(host=executable,service_owner=host,registry=SimpleNamespace(_check=Mock()),
            dispatch_aux_event_category_null=Mock(return_value='category_nil'),
            dispatch_game_event_result=Mock(return_value=(True,0)))
        original=dict(host._slot_bindings);functions=tuple(host.functions)
        service=ScriptEventService(host,runtime)
        def read(ptr,size):
            if (ptr,size)==(base+0x9F2640,8):return host.pointer.to_bytes(8,'little')
            if (ptr,size)==(base+0x9F2648,8):return C.addressof(host.aux_object).to_bytes(8,'little')
            if size==1 and address<=ptr<=address+len(name):return (name+b'\0')[ptr-address:ptr-address+1]
            raise AssertionError('Unexpected synthetic read')
        with patch.object(source,'xp1_source',return_value={}),patch.object(source,'verify_xp1_live'):
            service.install_postload_aux90_null(SimpleNamespace(_handle=base),
                core_sha256=source.XP1_CORE_SHA256,read=read)
        return host,runtime,service,address,original,functions

    def test_actual_null_category_outcome_returns_al1_without_creating_listeners(self):
        for name in (b'AutoPlayStart',b'AutoPlayEnd'):
            h,r,s,p,original,functions=self.fixture(name)
            self.assertIsNot(r.host,h)
            self.assertIs(r.service_owner,h)
            self.assertIs(s.dispatch_postload_aux90_null(C.addressof(h.aux_object),1,p,None),True)
            r.dispatch_aux_event_category_null.assert_called_once_with(name,category=2)
            self.assertEqual(s.dispatch_depth,0)
            self.assertFalse(s.aux90_poisoned)
            s.close()
            self.assertEqual(h._slot_bindings,original)
            self.assertEqual(tuple(h.functions),functions)

    def test_unknown_kind_name_or_nonnull_argument_poison_and_do_not_dispatch(self):
        for kind,name,arg in ((0,b'AutoPlayStart',None),(2,b'AutoPlayStart',None),
                              (True,b'AutoPlayStart',None),(1,b'Unknown',None),
                              (1,b'AutoPlayStart',0x10000)):
            h,r,s,p,_,_=self.fixture(name)
            with self.subTest(kind=kind,name=name,arg=arg),self.assertRaises(ValueError):
                s.dispatch_postload_aux90_null(C.addressof(h.aux_object),kind,p,arg)
            r.dispatch_aux_event_category_null.assert_not_called()
            self.assertTrue(s.aux90_poisoned)
            with self.assertRaises(ValueError):s.close()

    def test_foreign_receiver_and_reentry_refuse_before_dispatch(self):
        h,r,s,p,_,_=self.fixture()
        with self.assertRaisesRegex(ValueError,'Foreign'):
            s.dispatch_postload_aux90_null(0x10000,1,p,None)
        s.dispatch_depth=1
        with self.assertRaisesRegex(RuntimeError,'reentered'):
            s.dispatch_postload_aux90_null(C.addressof(h.aux_object),1,p,None)
        r.dispatch_aux_event_category_null.assert_not_called()

    def test_changed_slot_owner_prevents_release(self):
        h,r,s,_,_,_=self.fixture()
        h.aux_vtable[0x90//8]=1
        with self.assertRaisesRegex(ValueError,'ownership changed'):s.close()

    def test_foreign_service_owner_refuses_before_source_checks_and_binding(self):
        host=Host()
        executable=SimpleNamespace(LAB_Aux90DispatchCategoryNull=Mock())
        runtime=SimpleNamespace(host=executable,service_owner=object(),
            registry=SimpleNamespace(_check=Mock()),dispatch_game_event_result=Mock())
        service=ScriptEventService(host,runtime)
        previous=dict(host._slot_bindings)
        with patch.object(source,'xp1_source') as proof,patch.object(source,'verify_xp1_live') as live:
            with self.assertRaisesRegex(ValueError,'another service owner'):
                service.install_postload_aux90_null(SimpleNamespace(_handle=0x200000000),
                    core_sha256=source.XP1_CORE_SHA256,read=Mock())
            proof.assert_not_called();live.assert_not_called()
        self.assertIsNot(runtime.host,host)
        self.assertEqual(host._slot_bindings,previous)


if __name__=='__main__':
    unittest.main()
