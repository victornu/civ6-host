"""City-center and district shots on the secondary Gathering Storm perspective."""

from functools import partial
from struct import pack

from civ6_host.contracts import city_ranged
from .configuration_profiles import XP2_CORE_SHA256


FIELDS = {'city_range_attack': 'city_shots', 'district_range_attack': 'district_shots'}


def enabled(saved):
    return getattr(saved, '_xp2_lan_ranged_shots_enabled', False) is True


def require_archive(payload, player_id, action):
    city_ranged.uint(player_id, 'player', 63)
    if action['kind'] == 'city_range_attack':
        city_ranged.city_validate_action(action)
        type_id, object_id = 2, action['city_id']
    else:
        city_ranged.district_validate_action(action)
        type_id, object_id = 3, action['district_id']
    expected = pack('<IHH7I', 0x346b0a13, player_id, type_id, object_id,
                    1, 0, 1, 0, action['x'], action['y'])
    if type(payload) is not bytes or payload != expected:
        raise ValueError('Borrowed ranged archive differs from actor, shooter or destination')


def read(saved, observation, *, strategic_allowed):
    from .native import native_saved_city_shot as city, native_saved_district_shot as district
    from .xp1_session_view import _borrowed_xp2_reference

    if not enabled(saved) or not strategic_allowed:
        return {}
    pid, turn = observation['player_id'], observation['turn']
    _borrowed_xp2_reference(saved, pid)
    token = saved.continuation
    token.transport.require_empty_native_queue()
    result = {}
    for kind, codec in (('city_range_attack', city), ('district_range_attack', district)):
        shots = codec.catalog(saved.prefix, turn, player_id=pid)
        codec.compare_own_cities(shots, observation)
        result[kind] = shots
    token.transport.require_empty_native_queue()
    return result


def apply(saved, action, observation, snapshots, *, expected):
    from .native import native_saved_city_shot as city, native_saved_district_shot as district
    from .native import native_saved_city_targets as defenses
    from .xp1_session_view import _borrowed_xp2_reference

    kind = action['kind']
    state = snapshots.get(kind)
    is_city = kind == 'city_range_attack'
    codec = city if is_city else district
    shooter = 'city' if is_city else 'district'
    refused = dict(status='refused', requested_action=action)
    if state is None or action not in codec.actions(state):
        return dict(refused, reason='native_' + shooter + '_shot_unavailable'), None
    if state != expected:
        return dict(refused, reason='native_' + shooter + '_shot_state_changed'), None

    pid, turn = observation['player_id'], observation['turn']
    _borrowed_xp2_reference(saved, pid)
    token, prefix = saved.continuation, saved.prefix
    old_defenses = defenses.catalog(prefix, turn, player_id=pid, collect=False,
                                    core_sha256=XP2_CORE_SHA256)['cities']
    count = token.publication_count
    with token.transport.require_xp2_single_archive(partial(require_archive, player_id=pid, action=action)):
        after = city.execute(saved, prefix, action, turn, observation, player_id=pid,
            expected_catalogue=state, expected_defenses=old_defenses, validate=codec.validate_action,
            read_catalogue=codec.catalog, compare=codec.compare_own_cities, offers=codec.actions,
            request=codec.request_source, verify_effect=codec.effect, shooter=shooter,
            proof_sha=codec.PROOF_SHA, defense_core_sha256=XP2_CORE_SHA256)
    if token.publication_count != count + 1:
        raise RuntimeError('Borrowed ranged shot crossed its native publication boundary')
    feedback = token.trade_feedback
    if feedback is not None and feedback.events:
        delivered = token.flush_trade_feedback()
        if delivered:
            saved.emit('xp2_bbg_trade_gameplay_delivered', feedback=delivered)
        from .native.native_player_observation import observe_player

        after = observe_player(prefix.runtime, prefix.ui_child, pid)
    token.transport.require_empty_native_queue()
    return dict(status='completed', reason=None, requested_action=action), after
