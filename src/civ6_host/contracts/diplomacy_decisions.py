"""Public, redacted contract for a pending diplomatic response modal.

The host's private 948 catalogue is an input to :func:`build` only. This wire
contract deliberately carries the menu identity and offered actions without
carrying statement payloads, AI fields, opaque values, or internal source data.
"""
from __future__ import annotations

import copy
import hashlib
import json

SCHEMA = 'civ6-host.network-diplomacy-decisions.v1'
BASE_SCHEMA = 'civ6rl.diplomacy_decisions948.v1'
STATEMENT_SOURCE_SHA256 = '5c76284af04f07fc754dcceffdd499b3769c12f49b198ff628671a721932d566'
# Replaced only when the selected renderer source proof is admitted.
PUBLIC_DISPLAY_SOURCE_SHA256 = 'c174fdd3559007895a8bf1dbdaf0e0cbcf3b0ae8cf807788b34d331dbb856c3f'
PUBLIC_DISPLAY_GAP = 'xp2_diplomacy_public_display_unqualified'
_FIELDS = frozenset({
    'schema', 'base_schema', 'episode_id', 'game_generation', 'sequence',
    'player_id', 'turn', 'origin_turn', 'player_map', 'turn_controls',
    'dialogue', 'choices', 'public_display', 'public_display_source_sha256',
    'statement_source_sha256', 'candidates', 'unsupported',
    'complete_action_space', 'decision_id',
})
_DIALOGUE_FIELDS = frozenset({'session_id', 'statement_sequence', 'from_player', 'to_player'})
_CHOICE_FIELDS = frozenset({'key', 'disabled'})
_CANDIDATE_FIELDS = frozenset({'candidate_id', 'action'})
_DISPLAY_FIELDS = frozenset({'schema', 'speaker_leader', 'statement_text', 'reason_text', 'selections'})
_DISPLAY_CHOICE_FIELDS = frozenset({'key', 'text', 'disabled', 'tooltip'})
_CHOICE_KEYS = frozenset({'CHOICE_POSITIVE', 'CHOICE_EXIT'})


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def is_catalogue(value):
    return type(value) is dict and value.get('schema') == SCHEMA


def _identity(identity):
    if type(identity) is dict:
        episode, generation = identity.get('episode_id'), identity.get('game_generation')
    else:
        episode = getattr(identity, 'episode_id', None)
        generation = getattr(identity, 'game_generation', None)
    if (type(episode) is not str or not episode
            or type(generation) is not str or not generation):
        raise ValueError('Diplomacy episode identity is missing')
    return episode, generation


def _text(value, label, *, nullable=False):
    if value is None and nullable:
        return
    if (type(value) is not str or '\x00' in value
            or len(value.encode('utf-8')) > 4096):
        raise ValueError('Malformed public diplomacy ' + label)


def _choices(value):
    if type(value) is not list or not 1 <= len(value) <= 64:
        raise ValueError('Diplomacy choices must be a bounded nonempty list')
    seen = set()
    result = []
    for row in value:
        if (type(row) is not dict or set(row) != _CHOICE_FIELDS
                or type(row.get('key')) is not str or row['key'] not in _CHOICE_KEYS
                or type(row.get('disabled')) is not bool or row['key'] in seen):
            raise ValueError('Malformed public diplomacy choice')
        seen.add(row['key'])
        result.append(dict(key=row['key'], disabled=row['disabled']))
    return result


def _project_private_choices(value):
    """Reduce already validated native menu rows to key and disabled only."""
    if type(value) is not list or not 1 <= len(value) <= 64:
        raise ValueError('Private diplomacy menu is outside its bound')
    projected = []
    for row in value:
        if (type(row) is not dict
                or set(row) != {'key', 'sort', 'text', 'tooltip',
                                'diplomatic_action_type', 'disabled'}):
            raise ValueError('Private diplomacy menu row changed shape')
        projected.append(dict(key=row['key'], disabled=row['disabled']))
    return _choices(projected)


def _display(value, choices):
    if (type(value) is not dict or set(value) != _DISPLAY_FIELDS
            or value.get('schema') != 'civ6rl.diplomacy_public_display986.v2'):
        raise ValueError('Malformed public diplomatic display')
    _text(value['speaker_leader'], 'speaker', nullable=True)
    _text(value['statement_text'], 'statement')
    _text(value['reason_text'], 'reason')
    rows = value['selections']
    if type(rows) is not list or len(rows) != len(choices):
        raise ValueError('Diplomatic display menu differs from the native menu')
    seen = set()
    for row, choice in zip(rows, choices):
        if (type(row) is not dict or set(row) != _DISPLAY_CHOICE_FIELDS
                or row.get('key') != choice['key']
                or type(row.get('disabled')) is not bool
                or row['disabled'] is not choice['disabled']
                or row['key'] in seen):
            raise ValueError('Diplomatic display identity or order differs')
        _text(row['key'], 'choice key')
        _text(row['text'], 'choice text')
        _text(row['tooltip'], 'tooltip', nullable=True)
        if not row['disabled'] and row['tooltip'] is not None:
            raise ValueError('Enabled diplomatic choice has an unsupported tooltip')
        seen.add(row['key'])
    return value


