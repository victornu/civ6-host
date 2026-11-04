"""Read pinned Civilization VI configuration descriptors without mutating them.

Lua's MapConfiguration userdata is EXE-owned. This module intentionally exposes
the verified database choices as data; it does not fabricate that userdata or
guess how the MAP_SIZE hash is encoded in Core's normalized value tree.
"""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import sqlite3
import ctypes as C
import zlib
from dataclasses import dataclass
from pathlib import Path

@dataclass(frozen=True)
class MapSize:
    map_size_type: str
    sort_index: int
    min_players: int
    max_players: int
    default_players: int
    min_city_states: int
    max_city_states: int
    default_city_states: int
STANDARD_MAP_SIZE_PARAMETER = {'parameter_id': 'MapSize', 'configuration_id': 'MAP_SIZE', 'domain': 'StandardMapSizes', 'hash': True}
MAP_SIZE_CONFIGURATION_KEY = 2632306504
GAMECORE_CONFIGURATION_VTABLE_RVA = 8507296
GAMECORE_MAP_INTEGER_SETTER_SLOT = 304
GAMECORE_MAP_INTEGER_SETTER_RVA = 7628192
GAMECORE_MAP_VALUE_GETTER_SLOT = 104
GAMECORE_MAP_VALUE_GETTER_RVA = 7626176
GAMECORE_BOOLEAN_SETTER_SLOT = 312
GAMECORE_BOOLEAN_SETTER_RVA = 7632112
RANDOM_SEED_CONFIGURATION_KEY = 2529544060

def standard_map_sizes(database: str | Path) -> tuple[MapSize, ...]:
    """Read the standard map-size domain from a SQLite DB opened read-only."""
    path = _resolve_resource_path(Path(database)).absolute()
    uri = path.as_uri() + '?mode=ro'
    with sqlite3.connect(uri, uri=True) as connection:
        rows = connection.execute("SELECT MapSizeType, SortIndex, MinPlayers, MaxPlayers, DefaultPlayers,\n                      MinCityStates, MaxCityStates, DefaultCityStates\n                 FROM MapSizes WHERE Domain='StandardMapSizes' ORDER BY SortIndex").fetchall()
    result = tuple((MapSize(str(row[0]), *(int(value) for value in row[1:])) for row in rows))
    if not result or len({item.map_size_type for item in result}) != len(result):
        raise ValueError('Pinned DB has no unique StandardMapSizes domain')
    return result

def find_map_size(database: str | Path, map_size_type: str) -> MapSize:
    """Resolve an exact DB identifier such as MAPSIZE_SMALL, case-sensitively."""
    if not isinstance(map_size_type, str) or not map_size_type or '\x00' in map_size_type:
        raise ValueError('Map size must be a nonempty database identifier')
    for item in standard_map_sizes(database):
        if item.map_size_type == map_size_type:
            return item
    raise KeyError(f'Unknown StandardMapSizes identifier: {map_size_type}')

def game_configuration_hash(value: str) -> int:
    """Pinned EXE MakeHash semantics: reflected CRC-32, seed FFFFFFFF, no final XOR."""
    if not isinstance(value, str) or not value or '\x00' in value:
        raise ValueError('Hash input must be a nonempty string without NUL')
    encoded = value.encode('ascii', 'strict')
    return (zlib.crc32(encoded) ^ 4294967295) & 4294967295

def set_hotseat_game_mode(core_base: int, context: int, read=None) -> dict:
    """Set the source-proven mode property; not a replacement for SetToDefaults.

    EXE 10C500 -> 1039D0 uses hash setter +128. Registered IsHotseat's
    helper 102110 compares the getter's numeric value with 0C67CEE3.
    """
    key = game_configuration_hash('GAME_MODE')
    value = game_configuration_hash('HOTSEAT')
    if (key, value) != (103015827, 208129763):
        raise RuntimeError('Pinned game mode hash contract changed')
    observed = _set_and_read_named_integer(core_base, context, 'normalized_configuration', key, value, read, slot=296, expected_tag=3)
    if observed['value'] != value:
        raise RuntimeError('Native HOTSEAT game mode did not persist')
    return {'configuration_id': 'GAME_MODE', 'mode': 'HOTSEAT', 'key_hash': key, 'native_value': value, 'variant_tag': observed['tag'], 'roundtrip_verified': True, 'complete_set_to_defaults_reproduced': False}

