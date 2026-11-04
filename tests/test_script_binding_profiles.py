"""Sparse memory fixtures over the actual sealed binding profile; no native calls."""
from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
import json
import struct
import unittest
from unittest.mock import patch

from civ6_host.runtime import script_binding_profiles as profiles
from civ6_host.runtime.paths import resource_root
from civ6_host.runtime.resource_resolution import resolve_path


class Memory:
    def __init__(self, profile):
        self.base = 0x180000000
        self.context = 0x40000000
        self.blocks = {}
        self.calls = []
        self.put(self.context, self.base+profile.context_vtable_rva)
        self.interface = self.base+profile.interface_rva
        self.put(self.interface,self.base+profile.interface_vtable_rva)
        for body in profile.bodies:self.blocks[self.base+body.rva] = body.raw
        for slot in profile.slots:self.put(self.base+slot.table_rva+slot.slot,self.base+slot.target_rva)
        for index, owner in enumerate(profile.prerequisites):
            self.put(self.base+owner.global_rva,0x50000000+index*0x1000)

    def put(self,address,pointer):
        self.blocks[address] = struct.pack('<Q',pointer)

    def read(self,address,size):
        self.calls.append((address,size))
        raw = self.blocks.get(address)
        if raw is None:raise AssertionError('Fixture has no declared memory block at '+hex(address))
        return raw[:size]


