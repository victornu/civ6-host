"""Encode the EXE 0x9DEB82E7 ring-writer record from callback stack inputs.

This is a writer-layer encoder, not a reconstruction of the Core argument
marshaller. The callback has stack bytes that it does not initialize, so callers
must provide the captured 0x20/0x3c-byte source blocks explicitly. A caller that
zero-fills unspecified bytes creates a deterministic diagnostic record, not a
byte-for-byte claim about the native callback's stack contents.
"""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import struct
from civ6_host.runtime.native.native_application_mirror import decode_scalar
RECORD_SIZE = 112
RECORD_TYPE = 22
CALLBACK_SOURCE1_SIZE = 32
CALLBACK_SOURCE2_SIZE = 60

def encode_9deb_record(sequence: int, callback_source1: bytes, callback_source2: bytes, *, metadata: int=0) -> bytes:
    """Apply EXE writer 0x140126FC0 to its two callback source blocks.

    The writer makes a 0x70-byte record: header at 0, source2 at +0x10,
    source1 at +0x50. It overwrites source2 byte range +0x44..+0x47 with
    zero and source1's first dword with the sequence number.
    """
    if type(sequence) is not int or not 1 <= sequence <= 4294967295:
        raise ValueError('sequence must be an unsigned nonzero DWORD')
    if type(metadata) is not int or not 0 <= metadata <= 4294967295:
        raise ValueError('metadata must be an unsigned DWORD')
    if not isinstance(callback_source1, (bytes, bytearray, memoryview)) or len(callback_source1) != CALLBACK_SOURCE1_SIZE:
        raise ValueError('callback_source1 must contain exactly 0x20 bytes')
    if not isinstance(callback_source2, (bytes, bytearray, memoryview)) or len(callback_source2) != CALLBACK_SOURCE2_SIZE:
        raise ValueError('callback_source2 must contain exactly 0x3c bytes')
    record = bytearray(RECORD_SIZE)
    struct.pack_into('<IIII', record, 0, RECORD_SIZE, RECORD_TYPE, sequence, metadata)
    record[16:76] = callback_source2
    record[68:72] = b'\x00' * 4
    record[80:112] = callback_source1
    struct.pack_into('<I', record, 80, sequence)
    return bytes(record)

def encode_9deb_fields(sequence: int, fields: dict[int, bytes], read, *, metadata: int=0) -> bytes:
    """Normalize the observed scalar/entity/position arguments and encode them.

    The Core callback's normalized descriptor is ``<owner:uint16, type=1,
    identifier:uint32>``. The callback's uninitialized stack padding is zeroed
    in this deterministic diagnostic profile; this is not a byte-exact capture
    of native stack garbage.
    """
    expected = {2716180809, 4032072631, 2353434172}
    if set(fields) != expected or decode_scalar(fields[2716180809], 3) != 0:
        raise ValueError('Unverified 0x9DEB82E7 argument keys or selector')

    def blob(raw: bytes, expected_tag: int) -> bytes:
        if not isinstance(raw, bytes) or len(raw) != 24 or struct.unpack_from('<H', raw)[0] != expected_tag:
            raise ValueError('Unverified 0x9DEB82E7 blob variant')
        pointer, size, flags = struct.unpack_from('<QII', raw, 8)
        if not pointer or size != 8 or flags != 553648129:
            raise ValueError('Unverified 0x9DEB82E7 blob allocation')
        data = read(pointer, 8)
        if not isinstance(data, (bytes, bytearray, memoryview)) or len(data) != 8:
            raise ValueError('Incomplete 0x9DEB82E7 blob copy')
        return bytes(data)
    owner, _source_type, identifier = struct.unpack('<HHI', blob(fields[4032072631], 1024))
    position = blob(fields[2353434172], 0)
    descriptor = struct.pack('<HHI', owner, 1, identifier)
    source1 = bytearray(32)
    source1[8:16] = descriptor
    source1[16:24] = position
    source2 = bytearray(b'\xff\xff\xff\xff\xff\xff\xff\xff' + b'\x00' * (60 - 8))
    source2[8:16] = descriptor
    for offset in (16, 24, 32, 40):
        struct.pack_into('<HHi', source2, offset, 65535, 0, -1)
    source2[48:60] = b'\x00' * 12
    return encode_9deb_record(sequence, source1, source2, metadata=metadata)
