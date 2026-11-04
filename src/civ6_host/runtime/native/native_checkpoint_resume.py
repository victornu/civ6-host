"""Bounded native resume on the retained Load owner, without NewGame or reset.

This diagnostic observes one turn transition and retains callbacks until the
controlled worker stop. It does not establish full restore or RL readiness.
"""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
from contextlib import contextmanager
from pathlib import Path
import hashlib
ROOT = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_checkpoint_resume.py')))).resolve().parents[1]
SOURCE_ROOT = ROOT
ACTION_PROFILE = 'develop-round'
PRODUCTION_POLICY = 'native-development'
MAX_PUBLIC_GAME_UPDATES = 145
RESUME_PROFILES = {'baseline352': 2, 'late380': 115, 'retained118': 118, 'retained121': 121, 'retained150': 150, 'retained182': 182, 'previctory12': 12}
LATE_CHAIN_PROFILES = {'late380': 115, 'retained118': 118, 'retained150': 150}

def _late_chain_start(inputs):
    name = inputs.profile_name
    turn = inputs.expected_turn
    if type(name) is not str or name not in LATE_CHAIN_PROFILES or type(turn) is not int or (turn != LATE_CHAIN_PROFILES[name]):
        raise RuntimeError('Bounded multiround mode requires an exact late380/115, retained118/118, or retained150/150 pair')
    return turn
_ATTEMPTS: dict[tuple[int, int], bool] = {}
from civ6_host.runtime.native import native_checkpoint_resume_round as protocol
SOURCE_SHA256 = {'civ6rl/native_score_turn_limit.py': 'cfde3317210a1b00cfac1aab72d03e157ac5c562841fa4e0fa244fd30342a532', 'civ6rl/native_score_limit_diagnostic.py': 'bff8298830cc9f7cced994653cab26747e581b85611ace075ff7829eab14c667', 'civ6rl/native_checkpoint_previctory_profile.py': '81e9bebe9f373cb3f6d2e7780cf06f92ee225268e9abfb321b76fc56cee66057', 'civ6rl/native_checkpoint_retained_save.py': '6e9c8376329b2797e490f20e6b88020ad550a074632c8d294c7b438a05fba8e4', 'civ6rl/native_event_e660_building_pillaged.py': '2efd026d7e68d781af5fbda89fe2a1dc09064404c46e9aecac1cc7be8743a65c', 'civ6rl/native_event_f74afc79.py': 'eb5ccfa5b183199d5503d576d5987ba8b04ce74fcae1c42ea5d22002770e6f3d', 'civ6rl/native_stdout_transport.py': '345de023c4043de995b156720129ddba1b3314b512c57fb9849da8c0f90f2561', 'civ6rl/native_event_754cbd1b_city.py': '5d1ae3bc76ad60f74ece376cb149716ed75de7cd9b960eeeb4888554a8569f87', 'civ6rl/native_city_kill_receipt.py': '54234f0ae1bcb4a5b28229e00c7d7cd45a4287255866190b27ab275be2cf4375', 'civ6rl/native_queue_trace.py': 'c48c8da9357a1929de9e68e23925fc81279792efa99750bf6cfd7c5b5d355fb7', 'civ6rl/native_checkpoint_retained_profile.py': 'bd865df3d3bf160e0adbcf2ae9c9ec37f3945d05612a5508c828c4974c584dd9', 'civ6rl/native_checkpoint_load.py': '4f44b35bbd01d6420af52c215a9c5c4e910777e07d3f3ea0f8061c102031352a', 'civ6rl/native_checkpoint_profile.py': '97123eb18e038a8e37c094dbed557246bbe802574df1f9bb65049aba6b31399a', 'civ6rl/native_event_84c1fdd6.py': '913d062a6e639323d2f32211377377314ff214c8e05a8fd6f7a166adca9391f0', 'civ6rl/native_event_1d103404.py': 'deaeb02ade4fb61a2bbe54bec131ed0a266ddd6f88ca8cff480959bdc7027afc', 'civ6rl/native_event_47261a7d.py': '1e5ccee46e37155a5953cdf74eb2ef22685fb92743468c29cada1a7cf50e569a', 'civ6rl/native_deferred_empty_profile.py': '16c53e27ef23ae44accf8c94f0e4ab80062c348ffa5ff5be4408df6884fa6805', 'civ6rl/native_city_range_attack.py': 'f9e295f276166b630126eca672e37db9cd59f682aff93c54deed9ee492ea3254', 'civ6rl/native_checkpoint_postload_facades.py': '6972b7d7bd6921bc7de27615552e327f7aa9060c9e8e661c580d2f917ac263b9', 'civ6rl/native_checkpoint_postload160.py': '5d342fdac9229464eb217dccf2abfc863bb51c92f34518fb8e4ae141d41e37c7', 'civ6rl/native_map_script.py': 'ddd7db5fcfb0a5819c58289dfb93f5c4d424c7fa565847d3d0f686836d53ebc9', 'civ6rl/native_gameplay_script_registry.py': 'd9f9ab12b159d5dd05a9847ca378868b07cdb7ee1154c9d16d784abdc272a7da', 'civ6rl/native_host_events.py': '55b7e72d0b23e0fd0ae4cb399678f2cbe52f866d906b7e0e3bc7372c6992bf1d', 'civ6rl/native_action_transport.py': '32e2356a64d5b1b7353e9bbdeea40efe113764618317535379c087e4f23feecf', 'civ6rl/native_turn_decisions.py': 'e0d75ad03628c2261abf80260cadb14c2403031041716a71d0a11141d46f5227', 'civ6rl/native_endturn_gate.py': 'cff9433aa0907919dcea6096b3fab261d1d4638a02c25261e73548e1c21d2ac7', 'civ6rl/native_ai_round_pump.py': 'a88eec1d23215eeea8aea59a2410c3d73a6187eea1d679a469d296761192ad00', 'civ6rl/native_episode_facts.py': '239e732ab889d2c2ee08d838a5e3444895a14cfe13fd6e212b6d575beb966145', 'civ6rl/native_victory_diagnostic.py': 'c7f396b95c45921797147c1fa3462176a8e1ae70ddd62a979d10dfe8811c990c', 'civ6rl/native_victory_episode.py': 'e61f7f1fda6b5257c7e92803b0d018042681b9885e27aed8d4682d5bb7313538', 'civ6rl/native_winning_team.py': '482f62d89388d2c600cbf635a0aeba39bda8a6d6234be4f31d0fe149e209a275', 'civ6rl/native_city_production_observation.py': '9376930c79ed0385b217c812b08ebc624f1b58fa73b11157fafdf3114f3d9dd0', 'civ6rl/native_checkpoint_postload_jobs.py': '425093e399ef91e9bbdaeafbdc35d61780a3a72cdb2bbdc1653ddd5ecfafd2e8', 'civ6rl/native_checkpoint_resume_round.py': 'c71f764e2253e0b1e7b7afce8c9f2850ee056170d63e3e0eb669d536eb16bb8f', 'civ6rl/native_enabled_mods_empty.py': '532b0e7ed5d0845801bcbef8ecbd44cad4908806ad69a5033faa5fbe63d63d8c'}

