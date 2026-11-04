"""Bounded read-only AUX+A8 snapshot and transport; does not execute Lua.

Only source-decoded tree maps and value types are admitted. The caller must
apply the validated transport to the *supplied* live HKS state in protected C,
preserving its existing stack and adding exactly one table. No gameplay values
are predicted and no native map is modified or released by this module.
"""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
from dataclasses import dataclass
import math
from pathlib import Path
import struct
from civ6_host.runtime.native.native_source_cache import load_pinned_json
_ROOT = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_aux_map_conversion.py')))).resolve().parents[1]
PROOF_SHA256 = '8aedcab5c742d8b142e760e76ce6d079296d7ad12ec80cf045f89091c7e4dfb1'
_PROOF = _ROOT / 'evidence/native-aux-map-conversion' / (PROOF_SHA256 + '.json')
LIST_PROOF_SHA256 = '0c9f0be72fab4e7d2c41db24c1d2f8383162f1ca8b07e04bf4144586e4ac8d3c'
_LIST_PROOF = _ROOT / 'evidence/native-aux-variant-list' / (LIST_PROOF_SHA256 + '.json')
STRING_PROOF_SHA256 = 'a48899a24eebf35606fb66d0e0e0f071308c089702a15626344b3f225f0a1600'
_STRING_PROOF = _ROOT / 'evidence/native-aux-byte-string' / (STRING_PROOF_SHA256 + '.json')
ARRAY_PROOF_SHA256 = 'eed3ff23101ec0f32754316e9a7ae785c8f46fa00f529f41efcdb96aa6c18660'
_ARRAY_PROOF = _ROOT / 'evidence/native-aux-typed-array' / (ARRAY_PROOF_SHA256 + '.json')
STRING_KEYS_PROOF_SHA256 = 'c0888f43478742bf6caf7d6bd0d48b80b5cd6a89ac3875c9226934e020c53c9d'
STRING_KEYS_PROOF = _ROOT / 'evidence/native-aux-string-keys' / (STRING_KEYS_PROOF_SHA256 + '.json')
TABLE, NUMBER, BOOLEAN, STRING_CONST, RAWSET, RAWSETI = range(1, 7)
STRING_BYTES = 7
NIL = 8
DESCRIPTOR_KEYS = (b'player', b'type', b'id')
MAX_FIELDS = 4096
MAX_ELEMENTS = 65536
MAX_OPS = 262144
MAX_READ_BYTES = 8 * 1024 * 1024
MAX_LIST_DEPTH = 8
MAX_STRING_BYTES = 65536
MAX_TOTAL_STRING_BYTES = 1024 * 1024
_OP = struct.Struct('<IIQ')
_VT_RVA = 8507296
_SLOTS = {8: 3008592, 96: 7625984, 112: 7626256, 472: 422768}
RESERVED_ARRAY_KEY = 583956078

def verify_source_evidence():
    proof = load_pinned_json(_PROOF, PROOF_SHA256)
    if proof.get('schema') != 'civ6rl.native_aux_map_conversion.static.v1' or proof['images']['core_sha256'] != 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3' or proof['images']['exe_sha256'] != 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63' or (proof['core_tree_vtable']['va'] != '0x18081cfa0'):
        raise RuntimeError('AUX+A8 source identity changed')
    lists = load_pinned_json(_LIST_PROOF, LIST_PROOF_SHA256)
    if lists.get('schema') != 'civ6rl.native_aux_variant_list.static.v1' or lists['parent']['sha256'] != PROOF_SHA256 or lists['images'] != proof['images'] or (lists['captures']['variant_list_to_table']['start_va'] != '0x140db6280') or (lists['contract']['element_stride'] != 24):
        raise RuntimeError('AUX+A8 Variant-list source identity changed')
    strings = load_pinned_json(_STRING_PROOF, STRING_PROOF_SHA256)
    if strings.get('schema') != 'civ6rl.native_aux_byte_string.static.v1' or strings['parent']['sha256'] != PROOF_SHA256 or strings['images'] != proof['images'] or (strings['contract']['tag'] != 5) or (strings['contract']['required_array_flag_bit'] != 29):
        raise RuntimeError('AUX+A8 byte-string source identity changed')
    arrays = load_pinned_json(_ARRAY_PROOF, ARRAY_PROOF_SHA256)
    if arrays.get('schema') != 'civ6rl.native_aux_typed_array.static.v1' or arrays['parent']['sha256'] != PROOF_SHA256 or arrays['images'] != proof['images'] or (tuple(arrays['contract']['numeric_tags']) != (1, 2, 3, 4)) or (tuple(arrays['contract']['descriptor_tags']) != (1024, 1025)) or (arrays['contract']['count_offset'] != 20) or (arrays['contract']['count_mask'] != 16777215) or (arrays['contract']['ignored_size_offset'] != 16):
        raise RuntimeError('AUX+A8 typed-array source identity changed')
    return proof

