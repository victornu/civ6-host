"""Source-backed plot descriptor producer for event5D0F4014."""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import ctypes as C
import hashlib
import json
import struct
from pathlib import Path
from civ6_host.runtime.native.native_application_mirror import decode_scalar
from civ6_host.runtime.native.native_feature_visibility_event import CORE_CODE_PINS
from civ6_host.runtime.native.native_feature_visibility_event import _copy_blob
EVENT_KIND, RECORD_TYPE, RECORD_SIZE = (1561280532, 152, 128)
BLOB_KEY, SELECTOR_KEY = (2353434172, 2716180809)
VALUE_KEY, TAIL_KEY = (2717631346, 3606901732)
SNAPSHOT_SIZE = 24
_SNAPSHOT_GUARD = b'\xd3' * 16
_PROOF_SHA = 'a3b4062c077f890366dbf2f40b4671cf7934efccef47c9e75779cc232e89c4ac'
_PROOF = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_event_5d0f4014.py')))).resolve().parents[1] / 'evidence/native-event-5d0f4014' / f'{_PROOF_SHA}.json'
_CORE_EXTRA_PINS = {(4382336, 36): '6fb985fba998e73a2093f335c5df7a15f060a7ab76a462ca44714ccf7c96838c', (66960, 38): '7cf4be1451186311c72ab518fc541a4d7b1b46fe41b7688658b7d5aaf3ea5903', (4395200, 94): 'fd47926a6db842db064a0c37002e2516f731a12b8fbfb3879bf2b6e4d74e2d95', (4435760, 29): 'af3c1a3bbe9df9206e3a9c8b9824700e96c36331a75a4ef585169dba6597f72c', (4388528, 25): 'e89afe56fddf938745c88f47f528c77ad21b5d8c4d3c6d171efab1c118341d0e', (4388560, 32): '918678ea6da9249450d59473ce1882d02b8455062f7ef73f732de1b086bdf635'}

def verify_source_evidence() -> None:
    raw = _resolve_resource_path(_PROOF).read_bytes()
    if hashlib.sha256(raw).hexdigest() != _PROOF_SHA:
        raise RuntimeError('Pinned5D0F4014 evidence changed')
    proof = json.loads(raw)
    if proof.get('schema') != 'civ6rl.native_event_5d0f4014.static.v1' or proof['registration']['callback_va'] != '0x140152660' or proof['images']['core_sha256'] != 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3' or (proof['images']['exe_sha256'] != 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63') or (proof['captures']['query']['raw_sha256'] != '18109bf51803e359c32da882ce3ce204c6eff3fab1273e2d87d33571db697c0c') or (proof['captures']['writer']['raw_sha256'] != 'b900721c6453038397e01d598e8b3ef234593bd324bab2c9bcca72b8cb434dda'):
        raise RuntimeError('Pinned5D0F4014 identity changed')

def decode_fields(fields: dict[int, bytes], read) -> dict:
    verify_source_evidence()
    if not isinstance(fields, dict) or set(fields) != {BLOB_KEY, SELECTOR_KEY, VALUE_KEY, TAIL_KEY}:
        raise ValueError('Unverified5D0F4014 input fields')
    selector = decode_scalar(fields[SELECTOR_KEY], 3)
    value = decode_scalar(fields[VALUE_KEY], 2)
    tail = decode_scalar(fields[TAIL_KEY], 2)
    position = _copy_blob(fields[BLOB_KEY], read, 0)
    x, y = struct.unpack('<ii', position)
    return {'position_bytes': position, 'x': x, 'y': y, 'selector': selector, 'source_value': value, 'descriptor_tail': tail}

def _check_position(position):
    if not isinstance(position, dict) or type(position.get('position_bytes')) is not bytes or len(position['position_bytes']) != 8 or (type(position.get('x')) is not int) or (type(position.get('y')) is not int) or (struct.unpack('<ii', position['position_bytes']) != (position['x'], position['y'])):
        raise ValueError('Unverified5D0F4014 decoded position')
    for key in ('source_value', 'descriptor_tail'):
        if type(position.get(key)) is not int or not 0 <= position[key] <= 4294967295:
            raise ValueError('Unverified5D0F4014 scalar value')

