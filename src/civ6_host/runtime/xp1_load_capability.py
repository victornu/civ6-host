"""Captured XP1 inputs for the shared EXE absent-numeric capability service.

The historical XP1 HOTSEAT proof supplies catalogue equality and native getter
bytes only. LAN uses its separately verified EXE convergence branch. No license
response, live EXE registry, networking or public session admission is supplied.
"""
import ctypes as C
from contextlib import contextmanager
from dataclasses import dataclass
import struct
from pathlib import Path

from .configuration_profiles import XP1_CORE_SHA256, configuration_abi, _source, _body
from .saved_load_profiles import XP2_CORE_SHA256
from .xp1_saved_load import REFERENCE, validate_candidate_inputs
from .xp1_saved_init import DATABASE_PINS, database_input_binding

SOURCE = ('work/native-xp1-capability895/capture895v3.json',
          '2f520f4cd0069f2dc34dfcc449e8bde5cccb8310a090b8c0f478afcc4cc7a667')
CALLER = ('work/native-xp1-newgame894/capability894.json',
          '70de00a08b6b2202856764e62c3d8500fad061cf6c24c5e0b297db17d88ae9ed')
CONVERGENCE = ('work/host-extensions/xp1-capability-static/lan-vector-convergence.json',
               '2def3ce66b37a4c4402bd8272182edaaca5de9d03fc9d30bf9b7b70ef42d5e0f')
EXE_SHA = 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63'


def source_profile(backend=None, *, core_sha256=XP1_CORE_SHA256):
    if backend is not None:
        return _receipt(backend).profile
    if core_sha256 == XP2_CORE_SHA256:
        from .xp2_load_options_capability_profile import capability_profile
        return capability_profile()
    if core_sha256 != XP1_CORE_SHA256:
        raise ValueError('Unknown capability source profile')
    from .native.native_app_ownership import verify_producer_source
    from .native.native_host_capability_status import verify_source
    p, caller = _source(SOURCE), _source(CALLER)
    if (p['schema'] != 'civ6rl.native_xp1_capability895.source.v1'
            or p['xp1_sha256'] != XP1_CORE_SHA256 or p['exe_sha256'] != EXE_SHA
            or p['native_execution'] is not False or p['eligible_for_training'] is not False
            or p['source_validation']['xp1_catalogue_is_exact_named_subset_of_base'] is not True
            or caller['xp1_sha256'] != XP1_CORE_SHA256 or caller['exe_sha256'] != EXE_SHA
            or caller['abi'] != 'uint32(host*, uint32 player, uint32 capability)'
            or caller['result_implemented'] is not False or caller['host_global_rva'] != 0x9F2640
            or caller['caller']['total_length'] != 534
            or caller['exe_target']['fragments'][0]['raw_sha256']
                != verify_source()['exe_functions']['host_168_callback']['code_sha256']):
        raise ValueError('XP1 capability caller/catalogue source identity changed')
    for ref in p['parents'].values():
        _source((ref['path'], ref['sha256']))
    rows = p['catalogue_rows']
    producer = verify_producer_source()
    admitted = frozenset(producer['closed_base_hotseat_profile']['admitted_capability_hashes'])
    allowed = frozenset(row['hash_u32'] for row in rows)
    if (len(rows) != 92 or len(allowed) != 92 or not allowed <= admitted
            or p['contract']['fixed_input_count'] != 65 or p['contract']['present_input_count'] != 35
            or p['contract']['registry_domain'] != 0x62D100F0
            or p['configuration_vtable_rva'] != configuration_abi(XP1_CORE_SHA256).vtable_rva
            or p['slots']['0x58']['target_rva'] != configuration_abi(XP1_CORE_SHA256).lookup_rva
            or p['slots']['0x68']['target_rva'] != 0x845600
            or p['contract']['game_root_key'] != 0x871D5B63
            or p['contract']['game_root_key_rva'] != 0x9F3D20
            or p['contract']['mode_key'] != 0x0623E593
            or p['xp1_mode_key_initializer']['global_rva'] != 0x9F3D6C):
        raise ValueError('XP1 capability catalogue/owned provider source differs')
    _body(caller['caller'])
    for body in p['live_xp1_bodies'].values():
        _body(body)
    return p, caller


