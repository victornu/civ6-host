"""XP1 queue source selection and actual continuation gate; no native engine."""
from dataclasses import replace
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import unittest

from civ6_host.runtime import xp1_production_queue_profile as profile

HOST=Path(__file__).resolve().parents[1];LAB=HOST.parent/'civ6-rl-lab'


@lru_cache(maxsize=1)
def _captured_inputs():
    from civ6_host.runtime.native.native_official_load import OfficialInputs
    from civ6_host.runtime.native.native_official_bundle import parse_configuration
    from civ6_host.runtime.native.official_application_configuration import extract_application_configuration
    from civ6_host.runtime.xp1_saved_load import REFERENCE, CONFIGURATION_SHA256, GAME_SHA256
    from civ6_host.runtime.xp1_bundle_inputs import XP1_LAN_PROFILE
    folder=LAB/'work/official-capture/xp1-lan-20261030/save-capture/9e368607e66151a4ffbf7d3291613df08e8f4a30dd9c1b6fd57a7fb205ff4fde'
    configuration,_=extract_application_configuration((folder/'source.Civ6Save').read_bytes())
    _,maps=parse_configuration(configuration,'LAN')
    game=(folder/'section-02-00011439-gamecore_stream_candidate.raw').read_bytes()
    assert hashlib.sha256(configuration).hexdigest()==CONFIGURATION_SHA256
    assert hashlib.sha256(game).hexdigest()==GAME_SHA256
    return OfficialInputs(configuration,game,maps,XP1_LAN_PROFILE,None,REFERENCE)


def bind_gate_fixture(f):
    """Keep the real owner/lease; supply exact captured serialized inputs.

    It does not invoke or patch the admission. The external composed fixture
    retains synthetic native state, while input bytes/reference/ABI are real.
    PreparedBundle metadata below is only the narrow fixture required by the
    existing validator; no whole-bundle/native-load claim is made by these tests.
    """
    from civ6_host.runtime.native.native_official_bundle import PreparedBundle
    from civ6_host.runtime.xp1_saved_load import REFERENCE
    inputs=_captured_inputs();b=f.backend
    bundle=PreparedBundle(REFERENCE,inputs,1,Path(profile.verify_source()['image']['path']),{}, {},
        dict(turn=1,width=74,height=46,player_id=0),dict(engine=dict(gamecore_sha256=profile.XP1_CORE_SHA256)))
    b.inputs=f.saved.inputs=f.token.lease.inputs=inputs
    b.captured_bundle=bundle
    # The fixture represents a completed Load stream. Its consumed byte count
    # must match the actual captured game component joined above.
    b.reader.transport.cursor=len(inputs.game)


class QueueProfileTests(unittest.TestCase):
    def fixture(self):
        from test_xp1_unit_orders_owner import Fixture
        f=Fixture();self.addCleanup(f.close);bind_gate_fixture(f);return f

    def test_source_getat_full_native_body_and_ui_capture_are_pinned(self):
        p=profile.verify_source()
        self.assertEqual(p['bindings']['BuildQueue.GetAt']['callback_rva'],'0x5a7770')
        self.assertEqual(len(p['retained_base']['intervals']),14)
        self.assertEqual(set(p['retained_base']['aggregate']['kinds']),{'0x92492f56','0x2842ce14','0x9ea4c222'})
        dependencies=profile.source_dependencies()
        for ref in (*p['official_ui_sources'],*p['captured_ui_witnesses'],p['capture_manifest']):
            self.assertEqual(dependencies[str(Path(ref['path']).resolve())],ref['sha256'])
        with self.assertRaises(ValueError):profile.verify_source('0'*64)

    def test_real_owner_gate_binds_once_and_refuses_foreign_inputs_or_lease(self):
        f=self.fixture();b=f.backend
        receipt=profile.bind_owner(b,b.core,b.runtime.read)
        self.assertTrue(profile.gate_admitted(f.token))
        self.assertIs(profile.bind_owner(b,b.core,b.runtime.read),receipt)
        f.set_active(True);self.assertTrue(profile.gate_admitted(f.token));f.set_active(False)
        original=b.inputs;b.inputs=replace(original)
        with self.assertRaises((ValueError,RuntimeError)):profile.gate_admitted(f.token)
        b.inputs=original;f.token.lease.inputs=replace(original)
        with self.assertRaises((ValueError,RuntimeError)):profile.gate_admitted(f.token)
        f.token.lease.inputs=original
        with self.assertRaises(ValueError):profile.gate_admitted(object())

    def test_changed_getat_code_or_field_literal_is_rejected(self):
        f=self.fixture();base=f.backend.core._handle
        self.assertGreater(profile.verify_live(base,f.read),0)
        for address in (base+profile.GET_AT_RVA,base+0x8c6508,base+0x8c6510):
            def changed(pointer,size):
                raw=f.read(pointer,size)
                if pointer<=address<pointer+size:
                    i=address-pointer;raw=raw[:i]+bytes([raw[i]^1])+raw[i+1:]
                return raw
            with self.subTest(address=hex(address)),self.assertRaises(ValueError):
                profile.verify_live(base,changed)


if __name__=='__main__':unittest.main()
