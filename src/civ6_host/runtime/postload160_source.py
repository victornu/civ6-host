"""Source-checked outer+160 dispatch, separate from runnable XP1 postload.

The XP1 route reaches a real AutoPlay transition and AUX category 2. Its source
identity is useful independently; loaded facades and that service are still
missing admission prerequisites. This module never loads or calls a DLL.
"""
from dataclasses import dataclass
import hashlib
import struct
from types import MappingProxyType

from .configuration_profiles import BASE_CORE_SHA256, XP1_CORE_SHA256, XP2_CORE_SHA256, _source, _body
from .a0_family_source import _path, verify_pinned_files


SOURCE = ('work/host-extensions/xp1-postload-static/xp1-postload160-source-v1.json',
          '4c65885ed0199937bd7a8d351f8abccd6e13ec7e4c4bcaa63351f89ea8d320b3')
EXE_SHA256 = 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63'
CORE_IMAGE_BASE = 0x180000000


@dataclass(frozen=True)
class Post160ABI:
    core_sha256: str
    outer_vtable_rva: int
    outer_slot: int
    target_rva: int
    inner_vtable_rva: int
    inner_slot: int
    inner_target_rva: int


_PROFILES = MappingProxyType({
    BASE_CORE_SHA256: Post160ABI(BASE_CORE_SHA256, 0x79E020, 0x160, 0x42E4C0,
                               0x7C7078, 0x60, 0x3C250),
    XP1_CORE_SHA256: Post160ABI(XP1_CORE_SHA256, 0x8A8DF0, 0x160, 0x4BD5C0,
                              0x8D7168, 0x60, 0x3D300),
    XP2_CORE_SHA256: Post160ABI(XP2_CORE_SHA256,0xa101e8,0x160,0x590780,
                              0xa44f70,0x60,0x463a0),
})


def profile_for_sha(core_sha256):
    if type(core_sha256) is not str or core_sha256 not in _PROFILES:
        raise ValueError('Unqualified outer+160 engine')
    return _PROFILES[core_sha256]


def require_runtime_admission(profile):
    if type(profile) is not Post160ABI or _PROFILES.get(profile.core_sha256) is not profile:
        raise ValueError('Post160 requires its canonical source profile')
    if profile.core_sha256 != BASE_CORE_SHA256:
        engine='XP2' if profile.core_sha256==XP2_CORE_SHA256 else 'XP1'
        raise ValueError(engine+' outer+160 is not admitted: loaded cache facade publication, '
                         'AUX+90 category2/NULL and transitive Player/scheduler effects remain unqualified')
    return profile


def xp1_source(core_sha256=XP1_CORE_SHA256):
    if profile_for_sha(core_sha256).core_sha256 != XP1_CORE_SHA256:
        raise ValueError('Exact XP1 source required')
    proof = _source(SOURCE)
    c = proof['contract']
    abi = _PROFILES[XP1_CORE_SHA256]
    if (proof['schema'] != 'civ6_host.xp1_postload160.static.v1'
            or any(proof[name] is not False for name in ('native_execution','process_memory_read','product_modified'))
            or proof['images']['xp1']['sha256'] != XP1_CORE_SHA256
            or proof['images']['exe']['sha256'] != EXE_SHA256
            or c['core_sha256'] != XP1_CORE_SHA256 or c['exe_sha256'] != EXE_SHA256
            or c['signature'] != 'void-like(void *outer_this, uint8 flag)'
            or c['argument'] != 1 or c['native_return_ignored'] is not True
            or any(c[name] is not False for name in ('full_load_admitted','public_cache_admitted','post160_runtime_admitted'))
            or tuple(c[name] for name in ('outer_vtable_rva','outer_slot','outer_target_rva',
                'inner_offset','inner_vtable_rva','inner_slot','inner_target_rva','game_offset',
                'game_forward_rva','transition_rva')) !=
                (abi.outer_vtable_rva,abi.outer_slot,abi.target_rva,8,abi.inner_vtable_rva,
                 abi.inner_slot,abi.inner_target_rva,0x60,0x558830,0x39400)):
        raise ValueError('XP1 outer+160 source contract changed')
    callback = c['callback']
    if (callback['wrapper_rva'] != 0x22EF0 or callback['auxiliary_slot'] != 0x90
            or callback['raw_kind'] != 1 or callback['category'] != 2
            or callback['arguments'] is not None or callback['own_core_scope_bracketing'] is not True
            or tuple(callback['events']) != ('AutoPlayStart','AutoPlayEnd')):
        raise ValueError('XP1 post160 callback scope changed')
    transition = proof['functions']['xp1']['transition']
    if (transition['boundary_method'] != 'complete-runtime-function-chained-unwind-root-v2'
            or transition['fragment_count'] != 7 or transition['total_length'] != 469
            or set(proof['functions']['xp1']) != {'outer160','inner60','game_forward','tail1','tail2','transition','aux_scope'}):
        raise ValueError('XP1 post160 complete body coverage changed')
    for body in proof['functions']['xp1'].values():
        _body(body)
    pins = {str(_path(r['path'])):r['sha256'] for r in proof['references'].values()}
    pins.update({str(_path(path)):digest for path,digest in proof['source_pins'].items()})
    verify_pinned_files(pins)
    return proof


