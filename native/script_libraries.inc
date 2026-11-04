/* EXE 9744c0 -> 9750e0(mode1) -> 975e90. Restricted libraries are per-child
 * filtered shallow copies behind the native read-only proxy shape. */
#include "script_library_names.inc"
static void script_copy_named_fields(LuaState* state, int source, int target,
                                     const char* const* names) {
    for (size_t i=0; names[i]; ++i) {
        th_getfield(state, source, names[i]);
        th_setfield(state, target, names[i]);
    }
}
static void script_proxy_top(LuaState* state) {
    LuaStackResult result;
    th_newtable(state, 0, 0); th_newtable(state, 0, 0);
    th_pushvalue(state, -3); th_setfield(state, -2, "__index");
    th_pushbool(state, &result, 0); th_setfield(state, -2, "__metatable");
    th_closure(state, namespace_readonly_error, 0, "lReadOnlyError", 0);
    th_setfield(state, -2, "__newindex");
    th_setmeta(state, -2); th_remove(state, -2);
}
static int __cdecl script_include_unavailable(LuaState* state) {
    return th_lerror(state, "Civ6RL unresolved include file registry/loader");
}
static int __cdecl script_tick_count(LuaState* state) {
    /* EXE 9753c0 calls 98a630(false,true): unconverted UTC FILETIME,
     * then clears bit31 of its low dword. It is not Win32 GetTickCount. */
    FILETIME value;
    GetSystemTimeAsFileTime(&value);
    th_number(state, (double)(value.dwLowDateTime & 0x7fffffffU));
    return 1;
}
static int __cdecl script_libraries_callback(LuaState* state) {
    LuaState* child=(LuaState*)th_userdata(state, 1);
    th_getfield(state, LUA_GLOBALS, "Threads");
    if (th_type(state,-1)!=5) return th_lerror(state,"Civ6RL missing thread registry");
    th_pushnil(state); int found=0;
    while (th_next(state,2)) {
        if (th_tothread(state,-2)==child) { found=1; break; }
        th_settop(state,-2);
    }
    if (!found || th_type(state,-1)!=5)
        return th_lerror(state,"Civ6RL missing child environment");
    th_remove(state,2); th_remove(state,2); /* userdata, child env */
    script_copy_named_fields(state,LUA_GLOBALS,2,script_names_globals);
    static const struct { const char* name; const char* const* fields; } libs[]={
        {"coroutine",script_names_coroutine},{"string",script_names_string},
        {"table",script_names_table},{"math",script_names_math},{"os",script_names_os}};
    for (size_t i=0; i<sizeof(libs)/sizeof(libs[0]); ++i) {
        th_getfield(state,LUA_GLOBALS,libs[i].name);
        th_newtable(state,0,0);
        script_copy_named_fields(state,3,4,libs[i].fields);
        th_remove(state,3); script_proxy_top(state);
        th_setfield(state,2,libs[i].name);
    }
    /* Include installation depends on the EXE's file registry. Preserve an
     * explicit boundary until the source-backed provider is available. */
    th_closure(state,script_include_unavailable,0,"lInclude",0);
    th_setfield(state,2,"include");
    th_getfield(state,LUA_GLOBALS,"debug"); th_getfield(state,-1,"traceback");
    int type=th_type(state,-1);
    if (type!=6 && type!=9 && type!=10)
        return th_lerror(state,"Cannot find debug.traceback method.");
    th_remove(state,-2); th_setfield(state,2,"traceback");
    th_closure(state,script_tick_count,0,"lGetTickCount",0);
    th_setfield(state,2,"GetTickCount");
    return 0;
}
__declspec(dllexport) int __cdecl LAB_ScriptLibrariesInstall(LuaState* root, LuaState* child) {
    if (root!=thread_registry_root || !script_known_child(child) || th_gettop(root)) return -1003;
    return th_cpcall(root,script_libraries_callback,child);
}
