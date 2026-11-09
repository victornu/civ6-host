"""Portable public DeclareWarPopup payload and explicit button identities.

The caller supplies the digest of its source-qualified renderer. This codec
checks data and identity; it does not admit an engine profile, establish human
availability, or authorize a native request. It reads no installed game files.
"""
from __future__ import annotations

import json
import re

DISPLAY_SCHEMA = 'civ6rl.native_world_war_display.v2'
MAX_BYTES = 65536
MAX_TEXT_BYTES = 4096
ACTION_KIND = 'world_war_response'


def _uint(value, name, maximum=0xffffffff):
    if type(value) is not int or not 0 <= value <= maximum:
        raise ValueError('invalid ' + name)
    return value


def _war(value):
    if type(value) is not int or not -(1 << 31) <= value <= 0xffffffff:
        raise ValueError('invalid war type')
    return value


def _text(value, name):
    if type(value) is not str or '\x00' in value:
        raise ValueError('malformed displayed ' + name)
    try:
        length = len(value.encode('utf-8'))
    except UnicodeEncodeError as exc:
        raise ValueError('malformed displayed ' + name) from exc
    if length > MAX_TEXT_BYTES:
        raise ValueError('malformed displayed ' + name)
    return value


def validate_prompt(value, player_id):
    pid = _uint(player_id, 'player ID', 63)
    if (type(value) is not dict
            or set(value) != {'attacking_player', 'defending_player', 'war_type'}
            or type(value['attacking_player']) is not int
            or value['attacking_player'] != pid):
        raise ValueError('invalid public war prompt identity')
    defender = _uint(value['defending_player'], 'defender player ID', 63)
    _war(value['war_type'])
    if defender == pid:
        raise ValueError('war prompt targets the attacking player')
    return value


def validate_action(value):
    if (type(value) is not dict or set(value) != {'kind', 'accept'}
            or value['kind'] != ACTION_KIND or type(value['accept']) is not bool):
        raise ValueError('invalid explicit war confirmation response')
    return value


def actions(prompt, player_id):
    validate_prompt(prompt, player_id)
    return [dict(kind=ACTION_KIND, accept=accept) for accept in (False, True)]


def parse_display(raw, player_id, expected_turn, defender_player_ids, war_type, *,
                  expected_source_sha256):
    """Validate the existing v2 display wire format without runtime imports."""
    if type(raw) is not bytes or not raw or len(raw) > MAX_BYTES:
        raise ValueError('invalid war display payload size')

    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('duplicate war display JSON key')
            result[key] = value
        return result

    def nonfinite(_):
        raise ValueError('nonfinite JSON')

    try:
        value = json.loads(raw, object_pairs_hook=unique, parse_constant=nonfinite)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError('malformed war display JSON') from exc
    pid = _uint(player_id, 'player ID', 63)
    turn = _uint(expected_turn, 'turn')
    war = _war(war_type)
    if (type(defender_player_ids) not in (list, tuple) or not defender_player_ids
            or len(defender_player_ids) > 64):
        raise ValueError('invalid requested defender list')
    defenders = [_uint(item, 'defender player ID', 63) for item in defender_player_ids]
    if len(set(defenders)) != len(defenders) or pid in defenders:
        raise ValueError('invalid or repeated requested defender')
    if (type(value) is not dict or set(value) != {
            'schema', 'player_id', 'turn', 'defender_player_ids', 'war_type',
            'targets', 'message', 'warmonger_text', 'source_sha256', 'buttons', 'static_text'}
            or value['schema'] != DISPLAY_SCHEMA or type(value['player_id']) is not int
            or value['player_id'] != pid or type(value['turn']) is not int
            or value['turn'] != turn or type(value['war_type']) is not int
            or value['war_type'] != war or type(value['defender_player_ids']) is not list
            or value['defender_player_ids'] != defenders):
        raise ValueError('war display identity or schema mismatch')
    if type(value['targets']) is not list or len(value['targets']) != len(defenders):
        raise ValueError('war display target count mismatch')
    for target, defender in zip(value['targets'], defenders):
        if (type(target) is not dict or set(target) != {'player_id', 'display_name', 'icon_name'}
                or type(target['player_id']) is not int or target['player_id'] != defender):
            raise ValueError('war display target identity mismatch')
        for key in ('display_name', 'icon_name'):
            _text(target[key], key)
    _text(value['message'], 'message')
    _text(value['warmonger_text'], 'warmonger text')
    if type(value['buttons']) is not list or len(value['buttons']) != 2:
        raise ValueError('war confirmation requires both official buttons')
    for button, accept in zip(value['buttons'], (False, True)):
        if (type(button) is not dict or set(button) != {'accept', 'text'}
                or button['accept'] is not accept):
            raise ValueError('war confirmation button order or identity changed')
        _text(button['text'], 'button text')
    if type(value['static_text']) is not dict or set(value['static_text']) != {'title', 'warmonger_heading'}:
        raise ValueError('war confirmation static label fields changed')
    for key, text in value['static_text'].items():
        _text(text, key)
    if (type(expected_source_sha256) is not str
            or re.fullmatch('[0-9a-f]{64}', expected_source_sha256) is None
            or type(value['source_sha256']) is not str
            or value['source_sha256'] != expected_source_sha256):
        raise ValueError('invalid war display source digest')
    return value
