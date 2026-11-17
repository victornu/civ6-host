"""Public overview data and explicit initial diplomatic choices; no native code."""
from __future__ import annotations

import re

SCHEMA = 'civ6-host.diplomacy-overview.v1'
RELATIONSHIPS_SCHEMA = 'civ6-host.diplomacy-overview.v2'
CITY_STATE_PEACE_SCHEMA = 'civ6-host.diplomacy-overview.v3'
MAJOR_DEALS_SCHEMA = 'civ6-host.diplomacy-overview.v4'
DEAL_DRAFT_SCHEMA = 'civ6-host.diplomacy-overview.v5'
OPEN_BORDERS_SCHEMA = 'civ6-host.diplomacy-overview.v6'
DEMAND_SCHEMA = 'civ6-host.diplomacy-overview.v7'
MAJOR_PEACE_SCHEMA = 'civ6-host.diplomacy-overview.v8'
STOCK_MAJOR_PEACE_SCHEMA = 'civ6-host.diplomacy-overview.stock-major-peace.v1'
STOCK_NEGOTIATION_SCHEMA = 'civ6-host.diplomacy-overview.stock-negotiation.v1'
STOCK_FRIENDSHIP_SCHEMA = 'civ6-host.diplomacy-overview.stock-negotiation.v2'
STOCK_PROMISE_SCHEMA = 'civ6-host.diplomacy-overview.stock-negotiation.v3'
STOCK_PROMISE_STATUS_SCHEMA = 'civ6-host.diplomacy-overview.stock-negotiation.v4'
STOCK_CITY_STATE_PEACE_SCHEMA = 'civ6-host.diplomacy-overview.stock-negotiation.v5'
STOCK_PROMISE_STATUS_SCHEMAS = (STOCK_PROMISE_STATUS_SCHEMA, STOCK_CITY_STATE_PEACE_SCHEMA)
STOCK_SCHEMAS = (STOCK_MAJOR_PEACE_SCHEMA, STOCK_NEGOTIATION_SCHEMA, STOCK_FRIENDSHIP_SCHEMA,
                 STOCK_PROMISE_SCHEMA, *STOCK_PROMISE_STATUS_SCHEMAS)
MAKE_PEACE = 'CHOICE_MAKE_PEACE'
DENOUNCE = 'CHOICE_DENOUNCE'
DECLARE_FRIENDSHIP = 'CHOICE_DECLARE_FRIENDSHIP'
OPEN_DEAL = 'CHOICE_MAKE_DEAL'
OPEN_DEMAND = 'CHOICE_MAKE_DEMAND'
PROMISE_REQUESTS = {
    'CHOICE_DEMAND_PROMISE_DONT_SPY': 'WARNING_STOP_SPYING_ON_ME',
    'CHOICE_DEMAND_PROMISE_DONT_SETTLE_TOO_NEAR': 'WARNING_DONT_SETTLE_NEAR_ME',
    'CHOICE_DEMAND_PROMISE_DONT_CONVERT_CITY': 'WARNING_STOP_CONVERTING_MY_CITIES',
    'CHOICE_DEMAND_PROMISE_DONT_DIG_ARTIFACTS': 'WARNING_STOP_DIGGING_UP_ARTIFACTS',
}
PROMISE_CHOICES = tuple(PROMISE_REQUESTS)
PROMISE_TYPES = ('DONT_SETTLE_NEAR_ME', 'DONT_SPY_ON_ME', 'DONT_DIG_UP_MY_ARTIFACTS', 'DONT_CONVERT_MY_CITIES')
STOCK_DIRECT_AI_CHOICES = {
    STOCK_FRIENDSHIP_SCHEMA: frozenset((DECLARE_FRIENDSHIP,)),
    STOCK_PROMISE_SCHEMA: frozenset((DECLARE_FRIENDSHIP, *PROMISE_CHOICES)),
    **{schema: frozenset((DECLARE_FRIENDSHIP, *PROMISE_CHOICES)) for schema in STOCK_PROMISE_STATUS_SCHEMAS},
}
DEMAND_SCHEMAS = (DEMAND_SCHEMA, MAJOR_PEACE_SCHEMA, STOCK_NEGOTIATION_SCHEMA, STOCK_FRIENDSHIP_SCHEMA,
                  STOCK_PROMISE_SCHEMA, *STOCK_PROMISE_STATUS_SCHEMAS)
