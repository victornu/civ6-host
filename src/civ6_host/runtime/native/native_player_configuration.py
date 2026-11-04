"""Bounded writes to already-owned native player configuration objects.

This module never allocates Core objects. It accepts only a setup-owned record
0 or 1, and only identities paired in the pinned Players database domain.
"""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import ctypes as C
import sqlite3
from pathlib import Path
from civ6_host.runtime.native.native_game_configuration import game_configuration_hash
from civ6_host.runtime.native.native_player_records import bounded_get_player_config
PLAYER_CONFIG_VTABLE_RVA = 8507296
VALUE_GETTER_SLOT = 104
VALUE_GETTER_RVA = 7626176
STRING_SETTER_SLOT = 264
STRING_SETTER_RVA = 7657312
HASHED_ID_SETTER_SLOT = 296
HASHED_ID_SETTER_RVA = 7628480
INTEGER_SETTER_SLOT = 304
INTEGER_SETTER_RVA = 7628192
ERASE_SLOT = 320
ERASE_RVA = 7626960
LOOKUP_SLOT = 88
LOOKUP_RVA = 7625904
SLOT_STATUS = 'SLOT_STATUS'
CIVILIZATION_TYPE_NAME = 'CIVILIZATION_TYPE_NAME'
CIVILIZATION_TYPE_ID = 'CIVILIZATION_TYPE_ID'
LEADER_TYPE_NAME = 'LEADER_TYPE_NAME'
LEADER_TYPE_ID = 'LEADER_TYPE_ID'
LEADER_RANDOM_POOL_ID = 'LEADER_RANDOM_POOL_ID'
CIVILIZATION_LEVEL_TYPE_NAME = 'CIVILIZATION_LEVEL_TYPE_NAME'
CIVILIZATION_LEVEL_TYPE_ID = 'CIVILIZATION_LEVEL_TYPE_ID'
TEAM = 'TEAM'
HANDICAP_TYPE_ID = 'HANDICAP_TYPE_ID'
SS_TAKEN = 3

def _local_reader():
    kernel = C.WinDLL('kernel32', use_last_error=True)
    kernel.GetCurrentProcess.argtypes = []
    kernel.GetCurrentProcess.restype = C.c_void_p
    kernel.ReadProcessMemory.argtypes = [C.c_void_p, C.c_void_p, C.c_void_p, C.c_size_t, C.POINTER(C.c_size_t)]
    kernel.ReadProcessMemory.restype = C.c_int
    process = kernel.GetCurrentProcess()

    def read(address: int, size: int) -> bytes:
        if not isinstance(address, int) or address <= 0 or (not 0 < size <= 256):
            raise ValueError('Native player-config read is outside the bounded range')
        buffer = C.create_string_buffer(size)
        count = C.c_size_t()
        if not kernel.ReadProcessMemory(process, C.c_void_p(address), buffer, size, C.byref(count)):
            raise C.WinError(C.get_last_error())
        if count.value != size:
            raise RuntimeError('Incomplete native player-config memory copy')
        return buffer.raw
    return read

def _validate_player_pair(database: str | Path, civilization: str, leader: str) -> dict:
    if any((not isinstance(item, str) or not item or '\x00' in item for item in (civilization, leader))):
        raise ValueError('Civilization and leader must be exact nonempty DB identifiers')
    path = _resolve_resource_path(Path(database)).absolute()
    with sqlite3.connect(path.as_uri() + '?mode=ro', uri=True) as connection:
        rows = connection.execute('SELECT P.Domain, P.CivilizationType, P.LeaderType, P.HumanPlayable FROM Players P WHERE P.CivilizationType=? AND P.LeaderType=? AND EXISTS (SELECT 1 FROM PlayerItems I WHERE I.Domain=P.Domain AND I.CivilizationType=P.CivilizationType AND I.LeaderType=P.LeaderType) ORDER BY P.Domain', (civilization, leader)).fetchall()
        items = connection.execute('SELECT CivilizationType, LeaderType FROM PlayerItems WHERE CivilizationType=? AND LeaderType=? LIMIT 1', (civilization, leader)).fetchone()
    eligible = [row for row in rows if bool(row[3])]
    if not eligible:
        raise KeyError('Civilization/leader pair is absent or not HumanPlayable in Players')
    if items is None:
        raise KeyError('Civilization/leader pair has no matching PlayerItems row')
    return {'players_domains': sorted({str(row[0]) for row in eligible}), 'civilization': civilization, 'leader': leader, 'human_playable': True, 'player_item_pair_present': True}

def _checked_object(core_base: int, config: int, read, slot: int, target_rva: int) -> int:
    vtable = int.from_bytes(read(config, 8), 'little')
    if vtable != core_base + PLAYER_CONFIG_VTABLE_RVA:
        raise ValueError('Unexpected normalized player configuration vtable')
    target = int.from_bytes(read(vtable + slot, 8), 'little')
    if target != core_base + target_rva:
        raise ValueError(f'Unverified player configuration vtable slot +0x{slot:x}')
    return target

