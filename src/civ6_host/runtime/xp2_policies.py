"""Caller-selected free policy assignments through the native XP2 Culture API."""
from .configuration_profiles import XP1_CORE_SHA256
from .native import native_policy_catalog as catalogue
from .native import native_policy_actions as native
from .xp2_policy_relocation import (
    bind_owner, catalog_source, request_source, confirmation_state_source, parse_confirmation_state)
from .xp2_policy_source import SOURCE


def snapshot(saved, observation):
    core = saved.backend.load_abi.core_sha256
    pid, turn = observation['player_id'], observation['turn']
    if core == XP1_CORE_SHA256:
        from .xp1_government_policy_source import bind_owner as bind_xp1
        bind_xp1(saved)
        source = catalogue.catalog_source(pid, turn, core_sha256=core)
    else:
        bind_owner(saved)
        source = catalog_source(pid, turn)
    raw = saved.prefix.runtime.evaluate_text(saved.prefix.ui_child,
        source,
        b'@xp2_explicit_policy_catalog', capacity=524289)
    return catalogue.parse_catalog(raw, pid, turn, allow_relocation=core != XP1_CORE_SHA256)


def read(saved, observation):
    result = snapshot(saved, observation)
    saved.continuation.explicit_policies = result
    return result


def apply(saved, action, before, *, borrowed=None):
    from .native.native_player_observation import observe_player
    from civ6_host.contracts.policies import choose

    core = saved.backend.load_abi.core_sha256
    xp1 = core == XP1_CORE_SHA256
    pid, turn = before['player_id'], before['turn']
    expected = action['candidate']
    prior = saved.continuation.explicit_policies if borrowed is None else borrowed
    fresh = read(saved, before) if borrowed is None else snapshot(saved, before)
    if fresh != prior or fresh['reason'] != 'available':
        raise RuntimeError('Free policy window or slot choices changed')
    chosen = choose(fresh['slots'], [value & 0xffffffff for _, value in expected['assignments']],
                    pid, turn, allow_relocation=not xp1, allow_unchanged=not xp1)
    if chosen != expected:
        raise RuntimeError('Policy request differs from the native slot choices')
    p = saved.prefix
    def window_state():
        raw=p.runtime.evaluate_text(p.ui_child,confirmation_state_source(pid,turn),
                                   b'@xp2_policy_confirmation_state',capacity=257)
        return parse_confirmation_state(raw,pid,turn)
    prior_window=window_state()
    if prior_window['changed'] or prior_window['unlock_cost']!=0:
        raise RuntimeError('XP2 policy confirmation lost its native free window')
    if xp1:
        from .xp1_government_policy_source import SOURCE as xp1_source
        source_pin = xp1_source[1]
        request = native.request_source(pid, chosen, core_sha256=core)
    else:
        source_pin = SOURCE[1]
        request = request_source(pid, chosen, allow_unchanged=True)
    raw = p.runtime.evaluate_text(p.ui_child, request,
        b'@xp2_explicit_policy_request', capacity=4096)
    accepted = native.parse_request_result(raw, pid, turn, chosen['slot_count'])
    if len(p.actions.pending) != 1:
        raise RuntimeError('Policies require exactly one native queued request')
    if xp1 or borrowed is not None:
        native.validate_assignment_archive(p.actions.pending[0], chosen)
    saved.emit('xp2_explicit_policy_request_submitted', candidate=chosen, accepted=accepted,
               source_proof_sha256=source_pin, native_effect_verified=False)
    p.actions.deliver_one()
    p.deferred_events.drain()
    p.view_publisher.publish()
    raw = p.runtime.evaluate_text(p.ui_child,
        native.effect_source(pid, chosen, core_sha256=core),
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
               source_proof_sha256=source_pin, automatic_choices_applied=False)
    return dict(observation=observed, effect=effect)
