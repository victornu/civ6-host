"""Staged, offline-only profile for the exact fresh Save12 pair.

This module deliberately does not register the profile in production and does
not call native code. Pair admission requires the exact pinned 698 audit
receipt bytes/hash, which are checked before the component pair is returned.
"""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
ROOT = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_checkpoint_previctory_profile.py')))).resolve().parents[1]
PROFILE_ID = 'previctory12'
CORE_SHA256 = 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'
RAW410_PATH = 'evidence/native-newgame-script-prefix410.json'
RAW410_SHA256 = 'd5e62a23b61826c3d365eac7f5759a3cf2d208ecd8d1c797d49d285fae8170fd'
MANIFEST_PATH = 'work/native-checkpoints/3c1c36d188ae465794eb3bd19183cd11/turn12.checkpoint.json'
MANIFEST_SHA256 = '763aac9b13207811ade9f00317463a5053fa551d3192ce05400077048cc30f3a'
GAME_PATH = 'work/native-checkpoints/3c1c36d188ae465794eb3bd19183cd11/turn12.gamecore.raw'
GAME_BYTES = 2633343
GAME_SHA256 = '68218224a4d7fd0a51226e1b8287cf09e8fa1b8950d51ff101d40f88d1087d07'
CONFIGURATION_PATH = 'work/native-checkpoints/3c1c36d188ae465794eb3bd19183cd11/turn12.configuration.raw'
CONFIGURATION_BYTES = 15053
CONFIGURATION_SHA256 = '7f0079922f0d01c87b2c87da953716066ce32d3448e7cd7d5cc6a4faac6cd326'
MANIFEST_SCHEMA = 'civ6rl.native_checkpoint_pre_victory12_components.v1'
SCORE_SOURCE_SHA256 = 'ffc81619c7c60351f8275edcb1c9c25170726882c8bd89eb2fd256996d43924c'
SCORE_CONTEXT_SOURCE_SHA256 = '6dd4f257de13b97ac15b5f4712c94e545d1230459e07695ae748855ea9323bb0'
CONFIGURATION_PROOF_SHA256 = '3d5ef65d87185b09b2925e2c0f61f7181d993b3f25e2e55cc3fbcc3c08a817a7'
AUDIT698_PATH = 'work/native-previctory-audit698/audit410-final.json'
AUDIT698_SHA256 = 'f70e912a2f2d2ee0348782b4a1f8c5c534a0b25b6e6d75d21b7fe614112ce672'
HEX64 = re.compile('^[0-9a-f]{64}$')
MAX_REPORT_BYTES = 32 * 1024 * 1024
MAX_COMPONENT_BYTES = 32 * 1024 * 1024

@dataclass(frozen=True)
class PrevictoryPairProfile:
    profile_id: str = PROFILE_ID
    completed_rounds: int = 11
    expected_turn: int = 12
    width: int = 74
    height: int = 46
    manifest_path: str = MANIFEST_PATH
    manifest_sha256: str = MANIFEST_SHA256
    witness_path: str = RAW410_PATH
    witness_sha256: str = RAW410_SHA256
    game_path: str = GAME_PATH
    game_bytes: int = GAME_BYTES
    game_sha256: str = GAME_SHA256
    configuration_path: str = CONFIGURATION_PATH
    configuration_bytes: int = CONFIGURATION_BYTES
    configuration_sha256: str = CONFIGURATION_SHA256
PREVICTORY12 = PrevictoryPairProfile()

@dataclass(frozen=True)
class MatchedPrevictoryPair:
    profile: PrevictoryPairProfile
    game: bytes
    configuration: bytes
    manifest_sha256: str
    witness_sha256: str
    witness: dict

def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()

def _verify_pinned_bytes(raw: bytes, expected_bytes: int, expected_sha256: str, label: str) -> None:
    if type(raw) is not bytes or type(expected_bytes) is not int or len(raw) != expected_bytes or (_sha(raw) != expected_sha256):
        raise ValueError(label + ' bytes/hash differ from exact profile')

