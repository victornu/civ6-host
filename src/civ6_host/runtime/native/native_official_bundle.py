"""Explicit capture994 inputs for the existing Base Load path.

This is diagnostic plumbing, not scenario admission. In particular a capture
without an authenticated active Localization export is refused, never filled
from the historical cache. No native code is run by this module.
"""
from civ6_host.runtime import localization_bulk_export as bulk_export
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
from dataclasses import dataclass
from collections import OrderedDict
from pathlib import Path
import copy
import ctypes as C
import hashlib
import hmac
import json
import math
import os
import re
import secrets
import time
from weakref import WeakKeyDictionary
ROOT = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_official_bundle.py')))).resolve().parents[1]
DATABASE_PROFILE = 'official-captured-bundle-diagnostic'
SCHEMA = 'civ6rl.phase1_capture994.v1'
_VALIDATOR_MODULE_SHA256 = hashlib.sha256(_resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_official_bundle.py')))).read_bytes()).hexdigest()
LOCALIZATION_HANDOFF_ENV = 'CIV6RL_LOCALIZATION_HANDOFF_KEY'
LOCALIZATION_HANDOFF_FIELD = 'parent_localization_validation'
LOCALIZATION_HANDOFF_SCHEMA = 'civ6rl.parent_localization_validation.v1'
_PREPARED_BUNDLE_ADMISSIONS = WeakKeyDictionary()
_PARENT_ADMISSION_TOKEN = object()
_PREPARED_BUNDLE_VALIDATOR_PATHS = ('civ6rl/native_official_bundle.py', 'civ6rl/native_official_load.py', 'civ6rl/native_checkpoint_provider.py', 'civ6rl/official_save.py', 'civ6rl/database_capture_bundle993.py', 'civ6rl/native_gameplay_source_capture.py', 'civ6rl/native_gameplay_empty.py', 'civ6rl/native_localization_logical_export.py', 'civ6rl/native_localization.py', 'civ6rl/native_source_cache.py', 'civ6rl/official_configuration.py', 'civ6rl/official_application_configuration.py', 'tools/capture_phase1_bundle994.py')

def require(ok, message):
    if not ok:
        raise ValueError(message)

def sha(raw):
    return hashlib.sha256(raw).hexdigest()

def normalize_reference(reference):
    require(type(reference) is dict and set(reference) == {'path', 'sha256'}, 'Official bundle requires an explicit path and SHA256')
    require(type(reference['path']) is str and type(reference['sha256']) is str and re.fullmatch('[0-9a-f]{64}', reference['sha256']), 'Invalid official bundle reference')
    path = _resolve_resource_path(ROOT / reference['path']).resolve()
    require(path.is_relative_to(ROOT / 'work') and _resolve_resource_path(path).is_file(), 'Official bundle must be retained under work')
    require(0 < _resolve_resource_path(path).stat().st_size <= 4 * 1024 ** 2, 'Official bundle manifest exceeds its byte bound')
    return (path.relative_to(ROOT).as_posix(), reference['sha256'])

def _file(row, dependencies, *, workspace=True, maximum=128 * 1024 ** 2, prefix_bytes=None):
    """Authenticate every byte, optionally retaining only the requested header."""
    require(type(row) is dict and type(row.get('path')) is str and (type(row.get('bytes')) is int) and (0 < row['bytes'] <= maximum) and (type(row.get('sha256')) is str) and re.fullmatch('[0-9a-f]{64}', row['sha256']), 'Malformed or unbounded bundle file')
    path = _resolve_resource_path(ROOT / row['path']).resolve()
    require(not workspace or path.is_relative_to(ROOT / 'work'), 'Bundle file escaped private work artifacts')
    source = _resolve_resource_path(path)
    require(source.is_file() and source.stat().st_size == row['bytes'], 'Bundle file size differs')
    if prefix_bytes is None:
        raw = source.read_bytes()
        size, digest = len(raw), sha(raw)
    else:
        require(type(prefix_bytes) is int and 0 <= prefix_bytes <= min(row['bytes'], 256 * 1024),
                'Invalid bundle file prefix bound')
        with source.open('rb') as stream:
            raw = stream.read(prefix_bytes)
            checksum = hashlib.sha256(raw)
            size = len(raw)
            while chunk := stream.read(256 * 1024):
                size += len(chunk)
                require(size <= row['bytes'], 'Bundle file size changed during read')
                checksum.update(chunk)
        digest = checksum.hexdigest()
    require(size == row['bytes'], 'Bundle file size changed during read')
    require(digest == row['sha256'], 'Bundle file hash differs: ' + str(path))
    if isinstance(dependencies, _LocalizationDependencyPins):
        dependencies._record_verified(str(path), row['sha256'], size)
    else:
        dependencies[str(path)] = row['sha256']
    return raw

def _manifest(reference):
    from civ6_host.runtime.native.native_source_cache import load_pinned_json
    if type(reference) is dict:
        reference = normalize_reference(reference)
    require(type(reference) is tuple and len(reference) == 2 and (normalize_reference(dict(path=reference[0], sha256=reference[1])) == reference), 'Noncanonical official bundle reference')
    m = load_pinned_json(ROOT / reference[0], reference[1])
    raw = _resolve_resource_path(ROOT / reference[0]).read_bytes()
    require(sha(raw) == reference[1], 'Official bundle changed during read')
    m = json.loads(raw)
    require(m.get('schema') == SCHEMA and m.get('status') == 'correlated_capture_unqualified' and (m.get('training_eligible') is False) and (m.get('atomic_snapshot') is False), 'Expected an unmodified correlated capture994 manifest')
    return (reference, m)

def _response_transport(manifest, dependencies):
    """Retain an explicit direct writer's full closure; absent means legacy."""
    continuation_options = {}
    from civ6_host.runtime.workers import capture_phase1_bundle994 as capture
    before = manifest['preflight'].get('response_file_transport')
    current = manifest.get('response_file_transport')
    if 'response_file_transport' not in manifest['preflight'] and 'response_file_transport' not in manifest:
        return
    require(type(current) is dict and current == before, 'Response transport provenance differs from preflight')
    if current.get('predecessor') is not None:
        continuation_options['predecessor'] = current['predecessor']
    verified = capture._response_file_provenance(current['installation'], manifest['preflight']['process'], time.monotonic() + 30, **continuation_options)
    require(current == verified, 'Response transport retained closure differs')
    require(manifest.get('bridge_session') == current['prepared']['session_id'], 'Response transport session differs from capture')
    for side in ('before', 'after'):
        observation = json.loads(_file(manifest['artifacts']['observation-' + side + '.json'], dependencies, maximum=16 * 1024 ** 2))
        require(observation.get('player_id') == current['player_id'] and observation.get('turn') == current['turn'], 'Response transport belongs to another player/turn boundary')
    for item in current['dependencies'] + list(current['implementation_sources'].values()):
        _file(item, dependencies, workspace=False, maximum=4 * 1024 ** 2)
    if current.get('predecessor') is not None:
        for item in current['predecessor_dependencies']:
            _file(item, dependencies, workspace=False, maximum=64 * 1024 * 1024)

def _localization(manifest, dependencies, *, cache_key=None):
    """Join two validated active exports to the captured save boundary.

    This preserves the producer's bounded claim: equal observed owners/bytes
    around one save request, not a transaction or a completed headless Load.
    """
    from civ6_host.runtime.capture_admission import try_localization
    prepared = try_localization(manifest, dependencies, reference=cache_key)
    if prepared is not None:
        return prepared
    return _localization_cached(manifest, dependencies, cache_key=cache_key)
_LOCALIZATION_CACHE_LIMIT = 2
_LOCALIZATION_CACHE = OrderedDict()

class _LocalizationDependencyPins(dict):
    """Collect exact sizes alongside hashes checked from bytes or verified receipts."""

    def __init__(self):
        super().__init__()
        self.sizes = {}

    def __setitem__(self, path, digest):
        resolved = str(_resolve_resource_path(_resolve_resource_path(Path(path))).resolve(strict=True))
        require(resolved == path, 'Localization dependency path is not canonical')
        size = _resolve_resource_path(_resolve_resource_path(Path(path))).stat().st_size
        self._record_verified(path, digest, size)

    def _record_verified(self, path, digest, size):
        if path in self and (self[path] != digest or self.sizes[path] != size):
            raise ValueError('Localization dependency changed during validation')
        super().__setitem__(path, digest)
        self.sizes[path] = size

def _localization_cache_manifest(manifest, cache_key):
    if type(cache_key) is not tuple or len(cache_key) != 2 or any((type(part) is not str for part in cache_key)):
        raise ValueError('Localization cache requires the validated exact bundle reference')
    reference, current = _manifest(dict(path=cache_key[0], sha256=cache_key[1]))
    if reference != cache_key or current != manifest:
        raise ValueError('Localization cache key does not identify this exact manifest')
    path = ROOT / reference[0]
    raw = _resolve_resource_path(path).read_bytes()
    return (reference, dict(path=str(_resolve_resource_path(path).resolve(strict=True)), sha256=reference[1], bytes=len(raw)))

def _cache_resolve_path(path):
    if _resolve_resource_path(Path(path)).is_symlink():
        raise ValueError('Cached Localization dependency path became a symlink')
    return _resolve_resource_path(_resolve_resource_path(Path(path))).resolve(strict=True)

def _revalidate_localization_cache(reference, manifest_pin, entry):
    manifest_path = _cache_resolve_path(manifest_pin['path'])
    if str(manifest_path) != manifest_pin['path']:
        raise ValueError('Cached Localization manifest path was redirected')
    raw = _resolve_resource_path(manifest_path).read_bytes()
    if len(raw) != manifest_pin['bytes'] or sha(raw) != manifest_pin['sha256']:
        raise ValueError('Cached Localization manifest changed')
    for path, pin in entry['dependencies'].items():
        resolved = _cache_resolve_path(path)
        if str(resolved) != path:
            raise ValueError('Cached Localization dependency path was redirected')
        if not _resolve_resource_path(resolved).is_file() or _resolve_resource_path(resolved).stat().st_size != pin['bytes']:
            raise ValueError('Cached Localization dependency is missing or changed size')
        if sha(_resolve_resource_path(resolved).read_bytes()) != pin['sha256']:
            raise ValueError('Cached Localization dependency bytes changed')

def _localization_cached(manifest, dependencies, *, cache_key):
    if cache_key is None:
        return _localization_uncached(manifest, dependencies)
    reference, manifest_pin = _localization_cache_manifest(manifest, cache_key)
    key = (reference[0], reference[1])
    entry = _LOCALIZATION_CACHE.get(key)
    if entry is not None:
        try:
            require(entry.get('validator_module_sha256') == _current_validator_digest(), 'Localization cache validator source changed')
            if entry['manifest_pin'] != manifest_pin:
                raise ValueError('Cached Localization manifest pin differs')
            _revalidate_localization_cache(reference, manifest_pin, entry)
        except BaseException:
            _LOCALIZATION_CACHE.pop(key, None)
            raise
        _LOCALIZATION_CACHE.move_to_end(key)
        _merge_localization_pins(dependencies, entry['dependency_hashes'])
        return copy.deepcopy(entry['result'])
    validator_digest = _current_validator_digest()
    pins = _LocalizationDependencyPins()
    result = _localization_uncached(manifest, pins)
    require(_current_validator_digest() == validator_digest, 'Localization validator changed during validation')
    dependency_hashes = dict(pins)
    dependency_snapshot = {path: dict(sha256=digest, bytes=pins.sizes[path]) for path, digest in dependency_hashes.items()}
    _merge_localization_pins(dependencies, dependency_hashes)
    _LOCALIZATION_CACHE[key] = dict(result=copy.deepcopy(result), manifest_pin=manifest_pin, dependency_hashes=dependency_hashes, dependencies=dependency_snapshot, validator_module_sha256=validator_digest)
    while len(_LOCALIZATION_CACHE) > _LOCALIZATION_CACHE_LIMIT:
        _LOCALIZATION_CACHE.popitem(last=False)
    return result

def _current_validator_digest():
    digest = sha(_resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_official_bundle.py')))).read_bytes())
    require(digest == _VALIDATOR_MODULE_SHA256, 'Loaded Localization validator differs from its current source')
    return digest

def _handoff_bytes(payload):
    raw = json.dumps(payload, sort_keys=True, separators=(',', ':'), ensure_ascii=True, allow_nan=False).encode('ascii')
    require(len(raw) <= 32 * 1024 ** 2, 'Localization handoff exceeds its byte bound')
    return raw

def _require_closure_pin(pins, path, digest):
    """Cache paths are already canonical; preserve all spelling conflicts."""
    require(type(pins) is dict and type(path) is str and _resolve_resource_path(Path(path)).is_absolute(), 'Localization handoff needs canonical closure dependencies')
    candidate = _resolve_resource_path(Path(path))
    keys = {path}
    if candidate.is_relative_to(ROOT):
        relative = candidate.relative_to(ROOT)
        keys.update((str(relative), relative.as_posix()))
    found = [pins[key] for key in keys if key in pins]
    require(found and all((value == digest for value in found)), 'Localization handoff dependency missing or changed in closure: ' + path)

def create_parent_localization_handoff(closure):
    """Export only this process's successful full validation, never a saved assertion.

    The random key travels only in the child's private launch environment.
    A private sidecar retains the authenticated payload, not the key. This is
    a trusted parent/child handoff, not a portable or persistent certificate.
    """
    require(LOCALIZATION_HANDOFF_FIELD not in closure, 'Localization handoff already present')
    reference, manifest = _manifest(closure['official_bundle'])
    entry = _LOCALIZATION_CACHE.get(reference)
    require(entry is not None, 'Parent has no completed Localization validation for this bundle')
    digest = _current_validator_digest()
    require(entry.get('validator_module_sha256') == digest, 'Parent Localization validation used another source')
    _, manifest_pin = _localization_cache_manifest(manifest, reference)
    require(entry['manifest_pin'] == manifest_pin, 'Parent Localization manifest differs')
    require(set(entry['dependencies']) == set(entry['dependency_hashes']) and all((pin['sha256'] == entry['dependency_hashes'][path] for path, pin in entry['dependencies'].items())), 'Parent Localization dependency closure is incomplete')
    nonce = closure.get('nonce')
    require(type(nonce) is str and re.fullmatch('[0-9a-f]{32}', nonce), 'Localization handoff requires this session nonce')
    require(closure.get('input_profile') in ('single', 'hotseat-four', 'lan'), 'Localization handoff profile differs')
    pins = closure['pins']
    _require_closure_pin(pins, str(_resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_official_bundle.py')))).resolve()), digest)
    _require_closure_pin(pins, manifest_pin['path'], manifest_pin['sha256'])
    for path, pin in entry['dependencies'].items():
        _require_closure_pin(pins, path, pin['sha256'])
    payload = dict(schema=LOCALIZATION_HANDOFF_SCHEMA, nonce=nonce, reference=dict(path=reference[0], sha256=reference[1]), input_profile=closure['input_profile'], validator_module_sha256=digest, manifest_pin=copy.deepcopy(manifest_pin), dependencies=copy.deepcopy(entry['dependencies']), result=copy.deepcopy(entry['result']))
    raw = _handoff_bytes(payload)
    key = secrets.token_hex(32)
    envelope = dict(payload=payload, mac=hmac.new(bytes.fromhex(key), raw, hashlib.sha256).hexdigest())
    return (envelope, key)

def consume_parent_localization_handoff(closure, *, environment=None):
    """Install an authenticated memo; ordinary cache use rehashes every file.

    The caller has just checked all closure pins. We never directly serve the
    imported result: read_bundle still calls _localization_cached, including
    its canonical-path, size and full-byte revalidation before every use.
    """
    from civ6_host.runtime.capture_admission import consume_prepared_closure
    prepared = consume_prepared_closure(closure, environment=environment)
    if prepared is not None:
        return prepared
    environment = os.environ if environment is None else environment
    key = environment.pop(LOCALIZATION_HANDOFF_ENV, None)
    if LOCALIZATION_HANDOFF_FIELD not in closure:
        require(key is None, 'Unexpected Localization handoff key without a payload')
        return None
    require(type(key) is str and re.fullmatch('[0-9a-f]{64}', key), 'Localization handoff key absent or malformed')
    sidecar = closure[LOCALIZATION_HANDOFF_FIELD]
    require(type(sidecar) is dict and set(sidecar) == {'path', 'sha256', 'bytes'}, 'Malformed Localization handoff sidecar reference')
    recorded = {}
    envelope = json.loads(_file(sidecar, recorded, maximum=32 * 1024 ** 2))
    for path, digest in recorded.items():
        _require_closure_pin(closure['pins'], path, digest)
    require(type(envelope) is dict and set(envelope) == {'payload', 'mac'}, 'Malformed Localization handoff envelope')
    payload, mac = (envelope['payload'], envelope['mac'])
    require(type(payload) is dict and type(mac) is str and re.fullmatch('[0-9a-f]{64}', mac), 'Malformed Localization handoff authentication')
    raw = _handoff_bytes(payload)
    require(hmac.compare_digest(mac, hmac.new(bytes.fromhex(key), raw, hashlib.sha256).hexdigest()), 'Localization handoff authentication failed')
    require(set(payload) == {'schema', 'nonce', 'reference', 'input_profile', 'validator_module_sha256', 'manifest_pin', 'dependencies', 'result'} and payload['schema'] == LOCALIZATION_HANDOFF_SCHEMA, 'Localization handoff schema differs')
    require(payload['nonce'] == closure.get('nonce') and payload['input_profile'] == closure.get('input_profile') and (payload['input_profile'] in ('single', 'hotseat-four', 'lan')) and (payload['reference'] == closure.get('official_bundle')), 'Localization handoff belongs to another session/profile/bundle')
    digest = _current_validator_digest()
    require(payload['validator_module_sha256'] == digest, 'Localization handoff validator source differs')
    reference, manifest = _manifest(payload['reference'])
    _, manifest_pin = _localization_cache_manifest(manifest, reference)
    require(payload['manifest_pin'] == manifest_pin, 'Localization handoff manifest differs')
    pins = closure['pins']
    _require_closure_pin(pins, str(_resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_official_bundle.py')))).resolve()), digest)
    _require_closure_pin(pins, manifest_pin['path'], manifest_pin['sha256'])
    dependencies = payload['dependencies']
    require(type(dependencies) is dict and 0 < len(dependencies) <= 65536, 'Localization handoff dependency count differs')
    for path, pin in dependencies.items():
        require(type(pin) is dict and set(pin) == {'sha256', 'bytes'} and (type(pin['sha256']) is str) and re.fullmatch('[0-9a-f]{64}', pin['sha256']) and (type(pin['bytes']) is int) and (0 <= pin['bytes'] <= 512 * 1024 ** 2), 'Malformed Localization handoff dependency')
        _require_closure_pin(pins, path, pin['sha256'])
    result = payload['result']
    require(type(result) in (tuple, list) and len(result) == 2 and all((type(row) is dict for row in result)), 'Localization handoff must contain the complete result')
    _LOCALIZATION_CACHE[reference] = dict(result=copy.deepcopy(tuple(result)), manifest_pin=manifest_pin, dependencies=dependencies, dependency_hashes={path: pin['sha256'] for path, pin in dependencies.items()}, validator_module_sha256=digest)
    _LOCALIZATION_CACHE.move_to_end(reference)
    while len(_LOCALIZATION_CACHE) > _LOCALIZATION_CACHE_LIMIT:
        _LOCALIZATION_CACHE.popitem(last=False)
    return dict(schema=LOCALIZATION_HANDOFF_SCHEMA, reference=payload['reference'], payload_sha256=sha(raw), dependency_count=len(dependencies), authority='same_run_parent_full_validation', byte_revalidation_required=True, actor_input=False, strategic_training_ready=False)

def _merge_localization_pins(destination, pins):
    for path, digest in pins.items():
        previous = destination.setdefault(path, digest)
        require(previous == digest, 'Localization dependency conflicts with an existing pin')

def _merge_localization_pin_records(destination, records):
    """Merge receipts whose digest and byte size came from one verified read."""
    for path, digest, size in records:
        if isinstance(destination, _LocalizationDependencyPins):
            destination._record_verified(path, digest, size)
        else:
            previous = destination.setdefault(path, digest)
            require(previous == digest, 'Localization dependency conflicts with an existing pin')

def _logical_dependency_references_from_validated(logical, reference, report, verified_tables=None, *, retained_sources=None):
    """Return the producer's exact closure without replaying its validator."""
    from civ6_host.runtime.native import database_capture_bundle993 as tables
    installed = logical._json(report['installation'])
    registered = logical._json(report['registration'])
    build = logical._json(report['build'])
    refs = [reference, report['installation'], report['registration'], report['build'], report['database'], report['installed_collector'], report['tables_bundle'], installed['command']]
    if report.get('database_production') == logical.MATERIALIZED:
        refs.append(report['template'])
    refs += bulk_export.extra_dependencies(report, retained_sources=retained_sources)
    refs += logical.producer_dependencies(report['producer_sources'])['dependency_references']
    refs += build['sources'] + build['snapshots'] + [build['dll']]
    for runtime_ref in (report['runtime_before'], report['runtime_after'], installed['runtime_before'], installed['runtime_after']):
        refs += [runtime_ref, logical._json(runtime_ref)['icu_data']]
    if verified_tables is None:
        bundle = logical._json(report['tables_bundle'], limit=logical.MAX_MANIFEST_BYTES)
        directory = _resolve_resource_path(Path(report['tables_bundle']['path'])).parent
        refs += [{**pin, 'path': str(directory / pin['path'])} for pin in bundle['files']]
    else:
        require(tables._is_verified_bundle(verified_tables) and verified_tables.directory == _resolve_resource_path(_resolve_resource_path(Path(report['tables_bundle']['path']))).resolve().parent, 'Verified Localization journal evidence differs from export reference')
    logical._require(registered['build'] == report['build'], 'Dependency build join differs')
    unique = {}
    for pin in refs:
        previous = unique.setdefault(pin['path'], pin)
        logical._require(previous == pin, 'Conflicting dependency file pins')
    return list(unique.values())

def _localization_uncached(manifest, dependencies, *, _retained_sources=None):
    """Full semantic validation; only successful results may enter the cache."""
    from civ6_host.runtime.native import native_localization_export as export
    from civ6_host.runtime.native import native_localization_capture as reader
    from civ6_host.runtime.native import native_localization_logical_export as logical
    from civ6_host.runtime.native import database_capture_bundle993 as tables
    from civ6_host.runtime.workers import capture_phase1_bundle994 as capture
    refs = manifest.get('localization_exports')
    require(type(refs) is dict and set(refs) == {'before', 'after'}, 'Official bundle Localization active export is unavailable; historical cache substitution refused')
    process = manifest['preflight']['process']
    capture._identity(process, process['identity']['pid'])
    require(manifest.get('process_after') == process, 'Localization capture process changed across save')
    caller = manifest['preflight']['tool_source_pins']['tools/capture_phase1_bundle994.py']
    require(_resolve_resource_path(_resolve_resource_path(Path(caller['path']))).resolve() == _resolve_resource_path(_resolve_resource_path(Path(_historical_module_file(capture)))).resolve(), 'Localization capture caller differs')
    _file(caller, dependencies, workspace=False, maximum=4 * 1024 ** 2)
    operations = manifest.get('capture_operations')
    expected = ('localization_export', 'official_save_request', 'official_save_acknowledged', 'localization_export')
    require(type(operations) is list and len(operations) == 4 and all((type(row) is dict and type(row.get('index')) is int and (row['index'] == index) and (row.get('kind') == expected[index]) for index, row in enumerate(operations))), 'Localization exports do not bracket exactly one official save request')
    elapsed = [row.get('elapsed_seconds') for row in operations]
    require(all((type(value) in (int, float) and math.isfinite(value) and (value >= 0) for value in elapsed)) and elapsed == sorted(elapsed), 'Localization operation timings are malformed')
    artifacts = manifest['artifacts']

    def artifact(name):
        return json.loads(_file(artifacts[name], dependencies, maximum=16 * 1024 ** 2))
    receipt = artifact('save-receipt.json')
    ack = receipt['acknowledgement']
    saved = manifest['save']
    request, completed = operations[1:3]
    player, turn = (request.get('expected_player_id'), request.get('expected_turn'))
    require(type(player) is int and player == 0 and (type(turn) is int) and (1 <= turn <= 100000), 'Localization save boundary is outside the supported player-zero Load profiles')
    require(type(request.get('name')) is str and request['name'] and (_resolve_resource_path(Path(receipt['path'])).stem == request['name']) and (_resolve_resource_path(_resolve_resource_path(Path(saved['source']['path']))).resolve() == _resolve_resource_path(_resolve_resource_path(Path(receipt['path']))).resolve()), 'Localization save request name/path differs')
    require(ack.get('type') == 'transport_status' and ack.get('status') == 'ok' and (ack.get('reason') == 'save_snapshot_requested') and (type(ack.get('sequence')) is int) and (ack['sequence'] >= 0) and (type(saved.get('request_nonce')) is str) and saved['request_nonce'] and (ack.get('request_id') == saved['request_nonce']) and (type(ack.get('player_id')) is int) and (ack['player_id'] == player) and (type(ack.get('turn')) is int) and (ack['turn'] == turn) and (completed.get('request_id') == ack['request_id']) and (type(completed.get('sequence')) is int) and (completed['sequence'] == ack['sequence']) and (type(completed.get('player_id')) is int) and (completed['player_id'] == player) and (type(completed.get('turn')) is int) and (completed['turn'] == turn) and (completed.get('save_sha256') == saved['source']['sha256'] == receipt['sha256']) and (saved['source']['bytes'] == receipt['bytes']), 'Localization save acknowledgement join differs')
    events = [row for row in manifest['bridge_events'] if row.get('kind') == 'save_snapshot']
    require(events == [dict(kind='save_snapshot', nonce=ack['request_id'], sequence=ack['sequence'])], 'Localization save event differs from the bridge receipt')
    runtime_claim = manifest.get('localization_runtime')
    require(runtime_claim == dict(before_artifact='localization-before.json', after_artifact='localization-after.json', observed_context_and_loaded_icu_equal=True, source_database_exported=True, database_lifetime_lease_proven=False, atomic_snapshot_proven=False, headless_bootstrap_qualified=False), 'Localization runtime scope differs')
    verified = []
    for side, operation in zip(('before', 'after'), (operations[0], operations[3])):
        reference = refs[side]
        require(type(reference) is dict and set(reference) == {'path', 'sha256', 'bytes'} and (operation.get('side') == side) and (operation.get('reference') == reference), 'Localization export operation reference differs')
        _file(reference, dependencies, maximum=4 * 1024 ** 2)
        report = artifact('localization-' + side + '.json')
        folder = _resolve_resource_path(_resolve_resource_path(Path(artifacts['localization-' + side + '.json']['path']))).resolve().parent
        require(_resolve_resource_path(_resolve_resource_path(Path(reference['path']))).resolve().parent == folder / ('localization-export-' + side), 'Localization export escaped its capture side')
        state = capture._localization_semantics(report, process, folder / ('localization-' + side), time.monotonic() + 30)
        _file(report['icu_data'], dependencies, maximum=reader.MAX_ICU_BYTES)
        validator = capture._localization_export_validator(reference)
        validation_options = dict(expected_process=process['identity'], expected_nonce=operation.get('nonce'))
        if validator is logical.validate_export_manifest:
            validation_options['_with_verified_tables'] = True
            if _retained_sources is not None:
                validation_options['_retained_sources'] = _retained_sources
        current = validator(reference, **validation_options)
        result = current['manifest']
        require(type(operation.get('nonce')) is str and re.fullmatch('[0-9a-f]{32}', operation['nonce']) and (result['expected_player_id'] == player) and (result['expected_turn'] == turn) and (current['runtime_identity'] == state), 'Localization export belongs to another save boundary or owner')
        observation = artifact('observation-' + side + '.json')
        require(type(observation.get('player_id')) is int and observation['player_id'] == player and (type(observation.get('turn')) is int) and (observation['turn'] == turn), 'Localization export differs from the observed player/turn')
        for name in ('runtime_before', 'runtime_after'):
            runtime = json.loads(_file(result[name], dependencies, maximum=4 * 1024 ** 2))
            require(runtime['modules'] == report['modules'], 'Localization export module inventory differs')
            _file(runtime['icu_data'], dependencies, maximum=reader.MAX_ICU_BYTES)
        _file(current['database'], dependencies, maximum=export.MAX_DB_BYTES)
        if result['schema'] == logical.SCHEMA:
            verified_tables = current['_verified_tables']
            for dependency in _logical_dependency_references_from_validated(logical, reference, result, verified_tables, retained_sources=_retained_sources):
                _file(dependency, dependencies, workspace=False, maximum=export.MAX_DB_BYTES)
            _merge_localization_pin_records(dependencies, verified_tables.dependency_pins())
        verified.append(current)
    require(operations[0]['nonce'] != operations[3]['nonce'], 'Localization export nonce reused')
    first, last = verified
    bulk_export.same_profile(first['manifest'], last['manifest'])
    require(first['manifest']['schema'] == last['manifest']['schema'], 'Localization export producer changed across save')
    require(first['runtime_identity'] == last['runtime_identity'] and all((first['database'][key] == last['database'][key] for key in ('sha256', 'bytes'))), 'Active Localization changed across the official save')
    if first['manifest']['schema'] == export.SCHEMA:
        build = export.verify_build()
        for reference in (export.reference(export.BUILD_PATH), build['source_snapshot'], build['dll'], *build['sources']):
            _file(reference, dependencies, workspace=False, maximum=4 * 1024 ** 2)
    for module in (export, reader):
        _file(export.reference(_historical_module_file(module)), dependencies, workspace=False, maximum=4 * 1024 ** 2)
    return ({key: last['database'][key] for key in ('path', 'sha256', 'size_bytes')}, {**last['bootstrap'], 'official_export': dict(refs['after'])})

def validate_localization_fixture(manifest):
    """Validate an explicit bootstrap/private DB against its retained bundle."""
    reference, captured = _manifest(manifest.get('official_bundle'))
    _response_transport(captured, {})
    database, bootstrap = _localization(captured, {}, cache_key=reference)
    if manifest.get('input_profile') in ('xp1-lan', 'xp2-lan'):
        from civ6_host.runtime.xp1_saved_load import REFERENCE, validate_private_bootstrap
        if manifest['input_profile'] == 'xp2-lan':
            from civ6_host.runtime.xp2_bundle_inputs import REFERENCE
        require(reference == REFERENCE, 'Private Localization belongs to another expansion capture')
        validate_private_bootstrap(manifest, bootstrap, private_root=_resolve_resource_path(Path(manifest['databases']['localization']['path'])).resolve().parent)
    else:
        require(manifest.get('localization_bootstrap') == bootstrap, 'Localization bootstrap differs from the official captured export')
    actual = manifest['databases']['localization']
    require(actual.get('sha256') == database['sha256'] and actual.get('size_bytes') == database['size_bytes'] and _resolve_resource_path(_resolve_resource_path(Path(actual['path']))).is_file() and (_resolve_resource_path(_resolve_resource_path(Path(actual['path']))).stat().st_size == database['size_bytes']), 'Localization fixture database differs from the official captured export')
    return bootstrap

def _configuration(raw, manifest, mode, *, expected_ruleset='RULESET_STANDARD'):
    from civ6_host.runtime.native.official_application_configuration import extract_application_configuration
    configuration, receipt = extract_application_configuration(raw)
    require(receipt['save_sha256'] == manifest['save']['source']['sha256'], 'Application provider belongs to another save')
    require(receipt['content_declaration']['declared_ruleset'] == expected_ruleset, 'Captured ruleset differs from the selected official capture input family')
    return parse_configuration(configuration, mode)

def parse_configuration(configuration, mode):
    """Parse an already authenticated provider; never discovers its identity."""
    from civ6_host.runtime.native.official_configuration import read_provider
    from civ6_host.runtime.native.native_game_configuration import game_configuration_hash as key
    values, end = read_provider(configuration)
    require(end == len(configuration), 'Application provider boundary differs')
    roots = {v.key: v for v in values}
    require(len(roots) == len(values), 'Duplicate application provider roots')
    game = {v.key: v for v in roots[key('GAME_ROOT')].children}
    saved_mode = game[key('GAME_MODE')]
    require(saved_mode.tag == 3 and saved_mode.scalar() == key(mode), 'Captured game mode differs from the session family')
    children = {v.key: v for v in roots[key('MAP_ROOT')].children}
    maps = []
    for name in ('start', 'world_age', 'RANDOM_SEED', 'MAP_SIZE'):
        value = children.get(key(name))
        if value is None and name in ('start', 'world_age'):
            maps.append((name, None))
        else:
            require(value is not None and value.tag in (2, 3) and (value.flags == 0), 'Unsupported captured map value: ' + name)
            maps.append((name, C.c_int32(value.scalar()).value))
    return (configuration, tuple(maps))

@dataclass(frozen=True, eq=False)
class PreparedBundle:
    reference: tuple
    inputs: object
    initial_turn: int
    engine_path: Path
    fixture: dict
    dependencies: dict
    expected_readback: dict
    content_profile: dict
    # Capture provenance stays in content_profile. This optional selection is
    # the distinct image requested for this execution, never a rewritten capture.
    execution_image: object | None = None

def _prepared_bundle_validator_digests():
    """Hash validator source bytes exactly; no timestamp-based admission."""
    try:
        return {name: sha(_resolve_resource_path(ROOT / name).read_bytes()) for name in _PREPARED_BUNDLE_VALIDATOR_PATHS}
    except OSError as exc:
        raise ValueError('Prepared bundle validator source is unavailable') from exc

def _prepared_bundle_fingerprint(bundle):
    try:
        inputs = bundle.inputs
        profile = inputs.profile
        payload = dict(reference=list(bundle.reference), input_profile=profile.mode_name, profile_identity=dict(config_sha=profile.config_sha, game_sha=profile.game_sha, save_sha=profile.save_sha), inputs=dict(configuration_sha=sha(inputs.configuration), configuration_bytes=len(inputs.configuration), game_sha=sha(inputs.game), game_bytes=len(inputs.game), map_values=inputs.map_values, official_bundle=inputs.official_bundle, checkpoint=inputs.checkpoint), initial_turn=bundle.initial_turn, engine_path=str(_resolve_resource_path(bundle.engine_path).resolve()), fixture=bundle.fixture, dependencies=bundle.dependencies, expected_readback=bundle.expected_readback, content_profile=bundle.content_profile)
        if bundle.execution_image is not None:
            from civ6_host.runtime.execution_images import identity
            payload['execution_image'] = identity(bundle.execution_image)
        raw = json.dumps(payload, sort_keys=True, separators=(',', ':'), ensure_ascii=True, allow_nan=False).encode('ascii')
        return sha(raw)
    except (AttributeError, OSError, TypeError, ValueError) as exc:
        raise ValueError('Parent-admitted bundle contents are malformed') from exc

def _remember_prepared_bundle(bundle, input_profile, validator_digests, *, _token=None, _input_only=False):
    require(_token is _PARENT_ADMISSION_TOKEN and type(bundle) is PreparedBundle and (input_profile in ('single', 'hotseat-four', 'lan') or (_input_only is True and input_profile in ('xp1-lan', 'xp2-lan'))) and (type(validator_digests) is dict) and (set(validator_digests) == set(_PREPARED_BUNDLE_VALIDATOR_PATHS)), 'Cannot register malformed prepared bundle admission')
    input_validators = None
    if _input_only:
        if input_profile == 'xp1-lan':
            from civ6_host.runtime.xp1_bundle_inputs import reader_validator_digests
        elif input_profile == 'xp2-lan':
            from civ6_host.runtime.xp2_bundle_inputs import reader_validator_digests
        else:
            raise ValueError('Input-only admission requires an explicit expansion family')
        input_validators = reader_validator_digests()
    _PREPARED_BUNDLE_ADMISSIONS[bundle] = dict(input_only=_input_only, input_validators=input_validators, reference=bundle.reference, input_profile=input_profile, validator_digests=dict(validator_digests), fingerprint=_prepared_bundle_fingerprint(bundle))
    return bundle

def _reuse_prepared_bundle(bundle, reference, input_profile, *, _input_only=False):
    from civ6_host.runtime.capture_profiles import LAN_PROFILE
    require(type(bundle) is PreparedBundle and bundle in _PREPARED_BUNDLE_ADMISSIONS, 'Prepared bundle reuse requires a parent-admitted instance')
    admission = _PREPARED_BUNDLE_ADMISSIONS[bundle]
    from civ6_host.runtime.native.native_official_load import SINGLE_PROFILE
    from civ6_host.runtime.native.native_official_load import HOTSEAT_FOUR_PROFILE
    expected_profile = {'single': SINGLE_PROFILE, 'hotseat-four': HOTSEAT_FOUR_PROFILE, 'lan': LAN_PROFILE}
    require(type(_input_only) is bool and admission.get('input_only', False) is _input_only, 'Prepared bundle input-only scope differs')
    if _input_only:
        if input_profile == 'xp1-lan':
            from civ6_host.runtime.xp1_bundle_inputs import XP1_LAN_PROFILE, reader_validator_digests
            expected_profile = {'xp1-lan': XP1_LAN_PROFILE}
        elif input_profile == 'xp2-lan':
            from civ6_host.runtime.xp2_bundle_inputs import XP2_LAN_PROFILE, reader_validator_digests
            expected_profile = {'xp2-lan': XP2_LAN_PROFILE}
        else:
            raise ValueError('Input-only reuse requires an explicit expansion family')
        require(reader_validator_digests() == admission['input_validators'], 'Expansion input validator sources changed')
    normalized = reference if type(reference) is tuple and len(reference) == 2 else normalize_reference(reference)
    require(input_profile in expected_profile and normalized == bundle.reference and (admission['reference'] == bundle.reference) and (admission['input_profile'] == input_profile) and (bundle.inputs.official_bundle == bundle.reference) and (bundle.inputs.profile is expected_profile[input_profile]), 'Parent-admitted bundle identity or profile differs')
    require(_prepared_bundle_validator_digests() == admission['validator_digests'], 'Prepared bundle validator sources changed')
    require(_prepared_bundle_fingerprint(bundle) == admission['fingerprint'], 'Parent-admitted bundle contents changed')
    return bundle

def build_content_profile(*, process, databases, localization_bootstrap, resolved_content, gameplay_selection, active_state, script_manifest):
    """Build a bounded, path-free content description from verified capture data.

    The observed component vectors are handles, not proven persistent content
    identifiers. They are retained for diagnostics, but non-empty vectors make
    cross-capture equivalence unsupported until each handle has a stable
    source/content join. This is not a ruleset or gameplay qualification.
    """
    require(type(process) is dict and type(process.get('exe_sha256')) is str and re.fullmatch('[0-9a-f]{64}', process['exe_sha256']) and (type(process.get('gamecore_module')) is dict) and (type(process['gamecore_module'].get('sha256')) is str) and re.fullmatch('[0-9a-f]{64}', process['gamecore_module']['sha256']), 'Content profile needs exact executable and engine hashes')
    require(type(databases) is dict and set(databases) == {'configuration', 'gameplay', 'localization'}, 'Content profile needs all three final databases')
    database_profile = {}
    for role, row in databases.items():
        require(type(row) is dict and type(row.get('sha256')) is str and re.fullmatch('[0-9a-f]{64}', row['sha256']) and (type(row.get('size_bytes')) is int) and (0 < row['size_bytes'] <= 128 * 1024 ** 2), 'Invalid final database identity in content profile')
        database_profile[role] = dict(sha256=row['sha256'], size_bytes=row['size_bytes'])
    require(type(localization_bootstrap) is dict and type(localization_bootstrap.get('locale')) is str and (0 < len(localization_bootstrap['locale']) <= 128) and (type(localization_bootstrap.get('dictionary_flag')) is bool) and (type(localization_bootstrap.get('icu_data')) is dict), 'Invalid localization bootstrap in content profile')
    icu = localization_bootstrap['icu_data']
    require(type(icu.get('sha256')) is str and re.fullmatch('[0-9a-f]{64}', icu['sha256']), 'Invalid ICU identity in content profile')
    from civ6_host.runtime.native.native_resolved_content import CURRENT_EXE_SHA
    current_content_v2 = type(resolved_content) is dict and 'opaque_manager_headers' in resolved_content
    require(current_content_v2 == (process['exe_sha256'] == CURRENT_EXE_SHA),
            'Resolved-content profile version does not match the selected executable')
    if current_content_v2:
        require(set(resolved_content) == {
            'manager_address', 'provider_address', 'vector_headers_hex',
            'active_mod_handles', 'ordered_component_handles', 'opaque_manager_headers'},
            'Current resolved-content semantic fields differ from the v2 contract')
    vector_names = ('active_mod_handles', 'ordered_component_handles') if current_content_v2 else ('configured_mod_handles', 'active_mod_handles', 'ordered_component_handles')
    vectors = {}
    for name in vector_names:
        value = resolved_content.get(name) if type(resolved_content) is dict else None
        require(type(value) is list and len(value) <= 65536 and all((type(item) is int and 0 <= item < 2 ** 32 for item in value)), 'Invalid resolved-content vector in content profile')
        vectors[name] = list(value)
    opaque_headers = None
    if current_content_v2:
        candidate = resolved_content.get('opaque_manager_headers')
        require(type(candidate) is dict and set(candidate) == {'manager_plus_0x1d8'}
                and type(candidate['manager_plus_0x1d8']) is str
                and re.fullmatch('[0-9a-f]{48}', candidate['manager_plus_0x1d8']),
                'Invalid opaque current resolved-content manager header')
        headers = resolved_content.get('vector_headers_hex')
        require(type(headers) is dict and set(headers) == set(vector_names)
                and all((type(value) is str and re.fullmatch('[0-9a-f]{48}', value) for value in headers.values())),
                'Invalid current resolved-content vector header set')
        opaque_headers = dict(candidate)
    require(type(gameplay_selection) is dict and type(gameplay_selection.get('selected_paths')) is list and (type(active_state) is dict) and (type(script_manifest) is dict), 'Missing selected/active gameplay source evidence')
    selected_paths = gameplay_selection['selected_paths']
    active_count = active_state.get('active_count')
    selected_active_empty = active_state.get('selected_and_active_empty')
    require(len(selected_paths) <= 4096 and all((type(path) is str and path and (len(path) <= 4096) for path in selected_paths)) and (type(active_count) is int) and (active_count >= 0) and (type(selected_active_empty) is bool), 'Invalid selected gameplay source state')
    records = script_manifest.get('records')
    files = script_manifest.get('files')
    require(type(records) is list and len(records) <= 4096 and (type(files) is dict) and (len(files) <= 4096), 'Invalid selected gameplay source manifest')
    vectors_empty = all((not value for value in vectors.values()))
    scripts_empty = not selected_paths and selected_active_empty is True and (active_count == 0) and (not records) and (not files)
    result = dict(schema='civ6rl.official_content_profile.v2' if current_content_v2 else 'civ6rl.official_content_profile.v1', engine=dict(executable_sha256=process['exe_sha256'], gamecore_sha256=process['gamecore_module']['sha256']), final_databases=database_profile, localization_bootstrap=dict(locale=localization_bootstrap['locale'], dictionary_flag=localization_bootstrap['dictionary_flag'], icu_sha256=icu['sha256']), resolved_content_vectors=vectors, gameplay_scripts=dict(selected_path_count=len(selected_paths), active_count=active_count, selected_and_active_empty=selected_active_empty, source_records=len(records), source_files=len(files)), cross_capture_equivalence_supported=bool(vectors_empty and scripts_empty and not current_content_v2), limitations=['Content identity comparison only; no game-rule or whole-game compatibility claim.', 'Nonempty resolved component handles are not persistent IDs and cannot establish cross-capture equivalence.', 'Nonempty gameplay scripts remain unsupported.'])
    if current_content_v2:
        result['opaque_manager_headers'] = opaque_headers
        result['limitations'].append('Opaque current manager headers are retained as raw bytes and are not persistent content identifiers.')
    return result

def read_bundle(reference, *, input_profile):
    if input_profile not in ('xp1-lan', 'xp2-lan'):
        from civ6_host.runtime.capture_admission import try_bundle
        prepared = try_bundle(reference, input_profile=input_profile)
        if prepared is not None:
            return prepared
    from civ6_host.runtime.capture_profiles import profile_for_capture
    'Revalidate retained evidence and bytes; no fallback and no DLL calls.'
    from civ6_host.runtime.native.native_official_load import OfficialInputs
    from civ6_host.runtime.native.native_official_load import SINGLE_PROFILE
    from civ6_host.runtime.native.native_official_load import HOTSEAT_FOUR_PROFILE
    from civ6_host.runtime.native.native_checkpoint_provider import CORE_SHA256
    from civ6_host.runtime.native.official_save import inspect_save
    from civ6_host.runtime.native.database_capture_bundle993 import _verify_bundle
    from civ6_host.runtime.native.database_capture_bundle993 import compare_sqlite_export
    from civ6_host.runtime.native.database_capture_bundle993 import _semantic
    from civ6_host.runtime.native.native_gameplay_source_capture import recheck_selected_sources
    from civ6_host.runtime.workers.capture_phase1_bundle994 import _identity
    from civ6_host.runtime.workers.capture_phase1_bundle994 import _join_native_report
    from civ6_host.runtime.workers.capture_phase1_bundle994 import _content_semantics
    from civ6_host.runtime.workers.capture_phase1_bundle994 import _selection_semantics
    from civ6_host.runtime.native.native_resolved_content import CURRENT_EXE_SHA
    from civ6_host.runtime.native.native_gameplay_empty import stable_capture_identity
    from civ6_host.runtime.native.native_gameplay_empty import SCHEMA as EMPTY_SCHEMA
    import time
    validator_digests = _prepared_bundle_validator_digests()
    require(input_profile in ('single', 'hotseat-four', 'lan', 'xp1-lan', 'xp2-lan'), 'Unsupported official capture input family')
    if input_profile == 'xp1-lan':
        from civ6_host.runtime.xp1_bundle_inputs import XP1_LAN_PROFILE
        from civ6_host.runtime.xp1_bundle_inputs import reader_validator_digests, recheck_reader_validators
        xp1_validator_digests = reader_validator_digests()
        profile = XP1_LAN_PROFILE
    elif input_profile == 'xp2-lan':
        from civ6_host.runtime import xp2_bundle_inputs as xp2_inputs
        xp2_validator_digests = xp2_inputs.reader_validator_digests()
        profile = xp2_inputs.XP2_LAN_PROFILE
    else:
        profile = profile_for_capture(input_profile)
    reference, m = _manifest(reference)
    if input_profile == 'xp2-lan':
        xp2_inputs.validate_reference(reference)
    dependencies = {str(ROOT / reference[0]): reference[1]}
    process = m['preflight']['process']
    _identity(process, process['identity']['pid'])
    require(m.get('process_after') == process, 'Capture process identity differs across save')
    expected_core = CORE_SHA256
    if input_profile == 'xp1-lan':
        from civ6_host.runtime.xp1_bundle_inputs import validate_process
        expected_core = validate_process(process)
    elif input_profile == 'xp2-lan':
        expected_core = xp2_inputs.validate_process(process)
    require(process['gamecore_module']['sha256'] == expected_core, 'Captured engine differs from the selected official capture input family')
    engine = _resolve_resource_path(_resolve_resource_path(Path(process['gamecore_module']['path']))).resolve()
    require(_resolve_resource_path(engine).is_file() and sha(_resolve_resource_path(engine).read_bytes()) == expected_core, 'Captured engine bytes are unavailable or changed')
    dependencies[str(engine)] = expected_core
    _response_transport(m, dependencies)
    if input_profile == 'xp2-lan':
        localization, bootstrap = _localization_uncached(m, dependencies, _retained_sources=xp2_inputs.retained_localization_sources())
    else:
        localization, bootstrap = _localization_uncached(m, dependencies) if input_profile == 'xp1-lan' else _localization(m, dependencies, cache_key=reference)
    artifacts = m['artifacts']

    def artifact(name):
        return json.loads(_file(artifacts[name], dependencies, maximum=16 * 1024 ** 2))
    before, after = (artifact('observation-before.json'), artifact('observation-after.json'))
    require(before['player_id'] == after['player_id'] == 0 and type(before['turn']) is int and (1 <= before['turn'] <= 100000) and (before['turn'] == after['turn']) and (before['observation'] == after['observation']), 'Bundle needs one unchanged player-zero decision boundary')
    saved = m['save']
    require(saved.get('absent_before_request') is True and saved.get('new_load_or_reset_qualified') is False, 'Expected a newly requested, unqualified official save')
    receipt = artifact('save-receipt.json')
    ack = receipt['acknowledgement']
    require(ack.get('reason') == 'save_snapshot_requested' and ack.get('status') == 'ok' and (ack['request_id'] == saved['request_nonce']) and (ack['player_id'] == 0) and (ack['turn'] == before['turn']), 'Official save acknowledgement differs')
    extraction = saved['extraction907']
    require(extraction.get('original_rehashed_unchanged') is True, 'Official save changed during extraction')
    extract_path = _resolve_resource_path(ROOT / extraction['manifest']).resolve()
    require(extract_path.is_relative_to((ROOT / reference[0]).parent) and 0 < _resolve_resource_path(extract_path).stat().st_size <= 4 * 1024 ** 2, 'Extracted save escaped captured bundle or byte bound')
    report = json.loads(_resolve_resource_path(extract_path).read_bytes())
    dependencies[str(extract_path)] = sha(_resolve_resource_path(extract_path).read_bytes())
    save_path = extract_path.parent / 'source.Civ6Save'
    raw = _file(dict(path=str(save_path), bytes=saved['source']['bytes'], sha256=saved['source']['sha256']), dependencies)
    require(receipt['sha256'] == extraction['sha256'] == report['sha256'] == sha(raw) and receipt['bytes'] == extraction['bytes'] == report['bytes'] == len(raw), 'Save/extraction/receipt join differs')
    inspected, sections = inspect_save(raw)
    games = [s for s in sections if s.kind == 'gamecore_stream_candidate']
    require(len(games) == 1 and report['sections'] == [dict(s.receipt(), extracted_file=r['extracted_file']) for s, r in zip(sections, report['sections'])] and (len(sections) == len(report['sections'])), 'Captured GameCore stream selection differs')
    configuration, maps = _configuration(raw, m, profile.mode_name, expected_ruleset={'xp1-lan': 'RULESET_EXPANSION_1', 'xp2-lan': 'RULESET_EXPANSION_2'}.get(input_profile, 'RULESET_STANDARD'))
    from civ6_host.runtime.native.official_application_configuration import SOURCE_PATH
    from civ6_host.runtime.native.official_application_configuration import SOURCE_SHA256
    dependencies[str(ROOT / SOURCE_PATH)] = SOURCE_SHA256
    if input_profile in ('xp1-lan', 'xp2-lan'):
        from civ6_host.runtime.gameplay_active_profiles import SOURCE as EMPTY_SOURCE
        dependencies[str(ROOT / EMPTY_SOURCE[0])] = EMPTY_SOURCE[1]
    else:
        from civ6_host.runtime.native.native_gameplay_empty import SOURCE_PATH as EMPTY_PATH
        from civ6_host.runtime.native.native_gameplay_empty import SOURCE_SHA256 as EMPTY_SHA
        dependencies[str(EMPTY_PATH)] = EMPTY_SHA
    game = games[0].payload
    if input_profile == 'xp2-lan':
        xp2_inputs.validate_components(configuration, game)
    runtime = []
    for name in ('runtime-selections-before.json', 'runtime-selections-after.json'):
        r = artifact(name)
        content_capture_schema = ('civ6rl.official_resolved_content929.capture.v2'
                                  if process['exe_sha256'] == CURRENT_EXE_SHA
                                  else 'civ6rl.official_resolved_content929.capture.v1')
        _join_native_report(r['content929'], process, content_capture_schema)
        content = _content_semantics(r['content929']['snapshot'], process)
        selection = _selection_semantics(r['gameplay_selection994'], process, content)
        if input_profile == 'xp1-lan':
            from civ6_host.runtime.xp1_bundle_inputs import validate_selection_scope
            validate_selection_scope(r)
        elif input_profile == 'xp2-lan':
            xp2_inputs.validate_selection_scope(r)
        else:
            require(r['gameplay_selection994']['consumer_core_matches_base_proof'] is True, 'Gameplay consumer does not match the supported Base source')
        active = r['gameplay_active_list']
        _join_native_report(active, process, EMPTY_SCHEMA)
        active_identity = stable_capture_identity(active)
        if input_profile == 'xp2-lan':
            require(_selection_semantics(active['selection'], process, content) == selection, 'XP2 selected and retained active script witnesses differ')
        else:
            require(_selection_semantics(active['selection'], process, content) == selection and active.get('selected_and_active_empty') is True and (selection['selected_paths'] == []), 'Nonempty gameplay selection/activation/includes are not yet supported by this Load adapter')
        runtime.append((selection, active_identity))
    expected_paths = list(xp2_inputs.SELECTED_PATHS) if input_profile == 'xp2-lan' else []
    require(runtime[0] == runtime[1] and m['runtime_selections']['selected_paths'] == expected_paths, 'Captured script state changed around save')
    if input_profile == 'xp1-lan':
        from civ6_host.runtime.xp1_bundle_inputs import validate_summary_scope
        validate_summary_scope(m['runtime_selections'])
    elif input_profile == 'xp2-lan':
        xp2_inputs.validate_summary_scope(m['runtime_selections'])
    script_ref = m['selected_gameplay_sources']['manifest']
    scripts = json.loads(_file(script_ref, dependencies, maximum=4 * 1024 ** 2))
    if input_profile == 'xp2-lan':
        xp2_inputs.validate_scripts(scripts, _resolve_resource_path(Path(script_ref['path'])).parent, process, dependencies)
    else:
        require(scripts['selected_paths'] == scripts['records'] == [] and scripts['files'] == {}, 'Captured gameplay source list is not the observed empty list')
        recheck_selected_sources(scripts, _resolve_resource_path(Path(script_ref['path'])).parent, deadline=time.monotonic() + 15)
    databases = {}
    db_witness = m['active_database_witness']
    sides = []
    for name in ('before_manifest', 'after_manifest'):
        pin = db_witness[name]
        witness_limit = 4 * 1024 ** 2
        if input_profile == 'xp1-lan':
            from civ6_host.runtime.xp1_bundle_inputs import DATABASE_WITNESS_MAX_BYTES
            witness_limit = DATABASE_WITNESS_MAX_BYTES
        elif input_profile == 'xp2-lan':
            witness_limit = xp2_inputs.DATABASE_WITNESS_MAX_BYTES
        _file(pin, dependencies, maximum=witness_limit)
        path = _resolve_resource_path(Path(pin['path']))
        verified_journal = _verify_bundle(path.parent)
        journal = verified_journal.manifest
        require(journal['connections'] == ['gameplay', 'configuration'] and journal['expected_player_id'] == 0 and (journal['expected_turn'] == before['turn']), 'Active database boundary differs')
        sides.append((path.parent, journal, verified_journal))
        for row in journal['files']:
            dependencies[str(path.parent / row['path'])] = row['sha256']
    require([_semantic(x) for x in sides[0][1]['passes'][0]] == [_semantic(x) for x in sides[1][1]['passes'][0]], 'Active databases changed across save')
    for role in ('configuration', 'gameplay'):
        row = m['export_matches'][role]['copy']
        raw_db = _file(row, dependencies)
        require(raw_db.startswith(b'SQLite format 3\x00'), 'Invalid database copy')
        match = compare_sqlite_export(sides[1][0], row['path'], connection=role, _verified=sides[1][2])
        require(match == m['export_matches'][role]['comparison'], 'Recorded export comparison differs')
        databases[role] = dict(path=row['path'], sha256=row['sha256'], size_bytes=row['bytes'])
    databases['localization'] = localization
    content_profile = build_content_profile(process=process, databases=databases, localization_bootstrap=bootstrap, resolved_content=runtime[0][0]['content'], gameplay_selection=runtime[0][0], active_state=dict(active_count=active['state']['active_count'], selected_and_active_empty=active['selected_and_active_empty']), script_manifest=scripts)
    state = before['observation']
    fields = ('id', 'type', 'x', 'y', 'damage', 'moves')
    expected = dict(turn=before['turn'], width=state['map']['width'], height=state['map']['height'], player_id=0, gold=state['economy']['gold'], city_count=len(state['cities']), units=sorted(({k: u[k] for k in fields} for u in state['units']), key=lambda u: u['id']))
    fixture = dict(schema='civ6rl.native-fixture.v1', purpose='diagnostic exact captured official bundle', eligible_for_training=False, databases=databases, localization_bootstrap=bootstrap, official_bundle=dict(path=reference[0], sha256=reference[1]), input_profile=input_profile)
    inputs = OfficialInputs(configuration, game, maps, profile, official_bundle=reference)
    require(_prepared_bundle_validator_digests() == validator_digests, 'Prepared bundle validator sources changed during admission')
    if input_profile == 'xp1-lan':
        recheck_reader_validators(xp1_validator_digests)
        dependencies.update(xp1_validator_digests)
    elif input_profile == 'xp2-lan':
        xp2_inputs.recheck_reader_validators(xp2_validator_digests)
        dependencies.update(xp2_validator_digests)
    bundle = PreparedBundle(reference, inputs, before['turn'], engine, fixture, dependencies, expected, content_profile)
    if input_profile in ('xp1-lan', 'xp2-lan'):
        return _remember_prepared_bundle(bundle, input_profile, validator_digests, _token=_PARENT_ADMISSION_TOKEN, _input_only=True)
    return _remember_prepared_bundle(bundle, input_profile, validator_digests, _token=_PARENT_ADMISSION_TOKEN)

def prepare_official_bundle(reference, *, input_profile, output_directory, _admitted_bundle=None):
    require(input_profile not in ('xp1-lan', 'xp2-lan'), 'Expansion inputs do not admit official fixture preparation or native Load')
    bundle = read_bundle(reference, input_profile=input_profile) if _admitted_bundle is None else _reuse_prepared_bundle(_admitted_bundle, reference, input_profile)
    directory = _resolve_resource_path(_resolve_resource_path(Path(output_directory))).resolve()
    require(directory.is_relative_to(ROOT / 'work') and (not _resolve_resource_path(directory).exists()), 'Use a fresh private bundle fixture directory')
    directory.mkdir(parents=True)
    path = directory / 'manifest.json'
    path.write_text(json.dumps(bundle.fixture, indent=2) + '\n', encoding='utf8')
    from civ6_host.runtime.native.native_host import validate_fixture
    from civ6_host.runtime.native.native_localization import validate_localization
    validate_localization(validate_fixture(path))
    return (bundle, path)

def validate_fixture(bundle, path):
    from civ6_host.runtime.xp1_saved_load import validate_private_bootstrap
    from civ6_host.runtime.native.native_host import validate_fixture as read_fixture
    from civ6_host.runtime.native.native_localization import validate_localization
    actual = read_fixture(path)
    validate_localization(actual)
    require(actual.get('official_bundle') == bundle.fixture['official_bundle'] and actual.get('input_profile') == bundle.fixture['input_profile'] and (validate_private_bootstrap(actual, bundle.fixture['localization_bootstrap'], private_root=_resolve_resource_path(Path(path)).resolve().parent) if bundle.fixture['input_profile'] in ('xp1-lan', 'xp2-lan') else actual.get('localization_bootstrap') == bundle.fixture['localization_bootstrap']) and (set(actual['databases']) == set(bundle.fixture['databases'])), 'Worker fixture belongs to another bundle')
    for role, expected in bundle.fixture['databases'].items():
        row = actual['databases'][role]
        require(row['sha256'] == expected['sha256'] and row['size_bytes'] == expected['size_bytes'] and (_resolve_resource_path(_resolve_resource_path(Path(row['path']))).resolve().parent == _resolve_resource_path(_resolve_resource_path(Path(path))).resolve().parent) and (_resolve_resource_path(_resolve_resource_path(Path(row['path']))).resolve() != _resolve_resource_path(_resolve_resource_path(Path(expected['path']))).resolve()), 'Worker requires exact, private captured databases')

def validate_inputs(inputs, *, _input_only=False):
    from civ6_host.runtime.capture_profiles import LAN_PROFILE
    if inputs.profile is LAN_PROFILE and inputs.checkpoint is not None:
        from civ6_host.runtime.network_checkpoint import validate_inputs as validate_lan_checkpoint
        return validate_lan_checkpoint(inputs)
    from civ6_host.runtime.native.official_save import inspect_save
    require(inputs.checkpoint is None, 'Checkpoint and official bundle are mutually exclusive')
    reference, m = _manifest(inputs.official_bundle)
    folder = (ROOT / m['save']['extraction907']['manifest']).parent
    raw = _resolve_resource_path(folder / 'source.Civ6Save').read_bytes()
    expected_ruleset = 'RULESET_STANDARD'
    if _input_only:
        from civ6_host.runtime.xp1_bundle_inputs import XP1_LAN_PROFILE
        from civ6_host.runtime.xp1_saved_load import REFERENCE
        from civ6_host.runtime import xp2_bundle_inputs as xp2_inputs
        require(_input_only is True, 'Input-only save validation flag must be Boolean')
        if inputs.profile is xp2_inputs.XP2_LAN_PROFILE:
            xp2_inputs.validate_reference(reference)
            xp2_inputs.validate_components(inputs.configuration, inputs.game)
            require(inputs.checkpoint is None, 'XP2 candidate checkpoints are not yet admitted')
            expected_ruleset = 'RULESET_EXPANSION_2'
        else:
            require(inputs.profile is XP1_LAN_PROFILE and reference == REFERENCE, 'Input-only save validation requires an exact admitted private capture')
            expected_ruleset = 'RULESET_EXPANSION_1'
    configuration, maps = _configuration(raw, m, inputs.profile.mode_name, expected_ruleset=expected_ruleset)
    require(inputs.configuration == configuration and inputs.map_values == maps, 'Loaded bundle configuration differs')
    _, sections = inspect_save(raw)
    games = [s for s in sections if s.kind == 'gamecore_stream_candidate']
    require(len(games) == 1 and inputs.game == games[0].payload, 'Loaded bundle GameCore bytes differ')

def validate_closure_profile(closure):
    if closure.get('input_profile') in ('lan', 'xp1-lan'):
        from civ6_host.runtime.network_checkpoint import validate_closure as validate_lan_checkpoint_closure
        return validate_lan_checkpoint_closure(closure)
    explicit = closure.get('official_bundle')
    if explicit is None:
        require(closure.get('database_profile') == 'official-cache-phase23-diagnostic', 'Historical database profile differs')
    else:
        require(closure.get('database_profile') == DATABASE_PROFILE and closure.get('resume_checkpoint') is None and (closure.get('checkpoint_on_close', False) is False), 'Explicit bundle cannot fall back to historical databases or checkpoints')
        normalize_reference(explicit)
        require(type(closure.get('initial_turn')) is int and 1 <= closure['initial_turn'] <= 100000, 'Captured initial turn is required')

def verify_loaded_script_state(owner):
    """Check the captured empty selection after the actual Load/postload path.

    This does not demand a history for absent scripts. It also does not equate
    successful Load with whole-game fidelity or support a nonempty script list.
    """
    from civ6_host.runtime.native.native_gameplay_empty import read_gameplay_state
    require(owner.inputs.official_bundle is not None and owner.captured_bundle.inputs is owner.inputs, 'Captured script state needs its exact Load owner')
    require(owner.prefix.gameplay_scripts.count() == 0, 'Loaded host script selection differs from the captured empty list')
    topology = owner.topology(game_required=True)
    state = read_gameplay_state(owner.runtime.read, owner.core._handle, expected_inner=topology['inner'], expected_auxiliary_vtable=C.addressof(owner.host.aux_vtable))
    require(state['active_list_empty'] is True and state['active_count'] == 0, 'Loaded native gameplay scripts differ from captured active-list absence')
    owner.emit('official_bundle_empty_gameplay_after_load', bundle_reference=owner.inputs.official_bundle, state=state, current_selection_and_active_list_match=True, historical_execution_claimed=False, strategic_training_ready=False)
    return state