def verify_source_bundle(root: Path | None=None) -> dict[str, str]:
    """Check the exact mirrored source inputs and live module evidence pins."""
    if root is None:
        root = SOURCE_ROOT
    actual = {}
    for relative, expected in SOURCE_SHA256.items():
        path = root / relative
        digest = hashlib.sha256(_resolve_resource_path(path).read_bytes()).hexdigest()
        if expected == 'PENDING' or digest != expected:
            raise RuntimeError(f'Resume adapter source pin changed: {relative}')
        actual[relative] = digest
    from civ6_host.runtime.native import native_checkpoint_load as load
    from civ6_host.runtime.native import native_checkpoint_postload_facades as facades
    from civ6_host.runtime.native import native_checkpoint_postload160 as post160
    from civ6_host.runtime.native import native_ai_round_pump as ai
    from civ6_host.runtime.native import native_endturn_gate as endturn
    from civ6_host.runtime.native import native_episode_facts as facts
    from civ6_host.runtime.native import native_victory_diagnostic as victory_diagnostic
    from civ6_host.runtime.native import native_victory_episode as victory_episode
    from civ6_host.runtime.native import native_winning_team as winning_team
    load.verify_source()
    facades.verify_source()
    post160.verify_source()
    ai.verify_source_evidence()
    endturn.verify_source()
    facts.verify_source()
    victory_episode.verify_source()
    winning_team.source()
    return actual

def _exact_bool(mapping, key, value=True):
    return type(mapping.get(key)) is bool and mapping[key] is value

def _validated_resume_inputs(owner):
    """Revalidate the exact retained pair, then select one explicit resume profile."""
    from civ6_host.runtime.native import native_checkpoint_load as load
    inputs = load.validated_owner_inputs(owner)
    if type(inputs) is not load.MatchedInputs or type(inputs.profile_name) is not str or inputs.profile_name not in RESUME_PROFILES or (type(inputs.expected_turn) is not int) or (inputs.expected_turn != RESUME_PROFILES[inputs.profile_name]) or (type(inputs.expected_width) is not int) or (type(inputs.expected_height) is not int) or ((inputs.expected_width, inputs.expected_height) != (74, 46)) or (type(inputs.game) is not bytes) or (not inputs.game):
        raise RuntimeError('Resume needs an explicitly registered immutable checkpoint pair')
    return inputs

def _current_resume_profile_binding(profile_name):
    """Return the live registry and exact profile object for one admitted pair."""
    if profile_name in ('retained118', 'retained121', 'retained150', 'retained182'):
        from civ6_host.runtime.native import native_checkpoint_retained_profile as retained
        return (retained.RETAINED_PROFILES, retained.RETAINED_PROFILES.get(profile_name))
    if profile_name == 'previctory12':
        from civ6_host.runtime.native import native_checkpoint_previctory_profile as profile
        return (profile, profile.PREVICTORY12)
    if profile_name == 'late380':
        from civ6_host.runtime.native import native_checkpoint_profile as profile
        return (profile, profile.LATE_380)
    raise RuntimeError('Late input token has no admitted profile registry')

class _LateInputValidationToken:
    """Attempt-local proof that the exact frozen input object passed full admission."""
    __slots__ = ('valid', 'owner', 'core', 'context', 'inputs', 'profile_name', 'profile_registry', 'profile', 'field_values', 'field_types', 'configuration', 'game')

    def __init__(self, owner, ports):
        from civ6_host.runtime.native import native_checkpoint_load as load
        inputs = ports.inputs
        if type(inputs) is not load.MatchedInputs or owner.inputs is not inputs or ports.owner is not owner:
            raise RuntimeError("Late input token needs this owner's exact validated MatchedInputs")
        names = ('configuration', 'game', 'manifest_sha256', 'expected_turn', 'expected_width', 'expected_height', 'profile_name')
        values = tuple((getattr(inputs, name) for name in names))
        types = tuple((type(value) for value in values))
        if types != (bytes, bytes, str, int, int, int, str) or not values[0] or (not values[1]):
            raise RuntimeError('Late input token fields are not canonical immutable values')
        registry, profile = _current_resume_profile_binding(inputs.profile_name)
        if profile is None:
            raise RuntimeError('Late input token profile is no longer registered')
        self.valid = True
        self.owner = owner
        self.core = owner.core
        self.context = owner.context
        self.inputs = inputs
        self.profile_name = inputs.profile_name
        self.profile_registry = registry
        self.profile = profile
        self.field_values = values
        self.field_types = types
        self.configuration = inputs.configuration
        self.game = inputs.game

    def matches(self, owner, ports):
        if self.valid is not True or owner is not self.owner or ports.owner is not owner or (owner.core is not self.core) or (type(owner.context) is not type(self.context)) or (owner.context != self.context) or (owner.inputs is not self.inputs) or (ports.inputs is not self.inputs):
            return False
        try:
            registry, profile = _current_resume_profile_binding(self.profile_name)
        except (RuntimeError, ValueError):
            return False
        if registry is not self.profile_registry or profile is not self.profile:
            return False
        names = ('configuration', 'game', 'manifest_sha256', 'expected_turn', 'expected_width', 'expected_height', 'profile_name')
        values = tuple((getattr(self.inputs, name) for name in names))
        if tuple((type(value) for value in values)) != self.field_types:
            return False
        if values[0] is not self.configuration or values[1] is not self.game or values[2:] != self.field_values[2:]:
            return False
        return True

    def invalidate(self):
        self.valid = False
        self.owner = self.core = self.context = self.inputs = None
        self.profile_registry = self.profile = None
        self.field_values = self.field_types = None
        self.configuration = self.game = None

def _require_late_input_validation_token(owner, ports):
    token = getattr(ports, '_input_validation_token', None)
    if type(token) is not _LateInputValidationToken or not token.matches(owner, ports):
        raise RuntimeError('Late resume immutable-input admission token is missing or changed')
    return ports.inputs

def _invalidate_late_input_validation_token(ports):
    if ports is None:
        return
    token = getattr(ports, '_input_validation_token', None)
    if type(token) is _LateInputValidationToken:
        token.invalidate()
    ports._input_validation_token = None

def _require_matched_readback(readback, inputs, phase):
    if type(readback) is not dict or any((type(readback.get(key)) is not int for key in ('current_game_turn', 'width', 'height'))) or readback['current_game_turn'] != inputs.expected_turn or (readback['width'] != inputs.expected_width) or (readback['height'] != inputs.expected_height) or (type(readback.get('major_player_ids')) is not list) or any((type(pid) is not int for pid in readback['major_player_ids'])) or (readback['major_player_ids'] != [0, 1]) or (readback.get('game_update_called') is not False):
        raise RuntimeError(f'Resume {phase} readback differs from the matched saved profile')

def _require_empty_gameplay_registry(registry) -> None:
    from civ6_host.runtime.native.native_gameplay_script_registry import NativeGameplayScriptRegistry
    if type(registry) is not NativeGameplayScriptRegistry:
        raise RuntimeError('Resume requires the retained native GameplayScripts registry')
    count = registry.count()
    if type(count) is not int or count != 0:
        raise RuntimeError('Checkpoint resume profile requires an explicitly empty GameplayScripts list')

