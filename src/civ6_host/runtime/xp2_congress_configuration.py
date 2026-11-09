"""Source-bound lexical configuration for the retained XP2 Congress UI child.

The application-B provider is borrowed, never constructed or written. These
bindings expose only fields actually read for this query; they do not install
replacement global configuration tables in the native Lua environment.
"""
import ctypes as C
import hashlib
import struct

from .configuration_profiles import XP2_CORE_SHA256, configuration_abi
from .execution_images import identity
from .paths import resource_root
from .resource_resolution import resolve_path
from .native.native_source_cache import load_pinned_json
from .native.native_configuration_finalization import _invoke
from .native.native_game_configuration import game_configuration_hash
from .native.native_script_parameters import lua_string
from . import xp2_world_configuration as configuration
from . import xp2_initial_query_source as initial

SOURCE = ('work/trade-common-client/congress-configuration-source/congress-configuration-source.json',
          '7b2a39c2f52e8955b4785787cba612465c7ebef61769f1b26927adb654551d35')


def source(*, execution_image):
    selected = identity(execution_image)
    proof = load_pinned_json(resolve_path(resource_root() / SOURCE[0]), SOURCE[1])
    alive, name = proof['contract']['IsAlive'], proof['contract']['GetLeaderName']
    if (proof['schema'] != 'civ6-host.congress-configuration-source.v1'
            or proof['images']['core']['sha256'] != selected['image_sha256']
            or selected['reference_core_sha256'] != XP2_CORE_SHA256
            or alive['provider_slot'] != '0x58' or alive['key'] != 'IS_ALIVE'
            or alive['lookup_missing_result'] is not True
            or alive['allowed_numeric_tag_mask'] != '0x30002e'
            or name['provider_slot'] != '0x68'
            or (name['primary_key'], name['secondary_key']) != ('LEADER_NAME', 'CIVILIZATION_SHORT_DESCRIPTION')
            or name['primary_empty_string_triggers_secondary'] is not True
            or name['secondary_invalid_fallback'] != ''
            or any(proof['keys'][key]['hash_u32'] != game_configuration_hash(key) for key in proof['keys'])):
        raise ValueError('Congress configuration caller/provider source differs')
    abi = configuration_abi(XP2_CORE_SHA256)
    for slot, rva in (('0x58', abi.lookup_rva), ('0x68', 0x99f680)):
        row = proof['provider_slots'][slot]
        if int(row['vtable_rva'], 16) != abi.vtable_rva or int(row['target_rva'], 16) != rva:
            raise ValueError('Congress configuration source selects a different provider')
    return proof


def source_dependencies(*, execution_image):
    proof = source(execution_image=execution_image)
    refs = [dict(path=SOURCE[0], sha256=SOURCE[1]), *proof['parents'].values()]
    pins = configuration.source_dependencies()
    pins.update(initial.source_dependencies(execution_image=execution_image))
    for row in refs:
        path = resolve_path(resource_root() / row['path'])
        if hashlib.sha256(path.read_bytes()).hexdigest() != row['sha256']:
            raise ValueError('Congress configuration dependency changed')
        pins[str(path.resolve())] = row['sha256']
    return pins


def _live_lookup(base, read_memory, proof):
    row = proof['spans']['nullable_lookup']
    raw = bytes.fromhex(row['raw_hex'])
    if len(raw) != row['bytes'] or hashlib.sha256(raw).hexdigest() != row['sha256']:
        raise ValueError('Congress nullable lookup capture is inconsistent')
    for offset in range(0, len(raw), 256):
        part = raw[offset:offset + 256]
        if configuration.shared._bytes(read_memory, base + int(row['start_rva'], 16) + offset, len(part)) != part:
            raise ValueError('Congress nullable lookup code changed')


def _lookup(base, pointer, key, read_memory, call, proof):
    row = proof['provider_slots']['0x58']
    table, = struct.unpack('<Q', configuration.shared._bytes(read_memory, pointer, 8))
    if table != base + int(row['vtable_rva'], 16):
        raise ValueError('Congress nullable lookup provider changed')
    target, = struct.unpack('<Q', configuration.shared._bytes(read_memory, table + 0x58, 8))
    if target != base + int(row['target_rva'], 16):
        raise ValueError('Congress nullable lookup virtual target changed')
    address = _invoke(call, target, C.c_void_p, pointer, (C.c_uint32,), game_configuration_hash(key))
    if address is None or (type(address) is int and address == 0):
        return None
    if type(address) is not int or address < 0:
        raise ValueError('Congress nullable lookup returned an invalid pointer')
    return configuration.shared._bytes(read_memory, address, 24)


def alive(raw):
    """Exact EXE IsAlive conversion; an absent key is true, not zero."""
    if raw is None:
        return True
    if type(raw) is not bytes or len(raw) != 24:
        raise ValueError('Invalid Congress alive variant')
    tag = struct.unpack_from('<H', raw)[0]
    flags = struct.unpack_from('<I', raw, 20)[0]
    return bool(tag <= 21 and (0x30002e >> tag) & 1 and not flags & (1 << 29)
                and struct.unpack_from('<I', raw, 8)[0] != 0)


