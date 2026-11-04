"""Compose the source-ordered C0 consumer with the shared native owner and FIFO."""
from __future__ import annotations

import ctypes as C
import struct
import threading
from .configuration_profiles import XP1_CORE_SHA256,XP2_CORE_SHA256
from .native.native_host_slot_c0 import dispatch_status_message,PADDING_POLICY,PROOF_SHA256
from .native.native_deferred_empty_profile import validate_empty_profile_record
from .retained_game_service import RetainedGameLease

_MISSING=object()


class StatusMessageService:
    def __init__(self,host,core,context,arguments,*,core_sha256,read,emit,context_alive,
                 receiver_state,writer_metadata_service,per_thread_hook):
        if core_sha256 not in (XP1_CORE_SHA256,XP2_CORE_SHA256) or writer_metadata_service is not None or per_thread_hook is not None:
            raise ValueError('Status owner requires an explicit expansion profile and absent optional hooks')
        arguments._check();deferred=arguments.deferred
        if (arguments.host is not host or deferred.core is not core or deferred.context!=context
                or deferred.cache_core_sha256!=core_sha256
                or getattr(host,'_status_message_owner',None) is not None):
            raise ValueError('Status owner is foreign or already installed')
        if type(receiver_state) is not dict:raise ValueError('Status receiver profile must be explicit')
        shape=bytearray(1120);struct.pack_into('<II',shape,0,1120,0xF7)
        validate_empty_profile_record(shape,**receiver_state)
        self.previous_state=getattr(deferred,'empty_receiver_state',_MISSING)
        if self.previous_state is not _MISSING and self.previous_state!=receiver_state:
            raise ValueError('Status receiver differs from shared queue profile')
        self.host,self.arguments,self.deferred,self.emit=host,arguments,deferred,emit
        self.read,self.core_sha256=read,core_sha256
        self.thread=threading.get_ident();self.closed=self.quarantined=False
        self.depth=self.count=0;self.receiver_state=dict(receiver_state)
        from .retained_game_source import verify_status_live
        self.source=verify_status_live(core._handle,read,host_pointer=host.pointer,core_sha256=core_sha256)
        self.game=RetainedGameLease(core,context,read,core_sha256=core_sha256,context_alive=context_alive)
        self.previous=(host.vtable[0xC0//8],host._slot_bindings.get((C.addressof(host.vtable),0xC0)))
        host._status_message_owner=self;deferred.empty_receiver_state=dict(receiver_state)
        try:
            host._bind(host.vtable,0xC0,C.c_uint32,[C.c_void_p,C.c_uint32,C.c_uint32,C.c_void_p],self.dispatch)
            self.address=host.vtable[0xC0//8]
        except BaseException:
            self.quarantined=True
            raise

    def _check(self):
        if threading.get_ident()!=self.thread:raise ValueError('Status owner belongs to another native thread')
        if (self.closed or self.quarantined or self.host._status_message_owner is not self
                or self.host.vtable[0xC0//8]!=self.address):
            raise RuntimeError('Status owner closed, poisoned or replaced')
        self.arguments._check();self.game.check()
        if self.deferred.empty_receiver_state!=self.receiver_state:
            raise RuntimeError('Status receiver profile changed')

    def dispatch(self,receiver,kind,target,argument):
        self._check();self.host._check(receiver)
        if self.depth:raise RuntimeError('Reentrant status production is unqualified')
        self.depth+=1
        try:
            d=self.deferred
            result=dispatch_status_message(kind,target,argument,retained_game_getter=self.game.value,
                read_fields=self.arguments.reader.fields,read=self.read,sequence=d._sequence+1,
                empty_receiver_state=self.receiver_state,padding_policy=PADDING_POLICY,
                writer_metadata_callback_present=False,per_thread_hook_present=False)
            record=result.pop('record')
            if record is not None:
                if d.host_notification_counter:raise ValueError('Status notification metadata scope is unqualified')
                d._enqueue(record)
                self.emit('native_deferred_host_event_enqueued',host_slot='0xc0',queue_type='0xf7',
                    record_hex=record.hex(),pending_count=len(d.pending),source_proof_sha256=PROOF_SHA256,
                    consumer_validated=False,eligible_for_training=False,native_dispatch_return=0)
            self.count+=1
            self.emit('native_host_status_message_completed',slot='0xc0',metadata_argument=kind,target_value=target,
                **result,record_enqueued=record is not None,source_proof_sha256=PROOF_SHA256,
                source_order_preserved=True,native_getter_called=True,gameplay_result_substituted=False,
                payload_exposed_to_learner=False,eligible_for_training=False,native_dispatch_return=0)
            return 0
        except BaseException:
            self.quarantined=True
            raise
        finally:self.depth-=1

    def consume(self,record,sequence):
        self._check()
        if self.depth or int.from_bytes(record[4:8],'little')!=0xF7:
            raise ValueError('Status receiver is busy or record kind differs')
        self.deferred._consume_empty_record(record,sequence)

    def close(self):
        if self.closed:return
        self._check()
        d=self.deferred
        if self.depth or d.pending or d._draining_empty_receivers or d.host_notification_counter or d.host_metadata_counter:
            raise RuntimeError('Status owner still has active consumers')
        self.host.vtable[0xC0//8]=self.previous[0]
        key=(C.addressof(self.host.vtable),0xC0)
        if self.previous[1] is None:self.host._slot_bindings.pop(key,None)
        else:self.host._slot_bindings[key]=self.previous[1]
        try:self.game.close()
        except BaseException:
            self.quarantined=True
            raise
        if self.previous_state is _MISSING:del d.empty_receiver_state
        else:d.empty_receiver_state=self.previous_state
        self.host._status_message_owner=None;self.closed=True
