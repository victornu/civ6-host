"""Pinned diagnostic profile for the actual retained native385 Save at turn118.

Only the reviewed native385 pair is registered here. This module does
not interpret a NewGame completed-round count as the lineage of a Save-after-
Load checkpoint.  Admission requires a separately frozen profile created
from an actual Save receipt.
"""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
from dataclasses import dataclass
import json
from pathlib import Path
import re
from types import MappingProxyType
import math
import hashlib
from civ6_host.runtime.native import native_checkpoint_profile as common_pair
SCHEMA = 'civ6rl.native_checkpoint_retained_components.v1'
AUDIT_WITNESS_SCHEMA = 'civ6rl.native_retained_save118_audit434.v2'
AUDIT_WITNESS_121_SCHEMA = 'civ6rl.native_retained_save121_audit470.v1'
AUDIT_WITNESS_150_SCHEMA = 'civ6rl.native_retained_save150_audit569.v1'
AUDIT_WITNESS_182_SCHEMA = 'civ6rl.native_retained_save182_audit648.v1'
CORE_SHA256 = 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'
CONFIGURATION_PROOF_SHA256 = '3d5ef65d87185b09b2925e2c0f61f7181d993b3f25e2e55cc3fbcc3c08a817a7'
MAX_COMPONENT_BYTES = 32 * 1024 * 1024
MAX_MANIFEST_BYTES = 256 * 1024
MAX_WITNESS_BYTES = 256 * 1024
HEX64 = re.compile('^[0-9a-f]{64}$')

@dataclass(frozen=True)
class RetainedProfile:
    """Immutable expected inputs for one independently observed retained Save."""
    profile_id: str
    manifest_path: str
    manifest_sha256: str
    witness_path: str
    witness_sha256: str
    expected_turn: int
    width: int
    height: int
    original_input_turn: int
    resumed_rounds: int
    transitions: tuple[tuple[int, int], ...]
    game_path: str
    game_bytes: int
    game_sha256: str
    configuration_path: str
    configuration_bytes: int
    configuration_sha256: str
    input_manifest_sha256: str
    input_game_sha256: str
    input_configuration_sha256: str
    source_proofs: tuple[tuple[str, str], ...]
    input_profile: str = 'late380'

    def validate_definition(self) -> None:
        if type(self) is not RetainedProfile:
            raise TypeError('A frozen retained checkpoint profile is required')
        if type(self.profile_id) is not str or not self.profile_id or 'pending' in self.profile_id.lower():
            raise ValueError('Invalid retained profile identifier')
        ints = (self.expected_turn, self.width, self.height, self.original_input_turn, self.resumed_rounds, self.game_bytes, self.configuration_bytes)
        if any((type(value) is not int for value in ints)):
            raise ValueError('Retained profile integer fields require exact ints')
        if type(self.transitions) is not tuple or any((type(row) is not tuple or len(row) != 2 or any((type(x) is not int for x in row)) for row in self.transitions)):
            raise ValueError('Retained transitions must be immutable exact-int pairs')
        contracts = {'retained118': ('late380', 118, 115, 3, ((115, 116), (116, 117), (117, 118))), 'retained121': ('retained118', 121, 118, 3, ((118, 119), (119, 120), (120, 121))), 'retained150': ('retained118', 150, 118, 32, tuple(((turn, turn + 1) for turn in range(118, 150)))), 'retained182': ('retained150', 182, 150, 32, tuple(((turn, turn + 1) for turn in range(150, 182))))}
        contract = contracts.get(self.profile_id)
        if contract is None or self.input_profile != contract[0] or self.expected_turn != contract[1] or ((self.width, self.height) != (74, 46)) or (self.original_input_turn != contract[2]) or (self.resumed_rounds != contract[3]) or (self.transitions != contract[4]):
            raise ValueError('This adapter admits only explicitly observed retained save chains')
        for name in ('manifest_path', 'witness_path', 'game_path', 'configuration_path'):
            value = getattr(self, name)
            if type(value) is not str or not value:
                raise ValueError('Retained profile path is missing: ' + name)
            path = _resolve_resource_path(Path(value))
            if path.is_absolute() or '..' in path.parts or 'PENDING' in value.upper():
                raise ValueError('Retained profile paths must be concrete and relative')
        for name in ('manifest_sha256', 'witness_sha256', 'game_sha256', 'configuration_sha256', 'input_manifest_sha256', 'input_game_sha256', 'input_configuration_sha256'):
            value = getattr(self, name)
            if type(value) is not str or not HEX64.fullmatch(value):
                raise ValueError('Retained profile has a missing or invalid pin: ' + name)
        expected_proof_keys = {'plan_sha256', 'provider_sha256', 'jobs_sha256', 'core_sha256'} if self.profile_id == 'retained118' else {'plan_sha256', 'provider_sha256', 'jobs_sha256', 'core_sha256', 'retained_save121_profile_plan_sha256' if self.profile_id == 'retained121' else 'native_checkpoint_retained_save150_plan_sha256' if self.profile_id == 'retained150' else 'native_checkpoint_retained_save182_plan_sha256'}
        if type(self.source_proofs) is not tuple or len(self.source_proofs) != len(expected_proof_keys) or any((type(row) is not tuple or len(row) != 2 for row in self.source_proofs)) or ({key for key, _ in self.source_proofs} != expected_proof_keys) or any((type(key) is not str or type(value) is not str or (not HEX64.fullmatch(value)) for key, value in self.source_proofs)):
            raise ValueError('Retained source proof pins are incomplete or malformed')
        if not (4 <= self.game_bytes <= MAX_COMPONENT_BYTES and 1 <= self.configuration_bytes <= MAX_COMPONENT_BYTES):
            raise ValueError('Retained component sizes are outside the bounded reader')

@dataclass(frozen=True)
class RetainedMatchedPair:
    profile: RetainedProfile
    manifest_sha256: str
    witness_sha256: str
    game: bytes
    configuration: bytes
    witness: bytes
    expected_turn: int
    width: int
    height: int

def _contained(root: Path, relative: str) -> Path:
    return common_pair._contained(_resolve_resource_path(root).resolve(), relative)

def _read_pinned(root: Path, relative: str, expected_sha: str, max_bytes: int) -> bytes:
    path = _contained(root, relative)
    if _resolve_resource_path(path).stat().st_size > max_bytes:
        raise ValueError('Retained checkpoint file exceeds its size bound')
    with _resolve_resource_path(path).open('rb') as stream:
        data = stream.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise ValueError('Retained checkpoint file exceeds its size bound')
    if common_pair._sha(data) != expected_sha:
        raise ValueError('Retained checkpoint source hash changed: ' + relative)
    return data

def current_source_proofs(root: Path | None=None, profile_id: str='retained118') -> dict[str, str]:
    """Recheck the retained-Save source bundle without entering native code."""
    from civ6_host.runtime.native import native_checkpoint_jobs as jobs
    from civ6_host.runtime.native import native_checkpoint_provider as provider
    root = common_pair.ROOT if root is None else _resolve_resource_path(_resolve_resource_path(Path(root))).resolve()
    plan_raw = _read_pinned(root, 'work/native-retained-save-plan426.json', 'a5a1d99430c0aaf87528740af33bdbd3703058514e6988ade803bcc463df1688', MAX_MANIFEST_BYTES)
    plan = json.loads(plan_raw.decode('utf-8'))
    if plan.get('schema') != 'civ6rl.native_retained_save_plan426.v1' or plan.get('manifest', {}).get('schema_proposal') != SCHEMA or plan.get('insertion', {}).get('first_profile') != {'input_profile': 'late380', 'expected_input_turn': 115, 'resumed_rounds': 3, 'observed_save_turn': 118}:
        raise ValueError('Retained Save source plan differs from the bounded 115→118 contract')
    provider.verify_source()
    jobs.verify_source()
    result = {'plan_sha256': 'a5a1d99430c0aaf87528740af33bdbd3703058514e6988ade803bcc463df1688', 'provider_sha256': provider.PROOF_SHA256, 'jobs_sha256': jobs.PROOF_SHA256, 'core_sha256': provider.CORE_SHA256}
    if profile_id == 'retained121':
        extension_raw = _read_pinned(root, 'work/native-retained-save121-profile-plan-v2.json', '5c15783c42a52af935d6a5a8002c09bb8cabf5c164096a1698bf629fa19cb12e', MAX_MANIFEST_BYTES)
        extension = json.loads(extension_raw.decode('utf-8'))
        expected = {'input_profile': 'retained118', 'input_turn': 118, 'rounds': 3, 'save_turn': 121}
        if extension.get('schema') != 'civ6rl.native_retained_save121_profile_plan.v1' or extension.get('profiles', {}).get('trace-checkpoint-resume-retained118-save121') != expected or extension.get('bounded_resume_witness', {}).get('observed_transitions') != [[118, 119], [119, 120], [120, 121]]:
            raise ValueError('Retained121 plan differs from the pinned 118→121 contract')
        result['retained_save121_profile_plan_sha256'] = '5c15783c42a52af935d6a5a8002c09bb8cabf5c164096a1698bf629fa19cb12e'
    elif profile_id == 'retained150':
        from civ6_host.runtime.native import native_checkpoint_retained_save as retained_save
        save_proofs = retained_save.verify_source(retained_save.MODE150)
        expected_save_proofs = result | {'native_checkpoint_retained_save150_plan_sha256': '5f13e25b218b770b89122cf5cacba22d026f7ecc67c22b942af146d641dc2dd6'}
        if save_proofs != expected_save_proofs:
            raise ValueError('Retained150 Save source plan differs from the audited 118→150 chain')
        result['native_checkpoint_retained_save150_plan_sha256'] = save_proofs['native_checkpoint_retained_save150_plan_sha256']
    elif profile_id == 'retained182':
        from civ6_host.runtime.native import native_checkpoint_retained_save as retained_save
        save_proofs = retained_save.verify_source(retained_save.MODE182)
        expected_save_proofs = result | {'native_checkpoint_retained_save182_plan_sha256': 'e076939baed31baea3fa9924f1169650e47bb458045900ef9a674c76e628448f'}
        if save_proofs != expected_save_proofs:
            raise ValueError('Retained182 source plan differs from the pinned 150→182 Save chain')
        result['native_checkpoint_retained_save182_plan_sha256'] = save_proofs['native_checkpoint_retained_save182_plan_sha256']
    elif profile_id != 'retained118':
        raise ValueError('Unknown retained profile source contract')
    return result