def source_pins(core_sha256=XP1_CORE_SHA256):
    if core_sha256==XP2_CORE_SHA256:
        from .xp2_postload_source import source_dependencies
        pins=source_pins(XP1_CORE_SHA256)  # Common EXE calling/transport ancestry.
        pins.update(source_dependencies())
        return pins
    if core_sha256!=XP1_CORE_SHA256:raise ValueError('Unknown expansion post160 source')
    proof = xp1_source()
    pins = {str(_path(SOURCE[0])):SOURCE[1]}
    pins.update({str(_path(r['path'])):r['sha256'] for r in proof['references'].values()})
    pins.update({str(_path(path)):digest for path,digest in proof['source_pins'].items()})
    return pins


def expansion_source(core_sha256=XP1_CORE_SHA256):
    if core_sha256==XP2_CORE_SHA256:
        from .xp2_postload_source import source
        return source()
    return xp1_source(core_sha256)


def verify_expansion_live(base,read,proof,*,core_sha256):
    if core_sha256==XP2_CORE_SHA256:
        from .xp2_postload_source import verify_live
        return verify_live(base,read,proof,core_sha256=core_sha256)
    return verify_xp1_live(base,read,proof,core_sha256=core_sha256)


def verify_xp1_live(base, read, proof, *, core_sha256):
    """Compare the complete bounded native route; never dispatch or infer state.

    Runtime admission must already have refused an unqualified XP1 owner. This
    checker does not make loaded caches, a nil category or inactive flags true.
    """
    if (core_sha256 != XP1_CORE_SHA256 or type(base) is not int or base < 65536
            or base % 65536 or base > (1 << 47) - 0x10000000 or not callable(read)):
        raise ValueError('Invalid XP1 post160 image or reader')
    if proof != xp1_source(core_sha256):
        raise ValueError('XP1 post160 proof is not the retained complete route')
    for body in proof['functions']['xp1'].values():
        for fragment in _body(body)['fragments']:
            for row in fragment['instructions']:
                raw = bytes.fromhex(row['bytes'])
                rva = int(row['va'],16) - CORE_IMAGE_BASE
                if rva < 0 or read(base+rva,len(raw)) != raw:
                    raise ValueError('XP1 post160 instruction differs at ' + hex(rva))
    for row in proof['tables']['xp1'].values():
        raw = read(base+row['vtable_rva']+row['slot'],8)
        if raw != struct.pack('<Q',base+row['target_rva']):
            raise ValueError('XP1 post160 virtual dispatch target differs')
    for address, literal in proof['literals'].items():
        raw = read(base+int(address,16)-CORE_IMAGE_BASE,literal['bytes'])
        if type(raw) is not bytes or len(raw) != literal['bytes'] or hashlib.sha256(raw).hexdigest() != literal['sha256']:
            raise ValueError('XP1 post160 event literal differs')
