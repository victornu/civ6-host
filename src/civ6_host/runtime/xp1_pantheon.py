"""Compose the shared pantheon family on the actual installed XP1 owner.

Catalogue is the existing native format. Session admission/versioning remains
with the caller; an unqualified action graph never becomes an empty catalogue.
"""
from copy import deepcopy
from civ6_host.contracts import pantheon
from .configuration_profiles import XP2_CORE_SHA256
from . import xp1_pantheon_source as source
from .native import native_saved_pantheon as shared

source_for = source.source_for
supports = source.supports
source_dependencies = source.source_dependencies
require_actions = source.require_actions


def read_pantheon_index(saved, observation):
    saved._check_query()
    prefix = saved.prefix
    core_sha256 = source.core_for(prefix)
    if core_sha256 != XP2_CORE_SHA256:
        raise ValueError('Direct pantheon index reader requires the selected Gathering Storm image')
    source.bind_prefix(prefix)
    return _index(prefix, observation)


def _index(prefix, observation):
    pid,turn = _identity(observation)
    wire = prefix.runtime.evaluate_text(prefix.ui_child,
        shared.native.index_source(pid,turn,core_sha256=XP2_CORE_SHA256),b'@explicit_pantheon_index',capacity=128)
    return shared.native.parse_index(wire,pid,turn)


def catalogue(saved, observation):
    saved._check_query()
    source.bind_prefix(saved.prefix)
    pid, turn = _identity(observation)
    value = shared.catalog(saved.prefix, turn, player_id=pid, core_sha256=source.core_for(saved.prefix))
    saved.explicit_pantheon = deepcopy(value)
    return value


def _identity(observation):
    if type(observation) is not dict:
        raise ValueError('Pantheon requires the public actor observation')
    pid, turn = observation.get('player_id'), observation.get('turn')
    if type(pid) is not int or not 0 <= pid < 64 or type(turn) is not int or turn < 0:
        raise ValueError('Pantheon actor identity differs')
    return pid, turn


def actions(value):
    return shared.actions(value)


def borrowed_enabled(saved, requested=None):
    enabled = getattr(saved, 'xp2_pantheon', False) is True
    if requested is None:
        return enabled
    if type(requested) is not bool or requested and not enabled:
        raise ValueError('Borrowed pantheon requires its admitted Gathering Storm option')
    return requested


def borrowed_state(saved, observation):
    from .xp1_session_view import _borrowed_xp2_reference

    pid, turn = _identity(observation)
    _borrowed_xp2_reference(saved, pid)
    prefix = saved.prefix
    source.bind_prefix(prefix)
    raw = shared.catalog(prefix, turn, player_id=pid, core_sha256=XP2_CORE_SHA256)
    return pantheon.validate_state(dict(schema=pantheon.STATE_SCHEMA, player_id=pid, turn=turn,
        pantheon_index=_index(prefix, observation), catalogue=raw), pid, turn)


def apply(saved, action, before, *, borrowed_catalogue=None):
    saved._check_active()
    source.bind_prefix(saved.prefix, action=True)
    pid, turn = _identity(before)
    try:
        after = shared.apply(saved, saved.prefix, action, turn, before,
            player_id=pid, core_sha256=source.core_for(saved.prefix), borrowed_catalogue=borrowed_catalogue)
    except shared.StaleBorrowedPantheon:
        return dict(status='refused', observation=deepcopy(before), refusal_code='native_pantheon_offer_changed',
                    source_sha256=source.source_hash(XP2_CORE_SHA256))
    except shared.NativePantheonRefused as refusal:
        return dict(status='refused', observation=deepcopy(before),
            refusal_code='native_pantheon_can_start_false', request=refusal.request,
            source_sha256=source.source_hash(source.core_for(saved.prefix)))
    return dict(status='completed', observation=after, selected_index=action['index'],
        selected_hash=action['hash'], source_sha256=source.source_hash(source.core_for(saved.prefix)))


def apply_borrowed(saved, action, before, *, expected, available):
    if not available or expected is None:
        return dict(status='refused', reason='native_pantheon_acting_boundary_unavailable',
                    requested_action=action), None
    pid, turn = _identity(before)
    pantheon.validate_state(expected, pid, turn)
    token = saved.continuation
    publications = token.publication_count
    result = apply(saved, action, before, borrowed_catalogue=expected['catalogue'])
    if result['status'] == 'refused':
        return dict(status='refused', reason=result['refusal_code'], requested_action=action), None
    if (result['status'] != 'completed' or result['selected_index'] != action['index']
            or result['selected_hash'] != action['hash'] or token.publication_count != publications + 1):
        raise RuntimeError('Borrowed pantheon request lacks its selected native effect')
    after = result['observation']
    feedback = token.trade_feedback
    if feedback is not None and feedback.events:
        delivered = token.flush_trade_feedback()
        if delivered:
            saved.emit('xp2_bbg_trade_gameplay_delivered', feedback=delivered)
        prefix = saved.prefix
        from .native.native_player_observation import observe_player

        after = observe_player(prefix.runtime, prefix.ui_child, pid)
    return dict(status='completed', reason=None, requested_action=action), after
