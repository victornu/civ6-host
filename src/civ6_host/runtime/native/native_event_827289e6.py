"""Source-bounded encoder for EXE host callback 0x827289E6 (record B5)."""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import ctypes as C
import struct
from pathlib import Path
from civ6_host.runtime.native.native_application_mirror import decode_scalar
EVENT_KIND = 2188544486
SELECTOR_KEY = 2716180809
VALUE_KEY = 3606901732
POSITION_KEY = 2353434172
OPTIONAL_VALUE_KEY = 2717631346
OPTIONAL_METADATA_KEY = 1532339015
IGNORED_SCALAR_KEY = 955421384
IGNORED_PLAYER_KEY = 4033489650
_EXPECTED_KEYS = frozenset({SELECTOR_KEY, VALUE_KEY, POSITION_KEY, OPTIONAL_VALUE_KEY, OPTIONAL_METADATA_KEY, IGNORED_SCALAR_KEY, IGNORED_PLAYER_KEY})
_EXE_SHA256 = 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63'
_EVIDENCE_SHA256 = '30a78ad61e21b0003de294a0fbd787402835d29a9a89e7bf441418087a39fab1'
_EVIDENCE_PATH = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_event_827289e6.py')))).resolve().parents[1] / 'evidence' / 'native-event-827289e6' / f'{_EVIDENCE_SHA256}.json'

def verify_source_evidence() -> None:
    from civ6_host.runtime.native.native_source_cache import load_pinned_json
    report = load_pinned_json(_EVIDENCE_PATH, _EVIDENCE_SHA256)
    if report.get('schema') != 'civ6rl.native_event_827289e6.static.v3' or report.get('registration_registry', {}).get('callback_va') != '0x14014c4a0' or report.get('images', {}).get('exe_sha256') != _EXE_SHA256:
        raise RuntimeError('Pinned 0x827289E6 source identity mismatch')
    if report['captures']['payload_builder']['body'].get('reachable_bytes_sha256') != 'b67ae6e02bb1eef84525103f3b32485ac22e85de478ca6dd4d7949bb975f906e' or report['contract']['writer']['payload_copy_size'] != '0x28' or report['contract']['writer']['metadata_size'] != '0x3c':
        raise RuntimeError('Pinned 0x827289E6 complete builder/writer contract changed')
    if report['images']['core_sha256'] != 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3' or report['positive_query']['core_captures']['map_index_position']['code_sha256'] != 'a902d6f4fe75debb0860785ab922bbdbc926d04acdbe659f41c31eb417c80835':
        raise RuntimeError('Pinned827289E6 public map query changed')
_QUERY_GUARD = bytes.fromhex('5375a970d0240bc124990fea657cee01')

