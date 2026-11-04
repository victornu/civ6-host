"""Bounded diagnostic: restore/roundtrip owned configuration B, never GameLoad.

No DLL is loaded at import and there is no executable native CLI. The reviewed
worker may call run_configuration_only immediately after its existing verified
DllCreateGameContext. This function owns Init and successful Destroy; its caller
must not execute the ordinary worker Init/Destroy path again. Errors after Init
entry are fatal, matching the disposable worker's existing failure policy.
"""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import ctypes as C
import hashlib
import json
import os
from pathlib import Path
import struct
import time
ROOT = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_checkpoint_configuration_only.py')))).resolve().parents[1]
from civ6_host.runtime.native import native_checkpoint_provider as provider
from civ6_host.runtime.native.native_application_configuration import NativeApplicationConfiguration
from civ6_host.runtime.native.native_host import initialize_context
from civ6_host.runtime.native.native_host import finish_database
from civ6_host.runtime.native.native_host import validate_fixture
AUDIT_PATH = 'work/native-checkpoint-prepared-restore-audit349.json'
AUDIT_SHA = 'f9ed67a31787eadb184e093a7587b67c9737ef5687e058f4a138632d34ff6af9'
WITNESS_PATH = 'evidence/native-newgame-script-prefix352.json'
WITNESS_SHA = '87eeaa8d9a5d174d2930fce0d47b0a854c2737c71380f165b29ace67496bd8fc'
MANIFEST_PATH = 'work/native-checkpoints/57550309b836401898464888261ccb9f/round1.checkpoint.json'
MANIFEST_SHA = '8b6db0574d5e8a5288936a17a308b30db918f53bf63a94f862edfb670ffba53d'
SIDECAR_SHA = '9d6dd5f7c4ca59e95a97b09df342634b20016eccaf5f86d03cb6e0f7ff6cc79b'
SIDECAR_SIZE = 15053
MAX_BYTES = 32 * 1024 * 1024
MAX_CALLS = 1000000
FATAL_EXIT_CODE = 88
_RETAINED = {}

def sha(data):
    return hashlib.sha256(data).hexdigest()

def _json_pin(relative, expected):
    raw = _resolve_resource_path(ROOT / relative).read_bytes()
    if sha(raw) != expected:
        raise ValueError('Changed source/input pin: ' + relative)
    return json.loads(raw)

def verify_source():
    proof = provider.verify_source()
    audit = _json_pin(AUDIT_PATH, AUDIT_SHA)
    if audit.get('schema') != 'civ6rl.native_checkpoint_prepared_restore_audit.v1' or audit['images']['core']['sha256'] != provider.CORE_SHA256 or audit['native_execution'] is not False or (audit['contract']['create_B_before_prepare']['source_possible'] is not True):
        raise ValueError('Fresh pre-Prepare ownership source differs')
    witness = _json_pin(WITNESS_PATH, WITNESS_SHA)
    if witness['dll_sha256'] != provider.CORE_SHA256:
        raise ValueError('Sidecar source Core differs')
    return (proof, witness)

def read_pinned_sidecar():
    """This first proposal only admits the immutable run352 sidecar, not a save picker."""
    doc = _json_pin(MANIFEST_PATH, MANIFEST_SHA)
    if doc.get('schema') != 'civ6rl.native_checkpoint_components.v1' or doc['core_sha256'] != provider.CORE_SHA256 or doc['completed_rounds'] != 1 or (doc['eligible_for_training'] is not False) or (doc['full_civ6save_container'] is not False) or (doc['configuration_receipt']['proof_sha256'] != provider.PROOF_SHA256):
        raise ValueError('Configuration component provenance differs')
    row = doc['components']['application_configuration']
    relative = _resolve_resource_path(Path(row['path']))
    if relative.is_absolute() or '..' in relative.parts:
        raise ValueError('Configuration component must have a contained relative path')
    path = _resolve_resource_path(ROOT / relative).resolve()
    folder = _resolve_resource_path(ROOT / MANIFEST_PATH).resolve().parent
    if path.parent != folder or path.name != 'round1.configuration.raw':
        raise ValueError('Configuration component is outside its pinned checkpoint folder')
    data = _resolve_resource_path(path).read_bytes()
    if type(row['bytes']) is not int or row['bytes'] != SIDECAR_SIZE or len(data) != SIDECAR_SIZE or (row['sha256'] != SIDECAR_SHA) or (sha(data) != SIDECAR_SHA):
        raise ValueError('Configuration sidecar length or complete hash differs')
    return data

