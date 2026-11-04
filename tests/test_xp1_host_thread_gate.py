"""Exercise the retained callbacks with explicit memory/thread fixtures only."""
import ctypes as C
import os
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

HOST=Path(__file__).resolve().parents[1]
os.environ.setdefault('CIV6_HOST_RESOURCE_ROOT',str(HOST.parent/'civ6-rl-lab'))
sys.path.insert(0,str(HOST/'src'))
from civ6_host.runtime import xp1_host_thread_gate as profile
from civ6_host.runtime.configuration_profiles import XP1_CORE_SHA256,_body
from civ6_host.runtime.native import native_host_thread_gate as shared


class HostFixture:
    def __init__(self):
        self.pointer=0x200000
        self.vtable=(C.c_void_p*128)()
        self._slot_bindings={}
        self.emit=Mock()
        self.bindings=[]
        for slot in (0x58,0x60):
            def unavailable(this):raise RuntimeError('strict fixture default')
            unavailable._native_unavailable=('host',slot)
            self._bind(self.vtable,slot,None,[C.c_void_p],unavailable)
        self.bindings.clear()

    def _check(self,this):
        if this!=self.pointer:raise ValueError('foreign host')

    def _bind(self,table,slot,result,args,callback):
        # No ffi callback allocation/invocation. Retain exact supplied signature
        # and call the shared Python body directly in the test below.
        pointer=0x100000+len(self._slot_bindings)*8+slot
        table[slot//8]=pointer
        self._slot_bindings[C.addressof(table),slot]=(pointer,callback)
        self.bindings.append((slot,result,args,callback))


def fixture():
    proof=profile.verify_source()
    memory={}
    for body in proof['functions'].values():
        for fragment in _body(body)['fragments']:
            for row in fragment['instructions']:
                for i,value in enumerate(bytes.fromhex(row['bytes'])):
                    memory[int(row['va'],16)+i]=value
    host=HostFixture()
    for i,value in enumerate(host.pointer.to_bytes(8,'little')):
        memory[0x180000000+proof['host_global_rva']+i]=value
    reader=lambda address,count:bytes(memory[address+i] for i in range(count))
    owner=SimpleNamespace(host=host,load_abi=SimpleNamespace(core_sha256=XP1_CORE_SHA256),
        stage='prepared',prefix=None,destroyed=False,poisoned=False,busy=True,
        _saved_load_candidate=True,check_thread=Mock(),emit=Mock(),
        core=SimpleNamespace(_handle=0x180000000),runtime=SimpleNamespace(read=reader))
    return owner,memory


class ThreadGateTests(unittest.TestCase):
    def test_selected_source_and_live_module_host_identity(self):
        self.assertEqual(len(profile.source_dependencies()),4)
        owner,memory=fixture()
        self.assertGreater(profile.verify_live(owner.core._handle,owner.runtime.read,owner.host.pointer),0)
        with self.assertRaises(ValueError):
            profile.verify_live(owner.core._handle,owner.runtime.read,owner.host.pointer+8)
        memory[0x180050b40]^=1
        with self.assertRaises(ValueError):
            profile.verify_live(owner.core._handle,owner.runtime.read,owner.host.pointer)

    def test_real_shared_algorithm_compares_threads_and_retains_idle_profile(self):
        owner,_=fixture()
        current=Mock(return_value=511)
        with patch.object(C,'WinDLL',return_value=SimpleNamespace(GetCurrentThreadId=current)):
            receipt=profile.install(owner)
            self.assertIs(receipt,owner._xp1_thread_gate)
            self.assertIs(receipt.gate,owner.host.thread_gate)
            callbacks={slot:callback for slot,result,args,callback in owner.host.bindings}
            self.assertEqual(set(callbacks),{0x58,0x60})
            for slot,result,args,callback in owner.host.bindings:
                self.assertIs(result,C.c_bool)
                self.assertEqual(args,[C.c_void_p])
            self.assertIs(callbacks[0x60](owner.host.pointer),True)
            current.return_value=733
            self.assertIs(callbacks[0x60](owner.host.pointer),False)
            self.assertIs(callbacks[0x58](owner.host.pointer),False)
            self.assertIs(receipt.gate.activity_object_present,False)
            self.assertEqual(receipt.gate.activity_count,0)
            for callback in callbacks.values():
                with self.assertRaises(ValueError):callback(owner.host.pointer+8)
            with self.assertRaises(ValueError):profile.install(owner)
        with self.assertRaises(ValueError):
            shared.HostThreadGate(511,shared.PROFILE,activity_object_present=True)

    def test_foreign_profiles_phases_and_existing_slots_refuse_before_binding(self):
        changes=(lambda b:setattr(b.load_abi,'core_sha256','base'),
                 lambda b:setattr(b,'prefix',object()),lambda b:setattr(b,'destroyed',True),
                 lambda b:setattr(b,'stage','xp1-continuation-ready'),
                 lambda b:setattr(b,'busy',False),lambda b:setattr(b,'poisoned',True))
        for change in changes:
            owner,_=fixture();change(owner)
            with patch.object(C,'WinDLL') as dll:
                with self.assertRaises(ValueError):profile.install(owner)
                dll.assert_not_called()
            self.assertEqual(owner.host.bindings,[])
        owner,_=fixture()
        previous=owner.host._slot_bindings[C.addressof(owner.host.vtable),0x60]
        owner.host._slot_bindings[C.addressof(owner.host.vtable),0x60]=(previous[0],lambda this:True)
        with patch.object(C,'WinDLL') as dll:
            with self.assertRaises(ValueError):profile.install(owner)
            dll.assert_not_called()
        self.assertEqual(owner.host.bindings,[])


if __name__=='__main__':unittest.main(verbosity=2)
