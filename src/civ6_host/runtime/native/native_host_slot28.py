"""Owned, unopened native history service for the explicit headless profile.

The original host getter returns a stable object. Its transaction method has
a real disconnected branch; returning a null object or reporting a successful
history write would have different semantics.
"""
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import ctypes as C
from pathlib import Path
import struct
import threading
from civ6_host.runtime.native.native_source_cache import load_pinned_json
PROFILE = 'owned-headless-history-not-opened-v1'
PROOF_SHA256 = '4c1e19b7ba1701c0269f6c45a4534ec924f48ec2573cbe7dffeb57931dbeb215'
ROOT = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_host_slot28.py')))).resolve().parents[1]

def verify_source():
    if not PROOF_SHA256:
        raise RuntimeError('Host28 history source proof has not been pinned')
    proof = load_pinned_json(ROOT / 'evidence/native-host-slot28' / (PROOF_SHA256 + '.json'), PROOF_SHA256)
    contract = proof.get('contract', {})
    if proof.get('schema') != 'civ6rl.native_host_slot28.static.v1' or proof.get('images', {}).get('exe_sha256') != 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63' or proof.get('images', {}).get('core_sha256') != 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3' or (contract.get('profile') != PROFILE) or (contract.get('service_size') != 88) or (contract.get('bucket_count') != 8) or (contract.get('bucket_pointer_count') != 16) or (contract.get('disconnected_external_or_core_writes') is not False) or (contract.get('full_exe_history_lifecycle_reproduced') is not False) or (proof.get('binding', {}).get('thunk_va') != '0x1401c9740') or (proof.get('binding', {}).get('getter_va') != '0x140033210') or (proof.get('binding', {}).get('slot') != 40) or (proof.get('functions', {}).get('begin_history', {}).get('code_sha256') != '474c0fb3414202a74c3729a90c27c323c3ac4eaedf22af176ad0df20ffdc08e1') or (proof.get('core_functions', {}).get('history_caller', {}).get('code_sha256') != 'ab9bec8e606c06b26bf193ebaa33aaf65f476f3b533a73316901eec6a18199a1'):
        raise RuntimeError('Host28 history source identity changed')
    return proof

class UnopenedHistory:
    """A bounded ABI facade; no connection-opening API is installed.

    Native callers can only get this identity and try to begin history output.
    All other methods refuse. The owned buffers mirror the source initial
    empty container; they are never handed to a native allocator/destructor.
    """

    def __init__(self, host, *, profile):
        verify_source()
        if profile != PROFILE:
            raise ValueError('Host28 requires the explicit unopened history profile')
        if C.sizeof(C.c_void_p) != 8:
            raise ValueError('Native history facade requires 64-bit pointers')
        self.host, self.profile = (host, profile)
        self.owner_thread = threading.get_ident()
        self.vtable = (C.c_void_p * 64)()
        self.object = (C.c_uint64 * 11)()
        self.sentinel = (C.c_uint64 * 6)()
        self.buckets = (C.c_void_p * 16)()
        self.pointer = C.addressof(self.object)
        sentinel = C.addressof(self.sentinel)
        self.sentinel[0] = self.sentinel[1] = sentinel
        for i in range(16):
            self.buckets[i] = sentinel
        self.object[0] = C.addressof(self.vtable)
        struct.pack_into('<f', self.object, 24, 1.0)
        self.object[32 // 8] = sentinel
        self.object[48 // 8] = C.addressof(self.buckets)
        self.object[56 // 8] = C.addressof(self.buckets) + C.sizeof(self.buckets)
        self.object[64 // 8] = self.object[56 // 8]
        self.object[72 // 8], self.object[80 // 8] = (7, 8)
        self._initial = bytes(self.object)
        for slot in range(0, C.sizeof(self.vtable), 8):
            host._bind(self.vtable, slot, None, [C.c_void_p], self._unsupported(slot))
        host._bind(self.vtable, 8, C.c_uint8, [C.c_void_p, C.c_void_p], self.begin)

    def _unsupported(self, slot):

        def call(this):
            self.check(this)
            self.host._fatal('Unimplemented native history method', interface='history', slot=hex(slot), profile=self.profile, result_substituted=False)
            raise RuntimeError('Native history refusal unexpectedly returned')
        return call

    def check(self, this):
        verify_source()
        if threading.get_ident() != self.owner_thread:
            raise ValueError('Native history profile requires its owned synchronous thread')
        if type(this) is not int or this != self.pointer:
            raise ValueError('Foreign native history identity')
        if self.profile != PROFILE or bytes(self.object) != self._initial or self.sentinel[0] != C.addressof(self.sentinel) or (self.sentinel[1] != C.addressof(self.sentinel)) or any((value != C.addressof(self.sentinel) for value in self.buckets)):
            raise ValueError('Native history requires the actual disconnected empty state')

    def get(self, this):
        self.host._check(this)
        self.check(self.pointer)
        self.host.emit('native_history_service_returned', profile=self.profile, stable_identity=self.pointer, connection_present=False, reference_acquired=False, source_proof_sha256=PROOF_SHA256, original_exe_open_history_lifecycle_reproduced=False, eligible_for_training=False)
        return self.pointer

    def begin(self, this, ruleset):
        self.check(this)
        self.host.emit('native_history_begin_disconnected', profile=self.profile, cache_entries_before=0, cache_entries_after=0, buckets=8, connection_present=False, ruleset_pointer_read=False, history_written=False, native_result=0, source_proof_sha256=PROOF_SHA256, eligible_for_training=False)
        return 0

def install(host, *, profile):
    if hasattr(host, '_native_unopened_history'):
        raise ValueError('Native history service is already installed')
    service = UnopenedHistory(host, profile=profile)
    host._bind(host.vtable, 40, C.c_void_p, [C.c_void_p], service.get)
    host._native_unopened_history = service
    host.emit('native_history_service_installed', profile=profile, connection_present=False, source_proof_sha256=PROOF_SHA256, original_exe_open_history_lifecycle_reproduced=False, native_success_substituted=False, eligible_for_training=False)
    return service
