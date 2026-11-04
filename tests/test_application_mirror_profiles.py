"""Engine selection and refusal boundaries; no native process is started."""
import ctypes as C
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch

from civ6_host.runtime import application_mirror_profiles as p
from civ6_host.runtime.configuration_profiles import BASE_CORE_SHA256,XP1_CORE_SHA256,XP2_CORE_SHA256


class ApplicationMirrorProfilesTests(unittest.TestCase):
    def test_source_profiles_are_distinct_and_unknown_engines_refuse(self):
        base=p.mirror_abi(BASE_CORE_SHA256);xp=p.mirror_abi(XP1_CORE_SHA256)
        self.assertEqual(base.variant_assign_rva,0x747AE0)
        self.assertEqual(xp.variant_assign_rva,0x8473E0)
        self.assertEqual(xp.methods['allocate'],0x836AF0)
        self.assertEqual(xp.methods['owned_map'],0x8461F0)
        self.assertIsNone(xp.live_inspection_sha256)
        xp2=p.mirror_abi(XP2_CORE_SHA256)
        self.assertEqual(xp2.variant_assign_rva,0x9a1320)
        self.assertEqual(xp2.methods['allocate'],0x990900)
        with self.assertRaises(ValueError):p.mirror_abi('0'*64)
        with self.assertRaises(ValueError):p.owner_abi(NS(_configuration_abi=base.configuration),XP1_CORE_SHA256)

    def test_civilization_source_joins_xp2_provider_to_shared_exe_key_initializer(self):
        xp1=p.civilization_source(XP1_CORE_SHA256)
        self.assertEqual(xp1['getter_rva'],0x845600)
        selected=p.civilization_source(XP2_CORE_SHA256)
        self.assertEqual(selected['getter_rva'],0x99F680)
        self.assertEqual(selected['sentinel_rva'],0xB90808)
        self.assertEqual(selected['variant_size'],24)
        self.assertEqual(selected['key'],0xC7D7515B)
        self.assertEqual(selected['source_sha256'],
            'e1241f8dcab67dee4166b9f818f55d070fee5cf53ef79a755cb4eb77a6c7cce8')
        self.assertEqual(selected['exe_key_source_sha256'],
            'e1816d452f11c2a1c85d26d14252cf99adbceaafd54d7a0b6500c0da2bf0b026')
        deps=p.civilization_source_dependencies(XP2_CORE_SHA256)
        self.assertIn(selected['exe_key_source_sha256'],set(deps.values()))
        self.assertIn(selected['source_sha256'],set(deps.values()))
        self.assertNotIn(p.CIVILIZATION_SOURCE[1],set(deps.values()))

    def test_civilization_source_rejects_changed_shared_exe_key_literal(self):
        from copy import deepcopy
        key_proof=p._source(p.XP2_CIVILIZATION_KEY_SOURCE)
        key_proof=deepcopy(key_proof)
        key_proof['captures']['exe']['civilization_type_id_key_literal']['text']='PLAYER_0'
        with patch.object(p,'_source',return_value=key_proof):
            with self.assertRaisesRegex(ValueError,'source join differs'):
                p.civilization_source(XP2_CORE_SHA256)

    def test_copy_reuses_complete_pinned_bodies_and_mutations_are_live_checked(self):
        proof=p.copy_source(XP1_CORE_SHA256)
        self.assertEqual(set(proof['core_functions']),{'variant_clone_assign','variant_release','provider_allocator','lookup'})
        state={}
        for body in proof['core_functions'].values():
            for fragment in body['fragments']:
                for i in fragment['instructions']:
                    for j,b in enumerate(bytes.fromhex(i['bytes'])):state[int(i['va'],16)+j]=b
        base=0x180000000;abi=p.mirror_abi(XP1_CORE_SHA256)
        def put(addr,data):state.update({addr+i:v for i,v in enumerate(data)})
        def read(addr,n):return bytes(state[addr+i] for i in range(n))
        def q(addr,value):put(addr,int(value).to_bytes(8,'little'))
        left,right=0x100000,0x200000
        for ptr in (left,right):q(ptr,base+abi.configuration.vtable_rva)
        q(base+abi.configuration.vtable_rva+0x58,base+abi.configuration.lookup_rva)
        q(base+abi.configuration.vtable_rva+0x20,base+abi.allocator_get_rva)
        from civ6_host.runtime.native.native_application_property_copy import copy_existing
        calls=[]
        def call(address,result,types,receiver,*args):
            calls.append(address)
            self.assertEqual(address,base+abi.configuration.lookup_rva)
            return None
        result=copy_existing(base,left,right,123,read=read,call=call,core_sha256=XP1_CORE_SHA256)
        self.assertEqual(result,{'mirrored':False,'native_branch':'missing_source'})
        self.assertEqual(len(calls),1)
        state[base+abi.variant_assign_rva]^=1
        with self.assertRaisesRegex(ValueError,'code differs'):
            copy_existing(base,left,right,123,read=read,call=call,core_sha256=XP1_CORE_SHA256)
        self.assertEqual(len(calls),1)

    def test_indexed_records_use_shared_reader_with_call_seam(self):
        call=lambda *a:None;lookup=lambda *a:None
        snapshot={'descriptor':1,'players':list(range(100,164))}
        target='civ6_host.runtime.native.native_configuration_finalization._linked_snapshot'
        with patch(target,return_value=snapshot) as shared:
            record=p.indexed_player(1000,2000,63,read=object(),lookup=lookup,call=call,core_sha256=XP1_CORE_SHA256)
        self.assertEqual(record['pointer'],163)
        self.assertIs(shared.call_args.args[3],call)
        self.assertEqual(shared.call_args.kwargs,{'core_sha256':XP1_CORE_SHA256})

    def test_native_callback_is_refused_after_close_or_from_another_thread(self):
        from civ6_host.runtime.native.native_application_mirror import NativePlayerApplicationMirror
        from threading import get_native_id
        mirror=object.__new__(NativePlayerApplicationMirror)
        mirror._mirror_thread=get_native_id();mirror.closed=True
        with self.assertRaisesRegex(ValueError,'closed'):
            mirror.dispatch(0,0,0,0)
        mirror.closed=False;mirror._mirror_thread=-1
        with self.assertRaisesRegex(ValueError,'another thread'):
            mirror.dispatch(0,0,0,0)

    def test_callback_release_checks_pending_journal_and_restores_slot_metadata(self):
        from civ6_host.runtime.native.native_application_mirror import NativePlayerApplicationMirror
        from threading import get_native_id
        mirror=object.__new__(NativePlayerApplicationMirror)
        mirror._mirror_thread=get_native_id();mirror.closed=False
        table=(C.c_void_p*64)();table[38]=333
        mirror._callback_address=333;mirror._previous_callback=222
        mirror._binding_key=(C.addressof(table),304)
        mirror._previous_binding=(222,'prior')
        mirror.host=NS(vtable=table,_slot_bindings={mirror._binding_key:(333,'current')})
        mirror.mirror=NS(changes=[(1,2)])
        with self.assertRaisesRegex(ValueError,'unconsumed'):mirror.close()
        self.assertEqual(table[38],333)
        mirror.mirror.changes.clear();mirror.close();mirror.close()
        self.assertEqual(table[38],222)
        self.assertEqual(mirror.host._slot_bindings[mirror._binding_key],(222,'prior'))
