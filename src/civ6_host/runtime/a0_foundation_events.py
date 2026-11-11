"""Borrow the shared notification algorithms during an exact XP1 command.

This is a family adapter, not another dispatcher or an admission of a playable
expansion. Core/context access expires when the synchronous producer returns.
"""
import struct
from .configuration_profiles import XP1_CORE_SHA256, XP2_CORE_SHA256
from .native.native_host_events import SharedHostEventDispatch
from .native.native_deferred_empty_profile import validate_empty_profile_record


def enable(owner, backend):
    owner._check()
    backend.check_thread()
    from .configuration_profiles import XP1_CORE_SHA256, XP2_CORE_SHA256
    core_sha256 = backend.load_abi.core_sha256
    if (owner.foundation_event_profile is not None or owner.arguments.depth
            or owner.active_kind is not None or owner.pending
            or owner.deferred._draining_empty_receivers
            or owner.host_notification_counter or owner.host_metadata_counter
            or backend.stage != 'prepared' or backend.prefix is not None
            or core_sha256 not in (XP1_CORE_SHA256, XP2_CORE_SHA256)
            or backend.host is not owner.arguments.host
            or backend.core is not owner.deferred.core
            or backend.context != owner.deferred.context
            or getattr(backend, '_xp1_commands_requested', False) is not True):
        raise ValueError('Foundation callbacks require the original idle saved command owner')
    from .foundation_event_profile import event_profile, verify_project_live, verify_pillage_live
    image = (getattr(backend.core, '_civ6_host_execution_image', None)
             if core_sha256 == XP2_CORE_SHA256 else None)
    execution_options = {'execution_image': image} if image is not None else {}
    profile = event_profile(core_sha256=core_sha256, **execution_options)
    if any(owner.handles_kind(kind) for kind in profile.record_types_by_kind):
        raise ValueError('Foundation event family overlaps an existing owner')
    for kind, size in profile.record_sizes.items():
        record = bytearray(size)
        struct.pack_into('<II', record, 0, size, kind)
        validate_empty_profile_record(record, execution_image=image, **owner.empty_receiver_state)
    from .foundation_facade_profiles import verify_xp1_once
    from .paths import resource_root
    verify_xp1_once(backend.core, backend.core._handle, owner.read, resource_root(),
                    core_sha256=core_sha256)
    if core_sha256==XP2_CORE_SHA256:
        from .xp2_wmd_fallout_visibility import verify_live as verify_wmd_visibility
        from .xp2_wonder_completion import verify_live as verify_wonder_completion
        verify_wmd_visibility(backend.core._handle,owner.read)
        verify_project_live(backend.core._handle, owner.read)
        verify_pillage_live(backend.core._handle, owner.read, **execution_options)
        verify_wonder_completion(backend.core._handle, owner.read)
        if image is not None:
            from .xp2_great_work import verify_live as verify_great_work
            from . import xp2_feature_events as feature
            from . import xp2_city_occupation_event as occupation
            from . import xp2_building_removal as removal
            from . import xp2_player_can_construct_event as construct
            if owner.profile.record_types_by_kind.get(feature.CHANGED) != frozenset((117,)):
                raise ValueError('FeatureChanged must retain the shared A0 producer')
            verify_great_work(backend.core, owner.read)
            feature.verify_live(backend.core, owner.read)
            occupation.verify_live(backend.core, owner.read)
            removal.verify_live(backend.core, owner.read)
            construct.verify_live(backend.core, owner.read)
            from .xp2_player_restored import verify_live as verify_restored
            verify_restored(backend.core, owner.read)
    owner.foundation_event_profile = owner._foundation_event_profile = profile
    owner._foundation_backend = backend
    return owner


def _active_profile(owner):
    for public, private in (('foundation_event_profile','_foundation_event_profile'),
                            ('history_event_profile','_history_event_profile'),
                            ('climate_event_profile','_climate_event_profile'),
                            ('turn_unit_event_profile','_turn_unit_event_profile'),
                            ('placement_event_profile','_placement_event_profile'),
                            ('combat_event_profile','_combat_event_profile'),
                            ('improvement_change_profile','_improvement_change_profile'),
                            ('district_damage_profile','_district_damage_profile'),
                            ('statement_event_profile','_statement_event_profile'),
                            ('natural_wonder_event_profile','_natural_wonder_event_profile')):
        profile=getattr(owner,public,None)
        if profile is not None and profile is getattr(owner,private,None) and owner.active_kind in profile.record_types_by_kind:
            return profile
    registry = getattr(owner, 'presentation_sources', None)
    if registry is not None and owner.active_kind in registry:
        from .empty_presentation_events import check_registry
        check_registry(owner)
        return registry[owner.active_kind]
    raise ValueError('Native query kind has no installed family profile')


