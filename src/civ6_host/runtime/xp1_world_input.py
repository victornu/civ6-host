"""Official world-input adapter on one exact active XP1 saved session.

The shared UI catalogue/click algorithm, transport and cache publisher remain
the implementation. This adapter binds their host UI state to the retained
session and classifies the existing result without simulating a game effect.
"""
from copy import deepcopy
from dataclasses import dataclass

from .configuration_profiles import XP1_CORE_SHA256, XP2_CORE_SHA256


@dataclass(frozen=True)
class _Catalogue:
    saved: object
    backend: object
    continuation: object
    prefix: object
    identity: object
    episode_id: str
    game_generation: str
    sequence: int
    observation: dict
    world_input: dict
    actions: tuple
    queued_orders: dict


def source_dependencies(core_sha256=XP1_CORE_SHA256):
    from .xp1_world_input_profile import source_dependencies as dependencies
    return dependencies(core_sha256=core_sha256)


def _owner(saved, *, active):
    from .xp1_saved_load_owner import SavedLoadOwner
    if type(saved) is not SavedLoadOwner:
        raise TypeError('World input requires the exact retained SavedLoadOwner')
    if active:
        saved._check_active()
    else:
        saved._check_query()
    b, t, p = saved.backend, saved.continuation, saved.prefix
    from .native.native_episode_identity import require_episode
    identity = require_episode(p)
    if (t.identity is not identity or t.owner is not b or t.prefix is not p
            or b.load_abi.core_sha256 not in (XP1_CORE_SHA256, XP2_CORE_SHA256)
            or type(t.sequence) is not int or t.sequence < 0):
        raise ValueError('World-input owner or episode identity changed')
    return b, t, p, identity


def _check_catalogue(saved, catalogue, *, active):
    b, t, p, identity = _owner(saved, active=active)
    if (type(catalogue) is not _Catalogue or catalogue.saved is not saved
            or catalogue.backend is not b or catalogue.continuation is not t
            or catalogue.prefix is not p or catalogue.identity is not identity
            or catalogue.episode_id != identity.episode_id
            or catalogue.game_generation != identity.game_generation
            or catalogue.sequence != t.sequence
            or t.observation != catalogue.observation
            or getattr(t, '_xp1_world_input_catalogue', None) is not catalogue
            or getattr(t, 'explicit_world_input', None) != catalogue.world_input):
        raise ValueError('World-input catalogue is stale or belongs to another session')
    return b, t, p, identity


class _BoundWorldOwner:
    """Only the host services/state consumed by the existing shared adapter."""
    __slots__ = ('saved', 'catalogue', 'active', 'receipt')

    def __init__(self, saved, *, active, catalogue=None):
        self.saved, self.active, self.catalogue = saved, active, catalogue
        self.receipt = None

    def _check(self):
        if self.active:
            return _check_catalogue(self.saved, self.catalogue, active=True)
        return _owner(self.saved, active=False)

    @property
    def prefix(self):
        return self._check()[2]

    @property
    def explicit_world_input(self):
        return self._check()[1].explicit_world_input

    @property
    def world_input_selections(self):
        return self._check()[1].world_input_selections

    @world_input_selections.setter
    def world_input_selections(self, value):
        self._check()[1].world_input_selections = value

    @property
    def world_input_prompts(self):
        return self._check()[1].world_input_prompts

    @world_input_prompts.setter
    def world_input_prompts(self, value):
        self._check()[1].world_input_prompts = value

    def control(self, *, empty):
        if empty is not True:
            raise ValueError('World input requires the active empty-control boundary')
        b, continuation, _, _ = self._check()
        if not self.active:
            # The selected popup performs two read-only control snapshots in
            # the existing query attempt. It must not impersonate an action.
            from .xp2_world_war import source_pin
            selected=getattr(self.saved,'war_source_sha256',None)
            if (b.load_abi.core_sha256!=XP2_CORE_SHA256 or selected is None
                    or not any(prompt is not None for prompt in continuation.world_input_prompts.values())):
                raise ValueError('World input control query requires the selected pending XP2 war popup')
            source_pin(selected,'xp2-lan')
        return b.control(empty=True)

    def emit(self, stage, **payload):
        if not self.active:
            raise ValueError('World-input query cannot publish an action receipt')
        self._check()
        if stage == 'official_world_input_result':
            if self.receipt is not None:
                raise RuntimeError('Shared world input emitted more than one result')
            self.receipt = deepcopy(payload)
        # Preserve the original event and payload. The copy is private adapter
        # bookkeeping; the recorded event is never amended or reconstructed.
        self.saved.emit(stage, **payload)


def _snapshot(owner, phase):
    if type(owner) is not _BoundWorldOwner or owner.active is not True:
        raise TypeError('World-input snapshot requires its active bound owner')
    if phase not in ('before', 'after'):
        raise ValueError('Unknown world-input snapshot phase')
    b, _, _, _ = owner._check()
    result = b.jobs_snapshot(phase)
    from .saved_load_job_observer import require_quiescent
    require_quiescent(result)
    return result


