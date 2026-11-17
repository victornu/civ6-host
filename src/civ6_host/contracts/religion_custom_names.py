"""Public custom-icon foundation choices and explicit, unmodified name text.

Only input shape and the qualified EditBox scalar limit are checked here.
The official Locale.ToUpper placeholder predicate is rechecked by the native
owner. Programmatic defaults retain their exact public localized string.
"""
from copy import deepcopy
from .religion_beliefs import _int, _keys, _own, project_snapshot

SCHEMA = 'civ6-host.religion-custom-names.v1'
KIND = 'found_custom_religion'
FIELDS = {'kind', 'index', 'hash'}
EXPANDED_FIELDS = FIELDS | {'custom_name'}
MAX_INPUT_SCALARS = 32


def _text(value, *, nonempty=False):
    if type(value) is not str or '\0' in value or nonempty and not value:
        raise ValueError('Religion text must be an exact string without NUL')
    try:
        value.encode('utf-8', errors='strict')
    except UnicodeEncodeError as exc:
        raise ValueError('Religion text contains a non-scalar Unicode value') from exc
    return value


def validate_input_name(value):
    _text(value, nonempty=True)
    if len(value) > MAX_INPUT_SCALARS or all(char == ' ' for char in value):
        raise ValueError('Religion input requires 1–32 Unicode scalars, not only U+0020')
    return value


def validate_action(action, *, expanded=True):
    _keys(action, EXPANDED_FIELDS if expanded else FIELDS)
    if action['kind'] != KIND:
        raise ValueError('Unexpected custom religion foundation action')
    _int(action['index'])
    _int(action['hash'], 0, 0xffffffff)
    if expanded:
        # A receipt may contain the official programmatic default. Its length
        # is not an EditBox input limit; choose() binds it to the offered icon.
        _text(action['custom_name'], nonempty=True)
    return action


def validate_template(candidate):
    return validate_action(candidate, expanded=False)


def validate(value, player_id, turn, *, observation=None):
    _int(player_id, 0, 63)
    _int(turn, 0, 0xffffffff)
    _keys(value, {'schema', 'player_id', 'turn', 'status', 'own', 'own_custom_name',
                  'rename_allowed', 'placeholder', 'custom_icons'})
    if (value['schema'] != SCHEMA or _int(value['player_id'], 0, 63) != player_id
            or _int(value['turn'], 0, 0xffffffff) != turn):
        raise ValueError('Foreign custom religion boundary')
    if observation is not None:
        if (type(observation) is not dict or type(observation.get('turn')) is not int
                or observation['turn'] != turn):
            raise ValueError('Stale custom religion observation')
    _own(value['own'], player_id, observation)
    if value['own_custom_name'] is not None:
        _text(value['own_custom_name'])
    if value['own']['own_religion'] is None and value['own_custom_name'] is not None:
        raise ValueError('Own custom name differs from the actor religion record')
    if type(value['rename_allowed']) is not bool:
        raise ValueError('Religion renaming requires its native capability flag')
    _text(value['placeholder'])
    rows = value['custom_icons']
    if (value['status'] not in ('catalog', 'not_due') or type(rows) is not list
            or len(rows) > 4096 or bool(rows) != (value['status'] == 'catalog')):
        raise ValueError('Custom religion status differs from its icon catalogue')
    own = value['own']
    if rows and (own['religion_type_created'] != -1 or not own['holy_city_present']
                 or own['num_beliefs_earned'] < 1):
        raise ValueError('Custom religion choices lack their native foundation context')
    indices, hashes = [], []
    for row in rows:
        _keys(row, {'index', 'hash', 'default_name'})
        validate_template(dict(kind=KIND, index=row['index'], hash=row['hash']))
        _text(row['default_name'], nonempty=True)
        indices.append(row['index'])
        hashes.append(row['hash'])
    if indices != sorted(set(indices)) or len(set(hashes)) != len(hashes):
        raise ValueError('Duplicate or unordered custom religion choices')
    return value


def project(value, player_id, turn, *, observation=None):
    """Project a native flat catalogue, stripping only own-state diagnostics."""
    _keys(value, {'status', 'own', 'own_custom_name', 'rename_allowed', 'placeholder', 'custom_icons'})
    result = dict(schema=SCHEMA, player_id=player_id, turn=turn,
                  own=project_snapshot(value['own'], player_id, turn, observation=observation),
                  own_custom_name=value['own_custom_name'],
                  status=value['status'], rename_allowed=value['rename_allowed'],
                  placeholder=value['placeholder'], custom_icons=deepcopy(value['custom_icons']))
    return validate(result, player_id, turn, observation=observation)


def actions(value):
    if value is None:
        return []
    validate(value, value['player_id'], value['turn'])
    return [dict(kind=KIND, index=row['index'], hash=row['hash'])
            for row in value['custom_icons']]


def choose(value, candidate, parameters=None):
    """Expand the selected icon using explicit input or its exact native default."""
    validate(value, value['player_id'], value['turn'])
    validate_template(candidate)
    matches = [row for row in value['custom_icons']
               if row['index'] == candidate['index'] and row['hash'] == candidate['hash']]
    if len(matches) != 1:
        raise ValueError('Custom religion icon is absent from the native catalogue')
    if value['rename_allowed']:
        _keys(parameters, {'name'})
        name = validate_input_name(parameters['name'])
    else:
        if parameters is not None:
            raise ValueError('Religion renaming is unavailable; no parameters accepted')
        name = matches[0]['default_name']
    return validate_action(dict(candidate, custom_name=name), expanded=True)
