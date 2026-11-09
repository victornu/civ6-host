"""Policy unlock through the composed argument owner and existing FIFO."""
import struct
from types import SimpleNamespace as NS
import unittest

import test_a0_family_service as fixtures
from civ6_host.runtime import a0_policy_unlock as event
from civ6_host.runtime.a0_family_source import family_profile
from civ6_host.runtime.configuration_profiles import XP2_CORE_SHA256
from civ6_host.runtime.native.native_deferred_empty_profile import validate_empty_profile_record


class PolicyUnlockEventTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.profile = family_profile()

    def fixture(self):
        host,deferred,arguments,owner,reader,*_ = fixtures.A0FamilyServiceTests.fixture(self,XP2_CORE_SHA256)
        backend=NS(stage='prepared',prefix=None,check_thread=lambda:None,
            load_abi=NS(core_sha256=XP2_CORE_SHA256),_xp1_commands_requested=True,
            host=host,core=deferred.core,context=deferred.context)
        owner._foundation_backend=backend
        memory={}
        for body in event.source()['core_functions'].values():
            for fragment in body['fragments']:
                raw=bytes.fromhex(fragment['raw_hex'])
                for offset in range(0,len(raw),4096):
                    block=raw[offset:offset+4096]
                    memory[(backend.core._handle+int(fragment['start_rva'],16)+offset,len(block))]=block
        reader.read.side_effect=lambda address,size: memory[(address,size)]
        return host,deferred,arguments,owner,reader,backend

    def test_exact_source_correspondence_and_empty_receiver(self):
        proof=event.source()
        text=lambda key:[r['text'] for f in proof['functions'][key]['fragments'] for r in f['instructions']]
        self.assertEqual(text('0x142ba0'),['jmp 0x14014d160'])
        writer=text('0x13a2f0')
        for instruction in ('mov dword ptr [rbx], 0x60','mov dword ptr [rbx + 4], 0xd0',
                'lock xadd dword ptr [rsi + 0x38], edi','mov qword ptr [rax], rcx',
                'mov dword ptr [rax], edi'):
            self.assertIn(instruction,writer)
        normalizer=text('0x1445f0')
        index=normalizer.index('call rax')
        self.assertEqual(normalizer[index+1],'xor eax, eax')
        shape=bytearray(96)
        struct.pack_into('<II',shape,0,96,208)
        row=validate_empty_profile_record(shape,**fixtures.PROFILE)
        self.assertEqual(row['event_name'],'GameCoreEvent::CivicsUnlocked')
        with self.assertRaises(ValueError):
            validate_empty_profile_record(shape,**(fixtures.PROFILE|{'subscriber_count':1}))

    def test_composed_owner_keeps_fifo_order_counter_scope_and_real_drain(self):
        host,d,a,owner,reader,backend=self.fixture()
        self.assertFalse(owner.handles_kind(event.KIND))
        event.enable(owner,backend)
        self.assertTrue(owner.handles_kind(event.KIND))
        self.assertTrue(owner.handles_record(208))
        for n,m in ((0,0),(2,7)):
            d.host_notification_counter,d.host_metadata_counter=n,m
            reader.fields.return_value={0xa1e5a149:fixtures.scalar(3,0),0xd6fcf3e4:fixtures.scalar(2,0)}
            self.assertEqual(a.dispatch(host.pointer,event.KIND,0x9000),0)
            raw=d.pending[-1]
            self.assertEqual(struct.unpack_from('<IIII',raw),(96,208,d._sequence,0))
            self.assertEqual(struct.unpack_from('<II',raw,80),(d._sequence,0))
            self.assertEqual(struct.unpack_from('<I',raw,72)[0],0)
            self.assertEqual((d.host_notification_counter,d.host_metadata_counter),(n,m))
        d.host_notification_counter=d.host_metadata_counter=0
        self.assertEqual(d.drain(),2)
        self.assertEqual(d.pending,[])
        self.assertEqual(d.consumed_count,2)
        self.assertEqual(a.count,2)
        with self.assertRaises(ValueError):
            event.enable(owner,backend)

    def test_descriptor_mismatch_refuses_and_quarantines(self):
        host,d,a,owner,reader,backend=self.fixture()
        event.enable(owner,backend)
        reader.fields.return_value={0xa1e5a149:fixtures.scalar(3,1),0xd6fcf3e4:fixtures.scalar(2,0)}
        with self.assertRaises(ValueError):
            a.dispatch(host.pointer,event.KIND,0x9000)
        self.assertTrue(a.quarantined)
        self.assertTrue(owner.quarantined)
        self.assertEqual(d.pending,[])

    def test_source_mismatch_is_refused_before_admission(self):
        host,d,a,owner,reader,backend=self.fixture()
        reader.read.side_effect=None
        reader.read.return_value=b'\0'
        with self.assertRaisesRegex(ValueError,'Live XP2'):
            event.enable(owner,backend)
        self.assertFalse(owner.handles_kind(event.KIND))
        self.assertEqual(d.pending,[])

    def test_optional_hook_change_cannot_be_silenced(self):
        host,d,a,owner,reader,backend=self.fixture()
        event.enable(owner,backend)
        owner.per_thread_hook_present=True
        reader.fields.return_value={0xa1e5a149:fixtures.scalar(3,0),0xd6fcf3e4:fixtures.scalar(2,0)}
        with self.assertRaisesRegex(RuntimeError,'hooks changed'):
            a.dispatch(host.pointer,event.KIND,0x9000)
        self.assertEqual(d.pending,[])