def _contained(root: Path, relative: str) -> Path:
    if type(relative) is not str or not relative:
        raise ValueError('Pair path must be a nonempty relative string')
    rel = _resolve_resource_path(Path(relative))
    if rel.is_absolute() or '..' in rel.parts:
        raise ValueError('Pair path escapes the project root')
    path = _resolve_resource_path(root / rel).resolve()
    if not path.is_relative_to(_resolve_resource_path(root).resolve()):
        raise ValueError('Pair path resolves outside the project root')
    return path

def validate_profile(profile: PrevictoryPairProfile=PREVICTORY12) -> None:
    """Validate exact profile constants and require an audit receipt pin."""
    if type(profile) is not PrevictoryPairProfile or profile != PREVICTORY12:
        raise ValueError('Only the exact staged previctory12 profile is admitted')
    if type(AUDIT698_SHA256) is not str or not HEX64.fullmatch(AUDIT698_SHA256):
        raise ValueError('Independent Save/victory audit 698 receipt is not pinned yet')
    for name in ('completed_rounds', 'expected_turn', 'width', 'height', 'game_bytes', 'configuration_bytes'):
        if type(getattr(profile, name)) is not int:
            raise ValueError('Profile integer field has wrong exact type: ' + name)
    if (profile.completed_rounds, profile.expected_turn, profile.width, profile.height) != (11, 12, 74, 46):
        raise ValueError('Profile differs from exact 11-completed/turn12 74x46 boundary')
    for name in ('manifest_sha256', 'witness_sha256', 'game_sha256', 'configuration_sha256'):
        value = getattr(profile, name)
        if type(value) is not str or not HEX64.fullmatch(value):
            raise ValueError('Invalid profile hash pin: ' + name)
    for name, expected in (('manifest_path', MANIFEST_PATH), ('witness_path', RAW410_PATH), ('game_path', GAME_PATH), ('configuration_path', CONFIGURATION_PATH)):
        if getattr(profile, name) != expected:
            raise ValueError('Profile path differs from pinned Save12 input: ' + name)
    if (profile.manifest_sha256, profile.witness_sha256, profile.game_sha256, profile.configuration_sha256) != (MANIFEST_SHA256, RAW410_SHA256, GAME_SHA256, CONFIGURATION_SHA256) or (profile.game_bytes, profile.configuration_bytes) != (GAME_BYTES, CONFIGURATION_BYTES):
        raise ValueError('Profile pins differ from exact Save12 component pair')

def validate_loaded_score_bound(result: dict) -> None:
    """Validate the official read-only score-bound receipt for Save12.

    This proves only the bounded configured score horizon, not full ruleset or
    game-configuration equality and not a victory prediction.
    """
    expected_ints = {'player_id': 0, 'current_game_turn': 12, 'start_turn': 1, 'effective_end_turn': 13, 'native_configured_max': 12, 'requested_limit': 12, 'score_victory_index': 0}
    if type(result) is not dict:
        raise ValueError('Loaded score-bound result must be a dictionary')
    for key, expected in expected_ints.items():
        value = result.get(key)
        if type(value) is not int or value != expected:
            raise ValueError('Loaded score-bound integer differs: ' + key)
    expected_bools = {'end_turn_exclusive': True, 'effective_bound_verified': True, 'native_victory_inferred': False, 'eligible_for_training': False}
    for key, expected in expected_bools.items():
        if type(result.get(key)) is not bool or result[key] is not expected:
            raise ValueError('Loaded score-bound flag differs: ' + key)
    if result.get('score_victory_type') != 'VICTORY_SCORE' or result.get('source_proof_sha256') != SCORE_SOURCE_SHA256 or result.get('context_source_proof_sha256') != SCORE_CONTEXT_SOURCE_SHA256:
        raise ValueError('Loaded score-bound source or selector differs from Save12 proof')

