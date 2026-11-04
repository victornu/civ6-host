"""Static proofs for exact XP2 optional achievement callback paths."""
from __future__ import annotations

import hashlib
import re
from pathlib import Path

from .a0_family_source import _path, verify_pinned_files
from .configuration_profiles import XP2_CORE_SHA256, _source

SOURCE = (
    "work/host-extensions/xp2-host-slot20-static/source-profile-v2.json",
    "75c84663fd822c1f0a7308dda39ad474fbcc7492ca567428579742f249b585d8",
)
FORMATION_SOURCE = (
    "work/host-extensions/xp2-host-slot20-static/source-profile-formation-v1.json",
    "bbe7b27f73b23fdfcf7e3046a6f0534c27c1f44da41c937f3109a2c9557d81ef",
)
ERA_TRANSITION_SOURCE = (
    "work/host-extensions/xp2-host-slot20-static/source-profile-era-transition-v1.json",
    "569c172f91b1b945ef561e6fd7104dca9b3cf14ef2e4bca00ade8aafdae49a8d",
)
ERA_TRANSITION_PREFIX = ("0x17f098", "0x177737", "0xda763", "0x284c4d")
_ERA_TRANSITION_LITERAL = b"NEW_ACHIEVEMENT_4_20\0"
RAF30_SOURCE = (
    "work/host-extensions/xp2-host-slot20-static/source-profile-raf30-v1.json",
    "921975e3a4d88c6676e9e79f2f70568725de52be3e655b24082a558c9f9aa4a3",
)
RAF30_PREFIX = ("0x17f098", "0x17ad1c", "0xda763", "0x285abe")
_RAF30_LITERAL = b"RAF_ACHIEVEMENT_30\0"
CITY_LISTENER_SOURCE = (
    "work/host-extensions/xp2-host-slot20-static/source-profile-city-listener-v1.json",
    "470ef25a36de360294366c9ec3622141cf219ba501a6c56a3e9f2c4cc30c4216",
)
CITY_LISTENER_PREFIX = ("0x17f098", "0x178ed0", "0x25c54c", "0x25d3f1", "0x25d459")
_CITY_LISTENER_LITERAL = b"NEW_ACHIEVEMENT_4_14\0"
FORMATION_CORE_RETURN_PREFIX = ("0x17f098", "0x17fa97", "0x226ed4", "0x1a33a5", "0x65a217")
_FORMATION_LITERAL = b"NEW_ACHIEVEMENT_4_13\0"
CORE_MODULE = "GameCore_XP2_FinalRelease.dll"
EXE_SHA256 = "e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63"
HOST_GLOBAL_RVA = 0xB8AA80
ACCEPTED_CORE_RETURN_PREFIX = ("0x17f098", "0x17b387", "0x35b0dc", "0x24025b")
MAX_READ_BYTES = 4096


def _verify_body(body: dict, label: str) -> int:
    if body.get("fragments"):
        pieces = []
        for fragment in body["fragments"]:
            raw = bytes.fromhex(fragment["raw_hex"])
            if (len(raw) != fragment.get("length")
                    or hashlib.sha256(raw).hexdigest() != fragment.get("sha256")):
                raise ValueError("XP2 host+20 source fragment digest changed: " + label)
            cursor = int(fragment["start_rva"], 16)
            for row in fragment.get("instructions", ()):
                code = bytes.fromhex(row["bytes"])
                if (not code or int(row["rva"], 16) != cursor
                        or raw[cursor - int(fragment["start_rva"], 16):
                               cursor - int(fragment["start_rva"], 16) + len(code)] != code):
                    raise ValueError("XP2 host+20 instruction map changed: " + label)
                cursor += len(code)
            if cursor != int(fragment["start_rva"], 16) + len(raw):
                raise ValueError("XP2 host+20 source tail changed: " + label)
            pieces.append(raw)
        complete = b"".join(pieces)
        if (len(complete) != body.get("length")
                or hashlib.sha256(complete).hexdigest() != body.get("sha256")):
            raise ValueError("XP2 host+20 chained body changed: " + label)
        rows = [row for fragment in body["fragments"] for row in fragment["instructions"]]
    else:
        raw = bytes.fromhex(body["raw_hex"])
        if (len(raw) != body.get("length")
                or hashlib.sha256(raw).hexdigest() != body.get("sha256")
                or "".join(row["bytes"] for row in body.get("instructions", ())) != raw.hex()):
            raise ValueError("XP2 host+20 source body changed: " + label)
        rows = body["instructions"]
    if not rows:
        raise ValueError("XP2 host+20 source has no instruction bytes: " + label)
    return len(rows)


