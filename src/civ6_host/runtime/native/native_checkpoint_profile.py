"""WORK-only explicit component-pair profiles for a later Load experiment.

This module is pure Python. It does not bind a DLL or call Load. A future pair
must be minted from a real Save report and its exact component manifest; the
late-turn profile intentionally remains unadmitted until those bytes exist.
"""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
from dataclasses import dataclass
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import re
ROOT = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_checkpoint_profile.py')))).resolve().parents[1]
HEX64 = re.compile('^[0-9a-f]{64}$')
MAX_COMPONENT_BYTES = 32 * 1024 * 1024
MAX_COMPACT_WITNESS_BYTES = 256 * 1024
CORE_SHA256 = 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'
CONFIGURATION_PROOF_SHA256 = '3d5ef65d87185b09b2925e2c0f61f7181d993b3f25e2e55cc3fbcc3c08a817a7'
LATE_WITNESS_SCHEMA = 'civ6rl.native_late_checkpoint_save_witness.v1'

@dataclass(frozen=True)
class ComponentPairProfile:
    name: str
    save_mode: str
    completed_rounds: int
    expected_turn: int
    manifest_turn: int | None
    preflight_turn: int | None
    width: int
    height: int
    manifest_path: str
    manifest_sha256: str
    witness_path: str
    witness_sha256: str
    game_path: str
    game_bytes: int
    game_sha256: str
    configuration_path: str
    configuration_bytes: int
    configuration_sha256: str
    manifest_schema: str
    game_filename: str
    configuration_filename: str
    witness_extractor_sha256: str | None = None

    def require_ready(self) -> None:
        if type(self) is not ComponentPairProfile:
            raise TypeError('A frozen ComponentPairProfile is required')
        if type(self.completed_rounds) is not int or type(self.expected_turn) is not int or type(self.width) is not int or (type(self.height) is not int) or (type(self.game_bytes) is not int) or (type(self.configuration_bytes) is not int):
            raise ValueError('Checkpoint profile integer fields must be exact ints')
        if (self.width, self.height) != (74, 46) or self.expected_turn != self.completed_rounds + 1:
            raise ValueError('Profile is outside the observed two-player 74x46 turn boundary')
        if self.name == 'late114':
            if (self.save_mode, self.completed_rounds, self.expected_turn, self.manifest_turn, self.preflight_turn, self.manifest_schema, self.game_filename, self.configuration_filename) != ('save-config-late114', 114, 115, 115, 115, 'civ6rl.native_checkpoint_late114_components.v1', 'turn115.gamecore.raw', 'turn115.configuration.raw'):
                raise ValueError('Late profile differs from the explicit 114/115 Save contract')
        elif self.name == 'baseline352':
            if (self.save_mode, self.completed_rounds, self.expected_turn, self.manifest_turn, self.preflight_turn, self.manifest_schema, self.game_filename, self.configuration_filename) != ('save-config', 1, 2, None, None, 'civ6rl.native_checkpoint_components.v1', 'round1.gamecore.raw', 'round1.configuration.raw'):
                raise ValueError('Baseline profile differs from the immutable 352 contract')
        else:
            raise ValueError('Unknown checkpoint profile')
        for name in ('manifest_path', 'witness_path', 'game_path', 'configuration_path'):
            value = getattr(self, name)
            if type(value) is not str or not value or 'PENDING' in value.upper():
                raise ValueError('Checkpoint profile still has pending path: ' + name)
            path = _resolve_resource_path(Path(value))
            if path.is_absolute() or '..' in path.parts:
                raise ValueError('Checkpoint profile paths must be contained and relative')
        for name in ('manifest_sha256', 'witness_sha256', 'game_sha256', 'configuration_sha256'):
            value = getattr(self, name)
            if type(value) is not str or not HEX64.fullmatch(value):
                raise ValueError('Checkpoint profile still has pending/invalid pin: ' + name)
        if self.name == 'late114' and (type(self.witness_extractor_sha256) is not str or not HEX64.fullmatch(self.witness_extractor_sha256)):
            raise ValueError('Late compact witness extractor pin is pending/invalid')
        if not (4 <= self.game_bytes <= MAX_COMPONENT_BYTES and 1 <= self.configuration_bytes <= MAX_COMPONENT_BYTES):
            raise ValueError('Checkpoint component byte sizes are not admitted')
