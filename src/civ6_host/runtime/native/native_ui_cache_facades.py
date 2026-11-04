"""Source-pinned helper for the public UI-cache facade sequence.

This is an injected ABI adapter, not a DLL/EXE loader. The host must provide
checked memory reads, direct native calls, and the public-cache gate callback.
The EXE caller cadence is unknown, so construction and refresh are explicit.
"""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
from civ6_host.runtime.cache_facade_profiles import facade_abi
from civ6_host.runtime.cache_facade_profiles import verify_facade_source
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol
CORE_IMAGE_SHA256 = 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'
EXE_IMAGE_SHA256 = 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63'
EVIDENCE_PATH = 'evidence/native-ui-cache-facades/885d3cc44768bbab936a9ece70c96fe138fd6de46bce11f3697fe8769e368214.json'
EVIDENCE_SHA256 = '885d3cc44768bbab936a9ece70c96fe138fd6de46bce11f3697fe8769e368214'
EVIDENCE_SCHEMA = 'civ6rl.native_ui_cache_facades.static.v1'
FACTORY_EVIDENCE_PATH = 'evidence/native-ui-cache-factory-lifetime/6c7c09b7be4cfb57108703394d79cdf0dcddb79344c97a9dfd73efeb217cd9d3.json'
FACTORY_EVIDENCE_SHA256 = '6c7c09b7be4cfb57108703394d79cdf0dcddb79344c97a9dfd73efeb217cd9d3'
FACTORY_EVIDENCE_SCHEMA = 'civ6rl.native_ui_cache_factory_lifetime.static.v1'
OUTER_VTABLE_RVA = 7987232
GAME_FACADE_VTABLE_RVA = 7990488
CACHE_SERVICE_VTABLE_RVA = 7991792
SYSTEM_FACADE_VTABLE_RVA = 7994264
CACHE_B0_RESULT_VTABLE_RVA = 7992208
CACHE_C0_RESULT_VTABLE_RVA = 7992064
SLOTS = {'outer_release': 8, 'outer_game_facade': 160, 'outer_cache_service': 176, 'outer_system_facade': 208, 'facade_release': 8, 'game_publish': 56, 'cache_copy': 232, 'cache_b0': 176, 'cache_c0': 192, 'result_release': 8}
TARGET_RVAS = {(OUTER_VTABLE_RVA, 8): 1388640, (OUTER_VTABLE_RVA, 160): 4381904, (OUTER_VTABLE_RVA, 176): 4381968, (OUTER_VTABLE_RVA, 208): 4382096, (GAME_FACADE_VTABLE_RVA, 8): 4409168, (GAME_FACADE_VTABLE_RVA, 56): 4410928, (CACHE_SERVICE_VTABLE_RVA, 8): 4416608, (CACHE_SERVICE_VTABLE_RVA, 176): 4419344, (CACHE_SERVICE_VTABLE_RVA, 192): 4417472, (CACHE_SERVICE_VTABLE_RVA, 232): 4417088, (SYSTEM_FACADE_VTABLE_RVA, 8): 4434416, (CACHE_B0_RESULT_VTABLE_RVA, 8): 4420496, (CACHE_C0_RESULT_VTABLE_RVA, 8): 4419712}
OUTPUT_SIZE = 32
OUTPUT_WRITE_EXTENT = 28
OUTPUT_CANARY_START = OUTPUT_WRITE_EXTENT
OUTPUT_CANARY_SIZE = OUTPUT_SIZE - OUTPUT_CANARY_START
_CANARY = b'\xd3\xa7\\\xe1'

class CacheFacadeBackend(Protocol):
    """Minimal injection boundary; no process or binary loading is performed here."""
    core_base: int

    def context_alive(self) -> bool:
        ...

    def read_qword(self, address: int) -> int:
        ...

    def call(self, target: int, *arguments):
        ...

    def set_public_cache_gate(self, enabled: bool) -> None:
        ...

@dataclass(frozen=True)
class CacheRefreshResult:
    copied_value: int
    output: bytes

def _read(backend: CacheFacadeBackend, address: int) -> int:
    _require_live_context(backend)
    value = int(backend.read_qword(address))
    if value < 0 or value > 18446744073709551615:
        raise ValueError('Native memory reader returned a non-qword value')
    return value