def _validate_official_victory_result(result, player_id, turn, identity, expected_winner, *, terminal):
    """Validate the exact result contract returned by FirstOfficialVictory.observe()."""
    from civ6_host.runtime.native import native_episode_facts as facts
    from civ6_host.runtime.native import native_victory_episode as victory
    keys = {'schema', 'episode_id', 'policy_id', 'player_id', 'current_game_turn', 'team_id', 'is_alive', 'was_ever_alive', 'episode_terminated', 'new_termination', 'termination_reason', 'first_result_observed_turn', 'absent_to_present_observed', 'result_present_on_first_observation', 'winner_present', 'winning_team', 'victory_type', 'winner_matches_player_team', 'global_engine_terminal', 'engine_halted', 'personal_elimination_used_as_global_trigger', 'source_proof_sha256', 'facts_source_proof_sha256', 'observation_only', 'eligible_for_training', 'exposed_to_learner', 'game_generation'}
    if type(result) is not dict or set(result) != keys:
        raise RuntimeError('Official victory reader result has an unknown or incomplete schema')
    if result.get('schema') != 'civ6rl.native_victory_episode.observation.v1' or result.get('episode_id') != identity.episode_id or result.get('policy_id') != victory.POLICY_ID or (type(result.get('game_generation')) is not str) or (result.get('game_generation') != identity.game_generation) or (type(result.get('player_id')) is not int) or (result.get('player_id') != player_id) or (type(result.get('current_game_turn')) is not int) or (result.get('current_game_turn') != turn) or (type(result.get('team_id')) is not int) or (not 0 <= result['team_id'] <= 63) or (type(result.get('is_alive')) is not bool) or (result.get('was_ever_alive') is not True) or (type(result.get('episode_terminated')) is not bool) or (result.get('episode_terminated') is not terminal) or (type(result.get('new_termination')) is not bool) or (type(result.get('absent_to_present_observed')) is not bool) or (type(result.get('result_present_on_first_observation')) is not bool) or (result.get('global_engine_terminal') is not None) or (result.get('engine_halted') is not None) or (result.get('personal_elimination_used_as_global_trigger') is not False) or (result.get('source_proof_sha256') != victory.PROOF_SHA256) or (result.get('facts_source_proof_sha256') != facts.PROOF_SHA256) or (result.get('observation_only') is not True) or (result.get('eligible_for_training') is not False) or (result.get('exposed_to_learner') is not False):
        raise RuntimeError('Official victory reader result changed identity, policy, or scope')
    expected_keys = {'winner_present', 'winning_team', 'victory_type'}
    if type(expected_winner) is not dict or set(expected_winner) != expected_keys or any((type(expected_winner[key]) is not type(result[key]) for key in expected_keys)) or any((expected_winner[key] != result[key] for key in expected_keys)):
        raise RuntimeError('Official victory reader result differs from its pinned native winner read')
    if terminal:
        first_turn = result.get('first_result_observed_turn')
        if result.get('winner_present') is not True or type(result.get('winning_team')) is not int or type(result.get('victory_type')) is not int or (type(result.get('winner_matches_player_team')) is not bool) or (type(first_turn) is not int) or (not 0 <= first_turn <= turn) or (result.get('new_termination') is True and first_turn != turn) or (result['absent_to_present_observed'] == result['result_present_on_first_observation']) or (result.get('termination_reason') != 'official_native_victory'):
            raise RuntimeError('Official terminal result is not the pinned first victory observation')
    elif result.get('winner_present') is not False or result.get('winning_team') is not None or result.get('victory_type') is not None or (result.get('winner_matches_player_team') is not None) or (result.get('new_termination') is not False) or (result.get('first_result_observed_turn') is not None) or (result.get('termination_reason') is not None) or (result.get('absent_to_present_observed') is not False) or (result.get('result_present_on_first_observation') is not False):
        raise RuntimeError('Official nonterminal result is not the pinned no-winner observation')

def validate_phase_receipts(owner, load_result, facade_result, post160_result, facade_attempt, post160_attempt) -> None:
    """Validate the three prior diagnostic receipts and their shared owner."""
    from civ6_host.runtime.native import native_checkpoint_load as load
    from civ6_host.runtime.native import native_checkpoint_postload_facades as facades
    from civ6_host.runtime.native import native_checkpoint_postload160 as post160
    if type(owner) is not load.NativeLoadBackend:
        raise TypeError('Resume needs the retained native Load owner')
    owner.check_thread()
    key = (id(owner.core), owner.context)
    if load._RETAINED.get(key) is not owner or owner.busy or owner.poisoned or owner.destroyed or (owner.stage != 'post160-observed-awaiting-controlled-stop'):
        raise RuntimeError('Resume owner is not the retained completed +160 context')
    inputs = _validated_resume_inputs(owner)
    game_bytes = len(inputs.game)
    if owner.reader is None or owner.reader.transport.closed is not True or type(owner.reader.transport.cursor) is not int or (owner.reader.transport.cursor != game_bytes):
        raise RuntimeError('Resume Load reader is not closed at the exact Game component boundary')
    receipt = load_result.get('receipt') if type(load_result) is dict else None
    if type(load_result) is not dict or not _exact_bool(load_result, 'raw_component_load_observed') or (not _exact_bool(load_result, 'controlled_stop_required')) or (not _exact_bool(load_result, 'post160_called', False)) or (type(receipt) is not dict) or (type(receipt.get('status')) is not int) or (receipt.get('status') != 0) or (type(receipt.get('bytes_consumed')) is not int) or (receipt.get('bytes_consumed') != game_bytes) or (not _exact_bool(receipt, 'scheduler_ledger_reconciliation_pending')):
        raise RuntimeError('Resume Load receipt is not the exact matched raw-load boundary')
    readback = load_result.get('readback')
    _require_matched_readback(readback, inputs, 'Load')
    if type(facade_attempt) is not facades.NativeFacadeBackend or facade_attempt.owner is not owner or facade_attempt.load_result is not load_result or (facade_attempt.attempted is not True) or (facade_attempt.publisher is not owner.prefix.view_publisher) or (type(facade_result) is not dict) or (not _exact_bool(facade_result, 'cache_facades_populated')) or (not _exact_bool(facade_result, 'jobs_identical')) or (facade_result.get('context_destroyed') is not False) or (facade_result.get('game_update_called') is not False) or (facade_result.get('publish190_called') is not False) or (facade_result.get('scheduler_load_ledger_postrun_required') is not True):
        raise RuntimeError('Resume facade result is not the completed retained cache phase')
    copied = facade_result.get('cache_snapshot_hex')
    if type(copied) is not str or len(copied) != 56 or bytes.fromhex(copied) != facade_attempt.publisher.cache_map_snapshot:
        raise RuntimeError('Resume cache snapshot does not match the retained publisher')
    if type(post160_attempt) is not post160.NativePostload160Backend or post160_attempt.owner is not owner or post160_attempt.load_result is not load_result or (post160_attempt.attempted is not True) or (post160_attempt._facade_attempt is not facade_attempt) or (type(post160_result) is not dict) or (not _exact_bool(post160_result, 'post160_called')) or (not _exact_bool(post160_result, 'call_returned')) or (not _exact_bool(post160_result, 'immediate_jobs_unchanged')) or (not _exact_bool(post160_result, 'postreadback_jobs_unchanged')) or (post160_result.get('post190_called') is not False) or (post160_result.get('game_update_called') is not False) or (post160_result.get('context_destroyed') is not False) or (post160_result.get('scheduler_load_ledger_postrun_required') is not True):
        raise RuntimeError('Resume +160 result is not the completed source-scoped phase')
    post_readback = post160_result.get('readback')
    _require_matched_readback(post_readback, inputs, '+160')
    prefix = owner.prefix
    publisher = getattr(prefix, 'view_publisher', None)
    if prefix is None or prefix.diagnostic_action != 'initial-view' or prefix.configuration_readback_verified is not True or (prefix.diagnostic_production_policy != 'warrior') or (publisher is not facade_attempt.publisher) or publisher._closed or (publisher.native_cache_gate is not True) or (publisher.full_facade_initialization_reproduced is not True) or (publisher._facades is None):
        raise RuntimeError('Resume prefix/publisher identity is not the retained load profile')
    _require_empty_gameplay_registry(prefix.gameplay_scripts)
    if facades._ATTEMPTS.get(key) is not facade_attempt or post160._ATTEMPTS.get(key) is not post160_attempt:
        raise RuntimeError('Resume phase attempt registry does not match this owner')
    if post160_attempt.native_call_attempted is not True:
        raise RuntimeError('Resume +160 native call was not made by the retained attempt')
    topology = owner.topology(game_required=True)
    if topology != owner.bound_identity or owner.game_flag() != 1:
        raise RuntimeError('Resume native Game/provider identity differs from Load/+160')
    owner.owner.require_context(owner.core._handle, owner.context)
    owner.control(empty=True)

