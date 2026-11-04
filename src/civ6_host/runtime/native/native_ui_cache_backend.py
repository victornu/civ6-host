"""Typed in-process calls for the pinned public cache-facade sequence."""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
from civ6_host.runtime.cache_facade_profiles import facade_abi
from civ6_host.runtime.cache_facade_profiles import verify_facade_source
import ctypes as C
import struct
from civ6_host.runtime.native.native_setup import local_reader
from civ6_host.runtime.native.native_ui_cache_facades import TARGET_RVAS
from civ6_host.runtime.native.native_ui_cache_facades import OUTPUT_SIZE

class NativeCacheFacadeBackend:

    def __init__(self, core, gate_changed, *, context_alive, read=None, core_sha256='d7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3', publication_owner=None):
        self.abi = facade_abi(core_sha256)
        self.publication_owner = publication_owner
        self.core_base = int(core._handle)
        self.read = local_reader() if read is None else read
        self.gate_changed = gate_changed
        self._context_alive = context_alive
        self._known_targets = frozenset(self.abi.targets.values())

    def require_loaded_publication(self, facades=None):
        from civ6_host.runtime.loaded_cache_publication import require_candidate
        return require_candidate(self, facades)

    def read_qword(self, address):
        return struct.unpack('<Q', self.read(address, 8))[0]

    def context_alive(self):
        return self._context_alive() is True

    def set_public_cache_gate(self, enabled):
        if type(enabled) is not bool:
            raise ValueError('Public cache gate requires an explicit boolean')
        if self.publication_owner is not None and enabled is not False:
            raise ValueError('Candidate population cannot open the public cache gate')
        self.gate_changed(enabled)

    def call(self, target, *arguments):
        candidate = self.publication_owner
        if candidate is None:
            return self._call(target, *arguments)
        from civ6_host.runtime.loaded_cache_publication import LoadedCachePublication
        if type(candidate) is not LoadedCachePublication:
            raise ValueError('Foreign candidate publication capability')
        try:
            candidate.before_backend_call(self, target, arguments)
            result = self._call(target, *arguments)
            candidate.after_backend_call(self, target, result)
            return result
        except BaseException:
            candidate.poison()
            raise

    def _call(self, target, *arguments):
        if not self.context_alive():
            raise RuntimeError('Native cache facade outlived its Core context')
        rva = target - self.core_base
        if rva not in self._known_targets:
            raise ValueError('Unverified native cache-facade method')
        if not arguments or type(arguments[0]) is not int or arguments[0] <= 0:
            raise ValueError('Invalid native facade receiver')
        receiver = arguments[0]
        if rva == self.abi.publish_rva:
            candidate = None if self.abi.full_refresh_admitted else self.require_loaded_publication()
            if len(arguments) != 2 or type(arguments[1]) is not int or arguments[1] != 1:
                raise ValueError('Only the source public population flag is admitted')
            try:
                if candidate is not None:
                    candidate.begin(self, receiver)
                C.WINFUNCTYPE(None, C.c_void_p, C.c_uint8)(target)(receiver, 1)
                if candidate is not None:
                    candidate.native_returned(self)
                return None
            except BaseException:
                if candidate is not None:
                    candidate.poison()
                raise
        if rva == self.abi.copy_rva:
            if len(arguments) != 2 or type(arguments[1]) is not bytearray or len(arguments[1]) != OUTPUT_SIZE:
                raise ValueError('Invalid public cache copy buffer')
            output = arguments[1]
            storage = C.create_string_buffer(OUTPUT_SIZE + 32)
            C.memmove(C.addressof(storage), bytes(output), OUTPUT_SIZE)
            C.memset(C.addressof(storage) + OUTPUT_SIZE, 165, 32)
            value = C.WINFUNCTYPE(C.c_uint32, C.c_void_p, C.c_void_p)(target)(receiver, C.addressof(storage))
            if storage.raw[OUTPUT_SIZE:] != b'\xa5' * 32:
                raise BufferError('Native cache copy exceeded its guarded buffer')
            output[:] = storage.raw[:OUTPUT_SIZE]
            return int(value)
        if len(arguments) != 1:
            raise ValueError('Unexpected native facade arguments')
        getters = self.abi.getter_rvas
        if rva in getters:
            return int(C.WINFUNCTYPE(C.c_void_p, C.c_void_p)(target)(receiver) or 0)
        releases = self.abi.release_rvas
        if rva in releases:
            C.WINFUNCTYPE(None, C.c_void_p)(target)(receiver)
            return None
        raise ValueError('Facade target lacks a reviewed ABI')
