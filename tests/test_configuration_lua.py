"""Changed configuration source join and ownership, without executing GameCore."""
import ctypes as C
import struct
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

from civ6_host.runtime import configuration_lua_source as source
from civ6_host.runtime.configuration_profiles import _body
from civ6_host.runtime.script_scalar_service import ScalarService


class ConfigurationLuaTests(unittest.TestCase):
    def fixture(self):
        base=0x200000000
        code={}
        for value in source.source()['functions']['xp1'].values():
            for fragment in _body(value)['fragments']:
                for instruction in fragment['instructions']:
                    raw=bytes.fromhex(instruction['bytes'])
                    code[base+int(instruction['va'],16)-0x180000000,len(raw)]=raw
        code[base+0x93F590+0x60,8]=struct.pack('<Q',base+0x845540)
        return base,code

    def test_actual_source_and_loaded_callers_provider_slot_must_agree(self):
        base,code=self.fixture()
        read=lambda address,size:code[address,size]
        self.assertFalse(source.verify_xp1(base,read)['saved_game_load_admitted'])
        slot=(base+0x93F590+0x60,8)
        original=code[slot];code[slot]=b'\0'*8
        with self.assertRaisesRegex(ValueError,'slot'):source.verify_xp1(base,read)
        code[slot]=original
        first=next(iter(code));code[first]=b'\0'*first[1]
        with self.assertRaisesRegex(ValueError,'code differs'):source.verify_xp1(base,read)

    def service(self):
        callback=C.CFUNCTYPE(None,C.c_void_p,C.c_void_p,C.c_void_p)(lambda *args:None)
        host=SimpleNamespace(aux_vtable=(C.c_void_p*32)())
        host.aux_vtable[20]=123
        runtime=SimpleNamespace(host=SimpleNamespace(LAB_AuxPushVariant=callback),
                                registry=SimpleNamespace(_check=Mock()))
        return host,runtime,ScalarService(host,runtime)

    def test_slot_has_single_owner_and_restores_previous_callback(self):
        host,runtime,service=self.service()
        self.assertEqual(host.aux_vtable[20],service.address)
        with self.assertRaises(ValueError):ScalarService(host,runtime)
        service.close();service.close()
        self.assertEqual(host.aux_vtable[20],123)
        self.assertIsNone(host._scalar_service_owner)

    def test_wrong_thread_or_replaced_slot_cannot_release_service(self):
        host,runtime,service=self.service();errors=[]
        def close():
            try:service.close()
            except ValueError as error:errors.append(error)
        worker=threading.Thread(target=close);worker.start();worker.join()
        self.assertEqual(len(errors),1);self.assertFalse(service.closed)
        host.aux_vtable[20]=124
        with self.assertRaisesRegex(ValueError,'ownership'):service.close()
        host.aux_vtable[20]=service.address;service.close()


if __name__=='__main__':unittest.main()