def validate_manifest(profile: RetainedProfile, manifest_raw: bytes) -> dict:
    """Validate manifest fields against an externally pinned profile, not itself."""
    profile.validate_definition()
    if type(manifest_raw) is not bytes or len(manifest_raw) > MAX_MANIFEST_BYTES:
        raise ValueError('Retained checkpoint manifest is not bounded bytes')
    if common_pair._sha(manifest_raw) != profile.manifest_sha256:
        raise ValueError('Retained checkpoint manifest pin mismatch')
    try:
        manifest = json.loads(manifest_raw.decode('utf-8'))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError('Retained checkpoint manifest is invalid JSON') from exc
    if type(manifest) is not dict or manifest.get('schema') != SCHEMA:
        raise ValueError('Wrong retained component manifest schema')
    if manifest.get('core_sha256') != CORE_SHA256:
        raise ValueError('Retained manifest Core identity mismatch')
    if type(manifest.get('observed_game_turn')) is not int or manifest['observed_game_turn'] != profile.expected_turn:
        raise ValueError('Retained manifest turn differs from the pinned profile')
    lineage = manifest.get('lineage')
    if 'lineage' in manifest or 'completed_rounds' in manifest or 'native_rounds_completed' in manifest or (manifest.get('input_profile') != profile.input_profile) or (type(manifest.get('original_input_turn')) is not int) or (manifest['original_input_turn'] != profile.original_input_turn) or (type(manifest.get('resumed_rounds')) is not int) or (manifest['resumed_rounds'] != profile.resumed_rounds) or (type(manifest.get('native_turn_transitions')) is not list) or (len(manifest['native_turn_transitions']) != len(profile.transitions)) or any((type(row) is not list or len(row) != 2 or any((type(item) is not int for item in row)) for row in manifest['native_turn_transitions'])) or (manifest['native_turn_transitions'] != [list(p) for p in profile.transitions]):
        raise ValueError('Retained manifest resume lineage differs from the pinned chain')
    if manifest.get('input_manifest_sha256') != profile.input_manifest_sha256 or manifest.get('input_components_sha256') != {'gamecore': profile.input_game_sha256, 'application_configuration': profile.input_configuration_sha256}:
        raise ValueError('Retained manifest does not bind the exact late380 source pair')
    components = manifest.get('components')
    expected_components = {'gamecore': {'path': profile.game_path, 'bytes': profile.game_bytes, 'sha256': profile.game_sha256}, 'application_configuration': {'path': profile.configuration_path, 'bytes': profile.configuration_bytes, 'sha256': profile.configuration_sha256}}
    if type(components) is not dict or set(components) != set(expected_components):
        raise ValueError('Retained component manifest differs from the frozen pair profile')
    for name, expected in expected_components.items():
        actual = components.get(name)
        if type(actual) is not dict or set(actual) != {'path', 'bytes', 'sha256'} or type(actual.get('path')) is not str or (type(actual.get('bytes')) is not int) or (type(actual.get('sha256')) is not str) or (actual != expected):
            raise ValueError('Retained component manifest differs from frozen ' + name)
    proofs = manifest.get('source_proofs')
    proof_keys = {key for key, _ in profile.source_proofs}
    if type(proofs) is not dict or set(proofs) != proof_keys or any((type(k) is not str or not k or type(v) is not str or (not HEX64.fullmatch(v)) for k, v in proofs.items())):
        raise ValueError('Retained manifest source proof pins are malformed')
    if proofs['core_sha256'] != CORE_SHA256:
        raise ValueError('Retained manifest Core source pin mismatch')
    if proofs != dict(profile.source_proofs):
        raise ValueError('Retained manifest source pins differ from frozen profile')
    receipt = manifest.get('configuration_receipt')
    receipt_keys = {'operation', 'proof_sha256', 'core_sha256', 'native_method_result_observed', 'native_return_interpreted', 'writer_flags32', 'reader_optional_pointer', 'bytes', 'sha256', 'stream_calls', 'identity_checked_before_after', 'all_property_values_compared', 'eligible_for_training'}
    if type(receipt) is not dict or set(receipt) != receipt_keys or receipt.get('operation') != 'serialize' or (receipt.get('proof_sha256') != CONFIGURATION_PROOF_SHA256) or (receipt.get('core_sha256') != CORE_SHA256) or (receipt.get('native_method_result_observed') is not False) or (receipt.get('identity_checked_before_after') is not True) or (receipt.get('native_return_interpreted') is not False) or (type(receipt.get('writer_flags32')) is not int) or (receipt['writer_flags32'] != 0) or (receipt.get('reader_optional_pointer') is not None) or (type(receipt.get('bytes')) is not int) or (receipt['bytes'] != profile.configuration_bytes) or (receipt.get('sha256') != profile.configuration_sha256) or (type(receipt.get('stream_calls')) is not int) or (not 1 <= receipt['stream_calls'] <= 1000000) or (receipt.get('all_property_values_compared') is not False) or (receipt.get('eligible_for_training') is not False):
        raise ValueError('Retained configuration serialization receipt is incomplete')
    jobs_before, jobs_after = (manifest.get('jobs_before'), manifest.get('jobs_after'))
    if type(jobs_before) is not dict or type(jobs_after) is not dict or jobs_before != jobs_after or (manifest.get('jobs_quiescent_unchanged') is not True):
        raise ValueError('Retained Save jobs snapshots are not unchanged')
    from civ6_host.runtime.native import native_checkpoint_jobs as jobs
    jobs.require_quiescent(jobs_before)
    jobs.require_quiescent(jobs_after)
    if type(manifest.get('native_save_status')) is not int or manifest['native_save_status'] != 0 or manifest.get('game_version_prefix') != '05000000' or (type(manifest.get('game_stream_calls')) is not int) or (not 1 <= manifest['game_stream_calls'] <= 1000000) or (manifest.get('stream_closed') is not True):
        raise ValueError('Retained Save receipt is absent or incomplete')
    control = manifest.get('control')
    if type(control) is not dict or set(control) != {'public_sequence', 'consumed_count', 'private_selector', 'private_cursors', 'processor_flags', 'notification_counter', 'metadata_counter'} or any((type(control.get(k)) is not int for k in ('public_sequence', 'consumed_count', 'private_selector', 'notification_counter', 'metadata_counter'))) or (control['public_sequence'] != control['consumed_count']) or (not 0 <= control['public_sequence'] <= 18446744073709551615) or (control['notification_counter'] != 0) or (control['metadata_counter'] != 0) or (not 0 <= control['private_selector'] <= 4294967295) or (type(control['private_cursors']) is not list) or (len(control['private_cursors']) != 2) or any((type(v) is not int or v < 0 for v in control['private_cursors'])) or (control['private_cursors'][control['private_selector'] & 1] != 0) or (type(control['processor_flags']) is not list) or (len(control['processor_flags']) != 4) or any((type(v) is not int or v not in (0, 1) for v in control['processor_flags'])):
        raise ValueError('Retained Save live control boundary is not quiescent')
    if manifest.get('native_load_of_new_pair_validated') is not False:
        raise ValueError('A retained Save manifest cannot claim a later Load')
    if manifest.get('reset_validated') is not False or manifest.get('context_destroyed') is not False or manifest.get('full_civ6save_container') is not False or (manifest.get('eligible_for_training') is not False) or (manifest.get('scheduler_load_ledger_reconciled') is not False) or (manifest.get('scheduler_load_ledger_postrun_required') is not True):
        raise ValueError('A retained Save manifest cannot claim reset validation')
    return manifest

