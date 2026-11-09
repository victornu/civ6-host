"""Public last-results readback on the exact owned v37 Congress catalogue.

This optional v38 projection never opens/closes a popup or sends a game action.
Cycle observations stay private and are distinct from submission acknowledgement.
"""
from copy import deepcopy


def source_dependencies(*, execution_image):
    from .xp2_world_congress import review_source_dependencies as cycle_dependencies
    from .native.native_world_congress_active_effects import source_dependencies as effects_dependencies
    result = effects_dependencies(execution_image=execution_image)
    for path, digest in cycle_dependencies(execution_image=execution_image).items():
        if path in result and result[path] != digest:
            raise ValueError('Congress review source closure conflicts')
        result[path] = digest
    return result


def _flags(saved):
    requested = getattr(saved, 'world_congress_review_diagnostic', False)
    prepared = getattr(saved.backend, '_xp2_world_congress_review_requested', False)
    if (type(requested) is not bool or type(prepared) is not bool
            or requested is not True or prepared is not True
            or getattr(saved, 'world_congress_diagnostic', False) is not True):
        raise ValueError('Congress review requires its explicit saved and prepared owner flags')


def _empty(b, c, p):
    c.transport.require_empty_native_queue()
    if p.actions.pending or p.deferred_events.pending:
        raise ValueError('Congress review requires empty action and event queues')
    b.control(empty=True)


def catalogue(saved, observation, *, sequence, congress):
    from civ6_host.contracts import world_congress_review as contract
    from . import xp2_world_congress as current
    from . import xp2_congress_cycle as cycle
    from . import xp2_congress_review_configuration as environment
    from .native import native_world_congress_review as native
    from .native.native_saved_unit_orders import uint
    from .xp1_world_input import _owner
    uint(sequence, 'sequence', 0xffffffff)
    _flags(saved)
    b, c, p, identity = _owner(saved, active=False)
    if observation != c.observation:
        raise ValueError('Congress review requires the current observation')
    if not cycle.enabled(b):
        raise ValueError('Congress review prepared cycle profile is absent')
    if congress is None:
        return dict(world_congress_review=None, world_congress_review_status='waiting_or_closed')
    record = getattr(c, '_xp2_world_congress_catalogue', None)
    current._check(saved, record, active=False)
    if (congress != record.public or record.observation != observation
            or record.public['sequence'] != sequence
            or (record.public['player_id'], record.public['turn']) != (
                observation['player_id'], observation['turn'])):
        raise ValueError('Congress review is not joined to the exact current v37 catalogue')
    source_dependencies(execution_image=getattr(b.core, '_civ6_host_execution_image', None))
    _empty(b, c, p)
    current._check(saved, record, active=False)
    admission = dict(public=deepcopy(record.public), private=deepcopy(record.private))
    permit = (cycle.prepare_review_readback(saved)
              if native.admission_allowed(admission, observation['player_id'], observation['turn'], sequence)
              else None)
    envelope = native.query(p, observation['player_id'], observation['turn'], sequence,
        backend=b, environment=environment, admission=admission, administrative=True)
    current._check(saved, record, active=False)
    _empty(b, c, p)
    current._check(saved, record, active=False)
    value = envelope['public'] if envelope is not None else None
    if value is not None:
        contract.compare_own(value, observation, sequence)
        if value['turn_segment'] != record.public['turn_segment']:
            raise ValueError('Congress review crossed its catalogue turn segment')
        if permit is not None:
            cycle.observe_review(saved, value, permit=permit, administrative=envelope['private'])
            current._check(saved, record, active=False)
            _empty(b, c, p)
    current._check(saved, record, active=False)
    status = 'available' if value is not None else 'review_ui_unavailable'
    contract.validate_group(value, status, record.public,
        observation['player_id'], observation['turn'], sequence)
    return dict(world_congress_review=deepcopy(value), world_congress_review_status=status)
