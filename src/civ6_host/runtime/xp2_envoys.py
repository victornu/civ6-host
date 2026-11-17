"""Public envoy queries and effects on source-bound expansion owners."""
import hashlib
from pathlib import Path

from civ6_host.contracts import envoys as contract
from .a0_policy_unlock_current import CURRENT_PROFILE_ID, _require_image
from .configuration_profiles import XP1_CORE_SHA256, XP2_CORE_SHA256
from .native import native_envoy_actions as native
from .paths import resource_root


CHECKPOINT_SOURCE = (
    'evidence/host-xp2-envoy-checkpoint-consideration-source.json',
    '7c1183034d592a19a1ad6f9d424b2e16660f7df8f018bf326ea69b998b8572fa',
)
UNBLOCKED_CHECKPOINT_SOURCE = (
    'evidence/host-xp2-envoy-unblocked-checkpoint-byte-source.json',
    'd0870cd2c6bbf77772686f20cc3da6ca9a4c1a296ed578e05b41445418829da7',
)
_UNBLOCKED_LAYOUT = dict(loaded_game_global_rva=0xb8aa68, player_registry=0x240, registry_slots=0x20,
    player_stride=8, player_id=0xd8, native_local_player=0x2da8, influence=0x748,
    influence_owner=0x498, considered=0x4a0)


def _checkpoint_source(image):
    from .configuration_profiles import _source

    _require_image(image)
    proof = _source(CHECKPOINT_SOURCE)
    if (proof['schema'] != 'civ6-host.xp2-envoy-checkpoint-consideration-source.v1'
            or proof['image']['sha256'] != image.image_sha256
            or Path(proof['image']['path']).resolve() != Path(image.path).resolve()
            or proof['source_contract']['archive_records_consideration'] is not False
            or proof['source_contract']['constructor_default'] is not True):
        raise ValueError('XP2 envoy checkpoint source differs')
    return proof


def _unblocked_checkpoint_source(image):
    from .configuration_profiles import _source

    _require_image(image)
    proof = _source(UNBLOCKED_CHECKPOINT_SOURCE)
    if (proof['schema'] != 'civ6-host.xp2-envoy-unblocked-checkpoint-byte.static.v1'
            or (proof['archive_source']['path'], proof['archive_source']['sha256']) != CHECKPOINT_SOURCE
            or proof['layout'] != _UNBLOCKED_LAYOUT
            or proof['image']['sha256'] != image.image_sha256
            or Path(proof['image']['path']).resolve() != Path(image.path).resolve()
            or set(proof['source_spans']) != {'playable_slot_bridge', 'lookup_player', 'registry',
                'local_player', 'considered_field', 'influence_back_reference_and_store',
                'notification_player', 'notification_refresh'}):
        raise ValueError('XP2 unblocked envoy checkpoint source differs')
    return proof


def source_dependencies(*, execution_image=None):
    from .xp2_envoys_source import source_dependencies as dependencies

    pins = dependencies(execution_image=execution_image)
    if getattr(execution_image, 'id', None) == CURRENT_PROFILE_ID:
        _checkpoint_source(execution_image)
        _unblocked_checkpoint_source(execution_image)
        for path, digest in (CHECKPOINT_SOURCE, UNBLOCKED_CHECKPOINT_SOURCE):
            pins[str((resource_root() / path).resolve())] = digest
    return pins


def _bind(saved, *, active):
    core = saved.backend.load_abi.core_sha256
    if core == XP1_CORE_SHA256:
        from .xp1_city_state_envoys import ACTION_SOURCE, bind_actions
        bind_actions(saved, active=active)
        return core, 'xp1', ACTION_SOURCE, ACTION_SOURCE
    if core == XP2_CORE_SHA256:
        from .xp2_envoys_source import APPLICATION, SOURCE, bind_owner
        bind_owner(saved, active=active)
        return core, 'xp2', SOURCE, APPLICATION
    raise ValueError('Envoys require an admitted expansion engine')


