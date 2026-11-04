"""Read only the application-B configuration fields used by DeclareWarPopup.

The reader borrows restored native objects and never writes configuration.
It intentionally reads PlayerName only for the popup's multiplayer/human
branch; other PlayerName branches are represented as ``None``.
"""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import ctypes as C
import hashlib
import json
import struct
from pathlib import Path
from civ6_host.runtime.native.native_configuration_finalization import CORE_SHA256
from civ6_host.runtime.native.native_configuration_finalization import EXE_SHA256
from civ6_host.runtime.native.native_configuration_finalization import _invoke
from civ6_host.runtime.native.native_diplomacy_configuration import human
from civ6_host.runtime.native.native_game_configuration import game_configuration_hash
from civ6_host.runtime.native.native_player_configuration import _checked_object
from civ6_host.runtime.native.native_player_configuration import VALUE_GETTER_SLOT
from civ6_host.runtime.native.native_player_configuration import VALUE_GETTER_RVA
from civ6_host.runtime.native.native_source_cache import load_pinned_json
ROOT = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_world_configuration.py')))).resolve().parents[1]
PROOF_SHA256 = '62dd74236082b2da47fc5a34fd1b59276c1abc951ac7e717e053630a3660e31e'
_TEXT_KEYS = {'short_description': 'CIVILIZATION_SHORT_DESCRIPTION', 'civilization_type_name': 'CIVILIZATION_TYPE_NAME', 'player_name': 'NICK_NAME'}
_LEVEL_KEY = 'CIVILIZATION_LEVEL_TYPE_ID'
_MODE_KEY = 'GAME_MODE'
_SINGLE_PLAYER_HASH = 3915931367
_EMPTY_SHORT_RVA = 16373920

def verify_source():
    if PROOF_SHA256 == 'TO_BE_PINNED':
        raise RuntimeError('Native world-configuration proof has not been pinned')
    proof = load_pinned_json(ROOT / 'evidence/native-world-configuration' / (PROOF_SHA256 + '.json'), PROOF_SHA256)
    if proof.get('schema') != 'civ6rl.native_world_configuration.static.v1' or proof.get('native_execution') is not False or proof.get('images') != {'core_sha256': CORE_SHA256, 'exe_sha256': EXE_SHA256} or (proof.get('parent_registration_proof_sha256') != '84fce676a2438dd67001f44658e6ccaea00bd7dc7663bfcd8307f568214d83eb') or (proof.get('application_b', {}).get('value_getter') != {'core_vtable_rva': 8507296, 'slot': 104, 'target_rva': 7626176}) or (proof.get('validation', {}).get('all_captured_instruction_occurrences_rechecked_against_pinned_pe') is not True) or (proof.get('validation', {}).get('registration_callback_targets_match_parent_method_factory') is not True):
        raise RuntimeError('Native world-configuration source contract changed')
    return proof

def _bytes(read, address, size):
    if type(address) is not int or address <= 0 or (not 0 < size <= 256):
        raise ValueError('Invalid bounded world-configuration read')
    raw = read(address, size)
    if type(raw) is not bytes or len(raw) != size:
        raise ValueError('Incomplete world-configuration memory copy')
    return raw

def _live_getter(core_base, read, proof):
    for ins in proof['parent_core_functions']['value_getter']['instructions']:
        raw = bytes.fromhex(ins['bytes'])
        address = core_base + int(ins['va'], 16) - 6442450944
        if _bytes(read, address, len(raw)) != raw:
            raise ValueError('Native configuration value-getter code changed')

def _value(core_base, config, read, call, key):
    getter = _checked_object(core_base, config, read, VALUE_GETTER_SLOT, VALUE_GETTER_RVA)
    address = _invoke(call, getter, C.c_void_p, config, (C.c_uint32,), game_configuration_hash(key))
    if type(address) is not int or address <= 0:
        raise RuntimeError('Native configuration getter returned null')
    return _bytes(read, address, 24)

def _text(raw, read, *, fallback):
    if type(raw) is not bytes or len(raw) != 24:
        raise ValueError('Invalid native configuration variant')
    tag = struct.unpack_from('<H', raw)[0]
    pointer = struct.unpack_from('<Q', raw, 8)[0]
    flags = struct.unpack_from('<I', raw, 20)[0]
    if tag != 5 or not flags & 1 << 29 or (not pointer):
        return fallback
    value = bytearray()
    for offset in range(4096):
        char = _bytes(read, pointer + offset, 1)
        if char == b'\x00':
            return bytes(value).decode('utf-8')
        value.extend(char)
    raise RuntimeError('Native configuration string exceeds read bound')

def _level(raw):
    if type(raw) is not bytes or len(raw) != 24:
        raise ValueError('Invalid native configuration variant')
    tag = struct.unpack_from('<H', raw)[0]
    flags = struct.unpack_from('<I', raw, 20)[0]
    if tag <= 21 and 3145774 >> tag & 1 and (not flags & 1 << 29):
        return struct.unpack_from('<i', raw, 8)[0]
    return 0

