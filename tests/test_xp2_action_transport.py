"""Real transport/recorder/owner methods; native machine and OS calls are fixtures."""
import ast
import ctypes as C
from contextlib import ExitStack
import hashlib
import struct
import tempfile
import threading
from pathlib import Path
from types import SimpleNamespace as NS
import unittest
from unittest.mock import Mock, patch

from civ6_host.runtime import xp2_action_transport_source as source
from civ6_host.runtime import action_transport_profiles as profiles
from civ6_host.runtime import unit_operation_ui_profile as units
from civ6_host.runtime import xp1_log_event_profile as logs
from civ6_host.runtime.configuration_profiles import XP1_CORE_SHA256, XP2_CORE_SHA256
from civ6_host.runtime.paths import resource_root
from civ6_host.runtime.saved_load_services import SavedLoadServices
from civ6_host.runtime.xp1_action_transport import SavedActionTransport
from civ6_host.runtime.xp1_loaded_lifetime import LoadedLifetime
from civ6_host.runtime.native.native_official_load import OfficialLoadBackend
from civ6_host.runtime.native.native_host import DiagnosticHost
from civ6_host.runtime.native.native_events import NativeEventRecorder
from civ6_host.runtime.native import native_action_transport as calls
import extraction_xp1_session_readers as hook


class Memory:
    base=0x180000000
    context=0x200000000
    def __init__(self):
        self.proof=source.source();self.bytes={};self.regions=[];self.owned=[];self.reads=[];self.calls=[]
        for body in self.proof['functions'].values():
            for f in body['fragments']:
                self.put(self.base+int(f['start_rva'],16),bytes.fromhex(f['raw_hex']))
        for row in self.proof['slots']:
            self.put(self.base+row['vtable_rva']+row['slot'],struct.pack('<Q',self.base+row['target_rva']))
        row=self.proof['message_vtable']
        self.put(self.base+row['rva'],b''.join(struct.pack('<Q',self.base+rva) for rva in row['entries']))
        for rva,row in self.proof['literals'].items():self.put(self.base+int(rva,16),bytes.fromhex(row['raw_hex']))
        self.put(self.context,struct.pack('<Q',self.base+0xA101E8))
        self.sentinel=self.base+source.ABI.receive_queue_rva
        self.empty_queue()
        self.put(self.base+source.ABI.processor_flags_rva,bytes(4))
        self.put(self.base+source.ABI.optional_queue_flag_rva,b'\0')
        self.put(self.base+0xB90648,bytes(8))

    def put(self,at,data):self.bytes.update((at+i,v) for i,v in enumerate(data))
    def empty_queue(self):self.put(self.sentinel,struct.pack('<QQ',self.sentinel,self.sentinel))
    def read(self,at,size):
        # Same limit as native_setup.local_reader, including composed owner use.
        if not at or not 0<size<=6784:raise ValueError('Invalid local native read')
        self.reads.append((at,size))
        if all(at+i in self.bytes for i in range(size)):return bytes(self.bytes[at+i] for i in range(size))
        if any(a<=at and at+size<=b for a,b in self.regions):return C.string_at(at,size)
        raise ValueError('Fixture refused unowned memory '+hex(at))
    def own(self,obj):
        self.owned.append(obj);at=C.addressof(obj);self.regions.append((at,at+C.sizeof(obj)));return at
    def make_archive(self,payload):
        data=self.own(C.create_string_buffer(payload,len(payload)))
        archive=self.own(C.create_string_buffer(struct.pack('<QQQ',self.base+source.ABI.archive_vtable_rva,data,len(payload)),24))
        return archive
    def virtual(self,core,ptr,slot,rva,result,*args):
        self.calls.append(('virtual',ptr,slot,rva))
        a=source.ABI
        if rva==a.archive_size_rva:return lambda p:int.from_bytes(self.read(p+16,8),'little')
        if rva==a.receive_rva:
            def receive(context,label,stream):
                raw=self.read(stream,40);_,buffer,position,length,_=struct.unpack('<QQQQQ',raw)
                self.assertion=(context,label,position)
                payload=self.read(buffer,length);data=self.own(C.create_string_buffer(payload,length))
                record=struct.pack('<QQI4xQQQQ',self.sentinel,self.sentinel,label,data,data+length,data+length,0)
                node=self.own(C.create_string_buffer(record,56));self.put(self.sentinel,struct.pack('<QQ',node,node))
                if getattr(self,'corrupt_copy',False):C.memset(data,ord('!'),1)
            return receive
        if rva==a.drain_rva:
            def drain(context):
                self.calls.append(('drain',context))
                if not getattr(self,'retain_node',False):self.empty_queue()
            return drain
        if rva==a.game_getter_rva:
            game=self.own(C.create_string_buffer(struct.pack('<Q',self.base+a.game_vtable_rva),32))
            return lambda context:game
        if rva in (a.game_release_rva,a.game_update_rva):
            return lambda ptr:self.calls.append(('release' if rva==a.game_release_rva else 'update',ptr))
        raise AssertionError('Unexpected native fixture virtual '+hex(rva))
    def factory(self,result,*args):
        original=self.original_factory(result,*args)
        def bind(address):
            if callable(address):return original(address) # real host callback trampoline
            rva=address-self.base
            if rva==source.ABI.view_ctor_rva:
                def ctor(ptr,buffer,length):
                    self.regions.append((ptr,ptr+64))
                    C.memmove(ptr,struct.pack('<QQQQQ',self.base+source.ABI.view_vtable_rva,buffer,0,length,0),40)
                    return ptr
                return ctor
            if rva==source.ABI.view_dtor_rva:
                def destroy(ptr):
                    self.calls.append(('stream_destroy',ptr))
                    if getattr(self,'damage_canary',False):C.memset(ptr+63,0,1)
                return destroy
            raise AssertionError('Unexpected native fixture call '+hex(rva))
        return bind