def snapshot(saved, observation, *, active=False):
    _, profile, _, _ = _bind(saved, active=active)
    pid, turn = observation['player_id'], observation['turn']
    p = saved.prefix
    raw = p.runtime.evaluate_text(p.ui_child, native.catalog_source(pid, turn),
                                 f'@{profile}_envoy_catalogue'.encode('ascii'), capacity=8193)
    value = native.parse_catalog(raw, pid, turn)
    value['targets'] = list(value['targets'])
    contract.validate_catalogue(value, pid, turn)
    return value


def catalogue(saved, observation, *, active=False):
    value = snapshot(saved, observation, active=active)
    saved.continuation.explicit_envoys = value
    return value


def _restore_unblocked_flag(saved, player_id, proof):
    from .native.native_checkpoint_stream import LocalMemory

    base = saved.core._handle
    memory = LocalMemory()
    for span in proof['source_spans'].values():
        raw = memory.read(base + span['rva'], span['size'])
        if hashlib.sha256(raw).hexdigest() != span['sha256']:
            raise ValueError('Live XP2 envoy checkpoint byte source differs')

    def pointer(address):
        value = int.from_bytes(memory.read(address, 8), 'little')
        if not 0x10000 <= value < (1 << 47) or value % 8:
            raise ValueError('Invalid native XP2 envoy checkpoint owner pointer')
        return value

    layout = _UNBLOCKED_LAYOUT
    loaded = pointer(base + layout['loaded_game_global_rva'])
    if loaded != saved.continuation.lease.identity['game']:
        raise ValueError('XP2 envoy consideration belongs to a different loaded game')
    game = pointer(loaded + layout['player_registry'])
    if (type(player_id) is not int or not 0 <= player_id < 64
            or int.from_bytes(memory.read(game + layout['native_local_player'], 4), 'little') != player_id):
        raise ValueError('XP2 envoy consideration belongs to a different local player')
    slots = pointer(game + layout['registry_slots'])
    player = pointer(slots + player_id * layout['player_stride'])
    if int.from_bytes(memory.read(player + layout['player_id'], 4), 'little') != player_id:
        raise ValueError('XP2 envoy checkpoint player slot differs')
    influence = pointer(player + layout['influence'])
    if pointer(influence + layout['influence_owner']) != player:
        raise ValueError('XP2 envoy checkpoint influence owner differs')

    # Only the omitted archive field is restored. The native UI setter
    # refreshes turn blockers as a separate effect.
    address = influence + layout['considered']
    before = memory.read(address - 8, 16)
    if before[8:9] != b'\x01':
        raise ValueError('XP2 envoy consideration changed before checkpoint restore')
    memory.write(address, b'\x00')
    if memory.read(address - 8, 16) != before[:8] + b'\x00' + before[9:]:
        raise RuntimeError('XP2 envoy checkpoint byte restoration differs')


