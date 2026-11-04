"""Public numerical economy inputs and an explicitly administrative snapshot.

This module only projects already validated native/UI snapshots. It does not
read native state, format locale text, or reconstruct hidden getter values.
Yield numbers retain one decimal of native UI precision. A displayed 999
research turn count is ambiguous between exactly 999 and the UI cap; the
public ``turns_capped`` flag records only that the displayed count is 999.
Selected research progress remains administrative until its public precision
and presentation are established.
"""
from __future__ import annotations

import copy
import math
from collections.abc import Mapping

from civ6_host.contracts import research_info983, yield_display982


SCHEMA = 'civ6-host.economy-inputs.v1'
ADMIN_SCHEMA = 'civ6-host.economy-administrative.v1'
ADMIN_ONLY = ('economy', 'city_yields', 'treasury', 'yield_display',
              'research_info', 'research_progress')
_CITY_YIELDS = yield_display982.CITY_YIELDS
_MAX_CITIES = 4096
_MAX_CHOICES = research_info983.MAX_CHOICES
_ROW_FIELDS = {'index', 'hash', 'cost', 'turns_left', 'boosted', 'turns_capped'}


def _fields(value, expected, label):
    if not isinstance(value, Mapping) or set(value) != set(expected):
        raise ValueError(f'{label} has unknown or missing fields')
    return value


def _number(value, label):
    if type(value) not in (int, float):
        raise ValueError(f'{label} must be a finite number')
    try:
        finite = math.isfinite(value)
    except OverflowError:
        finite = False
    if not finite:
        raise ValueError(f'{label} must be a finite number')
    return value


def _integer(value, label, low=0, high=None):
    if (type(value) is not int or (low is not None and value < low)
            or (high is not None and value > high)):
        raise ValueError(f'{label} must be an integer in range')
    return value


def _public_tenth(value, label):
    value = _number(value, label)
    try:
        scaled = value * 10
        finite = math.isfinite(scaled)
    except OverflowError:
        finite = False
        scaled = 0
    if not finite or abs(scaled - round(scaled)) > 1e-9:
        raise ValueError(f'{label} must use at most one decimal place')
    return value


def _identity(observation, player_id, turn):
    _fields(observation, {'schema', 'player_id', 'turn', 'width', 'height', 'plots',
                          'units', 'visible_enemy_units', 'cities', 'economy'}, 'observation')
    if (observation['schema'] != yield_display982.OBSERVATION_SCHEMA
            or type(observation['player_id']) is not int or observation['player_id'] != player_id
            or type(observation['turn']) is not int or observation['turn'] != turn):
        raise ValueError('economy observation identity mismatch')


def _treasury_snapshot(value, player_id, turn, observation=None):
    _fields(value, {'schema', 'player_id', 'turn', 'gold_balance', 'gold_yield',
                    'total_maintenance', 'net_gold_yield', 'public_display'}, 'treasury')
    if (value['schema'] != 'civ6rl.native_saved_treasury980.v1'
            or type(value['player_id']) is not int or value['player_id'] != player_id
            or type(value['turn']) is not int or value['turn'] != turn):
        raise ValueError('treasury identity or schema mismatch')
    balance = _number(value['gold_balance'], 'treasury gold balance')
    income = _number(value['gold_yield'], 'treasury gold yield')
    maintenance = _number(value['total_maintenance'], 'treasury maintenance')
    net = _number(value['net_gold_yield'], 'treasury net yield')
    if net != income - maintenance:
        raise ValueError('treasury net yield differs from income minus maintenance')
    display = _fields(value['public_display'], {'schema', 'gold_balance', 'gold_yield',
                     'gold_expense', 'net_gold_yield'}, 'treasury public display')
    if display['schema'] != 'civ6rl.native_treasury_display980.v1':
        raise ValueError('treasury display schema mismatch')
    if type(display['gold_balance']) is not int or display['gold_balance'] != math.floor(balance):
        raise ValueError('treasury displayed balance differs from native balance')
    for key, native in (('gold_yield', income), ('gold_expense', -maintenance),
                        ('net_gold_yield', net)):
        shown = yield_display982.public_number(display[key])
        if abs(shown - native) > 0.100000001:
            raise ValueError(f'treasury displayed {key} differs from native value')
    if observation is not None:
        observed_balance = _number(observation['economy'].get('gold'), 'observation gold')
        if observed_balance != balance:
            raise ValueError('treasury balance differs from player observation')
    return value


def _research_snapshot(value, player_id, turn, decisions):
    selected = decisions.get('research')
    if type(selected) is not dict or set(selected) != {'research', 'civic'}:
        raise ValueError('research selections are malformed')
    candidates = decisions.get('candidates')
    return research_info983.validate(value, player_id, turn, research=selected,
                                     candidates=candidates)