@contextmanager
def _python_development_policy(prefix, action_profile, production_policy):
    if action_profile != ACTION_PROFILE or production_policy != PRODUCTION_POLICY or prefix.diagnostic_action != 'initial-view' or (prefix.diagnostic_production_policy != 'warrior'):
        raise RuntimeError('Only the fixed Python develop-round selector is admitted')
    before_action = prefix.diagnostic_action
    before_policy = prefix.diagnostic_production_policy
    prefix.diagnostic_production_policy = PRODUCTION_POLICY
    try:
        yield (ACTION_PROFILE, PRODUCTION_POLICY)
    finally:
        prefix.diagnostic_production_policy = before_policy
        if prefix.diagnostic_action != before_action:
            raise RuntimeError('Resume changed the retained initial-view action profile')

@contextmanager
def _bounded_public_updates(actions, expected_method, limit=MAX_PUBLIC_GAME_UPDATES):
    """Temporarily count the real Game+0x30 calls made by bounded helpers."""
    if type(limit) is not int or limit != MAX_PUBLIC_GAME_UPDATES or 'update_game_once' in getattr(actions, '__dict__', {}):
        raise RuntimeError('Unexpected or already wrapped public update method')
    original = actions.update_game_once
    if getattr(original, '__func__', None) is not expected_method:
        raise RuntimeError('Public game update method differs from the pinned action transport')
    counter = {'count': 0}

    def bounded():
        if counter['count'] >= limit:
            raise RuntimeError('Resume exceeded its 145 public Game updates')
        counter['count'] += 1
        return original()
    actions.update_game_once = bounded
    try:
        yield counter
    finally:
        del actions.update_game_once

