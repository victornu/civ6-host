"""XP2 source and composed read fixtures; no native game execution claim."""
import unittest
from types import SimpleNamespace as NS
from unittest.mock import patch
from civ6_host.runtime import xp1_turn_ui_profile as gate,network_turns
from civ6_host.runtime.configuration_profiles import XP2_CORE_SHA256,XP1_CORE_SHA256
from civ6_host.runtime.captured_session_profile import select
from test_xp1_turn_ui_profile import fixture


class XP2TurnUI(unittest.TestCase):
    def test_complete_named_source_live_bytes_and_late_mutation(self):
        proof=gate.verify_source(XP2_CORE_SHA256)
        self.assertEqual(set(proof['bindings']),set(gate.XP2_CALLBACKS))
        self.assertEqual(sum(b['bytes'] for b in proof['functions'].values()),8098)
        memory={}
        for body in proof['functions'].values():
            for fragment in body['fragments']:
                for row in fragment['instructions']:
                    for i,value in enumerate(bytes.fromhex(row['bytes'])):
                        address=int(row['va'],16)+i
                        self.assertEqual(memory.setdefault(address,value),value)
        for name,row in proof['bindings'].items():
            for i,value in enumerate(name.split('.')[1].encode()+b'\0'):
                memory[0x180000000+row['name_rva']+i]=value
        sizes=[]
        def read(address,size):
            self.assertLessEqual(size,4096);sizes.append(size)
            return bytes(memory[address+i] for i in range(size))
        self.assertGreater(gate.verify_live(0x180000000,read,core_sha256=XP2_CORE_SHA256),0)
        with self.assertRaises((ValueError,KeyError)):
            gate.verify_live(0x180000000,read,core_sha256=XP1_CORE_SHA256)
        memory[max(memory)]^=1
        with self.assertRaises(ValueError):
            gate.verify_live(0x180000000,read,core_sha256=XP2_CORE_SHA256)

    def test_same_saved_owner_uses_xp2_timer_and_native_predicates(self):
        saved=fixture();b=saved.backend;selected=select(XP2_CORE_SHA256)
        b.load_abi=NS(core_sha256=XP2_CORE_SHA256);b._xp2_postload_requested=True
        saved._engine_sha256=XP2_CORE_SHA256;saved.requested['post160_candidate']=True
        saved.inputs.profile=selected.candidate.profile
        saved.inputs.official_bundle=selected.candidate.reference
        b.captured_bundle.reference=selected.candidate.reference
        saved.network_reference['capture_manifest_sha256']=selected.candidate.reference[1]
        with patch.object(gate,'bind_owner') as bind,patch(
                'civ6_host.runtime.network_timer.read',return_value=False) as timer:
            value=gate.read(saved,0,1)
        bind.assert_called_once_with(b)
        timer.assert_called_once_with(b,core_sha256=XP2_CORE_SHA256)
        self.assertEqual(value['source_sha256'],gate.XP2_SOURCE[1])
        self.assertEqual(value['core_sha256'],XP2_CORE_SHA256)
        self.assertIs(value['turn_availability']['force_end_turn'],True)
        self.assertFalse(value['diagnostics']['native_request_acceptance_inferred'])

    def test_activity_requires_same_engine_and_never_changes_order(self):
        saved=fixture();saved.backend.load_abi.core_sha256=XP2_CORE_SHA256
        saved.prefix.runtime.evaluate_text.return_value=b'1|0|0|0,1,1,0;1,1,0,0'
        with patch('civ6_host.runtime.xp1_status_profiles.bind_owner') as bind:
            activity=network_turns.read_activity(saved,core_sha256=XP2_CORE_SHA256)
            self.assertEqual([r['player_id'] for r in activity['rows']],[0,1])
            bind.assert_called_once_with(saved.backend,saved.backend.core,saved.backend.runtime.read)
            with self.assertRaisesRegex(ValueError,'another engine'):
                network_turns.read_activity(saved,core_sha256=XP1_CORE_SHA256)
            self.assertEqual(bind.call_count,1)


if __name__=='__main__':unittest.main()
