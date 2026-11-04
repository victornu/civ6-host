"""Production-bound adapter for the source-pinned B0 cache-service +0x90 call.

This forwards an exact signed-coordinate pair to the native method and returns
its EAX index together with the pair that the native method wrote back. It
never computes a map index in Python; admission remains guarded by the caller's
source-verified facade, thread, input, and receiver preflight.
"""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import ctypes as C
import hashlib
import json
from pathlib import Path
import struct
PROOF_SHA256 = 'c65198a8cfd6f4c900a41607c74f9d56e58d2d8d276682779c69a0a2bd15f104'
PROOF_PATH = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_36c9b2b4_cache_position_query.py')))).resolve().parents[1] / 'evidence/native-cache-service-position-index' / f'{PROOF_SHA256}.json'
CORE_SHA256 = 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'
CORE_BASE = 6442450944
SERVICE_VTABLE_RVA = 7991792
SERVICE_POSITION_INDEX_RVA = 4419104
POSITION_METHOD_SHA256 = '3690594a176e51489e7e1fe7835ba623e3b75aeaf7eafbe3604367d2e8c62135'
NORMALIZATION_HELPER_SHA256 = 'db91d6ea7adb9cc022eba44c174fced557ba0b0599a93163521768c58e7be805'

def verify_source_evidence() -> dict:
    raw = _resolve_resource_path(PROOF_PATH).read_bytes()
    if hashlib.sha256(raw).hexdigest() != PROOF_SHA256:
        raise RuntimeError('Immutable cache-service position-index evidence hash mismatch')
    proof = json.loads(raw)
    binding = proof.get('binding', {})
    if proof.get('schema') != 'civ6rl.native_cache_service_position_index.static.v1' or proof.get('images', {}).get('core_sha256') != CORE_SHA256 or binding.get('vtable_va') != '0x18079f1f0' or (binding.get('slot_offset') != '0x90') or (binding.get('slot_bytes') != '206e438001000000') or (binding.get('target_va') != '0x180436e20') or (binding.get('normalization_helper_va') != '0x180436b80') or (proof.get('producer_callsite', {}).get('instruction_va') != '0x14014a0cf'):
        raise RuntimeError('Unexpected cache-service +0x90 evidence contract')
    return proof

def _captured_code(body):
    return b''.join((bytes.fromhex(ins['bytes']) for frag in body['fragments'] for ins in frag['instructions']))

def _signed32(value, label):
    if type(value) is not int or not -(1 << 31) <= value < 1 << 31:
        raise ValueError(f'{label} must be an exact signed 32-bit integer')
    return value

def query_native_position_index(core, facades, position, *, read=None, native_api=None):
    """Return `(native_EAX, native_x, native_y)` for a borrowed coordinate pair.

    The injected API receives `(target_va, cache_service, pair_buffer_address)`.
    Its implementation must perform the reviewed native ABI call. The default
    path uses the Windows x64 ABI directly; tests use a seam that supplies a
    predetermined native result and pair mutation.
    """
    verify_source_evidence()
    if type(position) not in (tuple, list) or len(position) != 2:
        raise ValueError('Position must be a two-coordinate tuple/list')
    x, y = (_signed32(position[0], 'x'), _signed32(position[1], 'y'))
    base = getattr(core, '_handle', None)
    if type(base) is not int or base <= 0:
        raise ValueError('A live Core handle is required')
    backend = getattr(facades, 'backend', None)
    service = getattr(facades, 'cache_service', None)
    if backend is None or type(service) is not int or service <= 0 or (getattr(backend, 'core_base', None) != base):
        raise ValueError('The retained B0 facade does not belong to this Core handle')
    if not callable(getattr(backend, 'context_alive', None)) or backend.context_alive() is not True:
        raise RuntimeError('The retained B0 facade must belong to a live Core context')
    reader = read if read is not None else getattr(backend, 'read', None)
    if not callable(reader):
        raise ValueError('A checked native memory reader is required')

    def qword(address):
        raw = reader(address, 8)
        if type(raw) is not bytes or len(raw) != 8:
            raise ValueError('Native facade query requires exact qword reads')
        return struct.unpack('<Q', raw)[0]
    if qword(service) != base + SERVICE_VTABLE_RVA:
        raise ValueError('Cache service vtable identity changed')
    slot_address = base + SERVICE_VTABLE_RVA + 144
    if qword(slot_address) != base + SERVICE_POSITION_INDEX_RVA:
        raise ValueError('Cache service +0x90 target changed')
    proof = verify_source_evidence()
    method_bytes = _captured_code(proof['binding']['target_body'])
    helper_bytes = _captured_code(proof['binding']['normalization_helper'])
    if hashlib.sha256(method_bytes).hexdigest() != POSITION_METHOD_SHA256:
        raise RuntimeError('Pinned +0x90 method byte hash changed')
    if hashlib.sha256(helper_bytes).hexdigest() != NORMALIZATION_HELPER_SHA256:
        raise RuntimeError('Pinned coordinate helper byte hash changed')
    method_live = reader(base + SERVICE_POSITION_INDEX_RVA, len(method_bytes))
    helper_live = reader(base + 4418432, len(helper_bytes))
    if type(method_live) is not bytes or method_live != method_bytes:
        raise ValueError('Live +0x90 method bytes differ from the pinned body')
    if type(helper_live) is not bytes or helper_live != helper_bytes:
        raise ValueError('Live coordinate helper bytes differ from the pinned body')
    pair = (C.c_int32 * 2)(x, y)
    target = base + SERVICE_POSITION_INDEX_RVA
    if native_api is None:
        result = C.WINFUNCTYPE(C.c_uint32, C.c_void_p, C.c_void_p)(target)(service, C.addressof(pair))
    else:
        if type(native_api) is not dict or set(native_api) != {'call_position_index'} or (not callable(native_api['call_position_index'])):
            raise ValueError('Native query seam must expose only call_position_index')
        result = native_api['call_position_index'](target, service, C.addressof(pair))
    if getattr(core, '_handle', None) != base or getattr(facades, 'backend', None) is not backend or getattr(backend, 'core_base', None) != base or (getattr(facades, 'cache_service', None) != service) or (backend.context_alive() is not True):
        raise RuntimeError('Core context or retained B0 facade changed during +0x90 call')
    if qword(service) != base + SERVICE_VTABLE_RVA or qword(slot_address) != target:
        raise RuntimeError('Retained B0 facade identity changed during +0x90 call')
    if type(result) is not int or not 0 <= result <= 4294967295:
        raise ValueError('Native +0x90 method must return its exact EAX DWORD')
    return (result, int(pair[0]), int(pair[1]))
