"""Government and policy choices for the borrowed Gathering Storm human."""

from civ6_host.contracts import capability_policies, government
from civ6_host.contracts import policies as assignment
from civ6_host.contracts import policy_unlock
from . import xp2_government, xp2_policies, xp2_policy_unlock


FIELDS = {'government': 'government', 'retain_government': 'government',
          'policies': 'policies', 'policy_unlock': 'policy_unlock'}


def enabled(saved):
    return getattr(saved, '_xp2_lan_government_enabled', False) is True


def validate_action(action):
    kind = action['kind']
    if kind == 'policies':
        capability_policies.validate_explicit_action(action)
    elif kind == 'policy_unlock':
        policy_unlock.validate_action(action)
    else:
        government.validate_action(action)


def read(saved, observation, *, strategic_allowed):
    if not enabled(saved) or not strategic_allowed:
        return {}
    from .xp1_session_view import _borrowed_xp2_reference

    _borrowed_xp2_reference(saved, observation['player_id'])
    return dict(government=xp2_government.snapshot(saved, observation)[1],
                policies=xp2_policies.snapshot(saved, observation),
                policy_unlock=xp2_policy_unlock.snapshot(saved, observation)[1])


def apply(saved, action, observation, states, *, expected):
    kind = action['kind']
    current = states.get(FIELDS[kind])
    refusal = dict(status='refused', requested_action=action)
    if current is None:
        return dict(refusal, reason='native_government_choice_unavailable'), None
    if current != expected:
        return dict(refusal, reason='native_government_choice_changed'), None
    if kind == 'policies':
        if current['reason'] != 'available':
            return dict(refusal, reason='native_policy_assignment_unavailable'), None
        candidate = action['candidate']
        hashes = [value & 0xffffffff for _, value in candidate['assignments']]
        try:
            canonical = assignment.choose(current['slots'], hashes, observation['player_id'],
                observation['turn'], allow_relocation=True, allow_unchanged=True)
        except assignment.PolicyAssignmentUnavailable:
            return dict(refusal, reason='native_policy_assignment_unavailable'), None
        if candidate != canonical:
            return dict(refusal, reason='native_policy_assignment_unavailable'), None
        provider = xp2_policies
    else:
        is_unlock = kind == 'policy_unlock'
        offers = policy_unlock.actions(current) if is_unlock else government.actions(current)
        if action not in offers:
            return dict(refusal, reason='native_government_choice_unavailable'), None
        provider = xp2_policy_unlock if is_unlock else xp2_government

    token = saved.continuation
    token.transport.require_empty_native_queue()
    count = token.publication_count
    result = provider.apply(saved, action, observation, borrowed=current)
    if token.publication_count != count + 1:
        raise RuntimeError('Borrowed government choice did not publish its native effect')
    after = result['observation']
    feedback = token.trade_feedback
    if feedback is not None and feedback.events:
        delivered = token.flush_trade_feedback()
        if delivered:
            saved.emit('xp2_bbg_trade_gameplay_delivered', feedback=delivered)
        from .native.native_player_observation import observe_player

        after = observe_player(saved.prefix.runtime, saved.prefix.ui_child, observation['player_id'])
    token.transport.require_empty_native_queue()
    return dict(status='completed', reason=None, requested_action=action), after
