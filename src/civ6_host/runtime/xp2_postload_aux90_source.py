"""Exact XP2 Core source and live-memory guard for the post-load AUX+90 wrapper.

This validates the callback route only. It does not call Post160, admit a saved
game, or qualify the transitive Player/scheduler effects of the transition.
"""
from __future__ import annotations

import hashlib
from collections.abc import Mapping
from pathlib import Path
import struct

from .configuration_profiles import _source
from .paths import resource_root
from .resource_resolution import resolve_path
from .saved_load_profiles import XP2_CORE_SHA256

SOURCE = ('work/host-extensions/xp2-postload160-static/source-profile-v1.json',
          '1ec775a5195ce5bab1a6a5e7da17737d7bd80763e552c3f2b24200b54bd6eb7e')
EXE_SHA256 = 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63'
PREFERRED_BASE = 0x180000000
AUX_SCOPE_RVA = 0x26780
AUX_SCOPE_LENGTH = 145
AUX_SCOPE_SHA256 = 'f7dff3a270a88a44f2ba934a04953fd7b8987067716075ac43f06f4fc2ad029d'
HOST_GLOBAL_RVA = 0xB8AA80
AUX_GLOBAL_RVA = 0xB8AA88


def _body_bytes(body):
    raw = bytes.fromhex(body['raw_hex'])
    if (len(raw) != AUX_SCOPE_LENGTH or body.get('rva') != hex(AUX_SCOPE_RVA)
            or body.get('bytes') != AUX_SCOPE_LENGTH
            or hashlib.sha256(raw).hexdigest() != AUX_SCOPE_SHA256
            or body.get('sha256') != AUX_SCOPE_SHA256
            or body.get('boundary_method') != 'complete-runtime-function-chained-unwind-root-v2'
            or body.get('all_conditional_targets_captured') is not True):
        raise ValueError('XP2 AUX90 complete wrapper body differs')
    fragments = body.get('fragments')
    if not isinstance(fragments, (list, tuple)) or len(fragments) != 1:
        raise ValueError('XP2 AUX90 wrapper fragment coverage differs')
    fragment = fragments[0]
    part = bytes.fromhex(fragment['raw_hex'])
    if (fragment.get('start_rva') != hex(AUX_SCOPE_RVA)
            or fragment.get('length') != AUX_SCOPE_LENGTH
            or fragment.get('sha256') != AUX_SCOPE_SHA256
            or hashlib.sha256(part).hexdigest() != AUX_SCOPE_SHA256
            or part != raw
            or ''.join(row['bytes'] for row in fragment['instructions']) != raw.hex()):
        raise ValueError('XP2 AUX90 wrapper instructions do not cover the exact bytes')
    return raw


def source():
    proof = _source(SOURCE)
    c = proof.get('contract', {})
    callback = c.get('callback', {})
    expected_callback = {
        'wrapper_rva': AUX_SCOPE_RVA,
        'auxiliary_slot': 0x90,
        'raw_kind': 1,
        'category': 2,
        'arguments': None,
        'events': ('AutoPlayStart', 'AutoPlayEnd'),
        'own_core_scope_bracketing': True,
        'host_global_rva': HOST_GLOBAL_RVA,
        'host_owned_slot': 0x30,
        'host_release_slot': 0x38,
        'host_acquire_slot': 0x40,
        'signature': 'uint8(void *auxiliary, uint32 raw_kind, char const *name, void *arguments)',
        'result': 'native AUX AL preserved across optional Core-owned lock reacquire',
    }
    if (proof.get('schema') != 'civ6-host.xp2-postload160.source.v1'
            or proof.get('native_execution') is not False
            or proof.get('process_memory_read') is not False
            or proof.get('core_sha256') != XP2_CORE_SHA256
            or proof.get('exe_sha256') != EXE_SHA256
            or c.get('core_sha256') != XP2_CORE_SHA256
            or c.get('exe_sha256') != EXE_SHA256
            or callback != expected_callback
            or proof.get('contract', {}).get('full_load_admitted') is not False
            or proof.get('contract', {}).get('public_cache_admitted') is not False
            or proof.get('contract', {}).get('post160_runtime_admitted') is not False):
        raise ValueError('XP2 AUX90 source profile contract differs')
    body = proof.get('functions', {}).get('xp2', {}).get('aux_scope')
    if not isinstance(body, Mapping):
        raise ValueError('XP2 AUX90 wrapper body is missing')
    _body_bytes(body)
    return proof


