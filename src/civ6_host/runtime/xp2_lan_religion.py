"""Borrow the actor's official prophet, religion and belief choices."""

from civ6_host.contracts import network_turn, religion_beliefs
from . import xp1_prophet_activation_source, xp1_religion_beliefs_source, xp1_religion_founding_source
from . import xp1_religious_unit_operations as religious_units
from .configuration_profiles import XP2_CORE_SHA256
from .native import native_saved_religion as native
from .native.native_religion_diagnostic import NativeProphetRefused
from .xp1_session_view import _borrowed_xp2_reference


_READERS = {
    'prophet_activation': ('activation', xp1_prophet_activation_source, native.activation_catalog,
                           native.apply_activation),
    'religion_founding': ('foundation', xp1_religion_founding_source, native.foundation_catalog,
                          native.apply_foundation),
    'religion_beliefs': ('beliefs', xp1_religion_beliefs_source, native.belief_catalog, native.apply_belief),
}
_UNIT_FIELD = 'religious_unit_operations'
FIELDS = {kind: field for field, kinds in network_turn.SECONDARY_RELIGION_KINDS.items() for kind in kinds}


def scope(saved, requested=None):
    available = tuple(field for field in network_turn.SECONDARY_RELIGION_CONTRACTS
                      if getattr(saved, 'xp2_' + field, False) is True)
    if requested is None:
        return available
    if type(requested) is not tuple or requested != tuple(field for field in available if field in requested):
        raise ValueError('Borrowed religion requires the admitted Gathering Storm options')
    return requested


def validate_action(action):
    network_turn.SECONDARY_RELIGION_CONTRACTS[FIELDS[action['kind']]].validate_action(action)


def _read(saved, observation, field):
    subfield, source, catalogue, _ = _READERS[field]
    pid, turn = observation['player_id'], observation['turn']
    _borrowed_xp2_reference(saved, pid)
    prefix = saved.prefix
    source.bind_prefix(prefix)
    raw = catalogue(prefix, turn, player_id=pid, core_sha256=XP2_CORE_SHA256)
    contract = network_turn.SECONDARY_RELIGION_CONTRACTS[field]
    state = dict(schema=contract.SCHEMA, player_id=pid, turn=turn,
                 own=religion_beliefs.project_snapshot(raw['own'], pid, turn, observation=observation))
    state[subfield] = raw[subfield]
    return raw, contract.validate(state, pid, turn, observation=observation)


def read_all(saved, observation, fields, *, available):
    if not available:
        return dict.fromkeys(fields)
    return {field: (religious_units.borrowed_catalogue(saved, observation) if field == _UNIT_FIELD
                    else _read(saved, observation, field)[1]) for field in fields}


def apply(saved, action, observation, *, published, fields, available):
    field = FIELDS[action['kind']]
    refused = dict(status='refused', requested_action=action)
    if not available or field not in fields or published is None:
        return dict(refused, reason='native_religion_acting_boundary_unavailable'), None
    pid, turn = observation['player_id'], observation['turn']
    contract = network_turn.SECONDARY_RELIGION_CONTRACTS[field]
    contract.validate(published, pid, turn)
    if action not in contract.actions(published):
        raise ValueError('Borrowed religious action lacks its published offer')
    token = saved.continuation
    publications = token.publication_count
    if field == _UNIT_FIELD:
        result = religious_units.apply(saved, action, observation, borrowed_offer=published)
        if result['status'] == 'refused':
            return dict(refused, reason=result['refusal_code']), None
        status, reason = result['status'], result.get('refusal_code')
        if (status, reason) not in (('completed', None), ('submitted', religious_units.UNCONFIRMED)):
            raise RuntimeError('Unknown borrowed religious unit result')
        return _finish(saved, action, observation, result['observation'], publications, status=status, reason=reason)
    raw, fresh = _read(saved, observation, field)
    if action not in contract.actions(fresh):
        return dict(refused, reason='native_religion_offer_changed'), None
    _, source, _, command = _READERS[field]
    prefix = saved.prefix
    source.bind_prefix(prefix, action=True)
    try:
        after = command(saved, prefix, action, turn, observation, player_id=pid,
                        core_sha256=XP2_CORE_SHA256, borrowed_offer=raw)
    except NativeProphetRefused:
        return dict(refused, reason='native_prophet_can_start_false'), None
    return _finish(saved, action, observation, after, publications)


def _finish(saved, action, before, after, publications, *, status='completed', reason=None):
    token = saved.continuation
    if token.publication_count != publications + 1:
        raise RuntimeError('Borrowed religious request did not publish its native effect')
    feedback = token.trade_feedback
    if feedback is not None and feedback.events:
        delivered = token.flush_trade_feedback()
        if delivered:
            saved.emit('xp2_bbg_trade_gameplay_delivered', feedback=delivered)
        from .native.native_player_observation import observe_player

        after = observe_player(prefix.runtime, prefix.ui_child, before['player_id'])
    return dict(status=status, reason=reason, requested_action=action), after
