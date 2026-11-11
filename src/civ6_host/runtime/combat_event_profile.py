"""Admission of the shared combat, experience and world-text producer group."""
from functools import lru_cache
from types import MappingProxyType
from .configuration_profiles import XP1_CORE_SHA256,XP2_CORE_SHA256
from . import xp1_combat_profile as source


def source_dependencies(core_sha256=XP1_CORE_SHA256, *, execution_image=None):
    if core_sha256==XP2_CORE_SHA256:
        return source.source_dependencies(core_sha256, execution_image=execution_image)
    if execution_image is not None:raise ValueError('Selected execution image requires XP2 combat ABI')
    if core_sha256!=XP1_CORE_SHA256:
        raise ValueError('Combat event dependencies require exact XP1 or XP2')
    from .xp1_world_text_profile import source_dependencies as world_sources
    return {**source.source_dependencies(core_sha256),**world_sources(core_sha256)}


@lru_cache(maxsize=2)
def _event_profile(core_sha256=XP1_CORE_SHA256):
    from .a0_family_source import A0FamilyProfile
    from .native.native_combat_receiver import verify_source_evidence
    from .native.native_event_a479f83f import verify_source_evidence as experience
    from .xp1_world_text_profile import event_profile as world_profile
    if core_sha256==XP2_CORE_SHA256:
        from .xp2_combat_event_source import verify_source as verify_xp2,SOURCE as xp2_source
        verify_xp2(core_sha256);verify_source_evidence();world=world_profile(core_sha256)
        profile_source_sha=xp2_source[1]
    elif core_sha256==XP1_CORE_SHA256:
        source.verify_source();verify_source_evidence();experience();world=world_profile(core_sha256)
        profile_source_sha=source.SOURCE[1]
    else:
        raise ValueError('Combat event profile requires exact XP1 or XP2')
    kinds={0x8256dbe1:frozenset((248,)),0xa479f83f:frozenset((74,79)),**world.record_types_by_kind}
    sizes={248:128,74:96,79:112,**world.record_sizes}
    return A0FamilyProfile(MappingProxyType(kinds),MappingProxyType(sizes),profile_source_sha)


def event_profile(core_sha256=XP1_CORE_SHA256, *, execution_image=None):
    if execution_image is not None and core_sha256!=XP2_CORE_SHA256:
        raise ValueError('Selected execution image requires XP2 combat ABI')
    if execution_image is not None:
        from .execution_images import identity
        identity(execution_image)
    return _event_profile(core_sha256)


def bind_owner(backend,core,read,*,execution_image=None):
    from .xp1_world_text_profile import bind_owner as bind_world
    core_sha256=backend.load_abi.core_sha256
    if execution_image is None and core_sha256 == XP2_CORE_SHA256:
        execution_image=getattr(core,'_civ6_host_execution_image',None)
    source.bind_owner(backend,core,read,execution_image=execution_image)
    bind_world(backend,core,read,execution_image=execution_image)
    return event_profile(core_sha256,execution_image=execution_image)
