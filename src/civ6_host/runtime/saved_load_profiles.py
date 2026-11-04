"""Engine-specific addresses for the existing saved-game Load path.

Selection is not admission. Only Base may enter the current saved-game backend;
XP layouts are source-qualified metadata until their providers, host services,
saved inputs and script execution are qualified together. No DLL is loaded here.
The runtime still verifies the loaded image, code bytes and live virtual targets.
"""
from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType


BASE_CORE_SHA256 = 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'
XP1_CORE_SHA256 = '259b90a473a256aff6a7d621a4f3717e46f6921c59b9817475375c88b97e8c83'
XP2_CORE_SHA256 = '324c51e9ea3531758842e16c69e6cddbefbb226c5b675c3d6e60111646c2e98c'

# Private evidence references, not decompiled bodies distributed in this module.
SOURCES = (
    ('work/native-checkpoint-load-plan347.json',
     '09d365eca9bc902d20f1e02f168ed02152bea25f468327f1bbe960d45dbc9d83'),
    ('work/host-extensions/load-dispatch-static/complete-load-dispatch.json',
     'd3e8f3ada6f37edd1a5baf1bfa59dce93143dbe262fa92d3adb13ecf95d2aef2'),
    ('work/host-extensions/load-prepare-static/prepare-lifecycle-v2.json',
     '615cda7a2fb1ab7e17f3bc726578efd6a1ecbc96482764d6dc2414261a389e5a'),
    ('work/host-extensions/active-list-source/source.json',
     '404cc80b6ebb63a2e95a692a85152ce4df9cebcfc4cd4a90602b4423c5708dc6'),
)


@dataclass(frozen=True)
class SavedLoadABI:
    ruleset: str
    core_sha256: str
    outer_vtable_rva: int
    inner_vtable_rva: int
    game_vtable_rva: int
    prepare_rva: int
    copy_rva: int
    load_rva: int
    inner_prepare_rva: int
    inner_load_rva: int
    game_initialized_rva: int

    @property
    def virtual_targets(self):
        """The five virtual checks already performed by NativeLoadBackend."""
        return (
            (self.outer_vtable_rva, 0x40, self.prepare_rva),
            (self.outer_vtable_rva, 0x120, self.copy_rva),
            (self.outer_vtable_rva, 0x170, self.load_rva),
            (self.inner_vtable_rva, 0x50, self.inner_prepare_rva),
            (self.inner_vtable_rva, 0x70, self.inner_load_rva),
        )


_PROFILES = MappingProxyType({
    BASE_CORE_SHA256: SavedLoadABI(
        'base', BASE_CORE_SHA256, 0x79E020, 0x7C7078, 0x7C7270,
        0x42F5A0, 0x42F470, 0x42E420, 0x3CA90, 0x3C260, 0x4C3F60),
    XP1_CORE_SHA256: SavedLoadABI(
        'xp1', XP1_CORE_SHA256, 0x8A8DF0, 0x8D7168, 0x8D7360,
        0x4BE6A0, 0x4BE570, 0x4BD520, 0x3DB40, 0x3D310, 0x5587E0),
    XP2_CORE_SHA256: SavedLoadABI(
        'xp2', XP2_CORE_SHA256, 0xA101E8, 0xA44F70, 0xA45160,
        0x591870, 0x591740, 0x5906E0, 0x46BE0, 0x463B0, 0x63DA20),
})


def profile_for_sha(core_sha256):
    """Select immutable source metadata; never fall back to another engine."""
    if type(core_sha256) is not str or core_sha256 not in _PROFILES:
        raise ValueError('Unknown GameCore saved-Load ABI')
    return _PROFILES[core_sha256]


def require_saved_load_admission(profile):
    """Reject before native allocation/calls; XP metadata is not a runnable host."""
    if (type(profile) is not SavedLoadABI
            or _PROFILES.get(profile.core_sha256) is not profile):
        raise ValueError('Saved-Load ABI must be the canonical source-bound profile')
    if profile.ruleset != 'base':
        raise ValueError(
            'Expansion saved Load is not admitted: provider/host services, exact '
            'official bundle and gameplay-script execution remain unqualified')
    return profile
