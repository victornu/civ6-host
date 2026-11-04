"""Synthetic provider calls and local stream callbacks, never GameCore execution."""
import ctypes as C
from dataclasses import replace
import hashlib
import struct
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from civ6_host.runtime import configuration_profiles as profiles
from civ6_host.runtime.native import native_application_configuration as app
from civ6_host.runtime.native import native_checkpoint_provider as codec
from civ6_host.runtime.native import native_configuration_finalization as setup
from civ6_host.runtime.native import native_checkpoint_load as loader
from configuration_cases.test_native_application_configuration import ApplicationDouble
from configuration_cases.test_native_checkpoint_provider import Fixture, PAYLOAD, BUDGET


BASE = profiles.configuration_abi(profiles.BASE_CORE_SHA256)
XP1 = profiles.configuration_abi(profiles.XP1_CORE_SHA256)


def add_source_bytes(fake):
    application = app.verify_source(core_sha256=XP1.core_sha256)
    for body in application['core_functions'].values():
        for fragment in body['fragments']:
            for row in fragment['instructions']:
                fake.put(fake.base + int(row['va'],16) - 0x180000000, bytes.fromhex(row['bytes']))
    for row in codec._instructions(codec.verify_source(core_sha256=XP1.core_sha256)['captures']['core']):
        fake.put(fake.base + int(row['va'],16) - 0x180000000, bytes.fromhex(row['bytes']))


class XPApplicationDouble(ApplicationDouble):
    def __init__(self):
        super().__init__()
        self.xp_calls = []
        self.qword(self.context,self.base+XP1.load.outer_vtable_rva)
        self.qword(self.inner,self.base+XP1.load.inner_vtable_rva)
        for slot,target in ((0x38,XP1.initialized_getter_rva),*XP1.preparation):
            self.qword(self.base+XP1.load.outer_vtable_rva+slot,self.base+target)
        for slot,target in ((0x58,XP1.lookup_rva),(0x130,XP1.uint_setter_rva),
                            (0x178,XP1.copy_rva),(0x1D0,XP1.assign_rva)):
            self.qword(self.base+XP1.vtable_rva+slot,self.base+target)
        for pointer in (self.descriptor,self.normalized,self.map_normalized,*self.player_pointers()):
            self.qword(pointer,self.base+XP1.vtable_rva)
        self.put(self.base+XP1.root_key_rva,struct.pack('<I',self.root_key))
        self.put(self.base+XP1.map_key_rva,struct.pack('<I',self.map_key))
        for index,key in enumerate(self.player_keys):
            self.put(self.base+XP1.player_key_table_rva+index*0x44,struct.pack('<I',key))
        add_source_bytes(self)

    def call(self,address,result,args,receiver,*values):
        # Construction of the retained fixture still validates its Base source.
        if not hasattr(self,'xp_calls'):
            return super().call(address,result,args,receiver,*values)
        self.xp_calls.append((address-self.base,result,args,receiver,values))
        mapping={getattr(XP1,field):getattr(BASE,field) for field in
                 ('initialized_getter_rva','lookup_rva','constructor_rva','assign_rva','destructor_rva')}
        if address-self.base not in mapping:
            raise AssertionError('Unmodelled XP native call')
        value=super().call(self.base+mapping[address-self.base],result,args,receiver,*values)
        if address==self.base+XP1.constructor_rva:
            self.qword(receiver,self.base+XP1.vtable_rva)
        if address==self.base+XP1.assign_rva:
            for pointer in self.last_clone_pointers:
                self.qword(pointer,self.base+XP1.vtable_rva)
        return value

    def clone(self):
        return app.NativeApplicationConfiguration(SimpleNamespace(_handle=self.base),self.context,
                    read=self.read,call=self.call,core_sha256=XP1.core_sha256)


class XPCodecFixture(Fixture):
    def __init__(self):
        super().__init__(codec.verify_source())
        self.owner._configuration_abi=XP1
        self.putq(self.context,self.base+XP1.load.outer_vtable_rva)
        self.putq(self.inner,self.base+XP1.load.inner_vtable_rva)
        C.memmove(self.owner.pointer,struct.pack('<Q',self.base+XP1.vtable_rva),8)
        for pointer in (self.a,*(self.a_children+i*0x100 for i in range(66)),
                        *(self.b_children+i*0x100 for i in range(66))):
            self.putq(pointer,self.base+XP1.vtable_rva)
        for slot,target in XP1.codec_slots:
            self.putq(self.base+XP1.vtable_rva+slot,self.base+target)
        add_source_bytes(self)
        self.xp_calls=[]

    def snapshot(self,base,pointer,read,*,core_sha256):
        if core_sha256!=XP1.core_sha256:
            raise AssertionError('Snapshot used another engine')
        return super().snapshot(base,pointer,read)

    def invoke(self,address,pointer,stream,mode):
        slot=0x1F0 if mode=='writer' else 0x1E8
        if address!=self.base+dict(XP1.codec_slots)[slot]:
            raise AssertionError('Codec selected another engine address')
        self.xp_calls.append((address,pointer,mode))
        return super().invoke(self.base+dict(BASE.codec_slots)[slot],pointer,stream,mode)


