"""Private XP1 input handoff in the existing capture admission machinery."""
import ast


def change(raw, before, after, count=1):
    if raw.count(before) != count:
        raise ValueError('XP1 input handoff boundary changed: ' + before[:120])
    return raw.replace(before, after)


def parameterize(name, raw):
    if name != 'civ6rl.native_official_bundle':
        return raw
    raw = change(raw,
        'def _remember_prepared_bundle(bundle, input_profile, validator_digests, *, _token=None):',
        'def _remember_prepared_bundle(bundle, input_profile, validator_digests, *, _token=None, _input_only=False):')
    raw = change(raw, "(input_profile in ('single', 'hotseat-four', 'lan'))",
        "(input_profile in ('single', 'hotseat-four', 'lan') or (_input_only is True and input_profile == 'xp1-lan'))")
    raw = change(raw, '    _PREPARED_BUNDLE_ADMISSIONS[bundle] = dict(',
        '''    input_validators = None
    if _input_only:
        from civ6_host.runtime.xp1_bundle_inputs import reader_validator_digests
        require(input_profile == 'xp1-lan', 'Input-only admission requires the exact XP1 family')
        input_validators = reader_validator_digests()
    _PREPARED_BUNDLE_ADMISSIONS[bundle] = dict(input_only=_input_only, input_validators=input_validators, ''')
    raw = change(raw, 'def _reuse_prepared_bundle(bundle, reference, input_profile):',
        'def _reuse_prepared_bundle(bundle, reference, input_profile, *, _input_only=False):')
    raw = change(raw,
        "    expected_profile = {'single': SINGLE_PROFILE, 'hotseat-four': HOTSEAT_FOUR_PROFILE, 'lan': LAN_PROFILE}",
        """    expected_profile = {'single': SINGLE_PROFILE, 'hotseat-four': HOTSEAT_FOUR_PROFILE, 'lan': LAN_PROFILE}
    require(type(_input_only) is bool and admission.get('input_only', False) is _input_only,
            'Prepared bundle input-only scope differs')
    if _input_only:
        from civ6_host.runtime.xp1_bundle_inputs import XP1_LAN_PROFILE, reader_validator_digests
        expected_profile = {'xp1-lan': XP1_LAN_PROFILE}
        require(reader_validator_digests() == admission['input_validators'],
                'XP1 input validator sources changed')""")
    raw = change(raw,
        "    if input_profile == 'xp1-lan':\n        return bundle\n    return _remember_prepared_bundle",
        "    if input_profile == 'xp1-lan':\n        return _remember_prepared_bundle(bundle, input_profile, validator_digests, _token=_PARENT_ADMISSION_TOKEN, _input_only=True)\n    return _remember_prepared_bundle")
    raw = change(raw, 'def validate_inputs(inputs):', 'def validate_inputs(inputs, *, _input_only=False):')
    raw = change(raw,
        '    configuration, maps = _configuration(raw, m, inputs.profile.mode_name)',
        '''    expected_ruleset = 'RULESET_STANDARD'
    if _input_only:
        from civ6_host.runtime.xp1_bundle_inputs import XP1_LAN_PROFILE
        from civ6_host.runtime.xp1_saved_load import REFERENCE
        require(_input_only is True and inputs.profile is XP1_LAN_PROFILE and reference == REFERENCE,
                'Input-only save validation requires the exact XP1 capture')
        expected_ruleset = 'RULESET_EXPANSION_1'
    configuration, maps = _configuration(raw, m, inputs.profile.mode_name, expected_ruleset=expected_ruleset)''')
    raw = change(raw,
        "    require(manifest.get('localization_bootstrap') == bootstrap, 'Localization bootstrap differs from the official captured export')",
        """    if manifest.get('input_profile') == 'xp1-lan':
        from civ6_host.runtime.xp1_saved_load import REFERENCE, validate_private_bootstrap
        require(reference == REFERENCE, 'XP1 private Localization belongs to another capture')
        validate_private_bootstrap(manifest, bootstrap,
            private_root=_resolve_resource_path(Path(manifest['databases']['localization']['path'])).resolve().parent)
    else:
        require(manifest.get('localization_bootstrap') == bootstrap, 'Localization bootstrap differs from the official captured export')""")
    raw = change(raw,
        "(actual.get('localization_bootstrap') == bundle.fixture['localization_bootstrap'])",
        "(validate_private_bootstrap(actual, bundle.fixture['localization_bootstrap'], private_root=_resolve_resource_path(Path(path)).resolve().parent) if bundle.fixture['input_profile'] == 'xp1-lan' else actual.get('localization_bootstrap') == bundle.fixture['localization_bootstrap'])")
    raw = change(raw, 'def validate_fixture(bundle, path):',
        'def validate_fixture(bundle, path):\n    from civ6_host.runtime.xp1_saved_load import validate_private_bootstrap')
    return ast.unparse(ast.parse(raw)) + '\n'


