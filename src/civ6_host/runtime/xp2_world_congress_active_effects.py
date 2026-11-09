"""Current Effects display on the existing owned Congress query boundary."""
from copy import deepcopy


def source_dependencies(*,execution_image):
    from .native.native_world_congress_active_effects import source_dependencies as dependencies
    return dependencies(execution_image=execution_image)


def catalogue(saved,observation,*,sequence,congress):
    from civ6_host.contracts import world_congress_active_effects as contract
    from . import xp2_world_congress as current
    from . import xp2_congress_review_configuration as environment
    from .xp2_world_congress_review import _flags,_empty
    from .native import native_world_congress_active_effects as native
    from .native import native_world_congress_review as shared
    from .native.native_saved_unit_orders import uint
    from .xp1_world_input import _owner
    uint(sequence,'sequence',0xffffffff)
    _flags(saved)
    b,c,p,identity=_owner(saved,active=False)
    if observation != c.observation:
        raise ValueError('Congress active effects require the current observation')
    if congress is None:
        return dict(world_congress_active_effects=None,world_congress_active_effects_status='waiting_or_closed')
    record=getattr(c,'_xp2_world_congress_catalogue',None)
    current._check(saved,record,active=False)
    if (congress != record.public or record.observation != observation or record.public['sequence'] != sequence
            or (record.public['player_id'],record.public['turn']) != (observation['player_id'],observation['turn'])):
        raise ValueError('Congress active effects are not joined to the exact current catalogue')
    source_dependencies(execution_image=getattr(b.core,'_civ6_host_execution_image',None))
    _empty(b,c,p);current._check(saved,record,active=False)
    admission=dict(public=deepcopy(record.public),private=deepcopy(record.private))
    value=shared.query(p,observation['player_id'],observation['turn'],sequence,
        backend=b,environment=environment,admission=admission,projection=native)
    current._check(saved,record,active=False);_empty(b,c,p);current._check(saved,record,active=False)
    if value is not None:contract.compare_own(value,observation,sequence)
    status='available' if value is not None else 'active_effects_ui_unavailable'
    contract.validate_group(value,status,record.public,observation['player_id'],observation['turn'],sequence)
    return dict(world_congress_active_effects=deepcopy(value),world_congress_active_effects_status=status)
