"""One source-bounded Save after an explicitly selected retained three-round diagnostic.

Import does not call Core. This is neither NewGame bookkeeping nor a new Load
profile. The native Load scheduler ledger remains a supervisor post-run check.
"""
from __future__ import annotations
from civ6_host.runtime.configuration_profiles import BASE_CORE_SHA256 as _CHECKPOINT_BASE_CORE_SHA256
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import copy
import hashlib
import json
from pathlib import Path
import uuid
from dataclasses import dataclass
from types import MappingProxyType
from civ6_host.runtime.native import native_checkpoint_diagnostic as diagnostic
from civ6_host.runtime.native import native_checkpoint_load as load
from civ6_host.runtime.native import native_checkpoint_provider as provider
from civ6_host.runtime.native import native_checkpoint_resume as resume
from civ6_host.runtime.native import native_checkpoint_postload_facades as facades
from civ6_host.runtime.native import native_checkpoint_postload160 as post160
from civ6_host.runtime.native import native_checkpoint_jobs as jobs
from civ6_host.runtime.native import native_checkpoint_postload_jobs as postjobs
from civ6_host.runtime.native.native_checkpoint_job_observer import JobObserver
from civ6_host.runtime.native.native_checkpoint_stream import LocalMemory
from civ6_host.runtime.native.native_checkpoint_stream import Win64Stream
ROOT = diagnostic.ROOT
MODE = 'trace-checkpoint-resume-late114-save118'
MODE121 = 'trace-checkpoint-resume-retained118-save121'
MODE150 = 'trace-checkpoint-resume-retained118-save150'
MODE182 = 'trace-checkpoint-resume-retained150-save182'
PROFILE_PLAN_PATH = 'work/native-retained-save121-profile-plan-v2.json'
PROFILE_PLAN_SHA256 = '5c15783c42a52af935d6a5a8002c09bb8cabf5c164096a1698bf629fa19cb12e'
PROFILE150_PLAN_PATH = 'work/native-save150-stage568/native-retained-save150-profile-plan568.json'
PROFILE150_PLAN_SHA256 = '5f13e25b218b770b89122cf5cacba22d026f7ecc67c22b942af146d641dc2dd6'
PROFILE182_PLAN_PATH = 'work/native-retained150-save182-stage645/save182-plan645.json'
PROFILE182_PLAN_SHA256 = 'e076939baed31baea3fa9924f1169650e47bb458045900ef9a674c76e628448f'

@dataclass(frozen=True)
class SaveProfile:
    input_profile: str
    input_turn: int
    save_turn: int
    rounds: int = 3
SAVE_PROFILES = MappingProxyType({MODE: SaveProfile('late380', 115, 118), MODE121: SaveProfile('retained118', 118, 121), MODE150: SaveProfile('retained118', 118, 150, 32), MODE182: SaveProfile('retained150', 150, 182, 32)})

def save_profile(mode=MODE):
    if type(mode) is not str or mode not in SAVE_PROFILES:
        raise ValueError('Retained Save requires an explicit admitted mode')
    return SAVE_PROFILES[mode]
PLAN_PATH = 'work/native-retained-save-plan426.json'
PLAN_SHA256 = 'a5a1d99430c0aaf87528740af33bdbd3703058514e6988ade803bcc463df1688'
MAX_BYTES, MAX_CALLS = (32 * 1024 * 1024, 1000000)
_ATTEMPTS = {}

def sha(data):
    return hashlib.sha256(data).hexdigest()