def _verify_evidence_bytes(raw: bytes, expected_sha256: str=EVIDENCE_SHA256) -> dict:
    if not expected_sha256 or expected_sha256 == 'TO_BE_GENERATED':
        raise RuntimeError('UI cache facade evidence pin is not initialized')
    if hashlib.sha256(raw).hexdigest() != expected_sha256:
        raise RuntimeError('Immutable UI cache facade evidence hash mismatch')
    report = json.loads(raw)
    if report.get('schema') != EVIDENCE_SCHEMA:
        raise RuntimeError('Unexpected UI cache facade evidence schema')
    if report.get('core_image', {}).get('sha256') != CORE_IMAGE_SHA256:
        raise RuntimeError('UI cache facade evidence Core SHA mismatch')
    if report.get('exe_image', {}).get('sha256') != EXE_IMAGE_SHA256:
        raise RuntimeError('UI cache facade evidence EXE SHA mismatch')
    return report

def _verify_static_evidence() -> dict:
    root = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_ui_cache_facades.py')))).resolve().parents[1]
    path = root / EVIDENCE_PATH
    factory_path = root / FACTORY_EVIDENCE_PATH
    try:
        raw = _resolve_resource_path(path).read_bytes()
        factory_raw = _resolve_resource_path(factory_path).read_bytes()
    except OSError as exc:
        raise RuntimeError('Pinned immutable UI cache facade/factory evidence is missing') from exc
    report = _verify_evidence_bytes(raw)
    if hashlib.sha256(factory_raw).hexdigest() != FACTORY_EVIDENCE_SHA256:
        raise RuntimeError('Immutable UI cache factory evidence hash mismatch')
    factory = json.loads(factory_raw)
    if factory.get('schema') != FACTORY_EVIDENCE_SCHEMA:
        raise RuntimeError('Unexpected UI cache factory evidence schema')
    if factory.get('core_image', {}).get('sha256') != CORE_IMAGE_SHA256:
        raise RuntimeError('UI cache factory evidence Core SHA mismatch')
    return report

def _require_live_context(backend: CacheFacadeBackend) -> None:
    checker = getattr(backend, 'context_alive', None)
    if not callable(checker) or not checker():
        raise RuntimeError('Root GameCore context is not alive')

def _check_object(backend: CacheFacadeBackend, pointer: int, expected_vtable_rva: int, role: str) -> None:
    if not pointer or _read(backend, pointer) != backend.core_base + expected_vtable_rva:
        raise ValueError(f'Unexpected {role} vtable')

def _check_slot(backend: CacheFacadeBackend, vtable_rva: int, slot: int, *, core_sha256='d7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3') -> int:
    expected_rva = facade_abi(core_sha256).targets.get((vtable_rva, slot))
    if expected_rva is None:
        raise ValueError(f'Unpinned facade slot {vtable_rva:#x}+{slot:#x}')
    actual = _read(backend, backend.core_base + vtable_rva + slot)
    expected = backend.core_base + expected_rva
    if actual != expected:
        raise ValueError(f'Facade slot changed at {vtable_rva:#x}+{slot:#x}')
    return actual

def _invoke(backend: CacheFacadeBackend, receiver: int, vtable_rva: int, slot: int, *arguments, core_sha256='d7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'):
    _check_object(backend, receiver, vtable_rva, f'facade {vtable_rva:#x}')
    target = _check_slot(backend, vtable_rva, slot, core_sha256=core_sha256)
    return backend.call(target, receiver, *arguments)

