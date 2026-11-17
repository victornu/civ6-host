"""City focus and citizen management for a borrowed Gathering Storm seat."""

from functools import partial
from struct import pack
from types import SimpleNamespace

from civ6_host.contracts.capability_city_controls import ACTION_FIELDS, validate_action

from . import expansion_city_controls
from .configuration_profiles import XP2_CORE_SHA256


CATALOGUE_FIELDS = {'city_focus': 'city_focus_catalogs', 'city_citizen': 'citizen_catalogs'}
_MESSAGE = 0x346b0a13


def require_archive(archive, player_id, action, *, focus_request=None):
    validate_action(action)
    header = (_MESSAGE, player_id, 2, action['city_id'])
    if action['kind'] == 'city_focus':
        flags, enabled = focus_request
        yield_index = action['yield_index']
        expected = pack('<IHH7IB', *header, 2, flags, 1, 0, flags, yield_index, enabled)
    else:
        expected = pack('<IHH8I', *header, 3, 0, 1, 0, 5, action['x'], action['y'])
    if type(archive) is not bytes or archive != expected:
        raise RuntimeError('Borrowed city-control archive differs from its player, city or parameters')


def enabled(saved):
    return getattr(saved, '_expansion_city_controls_requested', (False, False))[0]


def read(saved, observation):
    if not enabled(saved):
        return None
    from .xp1_session_view import _borrowed_xp2_reference

    _borrowed_xp2_reference(saved, observation['player_id'])
    b, t, p, _, flags = expansion_city_controls._check(saved, active=True)
    t.transport.require_empty_native_queue()
    b.control(empty=True)
    result = expansion_city_controls.query_native_catalogues(
        p, observation, management=flags[1], core_sha256=XP2_CORE_SHA256)
    t.transport.require_empty_native_queue()
    b.control(empty=True)
    return result


def apply(saved, action, observation, state, *, expected_city):
    from .native import native_saved_city_focus1000 as focus, native_saved_citizens as citizens

    kind = action['kind']
    if state is None or action not in state[2][kind]:
        return dict(status='refused', reason='native_city_control_unavailable',
                    requested_action=action), None
    is_focus = kind == 'city_focus'
    cities = state[0] if is_focus else state[1]
    city = next(row for row in cities if row['city_id'] == action['city_id'])
    if city != expected_city:
        return dict(status='refused', reason='native_city_control_state_changed',
                    requested_action=action), None
    module = focus if is_focus else citizens
    expected_stage = ('official_explicit_city_focus_effect1000' if is_focus
                      else 'official_explicit_city_citizen_effect')
    state_key = 'focus' if is_focus else 'citizens'
    requests = focus.transition(action)[0] if is_focus else (None,)
    pid, turn = observation['player_id'], observation['turn']
    validators = tuple(partial(require_archive, player_id=pid, action=action, focus_request=request)
                       for request in requests)
    reports = []
    continuation = saved.continuation
    count = continuation.publication_count

    def emit(stage, **payload):
        if stage != expected_stage or reports:
            raise RuntimeError('Unexpected borrowed city-control receipt')
        reports.append(payload)
        saved.emit(stage, **payload)

    with continuation.transport.require_xp2_archives(validators):
        after = module.apply(SimpleNamespace(emit=emit), saved.prefix, action, turn, observation,
            player_id=pid, diagnostic_ui_enabled=True, core_sha256=XP2_CORE_SHA256)
    if len(reports) != 1:
        raise RuntimeError('Borrowed city control did not yield a native receipt')
    report = reports[0]
    if (report['action'] != action or report['observation_before'] != observation
            or report['observation_after'] != after or report[state_key + '_before'] != city
            or report['automatic_choices_applied'] is not False
            or continuation.publication_count != count + 1):
        raise RuntimeError('Borrowed city-control observation or publication differs')
    changed = city != report[state_key + '_after']
    return dict(status='completed' if changed else 'submitted',
                reason=None if changed else 'native_city_control_state_unchanged',
                requested_action=action), after
