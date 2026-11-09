"""Player-scoped espionage on the retained native XP2 saved session.

Command delivery and mission completion are separate milestones.  This adapter
reports native order readback; a running mission has not yet produced a result.
"""
from copy import deepcopy
from dataclasses import dataclass
import hashlib

from civ6_host.contracts import espionage as contract
from .configuration_profiles import XP2_CORE_SHA256
from .xp1_world_input import _owner


def source_dependencies(*, execution_image=None):
    from .execution_images import ExecutionImageProfile
    if (type(execution_image) is not ExecutionImageProfile
            or execution_image.image_sha256 !=
            '092abfbb2176f8df04b5212f819dc269dd83aea866ff05aaf489904a1ff7c41f'):
        raise ValueError('Espionage requires the pinned current XP2 execution image')
    from .native import native_saved_espionage as native
    return {row['path']: row['sha256'] for row in native.verify_source().values()}


@dataclass(frozen=True)
class _Catalogue:
    saved: object
    backend: object
    continuation: object
    prefix: object
    identity: object
    sequence: int
    observation: dict
    espionage: dict


def _current(saved, record, *, active):
    b, c, p, identity = _owner(saved, active=active)
    if (type(record) is not _Catalogue or record.saved is not saved
            or record.backend is not b or record.continuation is not c
            or record.prefix is not p or record.identity is not identity
            or record.sequence != c.sequence or record.observation != c.observation
            or getattr(c, '_xp2_espionage_catalogue', None) is not record
            or getattr(c, 'explicit_espionage', None) != record.espionage):
        raise ValueError('Espionage catalogue is stale or foreign')
    return b, c, p, identity


def _invalidate(c):
    c._xp2_espionage_catalogue = None
    c.explicit_espionage = None


def catalogue(saved, observation):
    from .native import native_saved_espionage as native
    b, c, p, identity = _owner(saved, active=False)
    if b.load_abi.core_sha256 != XP2_CORE_SHA256:
        raise ValueError('Espionage requires the selected XP2 engine')
    if type(observation) is not dict or observation != c.observation:
        raise ValueError('Espionage query requires its current observation')
    source_dependencies(execution_image=getattr(b.core, '_civ6_host_execution_image', None))
    _invalidate(c)
    before, sequence = deepcopy(observation), c.sequence
    c.transport.require_empty_native_queue()
    b.control(empty=True)
    state = native.catalog(p, before['turn'], player_id=before['player_id'])
    contract.compare_own(state, before)
    actual = _owner(saved, active=False)
    if (any(x is not y for x, y in zip(actual, (b, c, p, identity)))
            or c.sequence != sequence or c.observation != before):
        raise ValueError('Espionage query crossed its owner or observation revision')
    c.transport.require_empty_native_queue()
    b.control(empty=True)
    record = _Catalogue(saved, b, c, p, identity, sequence, before, deepcopy(state))
    c.explicit_espionage = deepcopy(state)
    c._xp2_espionage_catalogue = record
    return deepcopy(state)


def apply(saved, action, before):
    """Revalidate an offered command in the engine and read its actual state."""
    from .native import native_saved_espionage as native
    from .native.native_player_observation import observe_player
    _, c, _, _ = _owner(saved, active=True)
    record = getattr(c, '_xp2_espionage_catalogue', None)
    b, c, p, _ = _current(saved, record, active=True)
    if before != record.observation or action not in contract.actions(record.espionage):
        raise ValueError('Espionage command was not offered at this observation')
    c.transport.require_empty_native_queue()
    b.control(empty=True)
    count = c.publication_count
    request = native.request_source(action, record.espionage)
    raw = p.runtime.evaluate_text(p.ui_child, request, b'@xp2_espionage_request', capacity=1048576)
    if raw == b'refused':
        c.transport.require_empty_native_queue()
        b.control(empty=True)
        after = observe_player(p.runtime, p.ui_child, before['player_id'])
        _invalidate(c)
        return dict(status='refused', refusal_code='native_spy_choice_unavailable',
                    observation=deepcopy(after), receipt=dict(action=deepcopy(action),
                        native_archive_delivered=False, native_effect_readback=False))
    if raw != b'submitted' or len(p.actions.pending) != 1:
        raise RuntimeError('Native spy request did not enqueue exactly one action')
    archive_sha256 = hashlib.sha256(p.actions.pending[0]).hexdigest()
    p.actions.deliver_one()
    p.deferred_events.drain_empty_receivers()
    feedback = c.flush_trade_feedback()
    if p.deferred_events.pending:
        raise RuntimeError('Espionage feedback left native events unconsumed')
    p.view_publisher.publish()
    c.transport.require_empty_native_queue()
    b.control(empty=True)
    after = observe_player(p.runtime, p.ui_child, before['player_id'])
    refreshed = native.catalog(p, after['turn'], player_id=after['player_id'])
    contract.compare_own(refreshed, after)
    # Query native order state after publication, using the same official
    # operation identity as dispatch.  Archive delivery alone is not an effect.
    effect = native.read_effect(p, action, record.espionage, refreshed)
    if (type(effect) is not dict or set(effect) != {'applied', 'pending'}
            or any(type(effect[k]) is not bool for k in effect)
            or effect['applied'] == effect['pending']):
        raise RuntimeError('Unknown native espionage order readback')
    if c.publication_count != count + 1:
        raise RuntimeError('Espionage command publication did not advance once')
    receipt = dict(stage='official_explicit_espionage_order', action=deepcopy(action),
        native_archive_sha256=archive_sha256, native_archive_delivered=True,
        native_effect_readback=effect['applied'], native_order_pending=effect['pending'],
        mission_completion_claimed=False, automatic_choices_applied=False,
        gameplay_feedback=deepcopy(feedback), espionage_after=deepcopy(refreshed))
    _invalidate(c)
    saved.emit(receipt['stage'], receipt=deepcopy(receipt),
        observation_before=deepcopy(before), observation_after=deepcopy(after),
        catalogue_before=deepcopy(record.espionage), catalogue_after=deepcopy(refreshed))
    return dict(status='completed' if effect['applied'] else 'pending', refusal_code=None,
                observation=deepcopy(after), receipt=receipt)
