"""Bounded read-only inspection of serialized native configuration providers.

Uses the layout already captured for native_checkpoint_configuration_normalization
and the native variant writer's array and qword branches. This parses bytes;
it never constructs values, changes settings or admits a GameCore Load profile.
"""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
from dataclasses import dataclass
import struct

@dataclass(frozen=True)
class Value:
    offset: int
    end: int
    key: int | None
    tag: int
    extra: int
    flags: int
    size: int
    payload: bytes
    children: tuple['Value', ...] = ()

    def scalar(self):
        if self.tag in (1, 2, 3) and self.flags == self.size == 0:
            return int.from_bytes(self.payload, 'little')
        if self.tag in (5, 6) and self.flags >> 24 == 33:
            width = 1 if self.tag == 5 else 2
            if self.size != width:
                raise ValueError('Opaque variant stride is not an admitted string encoding')
            if not self.payload.endswith(b'\x00' * width):
                raise ValueError('String is not terminated')
            return self.payload[:-width].decode('utf-8' if width == 1 else 'utf-16-le')
        if self.tag == 5 and self.flags in (0, 536870912) and (self.payload == b'\x00' * 4):
            return ''
        raise ValueError('Value is not an admitted scalar')

class Reader:

    def __init__(self, data: bytes, offset: int=0, *, max_bytes=1024 * 1024, max_entries=16384, max_depth=16):
        if type(data) is not bytes or not 0 <= offset < len(data):
            raise ValueError('Immutable input and valid offset required')
        if not 0 < max_bytes <= 4 * 1024 * 1024 or not 0 < max_entries <= 65536 or (not 0 < max_depth <= 32):
            raise ValueError('Invalid inspection limits')
        self.data, self.offset = (data, offset)
        self.limit = min(len(data), offset + max_bytes)
        self.max_entries, self.max_depth, self.count = (max_entries, max_depth, 0)

    def take(self, size):
        if size < 0 or self.offset + size > self.limit:
            raise ValueError('Truncated or oversized configuration')
        result = self.data[self.offset:self.offset + size]
        self.offset += size
        return result

    def u32(self):
        return struct.unpack('<I', self.take(4))[0]

    def provider(self, depth=0):
        count = self.u32()
        if depth > self.max_depth or count > self.max_entries - self.count:
            raise ValueError('Provider count/depth exceeds inspection limit')
        result, previous = ([], -1)
        for _ in range(count):
            value = self.value(depth, keyed=True)
            if value.key <= previous:
                raise ValueError('Provider keys are duplicate or out of native order')
            previous = value.key
            result.append(value)
        return tuple(result)

    def value(self, depth, *, keyed):
        if depth > self.max_depth or self.count >= self.max_entries:
            raise ValueError('Variant count/depth exceeds inspection limit')
        self.count += 1
        start = self.offset
        key = self.u32() if keyed else None
        tag, extra = struct.unpack('<HH', self.take(4))
        flags, size = (self.u32(), self.u32())
        payload, children = (b'', ())
        if extra:
            raise ValueError(f'Unsupported variant extra word at {start}')
        if tag == 10 and flags == 83886080 and (size == 0):
            children = self.provider(depth + 1)
        elif tag == 11 and flags == 285212672 and (size == 0):
            count = self.u32()
            if count > self.max_entries - self.count:
                raise ValueError('Array count exceeds inspection limit')
            children = tuple((self.value(depth + 1, keyed=False) for _ in range(count)))
        elif tag in (1, 2, 3) and flags == size == 0:
            payload = self.take(4)
        elif tag in (20, 21) and flags == 2147483648 and (size == 0):
            payload = self.take(8)
        elif tag == 5 and flags in (0, 536870912) and (size in (0, 1)):
            payload = self.take(4)
            if payload != b'\x00' * 4:
                raise ValueError('Nonzero inline string is outside the observed profile')
        elif tag == 5 and flags >> 24 == 33 and (size == 2):
            length = flags & 16777215
            if not length or length > (self.limit - self.offset) // size:
                raise ValueError('Opaque configuration payload exceeds inspection limit')
            payload = self.take(length * size)
        elif tag in (5, 6, 24) and flags >> 24 == 33 and (size == (2 if tag == 6 else 1)):
            length = flags & 16777215
            if not length:
                raise ValueError('Empty indirect string/blob is outside the observed profile')
            payload = self.take(length * size)
        else:
            raise ValueError(f'Unsupported variant at {start}: tag={tag} flags={flags:#x} size={size}')
        return Value(start, self.offset, key, tag, extra, flags, size, payload, children)

def flatten(values):
    for value in values:
        yield value
        yield from flatten(value.children)

def read_provider(data: bytes, offset=0):
    reader = Reader(data, offset)
    values = reader.provider()
    return (values, reader.offset)

def compare_provider_roundtrip(before: bytes, after: bytes):
    """Compare complete streams, admitting only the previously proved change."""
    from civ6_host.runtime.native.native_checkpoint_configuration_normalization import verify_source_evidence
    from civ6_host.runtime.native.native_checkpoint_configuration_normalization import PROOF_SHA256
    verify_source_evidence()
    left, a_end = read_provider(before)
    right, b_end = read_provider(after)
    if a_end != len(before) or b_end != len(after) or len(before) != len(after):
        raise ValueError('Provider length or full consumption differs')
    a_values, b_values = (list(flatten(left)), list(flatten(right)))
    if len(a_values) != len(b_values):
        raise ValueError('Provider structure differs')
    predicted = bytearray(before)
    normalized = []
    for a, b in zip(a_values, b_values):

        def shape(v):
            return (v.offset, v.end, v.key, v.tag, v.extra, v.size, v.payload, len(v.children))
        if shape(a) != shape(b):
            raise ValueError('Provider value or layout differs')
        if a.flags == b.flags:
            continue
        if (a.tag, a.extra, a.flags, a.size, a.payload, b.flags) != (5, 0, 536870912, 1, b'\x00' * 4, 0):
            raise ValueError('Unproved provider normalization')
        flags_offset = a.offset + (8 if a.key is not None else 4)
        struct.pack_into('<I', predicted, flags_offset, 0)
        normalized.append(flags_offset + 3)
    if bytes(predicted) != after:
        raise ValueError('Other bytes changed outside the proved normalization')
    return dict(exact_bytes_equal=before == after, known_normalization_count=len(normalized), changed_offsets=normalized, values_compared=len(a_values), complete_streams_consumed=True, other_bytes_equal=True, normalization_proof_sha256=PROOF_SHA256, full_game_restored=False)
