"""Shared +120 copy/relink owner on byte-map/native-call fixtures, no DLL.

The actual source guard, owner checks, topology, provider and indexed snapshots
run. Only native instructions and the not-yet-qualified XP2 Lua readback are
fixture boundaries. This cannot construct/admit an XP2 Load session.
"""
from contextlib import contextmanager
import ctypes as C
from dataclasses import replace
import struct
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch

from civ6_host.runtime import configuration_profiles as profiles
from civ6_host.runtime import xp2_configuration_profile as xp2
from civ6_host.runtime.native import native_checkpoint_load as loader
from civ6_host.runtime.native import native_application_configuration as app
from civ6_host.runtime.saved_load_profiles import require_saved_load_admission
from test_xp2_configuration_owner_codec import XP2Fixture,XP2


class CopyFixture(XP2Fixture):
    def __init__(self):
        super().__init__()
        self.clone()
        self.game=self.context+0x390000
        self.copy_calls=[];self.getter_calls=[];self.corruption=None;self.readback_calls=0
        self.qword(self.inner+0x50,self.context+0x700000)
        self.qword(self.inner+0x58,self.context+0x710000)
        self.qword(self.inner+0x60,self.game)
        self.qword(self.game,self.base+XP2.load.game_vtable_rva)
        for table,slot,target in XP2.load.virtual_targets:
            self.qword(self.base+table+slot,self.base+target)
        for body in profiles.context_copy_source(XP2.load).values():
            for fragment in body['fragments']:
                for row in fragment['instructions']:
                    self.put(self.base+int(row['va'],16)-0x180000000,bytes.fromhex(row['bytes']))
        self.backend=object.__new__(loader.NativeLoadBackend)
        b=self.backend
        b.core=self.core;b.context=self.context;b.owner=self.owner;b.runtime=self;b.thread=self.thread()
        b.load_abi=XP2.load;b.stage='prefix-installed';b.poisoned=False;b.destroyed=False
        b.prefix=NS(configuration_readback_verified=False,
                    verify_configuration_scalar_marshalling=self.lua_readback_fixture)

    def lua_readback_fixture(self):
        self.readback_calls+=1
        self.backend.prefix.configuration_readback_verified=self.corruption!='readback'

    def function(self,result,*types):
        def at(address):
            def invoke(*args):
                if address==self.base+XP2.load.copy_rva:
                    assert result is None and types==(C.c_void_p,C.c_void_p)
                    assert args==(self.context,self.owner.pointer)
                    self.copy_calls.append((address,args))
                    # The older clone fixture allocates by provider-count. A
                    # second assignment to existing A needs fresh child addresses
                    # without creating another provider just to bump that count.
                    copied={}
                    for i,key in enumerate(self.providers[self.owner.pointer]):
                        pointer=self.context+0x500000+i*0x100
                        self.qword(pointer,self.base+XP2.vtable_rva)
                        copied[key]=self._variant(key,pointer)
                    self.providers[self.descriptor]=copied
                    snapshot=app.provider_snapshot(self.base,self.descriptor,self.read,self.call,core_sha256=XP2.core_sha256)
                    self.qword(self.setup+0x88,snapshot['normalized'])
                    self.qword(self.setup+0xc30,snapshot['map_normalized'])
                    begin=struct.unpack('<Q',self.read(self.setup+0x90,8))[0]
                    for i,pointer in enumerate(snapshot['players']):
                        self.qword(begin+i*0x20+0x10,pointer)
                    if self.corruption=='indexed':self.qword(begin+7*0x20+0x10,0)
                    if self.corruption=='alias':
                        # Preserve A/index equality while introducing a forbidden A/B submap alias.
                        node=self.providers[self.descriptor][self.root_key]
                        self.qword(node+8,self.owner.snapshot()['normalized'])
                        self.qword(self.setup+0x88,self.owner.snapshot()['normalized'])
                    return None
                if address==self.base+XP2.load.game_initialized_rva:
                    assert result is C.c_uint32 and types==(C.c_void_p,) and args==(self.game,)
                    self.getter_calls.append(address)
                    return int(self.corruption=='initialized')
                assert types and types[0] is C.c_void_p
                return self.call(address,result,tuple(types[1:]),*args)
            return invoke
        return at

    @contextmanager
    def native_call_fixture(self):
        with patch.object(C,'WINFUNCTYPE',self.function):yield


class XP2ConfigurationCopyTests(unittest.TestCase):
    def test_shared_copy_relinks_64_actual_records_keeps_b_disjoint_and_uses_xp2_entry(self):
        f=CopyFixture();before=f.owner.snapshot()
        with f.native_call_fixture():receipt=f.backend.copy_b_to_a()
        self.assertEqual(receipt['core_player_records_reacquired'],64)
        self.assertEqual(receipt['distinct_submaps'],66)
        self.assertFalse(receipt['new_game_called'])
        self.assertEqual(f.owner.snapshot(),before)
        self.assertEqual(f.copy_calls,[(f.base+0x591740,(f.context,f.owner.pointer))])
        self.assertEqual(f.backend.stage,'copied')
        self.assertEqual(f.readback_calls,1)
        verified=profiles.verify_context_copy(XP2.load,f.base,f.read)
        self.assertEqual(verified['source_sha256'],xp2.COPY_SOURCE[1])
        self.assertFalse(verified['native_call_made'])

    def test_wrong_owner_thread_live_bytes_virtual_target_and_initialized_game_refuse_before_copy(self):
        for fault in ('owner','thread','bytes','virtual','initialized'):
            with self.subTest(fault=fault):
                f=CopyFixture()
                if fault=='owner':f.owner.context+=1
                elif fault=='thread':f.backend.thread=(-1,-1)
                elif fault=='bytes':f.put(f.base+XP2.load.copy_rva,b'\x90')
                elif fault=='virtual':f.qword(f.base+XP2.load.outer_vtable_rva+0x120,0)
                else:f.corruption='initialized'
                with f.native_call_fixture(),self.assertRaises((ValueError,RuntimeError)):
                    f.backend.copy_b_to_a()
                self.assertEqual(f.copy_calls,[])
                self.assertEqual(f.readback_calls,0)

    def test_index_alias_and_unqualified_readback_do_not_promote_state_after_copy(self):
        for fault in ('indexed','alias','readback'):
            with self.subTest(fault=fault):
                f=CopyFixture();f.corruption=fault
                with f.native_call_fixture(),self.assertRaises((ValueError,RuntimeError)):
                    f.backend.copy_b_to_a()
                self.assertEqual(len(f.copy_calls),1)
                self.assertEqual(f.backend.stage,'prefix-installed')

    def test_source_profile_identity_exact_types_and_load_admission_stay_strict(self):
        for profile in (replace(XP2.load),profiles.configuration_abi(profiles.BASE_CORE_SHA256).load,None):
            with self.subTest(profile=profile),self.assertRaises(ValueError):xp2.context_copy_source(profile)
        with self.assertRaises(ValueError):require_saved_load_admission(XP2.load)
        proof=profiles._copy(xp2._source(xp2.COPY_SOURCE))
        proof['abi']['record_count']=64.0
        original=xp2._source
        with patch.object(xp2,'_source',side_effect=lambda ref:proof if ref==xp2.COPY_SOURCE else original(ref)):
            with self.assertRaisesRegex(ValueError,'source/ABI differs'):xp2.context_copy_source(XP2.load)


if __name__=='__main__':unittest.main()