class ScriptBindingProfileTests(unittest.TestCase):
    def setUp(self):
        if profiles.SOURCE_SHA == 'pending':
            self.skipTest('Private script binding source profile has not been sealed')
        path = resolve_path(resource_root()/profiles.SOURCE_PATH)
        if not path.is_file():self.skipTest('Private script binding source profile absent')
        self.profile = profiles.profile_for_sha(profiles.XP2_CORE_SHA256)
        self.document = json.loads(path.read_bytes())
        self.memory = Memory(self.profile)

    def verify(self,memory=None,profile=None):
        m = memory or self.memory
        return profiles.verify_live(profile or self.profile,m.base,m.context,m.read)

    def test_canonical_frozen_profile_checks_actual_body_bytes_slots_and_owned_interface(self):
        p = self.profile;m = self.memory
        self.assertIs(profiles.profile_for_sha(p.core_sha256),p)
        self.assertEqual(self.verify(),m.base+p.getter_rva)
        profiles.verify_interface(p,m.base,m.interface,m.read)
        self.assertFalse(p.load_admitted);self.assertFalse(p.complete_api_verified)
        self.assertIs(type(p.bodies),tuple);self.assertIs(type(p.slots),tuple)
        with self.assertRaises(FrozenInstanceError):p.getter_rva += 8
        with self.assertRaises(FrozenInstanceError):p.bodies[0].raw = b'changed'
        with self.assertRaises(ValueError):self.verify(profile=replace(p))
        dependencies = profiles.source_dependencies()
        self.assertEqual(dependencies[str(resolve_path(resource_root()/profiles.SOURCE_PATH).resolve())],profiles.SOURCE_SHA)
        self.assertEqual(len(dependencies),1+len(p.references))

    def test_each_changed_complete_body_is_refused_before_getter_is_returned(self):
        for body in self.profile.bodies:
            with self.subTest(body=body.name):
                m = Memory(self.profile)
                raw = bytearray(body.raw);raw[0] ^= 1
                m.blocks[m.base+body.rva] = bytes(raw)
                with self.assertRaisesRegex(ValueError,'body changed'):self.verify(m)

    def test_context_and_every_declared_slot_are_checked(self):
        m = self.memory;m.put(m.context,m.base+self.profile.context_vtable_rva+8)
        with self.assertRaisesRegex(ValueError,'context vtable'):self.verify()
        for slot in self.profile.slots:
            with self.subTest(table=slot.table_rva,slot=slot.slot):
                m = Memory(self.profile)
                m.put(m.base+slot.table_rva+slot.slot,m.base+slot.target_rva+8)
                with self.assertRaisesRegex(ValueError,'dispatch slot'):self.verify(m)

    def test_each_required_registration_owner_must_be_nonnull_and_a_valid_pointer(self):
        for owner in self.profile.prerequisites:
            for pointer in (0,1,2**63):
                with self.subTest(owner=owner.name,pointer=pointer):
                    m = Memory(self.profile);m.put(m.base+owner.global_rva,pointer)
                    with self.assertRaises(ValueError):self.verify(m)

    def test_interface_singleton_vtable_and_method_are_exact(self):
        p=self.profile;m=self.memory
        for pointer in (0,True,'foreign',m.interface+8):
            with self.subTest(pointer=pointer):
                before=len(m.calls)
                with self.assertRaises(ValueError):profiles.verify_interface(p,m.base,pointer,m.read)
                self.assertEqual(len(m.calls),before)
        for mode in ('vtable','method'):
            m=Memory(p)
            if mode=='vtable':m.put(m.interface,m.base+p.interface_vtable_rva+8)
            else:m.put(m.base+p.interface_vtable_rva+p.method_slot,m.base+p.method_rva+8)
            with self.subTest(mode=mode),self.assertRaises(ValueError):
                profiles.verify_interface(p,m.base,m.interface,m.read)

    def test_bad_addresses_short_reads_and_mutable_reader_buffers_are_refused(self):
        p=self.profile;m=self.memory
        for base,context in ((True,m.context),(m.base,False),(0,m.context),
                             (m.base,1),(2**64,m.context),(m.base,2**64)):
            with self.subTest(base=base,context=context):
                before=len(m.calls)
                with self.assertRaises(ValueError):profiles.verify_live(p,base,context,m.read)
                self.assertEqual(len(m.calls),before)
        for reader in (lambda a,n:b'\0'*(n-1),lambda a,n:bytearray(m.read(a,n)),None):
            with self.subTest(reader=reader),self.assertRaises(ValueError):
                profiles.verify_live(p,m.base,m.context,reader)

    def test_unknown_engines_and_pending_profile_do_not_read_source_or_memory(self):
        with patch.object(profiles,'load_pinned_json',side_effect=AssertionError('Unqualified source read')):
            for core in ('0'*64,True,None,[],profiles.XP2_CORE_SHA256.upper()):
                with self.subTest(core=core),self.assertRaises(ValueError):profiles.profile_for_sha(core)
            with patch.object(profiles,'SOURCE_SHA','pending'),self.assertRaises(ValueError):
                profiles.profile_for_sha(profiles.XP2_CORE_SHA256)

    def test_source_profile_rejects_incomplete_or_changed_contracts(self):
        for mode in ('native_execution','engine','abi','raw','digest','missing_body','missing_reader_body','missing_slot','nullable','reference'):
            doc=deepcopy(self.document)
            if mode=='native_execution':doc['native_execution']=True
            elif mode=='engine':doc['engine']['sha256']='0'*64
            elif mode=='abi':doc['abi']['getter_rva']+=8
            elif mode=='raw':doc['bodies'][0]['raw_hex']=doc['bodies'][0]['raw_hex'][:-2]
            elif mode=='digest':doc['bodies'][0]['sha256']='0'*64
            elif mode=='missing_body':doc['bodies']=[b for b in doc['bodies'] if b['rva']!=doc['abi']['getter_rva']]
            elif mode=='missing_reader_body':doc['bodies']=[b for b in doc['bodies'] if b['rva']!=doc['prerequisites'][0]['reader_rva']]
            elif mode=='missing_slot':doc['slots']=[s for s in doc['slots'] if s['table_rva']!=doc['abi']['context_vtable_rva']]
            elif mode=='nullable':doc['prerequisites'][0]['nullable']=True
            else:doc['references'][0]['sha256']='0'*64
            with self.subTest(mode=mode),self.assertRaises(ValueError):profiles._parse(doc)


if __name__ == '__main__':unittest.main()