def source() -> dict:
    proof = _source(SOURCE)
    if (proof.get("schema") != "civ6-host.xp2-host-slot20-achievement-attempt13.static.v2"
            or proof.get("images", {}).get("xp2", {}).get("sha256") != XP2_CORE_SHA256
            or proof.get("images", {}).get("exe", {}).get("sha256") != EXE_SHA256
            or proof.get("contract", {}).get("host_slot") != "0x20"
            or proof.get("contract", {}).get("host_global_rva") != "0xb8aa80"
            or tuple(proof.get("contract", {}).get("accepted_core_return_prefix", ()))
               != ACCEPTED_CORE_RETURN_PREFIX
            or proof.get("contract", {}).get("only_this_observed_propagating_site_admitted") is not True
            or proof.get("contract", {}).get("other_propagated_or_consumed_callers_admitted") is not False
            or proof.get("validation", {}).get("native_execution") is not False
            or proof.get("validation", {}).get("process_memory_read") is not False
            or proof.get("validation", {}).get("runtime_modified") is not False
            or len(proof.get("bodies", {})) != 5):
        raise ValueError("XP2 host+20 source identity changed")
    refs = proof.get("references", ())
    if not refs:
        raise ValueError("XP2 host+20 source references are missing")
    for ref in refs:
        path = _path(ref["path"])
        if (not path.is_file()
                or hashlib.sha256(path.read_bytes()).hexdigest() != ref["sha256"]):
            raise ValueError("XP2 host+20 source reference changed: " + ref["path"])
    for name, body in proof["bodies"].items():
        _verify_body(body, name)
    # These source joins are the point of the narrow exception: the callback
    # result may leave the helper's method, but the actual parent consumer
    # overwrites RAX before its first read.
    expected = {
        "helper_17f060": ("0x17f095", "call qword ptr [rax + 0x20]"),
        "method_17b190": ("0x17b382", "call 0x18017f060"),
        "owner_35b080": ("0x35b0d9", "call qword ptr [rax + 0x10]"),
        "consumer_240220": ("0x240256", "call 0x18035b080"),
        "consumer_getter_306b80": ("0x306b80", "mov rax, qword ptr [rip + 0x8875b9]"),
    }
    for name, (rva, text) in expected.items():
        rows = [row for body in (proof["bodies"][name],)
                for row in (row for frag in body.get("fragments", ())
                            for row in frag["instructions"])]
        if not rows:
            rows = proof["bodies"][name]["instructions"]
        matches = [row for row in rows if row["rva"] == rva]
        if len(matches) != 1 or matches[0].get("text") != text:
            raise ValueError("XP2 host+20 caller source join changed: " + name)
    return proof


