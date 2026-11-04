"""Private wall-time attribution for guarded callbacks on the update thread."""
from contextlib import contextmanager
from functools import cache
import sys
from threading import get_ident
from time import perf_counter_ns
from types import CodeType


@cache
def _guarded_code():
    from .native.native_host import DiagnosticHost

    guarded, = (code for code in DiagnosticHost._bind.__code__.co_consts
                if isinstance(code, CodeType) and code.co_name == 'guarded')
    return guarded


class _CallbackTiming:
    def __init__(self):
        self._thread = get_ident()
        self._depth = 0
        self._by_slot = {}
        self._nested = 0
        self.available = False

    def start(self, code, offset):
        if get_ident() != self._thread:
            return
        self._depth += 1
        if self._depth > 1:
            self._nested += 1
            return
        local = sys._getframe(1).f_locals
        callback = local['callback']
        name = getattr(callback, '__qualname__', type(callback).__qualname__)
        self._slot = f"{name}@{local['offset']:#x}"
        self._started = perf_counter_ns()

    def finish(self, code, offset, result):
        if get_ident() != self._thread:
            return
        self._depth -= 1
        if self._depth == 0:
            elapsed = perf_counter_ns() - self._started
            calls, nanoseconds = self._by_slot.get(self._slot, (0, 0))
            self._by_slot[self._slot] = (calls + 1, nanoseconds + elapsed)

    def report(self):
        return dict(
            scope='update-thread-guarded-vtable-callbacks',
            available=self.available,
            complete=self.available and self._depth == 0,
            outer_calls=sum(calls for calls, _ in self._by_slot.values()),
            nested_calls=self._nested,
            seconds=sum(ns for _, ns in self._by_slot.values()) / 1_000_000_000,
            slots={slot: dict(calls=calls, seconds=ns / 1_000_000_000)
                   for slot, (calls, ns) in sorted(self._by_slot.items())},
        )


@contextmanager
def measure():
    timing = _CallbackTiming()
    monitor = sys.monitoring
    tool = next((slot for slot in (3, 4) if monitor.get_tool(slot) is None), None)
    if tool is None:
        yield timing
        return
    code = _guarded_code()
    start, end = monitor.events.PY_START, monitor.events.PY_RETURN
    monitor.use_tool_id(tool, 'civ6-host-update-callback-timing')
    try:
        monitor.register_callback(tool, start, timing.start)
        monitor.register_callback(tool, end, timing.finish)
        monitor.set_local_events(tool, code, start | end)
        timing.available = True
        yield timing
    finally:
        monitor.set_local_events(tool, code, 0)
        monitor.register_callback(tool, start, None)
        monitor.register_callback(tool, end, None)
        monitor.free_tool_id(tool)