def read(backend, player_ids, *, local_player_id):
    """Read own alive/pause and names for the query's already-met players."""
    if (type(player_ids) not in (list, tuple) or not player_ids or len(player_ids) > 64
            or any(type(pid) is not int or not 0 <= pid < 64 for pid in player_ids)
            or len(set(player_ids)) != len(player_ids)
            or type(local_player_id) is not int or local_player_id not in player_ids):
        raise ValueError('Congress configuration needs unique scoped player IDs')
    backend.check_thread()
    if (backend.load_abi.core_sha256 != XP2_CORE_SHA256 or backend.poisoned or backend.destroyed
            or getattr(backend.owner, '_configuration_abi', None) is not configuration_abi(XP2_CORE_SHA256)):
        raise ValueError('Congress configuration requires the retained XP2 application provider')
    app, base = backend.owner, backend.core._handle
    read_memory, call = backend.runtime.read, getattr(backend.runtime, 'call', None)
    app.require_context(base, backend.context)
    before = app.snapshot()
    proof = source(execution_image=getattr(backend.core, '_civ6_host_execution_image', None))
    selected = configuration.verify_source()
    configuration._live_getter(base, read_memory, selected)
    _live_lookup(base, read_memory, proof)
    rows = {}
    for pid in player_ids:
        pointer = before['players'][pid]
        def value(key):
            return configuration._value(base, pointer, key, read_memory, call, selected)
        leader = configuration.shared._text(value('LEADER_NAME'), read_memory, fallback='')
        if not leader:
            leader = configuration.shared._text(value('CIVILIZATION_SHORT_DESCRIPTION'), read_memory, fallback='')
        rows[pid] = dict(leader_name=leader)
        if pid == local_player_id:
            rows[pid]['alive'] = alive(_lookup(base, pointer, 'IS_ALIVE', read_memory, call, proof))
    paused = initial.read_pause(backend)
    if app.snapshot() != before:
        raise RuntimeError('Application provider changed during Congress configuration read')
    app.require_context(base, backend.context)
    backend.emit('xp2_congress_configuration_read', provider='restored_application_B',
                 players=list(player_ids), local_player_id=local_player_id,
                 source_sha256=SOURCE[1], native_configuration_written=False)
    return dict(local_player_id=local_player_id, paused=paused, players=rows)


def lua_bindings(snapshot):
    if (type(snapshot) is not dict or set(snapshot) != {'local_player_id', 'paused', 'players'}
            or type(snapshot['paused']) is not bool or type(snapshot['players']) is not dict
            or type(snapshot['local_player_id']) is not int or snapshot['local_player_id'] not in snapshot['players']):
        raise ValueError('Invalid Congress configuration snapshot')
    lines = ['local GameConfiguration={IsPaused=function()return %s end}' % str(snapshot['paused']).lower(),
             'local PlayerConfigurations={}']
    for pid, row in sorted(snapshot['players'].items()):
        expected = {'leader_name', 'alive'} if pid == snapshot['local_player_id'] else {'leader_name'}
        if (type(pid) is not int or not 0 <= pid < 64 or type(row) is not dict or set(row) != expected
                or type(row['leader_name']) is not str
                or ('alive' in row and type(row['alive']) is not bool)):
            raise ValueError('Invalid Congress player configuration row')
        methods = ['GetLeaderName=function()return ' + lua_string(row['leader_name'].encode('utf-8')) + ' end']
        if 'alive' in row:
            methods.append('IsAlive=function()return %s end' % str(row['alive']).lower())
        lines.append('PlayerConfigurations[%d]={%s}' % (pid, ','.join(methods)))
    return ('\n'.join(lines) + '\n').encode('ascii')


def attach_namespaces(prefix, backend):
    """Reuse the bound gameplay DB and native namespaces on the same child."""
    backend.check_thread()
    runtime, child = prefix.runtime, prefix.ui_child
    native_runtime = backend.runtime
    current = (backend, runtime, child, backend.host, native_runtime)
    def check():
        if (backend.prefix is not prefix or prefix.backend is not backend
                or prefix.core is not backend.core or prefix.host is not backend.host
                or prefix.runtime is not runtime or backend.runtime is not native_runtime or prefix.ui_child is not child
                or backend.poisoned or backend.destroyed or prefix.closed or prefix.quarantined
                or runtime.database_bound is not True or runtime.service_owner is not backend.host):
            raise ValueError('Congress environment lost its retained database/owner/UI child')
        runtime.registry.validate(child)
    check()
    prior = getattr(prefix, '_congress_environment_binding', None)
    if prior is not None and (len(prior) != len(current) or any(a is not b for a, b in zip(prior, current))):
        raise ValueError('Congress environment was rebound')
    from .network_dialogue import attach_database
    from .native.native_locale_arguments import attach
    attach_database(backend)
    if prior is None:
        runtime.namespaces.register(child, 'GlobalParameters')
    attach(prefix)
    check()
    prefix._congress_environment_binding = current
