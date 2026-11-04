"""One explicit XP1 native population attempt borrowed from completed saved Load.

This lease authorizes the existing native facade call, not public callbacks,
postload continuation, empty queues, cleanup or a second owner/Game.
"""
from __future__ import annotations
import ctypes as C
import struct
import threading
from .configuration_profiles import BASE_CORE_SHA256,XP1_CORE_SHA256
from .saved_load_profiles import XP2_CORE_SHA256
from .cache_facade_profiles import context_state, check_facades
from .loaded_cache_profiles import qword, exact

class LoadedCachePublication:
    def __init__(self,attempt):
        from .native.native_checkpoint_postload_facades import NativeFacadeBackend
        from .native.native_official_postload import OfficialFacadeBackend
        from .native.native_checkpoint_load import NativeLoadBackend
        from .native.native_official_load import OfficialLoadBackend
        from .saved_load_services import SavedLoadServices
        from .deferred_service import DeferredService
        if (type(attempt) not in (NativeFacadeBackend,OfficialFacadeBackend)
                or attempt.publication_mode!='candidate' or attempt.cache_abi.core_sha256 not in (XP1_CORE_SHA256,XP2_CORE_SHA256)
                or type(attempt.owner) not in (NativeLoadBackend,OfficialLoadBackend)):
            raise ValueError('Candidate publication requires the retained native Load/facade owner')
        b=attempt.owner;p=b.prefix
        if (type(p) is not SavedLoadServices or type(p.deferred_events) is not DeferredService
                or p.backend is not b or p.host is not b.host or p.core is not b.core or p.context!=b.context
                or getattr(p.runtime,'service_owner',None) is not b.host
                or b.busy is not True or attempt.attempted is not True
                or b.load_abi.core_sha256!=attempt.cache_abi.core_sha256):
            raise ValueError('XP1 candidate requires its exact live SavedLoadServices binding')
        self.attempt,self.owner,self.prefix=attempt,b,p
        self.core_sha256=attempt.cache_abi.core_sha256
        self.core,self.host,self.script_runtime,self.configuration_owner=b.core,b.host,p.runtime,b.owner
        self.thread=threading.get_ident();self.stage=b.stage;self.inputs=b.inputs
        self.identity=context_state(b.core._handle,b.context,b.runtime.read,core_sha256=self.core_sha256)
        self.publisher=self.backend=None
        self.entered=self.returned=self.copied=self.poisoned=False
        self.tables=tuple((table,tuple(table)) for table in (b.host.vtable,b.host.aux_vtable,b.host.logger_vtable))
        if any(type(address) is not int or address<=0 for _,table in self.tables for address in table):
            raise ValueError('Candidate host tables require real callbacks or explicit refusal guards')
        self.bindings=dict(b.host._slot_bindings)
        self._check()
        logger=C.addressof(b.host.logger_vtable)
        for slot in (0x10,0x28,0x40):
            binding=self.bindings.get((logger,slot))
            if (binding is None or b.host.logger_vtable[slot//8]!=binding[0]
                    or getattr(binding[1],'_native_unavailable',None) is not None):
                raise ValueError('Cache population requires the actual logger channel callbacks')

    def _post160_identity(self, attempt):
        from .native.native_official_postload import OfficialPost160Backend
        if (type(attempt) is not OfficialPost160Backend or attempt.postload_mode != 'candidate'
                or attempt.owner is not self.owner or attempt.facade is not self.attempt
                or attempt._candidate_cache_lease is not self
                or self.attempt.publication_owner is not self
                or self.owner._xp1_post160_attempt is not attempt
                or not (self.entered and self.returned and self.copied)
                or self.poisoned or getattr(self, 'post160_finished', False)):
            raise ValueError('Post160 requires this completed candidate cache owner')

    def validate_completed_post160(self, attempt):
        self._post160_identity(attempt)
        if hasattr(self, 'post160_attempt') or hasattr(self.owner, '_saved_load_job_cache_owner'):
            raise ValueError('Post160 cannot reuse an active or previously borrowed cache lease')
        self._check_state('facades-candidate-observed', False)

    def begin_post160(self, attempt):
        self.validate_completed_post160(attempt)
        self.post160_attempt = attempt
        self.owner.stage = 'post160-candidate-active'
        self.owner.busy = True
        self.owner._saved_load_job_cache_owner = self
        self._check()

    def finish_post160(self, attempt):
        if getattr(self, 'post160_attempt', None) is not attempt:
            raise ValueError('Post160 cache lease belongs to another attempt')
        self._check()
        del self.owner._saved_load_job_cache_owner
        self.post160_finished = True

    def _check(self):
        lifetime = getattr(self, 'lifetime', None)
        if lifetime is not None:
            lifetime.check_wrapper_release(self)
            return self._check_state('loaded-lifetime-wrappers', True)
        continuation = getattr(self, 'continuation', None)
        if continuation is not None:
            from .xp1_continuation import SavedContinuation
            if type(continuation) is not SavedContinuation or continuation.lease is not self:
                raise ValueError('Cache continuation owner differs')
            return continuation.check(active=True)
        publication = getattr(self, 'publication_attempt', None)
        if publication is not None:
            self._publication_identity(publication)
            if getattr(self.owner, '_saved_load_job_cache_owner', None) is not self:
                raise ValueError('Publication scheduler/cache lease was replaced')
            return self._check_state('publication-candidate-active', True)
        attempt = getattr(self, 'post160_attempt', None)
        if attempt is not None:
            self._post160_identity(attempt)
            if getattr(self.owner, '_saved_load_job_cache_owner', None) is not self:
                raise ValueError('Post160 scheduler/cache lease was replaced')
            return self._check_state('post160-candidate-active', True)
        return self._check_state(self.stage, True)

    def _publication_identity(self, attempt):
        from .xp1_cache_publication import SavedCachePublication
        if (type(attempt) is not SavedCachePublication or attempt.owner is not self.owner
                or attempt.facade is not self.attempt or attempt.lease is not self
                or attempt.publisher is not self.publisher
                or self.attempt.publication_owner is not self
                or getattr(self, 'post160_finished', False) is not True
                or getattr(self, 'publication_finished', False) or self.poisoned
                or not (self.entered and self.returned and self.copied)):
            raise ValueError('Publication requires this completed post160/cache owner')

    def begin_publication(self, attempt):
        self._publication_identity(attempt)
        if hasattr(self, 'publication_attempt') or hasattr(self.owner, '_saved_load_job_cache_owner'):
            raise ValueError('Publication cannot replay or borrow an active lease')
        self._check_state('post160-candidate-observed-awaiting-controlled-stop', False)
        self.publication_attempt = attempt
        self.owner.stage = 'publication-candidate-active'
        self.owner.busy = True
        self.owner._saved_load_job_cache_owner = self
        self._check()

    def finish_publication(self, attempt):
        if getattr(self, 'publication_attempt', None) is not attempt:
            raise ValueError('Publication lease belongs to another attempt')
        self._check()
        del self.owner._saved_load_job_cache_owner
        self.publication_finished = True
        self.owner.stage = 'publication-candidate-observed-awaiting-controlled-stop'
        self.owner.busy = False

    def begin_release(self, lifetime):
        from .xp1_loaded_lifetime import LoadedLifetime
        if type(lifetime) is not LoadedLifetime or lifetime.lease is not self:
            raise ValueError('Wrapper release requires its exact loaded lifetime owner')
        lifetime.check_completed()
        if hasattr(self, 'lifetime'):
            raise ValueError('Loaded wrapper release cannot replay')
        self.lifetime = lifetime
        self.owner.stage = 'loaded-lifetime-wrappers'
        self.owner.busy = True
        self._check()

    def authorize_publisher_close(self, publisher):
        lifetime = getattr(self, 'lifetime', None)
        if lifetime is None or publisher is not self.publisher:
            raise ValueError('Candidate publisher has no qualified wrapper release owner')
        self._check()
        return lifetime

    def _check_state(self, expected_stage, expected_busy):
        b,p=self.owner,self.prefix;b.check_thread();p.check();p.deferred_events._check()
        self.configuration_owner.require_context(self.core._handle,b.context)
        if (threading.get_ident()!=self.thread or self.poisoned or b.prefix is not p
                or b.inputs is not self.inputs or b.busy is not expected_busy or b.stage!=expected_stage
                or b.core is not self.core or b.host is not self.host or p.runtime is not self.script_runtime
                or b.owner is not self.configuration_owner
                or b.reader is None or b.reader.transport.closed is not True
                or b.reader.transport.cursor!=len(self.inputs.game)
                or self.attempt.owner is not b or self.attempt.publication_mode!='candidate'
                or self.attempt.cache_abi.core_sha256!=self.core_sha256
                or b.load_abi.core_sha256!=self.core_sha256
                or p.configuration_readback_verified is not True
                or b.host._saved_load_services is not p or p.runtime.service_owner is not b.host
                or p.core is not b.core or p.context!=b.context
                or context_state(b.core._handle,b.context,b.runtime.read,core_sha256=self.core_sha256)!=self.identity
                or self.identity['game']!=b.bound_identity['game']
                or exact(b.runtime.read,self.identity['game']+0x2A4,1)!=b'\1'):
            raise RuntimeError('Candidate loaded-cache ownership or phase changed')
        if any(tuple(table)!=snapshot for table,snapshot in self.tables) or b.host._slot_bindings!=self.bindings:
            raise RuntimeError('Candidate host callback binding changed')
        if self.core_sha256==XP2_CORE_SHA256:
            from .xp2_cache_source import source
            globals_=source()['profile']['host_globals']
        else:globals_=(0x9F2640,0x9F2648,0x9F2650)
        for rva,ptr in zip(globals_,(b.host.pointer,C.addressof(b.host.aux_object),C.addressof(b.host.logger_object))):
            if qword(b.runtime.read,b.core._handle+rva)!=ptr:raise ValueError('Candidate Core host global differs')
        if self.publisher is not None:
            if (self.attempt.publisher is not self.publisher or p.view_publisher is not self.publisher
                    or self.publisher._closed or self.publisher.native_cache_gate is not False
                    or self.publisher.full_facade_initialization_reproduced is not False):
                raise RuntimeError('Candidate publisher replaced or public gate enabled')

    def attach(self,publisher,backend):
        self._check()
        if self.publisher is not None or self.backend is not None:raise RuntimeError('Candidate cache backend already bound')
        if (publisher.core is not self.owner.core or publisher.context!=self.owner.context
                or backend.core_base!=self.owner.core._handle
                or backend.abi.core_sha256!=self.core_sha256
                or publisher.cache_abi.core_sha256!=self.core_sha256 or backend.publication_owner is not self):
            raise ValueError('Candidate cache backend belongs to another native owner')
        self.publisher,self.backend=publisher,backend
        self._check()

    def require(self,backend,facades=None):
        self.check_backend(backend)
        if self.backend is not backend or self.publisher is None or backend.publication_owner is not self:
            raise ValueError('Candidate cache capability is not owned by this backend')
        actual=self.publisher._facades
        if actual is None or actual.backend is not backend or (facades is not None and actual is not facades):
            raise ValueError('Candidate facade owner differs')
        check_facades(actual,self.identity,self.owner.runtime.read)
        return actual

    def check_backend(self,backend):
        self._check()
        if self.backend is not backend or backend.publication_owner is not self:
            raise ValueError('Candidate typed backend was replaced')

    def _wrapper(self,backend,pointer,vtable):
        a=backend.abi
        field={a.game_facade_vtable_rva:'owner',a.cache_service_vtable_rva:'member',
            a.system_facade_vtable_rva:'system_member',a.cache_b0_result_vtable_rva:'b0_result_owner',
            a.cache_c0_result_vtable_rva:'c0_result_owner'}.get(vtable)
        if field is None or type(pointer) is not int or pointer<=0:
            raise ValueError('Candidate facade allocation/receiver is not a usable native wrapper')
        raw=exact(self.owner.runtime.read,pointer,32)
        if struct.unpack_from('<QQQI',raw)!=(backend.core_base+vtable,0,self.identity[field],1):
            raise ValueError('Candidate native facade branch, owner or reference count differs')

    def before_backend_call(self,backend,target,arguments):
        self.check_backend(backend);a=backend.abi;rva=target-backend.core_base
        matches=[key for key,value in a.targets.items() if value==rva]
        if len(matches)!=1 or not arguments or type(arguments[0]) is not int:
            raise ValueError('Candidate facade call target or receiver differs')
        vt,slot=matches[0]
        if vt==a.outer_vtable_rva:
            if slot not in (0xA0,0xB0,0xD0) or arguments[0]!=self.owner.context:
                raise ValueError('Candidate cannot release or replace the borrowed root')
        else:self._wrapper(backend,arguments[0],vt)

    def after_backend_call(self,backend,target,result):
        self.check_backend(backend);a=backend.abi;rva=target-backend.core_base
        result_vtables={a.targets[(a.outer_vtable_rva,0xA0)]:a.game_facade_vtable_rva,
            a.targets[(a.outer_vtable_rva,0xB0)]:a.cache_service_vtable_rva,
            a.targets[(a.outer_vtable_rva,0xD0)]:a.system_facade_vtable_rva,
            a.targets[(a.cache_service_vtable_rva,0xB0)]:a.cache_b0_result_vtable_rva,
            a.targets[(a.cache_service_vtable_rva,0xC0)]:a.cache_c0_result_vtable_rva}
        if rva in result_vtables:self._wrapper(backend,result,result_vtables[rva])

    def begin(self,backend,receiver):
        facades=self.require(backend)
        if self.entered or self.returned or self.copied or receiver!=facades.game_facade:
            raise RuntimeError('Candidate population cannot be reentered, replayed or rebound')
        self.entered=True

    def native_returned(self,backend):
        self.require(backend)
        if not self.entered or self.returned:raise RuntimeError('Candidate publication return is out of order')
        self.returned=True

    def copy_returned(self,backend,facades):
        self.require(backend,facades)
        if not self.returned or self.copied:raise RuntimeError('Candidate copy lacks one completed native publication')
        self.copied=True

    def poison(self):
        self.poisoned=True
        self.owner.poisoned=True
        self.prefix.quarantined=True
        if getattr(self.owner,'_saved_load_job_cache_owner',None) is self:
            del self.owner._saved_load_job_cache_owner

def require_candidate(backend,facades=None):
    owner=getattr(backend,'publication_owner',None)
    if type(owner) is not LoadedCachePublication:raise ValueError('An exact loaded-cache candidate owner is required')
    owner.require(backend,facades)
    return owner

def initial_publisher_state(prefix,core_sha256):
    if getattr(prefix,'view_publisher',None) is not None or prefix.configuration_readback_verified is not True:
        raise RuntimeError('Cache publisher already exists or configuration is unverified')
    d=prefix.deferred_events
    if core_sha256==BASE_CORE_SHA256:
        if d.ui_cache_callbacks_enabled is not False or d.retained_game_getter is not None or d.retained_combat_predicate is not None:
            raise RuntimeError('Public cache callbacks already bound')
        return
    if core_sha256 not in (XP1_CORE_SHA256,XP2_CORE_SHA256):raise ValueError('Unknown cache publisher engine')
    from .deferred_service import DeferredService
    if type(d) is not DeferredService:raise ValueError('XP1 candidate needs its shared deferred owner')
    d._check()
    # This owner intentionally has no public callback facade. Do not create one,
    # populate empty fields or treat lack of an owner as a successful public gate.
    for name in ('ui_cache_callbacks_enabled','retained_game_getter','retained_combat_predicate','retained_cache_facades'):
        if hasattr(d,name):raise ValueError('XP1 candidate unexpectedly has public cache bindings')

def source_dependencies(*,core_sha256=XP1_CORE_SHA256):
    from .cache_facade_profiles import source_pins
    from .xp1_cache_publication import source_dependencies as publication_dependencies
    from .a0_emergencies_updated import source_dependencies as event_dependencies
    result=source_pins(core_sha256=core_sha256)
    result.update(publication_dependencies(core_sha256=core_sha256))
    result.update(event_dependencies(core_sha256=core_sha256))
    return result