def validate_audit_witness(profile: RetainedProfile, witness: dict, manifest: dict, root: Path) -> dict:
    """Validate the compact receipt emitted by offline auditor434.

    The witness hash remains externally pinned by RetainedProfile. This check
    additionally ensures its semantic links match that profile and the already
    validated retained manifest; it does not produce or admit a profile.
    """
    if profile.profile_id == 'retained121':
        return _validate_audit_witness121(profile, witness, manifest, root)
    if profile.profile_id == 'retained150':
        return _validate_audit_witness150(profile, witness, manifest, root)
    if profile.profile_id == 'retained182':
        return _validate_audit_witness182(profile, witness, manifest, root)
    if type(witness) is not dict or witness.get('schema') != AUDIT_WITNESS_SCHEMA:
        raise ValueError('Retained audit witness schema is not auditor434')
    required = {'schema', 'input_report', 'child', 'load_and_resume', 'retained_save', 'native_fixture', 'native_fixture_sha256', 'native_fixture_isolation', 'load_postrun_ledger', 'source_pins', 'claims', 'limits'}
    if set(witness) != required:
        raise ValueError('Retained audit witness has unknown or missing top-level fields')
    input_report = witness.get('input_report')
    if type(input_report) is not dict or set(input_report) != {'path', 'bytes', 'sha256'} or type(input_report.get('path')) is not str or (not input_report['path'].startswith('evidence/')) or _resolve_resource_path(Path(input_report['path'])).is_absolute() or ('..' in _resolve_resource_path(Path(input_report['path'])).parts) or (type(input_report.get('bytes')) is not int) or (input_report['bytes'] <= 0) or (type(input_report.get('sha256')) is not str) or (not HEX64.fullmatch(input_report['sha256'])):
        raise ValueError('Witness does not pin an actual evidence report')
    child = witness.get('child')
    if type(child) is not dict or set(child) != {'pid', 'started_monotonic_seconds', 'ended_monotonic_seconds', 'wall_seconds', 'peak_sampled_private_bytes', 'exit_code', 'reaped', 'timed_out'} or type(child.get('pid')) is not int or (not 1 <= child['pid'] <= 4294967295) or (type(child.get('started_monotonic_seconds')) not in (int, float)) or (not math.isfinite(child['started_monotonic_seconds'])) or (type(child.get('ended_monotonic_seconds')) not in (int, float)) or (not math.isfinite(child['ended_monotonic_seconds'])) or (child['ended_monotonic_seconds'] < child['started_monotonic_seconds']) or (type(child.get('wall_seconds')) not in (int, float)) or (not 0 < child['wall_seconds'] <= 60) or (type(child.get('peak_sampled_private_bytes')) is not int) or (not 0 < child['peak_sampled_private_bytes'] <= 512 * 1024 * 1024) or (type(child.get('exit_code')) is not int) or (child['exit_code'] != 90) or (child.get('reaped') is not True) or (child.get('timed_out') is not False):
        raise ValueError('Witness child lifecycle/resource receipt is outside the bounded profile')
    chain = witness.get('load_and_resume')
    chain_keys = {'input_profile', 'input_manifest_sha256', 'input_game_bytes', 'load_status', 'game_initialized', 'load_markers', 'resume_prefix'}
    if type(chain) is not dict or set(chain) != chain_keys:
        raise ValueError('Witness Load/resume chain has wrong shape')
    if chain.get('input_profile') != 'late380' or chain.get('input_manifest_sha256') != profile.input_manifest_sha256 or type(chain.get('input_game_bytes')) is not int or (type(chain.get('load_status')) is not int) or (chain['load_status'] != 0) or (type(chain.get('game_initialized')) is not int) or (chain['game_initialized'] != 1):
        raise ValueError('Witness Load receipt differs from the pinned late380 source pair')
    from civ6_host.runtime.native.native_checkpoint_profile import LATE_380
    from civ6_host.runtime.native.native_checkpoint_profile import read_verified_pair
    input_pair = read_verified_pair(LATE_380, root=root)
    if chain['input_game_bytes'] != len(input_pair.game) or input_pair.manifest_sha256 != profile.input_manifest_sha256 or hashlib.sha256(input_pair.game).hexdigest() != profile.input_game_sha256 or (hashlib.sha256(input_pair.configuration).hexdigest() != profile.input_configuration_sha256):
        raise ValueError('Witness does not bind the exact pinned late380 source pair')
    markers = chain.get('load_markers')
    marker_order = ('before_native_checkpoint_load', 'native_checkpoint_load_returned_diagnostic', 'native_checkpoint_load_only_observed', 'native_checkpoint_postload_facades_observed', 'native_checkpoint_postload_160_observed')
    marker_values = [markers.get(key) for key in marker_order] if type(markers) is dict else []
    if type(markers) is not dict or set(markers) != set(marker_order) or any((type(v) is not int for v in marker_values)) or (marker_values != sorted(set(marker_values))):
        raise ValueError('Witness Load marker indices are not unique and ordered')
    prefix = chain.get('resume_prefix')
    prefix_keys = {'requested_rounds', 'round_effect_receipts', 'observed_transitions', 'aggregate_receipt_present', 'partial_boundary_present', 'unsupported_host_contract_events', 'unsupported_host_contract_details'}
    if type(prefix) is not dict or set(prefix) != prefix_keys or type(prefix.get('requested_rounds')) is not int or (prefix['requested_rounds'] != profile.resumed_rounds) or (type(prefix.get('round_effect_receipts')) is not int) or (prefix['round_effect_receipts'] != profile.resumed_rounds) or (prefix.get('observed_transitions') != [list(x) for x in profile.transitions]) or (prefix.get('aggregate_receipt_present') is not True) or (type(prefix.get('partial_boundary_present')) is not bool) or (type(prefix.get('unsupported_host_contract_events')) is not int) or (prefix['unsupported_host_contract_events'] != 0) or (prefix.get('unsupported_host_contract_details') != []):
        raise ValueError('Witness does not prove the exact three-round 115→118 prefix')
    saved = witness.get('retained_save')
    if type(saved) is not dict or set(saved) != {'manifest', 'components', 'save_marker_indices', 'save_status', 'stream_closed', 'jobs_unchanged_quiescent', 'ledger_postrun_required', 'ledger_reconciled_in_manifest'}:
        raise ValueError('Witness retained-Save evidence has wrong shape')
    saved_manifest = saved.get('manifest')
    if type(saved_manifest) is not dict or set(saved_manifest) != {'path', 'bytes', 'sha256'} or saved_manifest.get('path') != profile.manifest_path or (saved_manifest.get('sha256') != profile.manifest_sha256) or (type(saved_manifest.get('bytes')) is not int) or (saved_manifest['bytes'] <= 0):
        raise ValueError('Witness manifest reference differs from the registered retained profile')
    expected_components = {'gamecore': {'path': profile.game_path, 'bytes': profile.game_bytes, 'sha256': profile.game_sha256}, 'application_configuration': {'path': profile.configuration_path, 'bytes': profile.configuration_bytes, 'sha256': profile.configuration_sha256}}
    if saved.get('components') != expected_components:
        raise ValueError('Witness component references differ from the registered profile')
    indices = saved.get('save_marker_indices')
    if type(indices) is not dict or set(indices) != {'before_native_checkpoint_retained_save', 'native_checkpoint_retained_save_finalized'} or any((type(x) is not int for x in indices.values())) or (indices['native_checkpoint_retained_save_finalized'] <= indices['before_native_checkpoint_retained_save']):
        raise ValueError('Witness Save markers are not a single ordered pair')
    for key, expected in (('save_status', 0), ('stream_closed', True), ('jobs_unchanged_quiescent', True), ('ledger_postrun_required', True), ('ledger_reconciled_in_manifest', False)):
        if type(saved.get(key)) is not type(expected) or saved[key] != expected:
            raise ValueError('Witness Save receipt differs: ' + key)
    ledger = witness.get('load_postrun_ledger')
    if type(ledger) is not dict or set(ledger) != {'status', 'ledger_reconciled', 'schema', 'created_empty_handles', 'ledger_events_match_snapshot'} or ledger.get('status') != 'real_validator_reconciled' or (ledger.get('ledger_reconciled') is not True) or (ledger.get('schema') != 'civ6rl.native_checkpoint_postload_empty_jobs_transition.v1') or (type(ledger.get('created_empty_handles')) is not list) or any((type(handle) is not int or not 1 <= handle <= 64 for handle in ledger['created_empty_handles'])) or (len(ledger['created_empty_handles']) != len(set(ledger['created_empty_handles']))) or (ledger['created_empty_handles'] != sorted(ledger['created_empty_handles'])) or (ledger.get('ledger_events_match_snapshot') is not True):
        raise ValueError('Witness lacks the real post-run Load ledger validation receipt')
    if manifest.get('components') != expected_components:
        raise ValueError('Validated manifest differs from witness/profile component pins')
    pins = witness.get('source_pins')
    pin_paths = {'retained_save': 'civ6rl/native_checkpoint_retained_save.py', 'probe': 'civ6rl/native_probe.py', 'postload_jobs': 'civ6rl/native_checkpoint_postload_jobs.py', 'auditor417': 'work/audit_native_late_rounds417.py', 'auditor434': 'work/native-retained-save-auditor434.py', 'auditor434_v2': 'work/native-retained-save-auditor434-v2.py'}
    if type(pins) is not dict or set(pins) != set(pin_paths):
        raise ValueError('Witness source pin map has wrong shape')
    root = _resolve_resource_path(_resolve_resource_path(Path(root))).resolve()
    for key, relative in pin_paths.items():
        row = pins[key]
        if type(row) is not dict or set(row) != {'path', 'sha256'} or row.get('path') != relative or (type(row.get('sha256')) is not str) or (not HEX64.fullmatch(row['sha256'])):
            raise ValueError('Witness source pin is malformed: ' + key)
        archived = {('civ6rl/native_checkpoint_retained_save.py', 'ed7aa73eb00b0ec730a5fbd1def20774d653d7dc4f30f83edbbcda820cecd01f'): 'work/native390-baseline/native_checkpoint_retained_save.py', ('civ6rl/native_probe.py', '6c71a7fe6a44db399b49371b2d7cef24fc66ff62ca7de136696ffc5c2a6d47af'): 'work/native-postload-jobs-probe385.py', ('civ6rl/native_checkpoint_postload_jobs.py', 'e34da08b106c1a1073ab9950f42b56c48ba04014a7193012851f1bdee7a9a0c2'): 'work/native386-baseline/native_checkpoint_postload_jobs.py'}
        path = root / archived.get((relative, row['sha256']), relative)
        if not _resolve_resource_path(path).is_file() or hashlib.sha256(_resolve_resource_path(path).read_bytes()).hexdigest() != row['sha256']:
            raise ValueError('Witness source file no longer matches its pin: ' + key)
    _validate_fixture_isolation(witness, root)
    claims = witness.get('claims')
    expected_claims = {'retained_pair_published': True, 'new_pair_loaded': False, 'context_destroyed': False, 'reset_validated': False, 'complete_game': False, 'eligible_for_training': False}
    if claims != expected_claims:
        raise ValueError('Witness claims exceed the retained diagnostic boundary')
    limits = witness.get('limits')
    expected_limits = ['One retained late380 Load, three turns (115→118), and one Save receipt only.', 'The actual post-run Host41 validator supplies the Load ledger result; counters and snapshots are not substitutes.', 'Published components are raw diagnostic streams, not a full Civilization VI save container.', 'No Load of the new pair, process reset, full episode, destruction, or training readiness is established.']
    if limits != expected_limits:
        raise ValueError('Witness must preserve its four explicit scope limitations')
    return witness

