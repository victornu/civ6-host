"""Capture input families, separate from native session admission.

LAN inputs must come from a completely validated official capture. There is no
fallback LAN fixture, guessed configuration, roster, or replacement game mode.
Recognizing a captured family does not admit its host services or action loop.
"""
from dataclasses import dataclass
from types import MappingProxyType


CAPTURE_MODES = MappingProxyType({
    "single": "SINGLEPLAYER", "hotseat-four": "HOTSEAT", "lan": "LAN",
})


@dataclass(frozen=True)
class CapturedModeProfile:
    name: str
    mode_name: str
    # These fields belong to the historical fixture fingerprint, not the
    # captured bytes. Those are independently hashed and joined to the save.
    save_sha: None = None
    config_sha: None = None
    game_sha: None = None


LAN_PROFILE = CapturedModeProfile("base-lan-official-capture", "LAN")


def profile_for_capture(input_profile):
    if type(input_profile) is not str or input_profile not in CAPTURE_MODES:
        raise ValueError("Unsupported official capture input family")
    if input_profile == "lan":
        return LAN_PROFILE
    from .native.native_official_load import SINGLE_PROFILE, HOTSEAT_FOUR_PROFILE
    if input_profile == "single":
        return SINGLE_PROFILE
    if input_profile == "hotseat-four":
        return HOTSEAT_FOUR_PROFILE
    raise ValueError("Unsupported official capture input family")
