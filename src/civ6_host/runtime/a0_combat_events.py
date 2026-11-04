"""Borrow the existing saved continuation for combat-side host notifications."""
import struct
from .configuration_profiles import XP1_CORE_SHA256,XP2_CORE_SHA256


def enable(owner,backend):
    owner._check();backend.check_thread()
    core_sha256=backend.load_abi.core_sha256
    if (owner.combat_event_profile is not None or owner._foundation_backend is not backend
            or owner.foundation_event_profile is None or owner.arguments.depth or owner.active_kind is not None
            or owner.pending or owner.deferred._draining_empty_receivers
            or owner.host_notification_counter or owner.host_metadata_counter
            or backend.stage!='prepared' or backend.prefix is not None
            or core_sha256 not in (XP1_CORE_SHA256,XP2_CORE_SHA256)
            or backend.host is not owner.arguments.host or backend.core is not owner.deferred.core
            or backend.context!=owner.deferred.context
            or owner.deferred.combat_map_registry is not None or owner.deferred.combat_receiver is not None):
        raise ValueError('Combat callbacks require the original prepared idle saved owner')
    from .combat_event_profile import bind_owner
    from .native.native_combat_receiver import validate_receiver_profile
    from .native.native_deferred_empty_profile import validate_empty_profile_record
    profile=bind_owner(backend,backend.core,owner.read)
    if any(owner.handles_kind(kind) for kind in profile.record_types_by_kind):
        raise ValueError('Combat callbacks overlap an installed producer')
    validate_receiver_profile(owner.empty_receiver_state)
    for kind,size in profile.record_sizes.items():
        if kind==248:continue
        shape=bytearray(size);struct.pack_into('<II',shape,0,size,kind)
        validate_empty_profile_record(shape,**owner.empty_receiver_state)
    if hasattr(owner,'_combat_producer_poisoned') or hasattr(owner,'_experience_producer_poisoned'):
        raise ValueError('Combat producer state already exists')
    owner._combat_producer_poisoned=owner._experience_producer_poisoned=False
    owner.combat_event_profile=owner._combat_event_profile=profile
    return owner


def predicate(owner,signed_owner):
    from .a0_foundation_events import require_borrow
    from .native.native_combat_owner_predicate import query_owner
    token=require_borrow(owner)
    return query_owner(token.publisher._facades,signed_owner,owner.read,
                       core_sha256=token.owner.load_abi.core_sha256)


def validate_enqueue(owner,record):
    from .a0_foundation_events import require_borrow
    from .native.native_combat_receiver import validate_receiver_profile
    from .combat_event_profile import event_profile
    token=require_borrow(owner)
    core_sha256=token.owner.load_abi.core_sha256
    if owner.combat_event_profile is not event_profile(core_sha256) or owner.active_kind!=0x8256dbe1:
        raise ValueError('Combat record has no canonical synchronous producer')
    validate_receiver_profile(owner.empty_receiver_state)
    if type(record) is not bytes or len(record)!=128 or struct.unpack_from('<II',record)!=(128,248):
        raise ValueError('Combat producer returned an unexpected record')
    registry=owner.combat_map_registry
    if registry is None or registry.core_sha256!=core_sha256:
        raise ValueError('Combat producer has no selected native registry')
    item=registry.lookup(struct.unpack_from('<I',record,120)[0])
    if item is None or item.closed or item.poisoned or item.core is not token.owner.core:
        raise ValueError('Combat record has no exact live copied map')
