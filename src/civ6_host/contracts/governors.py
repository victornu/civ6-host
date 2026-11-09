"""Portable validation and action projection for governor choices."""

_MAX_I32 = 0x7fffffff
_MIN_I32 = -0x80000000
_MAX_U32 = 0xffffffff
_CATALOGUE_FIELDS = {
    'player_id', 'current_game_turn', 'points_obtained', 'points_spent',
    'can_appoint', 'titles_considered', 'governors',
}
_GOVERNOR_FIELDS = {
    'index', 'hash', 'appointed', 'can_ever_appoint', 'can_promote',
    'assignment_open', 'turns_to_establish', 'status', 'promotions',
    'assignment_targets',
}
_STATUS_FIELDS = {
    'neutralized_turns', 'established', 'turns_to_establish',
    'turns_on_site', 'assigned_city', 'govern_city_state',
    'can_assign_to_major_civ',
}
_CITY_FIELDS = {'owner', 'city_id'}
_PROMOTION_FIELDS = {
    'index', 'hash', 'owned', 'can_earn', 'hidden', 'base_ability', 'level',
}
_TARGET_FIELDS = {'owner', 'city_id', 'can_assign'}
ACTION_FIELDS = {
    'appoint_governor': {
        'kind', 'governor_index', 'governor_hash',
    },
    'promote_governor': {
        'kind', 'governor_index', 'governor_hash',
        'promotion_index', 'promotion_hash',
    },
    'assign_governor': {
        'kind', 'governor_index', 'governor_hash', 'city_owner', 'city_id',
    },
    'consider_governor_titles': {'kind'},
}


def _is_int32(value):
    return type(value) is int and _MIN_I32 <= value <= _MAX_I32


def _is_nonnegative_int32(value):
    return type(value) is int and 0 <= value <= _MAX_I32


def _is_hash(value):
    return type(value) is int and 0 <= value <= _MAX_U32


def _is_player_id(value):
    return type(value) is int and 0 <= value <= 63


def _require_bool(value):
    return type(value) is bool


def _validate_city(value):
    if (type(value) is not dict or set(value) != _CITY_FIELDS
            or not _is_player_id(value['owner'])
            or not _is_nonnegative_int32(value['city_id'])):
        raise ValueError('Malformed governor city identity')