def verify_source(mode=MODE):
    profile = save_profile(mode)
    plan = load.pinned_json(PLAN_PATH, PLAN_SHA256)
    if plan.get('schema') != 'civ6rl.native_retained_save_plan426.v1' or plan['insertion']['first_profile'] != {'input_profile': 'late380', 'expected_input_turn': 115, 'resumed_rounds': 3, 'observed_save_turn': 118}:
        raise ValueError('Retained Save plan changed')
    provider.verify_source()
    jobs.verify_source()
    resume.verify_source_bundle()
    result = {'plan_sha256': PLAN_SHA256, 'provider_sha256': provider.PROOF_SHA256, 'jobs_sha256': jobs.PROOF_SHA256, 'core_sha256': provider.CORE_SHA256}
    if mode == MODE121:
        extension = load.pinned_json(PROFILE_PLAN_PATH, PROFILE_PLAN_SHA256)
        if extension.get('schema') != 'civ6rl.native_retained_save121_profile_plan.v1' or extension['profiles'].get(mode) != {'input_profile': profile.input_profile, 'input_turn': profile.input_turn, 'save_turn': profile.save_turn, 'rounds': profile.rounds}:
            raise ValueError('Retained Save121 profile plan changed')
        witness = extension['bounded_resume_witness']
        observed = load.pinned_json(witness['path'], witness['sha256'])
        if observed['schema'] != 'civ6rl.native_retained118_multiround_audit451.v1' or observed['input'] != witness['report'] or observed['trial']['receipts']['observed_transitions'] != [[118, 119], [119, 120], [120, 121]] or (observed['trial']['receipts']['aggregate_receipt_present'] is not True) or (observed['trial']['exit_code'] != 90) or (witness['save_after_rounds_observed'] is not False):
            raise ValueError('Retained three-round witness changed; Save remains unobserved')
        result['retained_save121_profile_plan_sha256'] = PROFILE_PLAN_SHA256
    elif mode == MODE150:
        extension = load.pinned_json(PROFILE150_PLAN_PATH, PROFILE150_PLAN_SHA256)
        expected = {'input_profile': profile.input_profile, 'input_turn': profile.input_turn, 'save_turn': profile.save_turn, 'rounds': profile.rounds}
        if extension.get('schema') != 'civ6rl.native_retained_save150_profile_plan.v1' or extension.get('mode') != mode or extension.get('profiles', {}).get(mode) != expected or (extension.get('transition_contract') != {'transitions': [[118 + i, 119 + i] for i in range(32)], 'native_turn_transition': [118, 150], 'rounds_requested': 32, 'rounds_completed': 32, 'diagnostic_public_game_update_budget': 4640, 'diagnostic_public_game_updates_range': [0, 4640]}):
            raise ValueError('Retained Save150 profile plan changed')
        witness = extension.get('native_resume_evidence', {})
        observed = load.pinned_json(witness['path'], witness['sha256'])
        trial = observed.get('trial', {})
        receipts = trial.get('receipts', {})
        if observed.get('schema') != witness.get('schema') or observed.get('input', {}).get('sha256') != witness.get('source_report_sha256') or trial.get('classification') != 'all_requested_rounds_aggregate_observed_controlled_stop' or (trial.get('exit_code') != 90) or (trial.get('worker', {}).get('reaped') is not True) or (trial.get('worker', {}).get('timed_out') is not False) or (receipts.get('requested_rounds') != 32) or (receipts.get('round_effect_receipts') != 32) or (receipts.get('observed_transitions') != [[118 + i, 119 + i] for i in range(32)]) or (witness.get('save150_observed') is not False) or (receipts.get('aggregate_receipt_present') is not True) or (trial.get('scheduler_load_ledger', {}).get('transition', {}).get('ledger_reconciled') is not True):
            raise ValueError('Retained Save150 requires the pinned complete 32-round native resume evidence')
        boundary = load.pinned_json(extension['native_boundary_evidence']['path'], extension['native_boundary_evidence']['sha256'])
        btrial = boundary.get('trial', {})
        if boundary.get('source_sha256') != witness.get('source_report_sha256') or btrial.get('diagnostic_rounds_completed') != 32 or btrial.get('exit_code') != 90 or (btrial.get('reaped') is not True) or (btrial.get('timed_out') is not False) or (boundary.get('failure_rows') != []):
            raise ValueError('Retained Save150 native boundary evidence changed')
        frozen = load.pinned_json(extension['frozen_integration_evidence']['path'], extension['frozen_integration_evidence']['sha256'])
        if frozen.get('native_trial', {}).get('sha256') != witness.get('source_report_sha256'):
            raise ValueError('Retained Save150 frozen integration evidence changed')
        result['native_checkpoint_retained_save150_plan_sha256'] = PROFILE150_PLAN_SHA256
    elif mode == MODE182:
        extension = load.pinned_json(PROFILE150_PLAN_PATH, PROFILE150_PLAN_SHA256)
        expected_input = {'input_profile': 'retained118', 'input_turn': 118, 'save_turn': 150, 'rounds': 32}
        if extension.get('schema') != 'civ6rl.native_retained_save150_profile_plan.v1' or extension.get('mode') != MODE150 or extension.get('profiles', {}).get(MODE150) != expected_input or (extension.get('transition_contract') != {'transitions': [[118 + i, 119 + i] for i in range(32)], 'native_turn_transition': [118, 150], 'rounds_requested': 32, 'rounds_completed': 32, 'diagnostic_public_game_update_budget': 4640, 'diagnostic_public_game_updates_range': [0, 4640]}):
            raise ValueError('Retained150 input profile provenance changed')
        witness = extension.get('native_resume_evidence', {})
        observed = load.pinned_json(witness['path'], witness['sha256'])
        trial = observed.get('trial', {})
        receipts = trial.get('receipts', {})
        if observed.get('schema') != witness.get('schema') or observed.get('input', {}).get('sha256') != witness.get('source_report_sha256') or trial.get('classification') != 'all_requested_rounds_aggregate_observed_controlled_stop' or (trial.get('exit_code') != 90) or (trial.get('worker', {}).get('reaped') is not True) or (trial.get('worker', {}).get('timed_out') is not False) or (receipts.get('requested_rounds') != 32) or (receipts.get('round_effect_receipts') != 32) or (receipts.get('observed_transitions') != [[118 + i, 119 + i] for i in range(32)]) or (witness.get('save150_observed') is not False) or (receipts.get('aggregate_receipt_present') is not True) or (trial.get('scheduler_load_ledger', {}).get('transition', {}).get('ledger_reconciled') is not True):
            raise ValueError('Retained150 input witness changed')
        boundary = load.pinned_json(extension['native_boundary_evidence']['path'], extension['native_boundary_evidence']['sha256'])
        btrial = boundary.get('trial', {})
        if boundary.get('source_sha256') != witness.get('source_report_sha256') or btrial.get('diagnostic_rounds_completed') != 32 or btrial.get('exit_code') != 90 or (btrial.get('reaped') is not True) or (btrial.get('timed_out') is not False) or (boundary.get('failure_rows') != []):
            raise ValueError('Retained150 input boundary evidence changed')
        frozen = load.pinned_json(extension['frozen_integration_evidence']['path'], extension['frozen_integration_evidence']['sha256'])
        if frozen.get('native_trial', {}).get('sha256') != witness.get('source_report_sha256'):
            raise ValueError('Retained150 input frozen evidence changed')
        proposal = load.pinned_json(PROFILE182_PLAN_PATH, PROFILE182_PLAN_SHA256)
        expected_transitions = [[150 + i, 151 + i] for i in range(32)]
        expected_route = {'mode': 'trace-checkpoint-resume-retained150-long-bounded-rounds', 'path': 'evidence/native-newgame-script-prefix406.json', 'sha256': '3be64686bb7b0efdbf43779cec648a1daeecbcffceaeb9e664534e1b8e335e1e', 'bytes': 103762017, 'composition_manifest_path': 'work/native406-composition635/manifest635-final.json', 'composition_manifest_sha256': 'fb7408ff5d581b40e7c361e7f03e085dc03322bf9163f2db8fc2b70666611d97', 'promotion_receipt_path': 'work/native406-promotion637.json', 'promotion_receipt_sha256': '0201b6ffe4d7ddddaf1de490c55089f7efb1e7567c34e71f137d9dfad63dc732', 'rounds': 32, 'transitions': expected_transitions}
        if proposal.get('schema') != 'civ6rl.native_retained_save182_plan.v1' or proposal.get('status') != 'staged_proposal_no_save182_pair' or proposal.get('mode') != mode or (proposal.get('input_profile') != profile.input_profile) or (proposal.get('input_turn') != profile.input_turn) or (proposal.get('save_turn') != profile.save_turn) or (proposal.get('rounds') != profile.rounds) or (proposal.get('transitions') != expected_transitions) or (proposal.get('diagnostic_public_game_update_budget') != profile.rounds * 145) or (proposal.get('cli_limits') != {'timeout_seconds_max': 600, 'process_memory_mib': 512, 'instances': 1, 'attempts': 1, 'hold_seconds': 0, 'reserve_mib_min': 2048, 'compact_queue_trace': True, 'rounds_exact': 32}) or (proposal.get('input_profile_provenance') != {'schema': 'civ6rl.native_retained_save150_profile_plan.v1', 'path': PROFILE150_PLAN_PATH, 'sha256': PROFILE150_PLAN_SHA256, 'input_component_manifest_sha256': 'c8ab1271dd595138ffb58a7f06cb5829f27ee54c4e55fbaac63b88a7124797ff', 'input_save_audit_sha256': 'c61f6da2e1b9ba0d52249cebf4756f69604c4e996278946a03f2a42d4f26b3bb'}) or (proposal.get('demonstrated_resume150_to182') != expected_route) or (proposal.get('output_status') != {'save182_observed': False, 'save182_pair_created': False, 'save182_profile_registered_for_load': False, 'load_admission': False}):
            raise ValueError('Retained Save182 bounded proposal/provenance changed')
        composition = load.pinned_json(expected_route['composition_manifest_path'], expected_route['composition_manifest_sha256'])
        promotion = load.pinned_json(expected_route['promotion_receipt_path'], expected_route['promotion_receipt_sha256'])
        if composition.get('schema') != 'civ6rl.native406_composition635.v1' or promotion.get('schema') != 'civ6rl.native406_promotion637.v1' or promotion.get('composition', {}).get('sha256') != expected_route['composition_manifest_sha256'] or (promotion.get('promoted', {}).get('civ6rl/native_probe.py', {}).get('sha256') != 'aca73cc2369e3c19aad3ffcd472d151a912848444fb51d65d38d0d3c97d2b299') or (promotion.get('promoted', {}).get('civ6rl/native_checkpoint_resume.py', {}).get('sha256') != '9876c7d7cfa3347fdfb986527ca5eec8a1bba3812c52488b16d22050d5ed2b1d') or (promotion.get('promoted', {}).get('civ6rl/native_checkpoint_postload_jobs.py', {}).get('sha256') != '4f0f3b6db8123dae83568def504e72088122cba77caa3a1ebcbaba417db60f2a') or (promotion.get('promoted', {}).get('civ6rl/native_checkpoint_resume_round.py', {}).get('sha256') != 'bab4afcb797914699695b68f69b415cee813fe5216eaf1144aef503fd5db8a81'):
            raise ValueError('Retained150→182 parent run provenance changed')
        result['native_checkpoint_retained_save182_plan_sha256'] = PROFILE182_PLAN_SHA256
    return result