def _project_research(value):
    result = {}
    for topic in ('technology', 'civic'):
        source = value[topic]

        def row(item):
            shown = item['turns_display']
            return {'index': item['index'], 'hash': item['hash'], 'cost': item['cost'],
                    'turns_left': shown, 'boosted': item['boosted'],
                    'turns_capped': shown == 999}

        result[topic] = {
            'selected': source['selected'],
            'selected_info': None if source['selected_info'] is None else row(source['selected_info']),
            'choices': [row(item) for item in source['choices']],
        }
    return result


def project(observation, decisions) -> dict:
    """Project validated native snapshots into public numerical inputs."""
    if not isinstance(decisions, Mapping):
        raise ValueError('decisions must be an object')
    player_id = _integer(observation.get('player_id') if isinstance(observation, Mapping) else None,
                         'observation player_id', high=63)
    turn = _integer(observation.get('turn') if isinstance(observation, Mapping) else None,
                    'observation turn')
    _identity(observation, player_id, turn)
    treasury = _treasury_snapshot(decisions.get('treasury'), player_id, turn, observation)
    yields = yield_display982.validate(decisions.get('yield_display'), player_id, turn, observation)
    research = _research_snapshot(decisions.get('research_info'), player_id, turn, decisions)
    display = treasury['public_display']
    public = {
        'schema': SCHEMA, 'player_id': player_id, 'turn': turn,
        'treasury': {
            'gold_balance': display['gold_balance'],
            'gold_yield': yield_display982.public_number(display['gold_yield']),
            'gold_expense': yield_display982.public_number(display['gold_expense']),
            'net_gold_yield': yield_display982.public_number(display['net_gold_yield']),
        },
        'global_yields': {key: yield_display982.public_number(yields['public_display'][key])
                          for key in yield_display982.GLOBAL_YIELDS},
        'cities': [{'city_id': city['city_id'],
                    'yields': {key: yield_display982.public_number(city['public_display'][key])
                               for key in _CITY_YIELDS}}
                   for city in yields['cities']],
        'research': _project_research(research),
    }
    return validate(public, player_id, turn, observation=observation,
                    candidates=decisions.get('candidates'))


def _public_row(value, label):
    row = _fields(value, _ROW_FIELDS, label)
    index = _integer(row['index'], f'{label}.index', high=0xFFFFFFFF)
    native_hash = _integer(row['hash'], f'{label}.hash', high=0xFFFFFFFF)
    cost = _integer(row['cost'], f'{label}.cost', high=0x7FFFFFFF)
    turns = row['turns_left']
    if turns is not None:
        _integer(turns, f'{label}.turns_left', high=999)
    capped = row['turns_capped']
    boosted = row['boosted']
    if type(capped) is not bool or type(boosted) is not bool:
        raise ValueError(f'{label} flags must be boolean')
    if capped != (turns == 999):
        raise ValueError(f'{label}.turns_capped differs from displayed turn count')
    return {'index': index, 'hash': native_hash, 'cost': cost,
            'turns_left': turns, 'boosted': boosted, 'turns_capped': capped}


def _validate_research(value, candidates):
    research = _fields(value, {'technology', 'civic'}, 'research')
    normalized = {}
    for topic, kind in (('technology', 'research'), ('civic', 'civic')):
        source = _fields(research[topic], {'selected', 'selected_info', 'choices'}, topic)
        selected = source['selected']
        if selected is not None:
            _integer(selected, f'{topic}.selected', high=0xFFFFFFFF)
        selected_info = None if source['selected_info'] is None else _public_row(
            source['selected_info'], f'{topic}.selected_info')
        if (selected is None) != (selected_info is None) or (selected_info is not None
                and selected_info['index'] != selected):
            raise ValueError(f'{topic} selected information does not match selection')
        choices = source['choices']
        if type(choices) is not list or len(choices) > _MAX_CHOICES:
            raise ValueError(f'{topic}.choices is malformed or oversized')
        parsed, seen_hash, previous = [], set(), -1
        for pos, choice in enumerate(choices):
            item = _public_row(choice, f'{topic}.choices[{pos}]')
            if item['index'] <= previous or item['hash'] in seen_hash:
                raise ValueError(f'{topic}.choices contain duplicate or unsorted rows')
            parsed.append(item)
            previous = item['index']
            seen_hash.add(item['hash'])
        if selected_info is not None:
            matching = [item for item in parsed if item['index'] == selected]
            if matching and matching[0] != selected_info:
                raise ValueError(f'{topic}.selected_info differs from offered choice')
        normalized[topic] = {'selected': selected, 'selected_info': selected_info,
                             'choices': parsed}
        if candidates is not None:
            if type(candidates) is not list or len(candidates) > 131072:
                raise ValueError('candidates must be a bounded list')
            expected = {(item['index'], item['hash']) for item in parsed}
            actual = set()
            candidate_ids = set()
            for candidate in candidates:
                candidate = _fields(candidate, {'candidate_id', 'action'}, 'candidate')
                candidate_id = candidate['candidate_id']
                if type(candidate_id) is not str or not candidate_id or candidate_id in candidate_ids:
                    raise ValueError('candidate id must be unique and non-empty')
                candidate_ids.add(candidate_id)
                action = candidate['action']
                if not isinstance(action, Mapping) or type(action.get('kind')) is not str:
                    raise ValueError('candidate action is malformed')
                if action['kind'] != kind:
                    continue
                _fields(action, {'kind', 'index', 'hash'}, f'{kind} candidate action')
                pair = (_integer(action['index'], f'{kind} candidate index', high=0xFFFFFFFF),
                        _integer(action['hash'], f'{kind} candidate hash', high=0xFFFFFFFF))
                if pair in actual:
                    raise ValueError(f'duplicate {kind} candidate')
                actual.add(pair)
            if actual != expected:
                raise ValueError(f'{kind} candidates differ from public research choices')
    return normalized