def capture_package(raw):
    raw = change(raw, '                   validation_identity) -> dict:',
        '                   validation_identity, _xp1_candidate=False) -> dict:')
    raw = change(raw, '    if type(input_profile) is not str or input_profile not in CAPTURE_MODES:',
        '''    if type(_xp1_candidate) is not bool:
        raise CapturePackageError('Candidate input flag must be Boolean')
    modes = dict(CAPTURE_MODES)
    if _xp1_candidate:
        from .xp1_saved_load import REFERENCE, validate_candidate_inputs
        if bundle.reference != REFERENCE:
            raise CapturePackageError('Candidate package must name the exact XP1 capture')
        validate_candidate_inputs(inputs, bundle)
        modes = {'xp1-lan': 'LAN'}
    if type(input_profile) is not str or input_profile not in modes:''')
    raw = change(raw, '    expected_mode = CAPTURE_MODES[input_profile]', '    expected_mode = modes[input_profile]')
    raw = change(raw, 'def read_package(reference) -> tuple[dict, Path, dict[str, Path]]:',
        'def read_package(reference, *, _xp1_candidate=False) -> tuple[dict, Path, dict[str, Path]]:')
    raw = change(raw,
        '    if type(profile) is not str or profile not in CAPTURE_MODES or type(turn) is not int or not 1 <= turn <= 100000:',
        '''    if type(_xp1_candidate) is not bool:
        raise CapturePackageError('Candidate input flag must be Boolean')
    modes = dict(CAPTURE_MODES)
    if _xp1_candidate:
        from .xp1_saved_load import REFERENCE
        if (origin['path'], origin['sha256']) != REFERENCE:
            raise CapturePackageError('Candidate package must name the exact XP1 capture')
        modes = {'xp1-lan': 'LAN'}
    if type(profile) is not str or profile not in modes or type(turn) is not int or not 1 <= turn <= 100000:''')
    return raw


def capture_admission(raw):
    raw = change(raw, 'def _load():', 'def _load(*, _xp1_candidate=False):')
    raw = change(raw, '    manifest,folder,files=read_package(reference)',
        '    manifest,folder,files=read_package(reference, _xp1_candidate=_xp1_candidate)')
    raw = change(raw, "    admit_producer(manifest['validation_identity'],validation_identity())",
        """    if _xp1_candidate and manifest['validation_identity'] != validation_identity():
        raise ValueError('XP1 candidate package requires the same exact runtime producer')
    admit_producer(manifest['validation_identity'],validation_identity())""")
    raw = change(raw, 'def try_bundle(reference,*,input_profile):\n    loaded=_load()',
        'def try_bundle(reference,*,input_profile,_xp1_candidate=False):\n    loaded=_load(_xp1_candidate=_xp1_candidate)')
    raw = change(raw, '    profile=profile_for_capture(input_profile)',
        '''    if _xp1_candidate:
        from .xp1_bundle_inputs import XP1_LAN_PROFILE
        if input_profile != 'xp1-lan':raise ValueError('Candidate input family differs')
        profile=XP1_LAN_PROFILE
    else:
        profile=profile_for_capture(input_profile)''')
    raw = change(raw, '    original.validate_inputs(inputs)',
        '    original.validate_inputs(inputs, _input_only=_xp1_candidate)')
    raw = change(raw, '    from .native.native_checkpoint_provider import CORE_SHA256',
        '''    from .native.native_checkpoint_provider import CORE_SHA256
    if _xp1_candidate:
        from .saved_load_profiles import XP1_CORE_SHA256 as CORE_SHA256''')
    raw = change(raw,
        '    return original._remember_prepared_bundle(bundle,input_profile,original._prepared_bundle_validator_digests(),_token=original._PARENT_ADMISSION_TOKEN)',
        '    return original._remember_prepared_bundle(bundle,input_profile,original._prepared_bundle_validator_digests(),_token=original._PARENT_ADMISSION_TOKEN,_input_only=_xp1_candidate)')
    raw = change(raw, 'def try_localization(capture,dependencies,*,reference=None):\n    loaded=_load()',
        '''def try_localization(capture,dependencies,*,reference=None):
    if configured_reference() is None:return None
    from .saved_load_profiles import XP1_CORE_SHA256
    candidate=capture['preflight']['process']['gamecore_module']['sha256']==XP1_CORE_SHA256
    loaded=_load(_xp1_candidate=candidate)''')
    raw = change(raw, 'def consume_prepared_closure(closure,*,environment=None):',
        'def consume_prepared_closure(closure,*,environment=None,_xp1_candidate=False):')
    raw = change(raw, '    loaded=_load();manifest=loaded[1]',
        '    loaded=_load(_xp1_candidate=_xp1_candidate);manifest=loaded[1]')
    return raw


