"""Explicit application inputs using the shared local-ID and native controller.

This owns HOST D0/120 only. It does not create players, make a human roster,
advance turns or replace the native scheduler. A loaded session must separately
qualify the supplied local identity and the events which update controller state.
"""
from __future__ import annotations

import ctypes as C
import threading

from .configuration_profiles import XP1_CORE_SHA256,XP2_CORE_SHA256
from .native.native_host_events import HostControllerQuery
from .native.native_controller_code import NativeControllerCode
from .native.native_controller_state import NativeControllerTurnState


class ControlInputService(HostControllerQuery):
    def __init__(self,host,core,context,deferred,*,core_sha256,local_player_id,read,emit):
        if core_sha256 not in (XP1_CORE_SHA256,XP2_CORE_SHA256):
            raise ValueError('Control inputs require a source-qualified expansion')
        if type(local_player_id) is not int or not -1<=local_player_id<=64:
            raise ValueError('Local player ID must be explicit in -1..64')
        deferred._check()
        if (deferred.host is not host or deferred.core is not core or deferred.context!=context
                or hasattr(deferred,'turn_begin_state') or hasattr(host,'configured_local_player_id')
                or getattr(host,'_control_input_owner',None) is not None):
            raise ValueError('Control input owner is foreign or already configured')
        from .control_input_source import verify_xp1
        if core_sha256==XP2_CORE_SHA256:
            from .xp2_preload_source import verify_control
            self.source=verify_control(core._handle,context,read,host_pointer=host.pointer)
        else:
            self.source=verify_xp1(core._handle,context,read,host_pointer=host.pointer)
        self.host,self.core,self.context,self.deferred=host,core,context,deferred
        self.thread=threading.get_ident();self.emit=emit;self.local_player_id=local_player_id
        self.closed=self.quarantined=False
        self.previous={slot:(host.vtable[slot//8],host._slot_bindings.get((C.addressof(host.vtable),slot)))
                       for slot in (0xD0,0x120)}
        self.addresses={}
        host._control_input_owner=self
        try:
            execution_image=getattr(core,'_civ6_host_execution_image',None)
            self.code=(NativeControllerCode() if execution_image is None else
                       NativeControllerCode(execution_image=execution_image))
            self.turn_begin_state=NativeControllerTurnState(self.code,emit)
            deferred.turn_begin_state=self.turn_begin_state
            # The existing callback's source contract reads the supplied session
            # identity. No fallback player or guessed native roster is installed.
            host.configure_local_player_id(local_player_id)
            host._bind(host.vtable,0x120,C.c_uint8,[C.c_void_p],self.controller_flag)
            self.addresses={slot:host.vtable[slot//8] for slot in self.previous}
        except BaseException:
            self.quarantined=True
            raise  # retain callbacks/code until bounded worker termination

    def _check(self):
        if threading.get_ident()!=self.thread:
            raise ValueError('Control input owner belongs to another native thread')
        if self.closed or self.quarantined or self.host._control_input_owner is not self:
            raise RuntimeError('Control input owner closed, replaced or quarantined')
        self.deferred._check()
        if (getattr(self.deferred,'turn_begin_state',None) is not self.turn_begin_state
                or self.host.configured_local_player_id!=self.local_player_id
                or any(self.host.vtable[s//8]!=p for s,p in self.addresses.items())):
            raise RuntimeError('Control input state or callbacks were replaced')
        self.code._check()

    def controller_flag(self,receiver):
        self._check()
        try:
            return super().controller_flag(receiver)
        except BaseException:
            self.quarantined=True
            raise

    def close(self):
        if threading.get_ident()!=self.thread:
            raise ValueError('Control input close crossed its native thread')
        if self.closed:return
        self._check()
        if (self.deferred.pending or self.deferred._draining_empty_receivers
                or self.deferred.host_notification_counter or self.deferred.host_metadata_counter):
            raise RuntimeError('Control inputs still have pending events or an open scope')
        if getattr(self,'_a0_event_owner',None) is not None:
            raise RuntimeError('A0 event owner still borrows the controller')
        try:
            for slot,(pointer,binding) in self.previous.items():
                self.host.vtable[slot//8]=pointer
                key=(C.addressof(self.host.vtable),slot)
                if binding is None:self.host._slot_bindings.pop(key,None)
                else:self.host._slot_bindings[key]=binding
            self.turn_begin_state.close()
            self.code.close()
        except BaseException:
            self.quarantined=True
            raise
        del self.host.configured_local_player_id
        del self.deferred.turn_begin_state
        self.host._control_input_owner=None
        self.closed=True