def _candidate_spec(backend):
    core = getattr(getattr(backend, 'profile', None), 'core_sha256', XP1_CORE_SHA256)
    if core == XP2_CORE_SHA256:
        from .xp2_bundle_inputs import REFERENCE as reference, validate_candidate_inputs as validate
        from .xp2_saved_init import DATABASE_PINS as databases, database_input_binding as binding
        from .xp2_load_options_capability_profile import SOURCE as source
        return core, reference, validate, databases, binding, 'xp2-lan', source, source
    if core == XP1_CORE_SHA256:
        return core, REFERENCE, validate_candidate_inputs, DATABASE_PINS, database_input_binding, 'xp1-lan', SOURCE, CALLER
    raise ValueError('Unknown saved-Load capability candidate')


def _owner(backend, application, captured_bundle):
    from .native.native_application_configuration import NativeApplicationConfiguration
    core, reference, *_ = _candidate_spec(backend)
    if (getattr(backend, '_saved_load_candidate', False) is not True
            or backend.profile.core_sha256 != core
            or backend.captured_bundle is not captured_bundle
            or backend.inputs is not captured_bundle.inputs or captured_bundle.reference != reference
            or backend.owner is not application or type(application) is not NativeApplicationConfiguration
            or application._configuration_abi is not configuration_abi(core)
            or backend.host.application_configuration is not application
            or application.base != backend.core._handle or application.context != backend.context):
        raise ValueError('XP1 capability requires the retained captured application owner')
    application._check_guard()


def captured_catalogue(backend, application, manifest, captured_bundle, required_mode):
    from .lan_capabilities import LAN
    from .native.native_official_bundle import _reuse_prepared_bundle
    _owner(backend, application, captured_bundle)
    core, reference, validate, databases, binding, family, *_ = _candidate_spec(backend)
    validate(backend.inputs, captured_bundle)
    _reuse_prepared_bundle(captured_bundle, reference, family, _input_only=True)
    if manifest is not backend.host.manifest or required_mode != LAN:
        raise ValueError('XP1 ownership catalogue requires its exact private LAN owner')
    binding(captured_bundle, backend.host,
        manifest['databases']['configuration']['path'], manifest['databases']['gameplay']['path'],
        Path(backend.fixture).resolve().parent)
    p, _ = source_profile(backend)
    return {'fixture': {'gameplay_database_sha256': databases['gameplay']['sha256']},
            'capabilities': p['catalogue_rows'], 'admitted_count':97 if core == XP2_CORE_SHA256 else 92,
            'profile_name':'official-captured-'+family+'-candidate'}


def verify_candidate_live(backend):
    _owner(backend, backend.owner, backend.captured_bundle)
    p, caller = source_profile(backend)
    base, read = backend.core._handle, backend.runtime.read
    if read(base + caller['host_global_rva'], 8) != backend.host.pointer.to_bytes(8, 'little'):
        raise ValueError('XP1 capability global points to another host')
    for rva, expected in _receipt(backend).live_code:
        if read(base + rva, len(expected)) != expected:
            raise ValueError('XP1 capability live caller/getter changed')
    *_, source, caller = _candidate_spec(backend)
    return {'core_consumer_source_sha256': caller[1], 'provider_source_sha256': source[1]}


