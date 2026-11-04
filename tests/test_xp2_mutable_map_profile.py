"""Exact source guard fixtures; no native calls or HKS execution."""
import struct
import unittest
from unittest.mock import patch

from civ6_host.runtime import xp2_mutable_map_profile as profile
from test_xp2_aux_maps import memory


class MutableProfileTests(unittest.TestCase):
    def fixture(self):
        result=memory({})
        for row in profile.source()['bodies']:
            result.parts[result.base+row['rva']]=bytes.fromhex(row['raw_hex'])
        for slot,target in profile.SETTERS:
            result.parts[result.base+profile.VTABLE+slot]=struct.pack('<Q',result.base+target)
        for slot,target in ((0,0x99d820),(8,0x9a1610)):
            result.parts[result.base+profile.HELPERS['resolver_vtable']+slot]=struct.pack('<Q',result.base+target)
        return result

    def test_source_and_every_new_live_guard_are_required(self):
        m=self.fixture();proof=profile.verify_live(m.base,m.read)
        self.assertFalse(proof['native_execution'])
        self.assertIn(profile.SOURCE[1],profile.source_dependencies().values())
        for body in proof['bodies']:
            with self.subTest(body=body['name']):
                address=m.base+body['rva'];old=m.parts[address]
                m.parts[address]=bytes([old[0]^1])+old[1:]
                with self.assertRaises(ValueError):profile.verify_live(m.base,m.read)
                m.parts[address]=old
        for slot,target in profile.SETTERS:
            with self.subTest(slot=slot):
                address=m.base+profile.VTABLE+slot;old=m.parts[address]
                m.parts[address]=struct.pack('<Q',m.base+target+1)
                with self.assertRaisesRegex(ValueError,'dispatch differs'):profile.verify_live(m.base,m.read)
                m.parts[address]=old

    def test_runtime_requires_exact_registered_native_build_components(self):
        self.assertGreaterEqual(len(profile.COMPONENTS),5)
        from pathlib import Path
        from civ6_host.runtime.source_build_identity import verify_source_build
        artifact=Path(__file__).resolve().parents[1]/'work/xp2-result-map/build03/civ6rl-native-python.exe'
        result=verify_source_build(artifact,required_components=profile.COMPONENTS)
        self.assertFalse(result['native_compatibility_claimed'])
        wrong={**profile.COMPONENTS,'script_game_event_result_map.inc':'0'*64}
        with self.assertRaisesRegex(ValueError,'component'):
            verify_source_build(artifact,required_components=wrong)


if __name__=='__main__':unittest.main()
