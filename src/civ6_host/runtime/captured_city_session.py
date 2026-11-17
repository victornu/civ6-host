"""Shared occupation query and command on the retained saved-game owner."""

from copy import deepcopy
from types import SimpleNamespace

from civ6_host.contracts import captured_city
from civ6_host.contracts.network_turn import is_waiting


BINDINGS = frozenset((
    'City.CanRaze', 'City.GetJustConqueredFrom', 'City.GetOriginalOwner',
    'City.GetOwnerBeforeOccupation', 'CityManager.CanStartCommand',
    'CityManager.RequestCommand', 'Diplomacy.CanLiberateCityTo',
    'PlayerCities.GetNextCapturedCity',
))

def verify_source(execution_image):
    from .execution_images import _XP1_PROFILE

    if execution_image is _XP1_PROFILE:
        from . import xp1_captured_city as profile
    else:
        from . import xp2_captured_city as profile
    profile.source(execution_image)
    return profile.SOURCE[1]


def read(saved, observation, *, controls, actions_closed):
    from .native import native_saved_captured_city as native

    c = saved.continuation
    c.explicit_captured_city = None
    if actions_closed or is_waiting(controls) or getattr(c, 'captured_city_core', None) is None:
        return None
    core = saved.backend.core
    if c.captured_city_core is not core or observation != c.observation:
        raise ValueError('Captured-city query lost its retained Core or observation')
    value = native.catalog(c.prefix, observation['turn'], player_id=observation['player_id'],
                           execution_image=core._civ6_host_execution_image)
    public = captured_city.project_public(value, observation=observation)
    c.explicit_captured_city = deepcopy(value)
    return public


def apply(saved, action, before):
    from .native import native_saved_captured_city as native

    c = saved.continuation
    c.check(active=True)
    core = saved.backend.core
    if (getattr(c, 'captured_city_core', None) is not core
            or before != c.observation or c.explicit_captured_city is None):
        raise ValueError('Captured-city choice lacks its retained Core and catalogue')
    c.transport.require_empty_native_queue()
    after = native.apply(c, c.prefix, action, before['turn'], before,
                         player_id=before['player_id'], execution_image=core._civ6_host_execution_image)
    c.transport.require_empty_native_queue()
    c.explicit_captured_city = None
    return dict(status='completed', observation=after, action=deepcopy(action))


def borrowed_enabled(saved):
    return getattr(saved, '_xp2_lan_occupation_enabled', False) is True


def _borrowed_core(saved, player_id):
    from .xp1_session_view import _borrowed_xp2_reference

    _borrowed_xp2_reference(saved, player_id)
    core = saved.backend.core
    if getattr(saved.continuation, 'captured_city_core', None) is not core:
        raise ValueError('Borrowed city choice lacks its admitted Gathering Storm core')
    return core._civ6_host_execution_image


def borrowed_snapshot(saved, observation, state):
    from .native import native_saved_captured_city as native

    if not borrowed_enabled(saved):
        return None
    pid, turn = observation['player_id'], observation['turn']
    controls = next(row for row in state['rows'] if row['player_id'] == pid)
    if is_waiting(controls):
        return None
    image = _borrowed_core(saved, pid)
    transport = saved.continuation.transport
    transport.require_empty_native_queue()
    saved.backend.control(empty=True)
    raw = native.catalog(saved.prefix, turn, player_id=pid, execution_image=image)
    public = captured_city.project_public(raw, observation=observation)
    transport.require_empty_native_queue()
    saved.backend.control(empty=True)
    return raw, public


def apply_borrowed(saved, action, observation, occupation, *, expected):
    from .native import native_saved_captured_city as native

    refusal = dict(status='refused', requested_action=action)
    if occupation is None or action not in captured_city.public_actions(occupation[1]):
        return dict(refusal, reason='native_captured_city_unavailable'), None
    raw, public = occupation
    if public != expected:
        return dict(refusal, reason='native_captured_city_state_changed'), None

    pid, turn = observation['player_id'], observation['turn']
    image = _borrowed_core(saved, pid)
    token, prefix = saved.continuation, saved.prefix
    count = token.publication_count
    receipts = []

    def emit(stage, **data):
        if stage != 'official_explicit_captured_city_effect' or receipts:
            raise RuntimeError('Unexpected borrowed captured-city receipt')
        receipts.append(data)
        saved.emit(stage, **data)

    owner = SimpleNamespace(explicit_captured_city=raw, emit=emit)
    token.transport.require_empty_native_queue()
    after = native.apply(owner, prefix, action, turn, observation, player_id=pid, execution_image=image)
    if len(receipts) != 1:
        raise RuntimeError('Borrowed captured-city receipt is missing')
    receipt = receipts[0]
    if (receipt['action'] != action or receipt['catalog_before'] != raw
            or receipt['observation_before'] != observation or receipt['observation_after'] != after
            or receipt['choice_no_longer_pending'] is not True
            or receipt['automatic_choices_applied'] is not False
            or receipt['verified_liberation_recipient'] != public['city']['liberation_recipients'].get(action['directive'])
            or token.publication_count != count + 1):
        raise RuntimeError('Borrowed captured-city effect differs from the native choice')
    feedback = token.trade_feedback
    if feedback is not None and feedback.events:
        delivered = token.flush_trade_feedback()
        if delivered:
            saved.emit('xp2_bbg_trade_gameplay_delivered', feedback=delivered)
        from .native.native_player_observation import observe_player

        after = observe_player(prefix.runtime, prefix.ui_child, pid)
    token.transport.require_empty_native_queue()
    return dict(status='completed', reason=None, requested_action=action), after
