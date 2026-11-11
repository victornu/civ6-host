"""Explicit plot attacks on the retained captured expansion lifetimes.

The shared native catalogue, request, delivery, publication and effect readers
remain the implementation. This owner never selects a defender or damage rule.
"""
from copy import deepcopy
from dataclasses import dataclass
from .configuration_profiles import XP1_CORE_SHA256
from .xp1_world_input import _owner


@dataclass(frozen=True)
class _Catalogue:
    saved:object
    backend:object
    continuation:object
    prefix:object
    identity:object
    episode_id:str
    game_generation:str
    sequence:int
    core:object
    core_base:int
    core_sha256:str
    publication_count:int
    deferred_sequence:int
    deferred_consumed:int
    observation:dict
    state:dict
    actions:tuple
    queued_orders:dict


def source_dependencies(core_sha256=XP1_CORE_SHA256):
    from .xp1_unit_attack_profile import source_dependencies as dependencies
    return dependencies(core_sha256)


def _invalidate(t):
    t._xp1_unit_attack_catalogue=t.explicit_combat_units=t.explicit_combat_cities=None


def _check_catalogue(saved,catalogue,*,active=True):
    b,t,p,identity=_owner(saved,active=active)
    if (type(catalogue) is not _Catalogue or catalogue.saved is not saved
            or catalogue.backend is not b or catalogue.continuation is not t
            or catalogue.prefix is not p or catalogue.identity is not identity
            or catalogue.episode_id!=identity.episode_id or catalogue.game_generation!=identity.game_generation
            or catalogue.core is not b.core or catalogue.core_base!=b.core._handle
            or catalogue.core_sha256!=b.load_abi.core_sha256
            or catalogue.sequence!=t.sequence or catalogue.observation!=t.observation
            or not active and (catalogue.publication_count!=t.publication_count
                or catalogue.deferred_sequence!=p.deferred_events._sequence
                or catalogue.deferred_consumed!=p.deferred_events.consumed_count)
            or getattr(t,'_xp1_unit_attack_catalogue',None) is not catalogue
            or getattr(t,'explicit_combat_units',None)!=catalogue.state['units']
            or getattr(t,'explicit_combat_cities',None)!=catalogue.state['cities']):
        raise ValueError('Attack catalogue is stale or belongs to another session')
    return b,t,p,identity


class _BoundAttackOwner:
    __slots__=('saved','catalogue','receipt','readback')
    def __init__(self,saved,catalogue):
        self.saved,self.catalogue=saved,catalogue
        self.receipt=self.readback=None

    @property
    def explicit_combat_units(self):
        return _check_catalogue(self.saved,self.catalogue)[1].explicit_combat_units

    @property
    def explicit_combat_cities(self):
        return _check_catalogue(self.saved,self.catalogue)[1].explicit_combat_cities

    def emit(self,stage,**payload):
        _check_catalogue(self.saved,self.catalogue)
        if stage in ('official_explicit_unit_attack_effect','official_explicit_unit_attack_readback'):
            name='receipt' if stage.endswith('_effect') else 'readback'
            if getattr(self,name) is not None:raise RuntimeError('Shared attack emitted duplicate results')
            setattr(self,name,deepcopy(payload))
        self.saved.emit(stage,**payload)


def read(saved,observation):
    b,t,p,identity=_owner(saved,active=False)
    if type(observation) is not dict or observation!=t.observation:
        raise ValueError('Attack query requires the current continuation observation')
    from .xp1_unit_attack_profile import bind_owner, verify_public_precision_source
    core_sha256=b.load_abi.core_sha256
    _invalidate(t)
    before,sequence=deepcopy(observation),t.sequence
    boundary=(b.core,b.core._handle,core_sha256,t.publication_count,
              p.deferred_events._sequence,p.deferred_events.consumed_count)
    from .native import native_saved_combat as combat
    from civ6_host.contracts.capability_unit_attacks import validate_catalog,project_public
    try:
        bind_owner(b,b.core,b.runtime.read)
        verify_public_precision_source(core_sha256)
        t.transport.require_empty_native_queue();b.control(empty=True)
        from .xp1_attack_visible_scope import capture
        with capture(saved,before) as visible_scope:
            native=combat.catalog(p,before['turn'],before,player_id=before['player_id'],
                                 core_sha256=core_sha256,visible_scope=visible_scope)
        units=combat.unit_state(p,before['turn'],before,player_id=before['player_id'],core_sha256=core_sha256)
        choices=combat.orders(native,player_id=before['player_id'])
        queued=combat.queued_orders(p,before,player_id=before['player_id'],core_sha256=core_sha256)
        state=dict(player_id=before['player_id'],turn=before['turn'],width=native['width'],height=native['height'],
                   units=units,relationships=native['relationships'],cities=native['cities'],offers=choices)
        validate_catalog(state,before['player_id'],before['turn'],observation=before,queued_orders=queued)
        public=project_public(state,observation=before,queued_orders=queued)
        current=_owner(saved,active=False)
        if (any(actual is not expected for actual,expected in zip(current,(b,t,p,identity)))
                or t.sequence!=sequence or t.observation!=before
                or boundary!=(b.core,b.core._handle,b.load_abi.core_sha256,t.publication_count,
                             p.deferred_events._sequence,p.deferred_events.consumed_count)):
            raise ValueError('Attack query crossed an owner or observation revision')
        t.transport.require_empty_native_queue();b.control(empty=True)
    except BaseException:
        saved._poison()
        raise
    catalogue=_Catalogue(saved,b,t,p,identity,identity.episode_id,identity.game_generation,
        sequence,*boundary,before,deepcopy(state),tuple(deepcopy(choices)),deepcopy(queued))
    t.explicit_combat_units=deepcopy(units);t.explicit_combat_cities=deepcopy(native['cities'])
    t._xp1_unit_attack_catalogue=catalogue
    return dict(unit_attacks=deepcopy(public),actions=deepcopy(choices),queued_orders=deepcopy(queued))


