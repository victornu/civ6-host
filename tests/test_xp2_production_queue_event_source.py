"""Offline sourceguard tests for XP2 production-queue event producers."""
import hashlib
import os
from pathlib import Path
import sys
import threading
from types import MappingProxyType, SimpleNamespace
import unittest
from unittest.mock import patch

HOST = Path(__file__).resolve().parents[1]
LAB = HOST.parent / "civ6-rl-lab"
os.environ.setdefault("CIV6_HOST_RESOURCE_ROOT", str(LAB))
sys.path.insert(0, str(HOST / "src"))
sys.path.insert(0, str(HOST.parents[1] / "work/python-deps"))

import pefile

from civ6_host.runtime import a0_family_source
from civ6_host.runtime import xp2_production_queue_event_source as selected
from civ6_host.runtime.configuration_profiles import _copy
from civ6_host.runtime.native.native_official_load import OfficialLoadBackend
from civ6_host.runtime.saved_load_profiles import profile_for_sha


class XP2ProductionQueueEventSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.proof = selected.source()
        image_path = Path(cls.proof["images"]["xp2"]["path"])
        raw = image_path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != selected.XP2_CORE_SHA256:
            raise AssertionError("Independent XP2 Core image differs from captured source")
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
        backend.thread = threading.get_ident()
        backend.runtime = SimpleNamespace(thread=lambda: backend.thread)
        backend.runtime.read = read
        backend.poisoned = False
        backend.destroyed = False
        return backend, memory, read, reads

    def test_exact_producer_helpers_and_dispatch_match_independent_pe(self):
        _, _, read, reads = self.fixture()
        result = selected.verify_live(self.base, read)
        fragments = [fragment for collection in (
            self.proof["functions"], self.proof["direct_helper_functions"],
            self.proof["queue_dispatch_functions"])
            for body in collection.values() for fragment in body["fragments"]]
        self.assertEqual(result["verified_fragments"], len(fragments))
        self.assertEqual(len(fragments), 166)
        self.assertLessEqual(max(size for _, size in reads), 4096)
        self.assertGreater(max(size for _, size in reads), 0)
        covered = {offset + i for offset, size in reads for i in range(size)}
        for fragment in fragments:
            start = int(fragment["start_rva"], 16)
            self.assertTrue(all(start + i in covered for i in range(fragment["length"])))

    def test_queue_callback_map_and_shared_a0_record_types_are_exact(self):
        self.assertEqual(dict(selected.callback_mapping()), {
            0x92492F56: 0x141EA0,
            0x2842CE14: 0x141A40,
        })
        a0 = a0_family_source.source()["initial_group"]
        mapping = {int(k): tuple(v) for k, v in a0["kind_to_record_types"].items()}
        sizes = {int(k): v for k, v in a0["record_type_to_size"].items()}
        self.assertEqual(mapping[0x2842CE14], (95,))
        self.assertEqual(mapping[0x92492F56], (98,))
        self.assertEqual(sizes[95], 112)
        self.assertEqual(sizes[98], 112)
        # The neighboring absent event stays on the independently sourced
        # shared no-callback path; it is not synthesized by the queue profile.
        from civ6_host.runtime.xp2_world_unit_event_source import callback_mapping as world_mapping
        self.assertIsNone(world_mapping()[selected.ABSENT_QUEUE_EVENT_KIND])

    def test_source_receipt_binds_actual_backend_and_rechecks_code(self):
        backend, _, read, reads = self.fixture()
        receipt = selected.bind_owner(backend, backend.core, read)
        self.assertIs(type(backend), OfficialLoadBackend)
        self.assertIs(type(receipt), selected.VerifiedProductionQueueEventSource)
        self.assertIs(receipt.owner, backend)
        self.assertIs(receipt.core, backend.core)
        self.assertEqual(receipt.core_sha256, selected.XP2_CORE_SHA256)
        self.assertEqual(receipt.source_sha256, selected.SOURCE[1])
        self.assertEqual(receipt.verified_fragments, 166)
        prior_reads = len(reads)
        self.assertIs(selected.bind_owner(backend, backend.core, read), receipt)
        self.assertGreater(len(reads), prior_reads)

    def test_foreign_engine_core_owner_and_poisoned_backend_are_refused(self):
        backend, _, read, _ = self.fixture()
        backend.load_abi = profile_for_sha(XP1 := "259b90a473a256aff6a7d621a4f3717e46f6921c59b9817475375c88b97e8c83")
        with self.assertRaisesRegex(ValueError, "owner mismatch"):
            selected.bind_owner(backend, backend.core, read)

        backend, _, read, _ = self.fixture()
        with self.assertRaisesRegex(ValueError, "owner mismatch"):
            selected.bind_owner(backend, SimpleNamespace(_handle=self.base), read)

        backend, _, read, _ = self.fixture()
        backend.poisoned = True
        with self.assertRaisesRegex(RuntimeError, "foreign-thread, poisoned or destroyed"):
            selected.bind_owner(backend, backend.core, read)

        _, _, other_read, _ = self.fixture()
        with self.assertRaisesRegex(ValueError, "actual saved Load backend"):
            selected.bind_owner(object(), backend.core, other_read)

    def test_parent_producer_and_callback_mutations_fail_closed(self):
        original = selected._source

        def refused(mutate):
            proof = _copy(self.proof)
            mutate(proof)
            with patch.object(selected, "_source",
                              side_effect=lambda reference: proof if reference == selected.SOURCE
                              else original(reference)):
                with self.assertRaises(ValueError):
                    selected.source()

        def change_queue_parent(proof):
            proof["parents"]["retained_queue_profile"]["sha256"] = "0" * 64

        def drop_producer_reference(proof):
            proof["callbacks"]["0x92492f56"]["immediate_references"].pop()

        def change_callback_target(proof):
            proof["callbacks"]["0x2842ce14"]["exe_callback_rva"] = "0x141a41"

        for mutate in (change_queue_parent, drop_producer_reference, change_callback_target):
            with self.subTest(mutation=mutate.__name__):
                refused(mutate)

    def test_registry_mutation_and_a0_codec_mutation_fail_closed(self):
        changed_registry = dict(selected.EXE_EVENT_CALLBACKS)
        changed_registry[0x92492F56] = 0x141EA1
        with patch.object(selected, "EXE_EVENT_CALLBACKS", MappingProxyType(changed_registry)):
            with self.assertRaisesRegex(ValueError, "shared EXE registry"):
                selected.source()

        original = a0_family_source.source
        changed = _copy(original())
        changed["initial_group"]["kind_to_record_types"][str(0x2842CE14)] = [96]
        with patch.object(a0_family_source, "source", return_value=changed):
            with self.assertRaisesRegex(ValueError, "Shared EXE queue callback record mapping"):
                selected.source()

    def test_complete_dependency_closure_hashes_all_selected_sources(self):
        pins = selected.source_dependencies()
        self.assertIn(selected.SOURCE[1], pins.values())
        self.assertIn(selected.PARENT_PINS["retained_queue_profile"][1], pins.values())
        self.assertIn(selected.PARENT_PINS["prior_xp2_world_unit_source"][1], pins.values())
        self.assertGreaterEqual(len(pins), 500)
        for path, digest in pins.items():
            with self.subTest(path=path):
                self.assertEqual(hashlib.sha256(Path(path).read_bytes()).hexdigest(), digest)


if __name__ == "__main__":
    unittest.main()
