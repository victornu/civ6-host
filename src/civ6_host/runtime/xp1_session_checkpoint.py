"""Administrative Save on the existing retained XP1 session and shared codec.

This is an owner/engine adapter, not a replacement save format or Load path.
Every resumed pair retains its original official capture and closed producer.
"""
from contextlib import nullcontext
from copy import deepcopy
import hashlib
import json
from pathlib import Path

from .configuration_profiles import XP1_CORE_SHA256, XP2_CORE_SHA256
from .native.native_session_checkpoint import SessionSaveBackend, private_paths, run_sequence


def admit_resumed_bundle(original, resumed, manifest):
    from .captured_session_profile import select
    selected = select(original.content_profile['engine']['gamecore_sha256']).candidate
    REFERENCE, validate_candidate_inputs = selected.reference, selected.validate_inputs
    from .native.native_official_bundle import (
        _reuse_prepared_bundle, _remember_prepared_bundle,
        _prepared_bundle_validator_digests, _PARENT_ADMISSION_TOKEN)
    validate_candidate_inputs(original.inputs, original)
    _reuse_prepared_bundle(original, REFERENCE, selected.family, _input_only=True)
    if (resumed.reference != original.reference
            or resumed.inputs.profile is not original.inputs.profile
            or resumed.inputs.checkpoint is None
            or resumed.content_profile != original.content_profile
            or resumed.dependencies != original.dependencies
            or resumed.fixture != original.fixture or resumed.engine_path != original.engine_path
            or manifest['core_sha256'] != selected.core_sha256
            or manifest['input_profile'] != original.inputs.profile.name
            or resumed.initial_turn != manifest['observed_game_turn']):
        raise ValueError('XP1 checkpoint lost its original engine/content ownership')
    return _remember_prepared_bundle(resumed, selected.family, _prepared_bundle_validator_digests(),
                                    _token=_PARENT_ADMISSION_TOKEN, _input_only=True)


def validate_resumed_inputs(inputs, bundle):
    from .native.native_official_bundle import _reuse_prepared_bundle
    from .network_checkpoint import validate_inputs
    from .captured_session_profile import select
    selected = select(bundle.content_profile['engine']['gamecore_sha256']).candidate
    REFERENCE = selected.reference
    _reuse_prepared_bundle(bundle, REFERENCE, selected.family, _input_only=True)
    if inputs.official_bundle != REFERENCE:
        raise ValueError('XP1 resumed inputs belong to another official capture')
    m = validate_inputs(inputs)
    if (bundle.initial_turn != m['observed_game_turn']
            or bundle.expected_readback != expected_readback(m['observation'])):
        raise ValueError('XP1 resumed diagnostic fields differ from the actual saved observation')


def expected_readback(o):
    return dict(turn=o['turn'], width=o['width'], height=o['height'], player_id=o['player_id'],
        gold=o['economy']['gold'], city_count=len(o['cities']),
        units=sorted([{k:u[k] for k in ('id','type','x','y','damage','moves')}
                      for u in o['units']], key=lambda u:u['id']))


def boundary(saved):
    """Read the actual active human boundary, with no turn/update side effect."""
    from .xp1_saved_load_owner import SavedLoadOwner
    from .xp1_session_view import _reference, _read_state
    from .network_timer import read
    if type(saved) is not SavedLoadOwner:
        raise TypeError('XP1 Save requires its retained SavedLoadOwner')
    active = saved.backend.busy
    if not saved._running:
        saved._check('commands', requested='unit_commands_candidate')
    with nullcontext() if saved._running else saved._attempt():
        saved._check_active() if active else saved._check_query()
        ref, ids = _reference(saved, 0)
        session, activity = _read_state(saved, 0, ref, ids)
        rows = {row['player_id']: row for row in activity['rows']}
        row = rows[0]
        control = dict(schema='civ6-host.turn-controls.v1', player_id=0,
            turn=session['turn'], active=row['active'], active_complete=row['active_complete'],
            can_unready=row['can_unready'], timer_elapsed=read(saved.backend, core_sha256=saved.backend.load_abi.core_sha256))
        if (session['human_player_ids'] != [0] or session['active_human_player_ids'] != [0]
                or session['local_player_id'] != 0 or control['active'] is not True
                or control['active_complete'] is not True or control['can_unready'] is not False
                or control['timer_elapsed'] is not False
                or any(r['active'] for pid,r in rows.items() if pid != 0)
                or getattr(saved, 'turn_continuation', None) is not None
                or any(saved.continuation.world_input_prompts.values())):
            raise ValueError('XP1 Save requires a quiescent active untimed human boundary')
        saved.continuation.transport.require_empty_native_queue()
        saved.backend.control(empty=True)
        return dict(session=session, controls=control)


