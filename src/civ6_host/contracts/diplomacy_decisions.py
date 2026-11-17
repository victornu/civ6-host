"""Public, redacted contract for a pending diplomatic response modal.

The host's private 948 catalogue is an input to :func:`build` only. This wire
contract deliberately carries the menu identity and offered actions without
carrying statement payloads, AI fields, opaque values, or internal source data.
"""
from __future__ import annotations

import copy
import hashlib
import json
import re

from .diplomacy_overview import PROMISE_REQUESTS

SCHEMA = 'civ6-host.network-diplomacy-decisions.v1'
DEAL_DRAFT_SCHEMA = 'civ6-host.network-diplomacy-decisions.v2'
DEAL_GOLD_SCHEMA = 'civ6-host.network-diplomacy-decisions.v3'
DEAL_RECURRING_GOLD_SCHEMA = 'civ6-host.network-diplomacy-decisions.v4'
DEAL_BILATERAL_GOLD_SCHEMA = 'civ6-host.network-diplomacy-decisions.v5'
DEAL_RESOURCE_SCHEMA = 'civ6-host.network-diplomacy-decisions.v6'
DEAL_NEGOTIATION_SCHEMA = 'civ6-host.network-diplomacy-decisions.v7'
DEAL_OPEN_BORDERS_SCHEMA = 'civ6-host.network-diplomacy-decisions.v8'
DEAL_DEMAND_SCHEMA = 'civ6-host.network-diplomacy-decisions.v9'
DEAL_PEACE_SCHEMA = 'civ6-host.network-diplomacy-decisions.v10'
DEAL_PEACE_NEGOTIATION_SCHEMA = 'civ6-host.network-diplomacy-decisions.v11'
FRIENDSHIP_RESPONSE_SCHEMA = 'civ6-host.network-diplomacy-decisions.v12'
RECEIVED_PROMISE_SCHEMA = 'civ6-host.network-diplomacy-decisions.v13'
DEAL_PEACE_NEGOTIATION_GAP = 'deal_peace_negotiation_unqualified'
DEAL_RESOURCE_WRITE_GAP = 'native_deal_resource_type_write_unavailable'
DEAL_DRAFT_GAP = 'deal_draft_edit_and_submit'
DEAL_OTHER_TERMS_GAP = 'deal_other_terms_and_received_offers'
SET_GOLD = 'CHOICE_SET_DEAL_GOLD'
SET_RECURRING_GOLD = 'CHOICE_SET_DEAL_GOLD_PER_TURN'
SET_REQUESTED_GOLD = 'CHOICE_SET_REQUESTED_DEAL_GOLD'
SET_REQUESTED_RECURRING_GOLD = 'CHOICE_SET_REQUESTED_DEAL_GOLD_PER_TURN'
FINALIZE = 'CHOICE_FINALIZE_DEAL'
EQUALIZE = 'CHOICE_EQUALIZE_DEAL'
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
_FRIENDSHIP_RESPONSES = {'AI_ACCEPT_DEAL': 'accepted', 'AI_REFUSE_DEAL': 'rejected'}
PROMISE_STATEMENTS = frozenset(PROMISE_REQUESTS.values())
PROMISE_RESPONSES = {
    'CHOICE_POSITIVE': 'POSITIVE',
    'CHOICE_NEGATIVE': 'NEGATIVE',
    'CHOICE_IGNORE': 'RESPONSE_IGNORE',
}
GOLD_TERM_FIELDS = {
    SET_GOLD: 'deal_gold',
    SET_RECURRING_GOLD: 'deal_recurring_gold',
    SET_REQUESTED_GOLD: 'deal_requested_gold',
    SET_REQUESTED_RECURRING_GOLD: 'deal_requested_recurring_gold',
}
RESOURCE_CHOICES = {'CHOICE_SET_DEAL_RESOURCE': 'outgoing', 'CHOICE_SET_REQUESTED_DEAL_RESOURCE': 'incoming'}
OPEN_BORDERS_CHOICES = {
    'CHOICE_OFFER_OPEN_BORDERS': ('outgoing', False),
    'CHOICE_REMOVE_OFFERED_OPEN_BORDERS': ('outgoing', True),
    'CHOICE_REQUEST_OPEN_BORDERS': ('incoming', False),
    'CHOICE_REMOVE_REQUESTED_OPEN_BORDERS': ('incoming', True),
}
RESOURCE_CLASSES = ('RESOURCECLASS_LUXURY', 'RESOURCECLASS_STRATEGIC')
MAX_RESOURCE_TERMS = 256
_GOLD_CHOICES = frozenset({'CHOICE_EXIT', FINALIZE, EQUALIZE, *GOLD_TERM_FIELDS, *RESOURCE_CHOICES,
                           *OPEN_BORDERS_CHOICES})
