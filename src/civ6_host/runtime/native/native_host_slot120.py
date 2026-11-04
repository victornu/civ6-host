"""Host callback contract for EXE host vtable slot +0x120.

The native wrapper lazily obtains GameCoreController and returns its byte at
+0x0D, or zero when no controller exists. The current Python profile shares
controller state with the turn-status callback and requires that state to be
initialized before this getter is callable; it does not emulate the EXE's
lazy allocation path.
"""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import hashlib
import json
from pathlib import Path
_EVIDENCE_SHA256 = '390f3fe50aa1164633a834ad4dec0b91c7f0b331e12be7ce69050374d4947476'
_EVIDENCE_PATH = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_host_slot120.py')))).resolve().parents[1] / 'evidence' / 'native-host-slot120' / f'{_EVIDENCE_SHA256}.json'

def verify_source_pin() -> dict:
    raw = _resolve_resource_path(_EVIDENCE_PATH).read_bytes()
    if hashlib.sha256(raw).hexdigest() != _EVIDENCE_SHA256:
        raise RuntimeError('Pinned host slot +0x120 evidence changed')
    report = json.loads(raw)
    if report.get('schema') != 'civ6rl.native_host_slot120.static.v1' or report.get('host_vtable', {}).get('slot') != '0x120' or report.get('host_vtable', {}).get('target_va') != '0x1401c99c0':
        raise RuntimeError('Pinned host slot +0x120 source contract mismatch')
    return report

def initialize_fresh_controller_projection(turn_state):
    """Project the fresh constructor's queried byte, never replay a turn event.

    This does not allocate the EXE controller, its queues or mutex. It is an
    explicit diagnostic profile on a fresh process owner, not full lifecycle
    equivalence. Existing initialized state must never be reset through it.
    """
    from civ6_host.runtime.native.native_event_turn_status import TurnBeginAuxiliaryState
    if type(turn_state) is not TurnBeginAuxiliaryState or turn_state.controller_initialized is not False or turn_state.controller_byte_0d is not None or (turn_state.turn_values_by_thread != {}) or (type(turn_state.service_flags) is not int) or (turn_state.service_flags != 0):
        raise ValueError('Controller projection requires pristine owned state')
    proof = verify_source_pin()['host_vtable']
    ctor = proof['controller_constructor']
    getter = proof['controller_predicate']
    lazy = proof['controller_lazy_getter']
    if ctor['raw_sha256'] != '1e857c3048cbb91297aacc3cca163b37ccc8118fc08aea458f0c179de7ff00c3' or lazy['raw_sha256'] != '4745e2d2ef3fed920a3af86443247f6c0def3b69dc5f839ace1111402efbb307' or getter['raw_sha256'] != '57448557a187aba6fa24558d25f499f9e8396932da94cb4d9dc3fed1fd4f826e':
        raise ValueError('Fresh controller source bodies differ')
    rows = {r['va']: r for f in ctor['fragments'] for r in f['instructions']}
    instruction = bytes.fromhex(rows['0x1400f45b0']['bytes'])
    if instruction != bytes.fromhex('c7410c00000100'):
        raise ValueError('Fresh controller constructor field store differs')
    value = instruction[4]
    turn_state.controller_initialized = True
    turn_state.controller_byte_0d = value
    return dict(value=value, source_proof_sha256=_EVIDENCE_SHA256, source_store_va='0x1400f45b0', source_getter_va='0x1400f54f0', constructor_scalar_projection_only=True, full_controller_constructed=False, synthetic_turn_event=False, core_memory_written=False, eligible_for_training=False)

def host_slot120_result(turn_state) -> int:
    """Return the exact unsigned byte read from shared controller state.

    The Core caller's RDX argument is ignored by the captured EXE method.
    This headless API requires the owner state to have been initialized and
    refuses unknown lifecycle or values rather than allocating a controller.
    """
    verify_source_pin()
    from civ6_host.runtime.native.native_controller_state import NativeControllerTurnState
    if type(turn_state) is NativeControllerTurnState:
        return turn_state.read_native_flag()
    if getattr(turn_state, 'controller_initialized', None) is not True:
        raise ValueError('Host slot +0x120 controller state is not initialized')
    value = getattr(turn_state, 'controller_byte_0d', None)
    if type(value) is not int or not 0 <= value <= 255:
        raise ValueError('Host slot +0x120 controller byte +0x0D is unavailable')
    return value
__all__ = ['host_slot120_result', 'verify_source_pin', 'initialize_fresh_controller_projection']
