"""Bounded native Locale diagnostic, not a game or an RL environment."""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import ctypes as C
import hashlib
from pathlib import Path
import sqlite3
from civ6_host.runtime.native.native_configuration_database import NativeConfigurationDatabase
from civ6_host.runtime.native.native_database import load_database
from civ6_host.runtime.native.native_gameplay_database import NativeGameplayDatabase
from civ6_host.runtime.native.native_gameplay_database import bind_memory_initializer
from civ6_host.runtime.native.native_host import validate_fixture
from civ6_host.runtime.native.native_localization import finish_localization
from civ6_host.runtime.native.native_localization import initialize_localization
from civ6_host.runtime.native.native_locale_cases import ACHIEVEMENT_KEYS
from civ6_host.runtime.native.native_locale_cases import LOCALE_KEYS
from civ6_host.runtime.native.native_script_parameters import lua_string
from civ6_host.runtime.native.native_script_runtime import NativeScriptRuntime
_LOOKUP = '?Lookup@Localization@@YA?AVString@1@PEBD@Z'
_PUSH_STRING = '?PushArgument@String@Localization@@QEAA_NPEBD@Z'
_TO_UTF8 = '?toUTF8@String@Localization@@QEAAPEBDAEAIH@Z'
_DESTROY = '??1String@Localization@@UEAA@XZ'
_EXPORT_RVAS = {_LOOKUP: 104144, _PUSH_STRING: 55920, _TO_UTF8: 60592, _DESTROY: 49456}
_LOOKUP_MAX_BYTES = 1048576

def _native_lookup(library, key: bytes, arguments: tuple[bytes, ...]=(), *, explicit_length=False) -> bytes:
    """Call the DLL String ABI directly as an independent Lua-bridge oracle."""
    if not isinstance(key, bytes) or not key or b'\x00' in key or (len(key) > 65536) or (len(arguments) > 16) or any((not isinstance(arg, bytes) or b'\x00' in arg or len(arg) > 65536 for arg in arguments)):
        raise ValueError('Native Locale lookup oracle input outside diagnostic bounds')
    base = library._handle
    functions = {}
    for name, rva in _EXPORT_RVAS.items():
        function = getattr(library, name)
        if C.cast(function, C.c_void_p).value != base + rva:
            raise ValueError(f'Unverified Localization export {name}')
        functions[name] = function
    lookup = functions[_LOOKUP]
    lookup.argtypes, lookup.restype = ([C.c_void_p, C.c_char_p], C.c_void_p)
    push = functions[_PUSH_STRING]
    push.argtypes, push.restype = ([C.c_void_p, C.c_char_p], C.c_ubyte)
    to_utf8 = functions[_TO_UTF8]
    to_utf8.argtypes = [C.c_void_p, C.POINTER(C.c_uint), C.c_uint]
    to_utf8.restype = C.c_void_p
    destroy = functions[_DESTROY]
    destroy.argtypes, destroy.restype = ([C.c_void_p], None)
    allocation = C.create_string_buffer(128 + 15)
    object_pointer = C.addressof(allocation) + 15 & ~15
    object_arg = C.c_void_p(object_pointer)
    initialized = False
    try:
        returned = lookup(object_arg, key)
        if returned != object_pointer:
            raise RuntimeError('Native Localization::Lookup violated its hidden-return ABI')
        initialized = True
        for argument in arguments:
            push(object_arg, argument)
        length = C.c_uint(0)
        pointer = to_utf8(object_arg, C.byref(length), 1)
        if not pointer or length.value > _LOOKUP_MAX_BYTES:
            raise RuntimeError('Native Localization::String::toUTF8 exceeded diagnostic bounds')
        if explicit_length is True:
            return C.string_at(pointer, length.value)
        result = C.string_at(pointer, length.value + 1)
        if result[-1:] != b'\x00':
            raise RuntimeError('Native Localization::String::toUTF8 omitted its C terminator')
        return result[:-1]
    finally:
        if initialized:
            destroy(object_arg)

def _localization_rows(path: Path) -> dict[bytes, bytes]:
    """Select two independent en_US expectations from a private SQLite copy."""
    uri = _resolve_resource_path(path).resolve().as_uri() + '?mode=ro'
    with sqlite3.connect(uri, uri=True) as database:
        database.text_factory = bytes
        rows = dict(database.execute('SELECT Tag, Text FROM LocalizedText WHERE Language=? AND Tag IN (?, ?) ORDER BY Tag', ('en_US', 'ADVISOR_FTUE_47_ALT', 'LOC_GRAMMAR_A_AN')))
    expected = {b'ADVISOR_FTUE_47_ALT', b'LOC_GRAMMAR_A_AN'}
    if set(rows) != expected or any((value is None for value in rows.values())):
        raise ValueError('Localization fixture is missing required en_US witness rows')
    return rows

