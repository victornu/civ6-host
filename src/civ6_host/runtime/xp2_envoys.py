"""Reuse the native envoy query/effect algorithm on the selected XP2 owner.

The legacy prefix's envoy helper defaults to the Base ABI. This adapter instead
passes the selected XP2 engine to the shared player-operation request explicitly.
"""
from civ6_host.contracts import envoys as contract
from .configuration_profiles import XP2_CORE_SHA256
from .native import native_envoy_actions as native


def source_dependencies(*, execution_image=None):
    from .xp2_envoys_source import source_dependencies as dependencies
    return dependencies(execution_image=execution_image)


def catalogue(saved, observation, *, active=False):
    from .xp2_envoys_source import bind_owner
    bind_owner(saved, active=active)
    pid, turn = observation['player_id'], observation['turn']
    p = saved.prefix
    raw = p.runtime.evaluate_text(p.ui_child, native.catalog_source(pid, turn),
                                 b'@xp2_envoy_catalogue', capacity=8193)
    value = native.parse_catalog(raw, pid, turn)
    value['targets'] = list(value['targets'])
    contract.validate_catalogue(value, pid, turn)
    saved.continuation.explicit_envoys = value
    return value


def apply(saved, action, before):
    from .xp2_envoys_source import bind_owner, SOURCE, APPLICATION
    from .native.native_player_operation_request import request_player_operation
    from .native.native_player_observation import observe_player
    bind_owner(saved, active=True)
    contract.validate_action(action)
    pid, turn = before['player_id'], before['turn']
    expected = saved.continuation.explicit_envoys
    fresh = catalogue(saved, before, active=True)
    if fresh != expected or action not in contract.actions(fresh):
        raise RuntimeError('Envoy decision is stale or no longer offered')
    p, b = saved.prefix, saved.backend
    if p.actions.pending or p.deferred_events.pending:
        raise RuntimeError('Envoy choice requires drained owned transports')
    if action['kind'] == 'send_envoy':
        choice = native.choose(fresh, action['target_player_id'])
        checked = native.validate_fresh_choice(p.runtime.evaluate_text(p.ui_child,
            native.revalidation_source(choice), b'@xp2_envoy_revalidation', capacity=8193), choice)
        operation, parameters = native.operation_parameters(checked)
        result = request_player_operation(b.core, b.context, pid, operation, parameters,
                                          core_sha256=XP2_CORE_SHA256)
        if not result['can_start'] or not result['request_invoked']:
            raise RuntimeError('Native XP2 CanStartPlayerOperation refused envoy assignment')
        if len(p.actions.pending) != 1 or bytes(p.actions.pending[0][:4]) != (3294486831).to_bytes(4, 'little'):
            raise RuntimeError('Envoy request did not emit its single native operation archive')
        p.actions.deliver_one()
        p.deferred_events.drain()
        p.view_publisher.publish()
        observed = catalogue(saved, before, active=True)
        effect = native.verify_sent_effect(observed, choice)
    else:
        requested = native.parse_catalog(p.runtime.evaluate_text(p.ui_child,
            native.consideration_source(fresh), b'@xp2_envoy_consideration', capacity=8193), pid, turn)
        if p.actions.pending or not requested['considered']:
            raise RuntimeError('Envoy consideration serialized a command or did not take effect')
        p.deferred_events.drain()
        p.view_publisher.publish()
        observed = catalogue(saved, before, active=True)
        effect = native.verify_considered_effect(fresh, observed)
    if p.actions.pending or p.deferred_events.pending:
        raise RuntimeError('Envoy operation left pending native work')
    after = observe_player(p.runtime, p.ui_child, pid)
    if after['player_id'] != pid or after['turn'] != turn:
        raise RuntimeError('Envoy action crossed its player or turn boundary')
    saved.emit('xp2_envoy_effect_verified', action=action, before=fresh, after=observed,
        effect=effect, source_proof_sha256=SOURCE[1], application_source_sha256=APPLICATION[1],
        automatic_choices_applied=False)
    return dict(observation=after, effect=effect)