def prepare_private_fixture(source_manifest):
    """Optional parent-side filesystem preparation; launches no worker/native code."""
    from civ6_host.runtime.native.native_probe import prepare_init_fixture_copies
    return prepare_init_fixture_copies(_resolve_resource_path(Path(source_manifest)), 1)

def validate_private_fixture(manifest_path, witness):
    path = _resolve_resource_path(_resolve_resource_path(Path(manifest_path))).resolve()
    doc = validate_fixture(path)
    isolation = doc.get('isolation', {})
    if isolation.get('copies_created_before_worker_launch') is not True or type(isolation.get('worker_count')) is not int or isolation['worker_count'] != 1 or (type(isolation.get('worker_index')) is not int) or (isolation['worker_index'] != 0):
        raise ValueError('A single fresh private Init fixture is required')
    source = witness['native_fixture_isolation']
    if isolation.get('source_manifest_sha256') != source['source_manifest_sha256'] or _resolve_resource_path(_resolve_resource_path(Path(isolation['source_manifest_path']))).resolve() != _resolve_resource_path(_resolve_resource_path(Path(source['source_manifest_path']))).resolve():
        raise ValueError('Private database source differs from the sidecar witness')
    expected = source['workers'][0]['databases']
    if set(doc['databases']) != set(expected):
        raise ValueError('Private database set differs from the sidecar witness')
    paths = set()
    for name, row in doc['databases'].items():
        target = _resolve_resource_path(_resolve_resource_path(Path(row['path']))).resolve()
        if target.parent != path.parent or target in paths or target == _resolve_resource_path(_resolve_resource_path(Path(expected[name]['copy_path']))).resolve() or (target == _resolve_resource_path(_resolve_resource_path(Path(expected[name]['source_path']))).resolve()) or (row['sha256'] != expected[name]['sha256']) or (sha(_resolve_resource_path(target).read_bytes()) != expected[name]['sha256']):
            raise ValueError('Private database identity/copy differs: ' + name)
        paths.add(target)
    return path

def _fatal(error):
    try:
        os.write(2, (json.dumps({'stage': 'configuration_only_fatal', 'error': str(error)[:512], 'retry_permitted': False, 'cleanup_guessed': False}) + '\n').encode())
    finally:
        from civ6_host.runtime.native.native_checkpoint_stream import terminate_worker
        terminate_worker(FATAL_EXIT_CODE)

