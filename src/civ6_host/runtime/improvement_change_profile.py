"""Selected XP1 notifications using the existing A625 and 5D plot queries."""
from dataclasses import dataclass
from functools import lru_cache
from types import MappingProxyType
import re
from .configuration_profiles import BASE_CORE_SHA256,XP1_CORE_SHA256,XP2_CORE_SHA256,_source,_body

SOURCE=('work/host-extensions/xp1-improvement-change-static/source-v1.json',
        'e28fa6ba5cac066fd8aa2b567f2a22845c3a8acd1e7279dab83f810401ab9b85')
KINDS={0x30ae2a3d:144,0x7b65ff2e:153}
SIZES={144:144,153:128}


def rows(value):return tuple(r for f in _body(value)['fragments'] for r in f['instructions'])


@lru_cache(maxsize=1)
def verify_source():
    from .native import native_event_30ae2a3d as improvement,native_event_7b65ff2e as route
    from .native.native_host_event_registry import EXE_EVENT_CALLBACKS
    from .turn_unit_event_profile import verify_source as turn_source
    p=_source(SOURCE)
    if (p['schema']!='civ6-host.xp1-improvement-route.source.v1' or p['native_execution'] is not False
            or p['image']['sha256']!=XP1_CORE_SHA256
            or p['validation']['all_instruction_bytes_match_image'] is not True
            or p['validation']['exact_keys_and_native_dispatch_before_host'] is not True
            or EXE_EVENT_CALLBACKS[0x30ae2a3d]!=0x148fc0 or EXE_EVENT_CALLBACKS[0x7b65ff2e]!=0x152710):
        raise ValueError('XP1 improvement/route source identity changed')
    for ref in p['references']:_source((ref['path'],ref['sha256']))
    improvement.verify_source_evidence();route.verify_source_evidence();turn_source()
    expected={'improvement_builder':{0xa1e5a149,0x8c468e3c},
              'route_builder':{0xa1e5a149,0x8c468e3c,0xd6fcf3e4,0xa1fbc372}}
    for name,keys in expected.items():
        text=tuple(r['text'] for r in rows(p['functions'][name]))
        actual={int(m[1],16) for r in text if(m:=re.fullmatch('mov edx, 0x([a-f0-9]+)',r))}
        if (actual!=keys or not text.index('call 0x180070b10')<text.index('call qword ptr [rax + 0xa0]')<text.index('call 0x180844580')
                or 'mov dword ptr [rsp + 0x20], 8' not in text
                or 'mov dword ptr [rsp + 0x30], 0x1000000' not in text):
            raise ValueError('XP1 improvement/route normalizer shape/order changed')
    for key,kind in (('30ae2a3d',0x30ae2a3d),('7b65ff2e',0x7b65ff2e)):
        if (p['families'][key]['record_type'],p['families'][key]['record_size'])!=(KINDS[kind],SIZES[KINDS[kind]]):
            raise ValueError('XP1 improvement/route record membership changed')
    return p


def ensure_source(core_sha256):
    if core_sha256==BASE_CORE_SHA256:return
    if core_sha256==XP2_CORE_SHA256:
        from .xp2_improvement_event_source import source
        source();return
    if core_sha256!=XP1_CORE_SHA256:raise ValueError('Unqualified improvement/route engine')
    verify_source()


def source_sha(core_sha256,base_sha):
    ensure_source(core_sha256)
    if core_sha256==XP2_CORE_SHA256:
        from .xp2_improvement_event_source import SOURCE as selected
        return selected[1]
    return base_sha if core_sha256==BASE_CORE_SHA256 else SOURCE[1]


