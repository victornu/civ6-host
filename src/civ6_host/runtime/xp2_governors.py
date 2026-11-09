"""Explicit governor gestures through the existing XP2 operation transport.

Native predicates and the selected official panels define the offers. The
adapter never spends titles or computes governor effects in Python.
"""
from civ6_host.contracts import governors as contract
from . import xp2_governors_query as query
from .configuration_profiles import XP2_CORE_SHA256


def source_dependencies(*, execution_image=None):
    from .xp2_governors_source import source_dependencies as dependencies
    return dependencies(execution_image=execution_image)


def catalogue(saved, observation, *, active=False):
    from .xp2_governors_source import bind_owner, support_source
    bind_owner(saved, active=active)
    pid, turn = observation['player_id'], observation['turn']
    p = saved.prefix
    raw = p.runtime.evaluate_text(p.ui_child,
        query.catalogue_source(pid, turn, support_source()),
        b'@xp2_governor_catalogue', capacity=query.MAX_PAYLOAD + 1)
    result = query.parse_catalogue(raw, pid, turn)
    saved.continuation.explicit_governors = result
    return result


def _governor(value, action):
    rows = [row for row in value['governors']
            if (row['index'], row['hash']) == (action['governor_index'], action['governor_hash'])]
    if len(rows) != 1:
        raise RuntimeError('Governor identity no longer resolves in its exact rules database')
    return rows[0]


def verify_effect(before, after, action):
    """Require the selected native effect without inventing title-cost formulas."""
    kind = action['kind']
    if (before['player_id'], before['current_game_turn']) != (after['player_id'], after['current_game_turn']):
        raise RuntimeError('Governor effect crossed its player or turn boundary')
    if kind == 'consider_governor_titles':
        if before['titles_considered'] or not after['titles_considered']:
            raise RuntimeError('Governor title consideration was not observed')
    else:
        prior, current = _governor(before, action), _governor(after, action)
        if kind == 'appoint_governor':
            if prior['appointed'] or not current['appointed']:
                raise RuntimeError('Native governor appointment was not observed')
        elif kind == 'promote_governor':
            def promotion(row):
                selected = [p for p in row['promotions'] if (p['index'], p['hash']) ==
                            (action['promotion_index'], action['promotion_hash'])]
                if len(selected) != 1:
                    raise RuntimeError('Selected native promotion identity disappeared')
                return selected[0]
            if promotion(prior)['owned'] or not promotion(current)['owned']:
                raise RuntimeError('Native governor promotion was not observed')
        elif kind == 'assign_governor':
            expected = dict(owner=action['city_owner'], city_id=action['city_id'])
            if (prior['status'] is None or current['status'] is None
                    or prior['status']['assigned_city'] == expected
                    or current['status']['assigned_city'] != expected):
                raise RuntimeError('Native governor destination was not observed')
        else:
            raise ValueError('Unexpected governor effect kind')
    return dict(kind=kind, player_id=after['player_id'], current_game_turn=after['current_game_turn'],
                points_obtained_before=before['points_obtained'], points_spent_before=before['points_spent'],
                points_obtained_after=after['points_obtained'], points_spent_after=after['points_spent'],
                native_effect_observed=True, eligible_for_training=False)


def apply(saved, action, before):
    from .xp2_governors_source import bind_owner, operation_parameters, SOURCE, REQUEST_SOURCE
    from .native.native_player_operation_request import request_player_operation
    from .native.native_player_observation import observe_player
    bind_owner(saved, active=True)
    contract.validate_action(action)
    expected = saved.continuation.explicit_governors
    if action not in contract.actions(expected):
        raise RuntimeError('Governor action was not offered by this continuation')
    fresh = catalogue(saved, before, active=True)
    # Revalidate the selected gesture. An unrelated changed public value is not
    # by itself a refusal: native CanStart remains authoritative for requests.
    if action not in contract.actions(fresh):
        raise RuntimeError('Governor action is no longer offered')
    p, b = saved.prefix, saved.backend
    if p.actions.pending or p.deferred_events.pending:
        raise RuntimeError('Governor action requires drained owned transports')
    if action['kind'] == 'consider_governor_titles':
        result = p.runtime.evaluate_text(p.ui_child,
            query.consideration_source(before['player_id'], before['turn']),
            b'@xp2_governor_title_consideration', capacity=64)
        if result != b'considered' or p.actions.pending:
            raise RuntimeError('Governor consideration failed or serialized an unexpected operation')
    else:
        operation, parameters = operation_parameters(action)
        result = request_player_operation(b.core, b.context, before['player_id'],
            operation, parameters, core_sha256=XP2_CORE_SHA256)
        if not result['can_start'] or not result['request_invoked']:
            raise RuntimeError('Native CanStartPlayerOperation refused the governor request')
        if (len(p.actions.pending) != 1
                or bytes(p.actions.pending[0][:4]) != (3294486831).to_bytes(4, 'little')):
            raise RuntimeError('Governor request did not emit its single native operation archive')
        p.actions.deliver_one()
    p.deferred_events.drain()
    feedback_owner = saved.continuation.trade_feedback
    if feedback_owner is not None and feedback_owner.events:
        feedback = saved.continuation.flush_trade_feedback()
        if feedback:
            saved.emit('xp2_bbg_trade_gameplay_delivered', feedback=feedback)
    p.view_publisher.publish()
    observed = catalogue(saved, before, active=True)
    effect = verify_effect(fresh, observed, action)
    if p.actions.pending or p.deferred_events.pending:
        raise RuntimeError('Governor action left pending native work')
    observation = observe_player(p.runtime, p.ui_child, before['player_id'])
    if (observation['player_id'], observation['turn']) != (before['player_id'], before['turn']):
        raise RuntimeError('Governor action crossed its player or turn boundary')
    saved.emit('xp2_governor_effect_verified', action=action, before=fresh, after=observed,
        effect=effect, catalogue_changed_since_offer=fresh != expected,
        source_proof_sha256=SOURCE[1], request_source_sha256=REQUEST_SOURCE[1],
        automatic_choices_applied=False)
    return dict(observation=observation, effect=effect)