class RetainedResumePorts:
    """Bind the injected one-round protocol to the retained, already-loaded prefix."""

    def __init__(self, owner, *, emit=None):
        self.owner = owner
        self._emit_official_result = emit
        self.inputs = _validated_resume_inputs(owner)
        self.start_turn = self.inputs.expected_turn
        self.end_turn = self.start_turn + 1
        self.prefix = owner.prefix
        self._publisher_at_start = getattr(self.prefix, 'view_publisher', None)
        self._facades_at_start = getattr(self._publisher_at_start, '_facades', None)
        self._selected = None
        self._last_state = None
        self._native_flags_written = False
        self._loaded_score_bound_readback = None

    def late_round_mode(self):
        """This adapter owns one resumed round; the late subclass overrides it."""
        return False

    def load_phase(self):
        return self.owner.stage

    def prefix_action_profile(self):
        return self.prefix.diagnostic_action

    def configuration_readback_verified(self):
        return self.prefix.configuration_readback_verified

    def publisher_ready(self):
        publisher = getattr(self.prefix, 'view_publisher', None)
        return bool(publisher is self._publisher_at_start and publisher is not None and (publisher._facades is self._facades_at_start) and (not publisher._closed) and (publisher._facades is not None) and (publisher.full_facade_initialization_reproduced is True) and (publisher.native_cache_gate is True) and (len(publisher.cache_map_snapshot or b'') == 28))

    def publisher(self):
        return self.prefix.view_publisher

    def select_python_policy(self, action_profile, production_policy):
        if self._selected is not None:
            raise RuntimeError('Python diagnostic policy can be selected only once')
        if action_profile != ACTION_PROFILE or production_policy != PRODUCTION_POLICY or self.prefix.diagnostic_action != 'initial-view':
            raise RuntimeError('Unexpected Python resume policy')
        self._selected = (action_profile, production_policy)
        return self._selected

    def native_flags_written(self):
        return self._native_flags_written

    def _evaluate_observer(self, player_id, turn):
        from civ6_host.runtime.native import native_episode_facts as facts
        source = facts.build_source(player_id, turn)
        payload = self.prefix.runtime.evaluate_text(self.prefix.ui_child, source, b'@native_resume_local_observer')
        result = facts.parse_facts(payload, player_id, turn)
        if result['is_alive'] is not True:
            raise RuntimeError('Resume actor is not alive in the loaded player view')
        return result['player_id']

    def local_observer(self):
        if type(self._last_state) is not dict:
            raise RuntimeError('No fresh player-view state exists for observer validation')
        pid = self._last_state['local_player']
        return self._evaluate_observer(pid, self._last_state['current_game_turn'])

    def queues_empty(self):
        prefix = self.prefix
        if type(prefix.actions.pending) is not list or prefix.actions.pending or type(prefix.deferred_events.pending) is not list or prefix.deferred_events.pending:
            return False
        self.owner.control(empty=True)
        ring = prefix.deferred_events.private_progress_ring
        if ring is not None:
            diagnostic = ring.diagnostic()
            selector = diagnostic.get('selector')
            cursors = diagnostic.get('bank_cursors')
            if diagnostic.get('poisoned') is not False or type(selector) is not int or type(cursors) is not list or (len(cursors) != 2) or any((type(v) is not int or v < 0 for v in cursors)) or (cursors[selector & 1] != 0):
                return False
        return True

    def _verify_previctory12_loaded_bound(self, phase):
        if self.inputs.profile_name != 'previctory12':
            return
        from civ6_host.runtime.native import native_checkpoint_previctory_profile as profile
        if phase == 'after-load-initial-publication':
            if self._loaded_score_bound_readback is not None:
                raise RuntimeError('Loaded score-bound read may run only once')
            from civ6_host.runtime.native import native_score_limit_diagnostic as score_limit
            result = score_limit.observe(self.prefix, 0, self.start_turn, 12)
            profile.validate_loaded_score_bound(result)
            if self.queues_empty() is not True:
                raise RuntimeError('Loaded score-bound reader left queued work')
            self._loaded_score_bound_readback = result
            if callable(self._emit_official_result):
                self._emit_official_result('native_checkpoint_loaded_score_bound_verified', profile_name='previctory12', result=result, full_configuration_equivalence_claimed=False, eligible_for_training=False)
        else:
            profile.validate_loaded_score_bound(self._loaded_score_bound_readback)

    def observe_victory_boundary(self, player_id, turn, phase):
        """Read the official result from this retained, already-published UI child."""
        phases = {'after-load-initial-publication': (0, self.start_turn), 'after-player-0-readiness': (0, self.start_turn), 'after-player-1-readiness': (1, self.start_turn), 'after-player-0-decision-phase': (0, self.start_turn), 'after-player-1-decision-phase': (1, self.start_turn), 'after-player-0-endturn-handoff': (1, self.start_turn), 'after-completed-echo-before-next-update': (1, self.start_turn), 'after-final-update-publication': (0, self.end_turn)}
        if phase == 'after-next-turn-readiness-update':
            if getattr(self.inputs, 'profile_name', None) != 'previctory12' or self.start_turn != 12 or self.end_turn != 13:
                raise RuntimeError('Post-round readiness result is only admitted for previctory12')
            phases[phase] = (0, self.end_turn)
        state = self._last_state
        if phase == 'after-next-turn-readiness-update':
            rows = state.get('players') if type(state) is dict else None
            if type(rows) is not list or len(rows) != 2 or type(rows[0]) is not dict or (rows[0].get('complete') is not True):
                raise RuntimeError('Previctory readiness boundary must be the complete player-0 phase')
        if type(phase) is not str or phase not in phases or type(player_id) is not int or (player_id not in (0, 1)) or (type(turn) is not int) or (phases[phase] != (player_id, turn)) or (type(state) is not dict) or (state.get('local_player') != player_id) or (state.get('current_game_turn') != turn) or (self.publisher_ready() is not True) or (self.prefix.ui_child is None) or (self.queues_empty() is not True):
            raise RuntimeError('Retained victory read needs its exact published, drained phase')
        self._verify_previctory12_loaded_bound(phase)
        from civ6_host.runtime.native import native_victory_diagnostic as diagnostic
        from civ6_host.runtime.native import native_winning_team as winning
        from civ6_host.runtime.native.native_episode_identity import require_episode
        identity = require_episode(self.prefix)
        winner = winning.parse(self.prefix.runtime.evaluate_text(self.prefix.ui_child, winning.source(), b'@native_retained_resume_winning_team'))
        try:
            try:
                result = diagnostic.observe_victory_boundary(self.prefix, player_id, turn, winner)
            except BaseException as error:
                from civ6_host.runtime.native.native_victory_diagnostic import NativeVictoryReached
                if type(error) is not NativeVictoryReached:
                    raise
                _validate_official_victory_result(error.result, player_id, turn, identity, winner, terminal=True)
                if callable(self._emit_official_result):
                    self._emit_official_result('native_checkpoint_resume_official_result_observed', phase=phase, player_id=player_id, current_game_turn=turn, result=error.result)
                raise
            _validate_official_victory_result(result, player_id, turn, identity, winner, terminal=False)
            if callable(self._emit_official_result):
                self._emit_official_result('native_checkpoint_resume_official_result_observed', phase=phase, player_id=player_id, current_game_turn=turn, result=result)
            return result
        finally:
            if self.queues_empty() is not True:
                raise RuntimeError('Retained victory reader left queued native work')

    def pending_actions(self):
        return len(self.prefix.actions.pending)

    def observe(self):
        self.owner.check_thread()
        state = self.prefix.inspect_player_view()
        if type(state) is not dict or type(state.get('current_game_turn')) is not int or type(state.get('local_player')) is not int:
            raise RuntimeError('Loaded player view did not return its exact state shape')
        self._last_state = state
        return state

    def readiness(self, state, player_id):
        result = self.prefix.inspect_turn_readiness(state, player_id=player_id)
        self._last_state = result
        return result

    def resolve_development(self, player_id, *, action_profile, production_policy, policy_chosen_by):
        if policy_chosen_by != 'python-diagnostic' or self._selected != (action_profile, production_policy):
            raise RuntimeError('Development action is not the selected Python diagnostic profile')
        if type(player_id) is not int or player_id not in (0, 1) or type(self._last_state) is not dict or (self._last_state.get('local_player') != player_id) or (type(self._last_state.get('current_game_turn')) is not int) or (self._last_state.get('current_game_turn') not in (self.start_turn, self.end_turn)):
            raise RuntimeError('Development requires the fresh matching loaded-player observation')
        if player_id not in self.prefix.development_players:
            from civ6_host.runtime.native import native_city_production_observation as city_obs
            city_obs.verify_own_entity_source()
            roster = city_obs.parse_own_entity_snapshot(self.prefix.runtime.evaluate_text(self.prefix.ui_child, city_obs.own_entity_snapshot_source(player_id), b'@native_resume_owned_city_guard', capacity=262144), player_id)
            if type(roster.get('game_turn')) is not int or roster['game_turn'] != self._last_state['current_game_turn'] or type(roster.get('cities')) is not list or (not roster['cities']):
                raise RuntimeError('Post-Load player has no source-verified owned city')
            self.prefix.development_players.add(player_id)
        with _python_development_policy(self.prefix, action_profile, production_policy):
            self.prefix.inspect_development_decisions(player_id)

    def read_blockers(self, player_id, turn):
        from civ6_host.runtime.native import native_turn_decisions as decisions
        source = decisions.blocker_source(player_id)
        payload = self.prefix.runtime.evaluate_text(self.prefix.ui_child, source, b'@native_resume_endturn_blockers')
        return decisions.parse_blockers(payload, player_id, turn)

    def manual_endturn_gate(self, player_id, turn):
        from civ6_host.runtime.native import native_endturn_gate as gate
        payload = self.prefix.runtime.evaluate_text(self.prefix.ui_child, gate.gate_source(player_id), b'@native_resume_manual_endturn_gate')
        return gate.parse_gate(payload, player_id, turn)

    def request_endturn(self, player_id):
        return self.prefix.actions.request_end_turn(player_id)

    def deliver_one(self):
        return self.prefix.actions.deliver_one()

    def drain(self):
        return self.prefix.deferred_events.drain_empty_receivers()

    def wait_for_completed_round_echo(self, turn):
        from civ6_host.runtime.native.native_ai_round_pump import wait_for_completed_round_echo
        state = wait_for_completed_round_echo(self.prefix, turn, max_updates=128)
        self._last_state = state
        return state

    def completed_round_echo_valid(self, player, turn):
        if type(turn) is not int or turn != self.start_turn:
            return False
        flags = self.prefix.actions.validate_completed_round_echo(player)
        return flags == b'\x01\x01\x00\x00'

    def deliver_completed_round_echo(self, player):
        return self.prefix.actions.deliver_completed_round_echo(player)

    def update_game_once(self):
        return self.prefix.actions.update_game_once()

def _execute_attempt(owner, ports_factory, *, fatal, attempts, key, emit=None):
    if key in attempts:
        raise RuntimeError('Loaded-checkpoint resume attempt cannot be retried')
    if owner.busy:
        raise RuntimeError('Loaded-checkpoint owner is already busy')
    attempts[key] = True
    try:
        ports = ports_factory()
        if owner.busy:
            raise RuntimeError('Loaded-checkpoint owner became busy during preflight')
        owner.busy = True
        with _bounded_public_updates(ports.prefix.actions, __import__('civ6_host.runtime.native.native_action_transport', fromlist=['NativeActionTransport']).NativeActionTransport.update_game_once) as updates:
            previctory = getattr(getattr(ports, 'inputs', None), 'profile_name', None) == 'previctory12'
            result = protocol.run_one_round(ports, start_turn=ports.start_turn, **{'_previctory_readiness': True} if previctory else {})
        if type(result) is dict and result.get('terminal_result_observed') is True:
            _validate_terminal_identity(owner, ports, result)
            owner.busy = False
            owner.stage = 'postload-resume-terminal-observed'
            result.update({'profile_name': ports.inputs.profile_name, 'scheduler_load_ledger_postrun_required': True, 'scheduler_load_ledger_reconciled': False, 'context_destroyed': False, 'native_new_game_called': False, 'reset_validated': False, 'full_exe_scheduler_reproduced': False, 'diagnostic_public_game_update_budget': MAX_PUBLIC_GAME_UPDATES, 'diagnostic_public_game_updates': updates['count'], 'eligible_for_training': False, 'terminal_result_observed': True})
            if emit is not None:
                emit('native_checkpoint_resume_terminal_result_observed', **result)
            return result
        _validate_completed_identity(owner, ports)
        owner.busy = False
        owner.stage = 'postload-resume-diagnostic-observed'
        result.update({'profile_name': ports.inputs.profile_name, 'scheduler_load_ledger_postrun_required': True, 'scheduler_load_ledger_reconciled': False, 'context_destroyed': False, 'native_new_game_called': False, 'reset_validated': False, 'full_exe_scheduler_reproduced': False, 'diagnostic_public_game_update_budget': MAX_PUBLIC_GAME_UPDATES, 'diagnostic_public_game_updates': updates['count'], 'eligible_for_training': False})
        if emit is not None:
            emit(f'native_checkpoint_resume_{ports.start_turn}_to_{ports.end_turn}_observed', **result)
        return result
    except BaseException as error:
        owner.poisoned = True
        owner.stage = 'poisoned'
        owner.busy = False
        fatal(error)
        raise RuntimeError('Fatal resume termination unexpectedly returned') from error

