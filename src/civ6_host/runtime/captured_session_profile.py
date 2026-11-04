"""Exact captured expansion identities for the shared saved-session adapter.

These constants describe the retained input scopes, not runtime player activity,
action availability or admission of a complete expansion game.
"""
from dataclasses import dataclass
from .configuration_profiles import XP1_CORE_SHA256, XP2_CORE_SHA256


@dataclass(frozen=True)
class CapturedSessionProfile:
    candidate: object
    width: int
    height: int
    major_ids: tuple
    human_ids: tuple


def saved_geometry(bundle):
    """Read the staged capture dimensions and declared major/taken seats."""
    return configuration_geometry(bundle.inputs.configuration, bundle.initial_turn, bundle.expected_readback)


def configuration_geometry(configuration, initial_turn, state):
    from .session_configuration import read_saved_major_roster
    majors, taken = read_saved_major_roster(configuration)
    turn, width, height, player = (state[key] for key in ('turn', 'width', 'height', 'player_id'))
    if (any(type(value) is not int for value in (turn, width, height, player))
            or type(initial_turn) is not int or turn != initial_turn or not 1 <= turn <= 100000
            or not 1 <= width <= 16384 or not 1 <= height <= 16384 or width * height > 16384
            or player not in taken):
        raise ValueError('Captured map, turn or local seat differs from its saved input')
    return dict(turn=turn, width=width, height=height, local_player_id=player,
                major_player_ids=majors, taken_player_ids=taken)


def select(core_sha256):
    from .capture_candidates import select_private_candidate
    if core_sha256 == XP1_CORE_SHA256:
        family, width, height, ids = 'xp1-lan', 74, 46, tuple(range(6))
    elif core_sha256 == XP2_CORE_SHA256:
        family, width, height, ids = 'xp2-lan', 44, 26, (0, 1)
    else:
        raise ValueError('Unknown captured session engine')
    return CapturedSessionProfile(select_private_candidate(candidate_profile=family),
                                  width, height, ids, (0,))


def for_backend(backend):
    selected = select(backend.load_abi.core_sha256)
    bundle = backend.captured_bundle
    if (bundle.reference != selected.candidate.reference
            or bundle.inputs.profile is not selected.candidate.profile):
        raise ValueError('Captured session engine and input identity differ')
    return selected


def for_family(family):
    from .capture_candidates import select_private_candidate
    candidate=select_private_candidate(candidate_profile=family)
    if candidate is None:raise ValueError('An explicit captured session family is required')
    return select(candidate.core_sha256)
