"""Public captured-city choices shared by the native owner and client."""

KIND = 'resolve_captured_city'
DIRECTIVES = ('KEEP', 'RAZE', 'LIBERATE_FOUNDER', 'LIBERATE_PREVIOUS_OWNER')
FIELDS = {'kind', 'city_id', 'directive'}
CITY_FIELDS = ('city_id', 'x', 'y', 'original_owner', 'previous_owner', 'conquered_from')
_LIBERATION_OWNER = {'LIBERATE_FOUNDER': 'original_owner',
                     'LIBERATE_PREVIOUS_OWNER': 'previous_owner'}


def uint(value, label, maximum=0xffffffff):
    if type(value) is not int or not 0 <= value <= maximum:
        raise ValueError('Invalid captured-city ' + label)
    return value


def validate_action(action):
    if (type(action) is not dict or set(action) != FIELDS or action['kind'] != KIND
            or type(action['directive']) is not str or action['directive'] not in DIRECTIVES):
        raise ValueError('Unknown captured-city action')
    uint(action['city_id'], 'id')
    return action


def _envelope(value, pid, turn):
    uint(pid, 'player', 63)
    uint(turn, 'turn', 0x7fffffff)
    if (type(value) is not dict or set(value) != {'player_id', 'turn', 'city', 'directives'}
            or type(value['player_id']) is not int or value['player_id'] != pid
            or type(value['turn']) is not int or value['turn'] != turn):
        raise ValueError('Invalid captured-city catalogue')
    choices = value['directives']
    if (type(choices) is not list or len(choices) > len(DIRECTIVES)
            or any(type(d) is not str or d not in DIRECTIVES for d in choices)
            or len(set(choices)) != len(choices)):
        raise ValueError('Invalid captured-city directives')
    city = value['city']
    if city is None:
        if choices:
            raise ValueError('Directive without captured city')
    return city, choices


def _position(city, pid, turn, observation):
    uint(city['city_id'], 'id')
    uint(city['x'], 'x', 65535)
    uint(city['y'], 'y', 65535)
    if observation is not None and (observation['player_id'] != pid or observation['turn'] != turn
            or not any((r['id'], r['x'], r['y'], r['owner']) ==
                       (city['city_id'], city['x'], city['y'], pid)
                       for r in observation['cities'])):
        raise ValueError('Captured city differs from the public own-city observation')


def validate_catalog(value, pid, turn, *, observation=None):
    city, _ = _envelope(value, pid, turn)
    if city is None:
        return value
    if type(city) is not dict or set(city) != set(CITY_FIELDS):
        raise ValueError('Invalid captured city witness')
    _position(city, pid, turn, observation)
    for key in ('original_owner', 'previous_owner', 'conquered_from'):
        uint(city[key], key, 63)
    return value


def validate_public_catalog(value, pid, turn, *, observation=None):
    city, choices = _envelope(value, pid, turn)
    if city is None:
        return value
    if type(city) is not dict or set(city) != {'city_id', 'x', 'y', 'liberation_recipients'}:
        raise ValueError('Invalid public captured-city witness')
    _position(city, pid, turn, observation)
    recipients = city['liberation_recipients']
    if type(recipients) is not dict or set(recipients) != set(choices).intersection(_LIBERATION_OWNER):
        raise ValueError('Liberation recipients differ from the offered choices')
    for pid in recipients.values():
        uint(pid, 'liberation recipient', 63)
    return value


def project_public(value, *, observation):
    pid, turn = observation['player_id'], observation['turn']
    validate_catalog(value, pid, turn, observation=observation)
    city, choices = value['city'], value['directives']
    public = None
    if city is not None:
        public = {key: city[key] for key in ('city_id', 'x', 'y')}
        public['liberation_recipients'] = {
            d: city[_LIBERATION_OWNER[d]] for d in choices if d in _LIBERATION_OWNER}
    return dict(player_id=pid, turn=turn, city=public, directives=list(choices))


def _actions(value):
    return [dict(kind=KIND, city_id=value['city']['city_id'], directive=d)
            for d in value['directives']]


def actions(value):
    validate_catalog(value, value['player_id'], value['turn'])
    return _actions(value)


def public_actions(value):
    validate_public_catalog(value, value['player_id'], value['turn'])
    return _actions(value)
