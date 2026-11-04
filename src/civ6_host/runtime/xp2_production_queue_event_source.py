"""Source guard for XP2 Core producers of shared production-queue callbacks.

The selected profile covers producer-side static bodies and the shared EXE
callback identities. Queue UI, action reachability, A0 record interpretation,
and native XP2 queue behavior remain separate qualifications.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import re
from types import MappingProxyType

from .a0_family_source import _path, verify_pinned_files
from .configuration_profiles import _source
from .saved_load_profiles import XP1_CORE_SHA256, XP2_CORE_SHA256
from .native.native_host_event_registry import EXE_EVENT_CALLBACKS, EXE_SHA256

SOURCE = (
    "work/host-extensions/xp2-production-queue-events-static/source-profile-v1.json",
    "6c7fd1820304fdebc2e8f78d40098a588663a9f076d0a80df92d1d6295ab77b0",
)
EXE_SHA256_EXPECTED = "e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63"
QUEUE_EVENT_KINDS = frozenset({0x92492F56, 0x2842CE14})
ABSENT_QUEUE_EVENT_KIND = 0x9EA4C222
QUEUE_RECORD_TYPES = MappingProxyType({0x2842CE14: (95, 112), 0x92492F56: (98, 112)})
MAX_READ_BYTES = 4096

PARENT_PINS = MappingProxyType({
    "retained_queue_profile": ("work/host-extensions/xp1-production-queue-static/queue-source-v1.json",
                               "904de533550de187085331e6397559d22af6b23c1562f9eee2db0ab45e761fe1"),
    "retained_queue_delivery": ("evidence/host-xp1-production-queue.json",
                                "98e3fe4b2537dd43458e7b50e6f2c784de60d6cafc9383a97687f7f598abacaa"),
    "shared_a0_codecs": ("work/host-extensions/a0-family-reuse-static/a0-family-reuse-v1.json",
                         "0a1d3e3dabb677d7cb14cce1926dabb8360568c69fe97c5d2d61293c0c114e43"),
    "prior_xp2_world_unit_source": ("work/host-extensions/xp2-world-unit-events-static/source-profile-v1.json",
                                    "da6a821757433c29b5db74c173e020d233b7718cd9c8e5f5460b8e180a8b6b00"),
    "xp2_district_removed_source": ("work/host-extensions/xp2-district-removed-static/source-profile-v1.json",
                                    "a6b0bbf07a87acc794b381874613395d9356a4f0f636abbf4dadd57eac535e8f"),
})


def _body_rows(body):
    for fragment in body["fragments"]:
        yield from fragment["instructions"]


def _verify_body(body, label):
    if (body.get("boundary_method") != "complete-runtime-function-chained-unwind-root-v2"
            or body.get("all_conditional_targets_captured") is not True
            or not body.get("fragments")):
        raise ValueError("XP2 queue source body is incomplete: " + label)
    parts = []
    for fragment in body["fragments"]:
        raw = bytes.fromhex(fragment["raw_hex"])
        if (len(raw) != fragment.get("length")
                or hashlib.sha256(raw).hexdigest() != fragment.get("sha256")
                or "".join(row["bytes"] for row in fragment["instructions"]) != raw.hex()):
            raise ValueError("XP2 queue source fragment changed: " + label)
        start = int(fragment["start_rva"], 16)
        cursor = start
        for row in fragment["instructions"]:
            code = bytes.fromhex(row["bytes"])
            if (not code or int(row["rva"], 16) != cursor
                    or raw[cursor - start:cursor - start + len(code)] != code):
                raise ValueError("XP2 queue source instruction boundary changed: " + label)
            cursor += len(code)
        if cursor != start + len(raw):
            raise ValueError("XP2 queue source fragment tail changed: " + label)
        parts.append(raw)
    complete = b"".join(parts)
    if (len(complete) != body.get("bytes")
            or hashlib.sha256(complete).hexdigest() != body.get("sha256")
            or complete.hex() != body.get("raw_hex")):
        raise ValueError("XP2 queue source body digest changed: " + label)


def _body_collections(proof):
    return {
        "producers": proof["functions"],
        "direct_helpers": proof["direct_helper_functions"],
        "queue_dispatch": proof["queue_dispatch_functions"],
    }


def _call_map_signature(mapping, *, with_kinds=False):
    result = {}
    for target, rows in mapping.items():
        if with_kinds:
            result[target] = tuple((row["owner_function_rva"], tuple(row["owner_kinds"]),
                                    row["callsite_va"], row["instruction"])
                                   for row in rows)
        else:
            result[target] = tuple((row["owner_function_rva"], row["callsite_va"],
                                    row["instruction"])
                                   for row in rows)
    return result


def source():
    """Load static bodies and check producer, callback, and EXE codec joins."""
    proof = _source(SOURCE)
    validation = proof.get("validation", {})
    if (proof.get("schema") != "civ6-host.xp2-production-queue-event-references.static.v1"
            or proof.get("native_execution") is not False
            or proof.get("process_memory_read") is not False
            or proof.get("runtime_modified") is not False
            or proof.get("images", {}).get("xp2", {}).get("sha256") != XP2_CORE_SHA256
            or proof.get("images", {}).get("exe", {}).get("sha256") != EXE_SHA256_EXPECTED
            or EXE_SHA256 != EXE_SHA256_EXPECTED
            or {int(kind, 16) for kind in proof.get("callbacks", {})} != QUEUE_EVENT_KINDS
            or set(proof.get("parents", {})) != set(PARENT_PINS)
            or validation.get("function_count") != len(proof.get("functions", {}))
            or validation.get("direct_helper_function_count") != len(proof.get("direct_helper_functions", {}))
            or validation.get("queue_dispatch_function_count") != len(proof.get("queue_dispatch_functions", {}))
            or validation.get("all_conditional_targets_captured") is not True):
        raise ValueError("XP2 production-queue source identity changed")
    if len(proof["functions"]) != 17 or len(proof["direct_helper_functions"]) != 53:
        raise ValueError("XP2 production-queue source function set changed")
    for name, expected in PARENT_PINS.items():
        row = proof["parents"][name]
        if (row.get("path"), row.get("sha256")) != expected:
            raise ValueError("XP2 production-queue source parent changed: " + name)

    registered = set(EXE_EVENT_CALLBACKS) & QUEUE_EVENT_KINDS
    if registered != QUEUE_EVENT_KINDS:
        raise ValueError("Queue event kinds no longer join registered shared EXE callbacks")
    for key, entry in proof["callbacks"].items():
        kind = int(key, 16)
        if int(entry["exe_callback_rva"], 16) != EXE_EVENT_CALLBACKS[kind]:
            raise ValueError("XP2 queue kind callback differs from shared EXE registry")
        if not entry.get("immediate_references"):
            raise ValueError("XP2 queue kind has no producer owner")

    # The source uses the shared official EXE codec mapping for the two A0
    # records; only the Core producer bytes are XP2-specific here.
    from .a0_family_source import source as a0_source
    a0 = a0_source()["initial_group"]
    kinds = {int(key): tuple(types) for key, types in a0["kind_to_record_types"].items()}
    sizes = {int(key): value for key, value in a0["record_type_to_size"].items()}
    for kind, (record_type, record_size) in QUEUE_RECORD_TYPES.items():
        if kinds.get(kind) != (record_type,) or sizes.get(record_type) != record_size:
            raise ValueError("Shared EXE queue callback record mapping changed")
    if EXE_EVENT_CALLBACKS.get(ABSENT_QUEUE_EVENT_KIND) is not None:
        raise ValueError("Previously absent queue neighbor gained an EXE callback")

    for category, bodies in _body_collections(proof).items():
        for key, body in bodies.items():
            if body.get("rva") != key:
                raise ValueError("XP2 queue source body RVA changed: " + category + ":" + key)
            _verify_body(body, category + ":" + key)

    # Cross-check producer callsite metadata against the complete bodies.
    expected_calls = {}
    for owner, body in proof["functions"].items():
        owner_kinds = [kind for kind, entry in proof["callbacks"].items()
                       if any(ref["function_rva"] == owner for ref in entry["immediate_references"])]
        for edge in body.get("call_edges", []):
            target_va = edge.get("direct_target_va")
            if not target_va:
                continue
            target = hex(int(target_va, 16) - 0x180000000)
            expected_calls.setdefault(target, []).append(dict(
                owner_function_rva=owner, owner_kinds=owner_kinds,
                callsite_va=edge["va"], instruction=edge["instruction"]))
    if _call_map_signature(expected_calls, with_kinds=True) != _call_map_signature(
            proof.get("direct_call_sites", {}), with_kinds=True):
        raise ValueError("XP2 queue direct helper call map differs from producer bytes")
    for target, callsites in proof.get("direct_targets_without_new_unwind_entry", {}).items():
        if (target not in expected_calls
                or _call_map_signature({target: callsites.get("callsites", ())}, with_kinds=True)[target]
                   != _call_map_signature({target: expected_calls[target]}, with_kinds=True)[target]):
            raise ValueError("XP2 queue direct target boundary inventory changed")

    expected_nested = {}
    for owner, body in proof["direct_helper_functions"].items():
        for edge in body.get("call_edges", []):
            target_va = edge.get("direct_target_va")
            if not target_va:
                continue
            target = hex(int(target_va, 16) - 0x180000000)
            expected_nested.setdefault(target, []).append(dict(
                owner_function_rva=owner, callsite_va=edge["va"],
                instruction=edge["instruction"]))
    if _call_map_signature(expected_nested) != _call_map_signature(proof.get("nested_call_sites", {})):
        raise ValueError("XP2 queue nested call map differs from helper bytes")
    dispatcher = proof["queue_dispatch_functions"].get("0x7c670")
    if dispatcher is None:
        raise ValueError("XP2 queue A0 internal dispatch body missing")
    if not any(edge.get("direct_target_va") == "0x18007c670"
               for body in proof["direct_helper_functions"].values()
               for edge in body.get("call_edges", [])):
        raise ValueError("XP2 queue A0 dispatch callsite disappeared")
    return proof


def callback_mapping():
    """Return queue A0 kind to the existing shared EXE callback RVA."""
    proof = source()
    return MappingProxyType({int(kind, 16): int(row["exe_callback_rva"], 16)
                             for kind, row in proof["callbacks"].items()})


def verify_live(base, read):
    """Verify every captured producer/helper/dispatch fragment in bounded reads."""
    if type(base) is not int or base <= 0 or not callable(read):
        raise ValueError("XP2 queue source requires a module base and byte reader")
    proof = source()
    count = 0
    for bodies in _body_collections(proof).values():
        for body in bodies.values():
            for fragment in body["fragments"]:
                raw = bytes.fromhex(fragment["raw_hex"])
                start = base + int(fragment["start_rva"], 16)
                for offset in range(0, len(raw), MAX_READ_BYTES):
                    expected = raw[offset:offset + MAX_READ_BYTES]
                    actual = read(start + offset, len(expected))
                    if type(actual) is not bytes or actual != expected:
                        raise ValueError("XP2 queue Core fragment changed")
                count += 1
    return dict(source_sha256=SOURCE[1], core_sha256=XP2_CORE_SHA256,
                verified_fragments=count, native_execution=False)


def source_dependencies():
    """Join queue source, action helpers, configuration, A0, and cache pins."""
    proof = source()
    refs = [dict(path=SOURCE[0], sha256=SOURCE[1]),
            *(dict(path=path, sha256=digest) for path, digest in PARENT_PINS.values())]
    providers = (
        lambda: __import__("civ6_host.runtime.a0_family_source", fromlist=["source_pins"]).source_pins(),
        lambda: __import__("civ6_host.runtime.xp2_world_unit_event_source", fromlist=["source_dependencies"]).source_dependencies(),
        lambda: __import__("civ6_host.runtime.xp2_configuration_profile", fromlist=["source_dependencies"]).source_dependencies(),
        lambda: __import__("civ6_host.runtime.xp2_absent_event_source", fromlist=["source_dependencies"]).source_dependencies(),
        lambda: __import__("civ6_host.runtime.xp2_cache_source", fromlist=["source_dependencies"]).source_dependencies(),
    )
    refs.extend(dict(path=str(path), sha256=digest, absolute=True)
                for provider in providers for path, digest in provider().items())
    pins = {}
    for ref in refs:
        path = str(ref["path"]) if ref.get("absolute") else str(_path(ref["path"]))
        digest = ref["sha256"]
        if path in pins and pins[path] != digest:
            raise ValueError("Conflicting XP2 production-queue dependency")
        pins[path] = digest
    verify_pinned_files(pins)
    return pins


@dataclass(frozen=True)
class VerifiedProductionQueueEventSource:
    owner: object
    core: object
    base: int
    source_sha256: str
    core_sha256: str
    callback_mapping_sha256: str
    verified_fragments: int


def bind_owner(owner, core, read):
    """Bind static XP2 event source to the real OfficialLoadBackend owner."""
    from .native.native_official_load import OfficialLoadBackend
    if type(owner) is not OfficialLoadBackend:
        raise ValueError("XP2 queue source requires the actual saved Load backend")
    owner.check_thread()
    if (owner.core is not core or owner.load_abi.core_sha256 != XP2_CORE_SHA256
            or type(core._handle) is not int or core._handle <= 0
            or read != owner.runtime.read or owner.destroyed or owner.poisoned):
        raise ValueError("XP2 queue source owner mismatch")
    mapping_hash = hashlib.sha256(repr(sorted(callback_mapping().items())).encode("ascii")).hexdigest()
    previous = getattr(owner, "_xp2_production_queue_event_source_receipt", None)
    if previous is not None:
        if (type(previous) is not VerifiedProductionQueueEventSource
                or previous.owner is not owner or previous.core is not core
                or previous.base != core._handle or previous.source_sha256 != SOURCE[1]
                or previous.core_sha256 != XP2_CORE_SHA256
                or previous.callback_mapping_sha256 != mapping_hash):
            raise ValueError("XP2 queue event source receipt belongs to another owner")
    live = verify_live(core._handle, read)
    if previous is not None and previous.verified_fragments != live["verified_fragments"]:
        raise ValueError("XP2 queue event source fragment set changed")
    if previous is not None:
        return previous
    receipt = VerifiedProductionQueueEventSource(
        owner, core, core._handle, SOURCE[1], XP2_CORE_SHA256,
        mapping_hash, live["verified_fragments"])
    owner._xp2_production_queue_event_source_receipt = receipt
    return receipt
