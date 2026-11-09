"""XP2 placement family on the existing continuation, A0 service and FIFO."""
import ctypes as C
import struct
import unittest
from unittest.mock import patch

from civ6_host.runtime import (a0_foundation_events, foundation_facade_profiles,
    xp2_placement_event_source, placement_event_profile, faith_event_profile)
from civ6_host.runtime.saved_load_profiles import XP2_CORE_SHA256
from civ6_host.runtime import xp2_turn_notification_source as turn_source
from civ6_host.runtime import xp2_wmd_fallout_visibility, xp2_wonder_completion
from civ6_host.runtime.native import (native_event_6d7163b0 as district,
    native_event_6d7163b0_selector as district_selector,
    native_event_f391d7b3 as visibility, native_event_b3495127 as faith,
    native_event_fa5b1159 as shared_query, native_event_a625c726 as turn_query)
from test_xp1_turn_a0 import scalar
import test_xp2_climate_composition as climate_composition
from test_xp2_turn_notifications import pending_civilization_render


class XP2PlacementCompositionTests(unittest.TestCase):
    def graph(self):
        graph = climate_composition.ClimateCompositionTests().graph()
        self.addCleanup(self._close, graph)
        from civ6_host.runtime.native.native_official_load import OfficialLoadBackend
        old_backend = graph.backend
        backend = OfficialLoadBackend.__new__(OfficialLoadBackend)
        backend.__dict__.update(old_backend.__dict__)
        owner = graph.owner
        token, prefix = graph.continuation, graph.prefix
        # Keep the existing native-memory graph and rebind its real owner
        # references to one exact OfficialLoadBackend fixture instance.
        backend.prefix = prefix
        backend._xp1_continuation = token
        backend._xp1_player_view = token.view
        prefix.backend = backend
        token.owner = backend
        for child in (token.publication, token.view, token.lease, token.lease.attempt):
            if hasattr(child, "owner"):
                child.owner = backend
        if hasattr(prefix.actions, "backend"):
            prefix.actions.backend = backend
        owner._foundation_backend = backend
        graph.backend = backend
        token.check(active=True)
        base = backend.core._handle

        # The returned XP2 composition is already live. Rewind only the fixture's
        # saved-stage labels for the real installation APIs, then restore its
        # actual continuation/stage before any callback is invoked.
        query_proof = __import__("civ6_host.runtime.xp2_foundation_query_source",
                                 fromlist=["source"]).source()
        for body in xp2_placement_event_source._all_bodies(
                xp2_placement_event_source.source()):
            for entry in body.values():
                for part in entry["fragments"]:
                    graph.memory.put(base + int(part["start_rva"], 16),
                                     bytes.fromhex(part["raw_hex"]))
        for body in query_proof["functions"].values():
            for part in body["fragments"]:
                graph.memory.put(base + int(part["start_rva"], 16),
                                 bytes.fromhex(part["raw_hex"]))
        for body in xp2_wmd_fallout_visibility.source()["bodies"]["core"].values():
            for part in body.get("fragments") or (body,):
                graph.memory.put(base + int(part["start_rva"], 16),
                                 bytes.fromhex(part["raw_hex"]))
        for body in xp2_wonder_completion.source()[1]["functions"].values():
            for part in body["fragments"]:
                graph.memory.put(base + int(part["start_rva"], 16),
                                 bytes.fromhex(part["raw_hex"]))
        jump_table = xp2_placement_event_source.source()["direct_helper_functions"][
            "0x2c4f10"]["relative_jump_table"]
        graph.memory.put(base + int(jump_table["rva"], 16),
                         bytes.fromhex(jump_table["raw_hex"]))
        for table in query_proof["tables"].values():
            table_rva = int(table["vtable_rva"], 16)
            for slot, target in table["slots"].items():
                graph.memory.put(base + table_rva + int(slot, 16),
                                 (base + int(target, 16)).to_bytes(8, "little"))
        placement_proof = xp2_placement_event_source.source()
        for table in placement_proof["faith_query_abi"]["tables"].values():
            table_rva = int(table["vtable_rva"], 16)
            for slot, target in table["slots"].items():
                graph.memory.put(base + table_rva + int(slot, 16),
                                 (base + int(target, 16)).to_bytes(8, "little"))

        previous = (backend.stage, backend.prefix, backend.busy)
        backend.stage, backend.prefix, backend.busy = "prepared", None, False
        try:
            a0_foundation_events.enable(owner, backend)
            a0_foundation_events.enable_placements(owner, backend)
        finally:
            backend.stage, backend.prefix, backend.busy = previous
        self.assertEqual(backend.load_abi.core_sha256, XP2_CORE_SHA256)
        self.assertIs(owner._foundation_backend, backend)
        self.assertIs(owner.placement_event_profile, owner._placement_event_profile)
        self.assertEqual(owner.placement_event_profile.source_sha256,
                         xp2_placement_event_source.SOURCE[1])
        self.assertFalse(set(owner.placement_event_profile.record_types_by_kind) &
                         set(owner.history_event_profile.record_types_by_kind
                             if owner.history_event_profile is not None else ()))
        from civ6_host.runtime.xp2_history_event_profile import event_profile as history_profile
        self.assertFalse(set(owner.placement_event_profile.record_types_by_kind) &
                         set(history_profile(core_sha256=XP2_CORE_SHA256).record_types_by_kind))

        # Add only the XP2 district/faith query wrappers absent from the
        # turn/climate fixture. Existing A0 dispatch and all query helpers run.
        abi = foundation_facade_profiles.query_abi(XP2_CORE_SHA256,
                                                    __import__("civ6_host.runtime.paths",
                                                    fromlist=["resource_root"]).resource_root())
        turn_objects = {name: 0x800000 + 0x1000 * index
                        for index, name in enumerate(turn_source.TABLES)}
        objects = {
            "outer": backend.context,
            "player": turn_objects["player"],
            "district_collection": 0xA11000,
            "district": 0xA12000,
            "type_service": 0xA13000,
            "faith_facade": 0xA14000,
            "map": turn_objects["map"],
            "plot": turn_objects["plot"],
            "game": turn_objects["game"],
            "component": turn_objects["component"],
            "data": turn_objects["data"],
            "units": turn_objects["units"],
            "unit": turn_objects["unit"],
        }
        for name, (table_rva, slots) in abi.tables.items():
            ptr = objects.get(name)
            if ptr is None:
                # Non-placement interfaces in the complete ABI are already
                # allocated by the turn graph and share those live owners.
                ptr = None
            if ptr is None:
                continue
            graph.memory.put(ptr, struct.pack("<Q", base + table_rva))
            for offset, target in slots.items():
                graph.memory.put(base + table_rva + offset,
                                 struct.pack("<Q", base + target))
        faith_tables = placement_proof["faith_query_abi"]["tables"]
        for name, pointer in (("outer", backend.context),
                              ("player", objects["player"]),
                              ("facade", objects["faith_facade"])):
            table_rva = int(faith_tables[name]["vtable_rva"], 16)
            graph.memory.put(pointer, struct.pack("<Q", base + table_rva))
        graph.memory.put(objects["district"] + 8, struct.pack("<Q", 0xA15000))
        graph.memory.put(objects["player"] + 8, struct.pack("<Q", 0xA15100))
        graph.memory.put(objects["player"] + 16, struct.pack("<Q", 0xA15200))
        graph.memory.put(objects["faith_facade"] + 8, struct.pack("<Q", 0xA15300))
        graph.memory.put(objects["faith_facade"] + 16, struct.pack("<Q", 0xA15300))
        if abi.service_secondary_vtable is not None:
            graph.memory.put(objects["type_service"] + 8,
                             struct.pack("<Q", base + abi.service_secondary_vtable))
        graph.memory.put(0xA16000, struct.pack("<ii", 3, 4))
        graph.memory.put(0xA16100, struct.pack("<ii", 3, 4))
        graph.memory.put(0xA16200, struct.pack("<HHI", 1, 3, 29))

        calls, live = [], {name: 0 for name in
                           ("player", "collection", "district", "service", "faith",
                            "map", "plot", "component")}
        vector = 0xA17000
        graph.memory.put(vector, struct.pack("<QQ", 0x31, 0x32))

        def acquire(name):
            live[name] += 1
            return objects["district_collection" if name == "collection" else
                           "district" if name == "district" else
                           "type_service" if name == "service" else
                           "faith_facade" if name == "faith" else
                           name]

        release_names = {"release_player": "player", "release_collection": "collection",
                         "release_item": "district", "release_service": "service",
                         "release_facade": "faith", "release_map": "map",
                         "release_plot": "plot", "release_component": "component"}

        def native(name, *args):
            calls.append((name, args))
            if name in release_names:
                label = release_names[name]
                expected = objects["district_collection" if label == "collection" else
                                   "district" if label == "district" else
                                   "type_service" if label == "service" else
                                   "faith_facade" if label == "faith" else label]
                self.assertEqual(args[0], expected)
                self.assertGreater(live[label], 0)
                live[label] -= 1
                return None
            if name == "release_context":
                self.assertEqual(args, (backend.context,)); return None
            if name == "get_player":
                self.assertEqual(args[0], backend.context); return acquire("player")
            if name == "player_collection":
                self.assertEqual(args, (objects["player"],)); return acquire("collection")
            if name == "collection_index":
                self.assertEqual(args, (objects["district_collection"], 29)); return acquire("district")
            if name == "item_snapshot":
                self.assertEqual(args[0], objects["district"])
                raw = bytearray(64)
                raw[29] = 7
                struct.pack_into("<QI", raw, 40, vector, 2)
                struct.pack_into("<I", raw, 56, 1)
                C.memmove(args[1], bytes(raw), 64)
                return 1
            if name == "item_variant":
                self.assertEqual(args[0], objects["district"])
                C.memmove(args[1], struct.pack("<HHI", 1, 3, 29), 8)
                return args[1]
            if name == "item_raw": return 13
            if name == "free_vector": self.assertEqual(args, (vector,)); return None
            if name == "outer_map":
                self.assertEqual(args, (backend.context,)); return acquire("map")
            if name == "map_plot":
                self.assertEqual(args, (objects["map"], 3, 4)); return acquire("plot")
            if name == "plot_owner": self.assertEqual(args, (objects["plot"],)); return 1
            if name == "plot_value": self.assertEqual(args, (objects["plot"],)); return 35
            if name == "outer_service":
                self.assertEqual(args, (backend.context,)); return acquire("service")
            if name == "player_type": return 4
            if name == "service_player_type_hash": return 77
            if name == "get_facade":
                self.assertEqual(args, (objects["player"],)); return acquire("faith")
            if name in ("get_slot10", "get_slot18"):
                self.assertEqual(args[0], objects["faith_facade"])
                C.memmove(args[1], struct.pack("<I", 269 if name == "get_slot10" else 268), 4)
                return args[1]
            raise AssertionError("Unexpected placement-family native call: " + name)

        # Translate exact selected XP2 addresses to existing shared query
        # names. Calls still enter native producer/query helpers normally.
        operations = {name: spec["rva"] for name, spec in abi.operations.items()}
        aliases = {"get_player": "get_player", "release_player": "release_player",
                   "player_collection": "player_districts", "release_collection": "release_collection",
                   "collection_index": "district_by_id", "release_item": "release_district",
                   "item_raw": "district_type", "item_variant": "district_city_descriptor",
                   "item_snapshot": "district_snapshot70", "free_vector": "free_snapshot_vector",
                   "outer_map": "outer_map", "release_map": "release_map", "map_plot": "get_plot",
                   "release_plot": "release_plot", "plot_value": "plot_value",
                   "plot_owner": "plot_owner",
                   "outer_service": "outer_service", "release_service": "release_service",
                   "player_type": "player_type",
                   "service_player_type_hash": "service_player_type_hash"}
        target_name = {base + operations[operation]: name for name, operation in aliases.items()}
        faith_ops = faith_event_profile.verify_source(core_sha256=XP2_CORE_SHA256)["faith_query_abi"]["operations"]
        for name in ("release_context", "get_facade", "release_facade", "get_slot10", "get_slot18"):
            target_name[base + int(faith_ops[name]["target_rva"], 16)] = name

        def factory(result, *types):
            def bind(target):
                name = target_name.get(target)
                if name is not None:
                    return lambda *args: native(name, *args)
                return graph.factory(result, *types)(target)
            return bind

        return graph, factory, calls, live

    def fields(self, graph, kind):
        address = {"position": 0xA16000, "descriptor": 0xA16200}
        blob = lambda tag, ptr: struct.pack("<H6xQII", tag, ptr, 8, 553648129)
        if kind == district.EVENT_KIND:
            graph.memory.put(address["descriptor"], struct.pack("<HHI", 1, 3, 29))
            return {district.POSITION_KEY: blob(0, address["position"]),
                district.DESCRIPTOR_KEY: blob(1024, address["descriptor"]),
                district.SELECTOR_KEY: scalar(3, district_selector.AUX_SELECTOR),
                district.A1FBC_KEY: scalar(2, 9), district.D6_KEY: scalar(2, 11)}
        if kind == visibility.EVENT_KIND:
            return {visibility.POSITION_KEY: blob(0, address["position"]),
                visibility.SELECTOR_KEY: scalar(3, 0), visibility.VALUE_KEY: scalar(2, 12)}
        if kind == faith.EVENT_KIND:
            return {faith.SELECTOR_KEY: scalar(3, 0), faith.PLAYER_KEY: scalar(2, 1)}
        from civ6_host.runtime import goody_hut_reward as goody
        graph.memory.put(address["descriptor"], struct.pack("<HHI", 1, 1, 29))
        return {goody.SELECTOR_KEY: scalar(3, 0), goody.VALUE_KEY: scalar(2, 7),
                goody.SECOND_KEY: scalar(2, 8),
                goody.UNIT_KEY: blob(1024, 0xA16200)}

    @staticmethod
    def _close(graph):
        if not graph.owner.closed and not graph.owner.quarantined:
            graph.owner.close()

    def test_four_xp2_families_enqueue_five_exact_rows_on_the_shared_fifo(self):
        graph, factory, calls, live = self.graph()
        kinds = (district.EVENT_KIND, visibility.EVENT_KIND, faith.EVENT_KIND)
        from civ6_host.runtime import goody_hut_reward as goody
        with pending_civilization_render(), patch.object(C, "WINFUNCTYPE", factory):
            for kind in (*kinds, goody.EVENT_KIND):
                self.assertEqual(graph.owner.dispatch(kind, self.fields(graph, kind), 0), 0)
        self.assertEqual([struct.unpack_from("<I", row, 4)[0]
                          for row in graph.owner.pending], [157, 163, 145, 194, 259])
        self.assertEqual([len(row) for row in graph.owner.pending], [144, 128, 160, 96, 112])
        self.assertEqual(sum(name == "item_snapshot" for name, _ in calls), 2)
        self.assertEqual(sum(name == "free_vector" for name, _ in calls), 2)
        self.assertLess(next(i for i, (name, _) in enumerate(calls) if name == "free_vector"),
                        len(calls))
        self.assertTrue(all(value == 0 for value in live.values()), live)
        self.assertFalse(graph.owner._f391_producing)
        self.assertFalse(graph.owner._f391_poisoned)
        self.assertIsNone(graph.owner._foundation_borrow)
        self.assertEqual((graph.owner.host_notification_counter,
                          graph.owner.host_metadata_counter), (0, 0))
        self.assertEqual(graph.event.deferred.drain(), 5)
        self.assertEqual(graph.event.deferred.pending, [])
        self.assertEqual(graph.event.deferred.consumed_count, 5)
        self.assertEqual(graph.owner._climate_records, {})


if __name__ == "__main__":
    unittest.main()
