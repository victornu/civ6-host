"""Explicit missing-option diagnostic, not an AppOptions implementation.

EXE f8490 returns an empty keyed-map fallback when a domain is absent. Its
+68 returns a non-null invalid-value sentinel for an absent key. Core 745dc0
uses the same value layout and returns its own sentinel at RVA 8c0798. Keep
that original native value; do not fabricate an integer setting for the Core.
"""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import ctypes as C
PERFORMANCE_DOMAIN = 4222936745
OBSERVED_OPTION = 3246517102
EMPTY_VALUE_RVA = 9176984
EMPTY_PERFORMANCE_FAULT = 'Performance domain absent (bounded option diagnostic)'

class EmptyPerformanceProbe:

    def __init__(self, host, core_base, read):
        self.host = host
        self.value_address = core_base + EMPTY_VALUE_RVA
        self.value_bytes = read(self.value_address, 24)
        if len(self.value_bytes) != 24 or self.value_bytes[:2] != b'\x00\x00':
            raise ValueError('Pinned Core empty value has an unexpected discriminator')
        self.vtable = (C.c_void_p * 32)()
        self.object = (C.c_void_p * 1)(C.addressof(self.vtable))
        for index in range(len(self.vtable)):
            host._bind(self.vtable, index * 8, None, [C.c_void_p], host._unsupported('empty Performance diagnostic', index * 8))
        host._bind(self.vtable, 104, C.c_void_p, [C.c_void_p, C.c_uint32], self.get_value)
        host._bind(host.vtable, 344, C.c_void_p, [C.c_void_p, C.c_uint32], self.get_domain)
        host.emit('diagnostic_fault_enabled', fault=EMPTY_PERFORMANCE_FAULT, complete_app_options=False, eligible_for_training=False, native_empty_value_rva=hex(EMPTY_VALUE_RVA), native_empty_value_hex=self.value_bytes.hex())

    def get_domain(self, this, key):
        if this != self.host.pointer or key != PERFORMANCE_DOMAIN:
            self.host._fatal('domain outside bounded Performance diagnostic', key=hex(key))
        self.host.emit('diagnostic_empty_performance_domain', key=hex(key), eligible_for_training=False)
        return C.addressof(self.object)

    def get_value(self, this, key):
        if this != C.addressof(self.object):
            self.host._fatal('option outside bounded Performance diagnostic', key=hex(key))
        self.host.emit('diagnostic_absent_performance_option', key=hex(key), native_value_discriminator=0, integer_value_invented=False, eligible_for_training=False)
        return self.value_address

def enable_empty_performance_probe(host, core):
    from civ6_host.runtime.native.native_setup import local_reader
    host.empty_performance_probe = EmptyPerformanceProbe(host, core._handle, local_reader())