BASELINE_352 = ComponentPairProfile(name='baseline352', save_mode='save-config', completed_rounds=1, expected_turn=2, manifest_turn=None, preflight_turn=None, width=74, height=46, manifest_path='work/native-checkpoints/57550309b836401898464888261ccb9f/round1.checkpoint.json', manifest_sha256='8b6db0574d5e8a5288936a17a308b30db918f53bf63a94f862edfb670ffba53d', witness_path='evidence/native-newgame-script-prefix352.json', witness_sha256='87eeaa8d9a5d174d2930fce0d47b0a854c2737c71380f165b29ace67496bd8fc', game_path='work/native-checkpoints/57550309b836401898464888261ccb9f/round1.gamecore.raw', game_bytes=2542367, game_sha256='2b09cc670fa719b643e73278e9fbf50eee0f076c6156e231a32380d3f480d7d9', configuration_path='work/native-checkpoints/57550309b836401898464888261ccb9f/round1.configuration.raw', configuration_bytes=15053, configuration_sha256='9d6dd5f7c4ca59e95a97b09df342634b20016eccaf5f86d03cb6e0f7ff6cc79b', manifest_schema='civ6rl.native_checkpoint_components.v1', game_filename='round1.gamecore.raw', configuration_filename='round1.configuration.raw')
LATE114_PENDING = ComponentPairProfile(name='late114', save_mode='save-config-late114', completed_rounds=114, expected_turn=115, manifest_turn=115, preflight_turn=115, width=74, height=46, manifest_path='PENDING', manifest_sha256='PENDING', witness_path='PENDING', witness_sha256='PENDING', game_path='PENDING', game_bytes=0, game_sha256='PENDING', configuration_path='PENDING', configuration_bytes=0, configuration_sha256='PENDING', manifest_schema='civ6rl.native_checkpoint_late114_components.v1', game_filename='turn115.gamecore.raw', configuration_filename='turn115.configuration.raw')
LATE_380 = replace(LATE114_PENDING, manifest_path='work/native-checkpoints/5672c634c68348a48049e85acb0b8106/turn115.checkpoint.json', manifest_sha256='1fb0d9fcc3bc9aaf4af07b024b27cad87dece03173f81d0c17663c56dd75caa8', witness_path='evidence/native-late-save380-compact-witness404.json', witness_sha256='069a11cc91061774992a6b69fce19328cc139651fb2f141c4d01f3a380a71a3d', game_path='work/native-checkpoints/5672c634c68348a48049e85acb0b8106/turn115.gamecore.raw', game_bytes=2898151, game_sha256='595ef6934a7816f77526bb89e23a71d885e52f44995969e7776ae52ee87ff435', configuration_path='work/native-checkpoints/5672c634c68348a48049e85acb0b8106/turn115.configuration.raw', configuration_bytes=15053, configuration_sha256='9d6dd5f7c4ca59e95a97b09df342634b20016eccaf5f86d03cb6e0f7ff6cc79b', witness_extractor_sha256='11cae8a8d902f2b4774714d654fffc7634b831a817dca5bd51c1057dc30fb8fe')

@dataclass(frozen=True)
class MatchedComponentPair:
    profile: ComponentPairProfile
    game: bytes
    configuration: bytes
    manifest_sha256: str
    witness_sha256: str

def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def _contained(root: Path, relative: str, *, folder: Path | None=None, filename: str | None=None) -> Path:
    rel = _resolve_resource_path(Path(relative))
    if rel.is_absolute() or '..' in rel.parts:
        raise ValueError('Component path escapes the checkpoint root')
    path = _resolve_resource_path(root / rel).resolve()
    if not path.is_relative_to(_resolve_resource_path(root).resolve()):
        raise ValueError('Component path escapes the project root')
    if folder is not None and path.parent != _resolve_resource_path(folder).resolve():
        raise ValueError('Components must share their checkpoint directory')
    if filename is not None and path.name != filename:
        raise ValueError('Component filename differs from the selected profile')
    return path

