"""World-source fixtures read the PE file; they never load or execute it."""
import hashlib
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / 'work/python-deps'))
import pefile

from civ6_host.runtime import xp2_world_input_source as selected
from civ6_host.runtime import xp1_world_input_profile as shared
from civ6_host.runtime.configuration_profiles import XP1_CORE_SHA256 as XP1, XP2_CORE_SHA256 as XP2, _copy
from civ6_host.runtime.native.native_official_load import OfficialLoadBackend
from civ6_host.runtime.saved_load_profiles import profile_for_sha


class WorldInputSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.proof = selected.verify_source()
        path = Path(cls.proof['image']['path'])
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != XP2:
            raise AssertionError('Fixture PE image differs from source identity')
        pe = pefile.PE(data=raw)
        cls.base = pe.OPTIONAL_HEADER.ImageBase
        # Independent byte oracle, rather than copying the proposed profile.
        cls.image = pe.get_memory_mapped_image()
        pe.close()

    def fixture(self):
        memory = bytearray(self.image)
        reads = []
        def read(address, size):
            self.assertGreater(size, 0)
            self.assertLessEqual(size, 4096)
            offset = address - self.base
            self.assertGreaterEqual(offset, 0)
            self.assertLessEqual(offset + size, len(memory))
            reads.append((offset, size))
            return bytes(memory[offset:offset+size])
        owner = OfficialLoadBackend.__new__(OfficialLoadBackend)
        owner.core = SimpleNamespace(_handle=self.base)
        owner.load_abi = profile_for_sha(XP2)
        owner.thread = (11, 19)
        owner.runtime = SimpleNamespace(thread=lambda: owner.thread)
        owner.poisoned = owner.destroyed = False
        return owner, memory, read, reads

    def test_exact_registrar_pairs_and_inherited_official_route(self):
        self.assertEqual(len(self.proof['bindings']), 14)
        self.assertEqual(self.proof['bindings']['Plot.GetX']['registrar_rva'], '0x1b2e0')
        self.assertEqual(self.proof['bindings']['UnitManager.GetQueuedDestination']['callback_rva'], '0x6c1fc0')
        self.assertEqual(len(self.proof['functions']), 74)
        from civ6_host.runtime.native.native_movement_ui_source import source_manifest
        self.assertEqual(source_manifest()['functions'], self.proof['ui_route']['shared_functions'])
        self.assertFalse(self.proof['contracts']['war_confirmation_admitted'])
        self.assertFalse(self.proof['contracts']['full_movement_or_combat_qualified'])
        self.assertEqual(shared.verify_source(XP2), self.proof)
        self.assertEqual(shared.verify_source()['image']['sha256'], XP1)
        for bad in (XP1, 'unknown', None):
            with self.subTest(engine=bad), self.assertRaises(ValueError):
                selected.verify_source(bad)

    def test_swap_supplement_pins_only_the_inherited_can_start_request_branch(self):
        swap = selected.verify_swap_source()
        route = self.proof['ui_route']['shared_functions']
        self.assertEqual(swap['official_functions']['MoveUnitToPlot']['extracted_sha256'],
                         route['MoveUnitToPlot']['extracted_sha256'])
        self.assertEqual(swap['official_functions']['RequestMoveOperation']['extracted_sha256'],
                         route['RequestMoveOperation']['extracted_sha256'])
        self.assertEqual(swap['route']['operation_symbol'], 'UnitOperationTypes.SWAP_UNITS')
        self.assertIn('CanStartOperation', swap['route']['legality_owner'])
        self.assertFalse(swap['scope']['war_confirmation_admitted'])
        self.assertFalse(swap['scope']['other_request_operations_admitted'])
        self.assertFalse(swap['scope']['full_movement_or_combat_qualified'])
        original = selected._source
        altered = dict(swap)
        altered['route'] = dict(swap['route'], request_call='UnitManager.RequestOperation(kUnit, 999, tParameters)')
        with patch.object(selected, '_source', side_effect=lambda ref:
                          altered if ref == selected.SWAP_SOURCE else original(ref)):
            with self.assertRaisesRegex(ValueError, 'supplement differs'):
                selected.verify_swap_source()

    def test_full_live_fragments_bounded_and_independent_installed_pe(self):
        _, _, read, reads = self.fixture()
        self.assertEqual(selected.verify_live(self.base, read), 92)
        covered = {rva+i for rva, size in reads for i in range(size)}
        fragments = tuple(selected._fragments(self.proof))
        self.assertEqual(len(fragments), 77)
        for rva, raw in fragments:
            self.assertTrue(all(rva+i in covered for i in range(len(raw))))
        self.assertIn((0x1B2E0+4096, 4241-4096), reads)
        self.assertEqual(max(size for _, size in reads), 4096)

    def test_second_chunk_early_ret_tail_nested_lock_and_binding_name_fail(self):
        name = self.proof['bindings']['UnitManager.GetQueuedDestination']['name_va']
        addresses = (0x1C370, 0x6C203B, 0xD0DC8, int(name, 16)-self.base)
        for rva in addresses:
            with self.subTest(rva=hex(rva)):
                _, memory, read, _ = self.fixture()
                memory[rva] ^= 1
                with self.assertRaisesRegex(ValueError, 'live source changed'):
                    selected.verify_live(self.base, read)

    def test_short_reads_and_nonbytes_do_not_pass(self):
        for read in (lambda a, n: b'', lambda a, n: memoryview(self.image[a-self.base:a-self.base+n])):
            with self.assertRaisesRegex(ValueError, 'live source changed'):
                selected.verify_live(self.base, read)
        for base in (0, True, -1, 1 << 47):
            with self.assertRaises(ValueError): selected.verify_live(base, lambda a, n: b'')

    def test_source_semantic_and_completeness_mutations_refused(self):
        original = selected._source
        def changed_binding(p):
            p['bindings']['Plot.GetX']['registrar_rva'] = '0x7133b0'
        def changed_target(p):
            p['bindings']['Unit.GetComponentID']['callback_reference_va'] = p['bindings']['Unit.GetPlotId']['callback_reference_va']
        def missing_branch(p):
            p['functions']['0x6c1fc0']['conditional_branch_targets_verified'][0]['target_rva'] = '0x6c2038'
        def changed_nested_meaning(p):
            body = p['functions']['0x6c1fc0']
            for rows in (body['instructions'], body['fragments'][0]['instructions']):
                next(r for r in rows if r['rva']=='0x6c1fe7')['text'] = 'mov edx, dword ptr [rax + 0xec]'
        for mutate in (changed_binding, changed_target, missing_branch, changed_nested_meaning):
            proof = _copy(self.proof)
            mutate(proof)
            with self.subTest(mutation=mutate.__name__), patch.object(selected, '_source',
                    side_effect=lambda reference: proof if reference==selected.SOURCE else original(reference)):
                with self.assertRaises(ValueError): selected.verify_source()

    def test_real_backend_joins_status_operation_and_world_once_per_owner(self):
        owner, _, read, reads = self.fixture()
        receipt = shared.bind_owner(owner, owner.core, read)
        self.assertIs(type(receipt), selected.VerifiedWorldInputSource)
        self.assertEqual(receipt.core_sha256, XP2)
        self.assertEqual(receipt.source_sha256, selected.SOURCE[1])
        status = owner._xp1_status_source_receipt
        self.assertIs(status.owner, owner)
        self.assertEqual(status.core_sha256, XP2)
        # Native operation callbacks and their complete bodies were really read.
        self.assertTrue(any(rva==0x6C0390 for rva, _ in reads))
        self.assertTrue(any(rva==0x6C3150 for rva, _ in reads))
        self.assertTrue(any(rva==0xD0CE0 for rva, _ in reads))
        count = len(reads)
        self.assertIs(selected.bind_owner(owner, owner.core, read), receipt)
        self.assertEqual(count, len(reads))
        foreign, _, foreign_read, _ = self.fixture()
        foreign.core = owner.core
        foreign._xp2_world_input_source_receipt = receipt
        with self.assertRaisesRegex(ValueError, 'another lifetime'):
            selected.bind_owner(foreign, foreign.core, foreign_read)
        owner.poisoned = True
        with self.assertRaisesRegex(RuntimeError, 'poisoned'):
            selected.bind_owner(owner, owner.core, read)

    def test_real_selected_helpers_cannot_be_bypassed_by_world_receipt(self):
        # Only native memory is a fixture. Neither helper nor owner check is mocked.
        from civ6_host.runtime.xp2_initial_choice_source import CALLBACKS
        status_entry = CALLBACKS['status']['Game.GetCurrentGameTurn']
        for rva in (status_entry, 0x6C3150, 0xD0CE0):
            owner, memory, read, _ = self.fixture()
            memory[rva] ^= 1
            with self.subTest(rva=hex(rva)), self.assertRaises(ValueError):
                selected.bind_owner(owner, owner.core, read)
            self.assertFalse(hasattr(owner, '_xp2_world_input_source_receipt'))
        owner, _, read, _ = self.fixture()
        owner.load_abi = profile_for_sha(XP1)
        with self.assertRaisesRegex(ValueError, 'owner mismatch'):
            selected.bind_owner(owner, owner.core, read)

    def test_complete_dependency_join_keeps_historical_and_selected_sources(self):
        pins = selected.source_dependencies()
        self.assertIn(selected.SOURCE[1], pins.values())
        self.assertIn(selected.SWAP_SOURCE[1], pins.values())
        self.assertIn(shared.SOURCE[1], pins.values())
        self.assertTrue(any('xp2-initial-choices' in p for p in pins))
        self.assertTrue(any('xp2-action-transport' in p for p in pins))
        self.assertTrue(any('WorldInput_Expansion2.lua' in p for p in pins))
        for path, digest in pins.items():
            with self.subTest(path=path):
                self.assertEqual(hashlib.sha256(Path(path).read_bytes()).hexdigest(), digest)


if __name__ == '__main__':
    unittest.main()
