"""Named public information groups over an accepted player decision boundary.

This layer composes existing source-bound/public validators. It does not
select model features, make native calls, or alter the existing decision wire.
"""
from __future__ import annotations

import copy
import math
import re
from collections.abc import Mapping

from civ6_host.contracts import city_growth, economy_inputs, production_inputs
from civ6_host.contracts import unit_work_info, unit_work_state
from . import network_turn


PUBLIC_GROUPS = ('economy', 'production', 'growth', 'unit_work', 'combat', 'display', 'strategic_resources')
COMBAT_GROUP_SCHEMA='civ6-host.combat-inputs.v1'
PRODUCTION_GROUP_SCHEMA = 'civ6-host.production-inputs.v1'
CURRENT_PRODUCTION_GROUP_SCHEMA = 'civ6-host.production-inputs.v2'
UNIT_WORK_GROUP_SCHEMA = 'civ6-host.unit-work-inputs.v1'
UNIT_WORK_CATALOGUE_GROUP_SCHEMA = 'civ6-host.unit-work-inputs.v2'
UNIT_WORK_DETAILED_GROUP_SCHEMA = 'civ6-host.unit-work-inputs.v3'
_REQUIRED_FIELDS = {
    'display': (),
    'economy': ('treasury', 'yield_display', 'research_info', 'research', 'candidates'),
    'production': ('production', 'production_info', 'production_queues', 'candidates'),
    'growth': ('city_growth',),
    'strategic_resources': ('strategic_resources',),
    'combat': ('unit_attacks','queued_orders'),
    'unit_work': ('unit_work_state', 'unit_work_info', 'unit_work'),
}
_EVENT_IDENTITY_FIELDS = {'stage', 'episode_id', 'game_generation', 'player_id',
                          'sequence', 'turn', 'source_sha256', 'actor_channel'}
_PRODUCTION_RAW_ROW_FIELDS = {'city_id', 'owner_id', 'queue_size',
    'current_production_hash', 'previous_production_hash', 'production_yield',
    'has_production_progress', 'turns_left', 'kind', 'item_index', 'cost',
    'progress', 'formation'}


def required_fields(group: str, decision_schema=None) -> tuple[str, ...]:
    """Return the exact decision-side fields a group needs at this boundary."""
    if type(group) is not str or group not in _REQUIRED_FIELDS:
        raise ValueError(f'Unknown public information group: {group!r}')
    if group == 'unit_work' and decision_schema == network_turn.CAPABILITY_UNIT_WORK_STATE_SCHEMA:
        return ('unit_work_state', 'unit_work')
    if group == 'production' and decision_schema in network_turn.CURRENT_PRODUCTION_CAPABILITY_SCHEMAS:
        return ('production_current', 'production_queues')
    return _REQUIRED_FIELDS[group]


