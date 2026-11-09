"""Hidden official-save diagnostics, with explicit optional action/turn probes."""
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
from pathlib import Path
from datetime import datetime
from datetime import timezone
import ctypes as C
import hashlib
import json
import os
import subprocess
import sys
import threading
import time
import uuid
ROOT = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('tools/run_official_postload909.py')))).resolve().parents[1]
HOST = ROOT / 'work/native-script-services-host41/civ6rl-native-python.exe'
HOST_SHA = '2b938551555af92ef37bbda8631d0a90c585c3e89c9d7710d0758e85e2b01334'
CACHE_MANIFEST = ROOT / 'work/phase23-native-fixture02/manifest.json'
CACHE_MANIFEST_SHA = 'c0158df8759f234dc36857f61b6d3a0a7d805b2d34c14533425c17a682b6783d'

def sha(data):
    return hashlib.sha256(data).hexdigest()

def open_official_backend(closure, emit, win):
    candidate = closure.get('input_profile') in ('xp1-lan', 'xp2-lan')
    execution_image = None
    if 'execution_image' in closure:
        if closure.get('input_profile') != 'xp2-lan':
            raise ValueError('Execution image compatibility requires the explicit XP2 owner')
        from civ6_host.runtime.execution_images import from_identity
        execution_image = from_identity(closure['execution_image'])
    if candidate:
        from civ6_host.runtime.captured_saved_load import select_load_closure
        candidate_contract = select_load_closure(closure)
    from civ6_host.runtime.capture_profiles import LAN_PROFILE
    from civ6_host.runtime.resource_resolution import validate_closure
    validate_closure(closure)
    'Shared native Load path; retain the DLL-directory handle on its owner.'
    open_started = time.perf_counter()
    from civ6_host.runtime.native.native_official_load import OfficialLoadBackend
    from civ6_host.runtime.native.native_official_load import read_inputs
    from civ6_host.runtime.native.native_official_load import run_experiment
    from civ6_host.runtime.native.native_official_load import HOTSEAT_PROFILE
    from civ6_host.runtime.native.native_official_load import SINGLE_PROFILE
    from civ6_host.runtime.native.native_official_load import HOTSEAT_FOUR_PROFILE
    from civ6_host.runtime.native.native_checkpoint_load import verify_source
    from civ6_host.runtime.native.native_core_context_profiles import profile_for_core
    from civ6_host.runtime.native.native_core_context_profiles import validate_loaded_modules
    from civ6_host.runtime.native.native_host import validate_fixture
    phase_started = time.perf_counter()
    for name, digest in closure['pins'].items():
        with _resolve_resource_path(ROOT / name).open('rb') as stream:
            actual = hashlib.file_digest(stream, 'sha256').hexdigest()
        if actual != digest:
            raise ValueError('Worker source/input changed: ' + name)
    from civ6_host.runtime.native.native_official_bundle import consume_parent_localization_handoff
    if candidate:
        from civ6_host.runtime.capture_admission import consume_prepared_closure
        handoff_receipt = consume_prepared_closure(closure, _candidate_profile=candidate_contract.family)
        if handoff_receipt is None:
            raise ValueError('XP1 candidate requires its pinned prepared input closure')
    else:
        handoff_receipt = consume_parent_localization_handoff(closure)
    if handoff_receipt is not None:
        emit('official_parent_localization_validation', **handoff_receipt)
    if candidate:
        selected = candidate_contract.profile
    else:
        selected = {'hotseat': HOTSEAT_PROFILE, 'single': SINGLE_PROFILE, 'hotseat-four': HOTSEAT_FOUR_PROFILE, 'lan': LAN_PROFILE}[closure['input_profile']]
    emit('official_saved_database_profile', profile=closure.get('database_profile', 'reconstructed-base04'), official_save_database_binding_proven=False, gameplay_script_activation_proven=False, strategic_training_ready=False)
    if candidate:
        from civ6_host.runtime.captured_saved_load import proofs_for_candidate
        proofs = proofs_for_candidate(candidate_contract.core_sha256)
    else:
        proofs = verify_source()
    captured = None
    if closure.get('official_bundle') is not None:
        from civ6_host.runtime.native.native_official_bundle import read_bundle
        from civ6_host.runtime.native.native_official_bundle import validate_fixture as validate_bundle_fixture
        from civ6_host.runtime.captured_saved_load import validate_closure_profile
        if not (candidate and closure.get('network_checkpoint') is not None):
            validate_closure_profile(closure)
        if candidate:
            from civ6_host.runtime.capture_candidates import consume_input_handoff
            captured = consume_input_handoff(candidate_contract.family, closure['prepared_capture'],
                official_bundle=candidate_contract.reference,
                **({'execution_image': execution_image} if execution_image is not None else {}))
            if (closure['official_bundle']['path'], closure['official_bundle']['sha256']) != captured.reference:
                raise ValueError('XP1 worker capture differs from its prepared handoff')
            if closure.get('resume_checkpoint') is not None:
                raise ValueError('XP1 cannot inherit a historical Base checkpoint')
        else:
            captured = read_bundle(closure['official_bundle'], input_profile=closure['input_profile'])
        if closure.get('network_checkpoint') is not None:
            from civ6_host.runtime.network_checkpoint import resume_bundle
            captured = resume_bundle(captured, closure)
        if captured.initial_turn != closure['initial_turn']:
            raise ValueError('Worker initial turn differs from captured bundle')
        inputs = captured.inputs
        validate_bundle_fixture(captured, _resolve_resource_path(Path(closure['fixture'])))
    else:
        if closure.get('database_profile') == 'official-captured-bundle-diagnostic':
            raise ValueError('Captured database profile requires its explicit official bundle')
        inputs = read_inputs(selected)
    if closure.get('resume_checkpoint') is not None:
        from civ6_host.runtime.native.native_session_resume import read_inputs as read_checkpoint
        from civ6_host.runtime.native.native_session_resume import validate_fixture as validate_checkpoint_fixture
        inputs = read_checkpoint(closure['resume_checkpoint'])
        if selected is not SINGLE_PROFILE:
            raise ValueError('Checkpoint profile differs from the selected Single owner')
        validate_checkpoint_fixture(inputs.checkpoint, _resolve_resource_path(Path(closure['fixture'])))
    dll = captured.engine_path if captured is not None else _resolve_resource_path(Path(proofs['provider']['images']['core']['path']))
    fixture = _resolve_resource_path(Path(closure['fixture']))
    manifest = validate_fixture(fixture)
    if any((_resolve_resource_path(_resolve_resource_path(Path(row['path']))).resolve().parent != fixture.parent for row in manifest['databases'].values())):
        raise ValueError('Every database must be private to the process')
    emit('native_reset_timing', phase='child_source_and_fixture_verification_seconds', elapsed_seconds=time.perf_counter() - phase_started, timing_scope='non-overlapping stage', strategic_training_ready=False)
    phase_started = time.perf_counter()
    profile = profile_for_core(dll, mode='context' if candidate else 'init',
        **({'execution_image': execution_image} if execution_image is not None else {}))
    if execution_image is not None:
        from civ6_host.runtime.native.native_core_context_profiles import require_executable_profile
        from civ6_host.runtime.execution_images import identity
        require_executable_profile(profile)
        emit('native_execution_image_selected', execution_image=identity(execution_image),
            capture_engine_sha256=captured.content_profile['engine']['gamecore_sha256'],
            historical_capture_rewritten=False, native_library_loaded=False)
    handle = os.add_dll_directory(str(dll.parent))
    shared_handle = os.add_dll_directory(str(profile.shared_dependency_directory)) if candidate else None
    core = C.WinDLL(str(dll))
    if execution_image is not None:
        core._civ6_host_execution_image = execution_image
    loaded_modules = validate_loaded_modules(profile, win.modules())
    if execution_image is not None:
        emit('native_execution_modules_verified', execution_image=identity(execution_image),
            modules=loaded_modules, native_library_loaded=True, context_created=False)
    create = core.DllCreateGameContext
    create.argtypes, create.restype = ([], C.c_void_p)
    if C.cast(create, C.c_void_p).value != core._handle + profile.create_context_rva:
        raise ValueError('Factory address differs')
    context = create()
    if not context:
        raise RuntimeError('Factory returned null')
    backend = OfficialLoadBackend(core, context, fixture, profile.shared_dependency_directory, profile, proofs, emit, candidate_bundle=captured if candidate else None)
    command_profile_diagnostic = closure.get('command_profile_diagnostic', False)
    if (type(command_profile_diagnostic) is not bool
            or command_profile_diagnostic and (
                not candidate or candidate_contract.family != 'xp2-lan'
                or execution_image is None
                or profile.execution_image is not execution_image)):
        raise ValueError('Native Load profiling requires the explicit XP2 execution image')
    backend.command_profile_diagnostic = command_profile_diagnostic
    if captured is not None:
        backend.captured_bundle = captured
    backend.library_directory_handle = handle
    backend.shared_library_directory_handle = shared_handle
    emit('native_reset_timing', phase='dll_load_and_context_creation_seconds', elapsed_seconds=time.perf_counter() - phase_started, timing_scope='non-overlapping stage', strategic_training_ready=False)
    phase_started = time.perf_counter()
    if candidate:
        from civ6_host.runtime.captured_saved_load import configure_requested
        configure_requested(backend, closure)
        from civ6_host.runtime.xp1_saved_load_composition import compose_saved_load_services
        receipt = run_experiment(backend, inputs, prepare_services=compose_saved_load_services)
        backend.raw_load_result = receipt
        emit('xp1_candidate_raw_load_observed', postload_completed=False, public_session_admitted=False, controlled_process_stop_required=True)
        return backend
    receipt = run_experiment(backend, inputs)
    from civ6_host.runtime.native.native_official_postload import run_postload
    run_postload(backend, receipt)
    if captured is not None:
        from civ6_host.runtime.native.native_official_bundle import verify_loaded_script_state
        verify_loaded_script_state(backend)
    emit('native_reset_timing', phase='official_load_and_postload_inclusive_seconds', elapsed_seconds=time.perf_counter() - phase_started, timing_scope='inclusive; contains run_experiment phase events', strategic_training_ready=False)
    emit('native_reset_timing', phase='open_official_backend_total_seconds', elapsed_seconds=time.perf_counter() - open_started, timing_scope='inclusive; contains verification, DLL/context, and load events', strategic_training_ready=False)
    return backend