def _trial_events(report: dict):
    if report.get('schema') == LATE_WITNESS_SCHEMA:
        events = report.get('events')
        expected_stages = ['native_round_effect_verified', 'native_checkpoint_preflight', 'before_native_checkpoint_save', 'native_checkpoint_configuration_serialized', 'native_checkpoint_save_returned', 'native_checkpoint_postflight', 'native_checkpoint_save_finalized']
        if type(events) is not list or [e.get('stage') if type(e) is dict else None for e in events] != expected_stages:
            raise ValueError('Compact late Save witness has malformed bounded events')
        if any((type(event) is not dict or type(event.get('stage')) is not str for event in events)):
            raise ValueError('Compact late Save witness event is malformed')
        yield events
        return
    batches = report.get('batches')
    if type(batches) is not list:
        raise ValueError('Save witness has no batches')
    for batch in batches:
        if type(batch) is not dict or type(batch.get('trials')) is not list:
            raise ValueError('Save witness batch is malformed')
        for trial in batch['trials']:
            if type(trial) is not dict or type(trial.get('events')) is not list:
                raise ValueError('Save witness trial is malformed')
            events = [event for event in trial['events'] if type(event) is dict and type(event.get('stage')) is str]
            yield events

def read_verified_pair(profile: ComponentPairProfile, *, root: Path=ROOT) -> MatchedComponentPair:
    """Read a complete Save-bound pair only after every immutable pin is concrete."""
    profile.require_ready()
    root = _resolve_resource_path(root).resolve()
    manifest_path = _contained(root, profile.manifest_path)
    witness_path = _contained(root, profile.witness_path)
    witness_limit = MAX_COMPACT_WITNESS_BYTES if profile.name == 'late114' else 128 * 1024 * 1024
    if _resolve_resource_path(manifest_path).stat().st_size > 1024 * 1024 or _resolve_resource_path(witness_path).stat().st_size > witness_limit:
        raise ValueError('Checkpoint manifest/witness exceeds bounded read size')
    manifest_raw = _resolve_resource_path(manifest_path).read_bytes()
    witness_raw = _resolve_resource_path(witness_path).read_bytes()
    if _sha(manifest_raw) != profile.manifest_sha256 or _sha(witness_raw) != profile.witness_sha256:
        raise ValueError('Checkpoint manifest or Save witness hash differs')
    manifest, witness = (json.loads(manifest_raw), json.loads(witness_raw))
    if manifest.get('schema') != profile.manifest_schema or manifest.get('core_sha256') != CORE_SHA256 or manifest.get('completed_rounds') != profile.completed_rounds or (manifest.get('observed_game_turn') != profile.manifest_turn) or (manifest.get('eligible_for_training') is not False) or (manifest.get('full_civ6save_container') is not False):
        raise ValueError('Checkpoint manifest metadata differs from selected profile')
    if profile.name == 'late114':
        source = witness.get('source_report')
        if witness.get('schema') != LATE_WITNESS_SCHEMA or type(source) is not dict or set(source) != {'path', 'bytes', 'sha256'} or (type(source.get('path')) is not str) or (not source['path']) or _resolve_resource_path(Path(source['path'])).is_absolute() or ('..' in _resolve_resource_path(Path(source['path'])).parts) or (type(source.get('bytes')) is not int) or (source['bytes'] <= 0) or (type(source.get('sha256')) is not str) or (not HEX64.fullmatch(source['sha256'])) or (type(witness.get('extractor_sha256')) is not str) or (not HEX64.fullmatch(witness['extractor_sha256'])) or (witness.get('extractor_sha256') != profile.witness_extractor_sha256) or (witness.get('core_sha256') != CORE_SHA256) or (type(witness.get('source_pins')) is not dict) or (not witness['source_pins']) or any((type(key) is not str or 'sha256' not in key.lower() or type(value) is not str or (not HEX64.fullmatch(value)) for key, value in witness['source_pins'].items())) or (type(witness.get('native_fixture')) is not str) or (not witness['native_fixture']) or (type(witness.get('native_fixture_sha256')) is not str) or (not HEX64.fullmatch(witness['native_fixture_sha256'])) or (type(witness.get('native_fixture_isolation')) is not dict) or (type(witness['native_fixture_isolation'].get('worker_count')) is not int) or (witness['native_fixture_isolation']['worker_count'] != 1) or (type(witness['native_fixture_isolation'].get('workers')) is not list) or (len(witness['native_fixture_isolation']['workers']) != 1) or (type(witness.get('round_effect_chain')) is not list) or (len(witness['round_effect_chain']) != profile.completed_rounds) or (type(witness.get('selected_trial')) is not dict) or (set(witness['selected_trial']) != {'batch_index', 'trial_index'}) or any((type(witness['selected_trial'].get(key)) is not int or witness['selected_trial'][key] < 0 for key in ('batch_index', 'trial_index'))) or (witness.get('selection') != {'mode': 'save-config-late114', 'completed_rounds': 114, 'live_turn': 115}):
            raise ValueError('Late compact witness provenance/selection is malformed')
        worker = witness['native_fixture_isolation']['workers'][0]
        databases = worker.get('databases') if type(worker) is dict else None
        if type(worker) is not dict or worker.get('worker_index') != 0 or type(worker.get('manifest_path')) is not str or (not worker['manifest_path']) or (type(worker.get('manifest_sha256')) is not str) or (not HEX64.fullmatch(worker['manifest_sha256'])) or (type(databases) is not dict) or (not {'configuration', 'gameplay'}.issubset(databases)) or any((type(row) is not dict or type(row.get('sha256')) is not str or (not HEX64.fullmatch(row['sha256'])) for row in databases.values())):
            raise ValueError('Late compact witness fixture worker provenance is incomplete')
    elif witness.get('schema') != 'civ6rl.native-host-probe.v1' or witness.get('dll_sha256') != CORE_SHA256:
        raise ValueError('Save witness is not from the pinned Base Core probe')
    trial_groups = list(_trial_events(witness))
    matching = [(events, e) for events in trial_groups for e in events if e['stage'] == 'native_checkpoint_preflight' and e.get('mode') == profile.save_mode and (e.get('round_completed') == profile.completed_rounds) and (e.get('observed_turn' if profile.name == 'late114' else 'observed_game_turn') == profile.preflight_turn)]
    returned = [(events, e) for events in trial_groups for e in events if e['stage'] == 'native_checkpoint_save_returned']
    if len(matching) != 1 or len(returned) != 1 or matching[0][0] is not returned[0][0]:
        raise ValueError('Save witness does not uniquely authorize this completed-round boundary')
    events = matching[0][0]
    preflight_index = events.index(matching[0][1])
    prior_events = events[:preflight_index]
    if profile.name == 'late114':
        chain = witness['round_effect_chain']
        for ordinal, effect in enumerate(chain, 1):
            state = effect.get('after') if type(effect) is dict else None
            if type(effect) is not dict or effect.get('stage') != 'native_round_effect_verified' or type(effect.get('native_rounds_completed')) is not int or (effect['native_rounds_completed'] != 1) or (type(effect.get('cumulative_native_rounds_completed')) is not int) or (effect['cumulative_native_rounds_completed'] != ordinal) or (type(state) is not dict) or (type(state.get('current_game_turn')) is not int) or (state.get('current_game_turn') != ordinal + 1):
                raise ValueError('Compact witness does not prove the ordered cumulative round chain')
        expected_final = {'current_game_turn': 115, 'local_player': 0}
        final_state = chain[-1].get('after') if type(chain[-1]) is dict else None
        players = final_state.get('players') if type(final_state) is dict else None
        exact_roster = type(players) is list and len(players) == 2 and all((type(row) is dict and set(row) == {'player_id', 'active', 'complete'} and (type(row['player_id']) is int) and (type(row['active']) is bool) and (type(row['complete']) is bool) for row in players)) and (players == [{'player_id': 0, 'active': True, 'complete': False}, {'player_id': 1, 'active': False, 'complete': False}])
        if type(final_state) is not dict or any((type(final_state.get(key)) is not int for key in ('current_game_turn', 'local_player'))) or any((final_state.get(key) != value for key, value in expected_final.items())) or (not exact_roster):
            raise ValueError('Late Save round chain lacks the exact turn-115 player roster')
        before_markers = [e for e in events if e.get('stage') == 'before_native_checkpoint_save']
        if len(before_markers) != 1 or before_markers[0].get('outer_slot') != '0x168':
            raise ValueError('Late Save witness lacks the exact pre-Save marker')
    round_effects = [e for e in prior_events if e.get('stage') == 'native_round_effect_verified' and (e.get('cumulative_native_rounds_completed') if profile.name == 'late114' else e.get('native_rounds_completed')) == profile.completed_rounds and (type(e.get('after')) is dict) and (e['after'].get('current_game_turn') == profile.expected_turn)]
    if len(round_effects) != 1:
        raise ValueError('Save witness lacks the matching native round and live turn readback')
    returned_event = returned[0][1]
    if profile.name == 'late114' and (type(returned_event.get('status')) is not int or returned_event.get('status') != 0) or returned_event.get('bytes') != profile.game_bytes or returned_event.get('sha256') != profile.game_sha256 or (returned_event.get('native_version_prefix') != '05000000'):
        raise ValueError('Game Save return does not match the selected component')
    config_events = [e for e in events if e['stage'] == 'native_checkpoint_configuration_serialized']
    postflight = [e for e in events if e['stage'] == 'native_checkpoint_postflight' and e.get('mode') == profile.save_mode and (e.get('round_completed') == profile.completed_rounds)]
    if len(config_events) != 1 or len(postflight) != 1:
        raise ValueError('Save witness lacks a unique paired configuration/postflight receipt')
    config_receipt = config_events[0]
    if config_receipt.get('bytes') != profile.configuration_bytes or config_receipt.get('sha256') != profile.configuration_sha256 or config_receipt.get('proof_sha256') != CONFIGURATION_PROOF_SHA256:
        raise ValueError('Configuration Save return does not match the selected component')
    written_manifest = postflight[0].get('component_manifest_path')
    if type(written_manifest) is not str or _resolve_resource_path(_resolve_resource_path(Path(written_manifest))).resolve() != _resolve_resource_path(manifest_path).resolve():
        raise ValueError('Postflight witness points to another component manifest')
    config_index = events.index(config_events[0])
    save_index = events.index(returned_event)
    postflight_index = events.index(postflight[0])
    before_index = next((i for i, e in enumerate(events) if e.get('stage') == 'before_native_checkpoint_save'), -1)
    save_order_ok = preflight_index < before_index < config_index < save_index < postflight_index if profile.name == 'late114' else preflight_index < config_index < save_index < postflight_index
    if not save_order_ok:
        raise ValueError('Save/configuration receipts are not in the observed source order')
    if postflight[0].get('output_path') is None or _resolve_resource_path(_resolve_resource_path(Path(postflight[0]['output_path']))).resolve() != _resolve_resource_path(_contained(root, profile.game_path, folder=manifest_path.parent, filename=profile.game_filename)).resolve() or postflight[0].get('configuration_component_saved') is not True or (postflight[0].get('native_save_called') is not True) or (postflight[0].get('native_load_called') is not False):
        raise ValueError('Postflight does not identify this saved component pair')
    if profile.name == 'late114' and (matching[0][1].get('control') != postflight[0].get('control') or type(matching[0][1].get('control')) is not dict or manifest.get('control') != matching[0][1].get('control') or (type(postflight[0].get('jobs_before')) is not dict) or (type(postflight[0].get('jobs_after')) is not dict) or (postflight[0].get('jobs_before') != postflight[0].get('jobs_after')) or (matching[0][1].get('eligible_for_training') is not False) or (returned_event.get('load_validated') is not False) or (returned_event.get('reset_validated') is not False) or (returned_event.get('eligible_for_training') is not False) or (postflight[0].get('eligible_for_training') is not False)):
        raise ValueError('Late Save changed its native control or job snapshots')
    if profile.name == 'late114':
        finalized = [e for e in events if e.get('stage') == 'native_checkpoint_save_finalized']
        if len(finalized) != 1 or events.index(finalized[0]) <= postflight_index or finalized[0].get('mode') != profile.save_mode or (finalized[0].get('round_completed') != profile.completed_rounds) or (finalized[0].get('observed_turn') != profile.expected_turn) or (finalized[0].get('stream_closed') is not True) or (finalized[0].get('native_save_called') is not True) or (finalized[0].get('output_sha256') != profile.game_sha256) or (_resolve_resource_path(_resolve_resource_path(Path(finalized[0].get('component_manifest_path', '')))).resolve() != _resolve_resource_path(manifest_path).resolve()) or (finalized[0].get('component_manifest_sha256') != profile.manifest_sha256) or (finalized[0].get('native_load_validated') is not False) or (finalized[0].get('eligible_for_training') is not False):
            raise ValueError('Late Save is not authorized by its exact post-close finalized receipt')
        if manifest.get('jobs_quiescent_before_after') is not True:
            raise ValueError('Late manifest does not record equal before/after job snapshots')
    comps = manifest.get('components')
    if type(comps) is not dict or set(comps) != {'gamecore', 'application_configuration'}:
        raise ValueError('Checkpoint must contain exactly the paired Game and configuration components')
    folder = manifest_path.parent
    game_path = _contained(root, profile.game_path, folder=folder, filename=profile.game_filename)
    config_path = _contained(root, profile.configuration_path, folder=folder, filename=profile.configuration_filename)
    for key, path, size, digest in (('gamecore', game_path, profile.game_bytes, profile.game_sha256), ('application_configuration', config_path, profile.configuration_bytes, profile.configuration_sha256)):
        row = comps[key]
        expected_path = profile.game_path if key == 'gamecore' else profile.configuration_path
        manifest_component_path = row.get('path') if type(row) is dict else None
        if type(manifest_component_path) is not str or manifest_component_path.replace('\\', '/') != expected_path.replace('\\', '/'):
            raise ValueError('Manifest component reference differs: ' + key)
        data_size = _resolve_resource_path(path).stat().st_size
        if row.get('bytes') != size or row.get('sha256') != digest or data_size != size:
            raise ValueError('Manifest component size/hash differs: ' + key)
    game, config = (_resolve_resource_path(game_path).read_bytes(), _resolve_resource_path(config_path).read_bytes())
    if _sha(game) != profile.game_sha256 or _sha(config) != profile.configuration_sha256:
        raise ValueError('Raw checkpoint component contents differ from their manifest pins')
    if game[:4] != b'\x05\x00\x00\x00':
        raise ValueError('Game component lacks the observed native version prefix')
    receipt = manifest.get('configuration_receipt', {})
    if receipt.get('proof_sha256') != CONFIGURATION_PROOF_SHA256 or receipt.get('bytes') != profile.configuration_bytes or receipt.get('sha256') != profile.configuration_sha256:
        raise ValueError('Native configuration serializer receipt differs')
    return MatchedComponentPair(profile, game, config, profile.manifest_sha256, profile.witness_sha256)

