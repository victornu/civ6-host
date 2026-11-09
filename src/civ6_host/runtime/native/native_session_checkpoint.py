"""Administrative Save at an explicit session boundary, using existing native ABI.

This produces a matched B/Game pair, not a Civ6Save container or a proven reload.
It is deliberately outside the player's action catalogue. No Core calls at import.
"""
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
from pathlib import Path
import copy, hashlib, json
from civ6_host.runtime.native import native_official_load as official
from civ6_host.runtime.native.native_checkpoint_retained_save import NativeRetainedSaveBackend
from civ6_host.runtime.native.native_checkpoint_retained_save import _write_exclusive
from civ6_host.runtime.native.native_checkpoint_stream import LocalMemory
from civ6_host.runtime.native.native_checkpoint_job_observer import JobObserver
from civ6_host.runtime.native.native_player_observation import observe_player
from civ6_host.runtime.native.native_saved_actions import boundary
ROOT = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_session_checkpoint.py')))).resolve().parents[1]
SCHEMA = 'civ6rl.session_checkpoint939.v1'

def sha(raw):
    return hashlib.sha256(raw).hexdigest()

def validate_option(closure):
    value = closure.get('checkpoint_on_close', False)
    if type(value) is not bool or (value and closure.get('input_profile') not in ('single', 'lan')):
        raise ValueError('Checkpoint requires the explicit Single administrative option')
    return value

def private_paths(closure_path):
    path = _resolve_resource_path(_resolve_resource_path(Path(closure_path))).resolve()
    if path.name != 'closure.json' or not _resolve_resource_path(path).is_file() or (not path.parent.is_relative_to(ROOT / 'work')):
        raise ValueError('Checkpoint must belong to its private session closure')
    directory = path.parent / 'checkpoint'
    directory.mkdir(exist_ok=False)
    if _resolve_resource_path(directory).resolve().parent != path.parent:
        raise ValueError('Foreign checkpoint directory')
    return {key: directory / name for key, name in (('gamecore', 'game.raw'), ('application_configuration', 'configuration.raw'), ('manifest', 'checkpoint.json'))}

def run_sequence(backend, emit):
    """Reuse retained Save primitives without their fixed historical turn profile."""
    if backend.attempted:
        raise RuntimeError('Session Save cannot be retried')
    backend.attempted = True
    try:
        backend.enter()
        try:
            identity, control, state = backend.prepare()
            configuration, receipt = backend.serialize_configuration()
            backend.verify_after_configuration(identity, control, state)
            emit('before_native_session_checkpoint', turn=state['turn'], configuration=receipt, raw_components_only=True, strategic_training_ready=False)
            before = backend.jobs_snapshot('before')
            status = backend.call_save_once()
            after = backend.jobs_snapshot('after')
            data = backend.validate_return(status, before, after)
            backend.postflight(identity, control, state, after)
        finally:
            backend.close_stream()
        result = backend.publish(data, configuration, receipt, control, before, after)
        backend.finish()
        emit('native_session_checkpoint_finalized', **result, strategic_training_ready=False)
        return result
    except BaseException:
        backend.poison()
        raise

