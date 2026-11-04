"""Source-bounded codec and query helpers for EXE host event FA5B1159.

The optional per-thread hook and queue metadata service are explicitly refused.
"""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import ctypes as C
import hashlib
import json
import struct
from pathlib import Path
from collections.abc import Mapping
from civ6_host.runtime.native.native_application_mirror_records import bounded_get_player_config
from civ6_host.runtime.native.native_application_mirror_records import verify_source as verify_record_source
from civ6_host.runtime.native.native_application_mirror_records import PROOF_SHA256 as RECORD_ALIAS_PROOF_SHA256
from civ6_host.runtime.native.native_source_cache import load_pinned_json
from civ6_host.runtime.native.native_game_configuration import game_configuration_hash
from civ6_host.runtime.native.native_application_mirror import decode_scalar
from civ6_host.runtime.native.native_host_events import copy_eight_byte_variant
EVENT_KIND = 4200272217
EXE_SHA256 = 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63'
CORE_SHA256 = 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'
PINNED_EVIDENCE_SHA256 = 'e1816d452f11c2a1c85d26d14252cf99adbceaafd54d7a0b6500c0da2bf0b026'
EVIDENCE_SCHEMA = 'civ6rl.native_event_fa5b1159_query.v1'
QUERY_SOURCE_PROOF_SHA256 = '12a617afcb217a89b879b380c3e91a59d39f49e2710b94877bcd3992079de4e2'
_ROOT = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_event_fa5b1159.py')))).resolve().parents[1]
OUTER_VTABLE = 7987232
OUTER_ENTITY_SLOT, OUTER_ENTITY_GET = (184, 4382880)
OUTER_PAIR_SLOT, OUTER_PAIR_GET = (256, 4382336)
ENTITY_VTABLE = 7992320
ENTITY_RELEASE_SLOT, ENTITY_RELEASE = (8, 4421040)
ENTITY_VALUE_SLOT, ENTITY_VALUE = (24, 4422464)
PAIR_PRIMARY_VTABLE = 7988512
PAIR_SECONDARY_VTABLE = 7989976
PAIR_RELEASE_SLOT, PAIR_RELEASE = (8, 4388560)
PAIR_INDEX_SLOT, PAIR_INDEX_QUERY = (200, 4395200)
PLAYER_CONFIG_VTABLE = 8507296
PLAYER_CONFIG_GET_SLOT, PLAYER_CONFIG_GET = (104, 7626176)
PLAYER_CONFIG_ABSENT_VALUE = 9176984
CONFIG_DWORD_TAG_MASK = 3145774
CIVILIZATION_TYPE_ID = 'CIVILIZATION_TYPE_ID'
CIVILIZATION_TYPE_ID_HASH = 3352777051
DESCRIPTOR_KEY = 594779970
POSITION_KEY = 2353434172
SELECTOR_KEY = 2716180809
RECORD_TYPE = 87
RECORD_SIZE = 128
DESCRIPTOR_DEFAULT_WORD = 2
CALLBACK_RVA = 1314800
WRITER_RVA = 1240352
NORMALIZER_RVA = 1876688