class ConfigurationProfileTests(unittest.TestCase):
    def test_xp1_sources_have_full_bodies_and_layout_joins(self):
        self.assertIs(profiles.require_owner_profile(XP1),XP1)
        source=app.verify_source(core_sha256=XP1.core_sha256)
        self.assertEqual(len(source['player_keys']),64)
        self.assertEqual(set(app._LIVE)-set(source['core_functions']),set())
        self.assertEqual(len(source['additional_live_names']),4)
        bodies=codec.verify_source(core_sha256=XP1.core_sha256)['captures']['core']
        self.assertEqual(len(bodies),8)
        counts={key:sum(len(bytes.fromhex(row['bytes'])) for f in body['fragments'] for row in f['instructions'])
                for key,body in bodies.items()}
        self.assertEqual(counts['provider_slot_0x1e8'],852)
        self.assertEqual(counts['provider_slot_0x1f0'],134)

    def test_unknown_and_forged_owner_refuse_without_calls(self):
        for sha in ('0'*64,None):
            with self.assertRaises(ValueError):profiles.configuration_abi(sha)
        with self.assertRaises(ValueError):profiles.require_owner_profile(replace(XP1))
        with patch.object(codec,'_Runtime') as runtime:
            with self.assertRaises(ValueError):codec._Session(SimpleNamespace(_handle=1),1,object(),4096,10)
            runtime.assert_not_called()
        with patch.object(loader.configuration._NativeBackend,'__init__') as parent:
            with self.assertRaisesRegex(ValueError,'Expansion saved Load is not admitted'):
                loader.NativeLoadBackend(None,None,None,None,SimpleNamespace(core_sha256=XP1.core_sha256),{},None)
            parent.assert_not_called()

    def test_xp1_clone_player_and_destroy_use_real_abi_addresses(self):
        fake=XPApplicationDouble();source=app.provider_snapshot(fake.base,fake.descriptor,fake.read,
                                                            fake.call,core_sha256=XP1.core_sha256)
        owner=fake.clone()
        self.assertIs(owner._configuration_abi,XP1)
        clone=owner.snapshot()
        self.assertFalse(set(source['players']) & set(clone['players']))
        self.assertEqual(owner.player(17)['pointer'],clone['players'][17])
        owner.close()
        self.assertTrue(owner.closed)
        rv={row[0] for row in fake.xp_calls}
        self.assertTrue({XP1.constructor_rva,XP1.assign_rva,XP1.lookup_rva,XP1.destructor_rva}<=rv)

    def test_xp1_corrupt_key_or_code_refuses_before_clone(self):
        for field in ('key','code'):
            fake=XPApplicationDouble()
            address=fake.base+(XP1.player_key_table_rva if field=='key' else XP1.constructor_rva)
            fake.put(address,b'\x00'*4)
            with self.assertRaises(ValueError):fake.clone()
            self.assertNotIn(XP1.constructor_rva,{call[0] for call in fake.xp_calls})

    def test_xp1_same_bounded_stream_pipeline_restore_serialize_and_seal(self):
        fake=XPCodecFixture()
        with patch.object(codec,'_Runtime',return_value=fake), \
             patch.object(codec.application,'provider_snapshot',fake.snapshot):
            restored=codec.restore_provider(fake.core,fake.context,fake.owner,PAYLOAD,
                    expected_sha256=hashlib.sha256(PAYLOAD).hexdigest(),**BUDGET)
            output,saved=codec.serialize_provider(fake.core,fake.context,fake.owner,**BUDGET)
            self.assertEqual(output,PAYLOAD)
            for receipt in (restored,saved):
                self.assertEqual(receipt['core_sha256'],XP1.core_sha256)
                self.assertEqual(receipt['proof_sha256'],profiles.LIVE_SOURCE[1])
                self.assertFalse(receipt['native_return_interpreted'])
            codec.seal_restoration(fake.core,fake.context,fake.owner,**BUDGET)
            with self.assertRaisesRegex(ValueError,'unused owned B'):
                codec.restore_provider(fake.core,fake.context,fake.owner,PAYLOAD,
                        expected_sha256=hashlib.sha256(PAYLOAD).hexdigest(),**BUDGET)
            self.assertEqual([row[2] for row in fake.xp_calls],['reader','writer'])

    def test_xp1_owner_engine_or_slot_change_refused_before_stream(self):
        for fault in ('owner','slot'):
            fake=XPCodecFixture()
            with patch.object(codec,'_Runtime',return_value=fake), \
                 patch.object(codec.application,'provider_snapshot',fake.snapshot):
                state=codec._session(fake.core,fake.context,fake.owner,**BUDGET)
                if fault=='owner':fake.owner._configuration_abi=BASE
                else:fake.putq(fake.base+XP1.vtable_rva+0x1E8,fake.base+dict(BASE.codec_slots)[0x1E8])
                with self.assertRaises(ValueError):state.execute('writer')
                self.assertFalse(fake.xp_calls)


if __name__=='__main__':
    unittest.main()
