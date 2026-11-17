"""Installed XP1 predefined religion foundation; source admission, not coverage.

The existing religion action proof owns both numeric operations and their
transport. Reuse its live code/data verification and common service profiles.
Custom native strings and unobserved dynamic callbacks are not qualified here.
"""
from .configuration_profiles import XP1_CORE_SHA256, XP2_CORE_SHA256
from .execution_images import _PROFILE, _XP1_PROFILE
from . import xp2_religious_chain_source as xp2
from . import xp1_religion_beliefs_source as common

SOURCE = common.SOURCE

source_for = common.source_for
source_hash = common.source_hash
supports = common.supports
core_for = common.core_for
is_xp2 = common.is_xp2
_ENUMS = {'PlayerOperations.FOUND_RELIGION': 2765815733,
          'PlayerOperations.PARAM_RELIGION_TYPE': 581065611,
          'PlayerOperations.PARAM_INSERT_MODE': 2888817673,
          'PlayerOperations.VALUE_EXCLUSIVE': 2550048198}


def verify_source(core_sha256=XP1_CORE_SHA256):
    if core_sha256 == XP2_CORE_SHA256:
        return xp2.verify_source()
    proof = common.verify_source(core_sha256)
    if (any(proof['enums'][key]['u32'] != value for key, value in _ENUMS.items())
            or 'FOUND_RELIGION' not in proof['contracts']):
        raise ValueError('Installed predefined religion foundation source differs')
    return proof


def actions_qualified():
    verify_source()
    if not common.actions_qualified():
        return False
    from .a0_family_source import family_profile
    profile = family_profile()
    for kind, record in ((0x314df199, 0xc4), (0x99e85ec6, 0x68)):
        if record not in profile.record_types_by_kind.get(kind, frozenset()):
            raise ValueError('Shared religion foundation event receiver differs')
    return True


def require_actions(image=None):
    if image is not None and image is not _XP1_PROFILE and image is not _PROFILE:
        raise ValueError('Unqualified saved religion execution image')
    if image is _PROFILE:
        from .xp2_direct_religion_source import verify_source as verify_direct
        xp2.require_actions('foundation')
        verify_direct()
        return
    if not actions_qualified():
        raise ValueError('FOUND_RELIGION action dependencies are not qualified')


def source_dependencies(image, *, reference=None):
    if image is _PROFILE:
        from .xp2_direct_religion_source import source_dependencies as direct_dependencies
        return direct_dependencies(image,reference=reference)
    verify_source()
    return common.source_dependencies(image)


def bind_prefix(prefix, *, action=False):
    if is_xp2(prefix):
        from .xp2_direct_religion_source import bind_prefix as bind_direct
        return bind_direct(prefix,family='foundation',action=action)
    verify_source()
    if action:
        require_actions()
    # This verifies the full pinned 4f0f6c code/data/vtable group, including the
    # foundation normalizer/applicator. The real backend owns memory reads.
    common.bind_prefix(prefix, action=action)
