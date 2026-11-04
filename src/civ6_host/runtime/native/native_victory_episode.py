"""Explicit episode policy: stop at the first official native victory result.

The reader is the existing protected current-actor episode-facts reader. This
module neither executes it nor changes native state. An episode ending under
this policy does not assert that the engine halted: official OneMoreTurn is an
optional continuation. No winner is not evidence that the engine is running.
"""
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
from pathlib import Path
from civ6_host.runtime.native import native_episode_facts
from civ6_host.runtime.native.native_source_cache import load_pinned_json
ROOT = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_victory_episode.py')))).resolve().parents[1]
PROOF_SHA256 = 'b7de76fcb45fde2ba96958e18c71ccbcc48dae6837beb7fead6c4e44aaeb694b'
_PROOF = ROOT / 'evidence/native-victory-transition' / (PROOF_SHA256 + '.json')
POLICY_ID = 'first-official-native-victory-v1'

def verify_source(*, core_sha256='d7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'):
    if core_sha256 != 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3':
        from civ6_host.runtime.xp1_session_result import verify_reader_source
        return verify_reader_source(core_sha256)
    proof = load_pinned_json(_PROOF, PROOF_SHA256)
    contract = proof.get('result_contract', {})
    if proof.get('schema') != 'civ6rl.native_victory_transition.static.v1' or proof.get('images', {}).get('core_sha256') != 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3' or proof.get('images', {}).get('exe_sha256') != 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63' or (proof.get('sources', {}).get('episode_facts') != native_episode_facts.PROOF_SHA256) or (contract.get('callback_va') != '0x180523ed0') or (contract.get('absent_team') != -1) or (contract.get('absent_lua_arity') != 0) or (contract.get('present_lua_arity') != 2) or (tuple(contract.get('present_result_order', ())) != ('winning_team', 'victory_type')) or (contract.get('host_event_kind') != 477734356) or (contract.get('write_before_notification') is not True) or (proof.get('episode_policy_contract', {}).get('policy_id') != POLICY_ID) or (proof.get('native_execution') is not False):
        raise RuntimeError('Native victory-result source contract changed')
    native_episode_facts.verify_source()
    return proof

def build_source(player_id, expected_turn, *, core_sha256='d7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'):
    """Read only the current local/observer actor; no active/alive precondition."""
    verify_source(core_sha256=core_sha256)
    return native_episode_facts.build_source(player_id, expected_turn, core_sha256=core_sha256)

def guard_case(*, core_sha256='d7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'):
    """Run actual Lua reader guards under Lua5.1/HKS; not a native victory test."""
    verify_source(core_sha256=core_sha256)
    return native_episode_facts.guard_case(core_sha256=core_sha256)

class FirstOfficialVictory:
    """One instance per episode, including resets/loads; no implicit reset.

    observe() accepts the protected reader's raw payload. Call it only after
    native delivery/update and public-state publication have completed. The
    class cannot validate that external scheduling boundary. Repeated reads of
    the same result are idempotent. Disappearing/changed results or backward
    turns require a new episode instance and are refused without state change.
    """

    def __init__(self, episode_id, *, core_sha256='d7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'):
        if type(episode_id) is not str or not 1 <= len(episode_id) <= 128 or (not episode_id.isascii()) or any((ord(c) < 33 or ord(c) > 126 for c in episode_id)):
            raise ValueError('Explicit bounded episode identity required')
        verify_source(core_sha256=core_sha256)
        self._core_sha256 = core_sha256
        self.episode_id = episode_id
        self._last_turn = None
        self._seen_absent = False
        self._winner = None
        self._first_result_turn = None
        self._transition_observed = False

    def observe(self, payload, player_id, expected_turn):
        from civ6_host.runtime.xp1_session_result import bind_policy_provenance
        verify_source(core_sha256=self._core_sha256)
        facts = native_episode_facts.parse_facts(payload, player_id, expected_turn, core_sha256=self._core_sha256)
        turn = facts['current_game_turn']
        if self._last_turn is not None and turn < self._last_turn:
            raise ValueError('Episode turn moved backwards; explicit new episode required')
        current = (facts['winning_team'], facts['victory_type']) if facts['winner_present'] else None
        if self._winner is not None and current != self._winner:
            raise ValueError('Official victory result changed/disappeared within episode')
        first_result = current is not None and self._winner is None
        if first_result:
            self._winner = current
            self._first_result_turn = turn
            self._transition_observed = self._seen_absent
        elif current is None:
            self._seen_absent = True
        self._last_turn = turn
        return bind_policy_provenance({'schema': 'civ6rl.native_victory_episode.observation.v1', 'episode_id': self.episode_id, 'policy_id': POLICY_ID, 'player_id': player_id, 'current_game_turn': turn, 'team_id': facts['team_id'], 'is_alive': facts['is_alive'], 'was_ever_alive': facts['was_ever_alive'], 'episode_terminated': current is not None, 'new_termination': first_result, 'termination_reason': 'official_native_victory' if current is not None else None, 'first_result_observed_turn': self._first_result_turn, 'absent_to_present_observed': self._transition_observed, 'result_present_on_first_observation': current is not None and (not self._transition_observed), 'winner_present': facts['winner_present'], 'winning_team': facts['winning_team'], 'victory_type': facts['victory_type'], 'winner_matches_player_team': facts['winner_matches_player_team'], 'global_engine_terminal': None, 'engine_halted': None, 'personal_elimination_used_as_global_trigger': False, 'source_proof_sha256': PROOF_SHA256, 'facts_source_proof_sha256': native_episode_facts.PROOF_SHA256, 'observation_only': True, 'eligible_for_training': False, 'exposed_to_learner': False}, self._core_sha256)
