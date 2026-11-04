"""Explicit synchronous headless host state for source-decoded thread gates.

The EXE field predicates are known. Its application instance/thread lifecycle
has not been reproduced: this diagnostic host owns its own application thread
and has no EXE controller activity producers. This is not a captured EXE state.
"""
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
from dataclasses import dataclass
import hashlib
from pathlib import Path
PROFILE = 'owned-synchronous-host-idle-controller-v1'
PROOF_SHA = 'c3adcbf0c3eaef2a5b07290704d3610e0618438ac6991ed70016462efd6aa64f'
_PROOF = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_host_thread_gate.py')))).resolve().parents[1] / 'evidence/native-host-thread-gates' / (PROOF_SHA + '.json')
if hashlib.sha256(_resolve_resource_path(_PROOF).read_bytes()).hexdigest() != PROOF_SHA:
    raise RuntimeError('Native host thread-gate source capture changed')

@dataclass(frozen=True)
class HostThreadGate:
    owner_thread_id: int
    profile: str
    controller_enabled: int = 1
    activity_object_present: bool = False
    activity_count: int = 0

    def __post_init__(self):
        if self.profile != PROFILE:
            raise ValueError('Unknown host thread/controller profile')
        if type(self.owner_thread_id) is not int or not 1 <= self.owner_thread_id <= 4294967295:
            raise ValueError('Owner must be a real Win32 thread ID')
        if self.controller_enabled != 1 or self.activity_object_present is not False or self.activity_count != 0:
            raise ValueError('Controller activity scope lifecycle is not implemented')

    def is_owner_thread(self, current_thread_id):
        if type(current_thread_id) is not int or not 1 <= current_thread_id <= 4294967295:
            raise ValueError('Current thread must be a real Win32 thread ID')
        return current_thread_id == self.owner_thread_id

    def is_controller_active(self):
        return bool(self.controller_enabled and self.activity_object_present and (self.activity_count > 0))

def install_synchronous_host_thread_gate(host, *, profile):
    import ctypes as C
    if hasattr(host, 'thread_gate'):
        raise RuntimeError('Host thread gate already installed')
    current = C.WinDLL('kernel32').GetCurrentThreadId
    current.argtypes, current.restype = ([], C.c_uint32)
    gate = HostThreadGate(int(current()), profile)
    host.thread_gate = gate

    def owner(this):
        host._check(this)
        thread_id = int(current())
        result = gate.is_owner_thread(thread_id)
        host.emit('native_host_thread_gate', slot='0x60', current_thread_id=thread_id, owner_thread_id=gate.owner_thread_id, result=result, profile=profile, original_exe_application_lifecycle_verified=False, eligible_for_training=False)
        return result

    def active(this):
        host._check(this)
        result = gate.is_controller_active()
        host.emit('native_host_controller_gate', slot='0x58', result=result, controller_enabled=gate.controller_enabled, activity_object_present=gate.activity_object_present, activity_count=gate.activity_count, profile=profile, external_controller_activity_producers_admitted=False, eligible_for_training=False)
        return result
    host._bind(host.vtable, 96, C.c_bool, [C.c_void_p], owner)
    host._bind(host.vtable, 88, C.c_bool, [C.c_void_p], active)
    host.emit('native_host_thread_gate_profile', profile=profile, owner_thread_id=gate.owner_thread_id, source_proof_sha256=PROOF_SHA, original_exe_application_lifecycle_verified=False, eligible_for_training=False)
