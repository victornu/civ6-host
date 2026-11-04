"""Isolated raw-stream transport draft. Never loads or calls GameCore.

Keep each facade strongly referenced across its entire native caller lifetime.
Callbacks cannot report Python exceptions through a native return: every callback
failure poisons this object and terminates the process. Exercise failures only in
disposable subprocesses. Pure ByteTransport failures raise normally for tests.
"""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import ctypes as C
import hashlib
import json
import os
from pathlib import Path
import struct
import sys
import threading
ROOT = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_checkpoint_stream.py')))).resolve().parents[1]
PROOF_SHA256 = '5fb1c28a45e1afbaba6a823b56b2b5b4687499d32e60a8411651a7349d0fa6d5'
PROOF_PATH = ROOT / 'work/native-checkpoint-raw-stream-plan342.json'
PARENT_SHA256 = 'a1cdb76e813f5b7c9735ab694d0ebebd9d88b0d2fece1d3fdedcd5494ad8f275'
UINT64_MAX = (1 << 64) - 1
FATAL_EXIT_CODE = 86
GUARD = bytes.fromhex('dd971c41302afab884b3bcd73910e284')
VTABLE_SLOTS = 64

def terminate_worker(exit_code):
    """Stop a poisoned disposable worker without running native DLL detach.

    Probe358 logged its stream-budget refusal, then remained alive until the
    supervisor deadline under os._exit. Use the same immediate Windows process
    termination as DiagnosticHost; retain _exit only as the last-resort path.
    """
    try:
        if sys.platform == 'win32':
            terminate = C.WinDLL('kernel32').TerminateProcess
            terminate.argtypes, terminate.restype = ([C.c_void_p, C.c_uint32], C.c_int)
            terminate(C.c_void_p(-1), exit_code)
    finally:
        os._exit(exit_code)

def verify_source():
    raw = _resolve_resource_path(PROOF_PATH).read_bytes()
    if hashlib.sha256(raw).hexdigest() != PROOF_SHA256:
        raise RuntimeError('Raw stream plan pin changed')
    proof = json.loads(raw)
    parent_path = 'work/native-checkpoint-stream-contract341.json'
    if proof['schema'] != 'civ6rl.native_checkpoint_raw_stream_plan.v1' or proof['images']['core']['sha256'] != 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3' or proof['images']['exe']['sha256'] != 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63' or (proof['parents'][parent_path]['sha256'] != PARENT_SHA256) or (proof['bounded_closure']['direct_stream_methods_observed'] != {'writer': [40], 'reader': [48, 64]}) or (proof['adapter_plan']['reader28_if_later_needed']['initial_admission'] is not False) or (proof['native_execution'] is not False):
        raise RuntimeError('Raw stream plan contract changed')
    if hashlib.sha256(_resolve_resource_path(ROOT / parent_path).read_bytes()).hexdigest() != PARENT_SHA256:
        raise RuntimeError('Raw stream parent pin changed')
    return proof

def uint64(value, label):
    if type(value) is not int or not 0 <= value <= UINT64_MAX:
        raise ValueError(label + ' must be an exact uint64')
    return value

class ByteTransport:
    """Pure bounded byte storage; resource bounds are diagnostic policy."""

    def __init__(self, mode, *, max_bytes, max_calls, input_bytes=b''):
        verify_source()
        if mode not in ('writer', 'reader'):
            raise ValueError('Unknown stream mode')
        if type(max_bytes) is not int or not 0 < max_bytes <= sys.maxsize or type(max_calls) is not int or (not 0 < max_calls <= UINT64_MAX):
            raise ValueError('Explicit positive byte/call limits required')
        if type(input_bytes) is not bytes or len(input_bytes) > max_bytes:
            raise ValueError('Invalid immutable input or byte budget')
        if mode == 'writer' and input_bytes:
            raise ValueError('Writer must start empty')
        self.mode, self.max_bytes, self.max_calls = (mode, max_bytes, max_calls)
        self.input_bytes, self.output = (input_bytes, bytearray())
        self.cursor = self.calls = 0
        self.poisoned = self.closed = False
        self.error = None

    def poison(self, error):
        self.poisoned = True
        self.error = str(error)[:512]

    def begin(self, mode):
        if self.poisoned or self.closed or self.mode != mode:
            raise RuntimeError('Stream closed, poisoned or wrong mode')
        if self.calls >= self.max_calls:
            raise ValueError('Stream call budget exceeded')
        self.calls += 1

    def write_bytes(self, data):
        try:
            self.begin('writer')
            if type(data) is not bytes:
                raise ValueError('Writer accepts exact bytes')
            self.check_write_length(len(data))
            self.output.extend(data)
            self.cursor = len(self.output)
            return 0
        except BaseException as exc:
            self.poison(exc)
            raise

    def check_write_length(self, length):
        uint64(length, 'write length')
        if length > self.max_bytes - len(self.output):
            raise ValueError('Stream byte budget exceeded')

    def checked_read(self, request, capacity):
        uint64(capacity, 'destination capacity')
        if type(request) is not bytes or len(request) != 40:
            raise ValueError('Reader requires exact request40')
        offset, length, alignment, userdata, callback = struct.unpack('<5Q', request)
        if offset != UINT64_MAX:
            raise ValueError('Only source sequential offset is admitted')
        if userdata or callback:
            raise ValueError('Request callbacks are not admitted')
        if length > capacity:
            raise ValueError('Request exceeds destination capacity')
        if length > self.max_bytes or length > len(self.input_bytes) - self.cursor:
            raise ValueError('Short input refused before copy')
        return self.input_bytes[self.cursor:self.cursor + length]

    def read_bytes(self, request, capacity):
        try:
            self.begin('reader')
            data = self.checked_read(request, capacity)
            self.cursor += len(data)
            return data
        except BaseException as exc:
            self.poison(exc)
            raise

    def finish_read(self):
        try:
            self.begin('reader')
        except BaseException as exc:
            self.poison(exc)
            raise

