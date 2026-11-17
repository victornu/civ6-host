"""Explicit governor gestures through the expansion operation transport.

Native predicates and the selected official panels define the offers. The
adapter never spends titles or computes governor effects in Python.
"""
from struct import Struct

from civ6_host.contracts import governors as contract
from . import xp2_governors_query as query
from .configuration_profiles import XP1_CORE_SHA256, XP2_CORE_SHA256

_HEADER = Struct('<6I')
_ENTRY = Struct('<IHH10sI')


def _route(saved):
    if getattr(getattr(saved.backend, 'load_abi', None), 'core_sha256', None) == XP1_CORE_SHA256:
        from . import xp1_governors_source
        return xp1_governors_source, XP1_CORE_SHA256, 'xp1'
    from . import xp2_governors_source
    return xp2_governors_source, XP2_CORE_SHA256, 'xp2'


def source_dependencies(*, execution_image=None):
    from .xp2_governors_source import source_dependencies as dependencies
    return dependencies(execution_image=execution_image)


def borrowed_enabled(saved, requested=None):
    enabled = getattr(saved, 'governors_diagnostic', False) is True
    if requested is None:
        return enabled
    if type(requested) is not bool or (requested and not enabled):
        raise ValueError('Borrowed governors require the admitted Gathering Storm option')
    return requested


def catalogue(saved, observation, *, active=False, borrowed=False):
    binding, core_sha256, label = _route(saved)
    pid, turn = observation['player_id'], observation['turn']
    if borrowed:
        from .xp1_session_view import _borrowed_xp2_reference

        _borrowed_xp2_reference(saved, pid)
    binding.bind_owner(saved, active=active or borrowed)
    p = saved.prefix
    raw = p.runtime.evaluate_text(p.ui_child,
        query.catalogue_source(pid, turn, binding.support_source(),
                               rise_and_fall=core_sha256 == XP1_CORE_SHA256),
        f'@{label}_governor_catalogue'.encode('ascii'), capacity=query.MAX_PAYLOAD + 1)
    result = query.parse_catalogue(raw, pid, turn)
    if not borrowed:
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


def verify_archive(payload, actor, operation, parameters):
    """Check the exact numeric governor archive observed in the XP2 FIFO."""
    header = (0xc45de12f, actor, operation, 2, 0x80000001, len(parameters))
    if (type(payload) is not bytes
            or len(payload) != _HEADER.size + _ENTRY.size * len(parameters)
            or _HEADER.unpack_from(payload) != header):
        raise RuntimeError('Governor operation archive header differs')
    actual = {}
    for key, length, tag, flags, value in _ENTRY.iter_unpack(payload[_HEADER.size:]):
        if length != 0 or tag != 2 or flags != bytes(10) or key in actual:
            raise RuntimeError('Governor operation archive parameter encoding differs')
        actual[key] = value
    if actual != parameters:
        raise RuntimeError('Governor operation archive parameters differ')


def apply_borrowed(saved, action, before, *, expected, available):
    receipt = dict(status='refused', requested_action=action)
    if not available or expected is None:
        return dict(receipt, reason='native_governor_choice_unavailable'), None
    contract.validate_catalogue(expected, before['player_id'], before['turn'])
    if action not in contract.actions(expected):
        return dict(receipt, reason='native_governor_choice_unavailable'), None
    saved.continuation.transport.require_empty_native_queue()
    result = apply(saved, action, before, borrowed=expected)
    saved.continuation.transport.require_empty_native_queue()
    if 'refusal' in result:
        return dict(receipt, reason=result['refusal']), None
    return dict(receipt, status='completed', reason=None), result['observation']


def apply(saved, action, before, *, borrowed=None):
    from .native.native_player_operation_request import request_player_operation
    from .native.native_player_observation import observe_player
    binding, core_sha256, label = _route(saved)
    binding.bind_owner(saved, active=True)
    contract.validate_action(action)
    expected = saved.continuation.explicit_governors if borrowed is None else borrowed
    if action not in contract.actions(expected):
        raise RuntimeError('Governor action was not offered by this continuation')
    fresh = catalogue(saved, before, active=True, borrowed=borrowed is not None)
    # Revalidate the selected gesture. An unrelated changed public value is not
    # by itself a refusal: native CanStart remains authoritative for requests.
    if action not in contract.actions(fresh):
        if borrowed is not None:
            return dict(refusal='native_governor_choice_changed')
        raise RuntimeError('Governor action is no longer offered')
    p, b = saved.prefix, saved.backend
    if p.actions.pending or p.deferred_events.pending:
        raise RuntimeError('Governor action requires drained owned transports')
    if action['kind'] == 'consider_governor_titles':
        result = p.runtime.evaluate_text(p.ui_child,
            query.consideration_source(before['player_id'], before['turn']),
            f'@{label}_governor_title_consideration'.encode('ascii'), capacity=64)
        if result != b'considered' or p.actions.pending:
            raise RuntimeError('Governor consideration failed or serialized an unexpected operation')
    else:
        operation, parameters = binding.operation_parameters(action)
        result = request_player_operation(b.core, b.context, before['player_id'],
            operation, parameters, core_sha256=core_sha256)
        if not result['can_start'] or not result['request_invoked']:
            if (borrowed is not None and result['can_start'] is False
                    and result['request_invoked'] is False
                    and not p.actions.pending and not p.deferred_events.pending):
                return dict(refusal='native_governor_can_start_false')
            raise RuntimeError('Native CanStartPlayerOperation refused the governor request')
        if (len(p.actions.pending) != 1
                or bytes(p.actions.pending[0][:4]) != (3294486831).to_bytes(4, 'little')):
            raise RuntimeError('Governor request did not emit its single native operation archive')
        if borrowed is not None:
            verify_archive(bytes(p.actions.pending[0]), before['player_id'], operation, parameters)
        p.actions.deliver_one()
    p.deferred_events.drain()
    feedback_owner = saved.continuation.trade_feedback
    if feedback_owner is not None and feedback_owner.events:
        feedback = saved.continuation.flush_trade_feedback()
        if feedback:
            saved.emit('xp2_bbg_trade_gameplay_delivered', feedback=feedback)
    p.view_publisher.publish()
    observed = catalogue(saved, before, active=True, borrowed=borrowed is not None)
    effect = verify_effect(fresh, observed, action)
    if p.actions.pending or p.deferred_events.pending:
        raise RuntimeError('Governor action left pending native work')
    observation = observe_player(p.runtime, p.ui_child, before['player_id'])
    if (observation['player_id'], observation['turn']) != (before['player_id'], before['turn']):
        raise RuntimeError('Governor action crossed its player or turn boundary')
    saved.emit(f'{label}_governor_effect_verified', action=action, before=fresh, after=observed,
        effect=effect, catalogue_changed_since_offer=fresh != expected,
        source_proof_sha256=binding.SOURCE[1], request_source_sha256=binding.REQUEST_SOURCE[1],
        automatic_choices_applied=False)
    return dict(observation=observation, effect=effect)