def _session(catalogue, player_id):
    if type(catalogue) is not dict or catalogue.get('schema') != BASE_SCHEMA:
        raise ValueError('Public dialogue builder requires the validated 948 catalogue')
    data = catalogue.get('data')
    session = data.get('session') if type(data) is dict else None
    if type(session) is not dict:
        raise ValueError('Private catalogue lacks its native session identity')
    sid = session.get('session_id')
    source_statement = catalogue.get('statement')
    if type(source_statement) is not dict:
        raise ValueError('Private catalogue lacks its native statement identity')
    sequence = source_statement.get('event_sequence')
    from_player, to_player = session.get('from_player'), session.get('to_player')
    if (type(sid) is not int or not 0 <= sid <= 0xffffffff
            or type(sequence) is not int or not 0 < sequence <= 0x7fffffff
            or any(type(pid) is not int or not 0 <= pid < 64 for pid in (from_player, to_player))
            or from_player == to_player or player_id not in (from_player, to_player)):
        raise ValueError('Invalid public dialogue endpoints or sequence')
    return dict(session_id=sid, statement_sequence=sequence,
                from_player=from_player, to_player=to_player)


def _candidate_rows(dialogue, choices, *, actions_closed):
    if type(actions_closed) is not bool:
        raise ValueError('Action closure must be an exact Boolean')
    if actions_closed:
        return []
    rows = []
    for choice in choices:
        if choice['disabled']:
            continue
        action = dict(kind='diplomacy_response', session_id=dialogue['session_id'],
                      statement_sequence=dialogue['statement_sequence'], choice=choice['key'])
        rows.append(dict(candidate_id=digest(action), action=action))
    return rows


def build(identity, sequence, observation, controls, catalogue, *, public_display=None,
          display_source_sha256=None, actions_closed=False):
    """Build the public modal from an already validated private 948 catalogue."""
    episode, generation = _identity(identity)
    if (type(sequence) is not int or not 0 <= sequence <= 0x7fffffff
            or type(observation) is not dict
            or type(observation.get('player_id')) is not int
            or type(observation.get('turn')) is not int):
        raise ValueError('Invalid public dialogue boundary')
    pid, turn = observation['player_id'], observation['turn']
    if not 0 <= pid < 64 or turn < 0:
        raise ValueError('Invalid public dialogue actor or turn')
    if type(catalogue) is not dict or (catalogue.get('schema') != BASE_SCHEMA
            or catalogue.get('episode_id') != episode
            or catalogue.get('game_generation') != generation
            or catalogue.get('sequence') != sequence
            or catalogue.get('player_id') != pid
            or catalogue.get('turn') != turn):
        raise ValueError('Private catalogue crossed the public dialogue boundary')
    dialogue = _session(catalogue, pid)
    choices = _project_private_choices(catalogue['data'].get('selections'))
    offered = _candidate_rows(dialogue, choices, actions_closed=False)
    if type(catalogue.get('candidates')) is not list:
        raise ValueError('Private native candidates are missing')
    if (catalogue.get('candidates') != offered
            and not (actions_closed and catalogue.get('candidates') == [])):
        raise ValueError('Private native candidates differ from public choices')
    expected = _candidate_rows(dialogue, choices, actions_closed=actions_closed)
    gaps = catalogue.get('unsupported')
    if (type(gaps) is not list or any(type(item) is not str for item in gaps)
            or len(gaps) != len(set(gaps))):
        raise ValueError('Invalid public dialogue gap list')
    unsupported = list(gaps)
    if public_display is None:
        if display_source_sha256 is not None:
            raise ValueError('Missing diplomatic display cannot carry a source pin')
        if PUBLIC_DISPLAY_GAP not in unsupported:
            unsupported.append(PUBLIC_DISPLAY_GAP)
    else:
        if (PUBLIC_DISPLAY_SOURCE_SHA256 == 'PENDING'
                or type(display_source_sha256) is not str
                or display_source_sha256 != PUBLIC_DISPLAY_SOURCE_SHA256):
            raise ValueError('Diplomatic display source profile is not admitted')
        _display(public_display, choices)
        if PUBLIC_DISPLAY_GAP in unsupported:
            unsupported.remove(PUBLIC_DISPLAY_GAP)
    from .network_turn import validate_turn_controls
    turn_controls = validate_turn_controls(controls, pid, turn)
    result = dict(schema=SCHEMA, base_schema=BASE_SCHEMA, episode_id=episode,
        game_generation=generation, sequence=sequence, player_id=pid, turn=turn,
        origin_turn=catalogue['origin_turn'], player_map=copy.deepcopy(catalogue['player_map']),
        turn_controls=turn_controls, dialogue=dialogue, choices=choices,
        public_display=copy.deepcopy(public_display),
        public_display_source_sha256=display_source_sha256,
        statement_source_sha256=STATEMENT_SOURCE_SHA256,
        candidates=expected, unsupported=unsupported, complete_action_space=False)
    result['decision_id'] = digest(result)
    return validate(result, identity, sequence, turn, player_id=pid,
                    observation=observation, actions_closed=actions_closed)


