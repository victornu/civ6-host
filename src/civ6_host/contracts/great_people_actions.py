"""Recruitment, patronage and opt-in rejection from exact native offers.

This slice excludes activation of other Great Person classes.
It adds no data fields and does not claim the full Great People action space.
"""
from . import great_people

RECRUIT = 'recruit_great_person'
PATRONIZE = 'patronize_great_person'
REJECT = 'reject_great_person'
LEGACY_KINDS = (RECRUIT, PATRONIZE)
KINDS = (*LEGACY_KINDS, REJECT)
FIELDS = {
    RECRUIT: {'kind', 'individual_index', 'cost'},
    PATRONIZE: {'kind', 'individual_index', 'cost', 'currency'},
    REJECT: {'kind', 'individual_index', 'cost'},
}


def validate_action(action):
    if type(action) is not dict or action.get('kind') not in KINDS:
        raise ValueError('Unknown explicit Great Person action')
    great_people._keys(action, FIELDS[action['kind']])
    great_people._int(action['individual_index'])
    great_people._int(action['cost'], -(2**31) if action['kind'] == REJECT else 0)
    if action['kind'] == PATRONIZE and action['currency'] not in great_people.CURRENCIES:
        raise ValueError('Unknown Great Person patronage currency')
    return action


def actions(state, *, include_reject=False):
    """Copy the exact native offered identities/prices without strategic filtering."""
    if type(include_reject) is not bool:
        raise ValueError('Great Person rejection admission must be explicit')
    if state is None:
        return []
    great_people.validate(state, state['player_id'], state['turn'])
    result=[]
    for row in state['timeline']:
        if row['individual_index'] is None:
            continue
        if row['recruitment']['available']:
            result.append(dict(kind=RECRUIT, individual_index=row['individual_index'],
                               cost=row['recruitment']['cost']))
        for currency in great_people.CURRENCIES:
            offer=row['patronage'][currency]
            if offer['available']:
                result.append(dict(kind=PATRONIZE, individual_index=row['individual_index'],
                                   cost=offer['cost'], currency=currency))
        if include_reject and row['rejection']['available']:
            result.append(dict(kind=REJECT, individual_index=row['individual_index'],
                               cost=row['rejection']['cost']))
    for action in result:
        validate_action(action)
    return result
