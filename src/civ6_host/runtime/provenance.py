"""Separate historical proof inputs from the code actually executed.

Old receipts refer to original source bytes. They remain read-only evidence in
the private resource root. Installed code has its own source map and closure
pins; historical source identity must never be presented as executed-code identity.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path, PureWindowsPath

from .paths import resource_root

_RUNTIME = Path(__file__).resolve().parent
_PACKAGE = _RUNTIME.parent
_MAP_BYTES = None
_MAP_VALUE = None
_HISTORICAL_PINS = None


def _mapping():
    global _MAP_BYTES, _MAP_VALUE, _HISTORICAL_PINS
    if _MAP_VALUE is not None:return _MAP_VALUE
    raw=(_RUNTIME/'source-map.json').read_bytes()
    value=json.loads(raw)
    if value.get('schema')!='civ6-host.runtime-extraction.v1':
        raise RuntimeError('Unknown extracted runtime source map')
    pins = {}
    for row in value['sources']:
        path, digest = row['source'], row['source_sha256']
        if pins.setdefault(path, digest) != digest:
            raise ValueError('Conflicting historical source identities: '+path)
    _HISTORICAL_PINS = pins
    _MAP_BYTES=raw
    _MAP_VALUE=value
    return _MAP_VALUE


def historical_source_file(relative):
    """Return a named historical source *as proof data*, never as an import path."""
    _mapping()
    if relative not in _HISTORICAL_PINS:
        raise ValueError('Historical source is outside the extracted source map')
    root = resource_root()
    expected = root / relative
    path = expected.resolve()
    if path != expected or not path.is_relative_to(root) or not path.is_file():
        raise ValueError('Historical source proof is missing or redirected')
    with path.open('rb') as stream:
        if hashlib.file_digest(stream, 'sha256').hexdigest() != _HISTORICAL_PINS[relative]:
            raise ValueError('Historical source proof changed: '+relative)
    return str(path)


def historical_module_file(module):
    for row in _mapping()['sources']:
        if row['module']==module.__name__:
            return historical_source_file(row['source'])
    # Four contracts were extracted in the preceding delivery, outside this
    # runtime graph. Their historical pin is needed by legacy receipts only.
    prefix='civ6_host.contracts.'
    if module.__name__.startswith(prefix):
        path=resource_root()/'civ6rl/learning'/(module.__name__[len(prefix):]+'.py')
        if not path.is_file():raise ValueError('Historical public contract is missing')
        return str(path)
    return module.__file__


def worker_path(name):
    if name not in ('official_hotseat_worker923.py','official_action_worker920.py','network_worker.py'):
        raise ValueError('Only explicit-choice installed workers are supported')
    path=_RUNTIME/'workers'/name
    if not path.is_file():raise ValueError('Installed native worker is missing')
    return path


def installed_host_source_reference(reference):
    """Recognize exact host-source rows in historical turn proofs."""
    recorded = PureWindowsPath(reference)
    suffix = ('src', 'civ6_host', 'runtime', 'native')
    if (recorded.is_absolute() and recorded.parts[-5:-1] == suffix
            and recorded.name in ('native_host.py', 'native_host_thread_gate.py')):
        return _RUNTIME / 'native' / recorded.name
    return None


def pin_key(path):
    path=Path(path).resolve()
    if path.is_relative_to(resource_root()):return str(path.relative_to(resource_root()))
    if path.is_relative_to(_PACKAGE):return str(path)
    raise ValueError('Pin lies outside private resources and installed host package')


def installed_source_pins():
    paths=list(_PACKAGE.rglob('*.py'))+[_RUNTIME/'source-map.json']
    return {str(p.resolve()):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}


def _audit_historical_by_default():
    from .resource_resolution import configured_reference
    if configured_reference() is None:
        return True
    from .capture_admission import _COMPATIBLE_PRODUCERS, configured_reference as configured_capture
    capture = configured_capture()
    if capture is None:
        return True
    # The retained XP2 package has a fixed identity. Its full input admission
    # and per-source checks still run in the parent and worker.
    return not any(row.get('private_input_profile') == 'xp2-lan'
                   and row.get('package_sha256') == capture['sha256']
                   for row in _COMPATIBLE_PRODUCERS.values())


def verify_installation(*, audit_historical=None):
    """Verify installed code and optionally audit the complete source archive."""
    if audit_historical is None:
        audit_historical = _audit_historical_by_default()
    if type(audit_historical) is not bool:
        raise ValueError('Historical archive audit selection must be Boolean')
    mapping=_mapping()
    if (_RUNTIME/'source-map.json').read_bytes()!=_MAP_BYTES:
        raise RuntimeError('Runtime source map changed in this process; restart required')
    installed = installed_source_pins()
    if installed.get(str((_RUNTIME/'source-map.json').resolve())) != hashlib.sha256(_MAP_BYTES).hexdigest():
        raise RuntimeError('Runtime source map changed in this process; restart required')
    for row in mapping['sources']:
        actual=(_PACKAGE.parent/Path(row['destination']).relative_to('src')).resolve()
        if not actual.is_relative_to(_PACKAGE):raise ValueError('Runtime source escaped package')
        if installed.get(str(actual))!=row['destination_sha256']:
            raise ValueError('Runtime extraction source changed: '+str(actual))
        if audit_historical:
            historical_source_file(row['source'])
    return dict(modules=len(mapping['sources']),resource_root=str(resource_root()),
                installed_source_pins=installed,
                historical_archive_audited=audit_historical,standalone_resource_bundle_ready=False)