def source_dependencies():
    """Return verified path-to-SHA pins for the exact profile and its sources."""
    proof = source()
    rows = [{'path': SOURCE[0], 'sha256': SOURCE[1]}]
    refs = proof.get('references')
    if not isinstance(refs, (list, tuple)):
        raise ValueError('XP2 AUX90 source references are missing')
    rows.extend(refs)
    pins = {}
    root = resource_root().resolve()
    for row in rows:
        relative = Path(row['path'].replace('\\', '/'))
        if relative.is_absolute() or '..' in relative.parts:
            raise ValueError('XP2 AUX90 source dependency escaped the resource root')
        path = resolve_path(root / relative).resolve()
        if not path.is_relative_to(root):
            raise ValueError('XP2 AUX90 source dependency escaped the resource root')
        digest = row['sha256']
        if type(digest) is not str or len(digest) != 64:
            raise ValueError('XP2 AUX90 source dependency digest is invalid')
        if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError('XP2 AUX90 source dependency changed: ' + str(path))
        key = str(path)
        if key in pins and pins[key] != digest:
            raise ValueError('Conflicting XP2 AUX90 source dependency pins')
        pins[key] = digest
    return pins


def verify_xp2_live(base, read, *, host_pointer, auxiliary_pointer, proof=None):
    """Check exact wrapper bytes and the Core host-global identity; no call made."""
    if (type(base) is not int or base < 65536 or base % 65536
            or base > (1 << 47) - 0x1000000 or not callable(read)
            or type(host_pointer) is not int or not 0 < host_pointer < (1 << 47)
            or type(auxiliary_pointer) is not int or not 0 < auxiliary_pointer < (1 << 47)):
        raise ValueError('Invalid XP2 AUX90 image, reader or host pointer')
    selected = source()
    if proof is not None and proof != selected:
        raise ValueError('XP2 AUX90 proof is not the retained exact source')
    body = selected['functions']['xp2']['aux_scope']
    expected = _body_bytes(body)
    actual = read(base + AUX_SCOPE_RVA, AUX_SCOPE_LENGTH)
    if type(actual) is not bytes or actual != expected:
        raise ValueError('XP2 AUX90 live wrapper bytes differ from the retained source')
    raw_host = read(base + HOST_GLOBAL_RVA, 8)
    if type(raw_host) is not bytes or len(raw_host) != 8 or struct.unpack('<Q', raw_host)[0] != host_pointer:
        raise ValueError('XP2 AUX90 Core host-global owner differs')
    raw_auxiliary = read(base + AUX_GLOBAL_RVA, 8)
    if (type(raw_auxiliary) is not bytes or len(raw_auxiliary) != 8
            or struct.unpack('<Q', raw_auxiliary)[0] != auxiliary_pointer):
        raise ValueError('XP2 AUX90 Core auxiliary-global owner differs')
    return dict(source_sha256=SOURCE[1], core_sha256=XP2_CORE_SHA256,
                wrapper_rva=AUX_SCOPE_RVA, wrapper_sha256=AUX_SCOPE_SHA256,
                host_global_rva=HOST_GLOBAL_RVA, host_pointer=host_pointer,
                auxiliary_global_rva=AUX_GLOBAL_RVA, auxiliary_pointer=auxiliary_pointer,
                native_calls_made=False, saved_game_load_admitted=False)