def administrative_readback(saved,observation,sequence):
    """Copy raw city values at the same validated cache and protocol boundary."""
    if type(sequence) is not int or sequence<0:
        raise ValueError('Combat administrative sequence must be explicit')
    _,t,_,_=_owner(saved,active=False)
    catalogue=getattr(t,'_xp1_unit_attack_catalogue',None)
    _,_,_,identity=_check_catalogue(saved,catalogue,active=False)
    if type(observation) is not dict or observation!=catalogue.observation:
        raise ValueError('Combat administrative readback has another public boundary')
    from .xp1_unit_attack_profile import precision_reference
    return dict(stage='native_combat_administrative_readback',episode_id=identity.episode_id,
        game_generation=identity.game_generation,player_id=observation['player_id'],sequence=sequence,
        turn=observation['turn'],source_sha256=precision_reference(catalogue.core_sha256)[1],actor_channel=False,
        cities=deepcopy(catalogue.state['cities']))


def apply(saved,action,before):
    _,t,_,_=_owner(saved,active=True)
    catalogue=getattr(t,'_xp1_unit_attack_catalogue',None)
    b,t,p,_=_check_catalogue(saved,catalogue)
    from civ6_host.contracts.capability_unit_attacks import validate_action
    validate_action(action,catalogue.state['width'],catalogue.state['height'])
    if type(before) is not dict or before!=catalogue.observation or action not in catalogue.actions:
        raise ValueError('Attack was not offered at this exact observation')
    if (catalogue.publication_count!=t.publication_count
            or catalogue.deferred_sequence!=p.deferred_events._sequence
            or catalogue.deferred_consumed!=p.deferred_events.consumed_count):
        raise ValueError('Attack catalogue crossed a publication or FIFO boundary')
    owner=_BoundAttackOwner(saved,catalogue);count=t.publication_count
    from .native import native_saved_combat as combat
    from .xp1_unit_attack_profile import source_reference
    from .xp2_unit_attack_source import current_lifecycle_image
    SOURCE=source_reference(catalogue.core_sha256)
    lifecycle = (dict(live_core=b.core, live_read=b.runtime.read)
                 if current_lifecycle_image(getattr(b.core, '_civ6_host_execution_image', None)) else {})
    try:
        observed=combat.apply(owner,p,action,before['turn'],before,player_id=before['player_id'],
                              core_sha256=catalogue.core_sha256,**lifecycle)
        _check_catalogue(saved,catalogue)
        receipt,readback=owner.receipt,owner.readback
        if (type(receipt) is not dict or receipt.get('action')!=action
                or receipt.get('observation_before')!=before or receipt.get('observation_after')!=observed
                or receipt.get('automatic_choices_applied') is not False
                or receipt.get('native_defender_selection') is not True
                or receipt.get('source_proof_sha256')!=SOURCE[1]
                or receipt.get('city_target_source_sha256') not in (None,SOURCE[1])
                or type(receipt.get('effect')) is not dict
                or type(readback) is not dict or readback.get('action')!=action
                or readback.get('observation_before')!=before or readback.get('observation_after')!=observed
                or readback.get('native_defender_selection') is not True
                or readback.get('effect_verified') is not False
                or t.publication_count!=count+1):
            raise RuntimeError('Shared attack readback, effect or publication is inconsistent')
        effect=receipt['effect']
        if (effect.get('selected_defender_claimed') is not False
                or effect.get('death_or_capture_inferred_from_absence') is not False
                or effect.get('combat_resolution_inferred_from_queue') is not False
                or effect.get('combat_resolution_inferred_from_lifecycle') is not False):
            raise RuntimeError('Attack receipt exceeds its actual native observations')
        t.transport.require_empty_native_queue();b.control(empty=True)
        if effect.get('observable_native_change') is False:
            from .xp2_unit_attack_source import (
                CURRENT_XP2_NO_EFFECT, CURRENT_XP2_LIFECYCLE,
                CURRENT_XP2_RANGE_ADDED, CURRENT_XP2_RANGE_SUBMITTED,
            )
            cycle=effect.get('operation_lifecycle')
            if type(cycle) is not dict or observed != before:
                raise RuntimeError('Expansion attack lacks an exact no-effect lifecycle')
            source = cycle.get('current_xp2_source_sha256')
            if source == CURRENT_XP2_RANGE_ADDED[1] and cycle.get('status') == 'RANGE_ATTACK_added':
                return dict(status='submitted', refusal_code=CURRENT_XP2_RANGE_SUBMITTED,
                            observation=deepcopy(observed), receipt=deepcopy(receipt))
            if source != CURRENT_XP2_LIFECYCLE[1]:
                raise RuntimeError('Expansion attack lacks an exact no-effect lifecycle')
            return dict(status='refused',refusal_code=CURRENT_XP2_NO_EFFECT,
                        observation=deepcopy(observed),receipt=deepcopy(receipt))
        return dict(status='completed',refusal_code=None,observation=deepcopy(observed),receipt=deepcopy(receipt))
    except BaseException:
        saved._poison()
        raise
    finally:
        _invalidate(t)