_BORDER_SCHEMAS = (DEAL_OPEN_BORDERS_SCHEMA, DEAL_PEACE_NEGOTIATION_SCHEMA)
_NEGOTIATION_SCHEMAS = (DEAL_NEGOTIATION_SCHEMA, *_BORDER_SCHEMAS)
_RESOURCE_SCHEMAS = (DEAL_RESOURCE_SCHEMA, *_NEGOTIATION_SCHEMAS, DEAL_DEMAND_SCHEMA)
_DEAL_RESPONSES = ('none', 'accepted', 'rejected', 'settled')
_GOLD_TERM_COUNTS = {DEAL_GOLD_SCHEMA: 1, DEAL_RECURRING_GOLD_SCHEMA: 2, DEAL_BILATERAL_GOLD_SCHEMA: 4,
                     **dict.fromkeys(_RESOURCE_SCHEMAS, 4)}


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def is_catalogue(value):
    return type(value) is dict and value.get('schema') in (
        SCHEMA, FRIENDSHIP_RESPONSE_SCHEMA, RECEIVED_PROMISE_SCHEMA,
        DEAL_DRAFT_SCHEMA, DEAL_PEACE_SCHEMA, *_GOLD_TERM_COUNTS)


def is_received_promise(session, player_id):
    kind = session.get('statement_type')
    return (type(kind) is str and kind in PROMISE_STATEMENTS and session.get('statement_subtype') == 'NONE'
            and session.get('to_player') == player_id and session.get('from_player') != player_id)


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


def _choices(value, *, gold=False, received_promise=False):
    if type(value) is not list or not 1 <= len(value) <= 64:
        raise ValueError('Diplomacy choices must be a bounded nonempty list')
    seen = set()
    result = []
    allowed = _GOLD_CHOICES if gold else PROMISE_RESPONSES if received_promise else _CHOICE_KEYS
    for row in value:
        if (type(row) is not dict or set(row) != _CHOICE_FIELDS
                or type(row.get('key')) is not str
                or row['key'] not in allowed
                or type(row.get('disabled')) is not bool or row['key'] in seen):
            raise ValueError('Malformed public diplomacy choice')
        seen.add(row['key'])
        result.append(dict(key=row['key'], disabled=row['disabled']))
    return result


def _project_private_choices(value, *, gold=False, received_promise=False):
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
    return _choices(projected, gold=gold, received_promise=received_promise)


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


def resolve_gold_amount(value, action, parameters):
    """Bind a selected gold or resource quantity to the offered action."""
    choice = action.get('choice')
    if choice in RESOURCE_CHOICES:
        if (value.get('schema') not in _RESOURCE_SCHEMAS or value['deal_gold']['response'] == 'settled'
                or DEAL_RESOURCE_WRITE_GAP in value['unsupported']):
            raise ValueError('An editable resource draft is required')
        return dict(action, **resolve_resource(value['deal_resources'], choice, parameters))
    if choice not in GOLD_TERM_FIELDS:
        if parameters is not None:
            raise ValueError('This diplomatic action accepts no parameters')
        return copy.deepcopy(action)
    gold = value.get('deal_gold')
    terms = value.get(GOLD_TERM_FIELDS[choice])
    if (value.get('schema') not in _GOLD_TERM_COUNTS or type(gold) is not dict or type(terms) is not dict
            or gold['response'] == 'settled'
            or type(parameters) is not dict or set(parameters) != {'amount'}
            or type(parameters['amount']) is not int
            or not 0 <= parameters['amount'] <= terms['max_amount']
            or parameters['amount'] == terms['amount']):
        raise ValueError('An available and changed gold amount is required')
    return dict(action, amount=parameters['amount'])


def resolve_resource(rows, choice, parameters):
    if (type(parameters) is not dict or set(parameters) != {'resource_index', 'amount'}
            or not _u31(parameters['resource_index']) or not _u31(parameters['amount'])):
        raise ValueError('A resource index and amount are required')
    index, amount = parameters['resource_index'], parameters['amount']
    direction = RESOURCE_CHOICES[choice]
    term = next((row for row in rows if (row['direction'],row['resource_index']) == (direction,index)), None)
    if (term is None or amount == term['amount']
            or (amount > 0 and (not term['available'] or amount > term['max_amount']))):
        raise ValueError('Resource choice or quantity is unavailable')
    return parameters


