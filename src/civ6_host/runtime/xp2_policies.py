"""Caller-selected free policy assignments through the native XP2 Culture API."""
from .configuration_profiles import XP2_CORE_SHA256
from .native import native_policy_catalog as catalogue
from .native import native_policy_actions as native
from .xp2_policy_relocation import (
    bind_owner, catalog_source, request_source, confirmation_state_source, parse_confirmation_state)
from .xp2_policy_source import SOURCE


def read(saved, observation):
    bind_owner(saved)
    pid, turn = observation['player_id'], observation['turn']
    raw = saved.prefix.runtime.evaluate_text(saved.prefix.ui_child,
        catalog_source(pid, turn),
        b'@xp2_explicit_policy_catalog', capacity=524289)
    result = catalogue.parse_catalog(raw, pid, turn, allow_relocation=True)
    saved.continuation.explicit_policies = result
    return result


def apply(saved, action, before):
    from .native.native_player_observation import observe_player
    from civ6_host.contracts.policies import choose

    bind_owner(saved)
    pid, turn = before['player_id'], before['turn']
    expected = action['candidate']
    prior = saved.continuation.explicit_policies
    fresh = read(saved, before)
    if fresh != prior or fresh['reason'] != 'available':
        raise RuntimeError('XP2 free policy window or slot choices changed')
    chosen = choose(fresh['slots'], [value & 0xffffffff for _, value in expected['assignments']],
                    pid, turn, allow_relocation=True, allow_unchanged=True)
    if chosen != expected:
        raise RuntimeError('XP2 policy request differs from the native slot choices')
    p = saved.prefix
    def window_state():
        raw=p.runtime.evaluate_text(p.ui_child,confirmation_state_source(pid,turn),
                                   b'@xp2_policy_confirmation_state',capacity=257)
        return parse_confirmation_state(raw,pid,turn)
    prior_window=window_state()
    if prior_window['changed'] or prior_window['unlock_cost']!=0:
        raise RuntimeError('XP2 policy confirmation lost its native free window')
    raw = p.runtime.evaluate_text(p.ui_child,
        request_source(pid, chosen, allow_unchanged=True),
        b'@xp2_explicit_policy_request', capacity=4096)
    accepted = native.parse_request_result(raw, pid, turn, chosen['slot_count'])
    if len(p.actions.pending) != 1:
        raise RuntimeError('XP2 policies require exactly one native queued request')
    saved.emit('xp2_explicit_policy_request_submitted', candidate=chosen, accepted=accepted,
               source_proof_sha256=SOURCE[1], native_effect_verified=False)
    p.actions.deliver_one()
    p.deferred_events.drain()
    p.view_publisher.publish()
    raw = p.runtime.evaluate_text(p.ui_child,
        native.effect_source(pid, chosen, core_sha256=XP2_CORE_SHA256),
        b'@xp2_explicit_policy_effect', capacity=4096)
    effect = native.parse_effect(raw, pid, chosen, turn)
    final_window=window_state()
    unchanged=[row['prior_index'] for row in fresh['slots']]==[index for _,index in effect['readback']]
    saved.emit('xp2_policy_confirmation_state_observed',
               assignment_unchanged=unchanged,before=prior_window,after=final_window,
               native_request_delivered=True)
    if unchanged and not final_window['changed']:
        raise RuntimeError('Native unchanged policy request delivered without a verified confirmation turn marker')
    effect['confirmation_window_before']=prior_window
    effect['confirmation_window_after']=final_window
    effect['native_request_delivered']=True
    effect['assignment_unchanged']=unchanged
    effect['confirmation_verified_by']='turn_marker' if unchanged else 'slot_readback'
    observed = observe_player(p.runtime, p.ui_child, pid)
    saved.emit('xp2_explicit_policy_effect_verified', candidate=chosen, effect=effect,
               source_proof_sha256=SOURCE[1], automatic_choices_applied=False)
    return dict(observation=observed, effect=effect)