def read_mode(application, backend):
    """The shared mode algorithm, bound to the actual XP1 owned B provider."""
    from .native import native_configuration_finalization as config
    _owner(backend, application, backend.captured_bundle)
    p, _ = source_profile(backend)
    abi = application._configuration_abi
    base, read, call = application.base, application.read, application.call
    table = base + abi.vtable_rva
    getter = p['slots']['0x68']['target_rva']
    if (config._qword(read, application.pointer) != table
            or config._qword(read, table + 0x58) != base + abi.lookup_rva
            or config._qword(read, table + 0x68) != base + getter
            or struct.unpack('<I', config._read(read, base + abi.root_key_rva, 4))[0] != 0x871D5B63
            or struct.unpack('<I', config._read(read, base + p['xp1_mode_key_initializer']['global_rva'], 4))[0] != 0x0623E593):
        raise ValueError('XP1 live application mode provider changed')
    child = config._invoke(call, base + abi.lookup_rva, C.c_void_p, application.pointer, (C.c_uint32,), 0x871D5B63)
    if not child:
        raise ValueError('XP1 live GAME_ROOT is absent')
    raw = config._read(read, child, 24)
    target = struct.unpack_from('<Q', raw, 8)[0]
    if (struct.unpack_from('<H', raw)[0] != 10 or struct.unpack_from('<I', raw, 20)[0] != 0x05000000
            or not target or config._qword(read, target) != table):
        raise ValueError('XP1 GAME_ROOT is not an owned native map')
    value = config._invoke(call, base + getter, C.c_void_p, target, (C.c_uint32,), 0x0623E593)
    if not value:
        raise ValueError('XP1 nonnullable mode getter returned NULL')
    raw = config._read(read, value, 24)
    tag, flags = struct.unpack_from('<H', raw)[0], struct.unpack_from('<I', raw, 20)[0]
    return struct.unpack_from('<I', raw, 8)[0] if tag <= 21 and (0x30002e >> tag) & 1 and not flags & (1 << 29) else 0


def candidate_details(backend, player, capability):
    from .native.native_host_capability_status import request_details
    _owner(backend, backend.owner, backend.captured_bundle)
    details = request_details(player, capability, candidate_backend=backend)
    core, reference, _, databases, _, family, source, caller = _candidate_spec(backend)
    if core == XP2_CORE_SHA256:
        details = {**details, 'base_catalogue_name':None, 'base_catalogue_sha256':None,
                   'catalogue_name':next((r['name'] for r in source_profile(backend)[0]['catalogue_rows']
                                          if r['hash_u32']==capability),None),
                   'catalogue_source_sha256':source[1]}
    return {**details, 'core_consumer_source_sha256': caller[1],
            'catalogue_equality_source_sha256': source[1],
            **({'xp1_catalogue_equality_source_sha256':source[1]} if core == XP1_CORE_SHA256 else {}),
            'catalogue_database_sha256': databases['gameplay']['sha256'],
            'captured_bundle_sha256': reference[1], 'candidate_family':family}


def validate_lan_candidate(application, captured_bundle, backend):
    from .lan_capabilities import LAN
    _owner(backend, application, captured_bundle)
    if (captured_bundle.inputs.profile.mode_name != 'LAN'
            or captured_bundle.expected_readback['player_id'] != 0
            or read_mode(application, backend) != LAN):
        raise ValueError('XP1 LAN projection requires its captured and current native LAN mode')
    return convergence_source()