def formation_source() -> dict:
    proof = _source(FORMATION_SOURCE)
    contract = proof.get("contract", {})
    bodies = proof.get("bodies", {})
    if (proof.get("schema") != "civ6-host.xp2-host-slot20-formation.static.v1"
            or proof.get("images") != {"xp2": XP2_CORE_SHA256, "exe": EXE_SHA256}
            or tuple(contract.get("accepted_core_return_prefix", ())) != FORMATION_CORE_RETURN_PREFIX
            or contract.get("shared_parent_sha256") != SOURCE[1]
            or contract.get("absent_service_result") != "null"
            or contract.get("platform_request_submitted") is not False
            or contract.get("platform_success_reported") is not False
            or contract.get("guarded_lifetime_and_thread_required") is not True
            or proof.get("literal") != {"rva": "0x9ceee0", "raw_hex": _FORMATION_LITERAL.hex()}
            or proof.get("listener_vtable") != {"slot_rva": "0x9d1020", "slot": "0x10",
                "target_rva": "0x17fa50", "file_pointer_hex": "50fa178001000000"}
            or proof.get("validation") != {"native_execution": False, "process_memory_read": False,
                                           "runtime_modified": False}):
        raise ValueError("XP2 formation achievement source identity changed")
    expected = {
        "listener_17fa50": ("0x17fa92", "call 0x18017f060"),
        "dispatcher_226e80": ("0x226ed1", "call qword ptr [rax + 0x10]"),
        "producer_1a3290": ("0x1a33a0", "call 0x180226e80"),
        "consumer_65a170": ("0x65a217", "call 0x1800408f0"),
        "getter_0408f0": ("0x4093d", "xor eax, eax"),
    }
    if set(bodies) != set(expected):
        raise ValueError("XP2 formation achievement source bodies changed")
    for name, (rva, text) in expected.items():
        body = bodies[name]
        _verify_body(body, name)
        if sum(row["rva"] == rva and row["text"] == text for frag in body["fragments"]
               for row in frag["instructions"]) != 1:
            raise ValueError("XP2 formation achievement return join changed: " + name)
    return proof


def era_transition_source() -> dict:
    proof = _source(ERA_TRANSITION_SOURCE)
    if (proof["schema"] != "civ6-host.xp2-host-slot20-era-transition.static.v1"
            or proof["images"] != {"xp2": XP2_CORE_SHA256, "exe": EXE_SHA256}
            or tuple(proof["prefix"]) != ERA_TRANSITION_PREFIX
            or proof["literal"] != {"rva": "0x9ceb28", "raw_hex": _ERA_TRANSITION_LITERAL.hex()}
            or proof["native_execution"] is not False
            or proof["platform_success_reported"] is not False):
        raise ValueError("XP2 era-transition achievement source changed")
    expected = {
        "0x177710": (("0x177723", "lea r8, [rip + 0x8573fe]"),
                     ("0x177732", "call 0x18017f060"),
                     ("0x17773d", "call 0x180044f00")),
        "0xda753": (("0xda760", "call qword ptr [rax + 0x10]"),
                    ("0xda763", "mov rdi, rbx"),
                    ("0xda766", "mov rbx, qword ptr [rbx]")),
        "0x284c3f": (("0x284c48", "call 0x1800da700"),
                     ("0x284c4d", "mov rax, qword ptr [rdi + 0x90]")),
    }
    if set(proof["bodies"]) != set(expected):
        raise ValueError("XP2 era-transition achievement windows changed")
    for name, joins in expected.items():
        body = proof["bodies"][name]
        _verify_body(body, name)
        if body["start_rva"] != name or not set(joins) <= {
                (row["rva"], row["text"]) for row in body["instructions"]}:
            raise ValueError("XP2 era-transition achievement call join changed")
    return proof


def raf30_source() -> dict:
    proof = _source(RAF30_SOURCE)
    if (proof["schema"] != "civ6-host.xp2-host-slot20-raf30.static.v1"
            or proof["core_sha256"] != XP2_CORE_SHA256
            or tuple(proof["prefix"]) != RAF30_PREFIX
            or proof["literal"] != {"rva": "0x9d0288", "raw_hex": _RAF30_LITERAL.hex()}
            or proof["native_execution"] is not False
            or proof["platform_success_reported"] is not False):
        raise ValueError("XP2 RAF30 achievement source changed")
    expected = {
        "0x17acf0": {("0x17ad0d", "lea r8, [rip + 0x855574]"),
                     ("0x17ad17", "call 0x18017f060"),
                     ("0x17ad1f", "call 0x18016f6f0")},
        "0x285a9d": {("0x285ab9", "call 0x1800da700"),
                     ("0x285abe", "mov rax, qword ptr [rbx + 0x90]")},
    }
    if set(proof["bodies"]) != set(expected):
        raise ValueError("XP2 RAF30 achievement windows changed")
    for name, joins in expected.items():
        body = proof["bodies"][name]
        _verify_body(body, name)
        if body["start_rva"] != name or not joins <= {
                (row["rva"], row["text"]) for row in body["instructions"]}:
            raise ValueError("XP2 RAF30 achievement call join changed")
    return proof