def _validate_audit_witness121(profile: RetainedProfile, witness: dict, manifest: dict, root: Path) -> dict:
    """Strict semantic check for the separately pinned Save121 auditor470 receipt."""
    pinned_raw = _read_pinned(root, profile.witness_path, profile.witness_sha256, MAX_WITNESS_BYTES)
    try:
        pinned_value = json.loads(pinned_raw.decode('utf-8'))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError('Pinned retained121 witness is invalid JSON') from exc
    if type(witness) is not dict or witness != pinned_value:
        raise ValueError('Retained121 witness differs from its immutable auditor470 receipt')
    if type(witness) is not dict or witness.get('schema') != AUDIT_WITNESS_121_SCHEMA:
        raise ValueError('Retained121 witness is not the final auditor470 schema')
    required = {'child', 'claims', 'input_report', 'limits', 'load_and_resume', 'load_postrun_ledger', 'native_fixture', 'native_fixture_isolation', 'native_fixture_sha256', 'retained_save', 'schema', 'source_pins', 'translation_provenance'}
    if set(witness) != required:
        raise ValueError('Retained121 witness has unknown or missing fields')
    if witness['input_report'] != {'path': 'evidence/native-newgame-script-prefix390.json', 'bytes': 20755732, 'sha256': '65e1ecaa8a96f859be657adb61954823380460763447d88fff9ec606520529f8'}:
        raise ValueError('Retained121 witness input report is not the frozen native390 run')
    child = witness['child']
    if type(child) is not dict or child.get('exit_code') != 90 or type(child.get('exit_code')) is not int or (child.get('reaped') is not True) or (child.get('timed_out') is not False) or (type(child.get('pid')) is not int) or (child['pid'] <= 0) or (type(child.get('wall_seconds')) not in (int, float)) or (not 0 < child['wall_seconds'] <= 60) or (type(child.get('peak_sampled_private_bytes')) is not int) or (not 0 < child['peak_sampled_private_bytes'] <= 512 * 1024 * 1024):
        raise ValueError('Retained121 child receipt violates the bounded worker contract')
    load = witness['load_and_resume']
    if type(load) is not dict or load.get('input_profile') != 'retained118' or load.get('input_manifest_sha256') != profile.input_manifest_sha256 or (load.get('input_game_bytes') != RETAINED_118.game_bytes) or (load.get('load_status') != 0) or (load.get('game_initialized') != 1) or (load.get('resume_prefix', {}).get('requested_rounds') != 3) or (load.get('resume_prefix', {}).get('observed_transitions') != [[118, 119], [119, 120], [120, 121]]) or (load.get('resume_prefix', {}).get('round_effect_receipts') != 3) or (load.get('resume_prefix', {}).get('unsupported_host_contract_events') != 0) or (load.get('readback', {}).get('current_game_turn') != 118) or (load.get('readback', {}).get('width') != 74) or (load.get('readback', {}).get('height') != 46):
        raise ValueError('Retained121 native Load/resume lineage differs from the observed chain')
    saved = witness['retained_save']
    expected_components = {'gamecore': {'path': profile.game_path, 'bytes': profile.game_bytes, 'sha256': profile.game_sha256}, 'application_configuration': {'path': profile.configuration_path, 'bytes': profile.configuration_bytes, 'sha256': profile.configuration_sha256}}
    if type(saved) is not dict or saved.get('manifest') != {'path': profile.manifest_path, 'bytes': 18612, 'sha256': profile.manifest_sha256} or saved.get('components') != expected_components or (saved.get('save_status') != 0) or (saved.get('stream_closed') is not True) or (saved.get('jobs_unchanged_quiescent') is not True) or (saved.get('ledger_postrun_required') is not True) or (saved.get('ledger_reconciled_in_manifest') is not False):
        raise ValueError('Retained121 Save receipt does not match the pinned pair')
    if manifest.get('components') != expected_components:
        raise ValueError('Retained121 manifest and witness component identities differ')
    if witness['claims'] != {'retained_pair_published': True, 'new_pair_loaded': False, 'context_destroyed': False, 'reset_validated': False, 'complete_game': False, 'eligible_for_training': False}:
        raise ValueError('Retained121 witness claims exceed its Save-only boundary')
    ledger = witness['load_postrun_ledger']
    if type(ledger) is not dict or ledger.get('status') != 'real_validator_reconciled' or ledger.get('ledger_reconciled') is not True or (ledger.get('schema') != 'civ6rl.native_checkpoint_postload_empty_jobs_transition.v1') or (ledger.get('created_empty_handles') != [1]) or (ledger.get('ledger_events_match_snapshot') is not True):
        raise ValueError('Retained121 witness lacks the actual postrun ledger receipt')
    root = _resolve_resource_path(_resolve_resource_path(Path(root))).resolve()
    pins = witness['source_pins']
    expected_paths = {'auditor434_v2': 'work/native-retained-save-auditor434-v2.py', 'auditor451': 'work/audit_native_retained118_rounds451.py', 'auditor470': 'work/native-retained-save-auditor470.py', 'postload_jobs': 'civ6rl/native_checkpoint_postload_jobs.py', 'probe': 'civ6rl/native_probe.py', 'resume': 'civ6rl/native_checkpoint_resume.py', 'retained_profile': 'civ6rl/native_checkpoint_retained_profile.py', 'retained_save': 'civ6rl/native_checkpoint_retained_save.py'}
    if type(pins) is not dict or set(pins) != set(expected_paths):
        raise ValueError('Retained121 source pin set is incomplete')
    archived = {'civ6rl/native_checkpoint_postload_jobs.py': root / 'work/native391-baseline/native_checkpoint_postload_jobs.py', 'civ6rl/native_probe.py': root / 'work/native391-baseline/native_probe.py', 'civ6rl/native_checkpoint_resume.py': root / 'work/native391-baseline/native_checkpoint_resume.py', 'civ6rl/native_checkpoint_retained_profile.py': root / 'work/native391-baseline/native_checkpoint_retained_profile.py', 'civ6rl/native_checkpoint_retained_save.py': root / 'work/native391-baseline/native_checkpoint_retained_save.py'}
    for key, relative in expected_paths.items():
        pin = pins[key]
        if type(pin) is not dict or set(pin) != {'path', 'sha256'} or pin.get('path') != relative or (type(pin.get('sha256')) is not str) or (not HEX64.fullmatch(pin['sha256'])):
            raise ValueError('Retained121 source pin malformed: ' + key)
        source = archived.get(relative, root / relative)
        if not _resolve_resource_path(source).is_file() or hashlib.sha256(_resolve_resource_path(source).read_bytes()).hexdigest() != pin['sha256']:
            raise ValueError('Retained121 source pin mismatch: ' + key)
    _validate_fixture_isolation(witness, root)
    limits = witness['limits']
    if type(limits) is not list or len(limits) != 4 or any((type(x) is not str for x in limits)) or ('No Load of the new pair' not in limits[3]):
        raise ValueError('Retained121 witness scope limitations are missing')
    return witness