BORDERS_SCHEMAS = (OPEN_BORDERS_SCHEMA, *DEMAND_SCHEMAS)
DRAFT_SCHEMAS = (DEAL_DRAFT_SCHEMA, *BORDERS_SCHEMAS)
CITY_STATE_SCHEMAS = (CITY_STATE_PEACE_SCHEMA, MAJOR_DEALS_SCHEMA, DEAL_DRAFT_SCHEMA,
                      OPEN_BORDERS_SCHEMA, DEMAND_SCHEMA, MAJOR_PEACE_SCHEMA, STOCK_CITY_STATE_PEACE_SCHEMA)
MAJOR_DEAL_SCHEMAS = (MAJOR_DEALS_SCHEMA, *DRAFT_SCHEMAS, STOCK_MAJOR_PEACE_SCHEMA)
MAJOR_PEACE_SCHEMAS = (MAJOR_PEACE_SCHEMA, *STOCK_SCHEMAS)
SCHEMAS = (SCHEMA, RELATIONSHIPS_SCHEMA, CITY_STATE_PEACE_SCHEMA, MAJOR_DEALS_SCHEMA, DEAL_DRAFT_SCHEMA,
           OPEN_BORDERS_SCHEMA, DEMAND_SCHEMA, MAJOR_PEACE_SCHEMA, *STOCK_SCHEMAS)
MAX_DEAL_TERMS = 512
_FIELDS = {'schema', 'player_id', 'turn', 'capability', 'paused',
           'targets', 'complete_action_space'}
_SELECTION = {'key', 'disabled', 'supported', 'text', 'tooltip', 'diplomatic_action_type'}
ACTION_FIELDS = {'diplomacy_initiate': frozenset(('kind', 'target_player_id', 'choice'))}


def _signed_integer(value):
    return type(value) is int and -(1 << 31) <= value < (1 << 31)


def _validate_relationship(value, player_id, target_id):
    if value is None:
        return
    if (type(value) is not dict or set(value) != {'state', 'grievances', 'expiration'}
            or type(value['state']) is not str
            or re.fullmatch(r'DIPLO_STATE_[A-Z0-9_]{1,96}', value['state']) is None
            or not _signed_integer(value['grievances'])):
        raise ValueError('Malformed public diplomatic relationship')
    expected = {'DIPLO_STATE_DENOUNCED': 'denunciation',
                'DIPLO_STATE_DECLARED_FRIEND': 'friendship'}.get(value['state'])
    expiration = value['expiration']
    if expiration is None:
        if expected is None:
            return
        raise ValueError('Public diplomatic relationship is missing its displayed expiration')
    if (type(expiration) is not dict or set(expiration) != {'kind', 'turns_remaining', 'denouncer_player_id'}
            or (expiration['kind'] != expected and expiration['kind'] != 'alliance')
            or expiration['kind'] not in ('denunciation', 'friendship', 'alliance')
            or not _signed_integer(expiration['turns_remaining'])):
        raise ValueError('Malformed public diplomatic expiration')
    initiator = expiration['denouncer_player_id']
    if ((expiration['kind'] == 'denunciation'
         and (type(initiator) is not int or initiator not in (player_id, target_id)))
            or (expiration['kind'] != 'denunciation' and initiator is not None)):
        raise ValueError('Public diplomatic expiration belongs to another player')