def project(group: str, observation, decisions) -> dict:
    """Validate and copy one public group from a same-boundary observation.

    The caller supplies the exact accepted decision boundary. Session-level
    validation remains responsible for native queue catalogue validation;
    this function additionally binds production queue heads to the public
    current-production display and own-city roster.
    """
    if group == 'display':
        raise ValueError('Display information requires the same cached versioned public envelope')
    if not isinstance(decisions, Mapping):
        raise ValueError('decisions must be an object')
    fields = required_fields(group, decisions.get('schema'))
    missing = [field for field in fields if field not in decisions]
    if missing:
        raise ValueError(f'{group} information is unavailable; missing {", ".join(missing)}')
    if not isinstance(observation, Mapping):
        raise ValueError('observation must be an object')
    player_id, turn = observation.get('player_id'), observation.get('turn')
    if type(player_id) is not int or not 0 <= player_id <= 63 or type(turn) is not int or turn < 0:
        raise ValueError('information observation identity is malformed')

    if group == 'economy':
        return economy_inputs.project(observation, decisions)

    if group == 'strategic_resources':
        from . import strategic_resources
        return copy.deepcopy(strategic_resources.validate(decisions['strategic_resources'], player_id, turn))

    if group == 'production':
        if decisions.get('schema') in network_turn.CURRENT_PRODUCTION_CAPABILITY_SCHEMAS:
            current = production_inputs.validate_current(decisions['production_current'], player_id, turn,
                observation=observation, queues=decisions['production_queues'])
            return {'schema': CURRENT_PRODUCTION_GROUP_SCHEMA, 'current': copy.deepcopy(current),
                    'queues': copy.deepcopy(decisions['production_queues'])}
        current = production_inputs.validate_current(decisions['production'], player_id, turn,
            observation=observation, queues=decisions['production_queues'])
        info = decisions['production_info']
        if type(info) is dict and info.get('schema') == production_inputs.INFO_SCHEMA:
            quotes = production_inputs.validate_quotes(info, player_id, turn,
                candidates=decisions['candidates'], observation=observation)
        else:
            quotes = production_inputs.project_quotes(info, player_id, turn,
                candidates=decisions['candidates'], observation=observation)
        # Queue catalogues were already strictly validated by the accepted
        # action session. Preserve their complete canonical UI fields here.
        return {
            'schema': PRODUCTION_GROUP_SCHEMA,
            'current': copy.deepcopy(current),
            'quotes': copy.deepcopy(quotes),
            'queues': copy.deepcopy(decisions['production_queues']),
        }

    if group == 'combat':
        from .capability_unit_attacks import validate_public_catalog
        if decisions.get('schema') not in network_turn.PUBLIC_COMBAT_CAPABILITY_SCHEMAS:
            raise ValueError('Historical raw combat catalogue is not a qualified public projection')
        value=validate_public_catalog(decisions['unit_attacks'],player_id,turn,
            observation=observation,queued_orders=decisions['queued_orders'])
        if value is None or decisions['queued_orders'] is None:
            raise ValueError('Public combat information is unavailable')
        return {'schema':COMBAT_GROUP_SCHEMA,'unit_attacks':copy.deepcopy(value),
                'queued_orders':copy.deepcopy(decisions['queued_orders'])}

    if group == 'growth':
        value = city_growth.validate(decisions['city_growth'], player_id, turn,
                                     observation=observation)
        return copy.deepcopy(value)

    catalog = decisions['unit_work']
    if decisions.get('schema') in network_turn.UNIT_WORK_STATE_CAPABILITY_SCHEMAS:
        from .unit_work import validate_network_catalog
        validate_network_catalog(catalog, player_id, turn, observation=observation)
        state = unit_work_state.validate(decisions['unit_work_state'], player_id, turn,
            observation=observation, work_catalog=catalog, include_plot=True)
        result = {'schema': UNIT_WORK_CATALOGUE_GROUP_SCHEMA, 'state': copy.deepcopy(state),
                  'catalogue': copy.deepcopy(catalog)}
        if decisions['schema'] != network_turn.CAPABILITY_UNIT_WORK_STATE_SCHEMA:
            info = unit_work_info.validate(decisions['unit_work_info'], player_id, turn,
                observation=observation, work_catalog=catalog, work_state=state)
            result.update(schema=UNIT_WORK_DETAILED_GROUP_SCHEMA, info=copy.deepcopy(info))
        return result
    state = unit_work_state.validate(decisions['unit_work_state'], player_id, turn,
        observation=observation, work_catalog=catalog)
    info = unit_work_info.validate(decisions['unit_work_info'], player_id, turn,
        work_catalog=catalog, observation=observation)
    return {'schema': UNIT_WORK_GROUP_SCHEMA, 'state': copy.deepcopy(state),
            'info': copy.deepcopy(info)}


def _event_number(value, label):
    if type(value) not in (int, float):
        raise ValueError(f'{label} must be finite')
    try:
        finite = math.isfinite(value)
    except OverflowError:
        finite = False
    if not finite:
        raise ValueError(f'{label} must be finite')
    return value


def _response_boundary(response):
    if not isinstance(response, Mapping):
        raise ValueError('administrative response must be an object')
    observation = response.get('observation')
    decisions = response.get('decisions')
    if not isinstance(observation, Mapping) or not isinstance(decisions, Mapping):
        raise ValueError('administrative response lacks the exact public boundary')
    episode_id = response.get('episode_id')
    game_generation = response.get('game_generation')
    sequence = response.get('sequence')
    player_id, turn = observation.get('player_id'), observation.get('turn')
    if (type(episode_id) is not str or not episode_id
            or type(game_generation) is not str or not game_generation
            or type(sequence) is not int or sequence < 0
            or type(player_id) is not int or not 0 <= player_id <= 63
            or type(turn) is not int or turn < 0):
        raise ValueError('administrative response identity is malformed')
    return observation, decisions, episode_id, game_generation, sequence, player_id, turn