def _validate_audit_witness150(profile: RetainedProfile, witness: dict, manifest: dict, root: Path) -> dict:
    """Strict semantic admission for the independently audited Save150 receipt."""
    root = _resolve_resource_path(_resolve_resource_path(Path(root))).resolve()
    pinned_raw = _read_pinned(root, profile.witness_path, profile.witness_sha256, MAX_WITNESS_BYTES)
    try:
        pinned_value = json.loads(pinned_raw.decode('utf-8'))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError('Pinned retained150 witness is invalid JSON') from exc
    if type(witness) is not dict or witness != pinned_value:
        raise ValueError('Retained150 witness differs from its immutable auditor569 receipt')
    required = {'child', 'claims', 'input_report', 'limits', 'load_and_resume', 'load_postrun_ledger', 'native_fixture', 'native_fixture_isolation', 'native_fixture_sha256', 'retained_save', 'schema', 'source_pins', 'translation_provenance'}
    if set(witness) != required or witness.get('schema') != AUDIT_WITNESS_150_SCHEMA:
        raise ValueError('Retained150 witness schema or field set differs from auditor569')
    if witness['input_report'] != {'path': 'evidence/native-newgame-script-prefix401.json', 'bytes': 97714198, 'sha256': '4baa81641b0c8f11af8bd2480d12e2228df169de168c0dbbbeb5c99a9dfbb293'}:
        raise ValueError('Retained150 witness does not reference the audited native401 report')
    child = witness['child']
    if type(child) is not dict or set(child) != {'ended_monotonic_seconds', 'exit_code', 'peak_sampled_private_bytes', 'pid', 'reaped', 'started_monotonic_seconds', 'timed_out', 'wall_seconds'} or type(child.get('exit_code')) is not int or (child['exit_code'] != 90) or (child.get('reaped') is not True) or (child.get('timed_out') is not False) or (type(child.get('pid')) is not int) or (child['pid'] <= 0) or (type(child.get('wall_seconds')) not in (int, float)) or (not 0 < child['wall_seconds'] <= 600) or (type(child.get('peak_sampled_private_bytes')) is not int) or (not 0 < child['peak_sampled_private_bytes'] <= 512 * 1024 * 1024):
        raise ValueError('Retained150 child receipt violates its bounded 32-round worker contract')
    chain = witness['load_and_resume']
    if type(chain) is not dict or set(chain) != {'game_initialized', 'input_game_bytes', 'input_manifest_sha256', 'input_profile', 'load_markers', 'load_status', 'readback', 'resume_prefix'} or chain.get('input_profile') != 'retained118' or (chain.get('input_manifest_sha256') != profile.input_manifest_sha256) or (type(chain.get('input_game_bytes')) is not int) or (chain['input_game_bytes'] != RETAINED_118.game_bytes) or (type(chain.get('load_status')) is not int) or (chain['load_status'] != 0) or (type(chain.get('game_initialized')) is not int) or (chain['game_initialized'] != 1):
        raise ValueError('Retained150 Load receipt differs from the immutable retained118 input pair')
    readback = chain['readback']
    if type(readback) is not dict or set(readback) != {'current_game_turn', 'game_update_called', 'height', 'major_player_ids', 'scope', 'width'} or type(readback.get('current_game_turn')) is not int or (readback['current_game_turn'] != 118) or (type(readback.get('width')) is not int) or (readback['width'] != 74) or (type(readback.get('height')) is not int) or (readback['height'] != 46) or (readback.get('major_player_ids') != [0, 1]) or (readback.get('game_update_called') is not False) or (readback.get('scope') != 'privileged diagnostic; no learner observation'):
        raise ValueError('Retained150 Load readback differs from retained118 start state')
    markers = chain['load_markers']
    marker_keys = {'before_native_checkpoint_load', 'native_checkpoint_load_only_observed', 'native_checkpoint_load_returned_diagnostic', 'native_checkpoint_postload_160_observed', 'native_checkpoint_postload_facades_observed'}
    if type(markers) is not dict or set(markers) != marker_keys or any((type(markers.get(key)) is not int or markers[key] < 0 for key in marker_keys)) or (not markers['before_native_checkpoint_load'] < markers['native_checkpoint_load_returned_diagnostic'] < markers['native_checkpoint_load_only_observed'] < markers['native_checkpoint_postload_facades_observed'] < markers['native_checkpoint_postload_160_observed']):
        raise ValueError('Retained150 Load/facade/post160 marker order differs')
    prefix = chain['resume_prefix']
    transitions = [list(row) for row in profile.transitions]
    if type(prefix) is not dict or set(prefix) != {'aggregate_receipt_present', 'observed_transitions', 'partial_boundary_present', 'requested_rounds', 'round_effect_receipts', 'unsupported_host_contract_details', 'unsupported_host_contract_events'} or type(prefix.get('requested_rounds')) is not int or (prefix['requested_rounds'] != 32) or (type(prefix.get('round_effect_receipts')) is not int) or (prefix['round_effect_receipts'] != 32) or (prefix.get('observed_transitions') != transitions) or (prefix.get('aggregate_receipt_present') is not True) or (prefix.get('partial_boundary_present') is not True) or (type(prefix.get('unsupported_host_contract_events')) is not int) or (prefix['unsupported_host_contract_events'] != 0) or (prefix.get('unsupported_host_contract_details') != []):
        raise ValueError('Retained150 witness does not prove the exact 32-round 118→150 lineage')
    expected_components = {'gamecore': {'path': profile.game_path, 'bytes': profile.game_bytes, 'sha256': profile.game_sha256}, 'application_configuration': {'path': profile.configuration_path, 'bytes': profile.configuration_bytes, 'sha256': profile.configuration_sha256}}
    saved = witness['retained_save']
    if type(saved) is not dict or set(saved) != {'components', 'jobs_unchanged_quiescent', 'ledger_postrun_required', 'ledger_reconciled_in_manifest', 'manifest', 'save_marker_indices', 'save_status', 'stream_closed'} or saved.get('manifest') != {'path': profile.manifest_path, 'bytes': 19614, 'sha256': profile.manifest_sha256} or (saved.get('components') != expected_components) or (type(saved.get('save_status')) is not int) or (saved['save_status'] != 0) or (saved.get('stream_closed') is not True) or (saved.get('jobs_unchanged_quiescent') is not True) or (saved.get('ledger_postrun_required') is not True) or (saved.get('ledger_reconciled_in_manifest') is not False):
        raise ValueError('Retained150 Save receipt differs from the frozen component pair')
    save_markers = saved['save_marker_indices']
    if type(save_markers) is not dict or set(save_markers) != {'before_native_checkpoint_retained_save', 'native_checkpoint_retained_save_finalized'} or any((type(value) is not int or value < 0 for value in save_markers.values())) or (save_markers['native_checkpoint_retained_save_finalized'] <= save_markers['before_native_checkpoint_retained_save']) or (manifest.get('components') != expected_components):
        raise ValueError('Retained150 Save markers or manifest components differ')
    if witness['claims'] != {'complete_game': False, 'context_destroyed': False, 'eligible_for_training': False, 'new_pair_loaded': False, 'reset_validated': False, 'retained_pair_published': True}:
        raise ValueError('Retained150 witness claims exceed its one-Save boundary')
    ledger = witness['load_postrun_ledger']
    if type(ledger) is not dict or set(ledger) != {'created_empty_handles', 'ledger_events_match_snapshot', 'ledger_reconciled', 'schema', 'status'} or ledger.get('status') != 'real_validator_reconciled' or (ledger.get('ledger_reconciled') is not True) or (ledger.get('schema') != 'civ6rl.native_checkpoint_postload_empty_jobs_transition.v1') or (ledger.get('created_empty_handles') != [1]) or (ledger.get('ledger_events_match_snapshot') is not True):
        raise ValueError('Retained150 witness lacks the actual postrun Load ledger receipt')
    pins = witness['source_pins']
    expected_paths = {'auditor434_v2': 'work/native-retained-save-auditor434-v2.py', 'auditor470': 'work/native-retained-save-auditor470.py', 'auditor516': 'work/audit_native_retained118_long_rounds516.py', 'postload_jobs': 'civ6rl/native_checkpoint_postload_jobs.py', 'probe': 'civ6rl/native_probe.py', 'resume': 'civ6rl/native_checkpoint_resume.py', 'retained_profile': 'civ6rl/native_checkpoint_retained_profile.py', 'retained_save': 'civ6rl/native_checkpoint_retained_save.py'}
    if type(pins) is not dict or set(pins) != set(expected_paths):
        raise ValueError('Retained150 source pin set is incomplete')
    archived = {'civ6rl/native_checkpoint_postload_jobs.py': root / 'work/native401-composition572/civ6rl/native_checkpoint_postload_jobs.py', 'civ6rl/native_probe.py': root / 'work/native401-composition572/civ6rl/native_probe.py', 'civ6rl/native_checkpoint_resume.py': root / 'work/native401-composition572/civ6rl/native_checkpoint_resume.py', 'civ6rl/native_checkpoint_retained_profile.py': root / 'work/native393-composition491/native_checkpoint_retained_profile.py', 'civ6rl/native_checkpoint_retained_save.py': root / 'work/native401-composition572/civ6rl/native_checkpoint_retained_save.py'}
    for key, relative in expected_paths.items():
        pin = pins[key]
        if type(pin) is not dict or set(pin) != {'path', 'sha256'} or pin.get('path') != relative or (type(pin.get('sha256')) is not str) or (not HEX64.fullmatch(pin['sha256'])):
            raise ValueError('Retained150 source pin malformed: ' + key)
        source = archived.get(relative, root / relative)
        if not _resolve_resource_path(source).is_file() or hashlib.sha256(_resolve_resource_path(source).read_bytes()).hexdigest() != pin['sha256']:
            raise ValueError('Retained150 source pin mismatch: ' + key)
    _validate_fixture_isolation(witness, root)
    expected_provenance = {'fixture_validation': '434v2 function unchanged; actual three private DBs hashed', 'input_profile': 'retained118', 'input_turn': 118, 'native_turn_transitions': transitions, 'output_turn': 150, 'parents': {'work/audit_native_retained118_long_rounds516.py': '978eaecf84150ec5197ac9495a78165241b992c524fa8c252f4a5829daa1eb9b', 'work/native-retained-save-auditor434-v2.py': 'b551666eafa01db13a6843cfceae490c729f90784be6f1ba0e86f8833481ec47', 'work/native-retained-save-auditor470.py': 'a51f9c3a52e83cbfa16ddb2ec135c0f65a2d3b018248d30cb19638a7b447c1a0'}, 'profile_plan_sha256': '5f13e25b218b770b89122cf5cacba22d026f7ecc67c22b942af146d641dc2dd6', 'turn_offset_or_stage_relabel_used': False}
    if witness['translation_provenance'] != expected_provenance:
        raise ValueError('Retained150 translation provenance differs from the audited 118→150 chain')
    expected_limits = ['One retained118 Load, 32 turns (118→150), and one Save receipt only.', 'The actual post-run Host41 validator supplies the Load ledger result; counters and snapshots are not substitutes.', 'Published components are raw diagnostic streams, not a full Civilization VI save container.', 'No Load of the new pair, process reset, full episode, destruction, or training readiness is established.']
    if witness['limits'] != expected_limits:
        raise ValueError('Retained150 witness scope limitations differ from auditor569')
    return witness

