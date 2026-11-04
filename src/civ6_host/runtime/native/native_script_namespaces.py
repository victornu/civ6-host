"""Protected namespace attachment and bounded Path diagnostics on native Havok.

This is not a complete Map Script context. ASCII C-string prefixes below 260
bytes are the only admitted Path inputs until the conversion paths are ported.
"""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import ctypes as C
import hashlib
from civ6_host.runtime.native.native_script_kernel import bind_heap
from civ6_host.runtime.native.native_script_kernel import bind_kernel
from civ6_host.runtime.native.native_script_primitives import evaluate_lua
from civ6_host.runtime.native.native_script_threads import ThreadRegistry
from civ6_host.runtime.native.native_script_threads import bind_threads

class ScriptNamespaces:
    NAMESPACE_IDS = {'Path': 1, 'GlobalParameters': 2, 'GameInfo': 3, 'DB': 4, 'Locale': 5, 'Achievements': 6}

    def __init__(self, registry, host):
        registry._check()
        self.registry = registry
        self.native = host.LAB_NamespaceRegister
        self.native.argtypes = [C.c_void_p, C.c_void_p, C.c_uint]
        self.native.restype = C.c_int

    def register(self, context, name):
        pointer = self.registry.validate(context)
        if not isinstance(name, str) or name not in self.NAMESPACE_IDS:
            raise ValueError('Unimplemented native Lua namespace')
        self.registry._status(self.native(self.registry.root, pointer, self.NAMESPACE_IDS[name]), 'namespace registration')
PATH_CASES = {'names_and_types': '\nlocal expected={GetDirectoryName=true,GetExtension=true,GetFileName=true,\n GetFileNameWithoutExtension=true,NormalizePath=true,UsesExtension=true}\nassert(table.count(Path)==6)\nfor k,f in pairs(Path) do assert(expected[k] and type(f)=="function") end\nassert(Path.GetFileName(123)=="123")\nassert(not pcall(Path.GetFileName,{}) and not pcall(Path.GetFileName))\nassert(not pcall(Path.UsesExtension,"file.txt"))\nreturn 1\n', 'components': '\nlocal cases={\n {"","","","",""},\n {"plain","","plain","","plain"},\n {"file.lua","","file.lua",".lua","file"},\n {"a.b.c","","a.b.c",".c","a.b"},\n {".hidden","",".hidden",".hidden",""},\n {"trailing.","","trailing.",".","trailing"},\n {"dir.ext/file","dir.ext/","file","","file"},\n {"dir/file.lua","dir/","file.lua",".lua","file"},\n {"dir\\\\file.lua","dir\\\\","file.lua",".lua","file"},\n {"C:relative.lua","","relative.lua",".lua","relative"},\n {":file","","file","","file"},\n {"abc:def:g.lua","","def:g.lua",".lua","def:g"},\n {"C:\\\\dir/thing.tar.gz","\\\\dir/","thing.tar.gz",".gz","thing.tar"},\n {"abc:def\\\\file","def\\\\","file","","file"},\n {"//server/share/thing","/share/","thing","","thing"},\n {"//server","","server","","server"},\n {"//","","","",""},\n {"folder/","folder/","","",""},\n {"C:","","","",""},\n {"/","/","","",""},\n}\nfor _,c in ipairs(cases) do\n assert(Path.GetDirectoryName(c[1])==c[2],"directory "..c[1])\n assert(Path.GetFileName(c[1])==c[3],"file "..c[1])\n assert(Path.GetExtension(c[1])==c[4],"extension "..c[1])\n assert(Path.GetFileNameWithoutExtension(c[1])==c[5],"stem "..c[1])\nend\nreturn 1\n', 'normalization': '\nlocal cases={{"", ""},{"a||b///c","a||b/c"},{"///a////b","//a/b"},\n {"a\\\\b\\\\c","a/b/c"},{"/a/.././b//","/a/.././b/"},\n {"||||","||||"},{"C:thing","C:thing"},{"a/","a/"},\n {"\\\\\\\\server\\\\share\\\\file","//server/share/file"}}\nfor _,c in ipairs(cases) do assert(Path.NormalizePath(c[1])==c[2],c[1]) end\nreturn 1\n', 'extensions_and_bounds': '\nassert(Path.UsesExtension("a.LuA",".lua"))\nassert(not Path.UsesExtension("a.lua","lua") and not Path.UsesExtension("a.lua",".lu"))\nassert(Path.UsesExtension("a","") and Path.UsesExtension("",""))\nassert(not Path.UsesExtension("a.lua",".sql"))\nassert(not Path.UsesExtension("a.lua",".lua"..string.char(0)))\nassert(Path.GetFileName("dir/file.lua"..string.char(0).."/ignored")=="file.lua")\nlocal allowed=string.rep("a",259); assert(Path.GetFileName(allowed)==allowed)\nfor _,f in ipairs({Path.GetFileName,Path.GetDirectoryName,Path.GetExtension,\n Path.GetFileNameWithoutExtension,Path.NormalizePath}) do\n for _,v in ipairs({string.rep("a",260),"caf"..string.char(195,169)..".lua"}) do\n  local ok,msg=pcall(f,v); assert(not ok and string.find(msg,"Civ6RL Path diagnostic refuses",1,true))\n end\nend\nassert(not pcall(Path.UsesExtension,"a.lua",string.char(195,169)))\nreturn 1\n', 'proxies': '\nlocal a,b=Envs[1].Path,Envs[2].Path\nassert(a~=b and a~=Path and b~=Path and Envs[3].Path==nil)\nassert(rawget(a,"GetFileName")==nil and a.GetFileName==Path.GetFileName)\nassert(getmetatable(a)==false and not pcall(setmetatable,a,{}))\nassert(next(a)==nil)\nlocal ok,msg=pcall(function() a.new=4 end)\nassert(not ok and string.find(msg,"Attempt to modify read-only table",1,true))\nassert(not pcall(function() a.GetFileName=3 end))\nPath.shared=12; assert(a.shared==12 and b.shared==12)\nrawset(a,"shared",99); assert(a.shared==99 and b.shared==12 and Path.shared==12)\nPath.nested={value=5}; a.nested.value=7; assert(b.nested.value==7)\nreturn 1\n'}

