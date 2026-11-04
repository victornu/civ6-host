"""Real shared host callback ownership; only native memory/calls are fixtures."""
import ctypes as C
import struct
from types import SimpleNamespace as NS
import unittest
from unittest.mock import Mock, patch

from civ6_host.runtime import xp2_prepare as prepare
from civ6_host.runtime import xp2_prepare_source as source
from civ6_host.runtime.configuration_profiles import _copy
from civ6_host.runtime.prepare_services import PrepareServices
from civ6_host.runtime.native import native_host as nh
from civ6_host.runtime.native import native_core_context_profiles as profiles
from civ6_host.runtime.native import native_xp1_teardown_adapter as teardown
from civ6_host.runtime.native import native_setup, native_probe, native_localization
from civ6_host.runtime.saved_load_profiles import XP2_CORE_SHA256, XP1_CORE_SHA256


class XP2PrepareServicesTests(unittest.TestCase):
    def fixture(self):
        self.contract = source.verify_source()
        self.base,self.context,self.inner = 0x300000000,0x100000,0x200000
        self.memory = {}
        self.put = lambda address,data:self.memory.update({address+i:b for i,b in enumerate(data)})
        self.read = lambda address,size:bytes(self.memory[address+i] for i in range(size))
        self.q = lambda address,value:self.put(address,struct.pack('<Q',value))
        bootstrap = self.contract['bootstrap']
        for _,rva,raw in (*bootstrap['fragments'],*self.contract['fragments']):
            self.put(self.base+rva,raw)
        for capture in (*bootstrap['proof']['vtable_captures'].values(),
                        *self.contract['proof']['vtable_captures'].values()):
            raw = bytes.fromhex(capture['raw_hex'])
            pointers = struct.unpack('<'+'Q'*(len(raw)//8),raw)
            self.put(self.base+int(capture['rva'],16),
                struct.pack('<'+'Q'*len(pointers),*(self.base+p-0x180000000 for p in pointers)))
        self.put(self.base+0x9bfba8,nh.HOST_IID)
        for address,value in ((self.context,self.base+0xa101e8),(self.context+8,self.inner),
                (self.inner,self.base+0xa44f70),(self.base+0xb8aa60,self.inner),
                (self.inner+0x50,0x3450),(self.inner+0x58,0x3458),(self.inner+0x60,0)):
            self.q(address,value)
        self.put(self.inner+0x40,b'\1')
        host = object.__new__(nh.DiagnosticHost)
        host.functions=[];host.emit=Mock();host.dll_directory='fixture-only'
        host.types=nh.TypeRegistry(nh.BOOTSTRAP_TYPE_NAMES);host.archives=nh.ArchiveRegistry()
        host.filters=nh.EventFilterRegistry()
        host.manifest={'input_profile':'xp2-lan'}
        def fatal(*args,**kwargs):raise RuntimeError('unexpected host fatal: '+str(args))
        host._fatal=fatal
        for object_name,table_name,count in (('object','vtable',128),('aux_object','aux_vtable',32),
                ('logger_object','logger_vtable',32),('registrar_object','registrar_vtable',3),
                ('descriptor_object','descriptor_vtable',32)):
            table=(C.c_void_p*count)()
            setattr(host,table_name,table)
            setattr(host,object_name,(C.c_void_p*2)(C.addressof(table),1))
            for i in range(count):host._bind(table,i*8,None,[C.c_void_p],host._unsupported(table_name,i*8))
        host._bind(host.vtable,0x110,C.c_void_p,[C.c_void_p],host._registrar)
        host._bind(host.registrar_vtable,8,None,[C.c_void_p,C.c_void_p],host._remove_type)
        host.enable_tuner_unavailable_probe()
        self.freed=[]
        host.native_aligned_free=C.CFUNCTYPE(None,C.c_void_p)(self.freed.append)
        free=C.cast(host.native_aligned_free,C.c_void_p).value
        self.owner=dict(module_path='fixture-crt.dll',export='_aligned_free',address=hex(free))
        self.q(self.base+0x9b7680,free)
        globals={rva:p for rva,p in zip(bootstrap['globals_rvas'],
                    (host.pointer,C.addressof(host.aux_object),C.addressof(host.logger_object)))}
        for rva,p in globals.items():self.q(self.base+rva,p)
        observed={hex(rva):p for rva,p in globals.items()}
        for event,filter_id,value in bootstrap['declarations']:host.filters.declare(event,filter_id,value)
        host.context_init_receipt=dict(schema='civ6rl.native_xp2_context_init_receipt.v1',
            status='xp2_context_initialized_diagnostic_only',core_sha256=XP2_CORE_SHA256,
            source=bootstrap['receipt'],init_called=True,init_returned=True,initialized_after=True,host_setter_called=True,
            game_created=False,newgame_called=False,prepare_called=False,eligible_for_training=False,
            inputs={'captured_input_binding':{'input_profile':'xp2-lan'}},host_globals_after_set=observed,
            event_filter_declarations=[dict(event=hex(e),filter_id=hex(f),value=v) for e,f,v in bootstrap['declarations']])
        host.context_teardown_receipt=dict(schema='civ6-host.xp2-context-teardown-installation.v1',
            installed=True,source=bootstrap['receipt'],core_sha256=XP2_CORE_SHA256,host_globals_verified=observed,
            type_names_allowed=list(source.TYPE_NAMES),host_slot='0x110',registrar_remove_slot='0x8',
            aligned_free_iat_rva='0x9b7680',aligned_free_runtime_owner=self.owner,callback_references_retained=True,
            destroy_called=False,game_created=False,saved_load_admitted=False)
        host._xp2_teardown_binding=host.context_teardown_receipt
        self.host=host
        self.core=NS(_handle=self.base,_name='fixture-core.dll',_diagnostic_host=host)
        self.profile=NS(ruleset='xp2',mode='context',core_sha256=XP2_CORE_SHA256)
        self.native_calls=[];self.buffers=[]
        return host

    def string(self,name):
        raw=name.encode('ascii');buffer=C.create_string_buffer(raw)
        start=C.addressof(buffer)
        descriptor=(C.c_void_p*3)(start,start+len(raw),start+len(raw)+1)
        self.buffers.extend((buffer,descriptor))
        return C.addressof(descriptor),start

    def archive(self,key):
        descriptor=C.create_string_buffer(0x90)
        C.c_uint64.from_address(C.addressof(descriptor)+0x58).value=key
        self.buffers.append(descriptor)
        return C.addressof(descriptor)

    def declare_types(self,count=10):
        fn=C.WINFUNCTYPE(None,*([C.c_void_p]*4))(self.host.registrar_vtable[0])
        for name,pair in list(zip(source.TYPE_NAMES,source.CALLBACK_RVAS))[:count]:
            descriptor,_=self.string(name)
            fn(C.addressof(self.host.registrar_object),descriptor,*(self.base+rva for rva in pair))

    def native_factory(self,core,context,slot,rva,*abi):
        self.assertIs(core,self.core);self.assertEqual(context,self.context)
        self.assertEqual(rva,{0x38:0x590660,0x40:0x591870}[slot])
        if slot==0x38:return lambda ctx:True
        def call(ctx):
            self.native_calls.append('prepare')
            self.declare_types()
            get=C.WINFUNCTYPE(C.c_void_p,C.c_void_p)(self.host.vtable[0x108//8])
            self.assertEqual(get(self.host.pointer),C.addressof(self.host.descriptor_object))
            register=C.WINFUNCTYPE(C.c_bool,C.c_void_p,C.c_void_p)(self.host.descriptor_vtable[0])
            self.archive_pointer=self.archive(0x4ffff)
            C.c_void_p.from_address(self.archive_pointer+0x50).value=C.addressof(self.host.descriptor_object)
            self.assertTrue(register(C.addressof(self.host.descriptor_object),self.archive_pointer))
            self.assertEqual(C.c_uint8.from_address(self.archive_pointer+0x48).value,0)
            C.c_uint8.from_address(self.archive_pointer+0x48).value=1  # native AL-to-active write
            tuner=C.WINFUNCTYPE(C.c_void_p,C.c_void_p,C.c_char_p,C.c_uint8)(self.host.aux_vtable[0])
            self.assertIsNone(tuner(C.addressof(self.host.aux_object),b'GameCore_Tuner',1))
            self.put(self.archive_pointer,C.string_at(self.archive_pointer,0x90))
            self.q(self.inner+0x60,self.archive_pointer-0x20)
            self.q(self.archive_pointer-0x20,self.base+source.GAME_VTABLE_RVA)
            self.put(self.archive_pointer-0x20+source.GAME_INITIALIZED_OFFSET,b'\0')
        return call

    def invoke(self,factory=None,profile=None):
        def localize(host,directory):host.localization_initialized=True;self.native_calls.append('localization')
        with patch.object(profiles,'profile_for_core',return_value=self.profile), \
             patch.object(profiles,'validate_loaded_modules'), \
             patch.object(native_probe.Windows,'modules',return_value=['fixture-crt.dll']), \
             patch.object(native_setup,'local_reader',return_value=self.read), \
             patch.object(teardown,'_default_owner_verifier',return_value=self.owner), \
             patch.object(native_localization,'initialize_localization',side_effect=localize), \
             patch.object(nh,'virtual',side_effect=factory or self.native_factory):
            return prepare.prepare(self.core,self.context,self.host,profile or self.profile,Mock(),null_tuner_diagnostic=True)

    def test_composed_prepare_uses_real_registries_and_retains_destroy_callbacks(self):
        host=self.fixture()
        before={name:tuple(getattr(host,name)) for name in ('vtable','aux_vtable','logger_vtable','registrar_vtable','descriptor_vtable')}
        receipt=self.invoke()
        self.assertEqual(self.native_calls,['localization','prepare'])
        self.assertEqual((len(host.types.entries),len(self.freed)),(10,10))
        self.assertTrue(receipt['prepare_returned']);self.assertFalse(receipt['saved_game_loaded'])
        self.assertTrue(receipt['game_created']);self.assertTrue(receipt['allocated_game_object'])
        self.assertFalse(receipt['game_initialized'])
        self.assertEqual(receipt['services']['archive_entries'],[dict(key=0x4ffff,pointer=self.archive_pointer)])
        changed={'vtable':{0x108//8},'registrar_vtable':{0},'descriptor_vtable':{0,1},'aux_vtable':set(),'logger_vtable':set()}
        for name,values in before.items():
            self.assertEqual({i for i,(a,b) in enumerate(zip(values,getattr(host,name))) if a!=b},changed[name])
        remove=C.WINFUNCTYPE(None,C.c_void_p,C.c_void_p)(host.descriptor_vtable[1])
        remove(C.addressof(host.descriptor_object),self.archive_pointer)
        self.assertEqual(host.archives.entries,{})
        self.assertEqual(C.c_uint8.from_address(self.archive_pointer+0x48).value,1)
        remove_type=C.WINFUNCTYPE(None,C.c_void_p,C.c_void_p)(host.registrar_vtable[1])
        for name in source.TYPE_NAMES:
            descriptor,_=self.string(name);remove_type(C.addressof(host.registrar_object),descriptor)
        self.assertEqual(host.types.entries,{})
        self.assertEqual(len(self.freed),20)
        self.assertEqual(prepare.prepare_receipt(host)['services']['archive_remove_calls'],1)
        with self.assertRaisesRegex(ValueError,'already been entered'):self.invoke()

    def test_archive_false_idempotence_collision_and_inactive_remove_are_preserved(self):
        host=self.fixture();services=PrepareServices(host,self.base,contract=self.contract)
        this=C.addressof(host.descriptor_object);a=self.archive(7);b=self.archive(7);zero=self.archive(0)
        self.assertFalse(services.register_archive(this,0));self.assertFalse(services.register_archive(this,zero))
        self.assertTrue(services.register_archive(this,a));self.assertTrue(services.register_archive(this,a))
        self.assertFalse(services.register_archive(this,b));self.assertEqual(host.archives.entries,{7:a})
        services.remove_archive(this,a);self.assertEqual(host.archives.entries,{7:a})
        C.c_uint8.from_address(b+0x48).value=1
        services.remove_archive(this,b);self.assertEqual(host.archives.entries,{7:a})
        C.c_uint8.from_address(a+0x48).value=1
        services.remove_archive(this,a);self.assertEqual(host.archives.entries,{})
        self.assertEqual((services.accepted_calls,services.rejected_calls),(2,3))

    def test_type_order_callback_owner_and_allocator_refuse_without_consumption(self):
        host=self.fixture();services=PrepareServices(host,self.base,contract=self.contract);services.entered=True
        descriptor,_=self.string('Formation')
        with self.assertRaisesRegex(ValueError,'order'):
            services.register_type(C.addressof(host.registrar_object),descriptor,1,2)
        descriptor,_=self.string('Unit')
        with self.assertRaisesRegex(ValueError,'owner'):
            services.register_type(1,descriptor,*(self.base+r for r in source.CALLBACK_RVAS[0]))
        with self.assertRaisesRegex(ValueError,'order'):
            services.register_type(C.addressof(host.registrar_object),descriptor,self.base+1,self.base+2)
        self.assertEqual((services.count,self.freed,host.types.entries),(0,[],{}))
        self.q(self.base+0x9b7680,1234)
        with self.assertRaisesRegex(ValueError,'aligned-free'):
            source.verify_live(self.base,self.context,host,self.read,self.contract)

    def test_changed_late_branch_body_vtable_and_foreign_owner_refuse_before_calls(self):
        for kind in ('late_return','vtable','inner','host','allocator','init_owner'):
            host=self.fixture()
            if kind=='late_return':self.put(self.base+0x590683,b'\0')
            elif kind=='vtable':self.q(self.base+0xa44f70+0x50,self.base+0x3db40)
            elif kind=='inner':self.q(self.base+0xb8aa60,self.inner+1)
            elif kind=='host':self.q(self.base+0xb8aa80,123)
            elif kind=='allocator':self.q(self.base+0x9b7680,123)
            else:host._xp2_teardown_binding=dict(host.context_teardown_receipt)
            with self.subTest(kind=kind),self.assertRaises(ValueError):self.invoke()
            self.assertEqual(self.native_calls,[])
            self.assertFalse(hasattr(host,'_prepare_services'))

    def test_wrong_engine_and_null_tuner_flag_refuse_before_callbacks(self):
        host=self.fixture()
        with self.assertRaisesRegex(ValueError,'engine'):
            self.invoke(profile=NS(ruleset='xp1',mode='context',core_sha256=XP1_CORE_SHA256))
        for value in (False,None,1,'true'):
            with self.assertRaises(ValueError):prepare.require_null_tuner_diagnostic(host,value)
        host._bind(host.aux_vtable,0,None,[C.c_void_p],host._unsupported('aux',0))
        with self.assertRaisesRegex(ValueError,'retained'):self.invoke()
        self.assertEqual(self.native_calls,[])

    def test_incomplete_prepare_keeps_failed_lifetime_and_cannot_retry(self):
        host=self.fixture()
        def factory(core,ctx,slot,rva,*abi):
            if slot==0x38:return lambda _:True
            def call(_):
                self.declare_types(9)
                pointer=self.archive(0x4ffff)
                self.host._prepare_services.register_archive(C.addressof(host.descriptor_object),pointer)
                C.c_void_p.from_address(pointer+0x50).value=C.addressof(host.descriptor_object)
                C.c_uint8.from_address(pointer+0x48).value=1
                self.put(pointer,C.string_at(pointer,0x90));self.q(self.inner+0x60,pointer-0x20)
                self.q(pointer-0x20,self.base+source.GAME_VTABLE_RVA)
                self.put(pointer-0x20+source.GAME_INITIALIZED_OFFSET,b'\0')
            return call
        with self.assertRaises(prepare.XP2PrepareError) as caught:self.invoke(factory=factory)
        self.assertTrue(caught.exception.receipt['prepare_entered'])
        self.assertTrue(caught.exception.receipt['prepare_returned'])
        self.assertEqual(caught.exception.receipt['failure_phase'],'after_prepare')
        self.assertEqual(caught.exception.receipt['services']['registered_type_count'],9)
        with self.assertRaises(ValueError):self.invoke()
        self.assertIs(host._prepare_services,host._xp2_prepare_services)

    def test_corrupt_profile_contract_is_rejected_independently_of_image_hash(self):
        proof=_copy(source._source(source.SOURCE));proof['archive']['descriptor_fields']['key']['offset']=0x50
        original=source._source
        with patch.object(source,'_source',side_effect=lambda ref:proof if ref==source.SOURCE else original(ref)):
            with self.assertRaisesRegex(ValueError,'ABI'):source.verify_source()

    def test_returned_services_must_own_the_registered_archive(self):
        self.fixture()
        original=self.native_factory
        def factory(*args):
            fn=original(*args)
            if args[2]==0x38:return fn
            def wrong(ctx):
                fn(ctx)
                self.q(self.archive_pointer+0x50,C.addressof(self.host.registrar_object))
            return wrong
        with self.assertRaises(prepare.XP2PrepareError) as caught:self.invoke(factory=factory)
        self.assertIn('archive',caught.exception.receipt['failure_message'])
        self.assertTrue(caught.exception.receipt['services_nonnull'])
        self.assertTrue(caught.exception.receipt['game_created'])
        self.assertIsNone(caught.exception.receipt['game_initialized'])

    def test_prepared_game_cannot_report_initialized_or_use_foreign_vtable(self):
        for kind in ('flag','vtable'):
            self.fixture();original=self.native_factory
            def factory(*args):
                fn=original(*args)
                if args[2]==0x38:return fn
                def wrong(ctx):
                    fn(ctx)
                    game=self.archive_pointer-0x20
                    if kind=='flag':self.put(game+source.GAME_INITIALIZED_OFFSET,b'\1')
                    else:self.q(game,self.base+0x8d7360)
                return wrong
            with self.subTest(kind=kind),self.assertRaises(prepare.XP2PrepareError) as caught:
                self.invoke(factory=factory)
            self.assertIn('Game vtable/initialized',caught.exception.receipt['failure_message'])


if __name__=='__main__':unittest.main()
