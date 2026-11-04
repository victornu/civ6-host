"""GlobalParameters diagnostic on native DatabaseDLL + Havok, not a game.

The historical gameplay cache has unresolved ruleset/mod provenance. Synthetic
databases test conversion/error boundaries separately and are never game data.
"""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import ctypes as C
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import struct
from civ6_host.runtime.native.native_database import NativeDatabase
from civ6_host.runtime.native.native_database import load_database
from civ6_host.runtime.native.native_host import sha256
from civ6_host.runtime.native.native_host import validate_fixture
from civ6_host.runtime.native.native_script_kernel import bind_heap
from civ6_host.runtime.native.native_script_kernel import bind_kernel
from civ6_host.runtime.native.native_script_namespaces import ScriptNamespaces
from civ6_host.runtime.native.native_script_primitives import evaluate_lua
from civ6_host.runtime.native.native_script_threads import ThreadRegistry
from civ6_host.runtime.native.native_script_threads import bind_threads
BOUNDARY_ROWS = [('empty', ''), ('sql_null', None), ('null', 'NULL'), ('null_prefix', 'nUlLable'), ('integer', '2147483647'), ('leading_zeros', '0007'), ('zero', '0'), ('fraction', '.5'), ('rounded', '0.1'), ('decimal', '2.0'), ('negative', '-42'), ('negative_decimal', '-0.1'), ('positive_sign', '+5'), ('exponent', '1e2'), ('space', ' 5'), ('trailing_space', '5 '), ('dot', '.'), ('trailing_dot', '5.'), ('two_dots', '1.2.3'), ('unicode', 'café'), ('not_null', 'nul'), ('hex', '0xff')]

def create_boundary_database(path, rows):
    path = _resolve_resource_path(Path(path))
    if _resolve_resource_path(path).exists():
        raise FileExistsError(path)
    with sqlite3.connect(path) as database:
        database.execute('CREATE TABLE GlobalParameters(Name TEXT, Value TEXT)')
        database.executemany('INSERT INTO GlobalParameters VALUES (?, ?)', rows)
    return sha256(path)

def lua_string(value):
    """A byte-exact Lua literal; do not rely on JSON Unicode escapes in Lua."""
    return '"' + ''.join(('\\%03d' % c for c in value)) + '"'

def expected_parameter(value):
    """Oracle for this bounded source contract, independent of the C parser."""
    if value is None or value == b'' or value[:4].lower() == b'null':
        return ('nil', None)
    if re.fullmatch(b'[0-9]+', value):
        number = int(value)
        if number > 2147483647:
            raise ValueError('Native signed-long exception branch')
        return ('number', float(number))
    if re.fullmatch(b'[0-9]*\\.[0-9]+', value):
        return ('number', struct.unpack('<f', struct.pack('<f', float(value)))[0])
    return ('string', value)

def parameter_assertions(rows):
    assertions = []
    present = 0
    if any((k is None for k, _ in rows)) or len({k for k, _ in rows}) != len(rows):
        raise ValueError('Diagnostic oracle requires nonnull unique keys')
    for key, value in rows:
        kind, converted = expected_parameter(value)
        target = 'GlobalParameters[' + lua_string(key) + ']'
        assertions.append(f'assert(type({target})=="{kind}")')
        if kind != 'nil':
            present += 1
            literal = repr(converted) if kind == 'number' else lua_string(converted)
            assertions.append(f'assert({target}=={literal})')
    assertions.append(f'assert(table.count(GlobalParameters)=={present})')
    return '; '.join(assertions) + '; return 1'