def _host_executable():
    kernel = C.WinDLL('kernel32', use_last_error=True)
    kernel.GetModuleHandleW.argtypes, kernel.GetModuleHandleW.restype = ([C.c_wchar_p], C.c_void_p)
    module = kernel.GetModuleHandleW(None)
    if not module:
        raise RuntimeError('Could not identify diagnostic host executable')
    return C.WinDLL('', handle=module)

def _bind_namespace(runtime, host, context, namespace_id: int, label: str):
    register = host.LAB_NamespaceRegister
    register.argtypes, register.restype = ([C.c_void_p, C.c_void_p, C.c_uint], C.c_int)
    pointer = runtime.registry.validate(context)
    status = register(runtime.root, pointer, namespace_id)
    runtime._status(runtime.root, status, f'{label} namespace registration')

def _run(runtime, context, source: str, label: str, hashes: dict[str, str]):
    encoded = source.encode('utf-8')
    runtime.execute(context, encoded, ('@civ6rl_locale_' + label).encode('ascii'))
    hashes[label] = hashlib.sha256(encoded).hexdigest()

def _expected_lookup_source(key: bytes, expected: bytes) -> str:
    return f'assert(Locale.Lookup({lua_string(key)})=={lua_string(expected)})'

def run_locale_diagnostic(library, dll_directory, fixture, emit):
    """Exercise pinned Locale callbacks against private DB copies and DLL output."""
    manifest = validate_fixture(fixture)
    if not manifest.get('isolation', {}).get('copies_created_before_worker_launch'):
        raise ValueError('Locale requires supervisor-created private database copies')
    entries = manifest['databases']
    configuration, gameplay, localization = (entries[name] for name in ('configuration', 'gameplay', 'localization'))
    rows = _localization_rows(_resolve_resource_path(Path(localization['path'])))
    host = _host_executable()
    database_library = load_database(dll_directory)
    configure = bind_memory_initializer(host)

    class LocalizationOwner:
        database = database_library
        localization_initialized = False
        localization_library = None
        localization_connection = None

        def __init__(self):
            self.manifest = manifest

        @staticmethod
        def emit(event, **fields):
            emit(event, **fields)
    localization_owner = LocalizationOwner()
    runtime = context = None
    binder = None
    locale_bound = False
    hashes: dict[str, str] = {}
    with NativeGameplayDatabase(database_library, gameplay['path'], gameplay['sha256'], emit, configure) as gameplay_owner:
        try:
            with NativeConfigurationDatabase(gameplay_owner, configuration['path'], configuration['sha256'], emit):
                initialize_localization(localization_owner, dll_directory)
                runtime = NativeScriptRuntime(library, host, emit)
                context = runtime.acquire()
                runtime.attach_standard_libraries(context)
                binder = host.LAB_LocaleBind
                binder.argtypes, binder.restype = ([C.c_void_p, C.c_void_p], C.c_int)
                status = binder(runtime.root, localization_owner.localization_library._handle)
                runtime._status(runtime.root, status, 'Localization module bind')
                runtime.locale_bound = locale_bound = True
                _bind_namespace(runtime, host, context, 5, 'Locale')
                _bind_namespace(runtime, host, context, 6, 'Achievements')
                locale_keys = ','.join((lua_string(value.encode('ascii')) for value in LOCALE_KEYS))
                achievement_keys = ','.join((lua_string(value.encode('ascii')) for value in ACHIEVEMENT_KEYS))
                source = f"local lk={{{locale_keys}}}; local ak={{{achievement_keys}}}; assert(type(Locale)=='table' and type(Achievements)=='table'); for _,k in ipairs(lk) do assert(type(Locale[k])=='function',k) end; for _,k in ipairs(ak) do assert(type(Achievements[k])=='function',k) end"
                _run(runtime, context, source, 'surface', hashes)
                _run(runtime, context, "assert(Locale.StartsWith('MapScript','Map')); assert(not Locale.StartsWith('MapScript','map')); assert(Locale.StartsWith('',''))", 'starts_with', hashes)
                present_key = b'ADVISOR_FTUE_47_ALT'
                missing_key = b'CIV6RL_PHASE42_NO_SUCH_TEXT_KEY'
                for is_present, key in ((True, present_key), (False, missing_key)):
                    key_lua = lua_string(key)
                    native_text = _native_lookup(localization_owner.localization_library, key)
                    _run(runtime, context, f'assert(Locale.IsValidKey({key_lua})==true); assert(Locale.HasTextKey({key_lua})=={str(is_present).lower()}); ' + _expected_lookup_source(key, native_text), 'native_lookup_' + ('present' if is_present else 'missing'), hashes)
                    emit('locale_native_lookup_verified', key=key.decode('ascii'), valid_key=True, has_text_key=is_present, output_bytes=len(native_text), output_sha256=hashlib.sha256(native_text).hexdigest(), native_export_oracle=True)
                _run(runtime, context, "assert(not Locale.IsValidKey('invalid key with spaces')); assert(not Locale.IsValidKey('')); assert(not Locale.HasTextKey('invalid key with spaces'))", 'invalid_key_syntax', hashes)
                if rows[present_key] != _native_lookup(localization_owner.localization_library, present_key):
                    raise RuntimeError('Native Locale output disagrees with independent SQLite text')
                emit('locale_sqlite_text_verified', key=present_key.decode('ascii'), fixture_text_sha256=hashlib.sha256(rows[present_key]).hexdigest(), native_text_sha256=hashlib.sha256(_native_lookup(localization_owner.localization_library, present_key)).hexdigest())
                grammar_key, argument = (b'LOC_GRAMMAR_A_AN', b'Warrior')
                if grammar_key not in rows:
                    raise RuntimeError('Localization fixture omitted grammar witness')
                expected_formatted = _native_lookup(localization_owner.localization_library, grammar_key, (argument,))
                _run(runtime, context, f'assert(Locale.Lookup({lua_string(grammar_key)},{lua_string(argument)})=={lua_string(expected_formatted)})', 'lookup_string_argument', hashes)
                _run(runtime, context, "local ok,msg=pcall(Locale.Lookup,'LOC_GRAMMAR_A_AN',{}); assert(not ok and string.find(msg,'accepts only string format arguments',1,true))", 'nonstring_argument_refused', hashes)
                unsupported_locale = set(LOCALE_KEYS) - {'IsValidKey', 'HasTextKey', 'Lookup', 'StartsWith'}
                for key in sorted(unsupported_locale):
                    _run(runtime, context, f"local ok,msg=pcall(Locale[{lua_string(key.encode('ascii'))}]); assert(not ok and string.find(msg,'Locale diagnostic explicitly refuses',1,true))", 'locale_refusal_' + key, hashes)
                for key in ACHIEVEMENT_KEYS:
                    _run(runtime, context, f"local ok,msg=pcall(Achievements[{lua_string(key.encode('ascii'))}]); assert(not ok and string.find(msg,'Achievements diagnostic explicitly refuses',1,true))", 'achievement_refusal_' + key, hashes)
                emit('locale_namespace_diagnostic_verified', locale_methods=len(LOCALE_KEYS), achievement_methods=len(ACHIEVEMENT_KEYS), implemented_methods=4, explicitly_refused_methods=len(unsupported_locale) + len(ACHIEVEMENT_KEYS), lua_cases=len(hashes), cases_sha256=hashlib.sha256(''.join(hashes.values()).encode('ascii')).hexdigest(), game_created=False, native_turns_executed=0, map_script_factory_ready=False, eligible_for_training=False)
            if context is not None:
                runtime.registry.release(context)
                context = None
            if locale_bound:
                status = binder(runtime.root, None)
                runtime._status(runtime.root, status, 'Localization module unbind')
                runtime.locale_bound = locale_bound = False
            runtime.close()
            runtime = None
        finally:
            try:
                if runtime is not None:
                    try:
                        if context is not None:
                            runtime.registry.release(context)
                            context = None
                        if locale_bound and binder is not None and runtime.root:
                            status = binder(runtime.root, None)
                            runtime._status(runtime.root, status, 'Localization module cleanup unbind')
                            runtime.locale_bound = locale_bound = False
                        runtime.close()
                    finally:
                        runtime = None
            finally:
                if localization_owner.localization_initialized:
                    finish_localization(localization_owner)
                elif localization_owner.localization_connection:
                    connection = localization_owner.localization_connection
                    vtable = C.c_void_p.from_address(connection).value
                    release = C.c_void_p.from_address(vtable + 8).value
                    if release != database_library._handle + 6784:
                        raise RuntimeError('Unverified Localization connection release method')
                    C.WINFUNCTYPE(None, C.c_void_p)(release)(connection)
                    localization_owner.localization_connection = None
                    emit('localization_connection_released_after_failed_initialize')
