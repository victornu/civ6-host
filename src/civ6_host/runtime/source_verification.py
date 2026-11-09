"""Reuse verified static inputs during one parent preparation phase."""
from collections import OrderedDict
from contextlib import contextmanager
from contextvars import ContextVar
import hashlib


_ACTIVE = ContextVar('source_verification_scope', default=None)
_JSON_BYTES = 6 * 1024**2
_JSON_FILE_BYTES = 512 * 1024
_JSON_ENTRIES = 384


def _identity(path):
    info = path.stat()
    return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns


class _VerifiedSources:
    def __init__(self):
        self.hashes = {}
        self.json = OrderedDict()
        self.json_bytes = 0

    def remember_json(self, key, identity, value):
        size = identity[2]
        if size > _JSON_FILE_BYTES:
            return
        previous = self.json.pop(key, None)
        if previous is not None:
            self.json_bytes -= previous[0][2]
        self.json[key] = identity, value
        self.json_bytes += size
        while self.json_bytes > _JSON_BYTES or len(self.json) > _JSON_ENTRIES:
            _, (removed, _) = self.json.popitem(last=False)
            self.json_bytes -= removed[2]


@contextmanager
def verification_scope():
    """Limit reuse to one exact parent graph. The worker rehashes its closure."""
    token = _ACTIVE.set(_VerifiedSources())
    try:
        yield
    finally:
        _ACTIVE.reset(token)


def file_sha256(path):
    sources = _ACTIVE.get()
    if sources is not None:
        before = _identity(path)
        cached = sources.hashes.get(path)
        if cached is not None and cached[0] == before:
            return cached[1]
    with path.open('rb') as stream:
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    if sources is not None:
        if _identity(path) != before:
            raise ValueError('Static source changed during hash verification: ' + str(path))
        sources.hashes[path] = before, digest
    return digest


def pinned_json(path, expected, load):
    sources = _ACTIVE.get()
    if sources is None:
        return load(path, expected)
    before = _identity(path)
    key = path, expected
    cached = sources.json.get(key)
    if cached is not None and cached[0] == before:
        sources.json.move_to_end(key)
        return cached[1]
    value = load(path, expected)
    if _identity(path) != before:
        raise ValueError('Static JSON changed during source verification: ' + str(path))
    sources.remember_json(key, before, value)
    return value