def query_optional_position(core, context, index, *, read=None, native_api=None, core_sha256='d7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3') -> bytes:
    """Mirror147F10's positive branch through map+68 with an eight-byte output.

    The borrowed outer context remains owned by the host. The newly acquired
    map facade is released after the source pointer-returning query, including
    failure of output/canary validation. Cached facades are outside this profile.
    """
    _FOUNDATION_7987232 = 7987232
    _FOUNDATION_4382784 = 4382784
    _FOUNDATION_7991792 = 7991792
    _FOUNDATION_4416608 = 4416608
    _FOUNDATION_4418768 = 4418768
    if core_sha256 != 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3':
        from civ6_host.runtime.foundation_facade_profiles import query_abi
        from civ6_host.runtime.provenance import resource_root
        _foundation_abi = query_abi(core_sha256, resource_root())
        _FOUNDATION_7987232 = _foundation_abi.table('outer')
        _FOUNDATION_4382784 = _foundation_abi.rva('outer_map')
        _FOUNDATION_7991792 = _foundation_abi.table('map')
        _FOUNDATION_4416608 = _foundation_abi.rva('release_map')
        _FOUNDATION_4418768 = _foundation_abi.rva('optional_position')
    verify_source_evidence()
    if type(index) is not int or not 0 <= index <= 2147483647:
        raise ValueError('827289E6 positive map index must be a signed nonnegative DWORD')
    if core is None or type(context) is not int or context <= 0:
        raise ValueError('827289E6 nonnegative-value path requires live Core and context')
    base = int(core._handle)
    if base <= 0:
        raise ValueError('827289E6 requires a relocated Core image base')
    if read is None:
        from civ6_host.runtime.native.native_setup import local_reader
        read = local_reader()

    def raw(address, length):
        value = read(address, length)
        if not isinstance(value, (bytes, bytearray, memoryview)) or len(value) != length:
            raise ValueError('Incomplete827289E6 native query read')
        return bytes(value)

    def qword(address):
        return struct.unpack('<Q', raw(address, 8))[0]
    if qword(context) != base + _FOUNDATION_7987232:
        raise ValueError('Unexpected827289E6 outer interface')
    for table, offset, target in ((_FOUNDATION_7987232, 168, _FOUNDATION_4382784), (_FOUNDATION_7991792, 8, _FOUNDATION_4416608), (_FOUNDATION_7991792, 104, _FOUNDATION_4418768)):
        if qword(base + table + offset) != base + target:
            raise ValueError('Unexpected827289E6 public map method')
    if native_api is None:
        api = {'get_map': C.WINFUNCTYPE(C.c_void_p, C.c_void_p)(base + _FOUNDATION_4382784), 'lookup_index': C.WINFUNCTYPE(C.c_void_p, C.c_void_p, C.c_void_p, C.c_int32)(base + _FOUNDATION_4418768), 'release_map': C.WINFUNCTYPE(None, C.c_void_p)(base + _FOUNDATION_4416608)}
    else:
        if not isinstance(native_api, dict) or set(native_api) != {'get_map', 'lookup_index', 'release_map'}:
            raise ValueError('827289E6 test seam requires the exact three map operations')
        api = native_api
    facade = api['get_map'](context)
    if not facade or qword(facade) != base + _FOUNDATION_7991792:
        raise ValueError('827289E6 requires the nonnull source map facade')
    try:
        owner = qword(facade + 8)
        if not owner:
            raise ValueError('827289E6 cached map facade is outside the live profile')
        width = struct.unpack('<i', raw(owner + 40, 4))[0]
        count = struct.unpack('<i', raw(owner + 48, 4))[0]
        if width <= 0 or count < 0:
            raise ValueError('827289E6 native map dimensions are invalid')
        storage = C.create_string_buffer(_QUERY_GUARD + bytes(8) + _QUERY_GUARD, 40)
        pointer = C.addressof(storage) + 16
        result = api['lookup_index'](facade, pointer, index)
        if storage.raw[:16] != _QUERY_GUARD or storage.raw[24:] != _QUERY_GUARD:
            raise RuntimeError('827289E6 native output exceeded its source eight-byte extent')
        if result != pointer:
            raise ValueError('827289E6 map query returned a different output pointer')
        return bytes(storage.raw[16:24])
    finally:
        api['release_map'](facade)

def _copy_blob(raw: bytes, read, expected_tag: int, field: str) -> bytes:
    if not isinstance(raw, (bytes, bytearray, memoryview)) or len(raw) != 24:
        raise ValueError(f'Incomplete 0x827289E6 {field} variant')
    view = memoryview(raw).cast('B')
    tag = struct.unpack_from('<H', view)[0]
    pointer, size, flags = struct.unpack_from('<QII', view, 8)
    if tag != expected_tag or not pointer or size != 8 or (flags != 553648129):
        raise ValueError(f'Unverified 0x827289E6 {field} blob envelope')
    data = read(pointer, 8)
    if not isinstance(data, (bytes, bytearray, memoryview)) or len(data) != 8:
        raise ValueError(f'Incomplete 0x827289E6 {field} copy')
    return bytes(data)

def decode_fields(raw_fields: dict[int, bytes], read) -> dict[str, object]:
    """Decode the exact witnessed field set, retaining the tag-0x0D QWORD.

    The normalizer's key 0x8C468E3C branch dereferences the value pointer and
    copies a QWORD to normalized+0x48; it does not interpret tag 0x0D as a
    numeric scalar. Key 0xD6FCF3E4's tag-2 DWORD becomes normalized+0x50.
    Other decoded inputs are returned as explicit source values to support
    later modeling; this function doesn't enqueue or substitute a result.
    """
    verify_source_evidence()
    if not isinstance(raw_fields, dict) or set(raw_fields) != _EXPECTED_KEYS:
        raise ValueError('Unverified 0x827289E6 Core argument keys')
    selector = decode_scalar(raw_fields[SELECTOR_KEY], 3)
    value = decode_scalar(raw_fields[VALUE_KEY], 2)
    optional_value = decode_scalar(raw_fields[OPTIONAL_VALUE_KEY], 2)
    ignored_scalar = decode_scalar(raw_fields[IGNORED_SCALAR_KEY], 2)
    ignored_player = decode_scalar(raw_fields[IGNORED_PLAYER_KEY], 2)
    position = _copy_blob(raw_fields[POSITION_KEY], read, 13, 'position')
    optional_metadata = _copy_blob(raw_fields[OPTIONAL_METADATA_KEY], read, 1024, 'optional metadata')
    return {'selector': selector, 'callback_value': value, 'normalized_qword_48': position, 'optional_value_a1fbc372': optional_value, 'optional_metadata_bytes_5b55a347': optional_metadata, 'ignored_scalar_38f292c8': ignored_scalar, 'ignored_player_f06a2af2': ignored_player, 'record_encoding': 'decoded only; call encode_record for the explicitly supported initialized-cache profile'}

