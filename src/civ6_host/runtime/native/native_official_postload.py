"""Reuse native facade/+160 implementations for the official-save diagnostic.

Public observation and the first city action are explicit diagnostics only:
the saved fixture's scripts and final database binding remain unresolved.
"""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
from civ6_host.runtime.native import native_official_load as official
from civ6_host.runtime.native import native_checkpoint_postload_facades as facades
from civ6_host.runtime.native import native_checkpoint_postload160 as post160
from civ6_host.runtime.native import native_checkpoint_load as load

def validate_owner(owner, *, stage):
    if type(owner) is not official.OfficialLoadBackend:
        raise TypeError('Expected this official-save diagnostic owner')
    owner.check_thread()
    inputs = owner.inputs
    if getattr(owner, '_saved_load_candidate', False):
        official.validate_inputs(inputs, candidate_bundle=owner.captured_bundle)
    else:
        official.validate_inputs(inputs)
    if owner.stage != stage or owner.busy or owner.poisoned or owner.destroyed or (owner.reader is None) or (owner.reader.transport.closed is not True) or (owner.reader.transport.cursor != len(inputs.game)):
        raise RuntimeError('Official post-load boundary or immutable input pair differs')
    owner.control(empty=True)
    if owner.topology(game_required=True) != owner.bound_identity or owner.game_flag() != 1:
        raise RuntimeError('Official loaded Game identity differs')
    return inputs

def validate_receipt(receipt, inputs):
    if type(receipt) is not dict or type(receipt.get('status')) is not int or receipt['status'] != 0 or (receipt.get('game_initialized') != 1) or (receipt.get('bytes_consumed') != len(inputs.game)) or (receipt.get('scheduler_ledger_reconciliation_pending') is not True):
        raise ValueError('Official post-load requires its checked complete Load receipt')

class OfficialFacadeBackend(facades.NativeFacadeBackend):

    def __init__(self, owner, receipt, *, publication_mode='public'):
        inputs = validate_owner(owner, stage='raw-loaded')
        validate_receipt(receipt, inputs)
        self.owner = owner
        self.load_result = {'readback': {key: owner.loaded_readback[key] for key in ('width', 'height')}}
        self.receipt = receipt
        self.attempted = False
        self.publisher = None
        self.configure_publication(publication_mode)

    def enter(self):
        b = self.owner
        inputs = validate_owner(b, stage='raw-loaded')
        validate_receipt(self.receipt, inputs)
        p = b.prefix
        d = p.deferred_events
        from civ6_host.runtime.loaded_cache_publication import initial_publisher_state
        initial_publisher_state(p, self.cache_abi.core_sha256)
        facades.check_live_code(b.core._handle, b.runtime.read, self.proof, core_sha256=self.cache_abi.core_sha256)
        b.busy = True
        self.begin_publication_owner()

class OfficialPost160Backend(post160.NativePostload160Backend):

    def __init__(self, owner, facade, facade_result, *, postload_mode='public'):
        self.owner = owner
        self.facade = facade
        self.facade_result = facade_result
        self.attempted = False
        self.native_call_attempted = False
        self.postload_mode = postload_mode
        from civ6_host.runtime.xp1_postload_candidate import select_profile
        self.post160_abi = select_profile(self, postload_mode)
        self.proof = post160.verify_source(core_sha256=self.post160_abi.core_sha256)
        self._facade_attempt = None

    def enter(self):
        b = self.owner
        if self.postload_mode == 'candidate':
            from civ6_host.runtime.xp1_postload_candidate import enter
            return enter(self)
        validate_owner(b, stage='facades-observed-awaiting-post160')
        a = self.facade
        p = a.publisher
        if type(a) is not OfficialFacadeBackend or a.owner is not b or a.attempted is not True or (p is not b.prefix.view_publisher) or (p is None) or p._closed or (p.full_facade_initialization_reproduced is not True) or (p.native_cache_gate is not True) or (p._facades is None) or (len(p.cache_map_snapshot or b'') != 28) or (self.facade_result.get('cache_facades_populated') is not True) or (self.facade_result.get('jobs_identical') is not True):
            raise RuntimeError('Official +160 requires its complete retained facade phase')
        post160.check_live_post160(b.core._handle, b.runtime.read, self.proof, core_sha256=self.post160_abi.core_sha256)
        self._facade_attempt = a
        b.busy = True

    def readback(self):
        b = self.owner
        b.check_thread()
        raw = b.prefix.runtime.evaluate_text(b.prefix.game_child, official.roster_readback_source(b.inputs.profile, candidate_bundle=b.captured_bundle if self.postload_mode == 'candidate' else None), b'@official_postload_readback', capacity=256)
        if raw != b.loaded_roster:
            raise ValueError('Official post-load turn/dimensions/roster changed: ' + repr(raw))
        turn, width, height, *players = map(int, raw.decode('ascii').split('|'))
        return dict(current_game_turn=turn, width=width, height=height, major_player_ids=players, scope='privileged diagnostic; no learner observation', game_update_called=False)