def set_normalized_map_size(core_base: int, context: int, database: str | Path, map_size_type: str, read=None) -> dict:
    """Set and verify the hashed MapSize token on an active Core setup context."""
    size = find_map_size(database, map_size_type)
    value_hash = game_configuration_hash(size.map_size_type)
    observed = _set_and_read_map_integer(core_base, context, MAP_SIZE_CONFIGURATION_KEY, value_hash, read)
    if observed['value'] != value_hash:
        raise RuntimeError('MAP_SIZE did not persist through the Core integer setter')
    return {'configuration_id': 'MAP_SIZE', 'key_hash': MAP_SIZE_CONFIGURATION_KEY, 'map_size_type': size.map_size_type, 'value_hash': value_hash, 'value_hash_hex': hex(value_hash), 'sort_index': size.sort_index, 'player_bounds': [size.min_players, size.max_players], 'default_players': size.default_players, 'variant_tag': observed['tag'], 'readback_value': observed['value'], 'roundtrip_verified': True}

def set_normalized_map_random_seed(core_base: int, context: int, seed: int, read=None) -> dict:
    """Set and verify the integer RANDOM_SEED key on an active Core context."""
    if isinstance(seed, bool) or not isinstance(seed, int) or (not 0 <= seed <= 4294967295):
        raise ValueError('Map random seed must fit an unsigned 32-bit integer')
    observed = _set_and_read_map_integer(core_base, context, RANDOM_SEED_CONFIGURATION_KEY, seed, read)
    if observed['value'] != seed:
        raise RuntimeError('RANDOM_SEED did not persist through the Core integer setter')
    return {'configuration_id': 'RANDOM_SEED', 'key_hash': RANDOM_SEED_CONFIGURATION_KEY, 'value': seed, 'variant_tag': observed['tag'], 'roundtrip_verified': True}

def set_named_integer(core_base: int, context: int, database: str | Path, scope: str, configuration_id: str, value: int | str, read=None, *, parameter_id: str | None=None) -> dict:
    """Set one DB-declared integer Game/Map parameter through the proven Core slot.

    Only exact ConfigurationGroup/ConfigurationId rows with proven native
    setter contracts qualify. Hash=1 values must be exact DB domain tokens and
    are encoded with the pinned EXE hash. Boolean, text, player settings, and
    unknown scopes are refused.
    """
    if scope not in ('Game', 'Map'):
        raise ValueError("Configuration scope must be exactly 'Game' or 'Map'")
    if not isinstance(configuration_id, str) or not configuration_id or '\x00' in configuration_id:
        raise ValueError('ConfigurationId must be a nonempty database identifier')
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        raise TypeError('Configuration value must be an integer or exact DB token')
    descriptor = _integer_parameter(database, scope, configuration_id, value, parameter_id=parameter_id)
    if configuration_id == 'GAME_MAX_TURNS' and isinstance(value, int) and (value < 1):
        raise ValueError('GAME_MAX_TURNS callback requires a value of at least 1')
    native_value = game_configuration_hash(value) if descriptor['hash'] else value
    if not isinstance(native_value, int) or not 0 <= native_value <= 4294967295:
        raise ValueError('Core integer values must fit uint32')
    key = game_configuration_hash(configuration_id)
    object_name = 'normalized_configuration' if scope == 'Game' else 'normalized_map'
    slot, tag = _named_integer_setter(scope, configuration_id)
    observed = _set_and_read_named_integer(core_base, context, object_name, key, native_value, read, slot=slot, expected_tag=tag)
    if observed['value'] != native_value:
        raise RuntimeError(f'{configuration_id} did not persist through the Core integer setter')
    return {'scope': scope, 'configuration_id': configuration_id, 'parameter_ids': descriptor['parameter_ids'], 'domain': descriptor['domain'], 'parameter_id': parameter_id, 'key_hash': key, 'value': value, 'native_value': native_value, 'hash_encoded': descriptor['hash'], 'variant_tag': observed['tag'], 'roundtrip_verified': True}
_HASHED_DOMAIN_TABLES = {'StandardMapSizes': ('MapSizes', 'MapSizeType'), 'StandardGameSpeeds': ('GameSpeeds', 'GameSpeedType'), 'StandardEras': ('Eras', 'EraType'), 'StandardTurnTimers': ('TurnTimers', 'TurnTimerType'), 'StandardTurnLimits': ('DomainValues', 'Value')}

