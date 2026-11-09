"""Pure public contract for paid policy unlocks."""

_FIELDS = {'player_id', 'turn', 'cost', 'currency', 'reason', 'can_unlock'}
_CURRENCIES = {'YIELD_GOLD', 'YIELD_FAITH'}
_REASONS = {'available', 'already_changed', 'no_cost', 'insufficient_funds',
            'native_unavailable'}
_INT_MAX = 0x7fffffff


def validate(value, pid, turn):
    """Validate one source-qualified policy-unlock catalogue."""
    if (type(pid) is not int or not 0 <= pid <= 63
            or type(turn) is not int or not 0 <= turn <= 0xffffffff
            or type(value) is not dict or set(value) != _FIELDS):
        raise ValueError('Foreign or malformed policy unlock catalogue')
    if (type(value['player_id']) is not int or value['player_id'] != pid
            or type(value['turn']) is not int or value['turn'] != turn
            or type(value['cost']) is not int or not 0 <= value['cost'] <= _INT_MAX
            or type(value['currency']) is not str or value['currency'] not in _CURRENCIES
            or type(value['reason']) is not str or value['reason'] not in _REASONS
            or type(value['can_unlock']) is not bool):
        raise ValueError('Malformed policy unlock catalogue fields')
    reason, cost, can_unlock = value['reason'], value['cost'], value['can_unlock']
    if (can_unlock != (reason == 'available')
            or reason == 'available' and cost == 0
            or reason == 'no_cost' and cost != 0
            or reason == 'insufficient_funds' and cost == 0):
        raise ValueError('Policy unlock catalogue contradicts its status')
    return value


def actions(value):
    """Project an available paid unlock into its sole supported action."""
    if value is None:
        return []
    if type(value) is not dict or set(value) != _FIELDS:
        raise ValueError('Malformed policy unlock catalogue')
    validate(value, value['player_id'], value['turn'])
    if value['reason'] != 'available' or value['can_unlock'] is not True:
        return []
    return [dict(kind='policy_unlock', cost=value['cost'], currency=value['currency'])]


def validate_action(action):
    """Validate the closed action envelope for a paid policy unlock."""
    if (type(action) is not dict or set(action) != {'kind', 'cost', 'currency'}
            or action['kind'] != 'policy_unlock'
            or type(action['cost']) is not int or not 1 <= action['cost'] <= _INT_MAX
            or type(action['currency']) is not str or action['currency'] not in _CURRENCIES):
        raise ValueError('Malformed policy unlock action')
    return action