def run_postload(owner, load_receipt):
    if getattr(owner, 'official_postload_attempts', None) is not None:
        raise RuntimeError('Official post-load cannot retry in one context')
    attempts = []
    owner.official_postload_attempts = attempts
    facade = OfficialFacadeBackend(owner, load_receipt)
    attempts.append(facade)
    facade_result = facades.run_sequence(facade, owner.emit)
    post = OfficialPost160Backend(owner, facade, facade_result)
    attempts.append(post)
    major_ids = (0, 1, 2, 3) if owner.inputs.profile is official.HOTSEAT_FOUR_PROFILE else (0, 1)
    if owner.inputs.profile is official.LAN_PROFILE:
        from civ6_host.runtime.lan_load import reference_state
        major_ids = reference_state(owner.captured_bundle)['major_player_ids']
        if tuple(map(int, owner.loaded_roster.decode('ascii').split('|')[3:])) != major_ids:
            raise ValueError('LAN postload roster differs from checked Load readback')
    result = post160.run_sequence(post, owner.emit, expected_major_ids=major_ids)
    owner.emit('official_postload_observed', facades=facade_result, post160=result, gameplay_script_selection_proven=False, same_save_database_proven=False, actions_admitted=False, turns_admitted=False, full_restore_proven=False, strategic_training_ready=False)
    return result

def compare_public_own_fields(observation, loaded):
    """Check cache freshness for own fields; never infer complete observation parity."""
    fields = ('id', 'type', 'x', 'y', 'damage', 'moves')
    actual = dict(turn=observation['turn'], width=observation['width'], height=observation['height'], player_id=observation['player_id'], gold=observation['economy']['gold'], city_count=len(observation['cities']), units=sorted(({key: unit[key] for key in fields} for unit in observation['units']), key=lambda unit: unit['id']))
    if actual != loaded:
        raise ValueError('Published own-player fields differ from restored native gameplay state')
    return actual

def observe_saved_player(owner, *, found_city=False):
    """Explicit one-action diagnostic on the saved Single baseline, without Update."""
    inputs = validate_owner(owner, stage='post160-observed-awaiting-controlled-stop')
    if inputs.profile not in (official.SINGLE_PROFILE, official.LAN_PROFILE) or type(found_city) is not bool or (inputs.profile is official.LAN_PROFILE and found_city):
        raise ValueError('Public/action diagnostic requires the exact Single baseline')
    if getattr(owner, 'official_public_attempted', False):
        raise RuntimeError('Official public diagnostic cannot retry')
    owner.official_public_attempted = True
    owner.busy = True
    try:
        from civ6_host.runtime.native.native_player_observation import observe_player
        prefix = owner.prefix
        before = owner.jobs_snapshot('before')
        prefix.view_publisher.publish()
        turn = prefix.inspect_player_view()
        if turn['local_player'] != 0 or turn['current_game_turn'] != owner.loaded_readback['turn']:
            raise ValueError('Official public perspective or turn differs')
        observation = observe_player(prefix.runtime, prefix.ui_child, 0)
        own = compare_public_own_fields(observation, owner.loaded_readback)
        owner.control(empty=True)
        if owner.jobs_snapshot('after') != before:
            raise RuntimeError('Public observation changed the native scheduler')
        owner.emit('official_saved_public_view_observed', observation=observation, own_fields_match_gameplay=own, complete_player_observation=False, same_save_native_observation_compared=False, strategic_training_ready=False)
        owner.stage = 'official-public-observed-awaiting-controlled-stop'
        owner.busy = False
        if found_city:
            found_saved_city(owner)
        return observation
    except BaseException:
        owner.poisoned = True
        owner.stage = 'poisoned'
        owner.busy = False
        raise

