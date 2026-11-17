"""Borrowed-seat access to the shared native queue catalogue and dispatch."""

from functools import partial
from types import SimpleNamespace

from civ6_host.contracts.production_queue import FIELDS
from .configuration_profiles import XP2_CORE_SHA256
from .xp2_lan_production import _ITEM_FIELDS, city_operation_fields

_NONE = 0xffffffff


def require_archive(archive, player_id, action):
    fields = city_operation_fields(archive, player_id, action['city_id'])
    kind = action['kind']
    if kind == 'queue_append':
        category, item = _ITEM_FIELDS[action['category']]
        item_matches = fields[item] == action['hash']
        edit = (0x03, _NONE, _NONE) if action['mode'] == 'append' else (0x0b, 7, _NONE)
    elif kind == 'queue_remove':
        category = 7
        item_matches = fields[6:11] == (_NONE,) * 5
        edit = (0x07, action['position'], _NONE)
    elif kind == 'queue_swap':
        category = 8
        item_matches = fields[6:11] == (_NONE,) * 5
        edit = (0x09, action['destination_position'], action['source_position'])
    else:
        raise ValueError('Unknown borrowed production queue action')
    if (fields[4] != category or not item_matches or fields[14:17] != edit
            or fields[12:14] != (0xffffd8f1, 0xffffd8f1)):
        raise RuntimeError('Borrowed production queue archive differs from its item or positions')


def read(saved, observation, production):
    from .xp1_production_queue import read_queues

    if production is None:
        return None
    if not production[0]['cities']:
        return []
    saved.continuation.transport.require_empty_native_queue()
    return read_queues(saved, observation, production[0])


def apply(saved, action, observation, state, *, expected_queue):
    from .native.native_saved_production_queue import apply as request

    queue = next((row for row in state or () if row['city_id'] == action['city_id']), None)
    if queue is None or action not in queue['offers']:
        return dict(status='refused', reason='native_queue_choice_unavailable',
                    requested_action=action), None
    if expected_queue is None or queue['entries'] != expected_queue['entries']:
        return dict(status='refused', reason='native_queue_entries_changed',
                    requested_action=action), None
    receipts = []

    def emit(stage, **payload):
        if stage != 'official_explicit_production_queue_effect' or receipts:
            raise RuntimeError('Unexpected borrowed queue receipt')
        receipts.append(payload)
        saved.emit(stage, **payload)

    owner = SimpleNamespace(explicit_production_queues=state, emit=emit)
    continuation = saved.continuation
    pid, turn = observation['player_id'], observation['turn']
    guard = partial(require_archive, player_id=pid, action=action)
    with continuation.transport.require_xp2_single_archive(guard):
        after = request(owner, saved.prefix, action, turn, observation, player_id=pid,
                        core_sha256=XP2_CORE_SHA256, gate_owner=continuation)
    if len(receipts) != 1 or receipts[0]['action'] != action:
        raise RuntimeError('Borrowed native queue effect was not verified')
    receipt = receipts[0]
    changed = receipt['queue_before']['entries'] != receipt['queue_after']['entries']
    return dict(status='completed' if changed else 'submitted',
                reason=None if changed else 'native_queue_entries_unchanged',
                requested_action=action), after