def _restore_consideration(saved, observation, expected, fresh, proof, profile, *, reader,
                           unblocked_source=None):
    b, c, p = saved.backend, saved.continuation, saved.prefix
    for span in proof['live_spans'].values():
        raw = b.runtime.read(saved.core._handle + span['rva'], span['size'])
        if (type(raw) is not bytes or len(raw) != span['size']
                or hashlib.sha256(raw).hexdigest() != span['sha256']):
            raise ValueError(f'Live {profile} envoy checkpoint source differs')
    c.transport.require_empty_native_queue()
    b.control(empty=True)
    if p.actions.pending or p.deferred_events.pending:
        raise RuntimeError('Envoy checkpoint restore requires empty native queues')
    pid, turn = observation['player_id'], observation['turn']
    if unblocked_source is not None:
        _restore_unblocked_flag(saved, pid, unblocked_source)
    else:
        source = native._common(pid, turn) + f"""
local tokens, _, considered, blocker = header()
assert(tokens == {fresh['tokens_to_give']} and considered and not blocker,
 'envoy consideration changed during checkpoint restore')
influence:SetGivingTokensConsidered(false)
assert(influence:IsGivingTokensConsidered() == false, 'native envoy consideration did not restore')
return 'restored'
""".encode('ascii')
        raw = p.runtime.evaluate_text(p.ui_child, source,
            f'@{profile}_envoy_checkpoint_consideration'.encode('ascii'), capacity=32)
        if raw != b'restored' or p.actions.pending:
            raise RuntimeError('Envoy consideration restore emitted a player command')
        p.deferred_events.drain()
        p.view_publisher.publish()
    restored = reader(saved, observation, active=True)
    if restored != expected:
        raise RuntimeError('Native envoy checkpoint catalogue did not restore exactly')
    if p.actions.pending or p.deferred_events.pending:
        raise RuntimeError('Envoy checkpoint restoration left pending native work')
    c.transport.require_empty_native_queue()
    b.control(empty=True)
    return restored


def restore_borrowed_consideration(saved, observation, fresh, expected):
    if expected is None or fresh is None or expected == fresh:
        return fresh
    pid, turn = observation['player_id'], observation['turn']
    contract.validate_catalogue(expected, pid, turn)
    if (expected['considered'] is not False
            or (not expected['giving_tokens_blocker_present'] and expected['tokens_to_give'] != 0)
            or fresh != dict(expected, considered=True, giving_tokens_blocker_present=False)):
        return fresh
    from .xp1_session_view import _borrowed_xp2_reference

    _borrowed_xp2_reference(saved, pid)
    image = saved.core._civ6_host_execution_image
    proof = _checkpoint_source(image)
    restored = _restore_consideration(saved, observation, expected, fresh, proof, 'xp2', reader=snapshot)
    saved.emit('xp2_envoy_checkpoint_consideration_restored', player_id=pid, turn=turn,
        source_sha256=CHECKPOINT_SOURCE[1], player_command_submitted=False,
        considered_before=True, considered_after=False,
        blocker_before=False, blocker_after=restored['giving_tokens_blocker_present'])
    return restored


def restore_checkpoint_consideration(saved, observation, expected):
    """Restore the omitted native consideration bit from the authenticated view."""
    from .execution_images import _XP1_PROFILE

    image = getattr(getattr(saved, 'core', None), '_civ6_host_execution_image', None)
    xp1 = image is _XP1_PROFILE
    if ((not xp1 and getattr(image, 'id', None) != CURRENT_PROFILE_ID) or expected is None
            or expected['considered'] is not False
            or (xp1 and expected['giving_tokens_blocker_present'] is not True)):
        return
    pid, turn = observation['player_id'], observation['turn']
    contract.validate_catalogue(expected, pid, turn)
    from .saved_load_job_observer import require_quiescent
    from .xp1_continuation import ACTIVE, READY
    from .xp1_load_capability import capability_source_scope

    saved._check('commands', requested='unit_commands_candidate')
    with saved._attempt():
        fresh = catalogue(saved, observation)
        # The overall checkpoint comparison still rejects every other difference.
        if fresh != dict(expected, considered=True, giving_tokens_blocker_present=False):
            return
        b = saved.backend
        if xp1:
            from .xp1_city_state_envoys import CHECKPOINT_SOURCE as xp1_source, checkpoint_source
            proof, proof_hash, profile = checkpoint_source(image), xp1_source[1], 'xp1'
        else:
            proof, proof_hash, profile = _checkpoint_source(image), CHECKPOINT_SOURCE[1], 'xp2'
        unblocked = None
        if not xp1 and not expected['giving_tokens_blocker_present'] and expected['tokens_to_give'] > 0:
            unblocked = _unblocked_checkpoint_source(image)
            proof_hash = UNBLOCKED_CHECKPOINT_SOURCE[1]
        b.stage, b.busy = ACTIVE, True
        saved._check_active()
        require_quiescent(b.jobs_snapshot('before'))
        with capability_source_scope(b, 'continuation'):
            _restore_consideration(saved, observation, expected, fresh, proof, profile,
                reader=catalogue, unblocked_source=unblocked)
            require_quiescent(b.jobs_snapshot('after'))
        b.stage, b.busy = READY, False
        saved._check_query()
        saved.emit(f'{profile}_envoy_checkpoint_consideration_restored', player_id=pid, turn=turn,
                   source_sha256=proof_hash, player_command_submitted=False,
                   considered_before=fresh['considered'], considered_after=expected['considered'],
                   blocker_before=fresh['giving_tokens_blocker_present'],
                   blocker_after=expected['giving_tokens_blocker_present'])


