"""Read the war popup's configuration from the restored XP2 application B.

The EXE getters and variant conversions are shared with the retained Base
projection. The provider implementation is selected from the existing XP2
configuration/mirror profiles; no Base DLL address is called on an XP2 object.
This does not load content, construct a configuration, or submit game actions.
"""
from __future__ import annotations

import ctypes as C
import struct

from .configuration_profiles import XP2_CORE_SHA256, configuration_abi, require_owner_profile
from .application_mirror_profiles import civilization_source, civilization_source_dependencies
from .native import native_world_configuration as shared
from .native.native_configuration_finalization import _invoke
from .native.native_game_configuration import game_configuration_hash


def verify_source():
    """Join the shared EXE consumer to the already-qualified XP2 provider."""
    exe = shared.verify_source()
    abi = require_owner_profile(configuration_abi(XP2_CORE_SHA256))
    selected = civilization_source(XP2_CORE_SHA256)
    from .xp2_application_mirror_source import source as mirror_source
    mirror = mirror_source()
    if (exe['images']['exe_sha256'] != mirror['exe_sha256']
            or exe['application_b']['value_getter']['slot'] != 0x68
            or selected['variant_size'] != 24
            or dict(mirror['contract']['variant']) != {
                'size': 24, 'tag': 0, 'payload': 8, 'count': 16, 'flags': 20}):
        raise ValueError('XP2 world configuration EXE/provider contract differs')
    return dict(core_sha256=XP2_CORE_SHA256, vtable_rva=abi.vtable_rva,
                getter_slot=exe['application_b']['value_getter']['slot'],
                getter_rva=selected['getter_rva'],
                getter_body=selected['core_functions']['value_getter'],
                shared_exe_source_sha256=shared.PROOF_SHA256,
                provider_source_sha256=selected['source_sha256'])


def source_dependencies():
    verify_source()
    pins = civilization_source_dependencies(XP2_CORE_SHA256)
    path = shared.ROOT / 'evidence/native-world-configuration' / (shared.PROOF_SHA256 + '.json')
    pins[str(path.resolve())] = shared.PROOF_SHA256
    return pins


def _live_getter(base, read, source):
    for fragment in source['getter_body']['fragments']:
        for ins in fragment['instructions']:
            raw = bytes.fromhex(ins['bytes'])
            address = base + int(ins['va'], 16) - 0x180000000
            if shared._bytes(read, address, len(raw)) != raw:
                raise ValueError('XP2 world configuration getter code differs')


def _value(base, pointer, key, read, call, source):
    expected_table = base + source['vtable_rva']
    table, = struct.unpack('<Q', shared._bytes(read, pointer, 8))
    if table != expected_table:
        raise ValueError('XP2 world configuration provider differs')
    target, = struct.unpack('<Q', shared._bytes(read, table + source['getter_slot'], 8))
    if target != base + source['getter_rva']:
        raise ValueError('XP2 world configuration provider or getter differs')
    value = _invoke(call, target, C.c_void_p, pointer, (C.c_uint32,), game_configuration_hash(key))
    if type(value) is not int or value <= 0:
        raise RuntimeError('XP2 world configuration getter returned null')
    return shared._bytes(read, value, 24)


def read(backend, defender_ids):
    """Copy only fields consumed by the selected popup, without native writes."""
    if (type(defender_ids) not in (list, tuple) or not defender_ids or len(defender_ids) > 64
            or any(type(pid) is not int or not 0 <= pid < 64 for pid in defender_ids)
            or len(set(defender_ids)) != len(defender_ids)):
        raise ValueError('Defender ids must be a nonempty unique list from 0..63')
    backend.check_thread()
    if (backend.load_abi.core_sha256 != XP2_CORE_SHA256
            or backend.poisoned or backend.destroyed):
        raise ValueError('World configuration requires the live selected XP2 backend')
    app, base = backend.owner, backend.core._handle
    if getattr(app, '_configuration_abi', None) is not configuration_abi(XP2_CORE_SHA256):
        raise ValueError('World configuration requires the restored XP2 application provider')
    app.require_context(base, backend.context)
    before = app.snapshot()
    read_memory = backend.runtime.read
    call = getattr(backend.runtime, 'call', None)
    source = verify_source()
    _live_getter(base, read_memory, source)

    def value(pointer, key):
        return _value(base, pointer, key, read_memory, call, source)

    multiplayer = shared._mode_is_multiplayer(value(before['normalized'], shared._MODE_KEY))
    rows = {}
    for pid in sorted(defender_ids):
        pointer = before['players'][pid]
        human = shared.human(value(pointer, 'SLOT_STATUS'))
        rows[pid] = dict(
            short_description=shared._text(value(pointer, shared._TEXT_KEYS['short_description']), read_memory, fallback=''),
            civilization_type_name=shared._text(value(pointer, shared._TEXT_KEYS['civilization_type_name']), read_memory, fallback=None),
            is_human=human,
            player_name=(shared._text(value(pointer, shared._TEXT_KEYS['player_name']), read_memory, fallback='')
                         if multiplayer and human else None),
            level_type_id=shared._level(value(pointer, shared._LEVEL_KEY)))
    if app.snapshot() != before:
        raise RuntimeError('XP2 application provider changed during world configuration query')
    app.require_context(base, backend.context)
    result = dict(is_any_multiplayer=multiplayer, players=rows)
    backend.emit('xp2_world_configuration_read', provider='restored_application_B',
                 players=rows, is_any_multiplayer=multiplayer,
                 source_sha256=source['provider_source_sha256'],
                 shared_exe_source_sha256=source['shared_exe_source_sha256'],
                 native_configuration_written=False,
                 player_name_read_only_for_multiplayer_humans=True,
                 native_war_confirmation_qualified=False)
    return result


def lua_bindings(snapshot):
    """Reuse only the pure serializer; getter data comes from the XP2 reader."""
    return shared.lua_bindings(snapshot)