class _Region(C.Structure):
    _fields_ = [('base', C.c_void_p), ('allocation_base', C.c_void_p), ('allocation_protect', C.c_uint32), ('region_size', C.c_size_t), ('state', C.c_uint32), ('protect', C.c_uint32), ('type', C.c_uint32)]

class LocalMemory:
    """OS-checked local reads/writes; no unchecked source dereference."""

    def __init__(self):
        if sys.platform != 'win32' or C.sizeof(C.c_void_p) != 8:
            raise RuntimeError('This draft requires Win64')
        if C.sizeof(_Region) != 48:
            raise RuntimeError('Unexpected MEMORY_BASIC_INFORMATION layout')
        self.kernel = C.WinDLL('kernel32', use_last_error=True)
        k = self.kernel
        k.GetCurrentProcess.argtypes, k.GetCurrentProcess.restype = ([], C.c_void_p)
        k.VirtualQuery.argtypes = [C.c_void_p, C.POINTER(_Region), C.c_size_t]
        k.VirtualQuery.restype = C.c_size_t
        for name in ('ReadProcessMemory', 'WriteProcessMemory'):
            f = getattr(k, name)
            f.argtypes = [C.c_void_p, C.c_void_p, C.c_void_p, C.c_size_t, C.POINTER(C.c_size_t)]
            f.restype = C.c_int
        self.process = k.GetCurrentProcess()

    def check_span(self, address, length, *, writable=False):
        uint64(address, 'address')
        uint64(length, 'span length')
        if not length:
            return
        if not address or address > UINT64_MAX - length:
            raise ValueError('Invalid or overflowing memory span')
        end, current = (address + length, address)
        protections = {4, 8, 64, 128} if writable else {2, 4, 8, 32, 64, 128}
        while current < end:
            region = _Region()
            result = self.kernel.VirtualQuery(current, C.byref(region), C.sizeof(region))
            if result != C.sizeof(region) or region.state != 4096 or region.protect & 256 or (region.protect & 255 not in protections):
                raise ValueError('Unreadable or unwritable local span')
            following = int(region.base or 0) + region.region_size
            if following <= current:
                raise ValueError('Invalid local memory region')
            current = min(end, following)

    def read(self, address, length):
        self.check_span(address, length)
        if not length:
            return b''
        storage = C.create_string_buffer(GUARD + bytes(length) + GUARD, length + 32)
        count = C.c_size_t()
        if not self.kernel.ReadProcessMemory(self.process, address, C.addressof(storage) + 16, length, C.byref(count)) or count.value != length:
            raise OSError('Incomplete OS-checked local read')
        snapshot = storage.raw
        if snapshot[:16] != GUARD or snapshot[-16:] != GUARD:
            raise RuntimeError('Read staging canary changed')
        return snapshot[16:-16]

    def write(self, address, data):
        self.check_span(address, len(data), writable=True)
        if not data:
            return
        source = C.create_string_buffer(data, len(data))
        count = C.c_size_t()
        if not self.kernel.WriteProcessMemory(self.process, address, source, len(data), C.byref(count)) or count.value != len(data):
            raise OSError('Incomplete OS-checked local write; stream must terminate')

