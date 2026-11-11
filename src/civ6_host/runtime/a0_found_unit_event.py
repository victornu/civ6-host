"""XP1 UnitActivityChanged queries with the existing EXE codec and FIFO."""
import struct
from types import MappingProxyType
from .configuration_profiles import XP1_CORE_SHA256, XP2_CORE_SHA256
from .a0_family_source import A0FamilyProfile
from .native import native_found_city_event as codec
from .native.native_deferred_empty_profile import validate_empty_profile_record, _ROWS


def enable(owner):
    owner._check()
    if (owner.found_unit_event_profile is not None or owner.arguments.depth or owner.active_kind is not None
            or owner.pending or owner.deferred._draining_empty_receivers
            or owner.host_notification_counter or owner.host_metadata_counter):
        raise ValueError('Unit activity event needs its idle original A0 owner')
    from .found_unit_event_profiles import (verify_live,SOURCE,XP2_MAP_SOURCE)
    core_sha256=owner.deferred.cache_core_sha256
    if core_sha256 not in (XP1_CORE_SHA256,XP2_CORE_SHA256):
        raise ValueError('Unit activity event has no selected Core query profile')
    execution_image = (getattr(owner.deferred.core, '_civ6_host_execution_image', None)
                       if core_sha256 == XP2_CORE_SHA256 else None)
    verify_live(owner.deferred.core._handle,owner.read,core_sha256=core_sha256,
        execution_image=execution_image)
    if owner.handles_kind(codec.EVENT_KIND) or _ROWS[0x23]['handler_va']!='0x1400d6cd0' or _ROWS[0x23]['record_sizes']!={128}:
        raise ValueError('Unit activity event overlaps or has a different receiver')
    record=bytearray(128);struct.pack_into('<II',record,0,128,0x23)
    validate_empty_profile_record(record,**owner.empty_receiver_state)
    source_sha=XP2_MAP_SOURCE[1] if core_sha256==XP2_CORE_SHA256 else SOURCE[1]
    profile=A0FamilyProfile(MappingProxyType({codec.EVENT_KIND:frozenset((0x23,))}),
        MappingProxyType({0x23:128}),source_sha)
    owner.found_unit_event_profile=owner._found_unit_event_profile=profile
    return owner


def dispatch(owner,kind,fields):
    # ``enable`` installs one selected profile, but its local imports do not
    # define this function's globals. Resolve both exact source pins in the
    # callback path that rechecks the installed profile before enqueue.
    from .found_unit_event_profiles import SOURCE,XP2_MAP_SOURCE
    if kind!=codec.EVENT_KIND or len(owner.pending)>=owner.limit:
        raise ValueError('Unit activity event kind or queue bound differs')
    identity=codec.decode_found_city_fields(fields,owner.read)
    core_sha256=owner.deferred.cache_core_sha256
    if core_sha256 not in (XP1_CORE_SHA256,XP2_CORE_SHA256):
        raise ValueError('Unit activity event Core selection changed')
    if owner.found_unit_event_profile.source_sha256 != (
            XP2_MAP_SOURCE[1] if core_sha256==XP2_CORE_SHA256 else SOURCE[1]):
        raise ValueError('Unit activity event source selection changed')
    execution_image = (getattr(owner.deferred.core, '_civ6_host_execution_image', None)
                       if core_sha256 == XP2_CORE_SHA256 else None)
    query=(codec.query_unit_parameters(owner.deferred.core,owner.deferred.context,identity,
        incoming_selector=identity['selector'],read=owner.read,core_sha256=core_sha256,
        execution_image=execution_image)
        if identity['selector']==codec.SELECTOR else None)
    record=codec.encode_record(owner._sequence+1,identity,query,queue_callback_result=0,padding_policy='zero')
    owner._enqueue(record)
    owner.emit('native_deferred_host_event_enqueued',dispatch_kind=hex(kind),queue_type='0x23',
        record_hex=record.hex(),unit_identity=identity,native_unit_query=query,
        native_unit_query_required=identity['selector']==codec.SELECTOR,pending_count=len(owner.pending),
        native_dispatch_return=0,source_sha256=owner.found_unit_event_profile.source_sha256,
        optional_preprocessing_hook_registered=False,queue_metadata_service_registered=False,
        unspecified_padding_policy='zero',consumer_validated=False,eligible_for_training=False)
    return 0