def _integer_parameter(database: str | Path, scope: str, configuration_id: str, value: int | str, *, parameter_id: str | None=None) -> dict:
    path = _resolve_resource_path(Path(database)).absolute()
    with sqlite3.connect(path.as_uri() + '?mode=ro', uri=True) as connection:
        sql = 'SELECT ParameterId, Domain, Hash FROM Parameters\n                  WHERE ConfigurationGroup=? AND ConfigurationId=?'
        args: tuple = (scope, configuration_id)
        if parameter_id is not None:
            if not isinstance(parameter_id, str) or not parameter_id or '\x00' in parameter_id:
                raise ValueError('ParameterId must be a nonempty database identifier')
            sql += ' AND ParameterId=?'
            args += (parameter_id,)
        sql += ' ORDER BY ParameterId, Domain'
        rows = connection.execute(sql, args).fetchall()
        if not rows:
            raise KeyError(f'No {scope} parameter for ConfigurationId {configuration_id!r}')
        hash_flags = {bool(row[2]) for row in rows}
        if len(hash_flags) != 1:
            raise ValueError('ConfigurationId has conflicting database hash semantics')
        is_hashed = next(iter(hash_flags))
        domains = {str(row[1]) for row in rows}
        if len(domains) != 1:
            raise ValueError('ConfigurationId has conflicting database domains')
        domain = next(iter(domains))
        if is_hashed:
            if not isinstance(value, str) or domain not in _HASHED_DOMAIN_TABLES:
                raise ValueError('Hash=1 requires a supported exact string domain token')
            table, column = _HASHED_DOMAIN_TABLES[domain]
            if table == 'DomainValues':
                available = connection.execute('SELECT 1 FROM DomainValues WHERE Domain=? AND Value=? LIMIT 1', (domain, value)).fetchone()
            else:
                available = connection.execute(f'SELECT 1 FROM {table} WHERE Domain=? AND {column}=? LIMIT 1', (domain, value)).fetchone()
            if available is None:
                raise ValueError(f'{value!r} is absent from database domain {domain}')
        elif domain in ('int', 'uint'):
            if not isinstance(value, int):
                raise TypeError(f'{configuration_id} requires a numeric database value')
        else:
            if not isinstance(value, int):
                raise TypeError(f'{configuration_id} requires an enumerated integer')
            available = connection.execute('SELECT 1 FROM DomainValues WHERE Domain=? AND Value=? LIMIT 1', (domain, value)).fetchone()
            if available is None:
                raise ValueError(f'{configuration_id} value is absent from DB domain {domain}')
        if domain == 'int' and isinstance(value, int) and (value > 2147483647):
            raise ValueError('Signed DB integer exceeds int32 range')
        if domain == 'uint' and isinstance(value, int) and (value > 4294967295):
            raise ValueError('Unsigned DB integer exceeds uint32 range')
        return {'parameter_ids': sorted({str(row[0]) for row in rows}), 'domain': domain, 'hash': is_hashed}

def set_standard_victory_enabled(core_base: int, context: int, database: str | Path, victory_type: str, enabled: bool=True, read=None, ruleset: str='RULESET_STANDARD') -> dict:
    """Set a DB-listed StandardVictories flag through Core's verified bool slot."""
    if enabled is not True:
        raise ValueError('This bounded helper only enables standard victories')
    if not isinstance(victory_type, str) or not victory_type or '\x00' in victory_type:
        raise ValueError('VictoryType must be an exact database identifier')
    path = _resolve_resource_path(Path(database)).absolute()
    uri = path.as_uri() + '?mode=ro'
    with sqlite3.connect(uri, uri=True) as connection:
        domain_row = connection.execute('SELECT VictoryDomain FROM Rulesets WHERE RulesetType=?', (ruleset,)).fetchone()
        if domain_row is None:
            raise KeyError(f'Unknown ruleset: {ruleset}')
        row = connection.execute('SELECT Visible, ReadOnly, EnabledByDefault FROM Victories WHERE Domain=? AND VictoryType=?', (domain_row[0], victory_type)).fetchone()
    if row is None or not bool(row[0]) or bool(row[1]):
        raise KeyError(f'{victory_type!r} is not an editable visible victory for {ruleset}')
    key = game_configuration_hash(victory_type)
    result = _set_and_read_named_boolean(core_base, context, key, True, read)
    return {'configuration_group': 'Game', 'ruleset': ruleset, 'victory_domain': str(domain_row[0]), 'victory_type': victory_type, 'enabled': True, 'enabled_by_default': bool(row[2]), 'key_hash': key, 'variant_tag': result['tag'], 'readback_value': result['value'], 'roundtrip_verified': result['value'] is True}

