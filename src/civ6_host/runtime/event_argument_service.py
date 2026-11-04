"""Owned expansion argument reader and source-qualified absent scalar callbacks.

The shared reader copies variant headers before the native map dies. Pointee
data remains borrowed; per-kind consumers must copy/interpret it synchronously.
This service does not turn registered or unknown semantic events into success.
"""
from __future__ import annotations

import ctypes as C
import threading
from .configuration_profiles import XP1_CORE_SHA256,XP2_CORE_SHA256
from .native.native_event_argument_tree import read_event_fields
from .native.native_absent_scalar_a0 import validate_absent_scalar_a0


class EventArgumentReader:
    def __init__(self,core,*,core_sha256,read):
        from .event_argument_source import reader_abi,verify_reader_live
        self.abi=reader_abi(core_sha256)
        self.source=verify_reader_live(core._handle,read,core_sha256=core_sha256)
        self.core,self.base,self.core_sha256,self.read=core,core._handle,core_sha256,read
        self.thread=threading.get_ident();self.closed=False
        self.next_node=C.WINFUNCTYPE(C.c_void_p,C.c_void_p)(self.base+self.abi.successor_rva)

    def fields(self,pointer):
        if self.closed or threading.get_ident()!=self.thread:
            raise RuntimeError('Event argument reader is closed or on another thread')
        return read_event_fields(pointer,self.base,self.read,self.next_node,core_sha256=self.core_sha256)

    def close(self):
        if threading.get_ident()!=self.thread:raise ValueError('Event reader close crossed its thread')
        self.closed=True


class EventArgumentService:
    def __init__(self,host,core,context,deferred,*,core_sha256,read,emit,
                 normalizer_transform,dynamic_registrations):
        if core_sha256 not in (XP1_CORE_SHA256,XP2_CORE_SHA256):
            raise ValueError('Event argument owner requires a source-qualified expansion')
        if normalizer_transform is not None or dynamic_registrations!=():
            raise ValueError('Event owner requires the explicit fixed EXE registry and absent transform')
        deferred._check()
        if (deferred.host is not host or deferred.core is not core or deferred.context!=context
                or getattr(host,'_event_argument_owner',None) is not None):
            raise ValueError('Event argument owner is foreign or already installed')
        from .event_argument_source import verify_host_live
        self.source=verify_host_live(core._handle,context,read,host_pointer=host.pointer,
                                     core_sha256=core_sha256)
        self.reader=EventArgumentReader(core,core_sha256=core_sha256,read=read)
        self.host,self.deferred,self.emit=host,deferred,emit
        self.thread=threading.get_ident();self.closed=self.quarantined=False
        self.depth=0;self.count=0
        self.previous=(host.vtable[0xA0//8],host._slot_bindings.get((C.addressof(host.vtable),0xA0)))
        host._event_argument_owner=self
        try:
            host._bind(host.vtable,0xA0,C.c_int32,[C.c_void_p,C.c_uint32,C.c_void_p],self.dispatch)
            self.address=host.vtable[0xA0//8]
        except BaseException:
            self.quarantined=True
            raise

    def _check(self):
        if threading.get_ident()!=self.thread:
            raise ValueError('Event argument owner belongs to another native thread')
        if self.closed or self.quarantined or self.host._event_argument_owner is not self:
            raise RuntimeError('Event argument owner closed, quarantined or replaced')
        self.deferred._check()
        if self.host.vtable[0xA0//8]!=self.address:
            raise RuntimeError('Event argument callback replaced')

    def dispatch(self,receiver,kind,argument):
        self._check();self.host._check(receiver)
        if self.depth:raise RuntimeError('Reentrant argument dispatch is unqualified')
        self.depth+=1
        fields=None
        try:
            fields=self.reader.fields(argument)
            if getattr(self,'consumer',None) is not None and self.consumer.handles_kind(kind):
                result=self.consumer.dispatch(kind,fields,argument)
                self.count+=1
                return result
            from .xp1_absent_event_families import has_shape,dispatch as dispatch_absent_descriptor
            if has_shape(fields):
                result=dispatch_absent_descriptor(self,kind,fields)
                self.count+=1
                return result
            result=validate_absent_scalar_a0(kind,fields)
            self.count+=1
            self.emit('native_shared_absent_scalar_event',dispatch_kind=hex(kind),
                fields={hex(k):v.hex() for k,v in fields.items()},native_dispatch_return=result['normalizer_result'],
                callback_registered=False,core_internal_dispatch_preserved=True,
                copied_variant_headers=True,pointer_payloads_retained=False,eligible_for_training=False)
            return result['normalizer_result']
        except BaseException as error:
            self.quarantined=True
            # Administrative refusal evidence: headers already copied by the
            # checked reader only; never dereference or retain native pointers.
            if fields is not None:
                self.emit('native_host_event_failed_copied_headers',dispatch_kind=hex(kind),
                    core_sha256=self.reader.core_sha256,
                    fields={hex(k):v.hex() for k,v in fields.items()},
                    copied_variant_headers=True,pointer_payloads_retained=False,
                    result_substituted=False,eligible_for_training=False)
            error.add_note(f'A0 dispatch kind={kind:#010x}; no fallback executed')
            raise
        finally:
            self.depth-=1

    def close(self, *, loaded_lifetime=None):
        if threading.get_ident()!=self.thread:raise ValueError('Event owner close crossed its thread')
        if self.closed:return
        self._check()
        status=getattr(self.host,'_status_message_owner',None)
        if status is not None and status.arguments is self:
            raise RuntimeError('Status message owner still borrows the argument reader')
        if (self.depth or self.deferred.pending or self.deferred._draining_empty_receivers
                or self.deferred.host_notification_counter or self.deferred.host_metadata_counter):
            raise RuntimeError('Event argument owner still has active consumers')
        if getattr(self,'consumer',None) is not None:
            if loaded_lifetime is None:
                self.consumer.close()
            else:
                self.consumer.close(loaded_lifetime=loaded_lifetime)
        self.host.vtable[0xA0//8]=self.previous[0]
        key=(C.addressof(self.host.vtable),0xA0)
        if self.previous[1] is None:self.host._slot_bindings.pop(key,None)
        else:self.host._slot_bindings[key]=self.previous[1]
        self.reader.close()
        self.host._event_argument_owner=None;self.closed=True

    def install_consumers(self,*,receiver_state,pre_turn_immediate_state,entity_listener_count):
        self._check()
        if getattr(self,'consumer',None) is not None:raise ValueError('A0 consumers already installed')
        from .a0_family_service import A0FamilyService
        self.consumer=A0FamilyService(self,receiver_state=receiver_state,
            pre_turn_immediate_state=pre_turn_immediate_state,entity_listener_count=entity_listener_count)
        return self.consumer