def validate_action(action):
    if (type(action) is not dict or set(action) != ACTION_FIELDS['diplomacy_initiate']
            or action['kind'] != 'diplomacy_initiate'
            or type(action['target_player_id']) is not int
            or not 0 <= action['target_player_id'] < 64
            or type(action['choice']) is not str
            or re.fullmatch(r'CHOICE_[A-Z0-9_]{1,96}', action['choice']) is None):
        raise ValueError('Malformed initial diplomatic action')
    return action


def _validate_deals(rows, targets, *, draft, open_borders=False, demand=False,
                    major_peace=False, stock_peace=False, direct_ai_choices=(), promise_status=False):
    if type(rows) is not list or len(rows) != len(targets):
        raise ValueError('Missing public deals for the current major targets')
    count = 0
    fields = {'player_id', 'pending', 'terms'}
    if draft:
        fields.add('counterparty_is_human')
    if open_borders:
        fields.add('open_borders')
    for row, target in zip(rows, targets):
        if (type(row) is not dict or set(row) != fields
                or type(row['player_id']) is not int or row['player_id'] != target['player_id']
                or type(row['pending']) is not bool or type(row['terms']) is not list):
            raise ValueError('Malformed public deal or foreign counterparty')
        if draft:
            human = row['counterparty_is_human']
            opening = ((MAKE_PEACE,) if stock_peace else
                       (OPEN_DEAL, OPEN_DEMAND) if demand else (OPEN_DEAL,))
            if major_peace and not stock_peace:
                opening += (MAKE_PEACE,)
            if (type(human) is not bool
                    or any(s['supported'] != (not human and not row['pending'])
                           for s in target['selections'] if s['key'] in opening)):
                raise ValueError('Public deal opening must match its counterparty and pending status')
            if human and any(s['key'] in direct_ai_choices and s['supported'] for s in target['selections']):
                raise ValueError('Stock direct request currently requires an AI counterparty')
            if promise_status and (target['active_promises'] is None) != human:
                raise ValueError('Stock promise status crossed the counterparty controller boundary')
        if open_borders:
            rights = row['open_borders']
            if (type(rights) is not dict or set(rights) != {'outgoing','incoming'}
                    or any(type(v) is not bool for v in rights.values())):
                raise ValueError('Invalid public open-borders rights')
        count += len(row['terms'])
        if count > MAX_DEAL_TERMS:
            raise ValueError('Public deal terms exceed their wire bound')
        for item in row['terms']:
            if (type(item) is not dict or set(item) !=
                    {'direction', 'kind', 'amount', 'remaining_turns', 'resource_index'}
                    or item['direction'] not in ('outgoing', 'incoming')
                    or not _signed_integer(item['amount']) or not _signed_integer(item['remaining_turns'])
                    or item['kind'] not in ('gold', 'resource')
                    or (item['kind'] == 'gold' and item['resource_index'] is not None)
                    or (item['kind'] == 'resource' and
                        (not _signed_integer(item['resource_index']) or item['resource_index'] < 0))):
                raise ValueError('Malformed public deal term')


