"""Call the retained native Game facade used by EXE F1420, without guessing its value."""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import ctypes as C
import hashlib
from pathlib import Path
import struct
from civ6_host.runtime.native.native_source_cache import load_pinned_json
from civ6_host.runtime.native.native_ui_cache_facades import CORE_IMAGE_SHA256
from civ6_host.runtime.native.native_ui_cache_facades import EXE_IMAGE_SHA256
from civ6_host.runtime.native.native_ui_cache_facades import GAME_FACADE_VTABLE_RVA
PINNED_EVIDENCE_SHA256 = '2763ab2aecf67a5d38f789e28190b5e5ab8ff2dfb1424a0d36209f59a3314710'
_PROOF = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_retained_game_getter.py')))).resolve().parents[1] / 'evidence/native-retained-game-getter-f1420.json'
GETTER_SLOT, GETTER_RVA = (296, 4410112)
GETTER_CODE_SHA256 = '2210e968337657725a73dad2d9c5e0d7f0423e2521a3dfa1f291b3e51579a989'
CACHE_OWNER_VTABLE_RVA = 7760496

def verify_source_evidence():
    proof = load_pinned_json(_PROOF, PINNED_EVIDENCE_SHA256)
    if proof.get('schema') != 'civ6rl.native_retained_game_getter_f1420.static.v1' or proof['images']['exe']['sha256'] != EXE_IMAGE_SHA256 or proof['images']['core']['sha256'] != CORE_IMAGE_SHA256 or (proof['sources']['game_facade_vtable']['target_va'] != '0x180434b00') or (proof['sources']['game_facade_vtable']['slot_offset'] != '0x128') or (proof['sources']['slot_128_target_leaf']['length'] != 28) or (proof['sources']['slot_128_target_leaf']['raw_sha256'] != GETTER_CODE_SHA256) or (proof['sources']['F1420_helper']['raw_sha256'] != '30284832b08c3cec8353ec5c1c7e9aae01336fc38f3600f49e2194ff60b34720'):
        raise RuntimeError('Retained Game getter source contract changed')
    return proof

def _invoke_signed_getter(target, receiver):
    return int(C.WINFUNCTYPE(C.c_int32, C.c_void_p)(target)(receiver))

def read_retained_game_value(facades, read, *, invoke=None, core_sha256='d7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'):
    """Borrow the existing A0 facade; never create another one or return a default.

    The admitted constructor path has facade+8 null and facade+10 pointing to
    Cache_Game_Instance. The method remains a real native call; the owner field
    value is not read/reimplemented in Python and is not labeled LocalPlayer.
    """
    from civ6_host.runtime.retained_game_source import getter_abi
    abi = getter_abi(core_sha256)
    if core_sha256 == 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3':
        verify_source_evidence()
    if facades is None or facades._closed or (not facades.backend.context_alive()):
        raise RuntimeError('Retained Game facade is absent, closed or outlived its context')
    backend = facades.backend
    base, receiver = (backend.core_base, facades.game_facade)

    def qword(address):
        raw = read(address, 8)
        if type(raw) is not bytes or len(raw) != 8:
            raise ValueError('Retained Game getter requires an exact qword read')
        return struct.unpack('<Q', raw)[0]
    if not receiver or qword(receiver) != base + abi.facade_vtable_rva:
        raise ValueError('Unexpected retained Game facade vtable')
    if qword(receiver + 8) != 0:
        raise ValueError('Unadmitted live-object branch of retained Game facade')
    owner = qword(receiver + 16)
    if not owner or qword(owner) != base + abi.owner_vtable_rva:
        raise ValueError('Unexpected retained Game cache owner')
    target = qword(base + abi.facade_vtable_rva + abi.getter_slot)
    if target != base + abi.getter_rva:
        raise ValueError('Retained Game +128 slot changed')
    if hashlib.sha256(read(target, abi.getter_length)).hexdigest() != abi.getter_sha256:
        raise ValueError('Retained Game getter code differs from pinned native leaf')
    if not backend.context_alive():
        raise RuntimeError('Retained Game facade context closed before native call')
    value = (_invoke_signed_getter if invoke is None else invoke)(target, receiver)
    if type(value) is not int or not -(1 << 31) <= value < 1 << 31:
        raise ValueError('Retained Game getter returned a non-signed-DWORD result')
    return value