def _mode_is_multiplayer(raw):
    if type(raw) is not bytes or len(raw) != 24:
        raise ValueError('Invalid native GAME_MODE variant')
    tag = struct.unpack_from('<H', raw)[0]
    flags = struct.unpack_from('<I', raw, 20)[0]
    value = struct.unpack_from('<I', raw, 8)[0] if tag <= 21 and 3145774 >> tag & 1 and (not flags & 1 << 29) else 0
    return value != _SINGLE_PLAYER_HASH

def read(owner, defender_ids):
    """Return the popup's exact configuration projection from application B."""
    proof = verify_source()
    if type(defender_ids) not in (list, tuple) or not defender_ids or len(defender_ids) > 64 or any((type(pid) is not int or not 0 <= pid < 64 for pid in defender_ids)) or (len(set(defender_ids)) != len(defender_ids)):
        raise ValueError('Defender ids must be a nonempty unique list from 0..63')
    app = owner.owner
    base = owner.core._handle
    reader = owner.runtime.read
    call = getattr(owner.runtime, 'call', None)
    app.require_context(base, owner.context)
    before = app.snapshot()
    _live_getter(base, reader, proof)
    mode_raw = _value(base, before['normalized'], reader, call, _MODE_KEY)
    multiplayer = _mode_is_multiplayer(mode_raw)
    rows = {}
    for pid in sorted(defender_ids):
        pointer = before['players'][pid]
        status_raw = _value(base, pointer, reader, call, 'SLOT_STATUS')
        is_human = human(status_raw)
        short = _text(_value(base, pointer, reader, call, _TEXT_KEYS['short_description']), reader, fallback='')
        civ_type = _text(_value(base, pointer, reader, call, _TEXT_KEYS['civilization_type_name']), reader, fallback=None)
        level_id = _level(_value(base, pointer, reader, call, _LEVEL_KEY))
        player_name = None
        if multiplayer and is_human:
            player_name = _text(_value(base, pointer, reader, call, _TEXT_KEYS['player_name']), reader, fallback='')
        rows[pid] = {'short_description': short, 'civilization_type_name': civ_type, 'is_human': is_human, 'player_name': player_name, 'level_type_id': level_id}
    if app.snapshot() != before:
        raise RuntimeError('Application provider changed during world-configuration read')
    result = {'is_any_multiplayer': multiplayer, 'players': rows}
    owner.emit('native_world_configuration_read', provider='restored_application_B', players=rows, is_any_multiplayer=multiplayer, source_sha256=PROOF_SHA256, native_configuration_written=False, player_name_read_only_for_multiplayer_humans=True, eligible_for_training=False)
    return result

def lua_bindings(snapshot):
    """Produce lexical bindings for exactly the popup's configuration methods."""
    from civ6_host.runtime.native.native_script_parameters import lua_string
    if type(snapshot) is not dict or set(snapshot) != {'is_any_multiplayer', 'players'} or type(snapshot['is_any_multiplayer']) is not bool or (type(snapshot['players']) is not dict) or (not snapshot['players']):
        raise ValueError('Invalid scoped world-configuration snapshot')
    out = ['local GameConfiguration={IsAnyMultiplayer=function() return %s end}' % str(snapshot['is_any_multiplayer']).lower(), 'local PlayerConfigurations={}']
    expected = {'short_description', 'civilization_type_name', 'is_human', 'player_name', 'level_type_id'}
    for pid, row in sorted(snapshot['players'].items()):
        if type(pid) is not int or not 0 <= pid < 64 or type(row) is not dict or (set(row) != expected) or (type(row['short_description']) is not str) or (row['civilization_type_name'] is not None and type(row['civilization_type_name']) is not str) or (type(row['is_human']) is not bool) or (row['player_name'] is not None and type(row['player_name']) is not str) or (type(row['level_type_id']) is not int):
            raise ValueError('Invalid player world-configuration projection')
        short = lua_string(row['short_description'].encode('utf-8'))
        civ = 'nil' if row['civilization_type_name'] is None else lua_string(row['civilization_type_name'].encode('utf-8'))
        name = "error('GetPlayerName was not read for this popup branch')" if row['player_name'] is None else 'return ' + lua_string(row['player_name'].encode('utf-8'))
        methods = ['GetCivilizationShortDescription=function() return ' + short + ' end', 'GetCivilizationTypeName=function() return ' + civ + ' end', 'IsHuman=function() return ' + str(row['is_human']).lower() + ' end', 'GetCivilizationLevelTypeID=function() return ' + str(row['level_type_id']) + ' end', 'GetPlayerName=function() ' + name + ' end']
        out.append('PlayerConfigurations[%d]={%s}' % (pid, ','.join(methods)))
    return ('\n'.join(out) + '\n').encode('ascii')