def validate_cli_profile(mode, *, rounds, profile, instances, timeout_seconds, memory_limit_mib, compact_queue_trace):
    """Pure proposed CLI admission. Existing modes must not call this function."""
    selected = save_profile(mode)
    timeout_ok = type(timeout_seconds) in (int, float) and (0 < timeout_seconds <= 600 if mode in (MODE150, MODE182) else timeout_seconds == 60)
    if type(rounds) is not int or rounds != selected.rounds or profile != selected.input_profile or (type(instances) is not int) or (instances != 1) or (type(timeout_seconds) not in (int, float)) or (not timeout_ok) or (type(memory_limit_mib) is not int) or (memory_limit_mib != 512) or (compact_queue_trace is not True):
        raise ValueError('Retained Save requires the selected exact-round/Host41 bounded profile')

def _state(value, turn):
    if type(value) is not dict or set(value) != {'current_game_turn', 'local_player', 'players'} or type(value['current_game_turn']) is not int or (value['current_game_turn'] != turn) or (type(value['local_player']) is not int) or (value['local_player'] != 0) or (type(value['players']) is not list) or (len(value['players']) != 2):
        raise ValueError('Retained Save requires the exact observed turn/local-player state')
    for pid, player in enumerate(value['players']):
        if type(player) is not dict or set(player) != {'player_id', 'active', 'complete'} or type(player['player_id']) is not int or (player['player_id'] != pid) or (player['active'] is not (pid == 0)) or (player['complete'] is not False):
            raise ValueError('Retained Save requires player0 active and player1 inactive')
    return copy.deepcopy(value)

