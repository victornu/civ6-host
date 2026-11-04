"""Select exact captured expansion inputs within the existing Load pipeline.

This is a private candidate boundary, not public expansion admission. It does
not create a second VM, scheduler or game, and cannot replace missing services.
"""
import hashlib
from .saved_load_profiles import XP1_CORE_SHA256, XP2_CORE_SHA256, profile_for_sha
from .configuration_profiles import codec_source
from . import xp1_saved_load as xp1

SOURCES = xp1.SOURCES


def validate_closure_profile(closure):
    """Select only the XP2 administrative join; retain the raw reader intact."""
    if (closure.get('input_profile') == 'xp2-lan'
            and (closure.get('network_checkpoint') is not None
                 or closure.get('checkpoint_on_close', False) is not False)):
        from .network_checkpoint import validate_closure
        validate_closure(closure)
        return
    from .native.native_official_bundle import validate_closure_profile as original
    return original(closure)


def select_load_closure(closure):
    """Select the engine. The shared loader validates the closure before Load."""
    from .capture_candidates import select_private_candidate
    from .xp1_saved_load_owner import _requested
    _requested(closure)
    contract=select_private_candidate(candidate_profile=closure.get('input_profile'))
    if contract is None:
        raise ValueError('Captured Load needs an explicit expansion family')
    if contract.family == 'xp2-lan' and closure.get('resume_checkpoint') is not None:
        raise ValueError('XP2 cannot inherit a historical Base checkpoint')
    if contract.family == 'xp2-lan' and (closure.get('network_checkpoint') is not None
            or closure.get('checkpoint_on_close', False) is not False):
        from .network_checkpoint import _validate_closure_fields
        _validate_closure_fields(closure)
    return contract


def configure_requested(backend,closure):
    """Use the same pre-Load service composition for both expansions."""
    contract=select_load_closure(closure)
    if backend.load_abi.core_sha256!=contract.core_sha256:
        raise ValueError('Captured Load request differs from its selected engine')
    if contract.family=='xp2-lan' and hasattr(backend,'_xp2_postload_requested'):
        raise ValueError('XP2 Load service scope was already selected')
    # Backend.inputs is bound by run_experiment, after this pre-Load step.
    validate_candidate_inputs(backend.captured_bundle.inputs,backend.captured_bundle)
    from .captured_session_profile import for_backend
    from .session_configuration import read_saved_roster
    selected = for_backend(backend)
    saved_roster = read_saved_roster(backend.captured_bundle.inputs.configuration)
    if tuple(saved_roster['taken_slot_ids']) != selected.human_ids:
        raise ValueError('Saved taken seats differ from the captured LAN human roster')
    from .xp1_action_transport import configure_requested as configure_actions
    configure_actions(backend,closure)
    if contract.family=='xp2-lan':
        backend._xp2_postload_requested=closure.get('post160_candidate',False)


def _sha(bundle):
    from .native.native_official_bundle import PreparedBundle
    if type(bundle) is not PreparedBundle:
        raise ValueError('Captured Load requires its actual prepared input owner')
    value = bundle.content_profile['engine']['gamecore_sha256']
    if value not in (XP1_CORE_SHA256, XP2_CORE_SHA256):
        raise ValueError('Unknown captured Load engine')
    return value


def validate_candidate_inputs(inputs, bundle):
    if _sha(bundle) == XP1_CORE_SHA256:
        return xp1.validate_candidate_inputs(inputs, bundle)
    from .xp2_bundle_inputs import validate_candidate_inputs as validate
    return validate(inputs, bundle)


def bind_candidate(bundle, profile, fixture):
    if _sha(bundle) == XP1_CORE_SHA256:
        return xp1.bind_candidate(bundle, profile, fixture)
    from .xp2_saved_init import bind_candidate as bind
    bind(bundle, profile, fixture)
    return profile_for_sha(XP2_CORE_SHA256)


def proofs_for_candidate(core_sha256):
    if core_sha256 == XP1_CORE_SHA256:
        return xp1.proofs_for_candidate()
    if core_sha256 != XP2_CORE_SHA256:
        raise ValueError('Unknown captured Load source engine')
    xp1._source_bodies(core_sha256)
    return {'provider': codec_source(core_sha256), 'xp2_saved_load_sources': SOURCES,
            'saved_load_engine_sha256': core_sha256}


