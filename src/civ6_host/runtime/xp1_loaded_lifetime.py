"""Explicit expansion lifetime in the existing context/service pipeline.

This is a private candidate, not public session admission. A failed or uncertain
native effect poisons the owner; cleanup never retries or substitutes OS exit.
"""
import ctypes as C
import threading
import hashlib
from collections.abc import Mapping
from pathlib import Path
from .configuration_profiles import XP1_CORE_SHA256, XP2_CORE_SHA256, _source, _body

SOURCE=('work/host-extensions/xp1-loaded-lifetime-static/loaded-lifetime-source-v1.json',
        'afbbaa559595a916f1a47f7c63428ecbcf59853c1f11c2a34eeceff52c32b3b7')

def source(core_sha256=XP1_CORE_SHA256):
    if core_sha256==XP2_CORE_SHA256:
        from .xp2_loaded_lifetime_source import source as selected
        return selected()
    if core_sha256!=XP1_CORE_SHA256:raise ValueError('Unknown loaded lifetime engine')
    p=_source(SOURCE)
    if (p['schema']!='civ6_host.xp1_loaded_lifetime.static.v1' or p['native_execution'] is not False
            or p['image_sha256']!=XP1_CORE_SHA256
            or dict(p['slots'])!={'0x8a8df0+0x48':'0x4be690','0x8d7168+0x58':'0x3d970',
                                  '0x8d7360+0x0':'0x557840'}
            or p['contract']['unload_before_destroy'] is not True
            or p['contract']['public_loaded_lifetime_admitted'] is not False):
        raise ValueError('Loaded XP1 lifetime source changed')
    for body in p['bodies'].values():_body(body)
    for ref in p['references']:_source((ref['path'],ref['sha256']))
    return p

def source_dependencies(core_sha256=XP1_CORE_SHA256,*,postload=False,continuation=False):
    if type(continuation) is not bool or continuation and (not postload or core_sha256!=XP2_CORE_SHA256):
        raise ValueError('Continuation lifetime dependencies require XP2 postload')
    from .paths import resource_root
    from .resource_resolution import resolve_path
    selected=SOURCE
    if core_sha256==XP2_CORE_SHA256:
        from .xp2_loaded_lifetime_source import SOURCE as selected
    rows={selected[0]:selected[1]};p=source(core_sha256)
    def add(ref):
        path,digest=ref['path'],ref['sha256']
        if path in rows:
            if rows[path]!=digest:raise ValueError('Conflicting lifetime dependency')
            return
        rows[path]=digest
        actual=resolve_path(resource_root()/path)
        if actual.suffix.lower()!='.json':
            if hashlib.sha256(actual.read_bytes()).hexdigest()!=digest:
                raise ValueError('Lifetime source dependency changed: '+str(actual))
            return
        value=_source((path,digest))
        if not isinstance(value,Mapping):return
        for key in ('references','parents'):
            children=value.get(key,{})
            children=children.values() if hasattr(children,'values') else children
            for child in children:
                if hasattr(child,'get') and child.get('path') and child.get('sha256'):add(child)
    for ref in p['references']:add(ref)
    if core_sha256==XP2_CORE_SHA256:
        for key in ('generator','boundary_helper','extractor'):add(p[key])
    pins={str(resolve_path(resource_root()/path).resolve()):digest for path,digest in rows.items()}
    if core_sha256==XP2_CORE_SHA256:
        from .a0_district_removed import source_dependencies as district_dependencies
        pins.update(district_dependencies(core_sha256))
        if postload:
            from .xp2_loaded_lifetime_source import postload_source_dependencies
            for path,digest in postload_source_dependencies().items():
                if path in pins and pins[path]!=digest:
                    raise ValueError('Conflicting XP2 postload lifetime dependency: '+path)
                pins[path]=digest
    elif postload:
        raise ValueError('Postload lifetime dependencies are XP2-only')
    if continuation:
        from .xp2_action_transport_source import source_dependencies as action_dependencies
        from .xp2_turn_source import source_dependencies as turn_dependencies
        for group in (action_dependencies(),turn_dependencies()):
            for path,digest in group.items():
                if path in pins and pins[path]!=digest:
                    raise ValueError('Conflicting XP2 continuation lifetime dependency: '+path)
                pins[path]=digest
    return pins

def _q(read,address):
    raw=read(address,8)
    if type(raw) is not bytes or len(raw)!=8:raise ValueError('Incomplete lifetime pointer read')
    return int.from_bytes(raw,'little')

def _unloaded_record(record,consumer):
    from .native.native_deferred_empty_profile import validate_empty_profile_record
    if type(record) is not bytes or len(record)<12:
        return False
    kind=int.from_bytes(record[4:8],'little')
    if kind in (0x113,0xF7) or not consumer.handles_record(kind):
        return False
    # Only the already installed A0 receiver family: these copied byte records
    # take the proven no-hook/no-subscriber path, without dereferencing payloads
    # or calling Core. Native CacheUpdate feedback requires a live cache instead.
    validate_empty_profile_record(record,**consumer.empty_receiver_state)
    return True

