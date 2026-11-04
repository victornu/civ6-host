"""Shared Init dispatch and failure ownership; native calls replaced only here."""
import struct
from types import SimpleNamespace as NS
import unittest
from unittest.mock import Mock
from civ6_host.runtime import context_initialization as shared


class InitError(RuntimeError):
    def __init__(self, receipt, message):
        super().__init__(message)
        self.receipt = receipt


class InitializationTests(unittest.TestCase):
    def fixture(self, family='xp2'):
        base, context, table, inner = 0x70000000, 0x800000, 0x810000, 0x820000
        slots = {40: 0x100, 56: 0x200, 96: 0x300}
        values = [0x180000000 + i * 16 for i in range(13)]
        for slot, rva in slots.items(): values[slot // 8] = 0x180000000 + rva
        vtable_bytes = struct.pack('<13Q', *values)
        live = struct.pack('<13Q', *(base + p - 0x180000000 for p in values))
        host = NS(pointer=0x830000, aux_object=0x840000, logger_object=0x850000,
                  filters=NS(entries={}))
        memory = {context: struct.pack('<Q',table), table: live,
                  context+8: struct.pack('<Q',inner), inner+80: struct.pack('<Q',1),
                  inner+88: struct.pack('<Q',2)}
        for slot,rva in slots.items():memory[table+slot]=struct.pack('<Q',base+rva)
        for rva in (0x500,0x508,0x510):memory[base+rva]=struct.pack('<Q',0)
        state, calls = [False], []
        def read(address,size):
            value = memory[address]
            self.assertEqual(len(value),size)
            return value
        def factory(core,ctx,slot,rva,*abi):
            self.assertEqual((core._handle,ctx,rva),(base,context,slots[slot]))
            if slot==56:return lambda this: state[0]
            if slot==96:
                def setter(this,pointer):
                    calls.append('setter')
                    self.assertEqual(pointer,host.pointer)
                    for rva,p in zip((0x500,0x508,0x510),(host.pointer,host.aux_object,host.logger_object)):
                        memory[base+rva]=struct.pack('<Q',p)
                    host.filters.entries={11:[(12,1)]}
                return setter
            def init(this):calls.append('init');state[0]=True;return True
            return init
        kwargs=dict(profile=NS(ruleset=family,core_sha256='a'*64),source={},input_receipt={},
            callback_receipt={},slots=slots,globals_rvas=(0x500,0x508,0x510),
            declarations=((11,12,1),),vtable_bytes=vtable_bytes,
            context_validator=Mock(),virtual_factory=factory,read=read,emit=Mock(),error_type=InitError)
        return NS(_handle=base),context,host,kwargs,memory,state,calls

    def test_both_profiles_use_the_same_ordered_mechanics(self):
        for family in ('xp1','xp2'):
            core,ctx,host,kwargs,_,_,calls=self.fixture(family)
            receipt=shared.initialize(core,ctx,host,**kwargs)
            self.assertEqual(calls,['setter','init'])
            self.assertEqual(receipt['schema'],'civ6rl.native_'+family+'_context_init_receipt.v1')
            self.assertTrue(receipt['connections']['gameplay_nonnull'])
            self.assertFalse(receipt['game_created'])
            self.assertFalse(receipt['eligible_for_training'])

    def test_changed_dispatch_or_initial_state_never_calls_setter(self):
        for kind in ('dispatch','initialized'):
            core,ctx,host,kwargs,memory,state,calls=self.fixture()
            if kind=='dispatch':memory[0x810000+40]=struct.pack('<Q',core._handle+0x999)
            else:state[0]=True
            with self.assertRaises(ValueError):shared.initialize(core,ctx,host,**kwargs)
            self.assertEqual(calls,[])

    def test_failed_declaration_binding_preserves_partial_native_ownership(self):
        core,ctx,host,kwargs,_,_,calls=self.fixture()
        kwargs['declarations']=((99,12,1),)
        with self.assertRaises(InitError) as caught:shared.initialize(core,ctx,host,**kwargs)
        receipt=caught.exception.receipt
        self.assertEqual(calls,['setter','init'])
        self.assertTrue(receipt['context_may_require_destroy'])
        self.assertTrue(receipt['init_called'])
        self.assertEqual(receipt['status'],'failed')
        self.assertEqual(receipt['failure_phase'],'init')

    def test_installed_global_mismatch_is_detected_before_init(self):
        core,ctx,host,kwargs,memory,_,calls=self.fixture()
        real=kwargs['virtual_factory']
        def broken(*args):
            fn=real(*args)
            if args[2]!=96:return fn
            def call(*a):fn(*a);memory[core._handle+0x508]=struct.pack('<Q',42)
            return call
        kwargs['virtual_factory']=broken
        with self.assertRaises(InitError) as caught:shared.initialize(core,ctx,host,**kwargs)
        self.assertEqual(calls,['setter'])
        self.assertFalse(caught.exception.receipt['init_dispatch_started'])


class XP2ProfileTests(unittest.TestCase):
    def test_retained_sources_select_distinct_xp2_init_and_cleanup(self):
        from civ6_host.runtime import xp2_context_profile as profile
        from civ6_host.runtime.native.native_xp1_context_init import XP1_EVENT_DECLARATIONS
        value=profile.verify_source()
        self.assertEqual(value['declarations'],XP1_EVENT_DECLARATIONS)
        self.assertEqual(len(XP1_EVENT_DECLARATIONS),16)
        self.assertEqual(value['slots'][0x28],0x5905f0)
        self.assertEqual(value['globals_rvas'],(0xb8aa80,0xb8aa88,0xb8aa90))
        self.assertEqual(value['logger_slots'],(0x28,0x40))
        self.assertEqual(value['aligned_free_iat_rva'],0x9b7680)
        self.assertFalse(value['receipt']['saved_load_admitted'])

    def test_missing_capture_or_wrong_engine_refuses_before_native_init(self):
        from civ6_host.runtime.xp2_context_lifecycle import initialize_xp2_context
        with self.assertRaisesRegex(ValueError,'captured input owner'):
            initialize_xp2_context(object(),1,object(),configuration_path='a',
                gameplay_path='b',private_root='.',module_paths=[])


if __name__=='__main__':unittest.main()