def enable_history_events(owner, backend):
    """Install only XP2 History/Era/Era-score callbacks on the saved owner."""
    owner._check()
    backend.check_thread()
    core_sha256=backend.load_abi.core_sha256
    if (core_sha256!=XP2_CORE_SHA256
            or owner.history_event_profile is not None
            or owner._foundation_backend not in (None,backend)
            or owner._foundation_borrow is not None
            or owner.arguments.depth or owner.active_kind is not None or owner.pending
            or owner.deferred._draining_empty_receivers
            or owner.host_notification_counter or owner.host_metadata_counter
            or backend.stage!='prepared' or backend.prefix is not None
            or getattr(backend,'_xp1_commands_requested',False) is not True
            or backend.host is not owner.arguments.host
            or backend.core is not owner.deferred.core
            or backend.context!=owner.deferred.context
            or owner.deferred.cache_core_sha256!=XP2_CORE_SHA256
            or owner.arguments.reader.core_sha256!=XP2_CORE_SHA256
            or owner.normalizer_transform_present is not False):
        raise ValueError('History callbacks require the exact idle prepared XP2 command owner')
    from .xp2_history_event_profile import event_profile,bind_owner
    image = getattr(backend.core, '_civ6_host_execution_image', None)
    execution_options = {'execution_image': image} if image is not None else {}
    profile=event_profile(core_sha256=core_sha256, **execution_options)
    if any(owner.handles_kind(kind) for kind in profile.record_types_by_kind):
        raise ValueError('History callbacks overlap an installed A0 family')
    for kind,size in profile.record_sizes.items():
        record=bytearray(size);struct.pack_into('<II',record,0,size,kind)
        validate_empty_profile_record(record,**owner.empty_receiver_state)
    bind_owner(backend,backend.core,owner.read)
    owner.history_event_profile=owner._history_event_profile=profile
    owner._foundation_backend=backend
    return owner


def enable_improvement_changes(owner, backend):
    from .a0_improvement_changes import enable
    return enable(owner,backend)


def enable_placements(owner, backend):
    """Install the complete shared district-progress producer before Load."""
    owner._check();backend.check_thread()
    if (owner.placement_event_profile is not None or owner._foundation_backend is not backend
            or owner.foundation_event_profile is None or owner.arguments.depth
            or owner.active_kind is not None or owner.pending or owner.deferred._draining_empty_receivers
            or owner.host_notification_counter or owner.host_metadata_counter
            or backend.stage!='prepared' or backend.prefix is not None
            or backend.load_abi.core_sha256 not in (XP1_CORE_SHA256,XP2_CORE_SHA256)
            or backend.host is not owner.arguments.host or backend.core is not owner.deferred.core
            or backend.context!=owner.deferred.context):
        raise ValueError('Placement callbacks require the original prepared foundation owner')
    from .placement_event_profile import bind_owner
    if hasattr(owner,'_f391_producing') or hasattr(owner,'_f391_poisoned'):
        raise ValueError('Improvement visibility producer state already exists')
    profile=bind_owner(backend,backend.core,owner.read,core_sha256=backend.load_abi.core_sha256)
    if any(owner.handles_kind(kind) for kind in profile.record_types_by_kind):
        raise ValueError('Placement callbacks overlap an installed family')
    for kind,size in profile.record_sizes.items():
        record=bytearray(size);struct.pack_into('<II',record,0,size,kind)
        validate_empty_profile_record(record,**owner.empty_receiver_state)
    owner.placement_event_profile=owner._placement_event_profile=profile
    # Retain the Base synchronous producer states. Do not reset a running
    # scope or a poisoned producer while installing another family.
    owner._f391_producing=owner._f391_poisoned=False
    return owner