class SavedSessionSaveBackend(SessionSaveBackend):
    core_sha256 = XP1_CORE_SHA256

    def __init__(self, saved, observation, decisions, closure, closure_path):
        from .xp1_saved_load_owner import SavedLoadOwner
        from .network_checkpoint import save_provenance
        if type(saved) is not SavedLoadOwner:
            raise TypeError('XP1 Save requires its actual saved session')
        saved._check('commands', requested='unit_commands_candidate')
        saved.continuation.check(active=False)
        from .captured_session_profile import for_backend
        selected = for_backend(saved.backend).candidate
        self.core_sha256 = selected.core_sha256
        if (closure.get('checkpoint_on_close') is not True or closure.get('input_profile') != selected.family
                or json.loads(Path(closure_path).read_bytes()) != closure
                or getattr(saved.backend, 'session_checkpoint_attempt', None) is not None
                or observation != saved.continuation.observation
                or observation['player_id'] != 0 or decisions['player_id'] != 0
                or decisions['turn'] != observation['turn']):
            raise ValueError('XP1 administrative Save lacks an unchanged explicit boundary')
        self.saved = saved
        self.owner, self.prefix, self.inputs = saved.backend, saved.prefix, saved.inputs
        self.host_state_owner = saved.continuation
        self.expected_state, self.decisions = deepcopy(observation), deepcopy(decisions)
        self.closure, self.closure_path = deepcopy(closure), Path(closure_path).resolve()
        self.provenance = save_provenance(self.inputs, closure)
        self.network_boundary = boundary(saved)
        self.publisher = self.host_state_owner.publisher
        self.facade = self.publisher._facades
        self.paths = private_paths(closure_path)
        self.attempted = self.native_call_attempted = False
        self.memory = self.stream = self.save_call = None
        self.allow_uninitialized_private = True
        from .native.native_checkpoint_retained_save import MAX_CALLS
        self.stream_call_limit = max(MAX_CALLS, len(self.inputs.game) * 2)
        self.owner.session_checkpoint_attempt = self

    def enter(self):
        from .native.native_checkpoint_stream import LocalMemory
        self.saved._check_active()
        self.memory = LocalMemory()
        self.observe()

    def observe(self):
        self.saved._check_active()
        b = self.owner
        if (b.session_checkpoint_attempt is not self or b.inputs is not self.inputs
                or b.prefix is not self.prefix or self.prefix.view_publisher is not self.publisher
                or self.publisher._closed or self.publisher._facades is not self.facade
                or getattr(b.core, '_civ6rl_application_configuration', None) is not b.owner
                or not self.prefix.configuration_readback_verified):
            raise ValueError('XP1 Save lost its exact provider/publisher ownership')
        topology = b.topology(game_required=True)
        if topology != b.bound_identity or b.game_flag() != 1:
            raise ValueError('XP1 Save Game identity changed')
        b.owner.require_context(b.core._handle, b.context)
        self.host_state_owner.transport.require_empty_native_queue()
        b.control(empty=True)
        return dict(topology=topology, context=b.context, provider=b.owner.pointer,
                    publisher=id(self.publisher), facade=id(self.facade), prefix=id(self.prefix))

    def state(self):
        from .native.native_player_observation import observe_player
        self.saved._check_active()
        if boundary(self.saved) != self.network_boundary:
            raise ValueError('XP1 Save changed native readiness/session state')
        value = observe_player(self.prefix.runtime, self.prefix.ui_child, 0)
        if value != self.expected_state:
            raise ValueError('XP1 Save changed the public player observation')
        return value

    def finish(self):
        self.owner.snapshot_phase = 'idle'
        self.saved._check_active()

    def poison(self):
        self.owner.snapshot_phase = 'idle'
        self.saved._poison()


