"""Read-only admission of the actual XP2 surprise-war statement factory.

This checks a native registry, constructor and virtual targets. It neither
constructs a statement in Python nor treats source checks as gameplay proof.
"""
import hashlib
import struct

from .execution_images import identity
from .native.native_source_cache import load_pinned_json
from .paths import resource_root
from .resource_resolution import resolve_path

SOURCE = ("work/bbg751-turn-source-scope/war-confirmation/major-factory/source-profile.json",
          "dc0425d85a578417a80d887958c8b33c5659ff6eebface33462f2326e8a7a23c")
REQUEST_NAME = "DECLARE_SURPRISE_WAR"
REQUEST_HASH = 0xeabd49ad
FACTORY_RVA = 0x189d10
VTABLE_RVA = 0x9d2a48
MAX_BUCKETS = 1 << 20
MAX_CHAIN = 256


def source(*, execution_image):
    identity(execution_image)
    if execution_image.id != "xp2-gamecore-current-092abfbb":
        raise ValueError("Statement factory requires the registered current XP2 image")
    proof = load_pinned_json(resolve_path(resource_root()/SOURCE[0]), SOURCE[1])
    if (proof["schema"] != "civ6-host.xp2-war-statement-factory-source.v1"
            or proof["actual_image"]["sha256"] != execution_image.image_sha256
            or proof["reference_core_sha256"] != execution_image.reference_core_sha256
            or proof["supported_request_name"] != REQUEST_NAME
            or int(proof["supported_request_hash"], 16) != REQUEST_HASH
            or int(proof["factory_rva"], 16) != FACTORY_RVA
            or int(proof["vtable"]["rva"], 16) != VTABLE_RVA
            or proof["vtable"]["slots"]["0x10"] != "0x189db0"
            or proof["vtable"]["slots"]["0x28"] != "0x189950"
            or len(proof["bindings"]) != 21
            or not any(int(row["statement_hash"], 16) == REQUEST_HASH
                       and int(row["factory_rva"], 16) == FACTORY_RVA
                       for row in proof["bindings"])
            or proof["registry"] != dict(
                bucket_array_pointer_rva="0xb635c0", bucket_count_rva="0xb635c8",
                node_key_offset=0, node_factory_offset=8, node_next_offset=16,
                end_sentinel_index="bucket_count",
                semantic="Native hash modulo bucket_count; linked bucket nodes; sentinel on lookup miss.")):
        raise ValueError("Statement factory source correspondence changed")
    return proof


def source_dependencies(*, execution_image):
    proof = source(execution_image=execution_image)
    refs = [dict(path=SOURCE[0], sha256=SOURCE[1]), proof["extractor"],
            proof["previous_request_source"], *proof["capture_helpers"]]
    pins = {}
    for row in refs:
        path = resolve_path(resource_root()/row["path"])
        if hashlib.sha256(path.read_bytes()).hexdigest() != row["sha256"]:
            raise ValueError("Statement factory source dependency changed")
        pins[str(path)] = row["sha256"]
    return pins


def _read(read, pointer, size):
    raw = read(pointer, size)
    if type(raw) is not bytes or len(raw) != size:
        raise ValueError("Short statement factory memory read")
    return raw


def _pointer(value):
    if type(value) is not int or not 0x10000 <= value < (1 << 47) or value & 7:
        raise ValueError("Invalid statement factory native pointer")
    return value


def verify_request(base, read, *, execution_image, request_name=REQUEST_NAME):
    """Verify the exact current native registry entry before RequestSession."""
    if request_name != REQUEST_NAME:
        raise ValueError("Unqualified statement request factory")
    _pointer(base)
    proof = source(execution_image=execution_image)
    for name, body in proof["functions"].items():
        for fragment in body["fragments"]:
            raw = bytes.fromhex(fragment["raw_hex"])
            if hashlib.sha256(raw).hexdigest() != fragment["sha256"]:
                raise ValueError("Inconsistent statement factory body capture")
            start = base + int(fragment["start_rva"], 16)
            for offset in range(0, len(raw), 4096):
                expected = raw[offset:offset+4096]
                if _read(read, start+offset, len(expected)) != expected:
                    raise ValueError("Native statement factory code changed: "+name)
    table = proof["vtable"]
    offsets = sorted(int(offset, 16) for offset in table["slots"])
    expected = b"".join(struct.pack("<Q", base+int(table["slots"][hex(offset)], 16))
                        for offset in offsets)
    if _read(read, base+VTABLE_RVA, len(expected)) != expected:
        raise ValueError("Native war-statement virtual targets changed")
    registry = proof["registry"]
    count = struct.unpack("<I", _read(read, base+int(registry["bucket_count_rva"], 16), 4))[0]
    if not 0 < count <= MAX_BUCKETS:
        raise ValueError("Uninitialized or unbounded statement factory registry")
    buckets = _pointer(struct.unpack("<Q", _read(
        read, base+int(registry["bucket_array_pointer_rva"], 16), 8))[0])
    sentinel = struct.unpack("<Q", _read(read, buckets+count*8, 8))[0]
    node = struct.unpack("<Q", _read(read, buckets+(REQUEST_HASH % count)*8, 8))[0]
    seen = set()
    for _ in range(MAX_CHAIN):
        if node in (0, sentinel):
            raise ValueError("Surprise-war statement factory is not registered")
        _pointer(node)
        if node in seen:
            raise ValueError("Cyclic native statement factory bucket")
        seen.add(node)
        key = struct.unpack("<I", _read(read, node, 4))[0]
        if key == REQUEST_HASH:
            factory = struct.unpack("<Q", _read(read, node+8, 8))[0]
            if factory != base+FACTORY_RVA:
                raise ValueError("Registered statement factory differs from its qualified class")
            return dict(source_sha256=SOURCE[1], request_name=REQUEST_NAME,
                        statement_hash=REQUEST_HASH, factory_rva=hex(FACTORY_RVA),
                        vtable_rva=hex(VTABLE_RVA), start_virtual_rva="0x189db0",
                        field_builder_virtual_rva="0x189950",
                        registry_entry_verified=True, native_memory_modified=False,
                        native_factory_invoked=False, gameplay_effect_verified=False)
        node = struct.unpack("<Q", _read(read, node+16, 8))[0]
    raise ValueError("Native statement factory chain exceeds its bound")
