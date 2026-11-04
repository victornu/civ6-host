"""Own native XP1 cache facades without presenting prepared data as game state."""
from __future__ import annotations

import struct
import threading

from .configuration_profiles import XP1_CORE_SHA256
from .saved_load_profiles import XP2_CORE_SHA256
from .cache_facade_profiles import source, context_state, check_facades
from .native.native_ui_cache_backend import NativeCacheFacadeBackend
from .native.native_ui_cache_facades import NativeUiCacheFacades
from .native.native_retained_game_getter import read_retained_game_value


class _OwnedBackend(NativeCacheFacadeBackend):
    """Check borrowed owners around the unchanged typed call sequence."""
    def __init__(self, service):
        self.service=service
        super().__init__(service.core,service._gate_changed,context_alive=service._alive,
            read=service.read,core_sha256=service.core_sha256)

    def call(self,target,*arguments):
        s=self.service
        s._check_identity()
        a=self.abi;rva=target-self.core_base
        if rva==a.publish_rva:
            raise ValueError('Loaded Game cache publication is not qualified for XP1')
        vt_slot=next(((vt,slot) for (vt,slot),value in a.targets.items() if value==rva),None)
        if vt_slot is None or not arguments or type(arguments[0]) is not int:
            raise ValueError('Unqualified cache facade call')
        vt,slot=vt_slot
        if vt==a.outer_vtable_rva:
            if slot==8 or arguments[0]!=s.context:
                raise ValueError('Borrowed root context cannot be released or substituted')
        else:s._check_wrapper(arguments[0],vt)
        try:
            result=super().call(target,*arguments)
            s._check_identity()
            if rva in a.getter_rvas:
                expected={
                    (a.outer_vtable_rva,0xA0):a.game_facade_vtable_rva,
                    (a.outer_vtable_rva,0xB0):a.cache_service_vtable_rva,
                    (a.outer_vtable_rva,0xD0):a.system_facade_vtable_rva,
                    (a.cache_service_vtable_rva,0xB0):a.cache_b0_result_vtable_rva,
                    (a.cache_service_vtable_rva,0xC0):a.cache_c0_result_vtable_rva,
                }[(vt,slot)]
                s._check_wrapper(result,expected)
            return result
        except BaseException:
            s.quarantined=True
            raise  # No native retry or cleanup after an uncertain effect.


class CacheFacadeService:
    """Borrow one prepared context and own its five reference-counted wrappers.

    This internal service returns native cached bytes with their prepared-state
    provenance. They are not player observations. Full population requires a
    separately qualified loaded Game and stays explicitly unavailable here.
    """
    def __init__(self,core,context,*,core_sha256,read,context_alive):
        if core_sha256 not in (XP1_CORE_SHA256,XP2_CORE_SHA256):raise ValueError('Explicit expansion engine required')
        self.core_sha256=core_sha256
        self.core,self.context,self.read=core,context,read
        self._context_alive=context_alive
        self.thread=threading.get_ident()
        self.closed=self.quarantined=False
        self.public_cache_ready=False
        self.profile=source(core_sha256=core_sha256)['profile']
        self.identity=context_state(core._handle,context,read,core_sha256=core_sha256)
        self.backend=_OwnedBackend(self)
        try:
            self.facades=NativeUiCacheFacades(self.backend,context,core_sha256=core_sha256)
            self.check()
        except BaseException:
            self.quarantined=True
            raise

    def _alive(self):
        return (not self.closed and not self.quarantined and threading.get_ident()==self.thread
                and self._context_alive() is True)

    def _check_identity(self):
        if not self._alive():raise RuntimeError('Cache facade owner closed, quarantined or unavailable')
        try:
            if context_state(self.core._handle,self.context,self.read,core_sha256=self.core_sha256)!=self.identity:
                raise RuntimeError('Native cache owner was replaced')
        except BaseException:
            self.quarantined=True
            raise

    def _check_wrapper(self,ptr,vt):
        p=self.profile
        owner={p['game_facade_vtable_rva']:'owner',p['cache_service_vtable_rva']:'member',
            p['system_facade_vtable_rva']:'system_member',p['cache_b0_result_vtable_rva']:'b0_result_owner',
            p['cache_c0_result_vtable_rva']:'c0_result_owner'}[vt]
        if not ptr:raise ValueError('Native facade factory returned null')
        raw=self.read(ptr,32)
        if (type(raw) is not bytes or len(raw)!=32
                or struct.unpack_from('<QQQI',raw)!=(self.core._handle+vt,0,self.identity[owner],1)):
            raise ValueError('Native facade branch, owner or reference count changed')

    def _gate_changed(self,enabled):
        if enabled is not False:raise ValueError('Prepared cache metadata cannot enable player observations')
        self.public_cache_ready=False

    def check(self):
        self._check_identity()
        try:check_facades(self.facades,self.identity,self.read)
        except BaseException:
            self.quarantined=True
            raise

    def copy_cached_metadata(self):
        """Copy the official 28-byte cache block and replace B0/C0 references."""
        self.check()
        try:
            result=self.facades._copy_cache_outputs()
            self.check()
            return result
        except BaseException:
            self.quarantined=True
            raise

    def retained_game_value(self):
        self.check()
        try:
            return read_retained_game_value(self.facades,self.read,core_sha256=self.core_sha256)
        except BaseException:
            self.quarantined=True
            raise

    def close(self):
        if self.closed:return
        self.check()
        try:self.facades.close()
        except BaseException:
            self.quarantined=True
            raise
        self.closed=True
