"""Owned A8/B0 callbacks composed from the shared native map adapter."""
from __future__ import annotations

import ctypes as C
import threading

from .native.native_aux_map_adapter import NativeAuxMapAdapter


class MapService:
    def __init__(self, host, runtime, core, *, core_sha256, read, allow_nested_maps=False,
                 allow_event_states=False):
        runtime.registry._check()
        if type(allow_nested_maps) is not bool:
            raise ValueError('Nested map service option must be Boolean')
        if type(allow_event_states) is not bool:
            raise ValueError('Event state service option must be Boolean')
        if getattr(host, '_map_service_owner', None) is not None:
            raise ValueError('Native map service already has an owner')
        self.host, self.runtime, self.thread = host, runtime, threading.get_ident()
        self.event_states=None
        if allow_event_states:
            from .script_event_state import ActiveEventStates
            self.event_states=ActiveEventStates(runtime)
        self.bindings = []
        for slot, name in ((0xA8,'LAB_AuxPushMap'),(0xB0,'LAB_AuxPushOptionalMap')):
            function = getattr(runtime.host,name)
            function.argtypes, function.restype = [C.c_void_p]*3+[C.c_uint8],None
            address = C.cast(function,C.c_void_p).value
            if not address:
                raise ValueError('Native map service has no function address')
            self.bindings.append((slot,address,host.aux_vtable[slot//8],function))
        self.adapter = NativeAuxMapAdapter(runtime.host,runtime,core,
            C.addressof(host.aux_object),host.emit,read=read,core_sha256=core_sha256,
            allow_nested_maps=allow_nested_maps,
            state_validator=self.event_states.accepts if self.event_states is not None else None,
            on_refusal=self._refuse_snapshot if self.event_states is not None else None)
        self.adapter.install()
        self.closed = False
        host._map_service_owner = self
        for slot,address,previous,function in self.bindings:
            host.aux_vtable[slot//8] = address

    def _refuse_snapshot(self,reason):
        # GameEvents deliberately catches listener errors. A failed host
        # snapshot must instead quarantine this worker, never become a skipped
        # gameplay rule merely because Lua caught its transport error.
        self.host._fatal('native map snapshot refused',interface='auxiliary',
                         map_error=reason,result_substituted=False)

    def close(self):
        if threading.get_ident() != self.thread:
            raise ValueError('Native map service belongs to another thread')
        if self.closed:
            return
        self.runtime.registry._check()
        if (getattr(self.host,'_map_service_owner',None) is not self
                or any(self.host.aux_vtable[slot//8] != address
                       for slot,address,previous,function in self.bindings)):
            raise ValueError('Native map service ownership changed')
        self.adapter.close()
        if self.event_states is not None:
            self.event_states.close()
        for slot,address,previous,function in self.bindings:
            self.host.aux_vtable[slot//8] = previous
        self.host._map_service_owner = None
        self.closed = True
