"""Explicit installed XP1 prophet activation on the existing saved host."""
from copy import deepcopy
from . import xp1_prophet_activation_source as source
from .configuration_profiles import XP2_CORE_SHA256
from .native import native_prophet_activation as native
from .native import native_saved_religion as shared
from .native.native_religion_diagnostic import NativeProphetRefused


source_for = source.source_for
supports = source.supports
source_dependencies = source.source_dependencies
require_actions = source.require_actions


def _identity(value):
    if type(value) is not dict:
        raise ValueError('Prophet activation requires the actor observation')
    pid,turn=value.get('player_id'),value.get('turn')
    if (type(pid) is not int or not 0 <= pid < 64
            or type(turn) is not int or not 0 <= turn <= 0xffffffff):
        raise ValueError('Prophet activation actor identity differs')
    return pid,turn


def catalogue(saved, observation):
    saved._check_query()
    source.bind_prefix(saved.prefix)
    pid,turn=_identity(observation)
    core_sha256 = source.core_for(saved.prefix)
    value = shared.activation_catalog(saved.prefix,turn,player_id=pid,core_sha256=core_sha256)
    activation = value['activation']
    if core_sha256 == XP2_CORE_SHA256 and activation is not None and not activation['candidates']:
        _emit_availability(saved,observation,activation,pid,turn)
    saved.explicit_prophet_activation=deepcopy(value)
    return value


def _emit_availability(saved, observation, activation, pid, turn):
    own = tuple(sorted((unit['id'],unit['x'],unit['y']) for unit in observation['units']
                       if unit.get('owner') == pid and unit['type'] == activation['prophet_type_index']))
    if not own:
        return
    selected = own[:native.AVAILABILITY_MAX_UNITS]
    continuation, prefix = saved.continuation,saved.prefix
    continuation.transport.require_empty_native_queue()
    source.bind_availability(prefix)
    code = native.availability_source(pid,turn,selected,core_sha256=XP2_CORE_SHA256)
    payload = prefix.runtime.evaluate_text(prefix.ui_child,code,b'@native_prophet_availability',
                                           capacity=native.AVAILABILITY_MAX_WIRE)
    saved._check_query()
    continuation.transport.require_empty_native_queue()
    if prefix.deferred_events.pending:
        raise RuntimeError('Prophet availability query changed the native notification queue')
    visible, rows = native.parse_availability(payload,pid,turn,selected)
    saved.emit('xp2_prophet_availability_readback',actor_channel=False,native_gameplay_mutated=False,
               diagnostic_schema='civ6-host.xp2-prophet-availability.v2',
               episode_id=continuation.identity.episode_id,game_generation=continuation.identity.game_generation,
               sequence=continuation.sequence,player_id=pid,turn=turn,definition_visible=visible,
               own_prophet_count=len(own),units=rows,source_sha256=source.AVAILABILITY_SOURCE[1])


def actions(value):
    return shared.activation_actions(value)


def apply(saved, action, before):
    saved._check_active()
    source.bind_prefix(saved.prefix,action=True)
    pid,turn=_identity(before)
    try:
        after=shared.apply_activation(saved,saved.prefix,action,turn,before,
                                     player_id=pid,core_sha256=source.core_for(saved.prefix))
    except NativeProphetRefused as refusal:
        return dict(status='refused',observation=deepcopy(before),
            refusal_code='native_prophet_can_start_false',request=refusal.request,
            source_sha256=source.source_hash(source.core_for(saved.prefix)))
    return dict(status='completed',observation=after,unit_id=action['unit_id'],
        x=action['x'],y=action['y'],
        founding_site=deepcopy(saved.explicit_prophet_activation['own']['holy_city']),
        source_sha256=source.source_hash(source.core_for(saved.prefix)))