def worker(name, raw):
    if name != 'tools.run_official_postload909':return raw
    raw = change(raw,
        'def open_official_backend(closure, emit, win):',
        """def open_official_backend(closure, emit, win):
    candidate = closure.get('input_profile') in ('xp1-lan','xp2-lan')
    if candidate:
        from civ6_host.runtime.captured_saved_load import select_load_closure
        candidate_contract = select_load_closure(closure)""")
    raw = change(raw,
        '    handoff_receipt = consume_parent_localization_handoff(closure)',
        '''    if candidate:
        from civ6_host.runtime.capture_admission import consume_prepared_closure
        handoff_receipt = consume_prepared_closure(closure, _candidate_profile=candidate_contract.family)
        if handoff_receipt is None:
            raise ValueError('XP1 candidate requires its pinned prepared input closure')
    else:
        handoff_receipt = consume_parent_localization_handoff(closure)''')
    raw = change(raw,
        "    selected = {'hotseat': HOTSEAT_PROFILE, 'single': SINGLE_PROFILE, 'hotseat-four': HOTSEAT_FOUR_PROFILE, 'lan': LAN_PROFILE}[closure['input_profile']]",
        """    if candidate:
        selected = candidate_contract.profile
    else:
        selected = {'hotseat': HOTSEAT_PROFILE, 'single': SINGLE_PROFILE, 'hotseat-four': HOTSEAT_FOUR_PROFILE, 'lan': LAN_PROFILE}[closure['input_profile']]""")
    raw = change(raw, '    proofs = verify_source()',
        '''    if candidate:
        from civ6_host.runtime.captured_saved_load import proofs_for_candidate
        proofs = proofs_for_candidate(candidate_contract.core_sha256)
    else:
        proofs = verify_source()''')
    raw = change(raw,
        "        captured = read_bundle(closure['official_bundle'], input_profile=closure['input_profile'])",
        """        if candidate:
            from civ6_host.runtime.capture_candidates import consume_input_handoff
            captured = consume_input_handoff(candidate_contract.family,closure['prepared_capture'])
            if (closure['official_bundle']['path'], closure['official_bundle']['sha256']) != captured.reference:
                raise ValueError('XP1 worker capture differs from its prepared handoff')
            if closure.get('network_checkpoint') is not None or closure.get('resume_checkpoint') is not None:
                raise ValueError('XP1 candidate does not admit checkpoint resume')
        else:
            captured = read_bundle(closure['official_bundle'], input_profile=closure['input_profile'])""")
    raw = change(raw, "    profile = profile_for_core(dll, mode='init')",
        "    profile = profile_for_core(dll, mode='context' if candidate else 'init')")
    raw = change(raw, '    core = C.WinDLL(str(dll))',
        '''    shared_handle = os.add_dll_directory(str(profile.shared_dependency_directory)) if candidate else None
    core = C.WinDLL(str(dll))''')
    raw = change(raw,
        '    backend = OfficialLoadBackend(core, context, fixture, dll.parent, profile, proofs, emit)',
        '    backend = OfficialLoadBackend(core, context, fixture, profile.shared_dependency_directory, profile, proofs, emit, candidate_bundle=captured if candidate else None)')
    raw = change(raw, '    backend.library_directory_handle = handle',
        '    backend.library_directory_handle = handle\n    backend.shared_library_directory_handle = shared_handle')
    raw = change(raw, '    receipt = run_experiment(backend, inputs)',
        '''    if candidate:
        from civ6_host.runtime.xp1_saved_load_composition import compose_saved_load_services
        receipt = run_experiment(backend, inputs, prepare_services=compose_saved_load_services)
        backend.raw_load_result = receipt
        emit('xp1_candidate_raw_load_observed', postload_completed=False,
             public_session_admitted=False, controlled_process_stop_required=True)
        return backend
    receipt = run_experiment(backend, inputs)''')
    return ast.unparse(ast.parse(raw)) + '\n'
