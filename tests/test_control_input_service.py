"""Control-input lifecycle and shared state; no full native game is launched."""
import ast
import ctypes as C
import struct
import sys
from pathlib import Path
from types import SimpleNamespace as NS,ModuleType
import unittest
from unittest.mock import Mock,patch

from civ6_host.runtime.control_input_service import ControlInputService
from civ6_host.runtime.configuration_profiles import XP1_CORE_SHA256
from civ6_host.runtime.native.native_host import DiagnosticHost
from civ6_host.runtime.native.native_host_events import HostControllerQuery,NativeDeferredHostEvents
from civ6_host.runtime.paths import resource_root
from test_deferred_service import Host as QueueHost


class Flag:
    def __init__(self):self.value=0;self.closed=False
    def get_flag(self):return self.value
    def set_flag(self,value):self.value=value
    def snapshot(self):return {'flag':self.value,'constructor_executed':True}
    def close(self):self.closed=True


class Code:
    def __init__(self):self.creates=0;self.closed=False;self.flag=None
    def _check(self):
        if self.closed:raise RuntimeError('closed code')
    def create(self):self.creates+=1;self.flag=Flag();return self.flag
    def close(self):
        if self.flag and not self.flag.closed:raise RuntimeError('live flag')
        self.closed=True


class Host(QueueHost):
    configure_local_player_id=DiagnosticHost.configure_local_player_id


