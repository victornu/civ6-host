"""Host-owned payloads for the source-backed EXE auxiliary +0x40/+0x48 path.

Core creates an argument payload, appends uint32 or boolean values through
payload vtable +0x28/+0x38, dispatches it, then releases it through auxiliary +0x48. The source
append routine 0x140162250 grows a vector; the capacity below is our diagnostic
safety limit, not a four-argument game rule. Dispatch independently validates
each supported type. Other argument types remain unsupported.
"""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import ctypes as C
from dataclasses import dataclass
from pathlib import Path
import struct
AUX_SLOT_CREATE = 64
AUX_SLOT_RELEASE = 72
PAYLOAD_DESTRUCTOR_SLOT = 0
PAYLOAD_APPEND_UINT32_SLOT = 40
PAYLOAD_APPEND_BOOLEAN_SLOT = 56
PAYLOAD_SIZE = 440
PAYLOAD_VTABLE_SLOTS = 32
MAX_LIVE_PAYLOADS = 64
MAX_ARGUMENTS = 64
BOOLEAN_EVIDENCE_SHA256 = 'b2016e420f4d08854ca43b979330fb0ebfc52448b2d4deb6deb04992da7700f3'

def verify_boolean_source():
    from civ6_host.runtime.native.native_source_cache import load_pinned_json
    proof = load_pinned_json(_resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_script_arguments.py')))).resolve().parents[1] / 'evidence/native-script-argument-boolean' / f'{BOOLEAN_EVIDENCE_SHA256}.json', BOOLEAN_EVIDENCE_SHA256)
    if proof['schema'] != 'civ6rl.native_script_argument_boolean.static.v1' or proof['payload_vtable']['slots']['0x38'] != '0x140162520' or proof['payload_vtable']['slots']['0x58'] != '0x140161dc0' or (proof['marshaller_jump_table']['targets'][1] != '0x1404dc976'):
        raise RuntimeError('Boolean script argument source identity mismatch')

@dataclass(frozen=True)
class BooleanArgument:
    """EXE162520 stores raw DL; EXE161DC0 returns its nonzero predicate."""
    raw_byte: int

    def __post_init__(self):
        if type(self.raw_byte) is not int or not 0 <= self.raw_byte <= 255:
            raise ValueError('Boolean script argument must be a raw byte')

class HKSArgument(C.Structure):
    _fields_ = [('kind', C.c_uint32), ('value', C.c_uint32)]

def pack_arguments(arguments):
    arguments = tuple(arguments)
    if len(arguments) > MAX_ARGUMENTS:
        raise ValueError('GameEvents argument count exceeds 64')
    result = (HKSArgument * len(arguments))()
    for index, value in enumerate(arguments):
        if isinstance(value, BooleanArgument):
            result[index] = HKSArgument(1, value.raw_byte)
        elif type(value) is bool:
            result[index] = HKSArgument(1, int(value))
        elif type(value) is int and 0 <= value <= 4294967295:
            result[index] = HKSArgument(0, value)
        else:
            raise ValueError('GameEvents expects a raw DWORD or BooleanArgument')
    return result

def argument_evidence(arguments):
    arguments = tuple(arguments)
    from civ6_host.runtime.script_event_maps import has_maps
    from civ6_host.runtime.script_event_maps import argument_evidence as map_evidence
    if has_maps(arguments):
        return map_evidence(arguments)
    packed = pack_arguments(arguments)
    return {'arguments_typed': [{'type': 'boolean' if x.kind else 'uint32', 'raw': x.value} for x in packed], 'arguments_uint32': [x.value for x in packed] if all((x.kind == 0 for x in packed)) else None}

class _Payload:
    __slots__ = ('storage', 'vtable', 'address', 'owner', 'values', 'destroyed', 'callbacks')

    def __init__(self, owner: int):
        self.storage = C.create_string_buffer(PAYLOAD_SIZE)
        self.vtable = (C.c_void_p * PAYLOAD_VTABLE_SLOTS)()
        self.address = C.addressof(self.storage)
        self.owner = owner
        self.values: list[int | BooleanArgument] = []
        self.destroyed = False
        self.callbacks = []
        struct.pack_into('<QQ', self.storage, 0, C.addressof(self.vtable), owner)

class NativeScriptArguments:
    """Install the bounded host-owned argument factory on a native host.

    `arguments(payload)` is intended for the host's synchronous event-dispatch
    callback while Core still owns the payload. AUX +0x48 is the sole release
    path and discards the strong references after the verified destructor call.
    """

    def __init__(self, host, *, max_live: int=MAX_LIVE_PAYLOADS):
        verify_boolean_source()
        if isinstance(max_live, bool) or not isinstance(max_live, int) or (not 1 <= max_live <= MAX_LIVE_PAYLOADS):
            raise ValueError('Live native argument payload bound must be between 1 and 64')
        if not hasattr(host, 'aux_vtable') or not hasattr(host, 'aux_object') or (not hasattr(host, '_bind')):
            raise TypeError('Native argument adapter requires the verified auxiliary host interface')
        self.host = host
        self.max_live = max_live
        self._payloads: dict[int, _Payload] = {}
        host._bind(host.aux_vtable, AUX_SLOT_CREATE, C.c_void_p, [C.c_void_p], self._create)
        host._bind(host.aux_vtable, AUX_SLOT_RELEASE, None, [C.c_void_p, C.c_void_p], self._release)

    def _aux_pointer(self) -> int:
        return C.addressof(self.host.aux_object)

    def _check_aux(self, this) -> int:
        owner = self._aux_pointer()
        if not this or int(this) != owner:
            raise ValueError('Script-argument factory received a different auxiliary interface')
        return owner

    def _create(self, this) -> int:
        owner = self._check_aux(this)
        if len(self._payloads) >= self.max_live:
            raise ValueError('Live native script-argument payload bound exceeded')
        payload = _Payload(owner)
        address = payload.address
        if address in self._payloads:
            raise RuntimeError('Native script-argument address collision')
        self._payloads[address] = payload
        for offset in range(0, PAYLOAD_VTABLE_SLOTS * 8, 8):
            self._bind_payload(payload, offset, None, [C.c_void_p], lambda obj, offset=offset: self.host._fatal('unimplemented script-argument method', interface='script_arguments', slot=hex(offset), result_substituted=False))
        self._bind_payload(payload, PAYLOAD_DESTRUCTOR_SLOT, None, [C.c_void_p, C.c_uint32], lambda obj, deleting, address=address: self._destroy(address, obj, deleting))
        self._bind_payload(payload, PAYLOAD_APPEND_UINT32_SLOT, C.c_uint32, [C.c_void_p, C.c_uint32], lambda obj, value, address=address: self._append(address, obj, value))
        self._bind_payload(payload, PAYLOAD_APPEND_BOOLEAN_SLOT, C.c_uint32, [C.c_void_p, C.c_uint8], lambda obj, value, address=address: self._append_boolean(address, obj, value))
        return address

    def _bind_payload(self, payload: _Payload, offset: int, result, arguments, callback) -> None:

        def guarded(*args):
            try:
                return callback(*args)
            except BaseException as exc:
                import traceback
                self.host._fatal('native script-argument payload callback exception', slot=hex(offset), error=repr(exc), python_traceback=traceback.format_exc(limit=12))
        fn = C.WINFUNCTYPE(result, *arguments)(guarded)
        payload.callbacks.append(fn)
        payload.vtable[offset // 8] = C.cast(fn, C.c_void_p).value

    def _get_live(self, address: int) -> _Payload:
        payload = self._payloads.get(address)
        if payload is None or payload.destroyed:
            raise ValueError('Unknown or released native script-argument payload')
        return payload

    def _append(self, address: int, this, value) -> int:
        payload = self._get_live(address)
        if not this or int(this) != address:
            raise ValueError('Script-argument append received a different payload')
        if isinstance(value, bool) or not isinstance(value, int) or (not 0 <= value <= 4294967295):
            raise ValueError('Script argument must be an unsigned 32-bit value')
        if len(payload.values) >= MAX_ARGUMENTS:
            raise ValueError('Native script-argument count exceeds the diagnostic capacity')
        payload.values.append(value)
        return len(payload.values) - 1

    def _destroy(self, address: int, this, deleting) -> None:
        payload = self._get_live(address)
        if not this or int(this) != address:
            raise ValueError('Script-argument destructor received a different payload')
        if isinstance(deleting, bool) or not isinstance(deleting, int) or deleting != 0:
            raise ValueError('Only the verified non-deleting payload destructor form is supported')
        payload.destroyed = True

    def _append_boolean(self, address: int, this, value) -> int:
        payload = self._get_live(address)
        if not this or int(this) != address:
            raise ValueError('Script-argument append received a different payload')
        argument = BooleanArgument(value)
        if len(payload.values) >= MAX_ARGUMENTS:
            raise ValueError('Native script-argument count exceeds the diagnostic capacity')
        payload.values.append(argument)
        return len(payload.values) - 1

    def _release(self, this, payload_pointer) -> None:
        owner = self._check_aux(this)
        if not payload_pointer:
            raise ValueError('Cannot release a null native script-argument payload')
        address = int(payload_pointer)
        payload = self._get_live(address)
        if payload.owner != owner:
            raise ValueError('Native script-argument payload belongs to a different auxiliary interface')
        self._destroy(address, address, 0)
        del self._payloads[address]

    def arguments(self, payload_pointer) -> tuple[int | BooleanArgument, ...]:
        """Return appended typed raw arguments for the active dispatch only."""
        if not payload_pointer:
            raise ValueError('Cannot inspect a null native script-argument payload')
        return tuple(self._get_live(int(payload_pointer)).values)

    @property
    def live_count(self) -> int:
        return len(self._payloads)
