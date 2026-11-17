"""Ordinary production replacement scoped to a borrowed Gathering Storm seat."""

from struct import unpack
from types import SimpleNamespace

from civ6_host.contracts.capability_choices import project_production
from .configuration_profiles import XP2_CORE_SHA256
from .xp1_choice_queries import read_production

_BUILD = 739199558
# Category and hash word in the native 68-byte CityOperation Build message.
_ITEM_FIELDS = {'unit': (0, 7), 'building': (1, 6), 'district': (2, 9), 'project': (3, 10)}


def city_operation_fields(archive, player_id, city_id):
    """Read the common XP2 CityOperation header and its fixed-size payload."""
    if type(archive) is not bytes or len(archive) != 68:
        raise RuntimeError('Borrowed production requires one CityOperation archive')
    fields = unpack('<17I', archive)
    owner = unpack('<HH', archive[4:8])
    if fields[0] != 0x7ce9adc2 or owner != (player_id, 2) or fields[2] != city_id:
        raise RuntimeError('Borrowed production archive differs from its player or city')
    return fields


def require_archive(archive, choice):
    fields = city_operation_fields(archive, choice['player_id'], choice['city_id'])
    category, item = _ITEM_FIELDS[choice['kind']]
    if (choice['operation'] != _BUILD or fields[4] != category or fields[item] != choice['hash']
            or fields[12:16] != (0xffffd8f1, 0xffffd8f1, 0x0b, 0)):
        raise RuntimeError('Borrowed production archive differs from its item or replacement route')


def read(saved, observation):
    from .xp1_session_view import _borrowed_xp2_reference

    _borrowed_xp2_reference(saved, observation['player_id'])
    saved.continuation.transport.require_empty_native_queue()
    return read_production(saved, observation, core_sha256=XP2_CORE_SHA256)


def project(state):
    if state is None:
        return None
    snapshot, actions = state
    return dict(current=project_production(snapshot), actions=actions)


def apply(saved, action, observation, state, *, expected_head):
    from .explicit_production_operation import apply as request

    if state is None or action not in state[1]:
        return dict(status='refused', reason='native_production_choice_unavailable',
                    requested_action=action), None
    head = next(row for row in project_production(state[0]) if row['city_id'] == action['city_id'])
    if head != expected_head:
        return dict(status='refused', reason='native_production_state_changed',
                    requested_action=action), None
    reports = []

    def emit(stage, **payload):
        if stage != 'official_explicit_production_effect' or reports:
            raise RuntimeError('Unexpected borrowed production receipt')
        reports.append(payload)
        saved.emit(stage, **payload)

    # Keep the borrowed snapshot separate from the primary continuation's queue.
    owner = SimpleNamespace(explicit_production_snapshot=state[0], emit=emit)
    observed = request(owner, saved.prefix, action, observation['turn'],
        player_id=observation['player_id'], core_sha256=XP2_CORE_SHA256,
        archive_guard=require_archive)
    if len(reports) != 1 or (observed['player_id'], observed['turn']) != (
            observation['player_id'], observation['turn']):
        raise RuntimeError('Borrowed production effect crossed its perspective')
    report = reports[0]
    changed = report['production_before'] != report['production']
    receipt = dict(status='completed' if changed else 'submitted',
        reason=None if changed else 'native_production_choice_unchanged', requested_action=action)
    return receipt, observed