def _validate_manifest(manifest: dict, profile: PrevictoryPairProfile) -> None:
    if type(manifest) is not dict:
        raise ValueError('Checkpoint manifest must be an object')
    if manifest.get('schema') != MANIFEST_SCHEMA or manifest.get('core_sha256') != CORE_SHA256 or type(manifest.get('completed_rounds')) is not int or (manifest.get('completed_rounds') != profile.completed_rounds) or (type(manifest.get('observed_game_turn')) is not int) or (manifest.get('observed_game_turn') != profile.expected_turn) or (manifest.get('eligible_for_training') is not False) or (manifest.get('full_civ6save_container') is not False) or (manifest.get('native_load_validated') is not False) or (manifest.get('reset_validated') is not False):
        raise ValueError('Manifest metadata differs from exact pre-victory Save12 profile')
    boundary = manifest.get('pre_victory_boundary')
    bound = boundary.get('score_bound') if type(boundary) is dict else None
    if type(bound) is not dict:
        raise ValueError('Manifest lacks the independent score-bound receipt')
    validate_loaded_score_bound(bound)
    control = manifest.get('control')
    if type(control) is not dict or any((type(control.get(key)) is not int for key in ('public_sequence', 'consumed_count', 'private_selector', 'notification_counter', 'metadata_counter'))) or control.get('public_sequence') != control.get('consumed_count') or (control.get('notification_counter') != 0) or (control.get('metadata_counter') != 0) or (manifest.get('jobs_quiescent_before_after') is not True):
        raise ValueError('Manifest native queues/jobs are not proven drained and quiescent')
    receipt = manifest.get('configuration_receipt')
    if type(receipt) is not dict or receipt.get('operation') != 'serialize' or receipt.get('proof_sha256') != CONFIGURATION_PROOF_SHA256 or (receipt.get('native_method_result_observed') is not False) or (receipt.get('native_return_interpreted') is not False) or (receipt.get('eligible_for_training') is not False):
        raise ValueError('Configuration serialization receipt differs from exact source contract')
    components = manifest.get('components')
    if type(components) is not dict or set(components) != {'gamecore', 'application_configuration'}:
        raise ValueError('Manifest must contain exactly the two required components')
    for key, path, size, digest in (('gamecore', profile.game_path, profile.game_bytes, profile.game_sha256), ('application_configuration', profile.configuration_path, profile.configuration_bytes, profile.configuration_sha256)):
        row = components.get(key)
        if type(row) is not dict or type(row.get('path')) is not str or row['path'].replace('\\', '/') != path.replace('\\', '/') or (type(row.get('bytes')) is not int) or (row['bytes'] != size) or (row.get('sha256') != digest):
            raise ValueError('Manifest component row differs from exact profile: ' + key)