def validate(value, player_id: int, turn: int, observation=None, candidates=None) -> dict:
    """Validate and normalize the public economy/research input payload."""
    _integer(player_id, 'player_id', high=63)
    _integer(turn, 'turn')
    row = _fields(value, {'schema', 'player_id', 'turn', 'treasury', 'global_yields',
                          'cities', 'research'}, 'economy inputs')
    if (row['schema'] != SCHEMA or type(row['player_id']) is not int
            or row['player_id'] != player_id or type(row['turn']) is not int
            or row['turn'] != turn):
        raise ValueError('economy inputs identity or schema mismatch')
    treasury = _fields(row['treasury'], {'gold_balance', 'gold_yield', 'gold_expense',
                        'net_gold_yield'}, 'public treasury')
    balance = _integer(treasury['gold_balance'], 'public gold balance', low=None)
    income = _public_tenth(treasury['gold_yield'], 'public gold yield')
    expense = _public_tenth(treasury['gold_expense'], 'public gold expense')
    net = _public_tenth(treasury['net_gold_yield'], 'public net gold yield')
    if abs(net - (income + expense)) > 3 * 0.100000001:
        raise ValueError('public net gold yield differs from displayed income and expense')
    globals_ = _fields(row['global_yields'], yield_display982.GLOBAL_YIELDS, 'global yields')
    normalized_globals = {key: _public_tenth(globals_[key], f'global yield {key}')
                          for key in yield_display982.GLOBAL_YIELDS}
    cities = row['cities']
    if type(cities) is not list or len(cities) > _MAX_CITIES:
        raise ValueError('public city yields are malformed or oversized')
    normalized_cities, previous = [], -1
    for pos, city in enumerate(cities):
        city = _fields(city, {'city_id', 'yields'}, f'city yields[{pos}]')
        city_id = _integer(city['city_id'], f'city yields[{pos}].city_id')
        if city_id <= previous:
            raise ValueError('public city yields must have sorted unique ids')
        previous = city_id
        yields = _fields(city['yields'], _CITY_YIELDS, f'city yields[{pos}].yields')
        normalized_cities.append({'city_id': city_id,
                                  'yields': {key: _public_tenth(yields[key], f'city yield {key}')
                                             for key in _CITY_YIELDS}})
    research = _validate_research(row['research'], candidates)
    result = {'schema': SCHEMA, 'player_id': player_id, 'turn': turn,
              'treasury': {'gold_balance': balance, 'gold_yield': income,
                           'gold_expense': expense, 'net_gold_yield': net},
              'global_yields': normalized_globals, 'cities': normalized_cities,
              'research': research}
    if observation is not None:
        _identity(observation, player_id, turn)
        economy = observation['economy']
        obs_balance = _number(economy.get('gold'), 'observation gold')
        if balance != math.floor(obs_balance):
            raise ValueError('public gold balance differs from player observation')
        for name in ('science', 'culture', 'faith'):
            observed = _number(economy.get(name), f'observation {name}')
            if abs(normalized_globals[name] - observed) > 0.100000001:
                raise ValueError(f'public global {name} differs from player observation')
        own = {}
        all_ids = set()
        for pos, city in enumerate(observation['cities']):
            if not isinstance(city, Mapping):
                raise ValueError(f'observation city {pos} is malformed')
            city_id = _integer(city.get('id'), f'observation city {pos}.id')
            owner = _integer(city.get('owner'), f'observation city {pos}.owner')
            if city_id in all_ids:
                raise ValueError('duplicate city id in player observation')
            all_ids.add(city_id)
            if owner == player_id:
                own[city_id] = city
        if [city['city_id'] for city in normalized_cities] != sorted(own):
            raise ValueError('public yield city roster differs from own observation')
        for city in normalized_cities:
            source = _fields(own[city['city_id']].get('yields'), _CITY_YIELDS,
                             f'observation city {city["city_id"]}.yields')
            for name in _CITY_YIELDS:
                expected = math.floor(_number(source[name], f'observation city yield {name}') * 10) / 10
                if abs(city['yields'][name] - expected) > 1e-9:
                    raise ValueError(f'public city {name} differs from displayed observation value')
    return result


