"""Portable XP2 popup data, distinct from Base warmonger information.

Only the final visible consequence text is public here. The runtime must supply
the exact selected renderer digest. This codec neither admits a native engine
profile nor proves that a button request has taken effect.
"""
from __future__ import annotations

import json
import re

from .war_confirmation import (
    ACTION_KIND, MAX_BYTES, MAX_TEXT_BYTES, _text, _uint, _war,
    actions, validate_action, validate_prompt,
)

DISPLAY_SCHEMA = 'civ6-host.xp2-world-war-display.v1'


def parse_display(raw, player_id, expected_turn, defender_player_ids, war_type, *, expected_source_sha256):
    if type(raw) is not bytes or not raw or len(raw) > MAX_BYTES:
        raise ValueError('invalid XP2 war display payload size')

    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('duplicate XP2 war display JSON key')
            result[key] = value
        return result

    def nonfinite(_):
        raise ValueError('nonfinite XP2 war display JSON')

    try:
        value = json.loads(raw.decode('utf-8'), object_pairs_hook=unique, parse_constant=nonfinite)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError('malformed XP2 war display JSON') from exc
    pid = _uint(player_id, 'player ID', 63)
    turn = _uint(expected_turn, 'turn')
    war = _war(war_type)
    if (type(defender_player_ids) not in (list, tuple) or not defender_player_ids
            or len(defender_player_ids) > 64):
        raise ValueError('invalid requested XP2 defender list')
    defenders = [_uint(item, 'defender player ID', 63) for item in defender_player_ids]
    if len(set(defenders)) != len(defenders) or pid in defenders:
        raise ValueError('invalid or repeated requested XP2 defender')
    fields = {'schema', 'player_id', 'turn', 'defender_player_ids', 'war_type',
              'targets', 'message', 'consequences', 'buttons', 'static_text', 'source_sha256'}
    if (type(value) is not dict or set(value) != fields
            or value['schema'] != DISPLAY_SCHEMA
            or type(value['player_id']) is not int or value['player_id'] != pid
            or type(value['turn']) is not int or value['turn'] != turn
            or type(value['war_type']) is not int or value['war_type'] != war
            or type(value['defender_player_ids']) is not list
            or any(type(item) is not int for item in value['defender_player_ids'])
            or value['defender_player_ids'] != defenders):
        raise ValueError('XP2 war display identity or schema mismatch')
    if type(value['targets']) is not list or len(value['targets']) != len(defenders):
        raise ValueError('XP2 war display target count mismatch')
    for target, defender in zip(value['targets'], defenders):
        if (type(target) is not dict or set(target) != {'player_id', 'display_name', 'icon_name'}
                or type(target['player_id']) is not int or target['player_id'] != defender):
            raise ValueError('XP2 war display target identity mismatch')
        _text(target['display_name'], 'target display name')
        _text(target['icon_name'], 'target icon name')
    _text(value['message'], 'message')
    _text(value['consequences'], 'XP2 consequences')
    if type(value['buttons']) is not list or len(value['buttons']) != 2:
        raise ValueError('XP2 war display must expose both buttons')
    for button, accept in zip(value['buttons'], (False, True)):
        if (type(button) is not dict or set(button) != {'accept', 'text'}
                or type(button['accept']) is not bool or button['accept'] is not accept):
            raise ValueError('XP2 war display button identity mismatch')
        _text(button['text'], 'button text')
    if type(value['static_text']) is not dict or set(value['static_text']) != {'title', 'warmonger_heading'}:
        raise ValueError('XP2 war display static label fields changed')
    for name, text in value['static_text'].items():
        _text(text, name)
    if (type(expected_source_sha256) is not str
            or re.fullmatch('[0-9a-f]{64}', expected_source_sha256) is None
            or type(value['source_sha256']) is not str
            or value['source_sha256'] != expected_source_sha256):
        raise ValueError('XP2 war display source digest mismatch')
    return value


__all__ = ['DISPLAY_SCHEMA', 'ACTION_KIND', 'MAX_BYTES', 'MAX_TEXT_BYTES',
           'parse_display', 'actions', 'validate_action', 'validate_prompt']
