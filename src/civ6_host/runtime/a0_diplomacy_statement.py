"""Own XP2 statement map/FIFO lifetime; leave every answer to the caller."""
from .configuration_profiles import XP2_CORE_SHA256
from . import xp2_statement_source as source


def enable(owner,backend):
    owner._check();backend.check_thread()
    if (owner.statement_event_profile is not None or owner._foundation_backend is not backend
            or owner.foundation_event_profile is None or owner.combat_event_profile is None
            or owner.arguments.depth or owner.active_kind is not None or owner.pending
            or owner.deferred._draining_empty_receivers or owner.host_notification_counter
            or owner.host_metadata_counter or backend.stage!='prepared' or backend.prefix is not None
            or backend.load_abi.core_sha256!=XP2_CORE_SHA256
            or backend.core is not owner.deferred.core or backend.host is not owner.arguments.host):
        raise ValueError('Statement receiver requires the original prepared XP2 owner')
    image=getattr(backend.core,'_civ6_host_execution_image',None)
    source.source_dependencies(execution_image=image)
    profile=source.verify_live(backend.core._handle,owner.read,execution_image=image)
    from .native.native_combat_receiver import validate_receiver_profile
    validate_receiver_profile(owner.empty_receiver_state)
    if owner.handles_kind(source.KIND):raise ValueError('Statement producer overlaps an installed event')
    owner.statement_event_profile=owner._statement_event_profile=profile
    owner._statement_producing=owner._statement_poisoned=False
    deferred=owner.deferred
    if getattr(deferred,'diplomacy_statement_receiver',None) is not None:
        raise ValueError('Statement receiver already installed')
    deferred.diplomacy_statement_receiver=deferred
    deferred.statement_consumer=None
    return owner


def _owner(owner,*,producing):
    from .xp1_continuation import SavedContinuation
    backend=owner._foundation_backend
    token=getattr(backend,'_xp1_continuation',None)
    owner._check();backend.check_thread();owner.deferred._check()
    if (owner.statement_event_profile is not source.PROFILE
            or owner._statement_event_profile is not source.PROFILE
            or backend.load_abi.core_sha256!=XP2_CORE_SHA256
            or type(token) is not SavedContinuation or token.owner is not backend
            or token.prefix is not backend.prefix or token.prefix.deferred_events is not owner.deferred
            or backend.core is not owner.deferred.core or backend.context!=owner.deferred.context
            or owner._statement_poisoned or owner.deferred.diplomacy_statement_receiver is not owner.deferred
            or owner.host_notification_counter or owner.host_metadata_counter
            or producing and (owner.active_kind!=source.KIND or owner._statement_producing
                              or owner._foundation_borrow is not None)
            or not producing and (owner.active_kind is not None or owner.arguments.depth)):
        raise ValueError('Statement lifetime has a foreign or unqualified owner')
    return backend,token


def require_receiver(saved):
    """Admit a new request only on the exact active saved-session receiver."""
    deferred=saved.prefix.deferred_events
    owner=getattr(getattr(deferred,'host',None),'_a0_family_owner',None)
    if (owner is None or getattr(owner,'statement_event_profile',None) is not source.PROFILE
            or getattr(deferred,'diplomacy_statement_receiver',None) is not deferred):
        return False
    saved._check_active()
    backend,token=_owner(owner,producing=False)
    if backend is not saved.backend or token is not saved.continuation or deferred.pending_diplomacy_statements:
        raise ValueError('A new statement request overlaps a different saved dialogue')
    return True


