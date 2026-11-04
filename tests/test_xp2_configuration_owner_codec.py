"""Compose the shared owner and codec on explicit memory/call fixtures.

No GameCore is loaded. The actual linked-snapshot, provider lookup, owner,
stream state, guards and Win64Stream callbacks are exercised. Fixture bytes
are not claimed to be a native XP2 serialized configuration.
"""
import contextlib
import ctypes as C
from dataclasses import replace
import hashlib
import struct
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from civ6_host.runtime import configuration_profiles as profiles
from civ6_host.runtime import xp2_configuration_profile as xp2
from civ6_host.runtime.native import native_application_configuration as app
from civ6_host.runtime.native import native_configuration_finalization as setup
from civ6_host.runtime.native import native_checkpoint_provider as codec
from civ6_host.runtime.native import native_checkpoint_load as loader
from configuration_cases.test_native_application_configuration import ApplicationDouble
from configuration_cases.test_native_checkpoint_provider import Fixture as StreamFixture, PAYLOAD, BUDGET

BASE=profiles.configuration_abi(profiles.BASE_CORE_SHA256)
XP2=profiles.configuration_abi(profiles.XP2_CORE_SHA256)


class XP2Fixture(ApplicationDouble):
    """Reuse the Base memory/call model, selecting every actual entry by XP2 ABI."""
    def __init__(self,*,corrupt_clone_guard=False):
        super().__init__(corrupt_clone_guard=corrupt_clone_guard)
        self.xp_calls=[];self.codec_calls=[];self.fault=None
        self.thread_id=(threading.get_ident(),777)
        self.core=SimpleNamespace(_handle=self.base)
        self.qword(self.context,self.base+XP2.load.outer_vtable_rva)
        self.qword(self.inner,self.base+XP2.load.inner_vtable_rva)
        self.qword(self.inner+0x60,0)
        for slot,target in ((0x38,XP2.initialized_getter_rva),*XP2.preparation):
            self.qword(self.base+XP2.load.outer_vtable_rva+slot,self.base+target)
        for slot,target in ((0x58,XP2.lookup_rva),(0x130,XP2.uint_setter_rva),
                            (0x178,XP2.copy_rva),(0x1d0,XP2.assign_rva),*XP2.codec_slots):
            self.qword(self.base+XP2.vtable_rva+slot,self.base+target)
        for pointer in (self.descriptor,self.normalized,self.map_normalized,*self.player_pointers()):
            self.put(pointer,struct.pack('<Q',self.base+XP2.vtable_rva)+bytes(0x50))
        # Keep MAP_ROOT's source key, rather than the old fixture's dummy key.
        node=self.providers[self.descriptor].pop(self.map_key)
        self.map_key=0x7dd11279
        self.providers[self.descriptor][self.map_key]=node
        self.put(self.base+XP2.root_key_rva,struct.pack('<I',self.root_key))
        self.put(self.base+XP2.map_key_rva,struct.pack('<I',self.map_key))
        for index,key in enumerate(self.player_keys):
            self.put(self.base+XP2.player_key_table_rva+index*0x44,struct.pack('<I',key))
        # This embedded provider is distinct from the keyed MAP_ROOT value.
        self.qword(self.setup+0xc38,self.base+XP2.vtable_rva)
        for proof in (app.verify_source(core_sha256=XP2.core_sha256),
                      codec.verify_source(core_sha256=XP2.core_sha256)):
            for row in codec._instructions(proof):
                self.put(self.base+int(row['va'],16)-0x180000000,bytes.fromhex(row['bytes']))

    def call(self,address,result,args,receiver,*values):
        if not hasattr(self,'xp_calls'):
            return super().call(address,result,args,receiver,*values)
        self.xp_calls.append((address-self.base,result,args,receiver,values))
        mapping={getattr(XP2,k):getattr(BASE,k) for k in
                 ('initialized_getter_rva','lookup_rva','constructor_rva','assign_rva','destructor_rva')}
        if address-self.base not in mapping:raise AssertionError('Unmodelled XP2 entry')
        if address==self.base+XP2.initialized_getter_rva:
            self.assert_getter_signature=(result,args,receiver,values)
            assert self.assert_getter_signature==(C.c_bool,(),self.context,())
            return self.initialized
        returned=super().call(self.base+mapping[address-self.base],result,args,receiver,*values)
        if address==self.base+XP2.constructor_rva:
            self.put(receiver,struct.pack('<Q',self.base+XP2.vtable_rva)+bytes(0x50))
        elif address==self.base+XP2.assign_rva:
            for pointer in self.last_clone_pointers:
                self.put(pointer,struct.pack('<Q',self.base+XP2.vtable_rva)+bytes(0x50))
        return returned

    def clone(self,**kwargs):
        self.owner=app.NativeApplicationConfiguration(self.core,self.context,read=self.read,
                    call=self.call,core_sha256=XP2.core_sha256,**kwargs)
        self.core._civ6rl_application_configuration=self.owner
        return self.owner

    def thread(self):return (threading.get_ident(),self.thread_id[1])

    def image(self,base,proof):
        assert base==self.base and proof['images']['core']['sha256']==XP2.core_sha256
        self.image_checked=True
        return proof['images']['core']['path']

    def invoke(self,address,pointer,stream,mode):
        slot=0x1f0 if mode=='writer' else 0x1e8
        assert address==self.base+dict(XP2.codec_slots)[slot]
        self.codec_calls.append((address,pointer,mode))
        # Reuse local stream callback mechanics; no native provider code executes.
        return StreamFixture.invoke(self,self.base+dict(BASE.codec_slots)[slot],pointer,stream,mode)

    @contextlib.contextmanager
    def codec_runtime(self):
        self.owner.call=None  # Production codec deliberately refuses injected owner.call.
        def invoke(call,address,result,receiver,arg_types=(),*args):
            assert call is None
            return self.call(address,result,tuple(arg_types),receiver,*args)
        with patch.object(codec,'_Runtime',return_value=self),patch.object(setup,'_invoke',invoke):
            try:yield
            finally:self.owner.call=self.call


