"""Static source/profile guards, with an explicit byte-map reader; no native calls."""
import copy
from dataclasses import FrozenInstanceError, replace
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import sys
import unittest
from unittest.mock import patch

from civ6_host.runtime.configuration_profiles import configuration_abi,require_owner_profile,_copy
from civ6_host.runtime.saved_load_profiles import XP2_CORE_SHA256,XP1_CORE_SHA256,require_saved_load_admission

try:
    from civ6_host.runtime import xp2_configuration_profile as profile
except ImportError:
    # Staging uses the same package namespace, without installing during a
    # parent native run's global source freeze.
    path=Path(__file__).with_name('xp2_configuration_profile.py')
    spec=importlib.util.spec_from_file_location('civ6_host.runtime.xp2_configuration_profile',path)
    profile=importlib.util.module_from_spec(spec);sys.modules[spec.name]=profile
    spec.loader.exec_module(profile)


class XP2ConfigurationProfile(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.proof=profile.verify_source()

    def test_candidate_joins_shared_owner_without_saved_load_admission(self):
        abi=profile.candidate_abi()
        self.assertEqual(abi.core_sha256,XP2_CORE_SHA256)
        self.assertEqual((abi.root_key_rva,abi.map_key_rva,abi.player_key_table_rva),(0xb8c400,0xb8c4b0,0xb8c500))
        self.assertEqual(abi.load.ruleset,'xp2')
        self.assertIs(configuration_abi(XP2_CORE_SHA256),abi)
        self.assertIs(require_owner_profile(abi),abi)
        with self.assertRaises(ValueError):require_owner_profile(replace(abi))
        with self.assertRaises(ValueError):require_saved_load_admission(abi.load)
        with self.assertRaises(ValueError):profile.candidate_abi(XP1_CORE_SHA256)
        with self.assertRaises(ValueError):profile.candidate_abi(None)
        with self.assertRaises(FrozenInstanceError):abi.map_key_rva=0xb8c4c8

    def test_map_value_embedded_provider_ownership_and_inline_records_are_distinct(self):
        layout=profile.configuration_layout()
        self.assertEqual(layout['map_descriptor_offset']+8,layout['map_value_offset'])
        self.assertEqual(layout['map_value_offset']+8,layout['embedded_provider_offset'])
        self.assertEqual(layout['embedded_provider_offset']+layout['provider_storage_bytes'],layout['provider_owned_flag_offset'])
        self.assertEqual(layout['records_inline_offset']+layout['records_inline_bytes'],layout['sentinel_record_offset'])
        self.assertEqual(layout['record_count']*layout['record_stride'],layout['records_inline_bytes'])
        with self.assertRaises(TypeError):layout['map_value_offset']=0xc38
        rows={i['va']:i['text'] for f in self.proof['functions']['setup_destructor']['body']['fragments'] for i in f['instructions']}
        self.assertEqual(rows['0x180164126'],'cmp byte ptr [rcx + 0xc90], 0')
        self.assertEqual(rows['0x180164146'],'call qword ptr [rax]')
        self.assertEqual(rows['0x18016414f'],'call 0x18099e5d0')

    def test_shared_application_codec_shapes_preserve_bounded_lookup_extent(self):
        app=profile.application_source();codec=profile.codec_source()
        self.assertFalse(app['game_load_admitted']);self.assertFalse(codec['game_load_admitted'])
        self.assertEqual(len(app['player_keys']),64)
        self.assertEqual(set(codec['captures']['core']),{'provider_slot_'+hex(slot) for slot,_ in profile.candidate_abi().codec_slots})
        lookup=app['core_functions']['lookup']
        self.assertFalse(lookup['full_function_body_proven'])
        self.assertEqual(lookup['boundary_method'],'retained-bounded-reachable-CFG')
        self.assertTrue(all(f['instructions'] for f in lookup['fragments']))
        self.assertEqual(codec['images']['core']['sha256'],XP2_CORE_SHA256)

    def test_source_pins_include_every_consumed_proof_and_new_capture_script(self):
        pins=profile.source_dependencies()
        self.assertEqual(len(pins),17)
        for path,expected in pins.items():
            self.assertEqual(hashlib.sha256(Path(path).read_bytes()).hexdigest(),expected)
        self.assertTrue(any(path.endswith('provider-ownership-xp2-setup-map-record-v6.json') for path in pins))
        self.assertTrue(any(path.endswith('xp2_configuration_capture.py') for path in pins))
        self.assertTrue(any(path.endswith('active-list-source\\source.json') or path.endswith('active-list-source/source.json') for path in pins))

    def test_map_key_and_layout_confusion_refuse_before_a_native_owner(self):
        load=profile._source
        for kind in ('map_script_key','embedded_as_map_value','wrong_engine','wrong_player_key',
                     'bool_offset','float_rva','float_slot','bool_player_index'):
            changed=_copy(self.proof)
            if kind=='map_script_key':changed['abi']['map_key_rva']=0xb8c4c8
            elif kind=='embedded_as_map_value':changed['layout']['map_value_offset']=0xc38
            elif kind=='wrong_engine':changed['image']['sha256']=XP1_CORE_SHA256
            elif kind=='wrong_player_key':changed['player_keys'][3]['hash']^=1
            elif kind=='bool_offset':changed['layout']['record_index_offset']=False
            elif kind=='float_rva':changed['abi']['lookup_rva']=float(changed['abi']['lookup_rva'])
            elif kind=='float_slot':changed['abi']['codec_slots'][0][0]=float(changed['abi']['codec_slots'][0][0])
            else:changed['player_keys'][0]['index']=False
            def read(ref):return changed if ref==profile.SOURCE else load(ref)
            with self.subTest(kind=kind),patch.object(profile,'_source',side_effect=read),self.assertRaises(ValueError):
                profile.verify_source()

    def test_live_guards_with_byte_fixture_reject_code_slot_and_module_mismatch(self):
        base=0x100000000;memory={}
        bodies=profile._all_bodies(self.proof,profile._prior(self.proof))
        bodies['inner_initialized_getter']=profile._initialized_source()[1]
        for body in bodies.values():
            for fragment in body['fragments']:
                for row in fragment['instructions']:
                    at=base+int(row['va'],16)-0x180000000
                    for n,value in enumerate(bytes.fromhex(row['bytes'])):
                        if at+n in memory:self.assertEqual(memory[at+n],value)
                        memory[at+n]=value
        for row in self.proof['slots']:
            at=base+row['table_rva']+row['offset']
            for n,value in enumerate(struct.pack('<Q',base+row['target_rva'])):memory[at+n]=value
        calls=[]
        def read(at,size):
            calls.append((at,size));self.assertLessEqual(size,4096)
            return bytes(memory[at+i] for i in range(size))
        result=profile.verify_live(base,read)
        self.assertFalse(result['native_execution']);self.assertFalse(result['game_load_admitted'])
        self.assertGreater(result['instruction_guards'],100)
        first=base+0x164050;memory[first]^=1
        with self.assertRaisesRegex(ValueError,'instruction mismatch'):profile.verify_live(base,read)
        memory[first]^=1
        slot=base+0xabf080+0x58;memory[slot]^=1
        with self.assertRaisesRegex(ValueError,'virtual slot mismatch'):profile.verify_live(base,read)
        for bad in (True,0,-1,1.0):
            with self.subTest(base=bad),self.assertRaises(ValueError):profile.verify_live(bad,read)


if __name__=='__main__':unittest.main()