def standard_victories(database: str | Path, ruleset: str='RULESET_STANDARD') -> tuple[str, ...]:
    """Return DB-generated victory parameters enabled by this ruleset's defaults."""
    path = _resolve_resource_path(Path(database)).absolute()
    with sqlite3.connect(path.as_uri() + '?mode=ro', uri=True) as connection:
        rows = connection.execute('SELECT V.VictoryType FROM Victories V JOIN Rulesets R ON V.Domain=R.VictoryDomain\n                 WHERE R.RulesetType=? AND V.Visible=1 AND V.ReadOnly=0\n                   AND V.EnabledByDefault=1 ORDER BY V.VictoryType', (ruleset,)).fetchall()
    return tuple((str(row[0]) for row in rows))

def _set_and_read_named_boolean(core_base: int, context: int, key: int, value: bool, read=None) -> dict:
    from civ6_host.runtime.native.native_setup import local_reader
    from civ6_host.runtime.native.native_setup import inspect_setup
    if read is None:
        read = local_reader()
    snapshot = inspect_setup(core_base, context, read)
    target = int(snapshot['fields']['normalized_configuration']['raw_value'])
    if not target:
        raise RuntimeError('Normalized Game configuration object is absent')
    vtable = int.from_bytes(read(target, 8), 'little')
    if vtable != core_base + GAMECORE_CONFIGURATION_VTABLE_RVA:
        raise ValueError('Unknown normalized Game configuration vtable')
    setter = int.from_bytes(read(vtable + GAMECORE_BOOLEAN_SETTER_SLOT, 8), 'little')
    if setter != core_base + GAMECORE_BOOLEAN_SETTER_RVA:
        raise ValueError('Unverified GameCore boolean setter')
    getter = int.from_bytes(read(vtable + GAMECORE_MAP_VALUE_GETTER_SLOT, 8), 'little')
    if getter != core_base + GAMECORE_MAP_VALUE_GETTER_RVA:
        raise ValueError('Unverified GameCore value getter')
    set_value = C.WINFUNCTYPE(C.c_void_p, C.c_void_p, C.c_uint32, C.c_uint8)(setter)
    get_value = C.WINFUNCTYPE(C.c_void_p, C.c_void_p, C.c_uint32)(getter)
    set_value(target, key, int(value))
    variant = get_value(target, key)
    if not variant:
        raise RuntimeError('Core returned no value for normalized victory key')
    raw = read(variant, 24)
    tag = int.from_bytes(raw[:4], 'little')
    flags = int.from_bytes(raw[20:24], 'little')
    if tag != 1 or flags & 1 << 29:
        raise RuntimeError(f'Expected an unowned Core boolean variant (tag 1), got tag {tag}')
    return {'tag': tag, 'value': bool(raw[8])}

def _named_integer_setter(scope: str, configuration_id: str) -> tuple[int, int]:
    if scope == 'Game' and configuration_id in ('GAME_SPEED_TYPE', 'GAME_START_ERA'):
        return (296, 3)
    if scope == 'Map' and configuration_id == 'MAP_SIZE':
        return (304, 2)
    if scope == 'Game' and configuration_id in ('GAME_SYNC_RANDOM_SEED', 'GAME_MAX_TURNS', 'TURN_TIMER_TIME', 'TURN_TIMER_TYPE', 'GAME_TURN_LIMIT'):
        return (304, 2)
    if scope == 'Map' and configuration_id in ('RANDOM_SEED', 'start', 'temperature', 'world_age', 'rainfall', 'resources', 'sea_level'):
        return (304, 2)
    raise ValueError('No statically verified native integer setter for this ConfigurationId')