class ControlInputServiceTests(unittest.TestCase):
    def fixture(self,player_id=7):
        h=Host();core=NS(_handle=1000);before=list(h.vtable);bindings=dict(h._slot_bindings)
        d=NS(host=h,core=core,context=2000,_check=Mock(),pending=[],_draining_empty_receivers=False,
             host_notification_counter=0,host_metadata_counter=0)
        for target,value in (
            ('civ6_host.runtime.control_input_source.verify_xp1',Mock(return_value={})),
            ('civ6_host.runtime.control_input_service.NativeControllerCode',Code),
            ('civ6_host.runtime.native.native_controller_state.NativeControllerCode',Code)):
            m=patch(target,value);m.start();self.addCleanup(m.stop)
        s=ControlInputService(h,core,2000,d,core_sha256=XP1_CORE_SHA256,
            local_player_id=player_id,read=Mock(),emit=Mock())
        return h,d,s,before,bindings

    def test_explicit_identity_lazy_original_state_and_no_implicit_reset(self):
        h,d,s,before,bindings=self.fixture()
        local=C.WINFUNCTYPE(C.c_uint32,C.c_void_p)(h.vtable[0xD0//8])
        self.assertEqual(local(h.pointer),7)
        self.assertEqual(s.code.creates,0)
        self.assertIs(s.turn_begin_state,d.turn_begin_state)
        self.assertEqual(s.controller_flag(h.pointer),0);self.assertEqual(s.code.creates,1)
        # Later event consumers access this exact state, not a second flag.
        d.turn_begin_state.controller_byte_0d=0xA5
        self.assertEqual(s.controller_flag(h.pointer),0xA5);self.assertEqual(s.code.creates,1)
        s.close();s.close()
        self.assertTrue(s.code.closed);self.assertTrue(s.code.flag.closed)
        self.assertEqual(list(h.vtable),before);self.assertEqual(h._slot_bindings,bindings)
        self.assertFalse(hasattr(h,'configured_local_player_id'))
        self.assertFalse(hasattr(d,'turn_begin_state'))
        with self.assertRaisesRegex(RuntimeError,'closed'):s.controller_flag(h.pointer)

    def test_no_local_identity_is_inferred_and_negative_sentinel_is_uint32(self):
        h,d,s,_,_=self.fixture(-1)
        local=C.WINFUNCTYPE(C.c_uint32,C.c_void_p)(h.vtable[0xD0//8])
        self.assertEqual(local(h.pointer),0xFFFFFFFF);s.close()
        args=dict(core_sha256=XP1_CORE_SHA256,local_player_id=None,read=Mock(),emit=Mock())
        with self.assertRaisesRegex(ValueError,'explicit'):ControlInputService(h,s.core,2000,d,**args)
        args['local_player_id']=65
        with self.assertRaisesRegex(ValueError,'explicit'):ControlInputService(h,s.core,2000,d,**args)

    def test_pending_scope_foreign_thread_and_replaced_state_refuse(self):
        h,d,s,_,_=self.fixture();d.pending=[b'pending']
        with self.assertRaisesRegex(RuntimeError,'pending'):s.close()
        d.pending=[];d.host_notification_counter=1
        with self.assertRaisesRegex(RuntimeError,'open scope'):s.close()
        d.host_notification_counter=0
        with patch('civ6_host.runtime.control_input_service.threading.get_ident',return_value=-1):
            with self.assertRaisesRegex(ValueError,'thread'):s.controller_flag(h.pointer)
        d.turn_begin_state=object()
        with self.assertRaisesRegex(RuntimeError,'replaced'):s.controller_flag(h.pointer)

    def test_native_read_failure_quarantines_without_reset_or_retry(self):
        h,d,s,_,_=self.fixture()
        with patch.object(s.turn_begin_state,'read_native_flag',side_effect=OSError('uncertain')) as read:
            with self.assertRaises(OSError):s.controller_flag(h.pointer)
            with self.assertRaisesRegex(RuntimeError,'quarantined'):s.controller_flag(h.pointer)
            self.assertEqual(read.call_count,1)
        with self.assertRaisesRegex(RuntimeError,'quarantined'):s.close()

    def test_duplicate_or_foreign_owner_refuses_before_native_construction(self):
        h,d,s,_,_=self.fixture()
        with patch('civ6_host.runtime.control_input_service.NativeControllerCode') as code:
            with self.assertRaisesRegex(ValueError,'foreign or already'):
                ControlInputService(h,s.core,2000,d,core_sha256=XP1_CORE_SHA256,
                    local_player_id=7,read=Mock(),emit=Mock())
            code.assert_not_called()

    def test_shared_getter_preserves_the_existing_base_body(self):
        self.assertIs(NativeDeferredHostEvents.controller_flag,HostControllerQuery.controller_flag)
        def method(tree,cls):
            c=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name==cls)
            return next(n for n in c.body if isinstance(n,ast.FunctionDef) and n.name=='controller_flag')
        old=ast.parse((resource_root()/'civ6rl/native_host_events.py').read_text(encoding='utf-8'))
        new=ast.parse(Path(__import__(HostControllerQuery.__module__,fromlist=['x']).__file__).read_text(encoding='utf-8'))
        a=ast.parse(ast.unparse(method(old,'NativeDeferredHostEvents')))
        for n in ast.walk(a):
            if isinstance(n,ast.ImportFrom) and n.level==1:
                n.module='civ6_host.runtime.native.'+n.module;n.level=0
        self.assertEqual(ast.dump(a),ast.dump(ast.parse(ast.unparse(method(new,'HostControllerQuery')))))

    def test_source_checks_exact_callers_and_live_context_owner_without_invoking_them(self):
        from civ6_host.runtime import control_input_source as source
        base=0x200000000;ctx=0x1000;mem={}
        def put(addr,data):mem.update({addr+i:b for i,b in enumerate(data)})
        def read(addr,n):return bytes(mem[addr+i] for i in range(n))
        for name in ('local_player_update','controller_query'):
            for fragment in source.body(name)['fragments']:
                for i in fragment['instructions']:put(base+int(i['va'],16)-0x180000000,bytes.fromhex(i['bytes']))
        for addr,value in ((ctx,base+0x8A8DF0),(ctx+8,0x2000),(base+0x9F2620,0x2000),(base+0x9F2640,123)):
            put(addr,struct.pack('<Q',value))
        self.assertFalse(source.verify_xp1(base,ctx,read,host_pointer=123)['saved_game_load_admitted'])
        put(base+0x9F2640,struct.pack('<Q',456))
        with self.assertRaisesRegex(ValueError,'owner/context'):source.verify_xp1(base,ctx,read,host_pointer=123)
        put(base+0x9F2640,struct.pack('<Q',123));mem[base+0x533B0]^=1
        with self.assertRaisesRegex(ValueError,'instructions differ'):source.verify_xp1(base,ctx,read,host_pointer=123)


def load_tests(loader,tests,pattern):
    # Preserve the retained controller test's native refusal fixture without
    # importing the historical civ6rl implementation through its test package.
    helper=resource_root()/'tests/test_native_diplomacy_statement947.py'
    witness=ModuleType('retained_controller_witness');witness.__file__=str(helper)
    source=helper.read_text(encoding='utf-8').replace('civ6rl.','civ6_host.runtime.native.').replace('from civ6rl import','from civ6_host.runtime.native import')
    exec(compile(source,str(helper),'exec'),witness.__dict__)
    sys.modules[witness.__name__]=witness
    for name in ('test_native_controller_code','test_native_host_slot120','test_native_session_controller'):
        p=resource_root()/'tests'/(name+'.py');module=ModuleType('retained_'+name);module.__file__=str(p)
        source=p.read_text(encoding='utf-8').replace('civ6rl.','civ6_host.runtime.native.').replace('from civ6rl import','from civ6_host.runtime.native import').replace('tests.test_native_diplomacy_statement947','retained_controller_witness')
        exec(compile(source,str(p),'exec'),module.__dict__)
        tests.addTests(loader.loadTestsFromModule(module))
    return tests
