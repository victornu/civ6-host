"""Native public action serialization; queued bytes are not applied actions."""
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import ctypes as C
import struct
from civ6_host.runtime.native.native_host import virtual
from civ6_host.runtime.native.native_setup import local_reader

class NativeActionTransport:

    def __init__(self, host, core, context, emit, *, core_sha256='d7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'):
        self.host, self.core, self.context, self.emit = (host, core, context, emit)
        self.read = local_reader()
        from civ6_host.runtime.action_transport_profiles import transport_profile
        self.transport_abi = transport_profile(core_sha256, core, context, self.read)
        self.pending = []
        host._bind(host.vtable, 112, C.c_int32, [C.c_void_p, C.c_void_p], self.capture)

    def inspect_processor_flags(self, phase):
        values = list(self.read(self.core._handle + self.transport_abi.processor_flags_rva, 4))
        if any((value not in (0, 1) for value in values)):
            raise RuntimeError('Native processor flag representation changed')
        self.emit('native_processor_flags_observed', phase=phase, flags_by_rva={hex(self.transport_abi.processor_flags_rva + i): value for i, value in enumerate(values)}, memory_modified=False, player_observation=False, eligible_for_training=False)

    def update_game_once(self):
        """Invoke the native game facade update, preserving its lock/lifetime."""
        getter = virtual(self.core, self.context, 144, self.transport_abi.game_getter_rva, C.c_void_p)
        game = getter(self.context)
        if not game:
            raise RuntimeError('Native initialized-game facade is unavailable')
        release = virtual(self.core, game, 8, self.transport_abi.game_release_rva, None)
        try:
            if int.from_bytes(self.read(game, 8), 'little') != self.core._handle + self.transport_abi.game_vtable_rva:
                raise RuntimeError('Unexpected native game facade')
            update = virtual(self.core, game, 48, self.transport_abi.game_update_rva, None)
            self.inspect_processor_flags('before_public_game_update')
            self.emit('before_native_game_update', outer_slot='0x90', game_slot='0x30', scheduling_profile='Single explicit diagnostic update; EXE cadence unresolved')
            update(game)
            self.inspect_processor_flags('after_public_game_update')
            self.emit('native_game_update_returned', eligible_for_training=False)
        finally:
            release(game)

    def capture(self, receiver, archive):
        self.host._check(receiver)
        if not archive or int.from_bytes(self.read(archive, 8), 'little') != self.core._handle + self.transport_abi.archive_vtable_rva:
            raise ValueError('Unverified native command archive interface')
        size = virtual(self.core, archive, 16, self.transport_abi.archive_size_rva, C.c_size_t)(archive)
        data = int.from_bytes(self.read(archive + 8, 8), 'little')
        if not data or not 0 < size <= 6784 or len(self.pending) >= 64:
            raise ValueError('Native command archive exceeds admitted bounds')
        payload = self.read(data, size)
        self.pending.append(payload)
        self.emit('native_command_archive_queued', archive_hex=payload.hex(), bytes=size, delivery_pending=True, action_applied=False, queue_count=len(self.pending), eligible_for_training=False)
        return 0

    def deliver_one(self, context_value=4294967295):
        """Copy the queued archive through the native receive entry and drain.

        EXE265D50 uses Core+230, not direct dispatcher+228. Full chained
        Core02DA20 uses the context DWORD only in four log-formatting sites;
        the PlayerTurnComplete handler obtains player/reason from the message.
        We retain constructor default FFFFFFFF for this ordered local transport.
        This proves neither EXE validation nor its scheduling or log callbacks.
        See native-endturn-host-route.json, receive_context_analysis.
        """
        if type(context_value) is not int or not 0 <= context_value <= 4294967295 or (not self.pending):
            raise ValueError('Invalid diagnostic native command delivery')
        payload = self.pending[0]
        sentinel = self.core._handle + self.transport_abi.receive_queue_rva
        if int.from_bytes(self.read(sentinel, 8), 'little') != sentinel:
            raise RuntimeError('Native receive queue must be empty before diagnostic delivery')
        data = C.create_string_buffer(payload, len(payload))
        stream = C.create_string_buffer(64)
        pointer = C.addressof(stream)
        C.memset(pointer + 40, 165, 24)
        ctor = C.WINFUNCTYPE(C.c_void_p, C.c_void_p, C.c_void_p, C.c_size_t)(self.core._handle + self.transport_abi.view_ctor_rva)
        dtor = C.WINFUNCTYPE(None, C.c_void_p)(self.core._handle + self.transport_abi.view_dtor_rva)
        if ctor(pointer, C.addressof(data), len(payload)) != pointer:
            raise RuntimeError('Native receive view constructor mismatch')
        try:
            if int.from_bytes(self.read(pointer, 8), 'little') != self.core._handle + self.transport_abi.view_vtable_rva:
                raise RuntimeError('Native receive view has the wrong vtable')
            receive = virtual(self.core, self.context, 560, self.transport_abi.receive_rva, None, C.c_uint32, C.c_void_p)
            receive(self.context, context_value, pointer)
            node = int.from_bytes(self.read(sentinel, 8), 'little')
            if node == sentinel:
                raise RuntimeError('Native receiver did not enqueue a command')
            raw = self.read(node, 56)
            next_node, previous = struct.unpack_from('<QQ', raw)
            label = struct.unpack_from('<I', raw, 16)[0]
            begin, end, capacity = struct.unpack_from('<QQQ', raw, 24)
            if next_node != sentinel or previous != sentinel or label != context_value or (end - begin != len(payload)) or (capacity < end) or (self.read(begin, len(payload)) != payload):
                raise RuntimeError('Native receive queue differs from the serialized command')
            self.pending.pop(0)
            self.emit('native_command_received_in_core_queue', archive_hex=payload.hex(), context_value=context_value, native_owned_copy=True, action_applied=False, transport_profile='Ordered local Core delivery; context affects receive diagnostics', exe_network_validation_reproduced=False, optional_native_queue_enabled=bool(self.read(self.core._handle + self.transport_abi.optional_queue_flag_rva, 1)[0]), eligible_for_training=False)
        finally:
            dtor(pointer)
            if self.read(pointer + 40, 24) != b'\xa5' * 24:
                raise RuntimeError('Native view exceeded its source-sized storage')
        drain = virtual(self.core, self.context, 568, self.transport_abi.drain_rva, None)
        self.emit('before_native_command_queue_drain')
        self.inspect_processor_flags('before_command_drain')
        drain(self.context)
        self.inspect_processor_flags('after_command_drain')
        if int.from_bytes(self.read(sentinel, 8), 'little') != sentinel:
            raise RuntimeError('Native command drain retained a queue head')
        self.emit('native_command_queue_drained', native_dispatcher_used=True, gameplay_outcome_verified=False, eligible_for_training=False)

    def validate_completed_round_echo(self, player, *, player_ids=(0, 1)):
        """Validate the existing pre-update completion without consuming it."""
        from civ6_host.runtime.xp1_turn_profile import prepare_transport
        _turn_abi = prepare_transport(self)
        from civ6_host.runtime.native.native_diagnostic_roster import validate_player
        validate_player(player, player_ids)
        expected = struct.pack('<II', 467357532, player)
        if len(self.pending) != 1 or self.pending[0] != expected:
            raise RuntimeError('Expected exactly one native GameTurnComplete archive')
        flags = self.read(self.core._handle + _turn_abi.processor_flags_rva, 4)
        if flags != b'\x01\x01\x00\x00':
            raise RuntimeError('Late or unverified GameTurnComplete echo; refusing replay into another turn')
        from civ6_host.runtime.native.native_game_turn_complete import validate_pre_update_loopback
        validate_pre_update_loopback(self.pending[0], player, flags, core_sha256=_turn_abi.core_sha256)
        return flags

    def deliver_completed_round_echo(self, player, *, player_ids=(0, 1)):
        """Deliver the already generated GameTurnComplete before the next update.

        Its payload identifies a player, not a turn. Core02C040 ignores it
        while end-of-round flag8BB801 is set. Delaying it until the public
        update clears that flag can apply it to the next turn instead.
        This bounded route therefore refuses a late echo and never creates a
        replacement archive. Source: Core03F890/052EC0/02C040/040F60/03F460.
        """
        from civ6_host.runtime.xp1_turn_profile import prepare_transport
        _turn_abi = prepare_transport(self)
        flags = self.validate_completed_round_echo(player, player_ids=player_ids)
        expected = struct.pack('<II', 467357532, player)
        self.emit('before_native_game_turn_complete_echo', player_id=player, archive_hex=self.pending[0].hex(), archive_fabricated=False, source_guard=_turn_abi.completion_guard_description, eligible_for_training=False)
        self.deliver_one()
        if self.pending or self.read(self.core._handle + _turn_abi.processor_flags_rva, 4) != flags:
            raise RuntimeError('Completed-round echo produced an unexpected scheduler effect')
        self.emit('native_game_turn_complete_echo_verified', player_id=player, archive_hex=expected.hex(), core_dispatcher_used=True, processed_before_next_public_update=True, eligible_for_training=False)

    def request_end_turn(self, player, *, player_ids=(0, 1), user_forced=False):
        from civ6_host.runtime.xp1_turn_profile import prepare_transport
        _turn_abi = prepare_transport(self)
        from civ6_host.runtime.native.native_diagnostic_roster import validate_player
        validate_player(player, player_ids)
        if type(user_forced) is not bool:
            raise ValueError('Exact forced EndTurn flag required')
        if user_forced:
            from civ6_host.runtime.native.native_player_operation_request import _GuardedStorage
            from civ6_host.runtime.xp1_turn_profile import verify_parameter_source
            verify_parameter_source(_turn_abi.core_sha256)
            storage = _GuardedStorage(72, 'forced EndTurn vector parameters')
            ptr = storage.address
            ctor_rva, dtor_rva, vtable, lookup_rva = (_turn_abi.vector_ctor_rva, _turn_abi.vector_dtor_rva, _turn_abi.vector_vtable_rva, _turn_abi.vector_lookup_rva)
        else:
            storage = C.create_string_buffer(112)
            C.memset(C.addressof(storage) + 96, 165, 16)
            ptr = C.addressof(storage)
            ctor_rva, dtor_rva, vtable, lookup_rva = (_turn_abi.tree_ctor_rva, _turn_abi.tree_dtor_rva, _turn_abi.tree_vtable_rva, _turn_abi.tree_lookup_rva)

        def check_storage():
            if user_forced:
                storage.check()
            elif self.read(ptr + 96, 16) != b'\xa5' * 16:
                raise RuntimeError('Native action parameters exceeded their source-sized storage')
        ctor = C.WINFUNCTYPE(C.c_void_p, C.c_void_p)(self.core._handle + ctor_rva)
        dtor = C.WINFUNCTYPE(None, C.c_void_p)(self.core._handle + dtor_rva)
        if ctor(ptr) != ptr:
            raise RuntimeError('Native parameter constructor changed its result')
        try:
            check_storage()
            if int.from_bytes(self.read(ptr, 8), 'little') != self.core._handle + vtable:
                raise ValueError('Unverified native action parameter object')
            if user_forced and (self.read(ptr + 8, 24) != bytes(24) or self.read(ptr + 40, 24) != bytes(24)):
                raise ValueError('New native vector parameter storage is not empty')
            lookup = virtual(self.core, ptr, 96, lookup_rva, C.c_void_p, C.c_uint32)
            if lookup(ptr, 884977781):
                raise ValueError('New native parameter set is not empty')
            reason = 3069842052
            if user_forced:
                from civ6_host.runtime.native.native_forced_endturn import write_reason
                from civ6_host.runtime.native.native_forced_endturn import USER_FORCED_HASH
                reason_storage, receipt = write_reason(self.core, ptr, self.read, core_sha256=_turn_abi.core_sha256)
                check_storage()
                reason = USER_FORCED_HASH
                self.emit('native_forced_end_turn_parameters_verified', player_id=player, **receipt, action_applied=False, eligible_for_training=False)
            before = len(self.pending)
            request = virtual(self.core, self.context, 504, _turn_abi.request_rva, None, C.c_uint32, C.c_int32, C.c_void_p)
            self.emit('before_native_end_turn_request', player=player, action='0x2cc9a6b5')
            request(self.context, 751412917, player, ptr)
            check_storage()
            if len(self.pending) != before + 1:
                raise RuntimeError('Native end-turn request did not enqueue exactly one command')
            expected = struct.pack('<III', 3619694470, player, reason)
            if self.pending[-1] != expected:
                raise RuntimeError('Native end-turn archive differs from source-defined fields')
            self.emit('native_end_turn_serialization_verified', player=player, archive_hex=expected.hex(), native_parameter_object=True, action_applied=False, eligible_for_training=False)
        finally:
            try:
                dtor(ptr)
            finally:
                check_storage()

    def request_unready_turn(self, player, *, player_ids=(0, 1)):
        from civ6_host.runtime.xp1_turn_profile import prepare_transport
        _turn_abi = prepare_transport(self)
        from civ6_host.runtime.turn_requests import request_unready_turn
        return request_unready_turn(self, player, player_ids=player_ids, profile=_turn_abi)
