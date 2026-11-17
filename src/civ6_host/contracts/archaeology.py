"""Public pending artifact and the exact origins shown by the archaeology popup."""

import re

from . import city_buildings

SCHEMA = 'civ6-host.archaeology.v1'
MUSEUM_SCHEMA = 'civ6-host.archaeology.v2'
KIND = 'choose_artifact_origin'
ACTION_FIELDS = frozenset(('kind', 'unit_id', 'origin_player_id'))
EXCAVATE = 'excavate_artifact'
EXCAVATE_FIELDS = frozenset(('kind', 'unit_id', 'x', 'y'))
CONFIRM_ONLY_TYPES = (1, 2, 5)
ARTIFACT_TYPES = range(6)


def museum_slots(panel):
    if type(panel) is not dict or panel.get('schema') not in city_buildings.GREAT_WORK_OVERVIEW_SCHEMAS:
        raise ValueError('Museum archaeology requires the owned Great Work overview')
    return [(row['city_id'], row['building_index'], row['slot'], row['work']['index'])
            for row in panel['great_work_slots'] if row['work'] is not None
            and row['work']['object_type'] == 'GREATWORKOBJECT_ARTIFACT']


def validate(value, player_id, turn, *, observation=None, panel=None):
    schema = value.get('schema') if type(value) is dict else None
    fields = {'schema', 'player_id', 'turn', 'pending'}
    if schema == MUSEUM_SCHEMA:
        fields.add('museum_artifacts')
    if (type(value) is not dict or set(value) != fields or schema not in (SCHEMA, MUSEUM_SCHEMA)
            or type(value['player_id']) is not int or not 0 <= value['player_id'] < 64
            or type(value['turn']) is not int or not 0 <= value['turn'] < 2**31
            or (value['player_id'], value['turn']) != (player_id, turn)):
        raise ValueError('Invalid public archaeology boundary')
    if schema == MUSEUM_SCHEMA:
        expected = museum_slots(panel)
        if (panel['player_id'], panel['turn']) != (player_id, turn):
            raise ValueError('Museum archaeology belongs to another boundary')
        rows = value['museum_artifacts']
        identity = ('city_id', 'building_index', 'slot', 'work_index')
        if type(rows) is not list or len(rows) != len(expected):
            raise ValueError('Museum archaeology differs from the owned artifact slots')
        for row, slot in zip(rows, expected, strict=True):
            if (type(row) is not dict or set(row) != {*identity, 'era_type', 'origin_player_id'}
                    or any(type(row[key]) is not int for key in identity)
                    or tuple(row[key] for key in identity) != slot
                    or type(row['era_type']) is not str
                    or re.fullmatch(r'ERA_[A-Z0-9_]{1,100}', row['era_type']) is None
                    or (row['origin_player_id'] is not None and
                        (type(row['origin_player_id']) is not int or not 0 <= row['origin_player_id'] < 64))):
                raise ValueError('Invalid or foreign museum artifact')
    pending = value['pending']
    if pending is None:
        return value
    if type(pending) is not dict or set(pending) != {'unit_id', 'artifact_type', 'era_index', 'origin_player_ids'}:
        raise ValueError('Invalid public artifact fields')
    unit, artifact, era = (pending[key] for key in ('unit_id', 'artifact_type', 'era_index'))
    if (type(unit) is not int or not 0 <= unit < 2**32
            or type(artifact) is not int or artifact not in ARTIFACT_TYPES
            or type(era) is not int or not 0 <= era < 2**31):
        raise ValueError('Invalid public artifact identity')
    origins = pending['origin_player_ids']
    if (type(origins) is not list or len(origins) != (1 if artifact in CONFIRM_ONLY_TYPES else 2)
            or any(type(origin) is not int or not 0 <= origin < 64 for origin in origins)):
        raise ValueError('Artifact origins differ from the official popup')
    if observation is not None and ((observation['player_id'], observation['turn']) != (player_id, turn)
            or sum(row['id'] == unit and row['owner'] == player_id for row in observation['units']) != 1):
        raise ValueError('Pending archaeology must belong to an observed own unit')
    return value


def validate_action(action):
    if (type(action) is not dict or set(action) != ACTION_FIELDS or action['kind'] != KIND
            or type(action['unit_id']) is not int or not 0 <= action['unit_id'] < 2**32
            or type(action['origin_player_id']) is not int or not 0 <= action['origin_player_id'] < 64):
        raise ValueError('Invalid artifact origin action')
    return action


def actions(state):
    if state is None or state['pending'] is None:
        return []
    pending = state['pending']
    return [dict(kind=KIND, unit_id=pending['unit_id'], origin_player_id=player)
            for player in dict.fromkeys(pending['origin_player_ids'])]


def validate_excavation(action, *, observation=None):
    if (type(action) is not dict or set(action) != EXCAVATE_FIELDS or action['kind'] != EXCAVATE
            or type(action['unit_id']) is not int or not 0 <= action['unit_id'] < 2**32
            or any(type(action[k]) is not int or not 0 <= action[k] < 2**31 for k in ('x', 'y'))):
        raise ValueError('Invalid artifact excavation action')
    if observation is not None and sum(
            (unit['id'], unit['owner'], unit['x'], unit['y']) ==
            (action['unit_id'], observation['player_id'], action['x'], action['y'])
            for unit in observation['units']) != 1:
        raise ValueError('Artifact excavation must match an observed own unit and plot')
    return action
