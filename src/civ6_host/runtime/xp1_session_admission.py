"""Join the retained XP1 capture to the existing network session contract.

Saved settings describe the requested mode. Fresh native readers establish
current ownership/activity; saved mode tokens never prove scheduling parity.
"""
import hashlib
from pathlib import Path


def source_dependencies():
    from . import session_configuration, xp1_saved_load, captured_session_profile
    return {str(path): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in (Path(__file__).resolve(),
                         Path(session_configuration.__file__).resolve(),
                         Path(captured_session_profile.__file__).resolve(),
                         Path(xp1_saved_load.__file__).resolve())}


def bind(saved):
    """Bind once, after the real Load/UI/continuation stages have returned."""
    from .xp1_saved_load_owner import SavedLoadOwner
    from .captured_session_profile import for_backend
    from .lan_load import _parse_roster, _LAN_MODE, _SIMULTANEOUS_PHASE
    from .session_configuration import read_saved_settings
    if type(saved) is not SavedLoadOwner:
        raise TypeError('XP1 session needs its actual retained saved owner')
    saved._check('commands', requested='unit_commands_candidate')
    if hasattr(saved, 'network_reference'):
        raise ValueError('XP1 session reference was already bound')
    b = saved.backend
    selected = for_backend(b)
    selected.candidate.validate_inputs(saved.inputs, b.captured_bundle)
    settings = read_saved_settings(saved.inputs.configuration)
    mode, phase = settings['game_mode'], settings['turn_phase']
    if (mode['value'] != _LAN_MODE or mode['name'] != 'LAN'
            or phase['present'] is not True or phase['variant_tag'] != 2
            or phase['value'] != _SIMULTANEOUS_PHASE):
        raise ValueError('XP1 captured configuration is not the qualified LAN phase')
    turn, width, height, ids = _parse_roster(b.loaded_roster)
    observed = saved.view_result['observation']
    # The retained raw-Load adapter already executed validate_loaded_roster
    # against exactly this capture. The live view repeats human reads before
    # exposing anything; these IDs are not substituted for runtime results.
    if ((turn, width, height, ids) != (b.captured_bundle.initial_turn,
            selected.width, selected.height, selected.major_ids)
            or tuple(observed[k] for k in ('turn', 'width', 'height', 'player_id'))
                != (turn, width, height, 0)
            or b.host.configured_local_player_id != observed['player_id']
            or saved.continuation.view is not saved.player_view
            or saved.player_view.result is not saved.view_result):
        raise ValueError('XP1 native view and saved admission do not share their capture')
    # observe_player asserted both Game.GetLocalPlayer and GetLocalObserver;
    # they are checked afresh again by every session view read.
    reference = dict(capture_manifest_sha256=selected.candidate.reference[1],
        configuration_sha256=hashlib.sha256(saved.inputs.configuration).hexdigest(),
        state=dict(player_id=observed['player_id'], observer_id=observed['player_id'],
                   game_mode_u32=mode['value'], turn_phase_u32=phase['value']),
        major_player_ids=ids, human_player_ids=selected.human_ids)
    saved.network_reference = reference
    return reference
