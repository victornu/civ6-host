"""Own shared GameEvents callbacks without running NewGame diagnostics.

The factory, typed payloads, Call/TestAll semantics and protected HKS dispatch
are retained implementations. Engine/caller admission remains separate. This
service supports DWORD and boolean arguments; unknown methods still terminate
through the native host guard. It does not replace missing gameplay listeners.
"""
from __future__ import annotations

import ctypes as C
import threading

from .native.native_map_script import NativeGameEventCallbacks
from .native.native_script_arguments import NativeScriptArguments


class _OwnedArguments(NativeScriptArguments):
    def __init__(self, owner):
        self.owner = owner
        super().__init__(owner.host)

    def _check_aux(self, this):
        self.owner._check()
        return super()._check_aux(this)

    def _get_live(self, address):
        self.owner._check()
        return super()._get_live(address)

    def _create(self, this):
        address=super()._create(this)
        if self.owner.map_factory is not None:
            self._bind_payload(self._payloads[address],0x10,C.c_uint32,
                [C.c_void_p,C.c_void_p],lambda obj,source:self._append_map(address,obj,source))
        return address

    def _append_map(self,address,this,source):
        payload=self._get_live(address)
        if this!=address or not source:raise ValueError('Invalid map argument receiver/source')
        if len(payload.values)>=64:raise ValueError('Script argument capacity exceeded')
        payload.values.append(self.owner.map_factory(source))
        return len(payload.values)-1

    def _destroy(self,address,this,deleting):
        payload=self._get_live(address)
        if this!=address or type(deleting) is not int or deleting!=0:
            raise ValueError('Invalid map payload destructor receiver/form')
        if self.owner.map_factory is not None:
            from .script_event_maps import MAP_ARGUMENT_TYPES
            for value in payload.values:
                if isinstance(value,MAP_ARGUMENT_TYPES):value.close()
        return super()._destroy(address,this,deleting)