class Win64Stream:
    """Two distinct mode-specific facades; owner must outlive native callers.

    Do not pass just pointer to another owner and discard this instance. All
    ctypes object/table/callback references are deliberately held here. close()
    invalidates use but retains them, so a late call still reaches the fatal trap.
    Unknown slots within the allocated0x200-byte table are fatal. Access beyond
    that bounded table is unsupported; no universal vtable size is claimed.
    """

    def __init__(self, mode, *, max_bytes, max_calls, input_bytes=b''):
        self.transport = ByteTransport(mode, max_bytes=max_bytes, max_calls=max_calls, input_bytes=input_bytes)
        self.memory = LocalMemory()
        self.thread_id, self._entered = (threading.get_ident(), False)
        self._callbacks = []
        trap_type = C.WINFUNCTYPE(None, C.c_void_p)
        pointers = []
        for index in range(VTABLE_SLOTS):

            def trap(this, slot=index * 8):
                self._fatal(RuntimeError(f'Unadmitted stream slot {slot:#x}'))
            callback = trap_type(trap)
            self._callbacks.append(callback)
            pointers.append(C.cast(callback, C.c_void_p).value)
        methods = {40: (C.WINFUNCTYPE(C.c_int32, C.c_void_p, C.c_void_p, C.c_uint64), self._write)} if mode == 'writer' else {48: (C.WINFUNCTYPE(None, C.c_void_p, C.c_void_p, C.c_void_p, C.c_uint64), self._read), 64: (C.WINFUNCTYPE(None, C.c_void_p), self._finish)}
        for slot, (prototype, operation) in methods.items():

            def checked(*args, operation=operation):
                try:
                    self._check(args[0])
                    self._entered = True
                    result = operation(*args[1:])
                    self._check_storage()
                    return result
                except BaseException as exc:
                    self._fatal(exc)
                finally:
                    self._entered = False
            callback = prototype(checked)
            self._callbacks.append(callback)
            pointers[slot // 8] = C.cast(callback, C.c_void_p).value
        table = struct.pack('<' + 'Q' * VTABLE_SLOTS, *pointers)
        self._table_bytes = table
        self._table_storage = C.create_string_buffer(GUARD + table + GUARD, len(table) + 32)
        self._table_pointer = C.addressof(self._table_storage) + 16
        self._object_bytes = struct.pack('<Q', self._table_pointer)
        self._object_storage = C.create_string_buffer(GUARD + self._object_bytes + GUARD, 40)
        self.pointer = C.addressof(self._object_storage) + 16

    def _fatal(self, exc):
        try:
            self.transport.poison(exc)
            diagnostic = {'stage': 'raw_stream_fatal', 'mode': self.transport.mode, 'error': self.transport.error, 'calls': self.transport.calls, 'cursor': self.transport.cursor, 'poisoned': True}
            os.write(2, (json.dumps(diagnostic) + '\n').encode('utf-8'))
        finally:
            terminate_worker(FATAL_EXIT_CODE)

    def _check(self, this):
        if this != self.pointer or threading.get_ident() != self.thread_id or self._entered or self.transport.closed or self.transport.poisoned:
            raise RuntimeError('Wrong this/thread, reentry, closed or poisoned stream')
        self._check_storage()

    def _check_storage(self):
        if self._object_storage.raw != GUARD + self._object_bytes + GUARD:
            raise RuntimeError('Stream object/vtable pointer canary changed')
        if self._table_storage.raw != GUARD + self._table_bytes + GUARD:
            raise RuntimeError('Stream vtable/canary changed')

    def _write(self, source, length):
        t = self.transport
        t.begin('writer')
        t.check_write_length(length)
        data = self.memory.read(source or 0, length)
        t.output.extend(data)
        t.cursor = len(t.output)
        return 0

    def _read(self, request_pointer, destination, capacity):
        t = self.transport
        t.begin('reader')
        request = self.memory.read(request_pointer or 0, 40)
        data = t.checked_read(request, capacity)
        if data:
            dest_begin = destination or 0
            dest_end = dest_begin + len(data)
            request_begin = request_pointer or 0
            request_end = request_begin + 40
            if dest_begin < request_end and request_begin < dest_end:
                raise ValueError('Destination overlaps request descriptor')
        for storage in (self._object_storage, self._table_storage):
            begin, end = (C.addressof(storage), C.addressof(storage) + C.sizeof(storage))
            if data and (destination or 0) < end and ((destination or 0) + len(data) > begin):
                raise ValueError('Destination overlaps owned stream facade')
        self.memory.write(destination or 0, data)
        t.cursor += len(data)

    def _finish(self):
        self.transport.finish_read()

    def close(self):
        self._check(self.pointer)
        self.transport.closed = True

    def output_bytes(self):
        self._check(self.pointer)
        if self.transport.mode != 'writer':
            raise ValueError('Reader has no generated output')
        return bytes(self.transport.output)
