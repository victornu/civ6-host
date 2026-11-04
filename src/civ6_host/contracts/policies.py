"""Pure validation and projection of a player-selected policy assignment."""
import re


class PolicyAssignmentUnavailable(ValueError):
    """The requested assignment does not fit a valid policy catalogue."""


def validate_slots(slots):
    if type(slots) is not list or len(slots) > 64:
        raise ValueError('Invalid policy slots')
    prior = set()
    identities = {}
    hashes = {}
    names = {}
    relations = 0
    for i, row in enumerate(slots):
        if type(row) is not dict or set(row) != {'slot', 'prior_index', 'options'} or type(row['slot']) is not int or (row['slot'] != i) or (type(row['prior_index']) is not int) or (not -1 <= row['prior_index'] <= 2147483647) or (type(row['options']) is not list) or (len(row['options']) > 4096):
            raise ValueError('Malformed policy slot')
        index = row['prior_index']
        if index != -1:
            if index in prior:
                raise ValueError('Duplicate prior policy')
            prior.add(index)
        seen = set()
        last = -1
        for option in row['options']:
            if type(option) is not dict or set(option) != {'index', 'hash', 'native_hash', 'policy_type'} or type(option['index']) is not int or (not 0 <= option['index'] <= 2147483647) or (type(option['hash']) is not int) or (not 0 <= option['hash'] <= 4294967295) or (type(option['native_hash']) is not int) or (not -2147483648 <= option['native_hash'] <= 4294967295) or (option['native_hash'] & 4294967295 != option['hash']) or (type(option['policy_type']) is not str) or (len(option['policy_type']) > 128) or (re.fullmatch('POLICY_[A-Z0-9_]+', option['policy_type']) is None):
                raise ValueError('Invalid policy option')
            idx, bits, name = (option['index'], option['hash'], option['policy_type'])
            if bits in seen or idx <= last:
                raise ValueError('Duplicate or unordered policy options')
            if idx in identities and identities[idx] != (bits, name, option['native_hash']) or (bits in hashes and hashes[bits] != idx) or (name in names and names[name] != idx):
                raise ValueError('Inconsistent policy identity')
            seen.add(bits)
            last = idx
            identities[idx] = (bits, name, option['native_hash'])
            hashes[bits] = idx
            names[name] = idx
            relations += 1
    if relations > 8192:
        raise ValueError('Policy options exceed bound')
    for row in slots:
        if any((o['index'] in prior and o['index'] != row['prior_index'] for o in row['options'])):
            raise ValueError('Active policy relocation is outside this adapter')
    return slots


def choose(slots, assignments, player_id, turn):
    """Validate exactly the caller's dense list of hashes; no replacement choice."""
    validate_slots(slots)
    if type(assignments) is not list or not 1 <= len(assignments) == len(slots) <= 64 or any((type(h) is not int or not 0 <= h <= 4294967295 for h in assignments)) or (len(set(assignments)) != len(assignments)):
        raise PolicyAssignmentUnavailable('Policy assignment must be complete with unique unsigned hashes')
    indices = []
    native_hashes = []
    for row, h in zip(slots, assignments):
        matches = [o for o in row['options'] if o['hash'] == h]
        if len(matches) != 1:
            raise PolicyAssignmentUnavailable('Policy assignment is absent from the slot catalogue')
        indices.append(matches[0]['index'])
        native_hashes.append(matches[0]['native_hash'])
    prior = [r['prior_index'] for r in slots]
    if indices == prior:
        raise PolicyAssignmentUnavailable('Policy assignment is unchanged')
    if type(player_id) is not int or not 0 <= player_id <= 63:
        raise ValueError('Invalid player ID')
    if type(turn) is not int or not 0 <= turn <= 4294967295:
        raise ValueError('Invalid turn')
    result = dict(status='candidate', player_id=player_id, turn=turn, slot_count=len(slots), assignments=[[i, h] for i, h in enumerate(native_hashes)])
    if any((v != -1 for v in prior)):
        result['prior_indices'] = prior
    return result