def validate_resume_result(result, *, mode=MODE):
    profile = save_profile(mode)
    if type(result) is not dict:
        raise ValueError('Missing retained resume receipt')
    update_budget = profile.rounds * 145
    for key, expected in (('rounds_requested', profile.rounds), ('rounds_completed', profile.rounds), ('diagnostic_public_game_update_budget', update_budget)):
        if type(result.get(key)) is not int or result[key] != expected:
            raise ValueError('Retained Save requires all selected bounded rounds to complete')
    transitions = result.get('native_turn_transitions')
    if type(transitions) is not list or len(transitions) != profile.rounds or any((type(t) is not list or len(t) != 2 or any((type(v) is not int for v in t)) for t in transitions)) or (transitions != [[profile.input_turn + i, profile.input_turn + i + 1] for i in range(profile.rounds)]) or (type(result.get('native_turn_transition')) is not list) or any((type(v) is not int for v in result['native_turn_transition'])) or (result['native_turn_transition'] != [profile.input_turn, profile.save_turn]) or (type(result.get('diagnostic_public_game_updates')) is not int) or (not 0 <= result['diagnostic_public_game_updates'] <= update_budget) or (result.get('profile_name') != profile.input_profile) or (result.get('action_profile') != resume.ACTION_PROFILE) or (result.get('production_policy') != resume.PRODUCTION_POLICY) or (result.get('policy_chosen_by') != 'python-diagnostic'):
        raise ValueError('Retained Save resume transition or selected profile differs')
    for key in ('native_flags_written', 'native_new_game_called', 'reset_validated', 'context_destroyed', 'full_exe_scheduler_reproduced', 'scheduler_load_ledger_reconciled', 'eligible_for_training', 'complete_game', 'training_ready', 'learner_transport'):
        if result.get(key) is not False:
            raise ValueError('Resume receipt has an unknown lifecycle claim: ' + key)
    if result.get('scheduler_load_ledger_postrun_required') is not True:
        raise ValueError('The actual Load scheduler ledger must remain a post-run obligation')
    _state(result.get('before'), profile.input_turn)
    return _state(result.get('after'), profile.save_turn)