def _validate_audit_witness182(profile: RetainedProfile, witness: dict, manifest: dict, root: Path) -> dict:
    """Admit only the immutable auditor648 receipt for the actual Save182 pair."""
    raw = _read_pinned(root, profile.witness_path, profile.witness_sha256, MAX_WITNESS_BYTES)
    try:
        pinned = json.loads(raw.decode('utf-8'))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError('Pinned retained182 audit is invalid JSON') from exc
    if type(witness) is not dict or witness != pinned:
        raise ValueError('Retained182 witness differs from immutable auditor648 receipt')
    required = {'child', 'claims', 'composition_and_promotion', 'input_report', 'limits', 'load_and_resume', 'load_postrun_ledger', 'native_fixture', 'native_fixture_isolation', 'native_fixture_sha256', 'retained_save', 'schema', 'source_pins', 'translation_provenance'}
    if set(witness) != required or witness.get('schema') != AUDIT_WITNESS_182_SCHEMA:
        raise ValueError('Retained182 witness schema or fields differ from auditor648')
    child = witness['child']
    if type(child) is not dict or set(child) != {'ended_monotonic_seconds', 'exit_code', 'peak_sampled_private_bytes', 'pid', 'reaped', 'started_monotonic_seconds', 'timed_out', 'wall_seconds'} or type(child.get('exit_code')) is not int or (child['exit_code'] != 90) or (child.get('reaped') is not True) or (child.get('timed_out') is not False) or (type(child.get('pid')) is not int) or (child['pid'] <= 0) or (type(child.get('wall_seconds')) not in (int, float)) or (not 0 < child['wall_seconds'] <= 600) or (type(child.get('peak_sampled_private_bytes')) is not int) or (not 0 < child['peak_sampled_private_bytes'] <= 512 * 1024 * 1024):
        raise ValueError('Retained182 worker receipt is outside the bounded one-attempt contract')
    chain = witness['load_and_resume']
    if type(chain) is not dict or chain.get('input_profile') != 'retained150' or chain.get('input_manifest_sha256') != profile.input_manifest_sha256 or (type(chain.get('input_game_bytes')) is not int) or (chain['input_game_bytes'] != RETAINED_150.game_bytes) or (type(chain.get('load_status')) is not int) or (chain['load_status'] != 0) or (type(chain.get('game_initialized')) is not int) or (chain['game_initialized'] != 1):
        raise ValueError('Retained182 Load receipt differs from the exact retained150 input')
    readback = chain.get('readback')
    if type(readback) is not dict or readback.get('current_game_turn') != 150 or type(readback.get('current_game_turn')) is not int or (readback.get('width') != 74) or (type(readback.get('width')) is not int) or (readback.get('height') != 46) or (type(readback.get('height')) is not int) or (readback.get('major_player_ids') != [0, 1]) or (readback.get('game_update_called') is not False) or (readback.get('scope') != 'privileged diagnostic; no learner observation'):
        raise ValueError('Retained182 Load readback differs from turn150 retained input')
    prefix = chain.get('resume_prefix')
    transitions = [list(row) for row in profile.transitions]
    if type(prefix) is not dict or prefix.get('requested_rounds') != 32 or type(prefix.get('requested_rounds')) is not int or (prefix.get('round_effect_receipts') != 32) or (type(prefix.get('round_effect_receipts')) is not int) or (prefix.get('observed_transitions') != transitions) or (prefix.get('aggregate_receipt_present') is not True) or (prefix.get('partial_boundary_present') is not True) or (prefix.get('aggregate_public_game_update_budget') != 4640) or (type(prefix.get('aggregate_public_game_updates')) is not int) or (not 0 <= prefix['aggregate_public_game_updates'] <= 4640) or (prefix.get('unsupported_host_contract_events') != 0) or (prefix.get('unsupported_host_contract_details') != []):
        raise ValueError('Retained182 witness does not prove exactly 32 transitions 150→182')
    if witness['claims'] != {'complete_game': False, 'context_destroyed': False, 'eligible_for_training': False, 'new_pair_loaded': False, 'reset_validated': False, 'retained_pair_published': True}:
        raise ValueError('Retained182 witness claims exceed its Save-only boundary')
    ledger = witness['load_postrun_ledger']
    if type(ledger) is not dict or ledger.get('status') != 'real_validator_reconciled' or ledger.get('ledger_reconciled') is not True or (ledger.get('schema') != 'civ6rl.native_checkpoint_postload_empty_jobs_transition.v1') or (ledger.get('created_empty_handles') != [1]) or (ledger.get('ledger_events_match_snapshot') is not True):
        raise ValueError('Retained182 witness lacks its real postrun Load ledger receipt')
    expected_components = {'gamecore': {'path': profile.game_path, 'bytes': profile.game_bytes, 'sha256': profile.game_sha256}, 'application_configuration': {'path': profile.configuration_path, 'bytes': profile.configuration_bytes, 'sha256': profile.configuration_sha256}}
    saved = witness['retained_save']
    if type(saved) is not dict or saved.get('manifest') != {'path': profile.manifest_path, 'bytes': 19614, 'sha256': profile.manifest_sha256} or saved.get('components') != expected_components or (type(saved.get('save_status')) is not int) or (saved['save_status'] != 0) or (saved.get('stream_closed') is not True) or (saved.get('jobs_unchanged_quiescent') is not True) or (saved.get('ledger_postrun_required') is not True) or (saved.get('ledger_reconciled_in_manifest') is not False) or (manifest.get('components') != expected_components):
        raise ValueError('Retained182 audit and manifest differ from the exact saved pair')
    return witness

