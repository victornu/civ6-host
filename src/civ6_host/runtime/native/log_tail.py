"""A synchronous, complete-line tail of an existing append-only Lua.log."""
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import os
from pathlib import Path
MAX_FRAGMENT_BYTES = 64 * 1024
_READ_BYTES = 64 * 1024

class LogTailError(OSError):
    """The log was replaced/truncated, disappeared, or exceeded its line bound."""

class LogTail:
    """Open once at EOF and return only subsequently completed UTF-8 lines.

    ``read_lines`` never waits. Returned strings retain their LF (and optional
    CR), and malformed UTF-8 uses replacement characters. If the existing log
    ends mid-line, its subsequently appended remainder is discarded through
    the next LF. Rotation and observed truncation are errors, not implicit
    reconnections. After any LogTailError this instance must be closed.

    As with ordinary filesystem tailing, a truncate-and-regrow operation that
    finishes between checks without an identity change cannot always be seen.
    """

    def __init__(self, path: str | os.PathLike):
        self.path = _resolve_resource_path(Path(path))
        self._file = _resolve_resource_path(self.path).open('rb', buffering=0)
        self._fragment = b''
        self._discard_until_newline = False
        self._discarded_bytes = 0
        self._failed = False
        try:
            self._offset = self._file.seek(0, os.SEEK_END)
            self._last_size = self._offset
            self._identity = self._get_identity(os.fstat(self._file.fileno()))
            if self._offset:
                self._file.seek(self._offset - 1)
                self._discard_until_newline = self._file.read(1) != b'\n'
                self._file.seek(self._offset)
            self._check_file()
        except BaseException:
            self._file.close()
            raise

    @staticmethod
    def _get_identity(stat):
        return (stat.st_dev, stat.st_ino)

    @property
    def closed(self) -> bool:
        return self._file.closed

    def _error(self, reason: str) -> None:
        self._failed = True
        raise LogTailError(reason)

    def _check_file(self):
        try:
            current = os.fstat(self._file.fileno())
            at_path = _resolve_resource_path(os).stat(self.path)
        except OSError as exc:
            self._failed = True
            raise LogTailError(f'log file is unavailable: {exc}') from exc
        if self._get_identity(current) != self._identity or self._get_identity(at_path) != self._identity:
            self._error('log file rotated or was replaced')
        if min(current.st_size, at_path.st_size) < max(self._offset, self._last_size):
            self._error('log file was truncated')
        self._last_size = max(current.st_size, at_path.st_size)
        return current

    def read_lines(self) -> list[str]:
        """Read available complete lines; leave a trailing fragment buffered."""
        if self.closed:
            raise ValueError('log tail is closed')
        if self._failed:
            raise LogTailError('log tail already failed; close it before reconnecting')
        try:
            end = self._check_file().st_size
            result = []
            while self._offset < end:
                data = self._file.read(min(_READ_BYTES, end - self._offset))
                if not data:
                    self._check_file()
                    self._error('log ended before its observed size')
                self._offset += len(data)
                if self._discard_until_newline:
                    boundary = data.find(b'\n')
                    self._discarded_bytes += len(data) if boundary < 0 else boundary
                    if self._discarded_bytes > MAX_FRAGMENT_BYTES:
                        self._error('initial partial log line exceeds 64 KiB')
                    if boundary < 0:
                        continue
                    data = data[boundary + 1:]
                    self._discard_until_newline = False
                    self._discarded_bytes = 0
                parts = (self._fragment + data).split(b'\n')
                for part in parts[:-1]:
                    if len(part) > MAX_FRAGMENT_BYTES:
                        self._error('log line exceeds 64 KiB')
                    result.append((part + b'\n').decode('utf-8', errors='replace'))
                self._fragment = parts[-1]
                if len(self._fragment) > MAX_FRAGMENT_BYTES:
                    self._error('partial log line exceeds 64 KiB')
            self._check_file()
            return result
        except OSError:
            self._failed = True
            raise

    def close(self) -> None:
        self._file.close()
        self._fragment = b''

    def __enter__(self):
        if self.closed:
            raise ValueError('log tail is closed')
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()
