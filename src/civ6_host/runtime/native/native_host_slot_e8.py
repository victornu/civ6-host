"""Host-owned state transition for EXE host vtable slot +0xE8."""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
from pathlib import Path
from civ6_host.runtime.native.native_source_cache import load_pinned_json
SPECIAL_CODE = 1520042793
INITIAL_COUNTER = 0
_EVIDENCE_SHA256 = '811a4839412d53029d8b9078db8b1862a3d0121c0205efb6cc778430d532e44c'
_EVIDENCE_PATH = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_host_slot_e8.py')))).resolve().parents[1] / 'evidence' / 'native-host-slot-e8' / f'{_EVIDENCE_SHA256}.json'

def verify_source_pin() -> None:
    if not _EVIDENCE_SHA256:
        raise RuntimeError('Host slot +0xE8 source pin is not configured')
    report = load_pinned_json(_EVIDENCE_PATH, _EVIDENCE_SHA256)
    if report.get('schema') != 'civ6rl.native_host_slot_e8.static.v1' or report.get('host_vtable', {}).get('slot') != '0xe8' or report.get('host_vtable', {}).get('target_va') != '0x1401c93f0':
        raise RuntimeError('Pinned host slot +0xE8 source contract mismatch')

def next_host_slot_e8_counter(event_code: int, current_counter: int=INITIAL_COUNTER) -> int:
    """Return the exact updated DWORD counter for one host callback.

    The native method increments global DWORD 0x1422D7C6C iff event_code is
    0x5A9A0329. The DWORD is in the zero-filled virtual tail of PE .data, so
    the loader initializes it to zero. This return value models that global
    update; the native callback's RAX return is not meaningful.
    """
    verify_source_pin()
    for label, value in (('event_code', event_code), ('current_counter', current_counter)):
        if type(value) is not int or not 0 <= value <= 4294967295:
            raise ValueError(f'Invalid host slot +0xE8 {label}')
    if event_code == SPECIAL_CODE:
        return current_counter + 1 & 4294967295
    return current_counter
__all__ = ['SPECIAL_CODE', 'next_host_slot_e8_counter', 'verify_source_pin']