def resource_choices(rows, *, settled, can_edit=True):
    return [(choice, settled or not can_edit or not any(row['direction']==direction
                and (row['amount']>0 or (row['available'] and row['max_amount']>0)) for row in rows))
            for choice,direction in RESOURCE_CHOICES.items()]


def validate_resource_terms(rows):
    if type(rows) is not list or len(rows) > MAX_RESOURCE_TERMS:
        raise ValueError('Public resource terms exceed their bound')
    keys = set()
    for row in rows:
        if (type(row) is not dict or set(row) != {'direction', 'resource_index', 'resource_type', 'class_type',
                                                 'amount', 'max_amount', 'duration', 'available'}
                or row['direction'] not in RESOURCE_CHOICES.values()
                or not all(_u31(row[field]) for field in ('resource_index','amount','max_amount'))
                or type(row['resource_type']) is not str or re.fullmatch(r'RESOURCE_[A-Z0-9_]{1,96}',row['resource_type']) is None
                or row['class_type'] not in RESOURCE_CLASSES or type(row['available']) is not bool
                or (row['amount'] == 0 and (row['duration'] is not None or row['max_amount'] == 0))
                or (row['amount'] > 0 and not _u31(row['duration']))):
            raise ValueError('Malformed public resource term')
        key = (row['direction'], row['resource_index'])
        if key in keys:
            raise ValueError('Duplicate public resource term')
        keys.add(key)
    return rows


def validate_open_borders(rows):
    if type(rows) is not list or len(rows) != 2:
        raise ValueError('Missing public open-borders directions')
    for direction, row in zip(('outgoing','incoming'), rows):
        if (type(row) is not dict or set(row) != {'direction','duration','available_duration'}
                or row['direction'] != direction
                or any(n is not None and (not _u31(n) or n == 0)
                       for n in (row['duration'],row['available_duration']))
                or (row['duration'] is not None and row['available_duration'] is not None)):
            raise ValueError('Invalid public open-borders term')
    return rows


def validate_peace_terms(rows):
    if (type(rows) is not list or len(rows) != 2
            or any(type(row) is not dict or set(row) != {'direction', 'duration', 'locked'}
                   or row['direction'] != direction or row['locked'] is not True
                   or not _u31(row['duration'])
                   for row, direction in zip(rows, ('outgoing', 'incoming')))):
        raise ValueError('Malformed locked peace terms')
    return rows


def open_borders_choices(rows, *, settled):
    by_direction = {row['direction']: row for row in rows}
    return [(choice, settled or by_direction[direction]['duration' if remove else 'available_duration'] is None)
            for choice,(direction,remove) in OPEN_BORDERS_CHOICES.items()]


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
    session = catalogue['data']['session']
    received_promise = public_display is not None and is_received_promise(session, pid)
    gold = 'deal_gold' in catalogue['data']
    term_fields = {field: catalogue['data'][field] for field in GOLD_TERM_FIELDS.values()
                   if field in catalogue['data']}
    choices = _project_private_choices(catalogue['data'].get('selections'), gold=gold,
                                       received_promise=received_promise)
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
    is_draft = 'deal_draft' in catalogue['data']
    schema = DEAL_GOLD_SCHEMA if gold else DEAL_DRAFT_SCHEMA if is_draft else SCHEMA
    if 'deal_requested_gold' in term_fields or 'deal_requested_recurring_gold' in term_fields:
        schema = DEAL_BILATERAL_GOLD_SCHEMA
    elif 'deal_recurring_gold' in term_fields:
        schema = DEAL_RECURRING_GOLD_SCHEMA
    result = dict(schema=schema,
        base_schema=BASE_SCHEMA, episode_id=episode,
        game_generation=generation, sequence=sequence, player_id=pid, turn=turn,
        origin_turn=catalogue['origin_turn'], player_map=copy.deepcopy(catalogue['player_map']),
        turn_controls=turn_controls, dialogue=dialogue, choices=choices,
        public_display=copy.deepcopy(public_display),
        public_display_source_sha256=display_source_sha256,
        statement_source_sha256=STATEMENT_SOURCE_SHA256,
        candidates=expected, unsupported=unsupported, complete_action_space=False)
    if is_draft:
        result['deal_draft'] = copy.deepcopy(catalogue['data']['deal_draft'])
    result.update(copy.deepcopy(term_fields))
    if 'deal_resources' in catalogue['data']:
        result.update(schema=DEAL_RESOURCE_SCHEMA, deal_resources=copy.deepcopy(catalogue['data']['deal_resources']))
    if 'deal_equalize' in catalogue['data']:
        result.update(schema=DEAL_NEGOTIATION_SCHEMA, deal_equalize=catalogue['data']['deal_equalize'])
    if 'deal_open_borders' in catalogue['data']:
        result.update(schema=DEAL_OPEN_BORDERS_SCHEMA, deal_open_borders=copy.deepcopy(catalogue['data']['deal_open_borders']))
    if 'deal_demand' in catalogue['data']:
        result.update(schema=DEAL_DEMAND_SCHEMA, deal_demand=catalogue['data']['deal_demand'])
    if 'deal_peace' in catalogue['data']:
        result.update(schema=DEAL_PEACE_NEGOTIATION_SCHEMA if gold else DEAL_PEACE_SCHEMA,
                      deal_peace=copy.deepcopy(catalogue['data']['deal_peace']))
    if result['schema'] == SCHEMA and received_promise:
        result.update(schema=RECEIVED_PROMISE_SCHEMA, promise_request=session['statement_type'])
    if (result['schema'] == SCHEMA and public_display is not None and dialogue['to_player'] == pid
            and session.get('statement_type') == 'DECLARE_FRIEND'):
        subtype = session.get('statement_subtype')
        if type(subtype) is str and subtype in _FRIENDSHIP_RESPONSES:
            result.update(schema=FRIENDSHIP_RESPONSE_SCHEMA, friendship_response=_FRIENDSHIP_RESPONSES[subtype])
    result['decision_id'] = digest(result)
    return validate(result, identity, sequence, turn, player_id=pid,
                    observation=observation, actions_closed=actions_closed)


