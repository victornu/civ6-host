"""Portable player-scoped query and explicit native envoy choices.

The native producer filters known living city-states. This validator cannot
reconstruct that visibility or calculate influence bonuses from a catalogue.
"""
ACTION_FIELDS = {
    'send_envoy': frozenset(('kind', 'target_player_id')),
    'retain_envoys': frozenset(('kind',)),
}
FIELDS = {'player_id', 'current_game_turn', 'tokens_to_give', 'can_give_influence',
          'considered', 'giving_tokens_blocker_present', 'targets'}


def _int(value, maximum):
    return type(value) is int and 0 <= value <= maximum


def validate_catalogue(value, player_id, turn):
    if (not _int(player_id, 63) or not _int(turn, 0x7fffffff)
            or type(value) is not dict or set(value) != FIELDS
            or type(value['player_id']) is not int or value['player_id'] != player_id
            or type(value['current_game_turn']) is not int or value['current_game_turn'] != turn
            or not _int(value['tokens_to_give'], 0x7fffffff)
            or any(type(value[k]) is not bool for k in
                   ('can_give_influence', 'considered', 'giving_tokens_blocker_present'))
            or type(value['targets']) is not list or len(value['targets']) > 64):
        raise ValueError('Malformed or foreign envoy catalogue')
    seen = set()
    for row in value['targets']:
        if (type(row) is not dict or set(row) != {'target_player_id', 'can_give', 'tokens_received'}
                or not _int(row['target_player_id'], 63) or row['target_player_id'] == player_id
                or row['target_player_id'] in seen or type(row['can_give']) is not bool
                or not _int(row['tokens_received'], 0x7fffffff)):
            raise ValueError('Malformed or duplicate public envoy target')
        seen.add(row['target_player_id'])
    return value


def actions(value):
    if value is None:
        return []
    validate_catalogue(value, value['player_id'], value['current_game_turn'])
    result = []
    if value['can_give_influence'] and value['tokens_to_give'] > 0:
        result.extend(dict(kind='send_envoy', target_player_id=row['target_player_id'])
                      for row in value['targets'] if row['can_give'])
    if not value['considered'] and value['giving_tokens_blocker_present']:
        result.append(dict(kind='retain_envoys'))
    return result


def validate_action(value):
    if (type(value) is not dict or type(value.get('kind')) is not str
            or value['kind'] not in ACTION_FIELDS or set(value) != ACTION_FIELDS[value['kind']]
            or value['kind'] == 'send_envoy' and not _int(value['target_player_id'], 63)):
        raise ValueError('Malformed explicit envoy action')
    return value
