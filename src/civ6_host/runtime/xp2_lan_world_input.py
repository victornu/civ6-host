"""World clicks through the existing native widget, scoped to a borrowed seat."""

from contextlib import nullcontext
from functools import partial
from struct import unpack
from types import SimpleNamespace

from civ6_host.contracts.capability_world_input import WORLD_KINDS
from .configuration_profiles import XP2_CORE_SHA256


_OPCODES = {'MOVE_TO': 19, 'SWAP_UNITS': 49}
_MODIFIERS = 16400  # Official ATTACK + MOVE_IGNORE_UNEXPLORED_DESTINATION.


def enabled(saved):
    return getattr(saved, '_xp2_lan_world_input_enabled', False) is True


def require_archive(archive, player_id, action):
    from civ6_host.contracts.capability_world_input import validate_action

    validate_action(action)
    if action['kind'] != 'world_plot_click' or type(archive) is not bytes or len(archive) != 44:
        raise ValueError('Borrowed world click requires its native targeted UnitOperation archive')
    fields = unpack('<IHH9I', archive)
    if (fields[:4] != (0x8c0f3f36, player_id, 1, action['unit_id']) or fields[4] not in _OPCODES.values()
            or fields[5:] != (0xffffffff, 0, 1, action['x'], action['y'], _MODIFIERS, 0)):
        raise ValueError('Borrowed world archive differs from its owner, unit, route or destination')


def _owner(saved):
    return SimpleNamespace(prefix=saved.prefix, control=saved.backend.control,
        world_input_selections=saved.continuation.world_input_selections,
        world_input_prompts=saved.continuation.world_input_prompts)


def read(saved, observation):
    from .native import native_world_input as world
    from .native.native_saved_combat import queued_orders
    from .xp1_session_view import _borrowed_xp2_reference
    from .xp1_world_input_profile import bind_owner

    b, t = saved.backend, saved.continuation
    pid = observation['player_id']
    _borrowed_xp2_reference(saved, pid)
    bind_owner(b, b.core, b.runtime.read)
    t.transport.require_empty_native_queue()
    b.control(empty=True)
    state = world.observe(_owner(saved), observation, core_sha256=XP2_CORE_SHA256)
    queued = queued_orders(saved.prefix, observation, player_id=pid, core_sha256=XP2_CORE_SHA256)
    t.transport.require_empty_native_queue()
    b.control(empty=True)
    return state, queued


def apply(saved, action, observation, state, *, expected_state):
    from .native import native_world_input as world
    from .saved_load_job_observer import require_quiescent

    refused = dict(status='refused', requested_action=action)
    if state is None or action not in world.actions(state[0]):
        return dict(refused, reason='native_world_input_unavailable'), None
    if state != expected_state:
        return dict(refused, reason='native_world_input_state_changed'), None

    receipts = []

    def emit(stage, **payload):
        if stage != 'official_world_input_result' or receipts:
            raise RuntimeError('Unexpected borrowed world input receipt')
        receipts.append(payload)
        saved.emit(stage, **payload)

    def snapshot(owner, phase):
        current = saved.backend.jobs_snapshot(phase)
        require_quiescent(current)
        return current

    owner = _owner(saved)
    owner.emit = emit
    owner.explicit_world_input = state[0]
    token = saved.continuation
    publications = token.publication_count
    pid, turn = observation['player_id'], observation['turn']
    click = action['kind'] == 'world_plot_click'
    guard = (token.transport.require_xp2_single_archive(
        partial(require_archive, player_id=pid, action=action), allow_no_archive=True)
        if click else nullcontext())
    source_options = {}
    if click and getattr(saved, 'war_source_sha256', None) is not None:
        from .xp2_world_war import request_source

        source_options['request_source_reader'] = partial(request_source, saved)
    with guard:
        after = world.apply(owner, action, turn, observation, core_sha256=XP2_CORE_SHA256,
                            snapshot_reader=snapshot, **source_options)
    if len(receipts) != 1:
        raise RuntimeError('Borrowed world input did not return its native receipt')
    receipt = receipts[0]
    if (receipt['action'] != action or receipt['observation_before'] != observation
            or receipt['observation_after'] != after or receipt['automatic_choices_applied'] is not False
            or receipt['delegated_minor_war'] is not False or receipt['action_dialogue_retained'] is not False):
        raise RuntimeError('Borrowed world input crossed its explicit boundary')
    request = receipt['request']
    submitted = request is not None and request['status'] == 'request'
    if receipt['archive_delivered'] is not submitted or token.publication_count != publications + int(submitted):
        raise RuntimeError('Borrowed world input archive or publication differs')
    if not click:
        if request is not None or after != observation:
            raise RuntimeError('Borrowed selection changed the native observation')
        return dict(status='completed', reason=None, requested_action=action), after
    if not submitted:
        if request is not None and request['status'] == 'war_prompt' and source_options:
            prompt = dict(attacking_player=pid, defending_player=request['defender_player_id'],
                          war_type=request['war_type'])
            if token.world_input_prompts.get(pid) != prompt or after != observation:
                raise RuntimeError('Borrowed click changed its retained war prompt or public view')
            return dict(status='completed', reason=None, requested_action=action), after
        if request is None or request['status'] not in ('noop', 'unsupported') or after != observation:
            raise RuntimeError('Borrowed world click reached an unknown native branch')
        reason = ('native_world_input_branch_unqualified' if request['status'] == 'unsupported'
                  else 'native_world_input_noop')
        return dict(refused, reason=reason), None

    archive = bytes.fromhex(receipt['archive_hex'])
    if _OPCODES.get(request['operation_name']) != unpack('<I', archive[12:16])[0]:
        raise RuntimeError('Borrowed world click operation differs from its native receipt')
    destination = (action['x'], action['y'])
    before_units = {row['id']: (row['x'], row['y']) for row in observation['units']}
    after_units = {row['id']: (row['x'], row['y']) for row in after['units']}
    uid = action['unit_id']
    arrived = before_units[uid] != destination and after_units.get(uid) == destination
    if request['operation_name'] == 'SWAP_UNITS':
        changed = arrived and any(pos == destination and after_units.get(other) == before_units[uid]
                                  for other, pos in before_units.items() if other != uid)
    else:
        old_queue = next(row['plot_id'] for row in state[1]['units'] if row['unit_id'] == uid)
        queued = dict(unit_present=True, plot_id=action['plot_id'])
        changed = arrived or (receipt['queued_destination_after'] == queued
                              and (old_queue != action['plot_id'] or before_units[uid] != after_units.get(uid)))
    return dict(status='completed' if changed else 'submitted',
                reason=None if changed else 'native_world_move_effect_unresolved', requested_action=action), after
