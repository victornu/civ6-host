"""Source-backed Lua root helpers, tested only in a bounded Havok worker.

Not a complete root initializer or a GameCore Map Script service. Print uses
an explicitly diagnostic sink; unverified fill paths fail in the C bridge.
No Python callback may be used on a Lua error/unwind path.
"""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import ctypes as C
import hashlib
import math
import struct
from civ6_host.runtime.native.native_script_kernel import bind_heap
from civ6_host.runtime.native.native_script_kernel import bind_kernel
from civ6_host.runtime.native.native_script_threads import ThreadRegistry
from civ6_host.runtime.native.native_script_threads import bind_threads
PRIMITIVE_CASES = {'clamp': '\nassert(math.clamp(3,1,5)==3 and math.clamp(-4,1,5)==1)\nassert(math.clamp(12,1,5)==5 and math.clamp(3,9,2)==2)\nassert(math.clamp("3","1","5")==3 and math.clamp(3,1,5,99)==3)\nlocal n=0/0\nassert(math.clamp(n,1,5)==1)\n-- NaN results are checked by numeric bits in Python, outside Lua comparisons.\nassert(math.clamp(2,1,n)==2)\nlocal z=-1/math.huge\nassert(1/math.clamp(0,z,1)==-math.huge)\nassert(1/math.clamp(z,0,1)==math.huge)\nassert(1/math.clamp(0,-1,z)==-math.huge)\nassert(math.clamp(math.huge,1,5)==5)\nassert(not pcall(math.clamp,{},1,5) and not pcall(math.clamp,1,2))\nreturn 1\n', 'count': '\nlocal key={}; local t={[0]=false,[1]=10,[3]=30,a="a",[key]=2}\nsetmetatable(t,{__pairs=function() error("must use native next") end,\n __index=function() error("must not read missing keys") end})\nassert(table.count(t)==5 and table.count({},99)==0)\nt[1]=nil; assert(table.count(t)==4)\nassert(not pcall(table.count,4) and not pcall(table.count))\nreturn 1\n', 'fill': '\nlocal shared={}; local t=table.fill(shared,3)\nassert(table.count(t)==3 and t[1]==shared and t[2]==t[3])\nt[1].seen=9; assert(t[3].seen==9)\nlocal old={[0]=7,[1]=1,[2]=2,[3]=3,[4]=4,named="keep"}\nsetmetatable(old,{__newindex=function() error("must raw write") end})\nassert(table.fill(old,false,"3")==old)\nassert(old[0]==7 and old[1]==false and old[3]==false and old[4]==4 and old.named=="keep")\nassert(table.fill(old,nil,2)==old and rawget(old,1)==nil and rawget(old,2)==nil)\nassert(old[3]==false and table.count(table.fill(2,0))==0)\nassert(table.fill(17,"unused",0)==17 and table.fill(false,{},-3)==false)\nassert(select("#",table.fill(nil,{},0))==1)\nassert(table.count(table.fill(nil,3))==0)\nlocal frac=table.fill("x",2.9); assert(table.count(frac)==2)\nlocal fresh=setmetatable({},{__newindex=function() error("metamethod fired") end})\nassert(table.fill(fresh,5,2)==fresh and fresh[2]==5)\nfor _,args in ipairs({{}, {1}, {1,2,3,4}}) do\n local ok,msg=pcall(table.fill,unpack(args))\n assert(not ok and string.find(msg,"Invalid arguments.",1,true))\nend\nassert(not pcall(table.fill,1,{}))\nreturn 1\n', 'fill_guards': '\nfor _,args in ipairs({{1,-1},{1,1048577},{7,9,1}}) do\n local ok,msg=pcall(table.fill,unpack(args))\n assert(not ok and string.find(msg,"Civ6RL diagnostic refuses",1,true))\nend\nreturn 1\n', 'ipairs': '\nlocal t={[0]=false,[1]=11,[2]=22,[4]=44,other=8}\nlocal f,s,i=ipairs(t)\nassert(type(f)=="function" and s==t and i==-1 and select("#",ipairs(t))==3)\nlocal seen={}; for k,v in ipairs(t) do seen[#seen+1]=k end\nassert(#seen==3 and seen[1]==0 and seen[2]==1 and seen[3]==2)\nassert(select("#",f(t,2))==0)\nassert(select(3,ipairs({[1]=false}))==0)\nlocal n=0; for k,v in ipairs({false,2}) do n=n+1 end; assert(n==2)\nlocal raw=setmetatable({[1]="one",[3]="three"},{__index=function() error("raw only") end})\nassert(select(3,ipairs(raw))==0)\nassert(select("#",f(raw,1))==0 and select(2,f(raw,0))=="one")\nlocal wrapped={[-2147483648]="wrapped"}\nlocal k,v=f(wrapped,2147483647); assert(k==-2147483648 and v=="wrapped")\nassert(select(2,f(t,"0"))==11 and select(2,f(t,0.9))==11)\nassert(not pcall(ipairs,7) and not pcall(f,{},{}))\nassert(not pcall(f,7,0) and select("#",f({},0))==0)\nreturn 1\n', 'where': '\nassert(where()=="" and where(nil)=="" and where(0)=="")\nlocal location=where(1)\nassert(string.find(location,"civ6rl_primitives_where:3: ",1,true))\nassert(where(999)=="" and where(-1)=="")\nassert(type(where("1"))=="string" and not pcall(where,{}))\nreturn 1\n', 'heap_statistics': "\nassert(select('#',CollectLuaMemoryUsage())==0)\nlocal stats=GetLuaMemoryUsage()\nlocal expected={NumRegions=true,MaxUserAllocatedBytes=true,CurrentUserAllocatedBytes=true,\n CurrentAllocatedBytes=true,CurrentReservedBytes=true,CurrentOverheadBytes=true,CurrentUncommitedBytes=true}\nassert(table.count(stats)==7)\nfor name,value in pairs(stats) do\n assert(expected[name] and type(value)=='number' and value>=0 and value<=4294967295)\nend\nassert(stats.NumRegions>=1 and stats.CurrentAllocatedBytes>0 and stats.CurrentReservedBytes>0)\nreturn 1\n", 'diagnostic_print': '\nassert(select(\'#\',print(\'alpha\',17,false))==0)\nprint(\'embedded\'..string.char(0)..\'zero\',string.char(195,169))\nlocal saved=tostring\nlocal count=0\ntostring=function(v) count=count+1; tostring=function() error(\'must keep captured tostring\') end; return saved(v) end\nassert(pcall(print,\'one\',\'two\') and count==2)\ntostring=function() return 7 end\nlocal ok,msg=pcall(print,4)\nassert(not ok and string.find(msg,"\'tostring\' must return a string to \'print\'",1,true))\nlocal sentinel={}\ntostring=function() error(sentinel) end\nlocal ok,object=pcall(print,4); assert(not ok and object==sentinel)\ntostring=saved\nassert(pcall(print,\'recovered\'))\nreturn 1\n'}

