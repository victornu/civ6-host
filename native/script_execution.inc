/* EXE DB4760 -> luaL_loadbuffer and DB35E0 -> protected execution.
 * This adapter deliberately preserves the failure for the Python supervisor;
 * it does not reproduce the EXE's log-and-ignore file-error continuation.
 * File lookup/ownership is outside this buffer executor, never substituted. */
typedef struct ScriptBufferRequest {
    const char* bytes;
    size_t length;
    const char* name;
} ScriptBufferRequest;
static __declspec(thread) unsigned int script_protected_depth = 0;

static int script_known_child(LuaState* child) {
    if (!thread_registry_root || !child) return 0;
    for (size_t i = 0; i < 64; ++i) if (host_threads[i] == child) return 1;
    return 0;
}
static int __cdecl script_buffer_callback(LuaState* state) {
    ScriptBufferRequest* request = (ScriptBufferRequest*)th_userdata(state, 1);
    int status = th_loadbuffer(state, request->bytes, request->length, request->name);
    if (status) return th_error(state);
    th_call(state, 0, 0);
    return 0;
}
__declspec(dllexport) int __cdecl LAB_ScriptExecuteBuffer(LuaState* child, const char* bytes,
                                                       size_t length, const char* name) {
    if (!script_known_child(child) || th_gettop(child) != 0) return -1003;
    if (!bytes || !name || length > 16 * 1024 * 1024 || strnlen(name, 1301) > 1300) return -1600;
    ScriptBufferRequest request = { bytes, length, name };
    ++script_protected_depth;
    int status = th_cpcall(child, script_buffer_callback, &request);
    --script_protected_depth;
    return status;
}

/* Host-owned Python/Lua transport, not a replacement gameplay rule. Copy the
 * result while protected and while its Lua string remains rooted on stack. */
typedef struct ScriptTextResultRequest {
    ScriptBufferRequest script;
    char* output;
    size_t capacity;
    size_t* written;
} ScriptTextResultRequest;

static int __cdecl script_text_result_callback(LuaState* state) {
    ScriptTextResultRequest* request = (ScriptTextResultRequest*)th_userdata(state, 1);
    int status = th_loadbuffer(state, request->script.bytes,
                              request->script.length, request->script.name);
    if (status) return th_error(state);
    th_call(state, 0, 1);
    if (th_type(state, -1) != 4)
        return th_lerror(state, "Civ6RL result must be a string");
    size_t length = 0;
    const char* text = th_tolstring(state, -1, &length);
    if (!text || length > request->capacity)
        return th_lerror(state, "Civ6RL result exceeds output capacity");
    memcpy(request->output, text, length);
    *request->written = length;
    return 0;
}

__declspec(dllexport) int __cdecl LAB_ScriptEvaluateText(LuaState* child, const char* bytes,
        size_t length, const char* name, char* output, size_t capacity, size_t* written) {
    if (!script_known_child(child) || th_gettop(child) != 0) return -1003;
    if (!bytes || !name || !output || !written || capacity > 16*1024*1024 ||
        length > 16*1024*1024 || strnlen(name,1301)>1300) return -1600;
    *written = 0;
    ScriptTextResultRequest request = {{bytes,length,name},output,capacity,written};
    if (!LAB_ScriptLockEnter()) return -1601;
    ++script_protected_depth;
    int status = th_cpcall(child,script_text_result_callback,&request);
    --script_protected_depth;
    if (!LAB_ScriptLockLeave()) return -1602;
    return status;
}

/* Caller must validate that the callback is native and has the source-backed
 * lua_CFunction ABI. Lua errors cannot cross a Python callback frame. */
__declspec(dllexport) int __cdecl LAB_ScriptProtectedCall(LuaState* child, LuaCallback callback,
                                                       void* userdata) {
    if (!script_known_child(child) || th_gettop(child) != 0 || !callback) return -1003;
    if (!LAB_ScriptLockEnter()) return -1601;
    ++script_protected_depth;
    int status = th_cpcall(child, callback, userdata);
    --script_protected_depth;
    if (!LAB_ScriptLockLeave()) return -1602;
    return status;
}

/* EXE auxiliary +58 (161900 -> DB35e0): lua_pcall(nargs,nresults,0)
 * under the same recursive lock. Keep error text for the strict supervisor. */
__declspec(dllexport) int __cdecl LAB_ScriptProtectedStackCall(LuaState* child,
                                                            int nargs,int nresults) {
    if (!script_known_child(child) || nargs < 0 || nargs > 1024 ||
        nresults < -1 || nresults > 1024 || th_gettop(child) < nargs+1) return -1003;
    if (!LAB_ScriptLockEnter()) return -1601;
    ++script_protected_depth;
    int status = th_pcall(child,nargs,nresults,0);
    --script_protected_depth;
    if (!LAB_ScriptLockLeave()) return -1602;
    return status;
}