def validate(value, identity, sequence, turn, *, player_id, observation,
             actions_closed=False):
    """Validate one redacted public dialogue modal and its executable choices."""
    episode, generation = _identity(identity)
    if type(actions_closed) is not bool:
        raise ValueError('Action closure must be an exact Boolean')
    if type(value) is not dict or set(value) != _FIELDS or value.get('schema') != SCHEMA:
        raise ValueError('Unexpected public diplomacy catalogue fields')
    if (value['base_schema'] != BASE_SCHEMA or value['episode_id'] != episode
            or value['game_generation'] != generation
            or type(value['episode_id']) is not str
            or type(value['game_generation']) is not str):
        raise ValueError('Foreign public diplomacy episode')
    for name, expected, maximum in (('sequence', sequence, 0x7fffffff),
                                    ('player_id', player_id, 63),
                                    ('turn', turn, 0xffffffff)):
        if (type(expected) is not int or not 0 <= expected <= maximum
                or type(value[name]) is not int or value[name] != expected):
            raise ValueError('Stale public diplomacy ' + name)
    origin = value['origin_turn']
    if type(origin) is not int or not 0 <= origin <= turn or turn not in (origin, origin + 1):
        raise ValueError('Invalid public dialogue origin turn')
    if (type(observation) is not dict or observation.get('player_id') != player_id
            or observation.get('turn') != turn):
        raise ValueError('Public dialogue and observation differ')
    if value['statement_source_sha256'] != STATEMENT_SOURCE_SHA256:
        raise ValueError('Diplomatic statement source profile differs')
    if type(value['complete_action_space']) is not bool or value['complete_action_space'] is not False:
        raise ValueError('Diplomacy modal is not a complete action catalogue')
    gaps = value['unsupported']
    if (type(gaps) is not list or any(type(item) is not str for item in gaps)
            or len(gaps) != len(set(gaps))):
        raise ValueError('Invalid public diplomacy gap list')
    display = value['public_display']
    display_pin = value['public_display_source_sha256']
    choices = _choices(value['choices'])
    if display is None:
        if display_pin is not None or PUBLIC_DISPLAY_GAP not in gaps:
            raise ValueError('Missing display must be marked unqualified')
    else:
        if (PUBLIC_DISPLAY_SOURCE_SHA256 == 'PENDING'
                or display_pin != PUBLIC_DISPLAY_SOURCE_SHA256):
            raise ValueError('Diplomatic display source profile differs')
        _display(display, choices)
        if PUBLIC_DISPLAY_GAP in gaps:
            raise ValueError('Qualified display is marked unqualified')
    dialogue = value['dialogue']
    if type(dialogue) is not dict or set(dialogue) != _DIALOGUE_FIELDS:
        raise ValueError('Malformed public dialogue identity')
    sid, statement_sequence = dialogue['session_id'], dialogue['statement_sequence']
    from_player, to_player = dialogue['from_player'], dialogue['to_player']
    if (type(sid) is not int or not 0 <= sid <= 0xffffffff
            or type(statement_sequence) is not int or not 0 < statement_sequence <= 0x7fffffff
            or any(type(pid) is not int or not 0 <= pid < 64 for pid in (from_player, to_player))
            or from_player == to_player or player_id not in (from_player, to_player)):
        raise ValueError('Invalid public dialogue endpoints')
    from .network_turn import validate_turn_controls
    validate_turn_controls(value['turn_controls'], player_id, turn)
    expected = _candidate_rows(dialogue, choices, actions_closed=actions_closed)
    candidates = value['candidates']
    if type(candidates) is not list:
        raise ValueError('Public diplomacy candidates are missing')
    for row in candidates:
        if (type(row) is not dict or set(row) != _CANDIDATE_FIELDS
                or type(row.get('candidate_id')) is not str
                or type(row.get('action')) is not dict
                or set(row['action']) != {'kind', 'session_id', 'statement_sequence', 'choice'}
                or row['action'].get('kind') != 'diplomacy_response'
                or type(row['action'].get('session_id')) is not int
                or type(row['action'].get('statement_sequence')) is not int
                or type(row['action'].get('choice')) is not str
                or row['candidate_id'] != digest(row['action'])):
            raise ValueError('Malformed public diplomacy candidate')
    if candidates != expected:
        raise ValueError('Public diplomacy candidates differ from official menu choices')
    if type(value['player_map']) is not dict:
        raise ValueError('Public dialogue requires its player map')
    if type(value['decision_id']) is not str or value['decision_id'] != digest(
            {key: item for key, item in value.items() if key != 'decision_id'}):
        raise ValueError('Public diplomacy decision digest differs')
    return value


__all__ = ['SCHEMA', 'BASE_SCHEMA', 'STATEMENT_SOURCE_SHA256',
           'PUBLIC_DISPLAY_SOURCE_SHA256', 'PUBLIC_DISPLAY_GAP', 'digest',
           'is_catalogue', 'build', 'validate']
