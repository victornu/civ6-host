"""Explicit, bounded source for the Core GameplayScripts count/get interface.

This is a host-side record provider only. It does not inspect or infer which
mods are active, scan for scripts, parse modinfo, or execute Lua.
"""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import ctypes as C
from dataclasses import dataclass
import os
from pathlib import Path
from pathlib import PurePosixPath
from typing import Iterable
from civ6_host.runtime.script_wire_paths import encode_wire_path, selected_wire_paths, bind_wire_sources
from civ6_host.runtime.native.native_include_registry import _reject_reparse_components
MAX_PATH_UTF16_UNITS = 259
MAX_SELECTED_SCRIPTS = 8192

@dataclass(frozen=True)
class GameplayScriptEntry:
    """One explicitly selected Lua file beneath an approved root."""
    root: Path
    relative_path: str

def _approved_root(root: Path) -> Path:
    root = _resolve_resource_path(Path(os.path.abspath(_resolve_resource_path(Path(root)))))
    _reject_reparse_components(root)
    if not _resolve_resource_path(root).is_dir():
        raise ValueError(f'GameplayScripts root is not a directory: {root}')
    return root

def _relative_lua_path(value: str) -> PurePosixPath:
    if not isinstance(value, str) or not value or '\x00' in value:
        raise ValueError('GameplayScripts path must be a non-empty relative string')
    normalized = value.replace('\\', '/')
    candidate = PurePosixPath(normalized)
    if candidate.is_absolute() or any((part in ('', '.', '..') for part in candidate.parts)):
        raise ValueError(f'GameplayScripts path must stay beneath its approved root: {value!r}')
    if candidate.suffix.casefold() != '.lua':
        raise ValueError(f'GameplayScripts entry must name a .lua file: {value!r}')
    return candidate

class NativeGameplayScriptRegistry:
    """Provide ordered UTF-16 path pointers for a caller-selected script list.

    ``selected_scripts`` is mandatory. An explicitly empty tuple represents a
    zero-entry registry; omitted selection is an error. Buffers remain alive
    until ``close`` so native consumers can retain the returned pointers while
    processing the registry. Repeated paths remain repeated records, matching
    the official count/index consumer; the provider does not deduplicate them.
    """

    def __init__(self, asset_roots: Iterable[Path], *, selected_scripts: Iterable[GameplayScriptEntry] | None, wire_paths: Iterable[str] | None=None):
        if selected_scripts is None:
            raise ValueError('selected_scripts must be explicit (use () for an empty registry)')
        roots = tuple((_approved_root(_resolve_resource_path(Path(root))) for root in asset_roots))
        by_identity = {os.path.normcase(os.path.abspath(root)): root for root in roots}
        selected = tuple(selected_scripts)
        selected_names = selected_wire_paths(wire_paths, len(selected))
        names = []
        if len(selected) > MAX_SELECTED_SCRIPTS:
            raise ValueError('GameplayScripts selection exceeds the native record bound')
        paths: list[Path] = []
        buffers: list[C.Array] = []
        for index, entry in enumerate(selected):
            if not isinstance(entry, GameplayScriptEntry):
                raise TypeError('selected_scripts entries must be GameplayScriptEntry values')
            root = _resolve_resource_path(Path(os.path.abspath(_resolve_resource_path(Path(entry.root)))))
            key = os.path.normcase(str(root))
            if key not in by_identity:
                raise ValueError(f'GameplayScripts entry uses an unapproved root: {root}')
            relative = _relative_lua_path(entry.relative_path)
            path = _resolve_resource_path(Path(os.path.abspath(root.joinpath(*relative.parts))))
            try:
                path.relative_to(by_identity[key])
            except ValueError as exc:
                raise ValueError(f'GameplayScripts path escapes approved root: {entry.relative_path!r}') from exc
            _reject_reparse_components(path)
            if not _resolve_resource_path(path).is_file():
                raise FileNotFoundError(f'selected GameplayScripts file is missing: {path}')
            name = str(path) if selected_names is None else selected_names[index]
            encoded = encode_wire_path(name)
            names.append(name)
            units = len(encoded) // 2
            if units > MAX_PATH_UTF16_UNITS:
                raise ValueError(f'GameplayScripts path exceeds {MAX_PATH_UTF16_UNITS} UTF-16 units: {path}')
            paths.append(path)
            buffers.append(C.create_string_buffer(encoded + b'\x00\x00'))
        self._paths = tuple(paths)
        self._wire_paths = tuple(names)
        bind_wire_sources(self._paths, self._wire_paths)
        self._buffers = tuple(buffers)
        self._closed = False

    def count(self) -> int:
        """Return the selected record count, preserving caller order."""
        self._ensure_open()
        return len(self._paths)

    def get(self, index: int) -> int | None:
        """Return a stable UTF-16LE pointer, or null for a native OOB index."""
        self._ensure_open()
        if not isinstance(index, int) or isinstance(index, bool):
            raise TypeError('GameplayScripts index must be an integer')
        if index < 0 or index >= len(self._buffers):
            return None
        return C.addressof(self._buffers[index])

    @property
    def paths(self) -> tuple[Path, ...]:
        """Selected absolute paths in the exact order provided by the caller."""
        self._ensure_open()
        return self._paths

    @property
    def wire_paths(self) -> tuple[str, ...]:
        """Exact strings returned to native count/index consumers, in order."""
        self._ensure_open()
        return self._wire_paths

    def close(self) -> None:
        """Release pointer storage; repeated close is harmless."""
        if self._closed:
            return
        self._buffers = ()
        self._paths = ()
        self._wire_paths = ()
        self._closed = True

    def _ensure_open(self) -> None:
        if self._closed:
            raise RuntimeError('GameplayScripts registry is closed')

    def __enter__(self) -> 'NativeGameplayScriptRegistry':
        self._ensure_open()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()
