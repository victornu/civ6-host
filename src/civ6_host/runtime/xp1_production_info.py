"""Public stock XP1 production displays over the existing source-bound readers."""

from copy import deepcopy
from pathlib import Path

from civ6_host.contracts import network_turn, production_inputs
from .configuration_profiles import XP1_CORE_SHA256
from .execution_images import _XP1_PROFILE
from .xp1_saved_load import REFERENCE


def source_dependencies(image):
    if image is not _XP1_PROFILE:
        raise ValueError('Production information requires the installed Rise and Fall image')
    from .native.native_saved_production_info988 import verified_files
    from .production_inputs import source_files as display_files
    from .locale_text import source_files as locale_files
    from .resource_resolution import resolve_path
    # The shared readers retain their historical semantic proofs. The loaded
    # getter ABI is independently checked by xp1_production_profile.bind_owner.
    groups = [verified_files(), display_files(), locale_files(execution_image=image)[0]]
    pins = {}
    for group in groups:
        for path, digest in group.items():
            key = str(resolve_path(Path(path)).resolve())
            if key in pins and pins[key] != digest:
                raise ValueError('Conflicting production information source identity')
            pins[key] = digest
    return pins


def _bind(saved):
    saved._check_query()
    backend = saved.backend
    core = backend.core
    if (backend.load_abi.core_sha256 != XP1_CORE_SHA256
            or backend.captured_bundle.reference != REFERENCE
            or getattr(core, '_civ6_host_execution_image', None) is not _XP1_PROFILE):
        raise ValueError('Production information requires the exact Rise and Fall saved owner')
    from .xp1_production_profile import bind_owner
    bind_owner(backend, core, backend.runtime.read)


def attach(saved, observation, decisions):
    """Add only official display values; preserve raw getter evidence privately."""
    prior_schema = decisions['schema']
    if prior_schema not in network_turn.XP1_PRODUCTION_INFO_SCHEMA_BY_BASE:
        raise ValueError('Unsupported Rise and Fall production catalogue')
    pid, turn = observation['player_id'], observation['turn']
    if (type(pid) is not int or type(turn) is not int
            or decisions['player_id'] != pid or decisions['turn'] != turn):
        raise ValueError('Production information actor boundary differs')
    _bind(saved)
    current = quotes = None
    queues = decisions['production_queues']
    if queues is not None:
        from .production_inputs import read_current
        from .native.native_saved_production_info988 import observe
        prefix = saved.prefix
        current = read_current(prefix, observation, queues)
        actions = [row['action'] for row in decisions['candidates']]
        raw = observe(prefix, observation, actions)
        quotes = production_inputs.project_quotes(raw, pid, turn,
            candidates=decisions['candidates'], observation=observation)
        saved.emit('xp1_public_production_information_observed',
            episode_id=decisions['episode_id'], game_generation=decisions['game_generation'],
            sequence=decisions['sequence'], player_id=pid, turn=turn,
            source_schema=prior_schema, execution_image_sha256=_XP1_PROFILE.image_sha256,
            production_current=deepcopy(current), production_info=deepcopy(raw),
            actor_channel=False, native_gameplay_mutated=False)
    decisions['schema'] = network_turn.XP1_PRODUCTION_INFO_SCHEMA_BY_BASE[prior_schema]
    decisions['production_current'] = current
    decisions['production_info'] = quotes