class NativeUiCacheFacades:
    """Owns the captured A0/B0/D0 facade references and refreshed result refs.

    `outer_borrowed` is borrowed from the root context. Outer vtable +8 is a
    no-op, QueryInterface returns the same pointer without AddRef, and the
    exported factory creates a separate context rather than retaining this one.
    The backend's `context_alive()` must keep the root context owner alive through
    `close()`. Call `refresh()` explicitly; do not infer EXE cadence.
    """

    def __init__(self, backend: CacheFacadeBackend, outer_borrowed: int, *, core_sha256='d7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'):
        self.abi = facade_abi(core_sha256)
        if core_sha256 == 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3':
            _verify_static_evidence()
        else:
            verify_facade_source(backend, outer_borrowed, core_sha256=core_sha256)
        _require_live_context(backend)
        self.backend = backend
        self.outer = int(outer_borrowed)
        self.game_facade = 0
        self.cache_service = 0
        self.system_facade = 0
        self.cache_b0_result = 0
        self.cache_c0_result = 0
        self._closed = False
        _check_object(backend, self.outer, self.abi.outer_vtable_rva, 'outer Core facade')
        for slot in (160, 176, 208):
            _check_slot(backend, self.abi.outer_vtable_rva, slot, core_sha256=self.abi.core_sha256)
        try:
            self.game_facade = int(_invoke(backend, self.outer, self.abi.outer_vtable_rva, 160, core_sha256=self.abi.core_sha256) or 0)
            _check_object(backend, self.game_facade, self.abi.game_facade_vtable_rva, 'A0 game facade')
            self.cache_service = int(_invoke(backend, self.outer, self.abi.outer_vtable_rva, 176, core_sha256=self.abi.core_sha256) or 0)
            _check_object(backend, self.cache_service, self.abi.cache_service_vtable_rva, 'B0 cache service')
            self.system_facade = int(_invoke(backend, self.outer, self.abi.outer_vtable_rva, 208, core_sha256=self.abi.core_sha256) or 0)
            _check_object(backend, self.system_facade, self.abi.system_facade_vtable_rva, 'D0 system facade')
        except BaseException:
            try:
                self.close()
            except BaseException:
                pass
            raise

    def _release(self, pointer: int, vtable_rva: int) -> None:
        if pointer:
            _check_object(self.backend, pointer, vtable_rva, f'release target {vtable_rva:#x}')
            _invoke(self.backend, pointer, vtable_rva, 8, core_sha256=self.abi.core_sha256)

    def _replace_result(self, attribute: str, pointer: int, vtable_rva: int, role: str) -> None:
        pointer = int(pointer or 0)
        if pointer:
            _check_object(self.backend, pointer, vtable_rva, role)
        previous = getattr(self, attribute)
        setattr(self, attribute, pointer)
        if previous:
            self._release(previous, vtable_rva)

    def refresh(self, *, public_gate=True) -> CacheRefreshResult:
        if type(public_gate) is not bool:
            raise ValueError('Cache publication mode requires an exact Boolean')
        candidate = None
        if public_gate:
            if not self.abi.full_refresh_admitted:
                raise ValueError('Full public cache population is not qualified for this engine')
        else:
            candidate = self.backend.require_loaded_publication(self)
        if self._closed:
            raise RuntimeError('UI cache facades are closed')
        _require_live_context(self.backend)
        _invoke(self.backend, self.game_facade, self.abi.game_facade_vtable_rva, 56, 1, core_sha256=self.abi.core_sha256)
        result = self._copy_cache_outputs()
        if public_gate:
            self.backend.set_public_cache_gate(True)
        else:
            candidate.copy_returned(self.backend, self)
        return result

    def _copy_cache_outputs(self):
        if self._closed:
            raise RuntimeError('UI cache facades are closed')
        _require_live_context(self.backend)
        output = bytearray(b'\x00' * (OUTPUT_SIZE - OUTPUT_CANARY_SIZE) + _CANARY)
        copied_value = int(_invoke(self.backend, self.cache_service, self.abi.cache_service_vtable_rva, 232, output, core_sha256=self.abi.core_sha256) or 0)
        if len(output) < OUTPUT_SIZE:
            raise ValueError('Native UI cache output buffer is smaller than 0x20 bytes')
        if bytes(output[OUTPUT_CANARY_START:OUTPUT_SIZE]) != _CANARY:
            raise BufferError('Core cache copy wrote past its proven 0x1C-byte extent')
        b0_result = _invoke(self.backend, self.cache_service, self.abi.cache_service_vtable_rva, 176, core_sha256=self.abi.core_sha256)
        self._replace_result('cache_b0_result', b0_result, self.abi.cache_b0_result_vtable_rva, 'B0 result wrapper')
        c0_result = _invoke(self.backend, self.cache_service, self.abi.cache_service_vtable_rva, 192, core_sha256=self.abi.core_sha256)
        self._replace_result('cache_c0_result', c0_result, self.abi.cache_c0_result_vtable_rva, 'C0 result wrapper')
        return CacheRefreshResult(copied_value, bytes(output[:OUTPUT_WRITE_EXTENT]))

    def close(self) -> None:
        if self._closed:
            return
        try:
            _require_live_context(self.backend)
        except RuntimeError:
            self._closed = True
            self.cache_b0_result = 0
            self.cache_c0_result = 0
            self.game_facade = 0
            self.cache_service = 0
            self.system_facade = 0
            self.outer = 0
            raise
        self._closed = True
        first_error = None
        try:
            self.backend.set_public_cache_gate(False)
        except BaseException as exc:
            first_error = exc
        releases = (('cache_b0_result', self.abi.cache_b0_result_vtable_rva), ('cache_c0_result', self.abi.cache_c0_result_vtable_rva), ('game_facade', self.abi.game_facade_vtable_rva), ('cache_service', self.abi.cache_service_vtable_rva), ('system_facade', self.abi.system_facade_vtable_rva))
        for attribute, vtable_rva in releases:
            pointer = getattr(self, attribute)
            setattr(self, attribute, 0)
            if pointer:
                try:
                    self._release(pointer, vtable_rva)
                except BaseException as exc:
                    if first_error is None:
                        first_error = exc
        self.outer = 0
        if first_error is not None:
            raise first_error

    def __enter__(self) -> 'NativeUiCacheFacades':
        if self._closed:
            raise RuntimeError('UI cache facades are closed')
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()
