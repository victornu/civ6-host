"""Saved-script code/ownership guards against explicit memory fixtures."""
import ctypes as C
import struct
from types import SimpleNamespace as NS
import unittest
from unittest.mock import Mock,patch

from civ6_host.runtime import xp2_saved_script_services as profile
from civ6_host.runtime.configuration_profiles import configuration_abi,XP2_CORE_SHA256
from civ6_host.runtime.saved_load_profiles import profile_for_sha


class Memory:
    base=0x180000000
    context=0x1000000
    inner=0x1100000
    manager=0x1200000
    host=0x1300000
    auxiliary=0x1400000

    def __init__(self):
        self.parts={};abi=profile_for_sha(XP2_CORE_SHA256);self.proof=profile.source()
        for row in self.proof['bodies']:
            self.parts[self.base+row['rva']]=bytearray.fromhex(row['raw_hex'])
        for row in self.proof['slots']:
            self.put(self.base+row['vtable_rva']+row['slot'],self.base+row['target_rva'])
        self.put(self.context,self.base+abi.outer_vtable_rva)
        self.put(self.context+8,self.inner)
        self.put(self.inner,self.base+abi.inner_vtable_rva)
        for name,pointer in (('host',self.host),('auxiliary',self.auxiliary),('inner',self.inner)):
            self.put(self.base+self.proof['contract']['globals'][name],pointer)
        self.put(self.inner+0x1a58,self.manager);self.parts[self.manager]=bytearray(0x30)

    def put(self,address,value):self.parts[address]=bytearray(struct.pack('<Q',value))

    def read(self,address,size):
        for begin,raw in self.parts.items():
            if begin<=address and address+size<=begin+len(raw):
                return bytes(raw[address-begin:address-begin+size])
        raise ValueError(('Unmapped fixture read',address,size))

    def verify(self):
        return profile.verify_live(self.base,self.read,context=self.context,inner=self.inner,
            host_pointer=self.host,auxiliary_pointer=self.auxiliary)


class XP2SavedScriptProfileTests(unittest.TestCase):
    def test_live_ranges_slots_and_installed_globals_are_all_required(self):
        m=Memory();self.assertEqual(m.verify()['manager'],m.manager)
        self.assertIn(profile.SOURCE[1],profile.source_dependencies().values())
        for row in m.proof['bodies']:
            address=m.base+row['rva'];old=m.parts[address]
            with self.subTest(body=row['name']):
                m.parts[address]=bytearray([old[0]^1])+old[1:]
                with self.assertRaisesRegex(ValueError,'live code'):m.verify()
                m.parts[address]=old
        for row in m.proof['slots']:
            address=m.base+row['vtable_rva']+row['slot'];old=m.parts[address]
            m.put(address,m.base+row['target_rva']+8)
            with self.assertRaisesRegex(ValueError,'dispatch'):m.verify()
            m.parts[address]=old
        for name in ('host','auxiliary','inner'):
            address=m.base+m.proof['contract']['globals'][name];old=m.parts[address]
            m.put(address,0)
            with self.assertRaisesRegex(ValueError,'global'):m.verify()
            m.parts[address]=old

    def test_native_context_and_manager_must_be_the_actual_owners(self):
        m=Memory()
        for address in (m.context,m.context+8,m.inner,m.inner+0x1a58):
            old=m.parts[address];m.put(address,0)
            with self.assertRaises(ValueError):m.verify()
            m.parts[address]=old
        with self.assertRaisesRegex(ValueError,'Incomplete'):
            profile.verify_live(m.base,lambda *_:b'',context=m.context,inner=m.inner,
                host_pointer=m.host,auxiliary_pointer=m.auxiliary)

    def test_borrowed_database_lease_and_canonical_configuration_are_required(self):
        m=Memory();host=NS(pointer=m.host,aux_object=(C.c_void_p*2)())
        m.put(m.base+0xb8aa88,C.addressof(host.aux_object))
        backend=NS(core=NS(_handle=m.base),context=m.context,host=host,
                   configuration_abi=configuration_abi(XP2_CORE_SHA256))
        runtime=NS(registry=NS(_check=Mock()),service_owner=host)
        lease=NS(owner=host,inner=m.inner)
        with patch('civ6_host.runtime.core_script_services.check_bound',return_value=lease) as checked:
            self.assertEqual(profile.verify_services(backend,runtime,m.read)['manager'],m.manager)
            checked.assert_called_once_with(runtime,m.context,backend.core)
            lease.owner=object()
            with self.assertRaisesRegex(ValueError,'another owner'):profile.verify_services(backend,runtime,m.read)
        backend.configuration_abi=NS(core_sha256=XP2_CORE_SHA256)
        with self.assertRaisesRegex(ValueError,'canonical'):profile.verify_services(backend,runtime,m.read)

    def test_early_close_guard_reads_the_verified_xp2_initialized_field(self):
        m=Memory();abi=profile_for_sha(XP2_CORE_SHA256)
        backend=NS(core=NS(_handle=m.base),configuration_abi=configuration_abi(XP2_CORE_SHA256))
        profile.require_uninitialized_game(backend,m.read,0)
        game=0x1500000;m.put(game,m.base+abi.game_vtable_rva);m.parts[game+0x2a4]=bytearray(b'\0')
        profile.require_uninitialized_game(backend,m.read,game)
        m.parts[game+0x2a4][0]=1
        with self.assertRaisesRegex(RuntimeError,'Loaded Game teardown'):
            profile.require_uninitialized_game(backend,m.read,game)
        m.parts[game+0x2a4][0]=0;m.put(game,m.base+abi.game_vtable_rva+8)
        with self.assertRaisesRegex(ValueError,'Game differs'):
            profile.require_uninitialized_game(backend,m.read,game)


if __name__=='__main__':unittest.main()