def load_after_admission(profile: ComponentPairProfile, *, root: Path, native_load):
    """Test seam: a native loader is reached only after full pair admission.

    Production integration must retain the existing supervisor/owner and Load
    ABI guards; this helper is not a native entrypoint.
    """
    if not callable(native_load):
        raise TypeError('An injected Load seam is required')
    pair = read_verified_pair(profile, root=root)
    return native_load(pair)

@dataclass(frozen=True)
class TurnTransitionProfile:
    start_turn: int
    end_turn: int
    player_ids: tuple[int, int] = (0, 1)

    def validate(self):
        if type(self.start_turn) is not int or type(self.end_turn) is not int or (self.start_turn, self.end_turn) not in ((2, 3), (115, 116)) or (type(self.player_ids) is not tuple) or (self.player_ids != (0, 1)):
            raise ValueError('Only the observed 2->3 or proposed 115->116 two-player profile is staged')
RESUME_2_TO_3 = TurnTransitionProfile(2, 3)
RESUME_115_TO_116 = TurnTransitionProfile(115, 116)

def validate_turn_pair(profile: TurnTransitionProfile, before: dict, after: dict) -> None:
    profile.validate()
    if type(before) is not dict or type(after) is not dict or before.get('current_game_turn') != profile.start_turn or (after.get('current_game_turn') != profile.end_turn) or (before.get('local_player') != 0) or (after.get('local_player') != 0):
        raise ValueError('Observed turn transition differs from the selected profile')