def convergence_source():
    """Require independent POD-copy closure; never transfer old vector values."""
    proof = _source(CONVERGENCE)
    copy, cleanup, consumer, result = (proof[key] for key in
        ('copy_contract', 'cleanup_contract', 'consumer_contract', 'convergence'))
    no_effect_fields = ('element_retain_release_calls', 'element_constructors_destructors_or_callbacks',
                       'element_pointer_dereferences', 'source_writes')
    if (proof['schema'] != 'civ6_host.lan_capability_vector_convergence.static.v1'
            or proof['native_execution'] is not False or proof['exe_sha256'] != EXE_SHA
            or copy['element_bytes'] != 32
            or any(type(copy[key]) is not int or copy[key] != 0 for key in no_effect_fields)
            or cleanup['exact_code'] != '488bcae9284d7e00'
            or cleanup['no_element_walk_or_callback'] is not True
            or consumer['vector_field_read'] is not False or consumer['scalar_getter_slot'] != '0x68'
            or result['does_not_require_empty_vectors'] is not True
            or result['does_not_require_vector_contents_as_runtime_projection_input'] is not True
            or result['empty_Base_records_transferred_to_XP1'] is not False):
        raise ValueError('XP1 LAN record-copy convergence premise differs')
    imports = {(row['iat_va'], row['dll'], row['name']) for row in proof['allocation_imports']}
    if imports != {('0x140f975f8', 'api-ms-win-crt-heap-l1-1-0.dll', '_aligned_malloc'),
                   ('0x140f97618', 'api-ms-win-crt-heap-l1-1-0.dll', '_aligned_free')}:
        raise ValueError('LAN temporary record storage has an unknown allocator effect')
    for ref in proof['references'].values():
        _source((ref['path'], ref['sha256']))
    for body in proof['new_allocator_bodies'].values():
        _body(body)
    return {'record_copy_convergence_source_sha256': CONVERGENCE[1],
            'current_exe_record_snapshot_used': False, 'session_record_values_replayed': False,
            'empty_base_record_vectors_transferred': False,
            'projection_domain': 'well_formed_records_and_successful_temporary_allocation',
            'allocation_failure_or_oom_equivalence_claimed': False,
            'temporary_heap_cost_equivalence_claimed': False}