class ScriptEventService(NativeGameEventCallbacks):
    SLOTS = (0x40, 0x48, 0x60, 0x80)

    def __init__(self, host, runtime, *, map_factory=None):
        runtime.registry._check()
        if getattr(host, '_script_event_owner', None) is not None:
            raise ValueError('Native script events already have an owner')
        if map_factory is not None:
            from .script_event_maps import require_map_transport
            require_map_transport(runtime)
            map_factory.check()
        self.host, self.runtime, self.emit = host, runtime, host.emit
        self.map_factory=map_factory
        self.thread, self.closed, self.dispatch_depth = threading.get_ident(), False, 0
        table = C.addressof(host.aux_vtable)
        bindings = getattr(host, '_slot_bindings', {})
        self.previous = {slot:(host.aux_vtable[slot//8], bindings.get((table,slot)))
                         for slot in self.SLOTS}
        before = len(host.functions)
        # If installation fails, the caller must quarantine the native worker;
        # no speculative teardown after a partially installed callback table.
        host._script_event_owner = self
        self.script_arguments = _OwnedArguments(self)
        for slot, method in ((0x60,self.game_event_call),(0x80,self.game_event_test_all)):
            host._bind(host.aux_vtable, slot, C.c_uint8,
                       [C.c_void_p,C.c_char_p,C.c_void_p,C.c_void_p], method)
        self.installed = {slot:host.aux_vtable[slot//8] for slot in self.SLOTS}
        self.functions = tuple(host.functions[before:])

    def _check(self):
        if threading.get_ident() != self.thread:
            raise ValueError('Native script events belong to another thread')
        if self.closed or getattr(self.host, '_script_event_owner', None) is not self:
            raise ValueError('Native script event service is closed or ownership changed')
        self.runtime.registry._check()

    def check(self, this):
        self._check()
        super().check(this)

    def _dispatch(self, method, *args):
        self._check()
        self.dispatch_depth += 1
        try:
            return method(*args)
        finally:
            self.dispatch_depth -= 1

    def game_event_call(self, *args):
        return self._dispatch(super().game_event_call, *args)

    def game_event_test_all(self, *args):
        return self._dispatch(super().game_event_test_all, *args)

    def install_mutable_map_result(self, core, *, core_sha256, read):
        """Explicitly own source-qualified XP2 AUX68; default slots stay unchanged."""
        from .script_event_mutable_map import MutableMapResultDispatcher
        self._check()
        if (getattr(self, 'aux68_installed', False) or self.dispatch_depth
                or getattr(self, 'aux68_poisoned', False)
                or getattr(self, 'aux90_poisoned', False)):
            raise ValueError('Mutable map callback is installed, active or quarantined')
        if getattr(self.runtime, 'service_owner', None) is not self.host:
            raise ValueError('Mutable map runtime belongs to another service owner')
        table = C.addressof(self.host.aux_vtable)
        previous = self.host._slot_bindings.get((table, 0x68))
        if (previous is None or self.host.aux_vtable[0x68//8] != previous[0]
                or getattr(previous[1], '_native_unavailable', None) != ('auxiliary', 0x68)):
            raise ValueError('AUX68 already has another callback owner')
        dispatcher = MutableMapResultDispatcher(self.runtime, self.map_factory, core,
                                               core_sha256=core_sha256, read=read)
        self.previous[0x68] = (self.host.aux_vtable[0x68//8], previous)
        self.mutable_map_dispatcher, self.aux68_poisoned = dispatcher, False
        before = len(self.host.functions)
        # _bind owns the exception-to-fatal boundary, as for the other callbacks.
        self.host._bind(self.host.aux_vtable, 0x68, C.c_uint8,
                        [C.c_void_p, C.c_char_p, C.c_void_p, C.c_void_p],
                        self.game_event_mutable_map)
        self.functions += tuple(self.host.functions[before:])
        self.installed[0x68] = self.host.aux_vtable[0x68//8]
        self.aux68_installed = True

    def game_event_mutable_map(self, this, name, arguments, destination):
        """AUX68 returns result validity; truthiness is separate telemetry."""
        entered = False
        try:
            self.check(this)
            if (not getattr(self, 'aux68_installed', False)
                    or getattr(self, 'aux68_poisoned', False)
                    or getattr(self, 'aux90_poisoned', False) or self.dispatch_depth):
                raise RuntimeError('Mutable map callback is unavailable or reentered')
            self.dispatch_depth += 1
            entered = True
            # The installed XP2 source profile proves NULL skips the item
            # loop; protected C still appends the seeded result table.
            values = (() if arguments is None or type(arguments) is int and arguments == 0
                      else self.script_arguments.arguments(arguments))
            result = self.mutable_map_dispatcher.dispatch(name, values, destination)
            self.emit('native_game_event_mutable_map_dispatched',
                      gameplay_event_name=name.decode('utf-8', 'replace'),
                      argument_count=len(values), result_non_nil=result.valid,
                      result_truthiness=result.truthiness, native_status=result.status,
                      phase=result.phase, protected_call_success=result.status == 0,
                      destination_borrowed=True, destination_cloned=False,
                      eligible_for_training=False)
            return result.valid
        except BaseException:
            self.aux68_poisoned = True
            raise
        finally:
            if entered:
                self.dispatch_depth -= 1

    def install_postload_aux90_null(self, core, *, core_sha256, read):
        """Own one source-bound AUX90 callback; does not call outer+160."""
        from .saved_load_profiles import XP1_CORE_SHA256, XP2_CORE_SHA256
        self._check()
        if (core_sha256 not in (XP1_CORE_SHA256, XP2_CORE_SHA256) or not callable(read)
                or getattr(self, 'aux90_installed', False) or self.dispatch_depth):
            raise ValueError('Unqualified or repeated postload AUX90 installation')
        if not callable(getattr(self.runtime.host, 'LAB_Aux90DispatchCategoryNull', None)):
            raise ValueError('Native AUX category/NULL dispatcher export is unavailable')
        if getattr(self.runtime, 'service_owner', None) is not self.host:
            raise ValueError('AUX90 runtime belongs to another service owner')
        if core_sha256 == XP1_CORE_SHA256:
            from .postload160_source import xp1_source, verify_xp1_live
            proof = xp1_source()
            verify_xp1_live(core._handle, read, proof, core_sha256=core_sha256)
            for offset, pointer in ((0x9F2640, self.host.pointer),
                                    (0x9F2648, C.addressof(self.host.aux_object))):
                if read(core._handle + offset, 8) != pointer.to_bytes(8, 'little'):
                    raise ValueError('Postload AUX90 Core host/auxiliary ownership differs')
        else:
            from .xp2_postload_aux90_source import source, source_dependencies, verify_xp2_live
            proof = source()
            dependencies = source_dependencies()
            verify_xp2_live(core._handle, read, host_pointer=self.host.pointer,
                            auxiliary_pointer=C.addressof(self.host.aux_object), proof=proof)
        table = C.addressof(self.host.aux_vtable)
        previous = self.host._slot_bindings.get((table, 0x90))
        if (previous is None or self.host.aux_vtable[0x90//8] != previous[0]
                or getattr(previous[1], '_native_unavailable', None) != ('auxiliary', 0x90)):
            raise ValueError('AUX90 already has another callback owner')
        self.previous[0x90] = (self.host.aux_vtable[0x90//8], previous)
        self.aux90_read = read
        self.aux90_poisoned = False
        before = len(self.host.functions)
        self.host._bind(self.host.aux_vtable, 0x90, C.c_uint8,
                        [C.c_void_p, C.c_uint32, C.c_void_p, C.c_void_p],
                        self.dispatch_postload_aux90_null)
        self.functions += tuple(self.host.functions[before:])
        self.installed[0x90] = self.host.aux_vtable[0x90//8]
        self.aux90_core_sha256 = core_sha256
        self.aux90_core_base = core._handle
        self.aux90_source_proof = proof
        if core_sha256 == XP2_CORE_SHA256:
            self.aux90_source_dependencies = dependencies
        self.aux90_installed = True

    def validate_postload_aux90(self, core, *, core_sha256, read):
        """Recheck the source and actual installed callback before postload use."""
        from .saved_load_profiles import XP1_CORE_SHA256, XP2_CORE_SHA256
        self._check()
        if (core_sha256 not in (XP1_CORE_SHA256, XP2_CORE_SHA256)
                or core_sha256 != getattr(self, 'aux90_core_sha256', None)
                or getattr(core, '_handle', None) != getattr(self, 'aux90_core_base', None)
                or not callable(read)
                or getattr(self, 'aux90_installed', False) is not True
                or getattr(self, 'aux90_poisoned', True)
                or self.dispatch_depth):
            raise ValueError('Postload AUX90 service is not installed for this Core owner')
        if getattr(self.runtime, 'service_owner', None) is not self.host:
            raise ValueError('Postload AUX90 service owner changed')
        table = C.addressof(self.host.aux_vtable)
        binding = self.host._slot_bindings.get((table, 0x90))
        if (binding is None or self.host.aux_vtable[0x90//8] != binding[0]
                or binding[0] != self.installed.get(0x90)
                or getattr(binding[1], '__func__', None) is not type(self).dispatch_postload_aux90_null):
            raise ValueError('Postload AUX90 callback ownership changed')
        if core_sha256 == XP1_CORE_SHA256:
            from .postload160_source import source_pins, xp1_source, verify_xp1_live
            proof = xp1_source()
            verify_xp1_live(core._handle, read, proof, core_sha256=core_sha256)
            for offset, pointer in ((0x9F2640, self.host.pointer),
                                    (0x9F2648, C.addressof(self.host.aux_object))):
                if read(core._handle + offset, 8) != pointer.to_bytes(8, 'little'):
                    raise ValueError('Postload AUX90 Core host/auxiliary ownership differs')
            dependencies = source_pins()
        else:
            from .xp2_postload_aux90_source import source, source_dependencies, verify_xp2_live
            proof = source()
            verify_xp2_live(core._handle, read, host_pointer=self.host.pointer,
                            auxiliary_pointer=C.addressof(self.host.aux_object), proof=proof)
            dependencies = source_dependencies()
        if proof != getattr(self, 'aux90_source_proof', None):
            raise ValueError('Postload AUX90 installed source identity changed')
        return dict(core_sha256=core_sha256, source_proof=proof,
                    dependencies=dependencies, native_calls_made=False,
                    callback_address=binding[0], callback_owner=self)

    def dispatch_postload_aux90_null(self, this, kind, name, arguments):
        self.check(this)
        if (not getattr(self, 'aux90_installed', False)
                or getattr(self, 'aux90_poisoned', False) or self.dispatch_depth):
            raise RuntimeError('Postload AUX90 owner is unavailable or reentered')
        self.dispatch_depth += 1
        try:
            if (type(kind) is not int or kind != 1 or type(name) is not int
                    or not 0 < name < (1 << 47)
                    or not (arguments is None or type(arguments) is int and arguments == 0)):
                raise ValueError('Unqualified postload AUX90 kind/name/argument interface')
            raw = bytearray()
            for index in range(256):
                unit = self.aux90_read(name + index, 1)
                if type(unit) is not bytes or len(unit) != 1:
                    raise ValueError('Incomplete postload AUX90 name')
                if unit == b'\x00':
                    break
                raw.extend(unit)
            else:
                raise ValueError('Postload AUX90 name exceeds bound')
            if bytes(raw) not in (b'AutoPlayStart', b'AutoPlayEnd'):
                raise ValueError('Unqualified postload AUX90 event name')
            outcome = self.runtime.dispatch_aux_event_category_null(bytes(raw), category=2)
            self.emit('native_postload_aux90_observed', gameplay_event_name=raw.decode('ascii'),
                      raw_kind=1, category=2, argument_count=0, outcome=outcome,
                      listener_count_observed=False, post160_completed=False, eligible_for_training=False)
            return True  # Exact AUX90 AL1 only after observed lookup/call success.
        except BaseException:
            self.aux90_poisoned = True
            raise
        finally:
            self.dispatch_depth -= 1

    def close(self):
        if threading.get_ident() != self.thread:
            raise ValueError('Native script events belong to another thread')
        if self.closed:
            return
        self._check()
        if (self.dispatch_depth or self.script_arguments.live_count
                or getattr(self, 'aux90_poisoned', False) or getattr(self, 'aux68_poisoned', False)
                or getattr(getattr(self, 'mutable_map_dispatcher', None), 'poisoned', False)):
            raise ValueError('Native script events still have a dispatch or live payload')
        if any(self.host.aux_vtable[s//8] != a for s,a in self.installed.items()):
            raise ValueError('Native script event callback ownership changed')
        dispatcher = getattr(self, 'mutable_map_dispatcher', None)
        if dispatcher is not None:
            dispatcher.close()
        table = C.addressof(self.host.aux_vtable)
        for slot, (address, binding) in self.previous.items():
            self.host.aux_vtable[slot//8] = address
            key = (table,slot)
            if binding is None:
                self.host._slot_bindings.pop(key,None)
            else:
                self.host._slot_bindings[key] = binding
        owned = {id(fn) for fn in self.functions}
        self.host.functions[:] = [fn for fn in self.host.functions if id(fn) not in owned]
        self.host._script_event_owner = None
        self.closed = True
        self.functions = ()