def validate(value, identity, sequence, turn, *, player_id, observation,
             actions_closed=False):
    """Validate one redacted public dialogue modal and its executable choices."""
    episode, generation = _identity(identity)
    if type(actions_closed) is not bool:
        raise ValueError('Action closure must be an exact Boolean')
    if not is_catalogue(value):
        raise ValueError('Unexpected public diplomacy catalogue schema')
    term_count = _GOLD_TERM_COUNTS.get(value['schema'], 0)
    terms = list(GOLD_TERM_FIELDS.items())[:term_count]
    peace = value['schema'] in (DEAL_PEACE_SCHEMA, DEAL_PEACE_NEGOTIATION_SCHEMA)
    friendship = value['schema'] == FRIENDSHIP_RESPONSE_SCHEMA
    received_promise = value['schema'] == RECEIVED_PROMISE_SCHEMA
    is_draft = bool(term_count) or value['schema'] == DEAL_DRAFT_SCHEMA or peace
    fields = _FIELDS | {field for _, field in terms}
    if is_draft:
        fields |= {'deal_draft'}
    resources = value['schema'] in _RESOURCE_SCHEMAS
    negotiation = value['schema'] in _NEGOTIATION_SCHEMAS
    open_borders = value['schema'] in _BORDER_SCHEMAS
    demand = value['schema'] == DEAL_DEMAND_SCHEMA
    if resources:
        fields |= {'deal_resources'}
    if negotiation:
        fields |= {'deal_equalize'}
    if open_borders:
        fields |= {'deal_open_borders'}
    if demand:
        fields |= {'deal_demand'}
    if peace:
        fields |= {'deal_peace'}
    if friendship:
        fields |= {'friendship_response'}
    if received_promise:
        fields |= {'promise_request'}
    if set(value) != fields:
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
    choices = _choices(value['choices'], gold=bool(term_count), received_promise=received_promise)
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
    if (friendship and (to_player != player_id or display is None
                        or value['friendship_response'] not in _FRIENDSHIP_RESPONSES.values())):
        raise ValueError('Invalid public friendship response')
    if (received_promise and (to_player != player_id or display is None
                              or type(value['promise_request']) is not str
                              or value['promise_request'] not in PROMISE_STATEMENTS)):
        raise ValueError('Invalid public promise request')
    if is_draft:
        draft = value['deal_draft']
        target = to_player if from_player == player_id else from_player
        if (type(draft) is not dict or set(draft) != {'target_player_id', 'item_count', 'pending'}
                or type(draft['target_player_id']) is not int or draft['target_player_id'] != target
                or type(draft['item_count']) is not int
                or not 0 <= draft['item_count'] <= term_count + (MAX_RESOURCE_TERMS if resources else 0) + 2*open_borders + 2*peace
                or draft['pending'] is not False or origin != turn or display is not None
                or (not term_count and ([row['key'] for row in choices] != ['CHOICE_EXIT']
                                        or (DEAL_PEACE_NEGOTIATION_GAP if peace else DEAL_DRAFT_GAP) not in gaps))):
            raise ValueError('Malformed public empty deal draft')
    if peace:
        validate_peace_terms(value['deal_peace'])
        if not term_count and draft['item_count'] != 2:
            raise ValueError('Malformed locked peace terms')
    if term_count:
        state = value['deal_gold']
        responses = (*_DEAL_RESPONSES, 'adjusted', 'equalize_failed') if negotiation else _DEAL_RESPONSES
        finalizers = (None,'propose','accept')
        if demand:
            responses = ('none','rejected','settled')
            finalizers = (None,'demand')
        elif peace:
            finalizers = (None,'accept')
        if (not _gold_limit(state, {'response', 'finalize'})
                or state['response'] not in responses
                or state['finalize'] not in finalizers
                or (peace and state['finalize']=='accept' and state['response'] not in ('accepted','adjusted'))
                or DEAL_OTHER_TERMS_GAP not in gaps):
            raise ValueError('Malformed public gold deal')
        expected = [(SET_GOLD, state)]
        for key, field in terms[1:]:
            term = value[field]
            recurring = key in (SET_RECURRING_GOLD, SET_REQUESTED_RECURRING_GOLD)
            if (not _gold_limit(term, {'duration'} if recurring else set()) or (recurring and
                    (type(term['duration']) is not int or not 0 < term['duration'] <= 0x7fffffff))):
                raise ValueError('Malformed public gold term')
            expected.append((key, term))
        count = 2*(peace and state['response']!='settled') + sum(term['amount'] > 0 for _, term in expected)
        extra = validate_resource_terms(value['deal_resources']) if resources else []
        if demand and (value['deal_demand'] is not True or state['max_amount'] != 0
                       or value['deal_recurring_gold']['max_amount'] != 0
                       or any(row['direction']!='incoming' for row in extra)
                       or (state['finalize']=='demand' and state['response']!='none')):
            raise ValueError('Invalid native demand directions or availability')
        count += sum(term['amount'] > 0 for term in extra)
        borders = validate_open_borders(value['deal_open_borders']) if open_borders else []
        count += sum(row['duration'] is not None for row in borders)
        if draft['item_count'] != count or (count == 0 and state['finalize'] is not None):
            raise ValueError('Gold terms differ from the draft item count')
        closed_terms = state['response']=='settled' or (demand and state['response']=='rejected')
        tail = [dict(key=key, disabled=term['max_amount'] == 0 or closed_terms)
                for key, term in expected]
        if resources:
            tail.extend(dict(key=key,disabled=disabled) for key,disabled in resource_choices(
                extra, settled=closed_terms, can_edit=DEAL_RESOURCE_WRITE_GAP not in gaps))
        if open_borders:
            tail.extend(dict(key=key,disabled=disabled) for key,disabled in open_borders_choices(
                borders, settled=state['response']=='settled'))
        if negotiation:
            available = value['deal_equalize']
            if (type(available) is not bool
                    or (available and (count == 0 or state['response'] in ('settled', 'equalize_failed')))
                    or (state['response'] == 'equalize_failed' and state['finalize'] == 'accept')
                    or (state['response'] == 'adjusted' and state['finalize'] == 'propose')):
                raise ValueError('Malformed public deal negotiation availability')
            tail.append(dict(key=EQUALIZE, disabled=not available))
        tail.append(dict(key=FINALIZE, disabled=state['finalize'] is None))
        if choices[0]['key'] != 'CHOICE_EXIT' or choices[1:] != tail:
            raise ValueError('Gold offer differs from its native availability')
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


def _gold_limit(state, additional):
    return (type(state) is dict and set(state) == {'amount', 'max_amount'} | additional
            and type(state['amount']) is int and type(state['max_amount']) is int
            and 0 <= state['amount'] <= state['max_amount'] <= 0x7fffffff)


def _u31(n):
    return type(n) is int and 0 <= n <= 0x7fffffff


__all__ = ['SCHEMA', 'FRIENDSHIP_RESPONSE_SCHEMA', 'RECEIVED_PROMISE_SCHEMA',
           'DEAL_DRAFT_SCHEMA', 'DEAL_DRAFT_GAP', 'BASE_SCHEMA', 'STATEMENT_SOURCE_SHA256',
           'PUBLIC_DISPLAY_SOURCE_SHA256', 'PUBLIC_DISPLAY_GAP', 'digest',
           'is_catalogue', 'build', 'validate']
