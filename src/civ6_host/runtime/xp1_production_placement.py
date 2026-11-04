"""Shared native placement/resumption on the exact retained XP1 session."""
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
    production: dict
    tracking: dict
    offers: list
    progress: list


def _current(saved, catalogue, *, tracking=False):
    b, c, p, identity = _owner(saved, active=True)
    if (type(catalogue) is not _Catalogue or catalogue.saved is not saved
            or catalogue.backend is not b or catalogue.continuation is not c
            or catalogue.prefix is not p or catalogue.identity is not identity
            or catalogue.sequence != c.sequence or catalogue.observation != c.observation
            or getattr(c, '_xp1_placement_catalogue', None) is not catalogue
            or c.explicit_production_snapshot != catalogue.production
            or tracking and c.explicit_placements != catalogue.tracking):
        raise ValueError('Placement catalogue is stale or foreign')
    return b, c, p, identity


class _BoundPlacementOwner:
    def __init__(self, saved, catalogue):
        self.saved, self.catalogue, self.receipt = saved, catalogue, None

    @property
    def explicit_production_snapshot(self):
        return _current(self.saved, self.catalogue)[1].explicit_production_snapshot

    @property
    def explicit_placements(self):
        return deepcopy(_current(self.saved, self.catalogue)[1].explicit_placements)

    @explicit_placements.setter
    def explicit_placements(self, value):
        _current(self.saved, self.catalogue)[1].explicit_placements = deepcopy(value)

    def emit(self, stage, **payload):
        _current(self.saved, self.catalogue)
        if stage in ('official_explicit_placement_effect', 'official_explicit_production_resume_effect'):
            if self.receipt is not None:
                raise RuntimeError('Placement command emitted more than one effect')
            self.receipt = deepcopy(payload)
        self.saved.emit(stage, **payload)


def read(saved, observation):
    from .xp1_production_placement_profile import bind_owner
    from .native import native_saved_placement as placed
    b, c, p, identity = _owner(saved, active=False)
    if type(observation) is not dict or observation != c.observation:
        raise ValueError('Placements require the current player observation')
    bind_owner(b, b.core, b.runtime.read)
    c._xp1_placement_catalogue = None
    before, sequence = deepcopy(observation), c.sequence
    production, tracking = deepcopy(c.explicit_production_snapshot), deepcopy(c.explicit_placements)
    offers = []
    for city in before['cities']:
        catalog = placed.catalog(p, city['id'], before['turn'], player_id=before['player_id'],
                                 core_sha256=b.load_abi.core_sha256)
        offers.extend(placed.actions(catalog, city['id'], player_id=before['player_id']))
    progress = placed.progress(c, p, before['turn'], player_id=before['player_id'],
                               core_sha256=b.load_abi.core_sha256)
    placed.validate_offers(offers, player_id=before['player_id'])
    placed.validate_progress(progress, before['turn'], player_id=before['player_id'])
    actual = _owner(saved, active=False)
    if (any(a is not e for a, e in zip(actual, (b, c, p, identity)))
            or c.sequence != sequence or c.observation != before
            or c.explicit_production_snapshot != production or c.explicit_placements != tracking):
        raise ValueError('Placement enumeration crossed its owner or observation revision')
    c.transport.require_empty_native_queue(); b.control(empty=True)
    c._xp1_placement_catalogue = _Catalogue(saved, b, c, p, identity, sequence,
        before, production, tracking, deepcopy(offers), deepcopy(progress))
    return dict(placement_offers=deepcopy(offers), placements=deepcopy(progress),
                placement_observation_scope='host_tracked', actions=deepcopy(offers))


def apply(saved, action, before):
    from .native import native_saved_placement as placed
    from .explicit_production_operation import apply_placement
    _, c, _, _ = _owner(saved, active=True)
    catalogue = getattr(c, '_xp1_placement_catalogue', None)
    b, c, p, _ = _current(saved, catalogue, tracking=True)
    placed.validate_action(action, player_id=before['player_id'])
    if before != catalogue.observation or action not in catalogue.offers:
        raise ValueError('Placement action was not offered at this observation')
    count = c.publication_count
    owner = _BoundPlacementOwner(saved, catalogue)
    try:
        observed = apply_placement(owner, p, action, before['turn'], before,
            player_id=before['player_id'], core_sha256=b.load_abi.core_sha256)
        _current(saved, catalogue)
        receipt = owner.receipt
        if (c.publication_count != count + 1 or type(receipt) is not dict
                or receipt.get('action') != action
                or receipt.get('observation_before') != before
                or receipt.get('observation_after') != observed
                or receipt.get('automatic_choices_applied') is not False):
            raise RuntimeError('Placement command has no exact native effect/publication')
        c.transport.require_empty_native_queue(); b.control(empty=True)
        return dict(status='completed', refusal_code=None,
                    observation=deepcopy(observed), receipt=deepcopy(receipt))
    finally:
        c._xp1_placement_catalogue = None