def _read_integer(core_base: int, config: int, key: int, read, expected_tag: int) -> int:
    getter = _checked_object(core_base, config, read, VALUE_GETTER_SLOT, VALUE_GETTER_RVA)
    value = C.WINFUNCTYPE(C.c_void_p, C.c_void_p, C.c_uint32)(getter)(config, key)
    if not value:
        raise RuntimeError('Core returned no value for player configuration key')
    raw = read(value, 24)
    tag = int.from_bytes(raw[:4], 'little')
    flags = int.from_bytes(raw[20:24], 'little')
    observed = int.from_bytes(raw[8:12], 'little')
    if tag != expected_tag or flags & 1 << 29:
        raise RuntimeError(f'Expected unowned player-config variant tag {expected_tag}, got {tag}')
    return observed

def _read_string(core_base: int, config: int, key: int, read) -> str:
    """Decode the proven tag-5 c-string payload used by player-name getters."""
    getter = _checked_object(core_base, config, read, VALUE_GETTER_SLOT, VALUE_GETTER_RVA)
    value = C.WINFUNCTYPE(C.c_void_p, C.c_void_p, C.c_uint32)(getter)(config, key)
    if not value:
        raise RuntimeError('Core returned no value for player name configuration key')
    raw = read(value, 24)
    tag = int.from_bytes(raw[:2], 'little')
    flags = int.from_bytes(raw[20:24], 'little')
    text_pointer = int.from_bytes(raw[8:16], 'little')
    if tag != 5 or not flags & 1 << 29 or (not text_pointer):
        raise RuntimeError('Expected Core tag-5 player-name variant with a borrowed string pointer')
    pieces = bytearray()
    for offset in range(256):
        byte = read(text_pointer + offset, 1)
        if byte == b'\x00':
            try:
                return bytes(pieces).decode('ascii', 'strict')
            except UnicodeDecodeError as error:
                raise RuntimeError('Player configuration name is not ASCII') from error
        pieces.extend(byte)
    raise RuntimeError('Player configuration name exceeded the 256-byte read bound')

def _has_value(core_base: int, config: int, key: int, read) -> bool:
    lookup = _checked_object(core_base, config, read, LOOKUP_SLOT, LOOKUP_RVA)
    return bool(C.WINFUNCTYPE(C.c_void_p, C.c_void_p, C.c_uint32)(lookup)(config, key))

def _validate_handicap(database: str | Path, difficulty: str) -> str:
    if not isinstance(difficulty, str) or not difficulty or '\x00' in difficulty:
        raise ValueError('Difficulty must be an exact nonempty DB identifier')
    path = _resolve_resource_path(Path(database)).absolute()
    with sqlite3.connect(path.as_uri() + '?mode=ro', uri=True) as connection:
        found = connection.execute('SELECT 1 FROM Difficulties WHERE DifficultyType=? LIMIT 1', (difficulty,)).fetchone()
    if found is None:
        raise KeyError(f'Difficulty {difficulty!r} is absent from the database')
    return difficulty

