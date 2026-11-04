"""Existing CityPanel/PlotInfo gestures on the retained expansion owner graph."""
from copy import deepcopy
from dataclasses import dataclass

from .xp1_world_input import _owner
from .expansion_city_controls_profile import bind_owner,SOURCE


@dataclass(frozen=True)
class _Catalogue:
    saved:object
    backend:object
    continuation:object
    prefix:object
    identity:object
    sequence:int
    observation:dict
    focus:object
    citizens:object
    actions:tuple


def requested(closure):
    flags=tuple(closure.get(k,False) for k in ('city_focus_diagnostic','city_management_diagnostic'))
    if any(type(v) is not bool for v in flags) or flags[1] and not flags[0]:
        raise ValueError('City-control opt-ins must preserve the complete focus/MANAGE group')
    return flags


def enable(saved,closure):
    saved._check('commands',requested='unit_commands_candidate');saved.continuation.check(active=False)
    flags=requested(closure)
    if not flags[0] or hasattr(saved,'_expansion_city_controls_requested'):
        raise ValueError('City controls require one explicit source-selected attachment')
    bind_owner(saved)
    saved._expansion_city_controls_requested=flags
    saved.continuation._expansion_city_controls_catalogue=None


def _check(saved,catalogue=None,*,active):
    b,t,p,identity=_owner(saved,active=active)
    flags=getattr(saved,'_expansion_city_controls_requested',None)
    if type(flags) is not tuple or len(flags)!=2 or not flags[0] or any(type(v) is not bool for v in flags):
        raise ValueError('City-control source profile was not requested before use')
    bind_owner(saved)
    if catalogue is not None and (type(catalogue) is not _Catalogue or catalogue.saved is not saved
            or catalogue.backend is not b or catalogue.continuation is not t or catalogue.prefix is not p
            or catalogue.identity is not identity or catalogue.sequence!=t.sequence
            or catalogue.observation!=t.observation or getattr(t,'_expansion_city_controls_catalogue',None) is not catalogue):
        raise ValueError('City-control catalogue is stale, foreign or replaced')
    return b,t,p,identity,flags



def catalogue_snapshot(saved):
    """Exact previous public city state for the existing worker's fresh requery."""
    saved._check('commands',requested='unit_commands_candidate');saved.continuation.check(active=False)
    t=saved.continuation;catalogue=getattr(t,'_expansion_city_controls_catalogue',None)
    if type(catalogue) is not _Catalogue:return None
    if (catalogue.saved is not saved or catalogue.backend is not saved.backend
            or catalogue.continuation is not t or catalogue.prefix is not saved.prefix
            or catalogue.identity is not t.identity or catalogue.sequence!=t.sequence
            or catalogue.observation!=t.observation):raise ValueError('Previous city catalogue is stale or foreign')
    return deepcopy((catalogue.focus,catalogue.citizens))


def read(saved,observation):
    b,t,p,identity,flags=_check(saved,active=False)
    if type(observation) is not dict or observation!=t.observation:
        raise ValueError('City controls require the exact continuation observation')
    t._expansion_city_controls_catalogue=None
    t.transport.require_empty_native_queue();b.control(empty=True)
    from .native import native_saved_city_focus1000 as focus,native_saved_citizens as citizens
    before=deepcopy(observation);sequence=t.sequence
    focus_values=[];citizen_values=[] if flags[1] else None;actions=[]
    for city in sorted(before['cities'],key=lambda c:c['id']):
        value=focus.catalog(p,city['id'],before['turn'],player_id=before['player_id'],
            diagnostic_ui_enabled=True,core_sha256=b.load_abi.core_sha256)
        focus_values.append(value);actions.extend(focus.actions(value))
        if flags[1]:
            value=citizens.catalog(p,city['id'],before['turn'],player_id=before['player_id'],
                diagnostic_ui_enabled=True,core_sha256=b.load_abi.core_sha256)
            citizen_values.append(value);actions.extend(citizens.actions(value))
    from civ6_host.contracts.capability_city_controls import validate_catalogs
    expected=validate_catalogs(focus_values,citizen_values,before['player_id'],before['turn'],observation=before)
    # Family ordering is stable and does not sample native targets.
    actions=expected['city_focus']+expected['city_citizen']
    actual=_check(saved,active=False)
    if (any(a is not e for a,e in zip(actual[:4],(b,t,p,identity)))
            or t.sequence!=sequence or t.observation!=before):
        raise ValueError('City-control query crossed an owner or public revision')
    t.transport.require_empty_native_queue();b.control(empty=True)
    catalogue=_Catalogue(saved,b,t,p,identity,sequence,before,deepcopy(focus_values),deepcopy(citizen_values),tuple(deepcopy(actions)))
    t._expansion_city_controls_catalogue=catalogue
    return dict(city_focus_catalogs=deepcopy(focus_values),citizen_catalogs=deepcopy(citizen_values),actions=deepcopy(actions))


class _BoundCityOwner:
    __slots__=('saved','catalogue','receipt')
    def __init__(self,saved,catalogue):self.saved,self.catalogue,self.receipt=saved,catalogue,None
    def emit(self,stage,**payload):
        b,_,_,_,_=_check(self.saved,self.catalogue,active=True)
        if stage in ('official_explicit_city_focus_effect1000','official_explicit_city_citizen_effect'):
            if self.receipt is not None:raise RuntimeError('City control emitted duplicate native results')
            self.receipt=deepcopy(payload)
            self.receipt.update(source_proof_sha256=SOURCE[1],core_sha256=b.load_abi.core_sha256,
                captured_ui_gate_source_selected=True,qualification='source and fixture candidate; native expansion qualification required')
        self.saved.emit(stage,**(self.receipt if self.receipt is not None else payload))


def apply(saved,action,before):
    _,t,_,_,_=_check(saved,active=True);catalogue=getattr(t,'_expansion_city_controls_catalogue',None)
    if type(catalogue) is not _Catalogue:raise ValueError('City control lacks its exact queried catalogue')
    b,t,p,_,_=_check(saved,catalogue,active=True)
    from civ6_host.contracts.capability_city_controls import validate_action
    validate_action(action)
    if type(before) is not dict or before!=catalogue.observation or action not in catalogue.actions:
        raise ValueError('City control was not offered at this exact public boundary')
    from .native import native_saved_city_focus1000 as focus,native_saved_citizens as citizens
    module=focus if action['kind']=='city_focus' else citizens
    owner=_BoundCityOwner(saved,catalogue);count=t.publication_count
    try:
        observed=module.apply(owner,p,action,before['turn'],before,player_id=before['player_id'],
            diagnostic_ui_enabled=True,core_sha256=b.load_abi.core_sha256)
        _check(saved,catalogue,active=True);receipt=owner.receipt
        if (type(receipt) is not dict or receipt.get('action')!=action
                or receipt.get('observation_before')!=before or receipt.get('observation_after')!=observed
                or receipt.get('automatic_choices_applied') is not False or t.publication_count!=count+1):
            raise RuntimeError('City-control native receipt or publication is inconsistent')
        t.transport.require_empty_native_queue();b.control(empty=True)
        return dict(status='completed',refusal_code=None,observation=deepcopy(observed),receipt=deepcopy(receipt))
    finally:t._expansion_city_controls_catalogue=None
