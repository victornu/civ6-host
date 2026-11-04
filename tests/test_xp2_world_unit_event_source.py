"""Offline sourceguard checks for retained XP2 world/unit A0 event kinds."""
import hashlib
import json
import os
from pathlib import Path
import sys
from types import MappingProxyType, SimpleNamespace
import unittest
from unittest.mock import patch

HOST = Path(__file__).resolve().parents[1]
LAB = HOST.parent / "civ6-rl-lab"
os.environ.setdefault("CIV6_HOST_RESOURCE_ROOT", str(LAB))
sys.path.insert(0, str(HOST / "src"))
sys.path.insert(0, str(HOST.parents[1] / "work/python-deps"))

import pefile

from civ6_host.runtime import xp2_world_unit_event_source as selected
from civ6_host.runtime.configuration_profiles import _copy
from civ6_host.runtime.native.native_official_load import OfficialLoadBackend
from civ6_host.runtime.saved_load_profiles import profile_for_sha


class XP2WorldUnitSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.proof = selected.source()
        image_path = Path(cls.proof["images"]["xp2"]["path"])
        raw = image_path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != selected.XP2_CORE_SHA256:
            raise AssertionError("Independent XP2 PE image differs from selected source")
        image = pefile.PE(data=raw)
        cls.base = image.OPTIONAL_HEADER.ImageBase
        cls.image = image.get_memory_mapped_image()
        image.close()

    def fixture(self):
        memory = bytearray(self.image)
        reads = []

        def read(address, size):
            self.assertIs(type(address), int)
            self.assertGreater(size, 0)
            self.assertLessEqual(size, selected.MAX_READ_BYTES)
            offset = address - self.base
            self.assertGreaterEqual(offset, 0)
            self.assertLessEqual(offset + size, len(memory))
            reads.append((offset, size))
            return bytes(memory[offset:offset + size])

        backend = OfficialLoadBackend.__new__(OfficialLoadBackend)
        backend.core = SimpleNamespace(_handle=self.base)
        backend.load_abi = profile_for_sha(selected.XP2_CORE_SHA256)
        backend.thread = (11, 19)
        backend.runtime = SimpleNamespace(thread=lambda: backend.thread)
        backend.poisoned = False
        backend.destroyed = False
        return backend, memory, read, reads

    def test_full_core_bodies_match_independent_pe_in_bounded_reads(self):
        _, _, read, reads = self.fixture()
        result = selected.verify_live(self.base, read)
        fragments = [fragment for body in self.proof["functions"].values()
                     for fragment in body["fragments"]]
        self.assertEqual(result["verified_fragments"], len(fragments))
        self.assertEqual(len(reads), sum((fragment["length"] + 4095) // 4096 for fragment in fragments))
        self.assertLessEqual(max(size for _, size in reads), 4096)
        self.assertTrue(any(size == 4096 for _, size in reads))
        # The final bytes of the longest captured function are read too.
        longest = max(fragments, key=lambda fragment: fragment["length"])
        start = int(longest["start_rva"], 16)
        self.assertIn((start + 4096, longest["length"] - 4096), reads)
        self.assertEqual(longest["length"], 4547)

    def test_registry_mapping_is_exact_and_absent_9ea4_cannot_be_selected(self):
        mapping = selected.callback_mapping()
        expected = {
            int(kind, 16): (None if row["exe_callback_rva"] is None
                            else int(row["exe_callback_rva"], 16))
            for kind, row in self.proof["callbacks"].items()
        }
        self.assertEqual(dict(mapping), expected)
        self.assertEqual(sum(value is not None for value in mapping.values()), 16)
        self.assertIsNone(mapping[0x9EA4C222])
        with self.assertRaisesRegex(ValueError, "no registered"):
            selected.callback_rva(0x9EA4C222)
        self.assertEqual(selected.callback_rva(0x15C35863), expected[0x15C35863])

    def test_receipt_binds_actual_official_backend_and_rechecks_live_code(self):
        backend, _, read, reads = self.fixture()
        receipt = selected.bind_owner(backend, backend.core, read)
        self.assertIs(type(backend), OfficialLoadBackend)
        self.assertIs(type(receipt), selected.VerifiedWorldUnitEventSource)
        self.assertIs(receipt.owner, backend)
        self.assertIs(receipt.core, backend.core)
        self.assertEqual(receipt.core_sha256, selected.XP2_CORE_SHA256)
        self.assertEqual(receipt.source_sha256, selected.SOURCE[1])
        self.assertEqual(receipt.verified_fragments, 196)
        count = len(reads)
        self.assertIs(selected.bind_owner(backend, backend.core, read), receipt)
        self.assertGreater(len(reads), count, "receipt reuse must re-read live XP2 Core code")

    def test_wrong_engine_core_and_owner_receipts_are_refused(self):
        backend, _, read, _ = self.fixture()
        wrong_engine = profile_for_sha("259b90a473a256aff6a7d621a4f3717e46f6921c59b9817475375c88b97e8c83")
        backend.load_abi = wrong_engine
        with self.assertRaisesRegex(ValueError, "owner mismatch"):
            selected.bind_owner(backend, backend.core, read)

        backend, _, read, _ = self.fixture()
        foreign_core = SimpleNamespace(_handle=self.base)
        with self.assertRaisesRegex(ValueError, "owner mismatch"):
            selected.bind_owner(backend, foreign_core, read)

        backend, _, read, _ = self.fixture()
        receipt = selected.bind_owner(backend, backend.core, read)
        foreign_owner, _, foreign_read, _ = self.fixture()
        foreign_owner.core = backend.core
        foreign_owner._xp2_world_unit_event_source_receipt = receipt
        with self.assertRaisesRegex(ValueError, "another owner"):
            selected.bind_owner(foreign_owner, foreign_owner.core, foreign_read)

    def test_source_parent_callback_and_absent_mutations_fail_closed(self):
        original = selected._source

        def refused(mutator):
            proof = _copy(self.proof)
            mutator(proof)
            with patch.object(selected, "_source",
                              side_effect=lambda reference: proof if reference == selected.SOURCE
                              else original(reference)):
                with self.assertRaises(ValueError):
                    selected.source()

        def change_parent(proof):
            proof["parents"]["turn_filter_registration"]["sha256"] = "0" * 64

        def change_registered_callback(proof):
            proof["callbacks"]["0x15c35863"]["exe_callback_rva"] = "0x158051"

        def synthesize_absent_callback(proof):
            proof["callbacks"]["0x9ea4c222"]["exe_callback_rva"] = "0x145950"
            proof["callbacks"]["0x9ea4c222"]["absent_from_exe_registry"] = False

        def mutate_instruction_mapping(proof):
            proof["callbacks"]["0x15c35863"]["immediate_references"][0]["instruction_bytes"] = "90"

        for mutation in (change_parent, change_registered_callback,
                         synthesize_absent_callback, mutate_instruction_mapping):
            with self.subTest(mutation=mutation.__name__):
                refused(mutation)

    def test_complete_source_dependencies_are_verified_and_include_parent_profiles(self):
        pins = selected.source_dependencies()
        self.assertIn(selected.SOURCE[1], pins.values())
        self.assertIn(selected.PARENT_PINS["turn_filter_registration"][1], pins.values())
        self.assertIn(selected.PARENT_PINS["unit_orders"][1], pins.values())
        self.assertGreaterEqual(len(pins), 300)
        for path, expected in pins.items():
            with self.subTest(path=path):
                self.assertEqual(hashlib.sha256(Path(path).read_bytes()).hexdigest(), expected)


if __name__ == "__main__":
    unittest.main()