def set_player_identity(core_base: int, context: int, database: str | Path, index: int, civilization: str, leader: str, read=None, lookup=None, *, team_id: int | None=None, handicap_type: str='DIFFICULTY_PRINCE') -> dict:
    """Set one existing major player to a DB-valid human slot and identity.

    The allowed status is deliberately only SS_TAKEN (3). In the pinned EXE,
    that status takes the native helper's immediate-return branch after writing
    SLOT_STATUS, so its wrapper-owned HUMAN_REQUIRED side-effect path is not
    applicable to this direct normalized-object write.
    """
    if isinstance(index, bool) or not isinstance(index, int) or index not in (0, 1):
        raise ValueError('Only already-owned setup player records 0 and 1 are admitted')
    if not isinstance(core_base, int) or core_base <= 0 or (not isinstance(context, int)) or (context <= 0):
        raise ValueError('Invalid GameCore base or active context')
    db_pair = _validate_player_pair(database, civilization, leader)
    handicap_type = _validate_handicap(database, handicap_type)
    if team_id is not None and (isinstance(team_id, bool) or not isinstance(team_id, int) or (not 0 <= team_id <= 63)):
        raise ValueError('Team ID must be an integer in 0..63')
    read = read or _local_reader()
    borrowed = bounded_get_player_config(core_base, context, index, read=read, lookup=lookup)
    config = int(borrowed['pointer'])
    integer_setter = _checked_object(core_base, config, read, INTEGER_SETTER_SLOT, INTEGER_SETTER_RVA)
    hash_setter = _checked_object(core_base, config, read, HASHED_ID_SETTER_SLOT, HASHED_ID_SETTER_RVA)
    string_setter = _checked_object(core_base, config, read, STRING_SETTER_SLOT, STRING_SETTER_RVA)
    getter = _checked_object(core_base, config, read, VALUE_GETTER_SLOT, VALUE_GETTER_RVA)
    eraser = _checked_object(core_base, config, read, ERASE_SLOT, ERASE_RVA)
    set_integer = C.WINFUNCTYPE(C.c_void_p, C.c_void_p, C.c_uint32, C.c_uint32)(integer_setter)
    set_hash = C.WINFUNCTYPE(C.c_void_p, C.c_void_p, C.c_uint32, C.c_uint32)(hash_setter)
    set_string = C.WINFUNCTYPE(C.c_void_p, C.c_void_p, C.c_uint32, C.c_char_p)(string_setter)
    get_value = C.WINFUNCTYPE(C.c_void_p, C.c_void_p, C.c_uint32)(getter)
    erase_value = C.WINFUNCTYPE(C.c_void_p, C.c_void_p, C.c_uint32)(eraser)
    set_integer(config, game_configuration_hash(SLOT_STATUS), SS_TAKEN)
    civ_level = 'CIVILIZATION_LEVEL_FULL_CIV'
    civ_level_buffer = C.create_string_buffer(civ_level.encode('ascii'))
    set_string(config, game_configuration_hash(CIVILIZATION_LEVEL_TYPE_NAME), C.cast(civ_level_buffer, C.c_char_p))
    C.memset(civ_level_buffer, 88, C.sizeof(civ_level_buffer))
    set_hash(config, game_configuration_hash(CIVILIZATION_LEVEL_TYPE_ID), game_configuration_hash(civ_level))
    civ_bytes = civilization.encode('ascii', 'strict')
    civ_buffer = C.create_string_buffer(civ_bytes)
    set_string(config, game_configuration_hash(CIVILIZATION_TYPE_NAME), C.cast(civ_buffer, C.c_char_p))
    C.memset(civ_buffer, 88, C.sizeof(civ_buffer))
    set_hash(config, game_configuration_hash(CIVILIZATION_TYPE_ID), game_configuration_hash(civilization))
    leader_bytes = leader.encode('ascii', 'strict')
    leader_buffer = C.create_string_buffer(leader_bytes)
    set_string(config, game_configuration_hash(LEADER_TYPE_NAME), C.cast(leader_buffer, C.c_char_p))
    C.memset(leader_buffer, 88, C.sizeof(leader_buffer))
    set_hash(config, game_configuration_hash(LEADER_TYPE_ID), game_configuration_hash(leader))
    erase_value(config, game_configuration_hash(LEADER_RANDOM_POOL_ID))
    if team_id is not None:
        set_integer(config, game_configuration_hash(TEAM), team_id)
    set_hash(config, game_configuration_hash(HANDICAP_TYPE_ID), game_configuration_hash(handicap_type))
    observed_status = _read_integer(core_base, config, game_configuration_hash(SLOT_STATUS), read, 2)
    observed_civ_id = _read_integer(core_base, config, game_configuration_hash(CIVILIZATION_TYPE_ID), read, 3)
    observed_leader_id = _read_integer(core_base, config, game_configuration_hash(LEADER_TYPE_ID), read, 3)
    has_random_pool_id = _has_value(core_base, config, game_configuration_hash(LEADER_RANDOM_POOL_ID), read)
    observed_level_id = _read_integer(core_base, config, game_configuration_hash(CIVILIZATION_LEVEL_TYPE_ID), read, 3)
    observed_handicap = _read_integer(core_base, config, game_configuration_hash(HANDICAP_TYPE_ID), read, 3)
    observed_team = _read_integer(core_base, config, game_configuration_hash(TEAM), read, 2) if team_id is not None else None
    observed_civilization = _read_string(core_base, config, game_configuration_hash(CIVILIZATION_TYPE_NAME), read)
    observed_leader = _read_string(core_base, config, game_configuration_hash(LEADER_TYPE_NAME), read)
    if (observed_status, observed_civ_id, observed_leader_id) != (SS_TAKEN, game_configuration_hash(civilization), game_configuration_hash(leader)):
        raise RuntimeError('Player identity/status round-trip did not match the requested values')
    if has_random_pool_id:
        raise RuntimeError('Named-leader configuration retained a random-pool override')
    if (observed_civilization, observed_leader) != (civilization, leader):
        raise RuntimeError('Player name round-trip did not match the requested identifiers')
    if observed_level_id != game_configuration_hash(civ_level):
        raise RuntimeError('Player civilization-level round-trip did not match FULL_CIV')
    if observed_handicap != game_configuration_hash(handicap_type):
        raise RuntimeError('Player handicap round-trip did not match the requested difficulty')
    if team_id is not None and observed_team != team_id:
        raise RuntimeError('Player team round-trip did not match the requested team ID')
    return {'index': index, 'config_pointer_is_borrowed': borrowed['pointer_is_borrowed'], 'slot_status': 'SS_TAKEN', 'slot_status_value': observed_status, **db_pair, 'civilization_hash': observed_civ_id, 'civilization_level_type': civ_level, 'civilization_level_hash': observed_level_id, 'leader_id_hash': observed_leader_id, 'leader_random_pool_id_present': has_random_pool_id, 'handicap_type': handicap_type, 'handicap_hash': observed_handicap, 'team_id': observed_team, 'identity_values_roundtrip_verified': True, 'civilization_name_readback': observed_civilization, 'leader_name_readback': observed_leader, 'name_value_roundtrip_verified': True}