def _read_audit_receipt(root: Path) -> dict:
    if type(AUDIT698_SHA256) is not str or not HEX64.fullmatch(AUDIT698_SHA256):
        raise ValueError('Independent Save/victory audit 698 receipt is not pinned yet')
    path = _contained(root, AUDIT698_PATH)
    if _resolve_resource_path(path).stat().st_size > 1024 * 1024:
        raise ValueError('Audit receipt exceeds bounded read size')
    raw = _resolve_resource_path(path).read_bytes()
    if _sha(raw) != AUDIT698_SHA256:
        raise ValueError('Audit receipt differs from its immutable pin')
    audit = json.loads(raw)
    report = audit.get('input_report') if type(audit) is dict else None
    save = audit.get('save12') if type(audit) is dict else None
    child = audit.get('child') if type(audit) is dict else None
    victory = audit.get('official_score_victory') if type(audit) is dict else None
    claims = audit.get('claims') if type(audit) is dict else None
    if type(audit) is not dict or audit.get('schema') != 'civ6rl.native_previctory_save410_audit698.v1' or type(report) is not dict or (report.get('path') != RAW410_PATH) or (type(report.get('bytes')) is not int) or (report['bytes'] != 15381683) or (report.get('sha256') != RAW410_SHA256) or (type(save) is not dict) or (type(save.get('turn')) is not int) or (save.get('turn') != 12) or (type(save.get('completed_rounds')) is not int) or (save.get('completed_rounds') != 11) or (type(save.get('manifest')) is not dict) or (save['manifest'].get('path') != MANIFEST_PATH) or (save['manifest'].get('bytes') != 3916) or (save['manifest'].get('sha256') != MANIFEST_SHA256) or (save.get('stream_closed') is not True) or (save.get('save_status') != 0) or (save.get('load_validated') is not False) or (save.get('reset_validated') is not False) or (save.get('eligible_for_training') is not False) or (save.get('jobs_unchanged_quiescent') is not True) or (save.get('control_unchanged_quiescent') is not True) or (type(save.get('components')) is not dict) or (set(save['components']) != {'gamecore', 'application_configuration'}) or (save['components'].get('gamecore') != {'path': GAME_PATH, 'bytes': GAME_BYTES, 'sha256': GAME_SHA256}) or (save['components'].get('application_configuration') != {'path': CONFIGURATION_PATH, 'bytes': CONFIGURATION_BYTES, 'sha256': CONFIGURATION_SHA256}) or (type(child) is not dict) or (type(child.get('exit_code')) is not int) or (child.get('exit_code') != 0) or (child.get('success') is not True) or (child.get('reaped') is not True) or (child.get('timed_out') is not False) or (type(victory) is not dict) or (victory.get('player_id') != 0) or (victory.get('team_id') != 0) or (victory.get('current_game_turn') != 13) or (victory.get('winning_team') != 0) or (victory.get('victory_type') != 0) or (victory.get('winner_matches_player_team') is not True) or (victory.get('absent_to_present_observed') is not True) or (victory.get('engine_halted') is not None) or (victory.get('eligible_for_training') is not False) or (type(claims) is not dict) or (claims.get('fresh_save_at_observed_turn12') is not True) or (claims.get('official_native_score_victory_observed') is not True) or (claims.get('save_pair_loaded') is not False) or (claims.get('reset_validated') is not False) or (claims.get('complete_game_validated') is not False) or (claims.get('strategic_training_ready') is not False) or (claims.get('eligible_for_training') is not False):
        raise ValueError('Audit receipt does not independently admit this exact Save12 boundary')
    return audit

