"""Inspect actual Core-written records in the explicit headless telemetry host."""
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import ctypes as C
import hashlib
import struct
from civ6_host.runtime.native.native_setup import local_reader
TELEMETRY_CAPACITY = 4194304
TELEMETRY_RECORD_SIZE = 14592
TELEMETRY_HEADER_SIZE = 16
TELEMETRY_PAYLOAD_SIZE = 14568
TELEMETRY_UNWRITTEN_TAIL_SIZE = 8

def read_telemetry_bank(read, address, cursor):
    """Copy one capacity-checked bank without exceeding OS reader bounds."""
    if type(address) is not int or address <= 0:
        raise ValueError('Invalid native telemetry bank address')
    if type(cursor) is not int or not 0 <= cursor <= TELEMETRY_CAPACITY or cursor % 128:
        raise ValueError('Invalid native telemetry bank cursor')
    chunks = []
    for offset in range(0, cursor, 4096):
        size = min(4096, cursor - offset)
        chunk = read(address + offset, size)
        if not isinstance(chunk, bytes) or len(chunk) != size:
            raise RuntimeError('Incomplete native telemetry bank copy')
        chunks.append(chunk)
    return b''.join(chunks)

def parse_telemetry_bank(data, cursor):
    """Parse exact Core 0x3900 telemetry reservations from one ring bank.

    Core writes a 16-byte header, copies 0x38E8 payload bytes, then leaves the
    final eight reserved bytes untouched. Those bytes are surfaced verbatim;
    their values are not constrained because a reused native reservation can
    retain prior contents.
    """
    if type(cursor) is not int or not 0 <= cursor <= TELEMETRY_CAPACITY:
        raise ValueError('Native telemetry cursor outside source-defined capacity')
    if not isinstance(data, (bytes, bytearray, memoryview)):
        raise ValueError('Native telemetry bank must be bytes-like')
    view = memoryview(data).cast('B')
    if len(view) != cursor:
        raise ValueError('Native telemetry bytes do not match cursor')
    if cursor % 128:
        raise ValueError('Native telemetry cursor is not 0x80-aligned')
    records = []
    offset = 0
    while offset < cursor:
        if cursor - offset < TELEMETRY_HEADER_SIZE:
            raise ValueError('Truncated native telemetry record header')
        size, marker, header_flags = struct.unpack_from('<IQI', view, offset)
        if size != TELEMETRY_RECORD_SIZE:
            raise ValueError('Unexpected native telemetry record size')
        if marker != 1:
            raise ValueError('Unexpected native telemetry header marker')
        if header_flags != 0:
            raise ValueError('Unexpected native telemetry header flags')
        end = offset + size
        if end > cursor:
            raise ValueError('Native telemetry record exceeds cursor')
        payload_start = offset + TELEMETRY_HEADER_SIZE
        payload_end = payload_start + TELEMETRY_PAYLOAD_SIZE
        tail_end = payload_end + TELEMETRY_UNWRITTEN_TAIL_SIZE
        if payload_end != end - TELEMETRY_UNWRITTEN_TAIL_SIZE or tail_end != end:
            raise AssertionError('Pinned native telemetry size constants disagree')
        payload = bytes(view[payload_start:payload_end])
        tail = bytes(view[payload_end:tail_end])
        records.append({'offset': offset, 'size': size, 'header_marker': marker, 'header_flags': header_flags, 'payload_bytes': len(payload), 'payload_sha256': hashlib.sha256(payload).hexdigest(), 'unwritten_tail_bytes': tail.hex()})
        offset = end
    if offset != cursor:
        raise ValueError('Native telemetry cursor ends inside a record')
    return records

class NativeTelemetryProfile:

    def __init__(self, executable, emit):
        self.emit = emit
        self.get = executable.LAB_GetTelemetryDiagnosticStorage
        self.get.argtypes, self.get.restype = ([], C.c_void_p)
        self.pointer = int(self.get() or 0)
        if not self.pointer or self.pointer % 128:
            raise RuntimeError('Native telemetry storage is unavailable or misaligned')
        self.read = local_reader()

    def inspect(self, phase):
        pointer = int(self.get() or 0)
        if pointer != self.pointer:
            raise RuntimeError('Telemetry storage lifetime changed')
        if int.from_bytes(self.read(pointer + 4, 4), 'little') != 0:
            raise RuntimeError('Unverified native telemetry slot')
        slot = pointer + 128
        selector = int.from_bytes(self.read(slot + 8388864, 4), 'little')
        rows = []
        for bank in (0, 1):
            segment = slot + bank * 4194432
            cursor = int.from_bytes(self.read(segment, 4), 'little')
            if cursor > TELEMETRY_CAPACITY:
                raise RuntimeError('Native telemetry cursor outside source-defined bounds')
            data = read_telemetry_bank(self.read, segment + 128, cursor)
            try:
                records = parse_telemetry_bank(data, cursor)
            except ValueError as exc:
                raise RuntimeError(f'Invalid Core telemetry bank: {exc}') from exc
            rows.append({'bank': bank, 'used_bytes': cursor, 'records': records, 'sha256': hashlib.sha256(data).hexdigest()})
        self.emit('native_telemetry_records_observed', phase=phase, active_selector=selector, banks=rows, records_written_by_core=True, consumer_delivery_reproduced=False, eligible_for_training=False)
        return rows