def verify_source_evidence() -> None:
    if not PINNED_EVIDENCE_SHA256:
        raise RuntimeError('FA5B1159 source proof is not pinned')
    path = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_event_fa5b1159.py')))).resolve().parents[1] / 'evidence' / 'native-event-fa5b1159-query' / f'{PINNED_EVIDENCE_SHA256}.json'
    raw = _resolve_resource_path(path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != PINNED_EVIDENCE_SHA256:
        raise RuntimeError('Pinned FA5B1159 query proof bytes changed')
    doc = json.loads(raw)
    if doc.get('schema') != EVIDENCE_SCHEMA or doc.get('images', {}).get('exe_sha256') != EXE_SHA256 or doc.get('images', {}).get('core_sha256') != CORE_SHA256 or (doc.get('registration', {}).get('kind') != '0xfa5b1159') or (doc.get('registration', {}).get('callback_va') != '0x140140ff0'):
        raise RuntimeError('Pinned FA5B1159 evidence identity changed')
    queries = load_pinned_json(_ROOT / 'evidence/native-event-2b1ba0f8' / f'{QUERY_SOURCE_PROOF_SHA256}.json', QUERY_SOURCE_PROOF_SHA256)
    records = verify_record_source()

    def instructions(body):
        result = {}

        def visit(value):
            if isinstance(value, Mapping):
                if 'va' in value and 'text' in value:
                    result[value['va']] = value['text']
                for child in value.values():
                    visit(child)
            elif isinstance(value, (list, tuple)):
                for child in value:
                    visit(child)
        visit(body)
        return result
    q1 = instructions(queries['captures']['query_helper_147940'])
    q3 = instructions(queries['captures']['config_key_helper'])
    alias = instructions(records['exe_functions']['application_record_initialize'])
    getter = instructions(doc['captures']['core_leaf_windows']['player_config_value_getter'])
    checks = ((q1, {'0x140147966': 'je 0x1401479ce', '0x140147987': 'je 0x1401479ce', '0x1401479a6': 'je 0x1401479ce', '0x1401479d3': 'or eax, 0xffffffff', '0x1401479a0': 'call qword ptr [rax + 8]', '0x1401479ae': 'call qword ptr [rax + 0x20]', '0x1401479b9': 'call qword ptr [rdx + 8]'}), (q3, {'0x140114d24': 'mov rcx, qword ptr [rcx + 0x18]', '0x140114d31': 'call qword ptr [rax + 0x68]', '0x140114d37': 'shr ecx, 0x1d', '0x140114d3a': 'test cl, 1', '0x140114d3d': 'jne 0x140114d5a', '0x140114d3f': 'movzx ecx, word ptr [rax]', '0x140114d42': 'cmp cx, 0x15', '0x140114d46': 'ja 0x140114d5a', '0x140114d48': 'mov edx, 0x30002e', '0x140114d4d': 'bt edx, ecx', '0x140114d50': 'jae 0x140114d5a', '0x140114d52': 'mov eax, dword ptr [rax + 8]'}), (alias, {'0x140115701': 'mov rcx, qword ptr [r8]', '0x140115715': 'call qword ptr [rax + 0x58]', '0x14011577b': 'cmp word ptr [rax], 0xa', '0x140115781': 'mov rbx, qword ptr [rax + 8]', '0x140115789': 'mov qword ptr [rdi + 0x18], rbx'}), (getter, {'0x180745dff': 'jne 0x180745e08', '0x180745e01': 'lea rax, [rip + 0x17a990]'}))
    if any((body.get(va) != text for body, required in checks for va, text in required.items())):
        raise RuntimeError('FA5 query, null sentinel, or provider child-map alias source differs')

def _checked_reader(read):

    def exact(address, size):
        raw = read(address, size)
        if type(raw) is not bytes or len(raw) != size:
            raise ValueError(f'FA5 incomplete native copy at {address:#x} size {size}')
        return raw
    return exact

def _slot(read, base: int, table: int, offset: int, target: int) -> int:
    vtable = base + table
    actual = int.from_bytes(read(vtable + offset, 8), 'little')
    expected = base + target
    if actual != expected:
        raise ValueError(f'Unexpected Core vtable slot {table:#x}+{offset:#x}')
    return actual

def _check_object(read, base: int, pointer: int, table: int, label: str) -> None:
    if not pointer or int.from_bytes(read(pointer, 8), 'little') != base + table:
        raise ValueError(f'Unexpected Core {label} interface')

def query_secondary_value(core, context: int, first_result: int, *, read=None, native_api=None, core_sha256='d7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3') -> int:
    """Run the callback's second query using checked Core interfaces.

    `first_result` is the signed int32 returned by query1. The injected API is
    only a test seam; callers must not use it to replace the native Core
    operation. The native path uses exact source-resolved methods and releases
    the pair object before the entity wrapper, matching the EXE.
    """
    OUTER_VTABLE = globals()['OUTER_VTABLE']
    OUTER_ENTITY_GET = globals()['OUTER_ENTITY_GET']
    OUTER_PAIR_GET = globals()['OUTER_PAIR_GET']
    ENTITY_VTABLE = globals()['ENTITY_VTABLE']
    ENTITY_RELEASE = globals()['ENTITY_RELEASE']
    ENTITY_VALUE = globals()['ENTITY_VALUE']
    PAIR_PRIMARY_VTABLE = globals()['PAIR_PRIMARY_VTABLE']
    PAIR_RELEASE = globals()['PAIR_RELEASE']
    PAIR_INDEX_QUERY = globals()['PAIR_INDEX_QUERY']
    PAIR_SECONDARY_VTABLE = globals()['PAIR_SECONDARY_VTABLE']
    if core_sha256 != 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3':
        from civ6_host.runtime.foundation_facade_profiles import query_abi
        from civ6_host.runtime.provenance import resource_root
        _foundation_abi = query_abi(core_sha256, resource_root())
        OUTER_VTABLE = _foundation_abi.table('outer')
        OUTER_ENTITY_GET = _foundation_abi.rva('get_player')
        OUTER_PAIR_GET = _foundation_abi.rva('outer_service')
        ENTITY_VTABLE = _foundation_abi.table('player')
        ENTITY_RELEASE = _foundation_abi.rva('release_player')
        ENTITY_VALUE = _foundation_abi.rva('player_type')
        PAIR_PRIMARY_VTABLE = _foundation_abi.table('type_service')
        PAIR_RELEASE = _foundation_abi.rva('release_service')
        PAIR_INDEX_QUERY = _foundation_abi.rva('service_player_type_hash')
        PAIR_SECONDARY_VTABLE = _foundation_abi.service_secondary_vtable
    verify_source_evidence()
    if isinstance(first_result, bool) or type(first_result) is not int or (not -(1 << 31) <= first_result < 1 << 31):
        raise ValueError('first_result must be a signed native int32')
    if first_result == -1:
        return -1
    if not isinstance(context, int) or isinstance(context, bool) or context <= 0:
        raise ValueError('A live Core outer context is required')
    base = int(core._handle)
    if base <= 0:
        raise ValueError('Invalid GameCore image base')
    if read is None:
        from civ6_host.runtime.native.native_setup import local_reader
        read = local_reader()
    read = _checked_reader(read)
    _check_object(read, base, context, OUTER_VTABLE, 'outer context')
    _slot(read, base, OUTER_VTABLE, OUTER_ENTITY_SLOT, OUTER_ENTITY_GET)
    _slot(read, base, OUTER_VTABLE, OUTER_PAIR_SLOT, OUTER_PAIR_GET)
    _slot(read, base, ENTITY_VTABLE, ENTITY_RELEASE_SLOT, ENTITY_RELEASE)
    _slot(read, base, ENTITY_VTABLE, ENTITY_VALUE_SLOT, ENTITY_VALUE)
    _slot(read, base, PAIR_PRIMARY_VTABLE, PAIR_RELEASE_SLOT, PAIR_RELEASE)
    _slot(read, base, PAIR_PRIMARY_VTABLE, PAIR_INDEX_SLOT, PAIR_INDEX_QUERY)
    if native_api is None:
        get_entity = C.WINFUNCTYPE(C.c_void_p, C.c_void_p, C.c_int32)(base + OUTER_ENTITY_GET)
        create_pair = C.WINFUNCTYPE(C.c_void_p, C.c_void_p)(base + OUTER_PAIR_GET)
        release_entity = C.WINFUNCTYPE(None, C.c_void_p)(base + ENTITY_RELEASE)
        get_entity_value = C.WINFUNCTYPE(C.c_int32, C.c_void_p)(base + ENTITY_VALUE)
        release_pair = C.WINFUNCTYPE(None, C.c_void_p)(base + PAIR_RELEASE)
        get_indexed_value = C.WINFUNCTYPE(C.c_int32, C.c_void_p, C.c_int32)(base + PAIR_INDEX_QUERY)
    else:
        expected = {'get_entity', 'create_pair', 'release_entity', 'get_entity_value', 'release_pair', 'get_indexed_value'}
        if not isinstance(native_api, dict) or set(native_api) != expected:
            raise ValueError('FA5B1159 test seam must provide the exact six query operations')
        get_entity = native_api['get_entity']
        create_pair = native_api['create_pair']
        release_entity = native_api['release_entity']
        get_entity_value = native_api['get_entity_value']
        release_pair = native_api['release_pair']
        get_indexed_value = native_api['get_indexed_value']
    entity = get_entity(context, first_result)
    if not entity:
        return -1
    entity_validated = False
    pair = 0
    pair_validated = False
    try:
        _check_object(read, base, int(entity), ENTITY_VTABLE, 'entity wrapper')
        entity_validated = True
        pair = create_pair(context)
        if not pair:
            raise RuntimeError('Core pair factory returned null before an unguarded EXE dereference')
        _check_object(read, base, int(pair), PAIR_PRIMARY_VTABLE, 'pair primary')
        if PAIR_SECONDARY_VTABLE is not None and int.from_bytes(read(pair + 8, 8), 'little') != base + PAIR_SECONDARY_VTABLE:
            raise ValueError('Unexpected Core pair secondary interface')
        pair_validated = True
        entity_value = get_entity_value(entity)
        if type(entity_value) is not int or not -(1 << 31) <= entity_value < 1 << 31:
            raise ValueError('Core entity query returned a non-int32 result')
        value = get_indexed_value(pair, entity_value)
        if isinstance(value, bool) or type(value) is not int or (not -(1 << 31) <= value < 1 << 31):
            raise ValueError('Core indexed query returned a non-int32 result')
        return value
    finally:
        try:
            if pair_validated:
                release_pair(pair)
        finally:
            if entity_validated:
                release_entity(entity)

def read_player_civilization_type_id(core, context: int, player_index: int, *, expected_hash: int | None=None, read=None, record_lookup=None, value_lookup=None, key_hash=None, core_sha256='d7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3') -> int:
    """Read the application's existing child when the separate provider is bound.

    The old Core-only route remains a bounded diagnostic fallback. It is not
    equivalent to the separate source provider retained by the original EXE.
    expected_hash is a check, never a replacement for a native query result.
    """
    if core_sha256 not in ('d7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3', '259b90a473a256aff6a7d621a4f3717e46f6921c59b9817475375c88b97e8c83', '324c51e9ea3531758842e16c69e6cddbefbb226c5b675c3d6e60111646c2e98c'):
        raise ValueError('Unqualified facade engine')
    verify_source_evidence()
    base = int(core._handle)
    if base <= 0 or not isinstance(context, int) or isinstance(context, bool) or (context <= 0):
        raise ValueError('A live Core context is required')
    if type(player_index) is not int or not 0 <= player_index < 64:
        raise ValueError('FA5 civilization lookup requires an existing setup record 0..63')
    if expected_hash is not None and (type(expected_hash) is not int or isinstance(expected_hash, bool) or (not 0 <= expected_hash <= 4294967295)):
        raise ValueError('expected_hash must be a uint32 hash')
    application = getattr(core, '_civ6rl_application_configuration', None)
    if application is not None:
        application.require_context(base, context)
        if any((seam is not None for seam in (record_lookup, value_lookup, key_hash))):
            raise ValueError('Application provider queries cannot mix Core-only test seams')
        from civ6_host.runtime.native.native_application_property_copy import read_civilization_result
        return read_civilization_result(application, player_index, expected_hash=expected_hash, core_sha256=core_sha256)
    if core_sha256 != 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3':
        raise ValueError('XP1 civilization query requires its bound application configuration')
    if read is None:
        from civ6_host.runtime.native.native_setup import local_reader
        read = local_reader()
    read = _checked_reader(read)
    key_hash = game_configuration_hash if key_hash is None else key_hash
    key = key_hash(CIVILIZATION_TYPE_ID)
    if type(key) is not int or not 0 <= key <= 4294967295:
        raise ValueError('CIVILIZATION_TYPE_ID key hash is not a uint32')
    if key != CIVILIZATION_TYPE_ID_HASH:
        raise ValueError('CIVILIZATION_TYPE_ID hash differs from pinned EXE initializer')
    record = bounded_get_player_config(base, context, player_index, read=read, lookup=record_lookup)
    config = int(record['pointer'])
    _check_object(read, base, config, PLAYER_CONFIG_VTABLE, 'player configuration')
    getter = _slot(read, base, PLAYER_CONFIG_VTABLE, PLAYER_CONFIG_GET_SLOT, PLAYER_CONFIG_GET)
    if value_lookup is None:
        value_lookup = C.WINFUNCTYPE(C.c_void_p, C.c_void_p, C.c_uint32)(getter)
    value_pointer = value_lookup(config, key)
    if not value_pointer or value_pointer == base + PLAYER_CONFIG_ABSENT_VALUE:
        raise LookupError('CIVILIZATION_TYPE_ID is absent from the configured player record')
    raw = read(int(value_pointer), 24)
    tag = int.from_bytes(raw[0:2], 'little')
    value = int.from_bytes(raw[8:12], 'little')
    flags = int.from_bytes(raw[20:24], 'little')
    if flags & 1 << 29 or tag > 21 or (not CONFIG_DWORD_TAG_MASK & 1 << tag):
        raise ValueError(f'CIVILIZATION_TYPE_ID outside native scalar identity profile: player={player_index}, tag={tag}, flags={flags:#x}, raw_variant={raw.hex()}, source_fallback_zero=True')
    if expected_hash is not None and value != expected_hash:
        raise ValueError('Native civilization ID differs from the host-configured identity')
    if value_lookup(config, key) != value_pointer or read(int(value_pointer), 24) != raw:
        raise ValueError('CIVILIZATION_TYPE_ID changed during its native read')
    after = bounded_get_player_config(base, context, player_index, read=read, lookup=record_lookup)
    if after != record:
        raise ValueError('CIVILIZATION_TYPE_ID setup record changed during its native read')
    _check_object(read, base, config, PLAYER_CONFIG_VTABLE, 'player configuration')
    _slot(read, base, PLAYER_CONFIG_VTABLE, PLAYER_CONFIG_GET_SLOT, PLAYER_CONFIG_GET)
    return value

class EventFields:
    __slots__ = ('descriptor_bytes', 'descriptor_word', 'descriptor_dword', 'position_bytes', 'x', 'y', 'selector')

    def __init__(self, descriptor_bytes: bytes, descriptor_word: int, descriptor_dword: int, position_bytes: bytes, x: int, y: int, selector: int):
        self.descriptor_bytes = descriptor_bytes
        self.descriptor_word = descriptor_word
        self.descriptor_dword = descriptor_dword
        self.position_bytes = position_bytes
        self.x, self.y = (x, y)
        self.selector = selector

def decode_fields(fields: dict[int, bytes], read) -> EventFields:
    """Decode the exact three input keys in the refused FA5B prefix116 event."""
    verify_source_evidence()
    if not isinstance(fields, dict) or set(fields) != {DESCRIPTOR_KEY, POSITION_KEY, SELECTOR_KEY}:
        raise ValueError('FA5B1159 requires exactly descriptor, position, and A1E5 fields')
    selector = decode_scalar(fields[SELECTOR_KEY], 3)
    descriptor = copy_eight_byte_variant(fields[DESCRIPTOR_KEY], read, expected_tag=1024)
    position = copy_eight_byte_variant(fields[POSITION_KEY], read, expected_tag=0)
    descriptor_word = struct.unpack_from('<H', descriptor, 0)[0]
    descriptor_dword = struct.unpack_from('<I', descriptor, 4)[0]
    x, y = struct.unpack('<ii', position)
    return EventFields(descriptor, descriptor_word, descriptor_dword, position, x, y, selector)

def _query_plot_owner(core, context, fields, *, read, native_api=None, core_sha256='d7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'):
    """EXE147940, including its source-proven null map/plot -> -1 exits.

    The outer context is borrowed from the caller. The created map is
    released before plot+20; the retained plot is released before returning.
    """
    if core_sha256 not in ('d7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3', '259b90a473a256aff6a7d621a4f3717e46f6921c59b9817475375c88b97e8c83', '324c51e9ea3531758842e16c69e6cddbefbb226c5b675c3d6e60111646c2e98c'):
        raise ValueError('Unqualified facade engine')
    from civ6_host.runtime.foundation_facade_profiles import query_abi, verify_xp1_once, select_tables
    from civ6_host.runtime.provenance import resource_root
    _foundation_abi = query_abi(core_sha256, None if core_sha256 == 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3' else resource_root())
    from civ6_host.runtime.native import native_event_f4fe1b62 as plot
    base = int(core._handle)
    if type(context) is not int or context <= 0 or base <= 0:
        raise ValueError('FA5 requires a live Core context')
    if type(fields.position_bytes) is not bytes or len(fields.position_bytes) != 8 or type(fields.x) is not int or (type(fields.y) is not int) or (struct.unpack('<ii', fields.position_bytes) != (fields.x, fields.y)):
        raise ValueError('FA5 native position bytes and coordinates disagree')
    _check_object(read, base, context, _foundation_abi.table('outer'), 'outer context')
    for table, offset, target in ((_foundation_abi.table('outer'), _foundation_abi.slot('outer_map'), _foundation_abi.rva('outer_map')), (_foundation_abi.table('map'), _foundation_abi.slot('release_map'), _foundation_abi.rva('release_map')), (_foundation_abi.table('map'), _foundation_abi.slot('get_plot'), _foundation_abi.rva('get_plot')), (_foundation_abi.table('plot'), _foundation_abi.slot('release_plot'), _foundation_abi.rva('release_plot')), (_foundation_abi.table('plot'), _foundation_abi.slot('plot_owner'), _foundation_abi.rva('plot_owner'))):
        _slot(read, base, table, offset, target)
    if native_api is None:
        outer_map = C.WINFUNCTYPE(C.c_void_p, C.c_void_p)(base + _foundation_abi.rva('outer_map'))
        release_map = C.WINFUNCTYPE(None, C.c_void_p)(base + _foundation_abi.rva('release_map'))
        get_plot = C.WINFUNCTYPE(C.c_void_p, C.c_void_p, C.c_int32, C.c_int32)(base + _foundation_abi.rva('get_plot'))
        release_plot = C.WINFUNCTYPE(None, C.c_void_p)(base + _foundation_abi.rva('release_plot'))
        get_value = C.WINFUNCTYPE(C.c_int32, C.c_void_p)(base + _foundation_abi.rva('plot_owner'))
    else:
        required = {'outer_map', 'release_map', 'get_plot', 'release_plot', 'get_value'}
        if not isinstance(native_api, dict) or set(native_api) != required:
            raise ValueError('FA5 plot test seam requires the five exact native operations')
        outer_map, release_map, get_plot, release_plot, get_value = (native_api[name] for name in ('outer_map', 'release_map', 'get_plot', 'release_plot', 'get_value'))
    map_obj = outer_map(context)
    if not map_obj:
        return -1
    _check_object(read, base, map_obj, _foundation_abi.table('map'), 'map')
    plot_obj, plot_validated = (None, False)
    try:
        try:
            plot_obj = get_plot(map_obj, fields.x, fields.y)
            if plot_obj:
                _check_object(read, base, plot_obj, _foundation_abi.table('plot'), 'plot')
                plot_validated = True
        finally:
            release_map(map_obj)
        if not plot_obj:
            return -1
        value = get_value(plot_obj)
        if type(value) is not int or not -(1 << 31) <= value < 1 << 31:
            raise ValueError('FA5 native plot query did not return int32')
        return value
    finally:
        if plot_validated:
            release_plot(plot_obj)

def query_callback_values(core, context: int, fields: EventFields, *, expected_civilization_hash: int | None=None, expected_civilization_hashes: Mapping[int, int] | None=None, read=None, query1_api=None, query2_api=None, config_record_lookup=None, config_value_lookup=None, key_hash=None, core_sha256='d7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3') -> tuple[int, int, int]:
    """Run all three source queries using the native plot owner's setup map.

    Optional expected identities are checks only. A mapping is indexed by
    query1's result, never the descriptor owner; missing map entries mean no
    expected-value check, not a fabricated civilization identity. Query3 still
    requires a present typed cell from a validated existing record 0..63.
    """
    if core_sha256 not in ('d7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3', '259b90a473a256aff6a7d621a4f3717e46f6921c59b9817475375c88b97e8c83', '324c51e9ea3531758842e16c69e6cddbefbb226c5b675c3d6e60111646c2e98c'):
        raise ValueError('Unqualified facade engine')
    verify_source_evidence()
    if not isinstance(fields, EventFields):
        raise TypeError('fields must be decoded FA5B1159 EventFields')
    if expected_civilization_hash is not None and (type(expected_civilization_hash) is not int or not 0 <= expected_civilization_hash <= 4294967295):
        raise ValueError('A configured uint32 civilization identity hash is required')
    if expected_civilization_hashes is not None:
        if expected_civilization_hash is not None or not isinstance(expected_civilization_hashes, Mapping) or any((type(k) is not int or not 0 <= k < 64 or type(v) is not int or (not 0 <= v <= 4294967295) for k, v in expected_civilization_hashes.items())):
            raise ValueError('FA5 expected civilization mapping must contain only record indices and uint32 hashes')
        expected_civilization_hashes = dict(expected_civilization_hashes)
    if read is None:
        from civ6_host.runtime.native.native_setup import local_reader
        read = local_reader()
    read = _checked_reader(read)
    first_result = _query_plot_owner(core, context, fields, read=read, native_api=query1_api, core_sha256=core_sha256)
    second = query_secondary_value(core, context, first_result, read=read, native_api=query2_api, core_sha256=core_sha256)
    expected = expected_civilization_hashes.get(first_result) if expected_civilization_hashes is not None else expected_civilization_hash
    third = -1 if first_result == -1 else read_player_civilization_type_id(core, context, first_result, expected_hash=expected, read=read, record_lookup=config_record_lookup, value_lookup=config_value_lookup, key_hash=key_hash, core_sha256=core_sha256)
    return (first_result, second, third)

def encode_record(sequence: int, fields: EventFields, *, plot_value: int, secondary_value: int, civilization_id: int, queue_metadata_service_present: bool, producer_hook_present: bool, padding_policy: str) -> bytes:
    """Encode source-initialized type-0x57 record with explicit stack padding.

    The native callback copies 0x30 bytes from its stack; bytes +4..+7 and
    +0x24..+0x2f are not initialized by that callback. The named policy makes
    those bytes deterministic for diagnostics, without claiming native-stack
    equivalence. The queue metadata callback and per-thread hook remain refused.
    """
    verify_source_evidence()
    if type(sequence) is not int or not 1 <= sequence <= 4294967295:
        raise ValueError('sequence must be a nonzero uint32')
    if not isinstance(fields, EventFields):
        raise TypeError('fields must be decoded FA5B1159 EventFields')
    for label, value in (('plot_value', plot_value), ('secondary_value', secondary_value), ('civilization_id', civilization_id)):
        if type(value) is not int or not -(1 << 31) <= value <= 4294967295:
            raise ValueError(f'{label} must fit the source DWORD payload')
    if queue_metadata_service_present is not False or producer_hook_present is not False:
        raise ValueError('FA5B1159 queue metadata service and per-thread hook are not modeled')
    if padding_policy != 'headless-zero-uninitialized-callback-stack':
        raise ValueError('Explicit deterministic policy for uninitialized callback stack bytes is required')
    if len(fields.descriptor_bytes) != 8 or struct.unpack_from('<H', fields.descriptor_bytes)[0] != fields.descriptor_word or struct.unpack_from('<I', fields.descriptor_bytes, 4)[0] != fields.descriptor_dword or (not 0 <= fields.selector <= 4294967295) or (len(fields.position_bytes) != 8) or (struct.unpack('<ii', fields.position_bytes) != (fields.x, fields.y)):
        raise ValueError('Decoded FA5B1159 field bytes and values disagree')
    record = bytearray(RECORD_SIZE)
    struct.pack_into('<IIHHI', record, 16, 4294967295, 4294967295, 65535, 0, 4294967295)
    struct.pack_into('<HHI', record, 32, 65535, 0, 4294967295)
    struct.pack_into('<HHI', record, 40, 65535, 0, 4294967295)
    struct.pack_into('<HHI', record, 48, 65535, 0, 4294967295)
    struct.pack_into('<HHI', record, 56, 65535, 0, 4294967295)
    struct.pack_into('<Q', record, 64, 0)
    struct.pack_into('<I', record, 72, 0)
    payload = bytearray(48)
    struct.pack_into('<HHI', payload, 8, fields.descriptor_word, DESCRIPTOR_DEFAULT_WORD, fields.descriptor_dword)
    payload[16:24] = fields.position_bytes
    struct.pack_into('<III', payload, 24, plot_value & 4294967295, secondary_value & 4294967295, civilization_id & 4294967295)
    struct.pack_into('<IIII', record, 0, RECORD_SIZE, RECORD_TYPE, sequence, 0)
    record[80:128] = payload
    struct.pack_into('<I', record, 80, sequence)
    return bytes(record)
