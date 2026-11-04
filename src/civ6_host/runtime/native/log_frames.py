"""Bounded assembly of ASCII bridge frames from complete Lua.log lines.

The caller owns file tailing: pass each complete line once its newline arrives.
``feed_line`` never buffers text fragments or joins partial log lines. A passed
line may retain its final LF/CRLF. Only successfully validated bridge records
are returned; malformed matching frames raise ``FrameError``.
"""
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
from collections import OrderedDict
from dataclasses import dataclass
from dataclasses import field
import hashlib
import re
import zlib
from civ6_host.runtime.native.protocol import PREFIX
from civ6_host.runtime.native.protocol import decode_record
FRAME_PREFIX = 'CIV6RL_FRAME '
MAX_MESSAGE_BYTES = 1024 * 1024
MAX_CHUNK_BYTES = 512
MAX_CHUNKS = 4096
MAX_PENDING = 16
MAX_COMPLETED = 64
MAX_FRAME_CHARS = 2048
_SESSION = re.compile('[A-Za-z0-9_.:-]{1,128}\\Z')
_LINE_START = re.compile('\\A(?:\\[[^\\]\\r\\n]{1,128}\\][ \\t]*)?(?:[^:\\r\\n]{1,128}:[ \\t]+)?(?P<frame>CIV6RL_FRAME)(?= |\\r?$|\\n)')
_FRAME = re.compile('CIV6RL_FRAME ([A-Za-z0-9_.:-]{1,128}) ([0-9]+) ([0-9]+) ([0-9]+) ([0-9]+) ([0-9]+) ([0-9A-Fa-f]+)\\Z')

class FrameError(ValueError):
    """An applicable frame or its assembled bridge record is invalid."""

@dataclass
class _Pending:
    metadata: tuple[int, int, int]
    chunks: dict[int, bytes] = field(default_factory=dict)
    received_bytes: int = 0

@dataclass
class _Completed:
    metadata: tuple[int, int, int]
    chunks: dict[int, bytes]

class LogFrameCollector:
    """Assemble interleaved messages, optionally restricted to one session.

    The key is (session, message sequence); sequences must be positive. At most
    16 incomplete messages are held. Exceeding that limit raises rather than
    silently evicting an observation. The last 64 completed messages suppress
    identical frame replays and reject conflicting replays. Older keys may be
    accepted again after eviction; use a fresh session for each connection.

    A failed pending message is discarded. Call ``reset`` when intentionally
    abandoning outstanding messages, for example after a log rotation.
    """

    def __init__(self, expected_session: str | None=None):
        if expected_session is not None and (not isinstance(expected_session, str) or not _SESSION.fullmatch(expected_session)):
            raise ValueError('expected_session must contain 1-128 permitted ASCII characters')
        self.expected_session = expected_session
        self._pending: dict[tuple[str, int], _Pending] = {}
        self._completed: OrderedDict[tuple[str, int], _Completed] = OrderedDict()

    @property
    def pending_count(self) -> int:
        return len(self._pending)

    @property
    def completed_count(self) -> int:
        return len(self._completed)

    def reset(self) -> None:
        """Forget incomplete messages and replay history; keep the session filter."""
        self._pending.clear()
        self._completed.clear()

    def _fail(self, key: tuple[str, int], reason: str) -> None:
        self._pending.pop(key, None)
        raise FrameError(reason)

    def feed_line(self, line: str) -> dict | None:
        """Return one validated envelope, or None for unrelated/incomplete/replayed data."""
        if not isinstance(line, str):
            raise TypeError('feed_line expects a complete text line')
        start = _LINE_START.match(line)
        if start is None:
            return None
        frame = line[start.start('frame'):]
        if frame.endswith('\n'):
            frame = frame[:-1]
            if frame.endswith('\r'):
                frame = frame[:-1]
        if self.expected_session is not None and frame.startswith(FRAME_PREFIX):
            session = frame[len(FRAME_PREFIX):].split(' ', 1)[0]
            if session != self.expected_session:
                return None
        if len(frame) > MAX_FRAME_CHARS:
            raise FrameError('frame line exceeds the bounded ASCII frame size')
        match = _FRAME.fullmatch(frame)
        if match is None:
            raise FrameError('malformed frame; pass complete individual log lines')
        session, sequence, index, count, size, checksum, hex_payload = match.groups()
        sequence, index, count, size, checksum = map(int, (sequence, index, count, size, checksum))
        key = (session, sequence)
        if sequence < 1:
            self._fail(key, 'message sequence must be positive')
        if not 1 <= count <= MAX_CHUNKS or not 1 <= index <= count:
            self._fail(key, 'invalid chunk index or count')
        if not 1 <= size <= MAX_MESSAGE_BYTES or not count <= size <= count * MAX_CHUNK_BYTES:
            self._fail(key, 'invalid message byte length or impossible chunk count')
        if not 0 <= checksum <= 4294967295:
            self._fail(key, 'invalid Adler-32 checksum')
        if len(hex_payload) % 2 or not 2 <= len(hex_payload) <= MAX_CHUNK_BYTES * 2:
            self._fail(key, 'hex payload must encode 1-512 bytes')
        chunk = bytes.fromhex(hex_payload)
        metadata = (count, size, checksum)
        completed = self._completed.get(key)
        if completed is not None:
            if completed.metadata != metadata:
                raise FrameError('completed message metadata changed')
            if completed.chunks[index] != hashlib.sha256(chunk).digest():
                raise FrameError('conflicting duplicate of a completed chunk')
            return None
        pending = self._pending.get(key)
        if pending is None:
            if len(self._pending) >= MAX_PENDING:
                raise FrameError('too many incomplete messages; reset or complete pending messages')
            pending = _Pending(metadata)
            self._pending[key] = pending
        elif pending.metadata != metadata:
            self._fail(key, 'message metadata changed between chunks')
        previous = pending.chunks.get(index)
        if previous is not None:
            if previous != chunk:
                self._fail(key, 'conflicting duplicate chunk')
            return None
        pending.chunks[index] = chunk
        pending.received_bytes += len(chunk)
        remaining = count - len(pending.chunks)
        if not pending.received_bytes + remaining <= size <= pending.received_bytes + remaining * MAX_CHUNK_BYTES:
            self._fail(key, 'chunk lengths do not match declared message byte length')
        if remaining:
            return None
        del self._pending[key]
        payload = b''.join((pending.chunks[i] for i in range(1, count + 1)))
        if zlib.adler32(payload) & 4294967295 != checksum:
            raise FrameError('message Adler-32 checksum mismatch')
        try:
            record = decode_record(PREFIX + payload.decode('utf-8'))
        except (ValueError, UnicodeError, RecursionError) as exc:
            raise FrameError(f'invalid UTF-8 JSON bridge record: {exc}') from exc
        if record['sequence'] != sequence:
            raise FrameError('frame sequence does not match bridge record sequence')
        self._completed[key] = _Completed(metadata, {i: hashlib.sha256(part).digest() for i, part in pending.chunks.items()})
        if len(self._completed) > MAX_COMPLETED:
            self._completed.popitem(last=False)
        return record
