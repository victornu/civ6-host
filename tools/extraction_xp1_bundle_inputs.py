"""Reproducible input-only XP1 changes after native path/import rewriting."""

CHANGES = (
    ("        pin = db_witness[name]\n        _file(pin, dependencies, maximum=4 * 1024 ** 2)",
     "        pin = db_witness[name]\n        witness_limit = 4 * 1024 ** 2\n        if input_profile == 'xp1-lan':\n            from civ6_host.runtime.xp1_bundle_inputs import DATABASE_WITNESS_MAX_BYTES\n            witness_limit = DATABASE_WITNESS_MAX_BYTES\n        _file(pin, dependencies, maximum=witness_limit)"),
    ('def _configuration(raw, manifest, mode):',
     'def _configuration(raw, manifest, mode, *, expected_ruleset=\'RULESET_STANDARD\'):'),
    ('    require(receipt[\'content_declaration\'][\'declared_ruleset\'] == \'RULESET_STANDARD\', \'Captured ruleset is outside the current Base Load adapter\')',
     '    require(receipt[\'content_declaration\'][\'declared_ruleset\'] == expected_ruleset, \'Captured ruleset differs from the selected official capture input family\')'),
    ('    from civ6_host.runtime.capture_admission import try_bundle\n    prepared = try_bundle(reference, input_profile=input_profile)\n    if prepared is not None:\n        return prepared',
     '    if input_profile != \'xp1-lan\':\n        from civ6_host.runtime.capture_admission import try_bundle\n        prepared = try_bundle(reference, input_profile=input_profile)\n        if prepared is not None:\n            return prepared'),
    ('    require(input_profile in (\'single\', \'hotseat-four\', \'lan\'), \'Unsupported Base official capture input family\')\n    profile = profile_for_capture(input_profile)',
     '    require(input_profile in (\'single\', \'hotseat-four\', \'lan\', \'xp1-lan\'), \'Unsupported official capture input family\')\n    if input_profile == \'xp1-lan\':\n        from civ6_host.runtime.xp1_bundle_inputs import XP1_LAN_PROFILE\n        from civ6_host.runtime.xp1_bundle_inputs import reader_validator_digests, recheck_reader_validators\n        xp1_validator_digests = reader_validator_digests()\n        profile = XP1_LAN_PROFILE\n    else:\n        profile = profile_for_capture(input_profile)'),
    ('    require(process[\'gamecore_module\'][\'sha256\'] == CORE_SHA256, \'Captured engine is not the supported Base GameCore; XP1/XP2 Load is not admitted\')\n    engine = _resolve_resource_path(_resolve_resource_path(Path(process[\'gamecore_module\'][\'path\']))).resolve()\n    require(_resolve_resource_path(engine).is_file() and sha(_resolve_resource_path(engine).read_bytes()) == CORE_SHA256, \'Captured engine bytes are unavailable or changed\')\n    dependencies[str(engine)] = CORE_SHA256',
     '    expected_core = CORE_SHA256\n    if input_profile == \'xp1-lan\':\n        from civ6_host.runtime.xp1_bundle_inputs import validate_process\n        expected_core = validate_process(process)\n    require(process[\'gamecore_module\'][\'sha256\'] == expected_core, \'Captured engine differs from the selected official capture input family\')\n    engine = _resolve_resource_path(_resolve_resource_path(Path(process[\'gamecore_module\'][\'path\']))).resolve()\n    require(_resolve_resource_path(engine).is_file() and sha(_resolve_resource_path(engine).read_bytes()) == expected_core, \'Captured engine bytes are unavailable or changed\')\n    dependencies[str(engine)] = expected_core'),
    ('    localization, bootstrap = _localization(m, dependencies, cache_key=reference)',
     '    localization, bootstrap = _localization_uncached(m, dependencies) if input_profile == \'xp1-lan\' else _localization(m, dependencies, cache_key=reference)'),
    ('    configuration, maps = _configuration(raw, m, profile.mode_name)',
     '    configuration, maps = _configuration(raw, m, profile.mode_name, expected_ruleset=\'RULESET_EXPANSION_1\' if input_profile == \'xp1-lan\' else \'RULESET_STANDARD\')'),
    ('    from civ6_host.runtime.native.native_gameplay_empty import SOURCE_PATH as EMPTY_PATH\n    from civ6_host.runtime.native.native_gameplay_empty import SOURCE_SHA256 as EMPTY_SHA\n    dependencies[str(EMPTY_PATH)] = EMPTY_SHA',
     '    if input_profile == \'xp1-lan\':\n        from civ6_host.runtime.gameplay_active_profiles import SOURCE as EMPTY_SOURCE\n        dependencies[str(ROOT / EMPTY_SOURCE[0])] = EMPTY_SOURCE[1]\n    else:\n        from civ6_host.runtime.native.native_gameplay_empty import SOURCE_PATH as EMPTY_PATH\n        from civ6_host.runtime.native.native_gameplay_empty import SOURCE_SHA256 as EMPTY_SHA\n        dependencies[str(EMPTY_PATH)] = EMPTY_SHA'),
    ('        require(r[\'gameplay_selection994\'][\'consumer_core_matches_base_proof\'] is True, \'Gameplay consumer does not match the supported Base source\')',
     '        if input_profile == \'xp1-lan\':\n            from civ6_host.runtime.xp1_bundle_inputs import validate_selection_scope\n            validate_selection_scope(r)\n        else:\n            require(r[\'gameplay_selection994\'][\'consumer_core_matches_base_proof\'] is True, \'Gameplay consumer does not match the supported Base source\')'),
    ('    require(runtime[0] == runtime[1] and m[\'runtime_selections\'][\'selected_paths\'] == [], \'Captured script state changed around save\')',
     '    require(runtime[0] == runtime[1] and m[\'runtime_selections\'][\'selected_paths\'] == [], \'Captured script state changed around save\')\n    if input_profile == \'xp1-lan\':\n        from civ6_host.runtime.xp1_bundle_inputs import validate_summary_scope\n        validate_summary_scope(m[\'runtime_selections\'])'),
    ('    require(_prepared_bundle_validator_digests() == validator_digests, \'Prepared bundle validator sources changed during admission\')',
     '    require(_prepared_bundle_validator_digests() == validator_digests, \'Prepared bundle validator sources changed during admission\')\n    if input_profile == \'xp1-lan\':\n        recheck_reader_validators(xp1_validator_digests)\n        dependencies.update(xp1_validator_digests)'),
    ('    return _remember_prepared_bundle(bundle, input_profile, validator_digests, _token=_PARENT_ADMISSION_TOKEN)',
     '    if input_profile == \'xp1-lan\':\n        return bundle\n    return _remember_prepared_bundle(bundle, input_profile, validator_digests, _token=_PARENT_ADMISSION_TOKEN)'),
    ('def prepare_official_bundle(reference, *, input_profile, output_directory, _admitted_bundle=None):',
     'def prepare_official_bundle(reference, *, input_profile, output_directory, _admitted_bundle=None):\n    require(input_profile != \'xp1-lan\', \'XP1 inputs do not admit official fixture preparation or native Load\')'),
)


def qualify_inputs(raw):
    for before, after in CHANGES:
        if raw.count(before) != 1:
            raise ValueError('XP1 input extraction boundary changed: ' + before[:100])
        raw = raw.replace(before, after)
    return raw
