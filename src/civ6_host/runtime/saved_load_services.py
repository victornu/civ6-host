"""Compose the existing saved-Load Lua services without a NewGame prefix.

This owner borrows an initialized runtime and its native API child. It does not
create a second VM/DB, prepare a Game, choose scripts or admit a saved-game
profile. Deferred Core notifications and gameplay actions remain separate
admission requirements; their absence is never represented by empty queues.
"""
from __future__ import annotations

import ctypes as C
import re

from .configuration_profiles import XP1_CORE_SHA256, XP2_CORE_SHA256
from .configuration_lua_source import verify_xp1 as verify_configuration
from .script_context_source import verify_xp1 as verify_contexts
from .script_event_source import verify_xp1 as verify_events
from .script_context_service import ScriptContextService
from .script_event_service import ScriptEventService
from .script_event_maps import MapArgumentFactory
from .script_scalar_service import ScalarService
from .script_map_service import MapService
from .native.native_official_load import SavedConfigurationReadback
from .explicit_saved_operations import ExplicitSavedOperations


class SavedLoadServices(SavedConfigurationReadback,ExplicitSavedOperations):
    """Single owner for AUX scalars/maps/events/selected-script contexts.

    The caller retains Core, Lua and the execution lock through the relevant
    native lifetime. ``close`` refuses children retained by Core; it does not
    guess whether it is safe to destroy them. Its successful return does not
    authorize destroying a loaded Game without its own shutdown contract.
    """
    def __init__(self, backend, runtime, child, registry, *, core_sha256,
                 script_hashes, bootstrap, saved_map_values, saved_config_sha):
        if (core_sha256 not in (XP1_CORE_SHA256,XP2_CORE_SHA256)
                or backend.configuration_abi.core_sha256 != core_sha256):
            raise ValueError('Saved services require an explicit source-qualified engine')
        runtime.registry.validate(child)
        if (not runtime.database_bound or not runtime.configuration_bound or not runtime.locale_bound
                or getattr(runtime,'service_owner',None) is not backend.host):
            raise ValueError('Saved services must borrow this Core owner and its prepared databases')
        if getattr(backend.host,'_saved_load_services',None) is not None:
            raise ValueError('Saved services already have an owner')
        values=tuple(saved_map_values)
        if (not values or len(values)>8192 or len({r[0] for r in values})!=len(values)
                or any(type(name) is not str or re.fullmatch(r'[A-Za-z_][A-Za-z_0-9]*',name) is None
                       or (value is not None and (type(value) is not int or not -(1<<31)<=value<(1<<31)))
                       for name,value in values)):
            raise ValueError('Invalid saved configuration readback fields')
        if type(saved_config_sha) is not str or re.fullmatch('[0-9a-f]{64}',saved_config_sha) is None:
            raise ValueError('Saved configuration readback requires its exact source hash')
        self.backend,self.host,self.runtime,self.game_child=backend,backend.host,runtime,child
        self.core,self.context=backend.core,backend.context
        self.emit=backend.emit
        self.saved_map_values,self.saved_config_sha=values,saved_config_sha
        self.configuration_readback_verified=False
        self.application_mirror=None
        self.closed=self.quarantined=False
        read=backend.runtime.read
        inner=int.from_bytes(read(self.context+8,8),'little')
        auxiliary=C.addressof(self.host.aux_object)
        self.core_sha256=core_sha256
        if core_sha256==XP2_CORE_SHA256:
            from .xp2_saved_script_services import verify_services
            self.source_receipts=verify_services(backend,runtime,read)
        else:
            self.source_receipts={
                'configuration':verify_configuration(self.core._handle,read),
                'events':verify_events(self.core._handle,read,host_pointer=self.host.pointer,auxiliary_pointer=auxiliary),
                'manager':verify_contexts(self.core._handle,read,inner=inner,auxiliary=auxiliary),
            }
        self.host._saved_load_services=self
        try:
            self.scalars=ScalarService(self.host,runtime)
            options={'allow_nested_maps':True,'allow_event_states':True} if core_sha256==XP2_CORE_SHA256 else {}
            self.maps=MapService(self.host,runtime,self.core,core_sha256=core_sha256,read=read,**options)
            self.map_arguments=MapArgumentFactory(self.core,core_sha256=core_sha256,read=read)
            self.events=ScriptEventService(self.host,runtime,map_factory=self.map_arguments)
            if core_sha256==XP2_CORE_SHA256:
                self.events.install_mutable_map_result(self.core,core_sha256=core_sha256,read=read)
                from .source_build_identity import CURRENT_STRINGS_HOST_REFERENCE
                if self.events.mutable_map_dispatcher.proof['native_host_sha256'] == CURRENT_STRINGS_HOST_REFERENCE[1]:
                    self.events.install_string_arguments(self.core,read=read)
                if bootstrap is None:
                    from .script_context_service import bootstrap_cached_context
                    bootstrap=lambda context_child,name:bootstrap_cached_context(runtime,context_child,name)
            self.contexts=ScriptContextService(self.host,runtime,registry,
                expected_hashes=script_hashes,bootstrap=bootstrap,read=read,
                execution_image=getattr(self.core,'_civ6_host_execution_image',None))
        except BaseException:
            self.quarantined=True
            raise  # Isolated worker owns termination after possible native effects.

    def check(self):
        self.runtime.registry.validate(self.game_child)
        if self.closed or self.quarantined or self.host._saved_load_services is not self:
            raise RuntimeError('Saved services closed, quarantined or replaced')

    def verify_configuration_scalar_marshalling(self):
        self.check()
        try:
            return super().verify_configuration_scalar_marshalling()
        except BaseException:
            self.quarantined=True
            raise

    def attach(self, backend):
        """Install on the existing copy/readback backend, no Game Load admission."""
        self.check()
        if (backend.core is not self.core or backend.host is not self.host or backend.context!=self.context
                or backend.load_abi.core_sha256!=self.backend.configuration_abi.core_sha256
                or backend.stage!='prepared' or backend.prefix is not None
                or self.configuration_readback_verified):
            raise ValueError('Saved services/backend phase or ownership mismatch')
        backend.check_thread()
        if backend.game_flag()!=0:
            raise ValueError('Saved services require an uninitialized prepared Game')
        backend.prefix=self
        backend.stage='prefix-installed'

    def install_application_mirror(self):
        """Retain the native configuration notification path on this owner.

        Deferred event queues and full Load admission are separate. The mirror
        still refuses unqualified notification shapes and observer profiles.
        """
        self.check()
        if self.application_mirror is not None:
            raise ValueError('Saved services application mirror already installed')
        owner=getattr(self.backend,'owner',None)
        if owner is None or getattr(self.host,'application_configuration',None) is not owner:
            raise ValueError('Saved services require their existing application configuration')
        from .native.native_application_mirror import NativePlayerApplicationMirror
        try:
            self.application_mirror=NativePlayerApplicationMirror(self.host,self.core,self.context,
                self.emit,core_sha256=self.backend.configuration_abi.core_sha256)
        except BaseException:
            self.quarantined=True
            raise
        return self.application_mirror

    def install_deferred_events(self,*,optional_preprocessor,queue_metadata_service,limit=4096):
        """Install the shared native feedback queue, without filling other gaps."""
        self.check()
        if hasattr(self,'deferred_events'):
            raise ValueError('Saved services deferred callbacks already installed')
        from .deferred_service import DeferredService
        try:
            self.deferred_events=DeferredService(self.host,self.core,self.context,
                core_sha256=self.backend.configuration_abi.core_sha256,
                read=self.backend.runtime.read,emit=self.emit,limit=limit,
                optional_preprocessor=optional_preprocessor,queue_metadata_service=queue_metadata_service)
        except BaseException:
            self.quarantined=True
            raise
        return self.deferred_events

    def install_postload_aux90_null(self):
        """Bind the engine-selected, source-checked postload category2 service."""
        self.check()
        try:
            self.events.install_postload_aux90_null(self.core, core_sha256=self.core_sha256,
                                                   read=self.backend.runtime.read)
        except BaseException:
            self.quarantined = True
            raise

    def validate_postload_aux90(self):
        """Recheck the actual AUX90 owner and return its immutable source pins."""
        self.check()
        try:
            return self.events.validate_postload_aux90(
                self.core, core_sha256=self.core_sha256, read=self.backend.runtime.read)
        except BaseException:
            self.quarantined = True
            raise

    def close(self):
        self.runtime.registry._check()
        if self.closed:
            return
        self.check()
        if not self.backend.destroyed:
            read=self.backend.runtime.read
            inner=int.from_bytes(read(self.context+8,8),'little')
            game=int.from_bytes(read(inner+0x60,8),'little')
            if self.core_sha256==XP2_CORE_SHA256:
                from .xp2_saved_script_services import require_uninitialized_game
                require_uninitialized_game(self.backend,read,game)
            elif game and read(game+0x2A4,1)!=b'\0':
                raise RuntimeError('Loaded Game teardown still needs its script and borrowed DB services')
        if (self.contexts.names or self.contexts.depth or self.contexts.lock_depth
                or self.contexts.quarantined or self.events.dispatch_depth
                or self.events.script_arguments.live_count or self.map_arguments.live):
            raise RuntimeError('Saved services still have native consumers or retained payloads')
        try:
            if hasattr(self,'actions'):
                self.actions.close()
            if hasattr(self,'status_messages'):
                self.status_messages.close()
            if hasattr(self,'event_arguments'):
                if self.backend.destroyed:
                    from .xp1_loaded_lifetime import require_lifetime
                    token=require_lifetime(getattr(self.backend,'_loaded_lifetime',None),self.backend)
                    self.event_arguments.close(loaded_lifetime=token)
                else:
                    self.event_arguments.close()
            if hasattr(self,'control_inputs'):
                self.control_inputs.close()
            if hasattr(self,'deferred_events'):
                self.deferred_events.close()
            if hasattr(self,'player_queries'):
                if self.backend.destroyed:
                    from .xp1_loaded_lifetime import require_lifetime
                    token=require_lifetime(getattr(self.backend,'_loaded_lifetime',None),self.backend)
                    self.player_queries.close(loaded_lifetime=token)
                else:
                    self.player_queries.close()
            if hasattr(self,'cache_facades'):
                self.cache_facades.close()
            if self.application_mirror is not None:
                self.application_mirror.close()
            self.contexts.close()
            if hasattr(self, 'bbg_property_tables'):
                self.bbg_property_tables.close()
            self.events.close()
            self.map_arguments.close()
            self.maps.close()
            self.scalars.close()
        except BaseException:
            self.quarantined=True
            raise
        self.host._saved_load_services=None
        self.closed=True

    def install_control_inputs(self,*,local_player_id):
        """Bind an explicit host identity and the original controller getter.

        Requires the same deferred owner used by later turn-event consumers;
        this creates no action scheduler or full saved-Game admission.
        """
        self.check()
        if hasattr(self,'control_inputs') or not hasattr(self,'deferred_events'):
            raise ValueError('Control inputs require one existing deferred owner')
        from .control_input_service import ControlInputService
        try:
            self.control_inputs=ControlInputService(self.host,self.core,self.context,self.deferred_events,
                core_sha256=self.backend.configuration_abi.core_sha256,local_player_id=local_player_id,
                read=self.backend.runtime.read,emit=self.emit)
        except BaseException:
            self.quarantined=True
            raise
        return self.control_inputs

    def install_cache_facades(self):
        """Retain the shared native factory/copy/release pipeline, no publication."""
        self.check()
        if hasattr(self,'cache_facades'):
            raise ValueError('Saved services cache facades already installed')
        from .cache_facade_service import CacheFacadeService
        try:
            self.cache_facades=CacheFacadeService(self.core,self.context,
                core_sha256=self.backend.configuration_abi.core_sha256,read=self.backend.runtime.read,
                context_alive=lambda:not self.closed and not self.quarantined and not self.backend.destroyed)
        except BaseException:
            self.quarantined=True
            raise
        return self.cache_facades

    def install_player_queries(self,*,core_lock):
        """Reuse the native Player/component lease with this owner's lock."""
        self.check()
        if hasattr(self,'player_queries'):
            raise ValueError('Saved services Player queries already installed')
        from .player_notification_service import PlayerNotificationService
        try:
            self.player_queries=PlayerNotificationService(self.host,self.core,self.context,
                core_sha256=self.backend.configuration_abi.core_sha256,read=self.backend.runtime.read,
                context_alive=lambda:not self.closed and not self.quarantined and not self.backend.destroyed,
                core_lock=core_lock)
        except BaseException:
            self.quarantined=True
            raise
        return self.player_queries

    def install_event_arguments(self,*,normalizer_transform,dynamic_registrations):
        """Share the XP1 borrowed-map reader with source-qualified A0 consumers."""
        self.check()
        if hasattr(self,'event_arguments') or not hasattr(self,'deferred_events'):
            raise ValueError('Event arguments require one existing deferred owner')
        from .event_argument_service import EventArgumentService
        try:
            self.event_arguments=EventArgumentService(self.host,self.core,self.context,self.deferred_events,
                core_sha256=self.backend.configuration_abi.core_sha256,read=self.backend.runtime.read,
                emit=self.emit,normalizer_transform=normalizer_transform,
                dynamic_registrations=dynamic_registrations)
        except BaseException:
            self.quarantined=True
            raise
        return self.event_arguments

    def install_status_messages(self,*,receiver_state,writer_metadata_service,per_thread_hook):
        """Borrow the shared argument reader/queue and acquire the real Game facade."""
        self.check()
        if hasattr(self,'status_messages') or not hasattr(self,'event_arguments'):
            raise ValueError('Status messages require one existing event argument owner')
        from .status_message_service import StatusMessageService
        try:
            self.status_messages=StatusMessageService(self.host,self.core,self.context,self.event_arguments,
                core_sha256=self.backend.configuration_abi.core_sha256,read=self.backend.runtime.read,emit=self.emit,
                context_alive=lambda:not self.closed and not self.quarantined and not self.backend.destroyed,
                receiver_state=receiver_state,writer_metadata_service=writer_metadata_service,per_thread_hook=per_thread_hook)
        except BaseException:
            self.quarantined=True
            raise
        return self.status_messages
