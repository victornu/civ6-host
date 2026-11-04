"""Bounded native Save-only diagnostic; no native entry is invoked at import.

The caller must run this at the completed-round tail and provide the independently
verified Host41 job snapshot. No Load, queue draining, counter reset or retry.
"""
from __future__ import annotations
from civ6_host.runtime.configuration_profiles import BASE_CORE_SHA256 as _CHECKPOINT_BASE_CORE_SHA256
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import ctypes as C
import hashlib
import json
from pathlib import Path
import struct
import threading
from civ6_host.runtime.native.native_checkpoint_stream import LocalMemory
from civ6_host.runtime.native.native_checkpoint_stream import Win64Stream
from civ6_host.runtime.native.native_checkpoint_stream import verify_source
ROOT = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_checkpoint_diagnostic.py')))).resolve().parents[1]
BASE_CORE_SHA = 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'
PREVICTORY12_MODE = 'save-config-pre-victory12'
PREVICTORY12_ROUNDS = 16
PREVICTORY12_COMPLETED = 11
PREVICTORY12_TURN = 12
PREVICTORY12_LIMIT = 12

def check_control_boundary(session, read, *, allow_uninitialized_private=False, core_sha256=_CHECKPOINT_BASE_CORE_SHA256):
    """Read existing queues and counters; never make the boundary pass by mutation."""
    if core_sha256 != _CHECKPOINT_BASE_CORE_SHA256:
        from civ6_host.runtime.xp1_checkpoint_profile import control_boundary
        return control_boundary(session, read, allow_uninitialized_private=allow_uninitialized_private, core_sha256=core_sha256)
    deferred = session.deferred_events
    if session.actions.pending or deferred.pending:
        raise RuntimeError('Checkpoint requires empty command and deferred queues')
    if deferred._sequence != deferred.consumed_count:
        raise RuntimeError('Checkpoint requires every public record consumed')
    for name in ('_draining_empty_receivers', '_deferred_drain_poisoned', '_combat_producer_poisoned', '_status_producer_poisoned', '_experience_producer_poisoned', '_f391_poisoned', '_f391_producing', '_found_city_poisoned', '_found_city_producing', '_36c9_poisoned', '_36c9_producing', '_city_command_started_poisoned', '_city_command_started_producing', '_district_combat_poisoned', '_district_combat_producing', '_84c1fdd6_poisoned', '_84c1fdd6_producing'):
        if getattr(deferred, name, False):
            raise RuntimeError('Checkpoint during drain or poisoned producer: ' + name)
    for name in ('_city_range_attack_poisoned', '_city_range_attack_producing'):
        if getattr(session.actions, name, False):
            raise RuntimeError('Checkpoint during city range attack producer: ' + name)
    for name in ('host_notification_counter', 'host_metadata_counter'):
        value = getattr(deferred, name)
        if type(value) is not int or value != 0:
            raise RuntimeError('Checkpoint requires closed notification scope: ' + name)
    registry = deferred.combat_map_registry
    if registry is not None and (registry.poisoned or registry.entries):
        raise RuntimeError('Checkpoint retains combat ownership')
    ring = deferred.private_progress_ring
    if type(allow_uninitialized_private) is not bool:
        raise TypeError('Checkpoint private-ring admission must be Boolean')
    if ring is None:
        if not allow_uninitialized_private:
            raise RuntimeError('Checkpoint requires an initialized private bank')
    elif ring.poisoned or ring.cursors[ring.selector & 1] != 0:
        raise RuntimeError('Checkpoint requires a drained active private bank')
    base = session.core._handle
    sentinel = base + 9156296
    if read(sentinel, 8) != struct.pack('<Q', sentinel):
        raise RuntimeError('Checkpoint native receive queue is not empty')
    flags = read(base + 9156608, 4)
    if len(flags) != 4 or any((value not in (0, 1) for value in flags)):
        raise RuntimeError('Checkpoint processor flags have an unknown representation')
    return {'public_sequence': deferred._sequence, 'consumed_count': deferred.consumed_count, 'private_selector': None if ring is None else ring.selector, 'private_cursors': None if ring is None else list(ring.cursors), 'processor_flags': list(flags), 'notification_counter': 0, 'metadata_counter': 0}