@dataclass(frozen=True)
class MapSnapshot:
    transport: bytes
    field_count: int
    source_bytes_read: int
    variant_types: tuple[tuple[int, int, int], ...]

    @property
    def operation_count(self):
        return len(self.transport) // _OP.size

def validate_transport(transport: bytes) -> int:
    """Validate the complete stack program before any HKS mutation.

    Returns maximum added stack slots. C must independently make the same
    checks on the bytes crossing its ABI boundary before calling HKS.
    """
    if type(transport) is not bytes or not transport or len(transport) % 16 or (len(transport) // 16 > MAX_OPS):
        raise ValueError('Invalid AUX+A8 transport length')
    stack = []
    peak = 0
    offset = 0
    string_bytes = 0
    while offset < len(transport):
        opcode, arg, payload = _OP.unpack_from(transport, offset)
        offset += _OP.size
        if opcode == TABLE:
            if arg > MAX_ELEMENTS or payload > MAX_FIELDS:
                raise ValueError('AUX+A8 table allocation hint exceeds bounds')
            stack.append('table')
        elif opcode == NUMBER:
            if arg or not math.isfinite(struct.unpack('<d', struct.pack('<Q', payload))[0]):
                raise ValueError('Invalid AUX+A8 numeric transport')
            stack.append('number')
        elif opcode == BOOLEAN:
            if arg > 255 or payload:
                raise ValueError('Invalid AUX+A8 boolean transport')
            stack.append('boolean')
        elif opcode == STRING_CONST:
            if arg >= len(DESCRIPTOR_KEYS) or payload:
                raise ValueError('Invalid AUX+A8 source string')
            stack.append('string')
        elif opcode == STRING_BYTES:
            if payload or arg > MAX_STRING_BYTES:
                raise ValueError('Invalid AUX+A8 byte-string header')
            size = (arg + 1 + 15) // 16 * 16
            if offset + size > len(transport):
                raise ValueError('Incomplete AUX+A8 byte-string records')
            raw = transport[offset:offset + size]
            if b'\x00' in raw[:arg] or raw[arg] != 0 or any(raw[arg + 1:]):
                raise ValueError('Invalid AUX+A8 byte-string terminator/padding')
            string_bytes += arg
            if string_bytes > MAX_TOTAL_STRING_BYTES:
                raise ValueError('AUX+A8 total byte-string budget exceeded')
            offset += size
            stack.append('string')
        elif opcode == RAWSET:
            if arg or payload or len(stack) < 3 or (stack[-3] != 'table') or (stack[-2] not in ('number', 'string')):
                raise ValueError('Invalid AUX+A8 rawset stack')
            del stack[-2:]
        elif opcode == NIL:
            if arg or payload:
                raise ValueError('Invalid AUX map nil transport')
            stack.append('nil')
        elif opcode == RAWSETI:
            if not 1 <= arg <= MAX_ELEMENTS or payload or len(stack) < 2 or (stack[-2] != 'table'):
                raise ValueError('Invalid AUX+A8 rawseti stack')
            stack.pop()
        else:
            raise ValueError('Unknown AUX+A8 transport opcode')
        peak = max(peak, len(stack))
        if peak > 16:
            raise ValueError('AUX+A8 transport stack bound exceeded')
    if stack != ['table']:
        raise ValueError('AUX+A8 transport must produce exactly one table')
    return peak


def encode_script_request_table(parameters: dict) -> bytes:
    """Encode a bounded Lua object for the protected native table writer.

    Integer keys and values use signed int32 Lua numbers. Byte strings preserve
    the bytes used by Lua and the native name resolver. Lists and other Lua
    types require their own source-qualified conversion.
    """
    wire = bytearray()
    active = set()
    fields = string_bytes = 0

    def op(kind, arg=0, payload=0):
        if len(wire) // _OP.size >= MAX_OPS:
            raise ValueError('Script request transport operation budget exceeded')
        wire.extend(_OP.pack(kind, arg, payload))

    def scalar(value, *, key=False):
        nonlocal string_bytes
        if type(value) is bytes:
            size = len(value)
            if (not size and key or size > MAX_STRING_BYTES or b'\x00' in value
                    or size > MAX_TOTAL_STRING_BYTES - string_bytes):
                raise ValueError('Invalid script request byte string')
            string_bytes += size
            padded_size = (size // _OP.size + 1) * _OP.size
            if len(wire) + _OP.size + padded_size > MAX_OPS * _OP.size:
                raise ValueError('Script request transport operation budget exceeded')
            op(STRING_BYTES, size)
            wire.extend(value)
            wire.extend(bytes(padded_size - size))
        elif type(value) is int and -(1 << 31) <= value < (1 << 31):
            op(NUMBER, payload=struct.unpack('<Q', struct.pack('<d', value))[0])
        elif not key and type(value) is bool:
            op(BOOLEAN, int(value))
        else:
            raise ValueError('Unsupported script request table key or value')

    def table(value, depth):
        nonlocal fields
        if (depth > MAX_LIST_DEPTH or id(value) in active
                or len(value) > MAX_FIELDS - fields):
            raise ValueError('Script request table exceeds bounds or is cyclic')
        fields += len(value)
        active.add(id(value))
        op(TABLE, payload=len(value))
        for key, item in value.items():
            scalar(key, key=True)
            if type(item) is dict:
                table(item, depth + 1)
            else:
                scalar(item)
            op(RAWSET)
        active.remove(id(value))

    if type(parameters) is not dict:
        raise ValueError('Script request parameters must be an exact dictionary')
    table(parameters, 0)
    result = bytes(wire)
    validate_transport(result)
    return result


def snapshot_parameter_map(core_base: int, map_pointer: int, read, *, use_string_keys: bool, core_sha256='d7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3', transport_version=1, allow_nested_maps=False, native_copy_budget=False, xp2_operation_vector=False) -> MapSnapshot:
    """Copy a borrowed native tree map to a fully validated HKS stack program.

    `read(address,size)` must perform checked native memory reads. All reads,
    shape/type/budget checks finish before transport is returned. No native
    function is called; ASLR is supported through the supplied image base.
    """
    verify_source_evidence()
    from civ6_host.runtime.aux_map_profiles import profile_for_sha
    map_abi = profile_for_sha(core_sha256)
    if type(transport_version) is not int or transport_version not in (1, 2):
        raise ValueError('Unknown AUX map transport version')
    if transport_version == 2:
        from civ6_host.runtime.configuration_lua_source import source
        source()
    if type(use_string_keys) is not bool:
        raise ValueError('AUX+A8 key selector requires an exact Boolean')
    if use_string_keys and core_sha256 == 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3':
        proof = load_pinned_json(STRING_KEYS_PROOF, STRING_KEYS_PROOF_SHA256)
        if proof.get('schema') != 'civ6rl.native_aux_string_keys.static.v1' or proof.get('parent_sha256') != PROOF_SHA256 or proof.get('slot') != {'vtable_rva': 8507296, 'offset': 24, 'target_rva': 7661648, 'bytes': '50e8748001000000'}:
            raise ValueError('AUX+A8 string-key source contract changed')
    if any((type(v) is not int or v <= 0 or v >= 1 << 63 for v in (core_base, map_pointer))):
        raise ValueError('Invalid AUX+A8 base/map pointer')
    total = 0
    sources = {}

    def remember(address, data):
        span = (address, len(data))
        if span in sources and sources[span] != data:
            raise ValueError('AUX+A8 source changed during snapshot')
        sources[span] = data

    def copy(address, size, *, track=True):
        nonlocal total
        if type(address) is not int or address <= 0 or type(size) is not int or (size < 0) or (address + size >= 1 << 63):
            raise ValueError('Invalid AUX+A8 source span')
        if total + size > MAX_READ_BYTES:
            raise ValueError('AUX+A8 native read budget exceeded')
        result = bytearray()
        for offset in range(0, size, 4096):
            count = min(4096, size - offset)
            part = read(address + offset, count)
            if not isinstance(part, (bytes, bytearray)) or len(part) != count:
                raise ValueError('Incomplete AUX+A8 native copy')
            result.extend(part)
        total += size
        data = bytes(result)
        if track:
            remember(address, data)
        return data
    if type(allow_nested_maps) is not bool or (allow_nested_maps and transport_version != 2):
        raise ValueError('Nested map transport requires explicit V2 admission')
    if allow_nested_maps:
        from civ6_host.runtime.script_map_argument_source import source_for_core
        source_for_core(core_sha256)
    if xp2_operation_vector:
        from civ6_host.runtime.configuration_profiles import XP2_CORE_SHA256
        if core_sha256 != XP2_CORE_SHA256 or not allow_nested_maps:
            raise ValueError('Operation vector requires explicit XP2 nested map admission')
    active_maps = set()
    copy_bytes = 0
    if type(native_copy_budget) is not bool or (native_copy_budget and (not allow_nested_maps)):
        raise ValueError('Native copy bounds require the nested-map source profile')

    def charge_copy(size):
        nonlocal copy_bytes
        if native_copy_budget:
            copy_bytes += size
            if size < 0 or copy_bytes > MAX_READ_BYTES:
                raise ValueError('Native map copy allocation budget exceeded')

    def read_map(map_pointer):
        header = copy(map_pointer, 84)
        vt, = struct.unpack_from('<Q', header)
        if vt != core_base + map_abi.vtable_rva:
            raise ValueError(f'Unverified AUX+A8 map vtable {vt:#x}')
        for offset, rva in map_abi.slots:
            if struct.unpack('<Q', copy(vt + offset, 8))[0] != core_base + rva:
                raise ValueError(f'Unverified AUX+A8 map slot {offset:#x}')
        resolver = 0
        if use_string_keys:
            if struct.unpack('<Q', copy(vt + 24, 8))[0] != core_base + map_abi.name_getter_rva or copy(core_base + map_abi.name_getter_rva, 5) != bytes.fromhex('488b4120c3'):
                raise ValueError('Unverified AUX+A8 map-owned name resolver getter')
            resolver = struct.unpack_from('<Q', header, 32)[0]
        begin, root = struct.unpack_from('<QQ', header, 56)
        count, = struct.unpack_from('<I', header, 80)
        sentinel = map_pointer + 48
        if count > MAX_FIELDS or (count == 0 and (root or begin != sentinel)) or (count and (not root)):
            raise ValueError('Unverified AUX+A8 tree count/root')
        rows = []
        seen = set()
        pending = [(root, sentinel, False)] if root else []
        nodes = {}
        while pending:
            address, parent, visited = pending.pop()
            if not address:
                continue
            if visited:
                rows.append((address, nodes[address]))
                continue
            if address == sentinel or address in seen or len(seen) >= count:
                raise ValueError('AUX+A8 cyclic or oversized tree')
            raw = copy(address, 64)
            right, left, actual_parent = struct.unpack_from('<QQQ', raw)
            if actual_parent != parent:
                raise ValueError('AUX+A8 tree parent mismatch')
            seen.add(address)
            nodes[address] = raw
            if right:
                pending.append((right, address, False))
            pending.append((address, parent, True))
            if left:
                pending.append((left, address, False))
        if len(rows) != count or (rows and rows[0][0] != begin):
            raise ValueError('AUX+A8 tree iteration/count mismatch')
        keys = [struct.unpack_from('<I', row, 32)[0] for _, row in rows]
        if any((a >= b for a, b in zip(keys, keys[1:]))):
            raise ValueError('AUX+A8 map keys not strictly ordered')
        if RESERVED_ARRAY_KEY in keys:
            raise ValueError('AUX+A8 reserved array-key representation is not admitted')
        return ([node[40:64] for _, node in rows], keys, resolver, count)

    def read_operation_vector(address):
        header = copy(address, 72)
        vtable, = struct.unpack_from('<Q', header)
        if vtable != core_base + 0xabf918:
            raise ValueError('Unexpected XP2 operation vector vtable')
        if (struct.unpack('<Q', copy(vtable + 0x20, 8))[0] != core_base + 0x989d0
                or copy(core_base + 0x989d0, 5) != bytes.fromhex('488b4120c3')):
            raise ValueError('Unexpected XP2 operation vector resolver')
        resolver, start, end, capacity = struct.unpack_from('<QQQQ', header, 0x20)
        if (not 0 <= start <= end <= capacity < (1 << 47)
                or (end - start) % 32 or (capacity - start) % 32
                or end - start > MAX_FIELDS * 32
                or not start and (end or capacity)):
            raise ValueError('Invalid XP2 operation vector span')
        data = copy(start, end - start) if end > start else b''
        keys = [struct.unpack_from('<I', data, i)[0] for i in range(0, len(data), 32)]
        if RESERVED_ARRAY_KEY in keys or len(set(keys)) != len(keys):
            raise ValueError('Invalid XP2 operation vector keys')
        return ([data[i + 8:i + 32] for i in range(0, len(data), 32)],
                keys, resolver, len(keys))
    wire = bytearray()
    types = []
    elements = 0
    string_bytes = 0
    active_lists = set()

    def op(opcode, arg=0, payload=0):
        if len(wire) // 16 >= MAX_OPS:
            raise ValueError('AUX+A8 transport operation bound exceeded')
        wire.extend(_OP.pack(opcode, arg, payload))

    def number(value):
        op(NUMBER, 0, struct.unpack('<Q', struct.pack('<d', float(value)))[0])

    def numeric_element(tag, data):
        if tag == 1:
            op(BOOLEAN, data[0])
        elif tag in (2, 3):
            number(struct.unpack('<i', data)[0])
        elif tag == 4:
            bits, = struct.unpack('<I', data)
            exponent = bits >> 23 & 255
            if exponent == 255 or (exponent == 0 and bits & 8388607):
                raise ValueError('AUX+A8 nonfinite/subnormal float requires additional native-state proof')
            number(struct.unpack('<f', data)[0])
        else:
            raise ValueError('Unverified AUX+A8 numeric type')

    def descriptor(data):
        op(TABLE, 0, 3)
        for index, value in enumerate(struct.unpack('<hhi', data)):
            op(STRING_CONST, index)
            number(value)
            op(RAWSET)

    def byte_string(pointer):
        nonlocal string_bytes
        if not pointer:
            if transport_version == 2:
                op(NIL)
                return 0
            raise ValueError('AUX+A8 null byte-string pointer is not admitted')
        data = bytearray()
        limit = min(MAX_STRING_BYTES, MAX_TOTAL_STRING_BYTES - string_bytes)
        for index in range(limit + 1):
            item = copy(pointer + index, 1, track=False)
            if item == b'\x00':
                remember(pointer, bytes(data) + b'\x00')
                string_bytes += len(data)
                payload_size = (len(data) + 1 + 15) // 16 * 16
                if len(wire) // 16 + 1 + payload_size // 16 > MAX_OPS:
                    raise ValueError('AUX+A8 transport operation bound exceeded')
                op(STRING_BYTES, len(data), 0)
                wire.extend(data)
                wire.extend(bytes(payload_size - len(data)))
                return len(data)
            data.extend(item)
        raise ValueError('AUX+A8 byte-string terminator missing within string/global bound')

    def utf16_string(pointer):
        nonlocal string_bytes
        from civ6_host.runtime.variant_text import lua_utf16_snapshot
        data, units = lua_utf16_snapshot(pointer, copy, remember)
        if data is None:
            op(NIL)
            return units
        string_bytes += len(data)
        if string_bytes > MAX_TOTAL_STRING_BYTES:
            raise ValueError('AUX map total string budget exceeded')
        payload_size = (len(data) + 1 + 15) // 16 * 16
        if len(wire) // 16 + 1 + payload_size // 16 > MAX_OPS:
            raise ValueError('AUX map transport operation bound exceeded')
        op(STRING_BYTES, len(data), 0)
        wire.extend(data)
        wire.extend(bytes(payload_size - len(data)))
        return units

    def resolver_lookup(resolver, root_offset, sentinel_offset, key, *, name):
        """Exact unsigned lower-bound search from EXE7A1170, read-only."""
        sentinel = resolver + sentinel_offset
        node = struct.unpack('<Q', copy(resolver + root_offset, 8))[0]
        candidate = None
        visited = set()
        lower = -1
        upper = 1 << 32
        while node:
            if node == sentinel or node in visited or len(visited) >= MAX_FIELDS:
                raise ValueError('AUX+A8 cyclic or oversized name-resolver path')
            visited.add(node)
            raw = copy(node, 48 if name else 36)
            key_at = struct.unpack_from('<I', raw, 32)[0]
            if not lower < key_at < upper:
                raise ValueError('AUX+A8 name-resolver key order changed')
            if key_at >= key:
                candidate = (key_at, raw)
                upper = key_at
                node = struct.unpack_from('<Q', raw, 8)[0]
            else:
                lower = key_at
                node = struct.unpack_from('<Q', raw, 0)[0]
        if candidate is None or candidate[0] != key:
            return None
        return struct.unpack_from('<Q', candidate[1], 40)[0] if name else True

    def named_key(key, resolver):
        if not resolver or resolver_lookup(resolver, 32, 16, key, name=False) is None:
            return False
        pointer = resolver_lookup(resolver, 80, 64, key, name=True)
        if not pointer:
            return False
        byte_string(pointer)
        return True

    def value(raw, depth=0):
        nonlocal elements
        tag, = struct.unpack_from('<H', raw)
        pointer, size, flags = struct.unpack_from('<QII', raw, 8)
        if native_copy_budget and flags & 536870912:
            extent = size * (flags & 16777215)
            charge_copy(extent)
            if extent:
                copy(pointer, extent)
        if flags == 0 and tag in (1, 2, 3, 4):
            width = 1 if tag == 1 else 4
            numeric_element(tag, raw[8:8 + width])
            types.append((tag, flags, 1))
        elif allow_nested_maps and tag == 10 and (flags == 83886080):
            if pointer:
                emit_map(pointer, depth + 1)
            else:
                charge_copy(88)
                op(NIL)
            types.append((tag, flags, 1 if pointer else 0))
        elif transport_version == 2 and flags & 4278190080 in (536870912, 553648128) and (tag == 6):
            units = utf16_string(pointer)
            types.append((tag, flags, units))
        elif flags & 4278190080 in (536870912, 553648128) and tag == 5:
            length = byte_string(pointer)
            types.append((tag, flags, length))
        elif flags & 4278190080 in (536870912, 553648128) and tag in (1, 2, 3, 4, 1024, 1025):
            length = flags & 16777215
            width = 1 if tag == 1 else 8 if tag in (1024, 1025) else 4
            byte_count = width * length
            details = f'tag={tag:#x} flags={flags:#x} size={size} count={length} required_bytes={byte_count}'
            elements += length
            if elements > MAX_ELEMENTS or (length and (not pointer)):
                raise ValueError('AUX+A8 array size/count/pointer outside bounded profile: ' + details)
            try:
                data = copy(pointer, byte_count) if length else b''
            except Exception as exc:
                raise ValueError('AUX+A8 typed-array checked copy refused: ' + details + '; ' + str(exc)) from exc
            if tag == 1024 and length == 1:
                descriptor(data)
            else:
                op(TABLE, length, 0)
                for i in range(length):
                    item = data[i * width:(i + 1) * width]
                    if tag in (1024, 1025):
                        descriptor(item)
                    else:
                        numeric_element(tag, item)
                    op(RAWSETI, i + 1)
            types.append((tag, flags, length))
        elif tag == 11 and flags == 285212672:
            if not pointer:
                raise ValueError('AUX+A8 null list element has no source-pushed value')
            if depth >= MAX_LIST_DEPTH:
                raise ValueError('AUX+A8 list recursion depth exceeded')
            if pointer in active_lists:
                raise ValueError('AUX+A8 cyclic Variant list')
            bounds = copy(pointer + 40, 16)
            start, end = struct.unpack('<QQ', bounds)
            if start >= 1 << 63 or end >= 1 << 63 or end < start or (end - start) % 24 or (end != start and (not start)):
                raise ValueError('AUX+A8 invalid Variant-list span')
            length = (end - start) // 24
            charge_copy(256 + 24 * length)
            elements += length
            if elements > MAX_ELEMENTS:
                raise ValueError('AUX+A8 global element budget exceeded')
            data = copy(start, end - start) if length else b''
            types.append((tag, flags, length))
            active_lists.add(pointer)
            try:
                op(TABLE, length, 0)
                for i in range(length):
                    value(data[i * 24:(i + 1) * 24], depth + 1)
                    op(RAWSETI, i + 1)
            finally:
                active_lists.remove(pointer)
        else:
            raise ValueError(f'Unverified AUX+A8 variant tag={tag:#x} flags={flags:#x} size={size} count={flags & 16777215}; no result substituted')

    def emit_map(map_address, depth):
        nonlocal elements
        if depth >= MAX_LIST_DEPTH or map_address in active_maps:
            raise ValueError('AUX map recursion depth or cycle refused')
        vector = xp2_operation_vector and depth == 0
        reader = read_operation_vector if vector else read_map
        rows, keys, resolver, count = reader(map_address)
        charge_copy(72 + 32 * count if vector else 88 + 64 * count)
        if allow_nested_maps:
            elements += count
            if elements > MAX_ELEMENTS:
                raise ValueError('AUX map aggregate field budget exceeded')
        active_maps.add(map_address)
        try:
            op(TABLE, 0, count)
            for key, raw in zip(keys, rows):
                tag, = struct.unpack_from('<H', raw)
                pointer, _, flags = struct.unpack_from('<QII', raw, 8)
                if tag == 11 and flags == 285212672 and (not pointer):
                    types.append((tag, flags, 0))
                    continue
                if not (use_string_keys and named_key(key, resolver)):
                    number(struct.unpack('<i', struct.pack('<I', key))[0])
                value(raw, depth)
                op(RAWSET)
        finally:
            active_maps.remove(map_address)
        return count
    count = emit_map(map_pointer, 0)
    for (address, size), original in sources.items():
        if copy(address, size, track=False) != original:
            subject = 'map' if address == map_pointer else 'source'
            raise ValueError(f'AUX+A8 {subject} changed during snapshot')
    transport = bytes(wire)
    validate_transport(transport)
    return MapSnapshot(transport, count, total, tuple(types))
