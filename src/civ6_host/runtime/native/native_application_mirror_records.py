"""Read-only access to all 64 setup records for the application mirror.

Use this at the existing pre-finalization mirror checkpoint and to revalidate
the source record on a later notification. It does not create a destination,
copy values into gameplay, classify players, or initialize IS_ALIVE. The
application mirror's explicit baseline/presence policy remains its caller's
responsibility; this is not a replacement for the full EXE configuration.
"""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import ctypes as C
from pathlib import Path
import struct
from civ6_host.runtime.native.native_player_records import _local_reader
from civ6_host.runtime.native.native_source_cache import load_pinned_json
PROOF_SHA256 = '0421e7df0cc5152a987c25f8e8f8ce0562fbd1ec09328fb69045bf5c4805c1cf'
CORE_SHA256 = 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'
EXE_SHA256 = 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63'
_PROOF = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_application_mirror_records.py')))).resolve().parents[1] / 'evidence/native-application-mirror-records' / (PROOF_SHA256 + '.json')
OUTER_VTABLE_RVA = 7987232
INNER_VTABLE_RVA = 8155256
SETUP_OFFSET = 3456
CONFIG_OBJECT_VTABLE_RVA = 8507296
PROVIDER_LOOKUP_RVA = 7625904
PROVIDER_LOOKUP_SLOT = 88
RECORD_COUNT = 64
RECORD_STRIDE = 32
RECORD_INLINE_OFFSET = 184
SETUP_KEY_TABLE_RVA = 9162064
SETUP_KEY_STRIDE = 68
_MAX_POINTER = (1 << 64) - 1

def verify_source():
    proof = load_pinned_json(_PROOF, PROOF_SHA256)
    contract = proof.get('contract', {})
    if proof.get('schema') != 'civ6rl.native_application_mirror_records.static.v1' or proof.get('native_execution') is not False or proof.get('images') != {'core_sha256': CORE_SHA256, 'exe_sha256': EXE_SHA256} or (contract.get('record_count') != RECORD_COUNT) or (contract.get('core_record_stride') != RECORD_STRIDE) or (contract.get('core_setup_offset') != SETUP_OFFSET) or (contract.get('core_inline_offset') != RECORD_INLINE_OFFSET) or (contract.get('core_key_table_rva') != SETUP_KEY_TABLE_RVA) or (contract.get('core_key_stride') != SETUP_KEY_STRIDE) or (contract.get('configuration_vtable_rva') != CONFIG_OBJECT_VTABLE_RVA) or (contract.get('argument_tag_read_width') != 2) or (contract.get('late_cell_creation') is not False) or (proof.get('validation', {}).get('all_captured_instructions_match_pinned_pe') is not True):
        raise RuntimeError('Native application mirror record source contract changed')
    return proof

def _pointer(value, name):
    if type(value) is not int or not 0 < value <= _MAX_POINTER:
        raise ValueError('Invalid ' + name + ' pointer')
    return value

def _read(read, address, size):
    _pointer(address, 'memory')
    if not 0 < size <= 32 or address > _MAX_POINTER - size:
        raise ValueError('Application mirror record read exceeds bound')
    raw = read(address, size)
    if type(raw) is not bytes or len(raw) != size:
        raise ValueError('Incomplete application mirror record copy')
    return raw

def _qword(read, address):
    return struct.unpack('<Q', _read(read, address, 8))[0]

