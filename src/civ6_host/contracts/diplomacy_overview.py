"""Public overview data and explicit initial diplomatic choices; no native code."""
from __future__ import annotations

import re

SCHEMA = 'civ6-host.diplomacy-overview.v1'
_FIELDS = {'schema', 'player_id', 'turn', 'capability', 'paused',
           'targets', 'complete_action_space'}
_SELECTION = {'key', 'disabled', 'supported', 'text', 'tooltip', 'diplomatic_action_type'}


def validate(value, player_id, turn):
    if (type(value) is not dict or set(value) != _FIELDS
            or value['schema'] != SCHEMA
            or type(player_id) is not int or not 0 <= player_id < 64
            or type(turn) is not int or turn < 0
            or type(value['player_id']) is not int or value['player_id'] != player_id
            or type(value['turn']) is not int or value['turn'] != turn
            or type(value['capability']) is not bool or type(value['paused']) is not bool
            or value['complete_action_space'] is not False
            or type(value['targets']) is not list or len(value['targets']) > 63):
        raise ValueError('Malformed or foreign public diplomacy overview')
    players = set()
    for target in value['targets']:
        if (type(target) is not dict or set(target) != {'player_id', 'selections'}
                or type(target['player_id']) is not int
                or not 0 <= target['player_id'] < 64
                or target['player_id'] == player_id or target['player_id'] in players
                or type(target['selections']) is not list or len(target['selections']) > 64):
            raise ValueError('Invalid or duplicate diplomacy target')
        players.add(target['player_id'])
        keys = set()
        for selection in target['selections']:
            if (type(selection) is not dict or set(selection) != _SELECTION
                    or type(selection['key']) is not str
                    or re.fullmatch(r'CHOICE_[A-Z0-9_]{1,96}', selection['key']) is None
                    or selection['key'] in keys
                    or type(selection['disabled']) is not bool
                    or type(selection['supported']) is not bool
                    or any(selection[k] is not None and
                           (type(selection[k]) is not str or len(selection[k]) > 4096)
                           for k in ('text', 'tooltip', 'diplomatic_action_type'))):
                raise ValueError('Invalid or duplicate diplomacy selection')
            keys.add(selection['key'])
    return value


def candidates(value):
    if type(value) is not dict:
        raise ValueError('Missing public diplomacy overview')
    validate(value, value.get('player_id'), value.get('turn'))
    if not value['capability'] or value['paused']:
        return []
    return [dict(kind='diplomacy_initiate', target_player_id=target['player_id'],
                 choice=selection['key'])
            for target in value['targets'] for selection in target['selections']
            if selection['supported'] and not selection['disabled']]
