"""Owned native Lua root and protected script execution.

This is a host component, not a ready GameCore map context. In particular,
acquire() does not claim to have installed the EXE's context bootstrap.
Only use in the bounded native supervisor process.
"""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import ctypes as C
import hashlib
from pathlib import Path
from civ6_host.runtime.native.native_script_kernel import bind_heap
from civ6_host.runtime.native.native_script_kernel import bind_kernel
from civ6_host.runtime.native.native_script_threads import ThreadRegistry
from civ6_host.runtime.native.native_script_threads import bind_threads
from civ6_host.runtime.native.native_script_namespaces import ScriptNamespaces

class NativeScriptRuntime:

    def __init__(self, library, host, emit):
        self.library, self.host, self.emit = (library, host, emit)
        self.lua, self.heap = (bind_kernel(library), bind_heap(host))
        self.root = self.registry = None
        self.notification_service = None
        self.context_owner = None
        self.database_bound = self.configuration_bound = self.locale_bound = False
        self.closed = False
        self.execute_buffer = host.LAB_ScriptExecuteBuffer
        self.execute_buffer.argtypes = [C.c_void_p, C.c_char_p, C.c_size_t, C.c_char_p]
        self.execute_buffer.restype = C.c_int
        if self.heap['create']() != 1:
            raise RuntimeError('Script runtime cannot own the native heap')
        try:
            if bind_threads(host)['initialize'](library._handle) != 1:
                raise RuntimeError('Script runtime HKS ABI mismatch')
            self.root = self.lua['newstate'](C.cast(self.heap['allocate'], C.c_void_p), None)
            if not self.root:
                raise RuntimeError('Script root allocation failed')
            self.lua['gc'](self.root, 6, 110)
            self.lua['gc'](self.root, 7, 5)
            install = host.LAB_RootPrimitivesInstall
            install.argtypes, install.restype = ([C.c_void_p], C.c_int)
            self._status(self.root, install(self.root), 'root primitive installation')
            self.registry = ThreadRegistry(self.root, library, host, self.lua)
            self.namespaces = ScriptNamespaces(self.registry, host)
        except BaseException:
            self.close()
            raise

    def _status(self, state, status, operation):
        if not status:
            return
        length = C.c_size_t()
        pointer = self.lua['tolstring'](state, -1, C.byref(length)) if self.lua['gettop'](state) and self.lua['type'](state, -1) == 4 else None
        message = C.string_at(pointer, min(length.value, 4096)).decode('utf-8', 'replace') if pointer else ''
        self.lua['settop'](state, 0)
        raise RuntimeError(f'{operation}: native status {status}: {message}')

    def acquire(self):
        return self.registry.acquire()

    def evaluate_text(self, child, source: bytes, name=b'@python_result', *, capacity=2 * 1024 * 1024):
        """Execute a host-owned snippet and copy its string result, under protection."""
        pointer = self.registry.validate(child)
        if type(source) is not bytes or not source or type(capacity) is not int or (not 0 < capacity <= 16 * 1024 * 1024):
            raise ValueError('Invalid bounded Lua result request')
        if type(name) is not bytes or not name or b'\x00' in name or (len(name) > 1300):
            raise ValueError('Invalid Lua result chunk name')
        method = self.host.LAB_ScriptEvaluateText
        method.argtypes = [C.c_void_p, C.c_char_p, C.c_size_t, C.c_char_p, C.c_void_p, C.c_size_t, C.POINTER(C.c_size_t)]
        method.restype = C.c_int
        output = C.create_string_buffer(capacity)
        written = C.c_size_t()
        self._status(pointer, method(pointer, source, len(source), name, output, capacity, C.byref(written)), 'protected Lua string result')
        if written.value > capacity or self.lua['gettop'](pointer):
            raise RuntimeError('Lua result boundary invariant failed')
        return output.raw[:written.value]

    def bind_core_services(self, native_host, context, *, core_library=None, core_sha256=None):
        """Borrow Core's existing connections; never initialize Database twice."""
        self.registry._check()
        if self.database_bound or self.configuration_bound or self.locale_bound:
            raise RuntimeError('Script services already bound')
        if not getattr(native_host, 'localization_initialized', False):
            raise RuntimeError('Native localization must initialize before Lua binding')
        profiled_services = None
        if core_library is not None or core_sha256 is not None:
            from civ6_host.runtime.core_script_services import prepare
            profiled_services = prepare(self, native_host, context, core_library, core_sha256=core_sha256)
            inner = profiled_services.inner
            configuration = profiled_services.configuration
            gameplay = profiled_services.gameplay
        else:
            inner = C.c_void_p.from_address(context + 8).value
            if not inner:
                raise RuntimeError('Native Core inner context is null')
            configuration = C.c_void_p.from_address(inner + 80).value
            gameplay = C.c_void_p.from_address(inner + 88).value
            if not configuration or not gameplay:
                raise RuntimeError('Native Core database connections are null')
        bind = self.host.LAB_ParameterDatabaseBind
        bind.argtypes, bind.restype = ([C.c_void_p] * 3, C.c_int)
        self._status(self.root, bind(self.root, native_host.database._handle, gameplay), 'borrow Core gameplay DB')
        self.database_bound = True
        self.service_owner = native_host
        bind_configuration = self.host.LAB_DBConfigurationBorrow
        bind_configuration.argtypes, bind_configuration.restype = ([C.c_void_p] * 3, C.c_int)
        self._status(self.root, bind_configuration(self.root, native_host.database._handle, configuration), 'borrow Core configuration DB')
        self.configuration_bound = True
        bind_locale = self.host.LAB_LocaleBind
        bind_locale.argtypes, bind_locale.restype = ([C.c_void_p] * 2, C.c_int)
        self._status(self.root, bind_locale(self.root, native_host.localization_library._handle), 'borrow Localization')
        self.locale_bound = True
        if profiled_services is not None:
            from civ6_host.runtime.core_script_services import commit
            commit(self, profiled_services)
        self.emit('native_script_core_services_bound', borrowed=True, database_initialized_again=False, configuration_change_baseline_known=False)

    def unbind_services(self):
        self.registry._check()
        self._profile_borrowed_services = None
        if self.locale_bound:
            self._status(self.root, self.host.LAB_LocaleBind(self.root, None), 'unbind Localization')
            self.locale_bound = False
        if self.configuration_bound:
            unbind = self.host.LAB_DBConfigurationBind
            unbind.argtypes, unbind.restype = ([C.c_void_p] * 3 + [C.c_int32], C.c_int)
            self._status(self.root, unbind(self.root, None, None, 0), 'unbind configuration')
            self.configuration_bound = False
        if self.database_bound:
            self._status(self.root, self.host.LAB_ParameterDatabaseBind(self.root, None, None), 'unbind gameplay')
            self.database_bound = False
        self.service_owner = None

    def attach_event_category(self, context, category):
        pointer = self.registry.validate(context)
        if category not in (1, 2) or isinstance(category, bool):
            raise ValueError('Unverified Lua event category')
        install = self.host.LAB_ScriptEventsInstall
        install.argtypes, install.restype = ([C.c_void_p, C.c_void_p, C.c_int], C.c_int)
        self._status(self.root, install(self.root, pointer, category), 'event category installation')

    def attach_standard_libraries(self, context):
        pointer = self.registry.validate(context)
        install = self.host.LAB_ScriptLibrariesInstall
        install.argtypes, install.restype = ([C.c_void_p] * 2, C.c_int)
        self._status(self.root, install(self.root, pointer), 'restricted library installation')

    def install_aux_event_registry(self):
        install = self.host.LAB_AuxEventsInstall
        install.argtypes, install.restype = ([C.c_void_p], C.c_int)
        self._status(self.root, install(self.root), 'category-1 AUX event registry')

    def attach_game_events(self, context):
        pointer = self.registry.validate(context)
        install = self.host.LAB_GameEventsInstall
        install.argtypes, install.restype = ([C.c_void_p, C.c_void_p], C.c_int)
        self._status(self.root, install(self.root, pointer), 'GameEvents zero-listener profile')

    def dispatch_game_event(self, name: bytes, arguments):
        if not isinstance(name, bytes) or not name or b'\x00' in name or (len(name) > 255):
            raise ValueError('GameEvents name outside admitted bounds')
        arguments = tuple(arguments)
        from civ6_host.runtime.native.native_script_arguments import HKSArgument
        from civ6_host.runtime.native.native_script_arguments import pack_arguments
        data = pack_arguments(arguments)
        output = C.c_uint8(0)
        dispatch = self.host.LAB_GameEventsDispatchTyped
        dispatch.argtypes = [C.c_void_p, C.c_char_p, C.POINTER(HKSArgument), C.c_size_t, C.POINTER(C.c_uint8)]
        dispatch.restype = C.c_int
        self._status(self.root, dispatch(self.root, name, data, len(arguments), C.byref(output)), 'protected synchronous GameEvents dispatch')
        if self.lua['gettop'](self.root):
            raise RuntimeError('GameEvents dispatch left a nonempty root stack')
        return bool(output.value)

    def dispatch_aux_event(self, name: bytes):
        if not isinstance(name, bytes) or not name or b'\x00' in name or (len(name) > 255):
            raise ValueError('AUX event name outside admitted bounds')
        dispatch = self.host.LAB_Aux90Dispatch
        dispatch.argtypes, dispatch.restype = ([C.c_void_p, C.c_char_p], C.c_int)
        self._status(self.root, dispatch(self.root, name), 'native protected AUX event dispatch')
        if self.lua['gettop'](self.root):
            raise RuntimeError('AUX event left a nonempty root stack')

    def dispatch_aux_event_category_null(self, name: bytes, *, category, arguments=None):
        """Protected generic category lookup; only a real missing entry skips."""
        if type(category) is not int or category not in (1, 2) or type(name) is not bytes or (not name) or (len(name) > 255) or (b'\x00' in name) or (not name.isascii()) or (arguments is not None):
            raise ValueError('Unverified AUX category/NULL dispatch request')
        dispatch = getattr(self.host, 'LAB_Aux90DispatchCategoryNull', None)
        if not callable(dispatch):
            raise ValueError('Native AUX category/NULL dispatcher export is unavailable')
        if self.lua['gettop'](self.root):
            raise RuntimeError('AUX category dispatch requires an empty root stack')
        outcome = C.c_uint32(0)
        dispatch.argtypes = [C.c_void_p, C.c_uint32, C.c_char_p, C.c_void_p, C.POINTER(C.c_uint32)]
        dispatch.restype = C.c_int
        status = dispatch(self.root, category, name, None, C.byref(outcome))
        self._status(self.root, status, 'protected AUX category/NULL dispatch')
        if self.lua['gettop'](self.root):
            raise RuntimeError('AUX category dispatch left a nonempty root stack')
        meanings = {1: 'category_nil', 2: 'event_nil', 3: 'call_nil', 4: 'call_returned'}
        if outcome.value not in meanings:
            raise RuntimeError('Native AUX category dispatcher returned an unknown outcome')
        return meanings[outcome.value]

    def dispatch_game_event_result(self, name: bytes, arguments, *, method, output_initial=0):
        if method not in ('Call', 'TestAll') or type(output_initial) is not int or (not 0 <= output_initial <= 255):
            raise ValueError('Unverified GameEvents result method or byte')
        if not isinstance(name, bytes) or not name or b'\x00' in name or (len(name) > 255):
            raise ValueError('GameEvents name outside admitted bounds')
        arguments = tuple(arguments)
        from civ6_host.runtime.native.native_script_arguments import HKSArgument
        from civ6_host.runtime.native.native_script_arguments import pack_arguments
        from civ6_host.runtime.script_event_maps import has_maps
        from civ6_host.runtime.script_event_maps import dispatch_maps
        if has_maps(arguments):
            return dispatch_maps(self, name, arguments, method=method, output_initial=output_initial)
        data = pack_arguments(arguments)
        valid, output = (C.c_uint8(0), C.c_uint8(output_initial))
        dispatch = self.host.LAB_GameEventsDispatchTypedResult
        dispatch.argtypes = [C.c_void_p, C.c_char_p, C.POINTER(HKSArgument), C.c_size_t, C.c_uint, C.POINTER(C.c_uint8), C.POINTER(C.c_uint8)]
        dispatch.restype = C.c_int
        self._status(self.root, dispatch(self.root, name, data, len(arguments), int(method == 'TestAll'), C.byref(valid), C.byref(output)), 'protected GameEvents result dispatch')
        if self.lua['gettop'](self.root):
            raise RuntimeError('GameEvents result dispatch left a nonempty root stack')
        return (bool(valid.value), output.value)

    def attach_ui_enums(self, context):
        pointer = self.registry.validate(context)
        install = self.host.LAB_ScriptUIEnumsInstall
        install.argtypes, install.restype = ([C.c_void_p] * 2, C.c_int)
        self._status(self.root, install(self.root, pointer), 'UI enum installation')

    def bind_native_game_api(self, context, core_context, core_library, *, core_sha256='d7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'):
        """Native API registration prefix, not the complete EXE factory."""
        if core_sha256 == '324c51e9ea3531758842e16c69e6cddbefbb226c5b675c3d6e60111646c2e98c':
            from civ6_host.runtime.profile_script_binding import bind_game_api
            return bind_game_api(self, context, core_context, core_library, core_sha256=core_sha256)
        if core_sha256 == '259b90a473a256aff6a7d621a4f3717e46f6921c59b9817475375c88b97e8c83':
            from civ6_host.runtime.native.native_xp1_script_bindings import bind_xp1_game_api
            from civ6_host.runtime.native.native_probe import Windows
            if not hasattr(self.host, 'LAB_XP1ScriptCoreBindingsInstall'):
                raise ValueError('XP1 native API requires its qualified executable export')
            return bind_xp1_game_api(self, context, core_context, core_library, project_root=_resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_script_runtime.py')))).resolve().parents[1], module_paths=Windows().modules())
        if core_sha256 != 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3':
            raise ValueError('Native script API engine is not admitted')
        from civ6_host.runtime.native.native_host import virtual
        pointer = self.registry.validate(context)
        get_interface = virtual(core_library, core_context, 104, 4383104, C.c_void_p)
        interface = get_interface(core_context)
        if not interface:
            raise RuntimeError('Core returned no native scripting interface')
        install = self.host.LAB_ScriptCoreBindingsInstall
        install.argtypes, install.restype = ([C.c_void_p] * 4, C.c_int)
        status = install(self.root, pointer, interface, core_library._handle)
        self._status(self.root if self.lua['gettop'](self.root) else pointer, status, 'native GameCore API registration')
        self.emit('native_game_api_registered', interface_rva=hex(interface - core_library._handle), vtable_rva='0x79fe70', method_rva='0x43bce0', complete_exe_context=False, game_created=False)

    def attach_native_game_api(self, context):
        pointer = self.registry.validate(context)
        attach = self.host.LAB_ScriptCoreBindingsAttach
        attach.argtypes, attach.restype = ([C.c_void_p] * 2, C.c_int)
        self._status(self.root, attach(self.root, pointer), 'attach native GameCore API')

    def bind_native_ui_api(self, game_context, ui_context, core_context, core_library, *, core_sha256='d7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'):
        if core_sha256 == '324c51e9ea3531758842e16c69e6cddbefbb226c5b675c3d6e60111646c2e98c':
            from civ6_host.runtime.xp2_ui_binding_source import bind_ui_api
            return bind_ui_api(self, game_context, ui_context, core_context, core_library)
        if core_sha256 == '259b90a473a256aff6a7d621a4f3717e46f6921c59b9817475375c88b97e8c83':
            from civ6_host.runtime.xp1_ui_binding import bind_xp1_ui_api
            return bind_xp1_ui_api(self, game_context, ui_context, core_context, core_library)
        if core_sha256 != 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3':
            raise ValueError('Native UI binding engine is not admitted')
        from civ6_host.runtime.native.native_host import virtual
        game = self.registry.validate(game_context)
        ui = self.registry.validate(ui_context)
        interface = virtual(core_library, core_context, 104, 4383104, C.c_void_p)(core_context)
        install = self.host.LAB_ScriptCoreUIBindingsInstall
        install.argtypes, install.restype = ([C.c_void_p] * 4, C.c_int)
        self._status(ui, install(game, ui, interface, core_library._handle), 'native UI GameCore API registration')
        self.emit('native_ui_game_api_registered', method_rva='0x43bcf0', native_visibility_callbacks=True, complete_exe_context=False, context_profile='Separate owned child environment in diagnostic HKS root')

    def set_include_sources(self, sources):

        class Input(C.Structure):
            _fields_ = [('name', C.c_char_p), ('source', C.c_char_p), ('size', C.c_size_t)]
        records = tuple(sources)
        data = (Input * len(records))(*(Input(row.name.encode('utf-8'), row.source, len(row.source)) for row in records))
        configure = self.host.LAB_ScriptIncludeSetFiles
        configure.argtypes, configure.restype = ([C.POINTER(Input), C.c_size_t], C.c_int)
        self._status(self.root, configure(data, len(records)), 'configure include sources')
        self.emit('native_include_snapshot', files=len(records), source_bytes=sum((len(r.source) for r in records)), ordered_files=[{'name': r.name, 'sha256': hashlib.sha256(r.source).hexdigest()} for r in records], native_registry_order_verified=False, strict_load_errors=True)

    def attach_include(self, context):
        pointer = self.registry.validate(context)
        install = self.host.LAB_ScriptIncludeInstall
        install.argtypes, install.restype = ([C.c_void_p], C.c_int)
        self._status(pointer, install(pointer), 'install snapshot include loader')

    def execute(self, context, source: bytes, name: bytes):
        pointer = self.registry.validate(context)
        if not isinstance(source, bytes) or not isinstance(name, bytes):
            raise TypeError('Lua source and chunk name must be bytes')
        if not name or b'\x00' in name or len(name) > 1300 or (len(source) > 16 * 1024 * 1024):
            raise ValueError('Script buffer or name outside admitted bounds')
        self._status(pointer, self.execute_buffer(pointer, source, len(source), name), 'script execution')
        if self.lua['gettop'](pointer):
            raise RuntimeError('Protected script execution left a nonempty stack')
        self.emit('native_script_buffer_executed', name=name.decode('utf-8', 'replace'), bytes=len(source), sha256=hashlib.sha256(source).hexdigest(), map_created=False, native_turns_executed=0)

    def execute_file(self, context, path: Path):
        path = _resolve_resource_path(_resolve_resource_path(Path(path))).resolve(strict=True)
        name = str(path).encode('ascii')
        if len(str(path).encode('utf-16-le')) // 2 >= 260:
            raise ValueError('Native script path exceeds 259 UTF-16 units')
        with _resolve_resource_path(path).open('rb') as stream:
            source = stream.read(16 * 1024 * 1024 + 1)
        self.execute(context, source, name)

    def close(self):
        if self.closed:
            return
        if self.notification_service is not None:
            raise RuntimeError('Native context notification service is still bound')
        if self.context_owner is not None or (self.registry and self.registry._claims):
            raise RuntimeError('Retained script context owner is still bound')
        if self.registry:
            self.registry._check()
        if self.database_bound or self.configuration_bound or self.locale_bound:
            raise RuntimeError('Native script dependencies are still bound')
        try:
            if self.root:
                self.lua['close'](self.root)
                if self.registry:
                    self.registry.forget_after_root_close()
                self.root = None
        finally:
            counters = {key: self.heap['counter'](i) for i, key in enumerate(('live_blocks', 'allocation_calls', 'reallocation_calls', 'free_calls'))}
            if self.heap['destroy']() != 1:
                raise RuntimeError(f'Script runtime heap destruction refused: {counters}')
            self.closed = True
        self.emit('native_script_runtime_closed', **counters)
        if hasattr(self.host, 'LAB_ScriptIncludeSetFiles'):
            clear = self.host.LAB_ScriptIncludeSetFiles
            clear.argtypes, clear.restype = ([C.c_void_p, C.c_size_t], C.c_int)
            if clear(None, 0):
                raise RuntimeError('Could not release include source snapshot')

def run_core_services_diagnostic(native_host, context, dll_directory, emit, core_library=None):
    """Exercise Lua on Core's real, already prepared connections; no new game."""
    import sqlite3
    from civ6_host.runtime.native.native_havok import HAVOK_SHA256
    from civ6_host.runtime.native.native_host import sha256
    from civ6_host.runtime.native.native_script_parameters import lua_string
    path = _resolve_resource_path(Path(dll_directory)) / 'HavokScript_FinalRelease.dll'
    if sha256(path) != HAVOK_SHA256:
        raise ValueError('Unverified HavokScript module')
    kernel = C.WinDLL('kernel32', use_last_error=True)
    kernel.GetModuleHandleW.argtypes, kernel.GetModuleHandleW.restype = ([C.c_wchar_p], C.c_void_p)
    host = C.WinDLL('', handle=kernel.GetModuleHandleW(None))
    runtime = NativeScriptRuntime(C.WinDLL(str(path)), host, emit)
    try:
        runtime.bind_core_services(native_host, context)
        child = runtime.acquire()
        runtime.attach_standard_libraries(child)
        for name in ('DB', 'GameInfo', 'GlobalParameters', 'Path', 'Locale', 'Achievements'):
            runtime.namespaces.register(child, name)
        for database, method in (('gameplay', 'Query'), ('configuration', 'ConfigurationQuery')):
            path = _resolve_resource_path(Path(native_host.manifest['databases'][database]['path']))
            with sqlite3.connect(_resolve_resource_path(path).resolve().as_uri() + '?mode=ro', uri=True) as oracle:
                count = oracle.execute("SELECT count(*) FROM sqlite_master WHERE type='table'").fetchone()[0]
            source = f"""assert(DB.{method}("SELECT count(*) AS n FROM sqlite_master WHERE type='table'")[1].n=={count})"""
            runtime.execute(child, source.encode(), b'@borrowed_' + database.encode())
            emit('native_script_borrowed_database_verified', database=database, tables=count, independent_sqlite_oracle=True)
        runtime.execute(child, b"assert(type(GameInfo.Units)=='userdata')\nassert(type(GlobalParameters.COMBAT_BASE_DAMAGE)=='number')\nassert(Locale.IsValidKey('LOC_UNIT_SETTLER_NAME'))\nlocal ok,msg=pcall(DB.ConfigurationChanges)\nassert(not ok and string.find(msg,'baseline',1,true))\nassert(Path.GetFileName('Maps/Continents.lua')=='Continents.lua')\n", b'@borrowed_services')
        runtime.registry.release(child)
        if core_library is not None:
            game_child = runtime.acquire()
            runtime.attach_standard_libraries(game_child)
            runtime.bind_native_game_api(game_child, context, core_library)
            runtime.execute(game_child, b"assert(type(Map)=='table')\nassert(type(Map.GetGridSize)=='function')\nassert(type(Game)=='table' and type(Game.GetCurrentGameTurn)=='function')\n", b'@native_game_api_surface')
            runtime.registry.release(game_child)
        emit('native_script_core_services_verified', game_created=False, native_turns_executed=0)
    finally:
        runtime.unbind_services()
        runtime.close()

def run_execution_diagnostic(library, emit):
    kernel = C.WinDLL('kernel32', use_last_error=True)
    kernel.GetModuleHandleW.argtypes, kernel.GetModuleHandleW.restype = ([C.c_wchar_p], C.c_void_p)
    host = C.WinDLL('', handle=kernel.GetModuleHandleW(None))
    runtime = NativeScriptRuntime(library, host, emit)
    try:
        enter, leave = (host.LAB_ScriptLockEnter, host.LAB_ScriptLockLeave)
        enter.argtypes, enter.restype = ([], C.c_int)
        leave.argtypes, leave.restype = ([], C.c_int)
        if leave() != 0 or enter() != 1 or enter() != 1 or (leave() != 1) or (leave() != 1) or (leave() != 0):
            raise RuntimeError('Recursive script lock balance differs from its contract')
        emit('native_script_critical_section_verified', recursive=True, unbalanced_release_refused=True)
        first, second = (runtime.acquire(), runtime.acquire())
        runtime.attach_standard_libraries(first)
        runtime.attach_standard_libraries(second)
        runtime.attach_ui_enums(first)
        runtime.attach_ui_enums(second)
        from civ6_host.runtime.native.native_ui_enums_cases import NATIVE_UI_ENUMS_CASES
        for label, source in NATIVE_UI_ENUMS_CASES.items():
            runtime.execute(first, source.encode(), ('@' + label).encode())
        runtime.execute(first, b'Keys.Civ6RL_test=17', b'@enum_shared_write')
        runtime.execute(second, b'assert(Keys.Civ6RL_test==17); Keys.Civ6RL_test=nil', b'@enum_shared_read')
        get_filetime = kernel.GetSystemTimeAsFileTime
        get_filetime.argtypes, get_filetime.restype = ([C.POINTER(C.c_uint64)], None)
        before, after = (C.c_uint64(), C.c_uint64())
        get_filetime(C.byref(before))
        runtime.execute(first, b'observed_tick=GetTickCount()', b'@native_tick')
        get_filetime(C.byref(after))
        mask = 2147483647
        runtime.execute(first, f'assert(type(observed_tick)=="number" and observed_tick>=0 and observed_tick<={mask}); assert((observed_tick-{before.value & mask})%{mask + 1}<={after.value - before.value})'.encode(), b'@tick_witness')
        emit('native_script_tick_verified', mask=hex(mask), clock='GetSystemTimeAsFileTime', bounded_by_native_clock_reads=True)
        runtime.execute(first, b"assert(type(math.clamp)=='function' and math.clamp(7,1,5)==5)\nassert(type(table.fill)=='function' and table.count(table.fill(8,3))==3)\nassert(type(string.format)=='function' and type(coroutine.create)=='function')\nassert(type(os.clock)=='function' and os.execute==nil and os.getenv==nil)\nassert(io==nil and package==nil and rawset==nil and _G==nil and debug==nil)\nassert(getmetatable(math)==false and not pcall(function() math.abs=0 end))\nassert(type(traceback)=='function' and not pcall(include,'MapEnums'))\n", b'@restricted_libraries')
        runtime.attach_event_category(first, 1)
        runtime.attach_event_category(second, 1)
        from civ6_host.runtime.native.native_script_primitives import evaluate_lua
        if evaluate_lua(runtime.lua, runtime.root, "\nlocal a,b\nfor _,env in pairs(Threads) do if a then b=env.LuaEvents else a=env.LuaEvents end end\nassert(type(a)=='table' and type(b)=='table' and a~=b)\nassert(getmetatable(a)==LuaEventFactory[1] and getmetatable(b)==LuaEventFactory[1])\nassert(getmetatable(LuaEventsByContext[1])==LuaEventFactory[1] and LuaEvents==nil)\nlocal ok,msg=pcall(function() return a.MissingEvent end)\nassert(not ok and string.find(msg,'unresolved Lua event',1,true))\nreturn 1\n", b'@event_category_prefix') != 1:
            raise RuntimeError('Lua event category prefix witness failed')
        runtime.execute(first, b'marker=41; marker=marker+1', b'@buffer_success')
        runtime.execute(first, b'if marker~=42 then absent() end', b'@buffer_effect_witness')
        runtime.execute(second, b'if marker~=nil then absent() end', b'@buffer_isolation_witness')
        for source, label in ((b'local =', b'@compile_failure'), (b'call_missing_function()', b'@runtime_failure')):
            try:
                runtime.execute(first, source, label)
            except RuntimeError as exc:
                if 'native status' not in str(exc):
                    raise
                emit('native_script_expected_failure', name=label.decode(), error=str(exc))
            else:
                raise RuntimeError('Invalid script silently accepted')
            runtime.execute(first, b'if marker~=42 then absent() end', b'@recovery_after_error')
        from civ6_host.runtime.native.native_include_registry import IncludeSource
        runtime.set_include_sources((IncludeSource('test/a1.lua', b'order=(order or "").."1"'), IncludeSource('test/a2.lua', b'order=(order or "").."2"'), IncludeSource('test/bad.lua', b'local =')))
        runtime.attach_include(first)
        runtime.attach_include(second)
        runtime.execute(first, b"assert(select('#',include('a[12]%.lua'))==0)\nassert(order=='12'); include('a[12]%.lua'); assert(order=='1212')\nassert(select('#',include('no_such_module'))==0)\nassert(not pcall(include,'a1',{}))\nassert(not pcall(include,'['))\nassert(not pcall(include,'bad')); include('a1'); assert(order=='12121')\n", b'@include_diagnostic_pattern_order_errors')
        runtime.execute(second, b'assert(order==nil); include("a2"); assert(order=="2")', b'@include_diagnostic_environment')
        emit('native_include_snapshot_diagnostic_verified', all_matches=True, pattern_semantics=True, repeat_executes_again=True, child_environment_isolated=True, native_registry_order_verified=False, native_loader_error_policy_reproduced=False)
        runtime.registry.release(first)
        try:
            runtime.execute(first, b'marker=0', b'@released')
        except ValueError:
            pass
        else:
            raise RuntimeError('Released script context accepted')
        runtime.registry.release(second)
        emit('native_script_execution_verified', compile_errors_propagated=True, runtime_errors_propagated=True, side_effect_observed=True, recovery=True, game_created=False, native_turns_executed=0)
    finally:
        runtime.close()