def bind_save(session, memory, *, core_sha256=_CHECKPOINT_BASE_CORE_SHA256):
    """Validate live native Save entry points before creating a callable."""
    from civ6_host.runtime.xp1_checkpoint_profile import save_abi, bind_source
    abi = save_abi(core_sha256)
    if core_sha256 == _CHECKPOINT_BASE_CORE_SHA256:
        proof = verify_source()
        parent = json.loads(_resolve_resource_path(ROOT / 'work/native-checkpoint-stream-contract341.json').read_bytes())
    else:
        parent = bind_source(session, memory.read, core_sha256=core_sha256)
    read = memory.read
    base = session.core._handle
    context = session.context
    qword = lambda address: struct.unpack('<Q', read(address, 8))[0]
    if qword(context) != base + abi.outer_vtable_rva:
        raise RuntimeError('Checkpoint requires the pinned Base outer context')
    inner = qword(context + 8)
    if not inner:
        raise RuntimeError('Checkpoint inner context is absent')
    vt = qword(inner)
    if qword(base + abi.outer_vtable_rva + 360) != base + abi.outer_save_rva or qword(vt + 120) != base + abi.inner_save_rva:
        raise RuntimeError('Checkpoint Save virtual targets differ')
    for name in ('save_outer', 'inner_save'):
        body = parent['core_functions'][name]
        instructions = body.get('instructions')
        if instructions is None:
            instructions = [i for fragment in body['fragments'] for i in fragment['instructions']]
        for instruction in instructions:
            raw = bytes.fromhex(instruction['bytes'])
            if read(base + int(instruction['va'], 16) - 6442450944, len(raw)) != raw:
                raise RuntimeError('Checkpoint live Save instructions differ')
    if qword(base + abi.outer_vtable_rva + 56) != base + abi.initialized_rva or not C.WINFUNCTYPE(C.c_bool, C.c_void_p)(base + abi.initialized_rva)(context):
        raise RuntimeError('Checkpoint native initialization getter is false')
    game = qword(inner + 96)
    if not game:
        raise RuntimeError('Checkpoint native game pointer is absent')
    call = C.WINFUNCTYPE(C.c_int32, C.c_void_p, C.c_void_p)(base + abi.outer_save_rva)
    return (call, {'context': context, 'inner': inner, 'inner_vtable': vt, 'game': game, **parent.get('native_owner_identity', {})})