def verify_live(b):
    if getattr(getattr(b,'load_abi',None),'core_sha256',XP1_CORE_SHA256)==XP2_CORE_SHA256:
        from .xp2_loaded_lifetime_source import verify_live as selected
        return selected(b)
    p=source();base=b.core._handle;read=b.runtime.read
    for body in p['bodies'].values():
        for fragment in _body(body)['fragments']:
            for row in fragment['instructions']:
                raw=bytes.fromhex(row['bytes'])
                if read(base+int(row['va'],16)-0x180000000,len(raw))!=raw:
                    raise ValueError('Loaded lifetime instruction changed')
    for key,value in p['slots'].items():
        vt,slot=map(lambda s:int(s,16),key.split('+'))
        if _q(read,base+vt+slot)!=base+int(value,16):raise ValueError('Loaded lifetime slot changed')
    # The retained source bodies cover the complete unload, Game shutdown,
    # registry clear and host-detach boundaries, not an emulated destructor.
    for ref in p['references']:
        if 'deferred-load-static' in ref['path']:
            bodies=_source((ref['path'],ref['sha256']))['functions']['xp1']
            for name in ('inner_destroy','game_teardown','destroy_host_registry'):
                for f in _body(bodies[name])['fragments']:
                    for row in f['instructions']:
                        raw=bytes.fromhex(row['bytes'])
                        if read(base+int(row['va'],16)-0x180000000,len(raw))!=raw:
                            raise ValueError('Loaded teardown boundary changed: '+name)
    return p