def run_namespace_diagnostic(library, emit):
    kernel = C.WinDLL('kernel32', use_last_error=True)
    kernel.GetModuleHandleW.argtypes, kernel.GetModuleHandleW.restype = ([C.c_wchar_p], C.c_void_p)
    host = C.WinDLL('', handle=kernel.GetModuleHandleW(None))
    lua, heap, api = (bind_kernel(library), bind_heap(host), bind_threads(host))
    primitives = host.LAB_RootPrimitivesInstall
    primitives.argtypes, primitives.restype = ([C.c_void_p], C.c_int)
    if heap['create']() != 1:
        raise RuntimeError('Namespace diagnostic cannot own heap')
    root = registry = None

    def run(source, state=None):
        return evaluate_lua(lua, root if state is None else state, source, b'@civ6rl_namespaces')
    try:
        if api['initialize'](library._handle) != 1:
            raise RuntimeError('Pinned namespace API binding failed')
        root = lua['newstate'](C.cast(heap['allocate'], C.c_void_p), None)
        if not root:
            raise RuntimeError('Root creation failed')
        lua['gc'](root, 6, 110)
        lua['gc'](root, 7, 5)
        if primitives(root):
            raise RuntimeError('Protected primitive installation failed')
        registry = ThreadRegistry(root, library, host, lua)
        namespaces = ScriptNamespaces(registry, host)
        contexts = [registry.acquire() for _ in range(3)]
        for number, context in enumerate(contexts, 1):
            run(f'marker={number}; return 1', registry.validate(context))
        run('Envs={}; Handles={}; for t,e in pairs(Threads) do Envs[e.marker]=e; Handles[e.marker]=t end; assert(Path==nil); return 1')
        for context in contexts[:2]:
            namespaces.register(context, 'Path')
        emit('script_namespaces_installed', namespace='Path', methods=6, input_scope='ASCII C-string prefixes shorter than 260 bytes', map_script_factory_ready=False, full_root_initializer=False)
        for name, source in PATH_CASES.items():
            run(source)
            emit('script_namespace_case_verified', case=name, script_sha256=hashlib.sha256(source.encode('utf-8')).hexdigest())
        for context in contexts[:2]:
            run('return Path.GetFileName("C:/Maps/Continents.lua")=="Continents.lua" and 1 or 0', registry.validate(context))
        run('return Path==nil and 1 or 0', registry.validate(contexts[2]))
        run('OldProxy=Envs[1].Path; Backend=Path; return 1')
        namespaces.register(contexts[0], 'Path')
        run('assert(Envs[1].Path~=OldProxy and Envs[1].Path.shared==12 and Path==Backend); return 1')
        run('Path=false; return 1')
        namespaces.register(contexts[0], 'Path')
        run('assert(Path==false); assert(not pcall(function() return Envs[1].Path.GetFileName end)); Path=Backend; return 1')
        namespaces.register(contexts[0], 'Path')
        run('Path=nil; return 1')
        namespaces.register(contexts[2], 'Path')
        run('assert(Path~=Backend and Path.shared==nil and Envs[1].Path.shared==12 and Envs[2].Path.shared==12 and Envs[3].Path.shared==nil); return 1')
        emit('script_namespace_cache_verified', cached_non_nil_including_false=True, fresh_proxy_per_attachment=True, old_proxies_keep_original_backend=True, actual_child_calls=2)
        run('Envs[3].Path=nil; Path=nil; setmetatable(Envs[3], {__newindex=function() error("expected_namespace_attach_error") end}); return 1')
        try:
            namespaces.register(contexts[2], 'Path')
        except RuntimeError as exc:
            if 'expected_namespace_attach_error' not in str(exc):
                raise
        else:
            raise RuntimeError('Namespace assignment error falsely succeeded')
        run('assert(type(Path)=="table" and Envs[3].Path==nil); setmetatable(Envs[3],nil); return 1')
        namespaces.register(contexts[2], 'Path')
        run('assert(Envs[3].Path.GetFileName("x/y")=="y"); Threads[Handles[1]]=nil; return 1')
        try:
            namespaces.register(contexts[0], 'Path')
        except RuntimeError as exc:
            if 'environment missing from registry' not in str(exc):
                raise
        else:
            raise RuntimeError('Missing registered environment falsely succeeded')
        run('Threads[Handles[1]]=Envs[1]; return 1')
        namespaces.register(contexts[0], 'Path')
        if namespaces.native(root, contexts[0].pointer, 999) != -1100:
            raise RuntimeError('Unknown native namespace ID accepted')
        if namespaces.native(root, 1, 1) != -1003:
            raise RuntimeError('Unknown native child accepted')
        for context in contexts:
            registry.release(context)
        if namespaces.native(root, contexts[0].pointer, 1) != -1003:
            raise RuntimeError('Released native child accepted')
        run('assert(table.count(Threads)==0); for _,e in ipairs(Envs) do assert(next(e)==nil) end; Envs=nil; Handles=nil; OldProxy=nil; Backend=nil; return 1')
        lua['gc'](root, 2, 0)
        run('assert(table.count(WeakThreads)==0); return 1')
        emit('script_namespace_failures_verified', assignment_error_propagated=True, source_cache_side_effect_retained=True, missing_environment_refused=True, unsupported_namespace_refused=True, unknown_and_released_children_refused=True, recovered=True, game_created=False, native_turns_executed=0)
    finally:
        try:
            if root:
                lua['close'](root)
                if registry:
                    registry.forget_after_root_close()
        finally:
            counters = {name: heap['counter'](i) for i, name in enumerate(('live_blocks', 'allocation_calls', 'reallocation_calls', 'free_calls'))}
            if heap['destroy']() != 1:
                raise RuntimeError(f'Namespace diagnostic heap teardown failed: {counters}')
        emit('script_namespaces_closed', **counters, full_root_initializer=False, map_script_factory_ready=False, native_turns_executed=0)
