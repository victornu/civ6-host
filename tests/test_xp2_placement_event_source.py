"""Source guards and explicit XP2 ABI selection for placement events."""
import hashlib
import os
from pathlib import Path
import sys
import unittest

HOST = Path(__file__).resolve().parents[1]
LAB = HOST.parent / "civ6-rl-lab"
os.environ.setdefault("CIV6_HOST_RESOURCE_ROOT", str(LAB))
sys.path.insert(0, str(HOST / "src"))
sys.path.insert(0, str(HOST.parents[1] / "work/python-deps"))

import pefile

from civ6_host.runtime import (faith_event_profile, placement_event_profile,
    xp1_goody_hut_profile, xp2_placement_event_source as selected)
from civ6_host.runtime.saved_load_profiles import XP1_CORE_SHA256, XP2_CORE_SHA256
from civ6_host.runtime.native import native_event_6d7163b0 as district
from civ6_host.runtime.native import native_event_b3495127 as faith


class XP2PlacementSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.proof = selected.source()
        image_path = Path(cls.proof["images"]["xp2"]["path"])
        raw = image_path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != XP2_CORE_SHA256:
            raise AssertionError("Independent XP2 PE image differs from source profile")
        image = pefile.PE(data=raw)
        cls.base = image.OPTIONAL_HEADER.ImageBase
        cls.image = image.get_memory_mapped_image()
        image.close()

    def read(self, address, size):
        self.assertGreater(size, 0)
        self.assertLessEqual(size, 4096)
        offset = address - self.base
        self.assertGreaterEqual(offset, 0)
        self.assertLessEqual(offset + size, len(self.image))
        return bytes(self.image[offset:offset + size])

    def test_producer_family_is_exact_disjoint_and_all_rows_have_receiver_sizes(self):
        self.assertEqual(selected.PLACEMENT_KINDS,
            {0x6D7163B0, 0xF391D7B3, 0xB3495127, 0xC08FC0F9})
        self.assertFalse(selected.PLACEMENT_KINDS & selected.HISTORY_KINDS)
        profile = placement_event_profile.event_profile(core_sha256=XP2_CORE_SHA256)
        self.assertEqual(dict(profile.record_types_by_kind), {
            0x6D7163B0: frozenset((157, 163)),
            0xF391D7B3: frozenset((145,)),
            0xB3495127: frozenset((194,)),
            0xC08FC0F9: frozenset((259,)),
        })
        self.assertEqual(dict(profile.record_sizes),
            {157: 144, 163: 128, 145: 160, 194: 96, 259: 112})
        self.assertEqual(profile.source_sha256, selected.SOURCE[1])
        with self.assertRaises(ValueError):
            placement_event_profile.event_profile(core_sha256=XP1_CORE_SHA256 + "x")

    def test_all_captured_producer_helper_and_query_fragments_match_independent_pe(self):
        result = selected.verify_live(self.base, self.read)
        fragments = [fragment for group in selected._all_bodies(self.proof)
                     for body in group.values() for fragment in body["fragments"]]
        self.assertEqual(result["verified_fragments"], len(fragments))
        self.assertEqual(result["verified_switch_tables"], 1)
        self.assertGreater(len(fragments), 150)
        self.assertEqual(len(self.read(self.base + 0x2C5214, 28)), 28)

    def test_full_dependencies_are_hash_pinned_and_keep_xp1_history(self):
        pins = selected.source_dependencies()
        self.assertGreater(len(pins), 100)
        for filename, digest in pins.items():
            data = Path(filename).read_bytes()
            self.assertEqual(hashlib.sha256(data).hexdigest(), digest, filename)
        from civ6_host.runtime import xp2_history_event_profile
        history = xp2_history_event_profile.event_profile(core_sha256=XP2_CORE_SHA256)
        self.assertTrue(set(history.record_types_by_kind).isdisjoint(selected.PLACEMENT_KINDS))

    def test_district_query_selection_matches_semantic_xp2_operations(self):
        from civ6_host.runtime.foundation_facade_profiles import query_abi
        from civ6_host.runtime.paths import resource_root
        abi = query_abi(XP2_CORE_SHA256, resource_root())
        chosen = placement_event_profile.select_tables(XP2_CORE_SHA256, district._TABLES)
        names = placement_event_profile.OPERATION_NAMES
        table_names = placement_event_profile.TABLE_NAMES
        for label, (_, selected_slots) in chosen.items():
            table_name = table_names[label]
            self.assertEqual(chosen[label][0], abi.table(table_name))
            for slot, target in selected_slots:
                matching = [spec for spec in abi.operations.values()
                            if spec.get("table") == table_name and spec.get("slot") == slot]
                if label == "outer" and slot == 8:
                    target_rva = int(self.proof["faith_query_abi"]["tables"]["outer"]["slots"]["0x8"], 16)
                else:
                    self.assertEqual(len(matching), 1)
                    target_rva = matching[0]["rva"]
                self.assertEqual(target, target_rva)
        retained = {name: (0, restype, args) for name, restype, args in (
            ("get_player", object, (object, int)), ("release_player", None, (object,)),
            ("player_collection", object, (object,)), ("release_collection", None, (object,)),
            ("collection_index", object, (object, int)), ("release_item", None, (object,)),
            ("item_raw", int, (object,)), ("item_variant", object, (object, object)),
            ("item_snapshot", int, (object, object, int)), ("free_vector", None, (object,)),
            ("outer_map", object, (object,)),
            ("release_map", None, (object,)), ("map_plot", object, (object, int, int)),
            ("release_plot", None, (object,)), ("plot_value", int, (object,))) }
        chosen_specs = placement_event_profile.select_specs(XP2_CORE_SHA256, retained)
        for name, operation in names.items():
            self.assertEqual(chosen_specs[name][0], abi.rva(operation))
            self.assertEqual(chosen_specs[name][1:], retained[name][1:])
        contract = self.proof["district_snapshot_contract"]
        snapshot = abi.operations["district_snapshot70"]
        self.assertEqual((snapshot["slot"], snapshot["abi"]),
                         (0x70, "uint8(ptr,out64*,uint32)"))
        self.assertEqual(contract["output_bytes"], 64)
        self.assertEqual(dict(contract["vector_fields"]), {
            "pointer_offset": 40, "capacity_offset": 48, "count_offset": 56})
        rows = {int(row["rva"], 16): row["text"]
                for body in self.proof["query_methods"].values()
                for part in body["fragments"] for row in part["instructions"]}
        self.assertEqual(rows[0x7D936], "lea rdx, [rbx + 0x28]")
        self.assertEqual(rows[0x7D940], "mov dword ptr [rdx + 0x10], 0")
        self.assertEqual(rows[0x190878], "inc dword ptr [rbx + 0x10]")

    def test_faith_and_goody_select_their_exact_xp2_sources(self):
        faith_source = faith_event_profile.verify_source(core_sha256=XP2_CORE_SHA256)
        tables = faith_event_profile.select_tables(XP2_CORE_SHA256, faith._TABLES)
        specs = faith_event_profile.select_specs(XP2_CORE_SHA256, {
            name: (None, object, (object,)) for name in faith_event_profile.OPS})
        for name, table in faith_source["faith_query_abi"]["tables"].items():
            self.assertEqual(tables[name][0], int(table["vtable_rva"], 16))
            self.assertEqual(tables[name][1], {
                int(slot, 16): int(target, 16) for slot, target in table["slots"].items()})
        for name, operation in faith_source["faith_query_abi"]["operations"].items():
            self.assertEqual(specs[name][0], int(operation["target_rva"], 16))
        goody = xp1_goody_hut_profile.verify_source(core_sha256=XP2_CORE_SHA256)
        self.assertIn("0xc08fc0f9", goody["callbacks"])
        self.assertEqual(int(goody["callbacks"]["0xc08fc0f9"]["exe_callback_rva"], 16),
                         selected.EXPECTED_CALLBACKS[0xC08FC0F9])
        with self.assertRaises(ValueError):
            xp1_goody_hut_profile.source_dependencies(core_sha256=XP1_CORE_SHA256 + "x")

    def test_source_hash_mismatch_and_unknown_engine_fail_closed(self):
        from unittest.mock import patch
        changed = dict(self.proof)
        changed["callbacks"] = dict(self.proof["callbacks"])
        changed["callbacks"]["0xf391d7b3"] = dict(changed["callbacks"]["0xf391d7b3"],
                                                    exe_callback_rva="0x149211")
        with patch.object(selected, "_source", return_value=changed):
            with self.assertRaisesRegex(ValueError, "callback/record join changed"):
                selected.source()
        with self.assertRaises(ValueError):
            selected.bind_owner(object(), object(), self.read)


if __name__ == "__main__":
    unittest.main()