def _validate_fixture_isolation(witness: dict, root: Path) -> dict:
    """Check that fixture provenance came from a real one-worker private copy.

    This preserves the exact shape consumed later by configuration_only's
    validate_private_fixture; it does not claim training eligibility.
    """
    root = _resolve_resource_path(_resolve_resource_path(Path(root))).resolve()
    work = _resolve_resource_path(root / 'work').resolve()
    source_path_raw = witness.get('native_fixture')
    source_sha = witness.get('native_fixture_sha256')
    isolation = witness.get('native_fixture_isolation')
    if type(source_path_raw) is not str or not source_path_raw or type(source_sha) is not str or (not HEX64.fullmatch(source_sha)) or (type(isolation) is not dict) or (set(isolation) != {'root', 'source_manifest_path', 'source_manifest_sha256', 'worker_count', 'workers'}):
        raise ValueError('Retained witness lacks exact native fixture provenance')
    source_path = _resolve_resource_path(_resolve_resource_path(Path(source_path_raw))).resolve()
    if not source_path.is_relative_to(work) or not _resolve_resource_path(source_path).is_file() or hashlib.sha256(_resolve_resource_path(source_path).read_bytes()).hexdigest() != source_sha or (isolation.get('source_manifest_path') != str(source_path)) or (isolation.get('source_manifest_sha256') != source_sha):
        raise ValueError('Fixture source manifest path/SHA is not pinned to the witness')
    if type(isolation.get('worker_count')) is not int or isolation['worker_count'] != 1 or type(isolation.get('workers')) is not list or (len(isolation['workers']) != 1):
        raise ValueError('Only the captured single-worker fixture is supported')
    worker = isolation['workers'][0]
    worker_keys = {'worker_index', 'manifest_path', 'manifest_sha256', 'databases'}
    if type(worker) is not dict or set(worker) != worker_keys or type(worker.get('worker_index')) is not int or (worker['worker_index'] != 0) or (type(worker.get('manifest_path')) is not str) or (type(worker.get('manifest_sha256')) is not str) or (not HEX64.fullmatch(worker['manifest_sha256'])):
        raise ValueError('Private fixture worker manifest reference is malformed')
    worker_manifest = _resolve_resource_path(_resolve_resource_path(Path(worker['manifest_path']))).resolve()
    fixture_root = _resolve_resource_path(_resolve_resource_path(Path(isolation.get('root', '')))).resolve()
    if not fixture_root.is_relative_to(work) or worker_manifest.parent.parent != fixture_root or worker_manifest.name != 'manifest.json' or (not _resolve_resource_path(worker_manifest).is_file()) or (hashlib.sha256(_resolve_resource_path(worker_manifest).read_bytes()).hexdigest() != worker['manifest_sha256']):
        raise ValueError('Private worker manifest escapes or differs from its captured fixture root')
    from civ6_host.runtime.native.native_host import validate_fixture
    validated = validate_fixture(worker_manifest)
    raw_worker = json.loads(_resolve_resource_path(worker_manifest).read_text(encoding='utf-8-sig'))
    worker_iso = raw_worker.get('isolation')
    if type(worker_iso) is not dict or worker_iso.get('copies_created_before_worker_launch') is not True or type(worker_iso.get('worker_index')) is not int or (worker_iso['worker_index'] != 0) or (type(worker_iso.get('worker_count')) is not int) or (worker_iso['worker_count'] != 1) or (worker_iso.get('source_manifest_path') != str(source_path)) or (worker_iso.get('source_manifest_sha256') != source_sha):
        raise ValueError('Private manifest does not prove its one-worker source lineage')
    databases = worker.get('databases')
    if type(databases) is not dict or set(databases) != {'configuration', 'gameplay', 'localization'}:
        raise ValueError('Private fixture database map is incomplete')
    actual = validated.get('databases')
    for name in ('configuration', 'gameplay', 'localization'):
        row = databases[name]
        validated_row = actual.get(name)
        if type(row) is not dict or set(row) != {'source_path', 'copy_path', 'sha256'} or type(row.get('source_path')) is not str or (type(row.get('copy_path')) is not str) or (type(row.get('sha256')) is not str) or (not HEX64.fullmatch(row['sha256'])) or (type(validated_row) is not dict) or (_resolve_resource_path(_resolve_resource_path(Path(row['copy_path']))).resolve() != _resolve_resource_path(_resolve_resource_path(Path(validated_row['path']))).resolve()) or (_resolve_resource_path(_resolve_resource_path(Path(row['source_path']))).resolve() != _resolve_resource_path(_resolve_resource_path(Path(validated_row['source_path']))).resolve()) or (row['sha256'] != validated_row['sha256']):
            raise ValueError('Private fixture database identity differs: ' + name)
        copy_path, original_path = (_resolve_resource_path(_resolve_resource_path(Path(row['copy_path']))).resolve(), _resolve_resource_path(_resolve_resource_path(Path(row['source_path']))).resolve())
        if not copy_path.is_relative_to(work) or not original_path.is_relative_to(work) or (not _resolve_resource_path(copy_path).is_file()) or (not _resolve_resource_path(original_path).is_file()) or (hashlib.sha256(_resolve_resource_path(copy_path).read_bytes()).hexdigest() != row['sha256']) or (hashlib.sha256(_resolve_resource_path(original_path).read_bytes()).hexdigest() != row['sha256']):
            raise ValueError('Private fixture database bytes differ from captured hashes: ' + name)
    return isolation

def load_pair(profile: RetainedProfile, root: Path) -> RetainedMatchedPair:
    """Read only a separately pinned profile and verify its complete pair."""
    profile.validate_definition()
    if RETAINED_PROFILES.get(profile.profile_id) is not profile:
        raise ValueError('Retained profile is not in the frozen admission registry')
    if dict(profile.source_proofs) != current_source_proofs(profile_id=profile.profile_id):
        raise ValueError('Retained profile source proof pins no longer match live evidence')
    manifest_raw = _read_pinned(root, profile.manifest_path, profile.manifest_sha256, MAX_MANIFEST_BYTES)
    witness_raw = _read_pinned(root, profile.witness_path, profile.witness_sha256, MAX_WITNESS_BYTES)
    manifest = validate_manifest(profile, manifest_raw)
    game = _read_pinned(root, profile.game_path, profile.game_sha256, MAX_COMPONENT_BYTES)
    config = _read_pinned(root, profile.configuration_path, profile.configuration_sha256, MAX_COMPONENT_BYTES)
    if len(game) != profile.game_bytes or len(config) != profile.configuration_bytes:
        raise ValueError('Retained component length mismatch')
    if game[:4] != b'\x05\x00\x00\x00':
        raise ValueError('Retained Game component version prefix differs')
    try:
        witness = json.loads(witness_raw.decode('utf-8'))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError('Pinned retained Save witness is not bounded JSON') from exc
    if type(witness) is not dict:
        raise ValueError('Pinned retained Save witness root must be an object')
    validate_audit_witness(profile, witness, manifest, root)
    return RetainedMatchedPair(profile, profile.manifest_sha256, profile.witness_sha256, game, config, witness_raw, profile.expected_turn, profile.width, profile.height)

def load_inputs(profile_id: str, root: Path):
    """Read one explicitly registered, reviewed native Save pair."""
    if type(profile_id) is not str or profile_id not in RETAINED_PROFILES:
        raise ValueError('No retained Save profile is currently admitted')
    return load_pair(RETAINED_PROFILES[profile_id], root)

def _verify_pair_binding(pair: RetainedMatchedPair) -> None:
    if type(pair) is not RetainedMatchedPair:
        raise TypeError('A validated retained component pair is required')
    profile = pair.profile
    profile.validate_definition()
    if RETAINED_PROFILES.get(profile.profile_id) is not profile:
        raise ValueError('Retained profile is not in the frozen admission registry')
    if dict(profile.source_proofs) != current_source_proofs(profile_id=profile.profile_id):
        raise ValueError('Retained profile source proof pins no longer match live evidence')
    if type(pair.game) is not bytes or type(pair.configuration) is not bytes or len(pair.game) != profile.game_bytes or (len(pair.configuration) != profile.configuration_bytes) or (type(pair.witness) is not bytes) or (common_pair._sha(pair.witness) != profile.witness_sha256) or (common_pair._sha(pair.game) != profile.game_sha256) or (common_pair._sha(pair.configuration) != profile.configuration_sha256) or (pair.manifest_sha256 != profile.manifest_sha256) or (pair.witness_sha256 != profile.witness_sha256) or ((type(pair.expected_turn), type(pair.width), type(pair.height)) != (int, int, int)) or ((pair.expected_turn, pair.width, pair.height) != (profile.expected_turn, profile.width, profile.height)):
        raise ValueError('Retained matched pair differs from the registered profile pins')

def as_load_inputs(pair: RetainedMatchedPair, matched_inputs_type):
    """Build existing Load input shape only after retained pair admission.

    The production Load validator must separately add an explicit retained118
    branch before this helper can be used there.  This staging helper does not
    mutate or broaden the current production validator.
    """
    _verify_pair_binding(pair)
    if not callable(matched_inputs_type):
        raise TypeError('Existing Load MatchedInputs constructor is required')
    return matched_inputs_type(pair.configuration, pair.game, pair.manifest_sha256, pair.expected_turn, pair.width, pair.height, pair.profile.profile_id)

def read_selected_inputs(profile_id: str, root: Path, matched_inputs_type):
    """Staged analogue of Load's selector; profile registry remains the gate."""
    pair = load_inputs(profile_id, root)
    inputs = as_load_inputs(pair, matched_inputs_type)
    witness = json.loads(pair.witness.decode('utf-8'))
    return (inputs, witness)

def validate_load_binding(inputs, root: Path, matched_inputs_type):
    """Validate the existing Load dataclass against the separately admitted pair."""
    if type(inputs) is not matched_inputs_type:
        raise TypeError('Retained Load requires the existing exact MatchedInputs type')
    profile_id = getattr(inputs, 'profile_name', None)
    pair = load_inputs(profile_id, root)
    expected = as_load_inputs(pair, matched_inputs_type)
    names = ('configuration', 'game', 'manifest_sha256', 'expected_turn', 'expected_width', 'expected_height', 'profile_name')
    for name in names:
        if type(getattr(inputs, name, None)) is not type(getattr(expected, name)):
            raise ValueError('Retained Load input has noncanonical type: ' + name)
        if getattr(inputs, name) != getattr(expected, name):
            raise ValueError('Retained Load input differs from its frozen pair: ' + name)
    return pair

def resume_turn_binding(pair: RetainedMatchedPair) -> dict:
    """Minimal staged Load/resume binding, independent of NewGame round count."""
    _verify_pair_binding(pair)
    if pair.expected_turn not in (118, 121, 150, 182):
        raise ValueError('Retained resume turn is outside the explicitly observed profiles')
    initial_turn = pair.expected_turn
    return {'profile_name': pair.profile.profile_id, 'initial_turn': initial_turn, 'expected_turn_after_one_round': initial_turn + 1, 'width': pair.width, 'height': pair.height, 'input_pair_sha256': pair.manifest_sha256, 'original_input_turn': pair.profile.original_input_turn, 'resumed_rounds_before_save': pair.profile.resumed_rounds, 'eligible_for_training': False}
