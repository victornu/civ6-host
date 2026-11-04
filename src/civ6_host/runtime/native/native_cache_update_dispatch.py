"""Invoke the proven Core keyed dispatcher for an EXE CacheUpdate payload.

This is the synchronous Core outer-vtable +0x198 route. It is not a cache
release operation and makes no lifecycle claim about snapshot IDs.
"""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import ctypes as C
import hashlib
import json
import struct
from pathlib import Path
_PROOF = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_cache_update_dispatch.py')))).resolve().parents[1] / 'evidence' / 'native-cache-update-core-dispatch.json'
_PROOF_SHA256 = '50be75c1e881a25bea0f3dc1df2dd217451d31e74b3b78f2e2525703b9b2e059'
_OUTER_VTABLE_RVA = 7987232
_DISPATCH_SLOT = 408
_DISPATCH_RVA = 4388432
_PAYLOAD_SIZE = 20

def _validate_proof() -> None:
    from civ6_host.runtime.native.native_source_cache import load_pinned_json
    proof = load_pinned_json(_PROOF, _PROOF_SHA256)
    if proof.get('schema') != 'civ6rl.native_cache_update_core_dispatch.static.v1' or proof.get('images', {}).get('core_sha256') != 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3' or proof.get('core_outer_slot', {}).get('slot') != '0x198' or (proof.get('core_outer_slot', {}).get('target') != hex(_DISPATCH_RVA + 6442450944)):
        raise RuntimeError('Unsupported CacheUpdate Core-dispatch evidence')

def _native_reader():
    from civ6_host.runtime.native.native_setup import local_reader
    return local_reader()

def dispatch_cache_update_payload(core_base: int, context: int, payload: bytes, *, read_memory=None, invoke=None, core_sha256='d7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3') -> tuple[int, int, int, int]:
    """Synchronously dispatch the four DWORDs copied by EXE callback 0x14014A9F0.

    ``payload`` is the 20-byte CacheUpdate payload at record+0x50. The first
    DWORD is the queue sequence (the writer overwrote the producer's zero).
    The EXE callback copies DWORDs +4 through +0x10 into its local callback
    array and calls outer slot +0x198. The returned tuple is provided for
    diagnostics; Core's dispatcher returns void.

    ``read_memory`` and ``invoke`` are narrow seams for pure tests. Production
    callers omit them; native dispatch is synchronous and uses the current
    process reader. The caller retains ownership of ``context``.
    """
    from civ6_host.runtime.cache_update_profiles import dispatch_abi
    from civ6_host.runtime.cache_update_profiles import verify_dispatch_live
    abi = dispatch_abi(core_sha256)
    if core_sha256 == 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3':
        _validate_proof()
    if type(core_base) is not int or core_base <= 0 or type(context) is not int or (context <= 0):
        raise ValueError('Invalid Core base or outer context pointer')
    if not isinstance(payload, (bytes, bytearray, memoryview)) or len(payload) != _PAYLOAD_SIZE:
        raise ValueError('CacheUpdate payload must be exactly 20 bytes')
    _, context_arg, zero_word, selector, snapshot_id = struct.unpack('<IIIII', payload)
    args = (context_arg, zero_word, selector, snapshot_id)
    if read_memory is None:
        read_memory = _native_reader()
    if core_sha256 != 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3':
        verify_dispatch_live(core_base, context, read_memory, core_sha256=core_sha256, registry_key=context_arg)
    outer_vtable, = struct.unpack('<Q', read_memory(context, 8))
    expected_vtable = core_base + abi.outer_vtable_rva
    if outer_vtable != expected_vtable:
        raise ValueError('Unexpected GameCore outer-context vtable')
    target, = struct.unpack('<Q', read_memory(outer_vtable + _DISPATCH_SLOT, 8))
    expected_target = core_base + abi.dispatch_rva
    if target != expected_target:
        raise ValueError('Unexpected Core outer +0x198 dispatch target')
    native_args = (C.c_uint32 * 4)(*args)
    if invoke is None:
        call_type = getattr(C, 'WINFUNCTYPE', C.CFUNCTYPE)
        function = call_type(None, C.c_void_p, C.POINTER(C.c_uint32))(target)
        function(context, native_args)
    else:
        invoke(target, context, native_args)
    return args