def validate(value, player_id, turn):
    schema = value.get('schema') if type(value) is dict else None
    fields = _FIELDS.copy()
    if schema in CITY_STATE_SCHEMAS:
        fields.add('city_state_peace')
    if schema in MAJOR_DEAL_SCHEMAS:
        fields.add('major_deals')
    if (type(value) is not dict or set(value) != fields or schema not in SCHEMAS
            or type(player_id) is not int or not 0 <= player_id < 64
            or type(turn) is not int or turn < 0
            or type(value['player_id']) is not int or value['player_id'] != player_id
            or type(value['turn']) is not int or value['turn'] != turn
            or type(value['capability']) is not bool or type(value['paused']) is not bool
            or value['complete_action_space'] is not False
            or type(value['targets']) is not list or len(value['targets']) > 63):
        raise ValueError('Malformed or foreign public diplomacy overview')
    players = set()
    stock_peace = schema == STOCK_MAJOR_PEACE_SCHEMA
    promise_status = schema in STOCK_PROMISE_STATUS_SCHEMAS
    stock_options = {
        STOCK_MAJOR_PEACE_SCHEMA: (DENOUNCE, MAKE_PEACE),
        STOCK_NEGOTIATION_SCHEMA: (DENOUNCE, MAKE_PEACE, OPEN_DEAL, OPEN_DEMAND),
        STOCK_FRIENDSHIP_SCHEMA: (DENOUNCE, MAKE_PEACE, OPEN_DEAL, OPEN_DEMAND, DECLARE_FRIENDSHIP),
        STOCK_PROMISE_SCHEMA: (DENOUNCE, MAKE_PEACE, OPEN_DEAL, OPEN_DEMAND, DECLARE_FRIENDSHIP, *PROMISE_CHOICES),
        **{name: (DENOUNCE, MAKE_PEACE, OPEN_DEAL, OPEN_DEMAND, DECLARE_FRIENDSHIP, *PROMISE_CHOICES)
           for name in STOCK_PROMISE_STATUS_SCHEMAS},
    }.get(schema)
    target_fields = {'player_id', 'selections'}
    if schema != SCHEMA:
        target_fields.add('relationship')
    if promise_status:
        target_fields.add('active_promises')
    for target in value['targets']:
        if (type(target) is not dict or set(target) != target_fields
                or type(target['player_id']) is not int
                or not 0 <= target['player_id'] < 64
                or target['player_id'] == player_id or target['player_id'] in players
                or type(target['selections']) is not list or len(target['selections']) > 64):
            raise ValueError('Invalid or duplicate diplomacy target')
        players.add(target['player_id'])
        if schema != SCHEMA:
            _validate_relationship(target['relationship'], player_id, target['player_id'])
        if promise_status and target['active_promises'] is not None:
            active = target['active_promises']
            if type(active) is not list or active != [kind for kind in PROMISE_TYPES if kind in active]:
                raise ValueError('Invalid public active promises')
        keys = set()
        for selection in target['selections']:
            if (type(selection) is not dict or set(selection) != _SELECTION
                    or type(selection['key']) is not str
                    or re.fullmatch(r'CHOICE_[A-Z0-9_]{1,96}', selection['key']) is None
                    or selection['key'] in keys
                    or type(selection['disabled']) is not bool
                    or type(selection['supported']) is not bool
                    or (stock_options is not None and selection['supported'] and selection['key'] not in stock_options)
                    or (schema in CITY_STATE_SCHEMAS and schema not in MAJOR_PEACE_SCHEMAS and selection['key'] == MAKE_PEACE
                        and selection['supported'])
                    or any(selection[k] is not None and
                           (type(selection[k]) is not str or len(selection[k]) > 4096)
                           for k in ('text', 'tooltip', 'diplomatic_action_type'))):
                raise ValueError('Invalid or duplicate diplomacy selection')
            keys.add(selection['key'])
    if schema in CITY_STATE_SCHEMAS:
        validate_city_state_peace(value['city_state_peace'], player_id, excluded=players)
    if schema in MAJOR_DEAL_SCHEMAS:
        _validate_deals(value['major_deals'], value['targets'], draft=stock_peace or schema in DRAFT_SCHEMAS,
                        open_borders=schema in BORDERS_SCHEMAS, demand=schema in DEMAND_SCHEMAS,
                        major_peace=schema in MAJOR_PEACE_SCHEMAS, stock_peace=stock_peace,
                        direct_ai_choices=STOCK_DIRECT_AI_CHOICES.get(schema, ()), promise_status=promise_status)
    return value