def source_dependencies(*,core_sha256=XP1_CORE_SHA256,execution_image=None):
    if core_sha256==XP2_CORE_SHA256:
        from .xp2_improvement_event_source import source_dependencies as selected
        return selected(execution_image=execution_image)
    if execution_image is not None:raise ValueError('Selected execution image requires XP2 improvement/route ABI')
    if core_sha256!=XP1_CORE_SHA256:raise ValueError('Unqualified improvement/route source engine')
    from .paths import resource_root
    from .resource_resolution import resolve_path
    from .turn_unit_event_profile import source_dependencies as query_sources
    p=verify_source();refs=[dict(path=SOURCE[0],sha256=SOURCE[1]),p['image'],*p['references']]
    return {**query_sources(),**{str(resolve_path(resource_root()/r['path']).resolve()):r['sha256'] for r in refs}}


@lru_cache(maxsize=2)
def _event_profile(*,core_sha256=XP1_CORE_SHA256):
    if core_sha256==XP2_CORE_SHA256:
        from .xp2_improvement_event_source import event_profile as selected
        return selected()
    if core_sha256!=XP1_CORE_SHA256:raise ValueError('Unqualified improvement/route profile engine')
    from .a0_family_source import A0FamilyProfile
    from .native.native_deferred_empty_profile import resolve_empty_receiver_row
    verify_source()
    for record,size in SIZES.items():
        if set(resolve_empty_receiver_row(record)['record_sizes'])!={size}:
            raise ValueError('Improvement/route receiver shape changed')
    return A0FamilyProfile(MappingProxyType({k:frozenset((r,)) for k,r in KINDS.items()}),
                           MappingProxyType(SIZES),SOURCE[1])


def event_profile(*,core_sha256=XP1_CORE_SHA256,execution_image=None):
    if execution_image is not None and core_sha256!=XP2_CORE_SHA256:
        raise ValueError('Selected execution image requires XP2 improvement/route ABI')
    if execution_image is not None:
        from .execution_images import identity
        identity(execution_image)
    return _event_profile(core_sha256=core_sha256)


def verify_live(base,read,*,core_sha256=XP1_CORE_SHA256):
    if core_sha256==XP2_CORE_SHA256:
        from .xp2_improvement_event_source import verify_live as selected
        return selected(base,read)
    if core_sha256!=XP1_CORE_SHA256:raise ValueError('Unqualified improvement/route live engine')
    p=verify_source();count=0
    for name,value in p['functions'].items():
        for row in rows(value):
            raw=bytes.fromhex(row['bytes']);address=base+int(row['va'],16)-0x180000000
            if read(address,len(raw))!=raw:raise ValueError('XP1 improvement/route instruction changed: '+name)
            count+=1
    return count


@dataclass(frozen=True)
class VerifiedSource:
    owner:object
    core:object
    base:int
    proof_sha256:str
    instructions:int


def bind_owner(owner,core,read,*,execution_image=None):
    if owner.load_abi.core_sha256==XP2_CORE_SHA256:
        from .xp2_improvement_event_source import bind_owner as selected
        if execution_image is None:
            execution_image=getattr(core,'_civ6_host_execution_image',None)
        return selected(owner,core,read,execution_image=execution_image)
    if execution_image is not None:raise ValueError('Selected execution image requires XP2 improvement/route ABI')
    from .turn_unit_event_profile import bind_owner as bind_queries
    from .foundation_facade_profiles import verify_xp1_once
    from .paths import resource_root
    owner.check_thread()
    if owner.core is not core or owner.load_abi.core_sha256!=XP1_CORE_SHA256:
        raise ValueError('XP1 improvement/route source owner mismatch')
    old=getattr(owner,'_xp1_improvement_change_source',None)
    if old is not None:
        if (type(old) is not VerifiedSource or old.owner is not owner or old.core is not core
                or old.base!=core._handle or old.proof_sha256!=SOURCE[1]):
            raise ValueError('XP1 improvement/route source lifetime changed')
        return old
    bind_queries(owner,core,read)
    verify_xp1_once(core,core._handle,read,resource_root())
    receipt=VerifiedSource(owner,core,core._handle,SOURCE[1],verify_live(core._handle,read))
    owner._xp1_improvement_change_source=receipt
    return receipt
