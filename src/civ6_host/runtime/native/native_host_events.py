"""Bounded producers for source-decoded deferred EXE events.

EXE 1ca2d0 -> 1445f0 -> 14b220 -> 120400 enqueues event type 0x10c.
The explicit empty-subscriber diagnostic profile has a source-verified drain.
It refuses unknown rows and nonempty receiver state instead of dropping them.
"""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import ctypes as C
import struct
import hashlib
import threading
from pathlib import Path
from civ6_host.runtime.native.native_application_mirror import decode_scalar
from civ6_host.runtime.native.native_setup import local_reader
from civ6_host.runtime.native.native_host_event_registry import EXE_EVENT_CALLBACKS
from civ6_host.runtime.native.native_unary_event_family import UNARY_EVENT_SOURCES
from civ6_host.runtime.native.native_unary_event_family import encode_core_fields
from civ6_host.runtime.native.native_scalar_no_metadata_family import SOURCES as SCALAR_NO_METADATA_SOURCES
from civ6_host.runtime.native.native_two_value_event_family import MEMBERS as TWO_VALUE_EVENT_SOURCES
from civ6_host.runtime.native.native_player_event_domains import validate_player_transport_value
from civ6_host.runtime.native.native_player_event_domains import validate_player_query_input
from civ6_host.runtime.native.native_player_event_domains import validate_sequence
from civ6_host.runtime import xp1_combat_profile as _combat_source
from civ6_host.runtime import improvement_change_profile as _improvement_source
from civ6_host.runtime import district_damage_profile as _district_source
EVENT_KIND = 1390575708
INTEGER_EVENT_KIND = 8475370
BLOB_EVENT_KIND = 2599342313
PLAYER_QUERY_EVENT_KIND = 552735086
ENTITY_EVENT_KIND = 3305989846
UNREGISTERED_PLAYER_CREATED = 595451304
UNREGISTERED_SCALAR_KINDS = frozenset((UNREGISTERED_PLAYER_CREATED, 990500030))
ARGUMENT_KEYS = frozenset((2716180809, 3606901732, 2717631346))

def copy_eight_byte_variant(raw, read, *, expected_tag=0):
    if len(raw) != 24:
        raise ValueError('Invalid blob variant size')
    tag = struct.unpack_from('<H', raw)[0]
    pointer, size, flags = struct.unpack_from('<QII', raw, 8)
    if expected_tag not in (0, 1024) or tag != expected_tag or size != 8 or (flags != 553648129) or (not pointer):
        raise ValueError('Unverified native blob representation')
    result = read(pointer, 8)
    if len(result) != 8:
        raise ValueError('Incomplete native blob copy')
    return bytes(result)

def decode_entity_event(fields, read):
    if type(fields) is not dict or set(fields) != {2716180809, 3606901732, 4032072631}:
        raise ValueError('Unverified entity event fields')
    if any((type(raw) is not bytes or len(raw) != 24 for raw in fields.values())):
        raise ValueError('Entity event requires complete bytes variants')
    if decode_scalar(fields[2716180809], 3) != 0:
        raise ValueError('Unverified entity event selector')
    bits = decode_scalar(fields[3606901732], 4)
    from civ6_host.runtime.native.native_entity_event import pack_coordinate_8_8
    from civ6_host.runtime.native.native_entity_event import verify_source_evidence
    verify_source_evidence()
    pack_coordinate_8_8(bits)
    blob = copy_eight_byte_variant(fields[4032072631], read, expected_tag=1024)
    owner, _, identifier = struct.unpack('<HHI', blob)
    return {'float32_bits': bits, 'source_blob_hex': blob.hex(), 'entity_owner': owner, 'entity_type': 1, 'entity_id': identifier}

def encode_player_event(sequence: int, player: int, enabled: bool) -> bytes:
    """Copy the source DWORD; it is not proof that this player slot exists.

    The boolean callback initializes one byte at +58. The writer also copies
    undefined +59..5B, zeroed only under our explicit empty-receiver profile.
    """
    validate_sequence(sequence)
    validate_player_transport_value(player)
    if type(enabled) is not bool:
        raise ValueError('Unverified player event fields')
    record = bytearray(96)
    struct.pack_into('<IIII', record, 0, 96, 268, sequence, 0)
    struct.pack_into('<ii', record, 16, -1, -1)
    for offset in (24, 32, 40, 48, 56):
        struct.pack_into('<HHi', record, offset, 65535, 0, -1)
    struct.pack_into('<I', record, 72, 4)
    struct.pack_into('<II?', record, 80, sequence, player, enabled)
    return bytes(record)

def encode_integer_player_event(sequence: int, player: int, value: int) -> bytes:
    if type(value) is not int or not 0 <= value <= 4294967295:
        raise ValueError('Integer event value must be uint32')
    record = bytearray(encode_player_event(sequence, player, False))
    struct.pack_into('<I', record, 4, 265)
    struct.pack_into('<I', record, 72, 6)
    struct.pack_into('<I', record, 88, value)
    return bytes(record)

def encode_blob_event(sequence: int, selector: int, payload: bytes) -> bytes:
    if type(selector) is not int or not 0 <= selector <= 4294967295 or len(payload) != 8:
        raise ValueError('Unverified scalar blob event')
    record = bytearray(encode_player_event(sequence, 0, False))
    struct.pack_into('<I', record, 4, 182)
    struct.pack_into('<I', record, 72, 0)
    record[84:92] = payload
    struct.pack_into('<I', record, 92, selector)
    return bytes(record)

def encode_player_query_event(sequence: int, player: int, getter10: int, getter18: int) -> bytes:
    validate_player_query_input(player)
    if any((type(v) is not int or not 0 <= v <= 4294967295 for v in (getter10, getter18))):
        raise ValueError('Unverified native player query payload')
    record = bytearray(encode_blob_event(sequence, getter18, struct.pack('<II', player, getter10)))
    struct.pack_into('<I', record, 4, 193)
    return bytes(record)

class DeferredHostQueue:

    def host_notification(self, receiver, event_code):
        self.host._check(receiver)
        self._require_no_f391_reentry()
        from civ6_host.runtime.native.native_host_slot_e8 import next_host_slot_e8_counter
        before = self.host_notification_counter
        self.host_notification_counter = next_host_slot_e8_counter(event_code, before)
        self.emit('native_host_notification_counter_updated', slot='0xe8', event_code=hex(event_code), counter_before=before, counter_after=self.host_notification_counter, source_callback_rva='0x1c93f0', native_return_type='void', original_exe_counter_consumers_implemented=False, eligible_for_training=False)

    def host_notification_end(self, receiver, event_code):
        self.host._check(receiver)
        self._require_no_f391_reentry()
        from civ6_host.runtime.native.native_host_slot_f0 import next_host_slot_f0_counters
        before = (self.host_notification_counter, self.host_metadata_counter)
        after = next_host_slot_f0_counters(event_code, *before)
        self.host_notification_counter, self.host_metadata_counter = after
        self.emit('native_host_notification_counter_updated', slot='0xf0', event_code=hex(event_code), counter_before=before[0], counter_after=after[0], metadata_counter_before=before[1], metadata_counter_after=after[1], source_callback_rva='0x1c9490', native_return_type='void', original_exe_counter_consumers_implemented=False, eligible_for_training=False)

    def _enqueue(self, record):
        if len(self.pending) >= self.limit:
            raise RuntimeError('Native deferred queue bound exceeded')
        if int.from_bytes(record[8:12], 'little') != self._sequence + 1:
            raise ValueError('Native deferred sequence must increase across drains')
        self.pending.append(record)
        self._sequence += 1

    def cache_update(self, receiver, context_arg, packed_event):
        self.host._check(receiver)
        self._require_no_f391_reentry()
        from civ6_host.runtime.native.native_cache_update_event import encode_cache_update_producer
        from civ6_host.runtime.native.native_cache_update_event import decode_host_b0_scalar
        record = encode_cache_update_producer(self._sequence + 1, context_arg, packed_event, 0, host_callback_pair=self.cache_update_callback_pair)
        self._enqueue(record)
        selector, identifier = decode_host_b0_scalar(packed_event)
        self.emit('native_cache_update_enqueued', queue_type='0x113', context_arg=context_arg, selector=hex(selector), snapshot_id=identifier, record_hex=record.hex(), pending_count=len(self.pending), optional_host_callback_pair_registered=False, queue_metadata_service_registered=False, cache_snapshot_lifecycle_validated=False, consumer_validated=False, eligible_for_training=False, native_dispatch_return=0)
        return 0

    def _consume_cache_update_record(self, record, sequence):
        from civ6_host.runtime.native.native_cache_update_dispatch import dispatch_cache_update_payload
        from civ6_host.runtime.native.native_cache_update_event import encode_cache_update_producer
        if len(record) != 112:
            raise ValueError('Invalid CacheUpdate record size')
        seq, kind, zero, selector, identifier = struct.unpack_from('<5I', record, 80)
        expected = encode_cache_update_producer(sequence, kind, identifier << 32 | selector, 0, host_callback_pair=None)
        if seq != sequence or zero or record != expected:
            raise ValueError('Invalid source-produced CacheUpdate record')
        self.emit('before_native_cache_update_dispatch', sequence=sequence, context_arg=hex(kind), selector=hex(selector), snapshot_id=identifier, core_outer_slot='0x198', eligible_for_training=False)
        try:
            dispatch_cache_update_payload(self.base, self.context, record[80:100], read_memory=self.read, **{'core_sha256': self.cache_core_sha256} if hasattr(self, 'cache_core_sha256') else {})
        except BaseException:
            self._deferred_drain_poisoned = True
            raise
        self.pending.pop(0)
        self.consumed_count += 1
        self.consumed_bytes += len(record)
        self.consumed_digest.update(record)
        self.emit('native_cache_update_dispatched', sequence=sequence, context_arg=hex(kind), selector=hex(selector), snapshot_id=identifier, native_subscriber_dispatch_used=True, snapshot_release_verified=False, eligible_for_training=False)

    def _consume_empty_record(self, record, sequence, *, empty_receiver_state=None):
        from civ6_host.runtime.native.native_deferred_empty_profile import validate_empty_profile_record
        row = validate_empty_profile_record(record, **self.empty_receiver_state if empty_receiver_state is None else empty_receiver_state)
        from civ6_host.runtime.unit_panel_gate import observe_consumed_record
        observe_consumed_record(self, record)
        self.pending.pop(0)
        self.consumed_count += 1
        self.consumed_bytes += len(record)
        self.consumed_digest.update(record)
        self.emit('native_deferred_empty_record_consumed', sequence=sequence, **row, native_handler_has_no_gameplay_callback_in_this_profile=True, native_profiling_reproduced=False, eligible_for_training=False)

class HostControllerQuery:

    def controller_flag(self, receiver):
        self.host._check(receiver)
        from civ6_host.runtime.native.native_host_slot120 import host_slot120_result
        if getattr(self, 'fresh_controller_projection_enabled', False) is True and self.turn_begin_state.controller_initialized is False:
            from civ6_host.runtime.native.native_host_slot120 import initialize_fresh_controller_projection
            receipt = initialize_fresh_controller_projection(self.turn_begin_state)
            self.emit('native_fresh_controller_projection_initialized', **receipt)
        value = host_slot120_result(self.turn_begin_state)
        self.emit('native_host_controller_flag_read', slot='0x120', value=value, shared_with_turn_callbacks=True, original_exe_controller_lifecycle=False, eligible_for_training=False)
        return value

