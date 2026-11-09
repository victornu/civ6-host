"""Exact native factory admission for the selected initial-diplomacy handlers."""
import hashlib
import struct

from .execution_images import identity
from .native.native_source_cache import load_pinned_json
from .paths import resource_root
from .resource_resolution import resolve_path
from .xp2_statement_factory import _read, _pointer, MAX_BUCKETS, MAX_CHAIN

SOURCE = ("work/bbg751-turn-source-scope/war-confirmation/initial-diplomacy-integration/factory-source-profile.json",
          "805f9001539ef83b35312e462a88506c04bd7cb37e583591f97cbef02854e156")


def source(*, execution_image):
    selected = identity(execution_image)
    if selected["profile_id"] != "xp2-gamecore-current-092abfbb":
        raise ValueError("Initial statement factories require the selected current XP2 image")
    proof = load_pinned_json(resolve_path(resource_root()/SOURCE[0]), SOURCE[1])
    from .xp2_diplomacy_overview_source import REQUEST_STATEMENT_TYPES
    if (proof["schema"] != "civ6-host.xp2-initial-factory-source.v1"
            or proof["actual_image"]["sha256"] != selected["image_sha256"]
            or proof["reference_core_sha256"] != selected["reference_core_sha256"]
            or dict(proof["mappings"]) != REQUEST_STATEMENT_TYPES
            or len(proof["registrations"]) != 49 or len(proof["classes"]) != 7
            or set(proof["requests"]) != set(REQUEST_STATEMENT_TYPES.values())
            or {name for name, row in proof["requests"].items()
                if row["expected_registration"] is False} != {"DECLARE_GOLDEN_WAR"}):
        raise ValueError("Initial statement factory source correspondence differs")
    return proof


def source_dependencies(*, execution_image):
    proof = source(execution_image=execution_image)
    refs = [dict(path=SOURCE[0], sha256=SOURCE[1]), proof["extractor"],
            proof["official_dispatch"], *proof["helpers"]]
    pins = {}
    for row in refs:
        path = resolve_path(resource_root()/row["path"])
        if hashlib.sha256(path.read_bytes()).hexdigest() != row["sha256"]:
            raise ValueError("Initial statement factory source dependency changed")
        pins[str(path)] = row["sha256"]
    return pins


def verify_image(base, read, *, execution_image):
    _pointer(base)
    proof = source(execution_image=execution_image)
    for name, body in proof["functions"].items():
        for fragment in body["fragments"]:
            raw = bytes.fromhex(fragment["raw_hex"])
            if hashlib.sha256(raw).hexdigest() != fragment["sha256"]:
                raise ValueError("Inconsistent initial statement source capture")
            for offset in range(0, len(raw), 4096):
                chunk = raw[offset:offset+4096]
                address = base+int(fragment["start_rva"], 16)+offset
                if _read(read, address, len(chunk)) != chunk:
                    raise ValueError("Initial statement factory native code changed: "+name)
    for row in proof["classes"].values():
        slots = row["slots"]
        expected = b"".join(struct.pack("<Q", base+int(slots[hex(offset)], 16))
                            for offset in range(0, 64, 8))
        if _read(read, base+int(row["vtable_rva"], 16), len(expected)) != expected:
            raise ValueError("Initial statement virtual targets changed")
    return proof


def verify_request(base, read, name, *, execution_image):
    proof = source(execution_image=execution_image)
    if type(name) is not str or name not in proof["requests"]:
        raise ValueError("Unqualified initial statement request name")
    verify_image(base, read, execution_image=execution_image)
    target = proof["requests"][name]
    key = int(target["statement_hash"], 16)
    count = struct.unpack("<I", _read(read, base+0xb635c8, 4))[0]
    if not 0 < count <= MAX_BUCKETS:
        raise ValueError("Uninitialized or unbounded initial statement registry")
    buckets = _pointer(struct.unpack("<Q", _read(read, base+0xb635c0, 8))[0])
    sentinel = struct.unpack("<Q", _read(read, buckets+count*8, 8))[0]
    node = struct.unpack("<Q", _read(read, buckets+(key % count)*8, 8))[0]
    seen = set()
    for _ in range(MAX_CHAIN):
        if node in (0, sentinel):
            if target["expected_registration"]:
                raise ValueError("Selected initial statement factory is missing")
            return dict(source_sha256=SOURCE[1], request_name=name,
                        statement_hash=key, expected_registration=False,
                        observed_registration=False, native_memory_modified=False,
                        native_request_invoked=False)
        _pointer(node)
        if node in seen:
            raise ValueError("Cyclic initial statement registry bucket")
        seen.add(node)
        native_key = struct.unpack("<I", _read(read, node, 4))[0]
        if native_key == key:
            if not target["expected_registration"]:
                raise ValueError("Source literal has an unexpected registered native factory")
            expected = base+int(target["factory_rva"], 16)
            if struct.unpack("<Q", _read(read, node+8, 8))[0] != expected:
                raise ValueError("Initial statement registered factory changed")
            return dict(source_sha256=SOURCE[1], request_name=name,
                        statement_hash=key, expected_registration=True,
                        observed_registration=True, factory_rva=target["factory_rva"],
                        vtable_rva=target["vtable_rva"], native_memory_modified=False,
                        native_request_invoked=False)
        node = struct.unpack("<Q", _read(read, node+16, 8))[0]
    raise ValueError("Initial statement registry chain exceeds its bound")