def validate_catalogue(value, player_id, turn):
    """Validate exact public catalogue shape and its player/turn provenance."""
    if (not _is_player_id(player_id) or not _is_nonnegative_int32(turn)
            or type(value) is not dict or set(value) != _CATALOGUE_FIELDS
            or type(value['player_id']) is not int or value['player_id'] != player_id
            or type(value['current_game_turn']) is not int or value['current_game_turn'] != turn
            or not _is_int32(value['points_obtained'])
            or not _is_int32(value['points_spent'])
            or not _require_bool(value['can_appoint'])
            or not _require_bool(value['titles_considered'])
            or type(value['governors']) is not list):
        raise ValueError('Foreign or malformed governor catalogue')

    seen_governor_indices = set()
    seen_governor_hashes = set()
    for governor in value['governors']:
        if (type(governor) is not dict or set(governor) != _GOVERNOR_FIELDS
                or not _is_nonnegative_int32(governor['index'])
                or not _is_hash(governor['hash'])
                or governor['index'] in seen_governor_indices
                or governor['hash'] in seen_governor_hashes
                or not _require_bool(governor['appointed'])
                or not _require_bool(governor['can_ever_appoint'])
                or not _require_bool(governor['can_promote'])
                or not _require_bool(governor['assignment_open'])
                or not _is_int32(governor['turns_to_establish'])
                or type(governor['promotions']) is not list
                or type(governor['assignment_targets']) is not list):
            raise ValueError('Malformed or duplicate governor identity/state')
        seen_governor_indices.add(governor['index'])
        seen_governor_hashes.add(governor['hash'])

        status = governor['status']
        if governor['appointed'] != (status is not None):
            raise ValueError('Governor appointment and status disagree')
        if status is not None:
            if (type(status) is not dict or set(status) != _STATUS_FIELDS
                    or any(not _is_int32(status[key]) for key in
                           ('neutralized_turns', 'turns_to_establish', 'turns_on_site'))
                    or not _require_bool(status['established'])
                    or not _require_bool(status['govern_city_state'])
                    or not _require_bool(status['can_assign_to_major_civ'])):
                raise ValueError('Malformed governor status')
            if status['assigned_city'] is not None:
                _validate_city(status['assigned_city'])

        seen_promotion_indices = set()
        seen_promotion_hashes = set()
        for promotion in governor['promotions']:
            if (type(promotion) is not dict or set(promotion) != _PROMOTION_FIELDS
                    or not _is_nonnegative_int32(promotion['index'])
                    or not _is_hash(promotion['hash'])
                    or promotion['index'] in seen_promotion_indices
                    or promotion['hash'] in seen_promotion_hashes
                    or any(not _require_bool(promotion[key]) for key in
                           ('owned', 'can_earn', 'hidden', 'base_ability'))
                    or not _is_int32(promotion['level'])):
                raise ValueError('Malformed or duplicate governor promotion')
            seen_promotion_indices.add(promotion['index'])
            seen_promotion_hashes.add(promotion['hash'])

        seen_targets = set()
        for target in governor['assignment_targets']:
            if (type(target) is not dict or set(target) != _TARGET_FIELDS
                    or not _is_player_id(target['owner'])
                    or not _is_nonnegative_int32(target['city_id'])
                    or not _require_bool(target['can_assign'])):
                raise ValueError('Malformed governor assignment target')
            identity = (target['owner'], target['city_id'])
            if identity in seen_targets:
                raise ValueError('Duplicate governor assignment target')
            seen_targets.add(identity)
    return value


def actions(value):
    """Project every offered governor action, preserving catalogue order."""
    if value is None:
        return []
    if type(value) is not dict:
        raise ValueError('Malformed governor catalogue')
    validate_catalogue(value, value['player_id'], value['current_game_turn'])
    result = []
    for governor in value['governors']:
        index, hash_value = governor['index'], governor['hash']
        if (not governor['appointed'] and governor['can_ever_appoint']
                and value['can_appoint']):
            result.append(dict(kind='appoint_governor', governor_index=index,
                               governor_hash=hash_value))
        for promotion in governor['promotions']:
            if (promotion['can_earn'] and not promotion['owned']
                    and not promotion['base_ability'] and promotion['level'] != 0):
                result.append(dict(kind='promote_governor', governor_index=index,
                                   governor_hash=hash_value,
                                   promotion_index=promotion['index'],
                                   promotion_hash=promotion['hash']))
        if governor['assignment_open']:
            result.extend(dict(kind='assign_governor', governor_index=index,
                               governor_hash=hash_value, city_owner=target['owner'],
                               city_id=target['city_id'])
                          for target in governor['assignment_targets']
                          if target['can_assign'])
    if not value['titles_considered']:
        result.append(dict(kind='consider_governor_titles'))
    return result


def validate_action(value):
    """Validate an explicit governor action envelope without consulting game rules."""
    kind = value.get('kind') if type(value) is dict else None
    if (type(kind) is not str or kind not in ACTION_FIELDS
            or set(value) != ACTION_FIELDS[kind]):
        raise ValueError('Malformed explicit governor action')
    if kind == 'consider_governor_titles':
        return value
    if (not _is_nonnegative_int32(value['governor_index'])
            or not _is_hash(value['governor_hash'])):
        raise ValueError('Malformed governor action identity')
    if kind == 'promote_governor':
        if (not _is_nonnegative_int32(value['promotion_index'])
                or not _is_hash(value['promotion_hash'])):
            raise ValueError('Malformed governor promotion identity')
    elif kind == 'assign_governor':
        if (not _is_player_id(value['city_owner'])
                or not _is_nonnegative_int32(value['city_id'])):
            raise ValueError('Malformed governor city target')
    return value