def validate_city_state_peace(peace, player_id, *, excluded=()):
    players = set(excluded)
    if (type(peace) is not dict or set(peace) != {'military_enabled', 'targets'}
            or type(peace['military_enabled']) is not bool or type(peace['targets']) is not list
            or len(peace['targets']) + len(players) > 63
            or (not peace['military_enabled'] and peace['targets'])):
        raise ValueError('Malformed city-state peace panel')
    for row in peace['targets']:
        if (type(row) is not dict or set(row) != {'player_id', 'at_war', 'can_make_peace'}
                or type(row['player_id']) is not int or not 0 <= row['player_id'] < 64
                or row['player_id'] == player_id or row['player_id'] in players
                or type(row['at_war']) is not bool or type(row['can_make_peace']) is not bool
                or (row['can_make_peace'] and not row['at_war'])):
            raise ValueError('Invalid or duplicate city-state peace target')
        players.add(row['player_id'])
    return peace


def city_state_peace_actions(peace, player_id):
    validate_city_state_peace(peace, player_id)
    return [dict(kind='diplomacy_initiate', target_player_id=row['player_id'], choice=MAKE_PEACE)
            for row in peace['targets'] if row['can_make_peace']]


def project_legacy(value, player_id, turn, *, schema=SCHEMA):
    validate(value, player_id, turn)
    if (schema not in SCHEMAS or SCHEMAS.index(schema) >= SCHEMAS.index(value['schema'])
            or (value['schema'] in STOCK_SCHEMAS and schema not in (RELATIONSHIPS_SCHEMA, *STOCK_SCHEMAS))):
        raise ValueError('Expected a historical XP2 diplomacy overview version')
    projected = dict(value, schema=schema)
    if schema not in MAJOR_DEAL_SCHEMAS:
        projected.pop('major_deals', None)
    elif schema == STOCK_MAJOR_PEACE_SCHEMA:
        projected['major_deals'] = [{k:v for k,v in row.items() if k!='open_borders'} for row in value['major_deals']]
    elif schema not in DRAFT_SCHEMAS:
        projected['major_deals'] = [dict(player_id=r['player_id'], pending=r['pending'], terms=r['terms'])
                                    for r in value['major_deals']]
    elif schema == DEAL_DRAFT_SCHEMA:
        projected['major_deals'] = [{k:v for k,v in row.items() if k!='open_borders'} for row in value['major_deals']]
    if schema not in CITY_STATE_SCHEMAS:
        projected.pop('city_state_peace', None)
    if schema == SCHEMA:
        projected['targets'] = [dict(player_id=row['player_id'], selections=row['selections'])
                                for row in value['targets']]
    elif value['schema'] in STOCK_PROMISE_STATUS_SCHEMAS and schema not in STOCK_PROMISE_STATUS_SCHEMAS:
        projected['targets'] = [{k: v for k, v in row.items() if k != 'active_promises'}
                                for row in value['targets']]
    removed = set()
    if value['schema'] in DRAFT_SCHEMAS and schema not in DRAFT_SCHEMAS:
        removed.add(OPEN_DEAL)
    if value['schema'] in DEMAND_SCHEMAS and schema not in DEMAND_SCHEMAS:
        removed.add(OPEN_DEMAND)
    if value['schema'] in MAJOR_PEACE_SCHEMAS and schema not in MAJOR_PEACE_SCHEMAS:
        removed.add(MAKE_PEACE)
    removed.update(STOCK_DIRECT_AI_CHOICES.get(value['schema'], frozenset())
                   .difference(STOCK_DIRECT_AI_CHOICES.get(schema, ())))
    if removed:
        projected['targets'] = [
            dict(row, selections=[dict(s, supported=False) if s['key'] in removed else s
                                  for s in row['selections']]) for row in projected['targets']]
    return validate(projected, player_id, turn)


def candidates(value):
    if type(value) is not dict:
        raise ValueError('Missing public diplomacy overview')
    validate(value, value.get('player_id'), value.get('turn'))
    if value['paused']:
        return []
    targets = value['targets'] if value['capability'] else []
    result = [dict(kind='diplomacy_initiate', target_player_id=target['player_id'],
                   choice=selection['key'])
              for target in targets for selection in target['selections']
              if selection['supported'] and not selection['disabled']]
    peace = value.get('city_state_peace')
    if peace is not None:
        result.extend(city_state_peace_actions(peace, value['player_id']))
    return result