def city_listener_source() -> dict:
    proof = _source(CITY_LISTENER_SOURCE)
    if (proof["schema"] != "civ6-host.xp2-host-slot20-city-listener.static.v1"
            or proof["core_sha256"] != XP2_CORE_SHA256
            or tuple(proof["prefix"]) != CITY_LISTENER_PREFIX
            or proof["literal"] != {"rva": "0x9cee08", "raw_hex": _CITY_LISTENER_LITERAL.hex()}
            or proof["native_execution"] is not False
            or proof["platform_success_reported"] is not False):
        raise ValueError("XP2 city listener achievement source changed")
    joins = {
        "0x178eaf": {("0x178ebd", "lea r8, [rip + 0x855f44]"),
                     ("0x178ecb", "call 0x18017f060"),
                     ("0x178ed0", "test r15, r15")},
        "0x25c53e": {("0x25c549", "call qword ptr [rax + 0x10]"),
                     ("0x25c54c", "mov rdi, rbx")},
        "0x25d3df": {("0x25d3ec", "call 0x18025c4f0"),
                     ("0x25d3f1", "mov rdx, rbx")},
        "0x25d430": {("0x25d454", "call 0x18025d270"),
                     ("0x25d459", "add rsp, 0x38")},
    }
    if set(proof["bodies"]) != set(joins):
        raise ValueError("XP2 city listener achievement windows changed")
    for name, required in joins.items():
        body = proof["bodies"][name]
        _verify_body(body, name)
        if body["start_rva"] != name or not required <= {
                (row["rva"], row["text"]) for row in body["instructions"]}:
            raise ValueError("XP2 city listener achievement call join changed")
    return proof


def source_dependencies() -> dict[str, str]:
    """Return immutable proof and source references required by the adapter."""
    proof = source()
    formation = formation_source()
    refs = [{"path": SOURCE[0], "sha256": SOURCE[1]}, *proof["references"],
            {"path": FORMATION_SOURCE[0], "sha256": FORMATION_SOURCE[1]}, *formation["references"],
            {"path": ERA_TRANSITION_SOURCE[0], "sha256": ERA_TRANSITION_SOURCE[1]},
            {"path": RAF30_SOURCE[0], "sha256": RAF30_SOURCE[1]},
            {"path": CITY_LISTENER_SOURCE[0], "sha256": CITY_LISTENER_SOURCE[1]}]
    city_listener_source()
    raf30_source()
    era_transition_source()
    pins: dict[str, str] = {}
    for ref in refs:
        path = str(_path(ref["path"]))
        digest = ref["sha256"]
        if path in pins and pins[path] != digest:
            raise ValueError("Conflicting XP2 host+20 source dependency")
        pins[path] = digest
    module_path = str(Path(__file__).resolve())
    module_digest = hashlib.sha256(Path(module_path).read_bytes()).hexdigest()
    if module_path in pins and pins[module_path] != module_digest:
        raise ValueError("XP2 host+20 runtime source pin conflicts")
    pins[module_path] = module_digest
    verify_pinned_files(pins)
    return pins


def _read_exact(read, address: int, length: int) -> bytes:
    value = read(address, length)
    if type(value) is not bytes or len(value) != length:
        raise ValueError("XP2 host+20 live source read was incomplete")
    return value