class Fixture:
    """Instantiate actual command owner; surrounding already-loaded objects are fixture state."""
    def __init__(self):
        self.stack=ExitStack();self.memory=m=Memory();self.events=[]
        self.directory=Path(self.stack.enter_context(tempfile.TemporaryDirectory(dir=resource_root()/'work',prefix='xp2-transport-fixture-')))
        self.active_callback=0
        self.setter=C.CFUNCTYPE(None,C.c_void_p)(lambda p:setattr(self,'active_callback',p or 0))
        self.getter=C.CFUNCTYPE(C.c_void_p)(lambda:self.active_callback)
        self.kernel=NS()
        names=('ReadProcessMemory','CreateFileW','GetFileSizeEx','WriteFile','CloseHandle','GetModuleHandleW','GetProcAddress')
        for name in names:setattr(self.kernel,name,Mock(return_value=1))
        self.kernel.GetModuleHandleW.return_value=0x400000
        self.kernel.GetProcAddress.side_effect=lambda module,name:C.cast(self.setter if name==b'EXP_SetLogEventCallback' else self.getter,C.c_void_p).value
        self.stack.enter_context(patch.object(C,'WinDLL',return_value=self.kernel))
        self.stack.enter_context(patch('civ6_host.runtime.profile_script_binding._current_executable',
            return_value=resource_root()/'work/native-host-xp2-ui-build01/civ6rl-native-python.exe'))
        h=DiagnosticHost.__new__(DiagnosticHost);h.functions=[];h.vtable=(C.c_void_p*64)()
        h.object=(C.c_void_p*2)(C.addressof(h.vtable),1);h.aux_vtable=(C.c_void_p*64)()
        h.aux_object=(C.c_void_p*2)(C.addressof(h.aux_vtable),1)
        h.emit=lambda stage,**fields:self.events.append(dict(stage=stage,**fields))
        h._bind(h.vtable,0x70,C.c_int32,[C.c_void_p,C.c_void_p],h._unsupported('host',0x70))
        self.previous=(h.vtable[14],h._slot_bindings[(C.addressof(h.vtable),0x70)])
        b=OfficialLoadBackend.__new__(OfficialLoadBackend);b.thread=threading.get_ident()
        b.runtime=NS(thread=threading.get_ident,read=m.read);b.stage='prepared';b.prefix=None
        b.destroyed=b.poisoned=False;b.host=h;b.context=m.context;b.fixture=self.directory/'fixture.json'
        b.core=NS(_name=m.proof['image']['path'],_handle=m.base)
        b.load_abi=b.configuration_abi=NS(core_sha256=XP2_CORE_SHA256);b.emit=h.emit
        s=SavedLoadServices.__new__(SavedLoadServices)
        s.backend=b;s.host=h;s.core=b.core;s.context=b.context;s.core_sha256=XP2_CORE_SHA256;s.emit=h.emit
        h._saved_load_services=s
        m.put(m.base+0xB8AA80,struct.pack('<Q',h.pointer));m.put(m.base+0xB8AA88,struct.pack('<Q',C.addressof(h.aux_object)))
        self.host,self.backend,self.services=h,b,s
        self.stack.enter_context(patch.object(calls,'local_reader',return_value=m.read))
        self.stack.enter_context(patch.object(calls,'virtual',side_effect=m.virtual))
        m.original_factory=C.WINFUNCTYPE
        self.stack.enter_context(patch.object(C,'WINFUNCTYPE',side_effect=m.factory))
        create=C.create_string_buffer
        def buffer(*args):
            obj=create(*args);m.own(obj);return obj
        self.stack.enter_context(patch.object(C,'create_string_buffer',side_effect=buffer))
    def install(self):
        t=SavedActionTransport(self.services);self.backend.prefix=self.services;self.transport=t
        return t
    def close(self):
        recorder=getattr(self.host,'event_recorder',None)
        if recorder is not None and not recorder.closed:recorder.close()
        self.stack.close()


