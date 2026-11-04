/* Native game API binding prefix: EXE 161160 / 1614a0, Core outer +68
 * returns interface whose +10 is 43bce0 -> 44eeb0. No gameplay APIs are
 * reconstructed here: Core itself installs its C callbacks in HKS. */
typedef struct ScriptCoreBindRequest {
    LuaState* child;
    void* interface_pointer;
    uintptr_t module;
} ScriptCoreBindRequest;
static int __cdecl script_core_environment(LuaState* state) {
    ScriptCoreBindRequest* request=(ScriptCoreBindRequest*)th_userdata(state,1);
    th_getfield(state,LUA_GLOBALS,"GameCore");
    if (th_type(state,-1)!=0) return th_lerror(state,"Civ6RL GameCore cache already exists");
    th_settop(state,1);
    th_getfield(state,LUA_GLOBALS,"Threads"); th_pushnil(state);
    int found=0;
    while (th_next(state,2)) {
        if (th_tothread(state,-2)==request->child) { found=1; break; }
        th_settop(state,-2);
    }
    if (!found || th_type(state,-1)!=5) return th_lerror(state,"Civ6RL Core environment missing");
    th_remove(state,2); /* userdata, thread, original environment */
    th_newtable(state,0,0);
    th_pushvalue(state,-1); th_setfield(state,LUA_GLOBALS,"GameCore");
    th_newtable(state,0,0); th_pushvalue(state,3);
    th_setfield(state,-2,"__index"); th_setmeta(state,-2);
    if (!th_setenv(state,2)) return th_lerror(state,"Civ6RL Core environment swap failed");
    return 0;
}
static int __cdecl script_core_native_bind(LuaState* state) {
    ScriptCoreBindRequest* request=(ScriptCoreBindRequest*)th_userdata(state,1);
    th_newtable(state,0,2); th_setfield(state,LUA_GLOBALS,"MapModData");
    th_newtable(state,0,1); th_setfield(state,LUA_GLOBALS,"GameCoreState");
    typedef void (__cdecl *NativeBind)(void*,LuaState*);
    NativeBind bind=(NativeBind)(request->module+0x43bce0);
    bind(request->interface_pointer,state);
    return 0;
}
__declspec(dllexport) int __cdecl LAB_ScriptCoreBindingsInstall(
        LuaState* root,LuaState* child,void* core_interface,void* core_module) {
    if (root!=thread_registry_root || !script_known_child(child) || th_gettop(root) ||
        th_gettop(child) || !core_interface || !core_module) return -1700;
    uintptr_t base=(uintptr_t)core_module;
    uintptr_t* vtable=*(uintptr_t**)core_interface;
    if ((uintptr_t)vtable!=base+0x79fe70 || vtable[2]!=base+0x43bce0) return -1701;
    ScriptCoreBindRequest request={child,core_interface,base};
    int status=th_cpcall(root,script_core_environment,&request);
    if (status) return status;
    return th_cpcall(child,script_core_native_bind,&request);
}
static int __cdecl script_core_attach(LuaState* state) {
    LuaState* child=(LuaState*)th_userdata(state,1);
    th_getfield(state,LUA_GLOBALS,"Threads"); th_pushnil(state);
    int found=0;
    while (th_next(state,2)) {
        if (th_tothread(state,-2)==child) { found=1; break; }
        th_settop(state,-2);
    }
    if (!found || th_type(state,-1)!=5) return th_lerror(state,"Civ6RL Core attach environment missing");
    th_remove(state,2); th_remove(state,2);
    th_getfield(state,LUA_GLOBALS,"GameCore"); th_checktype(state,-1,5);
    script_copy_library_contents(state,3,2);
    return 0;
}
__declspec(dllexport) int __cdecl LAB_ScriptCoreBindingsAttach(LuaState* root,LuaState* child) {
    if (root!=thread_registry_root || !script_known_child(child) || th_gettop(root)) return -1700;
    return th_cpcall(root,script_core_attach,child);
}

typedef struct ScriptCoreUIBindRequest {
    LuaState* game;
    void* interface_pointer;
    uintptr_t module;
} ScriptCoreUIBindRequest;
static int __cdecl script_core_native_ui_bind(LuaState* state) {
    ScriptCoreUIBindRequest* request=(ScriptCoreUIBindRequest*)th_userdata(state,1);
    /* Core43bcf0 forwards its second/third arguments to44f0c0. That routine
     * installs Core's UI-facing callbacks in the third argument's Lua state.
     * The host supplies no replacement gameplay/visibility implementation. */
    typedef void (__cdecl *NativeUIBind)(void*,LuaState*,LuaState*);
    NativeUIBind bind=(NativeUIBind)(request->module+0x43bcf0);
    bind(request->interface_pointer,request->game,state);
    return 0;
}
__declspec(dllexport) int __cdecl LAB_ScriptCoreUIBindingsInstall(
        LuaState* game,LuaState* ui,void* core_interface,void* core_module) {
    if (!script_known_child(game) || !script_known_child(ui) || game==ui ||
        th_gettop(game) || th_gettop(ui) || !core_interface || !core_module) return -1710;
    uintptr_t base=(uintptr_t)core_module;
    uintptr_t* vtable=*(uintptr_t**)core_interface;
    if ((uintptr_t)vtable!=base+0x79fe70 || vtable[3]!=base+0x43bcf0) return -1711;
    ScriptCoreUIBindRequest request={game,core_interface,base};
    return th_cpcall(ui,script_core_native_ui_bind,&request);
}