def verify_live(base, read, proofs):
    if 'xp2_saved_load_sources' not in proofs:
        if 'saved_load_engine_sha256' in proofs:
            raise ValueError('Explicit Load engine lacks its matching source group')
        return xp1.verify_live(base, read, proofs)
    if (type(base) is not int or not 0 < base < (1 << 63) or not callable(read)
            or proofs.get('xp2_saved_load_sources') != SOURCES
            or proofs.get('saved_load_engine_sha256') != XP2_CORE_SHA256
            or proofs.get('provider') != codec_source(XP2_CORE_SHA256)
            or 'xp1_saved_load_sources' in proofs):
        raise ValueError('XP2 candidate source binding differs')
    seen = {}
    for name, body in xp1._source_bodies(XP2_CORE_SHA256).items():
        for fragment in body['fragments']:
            for row in fragment['instructions']:
                rva = int(row['va'], 16) - 0x180000000
                raw = bytes.fromhex(row['bytes'])
                if rva < 0 or not raw or (rva in seen and seen[rva] != raw):
                    raise ValueError('XP2 candidate source instruction conflict: ' + name)
                seen[rva] = raw
    for rva, raw in seen.items():
        if read(base + rva, len(raw)) != raw:
            raise ValueError('XP2 candidate live code differs at RVA ' + hex(rva))
    return {'source_references': SOURCES, 'native_call_made': False, 'public_session_admitted': False}


def prepare_candidate(backend, *, required_ownership_mode):
    if _sha(backend.captured_bundle) == XP1_CORE_SHA256:
        return xp1.prepare_candidate(backend, required_ownership_mode=required_ownership_mode)
    from .native.native_game_configuration import game_configuration_hash
    from .xp2_prepare import prepare
    validate_candidate_inputs(backend.inputs, backend.captured_bundle)
    if (backend.stage != 'B-restored-sealed'
            or required_ownership_mode != game_configuration_hash('LAN')):
        raise ValueError('XP2 Prepare requires its restored LAN configuration')
    backend.topology(game_required=False)
    backend.host.enable_tuner_unavailable_probe()
    receipt = prepare(backend.core, backend.context, backend.host, backend.profile,
                      backend.emit, null_tuner_diagnostic=True)
    if backend.game_flag() != 0:
        raise RuntimeError('Prepared XP2 Game is already initialized')
    backend.stage = 'prepared'
    return receipt


def attach_services(backend, services):
    if _sha(backend.captured_bundle) == XP1_CORE_SHA256:
        return xp1.attach_services(backend, services)
    from .saved_load_services import SavedLoadServices
    from .xp2_bundle_inputs import SELECTED_PATHS, SCRIPT_SHA256
    validate_candidate_inputs(backend.inputs, backend.captured_bundle)
    if (type(services) is not SavedLoadServices or services.backend is not backend
            or services.core_sha256 != XP2_CORE_SHA256
            or services.saved_config_sha != hashlib.sha256(backend.inputs.configuration).hexdigest()
            or services.saved_map_values != backend.inputs.map_values
            or services.contexts.wire_paths != SELECTED_PATHS
            or set(services.contexts.wire_sources) != set(SELECTED_PATHS)
            or len(services.contexts.sources) != 1):
        raise ValueError('XP2 prefix requires its exact captured script/configuration owners')
    path = services.contexts.wire_sources[SELECTED_PATHS[0]]
    if hashlib.sha256(services.contexts.sources[path]).hexdigest() != SCRIPT_SHA256:
        raise ValueError('XP2 selected gameplay script changed')
    services.attach(backend)


def control_snapshot(backend, *, empty, allow_diplomacy=False, pending_round_actor=None):
    # The common graph inspection has no engine addresses. Each service checks
    # its selected live source and exact owner; missing optional owners are not
    # invented. An unsupported callback still fails at its own dispatch.
    core_sha = _sha(backend.captured_bundle)
    if backend.prefix is None or backend.prefix.core_sha256 != core_sha:
        raise ValueError('Captured Load control graph belongs to another engine')
    return xp1.control_snapshot(backend, empty=empty, allow_diplomacy=allow_diplomacy,
                                pending_round_actor=pending_round_actor)


def make_job_observer(backend):
    from .saved_load_job_observer import make_job_observer as factory
    # The scheduler factory must independently admit the selected Core and its
    # compiled profile. This selector never bypasses its current strict guards.
    _sha(backend.captured_bundle)
    return factory(backend)


def validate_loaded_roster(backend, roster, human_flags):
    if _sha(backend.captured_bundle) == XP1_CORE_SHA256:
        return xp1.validate_loaded_roster(backend, roster, human_flags)
    from .lan_load import _parse_roster, _parse_humans
    from .captured_session_profile import saved_geometry
    bundle = backend.captured_bundle
    validate_candidate_inputs(backend.inputs, bundle)
    expected = saved_geometry(bundle)
    if _parse_roster(roster) != tuple(expected[key] for key in ('turn', 'width', 'height', 'major_player_ids')):
        raise ValueError('XP2 loaded roster/map/turn differs from its official capture')
    humans = _parse_humans(human_flags, expected['major_player_ids'])
    if humans != expected['taken_player_ids'] or backend.host.configured_local_player_id != expected['local_player_id']:
        raise ValueError('XP2 loaded human/local identity differs from its official capture')
    return dict(human_player_ids=list(humans), human_status_native_verified=True,
                control_of_all_players_proven=False, simultaneous_execution_qualified=False,
                capture_manifest_sha256=bundle.reference[1], public_session_admitted=False)