def found_saved_city(owner):
    """The existing first native city action, callable after observing the save."""
    inputs = validate_owner(owner, stage='official-public-observed-awaiting-controlled-stop')
    if inputs.profile is not official.SINGLE_PROFILE or getattr(owner, 'official_city_attempted', False):
        raise RuntimeError('City diagnostic requires its first attempt on the Single baseline')
    owner.official_city_attempted = True
    owner.busy = True
    try:
        from civ6_host.runtime.native.native_player_observation import observe_player
        prefix = owner.prefix
        observation = observe_player(prefix.runtime, prefix.ui_child, 0)
        compare_public_own_fields(observation, owner.loaded_readback)
        before = owner.jobs_snapshot('before')
        owner.emit('before_official_saved_found_city', player_id=0, jobs_before=before, same_save_database_proven=False, strategic_training_ready=False)
        prefix.inspect_found_city(0)
        after = observe_player(prefix.runtime, prefix.ui_child, 0)
        if after['turn'] != observation['turn'] or len(after['cities']) != len(observation['cities']) + 1 or len(after['units']) != len(observation['units']) - 1:
            raise RuntimeError('Official saved city action has inconsistent public counts')
        owner.control(empty=True)
        jobs_after = owner.jobs_snapshot('after')
        owner.emit('official_saved_found_city_observed', observation_after=after, jobs_before=before, jobs_after=jobs_after, scheduler_ledger_postrun_required=True, game_update_called=False, turn_advanced=False, same_save_native_transition_compared=False, strategic_training_ready=False)
        owner.busy = False
        return after
    except BaseException:
        owner.poisoned = True
        owner.stage = 'poisoned'
        owner.busy = False
        raise

def reconcile_action_jobs(before, after, events):
    """Post-run validation for this first city action, using authenticated child stdout."""
    from civ6_host.runtime.native.native_checkpoint_postload_jobs import _identity
    from civ6_host.runtime.native.native_job_evidence import validate_job_lifecycle
    if _identity(before, 'before action') != _identity(after, 'after action'):
        raise ValueError('Action scheduler executable identity changed')
    if type(events) not in (list, tuple) or len(events) > 10000:
        raise ValueError('Action ledger is outside the diagnostic bound')
    allowed = {'native_job_submission_observed', 'native_job_queued', 'native_job_spawn_requested', 'before_native_job_execute', 'native_job_executed', 'native_job_spawn_completed', 'native_job_set_wait_completed'}
    if any((e.get('stage', '').startswith(('native_job_', 'before_native_job_')) and e['stage'] not in allowed or e.get('export', '').startswith('EXP_JobManager_') for e in events)):
        raise ValueError('Action interval contains an unadmitted scheduler operation')
    report = validate_job_lifecycle(events)
    if before['submission_sequence'] != 0 or after['submission_sequence'] != 1 or report['submitted_jobs'] != 1 or (report['returned_native_callbacks'] != 1) or (report['completed_spawn_calls'] != 1) or (not report['all_submitted_jobs_returned']) or (report['execute_rva_counts'] != {'0x2bc230': 1}):
        raise ValueError('Action jobs do not match the one completed source-backed native callback')
    for key in before:
        if key not in ('submission_sequence', 'groups') and before[key] != after[key]:
            raise ValueError('Action scheduler changed an unexplained field: ' + key)
    submissions = [e for e in events if e.get('stage') == 'native_job_submission_observed']
    queued = [e for e in events if e.get('stage') == 'native_job_queued']
    if len(submissions) != 1 or len(queued) != 1:
        raise ValueError('Action needs its unique native job and owner witness')
    observed = submissions[0]
    waits = [e for e in events if e.get('stage') == 'native_job_set_wait_completed']
    if len(waits) != 1 or type(waits[0].get('pending_jobs')) is not int or waits[0]['pending_jobs'] != 0:
        raise ValueError('Action job set did not finish its native wait')
    if observed['job'] != queued[0]['job'] or observed['handle'] != queued[0]['handle'] or observed.get('readable') is not True or (observed.get('executed') is not False):
        raise ValueError('Action job producer witness differs from the executed job')
    old = {g['owner']: g for g in before['groups']}
    new = {g['owner']: g for g in after['groups']}
    if set(new) != set(old) | {observed['job_set']} or any((new[owner] != group for owner, group in old.items())):
        raise ValueError('Action group changes do not match the witnessed job set')
    return dict(report, quiescent_snapshots=True, stable_slots=True, groups_reconciled=True, submission_counter_reconciled=True, authenticated_stdout_required=True, strategic_training_ready=False)
