"""Explicit ordinary Congress review lifetime, separate from A0 subscribers.

Only an explicit open creates visibility. Catalogue reads may discard a stale
local view but never acknowledge gameplay. Existing transport owns all requests.
"""
from copy import deepcopy
from dataclasses import dataclass
import hashlib
from pathlib import Path

from .configuration_profiles import XP2_CORE_SHA256, _source
from .a0_family_source import _path, verify_pinned_files

SOURCE = ('work/trade-common-client/congress-popup-lifetime-source.json',
          '06a2d74b91d07b9bc4fdd135afc249410d7d84b28a51aac6dfc72f084343e835')
_FIELDS = frozenset(('capability','current_era','initial_era','has_emergency_proposals'))
_SEAL = object()


def source_dependencies():
    proof = _source(SOURCE)
    if (proof['schema'] != 'civ6-host.congress-popup-lifetime-source.static.v1'
            or proof['scope']['static_only'] is not True
            or proof['scope']['native_execution'] is not False
            or proof['scope']['ordinary_available_review_only'] is not True
            or proof['confirmation']['no_submit_or_end_turn'] is not True):
        raise ValueError('Congress review source contract changed')
    pins = {str(_path(SOURCE[0]).resolve()): SOURCE[1]}
    pins.update({str(Path(row['path']).resolve()):row['sha256']
                 for row in proof['source_files'].values()})
    parent = proof['parent_inventory']
    pins[str(Path(parent['path']).resolve())] = parent['sha256']
    verify_pinned_files(pins)
    return pins


def _binding(saved):
    from .xp1_world_input import _owner
    from .a0_policy_unlock_current import _require_image
    active = getattr(getattr(saved,'backend',None),'busy',None)
    if type(active) is not bool:
        raise ValueError('Congress review lacks an exact active/ready owner')
    b,c,p,identity = _owner(saved,active=active)
    if b.load_abi.core_sha256 != XP2_CORE_SHA256:
        raise ValueError('Congress review requires the selected XP2 owner')
    _require_image(getattr(b.core,'_civ6_host_execution_image',None))
    source_dependencies()
    return b,c,p,identity


def _scope(public):
    return (public['player_id'],public['turn'],public['turn_segment'],
            public['stage'],public['in_session'])


@dataclass(frozen=True)
class _Review:
    saved: object
    backend: object
    continuation: object
    prefix: object
    identity: object
    scope: tuple
    opened_sequence: int
    source_sha256: str
    starting_favor: float


@dataclass(frozen=True)
class _ClosePermit:
    seal: object
    review: _Review
    revision: int
    observation: dict


def _current(saved, public=None):
    b,c,p,identity = _binding(saved)
    review = getattr(c,'_xp2_world_congress_review',None)
    if review is not None and (type(review) is not _Review or review.saved is not saved
            or review.backend is not b or review.continuation is not c
            or review.prefix is not p or review.identity is not identity
            or review.source_sha256 != SOURCE[1]):
        raise ValueError('Congress review lost its original owner or source')
    if public is not None:
        if (public['player_id'] != c.observation['player_id']
                or public['turn'] != c.observation['turn']):
            raise ValueError('Congress review has a foreign player observation')
        if review is not None and review.scope != _scope(public):
            c._xp2_world_congress_review = None
            saved.emit('congress_review_invalidated',previous_scope=review.scope,
                current_scope=_scope(public),native_acknowledgement_issued=False,
                native_event_replayed=False,simulation_request_issued=False,
                automatic_timeout_lifecycle_qualified=False)
            review = None
    return b,c,p,identity,review


def _opening(private):
    value = private.get('popup') if type(private) is dict else None
    if type(value) is not dict or set(value) != _FIELDS:
        raise ValueError('Congress opening gates are absent or malformed')
    if (type(value['capability']) is not bool
            or type(value['has_emergency_proposals']) is not bool
            or any(type(value[k]) is not int or not -2147483648<=value[k]<=2147483647
                   for k in ('current_era','initial_era'))):
        raise ValueError('Congress opening gates differ from native types')
    return value


def _proposal_choice(public):
    rows = public['proposals'] or []
    # Disabled native entries start selected (votes=1), so their target also
    # disables another checkbox. Preserve this part of UpdateAvailableProposal.
    selected = {row['target_key'] for row in rows if row['disabled']}
    return any(not row['disabled'] and row['target_key'] not in selected
               and row['favor_cost'] <= public['favor'] for row in rows)


def catalogue_state(saved, public, private):
    """Project owned presentation; never open or send a native acknowledgement."""
    _,_,_,_,review = _current(saved,public)
    gates = _opening(private)
    ordinary = public['stage']=='ordinary' and public['in_session'] is False
    visible = review is not None
    return dict(presentation='available_proposals' if visible else 'closed',
        open=(not visible and ordinary and public['paused'] is False
              and public['local_alive'] is True and gates['capability']
              and gates['current_era']>=gates['initial_era']
              and gates['has_emergency_proposals']),
        confirm_proposals=bool(visible and ordinary and not public['paused']
                               and _proposal_choice(dict(public, favor=review.starting_favor))),
        close=bool(visible and ordinary))


def budget_limit(saved, public):
    """SetStage's displayed starting favor is retained until this review closes."""
    review = _current(saved, public)[4]
    return public['favor'] if review is None else review.starting_favor


def apply_open(saved, public, private):
    if not catalogue_state(saved,public,private)['open']:
        raise ValueError('Congress explicit opening is no longer available')
    b,c,p,identity,review = _current(saved,public)
    if review is not None:
        raise ValueError('Congress review already visible')
    sequence = public['sequence']
    if type(sequence) is not int or not 0<=sequence<=0xffffffff:
        raise ValueError('Congress open sequence is malformed')
    c._xp2_world_congress_review = _Review(saved,b,c,p,identity,
                                          _scope(public),sequence,SOURCE[1],public['favor'])
    return dict(local_presentation_opened=True,presentation='available_proposals',
                simulation_request_issued=False,native_archive_delivered=False,
                native_effect_readback=False,native_acknowledgement_issued=False)


def prepare_close(saved, public, private, *, confirmation=False):
    if type(confirmation) is not bool:
        raise ValueError('Congress close intent must be explicit')
    state = catalogue_state(saved,public,private)
    if not state['close'] or (confirmation and not state['confirm_proposals']):
        raise ValueError('Congress review close/confirmation is stale or unavailable')
    _,c,_,_,review = _current(saved,public)
    return _ClosePermit(_SEAL,review,c.sequence,deepcopy(c.observation))


def commit_close(saved, permit):
    """Consume visibility before RequestLOOKED, even if that request refuses.

    For proposals, the caller first enqueues selected discussion requests, then
    calls this method, then enqueues LOOKED. It delivers the batch afterward.
    """
    _,c,_,_,review = _current(saved)
    if (type(permit) is not _ClosePermit or permit.seal is not _SEAL
            or review is None or permit.review is not review
            or permit.revision != c.sequence or permit.observation != c.observation):
        raise ValueError('Congress close permit is stale, repeated or foreign')
    c._xp2_world_congress_review = None
    return dict(local_presentation_closed=True,presentation='closed',
                simulation_request_issued=False,native_archive_delivered=False,
                native_effect_readback=False,native_acknowledgement_issued=False)


def check_checkpoint(saved):
    if _current(saved)[4] is not None:
        raise ValueError('Close the owned Congress review before checkpoint or voluntary end turn')