class _NativeBackend:
    """Shared Base/XP1 configuration lifecycle; saved Load has separate admission."""

    def __init__(self, core, context, fixture, dll_directory, profile, proof, emit):
        from civ6_host.runtime.native.native_core_context_profiles import NativeCoreContextProfile
        if type(profile) is not NativeCoreContextProfile or (profile.ruleset, profile.mode) not in (('base', 'init'), ('xp1', 'context'), ('xp2', 'context')) or type(context) is not int or (context <= 0) or (type(getattr(core, '_handle', None)) is not int) or (core._handle <= 0) or hasattr(core, '_diagnostic_host') or hasattr(core, '_civ6rl_application_configuration'):
            raise ValueError('Expected a fresh admitted configuration context, with no prior host/provider')
        self.core, self.context, self.fixture, self.dll_directory = (core, context, fixture, _resolve_resource_path(Path(dll_directory)))
        self.profile, self.emit = (profile, emit)
        from civ6_host.runtime.configuration_profiles import configuration_abi
        self.configuration_abi = configuration_abi(profile.core_sha256)
        if self.configuration_abi.load.ruleset != profile.ruleset or proof['images']['core']['sha256'] != profile.core_sha256:
            raise ValueError('Configuration provider/context engine identities disagree')
        self.runtime = provider._Runtime()
        self.runtime.image(core._handle, proof)
        if os.path.normcase(str(self.dll_directory)) != os.path.normcase(str(profile.shared_dependency_directory)):
            raise ValueError('Dependency directory differs from pinned shared dependencies')
        self.thread = self.runtime.thread()
        self.host = self.owner = None
        self.init_entered = self.destroyed = False
        self.destroy = core.DllDestroyGameContext
        self.destroy.argtypes, self.destroy.restype = ([C.c_void_p], None)
        if C.cast(self.destroy, C.c_void_p).value != core._handle + profile.destroy_context_rva:
            raise ValueError('Actual Destroy export differs from lifecycle proof')

    def state(self, initialized):
        from civ6_host.runtime.native.native_core_context_profiles import validate_loaded_context
        if self.runtime.thread() != self.thread or self.destroyed:
            raise ValueError('Wrong thread or destroyed context')
        base, read = (self.core._handle, self.runtime.read)
        getter = validate_loaded_context(self.profile, base, self.context, read)
        actual = C.WINFUNCTYPE(C.c_bool, C.c_void_p)(getter)(self.context)
        q = lambda p: struct.unpack('<Q', read(p, 8))[0]
        inner = q(self.context + 8)
        if not inner or q(inner) != base + self.configuration_abi.load.inner_vtable_rva or q(inner + 96) != 0 or (actual is not initialized):
            raise ValueError('Configuration-only context must have no Game and the expected Init state')
        return (inner, q(inner + 3456 + 128))

    def initialize(self):
        candidate_options = {}
        if getattr(self, '_saved_load_candidate', False):
            if getattr(self, 'captured_bundle', None) is None:
                raise ValueError('XP1 Init candidate lost its captured input owner')
            candidate_options['candidate_bundle'] = self.captured_bundle
        self.init_entered = True
        self.host = initialize_context(self.core, self.context, self.fixture, self.dll_directory, self.emit, context_profile=self.profile, **candidate_options)

    def clone(self):
        self.owner = NativeApplicationConfiguration(self.core, self.context, emit=self.emit, core_sha256=self.profile.core_sha256)
        self.core._civ6rl_application_configuration = self.owner
        self.host.application_configuration = self.owner

    def restore(self, data, *, expected_sha256=None):
        if expected_sha256 is None:
            if self.profile.ruleset != 'base':
                raise ValueError('Expansion configuration restore requires an explicit input digest')
            expected_sha256 = SIDECAR_SHA
        return provider.restore_provider(self.core, self.context, self.owner, data, expected_sha256=expected_sha256, max_bytes=MAX_BYTES, max_calls=MAX_CALLS)

    def serialize(self):
        return provider.serialize_provider(self.core, self.context, self.owner, max_bytes=MAX_BYTES, max_calls=MAX_CALLS)

    def close_owner(self):
        self.owner.close()
        del self.core._civ6rl_application_configuration
        self.host.application_configuration = None

    def destroy_context(self, *, loaded_lifetime=None):
        if loaded_lifetime is not None:
            from civ6_host.runtime.xp1_loaded_lifetime import require_lifetime
            require_lifetime(loaded_lifetime, self).before_destroy(self)
        if self.profile.ruleset in ('xp1', 'xp2'):
            if loaded_lifetime is None and self.owner is not None and (not self.owner.closed):
                raise ValueError('XP1 context destruction requires its owned provider closed')
            if getattr(self.host, 'context_teardown_receipt', {}).get('installed') is not True:
                raise ValueError('XP1 context destruction requires verified teardown callbacks')
        self.emit('before_destroy')
        started = time.perf_counter()
        self.destroy(self.context)
        self.destroyed = True
        if loaded_lifetime is not None:
            loaded_lifetime.after_destroy(self)
        self.emit('destroyed', operation_seconds=time.perf_counter() - started, configuration_only=loaded_lifetime is None)

    def finish_database(self):
        return finish_database(self.host, self.emit)

