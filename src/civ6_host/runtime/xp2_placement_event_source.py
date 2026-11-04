"""XP2 Core producer source for placement's non-history A0 callback family.

XP2 membership is separate from the retained XP1 placement producer. The
shared EXE remains the authority for callback registration and record rows.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
from types import MappingProxyType

from .a0_family_source import _path, verify_pinned_files
from .configuration_profiles import _source, BASE_CORE_SHA256
from .saved_load_profiles import XP2_CORE_SHA256
from .native.native_host_event_registry import EXE_EVENT_CALLBACKS, EXE_SHA256

SOURCE = (
    "work/host-extensions/xp2-placement-events-static/source-profile-v1.json",
    "66b85efd5e522ac4e554dfebf1e80913611e1ca1912b69f2532d16f43bff72e8",
)
EXE_SHA256_EXPECTED = "e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63"
PLACEMENT_KINDS = frozenset({0x6D7163B0, 0xF391D7B3, 0xB3495127, 0xC08FC0F9})
HISTORY_KINDS = frozenset({0x4710F1A4, 0xF50673B7, 0x788B7534})
RECORDS = MappingProxyType({
    0x6D7163B0: ((157, 144), (163, 128)),
    0xF391D7B3: ((145, 160),),
    0xB3495127: ((194, 96),),
    0xC08FC0F9: ((259, 112),),
})
EXPECTED_CALLBACKS = MappingProxyType({
    0x6D7163B0: 0x144B30,
    0xF391D7B3: 0x149210,
    0xB3495127: 0x146520,
    0xC08FC0F9: 0x1480E0,
})
PARENT_PINS = MappingProxyType({
    "xp1_placement_delivery": ("evidence/host-xp1-production-placement.json", "ab49102e2c30fb6d7e3e82e3e2fd997e59625b59903d5d1beeaf20b5ea785e93"),
    "xp1_placement_source": ("work/host-extensions/xp1-production-placement-static/placement-source-v1.json", "25094b1e71dfba16ba48e6d0642a1d4cd8f30240d47fa3dac96b47a98867757a"),
    "xp1_inventory_delivery": ("evidence/host-xp1-placement-inventory.json", "e304d5ec503c9af697396209261e9c7bffe3701febfbf6951210826140e8dd41"),
    "xp1_inventory_source": ("work/host-extensions/xp1-placement-inventory-static/source-v1.json", "c8bec08656482cd145eff777f5c91338a52c3b20aff57ad3b50d5caf5e281fa1"),
    "xp2_turn_source": ("work/host-extensions/xp2-turn-notifications-static/source-profile-v1.json", "e6dad3289463a09baecfb8a34a52f3fcaedc03f50f94d06ae11840363de9419b"),
    "xp2_world_unit_source": ("work/host-extensions/xp2-world-unit-events-static/source-profile-v1.json", "da6a821757433c29b5db74c173e020d233b7718cd9c8e5f5460b8e180a8b6b00"),
    "xp2_queue_source": ("work/host-extensions/xp2-production-queue-events-static/source-profile-v1.json", "6c7fd1820304fdebc2e8f78d40098a588663a9f076d0a80df92d1d6295ab77b0"),
    "xp2_history_source": ("work/host-extensions/xp2-game-history-static/source-profile-v1.json", "17ac63754f1634ec22ef6ff3e6d2f1f3e271d535e001aa1b6f2a2bdbda677b7c"),
    "xp2_query_facade_source": ("work/host-extensions/xp2-foundation-query-facades-static/query-facade-source-v3.json", "7313418cd5d5f4f086ed41424c7f502c736e953a6bc345ab1b2da5368462a71e"),
    "xp2_player_query_source": ("work/host-extensions/xp2-player-query-static/source-profile-v1.json", "d5e71d1a2ff1eeceed0d316d209942c25068754716342c51540f0f8638f8af4c"),
    "shared_a0_codecs": ("work/host-extensions/a0-family-reuse-static/a0-family-reuse-v1.json", "0a1d3e3dabb677d7cb14cce1926dabb8360568c69fe97c5d2d61293c0c114e43"),
})
COMMON_EVIDENCE = MappingProxyType({
    "evidence/native-event-6d7163b0/ec07f3ed63488cd6aef905d870029a15072210ad5abd7f982298f4564b4825a1.json": "ec07f3ed63488cd6aef905d870029a15072210ad5abd7f982298f4564b4825a1",
    "evidence/native-event-6d7163b0-selector/1afec6235ee0e8096f7aa5bc9112b27dbea2814b51098703783ae5c86d7074e8.json": "1afec6235ee0e8096f7aa5bc9112b27dbea2814b51098703783ae5c86d7074e8",
    "evidence/native-event-f391d7b3/d4d74903f64c7579fcece750f4d2d8323c0b8dd9c7cac35a32a87a58431365b1.json": "d4d74903f64c7579fcece750f4d2d8323c0b8dd9c7cac35a32a87a58431365b1",
    "evidence/native-event-f391d7b3-position-variant/7c8114248a127b13fc0745ef3c3c0a4ff442ae93c03e00df78ad8fd29a3a789a.json": "7c8114248a127b13fc0745ef3c3c0a4ff442ae93c03e00df78ad8fd29a3a789a",
    "evidence/native-f391d7b3-positive-scope/a8c68d0467fa5c2348bca9a097dc7a6a31442bf05b4d476e2895092be4d0278b.json": "a8c68d0467fa5c2348bca9a097dc7a6a31442bf05b4d476e2895092be4d0278b",
    "evidence/native-event-b3495127/1c918a33a49cf6d1f43b9b6819da35fbb05f777ae88fd1c023a42b4db9800265.json": "1c918a33a49cf6d1f43b9b6819da35fbb05f777ae88fd1c023a42b4db9800265",
    "work/host-simultaneous/dialogue/event-c08fc0f9-core.json": "6ddafa215816e4fca42e4ebe8331758fda908ef92b7016a600498586472d23c8",
    "work/host-simultaneous/dialogue/event-c08fc0f9-exe-followup.json": "8ec9ebfd6a1de5d024eb9fc715bdd52916165d4a951043bc515274070c23e76d",
})


def _all_bodies(proof):
    return (proof["functions"], proof["direct_helper_functions"], proof["query_methods"])


def _verify_body(body, label, *, producer=False):
    allowed = {"complete-runtime-function-chained-unwind-root-v2",
               "complete-reachable-leaf-cfg-v1", "leaf ret/jmp within bounded window",
               "complete-switch-cfg-plus-relative-table-v1"}
    if (body.get("boundary_method") not in allowed
            or body.get("all_conditional_targets_captured") is not True
            or not body.get("fragments")):
        raise ValueError("XP2 placement source body boundary changed: " + label)
    if producer and body.get("boundary_method") != "complete-runtime-function-chained-unwind-root-v2":
        raise ValueError("XP2 placement producer is not a complete unwind body: " + label)
    parts = []
    for fragment in body["fragments"]:
        raw = bytes.fromhex(fragment["raw_hex"])
        if (len(raw) != fragment.get("length")
                or hashlib.sha256(raw).hexdigest() != fragment.get("sha256")
                or "".join(row["bytes"] for row in fragment["instructions"]) != raw.hex()):
            raise ValueError("XP2 placement fragment bytes changed: " + label)
        start, cursor = int(fragment["start_rva"], 16), int(fragment["start_rva"], 16)
        for row in fragment["instructions"]:
            code = bytes.fromhex(row["bytes"])
            if (not code or int(row["rva"], 16) != cursor
                    or raw[cursor - start:cursor - start + len(code)] != code):
                raise ValueError("XP2 placement instruction boundary changed: " + label)
            cursor += len(code)
        if cursor != start + len(raw):
            raise ValueError("XP2 placement fragment tail changed: " + label)
        parts.append(raw)
    complete = b"".join(parts)
    if (len(complete) != body.get("bytes")
            or hashlib.sha256(complete).hexdigest() != body.get("sha256")
            or complete.hex() != body.get("raw_hex")):
        raise ValueError("XP2 placement function digest changed: " + label)


def source():
    proof = _source(SOURCE)
    validation = proof.get("validation", {})
    if (proof.get("schema") != "civ6-host.xp2-placement-event-producers.static.v1"
            or proof.get("native_execution") is not False
            or proof.get("process_memory_read") is not False
            or proof.get("runtime_modified") is not False
            or proof.get("images", {}).get("xp2", {}).get("sha256") != XP2_CORE_SHA256
            or proof.get("images", {}).get("exe", {}).get("sha256") != EXE_SHA256_EXPECTED
            or EXE_SHA256 != EXE_SHA256_EXPECTED
            or set(map(lambda x: int(x, 16), proof.get("callbacks", {}))) != PLACEMENT_KINDS
            or set(proof.get("parents", {})) != set(PARENT_PINS)
            or validation.get("function_count") != len(proof.get("functions", {}))
            or validation.get("direct_helper_function_count") != len(proof.get("direct_helper_functions", {}))
            or validation.get("all_conditional_targets_captured") is not True):
        raise ValueError("XP2 placement source identity changed")
    if len(proof["functions"]) != 25 or len(proof["direct_helper_functions"]) != 139:
        raise ValueError("XP2 placement producer/helper set changed")
    for name, (path, digest) in PARENT_PINS.items():
        row = proof["parents"].get(name, {})
        if (row.get("path"), row.get("sha256")) != (path, digest):
            raise ValueError("XP2 placement source parent changed: " + name)
    if set(map(lambda value: int(value, 16), proof.get("callbacks", {}))) & HISTORY_KINDS:
        raise ValueError("XP2 placement profile overlaps the separately selected history family")
    if (set(proof.get("direct_targets_without_new_unwind_entry", {})) == set()
            or proof.get("direct_targets_with_unclosed_boundary") != {}):
        raise ValueError("XP2 placement direct-call boundary inventory changed")
    for kind, expected in EXPECTED_CALLBACKS.items():
        row = proof["callbacks"][hex(kind)]
        if (int(row.get("exe_callback_rva", "0"), 16) != expected
                or not row.get("immediate_references")
                or tuple((item["type"], item["size"]) for item in row.get("record_types", ())) != RECORDS[kind]):
            raise ValueError("XP2 placement callback/record join changed: " + hex(kind))
        if EXE_EVENT_CALLBACKS.get(kind) != expected:
            raise ValueError("XP2 placement callback differs from shared EXE registry")
    for category, bodies in zip(("producer", "direct-helper", "query-method"), _all_bodies(proof)):
        for key, body in bodies.items():
            if ((category == "query-method" and body.get("name") != key)
                    or (category != "query-method" and body.get("rva") != key)):
                raise ValueError("XP2 placement body RVA changed: " + category + ":" + key)
            _verify_body(body, category + ":" + key, producer=category == "producer")

    # The indirect switch in the district producer is closed through its exact
    # seven-entry relative table; all targets must land in the captured body.
    switch = proof["direct_helper_functions"]["0x2c4f10"]
    table = switch.get("relative_jump_table", {})
    table_raw = bytes.fromhex(table.get("raw_hex", ""))
    table_targets = tuple(table.get("target_rvas", ()))
    instruction_starts = {int(row["rva"], 16) for row in switch["fragments"][0]["instructions"]}
    if (table.get("rva") != "0x2c5214" or len(table_raw) != 28
            or hashlib.sha256(table_raw).hexdigest() != table.get("sha256")
            or table_targets != ("0x2c5165", "0x2c4f89", "0x2c4fb2", "0x2c4f89", "0x2c5007", "0x2c502e", "0x2c50b8")
            or any(int(target, 16) not in instruction_starts for target in table_targets)):
        raise ValueError("XP2 placement switch jump-table closure changed")

    snapshot = proof.get("district_snapshot_contract", {})
    if (snapshot.get("query_profile_sha256") != PARENT_PINS["xp2_query_facade_source"][1]
            or snapshot.get("table_rva") != "0xa10d98" or snapshot.get("slot") != "0x70"
            or snapshot.get("wrapper_rva") != "0x5965a0"
            or snapshot.get("wrapper_tail_target") != "0x7d8b0"
            or snapshot.get("vector_fill_target") != "0x190760"
            or snapshot.get("abi") != "uint8(ptr,out64*,uint32)"
            or snapshot.get("output_bytes") != 64
            or snapshot.get("vector_fields") != {"pointer_offset": 40, "capacity_offset": 48, "count_offset": 56}):
        raise ValueError("XP2 district snapshot output contract changed")
    rows = {int(row["rva"], 16): row
            for body in proof["query_methods"].values()
            for fragment in body["fragments"] for row in fragment["instructions"]}
    if (rows.get(0x5965A7, {}).get("text") != "jmp 0x18007d8b0"
            or rows.get(0x7D93A, {}).get("text") != "mov dword ptr [rbx + 0x20], eax"
            or rows.get(0x190760, {}).get("text") != "push rbx"
            or rows.get(0x1907B0, {}).get("text") != "call 0x180640d60"
            or rows.get(0x190898, {}).get("text") != "cmp dword ptr [rbx + 0x10], 0"):
        raise ValueError("XP2 district snapshot method/tail source changed")

    # Reuse the retained EXE encoders/receivers and their exact historical
    # caller evidence; these do not turn an XP1 Core producer into XP2 proof.
    from .native import native_event_6d7163b0 as district_event
    from .native import native_event_6d7163b0_selector as district_selector
    from .native import native_event_f391d7b3 as visibility_event
    from .native import native_event_b3495127 as faith_event
    from . import goody_hut_reward
    district_event.verify_source_evidence()
    district_selector.verify_source_evidence()
    visibility_event.verify_source_evidence()
    visibility_event.verify_typed_position_evidence()
    visibility_event.verify_scoped_source_evidence()
    faith_event.verify_source_evidence()
    goody_hut_reward.verify_source(core_sha256=BASE_CORE_SHA256)

    faith = proof.get("faith_query_abi", {})
    if faith != _EXPECTED_FAITH_ABI:
        raise ValueError("XP2 FaithChanged query ABI source changed")
    return proof


_EXPECTED_FAITH_ABI = {
    "tables": {
        "outer": {"vtable_rva": "0xa101e8", "slots": {"0x8": "0x8972d0", "0xb8": "0x590360"}},
        "player": {"vtable_rva": "0xa11a80", "slots": {"0x8": "0x59c8c0", "0xe0": "0x59d0d0"}},
        "facade": {"vtable_rva": "0xa12060", "slots": {"0x8": "0x59f680", "0x10": "0x59f780", "0x18": "0x59f740"}},
    },
    "operations": {
        "get_player": {"table": "outer", "slot": "0xb8", "target_rva": "0x590360", "abi": "ptr(ptr,int32)"},
        "release_context": {"table": "outer", "slot": "0x8", "target_rva": "0x8972d0", "abi": "void(ptr)"},
        "release_player": {"table": "player", "slot": "0x8", "target_rva": "0x59c8c0", "abi": "void(ptr)"},
        "get_facade": {"table": "player", "slot": "0xe0", "target_rva": "0x59d0d0", "abi": "ptr(ptr)"},
        "release_facade": {"table": "facade", "slot": "0x8", "target_rva": "0x59f680", "abi": "void(ptr)"},
        "get_slot10": {"table": "facade", "slot": "0x10", "target_rva": "0x59f780", "abi": "uint32(ptr,out32*)"},
        "get_slot18": {"table": "facade", "slot": "0x18", "target_rva": "0x59f740", "abi": "uint32(ptr,out32*)"},
    },
}


def callback_mapping():
    proof = source()
    return MappingProxyType({int(kind, 16): int(row["exe_callback_rva"], 16)
                             for kind, row in proof["callbacks"].items()})


def verify_live(base, read):
    if type(base) is not int or base <= 0 or not callable(read):
        raise ValueError("XP2 placement source needs a relocated base and reader")
    proof = source()
    count = 0
    for bodies in _all_bodies(proof):
        for body in bodies.values():
            for fragment in body["fragments"]:
                raw = bytes.fromhex(fragment["raw_hex"])
                for offset in range(0, len(raw), 4096):
                    expected = raw[offset:offset + 4096]
                    if read(base + int(fragment["start_rva"], 16) + offset, len(expected)) != expected:
                        raise ValueError("XP2 placement live source fragment changed")
                count += 1
    switch = proof["direct_helper_functions"]["0x2c4f10"]["relative_jump_table"]
    table_raw = bytes.fromhex(switch["raw_hex"])
    if read(base + int(switch["rva"], 16), len(table_raw)) != table_raw:
        raise ValueError("XP2 placement live switch table changed")
    for table in proof["faith_query_abi"]["tables"].values():
        table_rva = int(table["vtable_rva"], 16)
        for slot, target in table["slots"].items():
            expected = (base + int(target, 16)).to_bytes(8, "little")
            if read(base + table_rva + int(slot, 16), 8) != expected:
                raise ValueError("XP2 FaithChanged query vtable slot changed")
    return dict(source_sha256=SOURCE[1], core_sha256=XP2_CORE_SHA256,
                verified_fragments=count, verified_switch_tables=1)


def source_dependencies():
    proof = source()
    refs = [dict(path=SOURCE[0], sha256=SOURCE[1]),
            *(dict(path=path, sha256=digest) for path, digest in PARENT_PINS.values())]
    refs.extend(dict(path=path, sha256=digest) for path, digest in COMMON_EVIDENCE.items())
    # The shared EXE codecs and XP2 facade sources are source-qualified by
    # their existing runtime selectors; include their complete chosen closure.
    providers = (
        lambda: __import__("civ6_host.runtime.foundation_facade_profiles", fromlist=["source_dependencies"]).source_dependencies(core_sha256=XP2_CORE_SHA256),
        lambda: __import__("civ6_host.runtime.turn_unit_event_profile", fromlist=["source_dependencies"]).source_dependencies(core_sha256=XP2_CORE_SHA256),
        lambda: __import__("civ6_host.runtime.xp2_history_event_profile", fromlist=["source_dependencies"]).source_dependencies(core_sha256=XP2_CORE_SHA256),
        lambda: __import__("civ6_host.runtime.xp2_player_query_source", fromlist=["source_dependencies"]).source_dependencies(),
    )
    refs.extend(dict(path=str(path), sha256=digest, absolute=True)
                for provider in providers for path, digest in provider().items())
    pins = {}
    for row in refs:
        path = str(row["path"]) if row.get("absolute") else str(_path(row["path"]))
        if path in pins and pins[path] != row["sha256"]:
            raise ValueError("Conflicting XP2 placement source dependency")
        pins[path] = row["sha256"]
    verify_pinned_files(pins)
    return pins


@dataclass(frozen=True)
class VerifiedXP2PlacementEventSource:
    owner: object
    core: object
    base: int
    source_sha256: str
    core_sha256: str
    verified_fragments: int


def bind_owner(owner, core, read):
    from .native.native_official_load import OfficialLoadBackend
    if type(owner) is not OfficialLoadBackend:
        raise ValueError("XP2 placement source requires the actual saved Load backend")
    owner.check_thread()
    if (owner.core is not core or owner.load_abi.core_sha256 != XP2_CORE_SHA256
            or type(core._handle) is not int or core._handle <= 0
            or read != owner.runtime.read or owner.destroyed or owner.poisoned):
        raise ValueError("XP2 placement source owner mismatch")
    from .foundation_facade_profiles import verify_xp1_once
    from .paths import resource_root
    verify_xp1_once(core, core._handle, read, resource_root(), core_sha256=XP2_CORE_SHA256)
    live = verify_live(core._handle, read)
    previous = getattr(owner, "_xp2_placement_event_source_receipt", None)
    if previous is not None:
        if (type(previous) is not VerifiedXP2PlacementEventSource
                or previous.owner is not owner or previous.core is not core
                or previous.base != core._handle or previous.source_sha256 != SOURCE[1]
                or previous.core_sha256 != XP2_CORE_SHA256
                or previous.verified_fragments != live["verified_fragments"]):
            raise ValueError("XP2 placement source receipt belongs to another owner")
        return previous
    receipt = VerifiedXP2PlacementEventSource(owner, core, core._handle,
        SOURCE[1], XP2_CORE_SHA256, live["verified_fragments"])
    owner._xp2_placement_event_source_receipt = receipt
    return receipt


def event_profile(*, core_sha256):
    if core_sha256 != XP2_CORE_SHA256:
        raise ValueError("XP2 placement event profile requires the exact XP2 Core")
    proof = source()
    source_dependencies()
    from .native.native_deferred_empty_profile import resolve_empty_receiver_row
    from .a0_family_source import A0FamilyProfile
    mapping = {kind: frozenset(record_type for record_type, _ in rows)
               for kind, rows in RECORDS.items()}
    sizes = {record_type: size for rows in RECORDS.values()
             for record_type, size in rows}
    for rows in RECORDS.values():
        for record_type, size in rows:
            row = resolve_empty_receiver_row(record_type)
            if tuple(row["record_sizes"]) != (size,):
                raise ValueError("XP2 placement shared EXE receiver size changed")
    from .xp2_history_event_profile import HISTORY_KIND, ERA_KIND, ERA_SCORE_KIND
    if set(mapping) & {HISTORY_KIND, ERA_KIND, ERA_SCORE_KIND}:
        raise ValueError("XP2 placement and history profiles overlap")
    return A0FamilyProfile(MappingProxyType(mapping), MappingProxyType(sizes), SOURCE[1])