def _verify_pre_victory_boundary(session, state):
    """Require exact turn-12 state and fresh official score/winner reads before Save."""
    expected_players = [{'player_id': 0, 'active': True, 'complete': False}, {'player_id': 1, 'active': False, 'complete': False}]
    if type(state) is not dict or set(state) != {'current_game_turn', 'local_player', 'players'} or type(state.get('current_game_turn')) is not int or (state['current_game_turn'] != PREVICTORY12_TURN) or (type(state.get('local_player')) is not int) or (state['local_player'] != 0) or (type(state.get('players')) is not list) or (state['players'] != expected_players) or any((type(row) is not dict or set(row) != {'player_id', 'active', 'complete'} or type(row['player_id']) is not int or (type(row['active']) is not bool) or (type(row['complete']) is not bool) for row in state['players'])):
        raise RuntimeError('Pre-victory Save requires exact published turn-12 player-0 state')
    if session.diagnostic_action != 'develop-round' or session.diagnostic_rounds != PREVICTORY12_ROUNDS or session.diagnostic_production_policy != 'native-development' or (session.diagnostic_score_turn_limit != PREVICTORY12_LIMIT) or (session.ui_child is None) or session.actions.pending or session.deferred_events.pending:
        raise RuntimeError('Pre-victory Save requires the source-pinned drained score profile')
    from civ6_host.runtime.native import native_score_limit_diagnostic as score_limit
    prior = session.score_turn_limit_readback
    if type(prior) is not dict or prior.get('requested_limit') != PREVICTORY12_LIMIT or prior.get('effective_bound_verified') is not True or (prior.get('native_victory_inferred') is not False) or (type(prior.get('start_turn')) is not int) or (type(prior.get('effective_end_turn')) is not int) or (prior.get('effective_end_turn') != prior.get('start_turn') + PREVICTORY12_LIMIT) or (type(prior.get('native_configured_max')) is not int) or (prior.get('native_configured_max') != PREVICTORY12_LIMIT) or (prior.get('source_proof_sha256') != score_limit.contract.PROOF_SHA256):
        raise RuntimeError('Pre-victory Save lacks the initial source-verified score-limit readback')
    current = score_limit.observe(session, 0, PREVICTORY12_TURN, PREVICTORY12_LIMIT)
    for key in ('start_turn', 'effective_end_turn', 'requested_limit', 'end_turn_exclusive', 'score_victory_index', 'score_victory_type', 'source_proof_sha256', 'context_source_proof_sha256', 'native_configured_max', 'effective_bound_verified', 'native_victory_inferred'):
        if current.get(key) != prior.get(key):
            raise RuntimeError('Official score-bound configuration changed before the turn-12 Save')
    from civ6_host.runtime.native import native_winning_team as winning
    from civ6_host.runtime.native.native_victory_diagnostic import observe_victory_boundary
    observed_winner = winning.parse(session.runtime.evaluate_text(session.ui_child, winning.source(), b'@native_checkpoint_pre_victory12_winner'))
    result = observe_victory_boundary(session, 0, PREVICTORY12_TURN, observed_winner)
    from civ6_host.runtime.native.native_episode_identity import require_episode
    from civ6_host.runtime.native import native_victory_episode as victory
    identity = require_episode(session)
    if type(result) is not dict or result.get('schema') != 'civ6rl.native_victory_episode.observation.v1' or result.get('policy_id') != 'first-official-native-victory-v1' or (type(result.get('episode_id')) is not str) or (result.get('episode_id') != identity.episode_id) or (type(result.get('game_generation')) is not str) or (result.get('game_generation') != identity.game_generation) or (type(result.get('player_id')) is not int) or (result.get('player_id') != 0) or (type(result.get('current_game_turn')) is not int) or (result.get('current_game_turn') != PREVICTORY12_TURN) or (result.get('winner_present') is not False) or (result.get('winning_team') is not None) or (result.get('victory_type') is not None) or (result.get('episode_terminated') is not False) or (result.get('new_termination') is not False) or (result.get('termination_reason') is not None) or (result.get('absent_to_present_observed') is not False) or (result.get('result_present_on_first_observation') is not False) or (result.get('source_proof_sha256') != victory.PROOF_SHA256) or (result.get('facts_source_proof_sha256') != victory.native_episode_facts.PROOF_SHA256) or (result.get('eligible_for_training') is not False) or (result.get('exposed_to_learner') is not False) or (result.get('observation_only') is not True):
        raise RuntimeError('Turn-12 official read did not prove an absent winner')
    return {'score_bound': current, 'official_result': result}

