"""Own one official Game facade reference; borrow its native cache owner."""
from __future__ import annotations

import ctypes as C
import struct
import threading
from .configuration_profiles import XP1_CORE_SHA256
from .saved_load_profiles import XP2_CORE_SHA256
from .native.native_retained_game_getter import read_retained_game_value


class RetainedGameLease:
    def __init__(self,core,context,read,*,core_sha256,context_alive):
        if core_sha256 not in (XP1_CORE_SHA256,XP2_CORE_SHA256) or not callable(context_alive):
            raise ValueError('Retained Game lease requires XP1 and its live context owner')
        from .retained_game_source import getter_abi,verify_live,context_state
        self.core,self.core_base,self.context,self.read=core,core._handle,context,read
        self.core_sha256,self._alive=core_sha256,context_alive
        self.thread=threading.get_ident();self._closed=self.quarantined=False
        self.game_facade=0;self.backend=self
        self.abi=getter_abi(core_sha256)
        if not self.context_alive():raise ValueError('Retained Game context unavailable')
        self.source=verify_live(self.core_base,context,read,core_sha256=core_sha256)
        self.identity=context_state(self.core_base,context,read,core_sha256=core_sha256)
        try:
            self.game_facade=int(C.WINFUNCTYPE(C.c_void_p,C.c_void_p)(
                self.core_base+self.abi.factory_rva)(context) or 0)
            self.check()
            if struct.unpack('<I',read(self.game_facade+0x18,4))[0]!=1:
                raise ValueError('New retained Game facade does not own one reference')
        except BaseException:
            self.quarantined=True
            raise

    def context_alive(self):
        return bool(not self._closed and not self.quarantined and threading.get_ident()==self.thread and self._alive())

    def check(self):
        from .retained_game_source import context_state
        if not self.context_alive():raise RuntimeError('Retained Game lease closed, poisoned or foreign thread')
        if context_state(self.core_base,self.context,self.read,core_sha256=self.core_sha256)!=self.identity:
            raise RuntimeError('Retained Game cache owner changed')
        def q(addr):
            raw=self.read(addr,8)
            if type(raw) is not bytes or len(raw)!=8:raise ValueError('Incomplete retained Game read')
            return struct.unpack('<Q',raw)[0]
        p=self.game_facade
        if (not p or q(p)!=self.core_base+self.abi.facade_vtable_rva or q(p+8)!=0
                or q(p+16)!=self.identity['owner']):
            raise ValueError('Retained Game facade does not borrow its real native cache')

    def value(self):
        self.check()
        try:
            return read_retained_game_value(self,self.read,core_sha256=self.core_sha256)
        except BaseException:
            self.quarantined=True
            raise

    def close(self):
        if self._closed:return
        self.check()
        if struct.unpack('<I',self.read(self.game_facade+0x18,4))[0]!=1:
            raise RuntimeError('Retained Game facade reference count changed')
        try:
            # The official release frees this facade; the cache stays owned by
            # Core. Never inspect the freed facade or release its borrowed owner.
            C.WINFUNCTYPE(None,C.c_void_p)(self.core_base+self.abi.release_rva)(self.game_facade)
        except BaseException:
            self.quarantined=True
            raise
        self.game_facade=0;self._closed=True