def read_verified_pair(profile: PrevictoryPairProfile=PREVICTORY12, *, root: Path=ROOT) -> MatchedPrevictoryPair:
    """Read exact Save12 bytes only after validating the pinned audit receipt."""
    validate_profile(profile)
    root = _resolve_resource_path(root).resolve()
    _read_audit_receipt(root)
    manifest_path = _contained(root, profile.manifest_path)
    witness_path = _contained(root, profile.witness_path)
    if _resolve_resource_path(manifest_path).stat().st_size > 1024 * 1024 or _resolve_resource_path(witness_path).stat().st_size > MAX_REPORT_BYTES:
        raise ValueError('Manifest or raw Save/victory report exceeds bounded size')
    manifest_raw = _resolve_resource_path(manifest_path).read_bytes()
    witness_raw = _resolve_resource_path(witness_path).read_bytes()
    if _sha(manifest_raw) != profile.manifest_sha256 or _sha(witness_raw) != profile.witness_sha256:
        raise ValueError('Manifest or raw Save/victory report differs from exact pin')
    manifest = json.loads(manifest_raw)
    _validate_manifest(manifest, profile)
    witness = json.loads(witness_raw)
    if type(witness) is not dict or witness.get('schema') != 'civ6rl.native-host-probe.v1' or witness.get('mode') != 'trace-newgame-script-prefix-no-tuner' or (witness.get('dll_sha256') != CORE_SHA256):
        raise ValueError('Raw witness is not the pinned native Save12 probe report')
    game_path = _contained(root, profile.game_path)
    config_path = _contained(root, profile.configuration_path)
    if game_path.parent != manifest_path.parent or config_path.parent != manifest_path.parent:
        raise ValueError('Paired components must reside beside their exact manifest')
    component_bytes = []
    for path, size, digest in ((game_path, profile.game_bytes, profile.game_sha256), (config_path, profile.configuration_bytes, profile.configuration_sha256)):
        if _resolve_resource_path(path).stat().st_size != size or size > MAX_COMPONENT_BYTES:
            raise ValueError('Component size differs from exact Save12 profile')
        data = _resolve_resource_path(path).read_bytes()
        _verify_pinned_bytes(data, size, digest, path.name)
        component_bytes.append(data)
    components = manifest.get('components')
    if type(components) is not dict or set(components) != {'gamecore', 'application_configuration'}:
        raise ValueError('Manifest must contain exactly the two required components')
    for key, rel, size, digest in (('gamecore', profile.game_path, profile.game_bytes, profile.game_sha256), ('application_configuration', profile.configuration_path, profile.configuration_bytes, profile.configuration_sha256)):
        row = components.get(key)
        if type(row) is not dict or row.get('path', '').replace('\\', '/') != rel.replace('\\', '/') or type(row.get('bytes')) is not int or (row['bytes'] != size) or (row.get('sha256') != digest):
            raise ValueError('Manifest component row differs from exact profile: ' + key)
    game, config = component_bytes
    if game[:4] != b'\x05\x00\x00\x00':
        raise ValueError('Game component lacks the observed native version prefix')
    return MatchedPrevictoryPair(profile, game, config, profile.manifest_sha256, profile.witness_sha256, witness)

def read_selected_inputs(profile_name: str, root: Path, InputsClass):
    """Production-shaped explicit selector; no fallback or approximate pair."""
    if type(profile_name) is not str or profile_name != PROFILE_ID:
        raise ValueError('Unknown immutable checkpoint profile')
    if not callable(InputsClass):
        raise TypeError('An explicit matched-input type is required')
    pair = read_verified_pair(PREVICTORY12, root=root)
    inputs = InputsClass(pair.configuration, pair.game, pair.manifest_sha256, PREVICTORY12.expected_turn, PREVICTORY12.width, PREVICTORY12.height, PROFILE_ID)
    validate_load_binding(inputs, root, InputsClass)
    return (inputs, pair.witness)

def validate_load_binding(inputs, root: Path, InputsClass) -> None:
    """Require the exact owner input type and bytes for the audited pair."""
    if type(inputs) is not InputsClass:
        raise TypeError('Load input binding requires the exact matched-input type')
    validate_profile(PREVICTORY12)
    _read_audit_receipt(_resolve_resource_path(root).resolve())
    profile_name = getattr(inputs, 'profile_name', None)
    manifest_sha256 = getattr(inputs, 'manifest_sha256', None)
    if type(profile_name) is not str or profile_name != PROFILE_ID or type(getattr(inputs, 'configuration', None)) is not bytes or (type(getattr(inputs, 'game', None)) is not bytes) or (len(inputs.configuration) != CONFIGURATION_BYTES) or (_sha(inputs.configuration) != CONFIGURATION_SHA256) or (len(inputs.game) != GAME_BYTES) or (_sha(inputs.game) != GAME_SHA256) or (type(manifest_sha256) is not str) or (manifest_sha256 != MANIFEST_SHA256) or any((type(getattr(inputs, name, None)) is not int for name in ('expected_turn', 'expected_width', 'expected_height'))) or ((inputs.expected_turn, inputs.expected_width, inputs.expected_height) != (12, 74, 46)):
        raise ValueError('Only the immutable audited previctory12 component pair is admitted')
