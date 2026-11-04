"""Share the actual native flag between host queries and existing event adapters."""
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
from civ6_host.runtime.native.native_controller_code import NativeControllerCode
from civ6_host.runtime.native.native_controller_code import SOURCE_SHA
from civ6_host.runtime.native.native_event_turn_status import TurnBeginAuxiliaryState

def prepare_session_controller(owner):
    """Retain one lazy native controller across actions and later EndTurn.

    This binds the existing source-qualified constructor/flag adapter, not the
    EXE singleton or a restored scheduler. No construction, TurnBegin or flag
    reset is performed on installation or reuse. Call only at a checked owner
    boundary, before exposing actions (or at the historical first EndTurn).
    """
    owner.check_thread()
    events = owner.prefix.deferred_events
    state = events.turn_begin_state
    code = getattr(owner, 'native_controller_code', None)
    if type(state) is NativeControllerTurnState:
        if code is not state.code or state._poisoned:
            raise RuntimeError('Shared native controller owner differs or is poisoned')
        state.code._check()
        return state
    if code is not None or type(state) is not TurnBeginAuxiliaryState or state.controller_initialized is not False or (state.controller_byte_0d is not None) or state.turn_values_by_thread or (type(state.service_flags) is not int) or (state.service_flags != 0):
        raise RuntimeError('Native controller installation requires an untouched shared state')
    owner.native_controller_code = NativeControllerCode()
    events.turn_begin_state = NativeControllerTurnState(owner.native_controller_code, owner.emit)
    owner.emit('native_session_controller_bound', source_sha256=SOURCE_SHA, original_constructor_executed=False, synthetic_turn_event=False, core_memory_written=False, full_exe_controller_lifecycle=False, eligible_for_training=False)
    return events.turn_begin_state

class NativeControllerTurnState(TurnBeginAuxiliaryState):
    """Lazy original construction; telemetry/service flags retain their adapters.

    This owns the constructor/flag surface, not the EXE scheduler or its singleton.
    """

    def __init__(self, code, emit):
        if type(code) is not NativeControllerCode or not callable(emit):
            raise TypeError('Native controller state requires its exact code owner and emitter')
        code._check()
        self.code = code
        self.emit = emit
        self._controller = None
        self._poisoned = False
        self.service_flags = 0
        self.turn_values_by_thread = {}

    def _ensure(self):
        self.code._check()
        if self._poisoned:
            raise RuntimeError('Controller construction is poisoned')
        if self._controller is None:
            try:
                self._controller = self.code.create()
                self.emit('native_owned_controller_constructed', snapshot=self._controller.snapshot(), source_sha256=SOURCE_SHA, original_constructor_executed=True, synthetic_turn_event=False, core_memory_written=False, full_exe_controller_lifecycle=False, eligible_for_training=False)
            except BaseException:
                self._poisoned = True
                raise
        return self._controller

    @property
    def controller_initialized(self):
        return self._controller is not None

    @controller_initialized.setter
    def controller_initialized(self, value):
        if type(value) is not bool:
            raise ValueError('Controller existence must be Boolean')
        if value:
            self._ensure()
        elif self._controller is not None:
            raise RuntimeError('Cannot erase a live native controller')

    @property
    def controller_byte_0d(self):
        return self._controller.get_flag() if self._controller is not None else None

    @controller_byte_0d.setter
    def controller_byte_0d(self, value):
        if self._controller is None:
            raise RuntimeError('Native controller must exist before a flag write')
        self._controller.set_flag(value)

    def read_native_flag(self):
        result = self._ensure().get_flag()
        self.emit('native_owned_controller_flag_read', value=result, original_getter_executed=True, source_sha256=SOURCE_SHA, eligible_for_training=False)
        return result

    def close(self):
        if self._controller is not None:
            self._controller.close()