def _validate_terminal_identity(owner, ports, result):
    """Validate the unchanged native policy result and retained owner before accepting a stop."""
    from civ6_host.runtime.native import native_checkpoint_load as load
    from civ6_host.runtime.native.native_episode_identity import require_episode
    from civ6_host.runtime.native import native_victory_episode as victory
    from civ6_host.runtime.native import native_episode_facts as facts
    if type(result) is not dict or result.get('terminal_result_observed') is not True or result.get('post_terminal_update_called') is not False or (result.get('eligible_for_training') is not False) or (result.get('training_ready') is not False) or (result.get('learner_transport') is not False) or (result.get('native_flags_written') is not False) or (result.get('complete_game') is not False):
        raise RuntimeError('Terminal resume result exceeds diagnostic scope')
    owner.check_thread()
    key = (id(owner.core), owner.context)
    if load._RETAINED.get(key) is not owner or owner.busy is not True or owner.poisoned or owner.destroyed or (owner.stage != 'post160-observed-awaiting-controlled-stop'):
        raise RuntimeError('Terminal result changed or poisoned its retained owner')
    inputs = _validated_resume_inputs(owner)
    late = ports.late_round_mode() is True
    if late:
        _require_late_input_validation_token(owner, ports)
        if ports.initial_turn != _late_chain_start(inputs) or type(ports.start_turn) is not int or (not ports.initial_turn <= ports.start_turn < ports.initial_turn + 32):
            raise RuntimeError('Late terminal result changed its admitted retained turn chain')
    elif ports.start_turn != inputs.expected_turn:
        raise RuntimeError('Terminal result changed the retained checkpoint turn')
    if inputs is not ports.inputs or ports.prefix is not owner.prefix:
        raise RuntimeError('Terminal result changed the retained checkpoint pair')
    if owner.topology(game_required=True) != owner.bound_identity or owner.game_flag() != 1:
        raise RuntimeError('Terminal result changed the retained native Game identity')
    owner.owner.require_context(owner.core._handle, owner.context)
    owner.control(empty=True)
    prefix = ports.prefix
    publisher = ports._publisher_at_start
    if publisher is None or prefix.view_publisher is not publisher or publisher is not ports.publisher() or publisher._closed or (publisher._facades is not ports._facades_at_start) or prefix.actions.pending or prefix.deferred_events.pending or (ports.queues_empty() is not True):
        raise RuntimeError('Terminal result changed retained facades or left queued work')
    identity = require_episode(prefix)
    native = result.get('terminal_result')
    after = result.get('after')
    phase = result.get('terminal_phase')
    phase_state = {'after-load-initial-publication': (0, 0, False), 'after-player-0-readiness': (0, 0, True), 'after-player-1-readiness': (1, 1, True), 'after-player-0-decision-phase': (0, 0, True), 'after-player-1-decision-phase': (1, 1, True), 'after-player-0-endturn-handoff': (1, 1, False), 'after-completed-echo-before-next-update': (1, None, None), 'after-final-update-publication': (0, 0, None), 'after-next-turn-readiness-update': (0, 0, True)}.get(phase)
    if phase_state is None:
        raise RuntimeError('Unknown retained terminal phase')
    post_transition = phase in ('after-final-update-publication', 'after-next-turn-readiness-update')
    if phase == 'after-next-turn-readiness-update' and (inputs.profile_name != 'previctory12' or ports.start_turn != 12 or ports.end_turn != 13):
        raise RuntimeError('Post-round readiness result is only admitted for previctory12')
    pre_update = not post_transition
    expected_transition = None if pre_update else [ports.start_turn, ports.end_turn]
    if type(native) is not dict or native.get('schema') != 'civ6rl.native_victory_episode.observation.v1' or native.get('policy_id') != victory.POLICY_ID or (native.get('episode_id') != identity.episode_id) or (native.get('game_generation') != identity.game_generation) or (native.get('player_id') not in (0, 1)) or (type(native.get('player_id')) is not int) or (type(native.get('current_game_turn')) is not int) or (type(after) is not dict) or (native['player_id'] != after.get('local_player')) or (native['current_game_turn'] != after.get('current_game_turn')) or (type(after.get('players')) is not list) or (native['winner_present'] is not True) or (type(native.get('winning_team')) is not int) or (type(native.get('victory_type')) is not int) or (native.get('episode_terminated') is not True) or (native.get('termination_reason') != 'official_native_victory') or (native.get('source_proof_sha256') != victory.PROOF_SHA256) or (native.get('facts_source_proof_sha256') != facts.PROOF_SHA256) or (native.get('observation_only') is not True) or (native.get('eligible_for_training') is not False) or (native.get('exposed_to_learner') is not False) or (native.get('global_engine_terminal') is not None) or (native.get('engine_halted') is not None) or (type(native.get('absent_to_present_observed')) is not bool) or (type(native.get('result_present_on_first_observation')) is not bool) or (type(native.get('new_termination')) is not bool) or (type(native.get('first_result_observed_turn')) is not int) or (not 0 <= native['first_result_observed_turn'] <= native['current_game_turn']) or (native['new_termination'] is True and native['first_result_observed_turn'] != native['current_game_turn']) or (native['absent_to_present_observed'] == native['result_present_on_first_observation']) or (result.get('native_turn_transition') != expected_transition) or (result.get('round_completed') is not (not pre_update)):
        raise RuntimeError('Terminal result is not the exact current native victory observation')
    from civ6_host.runtime.native.native_checkpoint_resume_round import _state
    before = result.get('before')
    before_turn = ports.start_turn
    before_local, before_active = (1, 1) if phase in ('after-player-1-readiness', 'after-player-1-decision-phase', 'after-player-0-endturn-handoff') else (0, 0)
    _state(before, turn=before_turn, local=before_local, active=before_active, complete=False)
    if phase in ('after-final-update-publication', 'after-next-turn-readiness-update'):
        players = after.get('players') if type(after) is dict else None
        if type(players) is not list or len(players) != 2 or type(players[0]) is not dict or (type(players[0].get('complete')) is not bool):
            raise RuntimeError('Terminal final-publication completion flag is malformed')
        if phase == 'after-next-turn-readiness-update' and players[0]['complete'] is not True:
            raise RuntimeError('Previctory readiness terminal requires complete player-0 state')
        _state(after, turn=native['current_game_turn'], local=phase_state[0], active=phase_state[1], complete=players[0]['complete'])
        must_be_new = phase == 'after-next-turn-readiness-update' or players[0]['complete'] is True
        if must_be_new and (native.get('new_termination') is not True or native.get('first_result_observed_turn') != native['current_game_turn'] or native.get('absent_to_present_observed') is not True or (native.get('result_present_on_first_observation') is not False)):
            raise RuntimeError('Completed readiness phase lacks an immediate new official result')
    else:
        _state(after, turn=native['current_game_turn'], local=phase_state[0], active=phase_state[1], complete=phase_state[2])
    if pre_update and native['current_game_turn'] != ports.start_turn:
        raise RuntimeError('Pre-update terminal result is not at the retained start turn')
    if not pre_update and native['current_game_turn'] != ports.end_turn:
        raise RuntimeError('Post-update terminal result lacks the observed completed turn')

