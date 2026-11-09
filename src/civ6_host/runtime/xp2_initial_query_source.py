"""Selected XP2 player-contact Lua APIs and application pause value reader."""
import hashlib
import struct
from pathlib import Path

from .execution_images import identity
from .native.native_source_cache import load_pinned_json
from .paths import resource_root
from .resource_resolution import resolve_path
from .xp2_statement_factory import _read

SOURCE = ("work/bbg751-turn-source-scope/war-confirmation/initial-diplomacy-pause/4ef074b163edd86d4ec5f96be3236a3748620bae0f0e8c6efc8fad9907a1a6d8.json",
          "4ef074b163edd86d4ec5f96be3236a3748620bae0f0e8c6efc8fad9907a1a6d8")
SELECTED = {
    "GetID": ("0x6a8c90", "0x6a9be0"),
    "IsMajor": ("0x6a8c90", "0x6aa640"),
    "HasMet": ("0x6ae510", "0x6b01b0"),
    "GetAliveMajors": ("0x6b1d20", "0x6b25b0"),
}


def source(*, execution_image):
    selected = identity(execution_image)
    proof = load_pinned_json(resolve_path(resource_root()/SOURCE[0]), SOURCE[1])
    getter = proof["pause"]["current_xp2_provider_getter"]
    rows = proof["public_major_api_registrations"]["registrations"]
    actual = {(row["name"], row["registrar_rva"], row["callback_rva"]) for row in rows}
    if (selected["profile_id"] != "xp2-gamecore-current-092abfbb"
            or proof["schema"] != "civ6rl.xp2-pause-and-major-api-source-profile.v1"
            or proof["images"]["actual_xp2"]["sha256"] != selected["image_sha256"]
            or proof["images"]["xp2_provider_reference"]["core_sha256"] != selected["reference_core_sha256"]
            or getter["actual_slot_target_rva"] != "0x99f680"
            or getter["getter_slot"] != "0x68"
            or getter["vtable_rva_from_retained_xp2_profile"] != "0xabf080"
            or getter["reference_body_text_matches_actual"] is not True
            or proof["pause"]["key_source"]["string"] != "GAME_PAUSED"
            or proof["pause"]["key_source"]["value_hash_decimal"] != 2261104600
            or not {(name, *binding) for name, binding in SELECTED.items()} <= actual):
        raise ValueError("XP2 initial query caller/provider source differs")
    return proof


def source_dependencies(*, execution_image):
    proof = source(execution_image=execution_image)
    refs = [dict(path=SOURCE[0], sha256=SOURCE[1]),
            proof["pause"]["registration_source"], *proof["source_inputs"].values()]
    pins = {}
    for row in refs:
        path = resolve_path(resource_root()/Path(row["path"]))
        if hashlib.sha256(path.read_bytes()).hexdigest() != row["sha256"]:
            raise ValueError("XP2 initial-query source dependency changed")
        pins[str(path)] = row["sha256"]
    return pins


def verify_live(base, read, *, execution_image):
    proof = source(execution_image=execution_image)
    apis = proof["public_major_api_registrations"]
    bodies = [*apis["registrar_bodies"].values(), *apis["callback_bodies"].values(),
              proof["pause"]["current_xp2_provider_getter"]["actual_body"]]
    for body in bodies:
        for fragment in body["fragments"]:
            raw = bytes.fromhex(fragment["raw_hex"])
            if hashlib.sha256(raw).hexdigest() != fragment["sha256"]:
                raise ValueError("Inconsistent XP2 initial query body capture")
            for offset in range(0, len(raw), 4096):
                chunk = raw[offset:offset+4096]
                if _read(read, base+int(fragment["start_rva"], 16)+offset, len(chunk)) != chunk:
                    raise ValueError("XP2 initial query native binding changed")
    for row in apis["registrations"]:
        raw = row["name"].encode("ascii")+b"\0"
        if _read(read, base+int(row["name_rva"], 16), len(raw)) != raw:
            raise ValueError("XP2 initial query registered method name changed")
    if _read(read, base+0xabf080+0x68, 8) != struct.pack("<Q", base+0x99f680):
        raise ValueError("XP2 initial query value-getter virtual target changed")
    return proof


def read_pause(backend):
    """Use the XP2 value getter; only the proven pure Boolean conversion is shared."""
    backend.check_thread()
    from . import xp2_world_configuration as configuration
    from .diplomacy_overview import paused_from_variant
    core = backend.core
    proof = source(execution_image=getattr(core, "_civ6_host_execution_image", None))
    config_source = configuration.verify_source()
    if (config_source["getter_slot"] != 0x68 or config_source["getter_rva"] != 0x99f680
            or config_source["vtable_rva"] != 0xabf080):
        raise ValueError("XP2 pause reader selected a different configuration provider")
    app, base, read = backend.owner, core._handle, backend.runtime.read
    app.require_context(base, backend.context)
    before = app.snapshot()
    configuration._live_getter(base, read, config_source)
    raw = configuration._value(base, before["normalized"], "GAME_PAUSED",
                               read, getattr(backend.runtime, "call", None), config_source)
    paused = paused_from_variant(raw)
    if app.snapshot() != before:
        raise RuntimeError("Application provider changed during XP2 pause read")
    backend.emit("xp2_initial_diplomacy_pause_read", paused=paused,
                 source_sha256=SOURCE[1], native_configuration_written=False)
    return paused
