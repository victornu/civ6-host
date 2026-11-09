"""Pure policy catalog and explicit-assignment contracts for capability decisions."""
from . import policies


def validate_catalogue(value, player_id, turn, *, allow_relocation=False):
    """Validate the native parser's public result without inferring game rules."""
    if (type(player_id) is not int or not 0 <= player_id <= 63
            or type(turn) is not int or not 0 <= turn <= 0xffffffff
            or type(value) is not dict or set(value) != {'player_id', 'turn', 'reason', 'slots'}
            or type(value.get('player_id')) is not int or value['player_id'] != player_id
            or type(value.get('turn')) is not int or value['turn'] != turn
            or type(value.get('reason')) is not str
            or value['reason'] not in ('available', 'no_policy_slots', 'already_changed',
                                       'not_free', 'window_closed')):
        raise ValueError('Foreign or malformed policy catalogue')
    slots = policies.validate_slots(value['slots'], allow_relocation=allow_relocation)
    if ((value['reason'] == 'no_policy_slots') != (len(slots) == 0)
            or (value['reason'] != 'available' and any(row['options'] for row in slots))):
        raise ValueError('Policy catalogue contradicts its window')
    return value


def actions(catalogue, *, allow_relocation=False, allow_unchanged=False):
    """Rebuild the only candidate action permitted by a queried catalog."""
    if (catalogue is None or catalogue['reason'] != 'available'
            or not policies.can_change(catalogue['slots'], allow_relocation=allow_relocation,
                                       allow_unchanged=allow_unchanged)):
        return []
    return [dict(kind='policies', slots=catalogue['slots'])]


def validate_explicit_action(action, player_id=None, turn=None):
    """Validate the resolved client action envelope for session command paths."""
    if type(action) is not dict or set(action) != {'kind', 'candidate'} or action['kind'] != 'policies':
        raise ValueError('Malformed explicit policy action')
    candidate = action['candidate']
    fields = {'status', 'player_id', 'turn', 'slot_count', 'assignments'}
    if type(candidate) is not dict or not fields <= set(candidate) or set(candidate) - (fields | {'prior_indices'}):
        raise ValueError('Malformed explicit policy candidate')
    pid, seen_turn = candidate['player_id'], candidate['turn']
    if (type(pid) is not int or not 0 <= pid <= 63
            or player_id is not None and (type(player_id) is not int or pid != player_id)
            or type(seen_turn) is not int or not 0 <= seen_turn <= 0xffffffff
            or turn is not None and (type(turn) is not int or seen_turn != turn)
            or candidate['status'] != 'candidate'
            or type(candidate['slot_count']) is not int or not 1 <= candidate['slot_count'] <= 64
            or type(candidate['assignments']) is not list
            or len(candidate['assignments']) != candidate['slot_count']):
        raise ValueError('Malformed explicit policy candidate boundary')
    assignments = candidate['assignments']
    if any(type(pair) is not list or len(pair) != 2 or type(pair[0]) is not int
           or pair[0] != i or type(pair[1]) is not int
           or not -0x80000000 <= pair[1] <= 0xffffffff
           for i, pair in enumerate(assignments)):
        raise ValueError('Malformed explicit policy assignments')
    hashes = [pair[1] & 0xffffffff for pair in assignments]
    if len(set(hashes)) != len(hashes):
        raise ValueError('Duplicate explicit policy assignment')
    if 'prior_indices' in candidate:
        prior = candidate['prior_indices']
        if (type(prior) is not list or len(prior) != candidate['slot_count']
                or any(type(index) is not int or not -1 <= index <= 0x7fffffff for index in prior)
                or len([index for index in prior if index != -1]) != len(set(index for index in prior if index != -1))
                or all(index == -1 for index in prior)):
            raise ValueError('Malformed or unchanged explicit policy assignment')
    return action
