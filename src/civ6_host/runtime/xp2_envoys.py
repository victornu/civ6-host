"""Reuse the native envoy query/effect algorithm on the selected XP2 owner.

The legacy prefix's envoy helper defaults to the Base ABI. This adapter instead
passes the selected XP2 engine to the shared player-operation request explicitly.
"""
import hashlib
from pathlib import Path

from civ6_host.contracts import envoys as contract
from .a0_policy_unlock_current import CURRENT_PROFILE_ID, _require_image
from .configuration_profiles import XP2_CORE_SHA256
from .native import native_envoy_actions as native
from .paths import resource_root


CHECKPOINT_SOURCE = (
    'evidence/host-xp2-envoy-checkpoint-consideration-source.json',
    '7c1183034d592a19a1ad6f9d424b2e16660f7df8f018bf326ea69b998b8572fa',
)


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


def source_dependencies(*, execution_image=None):
    from .xp2_envoys_source import source_dependencies as dependencies

    pins = dependencies(execution_image=execution_image)
    if getattr(execution_image, 'id', None) == CURRENT_PROFILE_ID:
        _checkpoint_source(execution_image)
        pins[str((resource_root() / CHECKPOINT_SOURCE[0]).resolve())] = CHECKPOINT_SOURCE[1]
    return pins


def catalogue(saved, observation, *, active=False):
    from .xp2_envoys_source import bind_owner
    bind_owner(saved, active=active)
    pid, turn = observation['player_id'], observation['turn']
    p = saved.prefix
    raw = p.runtime.evaluate_text(p.ui_child, native.catalog_source(pid, turn),
                                 b'@xp2_envoy_catalogue', capacity=8193)
    value = native.parse_catalog(raw, pid, turn)
    value['targets'] = list(value['targets'])
    contract.validate_catalogue(value, pid, turn)
    saved.continuation.explicit_envoys = value
    return value


def restore_checkpoint_consideration(saved, observation, expected):
    """Restore the omitted native consideration bit from the authenticated view."""
    image = getattr(getattr(saved, 'core', None), '_civ6_host_execution_image', None)
    if (getattr(image, 'id', None) != CURRENT_PROFILE_ID or expected is None
            or expected['considered'] is not False
            or expected['giving_tokens_blocker_present'] is not True):
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
        b, c, p = saved.backend, saved.continuation, saved.prefix
        proof = _checkpoint_source(image)
        for span in proof['live_spans'].values():
            raw = b.runtime.read(saved.core._handle + span['rva'], span['size'])
            if hashlib.sha256(raw).hexdigest() != span['sha256']:
                raise ValueError('Live XP2 envoy checkpoint source differs')
        c.transport.require_empty_native_queue()
        b.control(empty=True)
        if p.actions.pending or p.deferred_events.pending:
            raise RuntimeError('Envoy checkpoint restore requires empty native queues')
        b.stage, b.busy = ACTIVE, True
        saved._check_active()
        require_quiescent(b.jobs_snapshot('before'))
        with capability_source_scope(b, 'continuation'):
            source = native._common(pid, turn) + f"""
local tokens, _, considered, blocker = header()
assert(tokens == {fresh['tokens_to_give']} and considered and not blocker,
 'envoy consideration changed during checkpoint restore')
influence:SetGivingTokensConsidered(false)
assert(influence:IsGivingTokensConsidered() == false, 'native envoy consideration did not restore')
return 'restored'
""".encode('ascii')
            raw = p.runtime.evaluate_text(p.ui_child, source,
                b'@xp2_envoy_checkpoint_consideration', capacity=32)
            if raw != b'restored' or p.actions.pending:
                raise RuntimeError('Envoy consideration restore emitted a player command')
            p.deferred_events.drain()
            p.view_publisher.publish()
            if catalogue(saved, observation, active=True) != expected:
                raise RuntimeError('Native envoy checkpoint catalogue did not restore exactly')
            c.transport.require_empty_native_queue()
            b.control(empty=True)
            require_quiescent(b.jobs_snapshot('after'))
        b.stage, b.busy = READY, False
        saved._check_query()
        saved.emit('xp2_envoy_checkpoint_consideration_restored', player_id=pid, turn=turn,
                   source_sha256=CHECKPOINT_SOURCE[1], player_command_submitted=False)


def apply(saved, action, before):
    from .xp2_envoys_source import bind_owner, SOURCE, APPLICATION
    from .native.native_player_operation_request import request_player_operation
    from .native.native_player_observation import observe_player
    bind_owner(saved, active=True)
    contract.validate_action(action)
    pid, turn = before['player_id'], before['turn']
    expected = saved.continuation.explicit_envoys
    fresh = catalogue(saved, before, active=True)
    if fresh != expected or action not in contract.actions(fresh):
        raise RuntimeError('Envoy decision is stale or no longer offered')
    p, b = saved.prefix, saved.backend
    if p.actions.pending or p.deferred_events.pending:
        raise RuntimeError('Envoy choice requires drained owned transports')
    if action['kind'] == 'send_envoy':
        choice = native.choose(fresh, action['target_player_id'])
        checked = native.validate_fresh_choice(p.runtime.evaluate_text(p.ui_child,
            native.revalidation_source(choice), b'@xp2_envoy_revalidation', capacity=8193), choice)
        operation, parameters = native.operation_parameters(checked)
        result = request_player_operation(b.core, b.context, pid, operation, parameters,
                                          core_sha256=XP2_CORE_SHA256)
        if not result['can_start'] or not result['request_invoked']:
            raise RuntimeError('Native XP2 CanStartPlayerOperation refused envoy assignment')
        if len(p.actions.pending) != 1 or bytes(p.actions.pending[0][:4]) != (3294486831).to_bytes(4, 'little'):
            raise RuntimeError('Envoy request did not emit its single native operation archive')
        p.actions.deliver_one()
        p.deferred_events.drain()
        p.view_publisher.publish()
        observed = catalogue(saved, before, active=True)
        effect = native.verify_sent_effect(observed, choice)
    else:
        requested = native.parse_catalog(p.runtime.evaluate_text(p.ui_child,
            native.consideration_source(fresh), b'@xp2_envoy_consideration', capacity=8193), pid, turn)
        if p.actions.pending or not requested['considered']:
            raise RuntimeError('Envoy consideration serialized a command or did not take effect')
        p.deferred_events.drain()
        p.view_publisher.publish()
        observed = catalogue(saved, before, active=True)
        effect = native.verify_considered_effect(fresh, observed)
    if p.actions.pending or p.deferred_events.pending:
        raise RuntimeError('Envoy operation left pending native work')
    after = observe_player(p.runtime, p.ui_child, pid)
    if after['player_id'] != pid or after['turn'] != turn:
        raise RuntimeError('Envoy action crossed its player or turn boundary')
    saved.emit('xp2_envoy_effect_verified', action=action, before=fresh, after=observed,
        effect=effect, source_proof_sha256=SOURCE[1], application_source_sha256=APPLICATION[1],
        automatic_choices_applied=False)
    return dict(observation=after, effect=effect)
