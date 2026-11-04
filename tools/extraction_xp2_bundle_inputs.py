"""Extend the shared raw reader with one explicit, input-only XP2 capture.

Applied after the existing source migrations. Historical code and Base/XP1
guards stay intact; this adds no Load backend, fixture or session admission.
"""
import ast


def change(raw, before, after):
    if raw.count(before) != 1:
        raise ValueError('XP2 input extraction boundary changed: ' + before[:110])
    return raw.replace(before, after)


def parameterize(name, raw):
    if name == 'civ6rl.native_localization_logical_export':
        raw = change(raw,
            'def validate_export_manifest(ref, *, expected_process=None, expected_nonce=None, _with_verified_tables=False):',
            'def validate_export_manifest(ref, *, expected_process=None, expected_nonce=None, _with_verified_tables=False, _retained_sources=None):')
        raw = change(raw, '    bulk_export.validate_sources(report, verified_tables, build)',
            '    bulk_export.validate_sources(report, verified_tables, build, retained_sources=_retained_sources)')
        return ast.unparse(ast.parse(raw)) + '\n'
    if name != 'civ6rl.native_official_bundle':
        return raw
    start = raw.index('\ndef read_bundle(')
    end = raw.index('\ndef prepare_official_bundle(', start)
    body = raw[start:end]
    body = change(body, "if input_profile != 'xp1-lan':", "if input_profile not in ('xp1-lan', 'xp2-lan'):")
    body = change(body, "('single', 'hotseat-four', 'lan', 'xp1-lan')", "('single', 'hotseat-four', 'lan', 'xp1-lan', 'xp2-lan')")
    body = change(body, '        profile = XP1_LAN_PROFILE\n    else:',
        """        profile = XP1_LAN_PROFILE
    elif input_profile == 'xp2-lan':
        from civ6_host.runtime import xp2_bundle_inputs as xp2_inputs
        xp2_validator_digests = xp2_inputs.reader_validator_digests()
        profile = xp2_inputs.XP2_LAN_PROFILE
    else:""")
    body = change(body, '    reference, m = _manifest(reference)',
        """    reference, m = _manifest(reference)
    if input_profile == 'xp2-lan':
        xp2_inputs.validate_reference(reference)""")
    body = change(body, '        expected_core = validate_process(process)',
        """        expected_core = validate_process(process)
    elif input_profile == 'xp2-lan':
        expected_core = xp2_inputs.validate_process(process)""")
    body = change(body, "if input_profile == 'xp1-lan' else _localization(m, dependencies, cache_key=reference)",
        "if input_profile in ('xp1-lan', 'xp2-lan') else _localization(m, dependencies, cache_key=reference)")
    body = change(body,
        "    localization, bootstrap = _localization_uncached(m, dependencies) if input_profile in ('xp1-lan', 'xp2-lan') else _localization(m, dependencies, cache_key=reference)",
        """    if input_profile == 'xp2-lan':
        localization, bootstrap = _localization_uncached(m, dependencies,
            _retained_sources=xp2_inputs.retained_localization_sources())
    else:
        localization, bootstrap = _localization_uncached(m, dependencies) if input_profile == 'xp1-lan' else _localization(m, dependencies, cache_key=reference)""")
    body = change(body, "expected_ruleset='RULESET_EXPANSION_1' if input_profile == 'xp1-lan' else 'RULESET_STANDARD'",
        "expected_ruleset={'xp1-lan': 'RULESET_EXPANSION_1', 'xp2-lan': 'RULESET_EXPANSION_2'}.get(input_profile, 'RULESET_STANDARD')")
    body = change(body, "    if input_profile == 'xp1-lan':\n        from civ6_host.runtime.gameplay_active_profiles import SOURCE as EMPTY_SOURCE",
        "    if input_profile in ('xp1-lan', 'xp2-lan'):\n        from civ6_host.runtime.gameplay_active_profiles import SOURCE as EMPTY_SOURCE")
    body = change(body, '    game = games[0].payload',
        "    game = games[0].payload\n    if input_profile == 'xp2-lan':\n        xp2_inputs.validate_components(configuration, game)")
    body = change(body, '            validate_selection_scope(r)\n        else:',
        "            validate_selection_scope(r)\n        elif input_profile == 'xp2-lan':\n            xp2_inputs.validate_selection_scope(r)\n        else:")
    body = change(body,
        "        require(_selection_semantics(active['selection'], process, content) == selection and active.get('selected_and_active_empty') is True and (selection['selected_paths'] == []), 'Nonempty gameplay selection/activation/includes are not yet supported by this Load adapter')",
        """        if input_profile == 'xp2-lan':
            require(_selection_semantics(active['selection'], process, content) == selection,
                    'XP2 selected and retained active script witnesses differ')
        else:
            require(_selection_semantics(active['selection'], process, content) == selection and active.get('selected_and_active_empty') is True and (selection['selected_paths'] == []), 'Nonempty gameplay selection/activation/includes are not yet supported by this Load adapter')""")
    body = change(body, "    require(runtime[0] == runtime[1] and m['runtime_selections']['selected_paths'] == [], 'Captured script state changed around save')",
        """    expected_paths = list(xp2_inputs.SELECTED_PATHS) if input_profile == 'xp2-lan' else []
    require(runtime[0] == runtime[1] and m['runtime_selections']['selected_paths'] == expected_paths, 'Captured script state changed around save')""")
    body = change(body, "        validate_summary_scope(m['runtime_selections'])",
        "        validate_summary_scope(m['runtime_selections'])\n    elif input_profile == 'xp2-lan':\n        xp2_inputs.validate_summary_scope(m['runtime_selections'])")
    body = change(body,
        "    require(scripts['selected_paths'] == scripts['records'] == [] and scripts['files'] == {}, 'Captured gameplay source list is not the observed empty list')\n    recheck_selected_sources(scripts, _resolve_resource_path(Path(script_ref['path'])).parent, deadline=time.monotonic() + 15)",
        """    if input_profile == 'xp2-lan':
        xp2_inputs.validate_scripts(scripts, _resolve_resource_path(Path(script_ref['path'])).parent, process, dependencies)
    else:
        require(scripts['selected_paths'] == scripts['records'] == [] and scripts['files'] == {}, 'Captured gameplay source list is not the observed empty list')
        recheck_selected_sources(scripts, _resolve_resource_path(Path(script_ref['path'])).parent, deadline=time.monotonic() + 15)""")
    body = change(body, '            witness_limit = DATABASE_WITNESS_MAX_BYTES',
        "            witness_limit = DATABASE_WITNESS_MAX_BYTES\n        elif input_profile == 'xp2-lan':\n            witness_limit = xp2_inputs.DATABASE_WITNESS_MAX_BYTES")
    body = change(body, '        dependencies.update(xp1_validator_digests)',
        "        dependencies.update(xp1_validator_digests)\n    elif input_profile == 'xp2-lan':\n        xp2_inputs.recheck_reader_validators(xp2_validator_digests)\n        dependencies.update(xp2_validator_digests)")
    body = change(body,
        "    if input_profile == 'xp1-lan':\n        return _remember_prepared_bundle(bundle, input_profile, validator_digests, _token=_PARENT_ADMISSION_TOKEN, _input_only=True)",
        "    if input_profile in ('xp1-lan', 'xp2-lan'):\n        return _remember_prepared_bundle(bundle, input_profile, validator_digests, _token=_PARENT_ADMISSION_TOKEN, _input_only=True)")
    raw = raw[:start] + body + raw[end:]
    raw = change(raw,
        "(_input_only is True and input_profile == 'xp1-lan')",
        "(_input_only is True and input_profile in ('xp1-lan', 'xp2-lan'))")
    raw = change(raw,
        "        from civ6_host.runtime.xp1_bundle_inputs import reader_validator_digests\n        require(input_profile == 'xp1-lan', 'Input-only admission requires the exact XP1 family')\n        input_validators = reader_validator_digests()",
        """        if input_profile == 'xp1-lan':
            from civ6_host.runtime.xp1_bundle_inputs import reader_validator_digests
        elif input_profile == 'xp2-lan':
            from civ6_host.runtime.xp2_bundle_inputs import reader_validator_digests
        else:
            raise ValueError('Input-only admission requires an explicit expansion family')
        input_validators = reader_validator_digests()""")
    raw = change(raw,
        "        from civ6_host.runtime.xp1_bundle_inputs import XP1_LAN_PROFILE, reader_validator_digests\n        expected_profile = {'xp1-lan': XP1_LAN_PROFILE}\n        require(reader_validator_digests() == admission['input_validators'], 'XP1 input validator sources changed')",
        """        if input_profile == 'xp1-lan':
            from civ6_host.runtime.xp1_bundle_inputs import XP1_LAN_PROFILE, reader_validator_digests
            expected_profile = {'xp1-lan': XP1_LAN_PROFILE}
        elif input_profile == 'xp2-lan':
            from civ6_host.runtime.xp2_bundle_inputs import XP2_LAN_PROFILE, reader_validator_digests
            expected_profile = {'xp2-lan': XP2_LAN_PROFILE}
        else:
            raise ValueError('Input-only reuse requires an explicit expansion family')
        require(reader_validator_digests() == admission['input_validators'], 'Expansion input validator sources changed')""")
    raw = change(raw,
        "    require(input_profile != 'xp1-lan', 'XP1 inputs do not admit official fixture preparation or native Load')",
        "    require(input_profile not in ('xp1-lan', 'xp2-lan'), 'Expansion inputs do not admit official fixture preparation or native Load')")
    raw = change(raw, 'def _localization_uncached(manifest, dependencies):',
        'def _localization_uncached(manifest, dependencies, *, _retained_sources=None):')
    raw = change(raw, "            validation_options['_with_verified_tables'] = True",
        "            validation_options['_with_verified_tables'] = True\n            if _retained_sources is not None:\n                validation_options['_retained_sources'] = _retained_sources")
    raw = change(raw,
        'def _logical_dependency_references_from_validated(logical, reference, report, verified_tables=None):',
        'def _logical_dependency_references_from_validated(logical, reference, report, verified_tables=None, *, retained_sources=None):')
    raw = change(raw, '    refs += bulk_export.extra_dependencies(report)',
        '    refs += bulk_export.extra_dependencies(report, retained_sources=retained_sources)')
    raw = change(raw,
        '_logical_dependency_references_from_validated(logical, reference, result, verified_tables)',
        '_logical_dependency_references_from_validated(logical, reference, result, verified_tables, retained_sources=_retained_sources)')
    raw = change(raw,
        "        from civ6_host.runtime.xp1_bundle_inputs import XP1_LAN_PROFILE\n        from civ6_host.runtime.xp1_saved_load import REFERENCE\n        require(_input_only is True and inputs.profile is XP1_LAN_PROFILE and (reference == REFERENCE), 'Input-only save validation requires the exact XP1 capture')\n        expected_ruleset = 'RULESET_EXPANSION_1'",
        """        from civ6_host.runtime.xp1_bundle_inputs import XP1_LAN_PROFILE
        from civ6_host.runtime.xp1_saved_load import REFERENCE
        from civ6_host.runtime import xp2_bundle_inputs as xp2_inputs
        require(_input_only is True, 'Input-only save validation flag must be Boolean')
        if inputs.profile is xp2_inputs.XP2_LAN_PROFILE:
            xp2_inputs.validate_reference(reference)
            xp2_inputs.validate_components(inputs.configuration, inputs.game)
            require(inputs.checkpoint is None, 'XP2 candidate checkpoints are not yet admitted')
            expected_ruleset = 'RULESET_EXPANSION_2'
        else:
            require(inputs.profile is XP1_LAN_PROFILE and reference == REFERENCE,
                    'Input-only save validation requires an exact admitted private capture')
            expected_ruleset = 'RULESET_EXPANSION_1'""")
    raw = change(raw,
        "    if manifest.get('input_profile') == 'xp1-lan':\n        from civ6_host.runtime.xp1_saved_load import REFERENCE, validate_private_bootstrap\n        require(reference == REFERENCE, 'XP1 private Localization belongs to another capture')",
        """    if manifest.get('input_profile') in ('xp1-lan', 'xp2-lan'):
        from civ6_host.runtime.xp1_saved_load import REFERENCE, validate_private_bootstrap
        if manifest['input_profile'] == 'xp2-lan':
            from civ6_host.runtime.xp2_bundle_inputs import REFERENCE
        require(reference == REFERENCE, 'Private Localization belongs to another expansion capture')""")
    raw = change(raw,
        "if bundle.fixture['input_profile'] == 'xp1-lan' else actual.get('localization_bootstrap')",
        "if bundle.fixture['input_profile'] in ('xp1-lan', 'xp2-lan') else actual.get('localization_bootstrap')")
    return ast.unparse(ast.parse(raw)) + '\n'
