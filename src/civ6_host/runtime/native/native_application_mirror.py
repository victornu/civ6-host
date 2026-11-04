"""Bounded native application notifications with borrowed provider preparation.

The native A prelude precedes fresh player/GAME lookups and native B copies.
B currently uses an explicit diagnostic clone with NULL observers, not the
EXE-owned singleton bootstrap. This is not the complete application dispatcher.
"""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
from civ6_host.runtime.configuration_profiles import BASE_CORE_SHA256 as _BASE_CORE
from civ6_host.runtime import application_mirror_profiles as _mirror_profiles
from civ6_host.runtime.application_mirror_profiles import mirror_abi as _mirror_abi
import ctypes as C
import struct
from civ6_host.runtime.native.native_application_mirror_records import bounded_get_player_config
from civ6_host.runtime.native.native_application_mirror_records import PROOF_SHA256
from civ6_host.runtime.native.native_setup import local_reader
PLAYER_CHANGE = 1829978708
PROPERTY_KEY = 2716180809
PLAYER_INDEX = 4033489650
IS_ALIVE = 1655168934

def decode_scalar(raw: bytes, expected_tag: int) -> int:
    if len(raw) != 24:
        raise ValueError('Incomplete notification variant')
    tag = struct.unpack_from('<H', raw)[0]
    flags = struct.unpack_from('<I', raw, 20)[0]
    if tag != expected_tag or flags:
        raise ValueError('Unverified notification variant type or ownership')
    value = struct.unpack_from('<I', raw, 8)[0]
    if tag == 1 and value not in (0, 1):
        raise ValueError('Noncanonical native boolean')
    return value

class PlayerApplicationMirror:
    """Copies validated native scalars; never stores borrowed variant pointers."""

    def __init__(self, initial_values: dict[int, bytes | None], limit: int=4096):
        if set(initial_values) != set(range(64)) or any((type(index) is not int for index in initial_values)):
            raise ValueError('All 64 native player records must be inspected before dispatch')
        self.cells = {}
        for index, raw in initial_values.items():
            if raw is not None:
                decode_scalar(raw, 1)
            self.cells[index] = bytes(raw) if raw is not None else None
        self.changes: list[tuple[int, int]] = []
        self.limit = limit

    def update(self, kind: int, index: int, key: int, raw: bytes) -> int:
        if kind != PLAYER_CHANGE or index not in self.cells or key != IS_ALIVE:
            raise ValueError('Unimplemented application mirror notification')
        decode_scalar(raw, 1)
        if self.cells[index] is None:
            return 0
        if len(self.changes) >= self.limit:
            raise ValueError('Application notification journal requires a verified consumer')
        self.cells[index] = bytes(raw)
        self.changes.append((index, key))
        return 0

