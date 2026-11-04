"""Own shared host FIFO/counters and source-selected expansion CacheUpdate.

This service does not install A0/C0 event decoders, a controller policy, actions
or a synthetic empty Core registry. Those remain separate admission boundaries.
"""
from __future__ import annotations

import ctypes as C
from contextlib import ExitStack
import hashlib
import threading
from time import perf_counter

from .configuration_profiles import XP1_CORE_SHA256,XP2_CORE_SHA256
from .native.native_host_events import DeferredHostQueue


class DeferredService(DeferredHostQueue):
    def __init__(self,host,core,context,*,core_sha256,read,emit,limit=4096,
                 optional_preprocessor,queue_metadata_service):
        if core_sha256 not in (XP1_CORE_SHA256,XP2_CORE_SHA256):
            raise ValueError('Shared deferred service requires a source-qualified expansion')
        if type(limit) is not int or not 0<limit<=65536:
            raise ValueError('Invalid deferred queue resource bound')
        if optional_preprocessor is not None or queue_metadata_service is not None:
            raise ValueError('Deferred source profile requires explicit absent optional EXE services')
        if getattr(host,'_deferred_service_owner',None) is not None:
            raise ValueError('Deferred callbacks already have an owner')
        from .cache_update_profiles import verify_dispatch_live,verify_notification_live
        self.source=verify_dispatch_live(core._handle,context,read,core_sha256=core_sha256)
        verify_notification_live(core._handle,read,host_pointer=host.pointer,core_sha256=core_sha256)
        self.host,self.core,self.base,self.context=host,core,core._handle,context
        self.cache_core_sha256,self.read,self.emit=core_sha256,read,emit
        self.thread=threading.get_ident()
        self.pending=[];self._sequence=self.consumed_count=self.consumed_bytes=0
        self.consumed_digest=hashlib.sha256()
        self.host_notification_counter=self.host_metadata_counter=0
        self.cache_update_callback_pair=None
        self.combat_map_registry=None
        self.combat_receiver=None
        self.limit=limit
        self.closed=self.quarantined=self._draining_empty_receivers=self._deferred_drain_poisoned=False
        self.previous={};self.addresses={}
        self.host._deferred_service_owner=self
        try:
            for slot,result,args,method in (
                (0xB0,C.c_int32,[C.c_void_p,C.c_uint32,C.c_uint64],self.cache_update),
                (0xE8,None,[C.c_void_p,C.c_uint32],self.host_notification),
                (0xF0,None,[C.c_void_p,C.c_uint32],self.host_notification_end)):
                key=(C.addressof(host.vtable),slot)
                self.previous[slot]=(host.vtable[slot//8],getattr(host,'_slot_bindings',{}).get(key))
                host._bind(host.vtable,slot,result,args,method)
                self.addresses[slot]=host.vtable[slot//8]
        except BaseException:
            self.quarantined=True
            raise

    def _check(self):
        if threading.get_ident()!=self.thread:
            raise ValueError('Deferred service belongs to another native thread')
        if (self.closed or self.quarantined or self._deferred_drain_poisoned
                or self.host._deferred_service_owner is not self):
            raise RuntimeError('Deferred service closed, replaced or poisoned')
        if any(self.host.vtable[s//8]!=a for s,a in self.addresses.items()):
            raise RuntimeError('Deferred service callback was replaced')

    def _require_no_f391_reentry(self):
        # The shared Base object owned both the FIFO and synchronous A0 query
        # producers. Preserve its guard across the two owned service objects.
        self._check()
        a0=getattr(self.host,'_a0_family_owner',None)
        if a0 is not None:
            if a0.deferred is not self or a0.arguments.host is not self.host:
                raise RuntimeError('Deferred callback has a foreign A0 producer')
            a0._require_no_f391_reentry()

    def drain(self, *, loaded_lifetime=None):
        self._check()
        self._require_no_f391_reentry()
        if self._draining_empty_receivers:
            raise RuntimeError('Reentrant deferred drain is not permitted')
        if loaded_lifetime is not None:
            from .xp1_loaded_lifetime import require_lifetime
            require_lifetime(loaded_lifetime).check_deferred_drain(self)
        self._draining_empty_receivers=True
        count=0
        counts_by_kind = {}
        seconds_by_kind = {}
        try:
            with ExitStack() as scopes:
                cache_scope_open = False
                while self.pending:
                    record=self.pending[0]
                    if type(record) is not bytes or len(record)<12:
                        raise ValueError('Malformed deferred head')
                    sequence=int.from_bytes(record[8:12],'little')
                    if sequence!=self.consumed_count+1:
                        raise ValueError('Deferred consumption is out of sequence')
                    kind=int.from_bytes(record[4:8],'little')
                    started = perf_counter()
                    if kind==0x113:
                        if not cache_scope_open and self.cache_core_sha256 == XP2_CORE_SHA256:
                            from .xp2_preload_source import cache_dispatch_scope
                            scopes.enter_context(cache_dispatch_scope(self.base, self.context, self.read))
                            cache_scope_open = True
                        self._consume_cache_update_record(record,sequence)
                    elif kind==0xF8:
                        if loaded_lifetime is not None:
                            raise ValueError('Combat map release is not qualified after native Unload')
                        self._consume_combat_record(record,sequence)
                    elif kind==0xF7 and getattr(self.host,'_status_message_owner',None) is not None:
                        self.host._status_message_owner.consume(record,sequence)
                    elif (getattr(self.host,'_a0_family_owner',None) is not None
                          and self.host._a0_family_owner.handles_record(kind)):
                        if loaded_lifetime is None:
                            self.host._a0_family_owner.consume(record,sequence)
                        else:
                            self.host._a0_family_owner.consume(record,sequence,loaded_lifetime=loaded_lifetime)
                    else:
                        raise ValueError('This service has no decoder for the pending record kind')
                    counts_by_kind[kind] = counts_by_kind.get(kind, 0) + 1
                    seconds_by_kind[kind] = seconds_by_kind.get(kind, 0.0) + (perf_counter() - started)
                    count+=1
            a0=getattr(self.host,'_a0_family_owner',None)
            private_seconds = 0.0
            if a0 is not None and getattr(a0,'private_notification_profile',None) is not None:
                from .a0_private_notifications import drain
                started = perf_counter()
                drain(a0,loaded_lifetime=loaded_lifetime)
                private_seconds = perf_counter() - started
            self._check()
            if count:
                self.emit('native_deferred_drain_timing',
                          records=[dict(record_type=kind, count=counts_by_kind[kind],
                                        seconds=seconds_by_kind[kind])
                                   for kind in sorted(counts_by_kind)],
                          private_notification_seconds=private_seconds,
                          includes_callbacks_and_trace_emission=True)
            return count
        except BaseException:
            self._deferred_drain_poisoned=True
            raise
        finally:
            self._draining_empty_receivers=False

    def drain_empty_receivers(self):
        """Shared action adapter interface; consume the actual owned FIFO.

        Admission of every kind remains in drain(), including native feedback.
        The receiver profile is established by the owned argument consumers.
        """
        return self.drain()

    def _consume_combat_record(self,record,sequence):
        """Run the existing EXE F8 release hook before committing this FIFO head."""
        from .native.native_combat_map_owner import CombatMapRegistry, NativeCombatMapOwner
        from .native.native_combat_receiver import CombatReceiver
        self._check()
        a0=getattr(self.host,'_a0_family_owner',None)
        registry=self.combat_map_registry
        if (type(record) is not bytes or len(record)!=128
                or not self._draining_empty_receivers or not self.pending or self.pending[0] is not record
                or sequence!=self.consumed_count+1 or type(registry) is not CombatMapRegistry
                or registry.core_sha256!=self.cache_core_sha256 or registry.poisoned
                or a0 is None or a0.deferred is not self or a0.arguments.host is not self.host
                or a0.combat_map_registry is not registry
                or getattr(a0,'combat_event_profile',None) is None
                or a0.combat_event_profile is not getattr(a0,'_combat_event_profile',None)
                or a0.active_kind is not None or a0.arguments.depth):
            raise ValueError('Combat receiver lacks its exact admitted producer, registry and FIFO head')
        a0._check()
        map_owner=registry.lookup(int.from_bytes(record[120:124],'little'))
        if (type(map_owner) is not NativeCombatMapOwner or map_owner.core is not self.core
                or map_owner.base!=self.base or map_owner.core_sha256!=self.cache_core_sha256):
            raise ValueError('Combat FIFO token belongs to a foreign native map owner')
        if self.combat_receiver is None:self.combat_receiver=CombatReceiver()
        if type(self.combat_receiver) is not CombatReceiver:
            raise TypeError('Combat receiver owner was replaced')
        receipt=self.combat_receiver.consume(record,registry,a0.empty_receiver_state)
        # Release/guards must have succeeded before the immutable row is removed.
        self.pending.pop(0)
        self.consumed_count+=1
        self.consumed_bytes+=len(record)
        self.consumed_digest.update(record)
        self.emit('native_combat_post_hook_consumed',sequence=sequence,
                  owned_map_core_sha256=registry.core_sha256,**receipt)

    def close(self):
        if threading.get_ident()!=self.thread:
            raise ValueError('Deferred close crossed its native thread')
        if self.closed:return
        self._check()
        self._require_no_f391_reentry()
        if (self._draining_empty_receivers or self.pending or self._sequence!=self.consumed_count
                or self.host_notification_counter or self.host_metadata_counter):
            raise RuntimeError('Deferred service still has pending work or an open scope')
        if (self.combat_map_registry is not None and
                (self.combat_map_registry.entries or self.combat_map_registry.poisoned)
                or self.combat_receiver is not None and
                (self.combat_receiver.dispatching or self.combat_receiver.poisoned)):
            raise RuntimeError('Deferred service still owns live or uncertain combat maps')
        controller=getattr(self.host,'_control_input_owner',None)
        if controller is not None and controller.deferred is self:
            raise RuntimeError('Control input owner still borrows the deferred service')
        arguments=getattr(self.host,'_event_argument_owner',None)
        if arguments is not None and arguments.deferred is self:
            raise RuntimeError('Event argument owner still borrows the deferred service')
        status=getattr(self.host,'_status_message_owner',None)
        if status is not None and status.deferred is self:
            raise RuntimeError('Status message owner still borrows the deferred service')
        a0=getattr(self.host,'_a0_family_owner',None)
        if a0 is not None and a0.deferred is self:
            raise RuntimeError('A0 family owner still borrows the deferred service')
        for slot,(address,binding) in self.previous.items():
            self.host.vtable[slot//8]=address
            key=(C.addressof(self.host.vtable),slot)
            if binding is None:self.host._slot_bindings.pop(key,None)
            else:self.host._slot_bindings[key]=binding
        self.host._deferred_service_owner=None
        self.closed=True