def _validate_raw_production_snapshot(value, player_id, turn, observation):
    if (type(value) is not dict or set(value) != {'player_id', 'game_turn', 'cities'}
            or type(value['player_id']) is not int or value['player_id'] != player_id
            or type(value['game_turn']) is not int or value['game_turn'] != turn
            or type(value['cities']) is not list or len(value['cities']) > 4096):
        raise ValueError('Malformed native production snapshot')
    own_ids = sorted(city['id'] for city in observation['cities']
                     if type(city) is dict and city.get('owner') == player_id)
    ids = []
    signed = ('current_production_hash', 'previous_production_hash',
              'production_yield', 'turns_left')
    for pos, row in enumerate(value['cities']):
        if type(row) is not dict or set(row) != _PRODUCTION_RAW_ROW_FIELDS:
            raise ValueError(f'Native production city {pos} has unknown or missing fields')
        cid = row['city_id']
        if type(cid) is not int or not 0 <= cid <= 0xFFFFFFFF:
            raise ValueError('Invalid native production city identity')
        ids.append(cid)
        if type(row['owner_id']) is not int or row['owner_id'] != player_id:
            raise ValueError('Foreign native production city')
        for key in signed:
            if type(row[key]) is not int or not -(1 << 31) <= row[key] < (1 << 31):
                raise ValueError(f'Invalid native production {key}')
        if type(row['queue_size']) is not int or not 0 <= row['queue_size'] <= 65535:
            raise ValueError('Invalid native production queue size')
        if type(row['has_production_progress']) is not bool:
            raise ValueError('Invalid native production progress flag')
        kind = row['kind']
        if kind not in ('N', 'U', 'B', 'D', 'P'):
            raise ValueError('Invalid native production kind')
        if kind == 'N':
            if any(row[k] is not None for k in ('item_index', 'cost', 'progress', 'formation')):
                raise ValueError('Empty native production row contains item data')
        else:
            if (type(row['item_index']) is not int or not 0 <= row['item_index'] <= 0xFFFFFFFF
                    or type(row['cost']) is not int or not -1 <= row['cost'] < (1 << 31)
                    or type(row['progress']) is not int or not -1 <= row['progress'] < (1 << 31)):
                raise ValueError('Invalid native production item values')
            if kind == 'U':
                if type(row['formation']) is not int or not 0 <= row['formation'] < (1 << 31):
                    raise ValueError('Invalid native unit formation')
            elif row['formation'] is not None:
                raise ValueError('Non-unit production has formation data')
    if ids != sorted(set(ids)) or ids != own_ids:
        raise ValueError('Native production city roster differs from own observation')
    return value