def enable_turn_units(owner, backend):
    owner._check()
    backend.check_thread()
    if (owner.turn_unit_event_profile is not None or (owner._foundation_backend is not None and owner._foundation_backend is not backend)
            or owner._foundation_borrow is not None or owner.arguments.depth
            or owner.active_kind is not None or owner.pending or owner.deferred._draining_empty_receivers
            or owner.host_notification_counter or owner.host_metadata_counter
            or backend.stage!='prepared' or backend.prefix is not None
            or getattr(backend,'_xp1_commands_requested',False) is not True
            or backend.load_abi.core_sha256 not in (XP1_CORE_SHA256,XP2_CORE_SHA256)
            or backend.host is not owner.arguments.host or backend.core is not owner.deferred.core
            or backend.context!=owner.deferred.context):
        raise ValueError('Turn unit callbacks require the original prepared command owner')
    # These are presentation-producer state inherited from
    # NativeDeferredHostEvents.__init__, not Core state or gameplay getters.
    # Install once before any family dispatch; never reset a running counter.
    if hasattr(owner, 'entity_event_count') or hasattr(owner, 'visual_profile'):
        raise ValueError('Turn unit producer state already exists')
    from .turn_unit_event_profile import event_profile, bind_owner
    image = (getattr(backend.core, '_civ6_host_execution_image', None)
             if backend.load_abi.core_sha256 == XP2_CORE_SHA256 else None)
    execution_options = {'execution_image': image} if image is not None else {}
    profile=event_profile(core_sha256=backend.load_abi.core_sha256, **execution_options)
    if any(owner.handles_kind(kind) for kind in profile.record_types_by_kind):
        raise ValueError('Turn unit callbacks overlap an installed family')
    for kind,size in profile.record_sizes.items():
        record=bytearray(size);struct.pack_into('<II',record,0,size,kind)
        validate_empty_profile_record(record,**owner.empty_receiver_state)
    bind_owner(backend,backend.core,owner.read)
    from .native.native_unit_created_event import VISUAL_PROFILE
    owner._foundation_backend = backend
    owner.entity_event_count = 0
    owner.visual_profile = VISUAL_PROFILE
    owner.turn_unit_event_profile=owner._turn_unit_event_profile=profile
    return owner


def require_borrow(owner):
    """Never expose a Base query fallback outside this explicit family."""
    from .xp1_continuation import SavedContinuation
    token = owner._foundation_borrow
    b = owner._foundation_backend
    if (type(token) is not SavedContinuation or b is None
            or token.owner is not b or getattr(b, '_xp1_continuation', None) is not token
            or owner.quarantined or owner.closed
            or b.host is not owner.arguments.host or b.core is not owner.deferred.core
            or b.context != owner.deferred.context):
        raise ValueError('Foundation query has no exact active native borrower')
    _active_profile(owner)
    token.check(active=True)
    return token


def dispatch(owner, kind, fields, borrowed_argument=None):
    from .xp1_continuation import SavedContinuation
    b = owner._foundation_backend
    token = getattr(b, '_xp1_continuation', None)
    if (type(token) is not SavedContinuation or token.owner is not b
            or owner._foundation_borrow is not None or owner.active_kind != kind):
        raise ValueError('Foundation callback lacks its exact synchronous continuation')
    _active_profile(owner)
    owner._foundation_borrow = token
    try:
        require_borrow(owner)
        # The internal population state is independent of the public admission
        # flags. A failed check must never become a synthetic gate-off branch.
        from .xp1_visibility_cache_gate import require_internal_cache
        require_internal_cache(token)
        if kind==0x8cbda9f3 and b.load_abi.core_sha256==XP2_CORE_SHA256:
            from .xp2_wmd_fallout_visibility import dispatch as dispatch_wmd_visibility
            return dispatch_wmd_visibility(owner,fields)
        if kind == 0x1a71e9f0 and b.load_abi.core_sha256 == XP2_CORE_SHA256:
            from .xp2_great_work import dispatch as dispatch_great_work
            return dispatch_great_work(owner, fields)
        if kind == 0xb39c906a and b.load_abi.core_sha256 == XP2_CORE_SHA256:
            from .xp2_feature_events import dispatch_added
            return dispatch_added(owner, fields)
        if kind == 0xe05ec908 and b.load_abi.core_sha256 == XP2_CORE_SHA256:
            from .xp2_city_occupation_event import dispatch as dispatch_occupation
            return dispatch_occupation(owner, fields)
        if kind == 0xe074eef4 and b.load_abi.core_sha256 == XP2_CORE_SHA256:
            from .xp2_building_removal import dispatch as dispatch_removal
            return dispatch_removal(owner, fields)
        if kind == 0xad6c0a71 and b.load_abi.core_sha256 == XP2_CORE_SHA256:
            from .xp2_player_restored import dispatch as dispatch_restored
            return dispatch_restored(owner, fields)
        if kind == 0xa0a8f479 and b.load_abi.core_sha256 == XP2_CORE_SHA256:
            from .xp2_player_can_construct_event import dispatch as dispatch_construct
            return dispatch_construct(owner, fields)
        return SharedHostEventDispatch._dispatch_fields(owner, kind, fields,
                                                        borrowed_argument=borrowed_argument)
    finally:
        owner._foundation_borrow = None