class SaveOnlyDiagnostic:
    """One synchronous Save in an explicitly bounded diagnostic episode."""

    def __init__(self, mode, *, output_path, jobs_snapshot):
        if mode not in ('baseline', 'save', 'save-config', 'save-config-late114', PREVICTORY12_MODE) or not callable(jobs_snapshot):
            raise ValueError('Explicit checkpoint mode and job observer required')
        self.mode = mode
        self.output_path = _resolve_resource_path(_resolve_resource_path(Path(output_path))).resolve()
        allowed_root = _resolve_resource_path(ROOT / 'work/native-checkpoints').resolve()
        if not allowed_root.is_relative_to(_resolve_resource_path(ROOT).resolve()) or not self.output_path.parent.is_relative_to(allowed_root) or self.output_path.parent == allowed_root or (not _resolve_resource_path(self.output_path.parent).is_dir()) or _resolve_resource_path(self.output_path).exists():
            raise ValueError('Checkpoint output must be new and inside its existing private work directory')
        self.jobs_snapshot = jobs_snapshot
        self.thread = threading.get_ident()
        self.entered = False
        self.snapshot_phase = 'idle'
        self.used = False
        self.save_succeeded = False
        self.stream = None
        self.memory = LocalMemory()

    def at_completed_round(self, session, after):
        late = self.mode == 'save-config-late114'
        pre_victory = self.mode == PREVICTORY12_MODE
        target_completed = PREVICTORY12_COMPLETED if pre_victory else 114 if late else 1
        target_turn = PREVICTORY12_TURN if pre_victory else 115 if late else None
        if self.entered or threading.get_ident() != self.thread:
            raise RuntimeError('Checkpoint reentry or wrong thread')
        if late or pre_victory:
            if self.used:
                if self.save_succeeded and session.native_rounds_completed > target_completed:
                    return
                raise RuntimeError('Bounded checkpoint attempt was already consumed without a successful save')
            if session.native_rounds_completed < target_completed:
                return
            if session.native_rounds_completed != target_completed:
                raise RuntimeError('Checkpoint target completed-round boundary was skipped')
        elif session.native_rounds_completed != target_completed:
            return
        if self.used:
            raise RuntimeError('Checkpoint reentry, repeat or wrong thread')
        valid_profile = type(session.diagnostic_rounds) is int and session.diagnostic_rounds == PREVICTORY12_ROUNDS and (session.diagnostic_action == 'develop-round') and (session.diagnostic_production_policy == 'native-development') if pre_victory else session.diagnostic_rounds == 128 and session.diagnostic_action == 'develop-round' and (session.diagnostic_production_policy == 'native-development') if late else session.diagnostic_rounds == 2 and session.diagnostic_action == 'develop-round'
        expected_limit = PREVICTORY12_LIMIT if pre_victory else None
        limit_matches = type(session.diagnostic_score_turn_limit) is int and session.diagnostic_score_turn_limit == expected_limit if pre_victory else session.diagnostic_score_turn_limit is None
        target_state = after.get('current_game_turn') == target_turn if late or pre_victory else True
        if not valid_profile or not limit_matches or after.get('local_player') != 0 or (not target_state) or (after.get('players') != [{'player_id': 0, 'active': True, 'complete': False}, {'player_id': 1, 'active': False, 'complete': False}]):
            raise RuntimeError('Checkpoint outside its exact target-turn profile')
        self.entered = True
        self.used = True
        try:
            call, identity = bind_save(session, self.memory)
            before_control = check_control_boundary(session, self.memory.read)
            saving = self.mode in ('save', 'save-config', 'save-config-late114', PREVICTORY12_MODE)
            if saving:
                self.stream = Win64Stream('writer', max_bytes=32 * 1024 * 1024, max_calls=1000000)
            completed_rounds = target_completed
            session.emit('native_checkpoint_preflight', mode=self.mode, round_completed=completed_rounds, observed_turn=after.get('current_game_turn'), control=before_control, eligible_for_training=False)
            data = None
            configuration = None
            configuration_receipt = None
            if saving:
                session.emit('before_native_checkpoint_save', outer_slot='0x168', raw_component_only=True, eligible_for_training=False)
            self.snapshot_phase = 'before'
            before_jobs = self.jobs_snapshot()
            self.snapshot_phase = 'save'
            if self.mode in ('save-config', 'save-config-late114', PREVICTORY12_MODE):
                from civ6_host.runtime.native.native_checkpoint_provider import serialize_provider
                owner = session.core._civ6rl_application_configuration
                configuration, configuration_receipt = serialize_provider(session.core, session.context, owner, max_bytes=32 * 1024 * 1024, max_calls=1000000)
                if not configuration:
                    raise RuntimeError('Native provider produced an empty configuration component')
                if check_control_boundary(session, self.memory.read) != before_control:
                    raise RuntimeError('Provider serialization changed checkpoint control state')
                session.emit('native_checkpoint_configuration_serialized', **configuration_receipt, complete_game_restore_validated=False)
            pre_victory_boundary = None
            if pre_victory:
                pre_victory_boundary = _verify_pre_victory_boundary(session, after)
                if check_control_boundary(session, self.memory.read) != before_control:
                    raise RuntimeError('Pre-victory official read changed checkpoint control state')
                session.emit('native_checkpoint_pre_victory_boundary_verified', completed_rounds=target_completed, observed_turn=after['current_game_turn'], score_bound=pre_victory_boundary['score_bound'], official_result=pre_victory_boundary['official_result'], native_save_called=False, eligible_for_training=False)
            if saving:
                status = call(session.context, self.stream.pointer)
            self.snapshot_phase = 'after'
            after_jobs = self.jobs_snapshot()
            self.snapshot_phase = 'postflight'
            if saving:
                data = self.stream.output_bytes()
                if status != 0 or len(data) < 4 or data[:4] != b'\x05\x00\x00\x00':
                    raise RuntimeError('Native Save failed or lacks its actual version marker')
                session.emit('native_checkpoint_save_returned', status=status, bytes=len(data), writes=self.stream.transport.calls, sha256=hashlib.sha256(data).hexdigest(), native_version_prefix=data[:4].hex(), load_validated=False, reset_validated=False, eligible_for_training=False)
            _, after_identity = bind_save(session, self.memory)
            after_control = check_control_boundary(session, self.memory.read)
            if identity != after_identity or before_control != after_control or before_jobs != after_jobs:
                raise RuntimeError('Checkpoint changed native identities, queues or control state')
            if data is not None:
                with _resolve_resource_path(self.output_path).open('xb') as stream:
                    stream.write(data)
            manifest_path = None
            if configuration is not None:
                component_stem = 'turn12' if pre_victory else 'turn115' if late else 'round1'
                configuration_path = self.output_path.with_name(component_stem + '.configuration.raw')
                with _resolve_resource_path(configuration_path).open('xb') as stream:
                    stream.write(configuration)
                manifest_path = self.output_path.with_name(component_stem + '.checkpoint.json')

                def component(path, raw):
                    return {'path': str(path.relative_to(ROOT)), 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}
                manifest = {'schema': 'civ6rl.native_checkpoint_pre_victory12_components.v1' if pre_victory else 'civ6rl.native_checkpoint_late114_components.v1' if late else 'civ6rl.native_checkpoint_components.v1', 'core_sha256': BASE_CORE_SHA, 'completed_rounds': completed_rounds, 'observed_game_turn': after.get('current_game_turn'), 'components': {'gamecore': component(self.output_path, data), 'application_configuration': component(configuration_path, configuration)}, 'configuration_receipt': configuration_receipt, **({'pre_victory_boundary': pre_victory_boundary} if pre_victory else {}), 'control': after_control, 'jobs_quiescent_before_after': True, 'full_civ6save_container': False, 'native_load_validated': False, 'reset_validated': False, 'eligible_for_training': False}
                with _resolve_resource_path(manifest_path).open('x', encoding='utf-8') as stream:
                    stream.write(json.dumps(manifest, indent=2) + '\n')
            session.emit('native_checkpoint_postflight', mode=self.mode, round_completed=completed_rounds, observed_turn=after.get('current_game_turn'), control=after_control, jobs_before=before_jobs, jobs_after=after_jobs, output_path=str(self.output_path) if data is not None else None, native_save_called=saving, native_load_called=False, configuration_component_saved=configuration is not None, component_manifest_path=str(manifest_path) if manifest_path else None, side_effect_free_proven=False, eligible_for_training=False)
        finally:
            try:
                if self.stream is not None:
                    try:
                        self.stream.close()
                    finally:
                        self.stream.transport.closed = True
            finally:
                self.snapshot_phase = 'idle'
                self.entered = False
        if saving:
            session.emit('native_checkpoint_save_finalized', mode=self.mode, round_completed=completed_rounds, observed_turn=after.get('current_game_turn'), stream_closed=True, native_save_called=True, output_sha256=hashlib.sha256(data).hexdigest(), component_manifest_path=str(manifest_path) if manifest_path else None, component_manifest_sha256=hashlib.sha256(_resolve_resource_path(manifest_path).read_bytes()).hexdigest() if manifest_path else None, native_load_validated=False, eligible_for_training=False)
        self.save_succeeded = True