def save(saved, observation, decisions, closure, closure_path, protocol_sequence):
    from .xp1_load_capability import capability_source_scope
    from .saved_load_job_observer import require_quiescent
    from .xp1_session_inputs import _write_once
    backend = SavedSessionSaveBackend(saved, observation, decisions, closure, closure_path)
    b, t = saved.backend, saved.continuation
    identity = (t.identity, t.sequence, t.publication_count)
    saved.emit('before_xp1_saved_checkpoint', protocol_sequence=protocol_sequence)
    with saved._attempt():
        from .xp1_continuation import ACTIVE, READY
        b.stage, b.busy = ACTIVE, True
        saved._check_active()
        with capability_source_scope(b, 'continuation'):
            before = b.jobs_snapshot('before'); require_quiescent(before)
            control = b.control(empty=True)
            result = run_sequence(backend, saved.emit)
            after = b.jobs_snapshot('after'); require_quiescent(after)
            after_control = b.control(empty=True)
            if (before != after or control != after_control
                    or identity != (t.identity,t.sequence,t.publication_count)
                    or observation != t.observation):
                raise ValueError('XP1 Save changed its retained session or scheduler')
        b.snapshot_phase = 'idle'
        b.stage, b.busy = READY, False
        saved._finish('commands')
    receipt = dict(save_result=result, jobs_before=before, jobs_after=after,
        episode_id=t.identity.episode_id, game_generation=t.identity.game_generation,
        sequence=t.sequence, publication_count=t.publication_count,
        observation_before=deepcopy(observation), observation_after=deepcopy(t.observation),
        control_before=control, control_after=after_control)
    saved.emit('xp1_saved_checkpoint_returned', protocol_sequence=protocol_sequence,
        receipt=_write_once(Path(closure_path).parent/f'checkpoint-result-{protocol_sequence}.json', receipt))
    return result


def manifest_sources(backend, reference):
    """Select provenance only; file writing and the manifest schema stay shared."""
    from .native import native_checkpoint_provider as provider, native_checkpoint_jobs as jobs
    from .native import native_checkpoint_stream as stream
    from .paths import resource_root
    root = resource_root()
    engine = getattr(backend, 'core_sha256', provider.CORE_SHA256)
    paths = [stream.PROOF_PATH, root/'work/native-checkpoint-stream-contract341.json']
    if engine == XP1_CORE_SHA256:
        from .xp1_checkpoint_profile import source_dependencies
        from .configuration_profiles import codec_source, LIVE_SOURCE, OWNERSHIP_SOURCE
        codec_source(engine)
        paths.extend(root/r[0] for r in (LIVE_SOURCE, OWNERSHIP_SOURCE))
        # Installed images are separately pinned by the complete producer
        # closure and core_sha256. These rows are the private source proofs.
        paths.extend(Path(path) for path in source_dependencies()
                     if Path(path).is_relative_to(root))
    elif engine == XP2_CORE_SHA256:
        from .xp1_checkpoint_profile import source_dependencies
        from .configuration_profiles import codec_source
        codec_source(engine)
        paths.extend(Path(path) for path in source_dependencies(core_sha256=engine)
                     if Path(path).is_relative_to(root))
    elif engine == provider.CORE_SHA256:
        paths.extend((root/'evidence/native-checkpoint-configuration-stream-v3'/
                      (provider.PROOF_SHA256+'.json'), jobs.PROOF_PATH))
    else:
        raise ValueError('Unknown session Save provenance engine')
    return engine, [reference(p) for p in dict.fromkeys(paths)]
