"""Production queue queries and commands on the retained XP1 session.

The common native queue adapter owns enumeration, request and effect checking.
This adapter only joins its catalogue to the existing saved-session lifetime.
"""
from copy import deepcopy
from dataclasses import dataclass
from .configuration_profiles import XP1_CORE_SHA256
from .xp1_world_input import _owner


@dataclass(frozen=True)
class _Catalogue:
    saved: object
    backend: object
    continuation: object
    prefix: object
    identity: object
    sequence: int
    observation: dict
    queues: list
    actions: tuple


def _current(saved, catalogue):
    b, c, p, identity = _owner(saved, active=True)
    if (type(catalogue) is not _Catalogue or catalogue.saved is not saved
            or catalogue.backend is not b or catalogue.continuation is not c
            or catalogue.prefix is not p or catalogue.identity is not identity
            or catalogue.sequence != c.sequence or catalogue.observation != c.observation
            or getattr(c, '_xp1_production_queue_catalogue', None) is not catalogue
            or getattr(c, 'explicit_production_queues', None) != catalogue.queues):
        raise ValueError('Production queue catalogue is stale or foreign')
    return b, c, p, identity


class _BoundQueueOwner:
    def __init__(self, saved, catalogue):
        self.saved, self.catalogue, self.receipt = saved, catalogue, None

    @property
    def explicit_production_queues(self):
        return _current(self.saved, self.catalogue)[1].explicit_production_queues

    def emit(self, stage, **payload):
        _current(self.saved, self.catalogue)
        if stage == 'official_explicit_production_queue_effect':
            if self.receipt is not None:
                raise RuntimeError('Queue command emitted more than one effect')
            self.receipt = deepcopy(payload)
        self.saved.emit(stage, **payload)


def read(saved, observation):
    from .xp1_production_queue_profile import bind_owner, gate_admitted
    from .native import native_saved_production_queue as queues
    b, c, p, identity = _owner(saved, active=False)
    if type(observation) is not dict or observation != c.observation:
        raise ValueError('Production queues require the current observation')
    bind_owner(b, b.core, b.runtime.read)
    c._xp1_production_queue_catalogue = c.explicit_production_queues = None
    before, sequence = deepcopy(observation), c.sequence
    enabled = gate_admitted(c)
    if type(enabled) is not bool:
        raise TypeError('Production queue UI admission must be exact')
    state = [queues.catalog(p, city['id'], before['turn'], player_id=before['player_id'],
                            enabled=enabled, core_sha256=b.load_abi.core_sha256)
             for city in before['cities']]
    queues.validate_all(state, before['player_id'], before['turn'])
    queues.check_heads(state, c.explicit_production_snapshot)
    actions = [action for row in state for action in queues.actions(row)]
    actual = _owner(saved, active=False)
    if (any(a is not e for a, e in zip(actual, (b, c, p, identity)))
            or c.sequence != sequence or c.observation != before):
        raise ValueError('Queue enumeration crossed its owner or observation revision')
    c.transport.require_empty_native_queue(); b.control(empty=True)
    catalogue = _Catalogue(saved, b, c, p, identity, sequence, before,
                           deepcopy(state), tuple(deepcopy(actions)))
    c.explicit_production_queues = deepcopy(state)
    c._xp1_production_queue_catalogue = catalogue
    return dict(production_queues=deepcopy(state), actions=deepcopy(actions))


def apply(saved, action, before):
    from .native import native_saved_production_queue as queues
    _, c, _, _ = _owner(saved, active=True)
    catalogue = getattr(c, '_xp1_production_queue_catalogue', None)
    b, c, p, _ = _current(saved, catalogue)
    queues.validate_action(action)
    if before != catalogue.observation or action not in catalogue.actions:
        raise ValueError('Queue action was not offered at this observation')
    count = c.publication_count
    owner = _BoundQueueOwner(saved, catalogue)
    try:
        observed = queues.apply(owner, p, action, before['turn'], before,
                                player_id=before['player_id'], core_sha256=b.load_abi.core_sha256,
                                gate_owner=c)
        _current(saved, catalogue)
        from .xp1_production_queue_profile import source_reference
        SOURCE=source_reference(b.load_abi.core_sha256)
        receipt = owner.receipt
        if (c.publication_count != count + 1 or type(receipt) is not dict
                or receipt.get('action') != action or receipt.get('native_archive_delivered') is not True
                or receipt.get('automatic_choices_applied') is not False
                or receipt.get('tutorial_gate_qualified') is not True
                or receipt.get('source_proof_sha256') != SOURCE[1]
                or receipt.get('public_source_proof_sha256') != SOURCE[1]):
            raise RuntimeError('Production queue command has no exact native effect/publication')
        c.transport.require_empty_native_queue(); b.control(empty=True)
        return dict(status='completed', refusal_code=None, observation=deepcopy(observed), receipt=deepcopy(receipt))
    finally:
        c._xp1_production_queue_catalogue = c.explicit_production_queues = None