class XP2TransportTests(unittest.TestCase):
    def fixture(self):
        f=Fixture();self.addCleanup(f.close);return f

    def test_exact_source_live_slots_complete_tails_and_dependencies(self):
        m=Memory();p=m.proof
        for family in ('transport','unit','log'):source.verify_live(m.base,m.read,family=family,context=m.context)
        self.assertLessEqual(max(n for _,n in m.reads),4096)
        # Mutate the last byte in every complete body, including short leaves after RET.
        for name,b in p['functions'].items():
            f=b['fragments'][-1];at=m.base+int(f['start_rva'],16)+f['length']-1
            with self.subTest(body=name):
                m.bytes[at]^=1
                with self.assertRaisesRegex(ValueError,'differs'):source.verify_live(m.base,m.read,family='transport')
                m.bytes[at]^=1
        at=m.base+0xA101E8+0x230;m.bytes[at]^=1
        with self.assertRaisesRegex(ValueError,'slot'):source.verify_live(m.base,m.read,family='transport')
        pins=source.source_dependencies()
        for path,digest in pins.items():self.assertEqual(hashlib.sha256(Path(path).read_bytes()).hexdigest(),digest)
        self.assertEqual(profiles.source_dependencies(core_sha256=XP2_CORE_SHA256),pins)
        self.assertEqual(units.source_dependencies(core_sha256=XP2_CORE_SHA256),pins)
        self.assertEqual(logs.source_dependencies(core_sha256=XP2_CORE_SHA256),pins)

    def test_selected_profiles_and_wrong_engine_refuse(self):
        m=Memory();core=NS(_name=m.proof['image']['path'],_handle=m.base)
        self.assertIs(profiles.transport_profile(XP2_CORE_SHA256,core,m.context,m.read),source.ABI)
        self.assertEqual(units.verify_live(m.base,m.read,core_sha256=XP2_CORE_SHA256)['callbacks'],source.CALLBACKS)
        self.assertEqual(logs.verify_live(m.base,m.read,core_sha256=XP2_CORE_SHA256)['source_sha256'],source.SOURCE[1])
        for fn in (profiles.source_dependencies,units.source_dependencies,logs.source_dependencies):
            with self.assertRaises(ValueError):fn(core_sha256='unknown')
        with self.assertRaisesRegex(ValueError,'binary changed'):profiles.transport_profile(XP1_CORE_SHA256,core,m.context,m.read)
        with self.assertRaisesRegex(ValueError,'Incomplete'):source.verify_live(m.base,lambda at,n:m.read(at,n)[:-1],family='unit')

    def test_real_constructor_capture_fifo_native_copy_canary_and_restore(self):
        f=self.fixture();t=f.install();m=f.memory
        self.assertIs(type(t.recorder),NativeEventRecorder);self.assertIs(NativeEventRecorder._installed,t.recorder)
        self.assertEqual(t.log_binding['callback_address'],f.active_callback)
        payload=bytes.fromhex('363f0f8c00000100000001000e000000ffffffff0000000000000000')
        self.assertEqual(t.capture(f.host.pointer,m.make_archive(payload)),0)
        self.assertEqual(t.pending,[payload])
        # This test exercises primitive delivery without admitting the separate session capability.
        with self.assertRaisesRegex(ValueError,'continuation'):t.deliver_one()
        calls.NativeActionTransport.deliver_one(t)
        self.assertEqual(m.assertion,(m.context,0xffffffff,0));self.assertEqual(t.pending,[])
        t.require_empty_native_queue()
        calls.NativeActionTransport.update_game_once(t)
        self.assertEqual([r[0] for r in m.calls if r[0] in ('update','release')],['update','release'])
        token=LoadedLifetime.__new__(LoadedLifetime);token.owner=f.backend;token.phase='services';token.destroy_returned=True
        f.backend._loaded_lifetime=token
        with self.assertRaisesRegex(ValueError,'before actual'):t.close()
        f.backend.destroyed=True;t.close()
        self.assertEqual((f.host.vtable[14],f.host._slot_bindings[(C.addressof(f.host.vtable),0x70)]),f.previous)
        self.assertTrue(t.closed);self.assertIs(NativeEventRecorder._installed,t.recorder)
        t.recorder.close();self.assertIsNone(NativeEventRecorder._installed);self.assertEqual(f.active_callback,0)

    def test_composed_foreign_owner_and_source_rejected_before_binding(self):
        f=self.fixture();f.services.core=object()
        with self.assertRaisesRegex(ValueError,'exact saved service'):SavedActionTransport(f.services)
        self.assertIsNone(NativeEventRecorder._installed);self.assertEqual(f.host.vtable[14],f.previous[0])
        f.services.core=f.backend.core;f.memory.bytes[f.memory.base+source.ABI.view_ctor_rva]^=1
        with self.assertRaisesRegex(ValueError,'differs'):SavedActionTransport(f.services)
        self.assertIsNone(NativeEventRecorder._installed);self.assertFalse(hasattr(f.services,'actions'))

    def test_composed_foreign_global_and_lazy_getter_refuse(self):
        f=self.fixture();m=f.memory;m.put(m.base+0xB8AA88,struct.pack('<Q',123))
        with self.assertRaisesRegex(ValueError,'auxiliary owner'):SavedActionTransport(f.services)
        self.assertIsNone(NativeEventRecorder._installed)
        m.put(m.base+0xB8AA88,struct.pack('<Q',C.addressof(f.host.aux_object)))
        m.put(m.base+0xB90648,struct.pack('<Q',123))
        with self.assertRaisesRegex(ValueError,'foreign executable'):SavedActionTransport(f.services)
        self.assertTrue(f.backend.poisoned)
        self.assertIsNotNone(NativeEventRecorder._installed) # retained for controlled quarantine

    def test_fifo_failures_preserve_uncertain_work(self):
        for failure in ('damage_canary','corrupt_copy','retain_node'):
            with self.subTest(failure=failure):
                f=self.fixture();t=f.install();m=f.memory
                try:
                    t.capture(f.host.pointer,m.make_archive(b'native-fixture'));setattr(m,failure,True)
                    with self.assertRaises(RuntimeError):calls.NativeActionTransport.deliver_one(t)
                    with self.assertRaises(ValueError):t.require_empty_native_queue()
                finally:f.close()

    def test_engine_and_callback_owner_cannot_change_after_install(self):
        f=self.fixture();t=f.install();t.check()
        f.services.core_sha256=XP1_CORE_SHA256
        with self.assertRaisesRegex(ValueError,'selected service'):t.check()
        f.services.core_sha256=XP2_CORE_SHA256;f.host._saved_load_services=object()
        with self.assertRaisesRegex(ValueError,'selected service'):t.check()

    def test_hook_keeps_founder_lua_and_only_selects_preface(self):
        # Use the real historical source before extraction, never edit generated runtime.
        path=resource_root()/'civ6rl/native_unit_actions.py';raw=path.read_text()
        # The global extractor rewrites import names before applying this hook.
        raw=raw.replace('from .native_','from civ6_host.runtime.native.native_')
        transformed=hook.parameterize('civ6rl.native_unit_actions',raw)
        old=next(n for n in ast.parse(raw).body if isinstance(n,ast.FunctionDef) and n.name=='found_city_catalog_source')
        new=next(n for n in ast.parse(transformed).body if isinstance(n,ast.FunctionDef) and n.name==old.name)
        self.assertEqual([ast.dump(n) for n in old.body[3:]],[ast.dump(n) for n in new.body[3:]])
        self.assertIn('XP2_CORE_SHA256',transformed)
        self.assertIn('unit_source(core_sha256=core_sha256)',transformed)


if __name__=='__main__':unittest.main()