class NativePlayerApplicationMirror:

    def __init__(self, host, core, context, emit, *, core_sha256=_BASE_CORE):
        from threading import get_native_id
        self._mirror_thread = get_native_id()
        self.closed = False
        self._previous_callback = host.vtable[304 // 8]
        self._binding_key = (C.addressof(host.vtable), 304)
        self._previous_binding = getattr(host, '_slot_bindings', {}).get(self._binding_key)
        self.abi = _mirror_abi(core_sha256)
        if core_sha256 != _BASE_CORE and getattr(host, 'application_configuration', None) is None:
            raise ValueError('Expansion mirror requires the existing configuration owner')
        self.host, self.base, self.context, self.emit = (host, core._handle, context, emit)
        self.read = local_reader()
        if core_sha256 != _BASE_CORE:
            _mirror_profiles.owner_abi(self.application_configuration if hasattr(self, 'application_configuration') else host.application_configuration, core_sha256)
            _mirror_profiles.verify_live(self.base, self.read, core_sha256=core_sha256)
        self.lookup = C.WINFUNCTYPE(C.c_void_p, C.c_void_p, C.c_uint32)(self.base + self.abi.configuration.lookup_rva)
        self.application_configuration = getattr(host, 'application_configuration', None)
        if self.application_configuration is not None:
            self.application_configuration.require_context(self.base, context)
        successor = C.WINFUNCTYPE(C.c_void_p, C.c_void_p)(self.base + self.abi.successor_rva)
        initial = {}
        self.initial_presence = {}
        for index in range(64):
            record = bounded_get_player_config(self.base, context, index, read=self.read) if self.application_configuration is None else self.application_configuration.player(index)
            obj = record['pointer']
            sentinel = obj + 48
            node = int.from_bytes(self.read(obj + 56, 8), 'little')
            keys = set()
            while node != sentinel:
                if not node or len(keys) >= 256:
                    raise ValueError('Initial application mirror key scan exceeds bound')
                key = int.from_bytes(self.read(node + 32, 4), 'little')
                if key in keys:
                    raise ValueError('Duplicate initial native configuration key')
                keys.add(key)
                node = successor(node)
            self.initial_presence[index] = frozenset(keys)
            value = self.lookup(record['pointer'], IS_ALIVE)
            initial[index] = self.read(value, 24) if value else None
        self.mirror = PlayerApplicationMirror(initial)
        emit('native_application_mirror_initialized', cells={str(i): bool(decode_scalar(v, 1)) if v is not None else None for i, v in initial.items()}, initialization='separate native application cells' if self.application_configuration else 'copy of existing setup cells', native_application_provider_present=self.application_configuration is not None, source_proof_sha256=self.abi.records_proof_sha256, inspected_record_count=64, initial_keys={str(i): [hex(k) for k in sorted(keys)] for i, keys in self.initial_presence.items()}, source_gameplay_modified=False, complete_exe_mirror=False)
        host._bind(host.vtable, 304, C.c_uint32, [C.c_void_p, C.c_uint32, C.c_void_p, C.c_void_p], self.dispatch)
        self._callback_address = host.vtable[304 // 8]

    def dispatch(self, receiver, kind, argument, source_store):
        from threading import get_native_id
        if self.closed or get_native_id() != self._mirror_thread:
            raise ValueError('Application mirror closed or called from another thread')
        self.host._check(receiver)
        from civ6_host.runtime.native.native_application_mirror_dispatch import BorrowedApplicationDispatcher
        from civ6_host.runtime.native.native_application_mirror_dispatch import GAME
        from civ6_host.runtime.native.native_application_mirror_dispatch import PROFILE
        from threading import get_native_id
        if kind not in (PLAYER_CHANGE, GAME) or not argument or (not source_store):
            self.host._fatal('unimplemented native host dispatch', interface='host', slot='0x130', dispatch_kind=hex(kind), result_substituted=False)
            raise RuntimeError('Fatal native host boundary unexpectedly returned')
        owner = self.application_configuration
        if owner is None:
            raise ValueError('Native dispatch requires owned application configuration')
        owner.require_context(self.base, self.context)
        dispatcher = getattr(self, '_borrowed_dispatcher', None)
        if dispatcher is None:

            def native_call(address, result_type, arg_types, *args):
                return C.WINFUNCTYPE(result_type, *arg_types)(address)(*args)
            dispatcher = BorrowedApplicationDispatcher(self.base, self.context, owner, read=self.read, invoke=native_call, current_thread_id=get_native_id, journal=self.mirror.changes, journal_limit=self.mirror.limit, diagnostic_profile=PROFILE, logging_enabled=False, core_sha256=self.abi.configuration.core_sha256)
            self._borrowed_dispatcher = dispatcher
        receipt = dispatcher.dispatch(kind, argument, source_store)
        if receipt.get('bounded_dispatch_completed') is not True or type(receipt.get('native_dispatch_return')) is not int or receipt['native_dispatch_return'] != 0 or (receipt.get('kind') != kind):
            raise ValueError('Application dispatcher did not prove bounded completion')
        if kind == PLAYER_CHANGE:
            index, key = (receipt['player_index'], receipt['property_key'])
            if receipt['mirrored'] and key == IS_ALIVE:
                destination = owner.player(index)
                value = self.lookup(destination['pointer'], key)
                if not value:
                    raise ValueError('Copied native IS_ALIVE destination disappeared')
                raw = self.read(value, 24)
                decode_scalar(raw, 1)
                self.mirror.cells[index] = bytes(raw)
            self.emit('native_application_player_notification', **receipt, property_name='IS_ALIVE' if key == IS_ALIVE else None, destination_presence_checked_live=True, native_application_provider_updated=receipt['mirrored'], source_provider_prepared=True)
        else:
            self.emit('native_application_game_notification', **receipt, source_provider_prepared=True)
        return 0

    def close(self):
        from threading import get_native_id
        if get_native_id() != self._mirror_thread:
            raise ValueError('Application mirror close crossed its native thread')
        if self.closed:
            return
        if self.host.vtable[304 // 8] != self._callback_address:
            raise ValueError('Application mirror callback has been replaced')
        if self.mirror.changes:
            raise ValueError('Application mirror still has unconsumed player notifications')
        dispatcher = getattr(self, '_borrowed_dispatcher', None)
        if dispatcher is not None:
            dispatcher.close()
        self.host.vtable[304 // 8] = self._previous_callback
        if self._previous_binding is None:
            self.host._slot_bindings.pop(self._binding_key, None)
        else:
            self.host._slot_bindings[self._binding_key] = self._previous_binding
        self.closed = True
