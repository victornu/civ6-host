"""Own the shared private notification ring without duplicating its algorithms.

Only the existing explicit empty receiver profile is admitted. Native gameplay
and private EXE listeners are never emulated by a successful dummy callback.
"""
from dataclasses import dataclass
import struct
from .configuration_profiles import XP1_CORE_SHA256, XP2_CORE_SHA256
from .native.native_host_events import NativeDeferredHostEvents,SharedHostEventDispatch
from .native.native_private_ring_profile import NativePrivateRingProfile
from .native.native_private_ring_consumer import EMPTY_RECEIVER_PROFILE
from .native.native_deferred_empty_profile import validate_empty_profile_record
from . import xp1_private_notification_profile as source


@dataclass(frozen=True)
class PrivateBinding:
    owner:object
    deferred:object
    ring:object
    profile:object
    core_sha256:str


def _binding(owner):
    b=getattr(owner,'_private_notification_binding',None)
    if (type(b) is not PrivateBinding or b.owner is not owner or b.deferred is not owner.deferred
            or getattr(owner,'private_notification_profile',None) is not b.profile
            or getattr(owner,'_private_notification_profile',None) is not b.profile
            or owner.private_progress_ring is not b.ring or type(b.ring) is not NativePrivateRingProfile
            or b.ring.profile!=EMPTY_RECEIVER_PROFILE or owner.closed or owner.quarantined
            or owner.deferred.closed or owner.deferred.quarantined
            or owner.arguments.host._a0_family_owner is not owner
            or owner.deferred.cache_core_sha256!=b.core_sha256
            or b.profile.source_sha256!=source.source_reference(core_sha256=b.core_sha256)[1]):
        raise ValueError('Private notification owner, profile or ring lifetime changed')
    if b.ring.poisoned:raise RuntimeError('Private notification ring is poisoned')
    return b


def enable(owner):
    owner._check()
    if (getattr(owner,'private_notification_profile',None) is not None
            or getattr(owner,'_private_notification_binding',None) is not None
            or getattr(owner,'private_progress_ring',None) is not None
            or owner.arguments.depth or owner.active_kind is not None or owner.pending
            or owner.deferred._draining_empty_receivers
            or owner.host_notification_counter or owner.host_metadata_counter
            or owner.deferred.cache_core_sha256 not in (XP1_CORE_SHA256,XP2_CORE_SHA256)):
        raise ValueError('Private notifications require the original idle expansion owner')
    core_sha256=owner.deferred.cache_core_sha256
    profile=source.event_profile(core_sha256=core_sha256)
    if any(owner.handles_kind(k) for k in profile.record_types_by_kind):
        raise ValueError('Private notification event already has a producer')
    source.verify_live(owner.deferred.core._handle,owner.read,core_sha256=core_sha256)
    record=bytearray(96);struct.pack_into('<II',record,0,96,5)
    validate_empty_profile_record(record,**owner.empty_receiver_state)
    # Reuse exact shared initializers and source-owned two-bank state. No live
    # original EXE listener table is claimed to have been inspected.
    ring=NativeDeferredHostEvents._private_ring(owner)
    if type(ring) is not NativePrivateRingProfile or ring.selector!=0 or ring.cursors!=(0,0):
        raise ValueError('Private ring was not freshly source initialized')
    owner.private_notification_profile=owner._private_notification_profile=profile
    owner._private_notification_binding=PrivateBinding(owner,owner.deferred,ring,profile,core_sha256)
    return owner


def get_ring(owner):
    return _binding(owner).ring


def dispatch(owner,kind,fields):
    b=_binding(owner)
    if kind not in b.profile.record_types_by_kind or owner.active_kind!=kind:
        raise ValueError('Private notification dispatched outside its admitted A0 kind')
    n,m=owner.host_notification_counter,owner.host_metadata_counter
    before_sequence,before_count=owner._sequence,len(owner.pending)
    selector=b.ring.selector;cursors=b.ring.cursors
    result=SharedHostEventDispatch._dispatch_fields(owner,kind,fields)
    after=b.ring.cursors;bank=selector&1;standard=int(kind==0x66ade3b3)
    if (result!=0 or (owner.host_notification_counter,owner.host_metadata_counter)!=(n,m)
            or owner._sequence!=before_sequence+standard or len(owner.pending)!=before_count+standard
            or b.ring.selector!=selector or after[bank]!=cursors[bank]+128
            or after[1-bank]!=cursors[1-bank]):
        raise RuntimeError('Private notification changed counters, dual ordering or ring reservation')
    return result


def drain(owner,*,loaded_lifetime=None):
    # Caller drains the actual standard FIFO first, including the dual type5.
    # The loaded lifetime token remains the authority after native Unload.
    owner._check(loaded_lifetime=loaded_lifetime)
    _binding(owner)
    if owner.arguments.depth or owner.active_kind is not None or owner.pending:
        raise ValueError('Private notification drain requires completed standard FIFO')
    return NativeDeferredHostEvents.drain_private_empty_receivers(owner)


def check_close(owner):
    b=_binding(owner)
    if (owner.arguments.depth or owner.active_kind is not None or owner.pending
            or owner.deferred._draining_empty_receivers
            or b.ring.cursors[b.ring.selector&1]!=0):
        raise RuntimeError('Private notification ring still has unconsumed records')
    # The consumed bank cursor intentionally stays nonzero until bank reuse.
    return b.ring.diagnostic()
