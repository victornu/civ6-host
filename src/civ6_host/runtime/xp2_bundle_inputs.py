"""Exact Gathering Storm capture inputs; no native Load or public admission.

The shared capture reader verifies the actual final databases and save. This
module adds only the distinct XP2 input contracts, including the nonempty
selected script. Disk bytes and retained list headers are not execution proof.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

from .capture_profiles import CapturedModeProfile
from .gameplay_active_profiles import XP2_CORE_SHA256, expansion_profile


REFERENCE = (
    'work/official-capture/xp2-gs-lan-rows-20261102-04/manifest.json',
    '28cc55ad4c2d56535db8c0a1351445125fd75800ab54eefd3b0b600b41717f1d',
)
XP2_LAN_PROFILE = CapturedModeProfile('xp2-lan-official-capture-inputs', 'LAN')
RULESET = 'RULESET_EXPANSION_2'
SELECTED_PATHS = ('../../../DLC/Expansion2/Scripts/WorldCongress.lua',)
SCRIPT_SHA256 = '26a2eeac85f64a13aed985f9d11ae3ac26c51b6abe50f0e5a89ded63e439c032'
SCRIPT_BYTES = 17340
CONFIGURATION_BYTES = 37135
CONFIGURATION_SHA256 = 'e9f5cf20b75932169b5b1c8bdd800ce349a0cea99c755cc1ab1d099c64eaf116'
GAME_BYTES = 2497280
GAME_SHA256 = '66dd00e4e6f88e2ea2b87318a7b833ebeeed15f545ef050ccf6931f5c24cf3ee'
DATABASE_WITNESS_MAX_BYTES = 16 * 1024 ** 2
RETAINED_LOCALIZATION_SOURCES = (
    'work/official-capture/xp2-gs-lan-rows-20261102-04-invocation/localization-source-snapshot/manifest.json',
    '1315b554c6c30a558d01560a09751d5d52e273b62b897acf1a855b5d1ca276f6',
    12499,
)


def retained_localization_sources():
    from .paths import resource_root
    from .native.native_localization_logical_export import _file
    path, digest, size = RETAINED_LOCALIZATION_SOURCES
    reference = dict(path=str(resource_root() / path), sha256=digest, bytes=size)
    _file(reference, limit=1024 * 1024)
    return reference


def reader_validator_digests():
    from . import capture_profiles, gameplay_active_profiles, capture_script_paths, localization_bulk_export
    from .native import native_official_bundle, native_gameplay_empty
    from .native import official_application_configuration, native_gameplay_source_capture
    from .workers import capture_phase1_bundle994
    modules = (capture_profiles, gameplay_active_profiles, capture_script_paths, localization_bulk_export,
               native_official_bundle, native_gameplay_empty,
               official_application_configuration, native_gameplay_source_capture,
               capture_phase1_bundle994)
    paths = (Path(__file__).resolve(), *(Path(module.__file__).resolve() for module in modules))
    pins = {}
    for path in paths:
        if not path.is_file() or not 0 < path.stat().st_size <= 4 * 1024 ** 2:
            raise ValueError('XP2 input validator source is unavailable or oversized')
        with path.open('rb') as stream:
            raw = stream.read(4 * 1024 ** 2 + 1)
        if not 0 < len(raw) <= 4 * 1024 ** 2:
            raise ValueError('XP2 input validator source exceeds its bound')
        pins[str(path)] = hashlib.sha256(raw).hexdigest()
    return pins


def recheck_reader_validators(expected):
    if type(expected) is not dict or reader_validator_digests() != expected:
        raise ValueError('XP2 input validator sources changed during admission')


def validate_reference(reference):
    if reference != REFERENCE:
        raise ValueError('XP2 inputs require the exact retained official capture')


def validate_process(process):
    from .native.official_application_configuration import EXE_SHA256
    if (type(process) is not dict or process.get('exe_sha256') != EXE_SHA256
            or type(process.get('gamecore_module')) is not dict
            or process['gamecore_module'].get('sha256') != XP2_CORE_SHA256):
        raise ValueError('XP2 input requires the exact source-pinned EXE and GameCore')
    expansion_profile(XP2_CORE_SHA256)
    return XP2_CORE_SHA256


def validate_components(configuration, game):
    for name, raw, size, digest in (
        ('configuration', configuration, CONFIGURATION_BYTES, CONFIGURATION_SHA256),
        ('GameCore stream', game, GAME_BYTES, GAME_SHA256),
    ):
        if type(raw) is not bytes or len(raw) != size or hashlib.sha256(raw).hexdigest() != digest:
            raise ValueError('XP2 captured ' + name + ' differs')


def validate_candidate_inputs(inputs, bundle):
    from .native.native_official_load import OfficialInputs
    from .native.native_official_bundle import PreparedBundle, parse_configuration
    if (type(bundle) is not PreparedBundle or type(inputs) is not OfficialInputs
            or bundle.inputs is not inputs or bundle.reference != REFERENCE
            or inputs.profile is not XP2_LAN_PROFILE or inputs.official_bundle != REFERENCE
            or type(bundle.initial_turn) is not int
            or not 1 <= bundle.initial_turn <= 100000):
        raise ValueError('XP2 candidate requires the exact original captured input pair')
    if inputs.checkpoint is None:
        validate_components(inputs.configuration, inputs.game)
        if bundle.initial_turn != 1:
            raise ValueError('XP2 original capture must retain its original turn')
    else:
        from .xp1_session_checkpoint import validate_resumed_inputs
        validate_resumed_inputs(inputs, bundle)
    _, maps = parse_configuration(inputs.configuration, 'LAN')
    if inputs.map_values != maps:
        raise ValueError('XP2 candidate map configuration differs')
    if (bundle.content_profile['engine']['gamecore_sha256'] != XP2_CORE_SHA256
            or tuple(bundle.expected_readback[k] for k in ('turn', 'width', 'height', 'player_id'))
               != (bundle.initial_turn, 44, 26, 0)):
        raise ValueError('XP2 candidate engine/readback identity differs')
    counts = bundle.content_profile.get('gameplay_scripts')
    if (type(counts) is not dict or counts.get('selected_and_active_empty') is not False
            or any(type(counts.get(k)) is not int or counts[k] != 1 for k in
                   ('selected_path_count', 'active_count', 'source_records', 'source_files'))):
        raise ValueError('XP2 candidate selected script profile differs')
    return XP2_LAN_PROFILE


def prepare_input_handoff(destination, *, bundle=None):
    from .capture_candidates import prepare_input_handoff as prepare
    return prepare('xp2-lan', destination, bundle=bundle)


def consume_input_handoff(reference):
    from .capture_candidates import consume_input_handoff as consume
    return consume('xp2-lan', reference)


def validate_selection_scope(runtime):
    if type(runtime) is not dict:
        raise ValueError('XP2 input requires retained gameplay witnesses')
    selected = runtime.get('gameplay_selection994')
    active = runtime.get('gameplay_active_list')
    embedded = active.get('selection') if type(active) is dict else None
    if any(type(value) is not dict or value.get('consumer_core_matches_base_proof') is not False
           for value in (selected, embedded)):
        raise ValueError('XP2 input must preserve the unsupported Base consumer proof scope')
    for report in (selected, embedded):
        snapshot = report.get('snapshot')
        if (type(snapshot) is not dict or type(snapshot.get('record_count')) is not int
                or snapshot['record_count'] != 1
                or snapshot.get('selected_paths') != list(SELECTED_PATHS)
                or type(snapshot.get('records')) is not list or len(snapshot['records']) != 1):
            raise ValueError('XP2 ordered WorldCongress selection differs')
        row = snapshot['records'][0]
        if (type(row) is not dict or type(row.get('index')) is not int or row['index'] != 0
                or row.get('path') != SELECTED_PATHS[0] or row.get('consumer_skips') is not False):
            raise ValueError('XP2 selected WorldCongress record differs')
    state = active.get('state')
    if (type(state) is not dict or type(state.get('active_count')) is not int
            or state['active_count'] != 1 or state.get('active_list_empty') is not False
            or active.get('selected_and_active_empty') is not False
            or active.get('status') != 'nonempty_profile_unqualified'):
        raise ValueError('XP2 retained active script scope differs')
    # Header/source/process joins and every negative execution claim are also
    # checked by the original stable_capture_identity reader, without a VM call.


def validate_summary_scope(summary):
    if (type(summary) is not dict or summary.get('selected_paths') != list(SELECTED_PATHS)
            or any(summary.get(name) is not False for name in (
                'consumer_core_matches_base_proof', 'content_application_success_proven',
                'gameplay_execution_proven'))):
        raise ValueError('XP2 input summary differs or overclaims execution qualification')
    active = summary.get('gameplay_active_list')
    if (type(active) is not dict or active.get('status') != 'nonempty_profile_unqualified'
            or active.get('selected_and_active_empty') is not False
            or active.get('observed_on_both_sides') is not True
            or active.get('load_completion_proven') is not False
            or active.get('historical_execution_proven') is not False):
        raise ValueError('XP2 summary must retain the nonempty unqualified active list')


def validate_scripts(scripts, folder, process, dependencies):
    """Pin original/copy bytes and the same-process CWD witness, not execution."""
    import time
    from .native.native_official_bundle import _file
    from .native.native_gameplay_source_capture import recheck_selected_sources
    from .resource_resolution import resolve_path
    filename = SCRIPT_SHA256 + '.lua'
    if (type(scripts) is not dict or scripts.get('selected_paths') != list(SELECTED_PATHS)
            or scripts.get('files') != {filename: dict(bytes=SCRIPT_BYTES, sha256=SCRIPT_SHA256)}
            or type(scripts.get('records')) is not list or len(scripts['records']) != 1
            or scripts.get('disk_bytes_only') is not True
            or scripts.get('in_memory_execution_bytes_proven') is not False
            or scripts.get('includes_and_dependencies_captured') is not False
            or scripts.get('training_eligible') is not False):
        raise ValueError('XP2 selected disk source identity or scope differs')
    row = scripts['records'][0]
    state = row.get('source_state') if type(row) is dict else None
    resolution = scripts.get('path_resolution')
    if (type(state) is not dict or state.get('bytes') != SCRIPT_BYTES
            or state.get('sha256') != SCRIPT_SHA256 or row.get('copy') != filename
            or row.get('source_path') != SELECTED_PATHS[0]
            or type(resolution) is not dict or type(resolution.get('context')) is not dict
            or resolution['context'].get('process') != process.get('identity')):
        raise ValueError('XP2 script/CWD witness belongs to another source or process')
    recheck_selected_sources(scripts, folder, deadline=time.monotonic() + 15)
    _file(dict(path=str(resolve_path(Path(folder)) / filename), bytes=SCRIPT_BYTES,
               sha256=SCRIPT_SHA256), dependencies)
    for pin in resolution['dependencies']:
        _file(pin, dependencies, workspace=False, maximum=4 * 1024 ** 2)
