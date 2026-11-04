"""Parameterless unit orders bound to the exact live XP1 saved session.

Native Lua availability, submission, archive delivery and publication use the
shared implementation. This module binds lifetime and records its exact result.
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
    observation:dict
    unit_orders:dict
    actions:tuple


def source_dependencies(core_sha256=XP1_CORE_SHA256):
    from .xp1_unit_orders_profile import source_dependencies as dependencies
    return dependencies(core_sha256=core_sha256)


def _check_catalogue(saved,catalogue):
    b,t,p,identity=_owner(saved,active=True)
    if (type(catalogue) is not _Catalogue or catalogue.saved is not saved
            or catalogue.backend is not b or catalogue.continuation is not t
            or catalogue.prefix is not p or catalogue.identity is not identity
            or catalogue.episode_id!=identity.episode_id or catalogue.game_generation!=identity.game_generation
            or catalogue.sequence!=t.sequence or catalogue.observation!=t.observation
            or getattr(t,'_xp1_unit_orders_catalogue',None) is not catalogue
            or getattr(t,'explicit_unit_orders',None)!=catalogue.unit_orders):
        raise ValueError('Unit-order catalogue is stale or belongs to another session')
    return b,t,p,identity


class _BoundOrderOwner:
    __slots__=('saved','catalogue','receipt')
    def __init__(self,saved,catalogue):
        self.saved,self.catalogue,self.receipt=saved,catalogue,None

    @property
    def explicit_unit_orders(self):
        return _check_catalogue(self.saved,self.catalogue)[1].explicit_unit_orders

    def emit(self,stage,**payload):
        _check_catalogue(self.saved,self.catalogue)
        if stage=='official_explicit_unit_order_effect':
            if self.receipt is not None:raise RuntimeError('Shared unit order emitted duplicate results')
            self.receipt=deepcopy(payload)
        self.saved.emit(stage,**payload)


def read(saved,observation):
    b,t,p,identity=_owner(saved,active=False)
    if type(observation) is not dict or observation!=t.observation:
        raise ValueError('Unit-order query requires the current continuation observation')
    from .xp1_unit_orders_profile import bind_owner
    bind_owner(b,b.core,b.runtime.read)
    t._xp1_unit_orders_catalogue=t.explicit_unit_orders=None
    before,sequence=deepcopy(observation),t.sequence
    t.transport.require_empty_native_queue();b.control(empty=True)
    from .native import native_saved_unit_orders as orders
    state=orders.catalog(p,before['turn'],player_id=before['player_id'],include_cancel=True,
                         core_sha256=b.load_abi.core_sha256)
    choices=orders.actions(state)
    actual=_owner(saved,active=False)
    if (any(a is not e for a,e in zip(actual,(b,t,p,identity)))
            or t.sequence!=sequence or t.observation!=before):
        raise ValueError('Unit-order query crossed an owner or observation revision')
    t.transport.require_empty_native_queue();b.control(empty=True)
    catalogue=_Catalogue(saved,b,t,p,identity,identity.episode_id,identity.game_generation,
                         sequence,before,deepcopy(state),tuple(deepcopy(choices)))
    t.explicit_unit_orders=deepcopy(state);t._xp1_unit_orders_catalogue=catalogue
    return dict(unit_orders=deepcopy(state),actions=deepcopy(choices))


def apply(saved,action,before):
    _,t,_,_=_owner(saved,active=True)
    catalogue=getattr(t,'_xp1_unit_orders_catalogue',None)
    b,t,p,_=_check_catalogue(saved,catalogue)
    from civ6_host.contracts.capability_unit_orders import validate_action
    validate_action(action)
    if type(before) is not dict or before!=catalogue.observation or action not in catalogue.actions:
        raise ValueError('Unit order was not offered at this exact observation')
    owner=_BoundOrderOwner(saved,catalogue);count=t.publication_count
    from .native import native_saved_unit_orders as orders
    from .xp1_unit_orders_profile import selected_proof
    from .xp1_unit_orders_profile import SOURCE
    proof_sha256=selected_proof(SOURCE[1],b.load_abi.core_sha256)
    try:
        observed=orders.apply(owner,p,action,before['turn'],before,player_id=before['player_id'],
                              include_cancel=True,core_sha256=b.load_abi.core_sha256)
        _check_catalogue(saved,catalogue)
        receipt=owner.receipt
        if (type(receipt) is not dict or receipt.get('action')!=action
                or receipt.get('observation_before')!=before or receipt.get('observation_after')!=observed
                or receipt.get('native_archive_delivered') is not True
                or receipt.get('automatic_choices_applied') is not False
                or receipt.get('source_proof_sha256')!=proof_sha256
                or t.publication_count!=count+1
                or action['item_type']=='UNITCOMMAND_CANCEL' and receipt.get('cancel_source_proof_sha256')!=proof_sha256):
            raise RuntimeError('Shared unit-order receipt or publication is inconsistent')
        t.transport.require_empty_native_queue();b.control(empty=True)
        return dict(status='completed',refusal_code=None,observation=deepcopy(observed),receipt=deepcopy(receipt))
    finally:
        t._xp1_unit_orders_catalogue=t.explicit_unit_orders=None
