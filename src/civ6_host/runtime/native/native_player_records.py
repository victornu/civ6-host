"""Read-only access to two setup-owned native configuration objects.

This module only returns a pointer after validating the pinned setup vector,
owner, provider getter and normalized-object vtable. It does not create or
replace values. The mapping from these records to actual player assignments
is still unproven.
"""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import ctypes as C
import struct
from civ6_host.runtime.native.native_setup import INNER_SIZE
from civ6_host.runtime.native.native_setup import INNER_VTABLE_RVA
from civ6_host.runtime.native.native_setup import OUTER_VTABLE_RVA
from civ6_host.runtime.native.native_setup import SETUP_OFFSET
SETUP_KEY_TABLE_RVA = 9162064
SETUP_KEY_STRIDE = 68
CONFIG_OBJECT_VTABLE_RVA = 8507296
PROVIDER_LOOKUP_SLOT = 88
PROVIDER_LOOKUP_RVA = 7625904
RECORD_BEGIN_OFFSET = 144
RECORD_END_OFFSET = 152
RECORD_CAPACITY_OFFSET = 160
RECORD_INLINE_OFFSET = 184
RECORD_STRIDE = 32
RECORD_COUNT = 64

def _local_reader():
    kernel = C.WinDLL('kernel32', use_last_error=True)
    kernel.GetCurrentProcess.argtypes = []
    kernel.GetCurrentProcess.restype = C.c_void_p
    kernel.ReadProcessMemory.argtypes = [C.c_void_p, C.c_void_p, C.c_void_p, C.c_size_t, C.POINTER(C.c_size_t)]
    kernel.ReadProcessMemory.restype = C.c_int
    process = kernel.GetCurrentProcess()

    def read(address: int, size: int) -> bytes:
        if not isinstance(address, int) or address <= 0:
            raise ValueError('Invalid native address')
        if not isinstance(size, int) or not 0 < size <= INNER_SIZE:
            raise ValueError('Native read exceeds the inspection bound')
        buffer = C.create_string_buffer(size)
        count = C.c_size_t()
        if not kernel.ReadProcessMemory(process, C.c_void_p(address), buffer, size, C.byref(count)):
            raise C.WinError(C.get_last_error())
        if count.value != size:
            raise RuntimeError('Incomplete native memory copy')
        return buffer.raw
    return read

def _native_lookup(core_base: int, read):
    """Resolve the source-verified read-only provider vtable slot +0x58."""
    return C.WINFUNCTYPE(C.c_void_p, C.c_void_p, C.c_uint32)(core_base + PROVIDER_LOOKUP_RVA)

def bounded_get_player_config(core_base: int, context: int, index: int, read=None, lookup=None) -> dict:
    """Return a validated pointer to setup record 0 or 1's existing object.

    `read(address, size) -> bytes` and `lookup(provider, key_id) -> address`
    are injectable for pure tests. Production `lookup` calls the verified
    GameCore provider getter, which performs a read-only key-tree lookup.
    The returned pointer is borrowed from the setup/provider lifetime.
    """
    if isinstance(index, bool) or not isinstance(index, int) or index not in (0, 1):
        raise ValueError('Only setup record indices 0 and 1 are admitted')
    if isinstance(core_base, bool) or not isinstance(core_base, int) or core_base <= 0:
        raise ValueError('Invalid GameCore base')
    if isinstance(context, bool) or not isinstance(context, int) or context <= 0:
        raise ValueError('Invalid GameCore context')
    read = read or _local_reader()
    outer_vtable, inner = struct.unpack('<QQ', read(context, 16))
    if outer_vtable != core_base + OUTER_VTABLE_RVA or not inner:
        raise ValueError('Unexpected GameCore outer context')
    if struct.unpack('<Q', read(inner, 8))[0] != core_base + INNER_VTABLE_RVA:
        raise ValueError('Unexpected GameCore inner context')
    setup = inner + SETUP_OFFSET
    begin, end, capacity = struct.unpack('<QQQ', read(setup + RECORD_BEGIN_OFFSET, 24))
    if begin != setup + RECORD_INLINE_OFFSET or end != begin + RECORD_COUNT * RECORD_STRIDE or capacity != end:
        raise ValueError('Unexpected setup record vector layout')
    record_address = begin + index * RECORD_STRIDE
    record = read(record_address, RECORD_STRIDE)
    record_index = struct.unpack_from('<i', record, 0)[0]
    provider, value, owner = struct.unpack_from('<QQQ', record, 8)
    if record_index != index:
        raise ValueError('Setup record index does not match its vector position')
    if owner != setup:
        raise ValueError('Setup record is not owned by this setup object')
    if not provider or not value:
        raise LookupError('Setup record has no native-owned configuration object')
    observed_key_id = struct.unpack('<I', read(core_base + SETUP_KEY_TABLE_RVA + index * SETUP_KEY_STRIDE, 4))[0]
    provider_vtable = struct.unpack('<Q', read(provider, 8))[0]
    if provider_vtable != core_base + CONFIG_OBJECT_VTABLE_RVA:
        raise ValueError('Unexpected setup provider vtable')
    lookup_target = struct.unpack('<Q', read(provider_vtable + PROVIDER_LOOKUP_SLOT, 8))[0]
    if lookup_target != core_base + PROVIDER_LOOKUP_RVA:
        raise ValueError('Unexpected provider +0x58 lookup slot')
    if lookup is None:
        lookup = _native_lookup(core_base, read)
    node = lookup(provider, observed_key_id)
    if not node:
        raise LookupError('Provider +0x58 did not resolve the record key')
    if struct.unpack('<H', read(node, 2))[0] != 10:
        raise ValueError('Provider key resolved to a value other than typed object tag 0xA')
    if struct.unpack('<Q', read(node + 8, 8))[0] != value:
        raise ValueError('Provider key result differs from record +0x10')
    value_vtable = struct.unpack('<Q', read(value, 8))[0]
    if value_vtable != core_base + CONFIG_OBJECT_VTABLE_RVA:
        raise ValueError('Unexpected normalized configuration object vtable')
    return {'index': index, 'key_id': observed_key_id, 'pointer': value, 'pointer_is_borrowed': True, 'owner_setup': setup, 'provider': provider, 'record': record_address, 'value_vtable_rva': hex(value_vtable - core_base), 'provider_lookup_rva': hex(lookup_target - core_base), 'configuration_modified': False, 'player_assignment_validated': False}
