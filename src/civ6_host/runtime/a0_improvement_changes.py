"""Admit the two source-selected plot notifications on the saved owner's FIFO."""
import struct
from .configuration_profiles import XP1_CORE_SHA256,XP2_CORE_SHA256


def enable(owner,backend):
    owner._check();backend.check_thread()
    if (owner.improvement_change_profile is not None or owner._foundation_backend is not backend
            or owner.foundation_event_profile is None or owner.turn_unit_event_profile is None
            or owner.arguments.depth or owner.active_kind is not None or owner.pending
            or owner.deferred._draining_empty_receivers or owner.host_notification_counter or owner.host_metadata_counter
            or backend.stage!='prepared' or backend.prefix is not None
            or backend.load_abi.core_sha256 not in (XP1_CORE_SHA256,XP2_CORE_SHA256)
            or backend.host is not owner.arguments.host or backend.core is not owner.deferred.core
            or backend.context!=owner.deferred.context):
        raise ValueError('Improvement/route callbacks require the original idle prepared saved owner')
    from .improvement_change_profile import bind_owner,event_profile
    from .native.native_deferred_empty_profile import validate_empty_profile_record
    execution_image=getattr(backend.core,'_civ6_host_execution_image',None)
    bind_owner(backend,backend.core,owner.read,execution_image=execution_image)
    profile=event_profile(core_sha256=backend.load_abi.core_sha256,execution_image=execution_image)
    if any(owner.handles_kind(kind) for kind in profile.record_types_by_kind):
        raise ValueError('Improvement/route callbacks overlap an existing producer')
    for kind,size in profile.record_sizes.items():
        shape=bytearray(size);struct.pack_into('<II',shape,0,size,kind)
        validate_empty_profile_record(shape,**owner.empty_receiver_state)
    owner.improvement_change_profile=owner._improvement_change_profile=profile
    return owner
