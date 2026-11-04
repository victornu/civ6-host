"""Shared HOST78 callback and real Init-mask ordering; no engine execution."""
import ctypes as C
import os
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

HOST=Path(__file__).resolve().parents[1]
os.environ.setdefault('CIV6_HOST_RESOURCE_ROOT',str(HOST.parent/'civ6-rl-lab'))
sys.path.insert(0,str(HOST/'src'))
from civ6_host.runtime import xp1_host_slot78 as profile
from civ6_host.runtime.configuration_profiles import XP1_CORE_SHA256,_body
from civ6_host.runtime.native.native_host import DiagnosticHost
from civ6_host.runtime.native.native_xp1_context_init import _rebind_unapproved_host_callbacks
from civ6_host.runtime.saved_load_services import SavedLoadServices


class HostFixture(DiagnosticHost):
    def __init__(self):
        self.vtable=(C.c_void_p*128)()
        self.aux_vtable=(C.c_void_p*32)()
        self.logger_vtable=(C.c_void_p*32)()
        self.registrar_vtable=(C.c_void_p*3)()
        self.descriptor_vtable=(C.c_void_p*32)()
        self.object=(C.c_void_p*2)(C.addressof(self.vtable),1)
        self._slot_bindings={};self.serial=0;self.emit=Mock()
        for name in ('vtable','aux_vtable','logger_vtable','registrar_vtable','descriptor_vtable'):
            table=getattr(self,name)
            for index in range(len(table)):
                self._bind(table,index*8,None,[],self.fixture_admitted)
        self._bind(self.vtable,0x78,C.c_uint32,[C.c_void_p,C.c_uint32],self._constant_zero_slot78)

    def fixture_admitted(self,*args):
        raise AssertionError('Fixture binding must never be invoked')

    def _bind(self,table,offset,result,args,callback):
        self.serial+=1;pointer=0x400000+self.serial*16
        table[offset//8]=pointer
        self._slot_bindings[C.addressof(table),offset]=(pointer,callback)
        self.last_signature=(result,args)


def fixture():
    host=HostFixture()
    _rebind_unapproved_host_callbacks(host)
    memory={};proof=profile.verify_source()
    for fragment in _body(proof['xp1_consumer'])['fragments']:
        for row in fragment['instructions']:
            for i,value in enumerate(bytes.fromhex(row['bytes'])):memory[int(row['va'],16)+i]=value
    for i,value in enumerate(host.pointer.to_bytes(8,'little')):memory[0x1809f2640+i]=value
    backend=SimpleNamespace(host=host,load_abi=SimpleNamespace(core_sha256=XP1_CORE_SHA256),
        stage='prepared',prefix=None,busy=True,poisoned=False,destroyed=False,
        _saved_load_candidate=True,_xp1_commands_requested=True,core=SimpleNamespace(_handle=0x180000000),
        runtime=SimpleNamespace(read=lambda p,n:bytes(memory[p+i] for i in range(n))),
        check_thread=Mock(),emit=Mock())
    return backend,memory


def composed(backend):
    host=backend.host
    for interface,(table_name,slots) in profile.REQUIRED.items():
        for slot in slots:
            if interface=='host' and slot==0x78:continue
            host._bind(getattr(host,table_name),slot,None,[],host.fixture_admitted)
    services=object.__new__(SavedLoadServices)
    services.backend=backend;services.host=host;services.closed=services.quarantined=False
    host._saved_load_services=services
    scalar=SimpleNamespace(host=host,closed=False,address=0x555500,function=C.c_void_p(0x555500))
    services.scalars=host._scalar_service_owner=scalar
    host.aux_vtable[0xA0//8]=scalar.address
    maps=SimpleNamespace(host=host,closed=False,bindings=[
        (0xA8,0x555508,None,C.c_void_p(0x555508)),(0xB0,0x555510,None,C.c_void_p(0x555510))])
    services.maps=host._map_service_owner=maps
    for slot,address,previous,function in maps.bindings:host.aux_vtable[slot//8]=address
    return services


class Slot78Tests(unittest.TestCase):
    def test_source_and_live_guards(self):
        pins=profile.source_dependencies()
        self.assertIn(len(pins),(5,7)) # exact original adapter or explicitly pinned class-preserving transition
        backend,memory=fixture()
        self.assertGreater(profile.verify_live(backend.core._handle,backend.runtime.read,backend.host.pointer),0)
        with self.assertRaises(ValueError):
            profile.verify_live(backend.core._handle,backend.runtime.read,backend.host.pointer+8)
        memory[0x1800409de]^=1
        with self.assertRaises(ValueError):profile.install(backend)
        self.assertFalse(hasattr(backend,'_xp1_slot78'))

    def test_real_mask_then_restore_only_shared78(self):
        backend,_=fixture();host=backend.host
        binding=host._slot_bindings[C.addressof(host.vtable),0x78]
        self.assertEqual(binding[1]._native_unavailable,('host',0x78))
        before=dict(host._slot_bindings)
        receipt=profile.install(backend)
        changed={key for key,value in host._slot_bindings.items() if before.get(key)!=value}
        self.assertEqual(changed,{(C.addressof(host.vtable),0x78)})
        self.assertEqual(host.last_signature,(C.c_uint32,[C.c_void_p,C.c_uint32]))
        callback=host._slot_bindings[C.addressof(host.vtable),0x78][1]
        self.assertIs(callback.__func__,DiagnosticHost._constant_zero_slot78)
        for key in (0x4fc6296a,0x715c87d1,0x12345678):
            self.assertEqual(callback(host.pointer,key),0)
        with self.assertRaises(ValueError):callback(host.pointer+8,1)
        with self.assertRaises(ValueError):profile.install(backend)
        self.assertIs(receipt['unknown_service_fallback'],False)

    def test_final_composition_checks_actual_entries_and_native_owners(self):
        backend,_=fixture();services=composed(backend)
        with self.assertRaisesRegex(ValueError,'host\\+0x78'):
            profile.require_composed_callbacks(backend,services)
        profile.install(backend)
        receipt=profile.require_composed_callbacks(backend,services)
        self.assertIs(receipt['semantic_qualification_inferred'],False)
        self.assertEqual(receipt['callback_count'],sum(len(slots) for table,slots in profile.REQUIRED.values())+3)
        host=backend.host
        for name,slot,interface in (('logger_vtable',0x50,'logger'),
                ('registrar_vtable',0,'type registrar'),('descriptor_vtable',0,'autoarchive registry'),
                ('aux_vtable',0x60,'auxiliary')):
            table=getattr(host,name);key=(C.addressof(table),slot);prior=host._slot_bindings[key]
            host._bind(table,slot,None,[C.c_void_p],host._unsupported(interface,slot))
            with self.assertRaises(ValueError):profile.require_composed_callbacks(backend,services)
            table[slot//8]=prior[0];host._slot_bindings[key]=prior
        host.aux_vtable[0xA8//8]+=8
        with self.assertRaisesRegex(ValueError,'native map callback replaced'):
            profile.require_composed_callbacks(backend,services)


if __name__=='__main__':unittest.main(verbosity=2)