def administrative(observation, decisions) -> dict:
    """Return labeled administrative snapshots, preserving native values verbatim."""
    if not isinstance(decisions, Mapping):
        raise ValueError('decisions must be an object')
    player_id = _integer(observation.get('player_id') if isinstance(observation, Mapping) else None,
                         'observation player_id', high=63)
    turn = _integer(observation.get('turn') if isinstance(observation, Mapping) else None,
                    'observation turn')
    _identity(observation, player_id, turn)
    _treasury_snapshot(decisions.get('treasury'), player_id, turn, observation)
    yield_display982.validate(decisions.get('yield_display'), player_id, turn, observation)
    candidates = decisions.get('candidates')
    research_snapshot = research_info983.validate(decisions.get('research_info'), player_id, turn,
        research=decisions.get('research'), candidates=decisions.get('candidates'))
    progress = decisions.get('research_progress')
    _fields(progress, {'schema', 'player_id', 'turn', 'technology', 'civic'}, 'research progress')
    if (progress['schema'] != 'civ6rl.native_saved_research_progress971.v1'
            or type(progress['player_id']) is not int or progress['player_id'] != player_id
            or type(progress['turn']) is not int or progress['turn'] != turn):
        raise ValueError('research progress identity or schema mismatch')
    for topic in ('technology', 'civic'):
        item = _fields(progress[topic], {'index', 'cost', 'progress', 'remaining'},
                       f'research progress {topic}')
        if item['index'] is None:
            if any(item[key] is not None for key in ('cost', 'progress', 'remaining')):
                raise ValueError(f'empty research progress {topic} has values')
        else:
            index = _integer(item['index'], f'research progress {topic}.index', high=0xFFFFFFFF)
            cost = _number(item['cost'], f'research progress {topic}.cost')
            progress_value = _number(item['progress'], f'research progress {topic}.progress')
            remaining = _number(item['remaining'], f'research progress {topic}.remaining')
            if remaining != cost - progress_value:
                raise ValueError(f'research progress {topic} remaining value is inconsistent')
            selected = research_snapshot[topic]['selected']
            if index != selected:
                raise ValueError(f'research progress {topic} index differs from selected item')
            selected_info = research_snapshot[topic]['selected_info']
            if selected_info is not None and selected_info['cost'] != cost:
                raise ValueError(f'research progress {topic} cost differs from selected item')
        if item['index'] is None and research_snapshot[topic]['selected'] is not None:
            raise ValueError(f'research progress {topic} is empty while an item is selected')
    economy = _fields(observation['economy'], {'science', 'culture', 'gold', 'faith'},
                      'observation economy')
    for key, value in economy.items():
        _number(value, f'observation economy {key}')
    city_yields = []
    if type(observation['cities']) is not list or len(observation['cities']) > _MAX_CITIES * 4:
        raise ValueError('observation cities are malformed or oversized')
    seen = set()
    for pos, city in enumerate(observation['cities']):
        if not isinstance(city, Mapping):
            raise ValueError(f'observation city {pos} is malformed')
        cid = _integer(city.get('id'), f'observation city {pos}.id')
        if cid in seen:
            raise ValueError('duplicate city id in observation')
        seen.add(cid)
        owner = _integer(city.get('owner'), f'observation city {pos}.owner')
        yields = _fields(city.get('yields'), _CITY_YIELDS, f'observation city {cid}.yields')
        for key, value in yields.items():
            _number(value, f'observation city {cid} yield {key}')
        city_yields.append({'id': cid, 'owner': owner, 'yields': copy.deepcopy(dict(yields))})
    return {'schema': ADMIN_SCHEMA, 'player_id': player_id, 'turn': turn,
            'actor_channel': False, 'economy': copy.deepcopy(dict(economy)),
            'city_yields': city_yields,
            'treasury': copy.deepcopy(decisions['treasury']),
            'yield_display': copy.deepcopy(decisions['yield_display']),
            'research_info': copy.deepcopy(decisions['research_info']),
            'research_progress': copy.deepcopy(progress)}


__all__ = ['SCHEMA', 'ADMIN_SCHEMA', 'project', 'validate', 'administrative']
