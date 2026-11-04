"""Read-only Civ6Save container inspection, not a native Load admission.

The 64 KiB zlib framing is adapted from pydt/civ6-save-parser's
readCompressedData (MIT, Mike Rosack and playyourdamnturn.com, 2017).
Pinned source and full license: third_party/pydt-civ6-save-parser/.
Unlike its permissive decoder, we retain each block boundary, reject partial
blocks and impose output limits. The observed streams use Z_SYNC_FLUSH, not
a final zlib checksum: successful inflation is not integrity certification.
"""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
from dataclasses import dataclass
import hashlib
import re
import struct
import zlib
MAX_SAVE_BYTES = 64 * 1024 * 1024
MAX_PAYLOAD_BYTES = 64 * 1024 * 1024
MAX_TOTAL_BYTES = 128 * 1024 * 1024
BLOCK_BYTES = 65536
GAME_HEADER = bytes.fromhex('050000000300000049fe334e03000000')
ZLIB_HEADER = b'x\x9c'

def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

@dataclass(frozen=True)
class CompressedSection:
    offset: int
    end: int
    block_lengths: tuple[int, ...]
    packed: bytes
    payload: bytes
    zlib_eof: bool

    @property
    def kind(self) -> str:
        if self.payload.startswith(b'DDS '):
            return 'dds_thumbnail'
        if self.payload.startswith(GAME_HEADER):
            return 'gamecore_stream_candidate'
        return 'other_compressed_section'

    def receipt(self) -> dict:
        return dict(offset=self.offset, end=self.end, block_lengths=list(self.block_lengths), kind=self.kind, compressed_bytes=len(self.packed), compressed_sha256=sha(self.packed), payload_bytes=len(self.payload), payload_sha256=sha(self.payload), payload_prefix_hex=self.payload[:32].hex(), zlib_eof=self.zlib_eof, final_checksum_verified=self.zlib_eof, native_load_compatibility_proven=False)

def read_section(data: bytes, offset: int, *, max_payload: int=MAX_PAYLOAD_BYTES) -> CompressedSection:
    """Decode one observed length-framed stream, with no allocation from a file length."""
    if not 0 <= offset <= len(data) - 6 or not 0 < max_payload <= MAX_PAYLOAD_BYTES:
        raise ValueError('Invalid section offset/output budget')
    if data[offset + 4:offset + 6] != ZLIB_HEADER:
        raise ValueError('Unsupported zlib header')
    pos, lengths, chunks = (offset, [], [])
    while True:
        if pos + 4 > len(data):
            raise ValueError('Missing block length')
        length = struct.unpack_from('<I', data, pos)[0]
        if not 0 < length <= BLOCK_BYTES:
            raise ValueError('Invalid compressed block length')
        if pos + 4 + length > len(data):
            raise ValueError('Truncated compressed block')
        lengths.append(length)
        chunks.append(data[pos + 4:pos + 4 + length])
        pos += 4 + length
        if length < BLOCK_BYTES:
            break
    packed = b''.join(chunks)
    decoder = zlib.decompressobj()
    try:
        payload = decoder.decompress(packed, max_payload + 1)
    except zlib.error as exc:
        raise ValueError('Invalid compressed section') from exc
    if len(payload) > max_payload or decoder.unconsumed_tail:
        raise ValueError('Decompressed section exceeds budget')
    if decoder.unused_data:
        raise ValueError('Extra bytes after zlib stream')
    if not decoder.eof and (not packed.endswith(b'\x00\x00\xff\xff')):
        raise ValueError('Incomplete stream: missing observed sync-flush boundary')
    return CompressedSection(offset, pos, tuple(lengths), packed, payload, decoder.eof)

def inspect_save(data: bytes) -> tuple[dict, tuple[CompressedSection, ...]]:
    if not 8 <= len(data) <= MAX_SAVE_BYTES or data[:4] != b'CIV6':
        raise ValueError('Unsupported Civ6Save container or size')
    sections, rejected = ([], [])
    covered_until = 0
    total = 0
    count = 0
    for match in re.finditer(ZLIB_HEADER, data):
        offset = match.start() - 4
        if offset < covered_until or offset < 8:
            continue
        length = struct.unpack_from('<I', data, offset)[0]
        if not 0 < length <= BLOCK_BYTES:
            continue
        count += 1
        if count > 512:
            raise ValueError('Too many compressed-section candidates')
        try:
            section = read_section(data, offset, max_payload=min(MAX_PAYLOAD_BYTES, MAX_TOTAL_BYTES - total))
        except ValueError as exc:
            rejected.append(dict(offset=offset, reason=str(exc)))
            continue
        total += len(section.payload)
        sections.append(section)
        covered_until = section.end
    games = [s for s in sections if s.kind == 'gamecore_stream_candidate']
    hints = sorted(set((m.decode('ascii') for m in re.findall(b'RULESET_[A-Z_0-9]+', data))))
    report = dict(schema='civ6rl.official_save_container_inspection.v1', bytes=len(data), sha256=sha(data), sections=[s.receipt() for s in sections], rejected_candidates=rejected, gamecore_candidate_count=len(games), ruleset_string_hints=hints, active_ruleset_proven=False, complete_container_interpreted=False, native_load_attempted=False, strategic_training_ready=False)
    return (report, tuple(sections))