def _validate_completed_identity(owner, ports):
    """Require the same retained ownership, matched inputs and final quiescence."""
    from civ6_host.runtime.native import native_checkpoint_load as load
    owner.check_thread()
    key = (id(owner.core), owner.context)
    if load._RETAINED.get(key) is not owner or owner.busy is not True or owner.poisoned or owner.destroyed or (owner.stage != 'post160-observed-awaiting-controlled-stop'):
        raise RuntimeError('Resume changed or poisoned the retained Load owner')
    inputs = _validated_resume_inputs(owner)
    if inputs is not ports.inputs or ports.start_turn != inputs.expected_turn or ports.end_turn != inputs.expected_turn + 1:
        raise RuntimeError('Resume changed the retained matched input pair or turn profile')
    if owner.topology(game_required=True) != owner.bound_identity or owner.game_flag() != 1:
        raise RuntimeError('Resume changed native Game/context identity')
    owner.owner.require_context(owner.core._handle, owner.context)
    owner.control(empty=True)
    prefix = ports.prefix
    if owner.prefix is not prefix or ports._publisher_at_start is None or prefix.view_publisher is not ports._publisher_at_start or (ports._publisher_at_start is not ports.publisher()) or (ports._publisher_at_start._facades is not ports._facades_at_start) or prefix.view_publisher._closed or prefix.actions.pending or prefix.deferred_events.pending:
        raise RuntimeError('Resume changed the retained publisher or left queued work')

def run_retained_resume(owner, load_result, facade_result, post160_result, *, emit, fatal=None):
    """Concrete retained-owner entry; guarded by source pins and phase receipts."""
    from civ6_host.runtime.native import native_checkpoint_load as load
    from civ6_host.runtime.native import native_checkpoint_postload_facades as facades
    from civ6_host.runtime.native import native_checkpoint_postload160 as post160
    if type(owner) is not load.NativeLoadBackend:
        raise TypeError('Resume requires the retained NativeLoadBackend')
    key = (id(owner.core), owner.context)
    if key not in facades._ATTEMPTS or key not in post160._ATTEMPTS or key not in load._RETAINED:
        raise RuntimeError("Resume does not have this Load owner's retained phase registry")
    if fatal is None:
        fatal = load._fatal

    def make_ports():
        verify_source_bundle()
        facade_attempt = facades._ATTEMPTS.get(key)
        post_attempt = post160._ATTEMPTS.get(key)
        validate_phase_receipts(owner, load_result, facade_result, post160_result, facade_attempt, post_attempt)
        return RetainedResumePorts(owner, emit=emit)
    if not callable(emit):
        raise ValueError('A bounded resume diagnostic emitter is required')
    return _execute_attempt(owner, make_ports, fatal=fatal, attempts=_ATTEMPTS, key=key, emit=emit)

class RetainedLateRoundsPorts(RetainedResumePorts):
    """Adapter for the two explicit retained multiround profiles."""

    def __init__(self, owner):
        super().__init__(owner)
        self.initial_turn = _late_chain_start(self.inputs)
        self._next_round_turn = self.initial_turn
        self._late_selected_policy = None
        self._input_validation_token = _LateInputValidationToken(owner, self)

    def late_round_mode(self):
        return True

    def late_round_initial_turn(self):
        if type(self.initial_turn) is not int or self.initial_turn != _late_chain_start(self.inputs):
            raise RuntimeError('Late chain initial turn differs from the retained pair')
        return self.initial_turn

    def begin_late_round(self, turn):
        initial = self.late_round_initial_turn()
        if type(turn) is not int or not initial <= turn < initial + 32 or turn != self._next_round_turn:
            raise RuntimeError('Late round must follow the last observed native turn exactly')
        self.start_turn = turn
        self.end_turn = turn + 1

    def finish_late_round(self, observed_end_turn):
        if type(observed_end_turn) is not int or observed_end_turn != self.start_turn + 1 or self.end_turn != observed_end_turn:
            raise RuntimeError('Late round completion did not match its native turn echo')
        self._next_round_turn = observed_end_turn

    def select_python_policy(self, action_profile, production_policy):
        selected = (action_profile, production_policy)
        if selected != (ACTION_PROFILE, PRODUCTION_POLICY):
            raise RuntimeError('Late mode only admits the fixed Python diagnostic policy')
        if self._late_selected_policy is None:
            self._late_selected_policy = selected
            self._selected = selected
        elif self._late_selected_policy != selected:
            raise RuntimeError('Late mode policy selection changed between rounds')
        return self._late_selected_policy

@contextmanager
def _bounded_late_public_updates(actions, expected_method, limit):
    if type(limit) is not int or not 145 <= limit <= 4640 or limit % 145 or ('update_game_once' in getattr(actions, '__dict__', {})):
        raise RuntimeError('Unexpected aggregate late-round GameUpdate bound')
    original = actions.update_game_once
    if getattr(original, '__func__', None) is not expected_method:
        raise RuntimeError('Public GameUpdate method differs from pinned action transport')
    counter = {'count': 0, 'round_limit': limit}

    def bounded():
        if counter['count'] >= limit:
            raise RuntimeError('Late resume exceeded its aggregate public GameUpdate budget')
        if counter['count'] >= counter['round_limit']:
            raise RuntimeError('Late resume exceeded its per-round GameUpdate budget')
        counter['count'] += 1
        return original()
    actions.update_game_once = bounded
    try:
        yield counter
    finally:
        del actions.update_game_once

def _validate_late_round_identity(owner, ports, start_turn, end_turn):
    from civ6_host.runtime.native import native_checkpoint_load as load
    owner.check_thread()
    key = (id(owner.core), owner.context)
    if load._RETAINED.get(key) is not owner or owner.busy is not True or owner.poisoned or owner.destroyed or (owner.stage != 'post160-observed-awaiting-controlled-stop'):
        raise RuntimeError('Late resume changed or poisoned the retained Load owner')
    inputs = _require_late_input_validation_token(owner, ports)
    if inputs is not ports.inputs or type(ports.initial_turn) is not int or ports.initial_turn != _late_chain_start(inputs) or (ports.start_turn != start_turn) or (ports.end_turn != end_turn) or ((start_turn, end_turn) != (ports._next_round_turn, ports._next_round_turn + 1)):
        raise RuntimeError('Late resume changed the immutable pair or turn chain')
    if owner.topology(game_required=True) != owner.bound_identity or owner.game_flag() != 1:
        raise RuntimeError('Late resume changed native Game/context identity')
    owner.owner.require_context(owner.core._handle, owner.context)
    owner.control(empty=True)
    prefix = ports.prefix
    publisher = ports._publisher_at_start
    if owner.prefix is not prefix or publisher is None or prefix.view_publisher is not publisher or (publisher is not ports.publisher()) or (publisher._facades is not ports._facades_at_start) or publisher._closed or prefix.actions.pending or prefix.deferred_events.pending or (ports.queues_empty() is not True):
        raise RuntimeError('Late resume changed retained facades or left queued work')