class XP2OwnerCodec(unittest.TestCase):
    def setUp(self):
        codec._STATES.clear();self.addCleanup(codec._STATES.clear)

    def test_real_owner_linked_map_players_and_close_select_xp2_only(self):
        f=XP2Fixture();source=setup._linked_snapshot(f.base,f.context,f.read,f.call,core_sha256=XP2.core_sha256)
        owner=f.clone();clone=owner.snapshot()
        self.assertIs(owner._configuration_abi,XP2)
        self.assertEqual(owner.player(63)['pointer'],clone['players'][63])
        self.assertEqual(source['map_normalized'],f.map_normalized)
        self.assertNotEqual(source['map_normalized'],f.setup+0xc38)
        self.assertFalse(set(clone['players'])&set(source['players']))
        owner.close()
        self.assertTrue(owner.closed)
        calls={r[0] for r in f.xp_calls}
        self.assertEqual(calls,{XP2.initialized_getter_rva,XP2.lookup_rva,XP2.constructor_rva,
                               XP2.assign_rva,XP2.destructor_rva})
        self.assertEqual(sum(r[0]==XP2.destructor_rva for r in f.xp_calls),1)
        with self.assertRaisesRegex(RuntimeError,'closed'):owner.close()

    def test_restore_save_seal_use_actual_shared_snapshots_and_bounded_stream(self):
        f=XP2Fixture();owner=f.clone()
        before=owner.snapshot()
        with f.codec_runtime():
            restored=codec.restore_provider(f.core,f.context,owner,PAYLOAD,
                    expected_sha256=hashlib.sha256(PAYLOAD).hexdigest(),**BUDGET)
            output,saved=codec.serialize_provider(f.core,f.context,owner,**BUDGET)
            codec.seal_restoration(f.core,f.context,owner,**BUDGET)
            with self.assertRaisesRegex(ValueError,'unused owned B'):
                codec.restore_provider(f.core,f.context,owner,PAYLOAD,
                    expected_sha256=hashlib.sha256(PAYLOAD).hexdigest(),**BUDGET)
            self.assertEqual(owner.snapshot(),before)
        self.assertEqual(output,PAYLOAD);self.assertEqual(f.restored_bytes,PAYLOAD)
        self.assertEqual([r[2] for r in f.codec_calls],['reader','writer'])
        self.assertTrue(f.image_checked)
        state=codec._STATES[id(owner)]
        self.assertTrue(all(stream.transport.closed for stream in state.streams))
        for receipt in (restored,saved):
            self.assertEqual(receipt['core_sha256'],XP2.core_sha256)
            self.assertEqual(receipt['proof_sha256'],xp2.SOURCE[1])
            self.assertFalse(receipt['native_return_interpreted'])
        owner.close()

    def test_wrong_map_record_key_slot_code_or_boolean_refuses_before_allocation(self):
        for fault in ('embedded','record_owner','key','slot','inner_getter','bool'):
            f=XP2Fixture()
            if fault=='embedded':f.qword(f.setup+0xc30,f.setup+0xc38)
            elif fault=='record_owner':f.qword(f.setup+0xb8+0x18,f.setup+1)
            elif fault=='key':f.put(f.base+XP2.map_key_rva,struct.pack('<I',0xb8c4c8))
            elif fault=='slot':f.qword(f.base+XP2.vtable_rva+0x58,f.base+BASE.lookup_rva)
            elif fault=='inner_getter':f.put(f.base+0x46290,b'\0')
            else:f.initialized=1
            with self.subTest(fault=fault),self.assertRaises((ValueError,LookupError)):
                f.clone()
            self.assertNotIn(XP2.constructor_rva,[r[0] for r in f.xp_calls])

    def test_partial_copy_guard_stays_owned_and_postcopy_failure_closes_once(self):
        f=XP2Fixture(corrupt_clone_guard=True)
        with self.assertRaisesRegex(RuntimeError,'storage') as caught:f.clone()
        partial=caught.exception.native_configuration_owner
        self.assertFalse(partial.closed)
        self.assertNotIn(XP2.destructor_rva,[r[0] for r in f.xp_calls])
        # No guessed rollback of a possibly damaged native object.
        with self.assertRaisesRegex(RuntimeError,'storage'):partial.close()
        f=XP2Fixture()
        def fail(*args,**kwargs):raise RuntimeError('fixture emitter failure')
        with self.assertRaisesRegex(RuntimeError,'emitter failure') as caught:f.clone(emit=fail)
        self.assertTrue(caught.exception.native_configuration_owner.closed)
        self.assertEqual(sum(r[0]==XP2.destructor_rva for r in f.xp_calls),1)

    def test_codec_refuses_changed_identity_thread_canary_or_live_game_before_calls(self):
        for fault in ('abi','core_owner','slot','thread','canary','game','borrowed_call'):
            codec._STATES.clear();f=XP2Fixture();owner=f.clone()
            with f.codec_runtime():
                state=codec._session(f.core,f.context,owner,**BUDGET)
                if fault=='abi':owner._configuration_abi=replace(XP2)
                elif fault=='core_owner':f.core._civ6rl_application_configuration=object()
                elif fault=='slot':f.qword(f.base+XP2.vtable_rva+0x1e8,f.base+dict(BASE.codec_slots)[0x1e8])
                elif fault=='thread':f.thread_id=(f.thread_id[0],778)
                elif fault=='canary':C.c_uint8.from_address(owner.pointer-1).value=0
                elif fault=='game':f.qword(f.inner+0x60,f.context+0x99900)
                else:owner.call=f.call
                with self.subTest(fault=fault),self.assertRaises((ValueError,RuntimeError)):
                    state.execute('reader',PAYLOAD,hashlib.sha256(PAYLOAD).hexdigest())
                self.assertFalse(f.codec_calls);self.assertFalse(state.streams)

    def test_exact_integer_domains_and_saved_load_remain_closed(self):
        f=XP2Fixture()
        for bad in (True,False,float(f.context),0,-1):
            with self.subTest(context=bad),self.assertRaises(ValueError):
                app.NativeApplicationConfiguration(f.core,bad,read=f.read,call=f.call,
                                                   core_sha256=XP2.core_sha256)
        owner=f.clone()
        for bad in (True,False,1.0,-1,64):
            with self.assertRaises(ValueError):owner.player(bad)
        with patch.object(codec,'_Runtime') as runtime:
            for bad in (True,1.0,0,-1):
                with self.assertRaises(ValueError):codec._Session(f.core,f.context,owner,bad,32)
            runtime.assert_not_called()
        with patch.object(loader.configuration._NativeBackend,'__init__') as parent:
            with self.assertRaisesRegex(ValueError,'Expansion saved Load is not admitted'):
                loader.NativeLoadBackend(None,None,None,None,SimpleNamespace(core_sha256=XP2.core_sha256),{},None)
            parent.assert_not_called()
        self.assertEqual(len(profiles.context_copy_source(XP2.load)),14)
        owner.close()


if __name__=='__main__':unittest.main()
