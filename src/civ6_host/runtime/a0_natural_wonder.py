"""Borrow the existing XP2 saved owner for the complete discovery callback."""
import struct
from .configuration_profiles import XP2_CORE_SHA256
from . import xp2_natural_wonder_source as source

def enable(owner,backend):
    owner._check();backend.check_thread()
    if (owner.natural_wonder_event_profile is not None or owner._foundation_backend is not backend
            or owner.foundation_event_profile is None or owner.arguments.depth or owner.active_kind is not None
            or owner.pending or owner.deferred._draining_empty_receivers
            or owner.host_notification_counter or owner.host_metadata_counter
            or backend.stage!='prepared' or backend.prefix is not None
            or backend.load_abi.core_sha256!=XP2_CORE_SHA256
            or getattr(backend,'_xp1_commands_requested',False) is not True
            or backend.host is not owner.arguments.host or backend.core is not owner.deferred.core
            or backend.context!=owner.deferred.context or owner.controller_owner is None
            or owner.controller_owner.turn_begin_state is not owner.turn_begin_state
            or owner.deferred.turn_begin_state is not owner.turn_begin_state
            or hasattr(owner,'_36c9_producing') or hasattr(owner,'_36c9_poisoned')):
        raise ValueError('Natural-wonder callbacks require the original idle prepared XP2 owner')
    profile=source.bind_owner(backend,owner.read)
    if owner.handles_kind(source.KIND):raise ValueError('Natural-wonder callback overlaps an installed family')
    from .native.native_deferred_empty_profile import validate_empty_profile_record
    for kind,size in profile.record_sizes.items():
        record=bytearray(size);struct.pack_into('<II',record,0,size,kind)
        validate_empty_profile_record(record,**owner.empty_receiver_state)
    owner.natural_wonder_event_profile=owner._natural_wonder_event_profile=profile
    owner._36c9_producing=owner._36c9_poisoned=False
    owner._natural_wonder_checkpoint_pending=False
    return owner