def _set_and_read_named_integer(core_base: int, context: int, field_name: str, key: int, value: int, read=None, *, slot: int=304, expected_tag: int=2) -> dict:
    from civ6_host.runtime.native.native_setup import local_reader
    from civ6_host.runtime.native.native_setup import inspect_setup
    if not isinstance(core_base, int) or not core_base or (not isinstance(context, int)) or (not context):
        raise ValueError('Core image base and context pointers must be nonzero integers')
    if field_name not in ('normalized_configuration', 'normalized_map'):
        raise ValueError('Unknown normalized configuration field')
    if read is None:
        read = local_reader()
    snapshot = inspect_setup(core_base, context, read)
    target = int(snapshot['fields'][field_name]['raw_value'])
    if not target:
        raise RuntimeError(f'Normalized {field_name} object is absent')
    vtable = int.from_bytes(read(target, 8), 'little')
    if vtable != core_base + GAMECORE_CONFIGURATION_VTABLE_RVA:
        raise ValueError(f'Unknown normalized {field_name} vtable')
    setter = int.from_bytes(read(vtable + slot, 8), 'little')
    expected_setter = {304: GAMECORE_MAP_INTEGER_SETTER_RVA, 296: 7628480}.get(slot)
    if expected_setter is None or setter != core_base + expected_setter:
        raise ValueError('Unverified GameCore integer setter')
    getter = int.from_bytes(read(vtable + GAMECORE_MAP_VALUE_GETTER_SLOT, 8), 'little')
    if getter != core_base + GAMECORE_MAP_VALUE_GETTER_RVA:
        raise ValueError('Unverified GameCore value getter')
    set_value = C.WINFUNCTYPE(C.c_void_p, C.c_void_p, C.c_uint32, C.c_uint32)(setter)
    get_value = C.WINFUNCTYPE(C.c_void_p, C.c_void_p, C.c_uint32)(getter)
    set_value(target, key, value)
    variant = get_value(target, key)
    if not variant:
        raise RuntimeError('Core returned no value for normalized configuration key')
    raw = read(variant, 24)
    tag = int.from_bytes(raw[:4], 'little')
    flags = int.from_bytes(raw[20:24], 'little')
    observed = int.from_bytes(raw[8:12], 'little')
    if tag != expected_tag or flags & 1 << 29:
        raise RuntimeError(f'Expected an unowned Core integer variant (tag {expected_tag}), got tag {tag}')
    return {'tag': tag, 'flags': flags, 'value': observed}

def _set_and_read_map_integer(core_base: int, context: int, key: int, value: int, read=None) -> dict:
    from civ6_host.runtime.native.native_setup import local_reader
    from civ6_host.runtime.native.native_setup import inspect_setup
    if not isinstance(core_base, int) or not core_base or (not isinstance(context, int)) or (not context):
        raise ValueError('Core image base and context pointers must be nonzero integers')
    if not 0 <= value <= 4294967295:
        raise ValueError('Configuration integer must fit uint32')
    if read is None:
        read = local_reader()
    snapshot = inspect_setup(core_base, context, read)
    normalized_map = int(snapshot['fields']['normalized_map']['raw_value'])
    if not normalized_map:
        raise RuntimeError('Normalized map configuration object is absent')
    vtable = int.from_bytes(read(normalized_map, 8), 'little')
    if vtable != core_base + GAMECORE_CONFIGURATION_VTABLE_RVA:
        raise ValueError('Unknown normalized map configuration vtable')
    setter = int.from_bytes(read(vtable + GAMECORE_MAP_INTEGER_SETTER_SLOT, 8), 'little')
    if setter != core_base + GAMECORE_MAP_INTEGER_SETTER_RVA:
        raise ValueError('Unverified GameCore map integer setter')
    getter = int.from_bytes(read(vtable + GAMECORE_MAP_VALUE_GETTER_SLOT, 8), 'little')
    if getter != core_base + GAMECORE_MAP_VALUE_GETTER_RVA:
        raise ValueError('Unverified GameCore map value getter')
    set_value = C.WINFUNCTYPE(C.c_void_p, C.c_void_p, C.c_uint32, C.c_uint32)(setter)
    get_value = C.WINFUNCTYPE(C.c_void_p, C.c_void_p, C.c_uint32)(getter)
    set_value(normalized_map, key, value)
    variant = get_value(normalized_map, key)
    if not variant:
        raise RuntimeError('Core returned no value for the normalized map key')
    raw = read(variant, 24)
    tag = int.from_bytes(raw[0:4], 'little')
    flags = int.from_bytes(raw[20:24], 'little')
    observed = int.from_bytes(raw[8:12], 'little')
    if tag != 2 or flags & 1 << 29:
        raise RuntimeError(f'Expected an unowned Core integer variant (tag 2), got tag {tag}')
    return {'tag': tag, 'flags': flags, 'value': observed}