def apply(saved, action, before, *, borrowed=None):
    from .native.native_player_operation_request import request_player_operation
    from .native.native_player_observation import observe_player
    core, profile, source, application = _bind(saved, active=True)
    contract.validate_action(action)
    pid, turn = before['player_id'], before['turn']
    reader = catalogue if borrowed is None else snapshot
    expected = saved.continuation.explicit_envoys if borrowed is None else borrowed
    fresh = reader(saved, before, active=True)
    if fresh != expected or action not in contract.actions(fresh):
        raise RuntimeError('Envoy decision is stale or no longer offered')
    p, b = saved.prefix, saved.backend
    if p.actions.pending or p.deferred_events.pending:
        raise RuntimeError('Envoy choice requires drained owned transports')
    if action['kind'] == 'send_envoy':
        choice = native.choose(fresh, action['target_player_id'])
        checked = native.validate_fresh_choice(p.runtime.evaluate_text(p.ui_child,
            native.revalidation_source(choice), f'@{profile}_envoy_revalidation'.encode('ascii'),
            capacity=8193), choice)
        operation, parameters = native.operation_parameters(checked)
        result = request_player_operation(b.core, b.context, pid, operation, parameters,
                                          core_sha256=core)
        if not result['can_start'] or not result['request_invoked']:
            raise RuntimeError('Native CanStartPlayerOperation refused envoy assignment')
        if len(p.actions.pending) != 1 or bytes(p.actions.pending[0][:4]) != (3294486831).to_bytes(4, 'little'):
            raise RuntimeError('Envoy request did not emit its single native operation archive')
        if borrowed is not None:
            from .xp2_city_state_levies import validate_target_archive
            validate_target_archive(p.actions.pending[0], pid, operation, action['target_player_id'])
        p.actions.deliver_one()
        p.deferred_events.drain()
        p.view_publisher.publish()
        observed = reader(saved, before, active=True)
        effect = native.verify_sent_effect(observed, choice)
    else:
        requested = native.parse_catalog(p.runtime.evaluate_text(p.ui_child,
            native.consideration_source(fresh), f'@{profile}_envoy_consideration'.encode('ascii'),
            capacity=8193), pid, turn)
        if p.actions.pending or not requested['considered']:
            raise RuntimeError('Envoy consideration serialized a command or did not take effect')
        p.deferred_events.drain()
        p.view_publisher.publish()
        observed = reader(saved, before, active=True)
        effect = native.verify_considered_effect(fresh, observed)
    if p.actions.pending or p.deferred_events.pending:
        raise RuntimeError('Envoy operation left pending native work')
    after = observe_player(p.runtime, p.ui_child, pid)
    if after['player_id'] != pid or after['turn'] != turn:
        raise RuntimeError('Envoy action crossed its player or turn boundary')
    saved.emit(f'{profile}_envoy_effect_verified', action=action, before=fresh, after=observed,
        effect=effect, source_proof_sha256=source[1], application_source_sha256=application[1],
        automatic_choices_applied=False)
    return dict(observation=after, effect=effect)