def dispatch(owner,kind,fields,original_argument):
    from .xp1_continuation import SavedContinuation
    from .a0_foundation_events import require_borrow
    from .xp1_visibility_cache_gate import require_internal_cache
    from .native import native_36c9b2b4 as shared
    from .native.native_36c9b2b4_pair_codec import ZERO_PADDING_POLICY,PROOF_SHA256
    from .native.native_retained_game_getter import read_retained_game_value
    backend=owner._foundation_backend;token=getattr(backend,'_xp1_continuation',None)
    receipt=getattr(backend,'_xp2_natural_wonder_source',None)
    if (kind!=source.KIND or type(token) is not SavedContinuation or token.owner is not backend
            or type(receipt) is not source.VerifiedSource or receipt.owner is not backend
            or receipt.core is not backend.core or receipt.base!=backend.core._handle
            or owner.read is not receipt.read or owner.arguments.reader.read is not receipt.read
            or backend.runtime.read!=receipt.read
            or receipt.source_sha256!=source.SOURCE[1] or backend.load_abi.core_sha256!=XP2_CORE_SHA256
            or owner.arguments.reader.core_sha256!=XP2_CORE_SHA256 or owner.deferred.cache_core_sha256!=XP2_CORE_SHA256
            or backend.host is not owner.arguments.host or backend.core is not owner.deferred.core
            or backend.context!=owner.deferred.context or owner.active_kind!=kind
            or owner.natural_wonder_event_profile is not source.event_profile()
            or owner._foundation_borrow is not None or owner._36c9_producing or owner._36c9_poisoned
            or owner.controller_owner is None or owner.deferred.turn_begin_state is not owner.turn_begin_state
            or type(original_argument) is not int or original_argument<=0):
        raise ValueError('Natural-wonder callback has no exact active saved borrower')
    owner._foundation_borrow=token;owner._36c9_producing=True
    try:
        require_borrow(owner);cache=require_internal_cache(token);source.validate_fields(fields)
        publisher=token.publisher;facades=publisher._facades
        if (publisher is not backend.prefix.view_publisher or facades is None or publisher._closed
                or publisher.core is not backend.core or publisher.context!=backend.context
                or getattr(publisher,'_xp1_continuation',None) is not token
                or owner.turn_begin_state is not owner.controller_owner.turn_begin_state):
            raise ValueError('Natural-wonder retained publisher/controller owner differs')
        # Gate-off still validates/copies the normalizer fields, as the EXE does.
        gate=cache['callback_gate_enabled']
        if type(gate) is not bool:raise ValueError('Natural-wonder cache gate is not Boolean')
        n,m,seq,count=(owner.host_notification_counter,owner.host_metadata_counter,owner._sequence,len(owner.pending))
        if gate and (count+2>owner.limit or type(seq) is not int or not 0<=seq<=0xfffffffd):
            raise RuntimeError('Natural-wonder pair requires two FIFO/sequence slots')
        # Keep the actual shared controller's initialized state. Never project
        # a synthetic turn or reset this state to admit the callback.
        result=shared.produce_pair_from_raw_fields(fields,owner.read,sequence_78=seq+1,
            core=backend.core,facades=facades,context=backend.context,turn_state=owner.turn_begin_state,
            retained_getter=lambda:read_retained_game_value(facades,owner.read,core_sha256=XP2_CORE_SHA256),
            notification_counter=n,metadata_counter=m,
            original_argument=original_argument,ui_cache_callbacks_enabled=gate,
            empty_receiver_state_78=owner.empty_receiver_state,empty_receiver_state_79=owner.empty_receiver_state,
            normalizer_transform_present=owner.normalizer_transform_present,
            per_thread_hook_present=owner.per_thread_hook_present,
            writer_metadata_callback_present=owner.writer_metadata_callback_present,
            entity_listener_count=owner.entity_listener_count,padding_policy=ZERO_PADDING_POLICY,
            core_sha256=XP2_CORE_SHA256)
        require_borrow(owner);require_internal_cache(token)
        if (owner.host_notification_counter,owner.host_metadata_counter,owner._sequence,len(owner.pending))!=(n,m,seq,count):
            raise RuntimeError('Natural-wonder counters/FIFO changed during native queries')
        records=result['records']
        if gate:
            owner._natural_wonder_checkpoint_pending=True
            if tuple(k for k,_ in records)!=(120,121):raise ValueError('Natural-wonder producer changed its pair')
            owner.emit('native_wonder_application_effects_applied',dispatch_kind=hex(kind),
                source_proof_sha256=source.SOURCE[1],**result['effects'],eligible_for_training=False)
            for record_type,record in records:
                owner._enqueue(record)
                owner.emit('native_deferred_host_event_enqueued',dispatch_kind=hex(kind),queue_type=hex(record_type),
                    record_hex=record.hex(),pending_count=len(owner.pending),source_proof_sha256=source.SOURCE[1],
                    consumer_validated=False,eligible_for_training=False)
        if (owner.host_notification_counter,owner.host_metadata_counter,owner._sequence,len(owner.pending))!=(
                n,m,seq+(2 if gate else 0),count+(2 if gate else 0)):
            raise RuntimeError('Natural-wonder pair changed counters or FIFO order')
        owner.emit('native_natural_wonder_pair_enqueued',dispatch_kind=hex(kind),source_proof_sha256=source.SOURCE[1],
            pair_codec_proof_sha256=PROOF_SHA256,callback_gate_open=gate,records_enqueued=gate,
            sequence_78=seq+1 if gate else None,sequence_79=seq+2 if gate else None,
            native_query_return=result.get('native_position_index'),notification_counter_before=n,
            notification_counter_after=n,metadata_counter_before=m,metadata_counter_after=m,
            native_gameplay_written=False,eligible_for_training=False)
        return 0
    except BaseException:
        owner._36c9_poisoned=True
        raise
    finally:
        owner._36c9_producing=False;owner._foundation_borrow=None

def require_checkpoint_quiescent(backend):
    """Do not silently drop transient host effects from a native checkpoint.

    The existing TurnBegin producer clears byte0D and UI bit6. The empty
    discovery and completion receivers leave them pending.
    """
    host=getattr(backend,'host',None);owner=getattr(host,'_a0_family_owner',None)
    if owner is None or getattr(owner,'natural_wonder_event_profile',None) is None:return
    owner._check();backend.check_thread()
    if owner._foundation_backend is not backend:raise ValueError('Natural-wonder checkpoint owner differs')
    pending=owner._natural_wonder_checkpoint_pending
    if type(pending) is not bool:raise ValueError('Natural-wonder checkpoint state differs')
    if not pending:return
    control=owner.controller_owner
    if (owner.arguments.depth or owner.active_kind is not None or owner._36c9_producing
            or owner._36c9_poisoned or owner.pending or owner.deferred._draining_empty_receivers
            or control is None or control.turn_begin_state is not owner.turn_begin_state):
        raise ValueError('Natural-wonder callback/FIFO is not quiescent for Save')
    flag=control.controller_flag(host.pointer);flags=owner.turn_begin_state.service_flags
    if type(flag) is not int or type(flags) is not int or not 0<=flags<=255 or flag!=0 or flags&0x40:
        raise ValueError('Natural-wonder transient controller/UI state is pending; checkpoint requires a normal TurnBegin clear')