def dispatch(owner,kind,fields,borrowed_argument):
    backend,token=_owner(owner,producing=True)
    if kind!=source.KIND or type(borrowed_argument) is not int or borrowed_argument<=0:
        raise ValueError('Statement requires its actual native argument map')
    from .native.native_combat_map_owner import NativeCombatMapOwner,CombatMapRegistry
    from .native.native_event_argument_tree import read_event_fields
    from .native import native_diplomacy_statement as codec
    owner._foundation_borrow=token;owner._statement_producing=True
    retained=None
    try:
        if (len(owner.pending)>=owner.limit or owner._sequence>=0x7fffffff
                or len(owner.deferred.pending_diplomacy_statements)>=owner.limit):
            raise RuntimeError('Statement queue or sequence capacity exceeded')
        if owner.combat_map_registry is None:
            owner.combat_map_registry=CombatMapRegistry(limit=min(owner.limit,1024),core_sha256=XP2_CORE_SHA256)
        registry=owner.combat_map_registry
        if registry.core_sha256!=XP2_CORE_SHA256:raise ValueError('Statement map registry engine differs')
        retained=NativeCombatMapOwner(backend.core,borrowed_argument,read=owner.read,core_sha256=XP2_CORE_SHA256)
        registry_token=registry.insert(retained)
        copied=read_event_fields(retained.pointer,backend.core._handle,owner.read,
                                owner.next_node,core_sha256=XP2_CORE_SHA256)
        decoded=codec.decode_fields(copied,owner.read)
        record=codec.encode_record(owner._sequence+1,retained.pointer,decoded,padding_bytes=bytes(7))
        owner.deferred._enqueue(record)
        owner.emit('native_xp2_diplomacy_statement_enqueued',dispatch_kind=hex(kind),queue_type='0x84',
            token=registry_token,record_hex=record.hex(),source_sha256=source.SOURCE[1],
            core_sha256=XP2_CORE_SHA256,execution_image_sha256=backend.core._civ6_host_execution_image.image_sha256,
            native_deep_copy_executed=True,automatic_response=False,native_dispatch_return=0,
            presentation_effects=dict(policy='omit_ui_dirty_hint',predicate_evaluated=False,
                predicate_result=None,service_flags_written=False,source_sha256=source.PRESENTATION[1]))
        return 0
    except BaseException as exc:
        owner._statement_poisoned=True
        if retained is not None:exc.native_diplomacy_map_owner=retained
        raise
    finally:
        owner._statement_producing=False;owner._foundation_borrow=None


def consume(deferred,record,sequence):
    from .native.native_combat_map_owner import CombatMapRegistry
    from .native.native_diplomacy_statement import StatementReceiver
    from .native.native_event_argument_tree import read_event_fields
    owner=getattr(deferred.host,'_a0_family_owner',None)
    if owner is None or owner.deferred is not deferred:raise ValueError('Statement receiver lost its producer')
    backend,token=_owner(owner,producing=False)
    registry=deferred.combat_map_registry
    if (not deferred._draining_empty_receivers or not deferred.pending or deferred.pending[0] is not record
            or sequence!=deferred.consumed_count+1 or type(registry) is not CombatMapRegistry
            or registry.core_sha256!=XP2_CORE_SHA256 or registry.poisoned):
        raise ValueError('Statement receiver lost its exact FIFO/map ownership')
    if deferred.statement_consumer is None:deferred.statement_consumer=StatementReceiver()
    if type(deferred.statement_consumer) is not StatementReceiver:raise TypeError('Statement receiver was replaced')
    def read_fields(pointer):
        return read_event_fields(pointer,deferred.base,deferred.read,owner.arguments.reader.next_node,
                                 core_sha256=XP2_CORE_SHA256)
    def deliver(statement):
        ledger=deferred.pending_diplomacy_statements
        if (len(ledger)>=deferred.limit
                or any(item['event_sequence']==statement['event_sequence'] for item in ledger)):
            raise ValueError('Statement ledger is full or duplicates a sequence')
        ledger.append(statement)
    receipt=deferred.statement_consumer.consume(record,registry,owner.empty_receiver_state,
                                               read_fields,deferred.read,deliver=deliver)
    deferred.pending.pop(0);deferred.consumed_count+=1
    deferred.consumed_bytes+=len(record);deferred.consumed_digest.update(record)
    deferred.emit('native_xp2_diplomacy_statement_consumed',**receipt,
                  xp2_source_sha256=source.SOURCE[1],automatic_response=False,
                  pending_choices=len(deferred.pending_diplomacy_statements))
