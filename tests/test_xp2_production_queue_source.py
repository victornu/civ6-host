"""Exact queue source, captured UI admission and actual saved-owner fixtures."""
from dataclasses import replace
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[3]/'work/python-deps'))
import pefile

from civ6_host.runtime import xp2_production_queue_source as profile
from civ6_host.runtime.configuration_profiles import _copy, XP1_CORE_SHA256 as XP1, XP2_CORE_SHA256 as XP2
from civ6_host.runtime.paths import resource_root


@lru_cache(maxsize=1)
def captured_inputs():
    from civ6_host.runtime.native.native_official_load import OfficialInputs
    from civ6_host.runtime.native.native_official_bundle import parse_configuration
    from civ6_host.runtime.native.official_application_configuration import extract_application_configuration
    from civ6_host.runtime import xp2_bundle_inputs as selected
    folder = resource_root()/'work/official-capture/xp2-gs-lan-rows-20261102-04/save-capture/48b816c0af186d477f412c10bba40d22f1281d57341d4c5644e95a0e2ce0a430'
    configuration, _ = extract_application_configuration((folder/'source.Civ6Save').read_bytes())
    _, maps = parse_configuration(configuration, 'LAN')
    games = list(folder.glob('*gamecore_stream_candidate.raw'))
    if len(games) != 1:
        raise AssertionError('Expected one retained XP2 Game stream')
    game = games[0].read_bytes()
    selected.validate_components(configuration, game)
    return OfficialInputs(configuration, game, maps, selected.XP2_LAN_PROFILE, None, selected.REFERENCE)


class QueueSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.proof = profile.verify_source()
        raw = Path(cls.proof['image']['path']).read_bytes()
        if hashlib.sha256(raw).hexdigest() != XP2:
            raise AssertionError('Independent PE oracle differs')
        image = pefile.PE(data=raw)
        cls.base = image.OPTIONAL_HEADER.ImageBase
        cls.memory = image.get_memory_mapped_image()
        image.close()

    def read(self, address, size):
        self.assertTrue(0 < size <= 4096)
        return self.memory[address-self.base:address-self.base+size]

    def graph(self):
        # Keep the concrete continuation/publication/lease graph and its real
        # owner guards. Only native memory and native-effect fixtures are reused.
        import test_xp2_continuation_lifetime as fixture
        from test_xp2_initial_choices import populate
        from civ6_host.runtime.xp2_initial_choice_source import source
        from civ6_host.runtime.native.native_official_bundle import PreparedBundle
        from civ6_host.runtime.xp2_bundle_inputs import REFERENCE
        setup = fixture.ContinuationLifetimeTests()
        self.addCleanup(setup.doCleanups)
        f, b, services, lease, continuation, transport = setup.graph()
        populate(f.put, f.core_base, source('production'))
        for body in self.proof['functions'].values():
            for frag in body['fragments']:
                f.put(f.core_base+int(frag['start_rva'], 16), bytes.fromhex(frag['raw_hex']))
        for row in self.proof['embedded_tables'].values():
            f.put(f.core_base+int(row['rva'], 16), bytes.fromhex(row['raw_hex']))
        for va, text in {**self.proof['callback_literals'], '0x180a2f828':'GetAt'}.items():
            f.put(f.core_base+int(va, 16)-self.base, text.encode()+b'\0')
        inputs = captured_inputs()
        b.inputs = lease.inputs = inputs
        b.reader.transport.cursor = len(inputs.game)
        b.captured_bundle = PreparedBundle(REFERENCE, inputs, 1, Path(self.proof['image']['path']), {}, {},
            dict(turn=1, width=44, height=26, player_id=0),
            dict(engine=dict(gamecore_sha256=XP2), gameplay_scripts=dict(selected_and_active_empty=False,
                selected_path_count=1, active_count=1, source_records=1, source_files=1)))
        original_read = b.runtime.read
        def bounded(address, size):
            self.assertTrue(0 < size <= 4096)
            return original_read(address, size)
        b.runtime.read = bounded
        return f, b, continuation

    def test_exact_getat_abi_fields_and_actual_pe_registration(self):
        self.assertEqual(profile.GET_AT_RVA, 0x68BE20)
        self.assertEqual(len(self.proof['functions']), 22)
        self.assertEqual(self.proof['contracts']['entry_stride'], 56)
        self.assertEqual(self.proof['contracts']['queue_size_offset'], 0x368)
        self.assertEqual(self.proof['contracts']['queue_pointer_offset'], 0x358)
        binding = self.proof['bindings']['BuildQueue.GetAt']
        instruction = self.read(int(binding['callback_reference_va'], 16), 7)
        self.assertEqual(instruction[:3], bytes.fromhex('488d15'))
        self.assertEqual(int(binding['callback_reference_va'], 16)+7+
            int.from_bytes(instruction[3:], 'little', signed=True), self.base+profile.GET_AT_RVA)
        self.assertEqual(profile.verify_live(self.base, self.read), 38)
        for body in self.proof['functions'].values():
            for frag in body['fragments']:
                self.assertEqual(self.read(self.base+int(frag['start_rva'], 16), frag['length']), bytes.fromhex(frag['raw_hex']))

    def test_full_after_ret_index_branch_key_and_embedded_table_mutations_refuse(self):
        for rva in (profile.GET_AT_RVA, 0x6BC46, 0xD9D3, 0xA2F840, 0x68C40E):
            def changed(address, size):
                raw = self.read(address, size)
                offset = self.base+rva-address
                if 0 <= offset < size:
                    raw = raw[:offset]+bytes([raw[offset]^1])+raw[offset+1:]
                return raw
            with self.subTest(rva=hex(rva)), self.assertRaises(ValueError):
                profile.verify_live(self.base, changed)

    def test_retained_xp2_ui_witnesses_not_xp1_and_no_dynamic_state_replay(self):
        p = self.proof
        self.assertTrue(all('xp2-gs-lan-rows-20261102-04' in ref['path'] for ref in p['captured_ui_witnesses']))
        self.assertFalse(p['gate']['dynamic_game_state_replayed'])
        self.assertFalse(p['gate']['runtime_context_sources_verified'])
        for ref in p['captured_ui_witnesses']:
            ui = profile._source((ref['path'], ref['sha256']))['diagnostics']['ui_availability']
            self.assertEqual(ui['controls']['production_queue_container']['hidden']['value'], True)
            self.assertEqual(ui['selection']['city_present']['value'], False)
            self.assertEqual(ui['tutorial']['production_test_mode']['status'], 'unknown')
        # Those raw unknown/closed states are preserved; visible QueueTab plus
        # pinned source establishes the immutable route, not a selected city.
        profile._witness(p)
        profile._ui_source(p)

    def test_unavailable_or_foreign_capture_cannot_admit_gate(self):
        original = profile._source
        ref = self.proof['captured_ui_witnesses'][0]
        for kind in ('hidden', 'tutorial', 'unknown', 'foreign core'):
            from civ6_host.runtime.xp2_bundle_inputs import REFERENCE
            altered = _copy(original(REFERENCE if kind=='foreign core' else (ref['path'], ref['sha256'])))
            if kind=='foreign core': altered['process_after']['gamecore_module']['sha256'] = XP1
            else:
                ui = altered['diagnostics']['ui_availability']
                if kind=='hidden':ui['controls']['production_queue_tab']['hidden']['value'] = True
                elif kind=='tutorial':ui['tutorial']['active']['value'] = True
                else:ui['controls']['production_queue_tab']['disabled'] = dict(status='unknown', reason='absent')
            target = REFERENCE if kind=='foreign core' else (ref['path'], ref['sha256'])
            with self.subTest(kind=kind), patch.object(profile, '_source', side_effect=lambda r: altered if r==target else original(r)):
                with self.assertRaises(ValueError): profile._witness(self.proof)

    def test_source_hash_engine_layout_and_conditional_coverage_refuse(self):
        for sha in (XP1, 'unknown'):
            with self.assertRaises(ValueError): profile.verify_source(sha)
        with patch.object(profile, 'SOURCE', (profile.SOURCE[0], '0'*64)):
            with self.assertRaises((ValueError, RuntimeError)): profile.verify_source()
        original = profile._source
        for mutation in ('stride', 'branch', 'registration'):
            p = _copy(self.proof)
            if mutation=='stride':
                body = p['functions']['0x6bc30']
                for rows in (body['instructions'], body['fragments'][0]['instructions']):
                    next(r for r in rows if r['rva']=='0x6bc3a')['text'] = 'imul rax, rax, 0x30'
            elif mutation=='branch':p['functions']['0x6bc30']['conditional_branch_targets_verified'][0]['target_rva'] = '0x6bc47'
            else:p['bindings']['BuildQueue.GetAt']['callback_rva'] = '0x5a7770'
            with self.subTest(mutation=mutation), patch.object(profile, '_source', side_effect=lambda r: p if r==profile.SOURCE else original(r)):
                with self.assertRaises(ValueError): profile.verify_source()

    def test_actual_saved_graph_input_owner_and_gate_lease(self):
        f, b, c = self.graph()
        receipt = profile.bind_owner(b, b.core, b.runtime.read)
        self.assertTrue(profile.gate_admitted(c))
        self.assertEqual(receipt.core_sha256, XP2)
        self.assertEqual(b._xp1_production_source_receipt.core, b.core)
        self.assertIs(profile.bind_owner(b, b.core, b.runtime.read), receipt)
        original = b.inputs
        b.inputs = replace(original)
        with self.assertRaises((ValueError, RuntimeError)): profile.gate_admitted(c)
        b.inputs = original
        c.lease.inputs = replace(original)
        with self.assertRaises((ValueError, RuntimeError)): profile.gate_admitted(c)
        c.lease.inputs = original
        b._xp2_production_queue_source_receipt = replace(receipt, source_sha256='0'*64)
        with self.assertRaisesRegex(ValueError, 'another saved lifetime'): profile.gate_admitted(c)
        b._xp2_production_queue_source_receipt = receipt
        b.poisoned = True
        with self.assertRaises((ValueError, RuntimeError)): profile.gate_admitted(c)
        with self.assertRaises(ValueError): profile.gate_admitted(object())

    def test_selected_production_helper_failure_never_installs_receipt(self):
        f, b, _ = self.graph()
        from civ6_host.runtime.xp2_initial_choice_source import CALLBACKS
        at = f.core_base+CALLBACKS['production']['BuildQueue.CanProduce']
        f.memory[at] ^= 1
        with self.assertRaises(ValueError): profile.bind_owner(b, b.core, b.runtime.read)
        self.assertFalse(hasattr(b, '_xp2_production_queue_source_receipt'))

    def test_full_pin_closure_keeps_partial_catalogue_limit_explicit(self):
        deps = profile.source_dependencies()
        self.assertIn(profile.SOURCE[1], deps.values())
        for path, sha in deps.items():
            self.assertEqual(hashlib.sha256(Path(path).read_bytes()).hexdigest(), sha)
        self.assertEqual(set(self.proof['contracts']['partial_append_gaps']),
                         {'placement_required_items', 'nonstandard_unit_formations'})
        self.assertEqual(self.proof['contracts']['public_schema'], 'civ6rl.production_queue.public.v2')


if __name__ == '__main__':
    unittest.main()
