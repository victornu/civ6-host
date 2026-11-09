"""Pinned native Localization bootstrap, only for disposable Windows probes."""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import ctypes as C
from pathlib import Path
from civ6_host.runtime.native.native_host import sha256
LOCALIZATION_SHA256 = '0becd5c425a3d6edc88f5315c01af3dd30dd7cb158271d56f4bba7ff2bb4e056'
ICU_SHA256 = '02cfa347cf8e80e3d9ca925a8c3371db9a125c53234f3e1c03fc0eae4705153f'
INITIALIZE = '?Initialize@Localization@@YA_NPEB_SPEAVIDatabaseConnection1@Database@@PEBD_NPEAVILocalizationLogger@1@@Z'
CREATE_CONNECTION = '?CreateConnection@Database@@YAPEAVIDatabaseConnection1@1@PEBDHPEAVIDatabaseLogger@1@@Z'

def validate_localization(manifest):
    """Require explicit settings and immutable workspace copies before DLL calls."""
    settings = manifest.get('localization_bootstrap')
    if not isinstance(settings, dict):
        raise ValueError('Prepare requires an explicit localization_bootstrap fixture')
    locale = settings.get('locale')
    explicit = 'official_bundle' in manifest or 'official_export' in settings
    if explicit:
        from civ6_host.runtime import xp2_bbg_inputs
        reference = manifest.get('official_bundle')
        if manifest.get('input_profile') == 'xp2-lan' and xp2_bbg_inputs.is_reference(reference):
            xp2_bbg_inputs.validate_localization_fixture(manifest)
        else:
            from civ6_host.runtime.native.native_official_bundle import validate_localization_fixture
            validate_localization_fixture(manifest)
    elif locale != 'en_US':
        raise ValueError('This diagnostic bootstrap only validates locale en_US')
    if type(settings.get('dictionary_flag')) is not bool:
        raise ValueError('The native dictionary flag must be an explicit boolean')
    root = _resolve_resource_path(_resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_localization.py')))).resolve().parents[1] / 'work').resolve()
    entries = {'icu_data': settings['icu_data'], 'localization': manifest['databases']['localization']}
    for name, entry in entries.items():
        path = _resolve_resource_path(_resolve_resource_path(Path(entry['path']))).resolve()
        if not path.is_relative_to(root):
            raise ValueError(f'{name} must be a workspace fixture copy')
        if sha256(path) != entry['sha256']:
            raise ValueError(f'Changed {name} fixture')
    if settings['icu_data']['sha256'] != ICU_SHA256:
        raise ValueError('Unrecognized ICU data version')
    with _resolve_resource_path(_resolve_resource_path(Path(entries['localization']['path']))).open('rb') as stream:
        if stream.read(16) != b'SQLite format 3\x00':
            raise ValueError('Invalid localization database fixture')
    return settings

def _localization_library_path(dll_directory, shared_dependency_profile=None):
    path = _resolve_resource_path(Path(dll_directory)) / 'Localization_FinalRelease.dll'
    if shared_dependency_profile is None:
        if sha256(path) != LOCALIZATION_SHA256:
            raise ValueError('Unrecognized Localization DLL')
        return path
    from civ6_host.runtime.native.native_shared_dependency_profiles import NativeSharedDependencyProfile
    if type(shared_dependency_profile) is not NativeSharedDependencyProfile:
        raise ValueError('Expected the explicit XP2 shared dependency profile')
    return shared_dependency_profile.verify_library_path('Localization_FinalRelease.dll', path)

def initialize_localization(host, dll_directory, *, shared_dependency_profile=None):
    settings = validate_localization(host.manifest)
    path = _localization_library_path(dll_directory, shared_dependency_profile)
    library = C.WinDLL(str(path))
    host.localization_library = library
    create = getattr(host.database, CREATE_CONNECTION)
    create.argtypes, create.restype = ([C.c_char_p, C.c_int, C.c_void_p], C.c_void_p)
    database_path = host.manifest['databases']['localization']['path']
    host.emit('before_localization_connection', path=database_path, flags=65)
    connection = create(str(database_path).encode('utf-8'), 65, None)
    if not connection:
        raise RuntimeError('Native localization database connection is null')
    host.localization_connection = connection
    initialize = getattr(library, INITIALIZE)
    initialize.argtypes = [C.c_wchar_p, C.c_void_p, C.c_char_p, C.c_bool, C.c_void_p]
    initialize.restype = C.c_bool
    host.emit('before_localization_initialize', locale=settings['locale'], dictionary_flag=settings['dictionary_flag'], dictionary_flag_semantics=('captured native lookup SQL: strict' if settings['dictionary_flag'] else 'captured native lookup SQL: priorities') if 'official_export' in settings else 'unresolved native boolean; explicit diagnostic profile', dll_sha256=sha256(path), reference_dll_sha256=LOCALIZATION_SHA256, icu_sha256=ICU_SHA256)
    result = initialize(settings['icu_data']['path'], connection, settings['locale'].encode('ascii'), settings['dictionary_flag'], None)
    host.localization_initialized = bool(result)
    host.emit('localization_initialize_result', return_value=bool(result))
    if not result:
        raise RuntimeError('Native Localization::Initialize returned false')
    current = getattr(library, '?GetCurrentLanguage@Localization@@YAAEBVLanguage@1@XZ')
    current.argtypes, current.restype = ([], C.c_void_p)
    get_type = getattr(library, '?GetType@Language@Localization@@QEBAPEBDXZ')
    get_type.argtypes, get_type.restype = ([C.c_void_p], C.c_char_p)
    language = current()
    if not language:
        raise RuntimeError('Native current language is null after initialization')
    actual = get_type(language)
    if actual != settings['locale'].encode('ascii'):
        raise RuntimeError(f'Native localization selected a different language: {actual!r}')
    host.emit('localization_initialized', current_language=actual.decode('ascii'), game_created=False, native_turns_executed=0)

def finish_localization(host, *, shared_dependency_profile=None):
    """Destroy dictionary/results before releasing the borrowed DB connection."""
    if shared_dependency_profile is not None:
        from civ6_host.runtime.native.native_shared_dependency_profiles import NativeSharedDependencyProfile
        if type(shared_dependency_profile) is not NativeSharedDependencyProfile:
            raise ValueError('Expected the explicit XP2 shared dependency profile')
        shared_dependency_profile.verify_library_path('Localization_FinalRelease.dll', host.localization_library._name)
    shutdown = getattr(host.localization_library, '?Shutdown@Localization@@YA_NXZ')
    shutdown.argtypes, shutdown.restype = ([], C.c_bool)
    result = shutdown()
    host.emit('localization_shutdown', return_value=bool(result))
    if not result:
        raise RuntimeError('Native Localization::Shutdown returned false')
    host.localization_initialized = False
    connection = host.localization_connection
    vtable = C.c_void_p.from_address(connection).value
    release = C.c_void_p.from_address(vtable + 8).value
    if release != host.database._handle + 6784:
        raise RuntimeError('Unrecognized localization database Release method')
    C.WINFUNCTYPE(None, C.c_void_p)(release)(connection)
    host.localization_connection = None
    host.emit('localization_connection_released')
    icu = host.manifest['localization_bootstrap']['icu_data']
    if sha256(icu['path']) != icu['sha256']:
        raise RuntimeError('Native Localization changed its ICU data copy')
    host.emit('icu_fixture_unchanged', sha256=icu['sha256'])
