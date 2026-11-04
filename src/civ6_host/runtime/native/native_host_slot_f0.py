"""Source-backed completion of EXE notification counter scopes at host +0xF0."""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import hashlib
import json
from pathlib import Path
SPECIAL_CODE = 1520042793
INITIAL_NOTIFICATION_COUNTER = 0
INITIAL_METADATA_COUNTER = 0
_EVIDENCE_SHA256 = '31677501c8ae11322b27ad2aa5c9731ef9e58718ebee94631e2a9c7751c07901'
_EVIDENCE = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_host_slot_f0.py')))).resolve().parents[1] / 'evidence/native-host-slot-f0' / f'{_EVIDENCE_SHA256}.json'

def verify_source_pin() -> None:
    raw = _resolve_resource_path(_EVIDENCE).read_bytes()
    if hashlib.sha256(raw).hexdigest() != _EVIDENCE_SHA256:
        raise RuntimeError('Pinned host slot +0xF0 evidence changed')
    report = json.loads(raw)
    if report.get('schema') != 'civ6rl.native_host_slot_f0.static.v1' or report.get('images') != {'exe_sha256': 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63', 'core_sha256': 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'} or report['host_vtable']['target_va'] != '0x1401c9490' or (report['host_vtable']['implementation']['reachable_bytes_sha256'] != 'a6b9851de0f1a56682638a316f19007c4f7a01b5b6f6a319afab4d2374b4897a') or ([(g['va'], g['loader_initial_u32']) for g in report['globals']] != [('0x1422d7c6c', 0), ('0x1422d7c68', 0)]):
        raise RuntimeError('Pinned host slot +0xF0 identity/state contract changed')

def next_host_slot_f0_counters(event_code: int, notification_counter: int, metadata_counter: int) -> tuple[int, int]:
    """Return the two EXE DWORD states after void host_F0(this, event_code).

    This does not return the native callback's RAX. Core has already popped
    its own notification stack before calling the host; do not pop it again.
    Preserve metadata_counter when the predicate fails, including when the
    special event arrives with notification_counter zero.
    """
    verify_source_pin()
    for name, value in (('event_code', event_code), ('notification_counter', notification_counter), ('metadata_counter', metadata_counter)):
        if type(value) is not int or not 0 <= value <= 4294967295:
            raise ValueError(f'Host slot +0xF0 {name} must be uint32')
    if event_code == SPECIAL_CODE and notification_counter:
        decremented = notification_counter - 1
        return (decremented, decremented)
    return (notification_counter, metadata_counter)
__all__ = ['SPECIAL_CODE', 'INITIAL_NOTIFICATION_COUNTER', 'INITIAL_METADATA_COUNTER', 'next_host_slot_f0_counters', 'verify_source_pin']
