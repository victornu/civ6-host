"""Static XP2 source references for retained world/unit input event kinds.

This module pins XP2 Core producer-side immediate references and the shared
EXE callback registry entries. It does not define record layouts, install A0
callbacks, or claim that a public input reaches any particular producer.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from types import MappingProxyType

from .a0_family_source import _path, verify_pinned_files
from .configuration_profiles import XP2_CORE_SHA256, _source
from .native.native_host_event_registry import EXE_EVENT_CALLBACKS, EXE_SHA256

SOURCE = (
    "work/host-extensions/xp2-world-unit-events-static/source-profile-v1.json",
    "da6a821757433c29b5db74c173e020d233b7718cd9c8e5f5460b8e180a8b6b00",
)
EXE_SHA256_EXPECTED = "e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63"
TARGET_KINDS = frozenset({
    0x15C35863, 0x195088C7, 0x1F943311, 0x383669F1, 0x827289E6,
    0x878CD252, 0x8FEF0D8E, 0x9AD1C020, 0x9AEA8529, 0x9EA4C222,
    0xA60328C5, 0xBE121408, 0xCB0345F1, 0xF26F3ACF, 0x3D4006F2,
    0xFC7DB95E, 0x281D81D2,
})
PREVIOUSLY_SELECTED_XP2_PRODUCERS = frozenset({
    0x6E7EF927, 0xC50D66D6, 0xE23B112D, 0xE992F3CD,
})
FOUNDATION_CODEC_ONLY_KINDS = frozenset({
    0x195088C7, 0x827289E6, 0x878CD252, 0x9AEA8529,
})
ABSENT_CALLBACK_KINDS = frozenset({0x9EA4C222})
MAX_READ_BYTES = 4096

PARENT_PINS = MappingProxyType({
    "turn_notifications": ("work/host-extensions/xp2-turn-notifications-static/source-profile-v1.json",
                           "e6dad3289463a09baecfb8a34a52f3fcaedc03f50f94d06ae11840363de9419b"),
    "turn_filter_registration": ("work/host-extensions/xp2-turn-notifications-static/filter-registration-v1.json",
                                 "ade0dc9783e39d4d5302f0242f04748ebb17572b8af335e392224e989652040e"),
    "a0_reuse": ("work/host-extensions/a0-family-reuse-static/a0-family-reuse-v1.json",
                 "0a1d3e3dabb677d7cb14cce1926dabb8360568c69fe97c5d2d61293c0c114e43"),
    "foundation_membership": ("work/host-extensions/xp1-foundation-events-static/foundation-events-source-v1.json",
                              "57e0f8d5dae2926327304d9efef742454b249d4b0949e389d8e0ffb1e655d0ed"),
    "foundation_plot_membership": ("work/host-extensions/xp1-foundation-events-static/foundation-plot-notifications-source-v1.json",
                                   "4e8c9bfc4e2f0c73bdbaa10b47ca3b2743bcc462dfc946991ba14a9bc1208a82"),
    "found_unit_query_map": ("work/host-extensions/xp2-foundation-static/found-unit-query-map-supplement-v1.json",
                             "11cd341bcb9bd2eb424fadd064179b8d586cdbdfcdda33bfc615a7b1bad54b0b"),
    "found_unit_facade": ("work/host-extensions/xp2-foundation-static/player-units-facade-candidate-v2.json",
                          "48dc11668c13d50316cf019f220fb30d2a4a260c4dc36e4e4be04079ae29ba56"),
    "found_unit_exe_callback": ("evidence/native-event-e23b112d.json",
                                "a24ffc52b8c654c49efd7c1679f9d2fb44dc8d28dda6092da2b2d6e70fd74c00"),
    "world_input": ("work/host-extensions/xp2-world-input-static/source-profile-v1.json",
                    "4f52cd6551bcb61b7af2d4e23571eb300c7c8b55ad34b6b94e0387c94a9e72f3"),
    "unit_orders": ("work/host-extensions/xp2-unit-orders-static/unit-orders-source-v1.json",
                    "df5c61d3c79fa061efaa7e77a7891fbc0c49e02ad0dfe75b2736f46e610ee902"),
    "unit_order_transport": ("work/host-extensions/xp2-unit-orders-static/command-transport-v1.json",
                              "d0966318a4227023b87141923edffe12a771d6307f6920f3ec21f1a634083c8e"),
    "unit_order_ui": ("work/host-extensions/xp2-unit-orders-static/ui-resolution-v1.json",
                      "cdf5401077c164bb8e0069d19ead22062fd4d20f601181f9f85aec4237fed24b"),
    "absent_event_families": ("work/host-extensions/xp2-absent-events-static/source-profile-v1.json",
                              "d59fc66f0cd772324dc1f141e18c3c82b1fdb3022aa18ad038d83449f9faba95"),
})


def _instructions(body):
    for fragment in body["fragments"]:
        yield from fragment["instructions"]


def source():
    """Load and verify exact static bytes and registry joins."""
    p = _source(SOURCE)
    if (p.get("schema") != "civ6-host.xp2-world-unit-event-references.static.v1"
            or p.get("native_execution") is not False
            or p.get("process_memory_read") is not False
            or p.get("runtime_modified") is not False
            or p.get("images", {}).get("xp2", {}).get("sha256") != XP2_CORE_SHA256
            or p.get("images", {}).get("exe", {}).get("sha256") != EXE_SHA256_EXPECTED
            or EXE_SHA256 != EXE_SHA256_EXPECTED
            or {int(value, 16) for value in p.get("callbacks", {})} != TARGET_KINDS
            or {int(value, 16) for value in p.get("scope", {}).get("shared_profiles_already_selected", ())}
               != PREVIOUSLY_SELECTED_XP2_PRODUCERS
            or {int(value, 16) for value in p.get("scope", {}).get("foundation_codec_membership_only", ())}
               != FOUNDATION_CODEC_ONLY_KINDS
            or {int(value, 16) for value in p.get("scope", {}).get("absent_registered_callbacks", ())}
               != ABSENT_CALLBACK_KINDS
            or p.get("validation", {}).get("body_count") != len(p.get("functions", {}))
            or p.get("validation", {}).get("all_immediate_owners_have_complete_unwind_bodies") is not True):
        raise ValueError("XP2 world/unit event source identity changed")

    parents = p.get("parents", {})
    if set(parents) != set(PARENT_PINS):
        raise ValueError("XP2 world/unit source parent set changed")
    for name, expected in PARENT_PINS.items():
        row = parents[name]
        if (row.get("path"), row.get("sha256")) != expected:
            raise ValueError("XP2 world/unit source parent changed: " + name)

    expected_registered = TARGET_KINDS - ABSENT_CALLBACK_KINDS
    if set(EXE_EVENT_CALLBACKS) & TARGET_KINDS != expected_registered:
        raise ValueError("XP2 world/unit target callback registration changed")
    total_refs = 0
    decoded_rows = {}
    for raw_kind, entry in p["callbacks"].items():
        kind = int(raw_kind, 16)
        registered = EXE_EVENT_CALLBACKS.get(kind)
        if kind in ABSENT_CALLBACK_KINDS:
            if registered is not None or entry.get("exe_callback_rva") is not None or not entry.get("absent_from_exe_registry"):
                raise ValueError("Absent XP2 callback was registered or synthesized")
        elif registered is None or int(entry.get("exe_callback_rva", "0"), 16) != registered:
            raise ValueError("XP2 Core event kind no longer joins its EXE callback")
        refs = entry.get("immediate_references")
        if not isinstance(refs, (list, tuple)) or not refs:
            raise ValueError("XP2 event kind has no decoded Core references")
        for ref in refs:
            if (ref.get("function_rva") not in p["functions"]
                    or not re.fullmatch(r"0x[0-9a-f]+", ref.get("instruction_rva", ""))
                    or not re.fullmatch(r"(?:[0-9a-f]{2})+", ref.get("instruction_bytes", ""))
                    or f"{kind:#x}" not in ref.get("instruction", "").lower()):
                raise ValueError("XP2 immediate reference no longer names its exact kind")
        total_refs += len(refs)
    if total_refs != p["validation"].get("immediate_reference_count"):
        raise ValueError("XP2 immediate reference count changed")

    for key, body in p["functions"].items():
        if (body.get("rva") != key
                or body.get("boundary_method") != "complete-runtime-function-chained-unwind-root-v2"
                or body.get("all_conditional_targets_captured") is not True):
            raise ValueError("XP2 function identity changed")
        parts = []
        for fragment in body.get("fragments", []):
            raw = bytes.fromhex(fragment["raw_hex"])
            if (len(raw) != fragment.get("length")
                    or hashlib.sha256(raw).hexdigest() != fragment.get("sha256")
                    or "".join(row["bytes"] for row in fragment["instructions"]) != raw.hex()):
                raise ValueError("XP2 function fragment bytes changed")
            cursor = int(fragment["start_rva"], 16)
            for instruction in fragment["instructions"]:
                code = bytes.fromhex(instruction["bytes"])
                if int(instruction["rva"], 16) != cursor or raw[cursor-int(fragment["start_rva"], 16):][:len(code)] != code:
                    raise ValueError("XP2 function instruction boundary changed")
                decoded_rows[instruction["rva"]] = instruction
                cursor += len(code)
            if cursor != int(fragment["start_rva"], 16) + len(raw):
                raise ValueError("XP2 function fragment tail changed")
            parts.append(raw)
        complete = b"".join(parts)
        if (len(complete) != body.get("bytes")
                or hashlib.sha256(complete).hexdigest() != body.get("sha256")
                or complete.hex() != body.get("raw_hex")):
            raise ValueError("XP2 complete function body changed")
    for entry in p["callbacks"].values():
        for ref in entry["immediate_references"]:
            decoded = decoded_rows.get(ref["instruction_rva"])
            if (decoded is None or decoded["bytes"] != ref["instruction_bytes"]
                    or decoded["text"] != ref["instruction"]):
                raise ValueError("XP2 event immediate does not match its captured instruction")
    return p


def callback_rva(kind):
    """Return a registered shared EXE callback RVA; absent kinds fail closed."""
    p = source()
    key = f"{int(kind):#x}"
    row = p["callbacks"].get(key)
    if row is None or row.get("absent_from_exe_registry"):
        raise ValueError("Event kind has no registered shared EXE callback")
    return int(row["exe_callback_rva"], 16)


def callback_mapping():
    """Return the captured target-kind to shared EXE callback mapping.

    Values are ``None`` only for the explicitly unregistered 0x9ea4c222 kind.
    This mapping is source metadata, not callback installation or admission.
    """
    p = source()
    return MappingProxyType({
        int(kind, 16): (None if row["exe_callback_rva"] is None
                        else int(row["exe_callback_rva"], 16))
        for kind, row in p["callbacks"].items()
    })


def source_dependencies():
    """Return exact source pins needed by the selected input-event families."""
    p = source()
    refs = [dict(path=SOURCE[0], sha256=SOURCE[1]),
            *(dict(path=path, sha256=digest) for path, digest in PARENT_PINS.values())]
    for provider in (
        lambda: __import__("civ6_host.runtime.xp2_turn_notification_source", fromlist=["source_dependencies"]).source_dependencies(),
        lambda: __import__("civ6_host.runtime.xp2_world_input_source", fromlist=["source_dependencies"]).source_dependencies(core_sha256=XP2_CORE_SHA256),
        lambda: __import__("civ6_host.runtime.xp2_unit_orders_source", fromlist=["source_dependencies"]).source_dependencies(),
        lambda: __import__("civ6_host.runtime.found_unit_event_profiles", fromlist=["source_dependencies"]).source_dependencies(core_sha256=XP2_CORE_SHA256),
        lambda: __import__("civ6_host.runtime.foundation_event_profile", fromlist=["source_dependencies"]).source_dependencies(core_sha256=XP2_CORE_SHA256),
        lambda: __import__("civ6_host.runtime.xp2_absent_event_source", fromlist=["source_dependencies"]).source_dependencies(),
    ):
        for path, digest in provider().items():
            refs.append(dict(path=str(path), sha256=digest, absolute=True))
    pins = {}
    for ref in refs:
        path = (str(ref["path"]) if ref.get("absolute") else str(_path(ref["path"])))
        digest = ref["sha256"]
        if path in pins and pins[path] != digest:
            raise ValueError("Conflicting XP2 world/unit source dependency")
        pins[path] = digest
    verify_pinned_files(pins)
    return pins


def verify_live(base, read):
    """Compare captured XP2 Core bodies to a supplied live module reader."""
    if type(base) is not int or base <= 0 or not callable(read):
        raise ValueError("XP2 world/unit source requires an exact module and reader")
    p = source()
    fragments = 0
    for body in p["functions"].values():
        for fragment in body["fragments"]:
            raw = bytes.fromhex(fragment["raw_hex"])
            start = base + int(fragment["start_rva"], 16)
            for offset in range(0, len(raw), MAX_READ_BYTES):
                expected = raw[offset:offset + MAX_READ_BYTES]
                actual = read(start + offset, len(expected))
                if type(actual) is not bytes or actual != expected:
                    raise ValueError("XP2 world/unit source bytes differ from the live Core")
            fragments += 1
    return dict(source_sha256=SOURCE[1], core_sha256=XP2_CORE_SHA256,
                verified_fragments=fragments, native_execution=False)


@dataclass(frozen=True)
class VerifiedWorldUnitEventSource:
    owner: object
    core: object
    base: int
    source_sha256: str
    core_sha256: str
    callback_map_sha256: str
    verified_fragments: int


def bind_owner(owner, core, read):
    """Bind source evidence to the exact live XP2 saved-command owner."""
    owner.check_thread()
    if (getattr(owner, "core", None) is not core
            or getattr(getattr(owner, "load_abi", None), "core_sha256", None) != XP2_CORE_SHA256
            or type(getattr(core, "_handle", None)) is not int
            or core._handle <= 0):
        raise ValueError("XP2 world/unit event owner mismatch")
    p = source()
    mapping_digest = hashlib.sha256(repr(sorted(callback_mapping().items())).encode("ascii")).hexdigest()
    previous = getattr(owner, "_xp2_world_unit_event_source_receipt", None)
    if previous is not None:
        if (type(previous) is not VerifiedWorldUnitEventSource
                or previous.owner is not owner or previous.core is not core
                or previous.base != core._handle or previous.source_sha256 != SOURCE[1]
                or previous.core_sha256 != XP2_CORE_SHA256
                or previous.callback_map_sha256 != mapping_digest):
            raise ValueError("XP2 world/unit event source receipt belongs to another owner")
        # Revalidate code on every reuse; never let a stale positive receipt
        # outlive an engine/source change.
        count = verify_live(core._handle, read)["verified_fragments"]
        if previous.verified_fragments != count:
            raise ValueError("XP2 world/unit event source fragment set changed")
        return previous
    live = verify_live(core._handle, read)
    receipt = VerifiedWorldUnitEventSource(
        owner, core, core._handle, SOURCE[1], XP2_CORE_SHA256,
        mapping_digest, live["verified_fragments"])
    owner._xp2_world_unit_event_source_receipt = receipt
    return receipt