def query_descriptor(core, context, position: dict, *, read=None, native_api=None, core_sha256='d7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3') -> dict:
    """Perform the complete147CC0 query on an admitted live map and plot.

    Null map/plot is refused because the source then leaves required output
    bytes uninitialized. Native values are queried, never guessed. A borrowed
    outer context is used; new map, plot and service references are released.
    """
    if core_sha256 not in ('d7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3', '259b90a473a256aff6a7d621a4f3717e46f6921c59b9817475375c88b97e8c83', '324c51e9ea3531758842e16c69e6cddbefbb226c5b675c3d6e60111646c2e98c'):
        raise ValueError('Unqualified facade engine')
    from civ6_host.runtime.foundation_facade_profiles import query_abi, verify_xp1_once, select_tables
    from civ6_host.runtime.provenance import resource_root
    _foundation_abi = query_abi(core_sha256, None if core_sha256 == 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3' else resource_root())
    verify_source_evidence()
    _check_position(position)
    base = int(core._handle)
    if read is None:
        from civ6_host.runtime.native.native_setup import local_reader
        read = local_reader()
    if native_api is None:
        if core_sha256 == 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3':
            for (rva, size), expected in {**CORE_CODE_PINS, **_CORE_EXTRA_PINS}.items():
                if hashlib.sha256(read(base + rva, size)).hexdigest() != expected:
                    raise ValueError(f'5D0F4014 Core code changed at{rva:#x}')
        else:
            verify_xp1_once(core, base, read, resource_root(), core_sha256=core_sha256)

    def check(pointer, vt, slots):
        if not pointer or int.from_bytes(read(pointer, 8), 'little') != base + vt:
            raise ValueError('Unexpected5D0F4014 Core interface')
        for offset, target in slots:
            if int.from_bytes(read(base + vt + offset, 8), 'little') != base + target:
                raise ValueError('5D0F4014 Core virtual slot changed')
    check(context, _foundation_abi.table('outer'), ((168, _foundation_abi.rva('outer_map')), (256, _foundation_abi.rva('outer_service'))))
    if native_api is None:
        from civ6_host.runtime.native.native_plot_ui_query import query_plot_ui
        api = {'outer_map': C.WINFUNCTYPE(C.c_void_p, C.c_void_p)(base + _foundation_abi.rva('outer_map')), 'get_plot': C.WINFUNCTYPE(C.c_void_p, C.c_void_p, C.c_int32, C.c_int32)(base + _foundation_abi.rva('get_plot')), 'release_map': C.WINFUNCTYPE(None, C.c_void_p)(base + _foundation_abi.rva('release_map')), 'release_plot': C.WINFUNCTYPE(None, C.c_void_p)(base + _foundation_abi.rva('release_plot')), 'snapshot180': C.WINFUNCTYPE(C.c_uint64, C.c_void_p, C.c_void_p, C.c_uint32)(base + _foundation_abi.rva('plot_snapshot180')), 'snapshot178': C.WINFUNCTYPE(C.c_uint64, C.c_void_p, C.c_void_p, C.c_uint32)(base + _foundation_abi.rva('plot_snapshot178')), 'outer_service': C.WINFUNCTYPE(C.c_void_p, C.c_void_p)(base + _foundation_abi.rva('outer_service')), 'translate': C.WINFUNCTYPE(C.c_int32, C.c_void_p, C.c_int32)(base + _foundation_abi.rva('service_player_type_hash')), 'release_service': C.WINFUNCTYPE(None, C.c_void_p)(base + _foundation_abi.rva('release_service')), 'ui_query': lambda p: query_plot_ui(core, context, p['position_bytes'], read=read, core_sha256=core_sha256)}
    else:
        api = native_api
        if set(api) != {'outer_map', 'get_plot', 'release_map', 'release_plot', 'snapshot180', 'snapshot178', 'outer_service', 'translate', 'release_service', 'ui_query'}:
            raise ValueError('5D0F4014 test seam must provide all ten entrypoints')
    map_obj = api['outer_map'](context)
    if not map_obj:
        raise ValueError('5D0F4014 null map leaves uninitialized source output')
    try:
        check(map_obj, _foundation_abi.table('map'), ((8, _foundation_abi.rva('release_map')), (64, _foundation_abi.rva('get_plot'))))
        plot = api['get_plot'](map_obj, position['x'], position['y'])
    finally:
        api['release_map'](map_obj)
    if not plot:
        raise ValueError('5D0F4014 null plot leaves uninitialized source output')
    try:
        check(plot, _foundation_abi.table('plot'), ((8, _foundation_abi.rva('release_plot')), (384, _foundation_abi.rva('plot_snapshot180')), (376, _foundation_abi.rva('plot_snapshot178'))))
        snapshot180 = C.create_string_buffer(SNAPSHOT_SIZE + len(_SNAPSHOT_GUARD))
        snapshot178 = C.create_string_buffer(SNAPSHOT_SIZE + len(_SNAPSHOT_GUARD))
        for output in (snapshot180, snapshot178):
            C.memset(C.addressof(output), 165, SNAPSHOT_SIZE)
            C.memmove(C.addressof(output) + SNAPSHOT_SIZE, _SNAPSHOT_GUARD, len(_SNAPSHOT_GUARD))
        api['snapshot180'](plot, C.addressof(snapshot180), 0)
        if snapshot180.raw[SNAPSHOT_SIZE:] != _SNAPSHOT_GUARD:
            raise ValueError('5D0F4014 snapshot180 exceeded source24-byte output')
        api['snapshot178'](plot, C.addressof(snapshot178), 0)
        if snapshot178.raw[SNAPSHOT_SIZE:] != _SNAPSHOT_GUARD:
            raise ValueError('5D0F4014 snapshot178 exceeded source24-byte output')
        service = api['outer_service'](context)
        if not service:
            raise ValueError('5D0F4014 null translation service is not a native fallback')
        try:
            check(service, _foundation_abi.table('type_service'), ((8, _foundation_abi.rva('release_service')), (200, _foundation_abi.rva('service_player_type_hash'))))
            byte_b = struct.unpack_from('<b', snapshot180.raw, 11)[0]
            byte_c = struct.unpack_from('<b', snapshot180.raw, 12)[0]
            translated = api['translate'](service, byte_c)
            if type(translated) is not int or not -(1 << 31) <= translated < 1 << 31:
                raise ValueError('Invalid native5D0F4014 translated DWORD')
            flags = snapshot180.raw[17]
            has_entity = struct.unpack_from('<I', snapshot178.raw, 8)[0] != 4294967295
            ui = api['ui_query'](position)
            if not isinstance(ui, dict) or type(ui.get('value_u64')) is not int or (not 0 <= ui['value_u64'] < 1 << 64) or (type(ui.get('flag_u8')) is not int) or (not 0 <= ui['flag_u8'] <= 255):
                raise ValueError('Invalid native5D0F4014 UI query output')
            return {'snapshot_byte_b': byte_b, 'translated_value': translated, 'ui_value': ui['value_u64'], 'ui_flag': ui['flag_u8'], 'has_entity': int(has_entity), 'flag_bit1': flags >> 1 & 1, 'flag_bit2': flags >> 2 & 1}
        finally:
            api['release_service'](service)
    finally:
        api['release_plot'](plot)

def encode_record(sequence: int, position: dict, descriptor: dict, *, thread_hook_present: bool, writer_metadata_callback_present: bool, padding_policy: str) -> bytes:
    verify_source_evidence()
    _check_position(position)
    if thread_hook_present is not False or writer_metadata_callback_present is not False:
        raise ValueError('5D0F4014 registered callbacks are not modeled')
    if type(sequence) is not int or not 1 <= sequence <= 2147483647:
        raise ValueError('Invalid5D0F4014 queue sequence')
    if padding_policy != 'zero':
        raise ValueError('5D0F4014 requires explicit zero source-padding policy')
    ranges = {'snapshot_byte_b': (-128, 127), 'translated_value': (-(1 << 31), (1 << 31) - 1), 'ui_value': (0, (1 << 64) - 1), 'ui_flag': (0, 255), 'has_entity': (0, 1), 'flag_bit1': (0, 1), 'flag_bit2': (0, 1)}
    if not isinstance(descriptor, dict) or set(descriptor) != set(ranges):
        raise ValueError('Incomplete5D0F4014 native query result')
    for key, (low, high) in ranges.items():
        if type(descriptor[key]) is not int or not low <= descriptor[key] <= high:
            raise ValueError('Invalid5D0F4014 native query result ' + key)
    record = bytearray(RECORD_SIZE)
    struct.pack_into('<IIII', record, 0, RECORD_SIZE, RECORD_TYPE, sequence, 0)
    struct.pack_into('<II', record, 16, 4294967295, 4294967295)
    for offset in (24, 32, 40, 48, 56):
        struct.pack_into('<HHI', record, offset, 65535, 0, 4294967295)
    struct.pack_into('<I', record, 80, sequence)
    record[88:96] = position['position_bytes']
    struct.pack_into('<iiQII', record, 96, descriptor['snapshot_byte_b'], descriptor['translated_value'], descriptor['ui_value'], position['source_value'], position['descriptor_tail'])
    struct.pack_into('<BBBB', record, 120, descriptor['has_entity'], descriptor['ui_flag'], descriptor['flag_bit1'], descriptor['flag_bit2'])
    return bytes(record)
__all__ = ['EVENT_KIND', 'RECORD_TYPE', 'decode_fields', 'query_descriptor', 'encode_record', 'verify_source_evidence']