def _load_receipt(result, inputs):
    receipt = result.get('receipt') if type(result) is dict else None
    if type(result) is not dict or type(receipt) is not dict or result.get('raw_component_load_observed') is not True or (result.get('controlled_stop_required') is not True) or (result.get('context_destroyed') is not False) or (result.get('post160_called') is not False) or (type(receipt.get('status')) is not int) or (receipt['status'] != 0) or (type(receipt.get('bytes_consumed')) is not int) or (receipt['bytes_consumed'] != len(inputs.game)) or (type(receipt.get('game_initialized')) is not int) or (receipt['game_initialized'] != 1) or (receipt.get('scheduler_ledger_reconciliation_pending') is not True):
        raise ValueError('Retained Save lacks the real completed raw Load receipt')
    resume._require_matched_readback(result.get('readback'), inputs, 'retained-Save Load')
    candidate = receipt.get('jobs_structural_candidate')
    keys = {'schema', 'snapshot_structural_candidate', 'ledger_reconciled', 'created_empty_handles_candidate', 'submission_sequence_unchanged', 'groups_unchanged', 'before_and_after_independently_quiescent', 'slot_pointer_identity_compared', 'native_load_success_claimed', 'source_proof_sha256', 'host_source_sha256'}
    if type(candidate) is not dict or set(candidate) != keys or candidate.get('schema') != 'civ6rl.native_checkpoint_postload_empty_jobs_transition.v1' or (candidate.get('source_proof_sha256') != jobs.PROOF_SHA256) or (candidate.get('host_source_sha256') != postjobs.HOST_SOURCE_SHA256) or any((candidate.get(k) is not True for k in ('snapshot_structural_candidate', 'submission_sequence_unchanged', 'groups_unchanged', 'before_and_after_independently_quiescent'))) or any((candidate.get(k) is not False for k in ('ledger_reconciled', 'slot_pointer_identity_compared', 'native_load_success_claimed'))):
        raise ValueError('Load scheduler structural candidate is not the source-bounded pending proof')
    handles = candidate['created_empty_handles_candidate']
    if type(handles) is not list or len(handles) > 64 or any((type(h) is not int or not 1 <= h <= 64 for h in handles)) or (len(handles) != len(set(handles))):
        raise ValueError('Malformed Load-created empty job-list handles')

def _private_paths(directory, *, mode=MODE):
    profile = save_profile(mode)
    allowed = _resolve_resource_path(ROOT / 'work/native-checkpoints').resolve()
    if directory is None:
        allowed.mkdir(parents=True, exist_ok=True)
        directory = allowed / uuid.uuid4().hex
        directory.mkdir(exist_ok=False)
    directory = _resolve_resource_path(_resolve_resource_path(Path(directory))).resolve()
    if directory == allowed or not directory.is_relative_to(allowed) or (not _resolve_resource_path(directory).is_dir()) or any(directory.iterdir()):
        raise ValueError('Retained Save output needs a new empty private checkpoint directory')
    paths = {k: directory / (f'turn{profile.save_turn}' + suffix) for k, suffix in (('gamecore', '.game.raw'), ('application_configuration', '.configuration.raw'), ('manifest', '.checkpoint.json'))}
    if any((_resolve_resource_path(p).exists() or _resolve_resource_path(p).resolve().parent != directory for p in paths.values())):
        raise ValueError('Retained Save paths are not exclusive private files')
    return paths

def _write_exclusive(path, data):
    with _resolve_resource_path(path).open('xb') as out:
        if out.write(data) != len(data):
            raise OSError('Short checkpoint file write')
    if _resolve_resource_path(path).read_bytes() != data:
        raise OSError('Closed checkpoint file bytes differ')

