"""Install the shared district notification producers on the saved owner."""
import struct
from .configuration_profiles import XP1_CORE_SHA256,XP2_CORE_SHA256


def enable(owner,backend):
    owner._check();backend.check_thread()
    if (owner.district_damage_profile is not None or owner._foundation_backend is not backend
            or owner.foundation_event_profile is None or owner.arguments.depth
            or owner.active_kind is not None or owner.pending
            or owner.deferred._draining_empty_receivers or owner.host_notification_counter or owner.host_metadata_counter
            or backend.stage!='prepared' or backend.prefix is not None
            or backend.load_abi.core_sha256 not in (XP1_CORE_SHA256,XP2_CORE_SHA256)
            or backend.host is not owner.arguments.host or backend.core is not owner.deferred.core
            or backend.context!=owner.deferred.context):
        raise ValueError('District callbacks require the original idle prepared saved owner')
    states=('_district_damage_producing','_district_damage_poisoned',
            '_district_combat_producing','_district_combat_poisoned')
    if any(hasattr(owner,name) for name in states):
        raise ValueError('District producer state already exists')
    from .district_damage_profile import bind_owner
    from .native.native_deferred_empty_profile import validate_empty_profile_record
    execution_image=getattr(backend.core,'_civ6_host_execution_image',None)
    profile=bind_owner(backend,backend.core,owner.read,execution_image=execution_image)
    if any(owner.handles_kind(kind) for kind in profile.record_types_by_kind):
        raise ValueError('District callbacks overlap an existing producer')
    for kind,size in profile.record_sizes.items():
        shape=bytearray(size);struct.pack_into('<II',shape,0,size,kind)
        validate_empty_profile_record(shape,**owner.empty_receiver_state)
    for name in states:setattr(owner,name,False)
    owner.district_damage_profile=owner._district_damage_profile=profile
    return owner


def invoke(owner,name,fields):
    """Keep the shared producer, with lifetime/reentry checks on its real owner."""
    from .a0_foundation_events import require_borrow
    from .native.native_host_events import NativeDeferredHostEvents
    require_borrow(owner)
    if name not in ('damage','combat'):raise ValueError('Unknown district producer')
    if (getattr(owner,'_district_'+name+'_producing')
            or getattr(owner,'_district_'+name+'_poisoned')):
        raise RuntimeError('District producer is reentrant or poisoned')
    return getattr(NativeDeferredHostEvents,'_enqueue_district_'+name+'_changed')(owner,fields)


def is_xp2_sibling(owner,kind,fields):
    """Recognize only the initial shared family's XP2 district descriptor path."""
    return (kind==0x754cbd1b and owner.arguments.reader.core_sha256==XP2_CORE_SHA256
            and 0xf343dc5a in fields)


def dispatch_sibling(owner,fields,borrowed_argument):
    from .xp1_continuation import SavedContinuation
    from . import xp2_district_damage_event_source as source
    from .native.native_host_events import SharedHostEventDispatch
    backend=owner._foundation_backend
    token=getattr(backend,'_xp1_continuation',None)
    if (type(token) is not SavedContinuation or token.owner is not backend
            or owner.active_kind!=source.SIBLING_KIND or owner._foundation_borrow is not None):
        raise ValueError('District sibling has no exact active continuation')
    owner._foundation_borrow=token
    try:
        proof=source.validate_sibling_owner(owner,fields)
        result=SharedHostEventDispatch._dispatch_fields(owner,source.SIBLING_KIND,fields,
                                                       borrowed_argument=borrowed_argument)
        owner.emit('native_xp2_district_sibling_source_admitted',dispatch_kind=hex(source.SIBLING_KIND),
            source_proof_sha256=proof,shared_codec_preserved=True,native_dispatch_return=result)
        return result
    finally:
        owner._foundation_borrow=None