def _emit_roundtrip_diagnostic(data, output, restore_receipt, serialize_receipt, emit):
    """Observe bounded bytes before the equality assertion; no success claim."""
    if type(data) is not bytes or type(output) is not bytes:
        raise RuntimeError('Native provider roundtrip differs from every pinned sidecar byte')
    if len(data) > 64 * 1024 or len(output) > 64 * 1024:
        raise RuntimeError('Native provider roundtrip diagnostic exceeds 64 KiB')
    emit('native_configuration_only_comparison', input_bytes=len(data), input_sha256=sha(data), output_bytes=len(output), output_sha256=sha(output), output_hex=output.hex(), restore=restore_receipt, serialize=serialize_receipt, diagnostic_byte_limit=64 * 1024, comparison_only=True, complete_game_restore_validated=False, eligible_for_training=False)

def _roundtrip(backend, data, emit, *, fatal=_fatal):
    """Private pure orchestration seam for tests; production always uses _NativeBackend."""
    backend.state(False)
    entered = False
    try:
        entered = True
        backend.initialize()
        identity = backend.state(True)
        backend.clone()
        if backend.state(True) != identity:
            raise RuntimeError('Provider construction changed context/A identity')
        restore_receipt = backend.restore(data)
        if backend.state(True) != identity:
            raise RuntimeError('Provider restore changed context/A identity')
        output, serialize_receipt = backend.serialize()
        _emit_roundtrip_diagnostic(data, output, restore_receipt, serialize_receipt, emit)
        raw_equal = output == data
        comparison = {'raw_bytes_equal': raw_equal, 'normalized_entry_count': 0, 'comparison_basis': 'exact-bytes'}
        if not raw_equal:
            from civ6_host.runtime.native.native_checkpoint_configuration_normalization import compare_configuration_streams
            try:
                comparison = compare_configuration_streams(data, output)
            except (ValueError, RuntimeError) as error:
                raise RuntimeError('Native provider roundtrip differs from every pinned sidecar byte outside the verified normalization') from error
        if backend.state(True) != identity:
            raise RuntimeError('Provider serialization changed context/A identity')
        emit('native_configuration_only_roundtrip', bytes=len(output), sha256=sha(output), restore=restore_receipt, serialize=serialize_receipt, exact_bytes_equal=raw_equal, configuration_comparison=comparison, game_created=False, game_load_called=False, prepare_called=False, complete_game_restore_validated=False, eligible_for_training=False)
        backend.close_owner()
        backend.state(True)
        backend.destroy_context()
        backend.finish_database()
        result = {'context_destroyed': True, 'configuration_roundtrip_equal': True, 'exact_bytes_equal': raw_equal, 'configuration_comparison': comparison, 'bytes': len(output), 'sha256': sha(output), 'game_load_called': False, 'prepare_called': False, 'eligible_for_training': False}
        emit('native_configuration_only_completed', **result)
        return result
    except BaseException as error:
        if entered:
            fatal(error)
            raise RuntimeError('Fatal implementation unexpectedly returned') from error
        raise

def run_configuration_only(core, context, *, fixture, dll_directory, profile, emit):
    """Call ONLY in the existing fresh disposable Init worker after its factory.

    The parent must retain its existing verified loader/supervisor/limits and
    provide a single newly copied fixture. On success this owns Destroy and DB
    shutdown. It must replace, not be followed by, ordinary worker Init/Destroy.
    """
    if not callable(emit):
        raise ValueError('An event emitter is required')
    proof, witness = verify_source()
    data = read_pinned_sidecar()
    fixture = validate_private_fixture(fixture, witness)
    key = (id(core), context)
    if key in _RETAINED:
        raise ValueError('Configuration-only context may be attempted only once')
    backend = _NativeBackend(core, context, fixture, dll_directory, profile, proof, emit)
    _RETAINED[key] = backend
    return _roundtrip(backend, data, emit)
