"""Own the existing native AUX+A0 conversion slot without a NewGame prefix.

The native C export owns all HKS calls, including errors. Python only binds and
releases its pointer. Engine callback/source admission belongs to the caller;
this service alone does not admit any saved-game profile or Lua method.
"""
from __future__ import annotations

import ctypes as C
import threading


class ScalarService:
    def __init__(self, host, runtime):
        runtime.registry._check()
        if getattr(host, '_scalar_service_owner', None) is not None:
            raise ValueError('Native scalar service already has an owner')
        function = runtime.host.LAB_AuxPushVariant
        function.argtypes, function.restype = [C.c_void_p] * 3, None
        address = C.cast(function, C.c_void_p).value
        if not address:
            raise ValueError('Native scalar service has no function address')
        self.host, self.runtime, self.function = host, runtime, function
        self.thread, self.address = threading.get_ident(), address
        self.previous, self.closed = host.aux_vtable[0xA0 // 8], False
        host._scalar_service_owner = self
        host.aux_vtable[0xA0 // 8] = address

    def close(self):
        if threading.get_ident() != self.thread:
            raise ValueError('Native scalar service belongs to another thread')
        if self.closed:
            return
        self.runtime.registry._check()
        if (getattr(self.host, '_scalar_service_owner', None) is not self
                or self.host.aux_vtable[0xA0 // 8] != self.address):
            raise ValueError('Native scalar service ownership changed')
        self.host.aux_vtable[0xA0 // 8] = self.previous
        self.host._scalar_service_owner = None
        self.closed = True
