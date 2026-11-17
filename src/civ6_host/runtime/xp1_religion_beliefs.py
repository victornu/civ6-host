"""Explicit installed XP1 ADD_BELIEF only; not the full religious family."""
from copy import deepcopy
from . import xp1_religion_beliefs_source as source
from .native import native_saved_religion as shared
from .native.native_religion_diagnostic import NativeBeliefRefused


source_for = source.source_for
supports = source.supports
source_dependencies = source.source_dependencies
require_actions = source.require_actions


def _identity(value):
    if type(value) is not dict:
        raise ValueError('Belief choice requires the actor observation')
    pid,turn=value.get('player_id'),value.get('turn')
    if type(pid) is not int or not 0 <= pid < 64 or type(turn) is not int or not 0 <= turn <= 0xffffffff:
        raise ValueError('Belief choice actor identity differs')
    return pid,turn


def catalogue(saved, observation):
    saved._check_query()
    source.bind_prefix(saved.prefix)
    pid,turn=_identity(observation)
    value=shared.belief_catalog(saved.prefix,turn,player_id=pid,core_sha256=source.core_for(saved.prefix))
    saved.explicit_religion_beliefs=deepcopy(value)
    return value


def actions(value):
    return shared.belief_actions(value)


def apply(saved, action, before):
    saved._check_active()
    source.bind_prefix(saved.prefix,action=True)
    pid,turn=_identity(before)
    try:
        after=shared.apply_belief(saved,saved.prefix,action,turn,before,
                                 player_id=pid,core_sha256=source.core_for(saved.prefix))
    except NativeBeliefRefused as refusal:
        return dict(status='refused',observation=deepcopy(before),
            refusal_code='native_belief_can_start_false',request=refusal.request,
            source_sha256=source.source_hash(source.core_for(saved.prefix)))
    return dict(status='completed',observation=after,selected_index=action['index'],
                selected_hash=action['hash'],selected_class=action['class'],source_sha256=source.source_hash(source.core_for(saved.prefix)))