def _execute_late_round_attempt(owner, ports_factory, *, fatal, attempts, key, requested_rounds, emit=None):
    if type(requested_rounds) is not int or not 1 <= requested_rounds <= 32:
        raise ValueError('Late bounded resume requires an exact round count in 1..32')
    if key in attempts:
        raise RuntimeError('Loaded-checkpoint resume attempt cannot be retried')
    if owner.busy:
        raise RuntimeError('Loaded-checkpoint owner is already busy')
    attempts[key] = True
    ports = None
    try:
        ports = ports_factory()
        if owner.busy:
            raise RuntimeError('Loaded-checkpoint owner became busy during preflight')
        owner.busy = True
        transitions = []
        first_before = None
        terminal_round = None
        current_turn = _late_chain_start(ports.inputs)
        if type(ports.initial_turn) is not int or ports.initial_turn != current_turn:
            raise RuntimeError('Late-round adapter initial turn differs from its retained pair')
        update_transport = __import__('civ6_host.runtime.native.native_action_transport', fromlist=['NativeActionTransport']).NativeActionTransport.update_game_once
        with _bounded_late_public_updates(ports.prefix.actions, update_transport, requested_rounds * 145) as updates:
            for ordinal in range(1, requested_rounds + 1):
                ports.begin_late_round(current_turn)
                updates_before_round = updates['count']
                updates['round_limit'] = min(updates_before_round + 145, requested_rounds * 145)
                one = protocol.run_one_round(ports, start_turn=current_turn, _late_round_chain=True)
                end_turn = current_turn + 1
                if type(one) is dict and one.get('terminal_result_observed') is True:
                    _validate_terminal_identity(owner, ports, one)
                    if updates['count'] - updates_before_round > 145:
                        raise RuntimeError('A late terminal round exceeded its 145 GameUpdate guard')
                    _validate_late_round_identity(owner, ports, current_turn, end_turn)
                    terminal_round = one
                    if one.get('round_completed') is True:
                        ports.finish_late_round(end_turn)
                        transitions.append([current_turn, end_turn])
                        if emit is not None:
                            emit('native_round_effect_verified', before=one['before'], after=one['after'], origin='retained-late380-checkpoint-resume' if ports.inputs.profile_name == 'late380' else 'retained-checkpoint150-resume' if ports.inputs.profile_name == 'retained150' else 'retained-checkpoint118-resume', round_ordinal=ordinal, rounds_requested=requested_rounds, round_transition=[current_turn, end_turn], terminal_result_observed=True, eligible_for_training=False)
                        current_turn = end_turn
                    break
                if one.get('native_turn_transition') != [current_turn, end_turn] or one.get('native_flags_written') is not False or one.get('complete_game') is not False or (one.get('training_ready') is not False):
                    raise RuntimeError('Late resume round lacks its exact native transition receipt')
                if updates['count'] - updates_before_round > 145:
                    raise RuntimeError('A late resume round exceeded its 145 GameUpdate guard')
                _validate_late_round_identity(owner, ports, current_turn, end_turn)
                ports.finish_late_round(end_turn)
                if first_before is None:
                    first_before = one['before']
                transitions.append([current_turn, end_turn])
                if emit is not None:
                    emit('native_round_effect_verified', before=one['before'], after=one['after'], origin='retained-late380-checkpoint-resume' if ports.inputs.profile_name == 'late380' else 'retained-checkpoint150-resume' if ports.inputs.profile_name == 'retained150' else 'retained-checkpoint118-resume', round_ordinal=ordinal, rounds_requested=requested_rounds, round_transition=[current_turn, end_turn], eligible_for_training=False)
                current_turn = one['after']['current_game_turn']
        final_inputs = _validated_resume_inputs(owner)
        if final_inputs is not ports.inputs:
            raise RuntimeError('Late resume final full input validation changed the admitted pair')
        _require_late_input_validation_token(owner, ports)
        owner.busy = False
        owner.stage = 'postload-resume-terminal-observed' if terminal_round is not None else 'postload-resume-diagnostic-observed'
        result = {'profile_name': ports.inputs.profile_name, 'native_turn_transitions': transitions, 'native_turn_transition': [ports.initial_turn, current_turn], 'rounds_requested': requested_rounds, 'rounds_completed': len(transitions), 'before': first_before, 'after': one['after'], 'action_profile': ACTION_PROFILE, 'production_policy': PRODUCTION_POLICY, 'policy_chosen_by': 'python-diagnostic', 'native_flags_written': False, 'native_new_game_called': False, 'reset_validated': False, 'context_destroyed': False, 'full_exe_scheduler_reproduced': False, 'scheduler_load_ledger_postrun_required': True, 'scheduler_load_ledger_reconciled': False, 'diagnostic_public_game_update_budget': requested_rounds * 145, 'diagnostic_public_game_updates': updates['count'], 'eligible_for_training': False, 'complete_game': False, 'training_ready': False, 'learner_transport': False}
        if terminal_round is not None:
            result.update({'terminal_result_observed': True, 'terminal_result': terminal_round['terminal_result'], 'terminal_phase': terminal_round['terminal_phase'], 'terminal_round_result': terminal_round, 'native_turn_transition': terminal_round['native_turn_transition'], 'round_completed': terminal_round['round_completed'], 'terminal_round_ordinal': len(transitions) if terminal_round['round_completed'] else len(transitions) + 1, 'rounds_completed': len(transitions), 'terminal_chain_start_turn': ports.initial_turn, 'terminal_chain_end_turn': current_turn, 'post_terminal_update_called': False, 'native_flags_written': False, 'context_destroyed': False, 'reset_validated': False, 'native_new_game_called': False, 'eligible_for_training': False})
        if emit is not None:
            aggregate_stage = 'native_checkpoint_resume_terminal_result_observed' if terminal_round is not None else 'native_checkpoint_resume_late114_rounds_observed' if ports.inputs.profile_name == 'late380' else 'native_checkpoint_resume_retained150_rounds_observed' if ports.inputs.profile_name == 'retained150' else 'native_checkpoint_resume_retained118_rounds_observed'
            emit(aggregate_stage, **result)
        return result
    except BaseException as error:
        owner.poisoned = True
        owner.stage = 'poisoned'
        owner.busy = False
        fatal(error)
        raise RuntimeError('Fatal late resume termination unexpectedly returned') from error
    finally:
        _invalidate_late_input_validation_token(ports)

def run_retained_late_rounds(owner, load_result, facade_result, post160_result, *, requested_rounds, emit, fatal=None):
    """Run one retained-pair attempt containing 1..32 observed turns."""
    from civ6_host.runtime.native import native_checkpoint_load as load
    from civ6_host.runtime.native import native_checkpoint_postload_facades as facades
    from civ6_host.runtime.native import native_checkpoint_postload160 as post160
    if type(owner) is not load.NativeLoadBackend:
        raise TypeError('Late resume requires the retained NativeLoadBackend')
    if type(requested_rounds) is not int or not 1 <= requested_rounds <= 32:
        raise ValueError('Late bounded resume requires an exact round count in 1..32')
    key = (id(owner.core), owner.context)
    if key not in facades._ATTEMPTS or key not in post160._ATTEMPTS or key not in load._RETAINED:
        raise RuntimeError("Late resume lacks this Load owner's retained phase registry")
    if fatal is None:
        fatal = load._fatal

    def make_ports():
        verify_source_bundle()
        facade_attempt = facades._ATTEMPTS.get(key)
        post_attempt = post160._ATTEMPTS.get(key)
        validate_phase_receipts(owner, load_result, facade_result, post160_result, facade_attempt, post_attempt)
        return RetainedLateRoundsPorts(owner, emit=emit)
    if not callable(emit):
        raise ValueError('A bounded late resume diagnostic emitter is required')
    return _execute_late_round_attempt(owner, make_ports, fatal=fatal, attempts=_ATTEMPTS, key=key, requested_rounds=requested_rounds, emit=emit)