class SharedHostEventDispatch:

    def _enqueue_city_command_started(self, raw_fields):
        from civ6_host.runtime.native import native_event_1d103404 as event
        from civ6_host.runtime.native.native_deferred_empty_profile import validate_empty_profile_record
        if len(self.pending) >= self.limit:
            raise RuntimeError('Native deferred queue bound exceeded')
        if type(self._sequence) is not int or not 0 <= self._sequence < 2147483647:
            raise ValueError('CityCommandStarted sequence exceeds the diagnostic domain')
        before = (self._sequence, len(self.pending), self.host_notification_counter, self.host_metadata_counter)
        self._city_command_started_producing = True
        self._city_command_started_poisoned = True
        try:
            record = event.encode_record(self._sequence + 1, raw_fields, self.read, receiver_state=dict(self.empty_receiver_state), entity_listener_count=self.entity_listener_count, notification_counter=self.host_notification_counter, metadata_counter=self.host_metadata_counter, normalizer_transform_present=False, thread_hook_present=False, writer_metadata_callback_present=False)
            if before != (self._sequence, len(self.pending), self.host_notification_counter, self.host_metadata_counter):
                raise RuntimeError('CityCommandStarted input reads changed the host queue or scope')
            validate_empty_profile_record(record, **self.empty_receiver_state)
            self._enqueue(record)
            self.emit('native_deferred_host_event_enqueued', dispatch_kind=hex(event.EVENT_KIND), queue_type='0x6d', record_hex=record.hex(), pending_count=len(self.pending), source_proof_sha256=event.SOURCE_PROOF_SHA256, unspecified_padding_policy=event.PADDING_POLICY, source_undefined_payload_ranges=[[4, 8]], payload_exposed_to_learner=False, native_queries_executed=False, consumer_validated=False, eligible_for_training=False, native_dispatch_return=0)
            self._city_command_started_poisoned = False
            return 0
        finally:
            self._city_command_started_producing = False

    def _enqueue_unit_embarked_state_changed(self, raw_fields):
        from civ6_host.runtime.native import native_event_84c1fdd6 as event
        from civ6_host.runtime.native.native_deferred_empty_profile import validate_empty_profile_record
        if len(self.pending) >= self.limit:
            raise RuntimeError('Native deferred queue bound exceeded')
        if type(self._sequence) is not int or not 0 <= self._sequence < 2147483647:
            raise ValueError('84C1FDD6 diagnostic sequence exhausted')
        if type(self.entity_listener_count) is not int or self.entity_listener_count != 0 or type(self.host_notification_counter) is not int or (self.host_notification_counter != 0) or (type(self.host_metadata_counter) is not int) or (self.host_metadata_counter != 0):
            raise ValueError('84C1FDD6 requires exact zero counters/listeners')
        shape = bytearray(event.RECORD_SIZE)
        struct.pack_into('<II', shape, 0, event.RECORD_SIZE, event.RECORD_TYPE)
        receiver_state = dict(self.empty_receiver_state)
        validate_empty_profile_record(shape, **receiver_state)
        before = (self._sequence, len(self.pending), self.host_notification_counter, self.host_metadata_counter)
        self._84c1fdd6_producing = True
        self._84c1fdd6_poisoned = True
        try:
            record = event.encode_record(self._sequence + 1, raw_fields, self.read, receiver_state=receiver_state, entity_listener_count=self.entity_listener_count, notification_counter=self.host_notification_counter, metadata_counter=self.host_metadata_counter, inline_node_value_present=False, normalizer_transform_present=False, writer_metadata_callback_present=False, padding_policy=event.PADDING_POLICY)
            if before != (self._sequence, len(self.pending), self.host_notification_counter, self.host_metadata_counter):
                raise RuntimeError('84C1FDD6 borrowed copy mutated host queue/scope')
            validate_empty_profile_record(record, **receiver_state)
            self._enqueue(record)
            self.emit('native_deferred_host_event_enqueued', dispatch_kind=hex(event.EVENT_KIND), queue_type='0x2c', record_hex=record.hex(), pending_count=len(self.pending), source_proof_sha256=event.SOURCE_PROOF_SHA256, receiver_proof_sha256=event.RECEIVER_PROOF_SHA256, unspecified_padding_policy=event.PADDING_POLICY, stack_undefined_ranges=[[84, 88], [97, 104]], writer_zero_filled_ranges=[[76, 80], [104, 112]], payload_exposed_to_learner=False, native_queries_executed=False, consumer_validated=False, eligible_for_training=False, normalizer_return=0)
            self._84c1fdd6_poisoned = False
            return 0
        finally:
            self._84c1fdd6_producing = False

    def _require_no_f391_reentry(self):
        if getattr(self, '_building_pillage_producing', False) or getattr(self, '_building_pillage_poisoned', False):
            raise RuntimeError('BuildingPillaged native producer is active or poisoned')
        if getattr(self, '_district_damage_producing', False) or getattr(self, '_district_damage_poisoned', False):
            raise RuntimeError('Reentrant or poisoned DistrictDamageChanged native producer')
        if getattr(self, '_city_command_started_producing', False) or getattr(self, '_city_command_started_poisoned', False):
            raise RuntimeError('Reentrant or poisoned CityCommandStarted producer')
        if getattr(self, '_district_combat_producing', False) or getattr(self, '_district_combat_poisoned', False):
            raise RuntimeError('Reentrant or poisoned DistrictCombatChanged native producer')
        if getattr(self, '_f391_producing', False) or getattr(self, '_f391_poisoned', False):
            raise RuntimeError('Reentrant or poisoned F391 native query producer')
        if getattr(self, '_found_city_producing', False) or getattr(self, '_found_city_poisoned', False):
            raise RuntimeError('Reentrant or poisoned found-city native query producer')
        if getattr(self, '_36c9_producing', False) or getattr(self, '_36c9_poisoned', False):
            raise RuntimeError('Reentrant or poisoned 36C9 native query producer')
        if getattr(self, '_84c1fdd6_producing', False) or getattr(self, '_84c1fdd6_poisoned', False):
            raise RuntimeError('Reentrant or poisoned 84C1FDD6 producer')

    def _finish_counter_neutral_event(self, kind, record, prior_scope):
        if prior_scope is None:
            return
        from civ6_host.runtime.native.native_counter_neutral_scope import PROOF_SHA256
        from civ6_host.runtime.native.native_counter_neutral_scope import _CLOSED_SCOPE_PROOFS
        if (self.host_notification_counter, self.host_metadata_counter) != prior_scope:
            raise RuntimeError('Counter-neutral notification changed its native scope')
        if struct.unpack_from('<I', record, 72)[0] != 0:
            raise RuntimeError('Counter-neutral notification produced a nonzero flag')
        self.emit('native_notification_metadata_transition', dispatch_kind=hex(kind), sequence=self._sequence, notification_counter=prior_scope[0], metadata_before=prior_scope[1], metadata_after=prior_scope[1], metadata_flag=0, source_proof_sha256=_CLOSED_SCOPE_PROOFS[kind][1] if kind in _CLOSED_SCOPE_PROOFS else PROOF_SHA256, counter_independent_producer=True, empty_receiver_state_verified=True, eligible_for_training=False)

    def _dispatch_fields(self, kind, raw_fields, *, borrowed_argument=None):
        self._require_no_f391_reentry()
        if kind in (1192292772, 4110840759, 2022405428):
            from civ6_host.runtime.a0_game_history_events import dispatch
            return dispatch(self, kind, raw_fields)
        if kind == 3230646521:
            from civ6_host.runtime.goody_hut_reward import enqueue
            return enqueue(self, raw_fields, core_sha256=getattr(self, 'placement_core_sha256', 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'))
        if kind == 487601156:
            return self._enqueue_city_command_started(raw_fields)
        if kind == 2227305942:
            return self._enqueue_unit_embarked_state_changed(raw_fields)
        if kind == 1193679485:
            return self._enqueue_district_combat_changed(raw_fields)
        if kind == 4148886649:
            return self._enqueue_district_damage_changed(raw_fields)
        if kind == 2186730465 and getattr(self, 'ui_cache_callbacks_enabled', False):
            return self._enqueue_combat(raw_fields, borrowed_argument)
        if kind == 4235402789 and getattr(self, 'ui_cache_callbacks_enabled', False):
            return self._enqueue_diplomacy_statement(raw_fields, borrowed_argument)
        if kind == 919188148:
            n, m, gate = self._preflight_36c9(borrowed_argument)
            if not gate:
                from civ6_host.runtime.native.native_36c9b2b4 import validate_closed_gate_input
                validate_closed_gate_input(raw_fields, self.read)
                return 0
            return self._enqueue_natural_wonder_pair(raw_fields, borrowed_argument)
        if kind == 1722672051:
            from civ6_host.runtime.native.native_event_66ade3b3 import encode_record
            record = encode_record(self._sequence + 1, raw_fields, thread_hook_present=False, writer_metadata_callback_present=False)
            self._enqueue(record)
            private_record = self._private_ring().append_turn_complete_fields(raw_fields)
            self.emit('native_turn_complete_dual_records_retained', dispatch_kind=hex(kind), queue_type='0x5', record_hex=record.hex(), pending_count=len(self.pending), private_record_hex=private_record.hex(), diagnostic=self.private_progress_ring.diagnostic(), source_order='standard deferred record then private ring record', private_consumer_validated=False, eligible_for_training=False, native_dispatch_return=0)
            return 0
        if kind == 468001286:
            record = self._private_ring().append_fields(raw_fields)
            self.emit('native_private_ring_record_retained', dispatch_kind=hex(kind), record_hex=record.hex(), record_sha256=hashlib.sha256(record).hexdigest(), diagnostic=self.private_progress_ring.diagnostic(), standard_deferred_queue_used=False, consumer_validated=False, bank_rotated=False, eligible_for_training=False, native_dispatch_return=0)
            return 0
        neutral_scope = None
        if kind == 4067375823 and (self.host_notification_counter != 0 or self.host_metadata_counter != 0):
            from civ6_host.runtime.native.native_f26f3acf_counter_scope import dispatch_scoped
            return dispatch_scoped(self, kind, raw_fields)
        if self.host_notification_counter != 0:
            from civ6_host.runtime.native.native_scalar_notification_scope import RECORDS as scalar_scope_records
            if kind in scalar_scope_records:
                from civ6_host.runtime.native.native_scalar_notification_scope import dispatch_scoped
                return dispatch_scoped(self, kind, raw_fields)
            from civ6_host.runtime.native.native_counter_neutral_scope import RECORD_TYPE_BY_KIND
            from civ6_host.runtime.native.native_counter_neutral_scope import validate_scope
            if kind in RECORD_TYPE_BY_KIND:
                validate_scope(kind, self.host_notification_counter, self.host_metadata_counter, self.entity_listener_count, self.empty_receiver_state)
                if len(self.pending) >= self.limit:
                    raise RuntimeError('Native deferred queue bound exceeded')
                if type(self._sequence) is not int or not 0 <= self._sequence < 2147483647:
                    raise ValueError('Counter-neutral notification sequence exhausted')
                neutral_scope = (self.host_notification_counter, self.host_metadata_counter)
            elif kind not in (2188544486, 2274153042, 424708295, 2599060777, 3241152231, 4086421427, 869823066, 685173694, 58334190, 490036867):
                raise ValueError('Nonzero native notification metadata scope is not yet modeled')
        if kind in (869823066, 685173694) and (self.host_notification_counter != 0 or self.host_metadata_counter != 0):
            from civ6_host.runtime.native.native_found_city_notification_scope import dispatch_scoped
            return dispatch_scoped(self, kind, raw_fields, core_sha256=getattr(self, 'foundation_core_sha256', 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'))
        if kind == 58334190 and (self.host_notification_counter or self.host_metadata_counter):
            from civ6_host.runtime.native.native_building_visibility_scope import dispatch_scoped
            return dispatch_scoped(self, kind, raw_fields, core_sha256=getattr(self, 'foundation_core_sha256', 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'))
        if kind == 490036867 and (self.host_notification_counter or self.host_metadata_counter):
            from civ6_host.runtime.native.native_city_value_notification_scope import dispatch_scoped
            return dispatch_scoped(self, kind, raw_fields, core_sha256=getattr(self, 'foundation_core_sha256', 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'))
        if kind not in EXE_EVENT_CALLBACKS and set(raw_fields) == {2716180809, 4032072631, 3606901732}:
            from civ6_host.runtime.native.native_absent_unit_scalar_family import validate_absent_event
            result = validate_absent_event(kind, raw_fields, self.read, normalizer_transform_present=False, registry_profile=self.callback_registry_profile, dynamic_registration_present=self.dynamic_event_registration_present, entity_listener_count=self.entity_listener_count)
            self.emit('native_host_event_without_registered_callback', dispatch_kind=hex(kind), native_branch='1445f0_absent_key', core_internal_dispatch_preserved=True, normalized_fields=result, native_dispatch_return=result['normalizer_result'], eligible_for_training=False)
            return result['normalizer_result']
        if kind not in EXE_EVENT_CALLBACKS and set(raw_fields) == {2716180809, 3036238893, 3606901732}:
            from civ6_host.runtime.native.native_absent_b4_scalar_family import validate_absent_event
            result = validate_absent_event(kind, raw_fields, normalizer_transform_present=False, registry_profile=self.callback_registry_profile, dynamic_registration_present=self.dynamic_event_registration_present, entity_listener_count=self.entity_listener_count)
            self.emit('native_host_event_without_registered_callback', dispatch_kind=hex(kind), native_branch='1445f0_absent_key', core_internal_dispatch_preserved=True, normalized_fields=result, native_dispatch_return=result['normalizer_result'], eligible_for_training=False)
            return result['normalizer_result']
        if kind == 507110547:
            from civ6_host.runtime.native.native_event_turn_status import build_turn_status_record
            from civ6_host.runtime.native.native_deferred_empty_profile import validate_empty_profile_record
            if set(raw_fields) != {2716180809, 3606901732} or decode_scalar(raw_fields[2716180809], 3) != 0:
                raise ValueError('Unverified pre-turn native event argument fields')
            value = decode_scalar(raw_fields[3606901732], 2)
            proof = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_host_events.py')))).resolve().parents[1] / 'evidence/native-pre-turn-immediate.json'
            if hashlib.sha256(_resolve_resource_path(proof).read_bytes()).hexdigest() != '3079a38a533a9ddefe14b6ca9dd68ccc4e908b2d465d87d20ff33e68dec8f24c':
                raise RuntimeError('Immediate pre-turn source proof changed')
            record = build_turn_status_record(kind, value, self._sequence + 1)
            validate_empty_profile_record(record, **self.pre_turn_immediate_state)
            self.emit('native_pre_turn_immediate_empty_dispatch', turn=value, handler_rva='0xefd90', subscriber_count=0, original_exe_listeners_captured=False, native_profiling_reproduced=False, eligible_for_training=False)
            self._enqueue(record)
            self.emit('native_deferred_host_event_enqueued', dispatch_kind=hex(kind), queue_type='0x3', turn=value, record_hex=record.hex(), pending_count=len(self.pending), optional_preprocessing_hook_registered=False, queue_metadata_service_registered=False, unspecified_padding_policy='zero', consumer_validated=False, eligible_for_training=False, native_dispatch_return=0)
            return 0
        if kind == 559109511:
            from civ6_host.runtime.native.native_event_turn_status import build_turn_status_record
            if set(raw_fields) != {2716180809, 3606901732} or decode_scalar(raw_fields[2716180809], 3) != 0:
                raise ValueError('Unverified turn-begin native event argument fields')
            value = decode_scalar(raw_fields[3606901732], 2)
            self.turn_begin_state.before_queue(value, 0)
            record = build_turn_status_record(kind, value, self._sequence + 1)
            self._enqueue(record)
            self.turn_begin_state.after_queue(value, 0)
            self.emit('native_deferred_host_event_enqueued', dispatch_kind=hex(kind), queue_type='0x4', turn=value, record_hex=record.hex(), pending_count=len(self.pending), optional_preprocessing_hook_registered=False, queue_metadata_service_registered=False, unspecified_padding_policy='zero', controller_byte_0d=self.turn_begin_state.controller_byte_0d, ui_manager_flags=self.turn_begin_state.service_flags, turn_telemetry_values=list(self.turn_begin_state.turn_values_by_thread[0]), original_exe_controller_scheduling=False, consumer_validated=False, eligible_for_training=False, native_dispatch_return=0)
            return 0
        if kind == 2163291757:
            from civ6_host.runtime.native.native_event_80f1366d import decode_fields
            if kind in EXE_EVENT_CALLBACKS:
                raise RuntimeError('Previously absent EXE callback is now registered')
            fields = decode_fields(raw_fields)
            self.emit('native_host_event_without_registered_callback', dispatch_kind=hex(kind), selector=fields.selector, value=fields.value, native_branch='1445f0_absent_key', core_internal_dispatch_preserved=True, source_registrar_rva='0x14d7a0', native_dispatch_return=0, eligible_for_training=False)
            return 0
        if kind == 1169496022:
            from civ6_host.runtime.native.native_event_45b517d6 import produce_record
            from civ6_host.runtime.native.native_event_45b517d6 import PROOF_SHA256
            from civ6_host.runtime.native.native_event_45b517d6 import CITY_DESCRIPTOR_KEY
            from civ6_host.runtime.native.native_event_45b517d6 import CITY_PROOF_SHA256
            if self.ui_cache_callbacks_enabled:
                if len(self.pending) >= self.limit:
                    raise RuntimeError('WorldTextMessage exceeds native deferred queue bound')
                if type(self._sequence) is not int or not 0 <= self._sequence < 2147483647:
                    raise ValueError('WorldTextMessage sequence exceeds bounded native range')
            record = produce_record(self._sequence + 1, raw_fields, self.read, gate_enabled=self.ui_cache_callbacks_enabled, cache_map_snapshot=self.ui_cache_map_snapshot, normalizer_transform_present=False, entity_listener_count=self.entity_listener_count, per_thread_hook_present=False, writer_metadata_callback_present=False, empty_receiver_state=self.empty_receiver_state)
            if record is None:
                self.emit('native_host_event_cache_gate_closed', dispatch_kind=hex(kind), source_gate_rva='0xf16d0', normalized_borrowed_fields_copied=True, text_characters_read=False, native_queries_executed=False, source_proof_sha256=PROOF_SHA256, native_dispatch_return=0, eligible_for_training=False)
                return 0
            self._enqueue(record)
            self.emit('native_deferred_host_event_enqueued', dispatch_kind=hex(kind), queue_type='0xfa', record_hex=record.hex(), pending_count=len(self.pending), native_queries_executed=False, payload_fully_initialized=True, text_copy_profile='native-strncpy-256', metadata_index=struct.unpack_from('<I', record, 20)[0], native_cache_width=struct.unpack_from('<I', self.ui_cache_map_snapshot)[0], metadata_source='retained-native-B0-E8-snapshot', source_proof_sha256=PROOF_SHA256, consumer_validated=False, city_descriptor_source_sha256=CITY_PROOF_SHA256 if CITY_DESCRIPTOR_KEY in raw_fields else None, payload_exposed_to_learner=False, eligible_for_training=False, native_dispatch_return=0)
            return 0
        if kind == 2188544486:
            from civ6_host.runtime.native.native_event_827289e6 import encode_scoped_record
            from civ6_host.runtime.native.native_notification_metadata import PROOF_SHA256
            from civ6_host.runtime.native.native_deferred_empty_profile import validate_empty_profile_record
            if self.ui_cache_callbacks_enabled:
                if type(self.entity_listener_count) is not int or self.entity_listener_count != 0:
                    raise ValueError('827289E6 requires the source empty entity-listener profile')
                if len(self.pending) >= self.limit:
                    raise RuntimeError('827289E6 exceeds native deferred queue bound')
                if type(self._sequence) is not int or not 0 <= self._sequence < 2147483647:
                    raise ValueError('827289E6 sequence exceeds bounded native range')
                shape = bytearray(128)
                struct.pack_into('<II', shape, 0, 128, 181)
                validate_empty_profile_record(shape, **self.empty_receiver_state)
            metadata_before = self.host_metadata_counter
            record, metadata_after = encode_scoped_record(raw_fields, self.read, sequence=self._sequence + 1, gate_enabled=self.ui_cache_callbacks_enabled, cache_initialized=self.ui_cache_callbacks_enabled, notification_counter=self.host_notification_counter, metadata_counter=metadata_before, optional_thread_hook=False, queue_metadata_service=False, padding_policy='headless-zero-initialization', core=self.core, context=self.context, core_sha256=getattr(self, 'foundation_core_sha256', 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'))
            if record is None:
                self.emit('native_host_event_cache_gate_closed', dispatch_kind=hex(kind), source_gate_rva='0xf16d0', native_dispatch_return=0, original_exe_lifecycle=False, eligible_for_training=False)
                return 0
            validate_empty_profile_record(record, **self.empty_receiver_state)
            self._enqueue(record)
            self.host_metadata_counter = metadata_after
            metadata_flag = struct.unpack_from('<I', record, 72)[0]
            if self.host_notification_counter != 0:
                self.emit('native_notification_metadata_transition', dispatch_kind=hex(kind), sequence=self._sequence, notification_counter=self.host_notification_counter, metadata_before=metadata_before, metadata_after=metadata_after, metadata_flag=metadata_flag, source_proof_sha256=PROOF_SHA256, empty_receiver_state_verified=True, eligible_for_training=False)
            self.emit('native_deferred_host_event_enqueued', dispatch_kind=hex(kind), queue_type='0xb5', record_hex=record.hex(), pending_count=len(self.pending), public_cache_initialized=True, notification_counter=self.host_notification_counter, metadata_before=metadata_before, metadata_after=metadata_after, metadata_flag=metadata_flag, metadata_scope_source_sha256=PROOF_SHA256, optional_preprocessing_hook_registered=False, queue_metadata_service_registered=False, unspecified_padding_policy='zero', original_exe_lifecycle=False, consumer_validated=False, eligible_for_training=False, native_dispatch_return=0)
            return 0
        if kind == 2597437472:
            from civ6_host.runtime.native.native_event_9ad1c020 import decode_fields
            from civ6_host.runtime.native.native_event_9ad1c020 import encode_record
            fields = decode_fields(raw_fields, self.read)
            record = encode_record(self._sequence + 1, fields, per_thread_hook_present=False, writer_metadata_callback_present=False, padding_policy='headless-zero-uninitialized-stack')
            self._enqueue(record)
            self.emit('native_deferred_host_event_enqueued', dispatch_kind=hex(kind), queue_type='0x102', record_hex=record.hex(), descriptor=fields.descriptor.hex(), pending_count=len(self.pending), metadata_flag=4, unspecified_padding_policy='zero', consumer_validated=False, eligible_for_training=False, native_dispatch_return=0)
            return 0
        if kind == 272736031:
            from civ6_host.runtime.native.native_event_10419f1f import decode_fields
            from civ6_host.runtime.native.native_event_10419f1f import produce_record
            fields = decode_fields(raw_fields, self.read)
            identities = getattr(self.host, 'configured_player_identity_hashes', {})
            record = produce_record(self._sequence + 1, self.core, self.context, fields, expected_civilization_hash=identities.get(fields.owner), normalizer_transform_present=False, per_thread_hook_present=False, writer_metadata_callback_present=False, padding_policy='headless-zero-uninitialized-stack', read=self.read, core_sha256=getattr(self, 'foundation_core_sha256', 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'))
            self._enqueue(record)
            self.emit('native_deferred_host_event_enqueued', dispatch_kind=hex(kind), queue_type='0x66', record_hex=record.hex(), owner=fields.owner, pending_count=len(self.pending), native_queries_executed=True, unspecified_padding_policy='zero', consumer_validated=False, eligible_for_training=False, native_dispatch_return=0)
            return 0
        if kind == 2910348563:
            from civ6_host.runtime.native import native_event_ad786513 as event
            from civ6_host.runtime.native.native_deferred_empty_profile import validate_empty_profile_record
            if len(self.pending) >= self.limit:
                raise RuntimeError('Native deferred queue bound exceeded')
            if type(self._sequence) is not int or not 0 <= self._sequence < 2147483647:
                raise ValueError('AD786513 requires a bounded native diagnostic sequence')
            if type(self.entity_listener_count) is not int or self.entity_listener_count != 0:
                raise ValueError('AD786513 requires actual empty entity listeners')
            shape = bytearray(event.RECORD_SIZE)
            struct.pack_into('<II', shape, 0, event.RECORD_SIZE, event.RECORD_TYPE)
            validate_empty_profile_record(shape, **self.empty_receiver_state)
            fields = event.decode_fields(raw_fields, self.read)
            record = event.encode_record(self._sequence + 1, fields, normalizer_transform_present=False, per_thread_hook_present=False, writer_metadata_callback_present=False, entity_listener_count=self.entity_listener_count, empty_receiver_state=self.empty_receiver_state, padding_policy=event.PADDING_POLICY)
            validate_empty_profile_record(record, **self.empty_receiver_state)
            self._enqueue(record)
            self.emit('native_deferred_host_event_enqueued', dispatch_kind=hex(kind), queue_type='0x115', record_hex=record.hex(), city_descriptor_hex=fields.city.hex(), unit_descriptor_hex=fields.unit.hex(), input_field_count=len(raw_fields), source_selector=fields.selector, source_proof_sha256=event.PROOF_SHA256, pending_count=len(self.pending), native_queries_executed=False, unit_consumed_by_callback=False, entity_listener_count=self.entity_listener_count, normalizer_transform_present=False, unspecified_padding_policy=event.PADDING_POLICY, undefined_value_is_native_default=False, empty_receiver_state_verified=True, payload_exposed_to_learner=False, consumer_validated=False, eligible_for_training=False, native_dispatch_return=0)
            return 0
        if kind == 1099678774:
            from civ6_host.runtime.native.native_event_418bc436 import decode_fields
            from civ6_host.runtime.native.native_event_418bc436 import encode_record
            from civ6_host.runtime.native.native_event_418bc436 import NORMALIZATION_PROOF_SHA256
            from civ6_host.runtime.native.native_deferred_empty_profile import validate_empty_profile_record
            if len(self.pending) >= self.limit:
                raise RuntimeError('Native deferred queue bound exceeded')
            if type(self._sequence) is not int or not 0 <= self._sequence < 2147483647:
                raise ValueError('418BC436 requires a bounded native diagnostic sequence')
            if type(self.entity_listener_count) is not int or self.entity_listener_count != 0:
                raise ValueError('418BC436 requires actual empty entity listeners')
            shape = bytearray(112)
            struct.pack_into('<II', shape, 0, 112, 105)
            validate_empty_profile_record(shape, **self.empty_receiver_state)
            fields = decode_fields(raw_fields, self.read)
            record = encode_record(self._sequence + 1, fields, normalizer_transform_present=False, per_thread_hook_present=False, writer_metadata_callback_present=False, padding_policy='headless-zero-uninitialized-stack')
            validate_empty_profile_record(record, **self.empty_receiver_state)
            self._enqueue(record)
            self.emit('native_deferred_host_event_enqueued', dispatch_kind=hex(kind), queue_type='0x69', record_hex=record.hex(), owner=fields.owner, item_id=fields.item_id, pending_count=len(self.pending), normalization_source_proof_sha256=NORMALIZATION_PROOF_SHA256, source_selector=hex(fields.selector), source_d6_value=fields.value, optional_value=fields.optional_value, optional_value_consumed_by_callback=False, input_field_count=len(raw_fields), native_queries_executed=False, entity_listener_count=self.entity_listener_count, normalizer_transform_present=False, unspecified_padding_policy='zero', undefined_value_is_native_default=False, empty_receiver_state_verified=True, payload_exposed_to_learner=False, consumer_validated=False, eligible_for_training=False, native_dispatch_return=0)
            return 0
        if kind in (2582142662, 2785224901, 943090161, 4217315035, 4222460616, 3270739392, 2381973687):
            if kind == 2381973687:
                from civ6_host.runtime.native.native_event_8dfa08b7 import decode_fields
                from civ6_host.runtime.native.native_event_8dfa08b7 import encode_record
                from civ6_host.runtime.native.native_event_8dfa08b7 import RECORD_TYPE
            elif kind == 2582142662:
                from civ6_host.runtime.native.native_event_99e85ec6 import decode_fields
                from civ6_host.runtime.native.native_event_99e85ec6 import encode_record
                from civ6_host.runtime.native.native_event_99e85ec6 import RECORD_TYPE
            elif kind == 943090161:
                from civ6_host.runtime.native.native_event_383669f1 import decode_fields
                from civ6_host.runtime.native.native_event_383669f1 import encode_record
                from civ6_host.runtime.native.native_event_383669f1 import RECORD_TYPE
            elif kind == 4217315035:
                from civ6_host.runtime.native.native_event_fb5f1edb import decode_fields
                from civ6_host.runtime.native.native_event_fb5f1edb import encode_record
                from civ6_host.runtime.native.native_event_fb5f1edb import RECORD_TYPE
            elif kind == 4222460616:
                from civ6_host.runtime.native.native_event_fbada2c8 import decode_event_fields as decode_fields
                from civ6_host.runtime.native.native_event_fbada2c8 import encode_record
                from civ6_host.runtime.native.native_event_fbada2c8 import RECORD_TYPE
            elif kind == 3270739392:
                from civ6_host.runtime.native.native_event_c2f385c0 import decode_fields
                from civ6_host.runtime.native.native_event_c2f385c0 import encode_record
                from civ6_host.runtime.native.native_event_c2f385c0 import RECORD_TYPE
            else:
                from civ6_host.runtime.native.native_event_a60328c5 import decode_fields
                from civ6_host.runtime.native.native_event_a60328c5 import encode_record
                from civ6_host.runtime.native.native_event_a60328c5 import RECORD_TYPE
            fields = decode_fields(raw_fields, self.read)
            record = encode_record(self._sequence + 1, fields, normalizer_transform_present=False, per_thread_hook_present=False, writer_metadata_callback_present=False, padding_policy='headless-zero-uninitialized-stack')
            if kind == 2381973687:
                from civ6_host.runtime.native.native_deferred_empty_profile import validate_empty_profile_record
                validate_empty_profile_record(record, **self.empty_receiver_state)
            self._enqueue(record)
            self.emit('native_deferred_host_event_enqueued', dispatch_kind=hex(kind), queue_type=hex(RECORD_TYPE), record_hex=record.hex(), owner=fields.owner, pending_count=len(self.pending), normalizer_transform_present=False, unspecified_padding_policy='zero', consumer_validated=False, empty_receiver_state_verified=kind == 2381973687, eligible_for_training=False, native_dispatch_return=0)
            return 0
        if kind in (2075911904, 689003850, 3727501331):
            from civ6_host.runtime.native.native_city_descriptor_events import decode_event_fields
            from civ6_host.runtime.native.native_city_descriptor_events import encode_record
            from civ6_host.runtime.native.native_city_descriptor_events import SPECS
            fields = decode_event_fields(kind, raw_fields, self.read)
            record = encode_record(kind, self._sequence + 1, fields, normalizer_transform_present=False, per_thread_hook_present=False, writer_metadata_callback_present=False, padding_policy='headless-zero-uninitialized-stack')
            self._enqueue(record)
            self.emit('native_deferred_host_event_enqueued', dispatch_kind=hex(kind), queue_type=hex(SPECS[kind].record_type), record_hex=record.hex(), owner=fields.descriptor_word, item_id=fields.descriptor_dword, pending_count=len(self.pending), unspecified_padding_policy='zero', consumer_validated=False, eligible_for_training=False, native_dispatch_return=0)
            return 0
        if kind == 94203074:
            from civ6_host.runtime.native.native_event_059d6cc2 import decode_fields
            from civ6_host.runtime.native.native_event_059d6cc2 import encode_research_record
            player, operation = decode_fields(raw_fields)
            record = encode_research_record(self._sequence + 1, player, operation, hook_present=False, writer_metadata_callback_present=False)
            self._enqueue(record)
            self.emit('native_deferred_host_event_enqueued', dispatch_kind=hex(kind), queue_type='0x10e', record_hex=record.hex(), player_id=player, operation=operation, pending_count=len(self.pending), unspecified_padding_policy='zero', consumer_validated=False, eligible_for_training=False, native_dispatch_return=0)
            return 0
        if kind == 490036867:
            from civ6_host.runtime.native.native_event_1d355e83 import decode_fields
            from civ6_host.runtime.native.native_event_1d355e83 import encode_record
            from civ6_host.runtime.native.native_event_1d355e83 import POSITIVE_PROOF_SHA256
            from civ6_host.runtime.native.native_deferred_empty_profile import validate_empty_profile_record
            if len(self.pending) >= self.limit:
                raise RuntimeError('Native deferred queue bound exceeded')
            shape = bytearray(128)
            struct.pack_into('<II', shape, 0, 128, 92)
            validate_empty_profile_record(shape, **self.empty_receiver_state)
            fields = decode_fields(raw_fields, self.read)
            queried = fields.optional_index is not None and fields.optional_index < 2147483648
            if queried and (not self.ui_cache_callbacks_enabled):
                raise ValueError('1D355E83 positive query requires the initialized native map facade')
            record = encode_record(self._sequence + 1, fields, notification_counter=self.host_notification_counter, notification_limit=self.host_metadata_counter, normalizer_transform_present=False, per_thread_hook_present=False, writer_metadata_callback_present=False, padding_policy='headless-zero-uninitialized-stack', core=self.core, context=self.context, read=self.read, core_sha256=getattr(self, 'foundation_core_sha256', 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'))
            validate_empty_profile_record(record, **self.empty_receiver_state)
            self._enqueue(record)
            self.emit('native_deferred_host_event_enqueued', dispatch_kind=hex(kind), queue_type='0x5c', record_hex=record.hex(), owner=fields.owner, item_id=fields.item_id, value=fields.value, pending_count=len(self.pending), optional_query_fields_absent=fields.optional_index is None, optional_fields_absent=fields.optional_fields_absent, input_shape=fields.input_shape, native_query_executed=queried, unspecified_padding_policy='zero', consumer_validated=False, eligible_for_training=False, native_dispatch_return=0)
            if queried:
                self.emit('native_1d355e83_optional_query_enqueued', dispatch_kind=hex(kind), source_proof_sha256=POSITIVE_PROOF_SHA256, queue_type='0x5c', optional_map_index=fields.optional_index, native_optional_position_hex=record[100:108].hex(), optional_scalar=fields.optional_scalar, record_sequence=self._sequence, record_sha256=hashlib.sha256(record).hexdigest(), native_map_released_before_enqueue=True, payload_exposed_to_learner=False, consumer_validated=False, eligible_for_training=False)
            return 0
        if kind == 1372081338:
            from civ6_host.runtime.native.native_event_51c84cba import decode_fields
            from civ6_host.runtime.native.native_event_51c84cba import encode_record
            fields = decode_fields(raw_fields, self.read)
            record = encode_record(self._sequence + 1, fields, normalizer_transform_present=False, per_thread_hook_present=False, writer_metadata_callback_present=False, padding_policy='headless-zero-uninitialized-stack')
            self._enqueue(record)
            self.emit('native_deferred_host_event_enqueued', dispatch_kind=hex(kind), queue_type='0x67', record_hex=record.hex(), owner=fields.owner, item_id=fields.item_id, value=fields.value, pending_count=len(self.pending), normalizer_transform_present=False, unspecified_padding_policy='zero', consumer_validated=False, eligible_for_training=False, native_dispatch_return=0)
            return 0
        if kind == 685173694:
            from civ6_host.runtime.native.native_event_28d6ebbe import decode_fields
            from civ6_host.runtime.native.native_event_28d6ebbe import produce_record_lease
            from civ6_host.runtime.native.native_event_28d6ebbe import POSITIVE_PROOF_SHA256
            from civ6_host.runtime.native.native_deferred_empty_profile import validate_empty_profile_record
            if len(self.pending) >= self.limit:
                raise RuntimeError('Native deferred queue bound exceeded')
            shape = bytearray(144)
            struct.pack_into('<II', shape, 0, 144, 158)
            validate_empty_profile_record(shape, **self.empty_receiver_state)
            fields = decode_fields(raw_fields, self.read)
            queried = fields.optional_index is not None and fields.optional_index < 2147483648
            if queried and (not self.ui_cache_callbacks_enabled):
                raise ValueError('28D6EBBE positive query requires the initialized native map facade')
            with produce_record_lease(self._sequence + 1, self.core, self.context, fields, notification_counter=self.host_notification_counter, notification_limit=self.host_metadata_counter, per_thread_hook_present=False, writer_metadata_callback_present=False, padding_policy='headless-zero-uninitialized-stack', read=self.read, core_sha256=getattr(self, 'foundation_core_sha256', 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3')) as record:
                validate_empty_profile_record(record, **self.empty_receiver_state)
                self._enqueue(record)
            self.emit('native_deferred_host_event_enqueued', dispatch_kind=hex(kind), queue_type='0x9e', record_hex=record.hex(), owner=fields.owner, item_id=fields.item_id, value=fields.value, retained_sources_live_at_enqueue=True, pending_count=len(self.pending), native_queries_executed=True, optional_fields_absent=fields.optional_fields_absent, unspecified_padding_policy='zero', consumer_validated=False, eligible_for_training=False, native_dispatch_return=0)
            if queried:
                self.emit('native_28d6ebbe_optional_query_enqueued', dispatch_kind=hex(kind), queue_type='0x9e', optional_map_index=fields.optional_index, source_proof_sha256=POSITIVE_PROOF_SHA256, native_optional_position_hex=record[124:132].hex(), optional_scalar=fields.optional_scalar, owner=fields.owner, item_id=fields.item_id, record_sequence=self._sequence, record_sha256=hashlib.sha256(record).hexdigest(), map_released_before_item_acquisition=True, item_released_after_enqueue=True, payload_exposed_to_learner=False, consumer_validated=False, eligible_for_training=False)
            return 0
        if kind == 1836147632:
            from civ6_host.runtime.native.native_event_6d7163b0 import decode_fields
            from civ6_host.runtime.native.native_event_6d7163b0 import produce_records
            from civ6_host.runtime.native.native_event_6d7163b0 import record_plan_from_fields
            from civ6_host.runtime.native.native_deferred_empty_profile import validate_empty_profile_record
            plan = record_plan_from_fields(raw_fields)
            if len(self.pending) + len(plan) > self.limit:
                raise RuntimeError('District notification plan exceeds native deferred queue bound')
            if type(self._sequence) is not int or not 0 <= self._sequence <= 2147483647 - len(plan):
                raise ValueError('District notification sequences exceed bounded native range')
            if type(self.entity_listener_count) is not int or self.entity_listener_count != 0:
                raise ValueError('District notification requires actual empty entity listeners')
            for record_type, record_size in plan:
                shape = bytearray(record_size)
                struct.pack_into('<II', shape, 0, record_size, record_type)
                validate_empty_profile_record(shape, **self.empty_receiver_state)
            fields = decode_fields(raw_fields, self.read)
            identities = getattr(self.host, 'configured_player_identity_hashes', {})
            first_sequence = self._sequence + 1
            enqueued_passes = []

            def enqueue_progress_record(record, pass_index, values):
                if pass_index != len(enqueued_passes) or pass_index not in range(len(plan)):
                    raise ValueError('District progress producer changed native write order')
                record_type, record_size = plan[pass_index]
                if len(record) != record_size or struct.unpack_from('<III', record) != (record_size, record_type, first_sequence + pass_index):
                    raise ValueError('District progress producer changed its native record shape')
                validate_empty_profile_record(record, **self.empty_receiver_state)
                self._enqueue(record)
                enqueued_passes.append(pass_index)
                self.emit('native_deferred_host_event_enqueued', dispatch_kind=hex(kind), queue_type=hex(record_type), record_hex=record.hex(), pass_index=pass_index, owner=fields.owner, item_id=fields.item_id, x=fields.x, y=fields.y, pending_count=len(self.pending), native_queries_executed=True, native_snapshot_size=64, native_snapshot_vector_released=True, retained_sources_live_at_enqueue=True, empty_receiver_state_verified=True, undefined_value_policy='zero-unread-empty-receiver-payload', undefined_value_is_native_default=False, payload_exposed_to_learner=False, consumer_validated=False, eligible_for_training=False, native_dispatch_return=0)
            produce_records(first_sequence, self.core, self.context, fields, enqueue_record=enqueue_progress_record, expected_civilization_hash=identities.get(fields.owner), normalizer_transform_present=False, per_thread_hook_present=False, writer_metadata_callback_present=False, padding_policy='zero-unread-empty-receiver-payload', empty_receiver_state=self.empty_receiver_state, read=self.read, core_sha256=getattr(self, 'placement_core_sha256', 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'))
            if enqueued_passes != list(range(len(plan))):
                raise ValueError('District progress producer did not deliver its complete native plan')
            self.emit('native_district_progress_notification_completed', dispatch_kind=hex(kind), record_count=len(plan), independent_query_passes=len(plan), retained_sources_released=True, selector=hex(fields.selector), eligible_for_training=False)
            return 0
        if kind == 3273144578:
            from civ6_host.runtime.native.native_event_c3183902 import decode_fields
            from civ6_host.runtime.native.native_event_c3183902 import produce_record_lease
            fields = decode_fields(raw_fields, self.read)
            identities = getattr(self.host, 'configured_player_identity_hashes', {})
            with produce_record_lease(self._sequence + 1, self.core, self.context, fields, expected_civilization_hash=identities.get(fields.owner), notification_counter=self.host_notification_counter, notification_limit=self.host_metadata_counter, per_thread_hook_present=False, writer_metadata_callback_present=False, padding_policy='headless-zero-uninitialized-stack', read=self.read, core_sha256=getattr(self, 'foundation_core_sha256', 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3')) as record:
                self._enqueue(record)
            self.emit('native_deferred_host_event_enqueued', dispatch_kind=hex(kind), queue_type='0x9c', record_hex=record.hex(), owner=fields.owner, item_id=fields.item_id, x=fields.x, y=fields.y, pending_count=len(self.pending), native_queries_executed=True, native_snapshot_size=64, native_snapshot_vector_released=True, retained_sources_live_at_enqueue=True, unspecified_padding_policy='zero', consumer_validated=False, eligible_for_training=False, native_dispatch_return=0)
            return 0
        if kind == 869823066:
            from civ6_host.runtime.native.native_event_33d8725a import decode_fields
            from civ6_host.runtime.native.native_event_33d8725a import encode_record
            from civ6_host.runtime.native.native_event_33d8725a import POSITIVE_PROOF_SHA256
            from civ6_host.runtime.native.native_deferred_empty_profile import validate_empty_profile_record
            if len(self.pending) >= self.limit:
                raise RuntimeError('Native deferred queue bound exceeded')
            shape = bytearray(128)
            struct.pack_into('<II', shape, 0, 128, 154)
            validate_empty_profile_record(shape, **self.empty_receiver_state)
            decoded = decode_fields(raw_fields, self.read)
            index = decoded['optional_index']
            queried = index is not None and index < 2147483648
            if queried and (not self.ui_cache_callbacks_enabled):
                raise ValueError('33D8725A positive query requires the initialized native map facade')
            record = encode_record(self._sequence + 1, decoded, notification_counter=self.host_notification_counter, notification_limit=self.host_metadata_counter, thread_hook_present=False, writer_metadata_callback_present=False, padding_policy='zero', core=self.core, context=self.context, read=self.read, core_sha256=getattr(self, 'foundation_core_sha256', 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'))
            validate_empty_profile_record(record, **self.empty_receiver_state)
            self._enqueue(record)
            self.emit('native_deferred_host_event_enqueued', dispatch_kind=hex(kind), queue_type='0x9a', x=decoded['x'], y=decoded['y'], descriptor_tail=decoded['descriptor_tail'], pending_count=len(self.pending), optional_fields_absent=decoded['optional_fields_absent'], record_hex=record.hex(), native_optional_map_query_executed=queried, optional_map_index=index, source_map_released_before_enqueue=queried, payload_exposed_to_learner=False, optional_preprocessing_hook_registered=False, queue_metadata_service_registered=False, unspecified_padding_policy='zero', consumer_validated=False, eligible_for_training=False, native_dispatch_return=0)
            if queried:
                self.emit('native_33d8725a_optional_query_enqueued', dispatch_kind=hex(kind), queue_type='0x9a', source_proof_sha256=POSITIVE_PROOF_SHA256, optional_map_index=index, native_optional_position_hex=record[100:108].hex(), optional_scalar=decoded['optional_scalar'], record_sequence=self._sequence, record_sha256=hashlib.sha256(record).hexdigest(), native_map_released_before_enqueue=True, consumer_validated=False, payload_exposed_to_learner=False, eligible_for_training=False)
            return 0
        if kind == 3765759732:
            from civ6_host.runtime.native.native_event_e074eef4 import decode_fields
            from civ6_host.runtime.native.native_event_e074eef4 import query_descriptor_lease
            from civ6_host.runtime.native.native_event_e074eef4 import encode_record
            from civ6_host.runtime.native.native_event_e074eef4 import validate_profile
            from civ6_host.runtime.native.native_event_e074eef4 import PINNED_EVIDENCE_SHA256
            profile = dict(normalizer_transform_present=False, thread_hook_present=False, writer_metadata_callback_present=False, padding_policy='zero-unread-empty-receiver-payload', empty_receiver_state=self.empty_receiver_state)
            validate_profile(**profile)
            if len(self.pending) >= self.limit:
                raise RuntimeError('Native deferred queue bound exceeded')
            if type(self._sequence) is not int or not 0 <= self._sequence < 2147483647:
                raise ValueError('BuildingRemovedFromMap sequence exhausted')
            fields = decode_fields(raw_fields, self.read)
            with query_descriptor_lease(self.core, self.context, fields, read=self.read, **profile) as descriptor:
                record = encode_record(self._sequence + 1, fields, descriptor, **profile)
                self._enqueue(record)
            self.emit('native_deferred_host_event_enqueued', dispatch_kind=hex(kind), queue_type='0xa8', record_hex=record.hex(), pending_count=len(self.pending), native_query_completed=True, native_plot_lease_released_after_append=True, source_proof_sha256=PINNED_EVIDENCE_SHA256, normalizer_transform_present=False, optional_preprocessing_hook_registered=False, queue_metadata_service_registered=False, empty_receiver_state_verified=True, source_padding_policy=profile['padding_policy'], undefined_value_is_native_default=False, payload_exposed_to_learner=False, consumer_validated=False, eligible_for_training=False, native_dispatch_return=0)
            return 0
        if kind == 2070282030:
            from civ6_host.runtime.native.native_event_7b65ff2e import decode_fields
            from civ6_host.runtime.native.native_event_7b65ff2e import query_descriptor
            from civ6_host.runtime.native.native_event_7b65ff2e import encode_record
            from civ6_host.runtime.native.native_event_7b65ff2e import validate_profile
            profile = dict(normalizer_transform_present=False, thread_hook_present=False, writer_metadata_callback_present=False, padding_policy='zero-unread-empty-receiver-payload', empty_receiver_state=self.empty_receiver_state)
            validate_profile(**profile)
            if len(self.pending) >= self.limit:
                raise RuntimeError('Native deferred queue bound exceeded')
            if type(self._sequence) is not int or not 0 <= self._sequence < 2147483647:
                raise ValueError('RouteChanged sequence exhausted')
            fields = decode_fields(raw_fields, self.read)
            descriptor = query_descriptor(self.core, self.context, fields, read=self.read, **profile, core_sha256=getattr(self, 'improvement_core_sha256', 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'))
            record = encode_record(self._sequence + 1, fields, descriptor, **profile)
            self._enqueue(record)
            self.emit('native_deferred_host_event_enqueued', dispatch_kind=hex(kind), queue_type='0x99', record_hex=record.hex(), pending_count=len(self.pending), native_query_source='0x140147cc0', native_query_completed=True, normalizer_transform_present=False, optional_preprocessing_hook_registered=False, queue_metadata_service_registered=False, empty_receiver_state_verified=True, source_padding_policy=profile['padding_policy'], undefined_value_is_native_default=False, payload_exposed_to_learner=False, consumer_validated=False, eligible_for_training=False, native_dispatch_return=0, source_proof_sha256=_improvement_source.source_sha(getattr(self, 'improvement_core_sha256', 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'), '24157becb7c25402cd2816aa2633b6f33bcb58c6740f10080234bda80cbd13ef'))
            return 0
        if kind == 1561280532:
            from civ6_host.runtime.native.native_event_5d0f4014 import decode_fields
            from civ6_host.runtime.native.native_event_5d0f4014 import query_descriptor
            from civ6_host.runtime.native.native_event_5d0f4014 import encode_record
            fields = decode_fields(raw_fields, self.read)
            descriptor = query_descriptor(self.core, self.context, fields, read=self.read, core_sha256=getattr(self, 'foundation_core_sha256', 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'))
            record = encode_record(self._sequence + 1, fields, descriptor, thread_hook_present=False, writer_metadata_callback_present=False, padding_policy='zero')
            self._enqueue(record)
            self.emit('native_deferred_host_event_enqueued', dispatch_kind=hex(kind), queue_type='0x98', record_hex=record.hex(), x=fields['x'], y=fields['y'], native_descriptor=descriptor, pending_count=len(self.pending), optional_preprocessing_hook_registered=False, queue_metadata_service_registered=False, unspecified_padding_policy='zero', consumer_validated=False, eligible_for_training=False, native_dispatch_return=0)
            return 0
        if kind == 4067375823:
            from civ6_host.runtime.native.native_event_f26f3acf import decode_fields
            from civ6_host.runtime.native.native_event_f26f3acf import encode_record
            fields = decode_fields(raw_fields, self.read)
            record = encode_record(self._sequence + 1, raw_fields, self.read, thread_hook_present=False, writer_metadata_callback_present=False, padding_policy='zero')
            self._enqueue(record)
            self.emit('native_deferred_host_event_enqueued', dispatch_kind=hex(kind), queue_type='0x100', record_hex=record.hex(), owner=fields['owner'], source_type=fields['source_type'], identifier=fields['identifier'], pending_count=len(self.pending), metadata_flags=4, optional_preprocessing_hook_registered=False, queue_metadata_service_registered=False, unspecified_padding_policy='zero', consumer_validated=False, eligible_for_training=False, native_dispatch_return=0)
            return 0
        if kind == 2979910027:
            from civ6_host.runtime.native.native_event_b19dd18b import decode_fields
            from civ6_host.runtime.native.native_event_b19dd18b import encode_record
            from civ6_host.runtime.native.native_event_b19dd18b import RECORD_TYPE
            from civ6_host.runtime.native.native_event_b19dd18b import RECORD_SIZE
            from civ6_host.runtime.native.native_event_b19dd18b import PROOF_SHA256
            from civ6_host.runtime.native.native_event_b19dd18b import PADDING_POLICY
            from civ6_host.runtime.native.native_deferred_empty_profile import validate_empty_profile_record
            if len(self.pending) >= self.limit:
                raise RuntimeError('Native deferred queue bound exceeded')
            validate_sequence(self._sequence + 1)
            if type(self.entity_listener_count) is not int or self.entity_listener_count != 0:
                raise ValueError('B19DD18B requires actual empty entity listeners')
            shape = bytearray(RECORD_SIZE)
            struct.pack_into('<II', shape, 0, RECORD_SIZE, RECORD_TYPE)
            validate_empty_profile_record(shape, **self.empty_receiver_state)
            fields = decode_fields(raw_fields, self.read)
            record = encode_record(self._sequence + 1, fields, normalizer_transform_present=False, per_thread_hook_present=False, writer_metadata_callback_present=False, entity_listener_count=self.entity_listener_count, padding_policy=PADDING_POLICY, empty_receiver_state=self.empty_receiver_state)
            self._enqueue(record)
            self.emit('native_deferred_host_event_enqueued', dispatch_kind=hex(kind), queue_type=hex(RECORD_TYPE), record_hex=record.hex(), pending_count=len(self.pending), source_proof_sha256=PROOF_SHA256, native_queries_executed=False, entity_listener_count=self.entity_listener_count, metadata_uses_unit_descriptor=True, metadata_uses_city_descriptor=True, unspecified_padding_policy=PADDING_POLICY, empty_receiver_state_verified=True, undefined_value_is_native_default=False, payload_exposed_to_learner=False, consumer_validated=False, eligible_for_training=False, native_dispatch_return=0)
            return 0
        if kind in (3892879390, 2313036916):
            from civ6_host.runtime.native.native_city_descriptor_aliases import decode_fields
            from civ6_host.runtime.native.native_city_descriptor_aliases import encode_record
            from civ6_host.runtime.native.native_city_descriptor_aliases import RECORD_TYPES
            from civ6_host.runtime.native.native_city_descriptor_aliases import RECORD_SIZE
            from civ6_host.runtime.native.native_city_descriptor_aliases import PROOF_SHA256
            from civ6_host.runtime.native.native_city_descriptor_aliases import PADDING_POLICY
            from civ6_host.runtime.native.native_deferred_empty_profile import validate_empty_profile_record
            if len(self.pending) >= self.limit:
                raise RuntimeError('Native deferred queue bound exceeded')
            validate_sequence(self._sequence + 1)
            if type(self.entity_listener_count) is not int or self.entity_listener_count != 0:
                raise ValueError('City descriptor aliases require actual empty entity listeners')
            shape = bytearray(RECORD_SIZE)
            struct.pack_into('<II', shape, 0, RECORD_SIZE, RECORD_TYPES[kind])
            validate_empty_profile_record(shape, **self.empty_receiver_state)
            fields = decode_fields(kind, raw_fields, self.read)
            record = encode_record(kind, self._sequence + 1, fields, normalizer_transform_present=False, per_thread_hook_present=False, writer_metadata_callback_present=False, entity_listener_count=self.entity_listener_count, padding_policy=PADDING_POLICY, empty_receiver_state=self.empty_receiver_state)
            self._enqueue(record)
            self.emit('native_deferred_host_event_enqueued', dispatch_kind=hex(kind), queue_type=hex(RECORD_TYPES[kind]), record_hex=record.hex(), pending_count=len(self.pending), source_proof_sha256=PROOF_SHA256, native_queries_executed=False, entity_listener_count=self.entity_listener_count, metadata_uses_city_descriptor=False, unspecified_padding_policy=PADDING_POLICY, empty_receiver_state_verified=True, undefined_value_is_native_default=False, payload_exposed_to_learner=False, consumer_validated=False, eligible_for_training=False, native_dispatch_return=0)
            return 0
        if kind in (902065822, 1716139958, 2603175280):
            from civ6_host.runtime.native.native_simple_unit_aliases import decode_fields
            from civ6_host.runtime.native.native_simple_unit_aliases import encode_record
            from civ6_host.runtime.native.native_simple_unit_aliases import RECORD_TYPES
            from civ6_host.runtime.native.native_simple_unit_aliases import RECORD_SIZES
            from civ6_host.runtime.native.native_simple_unit_aliases import PROOF_SHA256
            from civ6_host.runtime.native.native_simple_unit_aliases import PADDING_POLICY
            from civ6_host.runtime.native.native_deferred_empty_profile import validate_empty_profile_record
            if len(self.pending) >= self.limit:
                raise RuntimeError('Native deferred queue bound exceeded')
            validate_sequence(self._sequence + 1)
            if type(self.entity_listener_count) is not int or self.entity_listener_count != 0:
                raise ValueError('Simple unit aliases require actual empty entity listeners')
            shape = bytearray(RECORD_SIZES[kind])
            struct.pack_into('<II', shape, 0, len(shape), RECORD_TYPES[kind])
            validate_empty_profile_record(shape, **self.empty_receiver_state)
            fields = decode_fields(kind, raw_fields, self.read)
            record = encode_record(kind, self._sequence + 1, fields, normalizer_transform_present=False, per_thread_hook_present=False, writer_metadata_callback_present=False, entity_listener_count=self.entity_listener_count, padding_policy=PADDING_POLICY, empty_receiver_state=self.empty_receiver_state)
            self._enqueue(record)
            self.emit('native_deferred_host_event_enqueued', dispatch_kind=hex(kind), queue_type=hex(RECORD_TYPES[kind]), record_hex=record.hex(), pending_count=len(self.pending), source_proof_sha256=PROOF_SHA256, native_queries_executed=False, entity_listener_count=self.entity_listener_count, unspecified_padding_policy=PADDING_POLICY, empty_receiver_state_verified=True, undefined_value_is_native_default=False, payload_exposed_to_learner=False, consumer_validated=False, eligible_for_training=False, native_dispatch_return=0)
            return 0
        if kind in (1712392665, 1265909993):
            from civ6_host.runtime.native.native_unit_value_event_family import decode_fields
            from civ6_host.runtime.native.native_unit_value_event_family import encode_record
            from civ6_host.runtime.native.native_unit_value_event_family import RECORD_TYPES
            from civ6_host.runtime.native.native_unit_value_event_family import PROOF_SHA256
            from civ6_host.runtime.native.native_unit_value_event_family import PADDING_POLICY
            if len(self.pending) >= self.limit:
                raise RuntimeError('Native deferred queue bound exceeded')
            validate_sequence(self._sequence + 1)
            fields = decode_fields(raw_fields, self.read)
            record = encode_record(kind, self._sequence + 1, fields, normalizer_transform_present=False, per_thread_hook_present=False, writer_metadata_callback_present=False, entity_listener_count=self.entity_listener_count, padding_policy=PADDING_POLICY, empty_receiver_state=self.empty_receiver_state)
            self._enqueue(record)
            self.emit('native_deferred_host_event_enqueued', dispatch_kind=hex(kind), queue_type=hex(RECORD_TYPES[kind]), record_hex=record.hex(), pending_count=len(self.pending), source_proof_sha256=PROOF_SHA256, native_queries_executed=False, normalizer_transform_present=False, optional_preprocessing_hook_registered=False, queue_metadata_service_registered=False, entity_listener_count=self.entity_listener_count, unspecified_padding_policy=PADDING_POLICY, empty_receiver_state_verified=True, undefined_value_is_native_default=False, payload_exposed_to_learner=False, consumer_validated=False, eligible_for_training=False, native_dispatch_return=0)
            return 0
        if kind == 4236097886:
            from civ6_host.runtime.native.native_event_fc7db95e import decode_fields
            from civ6_host.runtime.native.native_event_fc7db95e import encode_record
            from civ6_host.runtime.native.native_event_fc7db95e import PROOF_SHA256
            from civ6_host.runtime.native.native_event_fc7db95e import PADDING_POLICY
            from civ6_host.runtime.native.native_event_fc7db95e import D6_KEY
            from civ6_host.runtime.native.native_event_fc7db95e import A1FBC_KEY
            if len(self.pending) >= self.limit:
                raise RuntimeError('Native deferred queue bound exceeded')
            validate_sequence(self._sequence + 1)
            fields = decode_fields(raw_fields, self.read)
            record = encode_record(self._sequence + 1, fields, normalizer_transform_present=False, per_thread_hook_present=False, writer_metadata_callback_present=False, entity_listener_count=self.entity_listener_count, padding_policy=PADDING_POLICY, empty_receiver_state=self.empty_receiver_state)
            self._enqueue(record)
            self.emit('native_deferred_host_event_enqueued', dispatch_kind=hex(kind), queue_type='0x48', record_hex=record.hex(), pending_count=len(self.pending), source_proof_sha256=PROOF_SHA256, native_queries_executed=False, normalizer_transform_present=False, optional_preprocessing_hook_registered=False, queue_metadata_service_registered=False, entity_listener_count=self.entity_listener_count, unspecified_padding_policy=PADDING_POLICY, empty_receiver_state_verified=True, source_initialized_absent_scalar_keys=[hex(k) for k in (D6_KEY, A1FBC_KEY) if k not in raw_fields], undefined_value_is_native_default=False, payload_exposed_to_learner=False, consumer_validated=False, eligible_for_training=False, native_dispatch_return=0)
            return 0
        if kind == 1914843435:
            from civ6_host.runtime.native.native_event_7222312b import decode_fields
            from civ6_host.runtime.native.native_event_7222312b import encode_record
            from civ6_host.runtime.native.native_event_7222312b import PROOF_SHA256
            from civ6_host.runtime.native.native_event_7222312b import PADDING_POLICY
            from civ6_host.runtime.native.native_deferred_empty_profile import validate_empty_profile_record
            if len(self.pending) >= self.limit:
                raise RuntimeError('Native deferred queue bound exceeded')
            if type(self._sequence) is not int or not 0 <= self._sequence < 2147483647:
                raise ValueError('7222312B requires a bounded native diagnostic sequence')
            if type(self.entity_listener_count) is not int or self.entity_listener_count != 0:
                raise ValueError('7222312B requires actual empty entity listeners')
            shape = bytearray(112)
            struct.pack_into('<II', shape, 0, 112, 38)
            validate_empty_profile_record(shape, **self.empty_receiver_state)
            fields = decode_fields(raw_fields, self.read)
            record = encode_record(self._sequence + 1, fields, normalizer_transform_present=False, per_thread_hook_present=False, writer_metadata_callback_present=False, entity_listener_count=self.entity_listener_count, padding_policy=PADDING_POLICY, empty_receiver_state=self.empty_receiver_state)
            self._enqueue(record)
            self.emit('native_deferred_host_event_enqueued', dispatch_kind=hex(kind), queue_type='0x26', record_hex=record.hex(), pending_count=len(self.pending), first_owner=fields.first_owner, first_id=fields.first_id, second_owner=fields.second_owner, second_id=fields.second_id, source_selector=hex(fields.selector), source_selector_consumed=False, source_proof_sha256=PROOF_SHA256, native_queries_executed=False, normalizer_transform_present=False, optional_preprocessing_hook_registered=False, queue_metadata_service_registered=False, entity_listener_count=self.entity_listener_count, unspecified_padding_policy=PADDING_POLICY, empty_receiver_state_verified=True, undefined_value_is_native_default=False, payload_exposed_to_learner=False, consumer_validated=False, eligible_for_training=False, native_dispatch_return=0)
            return 0
        if kind == 1967963419:
            from civ6_host.runtime.native import native_event_754cbd1b as event_codec
            from civ6_host.runtime.native import native_event_754cbd1b_city as district_codec
            district_shape = type(raw_fields) is dict and frozenset(raw_fields) == district_codec.FIELD_KEYS
            if district_shape:
                event_codec = district_codec
                from civ6_host.runtime.native.native_deferred_empty_profile import validate_empty_profile_record
                from civ6_host.runtime.native.native_absent_305c2e09 import REGISTRY_PROFILE
                if getattr(self, 'normalizer_transform_present', None) is not False or getattr(self, 'dynamic_event_registration_present', None) is not False or getattr(self, 'callback_registry_profile', None) != REGISTRY_PROFILE:
                    raise ValueError('754CBD1B district source requires the actual closed callback profile')
                if type(self.entity_listener_count) is not int or self.entity_listener_count != 0:
                    raise ValueError('754CBD1B district profile requires actual empty entity listeners')
                shape = bytearray(district_codec.RECORD_SIZE)
                struct.pack_into('<II', shape, 0, district_codec.RECORD_SIZE, district_codec.RECORD_TYPE)
                validate_empty_profile_record(shape, **self.empty_receiver_state)
            if len(self.pending) >= self.limit:
                raise RuntimeError('Native deferred queue bound exceeded')
            validate_sequence(self._sequence + 1)
            fields = event_codec.decode_fields(raw_fields, self.read)
            record = event_codec.encode_record(self._sequence + 1, fields, normalizer_transform_present=False, per_thread_hook_present=False, writer_metadata_callback_present=False, entity_listener_count=self.entity_listener_count, padding_policy=event_codec.PADDING_POLICY, empty_receiver_state=self.empty_receiver_state)
            source_fields = {'source_field_profile': district_codec.SOURCE_FIELD_PROFILE, 'source_district_descriptor': [fields.district_owner, 3, fields.district_id], 'source_second_unit_descriptor_default': True} if district_shape else {}
            self._enqueue(record)
            self.emit('native_deferred_host_event_enqueued', dispatch_kind=hex(kind), queue_type='0x1e', record_hex=record.hex(), pending_count=len(self.pending), source_proof_sha256=event_codec.PROOF_SHA256, native_queries_executed=False, normalizer_transform_present=False, optional_preprocessing_hook_registered=False, queue_metadata_service_registered=False, entity_listener_count=self.entity_listener_count, unspecified_padding_policy=event_codec.PADDING_POLICY, empty_receiver_state_verified=True, undefined_value_is_native_default=False, payload_exposed_to_learner=False, consumer_validated=False, eligible_for_training=False, native_dispatch_return=0, **source_fields)
            return 0
        if kind in (2638488821, 1467939621, 473910965, 4178559211, 4061177196, 895056929, 3058947620, 4202025642, 993573825, 2691445918):
            from civ6_host.runtime.native.native_unit_descriptor_event_family import decode_fields
            from civ6_host.runtime.native.native_unit_descriptor_event_family import encode_record
            from civ6_host.runtime.native.native_unit_descriptor_event_family import RECORD_TYPES
            from civ6_host.runtime.native.native_unit_descriptor_event_family import PROOF_SHA256
            from civ6_host.runtime.native.native_unit_descriptor_event_family import PADDING_POLICY
            if len(self.pending) >= self.limit:
                raise RuntimeError('Native deferred queue bound exceeded')
            validate_sequence(self._sequence + 1)
            fields = decode_fields(raw_fields, self.read)
            record = encode_record(kind, self._sequence + 1, fields, normalizer_transform_present=False, per_thread_hook_present=False, writer_metadata_callback_present=False, entity_listener_count=self.entity_listener_count, padding_policy=PADDING_POLICY, empty_receiver_state=self.empty_receiver_state)
            self._enqueue(record)
            self.emit('native_deferred_host_event_enqueued', dispatch_kind=hex(kind), queue_type=hex(RECORD_TYPES[kind]), record_hex=record.hex(), pending_count=len(self.pending), source_proof_sha256=PROOF_SHA256, native_queries_executed=False, normalizer_transform_present=False, optional_preprocessing_hook_registered=False, queue_metadata_service_registered=False, entity_listener_count=self.entity_listener_count, unspecified_padding_policy=PADDING_POLICY, empty_receiver_state_verified=True, undefined_value_is_native_default=False, payload_exposed_to_learner=False, consumer_validated=False, eligible_for_training=False, native_dispatch_return=0)
            return 0
        if kind in (3635281265, 2397249135, 675466772, 2454269782, 3918721997, 2314915267, 2620687093):
            if kind == 2620687093:
                from civ6_host.runtime.native.native_event_9c3482f5 import decode_fields
                from civ6_host.runtime.native.native_event_9c3482f5 import encode_record
                from civ6_host.runtime.native.native_event_9c3482f5 import RECORD_TYPE
            elif kind == 3918721997:
                from civ6_host.runtime.native.native_event_e992f3cd import decode_fields
                from civ6_host.runtime.native.native_event_e992f3cd import encode_record
                from civ6_host.runtime.native.native_event_e992f3cd import RECORD_TYPE
            elif kind == 3635281265:
                from civ6_host.runtime.native.native_event_d8adfd71 import decode_fields
                from civ6_host.runtime.native.native_event_d8adfd71 import encode_record
                from civ6_host.runtime.native.native_event_d8adfd71 import RECORD_TYPE
            elif kind == 2397249135:
                from civ6_host.runtime.native.native_event_8ee31e6f import decode_fields
                from civ6_host.runtime.native.native_event_8ee31e6f import encode_record
                from civ6_host.runtime.native.native_event_8ee31e6f import RECORD_TYPE
            elif kind == 2314915267:
                from civ6_host.runtime.native.native_event_89facdc3 import decode_fields
                from civ6_host.runtime.native.native_event_89facdc3 import encode_record
                from civ6_host.runtime.native.native_event_89facdc3 import RECORD_TYPE
            elif kind == 675466772:
                from civ6_host.runtime.native.native_event_2842ce14 import decode_fields
                from civ6_host.runtime.native.native_event_2842ce14 import encode_record
                from civ6_host.runtime.native.native_event_2842ce14 import RECORD_TYPE
            else:
                from civ6_host.runtime.native.native_event_92492f56 import decode_fields
                from civ6_host.runtime.native.native_event_92492f56 import encode_record
                from civ6_host.runtime.native.native_event_92492f56 import RECORD_TYPE
            fields = decode_fields(raw_fields, self.read)
            undefined = kind == 675466772 and fields.scalar_38f_value is None
            options = {'undefined_normalized_value_policy': 'zero-unread-empty-receiver-payload', 'empty_receiver_state': self.empty_receiver_state} if undefined else {}
            record = encode_record(self._sequence + 1, fields, normalizer_transform_present=False, per_thread_hook_present=False, writer_metadata_callback_present=False, padding_policy='headless-zero-uninitialized-stack', **options)
            if kind == 2620687093:
                from civ6_host.runtime.native.native_deferred_empty_profile import validate_empty_profile_record
                validate_empty_profile_record(record, **self.empty_receiver_state)
            self._enqueue(record)
            self.emit('native_deferred_host_event_enqueued', dispatch_kind=hex(kind), queue_type=hex(RECORD_TYPE), record_hex=record.hex(), pending_count=len(self.pending), native_queries_executed=False, unspecified_padding_policy='zero', undefined_normalized_field=undefined, undefined_value_is_native_default=False, payload_exposed_to_learner=False, empty_receiver_state_verified=undefined or kind == 2620687093, consumer_validated=False, eligible_for_training=False, native_dispatch_return=0)
            return 0
        if kind == 39808253:
            from civ6_host.runtime.native.native_event_025f6cfd import decode_fields
            from civ6_host.runtime.native.native_event_025f6cfd import encode_record_candidate
            from civ6_host.runtime.native.native_event_025f6cfd import DESCRIPTOR_KEY
            from civ6_host.runtime.native.native_deferred_empty_profile import validate_empty_profile_record
            descriptor = copy_eight_byte_variant(raw_fields[DESCRIPTOR_KEY], self.read, expected_tag=1024)
            fields = decode_fields(raw_fields, {DESCRIPTOR_KEY: {'byte_count': 8, 'bytes_hex': descriptor.hex()}})
            record = encode_record_candidate(self._sequence + 1, fields, normalizer_transform_present=False, per_thread_hook_present=False, writer_callback_present=False, padding_policy='zero-uninitialized-record-candidate')
            validate_empty_profile_record(record, **self.empty_receiver_state)
            self._enqueue(record)
            self.emit('native_deferred_host_event_enqueued', dispatch_kind=hex(kind), queue_type='0x101', record_hex=record.hex(), pending_count=len(self.pending), native_queries_executed=False, empty_receiver_state_verified=True, descriptor_hex=descriptor.hex(), raw_boolean_byte=fields.raw_boolean_byte, unspecified_padding_policy='zero-uninitialized-stack', consumer_validated=False, eligible_for_training=False, native_dispatch_return=0)
            return 0
        if kind == 2271638628:
            from civ6_host.runtime.native.native_event_87667464 import decode_fields
            from civ6_host.runtime.native.native_event_87667464 import encode_record
            fields = decode_fields(raw_fields)
            record = encode_record(self._sequence + 1, fields, per_thread_hook_present=False, queue_hook_present=False, padding_policy='zero-unread-empty-subscriber-record', empty_receiver_state=self.empty_receiver_state)
            self._enqueue(record)
            self.emit('native_deferred_host_event_enqueued', dispatch_kind=hex(kind), queue_type='0xc0', record_hex=record.hex(), pending_count=len(self.pending), native_queries_executed=False, empty_receiver_state_verified=True, unspecified_padding_policy='zero', consumer_validated=False, eligible_for_training=False, native_dispatch_return=0)
            return 0
        if kind == 1294624025:
            from civ6_host.runtime.native.native_event_4d2a6519 import decode_fields
            from civ6_host.runtime.native.native_event_4d2a6519 import encode_record
            fields = decode_fields(raw_fields, self.read)
            undefined = fields.value_38f is None
            options = {'undefined_normalized_value_policy': 'zero-unread-empty-receiver-payload', 'empty_receiver_state': self.empty_receiver_state} if undefined else {}
            record = encode_record(self._sequence + 1, fields, normalizer_transform_present=False, per_thread_hook_present=False, writer_metadata_callback_present=False, padding_policy='headless-zero-uninitialized-stack', **options)
            self._enqueue(record)
            self.emit('native_deferred_host_event_enqueued', dispatch_kind=hex(kind), queue_type='0x61', record_hex=record.hex(), pending_count=len(self.pending), native_queries_executed=False, undefined_normalized_field=undefined, undefined_value_is_native_default=False, payload_exposed_to_learner=False, empty_receiver_state_verified=undefined, consumer_validated=False, eligible_for_training=False, native_dispatch_return=0)
            return 0
        if kind == 2551878022 and set(raw_fields) == {2716180809, 4032072631}:
            from civ6_host.runtime.native.native_event_981a9186_short import encode_record
            from civ6_host.runtime.native.native_event_981a9186_short import PINNED_EVIDENCE_SHA256
            from civ6_host.runtime.native.native_event_981a9186_short import SELECTOR_PROOF_SHA256
            if len(self.pending) >= self.limit:
                raise RuntimeError('Native deferred queue bound exceeded')
            if type(self._sequence) is not int or not 0 <= self._sequence < 2147483647:
                raise ValueError('UnitActivate sequence exceeds bounded native range')
            record = encode_record(self._sequence + 1, raw_fields, self.read, normalizer_transform_present=False, entity_listener_count=self.entity_listener_count, per_thread_hook_present=False, writer_metadata_callback_present=False, empty_receiver_state=self.empty_receiver_state, padding_policy='zero-unread-empty-receiver-payload')
            self._enqueue(record)
            self.emit('native_deferred_host_event_enqueued', dispatch_kind=hex(kind), queue_type='0x49', record_hex=record.hex(), pending_count=len(self.pending), input_profile='unit-activate-two-key', source_selector=hex(struct.unpack_from('<I', record, 104)[0]), owner=struct.unpack_from('<H', record, 88)[0], unit_id=struct.unpack_from('<I', record, 92)[0], raw_boolean_byte=None, boolean_source_initialized=False, position_source_initialized=True, unspecified_padding_policy='zero-unread-empty-receiver-payload', empty_receiver_state_verified=True, payload_exposed_to_learner=False, undefined_value_is_native_default=False, native_queries_executed=False, source_proof_sha256=PINNED_EVIDENCE_SHA256, selector_source_proof_sha256=SELECTOR_PROOF_SHA256, consumer_validated=False, eligible_for_training=False, native_dispatch_return=0)
            return 0
        if kind == 2551878022:
            from civ6_host.runtime.native.native_event_981a9186 import decode_fields
            from civ6_host.runtime.native.native_event_981a9186 import encode_record
            fields = decode_fields(raw_fields, self.read)
            record = encode_record(self._sequence + 1, fields, normalizer_transform_present=False, per_thread_hook_present=False, writer_metadata_callback_present=False, padding_policy='headless-zero-uninitialized-stack')
            self._enqueue(record)
            self.emit('native_deferred_host_event_enqueued', dispatch_kind=hex(kind), queue_type='0x49', record_hex=record.hex(), pending_count=len(self.pending), owner=fields.owner, unit_id=fields.item_id, raw_boolean_byte=fields.raw_boolean_byte, native_queries_executed=False, unspecified_padding_policy='zero', consumer_validated=False, eligible_for_training=False, native_dispatch_return=0)
            return 0
        if kind in (3254088469, 1289970298):
            from civ6_host.runtime.native.native_event_c1f57315 import encode_record
            record = encode_record(self._sequence + 1, raw_fields, self.read, normalizer_transform_present=False, thread_hook_present=False, writer_metadata_callback_present=False, empty_receiver_state=self.empty_receiver_state, padding_policy='zero-unread-empty-receiver-payload')
            self._enqueue(record)
            self.emit('native_deferred_host_event_enqueued', dispatch_kind=hex(kind), queue_type='0xa4', record_hex=record.hex(), pending_count=len(self.pending), normalizer_transform_present=False, optional_preprocessing_hook_registered=False, queue_metadata_service_registered=False, consumer_validated=False, undefined_stack_range='record+0x54..0x57', undefined_value_policy='zero-unread-empty-receiver-payload', empty_receiver_state_verified=True, undefined_value_is_native_default=False, payload_exposed_to_learner=False, native_queries_executed=False, eligible_for_training=False, native_dispatch_return=0)
            return 0
        if kind == 1448787494:
            from civ6_host.runtime.native.native_event_565abe26 import encode_record
            record = encode_record(self._sequence + 1, raw_fields, thread_hook_present=False, writer_metadata_callback_present=False, empty_receiver_state=self.empty_receiver_state)
            self._enqueue(record)
            self.emit('native_deferred_host_event_enqueued', dispatch_kind=hex(kind), queue_type='0xc3', record_hex=record.hex(), pending_count=len(self.pending), empty_receiver_state_verified=True, native_queries_executed=False, source_payload_bytes=12, padding_origin='native-zero-allocation', eligible_for_training=False, native_dispatch_return=0)
            return 0
        if kind == 4129408428:
            from civ6_host.runtime.native.native_event_f621c5ac import encode_record
            from civ6_host.runtime.native.native_deferred_empty_profile import validate_empty_profile_record
            record = encode_record(self._sequence + 1, raw_fields, thread_hook_present=False, writer_metadata_callback_present=False, empty_receiver_profile=True, padding_policy='headless-zero-uninitialized-stack')
            validate_empty_profile_record(record, **self.empty_receiver_state)
            self._enqueue(record)
            self.emit('native_deferred_host_event_enqueued', dispatch_kind=hex(kind), queue_type='0xbc', record_hex=record.hex(), pending_count=len(self.pending), empty_receiver_state_verified=True, native_queries_executed=False, unspecified_padding_policy='zero-uninitialized-stack', eligible_for_training=False, native_dispatch_return=0)
            return 0
        if kind == 830651534:
            if 3606901732 in raw_fields and decode_scalar(raw_fields[3606901732], 2) == 3:
                return self._enqueue_project_completion(raw_fields)
            from civ6_host.runtime.native.native_event_3182bc8e import decode_fields
            from civ6_host.runtime.native.native_event_3182bc8e import encode_record
            from civ6_host.runtime.native.native_deferred_empty_profile import validate_empty_profile_record
            shape = bytearray(112)
            struct.pack_into('<II', shape, 0, 112, 96)
            validate_empty_profile_record(shape, **self.empty_receiver_state)
            fields = decode_fields(raw_fields, self.read)
            value_policy = 'zero-unread-empty-receiver-payload' if fields.normalized_58 is None else 'native-initialized-field'
            record = encode_record(self._sequence + 1, fields, normalizer_transform_present=False, thread_hook_present=False, writer_metadata_callback_present=False, padding_policy='zero', empty_receiver_profile=True, undefined_normalized_value_policy=value_policy)
            self._enqueue(record)
            self.emit('native_deferred_host_event_enqueued', dispatch_kind=hex(kind), queue_type='0x60', record_hex=record.hex(), pending_count=len(self.pending), extended_branch_entered=False, undefined_normalized_field='+0x58' if fields.normalized_58 is None else None, native_normalized_58=fields.normalized_58, undefined_value_policy=value_policy, undefined_value_is_native_default=False, empty_receiver_state_verified=True, payload_exposed_to_learner=False, unspecified_padding_policy='zero', consumer_validated=False, eligible_for_training=False, native_dispatch_return=0)
            return 0
        if kind == 3865055911:
            if 2716180809 in raw_fields and decode_scalar(raw_fields[2716180809], 3) == 1362298481:
                return self._enqueue_e660_building_pillaged(raw_fields)
            from civ6_host.runtime.native.native_event_e66012a7 import decode_fields
            from civ6_host.runtime.native.native_event_e66012a7 import produce_records
            from civ6_host.runtime.native.native_deferred_empty_profile import validate_empty_profile_record
            if not self.ui_cache_callbacks_enabled:
                raise RuntimeError('E66012A7 requires the initialized active-game diagnostic phase')
            fields = decode_fields(raw_fields, self.read)
            queries = []

            def enqueue_source_record(record):
                validate_empty_profile_record(record, **self.empty_receiver_state)
                self._enqueue(record)
                self.emit('native_deferred_host_event_enqueued', dispatch_kind=hex(kind), queue_type=hex(struct.unpack_from('<I', record, 4)[0]), record_hex=record.hex(), pending_count=len(self.pending), native_queries_executed=True, active_context_branch_executed=True, district_type_queries=list(queries), original_exe_manager_lifecycle_reproduced=False, unspecified_padding_policy='zero', consumer_validated=False, eligible_for_training=False, native_dispatch_return=0)
            produce_records(self._sequence + 1, self.core, self.context, fields, active_context_present=True, normalizer_transform_present=False, thread_hook_present=False, writer_metadata_callback_present=False, padding_policy='zero', read=self.read, diagnostics=queries, record_sink=enqueue_source_record, wonder_handler=self._enqueue_wonder_completion, core_sha256=getattr(self, 'foundation_core_sha256', 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'))
            return 0
        if kind == 3007926567:
            from civ6_host.runtime.native.native_event_b3495127 import decode_fields
            from civ6_host.runtime.native.native_event_b3495127 import produce_record_lease
            fields = decode_fields(raw_fields)
            diagnostic = {}
            with produce_record_lease(self._sequence + 1, self.core, self.context, fields, normalizer_transform_present=False, per_thread_hook_present=False, writer_metadata_callback_present=False, read=self.read, query_diagnostic=diagnostic, core_sha256=getattr(self, 'placement_core_sha256', 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3')) as record:
                if record is not None:
                    self._enqueue(record)
            if record is not None:
                self.emit('native_deferred_host_event_enqueued', dispatch_kind=hex(kind), queue_type='0xc2', record_hex=record.hex(), player_id=fields.player_id, pending_count=len(self.pending), native_query=diagnostic, retained_sources_live_at_enqueue=True, consumer_validated=False, eligible_for_training=False, native_dispatch_return=0)
            else:
                self.emit('native_deferred_host_event_source_null_branch', dispatch_kind=hex(kind), native_query=diagnostic, record_produced=False, eligible_for_training=False, native_dispatch_return=0)
            return 0
        if kind == 1854549907:
            from civ6_host.runtime.native.native_event_6e8a2f93 import decode_fields
            from civ6_host.runtime.native.native_event_6e8a2f93 import encode_record
            from civ6_host.runtime.native.native_event_6e8a2f93 import pack_float32_bits
            from civ6_host.runtime.native.native_deferred_empty_profile import validate_empty_profile_record
            fields = decode_fields(raw_fields, self.read)
            record = encode_record(self._sequence + 1, fields, normalizer_transform_present=False, per_thread_hook_present=False, writer_metadata_callback_present=False, padding_policy='headless-zero-uninitialized-stack')
            validate_empty_profile_record(record, **self.empty_receiver_state)
            self._enqueue(record)
            self.emit('native_deferred_host_event_enqueued', dispatch_kind=hex(kind), queue_type='0x1b', record_hex=record.hex(), owner=fields.owner, unit_id=fields.item_id, value_bits=fields.value_bits, packed_value=pack_float32_bits(fields.value_bits), pending_count=len(self.pending), native_queries_executed=False, empty_receiver_state_verified=True, unspecified_padding_policy='zero-uninitialized-stack', consumer_validated=False, eligible_for_training=False, native_dispatch_return=0)
            return 0
        if kind == 1853815079:
            from civ6_host.runtime.native.native_event_6e7ef927 import decode_fields
            from civ6_host.runtime.native.native_event_6e7ef927 import produce_record_lease
            fields = decode_fields(raw_fields, self.read)
            diagnostic = {}
            with produce_record_lease(self._sequence + 1, self.core, self.context, fields, normalizer_transform_present=False, per_thread_hook_present=False, writer_metadata_callback_present=False, padding_policy='headless-zero-uninitialized-stack', read=self.read, query_diagnostic=diagnostic, core_sha256=getattr(self, 'turn_unit_core_sha256', 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3')) as record:
                self._enqueue(record)
            self.emit('native_deferred_host_event_enqueued', dispatch_kind=hex(kind), queue_type='0x18', record_hex=record.hex(), owner=fields.owner, unit_id=fields.item_id, position_hex=fields.position_bytes.hex(), pending_count=len(self.pending), native_query=diagnostic, retained_sources_live_at_enqueue=diagnostic['unit_present'], unspecified_padding_policy='zero-uninitialized-stack', consumer_validated=False, eligible_for_training=False, native_dispatch_return=0)
            return 0
        if kind == 3188855816:
            from civ6_host.runtime.native.native_event_be121408 import decode_fields
            from civ6_host.runtime.native.native_event_be121408 import encode_record
            fields = decode_fields(raw_fields, self.read)
            record = encode_record(self._sequence + 1, fields, normalizer_transform_present=False, per_thread_hook_present=False, writer_metadata_callback_present=False, **self.empty_receiver_state, padding_policy='headless-empty-unitmoved-zero-unread-stack-gaps')
            self._enqueue(record)
            self.emit('native_deferred_host_event_enqueued', dispatch_kind=hex(kind), queue_type='0x17', record_hex=record.hex(), unit_descriptor_hex=fields.unit_descriptor.hex(), x=fields.x, y=fields.y, pending_count=len(self.pending), native_queries_executed=False, empty_receiver_required=True, unspecified_padding_policy='zero-unread-stack-gaps', consumer_validated=False, eligible_for_training=False, native_dispatch_return=0)
            return 0
        if kind == 4260438819:
            from civ6_host.runtime.native.native_event_fdf12323 import decode_fields
            from civ6_host.runtime.native.native_event_fdf12323 import produce_record_lease
            fields = decode_fields(raw_fields, self.read)
            query_diagnostic = {}
            with produce_record_lease(self._sequence + 1, self.core, self.context, fields, normalizer_transform_present=False, per_thread_hook_present=False, writer_metadata_callback_present=False, padding_policy='headless-zero-uninitialized-stack', read=self.read, empty_receiver_state=self.empty_receiver_state, missing_item_policy='zero-unread-item-DWORD', query_diagnostic=query_diagnostic) as record:
                self._enqueue(record)
            self.emit('native_deferred_host_event_enqueued', dispatch_kind=hex(kind), queue_type='0xa0', record_hex=record.hex(), owner=fields.owner, item_id=fields.item_id, pending_count=len(self.pending), **query_diagnostic, retained_item_released=query_diagnostic['item_present'], retained_sources_live_at_enqueue=query_diagnostic['item_present'], unspecified_padding_policy='zero', consumer_validated=False, eligible_for_training=False, native_dispatch_return=0)
            return 0
        if kind == 58334190:
            from civ6_host.runtime.native.native_event_037a1bee import decode_fields
            from civ6_host.runtime.native.native_event_037a1bee import produce_record_lease
            from civ6_host.runtime.native.native_event_037a1bee import POSITIVE_PROOF_SHA256
            from civ6_host.runtime.native.native_deferred_empty_profile import validate_empty_profile_record
            if len(self.pending) >= self.limit:
                raise RuntimeError('Native deferred queue bound exceeded')
            shape = bytearray(144)
            struct.pack_into('<II', shape, 0, 144, 167)
            validate_empty_profile_record(shape, **self.empty_receiver_state)
            fields = decode_fields(raw_fields, self.read)
            index = fields['optional_index']
            queried = index is not None and index < 2147483648
            if queried and (not self.ui_cache_callbacks_enabled):
                raise ValueError('037A1BEE positive query requires the initialized native map facade')
            with produce_record_lease(self._sequence + 1, self.core, self.context, fields, notification_counter=self.host_notification_counter, normalizer_transform_present=False, thread_hook_present=False, writer_metadata_callback_present=False, padding_policy='zero', read=self.read, core_sha256=getattr(self, 'foundation_core_sha256', 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3')) as record:
                validate_empty_profile_record(record, **self.empty_receiver_state)
                self._enqueue(record)
            self.emit('native_deferred_host_event_enqueued', dispatch_kind=hex(kind), queue_type='0xa7', record_hex=record.hex(), pending_count=len(self.pending), native_queries_executed=True, optional_query_fields_absent=fields['optional_fields_absent'], retained_plot_live_at_enqueue=True, plot_released_after_enqueue=True, unspecified_padding_policy='zero', consumer_validated=False, eligible_for_training=False, native_dispatch_return=0)
            if queried:
                self.emit('native_037a1bee_optional_query_enqueued', dispatch_kind=hex(kind), queue_type='0xa7', optional_map_index=index, source_proof_sha256=POSITIVE_PROOF_SHA256, native_optional_position_hex=record[124:132].hex(), optional_scalar=fields['optional_scalar'], record_sequence=self._sequence, record_sha256=hashlib.sha256(record).hexdigest(), optional_map_released_before_plot_acquisition=True, plot_released_after_enqueue=True, payload_exposed_to_learner=False, consumer_validated=False, eligible_for_training=False)
            return 0
        if kind == 443673072:
            from civ6_host.runtime.native.native_event_great_work import decode_fields
            from civ6_host.runtime.native.native_event_great_work import produce_record_lease
            from civ6_host.runtime.native.native_event_great_work import PROOF_SHA256
            if not self.ui_cache_callbacks_enabled:
                raise ValueError('GreatWorkCreated requires initialized native map services')
            fields, descriptor = decode_fields(raw_fields, self.read)
            with produce_record_lease(self._sequence + 1, self.core, self.context, fields, descriptor, normalizer_transform_present=False, thread_hook_present=False, writer_metadata_callback_present=False, padding_policy='zero-unread-empty-receiver', empty_receiver_state=self.empty_receiver_state, read=self.read) as record:
                self._enqueue(record)
            self.emit('native_deferred_host_event_enqueued', dispatch_kind=hex(kind), queue_type='0xdc', record_hex=record.hex(), pending_count=len(self.pending), source_proof_sha256=PROOF_SHA256, native_plot_snapshot_queried=True, native_plot_retained_through_enqueue=True, plot_released_after_enqueue=True, plot_flag148_called=False, unspecified_padding_policy='zero-unread-empty-receiver', consumer_validated=False, eligible_for_training=False, native_dispatch_return=0)
            return 0
        if kind == 130563502:
            from civ6_host.runtime.native.native_event_07c83dae import decode_fields
            from civ6_host.runtime.native.native_event_07c83dae import produce_record_lease
            fields = decode_fields(raw_fields, self.read)
            with produce_record_lease(self._sequence + 1, self.core, self.context, fields, expected_civilization_hashes=getattr(self.host, 'configured_player_identity_hashes', {}), normalizer_transform_present=False, thread_hook_present=False, writer_metadata_callback_present=False, padding_policy='zero', read=self.read, core_sha256=getattr(self, 'foundation_core_sha256', 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3')) as record:
                self._enqueue(record)
                self.emit('native_deferred_host_event_enqueued', dispatch_kind=hex(kind), queue_type='0xa5', record_hex=record.hex(), pending_count=len(self.pending), native_queries_executed=True, unspecified_padding_policy='zero', native_plot_retained_through_enqueue=True, consumer_validated=False, eligible_for_training=False, native_dispatch_return=0)
            return 0
        if kind == 723230968:
            from civ6_host.runtime.native.native_event_2b1ba0f8 import decode_fields
            from civ6_host.runtime.native.native_event_2b1ba0f8 import produce_record
            fields = decode_fields(raw_fields, self.read)
            identities = getattr(self.host, 'configured_player_identity_hashes', {})
            record = produce_record(self._sequence + 1, self.core, self.context, fields, expected_civilization_hashes=identities, normalizer_transform_present=False, producer_hook_present=False, queue_metadata_service_present=False, padding_policy='headless-zero-uninitialized-callback-stack', read=self.read, core_sha256=getattr(self, 'foundation_core_sha256', 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'))
            self._enqueue(record)
            self.emit('native_deferred_host_event_enqueued', dispatch_kind=hex(kind), queue_type='0x58', record_hex=record.hex(), owner=fields.descriptor_word, pending_count=len(self.pending), native_queries_executed=True, unspecified_padding_policy='zero', consumer_validated=False, eligible_for_training=False, native_dispatch_return=0)
            return 0
        if kind == 4200272217:
            from civ6_host.runtime.native.native_event_fa5b1159 import decode_fields
            from civ6_host.runtime.native.native_event_fa5b1159 import query_callback_values
            from civ6_host.runtime.native.native_event_fa5b1159 import encode_record
            fields = decode_fields(raw_fields, self.read)
            identities = getattr(self.host, 'configured_player_identity_hashes', {})
            first, second, third = query_callback_values(self.core, self.context, fields, expected_civilization_hashes=identities, read=self.read, core_sha256=getattr(self, 'foundation_core_sha256', 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'))
            record = encode_record(self._sequence + 1, fields, plot_value=first, secondary_value=second, civilization_id=third, queue_metadata_service_present=False, producer_hook_present=False, padding_policy='headless-zero-uninitialized-callback-stack')
            self._enqueue(record)
            self.emit('native_deferred_host_event_enqueued', dispatch_kind=hex(kind), queue_type='0x57', record_hex=record.hex(), x=fields.x, y=fields.y, native_plot_owner=first, native_secondary_value=second, civilization_id=third, descriptor_owner=fields.descriptor_word, pending_count=len(self.pending), identity_source='Fresh native setup submap readback', identity_lookup_index_source='Native plot query result', identity_mirror_profile='Existing aliased configuration records 0..63; absent values refused', optional_preprocessing_hook_registered=False, queue_metadata_service_registered=False, unspecified_padding_policy='zero', consumer_validated=False, eligible_for_training=False, native_dispatch_return=0)
            return 0
        if kind == 2599060777:
            from civ6_host.runtime.native.native_event_9aea8529 import decode_fields
            from civ6_host.runtime.native.native_event_9aea8529 import query_plot_word
            from civ6_host.runtime.native.native_event_9aea8529 import encode_scoped_record
            from civ6_host.runtime.native.native_event_9aea8529 import verify_scoped_source_evidence
            from civ6_host.runtime.native.native_event_9aea8529 import SCOPE_PROOF_SHA256
            from civ6_host.runtime.native.native_notification_metadata import metadata_scope_transition
            from civ6_host.runtime.native.native_deferred_empty_profile import validate_empty_profile_record
            verify_scoped_source_evidence()
            metadata_scope_transition(self.host_notification_counter, self.host_metadata_counter)
            if type(self.entity_listener_count) is not int or self.entity_listener_count != 0:
                raise ValueError('ResourceVisibilityChanged requires empty entity listeners')
            if len(self.pending) >= self.limit:
                raise RuntimeError('ResourceVisibilityChanged exceeds native deferred queue bound')
            if type(self._sequence) is not int or not 0 <= self._sequence < 4294967295:
                raise ValueError('ResourceVisibilityChanged sequence exceeds bounded encoder range')
            shape = bytearray(128)
            struct.pack_into('<II', shape, 0, 128, 140)
            validate_empty_profile_record(shape, **self.empty_receiver_state)
            fields = decode_fields(raw_fields, self.read)
            word = query_plot_word(self.core, self.context, fields, read=self.read, core_sha256=getattr(self, 'foundation_core_sha256', 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'))
            before = self.host_metadata_counter
            record, after = encode_scoped_record(self._sequence + 1, fields, word, notification_counter=self.host_notification_counter, metadata_counter=before, thread_hook_present=False, writer_metadata_callback_present=False, padding_policy='zero', core=self.core, context=self.context, read=self.read, core_sha256=getattr(self, 'foundation_core_sha256', 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'))
            validate_empty_profile_record(record, **self.empty_receiver_state)
            self._enqueue(record)
            self.host_metadata_counter = after
            if self.host_notification_counter != 0:
                self.emit('native_notification_metadata_transition', dispatch_kind=hex(kind), sequence=self._sequence, notification_counter=self.host_notification_counter, metadata_before=before, metadata_after=after, metadata_flag=struct.unpack_from('<I', record, 72)[0], source_proof_sha256=SCOPE_PROOF_SHA256, empty_receiver_state_verified=True, eligible_for_training=False)
            self.emit('native_deferred_host_event_enqueued', dispatch_kind=hex(kind), queue_type='0x8c', record_hex=record.hex(), x=fields['x'], y=fields['y'], native_plot_word=word, selector=fields['selector'], descriptor_tail=fields['descriptor_tail'], pending_count=len(self.pending), optional_preprocessing_hook_registered=False, queue_metadata_service_registered=False, unspecified_padding_policy='zero', consumer_validated=False, eligible_for_training=False, native_dispatch_return=0)
            return 0
        if kind == 424708295:
            from civ6_host.runtime.native.native_event_195088c7 import decode_fields
            from civ6_host.runtime.native.native_event_195088c7 import query_plot_word
            from civ6_host.runtime.native.native_event_195088c7 import encode_record
            from civ6_host.runtime.native.native_event_195088c7 import verify_notification_scope
            from civ6_host.runtime.native.native_event_195088c7 import SCOPE_PROOF_SHA256
            from civ6_host.runtime.native.native_deferred_empty_profile import validate_empty_profile_record
            verify_notification_scope(self.host_notification_counter, self.host_metadata_counter)
            if type(self.entity_listener_count) is not int or self.entity_listener_count != 0:
                raise ValueError('ResourceAddedToMap requires empty entity listeners')
            if len(self.pending) >= self.limit:
                raise RuntimeError('ResourceAddedToMap exceeds native deferred queue bound')
            if type(self._sequence) is not int or not 0 <= self._sequence < 2147483647:
                raise ValueError('ResourceAddedToMap sequence exceeds bounded encoder range')
            shape = bytearray(96)
            struct.pack_into('<II', shape, 0, 96, 138)
            validate_empty_profile_record(shape, **self.empty_receiver_state)
            fields = decode_fields(raw_fields, self.read)
            word = query_plot_word(self.core, self.context, fields, read=self.read, core_sha256=getattr(self, 'foundation_core_sha256', 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'))
            record = encode_record(self._sequence + 1, fields, word, thread_hook_present=False, writer_metadata_callback_present=False)
            validate_empty_profile_record(record, **self.empty_receiver_state)
            self._enqueue(record)
            if self.host_notification_counter != 0:
                self.emit('native_notification_metadata_transition', dispatch_kind=hex(kind), sequence=self._sequence, notification_counter=self.host_notification_counter, metadata_before=self.host_metadata_counter, metadata_after=self.host_metadata_counter, metadata_flag=0, source_proof_sha256=SCOPE_PROOF_SHA256, counter_independent_producer=True, empty_receiver_state_verified=True, eligible_for_training=False)
            self.emit('native_deferred_host_event_enqueued', dispatch_kind=hex(kind), queue_type='0x8a', record_hex=record.hex(), x=fields['x'], y=fields['y'], native_plot_word=word, selector=fields['selector'], pending_count=len(self.pending), optional_preprocessing_hook_registered=False, queue_metadata_service_registered=False, consumer_validated=False, eligible_for_training=False, native_dispatch_return=0)
            return 0
        if kind == 643323895:
            from civ6_host.runtime.native.native_event_265857f7 import encode_record_with_fields
            record, fields = encode_record_with_fields(self._sequence + 1, raw_fields, self.read, thread_hook_present=False, writer_metadata_callback_present=False, normalizer_transform_present=False)
            self._enqueue(record)
            self._finish_counter_neutral_event(kind, record, neutral_scope)
            if 'variant_evidence_sha256' in fields:
                self.emit('native_event_265857f7_typed_position_enqueued', dispatch_kind=hex(kind), sequence=self._sequence, record_hex=record.hex(), ignored_argument=fields['ignored_argument'], selector=fields['selector'], source_proof_sha256=fields['variant_evidence_sha256'], copied_bytes=8, normalizer_transform_present=False, gameplay_rules_modified=False, eligible_for_training=False)
            self.emit('native_deferred_host_event_enqueued', dispatch_kind=hex(kind), queue_type='0x8d', record_hex=record.hex(), blob_hex=fields['blob_bytes'].hex(), selector=fields['selector'], pending_count=len(self.pending), optional_preprocessing_hook_registered=False, queue_metadata_service_registered=False, consumer_validated=False, eligible_for_training=False, native_dispatch_return=0)
            return 0
        if kind in (477734356, 2175010909):
            from civ6_host.runtime.native.native_victory_notifications import decode_fields
            from civ6_host.runtime.native.native_victory_notifications import encode_record
            from civ6_host.runtime.native.native_victory_notifications import EVENT_SPECS
            from civ6_host.runtime.native.native_victory_notifications import PROOF_SHA256
            from civ6_host.runtime.native.native_deferred_empty_profile import validate_empty_profile_record
            if len(self.pending) >= self.limit:
                raise RuntimeError('Victory notification queue bound exceeded')
            if type(self._sequence) is not int or not 0 <= self._sequence < 2147483647:
                raise ValueError('Victory notification sequence exhausted')
            spec = EVENT_SPECS[kind]
            shape = bytearray(96)
            struct.pack_into('<II', shape, 0, 96, spec.record_type)
            validate_empty_profile_record(shape, **self.empty_receiver_state)
            codec_state = dict(profile=spec.empty_receiver_profile, record_type=spec.record_type, event_name='GameCoreEvent::' + spec.name, pre_hook=None, post_hook=None, subscriber_count=0, subscriber_list_empty=True, deferred_flag=0)
            fields = decode_fields(kind, raw_fields)
            record = encode_record(self._sequence + 1, fields, normalizer_transform_present=False, thread_hook_present=False, writer_metadata_callback_present=False, empty_receiver_state=codec_state, padding_policy='source-zero-allocation')
            validate_empty_profile_record(record, **self.empty_receiver_state)
            self._enqueue(record)
            self.emit('native_deferred_host_event_enqueued', dispatch_kind=hex(kind), queue_type=hex(spec.record_type), record_hex=record.hex(), pending_count=len(self.pending), normalizer_transform_present=False, optional_preprocessing_hook_registered=False, queue_metadata_service_registered=False, metadata_flags=6, empty_receiver_state_verified=True, source_proof_sha256=PROOF_SHA256, payload_exposed_to_learner=False, consumer_validated=False, eligible_for_training=False, native_dispatch_return=0)
            return 0
        if kind == 827191705:
            from civ6_host.runtime.native.native_religion_founded_event import encode_record
            from civ6_host.runtime.native.native_religion_founded_event import PROOF_SHA256
            from civ6_host.runtime.native.native_deferred_empty_profile import validate_empty_profile_record
            if len(self.pending) >= self.limit:
                raise RuntimeError('ReligionFounded queue bound exceeded')
            if type(self._sequence) is not int or not 0 <= self._sequence < 2147483647:
                raise ValueError('ReligionFounded sequence exhausted')
            shape = bytearray(96)
            struct.pack_into('<II', shape, 0, 96, 196)
            validate_empty_profile_record(shape, **self.empty_receiver_state)
            record = encode_record(self._sequence + 1, raw_fields, normalizer_transform_present=False, thread_hook_present=False, writer_metadata_callback_present=False, empty_receiver_state=self.empty_receiver_state, padding_policy='zero-unwritten-record-padding')
            validate_empty_profile_record(record, **self.empty_receiver_state)
            self._enqueue(record)
            player, religion = struct.unpack_from('<II', record, 84)
            self.emit('native_deferred_host_event_enqueued', dispatch_kind=hex(kind), queue_type='0xc4', record_hex=record.hex(), player_id=player, religion_index=religion, pending_count=len(self.pending), normalizer_transform_present=False, optional_preprocessing_hook_registered=False, queue_metadata_service_registered=False, metadata_flags=4, undefined_value_policy='zero-unwritten-record-padding', undefined_value_is_native_default=False, empty_receiver_state_verified=True, payload_exposed_to_learner=False, source_proof_sha256=PROOF_SHA256, consumer_validated=False, eligible_for_training=False, native_dispatch_return=0)
            return 0
        if kind == 3209231784:
            from civ6_host.runtime.native.native_event_bf48fda8 import encode_record
            from civ6_host.runtime.native.native_event_bf48fda8 import PINNED_EVIDENCE_SHA256
            from civ6_host.runtime.native.native_deferred_empty_profile import validate_empty_profile_record
            if len(self.pending) >= self.limit:
                raise RuntimeError('TechBoostTriggered queue bound exceeded')
            if type(self._sequence) is not int or not 0 <= self._sequence < 2147483647:
                raise ValueError('TechBoostTriggered sequence exhausted')
            shape = bytearray(112)
            struct.pack_into('<II', shape, 0, 112, 178)
            validate_empty_profile_record(shape, **self.empty_receiver_state)
            record = encode_record(self._sequence + 1, raw_fields, normalizer_transform_present=False, thread_hook_present=False, writer_metadata_callback_present=False)
            validate_empty_profile_record(record, **self.empty_receiver_state)
            self._enqueue(record)
            self.emit('native_deferred_host_event_enqueued', dispatch_kind=hex(kind), queue_type='0xb2', record_hex=record.hex(), pending_count=len(self.pending), normalizer_transform_present=False, optional_preprocessing_hook_registered=False, queue_metadata_service_registered=False, metadata_flags=4, empty_receiver_state_verified=True, source_proof_sha256=PINNED_EVIDENCE_SHA256, payload_exposed_to_learner=False, consumer_validated=False, eligible_for_training=False, native_dispatch_return=0)
            return 0
        if kind == 1072344322:
            from civ6_host.runtime.native.native_event_3feaad02 import encode_record
            from civ6_host.runtime.native.native_deferred_empty_profile import validate_empty_profile_record
            record = encode_record(self._sequence + 1, raw_fields, normalizer_transform_present=False, thread_hook_present=False, writer_metadata_callback_present=False)
            validate_empty_profile_record(record, **self.empty_receiver_state)
            self._enqueue(record)
            self.emit('native_deferred_host_event_enqueued', dispatch_kind=hex(kind), queue_type='0xb3', record_hex=record.hex(), pending_count=len(self.pending), normalizer_transform_present=False, optional_preprocessing_hook_registered=False, queue_metadata_service_registered=False, metadata_flags=4, payload_exposed_to_learner=False, consumer_validated=False, eligible_for_training=False, native_dispatch_return=0)
            return 0
        if kind == 529806097:
            from civ6_host.runtime.native.native_event_1f943311 import encode_record
            from civ6_host.runtime.native.native_deferred_empty_profile import validate_empty_profile_record
            record = encode_record(self._sequence + 1, raw_fields, self.read, normalizer_transform_present=False, thread_hook_present=False, writer_metadata_callback_present=False)
            validate_empty_profile_record(record, **self.empty_receiver_state)
            self._enqueue(record)
            self.emit('native_deferred_host_event_enqueued', dispatch_kind=hex(kind), queue_type='0x11f', record_hex=record.hex(), blob_hex=record[84:92].hex(), pending_count=len(self.pending), normalizer_transform_present=False, optional_preprocessing_hook_registered=False, queue_metadata_service_registered=False, consumer_validated=False, payload_exposed_to_learner=False, eligible_for_training=False, native_dispatch_return=0)
            return 0
        if kind == 2414808462:
            from civ6_host.runtime.native.native_event_8fef0d8e import encode_record
            record = encode_record(self._sequence + 1, raw_fields, normalizer_transform_present=False, thread_hook_present=False, writer_metadata_callback_present=False, padding_policy='zero-unread-empty-receiver-payload', empty_receiver_state=self.empty_receiver_state)
            self._enqueue(record)
            self.emit('native_deferred_host_event_enqueued', dispatch_kind=hex(kind), queue_type='0x120', record_hex=record.hex(), pending_count=len(self.pending), normalizer_transform_present=False, optional_preprocessing_hook_registered=False, queue_metadata_service_registered=False, consumer_validated=False, undefined_stack_range='record+0x54..0x57', undefined_value_policy='zero-unread-empty-receiver-payload', empty_receiver_state_verified=True, undefined_value_is_native_default=False, payload_exposed_to_learner=False, eligible_for_training=False, native_dispatch_return=0)
            return 0
        if kind == 3241152231:
            from civ6_host.runtime.native.native_unit_visibility_event import encode_scoped_record
            from civ6_host.runtime.native.native_unit_visibility_event import decode_fields
            from civ6_host.runtime.native.native_unit_visibility_event import POSITIVE_PROOF_SHA256
            from civ6_host.runtime.native.native_unit_visibility_event import SCOPE_PROOF_SHA256
            from civ6_host.runtime.native.native_unit_visibility_event import verify_scoped_source_evidence
            from civ6_host.runtime.native.native_notification_metadata import metadata_scope_transition
            from civ6_host.runtime.native.native_deferred_empty_profile import validate_empty_profile_record
            verify_scoped_source_evidence()
            metadata_scope_transition(self.host_notification_counter, self.host_metadata_counter)
            if type(self.entity_listener_count) is not int or self.entity_listener_count != 0:
                raise ValueError('UnitVisibilityChanged requires empty entity listeners')
            if type(self._sequence) is not int or not 0 <= self._sequence < 2147483647:
                raise ValueError('UnitVisibilityChanged sequence exceeds bounded encoder range')
            if len(self.pending) >= self.limit:
                raise RuntimeError('Native deferred queue bound exceeded')
            shape = bytearray(128)
            struct.pack_into('<II', shape, 0, 128, 36)
            validate_empty_profile_record(shape, **self.empty_receiver_state)
            fields = decode_fields(raw_fields, self.read)
            index = fields['optional_value']
            queried = index is not None and index < 2147483648
            if queried and (not self.ui_cache_callbacks_enabled):
                raise ValueError('C1300EE7 positive query requires the initialized native map facade')
            before = self.host_metadata_counter
            record, after = encode_scoped_record(self._sequence + 1, raw_fields, self.read, notification_counter=self.host_notification_counter, metadata_counter=before, entity_listener_count=self.entity_listener_count, thread_hook_present=False, writer_metadata_callback_present=False, padding_policy='headless-zero-initialization', core=self.core, context=self.context, core_sha256=getattr(self, 'foundation_core_sha256', 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'))
            validate_empty_profile_record(record, **self.empty_receiver_state)
            self._enqueue(record)
            self.host_metadata_counter = after
            if self.host_notification_counter != 0:
                self.emit('native_notification_metadata_transition', dispatch_kind=hex(kind), sequence=self._sequence, notification_counter=self.host_notification_counter, metadata_before=before, metadata_after=after, metadata_flag=struct.unpack_from('<I', record, 72)[0], source_proof_sha256=SCOPE_PROOF_SHA256, empty_receiver_state_verified=True, eligible_for_training=False)
            self.emit('native_deferred_host_event_enqueued', dispatch_kind=hex(kind), queue_type='0x24', record_hex=record.hex(), owner=fields['owner'], identifier=fields['identifier'], normalized_type=fields['normalized_type'], callback_mode=fields['callback_mode'], source_value=fields['source_value'], input_profile=fields['input_profile'], optional_boolean_present=fields['optional_boolean_present'], raw_boolean_byte=fields['raw_boolean_byte'], optional_native_query_entered=queried, pending_count=len(self.pending), entity_listener_count=0, optional_preprocessing_hook_registered=False, queue_metadata_service_registered=False, unspecified_padding_policy='zero', consumer_validated=False, eligible_for_training=False, native_dispatch_return=0)
            if queried:
                self.emit('native_c1300ee7_optional_query_enqueued', dispatch_kind=hex(kind), source_proof_sha256=POSITIVE_PROOF_SHA256, queue_type='0x24', optional_map_index=index, native_optional_position_hex=record[100:108].hex(), optional_scalar=fields['ignored_scalar'], record_sequence=self._sequence, raw_boolean_byte=fields['raw_boolean_byte'], record_sha256=hashlib.sha256(record).hexdigest(), native_map_released_before_enqueue=True, payload_exposed_to_learner=False, consumer_validated=False, eligible_for_training=False)
            return 0
        if kind == 3853650818:
            from civ6_host.runtime.native.native_event_e5b20b82 import decode_fields
            from civ6_host.runtime.native.native_event_e5b20b82 import produce_record
            from civ6_host.runtime.native.native_event_e5b20b82 import PADDING_POLICY
            fields = decode_fields(raw_fields, self.read)
            record = produce_record(self._sequence + 1, self.core, self.context, fields, expected_civilization_hashes=getattr(self.host, 'configured_player_identity_hashes', {}), normalizer_transform_present=False, thread_hook_present=False, writer_metadata_callback_present=False, padding_policy=PADDING_POLICY, empty_receiver_state=self.empty_receiver_state, read=self.read, core_sha256=getattr(self, 'turn_unit_core_sha256', 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'), candidate_backend=getattr(self, 'turn_unit_backend', None))
            self._enqueue(record)
            self.emit('native_deferred_host_event_enqueued', dispatch_kind=hex(kind), queue_type='0x8f', record_hex=record.hex(), plot_x=fields.x, plot_y=fields.y, pending_count=len(self.pending), native_queries_executed=True, local_query_uses_component_owner=True, application_mode_source='separate-native-provider-B', retained_sources_released_before_enqueue=True, empty_receiver_state_verified=True, consumer_validated=False, eligible_for_training=False, native_dispatch_return=0)
            return 0
        if kind == 816720445:
            from civ6_host.runtime.native.native_event_30ae2a3d import decode_fields
            from civ6_host.runtime.native.native_event_30ae2a3d import produce_record
            from civ6_host.runtime.native.native_event_30ae2a3d import PADDING_POLICY
            from civ6_host.runtime.native.native_event_30ae2a3d import PROOF_SHA256
            from civ6_host.runtime.native.native_deferred_empty_profile import validate_empty_profile_record
            if len(self.pending) >= self.limit:
                raise RuntimeError('Native deferred queue bound exceeded')
            validate_sequence(self._sequence + 1)
            if type(self.entity_listener_count) is not int or self.entity_listener_count != 0:
                raise ValueError('ImprovementChanged requires actual empty entity listeners')
            shape = bytearray(144)
            struct.pack_into('<II', shape, 0, 144, 144)
            validate_empty_profile_record(shape, **self.empty_receiver_state)
            fields = decode_fields(raw_fields, self.read)
            record = produce_record(self._sequence + 1, self.core, self.context, fields, expected_civilization_hashes=getattr(self.host, 'configured_player_identity_hashes', {}), normalizer_transform_present=False, thread_hook_present=False, writer_metadata_callback_present=False, entity_listener_count=self.entity_listener_count, padding_policy=PADDING_POLICY, empty_receiver_state=self.empty_receiver_state, read=self.read, core_sha256=getattr(self, 'improvement_core_sha256', 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'))
            self._enqueue(record)
            self.emit('native_deferred_host_event_enqueued', dispatch_kind=hex(kind), queue_type='0x90', record_hex=record.hex(), pending_count=len(self.pending), source_proof_sha256=_improvement_source.source_sha(getattr(self, 'improvement_core_sha256', 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'), PROOF_SHA256), native_queries_executed=True, plot_x=fields.x, plot_y=fields.y, entity_listener_count=self.entity_listener_count, retained_sources_released_before_enqueue=True, unspecified_padding_policy=PADDING_POLICY, empty_receiver_state_verified=True, undefined_value_is_native_default=False, payload_exposed_to_learner=False, consumer_validated=False, eligible_for_training=False, native_dispatch_return=0)
            return 0
        if kind == 1567648150:
            from civ6_host.runtime.native.native_event_5d706996 import decode_fields
            from civ6_host.runtime.native.native_event_5d706996 import encode_record
            from civ6_host.runtime.native.native_event_5d706996 import PROOF_SHA256
            from civ6_host.runtime.native.native_event_5d706996 import PADDING_POLICY
            from civ6_host.runtime.native.native_deferred_empty_profile import validate_empty_profile_record
            if len(self.pending) >= self.limit:
                raise RuntimeError('Native deferred queue bound exceeded')
            validate_sequence(self._sequence + 1)
            if type(self.entity_listener_count) is not int or self.entity_listener_count != 0:
                raise ValueError('Trade activity callback requires the closed empty observer profile')
            shape = bytearray(112)
            struct.pack_into('<II', shape, 0, 112, 215)
            validate_empty_profile_record(shape, **self.empty_receiver_state)
            fields = decode_fields(raw_fields, self.read)
            record = encode_record(self._sequence + 1, fields, normalizer_transform_present=False, per_thread_hook_present=False, writer_metadata_callback_present=False, entity_listener_count=self.entity_listener_count, padding_policy=PADDING_POLICY, empty_receiver_state=self.empty_receiver_state)
            self._enqueue(record)
            self.emit('native_deferred_host_event_enqueued', dispatch_kind=hex(kind), queue_type='0xd7', record_hex=record.hex(), pending_count=len(self.pending), source_proof_sha256=PROOF_SHA256, native_queries_executed=False, first_owner=fields.first_owner, first_id=fields.first_id, second_owner=fields.second_owner, second_id=fields.second_id, source_selector=fields.selector, selector_consumed=False, entity_listener_count=self.entity_listener_count, unspecified_padding_policy=PADDING_POLICY, empty_receiver_state_verified=True, undefined_value_is_native_default=False, payload_exposed_to_learner=False, consumer_validated=False, eligible_for_training=False, native_dispatch_return=0)
            return 0
        if kind in (2022911379, 1743160778):
            if kind == 2022911379:
                from civ6_host.runtime.native.native_event_78932d93 import decode_fields
                from civ6_host.runtime.native.native_event_78932d93 import encode_record
                from civ6_host.runtime.native.native_event_78932d93 import PROOF_SHA256
                from civ6_host.runtime.native.native_event_78932d93 import RECORD_TYPE
            else:
                from civ6_host.runtime.native.native_trade_route_position_events import decode_fields
                from civ6_host.runtime.native.native_trade_route_position_events import encode_record
                from civ6_host.runtime.native.native_trade_route_position_events import PROOF_SHA256
                from civ6_host.runtime.native.native_trade_route_position_events import RECORD_TYPE
            from civ6_host.runtime.native.native_deferred_empty_profile import validate_empty_profile_record
            if len(self.pending) >= self.limit:
                raise RuntimeError('Native deferred queue bound exceeded')
            validate_sequence(self._sequence + 1)
            if type(self.entity_listener_count) is not int or self.entity_listener_count != 0:
                raise ValueError('Position/value callback requires the closed empty observer profile')
            shape = bytearray(96)
            struct.pack_into('<II', shape, 0, 96, RECORD_TYPE)
            validate_empty_profile_record(shape, **self.empty_receiver_state)
            fields = decode_fields(raw_fields, self.read)
            record = encode_record(self._sequence + 1, fields, normalizer_transform_present=False, per_thread_hook_present=False, writer_metadata_callback_present=False, entity_listener_count=self.entity_listener_count, empty_receiver_state=self.empty_receiver_state)
            self._enqueue(record)
            self.emit('native_deferred_host_event_enqueued', dispatch_kind=hex(kind), queue_type=hex(RECORD_TYPE), record_hex=record.hex(), pending_count=len(self.pending), source_proof_sha256=PROOF_SHA256, native_queries_executed=False, plot_x=fields.x, plot_y=fields.y, source_d6_value=fields.value, source_selector=fields.selector, selector_consumed=False, entity_listener_count=self.entity_listener_count, payload_fully_initialized=True, empty_receiver_state_verified=True, payload_exposed_to_learner=False, consumer_validated=False, eligible_for_training=False, native_dispatch_return=0)
            return 0
        if kind in (2980214136, 4152393721, 330185301):
            from civ6_host.runtime.native.native_position_value_event_family import decode_fields
            from civ6_host.runtime.native.native_position_value_event_family import encode_record
            from civ6_host.runtime.native.native_position_value_event_family import RECORD_TYPES
            from civ6_host.runtime.native.native_position_value_event_family import PROOF_SHA256
            from civ6_host.runtime.native.native_deferred_empty_profile import validate_empty_profile_record
            if len(self.pending) >= self.limit:
                raise RuntimeError('Native deferred queue bound exceeded')
            validate_sequence(self._sequence + 1)
            if type(self.entity_listener_count) is not int or self.entity_listener_count != 0:
                raise ValueError('Position/value callbacks require the closed empty observer profile')
            shape = bytearray(96)
            struct.pack_into('<II', shape, 0, 96, RECORD_TYPES[kind])
            validate_empty_profile_record(shape, **self.empty_receiver_state)
            fields = decode_fields(raw_fields, self.read)
            record = encode_record(kind, self._sequence + 1, fields, normalizer_transform_present=False, per_thread_hook_present=False, writer_metadata_callback_present=False, entity_listener_count=self.entity_listener_count, empty_receiver_state=self.empty_receiver_state)
            self._enqueue(record)
            self._finish_counter_neutral_event(kind, record, neutral_scope)
            self.emit('native_deferred_host_event_enqueued', dispatch_kind=hex(kind), queue_type=hex(RECORD_TYPES[kind]), record_hex=record.hex(), pending_count=len(self.pending), source_proof_sha256=PROOF_SHA256, native_queries_executed=False, plot_x=fields.x, plot_y=fields.y, source_d6_value=fields.value, entity_listener_count=self.entity_listener_count, payload_fully_initialized=True, empty_receiver_state_verified=True, payload_exposed_to_learner=False, consumer_validated=False, eligible_for_training=False, native_dispatch_return=0)
            return 0
        if kind == 3629625883:
            from civ6_host.runtime.native.native_event_d857b21b import decode_fields
            from civ6_host.runtime.native.native_event_d857b21b import encode_record
            from civ6_host.runtime.native.native_event_d857b21b import PADDING_POLICY
            from civ6_host.runtime.native.native_event_d857b21b import PROOF_SHA256
            from civ6_host.runtime.native.native_deferred_empty_profile import validate_empty_profile_record
            if len(self.pending) >= self.limit:
                raise RuntimeError('Native deferred queue bound exceeded')
            validate_sequence(self._sequence + 1)
            if type(self.entity_listener_count) is not int or self.entity_listener_count != 0:
                raise ValueError('ImprovementActivated requires actual empty entity listeners')
            shape = bytearray(128)
            struct.pack_into('<II', shape, 0, 128, 147)
            validate_empty_profile_record(shape, **self.empty_receiver_state)
            fields = decode_fields(raw_fields, self.read)
            record = encode_record(self._sequence + 1, fields, normalizer_transform_present=False, per_thread_hook_present=False, writer_metadata_callback_present=False, entity_listener_count=self.entity_listener_count, padding_policy=PADDING_POLICY, empty_receiver_state=self.empty_receiver_state)
            self._enqueue(record)
            self._finish_counter_neutral_event(kind, record, neutral_scope)
            self.emit('native_deferred_host_event_enqueued', dispatch_kind=hex(kind), queue_type='0x93', record_hex=record.hex(), pending_count=len(self.pending), source_proof_sha256=PROOF_SHA256, native_queries_executed=False, plot_x=fields.x, plot_y=fields.y, entity_listener_count=self.entity_listener_count, metadata_uses_unit_descriptor=False, unspecified_padding_policy=PADDING_POLICY, empty_receiver_state_verified=True, undefined_value_is_native_default=False, payload_exposed_to_learner=False, consumer_validated=False, eligible_for_training=False, native_dispatch_return=0)
            return 0
        if kind == 4086421427:
            from civ6_host.runtime.native.native_event_f391d7b3 import decode_fields
            from civ6_host.runtime.native.native_event_f391d7b3 import produce_scoped_record
            from civ6_host.runtime.native.native_event_f391d7b3 import PADDING_POLICY
            from civ6_host.runtime.native.native_event_f391d7b3 import PROOF_SHA256
            from civ6_host.runtime.native.native_event_f391d7b3 import TYPED_POSITION_PROOF_SHA256
            from civ6_host.runtime.native.native_event_f391d7b3 import SCOPE_PROOF_SHA256
            from civ6_host.runtime.native.native_event_f391d7b3 import verify_scoped_source_evidence
            from civ6_host.runtime.native.native_notification_metadata import metadata_scope_transition
            from civ6_host.runtime.native.native_deferred_empty_profile import validate_empty_profile_record
            verify_scoped_source_evidence()
            before_metadata = self.host_metadata_counter
            metadata_scope_transition(self.host_notification_counter, before_metadata)
            if len(self.pending) >= self.limit:
                raise RuntimeError('Native deferred queue bound exceeded')
            if type(self._sequence) is not int or not 0 <= self._sequence < 2147483647:
                raise ValueError('F391 sequence exceeds the bounded queue profile')
            if type(self.entity_listener_count) is not int or self.entity_listener_count != 0:
                raise ValueError('F391 requires actual empty entity listeners')
            shape = bytearray(160)
            struct.pack_into('<II', shape, 0, 160, 145)
            validate_empty_profile_record(shape, **self.empty_receiver_state)
            fields = decode_fields(raw_fields, self.read)
            prior_state = (self._sequence, self.host_notification_counter, before_metadata)
            self._f391_producing = True
            try:
                record, next_metadata = produce_scoped_record(self._sequence + 1, self.core, self.context, fields, notification_counter=self.host_notification_counter, metadata_counter=before_metadata, entity_listener_count=self.entity_listener_count, expected_civilization_hashes=getattr(self.host, 'configured_player_identity_hashes', {}), normalizer_transform_present=False, thread_hook_present=False, writer_metadata_callback_present=False, padding_policy=PADDING_POLICY, empty_receiver_state=self.empty_receiver_state, read=self.read, core_sha256=getattr(self, 'placement_core_sha256', 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'))
                if (self._sequence, self.host_notification_counter, self.host_metadata_counter) != prior_state:
                    raise RuntimeError('F391 native queries changed queue or metadata state')
                self._enqueue(record)
            except BaseException:
                self._f391_poisoned = True
                raise
            finally:
                self._f391_producing = False
            self.host_metadata_counter = next_metadata
            if self.host_notification_counter != 0:
                self.emit('native_notification_metadata_transition', dispatch_kind=hex(kind), sequence=self._sequence, notification_counter=self.host_notification_counter, metadata_before=before_metadata, metadata_after=next_metadata, metadata_flag=struct.unpack_from('<I', record, 72)[0], source_proof_sha256=SCOPE_PROOF_SHA256, empty_receiver_state_verified=True, eligible_for_training=False)
            self.emit('native_deferred_host_event_enqueued', dispatch_kind=hex(kind), queue_type='0x91', record_hex=record.hex(), plot_x=fields.common.x, plot_y=fields.common.y, pending_count=len(self.pending), native_queries_executed=True, source_proof_sha256=PROOF_SHA256, input_shape=fields.input_shape, source_position_variant_tag=struct.unpack_from('<H', raw_fields[2353434172])[0], position_variant_source_proof_sha256=TYPED_POSITION_PROOF_SHA256 if struct.unpack_from('<H', raw_fields[2353434172])[0] == 13 else None, optional_native_query_executed=fields.optional_index is not None and fields.optional_index < 2147483648, retained_sources_released_before_enqueue=True, empty_receiver_state_verified=True, undefined_value_policy=PADDING_POLICY, undefined_value_is_native_default=False, payload_exposed_to_learner=False, consumer_validated=False, eligible_for_training=False, native_dispatch_return=0)
            return 0
        if kind == 2787493670:
            from civ6_host.runtime.native.native_event_a625c726 import decode_fields
            from civ6_host.runtime.native.native_event_a625c726 import produce_record
            from civ6_host.runtime.native.native_event_a625c726 import PADDING_POLICY
            fields = decode_fields(raw_fields, self.read)
            record = produce_record(self._sequence + 1, self.core, self.context, fields, expected_civilization_hashes=getattr(self.host, 'configured_player_identity_hashes', {}), normalizer_transform_present=False, thread_hook_present=False, writer_metadata_callback_present=False, padding_policy=PADDING_POLICY, empty_receiver_state=self.empty_receiver_state, read=self.read, core_sha256=getattr(self, 'turn_unit_core_sha256', 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'))
            self._enqueue(record)
            self.emit('native_deferred_host_event_enqueued', dispatch_kind=hex(kind), queue_type='0x94', record_hex=record.hex(), plot_x=fields.x, plot_y=fields.y, pending_count=len(self.pending), native_queries_executed=True, retained_sources_released_before_enqueue=True, empty_receiver_state_verified=True, undefined_value_policy=PADDING_POLICY, undefined_value_is_native_default=False, payload_exposed_to_learner=False, consumer_validated=False, eligible_for_training=False, native_dispatch_return=0)
            return 0
        if kind == 4110293858:
            from civ6_host.runtime.native.native_event_f4fe1b62 import decode_fields
            from civ6_host.runtime.native.native_event_f4fe1b62 import query_plot_value_lease
            from civ6_host.runtime.native.native_event_f4fe1b62 import encode_record
            fields = decode_fields(raw_fields, self.read)
            with query_plot_value_lease(self.core, self.context, fields, read=self.read, core_sha256=getattr(self, 'foundation_core_sha256', 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3')) as value:
                record = encode_record(self._sequence + 1, fields, plot_value=value, plot_query_succeeded=True, producer_hook_present=False, writer_service_present=False, padding_policy='headless-zero-initialization')
                self._enqueue(record)
            self.emit('native_deferred_host_event_enqueued', dispatch_kind=hex(kind), queue_type='0xb4', record_hex=record.hex(), plot_x=fields.x, plot_y=fields.y, native_plot_value=value, callback_value=fields.value, retained_sources_live_at_enqueue=True, pending_count=len(self.pending), optional_preprocessing_hook_registered=False, queue_metadata_service_registered=False, unspecified_padding_policy='zero', consumer_validated=False, eligible_for_training=False, native_dispatch_return=0)
            return 0
        if kind in (322781468, 145997718, 2301564700):
            if kind == 322781468:
                from civ6_host.runtime.native import native_event_133d411c as diplomacy_event
            elif kind == 145997718:
                from civ6_host.runtime.native import native_event_08b3bf96 as diplomacy_event
            else:
                from civ6_host.runtime.native import native_event_892f171c as diplomacy_event
            fields = diplomacy_event.decode_fields(raw_fields, self.read)
            record = diplomacy_event.encode_record(self._sequence + 1, fields, normalizer_transform_present=False, per_thread_hook_present=False, writer_metadata_callback_present=False, entity_listener_count=self.entity_listener_count, empty_receiver_state=self.empty_receiver_state)
            self._enqueue(record)
            self.emit('native_deferred_host_event_enqueued', dispatch_kind=hex(kind), queue_type=hex(diplomacy_event.RECORD_TYPE), record_hex=record.hex(), owner=fields.owner, unit_id=fields.unit_id, value=fields.value, second=fields.second, descriptor_present=diplomacy_event.UNIT_KEY in raw_fields, source_unused_selector=fields.selector, pending_count=len(self.pending), native_queries_executed=False, entity_listener_count=0, empty_receiver_state_verified=True, payload_exposed_to_learner=False, consumer_validated=False, eligible_for_training=False, native_dispatch_return=0)
            return 0
        if kind == 3405989361:
            from civ6_host.runtime.native.native_event_cb0345f1 import decode_fields
            from civ6_host.runtime.native.native_event_cb0345f1 import encode_record
            from civ6_host.runtime.native.native_event_cb0345f1 import PADDING_POLICY
            fields = decode_fields(raw_fields, self.read)
            record = encode_record(self._sequence + 1, fields, normalizer_transform_present=False, per_thread_hook_present=False, writer_metadata_callback_present=False, padding_policy=PADDING_POLICY, entity_listener_count=self.entity_listener_count, empty_receiver_state=self.empty_receiver_state)
            self._enqueue(record)
            self.emit('native_deferred_host_event_enqueued', dispatch_kind=hex(kind), queue_type='0x45', record_hex=record.hex(), owner=fields.owner, unit_id=fields.unit_id, value=fields.value, second=fields.second, source_unused_selector=fields.selector, pending_count=len(self.pending), native_queries_executed=False, entity_listener_count=0, empty_receiver_state_verified=True, consumer_validated=False, eligible_for_training=False, native_dispatch_return=0)
            return 0
        if kind == 1027606258:
            from civ6_host.runtime.native.native_event_3d4006f2 import decode_fields
            from civ6_host.runtime.native.native_event_3d4006f2 import decode_entity_blob
            from civ6_host.runtime.native.native_event_3d4006f2 import encode_queue_record
            fields = decode_fields(raw_fields)
            blob = self.read(fields.entity_pointer, 8)
            record = encode_queue_record(self._sequence + 1, raw_fields, entity_blob=blob, producer_hook_present=False, writer_service_present=False, padding_policy='headless-zero-initialization', entity_listener_count=self.entity_listener_count, normalizer_transform_present=False, empty_receiver_state=self.empty_receiver_state)
            self._enqueue(record)
            self.emit('native_deferred_host_event_enqueued', dispatch_kind=hex(kind), queue_type='0x44', record_hex=record.hex(), selector=hex(fields.selector), value=fields.value, source_blob_hex=blob.hex(), input_value_present=fields.value_present, value_origin='native_variant' if fields.value_present else 'native_normalizer_initial_zero', normalized_entity=decode_entity_blob(blob), pending_count=len(self.pending), optional_preprocessing_hook_registered=False, queue_metadata_service_registered=False, unspecified_padding_policy='zero', original_exe_hooks_captured=False, consumer_validated=False, eligible_for_training=False, native_dispatch_return=0)
            return 0
        if kind == 3065286044:
            from civ6_host.runtime.native.native_event_b6b48d9c import decode_fields
            if kind in EXE_EVENT_CALLBACKS:
                raise RuntimeError('Previously absent EXE callback is now registered')
            fields = decode_fields(raw_fields)
            self.emit('native_host_event_without_registered_callback', dispatch_kind=hex(kind), selector=fields.selector, value=fields.value, value_b=fields.value_b, native_branch='1445f0_absent_key', core_internal_dispatch_preserved=True, source_registrar_rva='0x14d7a0', native_dispatch_return=0, eligible_for_training=False)
            return 0
        if kind == 899089314:
            from civ6_host.runtime.native.native_event_359703a2 import decode_fields
            from civ6_host.runtime.native.native_event_359703a2 import query_plot_words
            from civ6_host.runtime.native.native_event_359703a2 import encode_records
            position = decode_fields(raw_fields, self.read)
            rows = query_plot_words(self.core, self.context, position, read=self.read, core_sha256=getattr(self, 'foundation_core_sha256', 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'))
            records = encode_records(self._sequence + 1, rows, hook_present=False, writer_metadata_callback_present=False, padding_policy='zero')
            if len(self.pending) + len(records) > self.limit:
                raise RuntimeError('Native deferred queue bound exceeded by plot-neighbor event')
            for row, record in zip(rows, records):
                self._enqueue(record)
                self.emit('native_deferred_host_event_enqueued', dispatch_kind=hex(kind), queue_type='0xb7', record_hex=record.hex(), native_plot_query=row, pending_count=len(self.pending), optional_preprocessing_hook_registered=False, queue_metadata_service_registered=False, unspecified_padding_policy='zero', original_exe_hooks_captured=False, consumer_validated=False, eligible_for_training=False, native_dispatch_return=0)
            return 0
        if kind == 1852022915:
            from civ6_host.runtime.native.native_event_6e63a083 import decode_fields
            from civ6_host.runtime.native.native_event_6e63a083 import encode_6e63a083_record
            fields = decode_fields(raw_fields)
            record = encode_6e63a083_record(self._sequence + 1)
            self._enqueue(record)
            self.emit('native_deferred_host_event_enqueued', dispatch_kind=hex(kind), queue_type='0x9', record_hex=record.hex(), input_fields=fields, input_values_used_by_exe_callback=False, pending_count=len(self.pending), optional_preprocessing_hook_registered=False, queue_metadata_service_registered=False, unspecified_padding_policy='zero', original_exe_hooks_captured=False, consumer_validated=False, eligible_for_training=False, native_dispatch_return=0)
            return 0
        if kind in (3565292211, 821819602, 1408378902):
            from civ6_host.runtime.native import native_city_descriptor_event_family as family
            from civ6_host.runtime.native.native_deferred_empty_profile import validate_empty_profile_record
            spec = family.SPECS[kind]
            shape = bytearray(spec.record_size)
            struct.pack_into('<II', shape, 0, spec.record_size, spec.record_type)
            validate_empty_profile_record(shape, **self.empty_receiver_state)
            state = self.empty_receiver_state
            record, descriptor = family.encode_record_with_fields(kind, self._sequence + 1, raw_fields, self.read, empty_receiver_profile='empty-no-observer-zero-subscriber-v1', observer_registered=state['observer_registered'], receiver_state_pointer_nonnull=state['state_pointer_nonnull'], receiver_pre_hook_present=state['pre_hook'] is not None, receiver_post_hook_present=state['post_hook'] is not None, receiver_subscriber_count=state['subscriber_count'], receiver_state_flags=state['state_flags'], normalizer_transform_present=False, per_thread_hook_present=False, writer_metadata_callback_present=False, padding_policy='headless-zero-uninitialized-stack-and-record-tail')
            validate_empty_profile_record(record, **self.empty_receiver_state)
            self._enqueue(record)
            self.emit('native_deferred_host_event_enqueued', dispatch_kind=hex(kind), queue_type=hex(spec.record_type), record_hex=record.hex(), owner=descriptor.owner, city_id=descriptor.identifier, pending_count=len(self.pending), optional_preprocessing_hook_registered=False, queue_metadata_service_registered=False, normalizer_transform_present=False, undefined_value_policy='headless-zero-uninitialized-stack-and-record-tail', undefined_value_is_native_default=False, empty_receiver_state_verified=True, payload_exposed_to_learner=False, source_proof_sha256=family.PROOF_SHA256, consumer_validated=False, eligible_for_training=False, native_dispatch_return=0)
            return 0
        if kind in (2842556304, 1920266315, 58288157, 1169483000, 3424348260):
            if kind == 2842556304:
                from civ6_host.runtime.native import native_event_a96df790 as ability_event
            elif kind == 1920266315:
                from civ6_host.runtime.native import native_event_7274f04b as ability_event
            elif kind == 58288157:
                from civ6_host.runtime.native import native_event_0379681d as ability_event
            elif kind == 1169483000:
                from civ6_host.runtime.native import native_event_45b4e4f8 as ability_event
            else:
                from civ6_host.runtime.native import native_event_cc1b6864 as ability_event
            from civ6_host.runtime.native.native_deferred_empty_profile import validate_empty_profile_record
            if len(self.pending) >= self.limit:
                raise RuntimeError('Unit descriptor notification queue bound exceeded')
            if type(self._sequence) is not int or not 0 <= self._sequence < 2147483647:
                raise ValueError('Unit descriptor notification sequence exhausted')
            if kind in (1169483000, 3424348260) and (type(self.entity_listener_count) is not int or self.entity_listener_count != 0):
                raise ValueError('UnitExitFormation requires actual empty entity listeners')
            shape = bytearray(112)
            struct.pack_into('<II', shape, 0, 112, ability_event.RECORD_TYPE)
            validated = validate_empty_profile_record(shape, **self.empty_receiver_state)
            state = self.empty_receiver_state
            receiver = dict(profile=ability_event.EMPTY_RECEIVER_PROFILE, record_type=validated['record_type'], event_name=validated['event_name'], pre_hook=state['pre_hook'], post_hook=state['post_hook'], subscriber_count=state['subscriber_count'], subscriber_list_empty=state['subscriber_count'] == 0, deferred_flag=state['state_flags'] & 3)
            fields = ability_event.decode_fields(raw_fields, self.read)
            extra_options = {'entity_listener_count': self.entity_listener_count} if kind in (1169483000, 3424348260) else {}
            record = ability_event.encode_record(self._sequence + 1, fields, normalizer_transform_present=False, per_thread_hook_present=False, writer_metadata_callback_present=False, empty_receiver_state=receiver, padding_policy=ability_event.PADDING_POLICY, **extra_options)
            validate_empty_profile_record(record, **self.empty_receiver_state)
            self._enqueue(record)
            pair_receipt = {'second_owner': fields.second_owner, 'second_id': fields.second_id, 'source_pair_proof_sha256': ability_event.PAIR_PROOF_SHA256, 'source_second_descriptor_present': ability_event.SECOND_KEY in raw_fields, 'entity_listener_count': self.entity_listener_count, 'native_queries_executed': False} if kind in (1169483000, 3424348260) else {}
            self.emit('native_deferred_host_event_enqueued', dispatch_kind=hex(kind), queue_type=hex(ability_event.RECORD_TYPE), record_hex=record.hex(), owner=fields.owner, unit_id=fields.unit_id, source_d6_value=fields.value, source_unused_selector=fields.selector, source_a1fbc_value=getattr(fields, 'second', None), pending_count=len(self.pending), optional_preprocessing_hook_registered=False, queue_metadata_service_registered=False, normalizer_transform_present=False, undefined_value_policy=ability_event.PADDING_POLICY, undefined_value_is_native_default=False, empty_receiver_state_verified=True, payload_exposed_to_learner=False, source_proof_sha256=ability_event.PINNED_EVIDENCE_SHA256, consumer_validated=False, eligible_for_training=False, native_dispatch_return=0, **pair_receipt)
            return 0
        if kind == 2987879876:
            from civ6_host.runtime.native.native_event_b2176dc4 import decode_fields
            from civ6_host.runtime.native.native_event_b2176dc4 import encode_record
            from civ6_host.runtime.native.native_event_b2176dc4 import EMPTY_RECEIVER_PROFILE
            from civ6_host.runtime.native.native_event_b2176dc4 import PADDING_POLICY
            from civ6_host.runtime.native.native_event_b2176dc4 import PINNED_EVIDENCE_SHA256
            from civ6_host.runtime.native.native_deferred_empty_profile import validate_empty_profile_record
            shape = bytearray(112)
            struct.pack_into('<II', shape, 0, 112, 46)
            validated = validate_empty_profile_record(shape, **self.empty_receiver_state)
            state = self.empty_receiver_state
            receiver = dict(profile=EMPTY_RECEIVER_PROFILE, record_type=validated['record_type'], event_name=validated['event_name'], pre_hook=state['pre_hook'], post_hook=state['post_hook'], subscriber_count=state['subscriber_count'], subscriber_list_empty=state['subscriber_count'] == 0, deferred_flag=state['state_flags'] & 3)
            fields = decode_fields(raw_fields, self.read)
            record = encode_record(self._sequence + 1, fields, normalizer_transform_present=False, per_thread_hook_present=False, writer_metadata_callback_present=False, empty_receiver_state=receiver, padding_policy=PADDING_POLICY)
            validate_empty_profile_record(record, **self.empty_receiver_state)
            self._enqueue(record)
            self.emit('native_deferred_host_event_enqueued', dispatch_kind=hex(kind), queue_type='0x2e', record_hex=record.hex(), owner=fields.owner, unit_id=fields.unit_id, source_d6_value=fields.value, source_a1fbc_value=fields.second, source_unused_selector=fields.selector, pending_count=len(self.pending), optional_preprocessing_hook_registered=False, queue_metadata_service_registered=False, normalizer_transform_present=False, undefined_value_policy=PADDING_POLICY, undefined_value_is_native_default=False, empty_receiver_state_verified=True, payload_exposed_to_learner=False, source_proof_sha256=PINNED_EVIDENCE_SHA256, consumer_validated=False, eligible_for_training=False, native_dispatch_return=0)
            return 0
        if kind == 2365609745:
            from civ6_host.runtime.native.native_event_8d005711 import decode_fields
            from civ6_host.runtime.native.native_event_8d005711 import encode_record
            from civ6_host.runtime.native.native_event_8d005711 import PADDING_POLICY
            from civ6_host.runtime.native.native_deferred_empty_profile import validate_empty_profile_record
            shape = bytearray(112)
            struct.pack_into('<II', shape, 0, 112, 91)
            validate_empty_profile_record(shape, **self.empty_receiver_state)
            fields = decode_fields(raw_fields, self.read)
            record = encode_record(self._sequence + 1, fields, normalizer_transform_present=False, per_thread_hook_present=False, writer_metadata_callback_present=False, padding_policy=PADDING_POLICY, empty_receiver_state=self.empty_receiver_state)
            self._enqueue(record)
            self.emit('native_deferred_host_event_enqueued', dispatch_kind=hex(kind), queue_type='0x5b', record_hex=record.hex(), owner=fields.owner, city_id=fields.item_id, source_scalar=fields.d6_value, source_unused_selector=fields.selector, pending_count=len(self.pending), optional_preprocessing_hook_registered=False, queue_metadata_service_registered=False, normalizer_transform_present=False, undefined_value_policy=PADDING_POLICY, undefined_value_is_native_default=False, empty_receiver_state_verified=True, payload_exposed_to_learner=False, consumer_validated=False, eligible_for_training=False, native_dispatch_return=0)
            return 0
        if kind == 3247915626:
            from civ6_host.runtime.native.native_event_c197426a import encode_record
            from civ6_host.runtime.native.native_event_c197426a import EMPTY_RECEIVER_PROFILE
            from civ6_host.runtime.native.native_event_c197426a import PADDING_POLICY
            from civ6_host.runtime.native.native_deferred_empty_profile import validate_empty_profile_record
            shape = bytearray(96)
            struct.pack_into('<II', shape, 0, 96, 155)
            validate_empty_profile_record(shape, **self.empty_receiver_state)
            record = encode_record(self._sequence + 1, raw_fields, self.read, thread_hook_present=False, writer_metadata_callback_present=False, normalizer_transform_present=False, empty_receiver_profile=EMPTY_RECEIVER_PROFILE, padding_policy=PADDING_POLICY)
            validate_empty_profile_record(record, **self.empty_receiver_state)
            self._enqueue(record)
            self.emit('native_deferred_host_event_enqueued', dispatch_kind=hex(kind), queue_type='0x9b', record_hex=record.hex(), source_position_blob_hex=record[84:92].hex(), pending_count=len(self.pending), optional_preprocessing_hook_registered=False, queue_metadata_service_registered=False, normalizer_transform_present=False, undefined_value_policy=PADDING_POLICY, undefined_value_is_native_default=False, empty_receiver_state_verified=True, payload_exposed_to_learner=False, consumer_validated=False, eligible_for_training=False, native_dispatch_return=0)
            return 0
        if kind == 3659576915:
            from civ6_host.runtime.native.native_feature_removed_event import decode_feature_removed_fields
            from civ6_host.runtime.native.native_feature_removed_event import encode_record
            from civ6_host.runtime.native.native_feature_removed_event import SCALAR_DOMAIN_SHA256
            position = decode_feature_removed_fields(raw_fields, self.read)
            record = encode_record(self._sequence + 1, position, thread_hook_present=False, writer_metadata_callback_present=False, padding_policy='zero')
            self._enqueue(record)
            self.emit('native_feature_removed_event_adapted', dispatch_kind=hex(kind), plot_x=position['x'], plot_y=position['y'], source_unused_selector=position['selector'], source_unused_tail=position['tail'], scalar_source_sha256=SCALAR_DOMAIN_SHA256, native_gameplay_mutated=False, payload_exposed_to_learner=False, eligible_for_training=False)
            self.emit('native_deferred_host_event_enqueued', dispatch_kind=hex(kind), queue_type='0x77', record_hex=record.hex(), source_position_blob_hex=position['position_bytes'].hex(), plot_x=position['x'], plot_y=position['y'], pending_count=len(self.pending), optional_preprocessing_hook_registered=False, queue_metadata_service_registered=False, unspecified_padding_policy='zero', original_exe_hooks_captured=False, consumer_validated=False, eligible_for_training=False, native_dispatch_return=0)
            return 0
        if kind == 2303979814:
            from civ6_host.runtime.native.native_event_8953f126 import decode_fields
            from civ6_host.runtime.native.native_event_8953f126 import encode_8953f126_record
            fields = decode_fields(raw_fields)
            record = encode_8953f126_record(self._sequence + 1, **fields)
            self._enqueue(record)
            self.turn_begin_state.controller_initialized = True
            self.turn_begin_state.controller_byte_0d = 0
            self.emit('native_deferred_host_event_enqueued', dispatch_kind=hex(kind), queue_type='0xf', record_hex=record.hex(), value=fields['value'], selector=fields['selector'], boolean_state=fields['state'] != 0, pending_count=len(self.pending), controller_byte_0d=self.turn_begin_state.controller_byte_0d, optional_preprocessing_hook_registered=False, queue_metadata_service_registered=False, unspecified_padding_policy='zero', original_exe_controller_scheduling=False, consumer_validated=False, eligible_for_training=False, native_dispatch_return=0)
            return 0
        if kind == 2274153042:
            from civ6_host.runtime.native.native_feature_visibility_event import decode_feature_visibility_fields
            from civ6_host.runtime.native.native_feature_visibility_event import query_plot_word
            from civ6_host.runtime.native.native_feature_visibility_event import encode_scoped_record
            from civ6_host.runtime.native.native_feature_visibility_event import verify_scoped_source_evidence
            from civ6_host.runtime.native.native_feature_visibility_event import SCOPE_PROOF_SHA256
            from civ6_host.runtime.native.native_notification_metadata import metadata_scope_transition
            from civ6_host.runtime.native.native_deferred_empty_profile import validate_empty_profile_record
            verify_scoped_source_evidence()
            metadata_scope_transition(self.host_notification_counter, self.host_metadata_counter)
            if type(self.entity_listener_count) is not int or self.entity_listener_count != 0:
                raise ValueError('FeatureVisibilityChanged requires empty entity listeners')
            if len(self.pending) >= self.limit:
                raise RuntimeError('FeatureVisibilityChanged exceeds native deferred queue bound')
            if type(self._sequence) is not int or not 0 <= self._sequence < 4294967295:
                raise ValueError('FeatureVisibilityChanged sequence exceeds source uint32 range')
            shape = bytearray(128)
            struct.pack_into('<II', shape, 0, 128, 118)
            validate_empty_profile_record(shape, **self.empty_receiver_state)
            captured = {}
            for key, raw in raw_fields.items():
                if len(raw) == 24:
                    tag = int.from_bytes(raw[:2], 'little')
                    pointer, size, flags = struct.unpack_from('<QII', raw, 8)
                    if tag in (0, 13, 1024) and pointer and (size == 8) and (flags == 553648129):
                        captured[hex(key)] = self.read(pointer, 8).hex()
            self.emit('native_feature_visibility_input_diagnostic', dispatch_kind=hex(kind), fields={hex(k): v.hex() for k, v in raw_fields.items()}, copied_eight_byte_payloads=captured, eligible_for_training=False)
            position = decode_feature_visibility_fields(raw_fields, self.read)
            word = query_plot_word(self.core, self.context, position, read=self.read, core_sha256=getattr(self, 'foundation_core_sha256', 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'))
            metadata_before = self.host_metadata_counter
            record, metadata_after = encode_scoped_record(self._sequence + 1, position, word, queue_callback_result=0, padding_policy='zero', notification_counter=self.host_notification_counter, metadata_counter=metadata_before, thread_hook_present=False, writer_metadata_callback_present=False)
            validate_empty_profile_record(record, **self.empty_receiver_state)
            self._enqueue(record)
            self.host_metadata_counter = metadata_after
            metadata_flag = struct.unpack_from('<I', record, 72)[0]
            if self.host_notification_counter != 0:
                self.emit('native_notification_metadata_transition', dispatch_kind=hex(kind), sequence=self._sequence, notification_counter=self.host_notification_counter, metadata_before=metadata_before, metadata_after=metadata_after, metadata_flag=metadata_flag, source_proof_sha256=SCOPE_PROOF_SHA256, empty_receiver_state_verified=True, eligible_for_training=False)
            self.emit('native_deferred_host_event_enqueued', dispatch_kind=hex(kind), queue_type='0x76', record_hex=record.hex(), source_position_blob_hex=position['position_bytes'].hex(), plot_x=position['x'], plot_y=position['y'], native_plot_word=word, metadata_before=metadata_before, metadata_after=metadata_after, metadata_flag=metadata_flag, metadata_scope_source_sha256=SCOPE_PROOF_SHA256, pending_count=len(self.pending), optional_preprocessing_hook_registered=False, queue_metadata_service_registered=False, unspecified_padding_policy='zero', original_exe_hooks_captured=False, consumer_validated=False, eligible_for_training=False, native_dispatch_return=0)
            return 0
        if kind == 3795521837:
            from civ6_host.runtime.native.native_found_city_event import decode_found_city_fields
            from civ6_host.runtime.native.native_found_city_event import query_unit_parameters
            from civ6_host.runtime.native.native_found_city_event import encode_record
            from civ6_host.runtime.native.native_found_city_event import SELECTOR
            identity = decode_found_city_fields(raw_fields, self.read)
            query = query_unit_parameters(self.core, self.context, identity, incoming_selector=identity['selector'], read=self.read) if identity['selector'] == SELECTOR else None
            record = encode_record(self._sequence + 1, identity, query, queue_callback_result=0, padding_policy='zero')
            self._enqueue(record)
            self.emit('native_deferred_host_event_enqueued', dispatch_kind=hex(kind), queue_type='0x23', record_hex=record.hex(), unit_identity=identity, native_unit_query=query, native_unit_query_required=identity['selector'] == SELECTOR, pending_count=len(self.pending), optional_preprocessing_hook_registered=False, queue_metadata_service_registered=False, unspecified_padding_policy='zero', original_exe_hooks_captured=False, consumer_validated=False, eligible_for_training=False, native_dispatch_return=0)
            return 0
        if kind == 365123683:
            from civ6_host.runtime.native.native_event_15c35863 import decode_fields
            from civ6_host.runtime.native.native_event_15c35863 import encode_queue_record
            from civ6_host.runtime.native.native_event_15c35863 import BLOB_KEY
            fields = decode_fields(raw_fields)
            if fields.selector != 0:
                raise ValueError('UnitOperationAdded selector is outside the headless profile')
            blob = copy_eight_byte_variant(raw_fields[BLOB_KEY], self.read, expected_tag=1024)
            record = encode_queue_record(self._sequence + 1, raw_fields, blob_contents=blob, hook_present=False, padding_policy='headless-zero-initialization')
            self._enqueue(record)
            self.emit('native_deferred_host_event_enqueued', dispatch_kind=hex(kind), queue_type='0x43', event_name='GameCoreEvent::UnitOperationAdded', record_hex=record.hex(), source_blob_hex=blob.hex(), pending_count=len(self.pending), optional_preprocessing_hook_registered=False, queue_metadata_service_registered=False, unspecified_padding_policy='zero', consumer_validated=False, eligible_for_training=False, native_dispatch_return=0)
            return 0
        if kind == 297827216:
            from civ6_host.runtime.native.native_event_11c07b90 import decode_fields
            from civ6_host.runtime.native.native_event_11c07b90 import encode_11c07b90_record
            fields = decode_fields(raw_fields)
            record = encode_11c07b90_record(self._sequence + 1, selector=fields['selector'])
            self._enqueue(record)
            self.emit('native_deferred_host_event_enqueued', dispatch_kind=hex(kind), queue_type='0x8', core_value=fields['value'], record_hex=record.hex(), core_value_used_by_exe_callback=False, pending_count=len(self.pending), optional_preprocessing_hook_registered=False, queue_metadata_service_registered=False, original_exe_hooks_captured=False, unspecified_padding_policy='zero', consumer_validated=False, eligible_for_training=False, native_dispatch_return=0)
            return 0
        if kind in UNARY_EVENT_SOURCES:
            source = UNARY_EVENT_SOURCES[kind]
            record = encode_core_fields(kind, self._sequence + 1, raw_fields, optional_callback_present=False, queue_hook_present=False, queue_metadata=0)
            self._enqueue(record)
            self.emit('native_deferred_host_event_enqueued', dispatch_kind=hex(kind), queue_type=hex(source['record_type']), value=int.from_bytes(record[84:88], 'little'), record_hex=record.hex(), callback_flag=source['callback_flag'], pending_count=len(self.pending), optional_preprocessing_hook_registered=False, queue_metadata_service_registered=False, original_exe_hooks_captured=False, unspecified_padding_policy='zero', consumer_validated=False, eligible_for_training=False, native_dispatch_return=0)
            return 0
        if kind == 1240186821:
            from civ6_host.runtime.native.native_event_49ebbfc5 import decode_fields
            from civ6_host.runtime.native.native_event_49ebbfc5 import encode_49ebbfc5_record
            fields = decode_fields(raw_fields)
            record = encode_49ebbfc5_record(self._sequence + 1, fields['selector'], optional_callback_present=False, queue_hook_present=False, queue_metadata=0)
            self._enqueue(record)
            self.emit('native_deferred_host_event_enqueued', dispatch_kind=hex(kind), queue_type='0xda', record_hex=record.hex(), pending_count=len(self.pending), optional_preprocessing_hook_registered=False, queue_metadata_service_registered=False, unspecified_padding_policy='zero; payload+4 is unspecified EXE stack data', original_exe_hooks_captured=False, consumer_validated=False, eligible_for_training=False, native_dispatch_return=0)
            return 0
        if kind == 2888264099:
            from civ6_host.runtime.native.native_event_ac2769 import decode_fields
            from civ6_host.runtime.native.native_event_ac2769 import encode_ac2769a3_record
            fields = decode_fields(raw_fields)
            if len(self.pending) >= self.limit:
                raise ValueError('Native event queue requires verified consumption')
            record = encode_ac2769a3_record(self._sequence + 1, fields['value'], queue_metadata=0)
            self._enqueue(record)
            self.emit('native_deferred_host_event_enqueued', dispatch_kind=hex(kind), queue_type='0xbf', selector=fields['selector'], value=fields['value'], record_hex=record.hex(), pending_count=len(self.pending), optional_preprocessing_hook_registered=False, queue_metadata_service_registered=False, unspecified_padding_policy='zero', consumer_validated=False, eligible_for_training=False, native_dispatch_return=0)
            return 0
        if kind == 3311480898 and 2717631346 in raw_fields:
            from civ6_host.runtime.native.native_event_c561 import decode_fields
            from civ6_host.runtime.native.native_event_c561 import encode_c5613042_record
            fields = decode_fields(raw_fields)
            if len(self.pending) >= self.limit:
                raise ValueError('Native event queue requires verified consumption')
            record = encode_c5613042_record(self._sequence + 1, fields['value_a'], fields['value_b'], queue_metadata=0)
            self._enqueue(record)
            self.emit('native_deferred_host_event_enqueued', dispatch_kind=hex(kind), queue_type='0xbe', value_a=fields['value_a'], value_b=fields['value_b'], record_hex=record.hex(), pending_count=len(self.pending), optional_preprocessing_hook_registered=False, queue_metadata_service_registered=False, unspecified_padding_policy='zero', consumer_validated=False, eligible_for_training=False, native_dispatch_return=0)
            return 0
        if kind == 2432381924 and 2717631346 in raw_fields:
            from civ6_host.runtime.native.native_event_90fb import decode_fields
            from civ6_host.runtime.native.native_event_90fb import encode_90fb33e4_record
            fields = decode_fields(raw_fields)
            if len(self.pending) >= self.limit:
                raise ValueError('Native event queue requires verified consumption')
            record = encode_90fb33e4_record(self._sequence + 1, fields['value_a'], fields['value_b'], queue_metadata=0)
            self._enqueue(record)
            self.emit('native_deferred_host_event_enqueued', dispatch_kind=hex(kind), queue_type='0xcb', value_a=fields['value_a'], value_b=fields['value_b'], record_hex=record.hex(), pending_count=len(self.pending), optional_preprocessing_hook_registered=False, queue_metadata_service_registered=False, unspecified_padding_policy='zero', consumer_validated=False, eligible_for_training=False, native_dispatch_return=0)
            return 0
        if kind == 2759456831:
            return self._enqueue_experience(raw_fields)
        if kind == 4171606804:
            from civ6_host.runtime.native.native_event_f8a5ab14 import decode_fields
            from civ6_host.runtime.native.native_event_f8a5ab14 import encode_record
            from civ6_host.runtime.native.native_event_f8a5ab14 import PADDING_POLICY
            from civ6_host.runtime.native.native_event_f8a5ab14 import PROOF_SHA256
            if len(self.pending) >= self.limit:
                raise RuntimeError('Native deferred queue bound exceeded')
            fields = decode_fields(raw_fields, self.read)
            record = encode_record(self._sequence + 1, fields, normalizer_transform_present=False, per_thread_hook_present=False, writer_metadata_callback_present=False, padding_policy=PADDING_POLICY, entity_listener_count=self.entity_listener_count, empty_receiver_state=self.empty_receiver_state)
            self._enqueue(record)
            self.emit('native_deferred_host_event_enqueued', dispatch_kind=hex(kind), queue_type='0x21', record_hex=record.hex(), pending_count=len(self.pending), source_proof_sha256=PROOF_SHA256, selector=fields.selector, unit_owner=fields.owner, unit_id=fields.unit_id, source_scalars=[fields.d6_value, fields.a1fbc_value, fields.value_38f], source_order_preserved=True, native_queries_executed=False, undefined_stack_ranges=['record+0x54..0x57', 'record+0x6c..0x6f'], undefined_value_policy=PADDING_POLICY, undefined_value_is_native_default=False, empty_receiver_state_verified=True, payload_exposed_to_learner=False, optional_preprocessing_hook_registered=False, queue_metadata_service_registered=False, consumer_validated=False, eligible_for_training=False, native_dispatch_return=0)
            return 0
        if kind == 2111680497:
            from civ6_host.runtime.native.native_event_7dddaff1 import decode_fields
            from civ6_host.runtime.native.native_event_7dddaff1 import encode_record
            from civ6_host.runtime.native.native_event_7dddaff1 import PADDING_POLICY
            from civ6_host.runtime.native.native_event_7dddaff1 import PROOF_SHA256
            if len(self.pending) >= self.limit:
                raise RuntimeError('Native deferred queue bound exceeded')
            fields = decode_fields(raw_fields)
            record = encode_record(self._sequence + 1, fields, normalizer_transform_present=False, per_thread_hook_present=False, writer_metadata_callback_present=False, padding_policy=PADDING_POLICY, empty_receiver_state=self.empty_receiver_state)
            self._enqueue(record)
            self.emit('native_deferred_host_event_enqueued', dispatch_kind=hex(kind), queue_type='0x7f', record_hex=record.hex(), pending_count=len(self.pending), source_proof_sha256=PROOF_SHA256, source_selector=fields[0], selector_consumed=False, source_scalars=list(fields[1:]), source_order_preserved=True, undefined_stack_ranges=['record+0x54..0x57', 'record+0x60..0x67'], undefined_value_policy=PADDING_POLICY, undefined_value_is_native_default=False, empty_receiver_state_verified=True, payload_exposed_to_learner=False, optional_preprocessing_hook_registered=False, queue_metadata_service_registered=False, consumer_validated=False, eligible_for_training=False, native_dispatch_return=0)
            return 0
        if kind == 3936998259:
            from civ6_host.runtime.native.native_event_eaa9d373 import decode_fields
            from civ6_host.runtime.native.native_event_eaa9d373 import encode_record
            from civ6_host.runtime.native.native_event_eaa9d373 import PADDING_POLICY
            from civ6_host.runtime.native.native_event_eaa9d373 import PROOF_SHA256
            if len(self.pending) >= self.limit:
                raise RuntimeError('Native deferred queue bound exceeded')
            fields = decode_fields(raw_fields)
            record = encode_record(self._sequence + 1, fields, normalizer_transform_present=False, per_thread_hook_present=False, writer_metadata_callback_present=False, padding_policy=PADDING_POLICY, empty_receiver_state=self.empty_receiver_state)
            self._enqueue(record)
            self.emit('native_deferred_host_event_enqueued', dispatch_kind=hex(kind), queue_type='0x89', record_hex=record.hex(), pending_count=len(self.pending), source_proof_sha256=PROOF_SHA256, raw_boolean_byte=fields.raw_boolean_byte, selector=fields.selector, source_scalars=[fields.d6_value, fields.a1fbc_value], source_order_preserved=True, native_queries_executed=False, undefined_stack_range='record+0x61..0x63', undefined_value_policy=PADDING_POLICY, undefined_value_is_native_default=False, empty_receiver_state_verified=True, payload_exposed_to_learner=False, optional_preprocessing_hook_registered=False, queue_metadata_service_registered=False, consumer_validated=False, eligible_for_training=False, native_dispatch_return=0)
            return 0
        if kind in TWO_VALUE_EVENT_SOURCES:
            from civ6_host.runtime.native.native_two_value_event_family import encode_core_fields as encode_two_value_fields
            from civ6_host.runtime.native.native_two_value_event_family import MISSING_B_PROOF_SHA256
            from civ6_host.runtime.native.native_deferred_empty_profile import validate_empty_profile_record
            if len(self.pending) >= self.limit:
                raise RuntimeError('Native deferred queue bound exceeded')
            shape = bytearray(96)
            struct.pack_into('<II', shape, 0, 96, int(TWO_VALUE_EVENT_SOURCES[kind]['record_type'], 16))
            validate_empty_profile_record(shape, **self.empty_receiver_state)
            record = encode_two_value_fields(kind, self._sequence + 1, raw_fields, optional_callback_present=False, queue_metadata_service_present=False)
            validate_empty_profile_record(record, **self.empty_receiver_state)
            self._enqueue(record)
            self.emit('native_deferred_host_event_enqueued', dispatch_kind=hex(kind), queue_type=TWO_VALUE_EVENT_SOURCES[kind]['record_type'], record_hex=record.hex(), pending_count=len(self.pending), optional_preprocessing_hook_registered=False, queue_metadata_service_registered=False, consumer_validated=False, eligible_for_training=False, native_dispatch_return=0)
            if 2717631346 not in raw_fields:
                self.emit('native_two_value_missing_b_enqueued', dispatch_kind=hex(kind), queue_type=TWO_VALUE_EVENT_SOURCES[kind]['record_type'], source_proof_sha256=MISSING_B_PROOF_SHA256, raw_a1fbc_present=False, normalized_b=0, record_sequence=self._sequence, record_sha256=hashlib.sha256(record).hexdigest(), empty_receiver_state_verified=True, raw_fields_mutated=False, payload_exposed_to_learner=False, consumer_validated=False, eligible_for_training=False)
            return 0
        if kind in SCALAR_NO_METADATA_SOURCES:
            from civ6_host.runtime.native.native_scalar_no_metadata_family import encode_fields
            record = encode_fields(kind, raw_fields, self._sequence + 1, optional_callback_present=False, queue_hook_present=False)
            self._enqueue(record)
            self.emit('native_deferred_host_event_enqueued', dispatch_kind=hex(kind), queue_type=hex(SCALAR_NO_METADATA_SOURCES[kind]['record_type']), record_hex=record.hex(), pending_count=len(self.pending), optional_preprocessing_hook_registered=False, queue_metadata_service_registered=False, consumer_validated=False, eligible_for_training=False, native_dispatch_return=0)
            return 0
        if kind == 3546175261:
            from civ6_host.runtime.native.native_event_d35e import decode_fields
            from civ6_host.runtime.native.native_event_d35e import encode_d35e571d_record
            fields = decode_fields(raw_fields)
            if len(self.pending) >= self.limit:
                raise ValueError('Native event queue requires verified consumption')
            record = encode_d35e571d_record(self._sequence + 1, fields['callback_value'], queue_metadata=0)
            self._enqueue(record)
            self.emit('native_deferred_host_event_enqueued', dispatch_kind=hex(kind), queue_type='0xd1', callback_value=fields['callback_value'], record_hex=record.hex(), pending_count=len(self.pending), optional_preprocessing_hook_registered=False, queue_metadata_service_registered=False, unspecified_padding_policy='zero', consumer_validated=False, eligible_for_training=False, native_dispatch_return=0)
            return 0
        if kind == 2649457383:
            from civ6_host.runtime.native.native_event_9deb import encode_9deb_fields
            if len(self.pending) >= self.limit:
                raise ValueError('Native event queue requires verified consumption')
            record = encode_9deb_fields(self._sequence + 1, raw_fields, self.read, metadata=0)
            self._enqueue(record)
            self.emit('native_deferred_host_event_enqueued', dispatch_kind=hex(kind), queue_type='0x16', record_hex=record.hex(), pending_count=len(self.pending), optional_preprocessing_hook_registered=False, queue_metadata_service_registered=False, unspecified_padding_policy='zero', consumer_validated=False, eligible_for_training=False, native_dispatch_return=0)
            return 0
        if kind == 3092339265:
            from civ6_host.runtime.native.native_unit_created_event import decode_fields
            from civ6_host.runtime.native.native_unit_created_event import query_native_values
            from civ6_host.runtime.native.native_unit_created_event import encode_record
            if len(self.pending) >= self.limit:
                raise ValueError('Native event queue requires verified consumption')
            fields = decode_fields(raw_fields, self.read)
            with query_native_values(self.base, self.context, fields['owner'], fields['identifier'], read=self.read, application=getattr(self.core, '_civ6rl_application_configuration', None), core_sha256=getattr(self, 'turn_unit_core_sha256', 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'), candidate_backend=getattr(self, 'turn_unit_backend', None)) as values:
                record = encode_record(self._sequence + 1, fields, values, visual_profile=self.visual_profile)
                self._enqueue(record)
                self.emit('native_deferred_host_event_enqueued', dispatch_kind=hex(kind), queue_type='0x1c', player_index=fields['owner'], unit_id=fields['identifier'], native_values=values, position_hex=fields['position'].hex(), record_hex=record.hex(), pending_count=len(self.pending), native_primary_interfaces_retained_during_enqueue=True, visual_profile=self.visual_profile, consumer_validated=False, eligible_for_training=False, native_dispatch_return=0)
            return 0
        if kind == ENTITY_EVENT_KIND:
            from civ6_host.runtime.native.native_entity_event import encode_c50_entity_event
            from civ6_host.runtime.native.native_entity_event import QUEUE_LIFETIME_PROOF_SHA256
            from civ6_host.runtime.native.native_deferred_empty_profile import validate_empty_profile_record
            filters = self.host.filters.entries.get(kind)
            if type(filters) is not list or filters != [(4032072631, 1)] or any((type(value) is not int for row in filters for value in row)):
                raise ValueError('Unexpected native entity-filter registration')
            if len(self.pending) >= self.limit:
                raise ValueError('Native entity event pending queue bound exceeded')
            if type(self._sequence) is not int or not 0 <= self._sequence < 2147483647:
                raise ValueError('Native entity event diagnostic sequence exhausted')
            if type(self.entity_event_count) is not int or self.entity_event_count < 0:
                raise ValueError('Native entity event telemetry counter is invalid')
            if type(self.entity_listener_count) is not int or self.entity_listener_count != 0:
                raise ValueError('Native entity event requires actual empty entity listeners')
            shape = bytearray(112)
            struct.pack_into('<II', shape, 0, 112, 25)
            validate_empty_profile_record(shape, **self.empty_receiver_state)
            fields = decode_entity_event(raw_fields, self.read)
            descriptor = struct.pack('<HHI', fields['entity_owner'], 1, fields['entity_id'])
            record = encode_c50_entity_event(self._sequence + 1, descriptor, fields['float32_bits'], queue_metadata=0, stack_padding_word=0, stack_padding_tail_word=0)
            validate_empty_profile_record(record, **self.empty_receiver_state)
            self._enqueue(record)
            self.entity_event_count += 1
            self.emit('native_deferred_host_event_enqueued', dispatch_kind=hex(kind), **fields, filter_value=1, receiver_count=0, receiver_profile='no-exe-entity-listeners', original_exe_registry_captured=False, source_branch='1caf50_absent_receiver_then_157b30_registered_producer', queue_type='0x19', record_hex=record.hex(), pending_count=len(self.pending), source_proof_sha256=QUEUE_LIFETIME_PROOF_SHA256, entity_event_count=self.entity_event_count, pending_record_limit=self.limit, cumulative_counter_is_queue_admission_limit=False, optional_preprocessing_hook_registered=False, queue_metadata_service_registered=False, unspecified_padding_policy='zero', undefined_record_ranges=[[84, 88], [100, 104]], undefined_value_is_native_default=False, empty_receiver_state_verified=True, payload_exposed_to_learner=False, consumer_validated=False, native_dispatch_return=0, eligible_for_training=False)
            return 0
        if kind == PLAYER_QUERY_EVENT_KIND:
            if set(raw_fields) != {2716180809, 3606901732} or decode_scalar(raw_fields[2716180809], 3) != 0:
                raise ValueError('Unverified native player-query event arguments')
            player = decode_scalar(raw_fields[3606901732], 2)
            from civ6_host.runtime.native.native_player_notifications import query_player_notification_values
            with self._query_player_notification_values(player) as values:
                if values is None:
                    self.emit('native_player_query_event_without_interface', dispatch_kind=hex(kind), player_index=player, native_branch='154310_null_interface', native_dispatch_return=0)
                    return 0
                if len(self.pending) >= self.limit:
                    raise ValueError('Native event queue requires verified consumption')
                record = encode_player_query_event(self._sequence + 1, player, values['getter_10_uint32'], values['getter_18_uint32'])
                self._enqueue(record)
                self.emit('native_deferred_host_event_enqueued', dispatch_kind=hex(kind), queue_type='0xc1', player_index=player, native_values=values, record_hex=record.hex(), pending_count=len(self.pending), native_interfaces_retained_during_enqueue=True, consumer_validated=False, eligible_for_training=False, native_dispatch_return=0)
            return 0
        if kind == BLOB_EVENT_KIND:
            if set(raw_fields) != {2716180809, 2353434172}:
                raise ValueError('Unverified blob notification keys')
            selector = decode_scalar(raw_fields[2716180809], 3)
            payload = copy_eight_byte_variant(raw_fields[2353434172], self.read)
            if len(self.pending) >= self.limit:
                raise ValueError('Native event queue requires verified consumption')
            record = encode_blob_event(self._sequence + 1, selector, payload)
            self._enqueue(record)
            self.emit('native_deferred_host_event_enqueued', dispatch_kind=hex(kind), queue_type='0xb6', selector=hex(selector), payload_hex=payload.hex(), record_hex=record.hex(), pending_count=len(self.pending), consumer_validated=False, eligible_for_training=False, native_dispatch_return=0)
            return 0
        if kind == 614932472:
            from civ6_host.runtime.native.native_event_24a71ff8 import dispatch_empty
            result = dispatch_empty(kind, raw_fields, self.read, normalizer_transform_present=False)
            self.emit('native_host_registered_empty_callback', dispatch_kind=hex(kind), **result, eligible_for_training=False)
            return result['native_dispatch_return']
        if kind == 4011729736:
            from civ6_host.runtime.native.native_absent_ef1e2348 import validate_absent_event
            result = validate_absent_event(kind, raw_fields, self.read, normalizer_transform_present=False)
            self.emit('native_host_event_without_registered_callback', dispatch_kind=hex(kind), native_branch='1445f0_absent_key', core_internal_dispatch_preserved=True, normalized_fields=result, native_dispatch_return=result['normalizer_result'], eligible_for_training=False)
            return result['normalizer_result']
        if kind == 3607864607:
            from civ6_host.runtime.native.native_absent_d70ba51f import validate_absent_event
            result = validate_absent_event(kind, raw_fields, self.read, normalizer_transform_present=False, registry_profile=self.callback_registry_profile, dynamic_registration_present=self.dynamic_event_registration_present, entity_listener_count=self.entity_listener_count)
            self.emit('native_host_event_without_registered_callback', dispatch_kind=hex(kind), native_branch='1445f0_absent_key', core_internal_dispatch_preserved=True, normalized_fields=result, native_dispatch_return=result['normalizer_result'], eligible_for_training=False)
            return result['normalizer_result']
        if kind == 811347465:
            from civ6_host.runtime.native.native_absent_305c2e09 import validate_absent_event
            result = validate_absent_event(kind, raw_fields, self.read, normalizer_transform_present=False, registry_profile=self.callback_registry_profile, dynamic_registration_present=self.dynamic_event_registration_present)
            self.emit('native_host_event_without_registered_callback', dispatch_kind=hex(kind), native_branch='1445f0_absent_key', core_internal_dispatch_preserved=True, normalized_fields=result, native_dispatch_return=result['normalizer_result'], eligible_for_training=False)
            return result['normalizer_result']
        if kind == 350149210:
            from civ6_host.runtime.native.native_trade_route_descriptor_events import validate_absent_event
            result = validate_absent_event(kind, raw_fields, self.read, normalizer_transform_present=False, registry_profile=self.callback_registry_profile, dynamic_registration_present=self.dynamic_event_registration_present, entity_listener_count=self.entity_listener_count)
            self.emit('native_host_event_without_registered_callback', dispatch_kind=hex(kind), native_branch='1445f0_absent_key', core_internal_dispatch_preserved=True, normalized_fields=result, native_dispatch_return=result['native_dispatch_return'], eligible_for_training=False)
            return result['native_dispatch_return']
        if kind == 1728061409:
            from civ6_host.runtime.native.native_absent_city_position_event import validate_absent_city_position_event
            result = validate_absent_city_position_event(kind, raw_fields, self.read, normalizer_transform_present=False)
            self.emit('native_host_event_without_registered_callback', dispatch_kind=hex(kind), native_branch='1445f0_absent_key', core_internal_dispatch_preserved=True, normalized_fields=result, native_dispatch_return=result['normalizer_result'], eligible_for_training=False)
            return result['normalizer_result']
        if kind in UNREGISTERED_SCALAR_KINDS:
            expected = {2716180809, 3606901732} if kind == UNREGISTERED_PLAYER_CREATED else ARGUMENT_KEYS
            if set(raw_fields) != expected:
                raise ValueError('Unverified fields for unregistered player event')
            from civ6_host.runtime.native.native_absent_scalar_a0 import validate_absent_scalar_a0
            validate_absent_scalar_a0(kind, raw_fields)
            player = decode_scalar(raw_fields[3606901732], 2)
            if len(self.unregistered_player_events) >= self.limit:
                raise ValueError('Unregistered scalar diagnostic ledger bound exceeded')
            self.unregistered_player_events.append((kind, player))
            self.emit('native_host_event_without_registered_callback', dispatch_kind=hex(kind), player_index=player, native_branch='1445f0_absent_key', source_registrar_rva='0x14d7a0', native_dispatch_return=0)
            return 0
        if kind not in EXE_EVENT_CALLBACKS and set(raw_fields) in ({2716180809}, {2716180809, 3606901732}, {2716180809, 2717631346, 3606901732}):
            from civ6_host.runtime.native.native_absent_scalar_a0 import validate_absent_scalar_a0
            validate_absent_scalar_a0(kind, raw_fields)
            self.emit('native_host_event_without_registered_callback', dispatch_kind=hex(kind), native_branch='1445f0_absent_key', core_internal_dispatch_preserved=True, source_registrar_rva='0x14d7a0', native_dispatch_return=0, eligible_for_training=False)
            return 0
        if kind not in (EVENT_KIND, INTEGER_EVENT_KIND):
            pointer_payloads = self._capture_pointer_payloads(raw_fields)
            extra = {}
            if kind == 2186730465:
                from civ6_host.runtime.native.native_combat_argument_snapshot import capture_borrowed_children
                try:
                    extra['diagnostic_combat_children'] = capture_borrowed_children(kind, raw_fields, self.base, self.read, self.next_node)
                except (ValueError, RuntimeError, OSError) as exc:
                    extra['diagnostic_combat_children'] = {'capture_error': repr(exc), 'callback_admitted': False, 'result_substituted': False, 'eligible_for_training': False}
            self.host._fatal('unimplemented deferred native event kind', interface='host', slot='0xa0', dispatch_kind=hex(kind), result_substituted=False, fields={hex(k): v.hex() for k, v in raw_fields.items()}, diagnostic_pointer_payloads=pointer_payloads, **extra)
        if set(raw_fields) != ARGUMENT_KEYS:
            raise ValueError('Unverified native event argument keys')
        fields = {key: decode_scalar(raw, 3 if key == 2716180809 else 2) for key, raw in raw_fields.items()}
        if set(fields) != ARGUMENT_KEYS or fields[2716180809] != 0:
            raise ValueError('Unverified event selector or missing fields')
        player, value = (fields[3606901732], fields[2717631346])
        if len(self.pending) >= self.limit:
            raise ValueError('Native event queue needs its verified consumer before continuing')
        if kind == EVENT_KIND:
            value = value != 0
            record = encode_player_event(self._sequence + 1, player, value)
            queue_type = '0x10c'
        else:
            record = encode_integer_player_event(self._sequence + 1, player, value)
            queue_type = '0x109'
        self._enqueue(record)
        self.emit('native_deferred_host_event_enqueued', dispatch_kind=hex(kind), queue_type=queue_type, player_index=player, value=value, record_hex=record.hex(), pending_count=len(self.pending), consumer_validated=False, optional_presentation_hook_registered=False, eligible_for_training=False, native_dispatch_return=0)
        return 0

    def _query_player_notification_values(self, player):
        from civ6_host.runtime.native.native_player_notifications import query_player_notification_values
        return query_player_notification_values(self.base, self.context, player)

class NativeDeferredHostEvents(DeferredHostQueue, HostControllerQuery, SharedHostEventDispatch):

    def __init__(self, host, core, context, emit, *, entity_observer_profile, visual_profile, limit=4096):
        if entity_observer_profile != 'no-exe-entity-listeners':
            raise ValueError('EXE entity receiver registration is not implemented')
        self.entity_listener_count = 0
        from civ6_host.runtime.native.native_unit_created_event import VISUAL_PROFILE
        if visual_profile != VISUAL_PROFILE:
            raise ValueError('EXE visual profile is not implemented')
        self.visual_profile = visual_profile
        from civ6_host.runtime.native.native_absent_305c2e09 import REGISTRY_PROFILE
        self.callback_registry_profile = REGISTRY_PROFILE
        self.dynamic_event_registration_present = False
        if any((EXE_EVENT_CALLBACKS.get(k) != v for k, v in ((EVENT_KIND, 1356320), (INTEGER_EVENT_KIND, 1357776), (BLOB_EVENT_KIND, 1360416), (PLAYER_QUERY_EVENT_KIND, 1393424), (3092339265, 1395808), (ENTITY_EVENT_KIND, 1407792), (2649457383, 1412384), (3546175261, 1348640), (2432381924, 1344352), (3311480898, 1321296), (2888264099, 1321728), (507110547, 1362368), (559109511, 1393648), (1240186821, 1346224), (3555948358, 1354848), (297827216, 1349536), (365123683, 1409104), (3795521837, 1395248), (2274153042, 1337680), (2303979814, 1359632), (3659576915, 1337520), (1852022915, 1349760), (899089314, 1306592), (1027606258, 1409968), (2188544486, 1361056), (4110293858, 1360576), (2787493670, 1347744), (3853650818, 1347280), (3241152231, 1413520), (643323895, 1385056), (424708295, 1384704), (2599060777, 1385216), (3247915626, 1386432), (529806097, 1361344), (2414808462, 1350208), (1072344322, 1321008), (2070282030, 1386256), (4067375823, 1352576), (4200272217, 1314800), (1561280532, 1386080), (468001286, 1394272), (869823066, 1386592), (1722672051, 1393984), (487601156, 1315232), (1193679485, 1331152), (3273144578, 1328720), (685173694, 1332192), (1836147632, 1329968), (1372081338, 1319120), (2582142662, 1319296), (2785224901, 1409392), (3405989361, 1409680), (272736031, 1317040), (943090161, 1410256), (2597437472, 1352944), (4217315035, 1319840), (490036867, 1320336), (723230968, 1315888), (94203074, 1358880), (2075911904, 1314624), (689003850, 1316144), (3727501331, 1316864), (130563502, 1309488), (443673072, 1346368), (4222460616, 1319648), (3270739392, 1320816), (1099678774, 1316496), (58334190, 1313872), (3865055911, 1310064), (830651534, 1317632), (2365609745, 1315056), (3565292211, 1316688), (821819602, 1318944), (1408378902, 1319472), (2987879876, 1398624), (2842556304, 1394352), (827191705, 1382768), (3209231784, 1391552), (1920266315, 1394640), (58288157, 1403344), (1169483000, 1400960), (3424348260, 1400960), (3765759732, 1313408), (477734356, 1391296), (2175010909, 1357056), (2551878022, 1394928), (3635281265, 1411312), (2397249135, 1406512), (2620687093, 1403632), (2381973687, 1403904), (675466772, 1317440), (2454269782, 1318560), (4260438819, 1331872), (3188855816, 1407152), (3918721997, 1408160), (1294624025, 1318752), (2271638628, 1321456), (1853815079, 1406688), (39808253, 1352160), (1854549907, 1408448), (3007926567, 1336608), (2314915267, 1406512), (4129408428, 1384112), (1448787494, 1354592), (3254088469, 1397616), (1289970298, 1397616), (3936998259, 1327744), (2186730465, 1322976), (4171606804, 1399504), (2759456831, 1401264), (1967963419, 1405920), (4236097886, 1398912), (1914843435, 1400384), (1712392665, 1410848), (1265909993, 1413232), (902065822, 1406224), (1716139958, 1398336), (2603175280, 1404480), (4086421427, 1348112), (3629625883, 1347072), (816720445, 1347520), (3892879390, 1315712), (2313036916, 1316320), (2979910027, 1308992), (2910348563, 1308704), (1169496022, 1417984), (2980214136, 1347952), (4152393721, 1337360), (330185301, 1392416)))):
            raise ValueError('Native callback registration evidence changed')
        if any((k in EXE_EVENT_CALLBACKS for k in UNREGISTERED_SCALAR_KINDS)):
            raise ValueError('An admitted missing-callback kind has a registered handler')
        if any((EXE_EVENT_CALLBACKS.get(kind) != int(source['callback_va'], 16) - 5368709120 for kind, source in UNARY_EVENT_SOURCES.items())):
            raise ValueError('Unary event source and EXE callback registry disagree')
        if any((EXE_EVENT_CALLBACKS.get(kind) != int(source['callback_va'], 16) - 5368709120 for kind, source in TWO_VALUE_EVENT_SOURCES.items())):
            raise ValueError('Two-value event source and EXE callback registry disagree')
        from civ6_host.runtime.native.native_unit_descriptor_event_family import verify_source_evidence as verify_unit_family
        verify_unit_family()
        self.host, self.base, self.emit = (host, core._handle, emit)
        self.core = core
        self.context = context
        self.ui_cache_map_snapshot = None
        self.read = local_reader()
        self.next_node = C.WINFUNCTYPE(C.c_void_p, C.c_void_p)(self.base + 7582736)
        self.pending: list[bytes] = []
        self.private_progress_ring = None
        self._sequence = 0
        self.consumed_count = 0
        self.consumed_bytes = 0
        self.consumed_digest = hashlib.sha256()
        self.empty_receiver_state = dict(observer_registered=False, state_pointer_nonnull=True, pre_hook=None, post_hook=None, subscriber_count=0, state_flags=0)
        self.pre_turn_immediate_state = self.empty_receiver_state.copy()
        from civ6_host.runtime.native.native_event_turn_status import TurnBeginAuxiliaryState
        self.turn_begin_state = TurnBeginAuxiliaryState(service_flags=0)
        host._bind(host.vtable, 288, C.c_uint8, [C.c_void_p], self.controller_flag)
        from civ6_host.runtime.native.native_host_slot_e8 import INITIAL_COUNTER
        self.host_notification_counter = INITIAL_COUNTER
        host._bind(host.vtable, 232, None, [C.c_void_p, C.c_uint32], self.host_notification)
        from civ6_host.runtime.native.native_host_slot_f0 import INITIAL_METADATA_COUNTER
        self.host_metadata_counter = INITIAL_METADATA_COUNTER
        host._bind(host.vtable, 240, None, [C.c_void_p, C.c_uint32], self.host_notification_end)
        self.ui_cache_callbacks_enabled = False
        self.normalizer_transform_present = False
        self.retained_game_getter = None
        self.retained_natural_wonder_publisher = None
        self.retained_cache_facades = None
        self._36c9_producing = False
        self._36c9_poisoned = False
        self.retained_combat_predicate = None
        self.combat_map_registry = None
        self.combat_receiver = None
        self.diplomacy_receiver = None
        self.pending_diplomacy_statements = []
        self.unregistered_player_events: list[tuple[int, int]] = []
        self.entity_event_count = 0
        self.limit = limit
        host._bind(host.vtable, 160, C.c_int32, [C.c_void_p, C.c_uint32, C.c_void_p], self.dispatch)
        host._bind(host.vtable, 192, C.c_uint32, [C.c_void_p, C.c_uint32, C.c_uint32, C.c_void_p], self.status_message)
        self.cache_update_callback_pair = None
        host._bind(host.vtable, 176, C.c_int32, [C.c_void_p, C.c_uint32, C.c_uint64], self.cache_update)
        self.emit('native_entity_observer_profile', profile=entity_observer_profile, receiver_count=0, original_exe_registry_captured=False, registration_api_implemented=False, eligible_for_training=False)
        self.emit('native_visual_registry_profile', profile=visual_profile, style_entry_count=0, game_mode_source='native_GAME_MODE_variant', original_exe_registry_captured=False, eligible_for_training=False)

    def admit_initialized_ui_cache_profile(self, initialization_profile, dimensions, *, full_facade_initialization_reproduced=False, cache_map_snapshot=None):
        if initialization_profile != 'public-cache-facade' or self.ui_cache_callbacks_enabled:
            raise ValueError('Unsupported or duplicate initialized UI cache profile')
        if len(dimensions) != 3 or any((type(v) is not int or v <= 0 for v in dimensions)) or dimensions[0] * dimensions[1] != dimensions[2]:
            raise ValueError('Native public cache publication must be validated first')
        if cache_map_snapshot is not None:
            if full_facade_initialization_reproduced is not True or type(cache_map_snapshot) is not bytes or len(cache_map_snapshot) != 28 or (struct.unpack_from('<iii', cache_map_snapshot) != tuple(dimensions)):
                raise ValueError('Native public map snapshot differs from its published dimensions')
        self.ui_cache_map_snapshot = cache_map_snapshot
        self.ui_cache_callbacks_enabled = True
        self.emit('native_host_ui_cache_callback_profile', profile='initialized-public-ui-cache-no-exe-hooks', gate_enabled=True, public_population_returned=True, native_dimensions=list(dimensions), copied_map_snapshot_hex=cache_map_snapshot.hex() if cache_map_snapshot is not None else None, full_exe_facade_initialization_reproduced=full_facade_initialization_reproduced, original_exe_lifecycle_reproduced=False, eligible_for_training=False)

    def bind_retained_game_getter(self, getter):
        if not self.ui_cache_callbacks_enabled or not callable(getter) or self.retained_game_getter is not None:
            raise ValueError('Retained Game getter requires one initialized facade binding')
        self.retained_game_getter = getter

    def bind_retained_combat_predicate(self, predicate):
        if not self.ui_cache_callbacks_enabled or not callable(predicate) or self.retained_combat_predicate is not None:
            raise RuntimeError('Combat predicate needs one initialized retained facade binding')
        self.retained_combat_predicate = predicate

    def bind_natural_wonder_facades(self, publisher):
        """Retain the exact initialized publisher/facades used by the cache queries."""
        from civ6_host.runtime.native.native_player_view import NativePlayerViewPublisher
        if type(publisher) is not NativePlayerViewPublisher or publisher.core is not self.core or publisher.context != self.context or (publisher._closed is not False) or (publisher.native_cache_gate is not True) or (publisher.full_facade_initialization_reproduced is not True) or (publisher.initialization_profile != 'public-cache-facade') or (publisher._owner_thread_id != __import__('threading').get_ident()) or (publisher._facades is None) or (self.retained_cache_facades is not None):
            raise RuntimeError('36C9 requires one live, initialized public cache publisher')
        facades = publisher._facades
        backend = getattr(facades, 'backend', None)
        if backend is None or getattr(backend, 'core_base', None) != self.base or (not callable(getattr(backend, 'context_alive', None))) or (backend.context_alive() is not True) or (type(getattr(facades, 'cache_service', None)) is not int) or (facades.cache_service <= 0):
            raise RuntimeError('36C9 cache facade is not retained by this live Core')
        self.retained_natural_wonder_publisher = publisher
        self.retained_cache_facades = facades

    def _enqueue_district_combat_changed(self, raw_fields):
        core_sha256 = getattr(self, 'district_damage_core_sha256', 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3')
        from civ6_host.runtime.native import native_event_47261a7d as event
        from civ6_host.runtime.native.native_deferred_empty_profile import validate_empty_profile_record
        if not getattr(self, 'ui_cache_callbacks_enabled', False):
            raise ValueError('DistrictCombatChanged requires initialized native cache facades')
        if len(self.pending) >= self.limit:
            raise RuntimeError('Native deferred queue bound exceeded')
        if type(self._sequence) is not int or not 0 <= self._sequence < 2147483647:
            raise ValueError('DistrictCombatChanged sequence exceeds the diagnostic domain')
        if type(self.entity_listener_count) is not int or self.entity_listener_count != 0:
            raise ValueError('DistrictCombatChanged requires the closed entity-listener profile')
        shape = bytearray(event.RECORD_SIZE)
        struct.pack_into('<II', shape, 0, event.RECORD_SIZE, event.RECORD_TYPE)
        validate_empty_profile_record(shape, **self.empty_receiver_state)
        fields = event.decode_fields(raw_fields, self.read)
        profile = dict(padding_policy=event.PADDING_POLICY, empty_receiver_state=dict(self.empty_receiver_state), notification_counter=self.host_notification_counter, metadata_counter=self.host_metadata_counter, per_thread_hook_present=False, writer_metadata_callback_present=False)
        event.validate_profile(self._sequence + 1, fields, **profile)
        before = (self._sequence, len(self.pending), self.host_notification_counter, self.host_metadata_counter)
        self._district_combat_producing = True
        self._district_combat_poisoned = True
        try:
            with event.produce_record_lease(self._sequence + 1, fields, core=self.core, context=self.context, read=self.read, normalizer_transform_present=False, profile=profile, core_sha256=core_sha256) as (record, query):
                if before != (self._sequence, len(self.pending), self.host_notification_counter, self.host_metadata_counter):
                    raise RuntimeError('DistrictCombatChanged native queries changed the host queue or scope')
                validate_empty_profile_record(record, **self.empty_receiver_state)
                self._enqueue(record)
            self.emit('native_deferred_host_event_enqueued', dispatch_kind=hex(event.EVENT_KIND), queue_type='0xa1', record_hex=record.hex(), pending_count=len(self.pending), owner=fields.owner, item_id=fields.item_id, selector=hex(fields.selector), source_proof_sha256=_district_source.source_sha(core_sha256, event.SOURCE_PROOF_SHA256), retained_source_live_at_enqueue=query['item_present'], source_lease_completed=True, consumer_validated=False, unspecified_padding_policy=event.PADDING_POLICY, eligible_for_training=False, native_dispatch_return=0, **query)
            self.emit('native_district_combat_change_query_completed', dispatch_kind=hex(event.EVENT_KIND), sequence=self._sequence, owner=fields.owner, item_id=fields.item_id, source_proof_sha256=_district_source.source_sha(core_sha256, event.SOURCE_PROOF_SHA256), native_dispatch_return=0, source_lease_completed=True, pending_count=len(self.pending), eligible_for_training=False, **query)
            self._district_combat_poisoned = False
            return 0
        finally:
            self._district_combat_producing = False

    def _enqueue_e660_building_pillaged(self, raw_fields):
        from civ6_host.runtime.native import native_event_e660_building_pillaged as event
        from civ6_host.runtime.native.native_deferred_empty_profile import validate_empty_profile_record
        if not getattr(self, 'ui_cache_callbacks_enabled', False):
            raise ValueError('BuildingPillaged requires initialized native cache facades')
        if len(self.pending) >= self.limit:
            raise RuntimeError('Native deferred queue bound exceeded')
        if type(self._sequence) is not int or not 0 <= self._sequence < 2147483647:
            raise ValueError('BuildingPillaged sequence exceeds the diagnostic domain')
        if type(self.entity_listener_count) is not int or self.entity_listener_count != 0:
            raise ValueError('BuildingPillaged requires the closed entity-listener profile')
        shape = bytearray(event.RECORD_SIZE)
        struct.pack_into('<II', shape, 0, event.RECORD_SIZE, event.RECORD_TYPE)
        validate_empty_profile_record(shape, **self.empty_receiver_state)
        fields = event.decode_fields(raw_fields, self.read)
        profile = dict(padding_policy=event.PADDING_POLICY, empty_receiver_state=dict(self.empty_receiver_state), notification_counter=self.host_notification_counter, metadata_counter=self.host_metadata_counter, per_thread_hook_present=False, writer_metadata_callback_present=False)
        event.validate_profile(self._sequence + 1, fields, **profile)
        before = (self._sequence, len(self.pending), self.host_notification_counter, self.host_metadata_counter)
        self._building_pillage_producing = True
        self._building_pillage_poisoned = True
        try:
            with event.produce_record_lease(self._sequence + 1, fields, core=self.core, context=self.context, read=self.read, normalizer_transform_present=False, profile=profile) as (record, query):
                if before != (self._sequence, len(self.pending), self.host_notification_counter, self.host_metadata_counter):
                    raise RuntimeError('BuildingPillaged native queries changed the host queue or scope')
                validate_empty_profile_record(record, **self.empty_receiver_state)
                self._enqueue(record)
            self.emit('native_deferred_host_event_enqueued', dispatch_kind=hex(event.EVENT_KIND), queue_type='0xaa', record_hex=record.hex(), pending_count=len(self.pending), city_owner=fields.city_owner, city_id=fields.city_id, selector=hex(fields.selector), d6_value=fields.d6_value, a1fbc_value=fields.a1fbc_value, source_proof_sha256=event.SOURCE_PROOF_SHA256, retained_source_live_at_enqueue=query['plot_present'], source_lease_completed=True, consumer_validated=False, unspecified_padding_policy=event.PADDING_POLICY, eligible_for_training=False, native_dispatch_return=0, **query)
            self.emit('native_building_pillage_query_completed', dispatch_kind=hex(event.EVENT_KIND), sequence=self._sequence, city_owner=fields.city_owner, city_id=fields.city_id, source_proof_sha256=event.SOURCE_PROOF_SHA256, native_dispatch_return=0, source_lease_completed=True, pending_count=len(self.pending), eligible_for_training=False, **query)
            self._building_pillage_poisoned = False
            return 0
        finally:
            self._building_pillage_producing = False

    def _enqueue_district_damage_changed(self, raw_fields):
        core_sha256 = getattr(self, 'district_damage_core_sha256', 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3')
        from civ6_host.runtime.native import native_event_f74afc79 as event
        from civ6_host.runtime.native.native_deferred_empty_profile import validate_empty_profile_record
        if not getattr(self, 'ui_cache_callbacks_enabled', False):
            raise ValueError('DistrictDamageChanged requires initialized native cache facades')
        if len(self.pending) >= self.limit:
            raise RuntimeError('Native deferred queue bound exceeded')
        if type(self._sequence) is not int or not 0 <= self._sequence < 2147483647:
            raise ValueError('DistrictDamageChanged sequence exceeds the diagnostic domain')
        if type(self.entity_listener_count) is not int or self.entity_listener_count != 0:
            raise ValueError('DistrictDamageChanged requires the closed entity-listener profile')
        shape = bytearray(event.RECORD_SIZE)
        struct.pack_into('<II', shape, 0, event.RECORD_SIZE, event.RECORD_TYPE)
        validate_empty_profile_record(shape, **self.empty_receiver_state)
        fields = event.decode_fields(raw_fields, self.read)
        profile = dict(padding_policy=event.PADDING_POLICY, empty_receiver_state=dict(self.empty_receiver_state), notification_counter=self.host_notification_counter, metadata_counter=self.host_metadata_counter, per_thread_hook_present=False, writer_metadata_callback_present=False)
        event.validate_profile(self._sequence + 1, fields, **profile)
        before = (self._sequence, len(self.pending), self.host_notification_counter, self.host_metadata_counter)
        self._district_damage_producing = True
        self._district_damage_poisoned = True
        try:
            with event.produce_record_lease(self._sequence + 1, fields, core=self.core, context=self.context, read=self.read, normalizer_transform_present=False, profile=profile, core_sha256=core_sha256) as (record, query):
                if before != (self._sequence, len(self.pending), self.host_notification_counter, self.host_metadata_counter):
                    raise RuntimeError('DistrictDamageChanged native queries changed the host queue or scope')
                validate_empty_profile_record(record, **self.empty_receiver_state)
                self._enqueue(record)
            self.emit('native_deferred_host_event_enqueued', dispatch_kind=hex(event.EVENT_KIND), queue_type='0x9f', record_hex=record.hex(), pending_count=len(self.pending), owner=fields.owner, item_id=fields.item_id, selector=hex(fields.selector), source_proof_sha256=_district_source.source_sha(core_sha256, event.SOURCE_PROOF_SHA256), retained_source_live_at_enqueue=query['item_present'], source_lease_completed=True, consumer_validated=False, unspecified_padding_policy=event.PADDING_POLICY, eligible_for_training=False, native_dispatch_return=0, **query)
            self.emit('native_district_damage_change_query_completed', dispatch_kind=hex(event.EVENT_KIND), sequence=self._sequence, owner=fields.owner, item_id=fields.item_id, source_proof_sha256=_district_source.source_sha(core_sha256, event.SOURCE_PROOF_SHA256), native_dispatch_return=0, source_lease_completed=True, pending_count=len(self.pending), eligible_for_training=False, **query)
            self._district_damage_poisoned = False
            return 0
        finally:
            self._district_damage_producing = False

    def _enqueue_combat(self, raw_fields, borrowed_argument):
        _core_sha256 = getattr(self, 'combat_core_sha256', 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3')
        from civ6_host.runtime.native.native_combat_receiver import validate_receiver_profile
        from civ6_host.runtime.native.native_combat_receiver import PADDING_POLICY
        from civ6_host.runtime.native.native_combat_map_owner import NativeCombatMapOwner
        from civ6_host.runtime.native.native_combat_map_owner import CombatMapRegistry
        from civ6_host.runtime.native.native_combat_map_owner import PROOF_SHA256
        from civ6_host.runtime.native.native_event_8256dbe1 import decode_fields
        from civ6_host.runtime.native.native_event_8256dbe1 import query_inputs
        from civ6_host.runtime.native.native_event_8256dbe1 import encode_record
        validate_receiver_profile(self.empty_receiver_state)
        if self.host_notification_counter != 0:
            raise ValueError('Nonzero combat notification metadata scope is not modeled')
        if not self.ui_cache_callbacks_enabled or not callable(self.retained_combat_predicate) or type(borrowed_argument) is not int or (borrowed_argument <= 0):
            raise RuntimeError('Combat requires the original borrowed map and retained predicate')
        if len(self.pending) >= self.limit or self._sequence >= 2147483647:
            raise RuntimeError('Combat producer has no bounded queue capacity')
        if getattr(self, '_combat_producer_poisoned', False):
            raise RuntimeError('Combat producer is poisoned after an incomplete callback')
        if self.combat_map_registry is None:
            self.combat_map_registry = CombatMapRegistry(limit=min(self.limit, 1024), **{'core_sha256': _core_sha256} if _core_sha256 != 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3' else {})
        registry = self.combat_map_registry
        if len(registry.entries) >= registry.limit or registry.next_id >= 4294967295:
            raise RuntimeError('Combat map registry has no bounded capacity')
        owner = None
        try:
            owner = NativeCombatMapOwner(self.core, borrowed_argument, read=self.read, **{'core_sha256': _core_sha256} if _core_sha256 != 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3' else {})
            token = registry.insert(owner)
            fields = decode_fields(raw_fields, self.base, self.read, self.next_node, **{'core_sha256': _core_sha256} if _core_sha256 != 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3' else {})
            results = tuple((None if value is None else self.retained_combat_predicate(value) for value in query_inputs(fields)))
            record = encode_record(self._sequence + 1, token, fields, results, padding_bytes=bytes(8), normalizer_transform_present=False, per_thread_hook_present=False, writer_metadata_callback_present=False)
            self._enqueue(record)
        except Exception as exc:
            self._combat_producer_poisoned = True
            if owner is not None:
                exc.native_combat_map_owner = owner
            raise
        self.emit('native_deferred_host_event_enqueued', dispatch_kind='0x8256dbe1', queue_type='0xf8', record_hex=record.hex(), pending_count=len(self.pending), consumer_validated=False, eligible_for_training=False, native_dispatch_return=0)
        self.emit('native_combat_record_enqueued', dispatch_kind='0x8256dbe1', queue_type='0xf8', token=token, record_hex=record.hex(), source_proof_sha256=_combat_source.source_sha(_core_sha256, PROOF_SHA256), owned_root_field_count=owner.source_count, native_deep_copy_executed=True, owned_map_retained_until_post_hook=True, padding_policy=PADDING_POLICY, query_inputs=query_inputs(fields), query_results=results, registry_live_maps=len(registry.entries), pending_count=len(self.pending), callback_completed=True, eligible_for_training=False, native_dispatch_return=0, **_combat_source.administrative_snapshot_policy(_core_sha256))
        return 0

    def _enqueue_diplomacy_statement(self, raw_fields, borrowed_argument):
        from civ6_host.runtime.native import native_diplomacy_statement as statement
        from civ6_host.runtime.native.native_combat_map_owner import NativeCombatMapOwner
        from civ6_host.runtime.native.native_combat_map_owner import CombatMapRegistry
        from civ6_host.runtime.native.native_combat_receiver import validate_receiver_profile
        from civ6_host.runtime.native.native_event_argument_tree import read_event_fields
        validate_receiver_profile(self.empty_receiver_state)
        statement.verify_source_evidence()
        if not self.ui_cache_callbacks_enabled or self.normalizer_transform_present is not False or (not callable(self.retained_game_getter)) or (self.retained_cache_facades is None) or (self.host_notification_counter != 0) or (self.host_metadata_counter != 0) or (type(borrowed_argument) is not int) or (borrowed_argument <= 0):
            raise RuntimeError('Statement requires the initialized native map/facade profile')
        if getattr(self, '_diplomacy_producing', False) or getattr(self, '_diplomacy_poisoned', False) or len(self.pending) >= self.limit or (len(self.pending_diplomacy_statements) >= self.limit) or (self._sequence >= 2147483647):
            raise RuntimeError('Statement producer is active, poisoned or full')
        if self.combat_map_registry is None:
            self.combat_map_registry = CombatMapRegistry(limit=min(self.limit, 1024))
        registry = self.combat_map_registry
        if len(registry.entries) >= registry.limit or registry.next_id >= 4294967295:
            raise RuntimeError('Shared native map registry has no capacity')
        owner = None
        self._diplomacy_producing = True
        try:
            owner = NativeCombatMapOwner(self.core, borrowed_argument, read=self.read)
            token = registry.insert(owner)
            copied = read_event_fields(owner.pointer, self.base, self.read, self.next_node)
            fields = statement.decode_fields(copied, self.read)
            effects = statement.apply_effects(self.core, self.context, self.read, self.turn_begin_state, self.retained_game_getter, self.retained_cache_facades, fields)
            record = statement.encode_record(self._sequence + 1, owner.pointer, fields, padding_bytes=bytes(7))
            self._enqueue(record)
        except BaseException as exc:
            self._diplomacy_poisoned = True
            if owner is not None:
                exc.native_diplomacy_map_owner = owner
            raise
        finally:
            self._diplomacy_producing = False
        self.emit('native_diplomacy_statement_enqueued', dispatch_kind='0xfc731e25', queue_type='0x84', token=token, record_hex=record.hex(), owned_map_field_count=owner.source_count, native_deep_copy_executed=True, effects=effects, pending_count=len(self.pending), source_proof_sha256=statement.PROOF_SHA256, padding_policy=statement.PADDING_POLICY, consumer_validated=False, automatic_response=False, native_dispatch_return=0, eligible_for_training=False)
        return 0

    def status_message(self, receiver, kind, target_value, argument_pointer):
        self.host._check(receiver)
        from civ6_host.runtime.native.native_host_slot_c0 import dispatch_status_message
        from civ6_host.runtime.native.native_host_slot_c0 import PROOF_SHA256
        from civ6_host.runtime.native.native_host_slot_c0 import PADDING_POLICY
        from civ6_host.runtime.native.native_event_argument_tree import read_event_fields
        if not self.ui_cache_callbacks_enabled or not callable(self.retained_game_getter) or getattr(self, '_status_producer_poisoned', False):
            raise RuntimeError('Status message requires a live initialized, unpoisoned host')
        result = dispatch_status_message(kind, target_value, argument_pointer, retained_game_getter=self.retained_game_getter, read_fields=lambda pointer: read_event_fields(pointer, self.base, self.read, self.next_node), read=self.read, sequence=self._sequence + 1, empty_receiver_state=self.empty_receiver_state, padding_policy=PADDING_POLICY, writer_metadata_callback_present=False, per_thread_hook_present=False)
        record = result.pop('record')
        if record is not None:
            if self.host_notification_counter != 0:
                raise ValueError('Status message notification metadata scope is not implemented')
            try:
                self._enqueue(record)
                self.emit('native_deferred_host_event_enqueued', host_slot='0xc0', queue_type='0xf7', record_hex=record.hex(), pending_count=len(self.pending), source_proof_sha256=PROOF_SHA256, consumer_validated=False, eligible_for_training=False, native_dispatch_return=0)
            except BaseException:
                self._status_producer_poisoned = True
                raise
        self.emit('native_host_status_message_completed', slot='0xc0', metadata_argument=kind, target_value=target_value, **result, record_enqueued=record is not None, source_proof_sha256=PROOF_SHA256, source_order_preserved=True, native_getter_called=True, gameplay_result_substituted=False, payload_exposed_to_learner=False, eligible_for_training=False, native_dispatch_return=0)
        return 0

    def _enqueue_experience(self, raw_fields):
        _core_sha256 = getattr(self, 'combat_core_sha256', 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3')
        from civ6_host.runtime.native.native_event_a479f83f import decode_fields
        from civ6_host.runtime.native.native_event_a479f83f import validate_profile
        from civ6_host.runtime.native.native_event_a479f83f import encode_experience
        from civ6_host.runtime.native.native_event_a479f83f import encode_promotion
        from civ6_host.runtime.native.native_event_a479f83f import PADDING_POLICY
        from civ6_host.runtime.native.native_event_a479f83f import PROOF_SHA256
        from civ6_host.runtime.native.native_unit_promotion_query import query_and_emit_promotion
        if getattr(self, '_experience_producer_poisoned', False):
            raise RuntimeError('Experience callback is poisoned; replay is forbidden')
        if self.host_notification_counter != 0:
            raise ValueError('Experience callback metadata scope is not implemented')
        if len(self.pending) + 2 > self.limit or self._sequence > 2147483645:
            raise RuntimeError('Experience callback requires room for both possible records')
        profile = dict(normalizer_transform_present=False, experience_hook_present=False, promotion_hook_present=False, writer_metadata_callback_present=False, entity_listener_count=self.entity_listener_count, padding_policy=PADDING_POLICY, empty_receiver_state=self.empty_receiver_state)
        validate_profile(**profile)
        fields = decode_fields(raw_fields, self.read)
        emitted = []

        def commit(record):
            self._enqueue(record)
            kind = int.from_bytes(record[4:8], 'little')
            emitted.append(kind)
            self.emit('native_deferred_host_event_enqueued', dispatch_kind='0xa479f83f', queue_type=hex(kind), record_hex=record.hex(), pending_count=len(self.pending), source_proof_sha256=_combat_source.source_sha(_core_sha256, PROOF_SHA256), consumer_validated=False, eligible_for_training=False, callback_completed=False, native_dispatch_return=None)
        try:
            commit(encode_experience(self._sequence + 1, fields, **profile))
            query = query_and_emit_promotion(self.core, self.context, fields, lambda value: commit(encode_promotion(self._sequence + 1, fields, value, **profile)), read=self.read, **{'core_sha256': _core_sha256} if _core_sha256 != 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3' else {})
        except BaseException:
            self._experience_producer_poisoned = True
            raise
        self.emit('native_experience_callback_completed', dispatch_kind='0xa479f83f', unit_owner=fields.owner, unit_id=fields.unit_id, query=query, enqueued_types=emitted, source_proof_sha256=_combat_source.source_sha(_core_sha256, PROOF_SHA256), source_order_preserved=True, callback_completed=True, payload_exposed_to_learner=False, eligible_for_training=False, native_dispatch_return=0)
        return 0

    def _enqueue_project_completion(self, raw_fields):
        from civ6_host.runtime.native.native_event_3182bc8e_project import decode_fields
        from civ6_host.runtime.native.native_event_3182bc8e_project import iter_records
        from civ6_host.runtime.native.native_event_3182bc8e_project import STACK_POLICY
        from civ6_host.runtime.native.native_event_3182bc8e_project import PINNED_EVIDENCE_SHA256
        from civ6_host.runtime.native.native_deferred_empty_profile import validate_empty_profile_record
        if not self.ui_cache_callbacks_enabled or not callable(self.retained_game_getter):
            raise RuntimeError('Project completion requires the retained native Game getter')
        if len(self.pending) + 3 > self.limit or self._sequence > 4294967292:
            raise RuntimeError('Project completion requires capacity and sequence space for three records')
        for size, kind in ((112, 96), (128, 99), (128, 100)):
            shape = bytearray(size)
            struct.pack_into('<II', shape, 0, size, kind)
            validate_empty_profile_record(shape, **self.empty_receiver_state)
        fields = decode_fields(raw_fields, self.read)
        records = iter_records(self._sequence + 1, fields, self.retained_game_getter, empty_receiver_profile=True, padding_policy=STACK_POLICY, normalizer_transform_present=False, thread_hook_present=False, project_hook_present=False, narrative_hook_present=False, writer_metadata_callback_present=False)
        emitted = []
        for record in records:
            validate_empty_profile_record(record, **self.empty_receiver_state)
            self._enqueue(record)
            queue_type = hex(struct.unpack_from('<I', record, 4)[0])
            emitted.append({'queue_type': queue_type, 'record_hex': record.hex()})
            self.emit('native_deferred_host_event_enqueued', dispatch_kind='0x3182bc8e', queue_type=queue_type, record_hex=record.hex(), pending_count=len(self.pending), extended_branch_entered=True, empty_receiver_state_verified=True, payload_exposed_to_learner=False, eligible_for_training=False, native_dispatch_return=0)
        self.emit('native_project_completion_records_enqueued', dispatch_kind='0x3182bc8e', source_sha256=PINNED_EVIDENCE_SHA256, records=emitted, native_descriptor_hex=fields.descriptor_bytes.hex(), owner_word=fields.owner, item_id=fields.item_id, project_index=fields.a1fbc_value, normalized_58=fields.normalized_58, coordinates=[-9999, -9999], native_getter_calls=1, city_map_lookup_executed=False, native_order_preserved=True, empty_receiver_state_verified=True, payload_exposed_to_learner=False, eligible_for_training=False)
        return 0

    def _enqueue_natural_wonder_pair(self, raw_fields, borrowed_argument):
        n, m, gate = self._preflight_36c9(borrowed_argument)
        if not gate:
            from civ6_host.runtime.native.native_36c9b2b4 import validate_closed_gate_input
            validate_closed_gate_input(raw_fields, self.read)
            return 0
        from civ6_host.runtime.native.native_36c9b2b4 import produce_pair_from_raw_fields
        from civ6_host.runtime.native.native_36c9b2b4 import SOURCE_PROOF_SHA256
        from civ6_host.runtime.native.native_36c9b2b4_pair_codec import ZERO_PADDING_POLICY
        from civ6_host.runtime.native.native_36c9b2b4_pair_codec import EMPTY_RECEIVER_STATE
        from civ6_host.runtime.native.native_36c9b2b4_pair_codec import PROOF_SHA256 as PAIR_PROOF_SHA256
        self._36c9_producing = True
        try:
            result = produce_pair_from_raw_fields(raw_fields, self.read, sequence_78=self._sequence + 1, core=self.core, facades=self.retained_cache_facades, context=self.context, turn_state=self.turn_begin_state, retained_getter=self.retained_game_getter, notification_counter=n, metadata_counter=m, original_argument=borrowed_argument, ui_cache_callbacks_enabled=True, empty_receiver_state_78=dict(EMPTY_RECEIVER_STATE), empty_receiver_state_79=dict(EMPTY_RECEIVER_STATE), normalizer_transform_present=False, per_thread_hook_present=False, writer_metadata_callback_present=False, entity_listener_count=self.entity_listener_count, padding_policy=ZERO_PADDING_POLICY)
            self._require_exact_36c9_counters(n, m, 'after producer')
            if (self.host_notification_counter, self.host_metadata_counter) != (n, m):
                raise RuntimeError('36C9 source counters changed before first enqueue')
            records = result['records']
            if tuple((kind for kind, _ in records)) != (120, 121):
                raise ValueError('36C9 producer returned an invalid pair')
            self._enqueue(records[0][1])
            self.emit('native_deferred_host_event_enqueued', dispatch_kind='0x36c9b2b4', queue_type='0x78', record_hex=records[0][1].hex(), pending_count=len(self.pending), consumer_validated=False, eligible_for_training=False)
            self._enqueue(records[1][1])
            self.emit('native_deferred_host_event_enqueued', dispatch_kind='0x36c9b2b4', queue_type='0x79', record_hex=records[1][1].hex(), pending_count=len(self.pending), consumer_validated=False, eligible_for_training=False)
            self._require_exact_36c9_counters(n, m, 'after pair enqueue')
            if (self.host_notification_counter, self.host_metadata_counter) != (n, m):
                raise RuntimeError('36C9 source counters changed after pair enqueue')
            self.emit('native_natural_wonder_pair_enqueued', dispatch_kind='0x36c9b2b4', source_proof_sha256=SOURCE_PROOF_SHA256, pair_codec_proof_sha256=PAIR_PROOF_SHA256, sequence_78=struct.unpack_from('<I', records[0][1], 8)[0], sequence_79=struct.unpack_from('<I', records[1][1], 8)[0], copied_position_hex=struct.pack('<ii', *result['native_position_before']).hex(), native_query_return=result['native_position_index'], native_output_position=list(result['native_position_after_query']), notification_counter_before=n, notification_counter_after=self.host_notification_counter, metadata_counter_before=m, metadata_counter_after=self.host_metadata_counter, records_enqueued=True, native_gameplay_written=False, eligible_for_training=False)
            self.emit('native_notification_metadata_transition', dispatch_kind='0x36c9b2b4', sequence=self._sequence, notification_counter=n, metadata_before=m, metadata_after=m, metadata_flag=6, source_proof_sha256=SOURCE_PROOF_SHA256, counter_independent_producer=True, empty_receiver_state_verified=True, eligible_for_training=False)
            return 0
        except BaseException:
            self._36c9_poisoned = True
            raise
        finally:
            self._36c9_producing = False

    def _enqueue_wonder_completion(self, first_sequence, fields, third_values, record_sink):
        from civ6_host.runtime.native.native_event_e66012a7_wonder import encode_wonder_records
        from civ6_host.runtime.native.native_event_e66012a7_wonder import PINNED_EVIDENCE_SHA256
        from civ6_host.runtime.native.native_wonder_application import apply_wonder_application_effects
        from civ6_host.runtime.native.native_deferred_empty_profile import validate_empty_profile_record
        if not self.ui_cache_callbacks_enabled or not callable(self.retained_game_getter) or first_sequence != self._sequence + 1:
            raise RuntimeError('Wonder completion requires the current native facade and sequence')
        if len(self.pending) + 2 > self.limit or not 1 <= first_sequence <= 4294967294:
            raise RuntimeError('Wonder completion requires capacity for AE/AF')
        for kind in (174, 175):
            shape = bytearray(144)
            struct.pack_into('<II', shape, 0, len(shape), kind)
            validate_empty_profile_record(shape, **self.empty_receiver_state)
        retained = self.retained_game_getter()
        records = encode_wonder_records(first_sequence, fields, third_values, retained, normalizer_transform_present=False, thread_hook_present=False, writer_metadata_callback_present=False, empty_receiver_profile_verified=True, padding_policy='zero-unread-empty-receiver-payload')
        record_sink(records[0])
        effect = apply_wonder_application_effects(self.core, self.context, self.read, self.turn_begin_state, self.retained_game_getter)
        self.emit('native_wonder_application_effects_applied', dispatch_kind='0xe66012a7', metadata_retained_game_value=retained, **effect, eligible_for_training=False)
        record_sink(records[1])
        self.emit('native_wonder_completion_records_enqueued', dispatch_kind='0xe66012a7', source_sha256=PINNED_EVIDENCE_SHA256, records=[dict(queue_type=hex(struct.unpack_from('<I', r, 4)[0]), record_hex=r.hex()) for r in records], input_city_owner=fields.owner, input_city_id=fields.identifier, position=[fields.x, fields.y], building_index=fields.value, input_progress=fields.second_value, narrative_progress=100, third_native_snapshot=third_values, metadata_retained_game_value=retained, native_order_preserved=True, empty_receiver_state_verified=True, payload_exposed_to_learner=False, eligible_for_training=False)
        return records

    def drain_empty_receivers(self):
        """Drain proven empty rows and route CacheUpdate through Core +0x198.

        The CacheUpdate receiver is active because it forwards native snapshots.
        Other admitted rows use the explicitly empty headless subscriber profile.
        Refusal leaves the failing record and all later records queued.
        """
        if getattr(self, '_diplomacy_producing', False) or getattr(self, '_diplomacy_poisoned', False):
            raise RuntimeError('Statement producer is active or poisoned; drain refused')
        if getattr(self, '_city_command_started_producing', False) or getattr(self, '_city_command_started_poisoned', False):
            raise RuntimeError('CityCommandStarted producer is active or poisoned; drain refused')
        if getattr(self, '_district_combat_producing', False) or getattr(self, '_district_combat_poisoned', False):
            raise RuntimeError('DistrictCombatChanged producer is active or poisoned; drain refused')
        if getattr(self, '_building_pillage_producing', False) or getattr(self, '_building_pillage_poisoned', False):
            raise RuntimeError('BuildingPillaged native producer is active or poisoned')
        if getattr(self, '_district_damage_producing', False) or getattr(self, '_district_damage_poisoned', False):
            raise RuntimeError('DistrictDamageChanged producer is active or poisoned; drain refused')
        if getattr(self, '_36c9_producing', False) or getattr(self, '_36c9_poisoned', False):
            raise RuntimeError('36C9 pair is producing or poisoned; deferred drain is refused')
        if getattr(self, '_84c1fdd6_producing', False) or getattr(self, '_84c1fdd6_poisoned', False):
            raise RuntimeError('84C1FDD6 producer is active or poisoned; drain refused')
        if getattr(self, '_draining_empty_receivers', False):
            raise RuntimeError('Reentrant native deferred drain is not allowed')
        if getattr(self, '_deferred_drain_poisoned', False):
            raise RuntimeError('Native deferred drain is poisoned after an uncertain callback failure')
        self._draining_empty_receivers = True
        try:
            count = self._drain_empty_receivers_once()
            self.drain_private_empty_receivers()
            return count
        finally:
            self._draining_empty_receivers = False

    def _private_ring(self):
        from civ6_host.runtime.native.native_private_ring_profile import NativePrivateRingProfile
        from civ6_host.runtime.native.native_private_ring_consumer import EMPTY_RECEIVER_PROFILE
        if getattr(self, 'private_progress_ring', None) is None:
            self.private_progress_ring = NativePrivateRingProfile(profile=EMPTY_RECEIVER_PROFILE)
        return self.private_progress_ring

    def drain_private_empty_receivers(self):
        ring = self._private_ring()
        result = ring.flush()
        self.emit('native_private_empty_drain_completed', consumed_this_call=result.records_consumed, consumed_bytes=result.bytes_consumed, counts_by_type={hex(kind): count for kind, count in result.counts_by_type}, diagnostic=ring.diagnostic(), source_order='after standard deferred drain', full_exe_frame_cadence_reproduced=False, native_callbacks_invoked=0, eligible_for_training=False)
        return result

    def _drain_empty_receivers_once(self):
        from civ6_host.runtime.native.native_deferred_empty_profile import validate_empty_profile_record
        count = 0
        while self.pending:
            record = self.pending[0]
            sequence = int.from_bytes(record[8:12], 'little')
            if sequence != self.consumed_count + 1:
                raise ValueError('Native deferred consumption is out of sequence')
            if int.from_bytes(record[4:8], 'little') == 275:
                self._consume_cache_update_record(record, sequence)
                count += 1
            elif int.from_bytes(record[4:8], 'little') == 132:
                from civ6_host.runtime.native.native_diplomacy_statement import StatementReceiver
                from civ6_host.runtime.native.native_event_argument_tree import read_event_fields
                if self.combat_map_registry is None:
                    raise RuntimeError('Statement lost its owned map registry')
                if self.diplomacy_receiver is None:
                    self.diplomacy_receiver = StatementReceiver()

                def deliver(statement):
                    if len(self.pending_diplomacy_statements) >= self.limit or any((row['event_sequence'] == statement['event_sequence'] for row in self.pending_diplomacy_statements)):
                        raise RuntimeError('Pending statement limit or duplicate delivery')
                    self.pending_diplomacy_statements.append(statement)
                try:
                    receipt = self.diplomacy_receiver.consume(record, self.combat_map_registry, self.empty_receiver_state, lambda ptr: read_event_fields(ptr, self.base, self.read, self.next_node), self.read, deliver=deliver)
                except BaseException:
                    self._deferred_drain_poisoned = True
                    raise
                self.pending.pop(0)
                self.consumed_count += 1
                self.consumed_bytes += len(record)
                self.consumed_digest.update(record)
                count += 1
                self.emit('native_diplomacy_statement_consumed', **receipt, pending_choices=len(self.pending_diplomacy_statements), automatic_response=False)
            elif int.from_bytes(record[4:8], 'little') == 248:
                from civ6_host.runtime.native.native_combat_receiver import CombatReceiver
                if self.combat_map_registry is None:
                    raise RuntimeError('Combat record cannot outlive its owned registry')
                if self.combat_receiver is None:
                    self.combat_receiver = CombatReceiver()
                try:
                    receipt = self.combat_receiver.consume(record, self.combat_map_registry, self.empty_receiver_state)
                except BaseException:
                    self._deferred_drain_poisoned = True
                    raise
                self.pending.pop(0)
                self.consumed_count += 1
                self.consumed_bytes += len(record)
                self.consumed_digest.update(record)
                count += 1
                self.emit('native_combat_post_hook_consumed', sequence=sequence, **receipt)
            else:
                self._consume_empty_record(record, sequence)
                count += 1
        self.emit('native_deferred_empty_drain_completed', consumed_this_call=count, consumed_total=self.consumed_count, consumed_bytes=self.consumed_bytes, consumed_sha256=self.consumed_digest.hexdigest(), pending_count=0, scope='Core CacheUpdate dispatch and source-verified empty presentation receivers', eligible_for_training=False)
        return count

    def _preflight_36c9(self, argument):
        if getattr(self, '_36c9_poisoned', False) or getattr(self, '_36c9_producing', False):
            raise RuntimeError('36C9 producer is reentrant or poisoned')
        n, m = (self.host_notification_counter, self.host_metadata_counter)
        if type(n) is not int or not 0 <= n <= 4294967295 or type(m) is not int or (not 0 <= m <= 4294967295):
            raise ValueError('36C9 requires exact uint32 notification/metadata counters')
        if type(self.entity_listener_count) is not int or self.entity_listener_count != 0:
            raise ValueError('36C9 requires the closed zero-listener source profile')
        if type(getattr(self, 'normalizer_transform_present', None)) is not bool or self.normalizer_transform_present is not False:
            raise ValueError('36C9 requires the captured absent-normalizer-transform profile')
        if type(self.ui_cache_callbacks_enabled) is not bool:
            raise ValueError('36C9 UI-cache callback gate must be an exact bool')
        if not self.ui_cache_callbacks_enabled:
            return (n, m, False)
        if type(argument) is not int or argument <= 0:
            raise ValueError('36C9 requires the original nonnull A0 argument tree')
        if len(self.pending) + 2 > self.limit or type(self._sequence) is not int or (not 0 <= self._sequence <= 4294967293):
            raise RuntimeError('36C9 requires two free same-queue sequence slots')
        from civ6_host.runtime.native.native_deferred_empty_profile import validate_empty_profile_record
        from civ6_host.runtime.native.native_36c9b2b4_pair_codec import EMPTY_RECEIVER_STATE
        from civ6_host.runtime.native.native_36c9b2b4_pair_codec import _is_exact_empty_receiver
        if not _is_exact_empty_receiver(self.empty_receiver_state):
            raise ValueError('36C9 host empty-receiver state changed type or value')
        for record_type in (120, 121):
            header = bytearray(112)
            struct.pack_into('<II', header, 0, 112, record_type)
            validate_empty_profile_record(header, **self.empty_receiver_state)
        publisher = self.retained_natural_wonder_publisher
        if publisher is None or self.retained_cache_facades is not getattr(publisher, '_facades', None) or getattr(self.retained_game_getter, '__self__', None) is not publisher or (getattr(self.retained_game_getter, '__func__', None) is not type(publisher).read_retained_game_value) or (publisher._closed is not False) or (publisher.native_cache_gate is not True) or (publisher.full_facade_initialization_reproduced is not True) or (publisher.core is not self.core) or (publisher.context != self.context):
            raise RuntimeError('36C9 retained cache publisher/getter is not the initialized owner')
        if publisher._owner_thread_id != threading.get_ident():
            raise RuntimeError('36C9 publisher may only be used from its owner thread')
        return (n, m, True)

    def _require_exact_36c9_counters(self, n, m, stage):
        current_n, current_m = (self.host_notification_counter, self.host_metadata_counter)
        if type(current_n) is not int or not 0 <= current_n <= 4294967295 or type(current_m) is not int or (not 0 <= current_m <= 4294967295):
            raise RuntimeError(f'36C9 counters ceased to be exact uint32 {stage}')
        if (current_n, current_m) != (n, m):
            raise RuntimeError(f'36C9 counters changed {stage}')

    def dispatch(self, receiver, kind, argument):
        self.host._check(receiver)
        self._require_no_f391_reentry()
        gate_36c9 = None
        if kind == 919188148:
            _n, _m, gate_36c9 = self._preflight_36c9(argument)
        from civ6_host.runtime.native.native_event_argument_tree import read_event_fields
        from civ6_host.runtime.native.native_event_argument_tree import EventArgumentTreeError
        from civ6_host.runtime.native.native_event_argument_tree import MAX_FIELDS
        from civ6_host.runtime.native.native_event_argument_tree import PROOF_SHA256
        try:
            raw_fields = read_event_fields(argument, self.base, self.read, self.next_node)
        except EventArgumentTreeError as exc:
            self.emit('native_host_event_argument_tree_failed', dispatch_kind=hex(kind), reason=exc.reason, error=repr(exc), declared_count=exc.declared_count, copied_count=len(exc.fields), field_budget=MAX_FIELDS, fields={hex(k): v.hex() for k, v in exc.fields.items()}, diagnostic_pointer_payloads={}, source_proof_sha256=PROOF_SHA256, input_complete=False, result_substituted=False, eligible_for_training=False)
            raise
        try:
            if kind == 919188148 and gate_36c9 is False:
                from civ6_host.runtime.native.native_36c9b2b4 import verify_source_evidence
                from civ6_host.runtime.native.native_36c9b2b4 import _decode_captured_raw_fields
                verify_source_evidence()
                _decode_captured_raw_fields(raw_fields, self.read)
                return 0
            if kind in (2186730465, 919188148, 4235402789) and getattr(self, 'ui_cache_callbacks_enabled', False):
                return self._dispatch_fields(kind, raw_fields, borrowed_argument=argument)
            return self._dispatch_fields(kind, raw_fields)
        except Exception as exc:
            pointer_payloads = {} if kind == 919188148 and gate_36c9 is False else self._capture_pointer_payloads(raw_fields)
            self.emit('native_host_event_failed_input', dispatch_kind=hex(kind), error=repr(exc), fields={hex(k): v.hex() for k, v in raw_fields.items()}, diagnostic_pointer_payloads=pointer_payloads, result_substituted=False, eligible_for_training=False)
            raise

    def _capture_pointer_payloads(self, raw_fields):
        """Copy only bounded, witnessed eight-byte variant envelopes for refusal evidence."""
        payloads = {}
        for key, raw in raw_fields.items():
            if len(raw) != 24:
                continue
            tag = struct.unpack_from('<H', raw)[0]
            pointer, size, flags = struct.unpack_from('<QII', raw, 8)
            if tag not in (0, 1024, 13) or size != 8 or flags != 553648129 or (not pointer):
                continue
            try:
                copied = self.read(pointer, 8)
                payloads[hex(key)] = {'bytes_hex': copied.hex(), 'byte_count': len(copied)}
            except (ValueError, RuntimeError, OSError) as exc:
                payloads[hex(key)] = {'read_error': repr(exc)}
        return payloads
