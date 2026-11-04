/* EXE 162ae0/1629f0: cache the root library, then 973e70 copies its
 * contents into the child's environment. These are shared group tables,
 * not read-only namespace proxies. */
#include "script_ui_enums.inc"
static void script_copy_library_contents(LuaState* state, int source, int target) {
    th_pushnil(state);
    while (th_next(state, source)) {
        th_pushvalue(state, -2);
        th_pushvalue(state, -2);
        (void)th_tolstring(state, -2, NULL);
        (void)th_tolstring(state, -1, NULL);
        th_settable(state, target);
        th_settop(state, -2);
    }
}
static int __cdecl script_ui_attach_callback(LuaState* state) {
    LuaState* child=(LuaState*)th_userdata(state, 1);
    th_getfield(state,LUA_GLOBALS,"Threads");
    th_pushnil(state); int found=0;
    while (th_next(state,2)) {
        if (th_tothread(state,-2)==child) { found=1; break; }
        th_settop(state,-2);
    }
    if (!found || th_type(state,-1)!=5)
        return th_lerror(state,"Civ6RL missing enum child environment");
    th_remove(state,2); th_remove(state,2);
    static const struct { const char* name; LuaCallback create; } libraries[]={
        {"UIEnumsLibrary",namespace_create_ui_enums},
        {"AppUIEnumsLibrary",namespace_create_app_ui_enums}};
    for (size_t i=0;i<sizeof(libraries)/sizeof(libraries[0]);++i) {
        th_getfield(state,LUA_GLOBALS,libraries[i].name);
        if (th_type(state,-1)==0) {
            th_settop(state,-2);
            th_closure(state,libraries[i].create,0,libraries[i].name,0);
            th_call(state,0,1);
            th_pushvalue(state,-1); th_setfield(state,LUA_GLOBALS,libraries[i].name);
        }
        script_copy_library_contents(state,3,2);
        th_settop(state,2);
    }
    return 0;
}
__declspec(dllexport) int __cdecl LAB_ScriptUIEnumsInstall(LuaState* root, LuaState* child) {
    if (root!=thread_registry_root || !script_known_child(child) || th_gettop(root)) return -1003;
    return th_cpcall(root,script_ui_attach_callback,child);
}
