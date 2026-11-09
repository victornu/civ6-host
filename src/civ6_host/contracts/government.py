"""Pure validation and projection of the XP2 government-choice query."""

_CATALOGUE_FIELDS = {
    'player_id', 'turn', 'current_index', 'can_change', 'changed',
    'civic_completed', 'considered', 'consideration_blocker', 'choices',
}
_CHOICE_FIELDS = {'index', 'hash', 'unlocked', 'can_change', 'anarchy_turns'}
_MAX_INDEX = 0x7fffffff
_MAX_HASH = 0xffffffff
_MAX_ANARCHY = 100000


def validate_catalogue(value, player_id, turn):
    """Validate the exact public projection returned by the native query."""
    if (type(player_id) is not int or not 0 <= player_id <= 63
            or type(turn) is not int or not 0 <= turn <= _MAX_HASH
            or type(value) is not dict or set(value) != _CATALOGUE_FIELDS
            or type(value['player_id']) is not int or value['player_id'] != player_id
            or type(value['turn']) is not int or value['turn'] != turn):
        raise ValueError('Foreign or malformed government catalogue')
    for field in ('can_change', 'changed', 'civic_completed', 'considered', 'consideration_blocker'):
        if type(value[field]) is not bool:
            raise ValueError('Malformed government query flag')
    current = value['current_index']
    choices = value['choices']
    if (type(current) is not int or not -1 <= current <= _MAX_INDEX
            or type(choices) is not list or not 1 <= len(choices) <= 256):
        raise ValueError('Malformed government index or choice list')
    prior_index = -1
    indices = set()
    for row in choices:
        if type(row) is not dict or set(row) != _CHOICE_FIELDS:
            raise ValueError('Unexpected government choice fields')
        index, hash_value = row['index'], row['hash']
        if (type(index) is not int or not 0 <= index <= _MAX_INDEX
                or index <= prior_index
                or type(hash_value) is not int or not 0 <= hash_value <= _MAX_HASH
                or hash_value in indices
                or type(row['unlocked']) is not bool
                or type(row['can_change']) is not bool
                or type(row['anarchy_turns']) is not int
                or not 0 <= row['anarchy_turns'] <= _MAX_ANARCHY):
            raise ValueError('Malformed or unordered government choice')
        prior_index = index
        indices.add(hash_value)
    if current != -1 and current not in {row['index'] for row in choices}:
        raise ValueError('Current government is absent from its choices')
    return value


def actions(value):
    """Rebuild direct non-anarchy government offers and explicit retention."""
    if value is None:
        return []
    result = []
    if (value['can_change'] and not value['changed']
            and (value['current_index'] == -1 or value['civic_completed'])):
        result.extend(dict(kind='government', index=row['index'], hash=row['hash'])
                      for row in value['choices']
                      if row['unlocked'] and row['can_change']
                      and row['index'] != value['current_index']
                      and row['anarchy_turns'] == 0)
    if (value['consideration_blocker'] and not value['considered']
            and value['current_index'] >= 0):
        result.append(dict(kind='retain_government', index=value['current_index']))
    return result


def validate_action(value):
    kind=value.get('kind') if type(value) is dict else None
    if kind not in ('government','retain_government'):
        raise ValueError('Unexpected government action')
    expected={'kind','index'} | ({'hash'} if kind=='government' else set())
    if (set(value)!=expected or type(value['index']) is not int
            or not 0 <= value['index'] <= _MAX_INDEX
            or kind=='government' and (type(value['hash']) is not int
                                      or not 0 <= value['hash'] <= _MAX_HASH)):
        raise ValueError('Malformed government action')
    return value