def run_sequence(backend, emit, *, mode=MODE):
    """Pure orchestration seam; native entry is isolated in the concrete backend."""
    profile = save_profile(mode)
    if getattr(backend, 'mode', mode) != mode:
        raise RuntimeError('Retained Save orchestration/backend profile differs')
    if backend.attempted:
        raise RuntimeError('Retained Save attempt cannot be retried')
    backend.attempted = True
    try:
        backend.enter()
        try:
            identity, control, state = backend.prepare()
            configuration, configuration_receipt = backend.serialize_configuration()
            backend.verify_after_configuration(identity, control, state)
            emit('before_native_checkpoint_retained_save', observed_game_turn=profile.save_turn, resumed_rounds=profile.rounds, configuration=configuration_receipt, scheduler_load_ledger_postrun_required=True, raw_component_only=True, eligible_for_training=False)
            before_jobs = backend.jobs_snapshot('before')
            status = backend.call_save_once()
            after_jobs = backend.jobs_snapshot('after')
            data = backend.validate_return(status, before_jobs, after_jobs)
            backend.postflight(identity, control, state, after_jobs)
        finally:
            backend.close_stream()
        files = backend.publish(data, configuration, configuration_receipt, control, before_jobs, after_jobs)
        result = dict(observed_game_turn=profile.save_turn, resumed_rounds=profile.rounds, native_save_called=True, native_status=0, stream_closed=True, **files, controlled_stop_required=True, controlled_stop_exit_code=90, scheduler_load_ledger_postrun_required=True, scheduler_load_ledger_reconciled=False, native_load_of_new_pair_validated=False, context_destroyed=False, reset_validated=False, full_civ6save_container=False, eligible_for_training=False)
        emit('native_checkpoint_retained_save_finalized', **result)
        backend.finish()
        return result
    except BaseException:
        backend.poison()
        raise