def make_diagnostic(mode):
    """Allocate a fresh private output and bind the actual Host41 observer."""
    import uuid
    from civ6_host.runtime.native.native_checkpoint_job_observer import CurrentProcessApi
    from civ6_host.runtime.native.native_checkpoint_job_observer import make_job_observer
    from civ6_host.runtime.native.native_checkpoint_jobs import PROFILE
    root = _resolve_resource_path(ROOT / 'work/native-checkpoints').resolve()
    if not root.is_relative_to(_resolve_resource_path(ROOT).resolve()):
        raise ValueError('Checkpoint directory resolves outside project work')
    root.mkdir(exist_ok=True)
    private = root / uuid.uuid4().hex
    private.mkdir(exist_ok=False)

    def unavailable():
        raise RuntimeError('Checkpoint job observer has not been installed')
    output_name = 'turn12.gamecore.raw' if mode == PREVICTORY12_MODE else 'turn115.gamecore.raw' if mode == 'save-config-late114' else 'round1.gamecore.raw'
    diagnostic = SaveOnlyDiagnostic(mode, output_path=private / output_name, jobs_snapshot=unavailable)
    api = CurrentProcessApi()
    diagnostic.jobs_snapshot = make_job_observer(diagnostic.memory.read, expected_executable_path=_resolve_resource_path(ROOT / 'work/native-script-services-host41/civ6rl-native-python.exe').resolve(), owner_thread_id=api.current_thread_id(), profile=PROFILE, exclusive_owner_entry=lambda: diagnostic.entered and diagnostic.snapshot_phase in ('before', 'after') and (threading.get_ident() == diagnostic.thread))
    return diagnostic
