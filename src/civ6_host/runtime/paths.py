"""Resolve the explicitly configured private host resource directory.

The launcher must set ``CIV6_HOST_RESOURCE_ROOT`` before importing the native
backend. The first successful call freezes its canonical path for this process;
use a separate process for a different resource root.
"""
from __future__ import annotations

import os
from pathlib import Path
import threading

_ENV_NAME = "CIV6_HOST_RESOURCE_ROOT"
_IMPORTED_RESOURCE_ROOT_VALUE = os.environ.get(_ENV_NAME)
_RESOURCE_ROOT: Path | None = None
_RESOURCE_ROOT_LOCK = threading.Lock()


def _resolve_configured_root(value: str | None) -> Path:
    if value is None or not value.strip():
        raise RuntimeError(f"{_ENV_NAME} is required")
    configured = Path(value)
    if not configured.is_absolute():
        raise ValueError(f"{_ENV_NAME} must be an absolute path")
    try:
        resolved = configured.resolve(strict=True)
    except (OSError, RuntimeError, ValueError) as exc:
        raise ValueError(f"{_ENV_NAME} must name an existing directory") from exc
    if not resolved.is_dir():
        raise ValueError(f"{_ENV_NAME} must name an existing directory")
    return resolved


def resource_root() -> Path:
    """Return the canonical configured resource root, frozen per process.

    There is deliberately no cwd, installed-package, or lab-directory fallback.
    After the first successful resolution, changing or removing the environment
    setting fails closed instead of redirecting a running backend.
    """
    global _RESOURCE_ROOT
    with _RESOURCE_ROOT_LOCK:
        value = os.environ.get(_ENV_NAME)
        if value != _IMPORTED_RESOURCE_ROOT_VALUE:
            raise RuntimeError(f"{_ENV_NAME} must be set before importing the backend and remain unchanged")
        if _RESOURCE_ROOT is None:
            _RESOURCE_ROOT = _resolve_configured_root(_IMPORTED_RESOURCE_ROOT_VALUE)
            return _RESOURCE_ROOT
        try:
            current = _resolve_configured_root(_IMPORTED_RESOURCE_ROOT_VALUE)
        except (OSError, RuntimeError, ValueError) as exc:
            raise RuntimeError(f"{_ENV_NAME} changed after the resource root was fixed") from exc
        if current != _RESOURCE_ROOT:
            raise RuntimeError(f"{_ENV_NAME} changed after the resource root was fixed")
        return _RESOURCE_ROOT


__all__ = ["resource_root"]
