"""Owned native Player/component queries; borrowed results are never fabricated."""
from __future__ import annotations

from contextlib import contextmanager
import ctypes as C
import threading

from .configuration_profiles import XP1_CORE_SHA256,XP2_CORE_SHA256
from .native.native_core_lock import NativeCoreLock
from .native.native_player_notifications import query_player_notification_values


class PlayerNotificationService:
    def __init__(self,host,core,context,*,core_sha256,read,context_alive,core_lock):
        if core_sha256 not in (XP1_CORE_SHA256,XP2_CORE_SHA256):raise ValueError('Explicit expansion Player query profile required')
        if type(core_lock) is not NativeCoreLock or core_lock.host is not host:
            raise ValueError('Player queries require the existing native execution lock')
        if getattr(host,'_player_notification_owner',None) is not None:
            raise ValueError('Player notification owner already installed')
        self.host,self.core,self.context,self.read=host,core,context,read
        self.core_sha256=core_sha256;self.core_lock=core_lock;self._context_alive=context_alive
        self.thread=threading.get_ident();self.closed=self.quarantined=False;self.depth=0
        self._a0_event_owner=None
        from .player_notification_profiles import verify_query_live
        self.source=verify_query_live(core._handle,context,read,host_pointer=host.pointer,core_sha256=core_sha256)
        self.identity=self.source['identity']
        self.lock_slots={slot:host.vtable[slot//8] for slot in (0x30,0x38,0x40,0x48)}
        bindings=host._slot_bindings
        for slot,method in ((0x30,'owned'),(0x38,'release'),(0x40,'acquire'),(0x48,'try_acquire')):
            if bindings.get((C.addressof(host.vtable),slot))!=(self.lock_slots[slot],getattr(core_lock,method)):
                raise ValueError('Player query callback belongs to another execution lock')
        if any(not value for value in self.lock_slots.values()) or core_lock.calls['owned']() not in (0,1):
            raise ValueError('Player query execution lock is unavailable')
        host._player_notification_owner=self

    def check(self):
        if (self.closed or self.quarantined or threading.get_ident()!=self.thread
                or self._context_alive() is not True or self.host._player_notification_owner is not self):
            raise RuntimeError('Player query owner closed, quarantined, replaced or on another thread')
        from .player_notification_profiles import context_identity
        if (context_identity(self.core._handle,self.context,self.read,core_sha256=self.core_sha256)!=self.identity
                or any(self.host.vtable[s//8]!=v for s,v in self.lock_slots.items())
                or self.core_lock.calls['owned']() not in (0,1)):
            self.quarantined=True
            raise RuntimeError('Player query context or execution lock changed')

    @contextmanager
    def query(self,player_index):
        self.check()
        if self.depth:raise RuntimeError('Reentrant Player notification queries are unqualified')
        self.depth+=1
        try:
            # Keep the original getter order and native leases around the caller's
            # enqueue. NULL is solely the actual native lookup's result.
            with query_player_notification_values(self.core._handle,self.context,player_index,
                    read=self.read,core_sha256=self.core_sha256) as values:
                yield values
            self.check()
        except BaseException:
            self.quarantined=True
            raise
        finally:self.depth-=1

    def close(self, *, loaded_lifetime=None):
        if self.closed:return
        if loaded_lifetime is None:
            self.check()
        else:
            from .xp1_loaded_lifetime import require_lifetime
            require_lifetime(loaded_lifetime).check_player_close(self)
        if self.depth or self._a0_event_owner is not None:
            raise RuntimeError('Player query still has active leases or event borrowers')
        self.host._player_notification_owner=None;self.closed=True