RETAINED_118 = RetainedProfile(profile_id='retained118', manifest_path='work/native-checkpoints/160e53d442ff438783ca9e2c40a115b5/turn118.checkpoint.json', manifest_sha256='5bca810ba20f9f0a5d12fac80745475dee6d20587d84c6938dddd86832db54f8', witness_path='work/native-retained-save385-audit434-v2c.json', witness_sha256='1d1457fbc3b9fdcbb6bbcd545d5d73f3577f92757359848d5a7eee3c57427ebd', expected_turn=118, width=74, height=46, original_input_turn=115, resumed_rounds=3, transitions=((115, 116), (116, 117), (117, 118)), game_path='work/native-checkpoints/160e53d442ff438783ca9e2c40a115b5/turn118.game.raw', game_bytes=2911000, game_sha256='131a3c7dd76313faec6f5eecfbe9b6dd7cee885ae96002be3e41c37ff8528f66', configuration_path='work/native-checkpoints/160e53d442ff438783ca9e2c40a115b5/turn118.configuration.raw', configuration_bytes=15053, configuration_sha256='a16042d6c91abf620776765daba7506ea648d9dd51e06b360ca69822338e59ed', input_manifest_sha256='1fb0d9fcc3bc9aaf4af07b024b27cad87dece03173f81d0c17663c56dd75caa8', input_game_sha256='595ef6934a7816f77526bb89e23a71d885e52f44995969e7776ae52ee87ff435', input_configuration_sha256='9d6dd5f7c4ca59e95a97b09df342634b20016eccaf5f86d03cb6e0f7ff6cc79b', source_proofs=(('core_sha256', 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'), ('jobs_sha256', '4b035fe2b0dfb0b4be35ae46c24b8b8d42affd95e98f97363e2ef1bebbd855bd'), ('plan_sha256', 'a5a1d99430c0aaf87528740af33bdbd3703058514e6988ade803bcc463df1688'), ('provider_sha256', '3d5ef65d87185b09b2925e2c0f61f7181d993b3f25e2e55cc3fbcc3c08a817a7')))
RETAINED_118.validate_definition()
RETAINED_121 = RetainedProfile(profile_id='retained121', manifest_path='work/native-checkpoints/f02e0cf02f974f7f892b879fc2f07a3d/turn121.checkpoint.json', manifest_sha256='3cf6dc1fc209df008916eb3ba06ee463287a5edd2e1fd077ad91a2b8e5181a19', witness_path='work/native-retained-save-audit390.json', witness_sha256='09243b44b1bdff81b6407939373767b46cc28efc0e6c3a47a5c51fdd1ffa0ef1', expected_turn=121, width=74, height=46, original_input_turn=118, resumed_rounds=3, transitions=((118, 119), (119, 120), (120, 121)), game_path='work/native-checkpoints/f02e0cf02f974f7f892b879fc2f07a3d/turn121.game.raw', game_bytes=2908109, game_sha256='bdc137066391e122bb794355f7e87feb4b97faaa708e92d265caf500382c7c48', configuration_path='work/native-checkpoints/f02e0cf02f974f7f892b879fc2f07a3d/turn121.configuration.raw', configuration_bytes=15053, configuration_sha256='a16042d6c91abf620776765daba7506ea648d9dd51e06b360ca69822338e59ed', input_manifest_sha256='5bca810ba20f9f0a5d12fac80745475dee6d20587d84c6938dddd86832db54f8', input_game_sha256='131a3c7dd76313faec6f5eecfbe9b6dd7cee885ae96002be3e41c37ff8528f66', input_configuration_sha256='a16042d6c91abf620776765daba7506ea648d9dd51e06b360ca69822338e59ed', source_proofs=(('core_sha256', 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'), ('jobs_sha256', '4b035fe2b0dfb0b4be35ae46c24b8b8d42affd95e98f97363e2ef1bebbd855bd'), ('plan_sha256', 'a5a1d99430c0aaf87528740af33bdbd3703058514e6988ade803bcc463df1688'), ('provider_sha256', '3d5ef65d87185b09b2925e2c0f61f7181d993b3f25e2e55cc3fbcc3c08a817a7'), ('retained_save121_profile_plan_sha256', '5c15783c42a52af935d6a5a8002c09bb8cabf5c164096a1698bf629fa19cb12e')), input_profile='retained118')
RETAINED_121.validate_definition()
RETAINED_150 = RetainedProfile(profile_id='retained150', manifest_path='work/native-checkpoints/fe8cb3bc376b4e9b9b8374dfc395e969/turn150.checkpoint.json', manifest_sha256='c8ab1271dd595138ffb58a7f06cb5829f27ee54c4e55fbaac63b88a7124797ff', witness_path='work/native-retained-save150-audit401.json', witness_sha256='c61f6da2e1b9ba0d52249cebf4756f69604c4e996278946a03f2a42d4f26b3bb', expected_turn=150, width=74, height=46, original_input_turn=118, resumed_rounds=32, transitions=tuple(((turn, turn + 1) for turn in range(118, 150))), game_path='work/native-checkpoints/fe8cb3bc376b4e9b9b8374dfc395e969/turn150.game.raw', game_bytes=2967464, game_sha256='5f125f666b28ae19659fc2c70f6dad0b9ecc1963f3b4c09a744014606a78cefe', configuration_path='work/native-checkpoints/fe8cb3bc376b4e9b9b8374dfc395e969/turn150.configuration.raw', configuration_bytes=15053, configuration_sha256='a16042d6c91abf620776765daba7506ea648d9dd51e06b360ca69822338e59ed', input_manifest_sha256='5bca810ba20f9f0a5d12fac80745475dee6d20587d84c6938dddd86832db54f8', input_game_sha256='131a3c7dd76313faec6f5eecfbe9b6dd7cee885ae96002be3e41c37ff8528f66', input_configuration_sha256='a16042d6c91abf620776765daba7506ea648d9dd51e06b360ca69822338e59ed', source_proofs=(('core_sha256', 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'), ('jobs_sha256', '4b035fe2b0dfb0b4be35ae46c24b8b8d42affd95e98f97363e2ef1bebbd855bd'), ('native_checkpoint_retained_save150_plan_sha256', '5f13e25b218b770b89122cf5cacba22d026f7ecc67c22b942af146d641dc2dd6'), ('plan_sha256', 'a5a1d99430c0aaf87528740af33bdbd3703058514e6988ade803bcc463df1688'), ('provider_sha256', '3d5ef65d87185b09b2925e2c0f61f7181d993b3f25e2e55cc3fbcc3c08a817a7')), input_profile='retained118')
RETAINED_150.validate_definition()
RETAINED_182 = RetainedProfile(profile_id='retained182', manifest_path='work/native-checkpoints/963b4a286cdb4ae0af60c03060991916/turn182.checkpoint.json', manifest_sha256='e20934f5d7d37b07ef50b79cff4ef402062d0a0e354b8f6077f13236f6d8a2f9', witness_path='work/native-retained150-save182-audit407.json', witness_sha256='fd04528f19a43e65d444d3951c2f9e5f887740129de998daa053ca9f9462b1a0', expected_turn=182, width=74, height=46, original_input_turn=150, resumed_rounds=32, transitions=tuple(((turn, turn + 1) for turn in range(150, 182))), game_path='work/native-checkpoints/963b4a286cdb4ae0af60c03060991916/turn182.game.raw', game_bytes=2990589, game_sha256='2c661d09156154f308c28bbab6e91d0f69c12280265432bf19631fdb879022d0', configuration_path='work/native-checkpoints/963b4a286cdb4ae0af60c03060991916/turn182.configuration.raw', configuration_bytes=15053, configuration_sha256='a16042d6c91abf620776765daba7506ea648d9dd51e06b360ca69822338e59ed', input_manifest_sha256='c8ab1271dd595138ffb58a7f06cb5829f27ee54c4e55fbaac63b88a7124797ff', input_game_sha256='5f125f666b28ae19659fc2c70f6dad0b9ecc1963f3b4c09a744014606a78cefe', input_configuration_sha256='a16042d6c91abf620776765daba7506ea648d9dd51e06b360ca69822338e59ed', source_proofs=(('core_sha256', 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'), ('jobs_sha256', '4b035fe2b0dfb0b4be35ae46c24b8b8d42affd95e98f97363e2ef1bebbd855bd'), ('native_checkpoint_retained_save182_plan_sha256', 'e076939baed31baea3fa9924f1169650e47bb458045900ef9a674c76e628448f'), ('plan_sha256', 'a5a1d99430c0aaf87528740af33bdbd3703058514e6988ade803bcc463df1688'), ('provider_sha256', '3d5ef65d87185b09b2925e2c0f61f7181d993b3f25e2e55cc3fbcc3c08a817a7')), input_profile='retained150')
RETAINED_182.validate_definition()
RETAINED_PROFILES = MappingProxyType({'retained118': RETAINED_118, 'retained121': RETAINED_121, 'retained150': RETAINED_150, 'retained182': RETAINED_182})