def validate_administrative(group, event, response, source_sha256=None):
    """Validate a raw native readback event against its exact public response.

    This only verifies same-boundary and source provenance. The returned
    detached event remains administrative evidence and is not an actor view.
    """
    if group not in ('production', 'growth', 'combat', 'turn_horizon'):
        raise ValueError(f'Unknown administrative information group: {group!r}')
    observation, decisions, episode_id, game_generation, sequence, player_id, turn = _response_boundary(response)
    if type(event) is not dict:
        raise ValueError('administrative event must be an object')
    payload_fields = {
        'production': {'production', 'production_info', 'public_production'},
        'growth': {'cities'}, 'combat': {'cities'}, 'turn_horizon': {'end_turn'},
    }[group]
    if set(event) != _EVENT_IDENTITY_FIELDS | payload_fields:
        raise ValueError('administrative event has unknown or missing fields')
    expected_stage = {'production':'native_production_administrative_readback',
                      'growth':'native_city_growth_administrative_readback',
                      'combat':'native_combat_administrative_readback',
                      'turn_horizon':'xp2_saved_end_turn_observed'}[group]
    if event['stage'] != expected_stage:
        raise ValueError('administrative event stage differs')
    for key, expected in (('episode_id', episode_id), ('game_generation', game_generation),
                          ('player_id', player_id), ('sequence', sequence), ('turn', turn)):
        if type(event[key]) is not type(expected) or event[key] != expected:
            raise ValueError(f'administrative event {key} differs from response')
    if event['actor_channel'] is not False:
        raise ValueError('administrative event cannot enter the actor channel')
    pin = event['source_sha256']
    if type(pin) is not str or re.fullmatch(r'[0-9a-f]{64}', pin) is None:
        raise ValueError('administrative source hash must be lowercase SHA-256')
    if source_sha256 is not None and (type(source_sha256) is not str or pin != source_sha256):
        raise ValueError('administrative source hash differs from expected pin')

    if group == 'turn_horizon':
        if (response.get('operation') != 'reset' or sequence != 0
                or type(event['end_turn']) is not int or not -(2**31) <= event['end_turn'] < 2**31):
            raise ValueError('Native end turn requires the exact reset boundary and signed integer')
        return copy.deepcopy(event)
    if group == 'combat':
        from .capability_unit_attacks import project_cities,PUBLIC_PRECISION_SHA256
        public=project('combat',observation,decisions)['unit_attacks']
        from .network_turn import combat_checkpoint_sources,_XP2_COMBAT_CORE
        if pin not in (PUBLIC_PRECISION_SHA256,combat_checkpoint_sources(_XP2_COMBAT_CORE)[0]):
            raise ValueError('Combat precision source differs from its selected public contract')
        cities=project_cities(event['cities'],public['width'],public['height'])
        if cities!=public['cities']:
            raise ValueError('Native combat cities differ from the exact public projection')
    elif group == 'production':
        public_current = production_inputs.validate_current(decisions.get('production'), player_id, turn,
            observation=observation, queues=decisions.get('production_queues'))
        public_quotes = production_inputs.validate_quotes(decisions.get('production_info'), player_id, turn,
            candidates=decisions.get('candidates'), observation=observation)
        _validate_raw_production_snapshot(event['production'], player_id, turn, observation)
        current = production_inputs.validate_current(event['public_production'], player_id, turn,
            observation=observation, queues=decisions.get('production_queues'))
        if current != public_current:
            raise ValueError('Readback production display differs from response')
        quotes = production_inputs.project_quotes(event['production_info'], player_id, turn,
            candidates=decisions.get('candidates'), observation=observation)
        if quotes != public_quotes:
            raise ValueError('Readback production quotes differ from response')
    else:
        public = city_growth.validate(decisions.get('city_growth'), player_id, turn,
                                      observation=observation)
        rows = event['cities']
        if type(rows) is not list or len(rows) > 4096:
            raise ValueError('Native growth readback cities are malformed or oversized')
        own_ids = sorted(city['id'] for city in observation['cities']
                         if type(city) is dict and city.get('owner') == player_id)
        ids = []
        fields = {'city_id', 'food_stock', 'growth_threshold', 'food_surplus',
                  'turns_until_growth', 'turns_until_starvation'}
        for pos, row in enumerate(rows):
            if type(row) is not dict or set(row) != fields:
                raise ValueError(f'Native growth city {pos} has unknown or missing fields')
            cid = row['city_id']
            if type(cid) is not int or not 0 <= cid <= 0xFFFFFFFF:
                raise ValueError('Invalid native growth city identity')
            ids.append(cid)
            for key in ('food_stock', 'growth_threshold', 'food_surplus'):
                _event_number(row[key], f'native growth {key}')
            for key in ('turns_until_growth', 'turns_until_starvation'):
                if type(row[key]) is not int or not -(1 << 31) <= row[key] < (1 << 31):
                    raise ValueError(f'Invalid native growth {key}')
        if ids != sorted(set(ids)) or ids != own_ids:
            raise ValueError('Native growth city roster differs from own observation')
        if ids != [row['city_id'] for row in public['cities']]:
            raise ValueError('Native growth readback roster differs from public growth')
    return copy.deepcopy(event)


__all__ = ['PUBLIC_GROUPS', 'PRODUCTION_GROUP_SCHEMA', 'UNIT_WORK_GROUP_SCHEMA', 'COMBAT_GROUP_SCHEMA',
           'required_fields', 'project', 'validate_administrative']


def project_cached_display(public_view):
    """Reuse the accepted cache; never perform a new collection or inversion."""
    from .player_display import display_information
    return display_information(public_view)
