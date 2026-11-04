"""Three source-bound expansion city/scalar aliases of the shared EXE codec."""
from dataclasses import dataclass
import struct
from types import MappingProxyType
from .a0_family_source import A0FamilyProfile
from .configuration_profiles import XP1_CORE_SHA256, XP2_CORE_SHA256
from .native.native_deferred_empty_profile import validate_empty_profile_record
from .native import native_event_8d005711 as codec


@dataclass(frozen=True)
class CityScalarBinding:
    owner:object
    arguments:object
    deferred:object
    host:object
    core:object
    base:int
    context:int
    core_sha256:str
    records:object
    profile:object


def _require_engine(owner):
    core_sha256=owner.deferred.cache_core_sha256
    if core_sha256==XP2_CORE_SHA256:
        from .event_argument_service import EventArgumentReader
        reader=owner.arguments.reader
        if (type(reader) is not EventArgumentReader or reader.core_sha256!=core_sha256
                or reader.core is not owner.deferred.core or reader.closed
                or reader.base!=owner.deferred.core._handle
                or owner.deferred.base!=reader.base):
            raise ValueError('XP2 city/scalar engine differs from its real argument reader')
    elif core_sha256!=XP1_CORE_SHA256:
        raise ValueError('Unknown city/scalar owner engine')
    return core_sha256


def _binding(owner):
    b=getattr(owner,'_city_scalar_binding',None)
    if (type(b) is not CityScalarBinding or b.owner is not owner
            or owner.arguments is not b.arguments or owner.deferred is not b.deferred
            or owner.arguments.host is not b.host or owner.deferred.host is not b.host
            or owner.deferred.core is not b.core or owner.deferred.context!=b.context
            or owner.deferred.core._handle!=b.base
            or owner.deferred.cache_core_sha256!=b.core_sha256
            or owner._city_scalar_records is not b.records
            or owner.city_scalar_event_profile is not b.profile
            or owner._city_scalar_event_profile is not b.profile):
        raise ValueError('City/scalar owner, engine or source binding changed')
    _require_engine(owner)
    return b


def enable(owner):
    owner._check()
    if (owner.city_scalar_event_profile is not None
            or getattr(owner,'_city_scalar_binding',None) is not None or owner.arguments.depth
            or owner.active_kind is not None or owner.pending
            or owner.deferred._draining_empty_receivers
            or owner.host_notification_counter or owner.host_metadata_counter
            or owner.deferred.cache_core_sha256 not in (XP1_CORE_SHA256,XP2_CORE_SHA256)):
        raise ValueError('City/scalar callbacks require an idle exact expansion event owner')
    from .city_scalar_event_profiles import NEW_KINDS, record_profile, source_dependencies
    core_sha256=_require_engine(owner)
    source_dependencies(core_sha256=core_sha256)
    profiles = {kind: record_profile(kind, core_sha256) for kind in NEW_KINDS}
    if any(owner.handles_kind(kind) for kind in profiles):
        raise ValueError('City/scalar alias overlaps an existing callback owner')
    for profile in profiles.values():
        record = bytearray(profile.record_size)
        struct.pack_into('<II', record, 0, profile.record_size, profile.record_type)
        validate_empty_profile_record(record, **owner.empty_receiver_state)
    owner._city_scalar_records = MappingProxyType(profiles)
    profile = A0FamilyProfile(
        MappingProxyType({k: frozenset((p.record_type,)) for k, p in profiles.items()}),
        MappingProxyType({p.record_type: p.record_size for p in profiles.values()}),
        next(iter(profiles.values())).source_sha256)
    owner.city_scalar_event_profile = owner._city_scalar_event_profile = profile
    owner._city_scalar_binding=CityScalarBinding(owner,owner.arguments,owner.deferred,
        owner.arguments.host,owner.deferred.core,owner.deferred.core._handle,owner.deferred.context,core_sha256,
        owner._city_scalar_records,profile)
    return owner


def dispatch(owner, kind, fields):
    from .city_scalar_event_profiles import require_record_profile, require_notification_scope
    binding=_binding(owner)
    profile = require_record_profile(binding.records[kind])
    if owner.active_kind != kind or profile.kind != kind or profile.core_sha256!=binding.core_sha256:
        raise ValueError('City/scalar callback has a foreign active producer')
    if len(owner.pending) >= owner.limit:
        raise RuntimeError('City/scalar callback exceeds the native queue bound')
    prior = (owner.host_notification_counter, owner.host_metadata_counter,
             owner._sequence, len(owner.pending))
    require_notification_scope(prior[0], prior[1],core_sha256=binding.core_sha256)
    decoded = codec.decode_fields(fields, owner.read)
    record = codec.encode_record(owner._sequence + 1, decoded,
        normalizer_transform_present=False, per_thread_hook_present=False,
        writer_metadata_callback_present=False, empty_receiver_state=owner.empty_receiver_state,
        padding_policy=codec.PADDING_POLICY,
        record_profile=profile)
    owner._enqueue(record)
    if (owner.host_notification_counter, owner.host_metadata_counter,
            owner._sequence, len(owner.pending)) != (prior[0], prior[1], prior[2] + 1, prior[3] + 1):
        raise RuntimeError('Counter-independent city/scalar callback changed its scope or FIFO')
    owner.emit('native_deferred_host_event_enqueued', dispatch_kind=hex(kind),
        queue_type=hex(profile.record_type), record_hex=record.hex(),
        pending_count=len(owner.pending), native_dispatch_return=0,
        source_sha256=profile.source_sha256, receiver_sha256=profile.receiver_sha256,
        contract_sha256=profile.contract_sha256,
        core_sha256=profile.core_sha256,
        native_queries_executed=False, notification_counters_preserved=True,
        normalizer_transform_present=False, unspecified_padding_policy=codec.PADDING_POLICY,
        consumer_validated=False, eligible_for_training=False)
    return 0