def bounded_get_player_config(core_base: int, context: int, index: int, read=None, lookup=None) -> dict:
    """Resolve one existing record 0..63 and validate its owner/provider/map.

    The return schema is compatible with native_player_records. ``lookup`` is
    an optional pure-test replacement for the verified, nullable +58 lookup.
    Neither the absent-value branch of Core's constructor nor any allocator is
    called here. All pointers are borrowed for the caller's setup lifetime.
    """
    if type(index) is not int or not 0 <= index < RECORD_COUNT:
        raise ValueError('Application mirror admits only setup record indices 0..63')
    _pointer(core_base, 'Core base')
    _pointer(context, 'Core context')
    if core_base > _MAX_POINTER - SETUP_KEY_TABLE_RVA - RECORD_COUNT * SETUP_KEY_STRIDE:
        raise ValueError('Core base relocation exceeds address range')
    if read is None:
        read = _local_reader()
    if not callable(read) or (lookup is not None and (not callable(lookup))):
        raise TypeError('Checked read and optional lookup must be callable')
    proof = verify_source()
    context_raw = _read(read, context, 16)
    outer, inner = struct.unpack('<QQ', context_raw)
    if outer != core_base + OUTER_VTABLE_RVA or not inner:
        raise ValueError('Unexpected GameCore outer context')
    if _qword(read, inner) != core_base + INNER_VTABLE_RVA:
        raise ValueError('Unexpected GameCore inner context')
    setup = inner + SETUP_OFFSET
    descriptor = _qword(read, setup + 128)
    vector_raw = _read(read, setup + 144, 24)
    begin, end, capacity = struct.unpack('<QQQ', vector_raw)
    if begin != setup + RECORD_INLINE_OFFSET or end != begin + RECORD_COUNT * RECORD_STRIDE or capacity != end:
        raise ValueError('Unexpected complete 64-record setup vector')
    address = begin + index * RECORD_STRIDE
    record_raw = _read(read, address, RECORD_STRIDE)
    record_index = struct.unpack_from('<i', record_raw)[0]
    provider, value, owner = struct.unpack_from('<QQQ', record_raw, 8)
    if record_index != index or owner != setup:
        raise ValueError('Application mirror record index or owner differs')
    if not provider or provider != descriptor or (not value):
        raise ValueError('Application mirror record has no matching setup provider/map')
    table = core_base + CONFIG_OBJECT_VTABLE_RVA
    if _qword(read, provider) != table or _qword(read, value) != table:
        raise ValueError('Unexpected setup provider or normalized configuration vtable')
    getter = _qword(read, table + PROVIDER_LOOKUP_SLOT)
    if getter != core_base + PROVIDER_LOOKUP_RVA:
        raise ValueError('Unverified setup provider nullable lookup')
    for fragment in proof['core_functions']['lookup']['fragments']:
        for ins in fragment['instructions']:
            raw = bytes.fromhex(ins['bytes'])
            if _read(read, core_base + int(ins['va'], 16) - 6442450944, len(raw)) != raw:
                raise ValueError('Setup provider lookup code differs from pinned source')
    key_address = core_base + SETUP_KEY_TABLE_RVA + index * SETUP_KEY_STRIDE
    key_raw = _read(read, key_address, 4)
    key = struct.unpack('<I', key_raw)[0]
    if lookup is None:
        lookup = C.WINFUNCTYPE(C.c_void_p, C.c_void_p, C.c_uint32)(getter)
    node = lookup(provider, key)
    if node is None or node == 0:
        raise LookupError('Existing setup provider does not contain the record key')
    _pointer(node, 'provider value')
    node_raw = _read(read, node, 16)
    if struct.unpack_from('<H', node_raw)[0] != 10:
        raise ValueError('Setup record key is not typed-object tag 0xA')
    if struct.unpack_from('<Q', node_raw, 8)[0] != value:
        raise ValueError('Provider record key does not match record map')
    if _read(read, context, 16) != context_raw or _qword(read, inner) != core_base + INNER_VTABLE_RVA or _qword(read, setup + 128) != descriptor or (_read(read, setup + 144, 24) != vector_raw) or (_read(read, address, RECORD_STRIDE) != record_raw) or (_read(read, node, 16) != node_raw) or (_read(read, key_address, 4) != key_raw) or (_qword(read, provider) != table) or (_qword(read, value) != table) or (_qword(read, table + PROVIDER_LOOKUP_SLOT) != getter):
        raise ValueError('Setup record changed during application mirror read')
    return {'index': index, 'key_id': key, 'pointer': value, 'pointer_is_borrowed': True, 'owner_setup': setup, 'provider': provider, 'record': address, 'value_vtable_rva': hex(CONFIG_OBJECT_VTABLE_RVA), 'provider_lookup_rva': hex(PROVIDER_LOOKUP_RVA), 'configuration_modified': False, 'player_assignment_validated': False, 'source_proof_sha256': PROOF_SHA256}
