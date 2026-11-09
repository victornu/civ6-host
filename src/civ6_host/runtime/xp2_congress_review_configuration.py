"""Scoped configuration for the official Congress results projection.

The public reader derives player and leader-name scopes from the
official public result branches; this module does not widen those scopes.
"""
from civ6_host.runtime import xp2_congress_configuration as congress
from civ6_host.runtime import xp2_world_configuration as configuration
from civ6_host.runtime.configuration_profiles import XP2_CORE_SHA256, configuration_abi
from civ6_host.runtime.native.native_script_parameters import lua_string


def _ids(values, label):
    if (type(values) not in (list, tuple) or len(values) > 64
            or any(type(value) is not int or not 0 <= value < 64 for value in values)
            or len(set(values)) != len(values)):
        raise ValueError('Invalid Congress review ' + label)
    return tuple(values)


def read(backend, player_ids, *, leader_ids):
    """Reuse native getter/conversion ABIs, never reading unscoped names."""
    ids, leaders = _ids(player_ids, 'players'), _ids(leader_ids, 'leader scope')
    if not set(leaders) <= set(ids):
        raise ValueError('Review leader scope exceeds its result players')
    backend.check_thread()
    if (backend.load_abi.core_sha256 != XP2_CORE_SHA256 or backend.poisoned or backend.destroyed
            or getattr(backend.owner, '_configuration_abi', None) is not configuration_abi(XP2_CORE_SHA256)):
        raise ValueError('Review requires the retained XP2 application provider')
    app, base = backend.owner, backend.core._handle
    app.require_context(base, backend.context)
    before = app.snapshot()
    memory, call = backend.runtime.read, getattr(backend.runtime, 'call', None)
    # Congress owns the exact leader-name primary/secondary conversion.
    congress.source(execution_image=getattr(backend.core, '_civ6_host_execution_image', None))
    selected = configuration.verify_source()
    configuration._live_getter(base, memory, selected)
    def value(pointer, key):
        return configuration._value(base, pointer, key, memory, call, selected)
    shared = configuration.shared
    multiplayer = shared._mode_is_multiplayer(value(before['normalized'], shared._MODE_KEY))
    rows = {}
    for pid in ids:
        pointer = before['players'][pid]
        human = shared.human(value(pointer, 'SLOT_STATUS'))
        name = (shared._text(value(pointer, shared._TEXT_KEYS['player_name']), memory, fallback='')
                if multiplayer and human else None)
        leader = None
        if pid in leaders:
            leader = shared._text(value(pointer, 'LEADER_NAME'), memory, fallback='')
            if not leader:
                leader = shared._text(value(pointer, 'CIVILIZATION_SHORT_DESCRIPTION'), memory, fallback='')
        rows[pid] = dict(is_human=human, player_name=name, leader_name=leader)
    if app.snapshot() != before:
        raise RuntimeError('Review configuration provider changed during read')
    app.require_context(base, backend.context)
    return dict(is_any_multiplayer=multiplayer, players=rows)


def lua_bindings(snapshot):
    if (type(snapshot) is not dict or set(snapshot) != {'is_any_multiplayer', 'players'}
            or type(snapshot['is_any_multiplayer']) is not bool or type(snapshot['players']) is not dict):
        raise ValueError('Invalid review configuration snapshot')
    _ids(list(snapshot['players']), 'configuration players')
    lines = ['local GameConfiguration={IsAnyMultiplayer=function()return %s end}' %
             str(snapshot['is_any_multiplayer']).lower(), 'local PlayerConfigurations={}']
    for pid, row in sorted(snapshot['players'].items()):
        if (type(row) is not dict or set(row) != {'is_human', 'player_name', 'leader_name'}
                or type(row['is_human']) is not bool
                or any(value is not None and type(value) is not str
                       for value in (row['player_name'], row['leader_name']))
                or (row['player_name'] is not None) != (snapshot['is_any_multiplayer'] and row['is_human'])):
            raise ValueError('Invalid review player configuration')
        methods = ['IsHuman=function()return %s end' % str(row['is_human']).lower()]
        for key, method in (('leader_name', 'GetLeaderName'), ('player_name', 'GetPlayerName')):
            body = ("error('Review configuration method outside public scope')"
                    if row[key] is None else 'return ' + lua_string(row[key].encode('utf8')))
            methods.append(method + '=function()' + body + ' end')
        lines.append('PlayerConfigurations[%d]={%s}' % (pid, ','.join(methods)))
    return ('\n'.join(lines) + '\n').encode('ascii')