class SessionSaveBackend(NativeRetainedSaveBackend):
    """Reuse prepare/stream/provider/Save/job/postflight methods already witnessed."""

    def __init__(self, owner, observation, decisions, closure, closure_path):
        if type(owner) is not official.OfficialLoadBackend or owner.inputs.profile not in (official.SINGLE_PROFILE, official.LAN_PROFILE):
            raise TypeError('Session Save requires the official Base Single owner')
        _checkpoint_boundary(owner)
        if not validate_option(closure):
            raise ValueError('Administrative Save was not enabled')
        if json.loads(_resolve_resource_path(_resolve_resource_path(Path(closure_path))).read_bytes()) != closure:
            raise ValueError('Private closure changed')
        if getattr(owner, 'session_checkpoint_attempt', None) is not None:
            raise RuntimeError('One Save per session')
        if type(observation) is not dict or type(decisions) is not dict or observation['player_id'] != 0 or (decisions['player_id'] != 0) or (decisions['turn'] != observation['turn']):
            raise ValueError('Save observation identity differs')
        self.owner = owner
        self.prefix = owner.prefix
        self.inputs = owner.inputs
        self.stage = owner.stage
        self.expected_state = copy.deepcopy(observation)
        self.decisions = copy.deepcopy(decisions)
        self.closure_path = _resolve_resource_path(_resolve_resource_path(Path(closure_path))).resolve()
        self.closure = copy.deepcopy(closure)
        from civ6_host.runtime.native.native_session_resume import save_provenance
        self.execution_image = getattr(owner.core, '_civ6_host_execution_image', None)
        if self.execution_image is None:
            self.provenance = save_provenance(self.inputs, self.closure)
        else:
            from civ6_host.runtime.network_checkpoint import save_provenance as lan_save_provenance
            self.provenance = lan_save_provenance(self.inputs, self.closure,
                execution_image=self.execution_image)
        self.paths = private_paths(closure_path)
        self.attempted = self.native_call_attempted = False
        self.memory = self.stream = self.save_call = None
        self.publisher = self.prefix.view_publisher
        self.facade = getattr(self.publisher, '_facades', None)
        owner.session_checkpoint_attempt = self

    def enter(self):
        b = self.owner
        _checkpoint_boundary(b)
        if b.session_checkpoint_attempt is not self or type(b.jobs) is not JobObserver or b.stage != self.stage or (self.publisher is None) or (self.facade is None):
            raise RuntimeError('Save lost its owner, publisher or scheduler')
        self.memory = LocalMemory()
        b.busy = True
        self.observe()

    def observe(self):
        b = self.owner
        b.check_thread()
        if b.busy is not True or b.poisoned is not False or b.destroyed is not False or (b.stage != self.stage) or (b.inputs is not self.inputs) or (b.prefix is not self.prefix) or (b.session_checkpoint_attempt is not self) or (self.prefix.view_publisher is not self.publisher) or self.publisher._closed or (self.publisher._facades is not self.facade) or (self.publisher.full_facade_initialization_reproduced is not True) or (self.publisher.native_cache_gate is not True) or (self.prefix.configuration_readback_verified is not True) or (getattr(b.core, '_civ6rl_application_configuration', None) is not b.owner):
            raise RuntimeError('Session Save owner/provider/publisher identity changed')
        official.validate_inputs(b.inputs)
        topology = b.topology(game_required=True)
        if topology != b.bound_identity or b.game_flag() != 1:
            raise RuntimeError('Session Save Game changed')
        b.owner.require_context(b.core._handle, b.context)
        b.control(empty=True)
        return dict(topology=topology, context=b.context, provider=b.owner.pointer, publisher=id(self.publisher), facade=id(self.facade), prefix=id(self.prefix))

    def state(self):
        current = observe_player(self.prefix.runtime, self.prefix.ui_child, 0)
        if current != self.expected_state:
            raise RuntimeError('Save changed the current player observation')
        return current

    def publish(self, data, configuration, receipt, control, before_jobs, after_jobs):
        if self.stream is None or self.stream.transport.closed is not True or self.native_call_attempted is not True or (self.owner.poisoned is not False):
            raise RuntimeError('Cannot publish before a validated closed native Save')
        components = {}
        for key, raw in (('gamecore', data), ('application_configuration', configuration)):
            p = self.paths[key]
            _write_exclusive(p, raw)
            components[key] = dict(path=p.relative_to(ROOT).as_posix(), bytes=len(raw), sha256=sha(raw))

        def reference(p):
            raw = _resolve_resource_path(p).read_bytes()
            return dict(path=p.relative_to(ROOT).as_posix(), bytes=len(raw), sha256=sha(raw))
        from civ6_host.runtime.native import native_checkpoint_stream as stream
        from civ6_host.runtime.native import native_checkpoint_provider as provider
        from civ6_host.runtime.native import native_checkpoint_jobs as jobs
        profile = self.inputs.profile
        from civ6_host.runtime.xp1_session_checkpoint import manifest_sources
        selected_core, selected_sources = manifest_sources(
            self, reference, execution_image=self.execution_image)
        manifest = dict(**self.provenance, components=components, observed_game_turn=self.expected_state['turn'], player_id=0, observation=self.expected_state, decisions=self.decisions, input_profile=profile.name, origin_official_save_sha256=profile.save_sha, input_components_sha256=dict(gamecore=sha(self.inputs.game), application_configuration=sha(self.inputs.configuration)), session_closure=reference(self.closure_path), fixture=reference(_resolve_resource_path(Path(self.closure['fixture']))), database_profile=self.closure['database_profile'], core_sha256=selected_core, source_proofs=selected_sources, configuration_receipt=receipt, native_save_status=0, game_version_prefix=data[:4].hex(), game_stream_calls=self.stream.transport.calls, stream_closed=True, control=control, jobs_before=before_jobs, jobs_after=after_jobs, jobs_quiescent_unchanged=True, host_placement_tracking=[dict(key=list(k), choice=copy.deepcopy(v)) for k, v in getattr(getattr(self, 'host_state_owner', self.owner), 'explicit_placements', {}).items()], native_load_of_new_pair_validated=False, full_civ6save_container=False, scheduler_load_ledger_postrun_required=True, scheduler_load_ledger_reconciled=False, exact_save_database_content_scripts_proven=False, dlc_mod_compatibility_proven=False, eligible_for_training=False)
        if self.inputs.profile.name in ('base-lan-official-capture', 'xp1-lan-official-capture-inputs', 'xp2-lan-official-capture-inputs'):
            from civ6_host.runtime.network_checkpoint import finalize_manifest
            manifest = finalize_manifest(self, manifest)
        _write_exclusive(self.paths['manifest'], (json.dumps(manifest, indent=2) + '\n').encode('utf-8'))
        return dict(manifest=reference(self.paths['manifest']), components=components, observed_game_turn=self.expected_state['turn'], native_save_status=0, stream_closed=True, native_load_of_new_pair_validated=False, controlled_stop_required=True)

    def finish(self):
        self.owner.snapshot_phase = 'idle'
        self.owner.busy = False

def save_checkpoint(owner, observation, decisions, closure, closure_path):
    backend = SessionSaveBackend(owner, observation, decisions, closure, closure_path)
    return run_sequence(backend, owner.emit)
from civ6_host.runtime.network_checkpoint import checkpoint_boundary as _checkpoint_boundary