def read(saved, observation):
    """Read inside SavedLoadOwner._attempt while continuation remains READY."""
    b, t, p, identity = _owner(saved, active=False)
    if type(observation) is not dict or observation != t.observation:
        raise ValueError('World-input query requires the current continuation observation')
    from .xp1_world_input_profile import bind_owner
    bind_owner(b, b.core, b.runtime.read)
    # Invalidate the old publication before any fresh native read can fail.
    t._xp1_world_input_catalogue = None
    t.explicit_world_input = None
    before, sequence = deepcopy(observation), t.sequence
    if not hasattr(t, 'world_input_selections'):
        t.world_input_selections = {}
    if not hasattr(t, 'world_input_prompts'):
        t.world_input_prompts = {}
    t.transport.require_empty_native_queue()
    b.control(empty=True)
    from .native import native_world_input as world
    from .native.native_saved_combat import queued_orders
    state = world.observe(_BoundWorldOwner(saved, active=False), before,
                          core_sha256=b.load_abi.core_sha256)
    if state['war_prompt'] is not None:
        raise ValueError('XP1 war confirmations are not qualified')
    choices = world.actions(state)
    queued = queued_orders(p, before, player_id=before['player_id'],
                           core_sha256=b.load_abi.core_sha256)
    actual_b, actual_t, actual_p, actual_identity = _owner(saved, active=False)
    if (any(actual is not expected for actual, expected in zip(
                (actual_b, actual_t, actual_p, actual_identity), (b, t, p, identity)))
            or t.sequence != sequence or t.observation != before):
        raise ValueError('World-input query crossed an owner or observation revision')
    t.transport.require_empty_native_queue()
    b.control(empty=True)
    catalogue = _Catalogue(saved, b, t, p, identity, identity.episode_id,
        identity.game_generation, sequence, before, deepcopy(state),
        tuple(deepcopy(choices)), deepcopy(queued))
    t.explicit_world_input = deepcopy(state)
    t._xp1_world_input_catalogue = catalogue
    return dict(world_input=deepcopy(state), actions=deepcopy(choices), queued_orders=deepcopy(queued))


def apply(saved, action, before):
    """Execute one currently published input; refusal is distinct from noop."""
    b, t, _, _ = _owner(saved, active=True)
    catalogue = getattr(t, '_xp1_world_input_catalogue', None)
    _check_catalogue(saved, catalogue, active=True)
    from civ6_host.contracts.capability_world_input import validate_action
    validate_action(action)
    if type(before) is not dict or before != catalogue.observation or action not in catalogue.actions:
        raise ValueError('World-input action was not offered at this exact observation')
    owner = _BoundWorldOwner(saved, active=True, catalogue=catalogue)
    from .native import native_world_input as world
    publication_count = t.publication_count
    try:
        options = {}
        war_enabled = b.load_abi.core_sha256 == XP2_CORE_SHA256 and getattr(saved, 'war_source_sha256', None) is not None
        if war_enabled:
            from functools import partial
            from .xp2_world_war import request_source
            options['request_source_reader'] = partial(request_source, saved)
        observed = world.apply(owner, action, before['turn'], before,
            core_sha256=b.load_abi.core_sha256, snapshot_reader=_snapshot, **options)
        _check_catalogue(saved, catalogue, active=True)
        receipt = owner.receipt
        if (type(receipt) is not dict or receipt.get('action') != action
                or receipt.get('observation_before') != before
                or receipt.get('observation_after') != observed
                or receipt.get('action_dialogue_retained') is not False
                or receipt.get('delegated_minor_war') is not False
                or receipt.get('automatic_choices_applied') is not False):
            raise RuntimeError('Shared world-input receipt is absent or inconsistent')
        request = receipt['request']
        refusal_code = None
        if action['kind'] in ('world_select_unit', 'world_deselect_unit'):
            if request is not None:
                raise RuntimeError('Host UI selection unexpectedly submitted a game request')
            status = 'completed'
            submitted = False
        else:
            statuses = ('request','noop','unsupported','war_prompt') if war_enabled else ('request','noop','unsupported')
            if type(request) is not dict or request.get('status') not in statuses:
                raise RuntimeError('World click reached an unqualified result branch')
            if request['status'] == 'war_prompt':
                from civ6_host.contracts.xp2_war_confirmation import validate_prompt
                expected = dict(attacking_player=before['player_id'],
                    defending_player=request['defender_player_id'], war_type=request['war_type'])
                validate_prompt(expected, before['player_id'])
                if t.world_input_prompts.get(before['player_id']) != expected:
                    raise RuntimeError('The official war prompt was not retained by its owner')
            submitted = request['status'] == 'request'
            status = 'refused' if request['status'] == 'unsupported' else 'completed'
            if status == 'refused':
                refusal_code = 'native_world_input_branch_unqualified'
            qualified_operations = {'MOVE_TO'}
            if b.load_abi.core_sha256 == XP2_CORE_SHA256:
                from .xp2_world_input_source import verify_swap_source
                verify_swap_source()
                qualified_operations.add('SWAP_UNITS')
            if (request.get('native_callback_invoked') is not submitted
                    or submitted and request.get('operation_name') not in qualified_operations):
                raise RuntimeError('World-input transmission differs from its qualified candidate')
        if (receipt.get('archive_delivered') is not submitted
                or t.publication_count != publication_count + int(submitted)):
            raise RuntimeError('World-input publication or archive receipt differs')
        archive = receipt.get('archive_hex')
        if submitted:
            if type(archive) is not str or not archive or bytes.fromhex(archive).hex() != archive:
                raise RuntimeError('World-input submission lacks its original archive')
            if request['operation_name'] == 'MOVE_TO' and observed == before:
                expected_queue = dict(unit_present=True, plot_id=action['plot_id'])
                if receipt['queued_destination_after'] != expected_queue:
                    status = 'refused'
                    refusal_code = 'native_world_move_effect_unobserved'
        elif archive is not None or observed != before:
            raise RuntimeError('Unsubmitted world input changed the native observation')
        return dict(status=status, refusal_code=refusal_code,
            observation=deepcopy(observed), receipt=deepcopy(receipt))
    finally:
        # The common worker publishes a fresh catalogue after every command.
        # Never allow a direct second use of the prior cache, even after refusal.
        t._xp1_world_input_catalogue = None
        t.explicit_world_input = None
