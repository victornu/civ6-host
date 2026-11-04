"""Pure plan for an explicit short Base score-victory diagnostic.

This module performs no native calls or configuration writes and predicts no
winner. Root's existing setters, publication and official victory reader remain
responsible for applying and observing the plan. A default call makes no changes.
"""
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
from pathlib import Path
from civ6_host.runtime.native.native_source_cache import load_pinned_json
ROOT = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_score_turn_limit.py')))).resolve().parents[1]
PROOF_SHA256 = 'ffc81619c7c60351f8275edcb1c9c25170726882c8bd89eb2fd256996d43924c'
_PROOF = ROOT / 'evidence/native-score-turn-limit' / (PROOF_SHA256 + '.json')
MIN_LIMIT = 1
MAX_LIMIT = 500
DEFAULT_MAX_TURNS = 500
DEFAULT_MODE = 'TURNLIMIT_GAMESPEED'
CUSTOM_MODE = 'TURNLIMIT_CUSTOM'
CUSTOM_MODE_HASH = 40503376
GAMESPEED_MODE_HASH = 3740922031
APPLICATION_STAGE = 'after-ruleset-before-startgame'

def verify_source():
    proof = load_pinned_json(_PROOF, PROOF_SHA256)
    contract = proof.get('contract', {})
    bindings = proof.get('bindings', {})
    if proof.get('schema') != 'civ6rl.native_score_turn_limit.static.v1' or proof.get('native_execution') is not False or proof.get('images', {}).get('core_sha256') != 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3' or (proof.get('images', {}).get('exe_sha256') != 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63') or (contract.get('custom_mode_hash') != CUSTOM_MODE_HASH) or (contract.get('positive_custom_max_used_exactly') is not True) or (contract.get('default_max_turns') != DEFAULT_MAX_TURNS) or (contract.get('default_mode') != DEFAULT_MODE) or (contract.get('application_stage') != APPLICATION_STAGE) or (contract.get('end_turn_exclusive') is not True) or (contract.get('public_end_turn_cache_offset') != 48) or (contract.get('diagnostic_only') is not True) or (contract.get('full_standard_game_claim') is not False) or (bindings.get('Game.GetGameEndTurn', {}).get('callback_va') != '0x180522610') or (bindings.get('GameConfiguration.GetStartTurn', {}).get('callback_va') != '0x18055f900') or (proof.get('validation', {}).get('all_captured_instructions_match_pinned_pe') is not True):
        raise RuntimeError('Native score-turn-limit source contract changed')
    return proof

def plan(limit=None):
    """Return ordered setup data; None leaves all existing defaults untouched.

    Bounds 1..500 are a diagnostic policy, not a claimed native maximum. Both
    settings must be applied after ruleset/setup dependencies and before StartGame.
    The native setter/readback must retain SCORE enabled. Cache readback after
    initialization records the exclusive Game.GetGameEndTurn, using the actual
    GameConfiguration.GetStartTurn rather than assuming zero or one.
    """
    if limit is not None and (type(limit) is not int or not MIN_LIMIT <= limit <= MAX_LIMIT):
        raise ValueError('Diagnostic score turn limit must be an integer in 1..500 or None')
    verify_source()
    override = limit is not None
    return {'schema': 'civ6rl.native_score_turn_limit.plan.v1', 'source_proof_sha256': PROOF_SHA256, 'override': override, 'requested_limit': limit, 'default_mode': DEFAULT_MODE, 'default_max_turns': DEFAULT_MAX_TURNS, 'settings': (('GAME_TURN_LIMIT', CUSTOM_MODE), ('GAME_MAX_TURNS', limit)) if override else (), 'mode_hash': CUSTOM_MODE_HASH if override else GAMESPEED_MODE_HASH, 'expected_max_turns': limit if override else DEFAULT_MAX_TURNS, 'require_score_enabled': True, 'score_victory_type': 'VICTORY_SCORE', 'application_stage': APPLICATION_STAGE, 'readback_before_start': ('GAME_TURN_LIMIT', 'GAME_MAX_TURNS', 'VICTORY_SCORE'), 'readback_after_publication': ('Game.GetCurrentGameTurn', 'Game.GetGameEndTurn', 'GameConfiguration.GetStartTurn'), 'custom_end_turn_relation': 'end_turn == published_start_turn + requested_limit' if override else None, 'end_turn_exclusive': True, 'winner_predicted': False, 'termination_policy': 'first-official-native-victory-v1', 'diagnostic_custom_horizon': override, 'full_standard_game_claim': False, 'required_native_witnesses': ('configuration readback matches after ruleset resolution and before StartGame', 'published exclusive end turn agrees with the selected CUSTOM configuration', 'official GetWinningTeam returns its native team/victory pair', 'native victory notification and pending transport complete at the source-proven boundary', 'clean close followed by a fresh episode whose official winner is absent') if override else ()}