def evaluate_lua(lua, state, source, chunk_name=b'@civ6rl_primitives'):
    """Protected execution; never coerce an error object outside lua_pcall."""
    if lua['gettop'](state) != 0:
        raise RuntimeError('Unbalanced Lua stack before primitive script')
    try:
        script = source.encode('utf-8')
        status = lua['loadbuffer'](state, script, len(script), chunk_name)
        stage = 'load'
        if not status:
            status = lua['pcall'](state, 0, 1, 0)
            stage = 'runtime'
        if status:
            message = '<non-string Lua error>'
            if lua['gettop'](state) and lua['type'](state, -1) == 4:
                length = C.c_size_t()
                ptr = lua['tolstring'](state, -1, C.byref(length))
                if ptr:
                    message = C.string_at(ptr, min(length.value, 2048)).decode('utf-8', 'replace')
            raise RuntimeError(f'Primitive script {stage} status {status}: {message}')
        if lua['gettop'](state) != 1 or lua['type'](state, -1) != 3 or lua['tonumber'](state, -1) != 1.0:
            raise RuntimeError('Unexpected primitive script result')
        return 1.0
    finally:
        lua['settop'](state, 0)

def run_primitive_diagnostic(library, emit):
    kernel = C.WinDLL('kernel32', use_last_error=True)
    kernel.GetModuleHandleW.argtypes, kernel.GetModuleHandleW.restype = ([C.c_wchar_p], C.c_void_p)
    host = C.WinDLL('', handle=kernel.GetModuleHandleW(None))
    lua, heap, api = (bind_kernel(library), bind_heap(host), bind_threads(host))
    install = host.LAB_RootPrimitivesInstall
    install.argtypes, install.restype = ([C.c_void_p], C.c_int)
    if heap['create']() != 1:
        raise RuntimeError('Primitive diagnostic cannot own heap')
    root = registry = None
    try:
        if api['initialize'](library._handle) != 1:
            raise RuntimeError('Pinned primitive API binding failed')
        if install(None) != -1000:
            raise RuntimeError('Null VM installation accepted')
        root = lua['newstate'](C.cast(heap['allocate'], C.c_void_p), None)
        if not root:
            raise RuntimeError('Root creation failed')
        lua['gc'](root, 6, 110)
        lua['gc'](root, 7, 5)
        if install(root):
            raise RuntimeError('Protected root primitive installation failed')
        emit('script_primitives_installed', full_root_initializer=False, map_script_factory_ready=False, implemented=['math.clamp', 'table.count', 'table.fill', 'ipairs', 'where', 'GetLuaMemoryUsage', 'CollectLuaMemoryUsage'], diagnostic_only=['print: stderr sink; native routing not yet reproduced'], diagnostic_guards=['fill count > 1048576', 'two-argument fill negative count', 'positive fill count with non-table target'])
        for expression, expected in (('0/0', 'nan'), ('math.clamp(2,0/0,5)', 'nan'), ('math.clamp(2,1,0/0)', 2.0), ('math.clamp(0/0,1,5)', 1.0), ('math.clamp(0,-1/math.huge,1)', -0.0), ('math.clamp(-1/math.huge,0,1)', 0.0), ('math.clamp(0,-1,-1/math.huge)', -0.0), ('(function() local a=0/0; return a~=a and 1 or 0 end)()', 0.0)):
            script = ('return ' + expression).encode('ascii')
            if lua['loadbuffer'](root, script, len(script), b'@primitive_nan_witness') or lua['pcall'](root, 0, 1, 0) or lua['type'](root, -1) != 3:
                raise RuntimeError('NaN numeric witness failed')
            value = lua['tonumber'](root, -1)
            lua['settop'](root, 0)
            if not (math.isnan(value) if expected == 'nan' else struct.pack('<d', value) == struct.pack('<d', expected)):
                raise RuntimeError(f'Numeric witness differs: {expression}: {value!r}')
            emit('script_primitive_numeric_witness', expression=expression, ieee754_le_hex=struct.pack('<d', value).hex(), verified=True)
        for name, source in PRIMITIVE_CASES.items():
            evaluate_lua(lua, root, source, ('@civ6rl_primitives_' + name).encode('ascii'))
            emit('script_primitive_case_verified', case=name, script_sha256=hashlib.sha256(source.encode('utf-8')).hexdigest())
        registry = ThreadRegistry(root, library, host, lua)
        contexts = [registry.acquire() for _ in range(2)]
        for context in contexts:
            evaluate_lua(lua, registry.validate(context), 'if math==nil then return 1 else return 0 end')
        for context in contexts:
            registry.release(context)
        evaluate_lua(lua, root, PRIMITIVE_CASES['ipairs'])
        evaluate_lua(lua, root, 'assert(table.count(Threads)==0); return 1')
        emit('script_primitives_registry_composition_verified', contexts=2, root_functions_retained=True, child_bindings_installed=False, game_created=False, native_turns_executed=0)
    finally:
        try:
            if root:
                lua['close'](root)
                if registry:
                    registry.forget_after_root_close()
        finally:
            counters = {name: heap['counter'](i) for i, name in enumerate(('live_blocks', 'allocation_calls', 'reallocation_calls', 'free_calls'))}
            if heap['destroy']() != 1:
                raise RuntimeError(f'Primitive diagnostic heap teardown failed: {counters}')
        emit('script_primitives_closed', **counters, full_root_initializer=False, map_script_factory_ready=False, native_turns_executed=0)