def encode_record(raw_fields: dict[int, bytes], read, *, sequence: int, gate_enabled: bool, cache_initialized: bool, notification_counter: int, optional_thread_hook: bool, queue_metadata_service: bool, padding_policy: str, core=None, context=None, native_api=None, core_sha256='d7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3') -> bytes | None:
    """Compatibility entry point for callers which only own zero-scope state."""
    if gate_enabled is True and (type(notification_counter) is not int or notification_counter != 0):
        raise ValueError('827289E6 nonzero notification counter requires explicit metadata state')
    record, _ = encode_scoped_record(raw_fields, read, sequence=sequence, gate_enabled=gate_enabled, cache_initialized=cache_initialized, notification_counter=notification_counter, metadata_counter=0, optional_thread_hook=optional_thread_hook, queue_metadata_service=queue_metadata_service, padding_policy=padding_policy, core=core, context=context, native_api=native_api, core_sha256=core_sha256)
    return record

def encode_scoped_record(raw_fields: dict[int, bytes], read, *, sequence: int, gate_enabled: bool, cache_initialized: bool, notification_counter: int, metadata_counter: int, optional_thread_hook: bool, queue_metadata_service: bool, padding_policy: str, core=None, context=None, native_api=None, core_sha256='d7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3') -> tuple[bytes | None, int]:
    """Build B5 and return the source-defined secondary metadata state.

    The callback returns before its writer when the public-cache gate is off.
    The supported headless profile has the gate on after cache initialization,
    an empty optional per-thread callback pair, no queue metadata service, and
    source-defined notification counters. The caller supplies cache lifecycle
    evidence, validates the empty receiver and commits the returned secondary
    state only with a successful enqueue. This pure encoder owns no host state.

    Native callback stack padding at payload+4 is uninitialized. The required
    policy explicitly zeroes those four unspecified bytes. All initialized
    fields and writer copies follow source; this is not byte-for-byte stack replay.
    """
    verify_source_evidence()
    if type(gate_enabled) is not bool:
        raise ValueError('827289E6 gate state must be an explicit boolean')
    if gate_enabled is False:
        return (None, metadata_counter)
    if cache_initialized is not True:
        raise ValueError('827289E6 requires witnessed public cache initialization')
    if optional_thread_hook is not False:
        raise ValueError('827289E6 optional per-thread hook is not modeled')
    if queue_metadata_service is not False:
        raise ValueError('827289E6 queue metadata service is not modeled')
    from civ6_host.runtime.native.native_notification_metadata import metadata_scope_transition
    flag, next_metadata_counter = metadata_scope_transition(notification_counter, metadata_counter)
    if type(sequence) is not int or not 1 <= sequence <= 2147483647:
        raise ValueError('827289E6 sequence must be a bounded positive integer')
    if padding_policy != 'headless-zero-initialization':
        raise ValueError('827289E6 requires an explicit stack-padding policy')
    values = decode_fields(raw_fields, read)
    optional_value = int(values['optional_value_a1fbc372'])
    optional_position = struct.pack('<ii', -9999, -9999)
    optional_scalar = 0
    if optional_value < 2147483648:
        optional_position = query_optional_position(core, context, optional_value, read=read, native_api=native_api, core_sha256=core_sha256)
        optional_scalar = int(values['ignored_scalar_38f292c8'])
    metadata = bytearray(60)
    for off in (0, 4, 12, 20, 28, 36, 44):
        struct.pack_into('<I', metadata, off, 4294967295)
    for off in (8, 16, 24, 32, 40):
        struct.pack_into('<H', metadata, off, 65535)
    for off in (10, 18, 26, 34, 42):
        struct.pack_into('<H', metadata, off, 0)
    struct.pack_into('<I', metadata, 56, flag)
    record = bytearray(128)
    struct.pack_into('<IIII', record, 0, 128, 181, sequence, 0)
    record[16:76] = metadata
    struct.pack_into('<I', record, 80, sequence)
    record[88:96] = values['normalized_qword_48']
    struct.pack_into('<I', record, 96, int(values['callback_value']))
    record[100:108] = optional_position
    struct.pack_into('<I', record, 108, optional_scalar)
    record[112:120] = values['optional_metadata_bytes_5b55a347']
    return (bytes(record), next_metadata_counter)
__all__ = ['EVENT_KIND', 'decode_fields', 'encode_record', 'encode_scoped_record', 'query_optional_position', 'verify_source_evidence']
