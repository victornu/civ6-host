"""Exact fixed-record encoders for two statically captured turn-status callbacks.

The encoder is deliberately limited to the native no-hook profile: callback
metadata and callback-result are the values produced by the source's null-hook
branch. It does not implement arbitrary EXE callback hooks.
"""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import struct
from dataclasses import dataclass
from dataclasses import field
_EVENTS = {507110547: (3, 8), 559109511: (4, 6)}

def build_turn_status_record(event_kind: int, turn_value: int, sequence: int) -> bytes:
    """Build the 0x60-byte record written by the captured EXE callback.

    ``sequence`` is the post-increment value from the source's atomic xadd.
    The two producer-specific metadata flags are initialized on the callback's
    stack; the optional callback result is zero because this profile has no hook.
    """
    if type(event_kind) is not int or event_kind not in _EVENTS:
        raise ValueError('Unrecognized native turn-status event kind')
    for name, value in (('turn_value', turn_value), ('sequence', sequence)):
        if type(value) is not int or not 0 <= value <= 4294967295:
            raise ValueError(f'{name} must be an unsigned 32-bit integer')
    record_type, metadata_flag = _EVENTS[event_kind]
    out = bytearray(96)
    struct.pack_into('<IIII', out, 0, 96, record_type, sequence, 0)
    meta = 16
    for offset in (0, 4, 12, 20, 28, 36, 44):
        struct.pack_into('<I', out, meta + offset, 4294967295)
    for offset in (8, 16, 24, 32, 40):
        struct.pack_into('<H', out, meta + offset, 65535)
    struct.pack_into('<Q', out, meta + 48, 0)
    struct.pack_into('<I', out, meta + 56, metadata_flag)
    struct.pack_into('<II', out, 80, sequence, turn_value)
    return bytes(out)

@dataclass
class TurnBeginAuxiliaryState:
    """Partial state model for source-visible type-4 callback side effects.

    This is not a drop-in native callback implementation: the object is a
    GameCoreController, and its scheduling behavior is unresolved. The caller
    must not use this class alone to claim callback equivalence.
    """
    service_flags: int
    controller_initialized: bool = False
    controller_byte_0d: int | None = None
    turn_values_by_thread: dict[int, list[int]] = field(default_factory=dict)

    @property
    def complete(self) -> bool:
        return False

    def _validate(self, turn_value: int, thread_index: int) -> None:
        if type(turn_value) is not int or not 0 <= turn_value <= 4294967295:
            raise ValueError('turn_value must be an unsigned 32-bit integer')
        if type(thread_index) is not int or not 0 <= thread_index <= 4294967295:
            raise ValueError('thread_index must be an unsigned 32-bit integer')
        if type(self.service_flags) is not int or not 0 <= self.service_flags <= 255:
            raise ValueError('service_flags must be the current unsigned byte')
        if len(self.turn_values_by_thread.get(thread_index, ())) >= 32768:
            raise ValueError('Turn telemetry capacity boundary is not modeled')

    def before_queue(self, turn_value: int, thread_index: int) -> None:
        self._validate(turn_value, thread_index)
        self.controller_initialized = True
        self.controller_byte_0d = 0
        self.service_flags &= 191

    def after_queue(self, turn_value: int, thread_index: int) -> None:
        self._validate(turn_value, thread_index)
        values = self.turn_values_by_thread.setdefault(thread_index, [])
        values.append(turn_value)

    def apply(self, turn_value: int, thread_index: int) -> None:
        self.before_queue(turn_value, thread_index)
        self.after_queue(turn_value, thread_index)
__all__ = ['build_turn_status_record', 'TurnBeginAuxiliaryState']
