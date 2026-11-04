"""Small metadata-aware LRU cache for hash-pinned static JSON evidence.

This module is only for immutable source/evidence files. It must not be used to
cache live game state or observations.
"""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
from collections import OrderedDict
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import threading
from types import MappingProxyType
from typing import Any
_MAX_ENTRIES = 64
_SHA256_RE = re.compile('[0-9a-fA-F]{64}\\Z')
_LOCK = threading.RLock()
_CACHE: OrderedDict[tuple[str, str, tuple[int, int, int, int, int]], Any] = OrderedDict()

def _stat_identity(path: Path) -> tuple[int, int, int, int, int]:
    stat = _resolve_resource_path(path).stat()
    return (stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns)

def _freeze(value: Any) -> Any:
    if isinstance(value, dict):
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, list):
        return tuple((_freeze(item) for item in value))
    return value

def load_pinned_json(path: str | Path, expected_sha256: str) -> Any:
    """Load and recursively freeze JSON whose exact file digest is pinned.

    Every call stats the file before looking in the cache. A miss is admitted
    only if its content digest matches and its metadata remains unchanged while
    it is read and parsed. Failures are never cached.
    """
    if not isinstance(expected_sha256, str) or not _SHA256_RE.fullmatch(expected_sha256):
        raise ValueError('expected_sha256 must be 64 hexadecimal characters')
    expected = expected_sha256.lower()
    resolved = _resolve_resource_path(Path(os.path.abspath(os.fspath(path))))
    identity_before = _stat_identity(resolved)
    cache_key = (str(resolved), expected, identity_before)
    with _LOCK:
        if cache_key in _CACHE:
            if _stat_identity(resolved) != identity_before:
                raise RuntimeError(f'pinned JSON changed while checking cache: {resolved}')
            cached = _CACHE[cache_key]
            _CACHE.move_to_end(cache_key)
            return cached
        raw = _resolve_resource_path(resolved).read_bytes()
        actual = sha256(raw).hexdigest()
        if actual != expected:
            raise RuntimeError(f'pinned JSON SHA-256 mismatch for {resolved}: {actual}')
        if _stat_identity(resolved) != identity_before:
            raise RuntimeError(f'pinned JSON changed while being read: {resolved}')
        parsed = json.loads(raw)
        if _stat_identity(resolved) != identity_before:
            raise RuntimeError(f'pinned JSON changed while being parsed: {resolved}')
        frozen = _freeze(parsed)
        _CACHE[cache_key] = frozen
        _CACHE.move_to_end(cache_key)
        while len(_CACHE) > _MAX_ENTRIES:
            _CACHE.popitem(last=False)
        return frozen

def _clear_cache_for_tests() -> None:
    with _LOCK:
        _CACHE.clear()

def _cache_size_for_tests() -> int:
    with _LOCK:
        return len(_CACHE)
