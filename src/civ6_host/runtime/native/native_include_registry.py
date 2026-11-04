"""Bounded, read-only Lua source provider for the native include adapter.

This module packages Lua files beneath explicitly supplied asset roots. It
does not execute Lua or resolve paths outside those roots.
"""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import ctypes as C
from dataclasses import dataclass
import os
from pathlib import Path
from typing import Iterable
MAX_FILES = 8192
MAX_NAME_BYTES = 1024
MAX_SOURCE_BYTES = 16 * 1024 * 1024
MAX_TOTAL_BYTES = 256 * 1024 * 1024

@dataclass(frozen=True)
class IncludeSource:
    name: str
    source: bytes

def _reject_reparse_components(path: Path) -> None:
    """Reject symlinks/junctions without resolving the target path."""
    if os.name == 'nt':
        kernel32 = C.WinDLL('kernel32', use_last_error=True)
        get_attributes = kernel32.GetFileAttributesW
        get_attributes.argtypes = (C.c_wchar_p,)
        get_attributes.restype = C.c_uint32
        components = list(reversed((path, *path.parents)))
        for component in components:
            attrs = get_attributes(str(component))
            if attrs == 4294967295:
                raise OSError(C.get_last_error(), 'GetFileAttributesW failed', str(component))
            if attrs & 1024:
                raise ValueError(f'reparse point in approved include path: {component}')
    else:
        for component in (path, *path.parents):
            if component.is_symlink():
                raise ValueError(f'symlink in approved include path: {component}')

def collect_lua_sources(roots: Iterable[Path]) -> tuple[IncludeSource, ...]:
    """Collect regular ``*.lua`` files under approved roots in stable order.

    Names are root-relative POSIX paths and remain case-preserving. Duplicate
    relative names across roots are rejected instead of silently shadowed.
    """
    result: list[IncludeSource] = []
    names: set[str] = set()
    total = 0
    for root in roots:
        root = _resolve_resource_path(Path(os.path.abspath(_resolve_resource_path(Path(root)))))
        _reject_reparse_components(root)
        for path in sorted(root.rglob('*.lua'), key=lambda item: item.as_posix().casefold()):
            if not _resolve_resource_path(path).is_file():
                continue
            path = _resolve_resource_path(Path(os.path.abspath(path)))
            _reject_reparse_components(path)
            try:
                relative = path.relative_to(root)
            except ValueError as exc:
                raise ValueError(f'include source escapes approved root: {path}') from exc
            name = relative.as_posix()
            encoded_name = name.encode('utf-8', 'strict')
            if not encoded_name or len(encoded_name) > MAX_NAME_BYTES or b'\x00' in encoded_name:
                raise ValueError(f'include source name exceeds bound: {name!r}')
            if name in names:
                raise ValueError(f'duplicate include source name: {name}')
            names.add(name)
            if len(result) >= MAX_FILES:
                raise ValueError('include source count exceeds bound')
            source = _resolve_resource_path(path).read_bytes()
            if len(source) > MAX_SOURCE_BYTES:
                raise ValueError(f'include source exceeds per-file bound: {name}')
            total += len(source)
            if total > MAX_TOTAL_BYTES:
                raise ValueError('include source total exceeds bound')
            result.append(IncludeSource(name, source))
    return tuple(result)

class _NativeInput(C.Structure):
    _fields_ = [('name', C.c_char_p), ('source', C.c_char_p), ('source_length', C.c_size_t)]

def bind_native_include_registry(loader, roots: Iterable[Path]) -> tuple[IncludeSource, ...]:
    """Copy a bounded source snapshot into the C host's native registry.

    ``loader`` is the already-loaded host library exposing
    ``LAB_ScriptIncludeSetFiles``. This function only calls that host API; it
    never starts or attaches to the game process.
    """
    records = collect_lua_sources(roots)
    api = loader.LAB_ScriptIncludeSetFiles
    api.argtypes = (C.POINTER(_NativeInput), C.c_size_t)
    api.restype = C.c_int
    keepalive: list[object] = []
    array = (_NativeInput * len(records))()
    for index, record in enumerate(records):
        name = C.create_string_buffer(record.name.encode('utf-8') + b'\x00')
        source = C.create_string_buffer(record.source if record.source else b'\x00')
        keepalive.extend((name, source))
        array[index] = _NativeInput(C.cast(name, C.c_char_p), C.cast(source, C.c_char_p), len(record.source))
    status = api(array, len(records))
    if status:
        raise RuntimeError(f'LAB_ScriptIncludeSetFiles failed with status {status}')
    return records