def verify_live(base: int, read, *, host_pointer: int) -> dict:
    """Match the pinned Core call chain and host-global owner to live memory."""
    if (type(base) is not int or base <= 0 or not callable(read)
            or type(host_pointer) is not int or host_pointer <= 0):
        raise ValueError("XP2 host+20 verification requires an exact Core and host")
    proof = source()
    count = spans = 0
    formation = formation_source()
    era = era_transition_source()
    raf30 = raf30_source()
    city_listener = city_listener_source()
    for name, body in {**proof["bodies"], **formation["bodies"], **era["bodies"],
                       **raf30["bodies"], **city_listener["bodies"]}.items():
        fragments = body.get("fragments") or [body]
        for fragment in fragments:
            raw = bytes.fromhex(fragment.get("raw_hex", ""))
            if not raw:
                raise ValueError("XP2 host+20 live body is incomplete: " + name)
            start_rva = int(fragment.get("start_rva", body.get("start_rva", "0")), 16)
            for offset in range(0, len(raw), MAX_READ_BYTES):
                expected = raw[offset:offset + MAX_READ_BYTES]
                if _read_exact(read, base + start_rva + offset, len(expected)) != expected:
                    raise ValueError("XP2 host+20 live source bytes changed: " + name)
                count += len(expected)
                spans += 1
    if _read_exact(read, base + HOST_GLOBAL_RVA, 8) != host_pointer.to_bytes(8, "little"):
        raise ValueError("XP2 HOST global does not reference the pinned owner")
    if _read_exact(read, base + 0x9ceee0, len(_FORMATION_LITERAL)) != _FORMATION_LITERAL:
        raise ValueError("XP2 formation achievement literal changed")
    if _read_exact(read, base + 0x9d1020, 8) != (base + 0x17fa50).to_bytes(8, "little"):
        raise ValueError("XP2 formation achievement listener slot changed")
    if _read_exact(read, base + 0x9ceb28, len(_ERA_TRANSITION_LITERAL)) != _ERA_TRANSITION_LITERAL:
        raise ValueError("XP2 era-transition achievement literal changed")
    if _read_exact(read, base + 0x9d0288, len(_RAF30_LITERAL)) != _RAF30_LITERAL:
        raise ValueError("XP2 RAF30 achievement literal changed")
    if _read_exact(read, base + 0x9cee08, len(_CITY_LISTENER_LITERAL)) != _CITY_LISTENER_LITERAL:
        raise ValueError("XP2 city listener achievement literal changed")
    count += len(_ERA_TRANSITION_LITERAL) + len(_RAF30_LITERAL) + len(_CITY_LISTENER_LITERAL)
    spans += 3
    return {"source_sha256": SOURCE[1], "formation_source_sha256": FORMATION_SOURCE[1],
            "era_transition_source_sha256": ERA_TRANSITION_SOURCE[1], "raf30_source_sha256": RAF30_SOURCE[1],
            "core_sha256": XP2_CORE_SHA256,
            "city_listener_source_sha256": CITY_LISTENER_SOURCE[1],
            "verified_bytes": count + len(_FORMATION_LITERAL) + 8, "verified_spans": spans + 2,
            "host_global_rva": hex(HOST_GLOBAL_RVA), "native_execution": False}


def select_contract(frames, *, service_installed: bool = False) -> str:
    """Admit only complete, source-proved Core return prefix."""
    source()
    if service_installed is not False:
        raise ValueError("XP2 optional achievement sink must remain explicitly uninstalled")
    if (type(frames) is not list or not frames
            or any(type(frame) is not dict or set(frame) != {"module", "rva"}
                   or type(frame["module"]) is not str
                   or type(frame["rva"]) is not str
                   or re.fullmatch(r"0x[0-9a-f]+", frame["rva"]) is None
                   for frame in frames)):
        raise ValueError("XP2 achievement caller stack is incomplete")
    core_frames = [frame for frame in frames if frame["module"].startswith("GameCore_")]
    if any(frame["module"] != CORE_MODULE for frame in core_frames):
        raise ValueError("Unproved XP2 optional achievement caller chain")
    returns = tuple(frame["rva"] for frame in core_frames)
    if returns[:len(ACCEPTED_CORE_RETURN_PREFIX)] == ACCEPTED_CORE_RETURN_PREFIX:
        return SOURCE[1]
    if returns[:len(FORMATION_CORE_RETURN_PREFIX)] == FORMATION_CORE_RETURN_PREFIX:
        formation_source()
        return FORMATION_SOURCE[1]
    if returns[:len(ERA_TRANSITION_PREFIX)] == ERA_TRANSITION_PREFIX:
        era_transition_source()
        return ERA_TRANSITION_SOURCE[1]
    if returns[:len(RAF30_PREFIX)] == RAF30_PREFIX:
        raf30_source()
        era_transition_source()
        return RAF30_SOURCE[1]
    if returns[:len(CITY_LISTENER_PREFIX)] == CITY_LISTENER_PREFIX:
        city_listener_source()
        return CITY_LISTENER_SOURCE[1]
    raise ValueError("Unproved XP2 optional achievement caller chain")