class NativeRetainedSaveBackend:

    def __init__(self, owner, resume_result, *, output_directory=None, mode=MODE):
        if type(owner) is not load.NativeLoadBackend:
            raise TypeError('Retained Save requires the exact Load backend')
        self.mode = mode
        self.profile = save_profile(mode)
        self.owner = owner
        self.resume_result = copy.deepcopy(resume_result)
        self.expected_state = validate_resume_result(self.resume_result, mode=mode)
        self.proofs = verify_source(mode)
        self.inputs = load.validated_owner_inputs(owner)
        if self.inputs.profile_name != self.profile.input_profile or type(self.inputs.expected_turn) is not int or self.inputs.expected_turn != self.profile.input_turn:
            raise ValueError('Retained Save requires the selected original immutable pair')
        self.paths = _private_paths(output_directory, mode=mode)
        self.attempted = self.native_call_attempted = False
        self.memory = self.stream = self.save_call = None
        self.prefix = owner.prefix
        self.publisher = self.facade = None

    def enter(self):
        b = self.owner
        b.check_thread()
        key = (id(b.core), b.context)
        f, p = (facades._ATTEMPTS.get(key), post160._ATTEMPTS.get(key))
        if load._RETAINED.get(key) is not b or b.busy is not False or b.poisoned is not False or (b.destroyed is not False) or (b.stage != 'postload-resume-diagnostic-observed') or (resume._ATTEMPTS.get(key) is not True) or (type(f) is not facades.NativeFacadeBackend) or (f.owner is not b) or (f.attempted is not True) or (type(p) is not post160.NativePostload160Backend) or (p.owner is not b) or (p.attempted is not True) or (p.native_call_attempted is not True) or (p._facade_attempt is not f) or (p.load_result is not f.load_result) or (p.inputs is not self.inputs) or (type(b.jobs) is not JobObserver) or (b.reader is None) or (b.reader.transport.closed is not True) or (type(b.reader.transport.cursor) is not int) or (b.reader.transport.cursor != len(self.inputs.game)):
            raise RuntimeError('Retained Save owner lacks the completed exclusive Load/resume chain')
        _load_receipt(f.load_result, self.inputs)
        self.facade_attempt, self.post160_attempt = (f, p)
        self.publisher = f.publisher
        self.facade = getattr(self.publisher, '_facades', None)
        b.busy = True
        self.memory = LocalMemory()
        self.observe()

    def observe(self):
        b = self.owner
        b.check_thread()
        key = (id(b.core), b.context)
        inputs = load.validated_owner_inputs(b)
        if load._RETAINED.get(key) is not b or b.busy is not True or b.poisoned is not False or (b.destroyed is not False) or (b.stage != 'postload-resume-diagnostic-observed') or (save_profile(self.mode) is not self.profile) or (inputs is not self.inputs) or (inputs.profile_name != self.profile.input_profile) or (type(inputs.expected_turn) is not int) or (inputs.expected_turn != self.profile.input_turn) or (b.prefix is not self.prefix) or (facades._ATTEMPTS.get(key) is not self.facade_attempt) or (post160._ATTEMPTS.get(key) is not self.post160_attempt) or (resume._ATTEMPTS.get(key) is not True):
            raise RuntimeError('Retained Save changed owner, input pair or completed phases')
        prefix, pub = (self.prefix, self.publisher)
        if prefix is None or prefix.view_publisher is not pub or pub is None or (self.facade_attempt.publisher is not pub) or (pub._facades is not self.facade) or (self.facade is None) or (pub._closed is not False) or (pub.full_facade_initialization_reproduced is not True) or (pub.native_cache_gate is not True) or (type(pub.cache_map_snapshot) is not bytes) or (len(pub.cache_map_snapshot) != 28) or (prefix.configuration_readback_verified is not True) or (prefix.diagnostic_action != 'initial-view') or (prefix.diagnostic_production_policy != 'warrior') or (prefix.diagnostic_score_turn_limit is not None) or (prefix.ui_child is None) or (getattr(b.core, '_civ6rl_application_configuration', None) is not b.owner):
            raise RuntimeError('Retained Save changed the actual loaded provider/publisher profile')
        resume._require_empty_gameplay_registry(prefix.gameplay_scripts)
        topology = b.topology(game_required=True)
        if topology != b.bound_identity or b.game_flag() != 1:
            raise RuntimeError('Retained Save Game/context identity changed')
        b.owner.require_context(b.core._handle, b.context)
        b.control(empty=True)
        return dict(topology=topology, context=b.context, provider=b.owner.pointer, publisher=id(pub), facade=id(self.facade), prefix=id(prefix))

    def state(self):
        result = _state(self.prefix.inspect_player_view(), self.profile.save_turn)
        if result != self.expected_state:
            raise RuntimeError('Retained Save fresh player/turn state differs from the final round')
        return result

    def prepare(self):
        identity = self.observe()
        state = self.state()
        self.save_call, self.save_identity = diagnostic.bind_save(self.prefix, self.memory, core_sha256=getattr(self, 'core_sha256', provider.CORE_SHA256))
        control = diagnostic.check_control_boundary(self.prefix, self.memory.read, allow_uninitialized_private=getattr(self, 'allow_uninitialized_private', False), core_sha256=getattr(self, 'core_sha256', provider.CORE_SHA256))
        self.stream = Win64Stream('writer', max_bytes=MAX_BYTES, max_calls=getattr(self, 'stream_call_limit', MAX_CALLS))
        self.owner.streams.append(self.stream)
        self.stream._check(self.stream.pointer)
        return (identity, control, state)

    def serialize_configuration(self):
        from civ6_host.runtime import xp1_checkpoint_profile as selected_checkpoint
        data, receipt = provider.serialize_provider(self.owner.core, self.owner.context, self.owner.owner, max_bytes=MAX_BYTES, max_calls=MAX_CALLS)
        if type(data) is not bytes or not 4 <= len(data) <= MAX_BYTES or type(receipt) is not dict or (receipt.get('operation') != 'serialize') or (type(receipt.get('bytes')) is not int) or (receipt['bytes'] != len(data)) or (receipt.get('sha256') != sha(data)) or (receipt.get('proof_sha256') != selected_checkpoint.provider_proof(getattr(self, 'core_sha256', provider.CORE_SHA256))) or (receipt.get('native_return_interpreted') is not False) or (receipt.get('identity_checked_before_after') is not True):
            raise RuntimeError('Native B serialization did not return its bounded exact receipt')
        return (data, receipt)

    def verify_after_configuration(self, identity, control, state):
        if self.observe() != identity or self.state() != state or diagnostic.check_control_boundary(self.prefix, self.memory.read, allow_uninitialized_private=getattr(self, 'allow_uninitialized_private', False), core_sha256=getattr(self, 'core_sha256', provider.CORE_SHA256)) != control:
            raise RuntimeError('Provider serialization changed retained state/control')
        self.stream._check(self.stream.pointer)

    def jobs_snapshot(self, phase):
        return self.owner.jobs_snapshot(phase)

    def call_save_once(self):
        b = self.owner
        if self.native_call_attempted or b.busy is not True or b.poisoned is not False or (b.snapshot_phase != 'before') or (self.stream is None) or (self.save_call is None):
            raise RuntimeError('Native Save requires its first exclusive final-snapshot entry')
        self.native_call_attempted = True
        b.snapshot_phase = 'save'
        return self.save_call(b.context, self.stream.pointer)

    def validate_return(self, status, before_jobs, after_jobs):
        from civ6_host.runtime import xp1_checkpoint_profile as selected_checkpoint
        self.owner.snapshot_phase = 'postflight'
        self.stream._check(self.stream.pointer)
        selected_checkpoint.require_quiescent(before_jobs, core_sha256=getattr(self, 'core_sha256', provider.CORE_SHA256))
        selected_checkpoint.require_quiescent(after_jobs, core_sha256=getattr(self, 'core_sha256', provider.CORE_SHA256))
        data = self.stream.output_bytes()
        if type(status) is not int or status != 0 or type(data) is not bytes or (not 4 <= len(data) <= MAX_BYTES) or (data[:4] != b'\x05\x00\x00\x00') or (before_jobs != after_jobs):
            raise RuntimeError('Native Save status/version/jobs did not match the bounded contract')
        return data

    def postflight(self, identity, control, state, jobs_after):
        _, after_save_identity = diagnostic.bind_save(self.prefix, self.memory, core_sha256=getattr(self, 'core_sha256', provider.CORE_SHA256))
        if after_save_identity != self.save_identity or self.observe() != identity or self.state() != state or (diagnostic.check_control_boundary(self.prefix, self.memory.read, allow_uninitialized_private=getattr(self, 'allow_uninitialized_private', False), core_sha256=getattr(self, 'core_sha256', provider.CORE_SHA256)) != control):
            raise RuntimeError('Native Save changed retained identity/player state/control')
        if self.jobs_snapshot('after') != jobs_after:
            raise RuntimeError('Post-Save readback changed the scheduler')
        self.owner.snapshot_phase = 'postflight'

    def close_stream(self):
        if self.stream is not None:
            try:
                self.stream.close()
            finally:
                self.stream.transport.closed = True

    def publish(self, data, configuration, configuration_receipt, control, before_jobs, after_jobs):
        if self.stream is None or self.stream.transport.closed is not True or self.native_call_attempted is not True or (self.owner.poisoned is not False):
            raise RuntimeError('Checkpoint files cannot be published before a validated closed Save')
        components = {}
        for key, raw in (('gamecore', data), ('application_configuration', configuration)):
            path = self.paths[key]
            _write_exclusive(path, raw)
            components[key] = dict(path=path.relative_to(ROOT).as_posix(), bytes=len(raw), sha256=sha(raw))
        manifest = dict(schema='civ6rl.native_checkpoint_retained_components.v1', observed_game_turn=self.profile.save_turn, resumed_rounds=self.profile.rounds, original_input_turn=self.profile.input_turn, input_profile=self.profile.input_profile, input_manifest_sha256=self.inputs.manifest_sha256, input_components_sha256={'gamecore': sha(self.inputs.game), 'application_configuration': sha(self.inputs.configuration)}, native_turn_transitions=self.resume_result['native_turn_transitions'], components=components, source_proofs=self.proofs, core_sha256=provider.CORE_SHA256, configuration_receipt=configuration_receipt, native_save_status=0, game_version_prefix=data[:4].hex(), game_stream_calls=self.stream.transport.calls, stream_closed=True, control=control, jobs_before=before_jobs, jobs_after=after_jobs, jobs_quiescent_unchanged=True, scheduler_load_ledger_postrun_required=True, scheduler_load_ledger_reconciled=False, native_load_of_new_pair_validated=False, full_civ6save_container=False, context_destroyed=False, reset_validated=False, eligible_for_training=False)
        raw = (json.dumps(manifest, indent=2) + '\n').encode('utf-8')
        _write_exclusive(self.paths['manifest'], raw)
        return dict(components=components, component_manifest_path=self.paths['manifest'].relative_to(ROOT).as_posix(), component_manifest_sha256=sha(raw))

    def finish(self):
        self.owner.snapshot_phase = 'idle'
        self.owner.stage = f'postload-retained-save{self.profile.save_turn}-observed'
        self.owner.busy = False

    def poison(self):
        self.owner.poisoned = True
        self.owner.stage = 'poisoned'
        self.owner.snapshot_phase = 'idle'
        self.owner.busy = False

def run_retained_save(owner, resume_result, *, emit, output_directory=None, fatal=None, mode=MODE):
    """Worker-only entry; the caller must stop the retained process with exit90."""
    if type(owner) is not load.NativeLoadBackend:
        raise TypeError('Retained Save requires the exact NativeLoadBackend')
    if fatal is None:
        fatal = load._fatal
    key = (id(owner.core), owner.context)
    try:
        if key in _ATTEMPTS or not callable(emit):
            raise RuntimeError('Retained Save is one-shot and requires a diagnostic emitter')
        _ATTEMPTS[key] = None
        backend = NativeRetainedSaveBackend(owner, resume_result, output_directory=output_directory, mode=mode)
        _ATTEMPTS[key] = backend
        return run_sequence(backend, emit, mode=mode)
    except BaseException as error:
        owner.poisoned = True
        owner.stage = 'poisoned'
        owner.snapshot_phase = 'idle'
        owner.busy = False
        fatal(error)
        raise RuntimeError('Fatal retained Save termination unexpectedly returned') from error
