from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from civ6_host.runtime import found_unit_event_profiles as profiles
from civ6_host.runtime.configuration_profiles import XP1_CORE_SHA256, XP2_CORE_SHA256


LAB = Path(__file__).resolve().parents[2] / 'civ6-rl-lab'


class FoundUnitEventProfilesTests(unittest.TestCase):
    def test_xp2_found_unit_query_uses_only_exact_profiled_facades_and_map(self):
        abi = profiles.query_abi(XP2_CORE_SHA256, LAB)
        self.assertEqual(abi.core_sha256, XP2_CORE_SHA256)
        self.assertEqual(abi.inner_vtable_rva, 0xA44F70)
        self.assertEqual(dict(abi.tables['outer'][1]), {0xB8: 0x590360})
        self.assertEqual(dict(abi.tables['player'][1]), {0x08: 0x59C8C0, 0x110: 0x59D310})
        self.assertEqual(dict(abi.tables['units'][1]), {0x08: 0x5A0390, 0x10: 0x5A03B0})
        self.assertEqual(dict(abi.tables['unit'][1]), {0x10: 0x5A23B0, 0xA8: 0x5A26D0, 0xB0: 0x5A26A0})
        self.assertEqual(dict(abi.constants), {
            'CORE_PARAMETER_CTOR': 0x99E4B0,
            'CORE_PARAMETER_DTOR': 0x99E8B0,
            'CORE_PARAMETER_LOOKUP': 0x99F5C0,
            'CORE_PARAMETER_VTABLE': 0xABF080,
            'CORE_UNIT_A8': 0x5A26D0,
            'CORE_UNIT_B0': 0x5A26A0,
        })
        deps = profiles.source_dependencies(LAB, core_sha256=XP2_CORE_SHA256)
        unit_path = str(LAB / profiles.XP2_UNIT_SOURCE[0])
        map_path = str(LAB / profiles.XP2_MAP_SOURCE[0])
        self.assertIn(unit_path, deps)
        self.assertIn(map_path, deps)
        self.assertEqual(deps[unit_path], profiles.XP2_UNIT_SOURCE[1])
        self.assertEqual(deps[map_path], profiles.XP2_MAP_SOURCE[1])

    def test_xp2_live_verifier_checks_all_selected_source_bytes_and_rebased_tables(self):
        base = 0x7FFF10000000
        abi = profiles.query_abi(XP2_CORE_SHA256, LAB)
        proof = profiles._xp2_source(LAB)
        bodies = list(proof['unit']['bodies'].values())
        bodies.extend(proof['query_map']['bodies'].values())
        bodies.extend(proof['application']['bodies'][name] for name in ('constructor', 'delete'))
        memory = {}
        for rva, raw in profiles._xp2_instruction_spans(bodies):
            for offset, value in enumerate(raw):
                memory[base + rva + offset] = value
        for vtable, slots in abi.tables.values():
            for slot, target in slots.items():
                memory.update({base + vtable + slot + offset: byte
                               for offset, byte in enumerate((base + target).to_bytes(8, 'little'))})
        lookup = abi.constants['CORE_PARAMETER_VTABLE'] + 0x60
        memory.update({base + lookup + offset: byte
                       for offset, byte in enumerate((base + abi.constants['CORE_PARAMETER_LOOKUP']).to_bytes(8, 'little'))})

        def read(address, size):
            try:
                return bytes(memory[address + offset] for offset in range(size))
            except KeyError as exc:
                raise AssertionError(f'unexpected source read at {address:#x}+{size:#x}') from exc

        receipt = profiles.verify_live(base, read, core_sha256=XP2_CORE_SHA256, root=LAB)
        self.assertEqual(receipt, dict(source_sha256=profiles.XP2_MAP_SOURCE[1],
                                       native_query_invoked=False, event_admitted=False))

    def test_xp2_source_preflight_refuses_changed_profile_before_memory_reads(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / profiles.XP2_UNIT_SOURCE[0]
            path.parent.mkdir(parents=True)
            source = json.loads((LAB / profiles.XP2_UNIT_SOURCE[0]).read_text(encoding='utf-8'))
            source['core_sha256'] = XP1_CORE_SHA256
            path.write_text(json.dumps(source), encoding='utf-8')
            reads = []

            def no_memory_reads(*args):
                reads.append(args)
                raise AssertionError('source preflight must fail before native reads')

            with self.assertRaisesRegex(ValueError, 'returned Unit facade source changed'):
                profiles.verify_live(0x70000000, no_memory_reads,
                                     core_sha256=XP2_CORE_SHA256, root=root)
            self.assertEqual(reads, [])

    def test_xp1_found_unit_profile_remains_on_its_original_source_and_tables(self):
        abi = profiles.query_abi(XP1_CORE_SHA256, LAB)
        self.assertEqual(abi.core_sha256, XP1_CORE_SHA256)
        self.assertEqual(abi.constants['CORE_UNIT_A8'], 0x4CC640)
        self.assertEqual(abi.constants['CORE_UNIT_B0'], 0x4CC610)
        self.assertEqual(profiles.source(LAB)['profile']['inner_vtable_rva'], 0x8D7168)


if __name__ == '__main__':
    unittest.main()