def install_saved_load_capabilities(backend):
    from .native.native_host import DiagnosticHost
    from .native.native_host_capability_status import install_typed_refusal
    from .native.native_app_ownership import install_closed_base_status
    from .lan_capabilities import LAN
    backend.check_thread()
    host = backend.host
    if (backend.stage != 'prepared' or backend.prefix is not None or backend.game_flag() != 0
            or type(host) is not DiagnosticHost):
        raise ValueError('XP1 capability binding requires its prepared raw-Load candidate')
    _owner(backend, backend.owner, backend.captured_bundle)
    address, prior = host._slot_bindings[C.addressof(host.vtable), 0x168]
    if address != host.vtable[0x168 // 8] or getattr(prior, '_native_unavailable', None) != ('host', 0x168):
        raise ValueError('XP1 capability callback has an unknown existing owner')
    _bind_source_receipt(backend)
    with capability_source_scope(backend, 'install'):
        install_typed_refusal(host, base=backend.core._handle, read=backend.runtime.read, candidate_backend=backend)
        install_closed_base_status(host, backend.owner, backend.dll_directory.parents[2],
            required_mode=LAN, captured_bundle=backend.captured_bundle, candidate_backend=backend)
    return host._closed_base_app_ownership


@dataclass(frozen=True)
class _OwnerSourceReceipt:
    backend: object
    application: object
    profile: tuple
    player_keys: tuple
    catalogue: object
    live_code: tuple
    dependencies: tuple
    identities: tuple


def source_dependencies(core_sha256=XP1_CORE_SHA256):
    """Exact static inputs for parent pre/post checks, including OS-stop paths.

    These are source pins only. The existing prepared-bundle/input closure still
    owns databases, content, Core bytes and private-copy identities.
    """
    from .configuration_profiles import COPY_SOURCE, OWNERSHIP_SOURCE, LIVE_SOURCE
    from .paths import resource_root
    from .resource_resolution import resolve_path
    from .native import native_host_capability_status as abi
    from .native.native_app_ownership import PRODUCER_PROOF_SHA256
    from .native.native_application_property_copy import PROOF_SHA256 as property_sha
    from .lan_capabilities import SOURCE_PINS
    if core_sha256 == XP2_CORE_SHA256:
        from .xp2_load_options_capability_profile import source_dependencies as selected_dependencies
        return selected_dependencies()
    if core_sha256 != XP1_CORE_SHA256:
        raise ValueError('Unknown capability dependency profile')
    refs = [SOURCE, CALLER, CONVERGENCE, COPY_SOURCE, OWNERSHIP_SOURCE, LIVE_SOURCE,
            *SOURCE_PINS.values(),
            ('evidence/native-host-capability-status/'+abi.PROOF_SHA256+'.json', abi.PROOF_SHA256),
            ('evidence/native-capability-catalogue/'+abi.CATALOGUE_SHA256+'.json', abi.CATALOGUE_SHA256),
            ('evidence/native-app-ownership-capability-catalogue/'+PRODUCER_PROOF_SHA256+'.json', PRODUCER_PROOF_SHA256),
            ('evidence/native-application-property-copy/'+property_sha+'.json', property_sha),
            ('evidence/native-game-mode.json', '6eb08daedc9c59f09c8d38a53bac51372a866482ede3af9adeb84ae37dbf6ead')]
    for source, field in ((SOURCE, 'parents'), (OWNERSHIP_SOURCE, 'source_refs'), (CONVERGENCE, 'references')):
        refs.extend((r['path'], r['sha256']) for r in _source(source)[field].values())
    refs.extend((path, row['sha256']) for path, row in _source(COPY_SOURCE)['source_files'].items())
    result = {}
    for relative, digest in refs:
        path = str(resolve_path(resource_root()/relative).resolve())
        if path in result and result[path] != digest:
            raise ValueError('Conflicting XP1 capability source pins')
        result[path] = digest
    return result


def _identity(path):
    value = Path(path).stat()
    return value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns, value.st_ctime_ns


def _bind_source_receipt(backend):
    """Retain verified immutable metadata on this exact application owner."""
    from .native.native_source_cache import load_pinned_json
    from .native.native_application_configuration import verify_source as application_source
    from .native import native_host_capability_status as abi
    _owner(backend, backend.owner, backend.captured_bundle)
    if hasattr(backend, '_xp1_capability_sources'):
        raise ValueError('XP1 capability static owner is already bound')
    core, *_ = _candidate_spec(backend)
    dependencies = tuple(sorted(source_dependencies(core).items()))
    before = tuple(_identity(path) for path, _ in dependencies)
    for path, digest in dependencies:
        if core == XP2_CORE_SHA256:
            from .xp2_load_options_capability_profile import verify_dependency
            verify_dependency(path,digest)
        else:
            load_pinned_json(path, digest)
    profile = source_profile(core_sha256=core)
    keys = tuple(row['hash'] for row in application_source(core_sha256=core)['player_keys'])
    if len(keys) != 64 or len(set(keys)) != 64 or any(type(k) is not int or not 0 < k <= 0xffffffff for k in keys):
        raise ValueError('XP1 capability PLAYER source keys differ')
    from .native.native_source_cache import _freeze
    catalogue = (_freeze({'capabilities':profile[0]['catalogue_rows']}) if core == XP2_CORE_SHA256 else
        load_pinned_json(abi.ROOT/'evidence/native-capability-catalogue'/(abi.CATALOGUE_SHA256+'.json'), abi.CATALOGUE_SHA256))
    p, caller = profile
    code = tuple((int(row['va'], 16) - 0x180000000, bytes.fromhex(row['bytes']))
                 for body in (caller['caller'], *p['live_xp1_bodies'].values())
                 for fragment in _body(body)['fragments'] for row in fragment['instructions'])
    after = tuple(_identity(path) for path, _ in dependencies)
    if before != after:
        raise ValueError('XP1 capability source changed while deriving owner metadata')
    receipt = _OwnerSourceReceipt(backend, backend.owner, profile, keys, catalogue, code, dependencies, after)
    backend._xp1_capability_sources = receipt
    backend._xp1_capability_source_scope = None
    return receipt


def _receipt(backend):
    _owner(backend, backend.owner, backend.captured_bundle)
    backend.check_thread()
    receipt = getattr(backend, '_xp1_capability_sources', None)
    if (type(receipt) is not _OwnerSourceReceipt or receipt.backend is not backend
            or receipt.application is not backend.owner
            or getattr(backend, '_xp1_capability_source_scope', None) is not receipt):
        raise ValueError('XP1 capability metadata requires its active verified owner boundary')
    return receipt


def _check_source_boundary(receipt):
    if tuple(_identity(path) for path, _ in receipt.dependencies) != receipt.identities:
        raise ValueError('XP1 capability source changed outside its verified immutable receipt')


def _cache_scope_owner(backend):
    from .loaded_cache_publication import LoadedCachePublication
    lease = getattr(backend, '_saved_load_job_cache_owner', None)
    if (type(lease) is not LoadedCachePublication or lease.owner is not backend
            or lease.attempt.publication_owner is not lease):
        raise ValueError('XP1 capability cache scope requires the existing publication lease')
    lease._check()
    return True


def _lifetime_scope_owner(backend):
    from .xp1_loaded_lifetime import require_lifetime
    token=require_lifetime(getattr(backend,'_loaded_lifetime',None),backend)
    return token.check_metadata_scope()

def _continuation_scope_owner(backend):
    from .xp1_continuation import SavedContinuation
    token=getattr(backend,'_xp1_continuation',None)
    if type(token) is not SavedContinuation or token.owner is not backend:
        raise ValueError('XP1 continuation metadata scope has no exact owner')
    token.check(active=True)
    return True


@contextmanager
def capability_source_scope(backend, phase):
    """One static check per existing exclusive native boundary, never per query.

    The source bytes were SHA-verified before deriving immutable values. Any
    metadata change invalidates that receipt even if content would hash equally.
    The parent must additionally rehash source_dependencies() after OS stop;
    timeout/termination cannot execute this worker's finally block.
    """
    _owner(backend, backend.owner, backend.captured_bundle)
    backend.check_thread()
    receipt = getattr(backend, '_xp1_capability_sources', None)
    if (type(receipt) is not _OwnerSourceReceipt or receipt.backend is not backend
            or receipt.application is not backend.owner
            or getattr(backend, '_xp1_capability_source_scope', None) is not None
            or backend.busy is not True
            or not ((phase == 'install' and backend.stage == 'prepared' and backend.prefix is None)
                    or (phase == 'load' and backend.stage == 'copied' and backend.snapshot_phase == 'load')
                    or (phase == 'cache' and _cache_scope_owner(backend))
                    or (phase == 'continuation' and _continuation_scope_owner(backend))
                    or (phase == 'lifetime' and _lifetime_scope_owner(backend)))):
        raise ValueError('XP1 capability source scope is outside its admitted owner lifecycle')
    _check_source_boundary(receipt)
    backend._xp1_capability_source_scope = receipt
    try:
        yield receipt
    finally:
        backend._xp1_capability_source_scope = None
        _check_source_boundary(receipt)


def candidate_player_key(application, index, backend):
    receipt = _receipt(backend)
    if application is not receipt.application or type(index) is not int or not 0 <= index < 64:
        raise ValueError('XP1 capability PLAYER metadata owner/index differs')
    return receipt.player_keys[index]


def candidate_label_catalogue(backend):
    return _receipt(backend).catalogue


def begin_cache_source_scope(attempt):
    if getattr(attempt, '_capability_source_context', None) is not None:
        raise ValueError('XP1 capability cache metadata scope already entered')
    scope = capability_source_scope(attempt.owner, 'cache')
    scope.__enter__()
    attempt._capability_source_context = scope


def finish_cache_source_scope(attempt):
    scope = getattr(attempt, '_capability_source_context', None)
    if scope is not None:
        del attempt._capability_source_context
        scope.__exit__(None, None, None)