def dispatch_history(owner,kind,fields):
    """Run a scalar history callback under the exact synchronous continuation.

    This producer copies only its two source-identified values. It does not
    consult the private visibility cache used by placement queries.
    """
    from .xp1_continuation import SavedContinuation
    backend=owner._foundation_backend
    token=getattr(backend,'_xp1_continuation',None) if backend is not None else None
    if (type(token) is not SavedContinuation or token.owner is not backend
            or owner._foundation_borrow is not None or owner.active_kind!=kind
            or backend.load_abi.core_sha256!=XP2_CORE_SHA256
            or owner.history_event_profile is None
            or owner.history_event_profile is not owner._history_event_profile
            or kind not in owner.history_event_profile.record_types_by_kind):
        raise ValueError('History callback lacks its exact XP2 continuation and family')
    token.check(active=True)
    owner._foundation_borrow=token
    try:
        require_borrow(owner)
        from .a0_game_history_events import dispatch as enqueue_history
        return enqueue_history(owner,kind,fields)
    finally:
        owner._foundation_borrow=None


def dispatch_project_completion(owner, fields):
    from .native import native_event_3182bc8e_project as project
    from .native.native_retained_game_getter import read_retained_game_value
    from .foundation_event_profile import PROJECT_KIND, PROJECT_SOURCE

    token = require_borrow(owner)

    if len(owner.pending) + 3 > owner.limit or not 0 <= owner._sequence < 0x7ffffffd:
        raise RuntimeError('Project completion requires three FIFO entries')
    owner.deferred._check()
    facades = token.lease.require(token.lease.backend, token.publisher._facades)
    decoded = project.decode_fields(fields, owner.read)

    def retained_value():
        token.lease.require(token.lease.backend, facades)
        return read_retained_game_value(facades, owner.read, core_sha256=XP2_CORE_SHA256)

    records = project.iter_records(
        owner._sequence + 1, decoded, retained_value, empty_receiver_profile=True,
        padding_policy=project.STACK_POLICY,
        normalizer_transform_present=owner.normalizer_transform_present)
    for record in records:
        owner._enqueue(record)
        record_type = struct.unpack_from('<I', record, 4)[0]
        owner.emit('native_deferred_host_event_enqueued', dispatch_kind=hex(PROJECT_KIND),
            queue_type=hex(record_type), record_hex=record.hex(), pending_count=len(owner.pending),
            source_proof_sha256=PROJECT_SOURCE[1], empty_receiver_state_verified=True,
            extended_branch_entered=True, eligible_for_training=False, native_dispatch_return=0)
    return 0



def dispatch_building_pillage(owner, fields):
    from .foundation_event_profile import PILLAGE_SOURCE
    from .native import native_event_e660_building_pillaged as event

    require_borrow(owner)
    if (not owner.ui_cache_callbacks_enabled or owner.active_kind != event.EVENT_KIND
            or owner.entity_listener_count != 0 or len(owner.pending) >= owner.limit
            or type(owner._sequence) is not int or not 0 <= owner._sequence < 0x7fffffff):
        raise ValueError('Building pillage requires its active empty-receiver XP2 owner')
    owner.deferred._check()
    decoded = event.decode_fields(fields, owner.read,
                                  execution_image=getattr(owner.core, '_civ6_host_execution_image', None))
    profile = dict(padding_policy=event.PADDING_POLICY,
                   empty_receiver_state=dict(owner.empty_receiver_state),
                   notification_counter=owner.host_notification_counter,
                   metadata_counter=owner.host_metadata_counter,
                   per_thread_hook_present=False, writer_metadata_callback_present=False)
    before = (owner._sequence, len(owner.pending), owner.host_notification_counter,
              owner.host_metadata_counter)
    with event.produce_record_lease(owner._sequence + 1, decoded, core=owner.core,
            context=owner.context, read=owner.read, profile=profile,
            normalizer_transform_present=owner.normalizer_transform_present,
            core_sha256=XP2_CORE_SHA256) as (record, query):
        if before != (owner._sequence, len(owner.pending), owner.host_notification_counter,
                      owner.host_metadata_counter):
            raise RuntimeError('Building pillage query changed its enclosing FIFO scope')
        validate_empty_profile_record(record, **owner.empty_receiver_state)
        owner._enqueue(record)
    owner.emit('native_deferred_host_event_enqueued', dispatch_kind=hex(event.EVENT_KIND),
               queue_type=hex(event.RECORD_TYPE), record_hex=record.hex(),
               pending_count=len(owner.pending), source_proof_sha256=PILLAGE_SOURCE[1],
               information_scope='administrative-unfiltered', native_dispatch_return=0,
               eligible_for_training=False, **query)
    return 0