def run_parameter_diagnostic(library, dll_directory, fixture, emit, *, database_factory=NativeDatabase):
    manifest = validate_fixture(fixture)
    isolation = manifest.get('isolation', {})
    if not isolation.get('copies_created_before_worker_launch'):
        raise ValueError('Parameter diagnostics require supervisor-isolated copies')
    entry = manifest['databases']['gameplay']
    workspace = _resolve_resource_path(_resolve_resource_path(Path(fixture))).resolve().parent
    boundary = workspace / 'parameter-boundaries.sqlite'
    overflow = workspace / 'parameter-overflow.sqlite'
    boundary_sha = create_boundary_database(boundary, BOUNDARY_ROWS)
    overflow_sha = create_boundary_database(overflow, [('prefix', '2'), ('overflow', '2147483648')])
    emit('parameter_synthetic_fixtures', fixtures=[{'path': str(boundary), 'sha256': boundary_sha, 'rows': len(BOUNDARY_ROWS)}, {'path': str(overflow), 'sha256': overflow_sha, 'rows': 2}], eligible_for_training=False)
    database_library = load_database(dll_directory)
    emit('parameter_database_library', path=str(_resolve_resource_path(Path(dll_directory)) / 'DatabaseDLL_FinalRelease.dll'), sha256=sha256(_resolve_resource_path(Path(dll_directory)) / 'DatabaseDLL_FinalRelease.dll'))
    kernel = C.WinDLL('kernel32', use_last_error=True)
    kernel.GetModuleHandleW.argtypes, kernel.GetModuleHandleW.restype = ([C.c_wchar_p], C.c_void_p)
    host = C.WinDLL('', handle=kernel.GetModuleHandleW(None))
    lua, heap, api = (bind_kernel(library), bind_heap(host), bind_threads(host))
    bind = host.LAB_ParameterDatabaseBind
    bind.argtypes, bind.restype = ([C.c_void_p, C.c_void_p, C.c_void_p], C.c_int)
    counter = host.LAB_ParameterCounter
    counter.argtypes, counter.restype = ([C.c_uint], C.c_size_t)
    install = host.LAB_RootPrimitivesInstall
    install.argtypes, install.restype = ([C.c_void_p], C.c_int)
    if heap['create']() != 1:
        raise RuntimeError('Parameter diagnostic cannot own heap')
    root = registry = None

    def run(source, context=None):
        return evaluate_lua(lua, root if context is None else registry.validate(context), source, b'@civ6rl_globalparameters')

    def expect_error(context, text):
        try:
            namespaces.register(context, 'GlobalParameters')
        except RuntimeError as exc:
            if text not in str(exc):
                raise
        else:
            raise RuntimeError('Expected parameter refusal was not raised')
        if counter(3):
            raise RuntimeError('A cursor survived the protected error')
    try:
        if api['initialize'](library._handle) != 1:
            raise RuntimeError('Pinned API binding failed')
        root = lua['newstate'](C.cast(heap['allocate'], C.c_void_p), None)
        if not root:
            raise RuntimeError('Parameter root creation failed')
        lua['gc'](root, 6, 110)
        lua['gc'](root, 7, 5)
        if install(root):
            raise RuntimeError('Root primitive installation failed')
        registry = ThreadRegistry(root, library, host, lua)
        namespaces = ScriptNamespaces(registry, host)
        contexts = [registry.acquire(), registry.acquire()]
        expect_error(contexts[0], 'database service is not bound')
        for label, path, expected_sha in (('historical_gameplay_cache', _resolve_resource_path(Path(entry['path'])), entry['sha256']), ('synthetic_boundaries', boundary, boundary_sha)):
            run('GlobalParameters=nil; GlobalParameters_Data=nil; return 1')
            with database_factory(database_library, path, expected_sha, emit) as database:
                native_rows = database.rows()
                with sqlite3.connect(_resolve_resource_path(path).resolve().as_uri() + '?mode=ro', uri=True) as oracle:
                    oracle.text_factory = bytes
                    sqlite_rows = oracle.execute('SELECT Name, Value FROM GlobalParameters').fetchall()
                if native_rows != sqlite_rows or database.rows() != native_rows:
                    raise RuntimeError('Native rows differ from the copied SQLite fixture or repeat')
                emit('parameter_native_rows_verified', fixture=label, rows=len(native_rows), ordered_rows_sha256=hashlib.sha256(json.dumps([[None if c is None else c.hex() for c in row] for row in native_rows], separators=(',', ':')).encode()).hexdigest(), repeat_identical=True, eligible_for_training=False)
                registry._status(bind(root, database_library._handle, database.connection), 'bind database')
                try:
                    before = counter(0)
                    namespaces.register(contexts[0], 'GlobalParameters')
                    assertions = parameter_assertions(native_rows)
                    run(assertions)
                    namespaces.register(contexts[1], 'GlobalParameters')
                    if counter(0) != before + 1:
                        raise RuntimeError('Root namespace cache unexpectedly reread the database')
                    run('return GlobalParameters.' + ('AI_BASE_LUXURY_VALUE==1.5' if label == 'historical_gameplay_cache' else 'rounded==0.10000000149011612') + ' and 1 or 0', contexts[1])
                    missing_key = next((key for key, value in native_rows if expected_parameter(value)[0] != 'nil'))
                    run('SavedData=GlobalParameters_Data; GlobalParameters_Data.extra=17; rawset(GlobalParameters_Data,' + lua_string(missing_key) + ',nil); setmetatable(GlobalParameters_Data,{__newindex=function() error("must rawset") end}); GlobalParameters=nil; return 1')
                    namespaces.register(contexts[0], 'GlobalParameters')
                    run('assert(GlobalParameters==SavedData and GlobalParameters.extra==17); setmetatable(GlobalParameters_Data,nil); GlobalParameters.extra=nil; return 1')
                    run(assertions)
                    if counter(0) != before + 2 or counter(0) != counter(1):
                        raise RuntimeError('Refill or query release count mismatch')
                    emit('parameter_lua_values_verified', fixture=label, rows=len(native_rows), assertions_sha256=hashlib.sha256(assertions.encode()).hexdigest(), namespace_cached=True, data_cache_refilled_in_place=True, rawset_bypasses_newindex=True, native_turns_executed=0)
                finally:
                    registry._status(bind(root, None, None), 'unbind database')
        run('GlobalParameters=nil; GlobalParameters_Data=nil; return 1')
        with database_factory(database_library, overflow, overflow_sha, emit) as database:
            registry._status(bind(root, database_library._handle, database.connection), 'bind error database')
            try:
                expect_error(contexts[0], 'native C++ numeric exception path')
                run('assert(GlobalParameters==nil and GlobalParameters_Data.prefix==2 and GlobalParameters_Data.overflow==nil); GlobalParameters_Data=false; return 1')
                expect_error(contexts[0], 'non-table data cache')
            finally:
                registry._status(bind(root, None, None), 'unbind error database')
        run('GlobalParameters=nil; GlobalParameters_Data=nil; return 1')
        with database_factory(database_library, boundary, boundary_sha, emit) as database:
            registry._status(bind(root, database_library._handle, database.connection), 'bind recovery database')
            try:
                namespaces.register(contexts[0], 'GlobalParameters')
                run('assert(GlobalParameters.integer==2147483647); return 1')
            finally:
                registry._status(bind(root, None, None), 'unbind recovery database')
        emit('parameter_error_paths_verified', missing_service_refused=True, numeric_exception_explicitly_refused=True, non_table_cache_refused=True, prefix_cache_side_effect_retained=True, recovered_in_same_vm=True, opened_cursors=counter(0), released_cursors=counter(1), active_cursors=counter(3), native_turns_executed=0, map_script_factory_ready=False)
        if counter(0) != counter(1) or counter(3):
            raise RuntimeError('A parameter cursor remained live')
        for context in contexts:
            registry.release(context)
    finally:
        try:
            if root:
                if registry:
                    registry._status(bind(root, None, None), 'final database unbind')
                lua['close'](root)
                if registry:
                    registry.forget_after_root_close()
        finally:
            counters = {name: heap['counter'](i) for i, name in enumerate(('live_blocks', 'allocation_calls', 'reallocation_calls', 'free_calls'))}
            if heap['destroy']() != 1:
                raise RuntimeError(f'Parameter diagnostic heap teardown failed: {counters}')
        emit('script_parameters_closed', **counters, full_root_initializer=False, map_script_factory_ready=False, native_turns_executed=0)