class LoadedLifetime:
    """One shutdown attempt borrowed from the actual successful loaded owner."""
    def __init__(self,owner,completed,*,raw_loaded=False):
        from .native.native_official_load import OfficialLoadBackend
        from .native.native_official_postload import OfficialPost160Backend
        from .loaded_cache_publication import LoadedCachePublication
        from .xp1_cache_publication import SavedCachePublication
        from .xp1_continuation import SavedContinuation
        if type(owner) is not OfficialLoadBackend or hasattr(owner,'_loaded_lifetime'):
            raise ValueError('Loaded lifetime needs one fresh official saved owner')
        if type(raw_loaded) is not bool:raise ValueError('Invalid raw lifetime mode')
        self.raw_loaded=raw_loaded
        engine_sha=owner.load_abi.core_sha256
        self.xp2_loaded=engine_sha==XP2_CORE_SHA256
        if engine_sha not in (XP1_CORE_SHA256,XP2_CORE_SHA256):
            raise ValueError('Unknown loaded lifetime engine')
        self.source_reference=SOURCE
        if self.xp2_loaded:
            from .xp2_loaded_lifetime_source import SOURCE as selected
            self.source_reference=selected
        if raw_loaded:
            if completed is not owner or not self.xp2_loaded:
                raise ValueError('Raw lifetime requires its own exact XP2 Load backend')
            lease=None
        elif type(completed) is OfficialPost160Backend:
            lease=completed._candidate_cache_lease
        elif type(completed) is SavedCachePublication:
            lease=completed.lease
        elif type(completed) is SavedContinuation:
            completed.check_close();lease=completed.lease
        else:raise ValueError('Loaded lifetime needs a completed native postload/publication owner')
        if not raw_loaded and (type(lease) is not LoadedCachePublication or lease.owner is not owner):
            raise ValueError('Loaded lifetime has a foreign cache owner')
        self.owner,self.completed,self.lease=owner,completed,lease
        self.prefix,self.host,self.core,self.application=owner.prefix,owner.host,owner.core,owner.owner
        self.runtime,self.child,self.lock=self.prefix.runtime,self.prefix.game_child,self.host.execution_lock
        self.context=owner.context
        self.inner=owner.bound_identity['inner'] if raw_loaded else lease.identity['inner']
        self.player_view=getattr(owner,'_xp1_player_view',None)
        self.ui_child=getattr(self.prefix,'ui_child',None)
        self.ui_source_dependencies=None
        self.ui_child_released=False
        self.action_transport=None
        self.continuation_source_dependencies=None
        self.continuation_source_receipt=None
        self.thread=threading.get_ident();self.phase='new';self.steps=[];self.poisoned=False
        self.unload_called=self.unload_returned=self.destroy_called=self.destroy_returned=False
        self.report=None
        self.check_completed()
        if not raw_loaded:
            previous=self.prefix.status_messages.previous[1]
            if previous is None or getattr(previous[1],'_native_unavailable',None)!=('host',0xC0):
                raise ValueError('Status wrapper release must restore the original explicit refusal')
        if self.xp2_loaded and not self.raw_loaded:
            from .xp2_loaded_lifetime_source import verify_postload_live
            self.proof=verify_postload_live(owner)
            self.postload_source_dependencies=source_dependencies(XP2_CORE_SHA256,postload=True)
        else:
            self.proof=verify_live(owner)
            self.postload_source_dependencies=None
        owner._loaded_lifetime=self

    def check_completed(self):
        if self.raw_loaded:
            self._check_raw_completed()
            return
        from .native.native_official_postload import OfficialPost160Backend,validate_owner
        from .xp1_cache_publication import SavedCachePublication,COMPLETED_STAGE
        from .xp1_continuation import SavedContinuation,READY
        from .xp1_postload_candidate import FINISHED_STAGE
        b=self.owner;l=self.lease;a=self.completed
        if type(a) is OfficialPost160Backend:
            stage=FINISHED_STAGE
            if (l.post160_attempt is not a or l.post160_finished is not True
                    or b._xp1_post160_attempt is not a or not a.attempted or not a.native_call_attempted
                    or a.candidate_diagnostics.get('void_return_ignored') is not True
                    or hasattr(l,'publication_attempt')):
                raise ValueError('Loaded lifetime lacks a completed +160 owner')
        elif type(a) is SavedCachePublication:
            stage=COMPLETED_STAGE
            if (l.publication_attempt is not a or l.publication_finished is not True
                    or b._xp1_publication_attempt is not a or a.completed is not True
                    or a.native_returned is not True or type(a.result) is not dict):
                raise ValueError('Loaded lifetime lacks a completed +190 owner')
        elif type(a) is SavedContinuation:
            stage=READY;a.check_close()
        else:raise ValueError('Unknown completed lifetime owner')
        validate_owner(b,stage=stage)
        expected_sha=XP2_CORE_SHA256 if self.xp2_loaded else XP1_CORE_SHA256
        if (b.load_abi.core_sha256!=expected_sha or a.owner is not b or b.busy
                or l.poisoned or l.publisher is not b.prefix.view_publisher
                or l.attempt.publication_owner is not l or not(l.entered and l.returned and l.copied)
                or hasattr(b,'_saved_load_job_cache_owner')):
            raise ValueError('Completed loaded lifetime ownership changed')
        l._check_state(stage,False)
        b.control(empty=True)
        if self.xp2_loaded:
            self._require_xp2_postload_services()
            receipt=self.prefix.validate_postload_aux90()
            publication=a.publication if type(a) is SavedContinuation else a
            receipt_owner=publication.post if type(publication) is SavedCachePublication else publication
            if (receipt.get('core_sha256')!=XP2_CORE_SHA256
                    or receipt.get('native_calls_made') is not False
                    or not receipt.get('dependencies')
                    or getattr(receipt_owner,'aux90_validation',None)!=receipt):
                raise ValueError('XP2 loaded lifetime lacks its actual AUX90 source owner')

    def _check_raw_completed(self):
        b=self.owner
        if (b.stage!='raw-loaded' or b.busy is not False or b.load_attempted is not True
                or b.poisoned or b.destroyed or b.snapshot_phase!='postflight'
                or b.reader is None or b.reader.transport.closed is not True
                or b.reader.transport.cursor!=len(b.inputs.game)
                or getattr(b,'_saved_load_candidate',False) is not True):
            raise ValueError('Raw lifetime lacks a validated complete Load and closed reader')
        result=getattr(b,'raw_load_result',None)
        if (type(result) is not dict or result.get('status')!=0 or type(result.get('status')) is not int
                or result.get('bytes_consumed')!=len(b.inputs.game)
                or result.get('game_initialized')!=1
                or result.get('load_source_sha256')!=b.load_source_sha256):
            raise ValueError('Raw lifetime lacks the retained validated Load result')
        if (hasattr(self,'raw_load_result') and self.raw_load_result is not result
                or hasattr(self,'raw_identity') and self.raw_identity!=b.bound_identity):
            raise ValueError('Raw lifetime retained completion owner changed')
        self.raw_load_result=result
        self.raw_identity=dict(b.bound_identity)
        self._check_raw_alive()
        b.control(empty=False)

    def _check_raw_alive(self):
        from .saved_load_services import SavedLoadServices
        from .prepare_services import PrepareServices
        from .native.native_core_lock import NativeCoreLock
        b=self.owner;p=self.prefix
        b.check_thread()
        if (type(p) is not SavedLoadServices or p.backend is not b or p.host is not self.host
                or p.core is not self.core or p.context!=self.context or p.core_sha256!=XP2_CORE_SHA256
                or b.load_abi.core_sha256!=XP2_CORE_SHA256 or b.configuration_abi.core_sha256!=XP2_CORE_SHA256
                or b.topology(game_required=True)!=self.raw_identity or b.bound_identity!=self.raw_identity
                or b.game_flag()!=1 or b.raw_load_result is not self.raw_load_result
                or self.raw_identity['inner']!=self.inner or self.application.closed
                or not (self.runtime.database_bound and self.runtime.configuration_bound and self.runtime.locale_bound)
                or self.runtime.service_owner is not self.host or type(self.lock) is not NativeCoreLock
                or self.lock.host is not self.host or self.lock.calls['owned']() not in (0,1)):
            raise ValueError('Raw lifetime native Game or borrowed owner differs')
        self._require_raw_services()
        p.check();self.application.require_context(self.core._handle,self.context)
        service=getattr(self.host,'_xp2_prepare_services',None)
        if (type(service) is not PrepareServices or service is not getattr(self.host,'_prepare_services',None)
                or service.host is not self.host or service.base!=self.core._handle
                or hasattr(self,'prepare_services') and self.prepare_services is not service):
            raise ValueError('Raw lifetime lost its actual Prepare registry owner')
        service.require_complete()
        self.prepare_services=service

    def _require_xp2_postload_services(self):
        from .cache_facade_service import CacheFacadeService
        from .player_notification_service import PlayerNotificationService
        from .status_message_service import StatusMessageService
        from .native.native_player_view import NativePlayerViewPublisher
        p=self.prefix;b=self.owner
        publisher=getattr(p,'view_publisher',None)
        if (type(p.cache_facades) is not CacheFacadeService
                or p.cache_facades.closed or p.cache_facades.quarantined
                or p.cache_facades.core is not self.core or p.cache_facades.context!=self.context
                or type(p.player_queries) is not PlayerNotificationService
                or p.player_queries.closed or p.player_queries.quarantined
                or type(p.status_messages) is not StatusMessageService
                or p.status_messages.closed or p.status_messages.quarantined
                or type(publisher) is not NativePlayerViewPublisher
                or getattr(publisher,'_closed',True)
                or publisher.core is not self.core
                or getattr(publisher,'context',self.context)!=self.context
                or p.player_queries.host is not self.host or p.player_queries.core is not self.core
                or p.player_queries.context!=self.context or p.status_messages.host is not self.host
                or p.player_queries.core_lock is not self.lock
                or p.player_queries._a0_event_owner is not p.event_arguments.consumer
                or p.status_messages.arguments is not p.event_arguments
                or p.status_messages.deferred is not p.deferred_events
                or p.deferred_events.core is not self.core
                or p.deferred_events.context!=self.context
                or p.deferred_events.cache_core_sha256!=XP2_CORE_SHA256
                or p.event_arguments.host is not self.host or p.event_arguments.deferred is not p.deferred_events
                or p.event_arguments.consumer.player_query_owner is not p.player_queries):
            raise ValueError('XP2 postload lifetime lacks its complete native cache/player/status owners')
        from .xp1_continuation import SavedContinuation,READY
        continuation=type(self.completed) is SavedContinuation
        if continuation:
            self._require_xp2_continuation()
        elif hasattr(p,'actions') or hasattr(b,'_xp1_continuation'):
            raise ValueError('XP2 postload lifetime has an unowned command continuation')
        self._validate_saved_player_view()
        p.validate_postload_aux90()
        lease=self.lease
        if (lease.owner is not b or lease.prefix is not p or lease.host is not self.host
                or lease.core is not self.core or lease.script_runtime is not self.runtime
                or lease.publisher is not publisher
                or lease.attempt.cache_abi.core_sha256!=XP2_CORE_SHA256):
            raise ValueError('XP2 postload cache lease/publisher owner differs')
        # The publication lease's _check() is intentionally active-only: after
        # finish_publication it rejects a completed publication. Revalidate the
        # retained completed stage through the same structural state checker.
        if getattr(lease,'publication_finished',False) is True:
            from .xp1_cache_publication import COMPLETED_STAGE
            if (getattr(lease,'publication_attempt',None) is not getattr(b,'_xp1_publication_attempt',None)
                    or getattr(lease.publication_attempt,'completed',False) is not True
                    or getattr(lease.publication_attempt,'native_returned',False) is not True):
                raise ValueError('XP2 postload publication completion owner differs')
            lease._check_state(READY if continuation else COMPLETED_STAGE,False)
        elif getattr(lease,'post160_finished',False) is True:
            from .xp1_postload_candidate import FINISHED_STAGE
            if getattr(lease,'post160_attempt',None) is not getattr(b,'_xp1_post160_attempt',None):
                raise ValueError('XP2 postload +160 completion owner differs')
            lease._check_state(FINISHED_STAGE,False)
        else:
            raise ValueError('XP2 postload cache lease has no completed publication stage')
        service=getattr(self.host,'_xp2_prepare_services',None)
        if (service is None or service is not getattr(self.host,'_prepare_services',None)
                or service.host is not self.host or service.base!=self.core._handle
                or hasattr(self,'prepare_services') and self.prepare_services is not service):
            raise ValueError('XP2 postload lifetime lost its native Prepare registry owner')
        service.require_complete();self.prepare_services=service

    def _require_xp2_continuation(self):
        """Retain the exact completed command owner without invoking a command."""
        from .xp1_action_transport import SavedActionTransport
        from .xp1_continuation import SavedContinuation
        from .xp1_cache_publication import SavedCachePublication
        from .xp2_action_transport_source import ABI,SOURCE as action_source,CALLBACKS,verify_live,verify_owners
        b,p,a=self.owner,self.prefix,self.completed
        transport=getattr(p,'actions',None)
        publication=getattr(a,'publication',None)
        if (type(a) is not SavedContinuation or getattr(b,'_xp1_continuation',None) is not a
                or type(transport) is not SavedActionTransport or a.transport is not transport
                or transport.backend is not b or transport.services is not p
                or transport.host is not self.host or transport.core is not self.core
                or transport.context!=self.context or transport.transport_abi is not ABI
                or type(publication) is not SavedCachePublication
                or publication.owner is not b or publication.lease is not self.lease
                or publication is not getattr(b,'_xp1_publication_attempt',None)
                or a.lease is not self.lease or a.view is not self.player_view
                or a.publisher is not p.view_publisher or a.runtime is not self.runtime
                or a.ui_child is not self.ui_child or a.game_child is not self.child
                or getattr(self,'action_transport',None) not in (None,transport)):
            raise ValueError('XP2 continuation lifetime lost its exact command/publication owner')
        unit=getattr(a,'unit_source',None);event=getattr(transport,'event_source',None)
        if (type(unit) is not dict or unit.get('core_sha256')!=XP2_CORE_SHA256
                or unit.get('source_sha256')!=action_source[1] or unit.get('callbacks')!=CALLBACKS
                or type(event) is not dict or event.get('core_sha256')!=XP2_CORE_SHA256
                or event.get('source_sha256')!=action_source[1]):
            raise ValueError('XP2 continuation lifetime command source identity differs')
        # check_close already checks publication, episode, registry and both
        # queues. Recheck the transport's real callback/recorder ownership here.
        transport.require_empty_native_queue()
        verify_owners(self.core._handle,self.context,b.runtime.read,
                      host_pointer=self.host.pointer,auxiliary_pointer=C.addressof(self.host.aux_object))
        if getattr(self,'continuation_source_receipt',None) is None:
            receipt=verify_live(self.core._handle,b.runtime.read,family='transport',context=self.context)
            self.continuation_source_dependencies=source_dependencies(XP2_CORE_SHA256,postload=True,continuation=True)
            self.continuation_source_receipt=receipt
        elif (self.continuation_source_receipt.get('core_sha256')!=XP2_CORE_SHA256
                or self.continuation_source_receipt.get('source_sha256')!=action_source[1]):
            raise ValueError('XP2 continuation lifetime retained source receipt changed')
        self.action_transport=transport

    def _validate_saved_player_view(self):
        """Validate one completed source-selected UI child under this Load owner."""
        b,p=self.owner,self.prefix
        view=getattr(b,'_xp1_player_view',None);child=getattr(p,'ui_child',None)
        if view is None and child is None:
            if self.player_view is not None or self.ui_child is not None:
                raise ValueError('Saved player view was detached or replaced')
            self.ui_source_dependencies=None
            return None
        if view is None or child is None or view is not self.player_view or child is not self.ui_child:
            raise ValueError('Saved player view and UI child must share their retained owner')
        from .xp1_ui_binding import SavedPlayerView,source_dependencies as ui_source_dependencies
        from .xp1_cache_publication import SavedCachePublication
        expected_publication=(self.completed if type(self.completed) is SavedCachePublication
                              else getattr(self.completed,'publication',None))
        if (type(view) is not SavedPlayerView or view.owner is not b or view.prefix is not p
                or type(expected_publication) is not SavedCachePublication
                or view.publication is not expected_publication or view.runtime is not self.runtime
                or view.child is not child or view.attempted is not True or view.completed is not True
                or view.core_sha256!=b.load_abi.core_sha256):
            raise ValueError('Saved player view is not the completed child owned by this publication')
        if view.core_sha256==XP2_CORE_SHA256:
            from .xp2_ui_binding_source import SOURCE as selected
            flag='_xp2_ui_bind_entered';method_rva='0x5a1db0'
        elif view.core_sha256==XP1_CORE_SHA256:
            from .xp1_ui_binding import SOURCE as selected
            flag='_xp1_ui_bind_entered';method_rva='0x4cbe50'
        else:
            raise ValueError('Saved player view engine is not source-qualified')
        if (view.source_sha256!=selected[1]
                or getattr(self.runtime,flag,False) is not True
                or type(view.result) is not dict
                or view.result.get('core_sha256')!=view.core_sha256
                or view.result.get('source_sha256')!=selected[1]
                or type(view.result.get('binding')) is not dict
                or view.result['binding'].get('native_ui_registration_returned') is not True
                or view.result['binding'].get('method_rva')!=method_rva
                or view.result['binding'].get('source_sha256')!=selected[1]):
            raise ValueError('Saved player view lacks its engine-specific native UI bind receipt')
        game=p.runtime.registry.validate(p.game_child)
        ui=p.runtime.registry.validate(child)
        if game==ui:
            raise ValueError('Saved player view must use a distinct managed UI child')
        dependencies=ui_source_dependencies(view.core_sha256)
        if selected[1] not in dependencies.values():
            raise ValueError('Saved player view source dependency closure omits its selected source')
        if self.ui_source_dependencies is not None and self.ui_source_dependencies!=dependencies:
            raise ValueError('Saved player view source dependencies changed')
        self.ui_source_dependencies=dependencies
        return view

    def _release_saved_player_view(self):
        """Release only the UI child captured by this loaded lifetime token."""
        if self.phase!='lua' or not self.destroy_returned:
            raise ValueError('Saved UI child release requires completed native Destroy')
        self._owned(destroyed=True)
        if self.ui_child is None:
            return False
        if self._validate_saved_player_view() is None:
            raise ValueError('Loaded lifetime refuses an unowned UI child')
        self.runtime.registry.release(self.ui_child)
        self.prefix.ui_child=None
        self.ui_child=None
        self.ui_child_released=True
        self.steps.append('saved_ui_child_released')
        return True

    def _require_raw_services(self):
        p=self.prefix;b=self.owner
        # These optional graphs acquire native facades or install extra routes;
        # they have not been qualified for this raw-Load shutdown family.
        if (any(getattr(p,n,None) is not None for n in ('cache_facades','view_publisher','status_messages',
                'player_queries','ui_child','actions'))
                or any(hasattr(b,n) for n in ('_saved_load_job_cache_owner','_xp1_post160_attempt',
                    '_xp1_publication_attempt','_xp1_continuation','_xp1_player_view'))):
            raise ValueError('Raw XP2 lifetime refuses unqualified cache/postload/UI owners')
        if (p.event_arguments.consumer.player_query_owner is not None
                or p.event_arguments.consumer.controller_owner is not p.control_inputs
                or p.control_inputs._a0_event_owner is not p.event_arguments.consumer):
            raise ValueError('Raw XP2 lifetime controller/A0 ownership differs')

    def _owned(self,*,destroyed=False):
        b=self.owner;p=self.prefix
        if (threading.get_ident()!=self.thread or b.runtime.thread()!=b.thread
                or self.poisoned or b.poisoned or b.destroyed is not destroyed
                or getattr(b,'_loaded_lifetime',None) is not self or b.busy is not True
                or b.prefix is not p or b.core is not self.core or b.host is not self.host
                or b.context!=self.context or b.owner is not self.application
                or p.runtime is not self.runtime or p.game_child is not self.child
                or getattr(b,'_xp1_player_view',None) is not getattr(self,'player_view',None)
                or getattr(p,'ui_child',None) is not getattr(self,'ui_child',None)
                or self.host.execution_lock is not self.lock):
            raise ValueError('Loaded lifetime ownership or thread changed')
        transport=getattr(self,'action_transport',None)
        if transport is not None and (getattr(p,'actions',None) is not transport
                or self.completed is not getattr(b,'_xp1_continuation',None)
                or self.completed.transport is not transport
                or transport.backend is not b or transport.services is not p
                or transport.core is not self.core or transport.context!=self.context):
            raise ValueError('Loaded lifetime command owner changed during shutdown')
        return b

    def check_wrapper_release(self,lease):
        self._owned()
        if (lease is not self.lease or self.phase!='wrappers' or self.unload_called
                or self.owner.stage!='loaded-lifetime-wrappers'):
            raise ValueError('Wrapper release is outside its original loaded owner')

    def check_metadata_scope(self):
        self._owned()
        if self.phase not in ('unload','unloaded','destroy'):
            raise ValueError('Capability lifetime metadata boundary is inactive')
        self.prefix.check();self.application.require_context(self.core._handle,self.context)
        return True

    def check_job_snapshot(self):
        b=self._owned()
        if getattr(self,'player_view',None) is not None or getattr(self,'ui_child',None) is not None:
            self._validate_saved_player_view()
        if self.phase=='wrappers' and b.stage=='loaded-lifetime-wrappers':
            if self.raw_loaded:self._check_raw_alive()
            else:self.lease._check()
        elif self.phase=='unloaded' and b.stage=='loaded-lifetime-unloaded':self._unloaded()
        else:raise ValueError('Job snapshot outside actual lifetime boundary')
        return True

    def _unloaded(self):
        b=self._owned();read=b.runtime.read;base=self.core._handle
        globals_=(0x9f2628,0x9f22e0,0x9f2e58)
        if self.xp2_loaded:globals_=self.proof['contract']['unloaded_zero_global_rvas']
        if (_q(read,self.context)!=base+b.load_abi.outer_vtable_rva
                or _q(read,self.context+8)!=self.inner
                or _q(read,self.inner)!=base+b.load_abi.inner_vtable_rva
                or any(_q(read,address) for address in (self.inner+0x60,self.inner+0x1a68,
                    *(base+rva for rva in globals_)))):
            raise ValueError('Native unload did not clear its actual Game/cache/rules owners')
        if self.xp2_loaded:
            self.prepare_services.verify_callbacks()
            if self.host.archives.entries or self.prefix.contexts.names:
                raise ValueError('Native unload retained archive or script-context owners')
        return dict(game_object_null=True,cache_service_null=True,rules_manager_null=True)

    def before_unload(self,core,context):
        b=self._owned()
        if core is not self.core or context!=self.context or self.phase!='unload' or self.unload_called:
            raise ValueError('Native unload is outside its exact one-shot owner')
        if self.raw_loaded:
            self._check_raw_alive();b.control(empty=True)
        elif (not self.prefix.cache_facades.closed or not self.prefix.view_publisher._closed
                or not self.prefix.status_messages.closed):
            raise ValueError('Native unload requires all real cache wrapper releases')
        self.unload_called=True
        target=0x591860 if self.xp2_loaded else 0x4be690
        self._emit('before_xp1_loaded_unload',source_sha256=self.source_reference[1],target_rva=hex(target))
        return target

    def _emit(self,event,**data):
        if self.xp2_loaded:event=event.replace('xp1_','xp2_',1)
        self.owner.emit(event,**data)

    def after_unload(self):
        if not self.unload_called or self.unload_returned:raise ValueError('Unload return out of order')
        state=self._unloaded();self.unload_returned=True;self.phase='unloaded'
        self.owner.stage='loaded-lifetime-unloaded';self.steps.append('native_unload')
        self.unloaded_state=state

    def before_destroy(self,backend):
        self._unloaded()
        if (backend is not self.owner or self.phase!='destroy' or not self.unload_returned
                or self.destroy_called or self.application.closed
                or self.prefix.closed or self.runtime.closed
                or not(self.runtime.database_bound and self.runtime.configuration_bound and self.runtime.locale_bound)):
            raise ValueError('Destroy requires actual unloaded owner and live borrowed services')
        if getattr(self.host,'context_teardown_receipt',{}).get('installed') is not True:
            raise ValueError('Destroy registrar service is unavailable')
        self.destroy_called=True
        self._emit('before_xp1_loaded_destroy',source_sha256=self.source_reference[1])

    def after_destroy(self,backend):
        self._owned(destroyed=True)
        if backend is not self.owner or not self.destroy_called or self.destroy_returned:
            raise ValueError('Destroy return out of order')
        read=backend.runtime.read;base=self.core._handle
        # Context/Game storage is freed: inspect only pinned module globals.
        globals_=(0x9f2640,0x9f2648,0x9f2650,0x9f2628,0x9f22e0)
        if self.xp2_loaded:globals_=self.proof['contract']['destroyed_zero_global_rvas']
        if any(_q(read,base+rva) for rva in globals_):
            raise ValueError('Destroy did not detach the native host/Game/cache globals')
        if self.xp2_loaded:
            self.prepare_services.verify_callbacks()
            if self.host.types.entries or self.host.archives.entries or self.prefix.contexts.names:
                raise ValueError('Native Destroy retained registered types, archives or scripts')
        self.destroy_returned=True;self.phase='services';self.steps.append('native_destroy')
        self._emit('xp1_loaded_destroy_returned',source_sha256=self.source_reference[1],void_return_ignored=True,
                     context_storage_read_after_destroy=False,native_globals_detached=True)

    def check_a0_owner(self,service):
        if self.phase=='unloaded':
            self._unloaded()
        elif self.phase=='services' and self.destroy_returned:
            self._owned(destroyed=True)
        else:
            raise ValueError('Detached A0 metadata outside completed native teardown')
        if (service is not self.prefix.event_arguments.consumer
                or service.arguments is not self.prefix.event_arguments
                or service.arguments.host is not self.host
                or service.deferred is not self.prefix.deferred_events
                or service.active_kind is not None
                or service.host_notification_counter or service.host_metadata_counter):
            raise ValueError('Detached A0 borrower lacks its exact quiescent lifetime')
        if self.raw_loaded:
            self._require_raw_services()
        else:self._check_player_reference(service.player_query_owner,event_borrower=service)

    def check_a0_release(self,service):
        self.check_a0_owner(service)
        if self.phase!='services' or service.pending or service.deferred._draining_empty_receivers:
            raise ValueError('A0 release requires Destroy and a drained queue')

    def check_a0_consume(self,service,record):
        self.check_a0_owner(service)
        if (self.phase!='unloaded' or not service.deferred._draining_empty_receivers
                or not _unloaded_record(record,service)):
            raise ValueError('Unloaded A0 consumption requires its qualified payload-unread record')

    def check_deferred_drain(self,service):
        self._unloaded()
        if (self.phase!='unloaded' or not self.unload_returned
                or service is not self.prefix.deferred_events
                or service._draining_empty_receivers
                or service.host_notification_counter or service.host_metadata_counter
                or any(not _unloaded_record(r,self.prefix.event_arguments.consumer) for r in service.pending)):
            raise ValueError('Unloaded drain contains an unqualified receiver or cache feedback')
        self.check_a0_owner(self.prefix.event_arguments.consumer)

    def check_player_close(self,service,*,event_borrower=None):
        self._owned(destroyed=True)
        if self.phase!='services' or not self.destroy_returned:
            raise ValueError('Player close requires actual native Destroy')
        self._check_player_reference(service,event_borrower=event_borrower)

    def _check_player_reference(self,service,*,event_borrower):
        # Python-owned metadata only: the Game/cache storage may already be freed.
        if (service is not self.prefix.player_queries
                or service.host is not self.host or service.core is not self.core or service.context!=self.context
                or service.quarantined or service.closed or service.depth or service._a0_event_owner is not event_borrower
                or event_borrower is not None and event_borrower is not self.prefix.event_arguments.consumer
                or threading.get_ident()!=service.thread or self.host._player_notification_owner is not service
                or any(self.host.vtable[s//8]!=v for s,v in service.lock_slots.items())
                or service.core_lock is not self.lock or self.lock.calls['owned']() not in (0,1)):
            raise ValueError('Detached Player query owner still has consumers or changed identity')

    def check_options_cleanup(self,borrower,rva=None):
        b=self._owned(destroyed=True);service=self.host._saved_load_performance_options
        allowed=(None,0x845600,0x844580)
        if self.xp2_loaded:
            from .xp2_load_options_capability_profile import performance_profile
            contract=performance_profile()[1]['contract']
            if service.provider.proof['contract']!=contract:
                raise ValueError('XP2 Performance teardown source differs')
            allowed=(None,contract['slots']['0x68'],contract['destructor_rva'])
        if (self.phase!='options' or not self.destroy_returned or borrower is not service.borrower
                or borrower.backend is not b or borrower.base!=self.core._handle
                or borrower.runtime is not b.runtime or borrower.read!=b.runtime.read
                or service.provider.poisoned or service.provider.closed
                or rva not in allowed):
            raise ValueError('Performance map teardown lacks its detached context owner')
        self.application.require_context(self.core._handle,self.context)

    def close(self):
        from .native.native_host import release_game_services
        from .saved_load_job_observer import require_quiescent
        from .xp1_load_capability import capability_source_scope
        if self.phase!='new':raise ValueError('Loaded lifetime cannot replay')
        b=self.owner;p=self.prefix
        try:
            loaded_notifications_consumed=0
            if self.raw_loaded:
                self.check_completed();b.busy=True
                # CacheUpdate feedback may call Core: consume these actual
                # records while Game is alive, before the unload snapshots.
                self.phase='unload';b.stage='loaded-lifetime-unloading'
                with capability_source_scope(b,'lifetime'):
                    loaded_notifications_consumed=p.deferred_events.drain()
                    b.control(empty=True)
                self.steps.append('loaded_notifications_consumed')
                self._emit('xp1_loaded_notifications_consumed',count=loaded_notifications_consumed,
                           sequence=p.deferred_events._sequence,consumed=p.deferred_events.consumed_count,
                           game_alive=True,post160_called=False,cache_wrappers_present=False)
                p.event_arguments.consumer.enable_district_events()
                self.phase='wrappers';b.stage='loaded-lifetime-wrappers'
            else:
                p.event_arguments.consumer.enable_district_events()
                self.phase='wrappers';self.lease.begin_release(self)
            before=b.jobs_snapshot('before');require_quiescent(before)
            self._emit('before_xp1_loaded_wrapper_release',source_sha256=self.source_reference[1],jobs_before=before)
            if not self.raw_loaded:
                p.cache_facades.close();p.view_publisher.close()
                # C0 owns a third independent A0 reference. Restore its refusal.
                p.status_messages.close()
                self.steps.append('native_cache_wrappers_released')
                self._emit('xp1_loaded_wrappers_released',owners=['prefix.cache_facades','publisher._facades','status.game'],
                       native_release_calls_completed=True,unknown_status_after_release_refused=True)
            self.phase='unload';b.stage='loaded-lifetime-unloading'
            with capability_source_scope(b,'lifetime'):
                release_game_services(self.core,self.context,b.emit,loaded_lifetime=self)
                after=b.jobs_snapshot('after');require_quiescent(after)
                transition=validate_jobs_shutdown(before,after)
                self._emit('xp1_loaded_unload_returned',**self.unloaded_state,source_sha256=self.source_reference[1],
                       void_return_ignored=True,jobs_unloaded=after,jobs_transition=transition)
                notifications_consumed=p.deferred_events.drain(loaded_lifetime=self)
                self._emit('xp1_unloaded_notifications_consumed',count=notifications_consumed,
                       sequence=p.deferred_events._sequence,consumed=p.deferred_events.consumed_count,
                       cache_feedback_executed=False)
                self.phase='destroy';b.stage='loaded-lifetime-destroying'
                b.destroy_context(loaded_lifetime=self)
            p.close();self.steps.append('shared_services_closed')
            self.phase='options'
            options=self.host._saved_load_performance_options.provider.close(context_destroyed=True)
            self.steps.append('native_performance_map_destroyed')
            self.phase='configuration';b.close_owner();self.steps.append('native_configuration_destroyed')
            self.phase='lua';self.runtime.unbind_services()
            ui_released=self._release_saved_player_view()
            self.runtime.registry.release(self.child)
            if ui_released:self.steps.append('game_child_released')
            if self.runtime.registry.contexts or self.runtime.registry._claims:
                raise ValueError('Script contexts remain after official teardown')
            self.runtime.close();self.steps.append('native_lua_closed')
            self.lock.close();self.steps.append('native_core_lock_closed')
            self.phase='database';database_shutdown=b.finish_database()
            if database_shutdown is not True:raise ValueError('Database shutdown did not confirm completion')
            recorder=getattr(b.host,'event_recorder',None)
            if recorder is not None and (not recorder.closed or recorder.setter is not None or recorder.streams):
                raise ValueError('Native event recorder remains active after database shutdown')
            if getattr(self,'action_transport',None) is not None and self.action_transport.closed is not True:
                raise ValueError('Loaded lifetime command transport remains active')
            self.steps.append('database_shutdown')
            self.phase='closed';b.stage='loaded-lifetime-closed';b.busy=False
            self.report=dict(native_unload_called=True,native_destroy_called=True,context_destroyed=True,
                cache_wrappers_released=not self.raw_loaded,services_closed=p.closed,configuration_closed=self.application.closed,
                performance_closed=options,lua_closed=self.runtime.closed,core_lock_closed=True,database_shutdown=database_shutdown,
                jobs_before=before,jobs_unloaded=after,jobs_identical=before==after,steps=list(self.steps),
                jobs_transition=transition,
                unloaded_notifications_consumed=notifications_consumed,
                source_sha256=self.source_reference[1],unknown_host_callbacks_refused=True,public_loaded_lifetime_admitted=False,
                cleanup_inferred_from_process_exit=False)
            if self.ui_child_released or self.xp2_loaded and not self.raw_loaded:
                self.report.update(ui_child_released=self.ui_child_released,
                    ui_child_release_order='after_native_destroy_before_game_child_and_runtime_close'
                        if self.ui_child_released else 'no_ui_child_owned',
                    ui_source_sha256=getattr(self.player_view,'source_sha256',None),
                    ui_source_pin_count=len(self.ui_source_dependencies or {}))
            if recorder is not None:self.report['event_recorder_closed']=True
            if self.raw_loaded:self.report.update(raw_load_only=True,post160_called=False,
                cache_wrappers_present=False,loaded_notifications_consumed=loaded_notifications_consumed)
            elif self.xp2_loaded:self.report.update(raw_load_only=False,post160_called=True,
                cache_wrappers_present=False,postload_candidate_only=getattr(self,'action_transport',None) is None,
                postload_source_pin_count=len(self.postload_source_dependencies))
            if getattr(self,'action_transport',None) is not None:
                self.report.update(continuation_closed=True,command_transport_closed=True,
                    command_source_sha256=self.continuation_source_receipt['source_sha256'],
                    continuation_source_pin_count=len(self.continuation_source_dependencies))
            self._emit('xp1_loaded_lifetime_closed',**self.report)
            return self.report
        except BaseException:
            self.poisoned=True
            if self.lease is not None:self.lease.poison()
            else:b.poisoned=True;p.quarantined=True
            b.stage='poisoned';b.busy=False
            raise

def close_loaded(owner,*,completed):
    return LoadedLifetime(owner,completed).close()

def close_raw_loaded(owner):
    """Close one validated XP2 raw Load; never run Post160/publication/UI."""
    return LoadedLifetime(owner,owner,raw_loaded=True).close()

def require_lifetime(token,owner=None):
    if type(token) is not LoadedLifetime or (owner is not None and token.owner is not owner):
        raise ValueError('Exact loaded lifetime owner required')
    return token

def validate_jobs_shutdown(before,after):
    """Only removal of existing empty slots/groups, requiring parent C ledger."""
    from .saved_load_job_observer import require_quiescent
    require_quiescent(before);require_quiescent(after)
    for key in ('submission_sequence','source_build','core_identity','current_executable',
                'host_sha256','profile','owner_thread_id'):
        if before[key]!=after[key]:raise ValueError('Lifetime scheduler identity/submission changed')
    removed=[]
    for left,right in zip(before['slots'],after['slots'],strict=True):
        if right['occupied'] and not left['occupied']:
            raise ValueError('Loaded cleanup created a job list')
        if right['occupied'] and right!=left:
            raise ValueError('Loaded cleanup changed an occupied job list')
        if left['occupied'] and not right['occupied']:removed.append(left['handle'])
    if any(group not in before['groups'] for group in after['groups']):
        raise ValueError('Loaded cleanup created or mutated an owned job group')
    return dict(snapshot_structural_candidate=True,ledger_reconciled=False,
                removed_empty_handles=removed,removed_owned_empty_groups=len(before['groups'])-len(after['groups']),
                submission_sequence_unchanged=True,identity_unchanged=True,
                post_destroy_snapshot_available=False)
