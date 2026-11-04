"""Exact XP2 source and saved owner composition for WMD visibility only."""
import struct
import unittest
from unittest.mock import patch

from civ6_host.runtime import xp2_wmd_fallout_visibility as wmd
from civ6_host.runtime.configuration_profiles import XP1_CORE_SHA256, XP2_CORE_SHA256
from civ6_host.runtime.foundation_event_profile import event_profile
from civ6_host.runtime.native.native_host_slot_e8 import SPECIAL_CODE
from civ6_host.runtime.xp1_load_capability import capability_source_scope
from test_xp2_natural_wonder import Fixture, scalar


class XP2WmdVisibilityTests(unittest.TestCase):
    def fixture(self):
        # Static PE verification is exercised independently below. Only the
        # fixture's mocked executable address space lacks these mapped bodies.
        with patch.object(wmd,'verify_live'):
            fixture=Fixture()
        self.addCleanup(fixture.close)
        self.assertEqual(fixture.owner.foundation_event_profile.record_types_by_kind[wmd.KIND],{0xc9})
        return fixture

    def invoke(self,fixture,fields):
        fixture.install_argument(fields)
        fixture.set_active(True)
        with capability_source_scope(fixture.backend,'continuation'):
            return fixture.arguments.dispatch(fixture.host.pointer,wmd.KIND,fixture.argument)

    def fields(self,fixture,*,perspective=True,value=2):
        address=0xd10000
        fixture.memory.put(address,struct.pack('<ii',37,12))
        result={wmd.SELECTOR:scalar(3,0),wmd.VALUE:scalar(2,value),
                wmd.POSITION:struct.pack('<H6xQII',13,address,8,0x21000001)}
        if perspective:
            result[wmd.PLAYER]=scalar(2,1)
        return result

    def test_source_and_live_core_bodies(self):
        from extract_phase31_next_export import pefile
        profile=wmd.source()
        from pathlib import Path
        from civ6_host.runtime.paths import resource_root
        boundary=resource_root()/'evidence/native-expansion-init-boundary/340edd6b0dcc82be34ce8342817ed76a331d724ff15bee20da55ee355222c607.json'
        import json
        core=json.loads(boundary.read_bytes())['images']['xp2']
        image=pefile.PE(core['path'],fast_load=True)
        self.addCleanup(image.close)
        base=image.OPTIONAL_HEADER.ImageBase
        wmd.verify_live(base,lambda address,size:image.get_data(address-base,size))
        changed=0x35c1b9
        def damaged(address,size):
            start=address-base
            raw=bytearray(image.get_data(start,size))
            if start<=changed<start+size:
                raw[changed-start]^=1
            return bytes(raw)
        with self.assertRaisesRegex(ValueError,'producer body changed'):
            wmd.verify_live(base,damaged)
        self.assertIn(wmd.SOURCE[1],wmd.source_dependencies().values())
        self.assertEqual(profile['contract']['values'],(0,2))
        self.assertNotIn(wmd.KIND,event_profile(core_sha256=XP1_CORE_SHA256).record_types_by_kind)
        self.assertIn(wmd.KIND,event_profile(core_sha256=XP2_CORE_SHA256).record_types_by_kind)

    def test_receiver_requires_actual_empty_subscribers(self):
        from civ6_host.runtime.native.native_deferred_empty_profile import validate_empty_profile_record
        state=dict(observer_registered=False,state_pointer_nonnull=True,
                   pre_hook=None,post_hook=None,subscriber_count=0,state_flags=0)
        record=struct.pack('<II',96,0xc9)+bytes(88)
        self.assertEqual(validate_empty_profile_record(record,**state)['handler_va'],'0x1400dab10')
        with self.assertRaisesRegex(ValueError,'subscriber list'):
            validate_empty_profile_record(record,**(state|{'subscriber_count':1}))
        with self.assertRaisesRegex(ValueError,'pre/post hook'):
            validate_empty_profile_record(record,**(state|{'post_hook':1}))

    def test_actual_scope_callbacks_two_producer_shapes_and_fifo_drain(self):
        f=self.fixture()
        f.deferred.host_notification(f.host.pointer,0x827289e6)
        self.assertEqual(f.deferred.host_notification_counter,0)
        self.assertEqual(self.invoke(f,self.fields(f,value=0)),0)
        f.deferred.host_notification_end(f.host.pointer,0x827289e6)
        f.deferred.host_notification(f.host.pointer,SPECIAL_CODE)
        self.assertEqual(self.invoke(f,self.fields(f,perspective=False)),0)
        self.assertEqual(f.deferred.host_metadata_counter,1)
        self.assertEqual(self.invoke(f,self.fields(f)),0)
        self.assertEqual(f.deferred.host_metadata_counter,1)
        f.deferred.host_notification_end(f.host.pointer,SPECIAL_CODE)
        self.assertEqual((f.deferred.host_notification_counter,f.deferred.host_metadata_counter),(0,0))
        for sequence,(record,flag,value) in enumerate(zip(f.deferred.pending,(0,0x20,0x40),(0,2,2)),1):
            self.assertEqual(struct.unpack_from('<IIII',record),(96,0xc9,sequence,0))
            self.assertEqual(struct.unpack_from('<I',record,72),(flag,))
            self.assertEqual(struct.unpack_from('<IiiI',record,80),(sequence,37,12,value))
        f.memory.put(f.argument,b'\0'*88)
        f.memory.put(0xd10000,b'\0'*8)
        self.assertEqual(f.deferred.drain(),3)
        self.assertEqual(f.deferred.pending,[])
        self.assertEqual(f.calls,[])

    def test_unproved_scalar_and_tag_refuse_before_enqueue(self):
        f=self.fixture()
        with self.assertRaisesRegex(ValueError,'selector or value'):
            self.invoke(f,self.fields(f,value=1))
        self.assertEqual(f.deferred.pending,[])
        self.assertEqual(f.deferred.host_metadata_counter,0)
        f=self.fixture()
        fields=self.fields(f)
        fields[wmd.POSITION]=struct.pack('<H6xQII',1024,0xd10000,8,0x21000001)
        with self.assertRaisesRegex(ValueError,'blob envelope'):
            self.invoke(f,fields)
        self.assertEqual(f.deferred.pending,[])


if __name__=='__main__':
    unittest.main()
