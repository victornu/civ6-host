"""Shared private captured-database binding for expansion Init ownership.

The caller supplies its exact source-selected profile. Registration, canonical
private paths and independent files remain mandatory; this does not admit Load.
"""
from pathlib import Path
from .resource_resolution import resolve_path


def database_input_binding(bundle, host, configuration_path, gameplay_path, private_root, *, family, reference, database_pins, validate_inputs):
    """Join actual callback paths to the unchanged, registered capture owner.

The existing Init validator still hashes the two databases, checks SQLite
headers and verifies all host callback ownership after this metadata selection.
The full bundle fixture validator checked Localization and ICU before any Init.
"""
    from .native.native_official_bundle import _reuse_prepared_bundle
    validate_inputs(getattr(bundle, 'inputs', None), bundle)
    _reuse_prepared_bundle(bundle, reference, family, _input_only=True)
    manifest = getattr(host, 'manifest', None)
    if (type(manifest) is not dict
            or manifest.get('official_bundle') != bundle.fixture['official_bundle']
            or manifest.get('input_profile') != family
            or bundle.content_profile.get('final_databases') != database_pins
            or set(manifest.get('databases', {})) != set(database_pins)):
        raise ValueError('Expansion Init candidate requires its exact captured database manifest')
    raw_root = resolve_path(Path(private_root))
    root = raw_root.resolve(strict=True)
    if not raw_root.is_absolute() or raw_root != root:
        raise ValueError('Expansion Init candidate requires its canonical private directory')
    selected = {}
    for role, pin in database_pins.items():
        expected = bundle.fixture['databases'][role]
        actual = manifest['databases'][role]
        raw_path = resolve_path(Path(actual['path']))
        path = raw_path.resolve(strict=True)
        source = resolve_path(Path(expected['path'])).resolve(strict=True)
        if (any(actual.get(key) != value or expected.get(key) != value for key, value in pin.items())
                or not raw_path.is_absolute() or raw_path != path or raw_path.is_symlink()
                or path.parent != root or not path.is_file() or path.samefile(source)):
            raise ValueError('Expansion Init candidate requires exact independent private database copies')
        selected[role] = dict(path=str(path), **pin)
    paths = (configuration_path, gameplay_path)
    if any(resolve_path(Path(path)).resolve(strict=True) != Path(selected[role]['path'])
           for role, path in zip(('configuration', 'gameplay'), paths)):
        raise ValueError('Expansion Init paths differ from the captured private manifest')
    if len({row['path'] for row in selected.values()}) != len(selected):
        raise ValueError('Expansion Init captured database roles share a file')
    return dict(schema='civ6-host.' + family.removesuffix('-lan') + '-captured-init-inputs.v1',
                origin=dict(path=reference[0], sha256=reference[1]),
                input_profile=family, databases=selected, private_root=str(root),
                historical_diagnostic_fixture_reused=False, public_session_admitted=False)


def validate_init_receipt_binding(bundle, host, receipt, *, family, reference, database_pins, validate_inputs):
    """Validate the actual retained Init receipt without rehashing open databases."""
    if getattr(host, 'context_init_receipt', None) is not receipt:
        raise ValueError('Expansion candidate teardown requires the retained Init receipt owner')
    inputs = receipt.get('inputs')
    if type(inputs) is not dict:
        raise ValueError('Expansion candidate Init input receipt is missing')
    binding = database_input_binding(bundle, host, inputs.get('configuration_path'),
        inputs.get('gameplay_path'), inputs.get('private_root'), family=family, reference=reference, database_pins=database_pins, validate_inputs=validate_inputs)
    if (inputs.get('captured_input_binding') != binding
            or any(inputs.get(role + '_sha256') != database_pins[role]['sha256']
                   for role in ('configuration', 'gameplay'))):
        raise ValueError('Expansion candidate Init receipt differs from its captured database binding')
    return binding


def selected_database_input_binding(bundle, host, configuration_path, gameplay_path, private_root, *, family):
    if family == 'xp1-lan':
        from .xp1_saved_init import database_input_binding as bind
    elif family == 'xp2-lan':
        from .xp2_saved_init import database_input_binding as bind
    else:
        raise ValueError('Unknown captured Init family')
    return bind(bundle, host, configuration_path, gameplay_path, private_root)
