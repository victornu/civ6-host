"""Reuse source-qualified engine-independent A0 codecs and their existing FIFO.

The shared dispatcher still contains native-query families for Base. Core and
context are borrowed only during an explicitly profiled XP1 foundation callback;
unqualified keys are refused before dispatch. No native query is simplified.
"""
from __future__ import annotations
import struct
from types import MappingProxyType
from .configuration_profiles import XP2_CORE_SHA256
from .native.native_host_events import SharedHostEventDispatch
from .native.native_deferred_empty_profile import validate_empty_profile_record
from .native.native_victory_notifications import EVENT_SPECS, RECORD_SIZE as VICTORY_RECORD_SIZE
from .a0_xp2_victory_source import verify_xp2_producer

class A0FamilyService(SharedHostEventDispatch):

    def __init__(self, arguments, *, receiver_state, pre_turn_immediate_state, entity_listener_count):
        arguments._check()
        if getattr(arguments, 'consumer', None) is not None or getattr(arguments.host, '_a0_family_owner', None) is not None:
            raise ValueError('A0 family owner already installed')
        if type(receiver_state) is not dict or type(pre_turn_immediate_state) is not dict or type(entity_listener_count) is not int or (entity_listener_count != 0):
            raise ValueError('A0 reuse requires an explicit source-qualified receiver/listener profile')
        from .a0_family_source import family_profile
        self.profile = family_profile()
        for kind, size in self.profile.record_sizes.items():
            record = bytearray(size)
            struct.pack_into('<II', record, 0, size, kind)
            validate_empty_profile_record(record, **receiver_state)
            if kind == 3:
                validate_empty_profile_record(record, **pre_turn_immediate_state)
        self.arguments, self.deferred = (arguments, arguments.deferred)
        self.read, self.emit = (arguments.reader.read, arguments.emit)
        self.empty_receiver_state = dict(receiver_state)
        self.entity_listener_count = entity_listener_count
        self.pre_turn_immediate_state = dict(pre_turn_immediate_state)
        self._receiver_profile = dict(receiver_state)
        self._immediate_profile = dict(pre_turn_immediate_state)
        self.closed = self.quarantined = False
        self.active_kind = None
        from .native.native_absent_unit_scalar_family import REGISTRY_PROFILE
        self.callback_registry_profile = REGISTRY_PROFILE
        self._registry_profile = REGISTRY_PROFILE
        self.dynamic_event_registration_present = False
        self.normalizer_transform_present = False
        # This owner installs neither optional EXE presentation producer hook
        # nor writer metadata service. Keep the owned absence explicit and
        # immutable; codecs must not substitute a caller-supplied literal.
        self.per_thread_hook_present = False
        self.writer_metadata_callback_present = False
        self.controller_profile = self.controller_owner = None
        self.player_query_profile = self.player_query_owner = None
        self.notification_scope_profile = self._notification_scope_profile = None
        self._active_notification_scope = None
        self.unregistered_player_events = []
        self._city_command_started_producing = self._city_command_started_poisoned = False
        self._84c1fdd6_producing = self._84c1fdd6_poisoned = False
        # Shared F26 scoped producer copies its descriptor before publishing.
        # Keep its existing guard on the same owned A0 lifetime as the FIFO.
        self._found_city_producing = self._found_city_poisoned = False
        arguments.host._a0_family_owner = self
        self.publication_event_profile = self._publication_event_profile = None
        self.district_event_profile = self._district_event_profile = None
        self.found_unit_event_profile = self._found_unit_event_profile = None
        self.foundation_event_profile = self._foundation_event_profile = None
        self.history_event_profile = self._history_event_profile = None
        self.climate_event_profile = self._climate_event_profile = None
        self._climate_records = {}
        self.presentation_sources = self._presentation_sources = MappingProxyType({})
        self._foundation_backend = self._foundation_borrow = None
        self.city_scalar_event_profile = self._city_scalar_event_profile = None
        self._city_scalar_records = None
        self.private_notification_profile = self._private_notification_profile = None
        self._private_notification_binding = None
        self.turn_unit_event_profile = self._turn_unit_event_profile = None
        self.placement_event_profile = self._placement_event_profile = None
        self.combat_event_profile = self._combat_event_profile = None
        self.improvement_change_profile = self._improvement_change_profile = None
        self.district_damage_profile = self._district_damage_profile = None
        self.natural_wonder_event_profile = self._natural_wonder_event_profile = None

    @property
    def pending(self):
        return self.deferred.pending

    @property
    def _sequence(self):
        return self.deferred._sequence

    @property
    def limit(self):
        return self.deferred.limit

    @property
    def host_notification_counter(self):
        return self.deferred.host_notification_counter

    @property
    def host_metadata_counter(self):
        return self.deferred.host_metadata_counter

    @host_metadata_counter.setter
    def host_metadata_counter(self, value):
        from .a0_foundation_events import require_borrow
        require_borrow(self)
        if type(value) is not int or not 0 <= value <= 0xFFFFFFFF:
            raise ValueError('Foundation metadata counter must remain uint32')
        self.deferred.host_metadata_counter = value

    @property
    def core(self):
        from .a0_foundation_events import require_borrow
        return require_borrow(self).owner.core

    @property
    def base(self):
        from .a0_foundation_events import require_borrow
        return require_borrow(self).owner.core._handle

    @property
    def context(self):
        from .a0_foundation_events import require_borrow
        return require_borrow(self).owner.context

    @property
    def host(self):
        from .a0_foundation_events import require_borrow
        return require_borrow(self).owner.host

    @property
    def foundation_core_sha256(self):
        from .a0_foundation_events import require_borrow
        return require_borrow(self).owner.load_abi.core_sha256

    @property
    def turn_unit_core_sha256(self):
        from .a0_foundation_events import require_borrow
        return require_borrow(self).owner.load_abi.core_sha256

    @property
    def turn_unit_backend(self):
        from .a0_foundation_events import require_borrow
        return require_borrow(self).owner

    @property
    def placement_core_sha256(self):
        from .a0_foundation_events import require_borrow
        return require_borrow(self).owner.load_abi.core_sha256

    @property
    def combat_core_sha256(self):
        from .a0_foundation_events import require_borrow
        return require_borrow(self).owner.load_abi.core_sha256

    @property
    def district_damage_core_sha256(self):
        from .a0_foundation_events import require_borrow
        return require_borrow(self).owner.load_abi.core_sha256

    @property
    def improvement_core_sha256(self):
        from .a0_foundation_events import require_borrow
        return require_borrow(self).owner.load_abi.core_sha256

    @property
    def combat_map_registry(self):
        return self.deferred.combat_map_registry

    @combat_map_registry.setter
    def combat_map_registry(self,value):
        from .a0_foundation_events import require_borrow
        from .configuration_profiles import XP1_CORE_SHA256,XP2_CORE_SHA256
        from .native.native_combat_map_owner import CombatMapRegistry
        token=require_borrow(self)
        core_sha256=token.owner.load_abi.core_sha256
        if (self.deferred.combat_map_registry is not None or type(value) is not CombatMapRegistry
                or core_sha256 not in (XP1_CORE_SHA256,XP2_CORE_SHA256)
                or value.core_sha256!=core_sha256):
            raise ValueError('Combat registry replacement or foreign engine')
        self.deferred.combat_map_registry=value

    @property
    def next_node(self):
        from .a0_foundation_events import require_borrow
        require_borrow(self)
        return self.arguments.reader.next_node

    @property
    def retained_combat_predicate(self):
        from .a0_combat_events import predicate
        return lambda signed_owner:predicate(self,signed_owner)

    @property
    def ui_cache_map_snapshot(self):
        from .xp1_world_text_profile import cache_snapshot
        return cache_snapshot(self)

    @property
    def ui_cache_callbacks_enabled(self):
        from .a0_foundation_events import require_borrow
        from .xp1_visibility_cache_gate import require_internal_cache
        return require_internal_cache(require_borrow(self))['callback_gate_enabled']

    def _check(self, *, loaded_lifetime=None):
        self.arguments._check()
        if self.closed or self.quarantined or self._found_city_poisoned or self.arguments.host._a0_family_owner is not self:
            raise RuntimeError('A0 family owner closed, poisoned or replaced')
        if loaded_lifetime is not None:
            from .xp1_loaded_lifetime import require_lifetime
            require_lifetime(loaded_lifetime).check_a0_owner(self)
        if self.empty_receiver_state != self._receiver_profile or self.pre_turn_immediate_state != self._immediate_profile or type(self.entity_listener_count) is not int or (self.entity_listener_count != 0) or (self.callback_registry_profile != self._registry_profile) or (self.dynamic_event_registration_present is not False) or (self.normalizer_transform_present is not False) or any((type(self.empty_receiver_state[k]) is not type(v) for k, v in self._receiver_profile.items())) or any((type(self.pre_turn_immediate_state[k]) is not type(v) for k, v in self._immediate_profile.items())):
            raise RuntimeError('A0 receiver or registration profile changed')
        if self.per_thread_hook_present is not False or self.writer_metadata_callback_present is not False:
            raise RuntimeError('A0 optional presentation producer hooks changed')
        from .empty_presentation_events import check_registry
        check_registry(self)
        if self.notification_scope_profile is not self._notification_scope_profile:
            raise RuntimeError('A0 notification scope profile replaced')
        if self.controller_owner is not None:
            self.controller_owner._check()
            if self.controller_owner._a0_event_owner is not self or self.turn_begin_state is not self.controller_owner.turn_begin_state:
                raise RuntimeError('A0 controller state or owner replaced')
        if self.player_query_owner is not None:
            if loaded_lifetime is None:
                self.player_query_owner.check()
            if self.player_query_owner._a0_event_owner is not self:
                raise RuntimeError('A0 Player query borrower changed')
        if self.publication_event_profile is not self._publication_event_profile:
            raise RuntimeError('A0 publication event profile replaced')
        if self.district_event_profile is not self._district_event_profile:
            raise RuntimeError('A0 district event profile replaced')
        if self.found_unit_event_profile is not self._found_unit_event_profile:
            raise RuntimeError('A0 unit activity event profile replaced')
        if self.foundation_event_profile is not self._foundation_event_profile:
            raise RuntimeError('A0 foundation event profile replaced')
        if self.history_event_profile is not self._history_event_profile:
            raise RuntimeError('A0 history event profile replaced')
        if self.climate_event_profile is not self._climate_event_profile:
            raise RuntimeError('A0 climate event profile replaced')
        if self.city_scalar_event_profile is not self._city_scalar_event_profile:
            raise RuntimeError('A0 city/scalar event profile replaced')
        if self.private_notification_profile is not self._private_notification_profile:
            raise RuntimeError('A0 private notification profile replaced')
        if self.turn_unit_event_profile is not self._turn_unit_event_profile:
            raise RuntimeError('A0 turn unit event profile replaced')
        if self.placement_event_profile is not self._placement_event_profile:
            raise RuntimeError('A0 placement event profile replaced')
        if self.combat_event_profile is not self._combat_event_profile:
            raise RuntimeError('A0 combat event profile replaced')
        if self.improvement_change_profile is not self._improvement_change_profile:
            raise RuntimeError('A0 improvement/route event profile replaced')
        if self.natural_wonder_event_profile is not self._natural_wonder_event_profile:
            raise RuntimeError('A0 natural-wonder event profile replaced')
        if self.district_damage_profile is not self._district_damage_profile:
            raise RuntimeError('A0 district damage/combat event profile replaced')

    def handles_kind(self, kind):
        if self.natural_wonder_event_profile is not None and kind in self.natural_wonder_event_profile.record_types_by_kind:
            return True
        if kind in self.presentation_sources:
            return True
        if self.climate_event_profile is not None and kind in self.climate_event_profile.record_types_by_kind:
            return True
        if self.history_event_profile is not None and kind in self.history_event_profile.record_types_by_kind:
            return True
        if self.district_damage_profile is not None and kind in self.district_damage_profile.record_types_by_kind:
            return True
        if self.improvement_change_profile is not None and kind in self.improvement_change_profile.record_types_by_kind:
            return True
        if self.combat_event_profile is not None and kind in self.combat_event_profile.record_types_by_kind:
            return True
        if self.placement_event_profile is not None and kind in self.placement_event_profile.record_types_by_kind:
            return True
        if self.turn_unit_event_profile is not None and kind in self.turn_unit_event_profile.record_types_by_kind:
            return True
        if self.private_notification_profile is not None and kind in self.private_notification_profile.record_types_by_kind:
            return True
        if self.city_scalar_event_profile is not None and kind in self.city_scalar_event_profile.record_types_by_kind:
            return True
        if self.foundation_event_profile is not None and kind in self.foundation_event_profile.record_types_by_kind:
            return True
        if self.found_unit_event_profile is not None and kind in self.found_unit_event_profile.record_types_by_kind:
            return True
        return ((kind in self.profile.record_types_by_kind or (self.controller_profile is not None and kind in self.controller_profile.record_types_by_kind) or (self.player_query_profile is not None and kind in self.player_query_profile.record_types_by_kind)) or (self.publication_event_profile is not None and kind in self.publication_event_profile.record_types_by_kind)) or (self.district_event_profile is not None and kind in self.district_event_profile.record_types_by_kind)

    def handles_record(self, kind):
        if self.natural_wonder_event_profile is not None and kind in self.natural_wonder_event_profile.record_sizes:
            return True
        if self.climate_event_profile is not None and kind in self.climate_event_profile.record_sizes:
            return True
        if self.history_event_profile is not None and kind in self.history_event_profile.record_sizes:
            return True
        if self.district_damage_profile is not None and kind in self.district_damage_profile.record_sizes:
            return True
        if self.improvement_change_profile is not None and kind in self.improvement_change_profile.record_sizes:
            return True
        if self.combat_event_profile is not None and kind in self.combat_event_profile.record_sizes:
            return True
        if self.placement_event_profile is not None and kind in self.placement_event_profile.record_sizes:
            return True
        if self.turn_unit_event_profile is not None and kind in self.turn_unit_event_profile.record_sizes:
            return True
        if self.private_notification_profile is not None and kind in self.private_notification_profile.record_sizes:
            return True
        if self.city_scalar_event_profile is not None and kind in self.city_scalar_event_profile.record_sizes:
            return True
        if self.foundation_event_profile is not None and kind in self.foundation_event_profile.record_sizes:
            return True
        if self.found_unit_event_profile is not None and kind in self.found_unit_event_profile.record_sizes:
            return True
        return ((kind in self.profile.record_sizes or (self.controller_profile is not None and kind in self.controller_profile.record_sizes) or (self.player_query_profile is not None and kind in self.player_query_profile.record_sizes)) or (self.publication_event_profile is not None and kind in self.publication_event_profile.record_sizes)) or (self.district_event_profile is not None and kind in self.district_event_profile.record_sizes)

    def enable_player_queries(self, owner):
        """Borrow a source-qualified Player lease; preserve enqueue-before-release."""
        self._check()
        from .player_notification_service import PlayerNotificationService
        if type(owner) is not PlayerNotificationService or self.player_query_owner is not None or owner.host is not self.arguments.host or (owner.core is not self.deferred.core) or (owner.context != self.deferred.context) or (owner._a0_event_owner is not None) or self.arguments.depth or (self.active_kind is not None) or self.pending or self.deferred._draining_empty_receivers:
            raise ValueError('A0 Player queries require one unborrowed owner of the same idle context')
        owner.check()
        if owner.core_sha256 != self.deferred.cache_core_sha256:
            raise ValueError('A0 Player query engine differs from its shared owner')
        from .player_notification_profiles import event_profile
        profile = event_profile(core_sha256=owner.core_sha256)
        if set(profile.record_types_by_kind) & set(self.profile.record_types_by_kind):
            raise ValueError('Player query overlaps the pure A0 families')
        for kind, size in profile.record_sizes.items():
            record = bytearray(size)
            struct.pack_into('<II', record, 0, size, kind)
            validate_empty_profile_record(record, **self.empty_receiver_state)
        self.player_query_profile, self.player_query_owner = (profile, owner)
        owner._a0_event_owner = self
        return self

    def _query_player_notification_values(self, player):
        if self.player_query_owner is None:
            raise RuntimeError('Player query owner is not installed')
        return self.player_query_owner.query(player)

    def enable_controller_events(self, control):
        """Borrow the existing controller; installation creates/resets no state."""
        self._check()
        from .control_input_service import ControlInputService
        if type(control) is not ControlInputService or self.controller_owner is not None or control.host is not self.arguments.host or (control.deferred is not self.deferred) or (getattr(control, '_a0_event_owner', None) is not None) or self.arguments.depth or (self.active_kind is not None) or self.pending or self.deferred._draining_empty_receivers:
            raise ValueError('A0 controller must be an unborrowed owner of this idle service')
        control._check()
        from .a0_controller_source import controller_profile
        profile = controller_profile()
        if set(profile.record_types_by_kind) & set(self.profile.record_types_by_kind):
            raise ValueError('A0 controller keys overlap the independent family profile')
        for kind, size in profile.record_sizes.items():
            record = bytearray(size)
            struct.pack_into('<II', record, 0, size, kind)
            validate_empty_profile_record(record, **self.empty_receiver_state)
        self.controller_profile, self.controller_owner = (profile, control)
        self.turn_begin_state = control.turn_begin_state
        control._a0_event_owner = self
        return self

    def enable_notification_scopes(self):
        """Opt into source-qualified counter-independent paths on one idle owner."""
        self._check()
        self._require_no_f391_reentry()
        if self.notification_scope_profile is not None or self.arguments.depth or self.active_kind is not None or self.pending or self.deferred._draining_empty_receivers or (type(self.host_notification_counter) is not int) or (self.host_notification_counter != 0) or (type(self.host_metadata_counter) is not int) or (self.host_metadata_counter != 0):
            raise ValueError('A0 notification scopes require one idle owner and closed counters')
        from .a0_notification_scope_source import notification_scope_profile
        profile = notification_scope_profile()
        for record_type, size, _ in profile.records.values():
            record = bytearray(size)
            struct.pack_into('<II', record, 0, size, record_type)
            validate_empty_profile_record(record, **self.empty_receiver_state)
        self.notification_scope_profile = self._notification_scope_profile = profile
        return self

    def dispatch(self, kind, fields, borrowed_argument):
        self._check()
        if not self.handles_kind(kind):
            raise ValueError('A0 native-query or unknown family is not admitted')
        if self.active_kind is not None:
            raise RuntimeError('Reentrant A0 family production is unqualified')
        n, m = (self.host_notification_counter, self.host_metadata_counter)
        if any((type(value) is not int or not 0 <= value <= 4294967295 for value in (n, m))):
            raise ValueError('A0 notification counters must be exact uint32 values')
        scope = None
        natural_wonder = self.natural_wonder_event_profile is not None and kind in self.natural_wonder_event_profile.record_types_by_kind
        foundation = self.foundation_event_profile is not None and kind in self.foundation_event_profile.record_types_by_kind
        turn_unit = self.turn_unit_event_profile is not None and kind in self.turn_unit_event_profile.record_types_by_kind
        placement = self.placement_event_profile is not None and kind in self.placement_event_profile.record_types_by_kind
        combat = self.combat_event_profile is not None and kind in self.combat_event_profile.record_types_by_kind
        improvement_change = self.improvement_change_profile is not None and kind in self.improvement_change_profile.record_types_by_kind
        district_damage = self.district_damage_profile is not None and kind in self.district_damage_profile.record_types_by_kind
        history = self.history_event_profile is not None and kind in self.history_event_profile.record_types_by_kind
        climate = self.climate_event_profile is not None and kind in self.climate_event_profile.record_types_by_kind
        city_scalar = self.city_scalar_event_profile is not None and kind in self.city_scalar_event_profile.record_types_by_kind
        private = self.private_notification_profile is not None and kind in self.private_notification_profile.record_types_by_kind
        presentation = kind in self.presentation_sources
        xp2_victory = self.deferred.cache_core_sha256 == XP2_CORE_SHA256 and kind in EVENT_SPECS
        from .a0_district_damage import is_xp2_sibling
        district_sibling = is_xp2_sibling(self,kind,fields)
        if (n or m) and not foundation and not history and not climate and not turn_unit and not placement and not combat and not city_scalar and not private and not presentation and not district_sibling and not natural_wonder:
            if xp2_victory:
                expected = (EVENT_SPECS[kind].record_type, VICTORY_RECORD_SIZE, 6)
            else:
                profile = self.notification_scope_profile
                if profile is None or kind not in profile.records:
                    raise ValueError('A0 family notification scope requires separate source admission')
                from .a0_notification_scope_source import require_scope_fields
                require_scope_fields(kind, fields)
                expected = profile.records[kind]
            if len(self.pending) >= self.limit:
                raise RuntimeError('Native deferred queue bound exceeded')
            if type(self._sequence) is not int or not 0 <= self._sequence < 2147483647:
                raise ValueError('A0 notification sequence exhausted')
            scope = (n, m, self._sequence, len(self.pending), expected)
        self.active_kind = kind
        self._active_notification_scope = scope
        try:
            if xp2_victory:
                verify_xp2_producer(kind, self.deferred.core._handle, self.read)
                if scope is None:
                    result = self._dispatch_fields(kind, fields)
                else:
                    result = self._enqueue_scoped_victory(kind, fields)
            elif natural_wonder:
                from .a0_natural_wonder import dispatch
                result=dispatch(self,kind,fields,borrowed_argument)
            elif presentation:
                from .empty_presentation_events import dispatch
                result = dispatch(self, kind, fields)
            elif climate:
                from .a0_xp2_turn_events import dispatch
                result = dispatch(self, kind, fields)
            elif private:
                from .a0_private_notifications import dispatch
                result = dispatch(self, kind, fields)
            elif city_scalar:
                from .a0_city_scalar_events import dispatch
                result = dispatch(self, kind, fields)
            elif history:
                from .a0_foundation_events import dispatch_history
                result=dispatch_history(self,kind,fields)
            elif foundation or turn_unit or placement or combat or improvement_change or district_damage:
                from .a0_foundation_events import dispatch
                result = dispatch(self, kind, fields, borrowed_argument)
            elif self.found_unit_event_profile is not None and kind in self.found_unit_event_profile.record_types_by_kind:
                from .a0_found_unit_event import dispatch
                result=dispatch(self,kind,fields)
            elif district_sibling:
                from .a0_district_damage import dispatch_sibling
                result=dispatch_sibling(self,fields,borrowed_argument)
            else:
                result = self._dispatch_publication_event(kind, fields) if self.publication_event_profile is not None and kind in self.publication_event_profile.record_types_by_kind else self._dispatch_district_event(kind, fields) if self.district_event_profile is not None and kind in self.district_event_profile.record_types_by_kind else self._dispatch_fields(kind, fields, borrowed_argument=borrowed_argument)
            if scope is not None:
                n, m, sequence, count, _ = scope
                if (self.host_notification_counter, self.host_metadata_counter, self._sequence, len(self.pending)) != (n, m, sequence + 1, count + 1):
                    raise RuntimeError('Counter-independent A0 dispatch changed its scope or FIFO')
            return result
        except BaseException:
            self.quarantined = True
            if self.controller_profile is not None and kind in self.controller_profile.record_types_by_kind:
                self.controller_owner.quarantined = True
            if self.player_query_profile is not None and kind in self.player_query_profile.record_types_by_kind:
                self.player_query_owner.quarantined = True
            raise
        finally:
            self.active_kind = None
            self._active_notification_scope = None

    def _enqueue_scoped_victory(self, kind, fields):
        from .native.native_victory_notifications import decode_fields, encode_record

        spec = EVENT_SPECS[kind]
        codec_state = dict(profile=spec.empty_receiver_profile, record_type=spec.record_type,
            event_name='GameCoreEvent::' + spec.name, pre_hook=None, post_hook=None,
            subscriber_count=0, subscriber_list_empty=True, deferred_flag=0)
        record = encode_record(self._sequence + 1, decode_fields(kind, fields),
            normalizer_transform_present=self.normalizer_transform_present,
            thread_hook_present=self.per_thread_hook_present,
            writer_metadata_callback_present=self.writer_metadata_callback_present,
            empty_receiver_state=codec_state)
        self._enqueue(record)
        self.emit('xp2_scoped_victory_notification_enqueued', dispatch_kind=hex(kind),
                  queue_type=hex(spec.record_type), sequence=self._sequence,
                  payload_exposed_to_learner=False)
        return 0

    def _enqueue(self, record):
        if self.active_kind is None:
            raise RuntimeError('A0 record produced outside an explicit dispatch')
        kind = int.from_bytes(record[4:8], 'little')
        profile = next((p for p in (self.climate_event_profile, self.history_event_profile, self.profile, self.controller_profile, self.player_query_profile, self.publication_event_profile, self.district_event_profile, self.found_unit_event_profile, self.foundation_event_profile, self.city_scalar_event_profile, self.private_notification_profile, self.turn_unit_event_profile, self.placement_event_profile,self.combat_event_profile,self.improvement_change_profile,self.district_damage_profile,self.natural_wonder_event_profile) if p is not None and self.active_kind in p.record_types_by_kind), None)
        if profile is None or kind not in profile.record_types_by_kind[self.active_kind]:
            raise ValueError('A0 codec produced a record outside its source-qualified family')
        if kind==248 and profile is self.combat_event_profile:
            from .a0_combat_events import validate_enqueue
            validate_enqueue(self,record)
        else:
            validate_empty_profile_record(record, **self.empty_receiver_state)
        if self._active_notification_scope is not None:
            n, m, sequence, count, expected = self._active_notification_scope
            record_type, size, flag = expected
            if (self.host_notification_counter, self.host_metadata_counter, self._sequence, len(self.pending)) != (n, m, sequence, count):
                raise RuntimeError('Counter-independent A0 scope changed before enqueue')
            if len(record) != size or kind != record_type or struct.unpack_from('<I', record, 72)[0] != flag:
                raise RuntimeError('Counter-independent A0 record metadata differs')
        return self.deferred._enqueue(record)

    def _enqueue_combat(self, fields, borrowed_argument):
        from .native.native_host_events import NativeDeferredHostEvents
        return NativeDeferredHostEvents._enqueue_combat(self, fields, borrowed_argument)

    def _enqueue_experience(self, fields):
        from .native.native_host_events import NativeDeferredHostEvents
        return NativeDeferredHostEvents._enqueue_experience(self, fields)

    def _enqueue_district_damage_changed(self, fields):
        from .a0_district_damage import invoke
        return invoke(self,'damage',fields)

    def _enqueue_district_combat_changed(self, fields):
        from .a0_district_damage import invoke
        return invoke(self,'combat',fields)

    def consume(self, record, sequence, *, loaded_lifetime=None):
        self._check(loaded_lifetime=loaded_lifetime)
        if loaded_lifetime is not None:
            loaded_lifetime.check_a0_consume(self, record)
        if self.active_kind is not None or not self.handles_record(int.from_bytes(record[4:8], 'little')):
            raise ValueError('A0 record consumer is active or unqualified')
        if self.climate_event_profile is not None and int.from_bytes(record[4:8], 'little') in self.climate_event_profile.record_sizes:
            from .a0_xp2_turn_events import consume
            return consume(self, record, sequence)
        self.deferred._consume_empty_record(record, sequence, empty_receiver_state=self.empty_receiver_state)

    def close(self, *, loaded_lifetime=None):
        if self.closed:
            return
        self._check(loaded_lifetime=loaded_lifetime)
        self._require_no_f391_reentry()
        if getattr(self,'_36c9_producing',False) or getattr(self,'_36c9_poisoned',False):
            raise RuntimeError('Natural-wonder producer active or poisoned')
        if loaded_lifetime is not None:
            loaded_lifetime.check_a0_release(self)
        if self.active_kind is not None or self.pending or self.deferred._draining_empty_receivers:
            raise RuntimeError('A0 family owner still has active consumers')
        if self._climate_records:
            raise RuntimeError('A0 climate records still own presentation storage')
        if self.private_notification_profile is not None:
            from .a0_private_notifications import check_close
            check_close(self)
        if self.controller_owner is not None:
            self.controller_owner._a0_event_owner = None
            del self.turn_begin_state
        if self.player_query_owner is not None:
            self.player_query_owner._a0_event_owner = None
        self.arguments.host._a0_family_owner = None
        self.closed = True

    def enable_private_notifications(self):
        from .a0_private_notifications import enable
        return enable(self)

    def _private_ring(self):
        from .a0_private_notifications import get_ring
        return get_ring(self)

    def enable_publication_events(self, publication):
        from .a0_emergencies_updated import enable
        return enable(self, publication)

    def _dispatch_publication_event(self, kind, fields):
        from .a0_emergencies_updated import dispatch
        return dispatch(self, kind, fields)

    def enable_district_events(self):
        self._check()
        if self.district_event_profile is not None or self.arguments.depth or self.active_kind is not None or self.pending or self.deferred._draining_empty_receivers or self.host_notification_counter or self.host_metadata_counter:
            raise ValueError('District events require one idle owner with closed notification scopes')
        from .a0_district_removed import event_profile, verify_live
        profile = event_profile(core_sha256=self.deferred.cache_core_sha256)
        verify_live(self.deferred.core._handle, self.deferred.context, self.read, core_sha256=self.deferred.cache_core_sha256)
        for kind, size in profile.record_sizes.items():
            record = bytearray(size)
            struct.pack_into('<II', record, 0, size, kind)
            validate_empty_profile_record(record, **self.empty_receiver_state)
        if any((self.handles_kind(kind) for kind in profile.record_types_by_kind)):
            raise ValueError('District event overlaps another installed A0 family')
        self.district_event_profile = self._district_event_profile = profile
        return self

    def _dispatch_district_event(self, kind, fields):
        from .a0_district_removed import dispatch
        return dispatch(self, kind, fields)

    def _enqueue_project_completion(self, fields):
        from .configuration_profiles import XP2_CORE_SHA256
        if self.deferred.cache_core_sha256 == XP2_CORE_SHA256:
            from .a0_foundation_events import dispatch_project_completion
            return dispatch_project_completion(self, fields)
        raise ValueError('XP1 project-completion extra effects require their own native profile')

    def _enqueue_e660_building_pillaged(self, fields):
        from .configuration_profiles import XP2_CORE_SHA256
        if self.deferred.cache_core_sha256 == XP2_CORE_SHA256:
            from .a0_foundation_events import dispatch_building_pillage
            return dispatch_building_pillage(self, fields)
        raise ValueError('XP1 building-pillage extra effects require their own native profile')

    def _enqueue_wonder_completion(self, *args):
        from .configuration_profiles import XP2_CORE_SHA256
        if self.foundation_core_sha256 == XP2_CORE_SHA256:
            from .xp2_wonder_completion import enqueue
            return enqueue(self, *args)
        raise ValueError('XP1 wonder extra effects require their own native profile')
