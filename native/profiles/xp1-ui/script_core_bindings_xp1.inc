/* XP1-only sibling of script_core_bindings.inc. The Base entry points and
 * address checks remain unchanged. Source profile: native-xp1-script854.
 * XP1 outer+68 -> 4bd280 -> singleton9f6690/vtable8aaf10;
 * interface+10 -> 4cbe40 -> 4df2d0 installs the official Lua callbacks.
 * Executed only inside a protected HKS frame in a bounded diagnostic child. */
static int __cdecl script_xp1_core_native_bind(LuaState* state) {
    ScriptCoreBindRequest* request=(ScriptCoreBindRequest*)th_userdata(state,1);
    th_newtable(state,0,2); th_setfield(state,LUA_GLOBALS,"MapModData");
    th_newtable(state,0,1); th_setfield(state,LUA_GLOBALS,"GameCoreState");
    typedef void (__cdecl *NativeBind)(void*,LuaState*);
    NativeBind bind=(NativeBind)(request->module+0x4cbe40);
    bind(request->interface_pointer,state);
    return 0;
}
__declspec(dllexport) int __cdecl LAB_XP1ScriptCoreBindingsInstall(
        LuaState* root,LuaState* child,void* core_interface,void* core_module) {
    if (root!=thread_registry_root || !script_known_child(child) || th_gettop(root) ||
        th_gettop(child) || !core_interface || !core_module) return -1720;
    uintptr_t base=(uintptr_t)core_module;
    /* The Python boundary additionally verifies the installed module hash and
     * the outer getter. No arbitrary callback address is accepted here. */
    if ((uintptr_t)core_interface!=base+0x9f6690) return -1721;
    uintptr_t* vtable=*(uintptr_t**)core_interface;
    if ((uintptr_t)vtable!=base+0x8aaf10 || vtable[2]!=base+0x4cbe40) return -1721;
    ScriptCoreBindRequest request={child,core_interface,base};
    int status=th_cpcall(root,script_core_environment,&request);
    if (status) return status;
    return th_cpcall(child,script_xp1_core_native_bind,&request);
}

/* XP1-only official separate UI binder.
 * Source: xp1-ui-binding-source-v1.json SHA256
 * e4e74533e8d85320a9f4509638fb6220108235e7f00a68c302b89138d505d061.
 * interface8AAF10+18 ->4CBE50 ->4DF4E0, ABI(interface*, game*, ui*).
 * Native registration performs its own protected calls/critical section and
 * ignores subordinate protected-call failures. Zero here means ONLY that the
 * outer protected frame returned; callers must validate required bindings and
 * observe the existing native error writer. No exhaustive success claim.
 * No GameCore table is attached/copied into UI, no borrowed provider is changed.
 */
static int __cdecl script_xp1_core_native_ui_bind(LuaState* state) {
    ScriptCoreUIBindRequest* request=(ScriptCoreUIBindRequest*)th_userdata(state,1);
    typedef void (__cdecl *NativeUIBind)(void*,LuaState*,LuaState*);
    NativeUIBind bind=(NativeUIBind)(request->module+0x4cbe50);
    bind(request->interface_pointer,request->game,state);
    return 0;
}
__declspec(dllexport) int __cdecl LAB_XP1ScriptCoreUIBindingsInstall(
        LuaState* game,LuaState* ui,void* core_interface,void* core_module) {
    /* Python owns the root/module/configuration/thread lease and additionally
     * verifies source bytes and loaded engine hash before crossing this ABI. */
    if (!thread_api_ready || !thread_registry_root ||
        !script_known_child(game) || !script_known_child(ui) || game==ui ||
        th_gettop(thread_registry_root) || th_gettop(game) || th_gettop(ui) ||
        !core_interface || !core_module) return -1730;
    uintptr_t base=(uintptr_t)core_module;
    if ((uintptr_t)core_interface!=base+0x9f6690) return -1731;
    uintptr_t* vtable=*(uintptr_t**)core_interface;
    if ((uintptr_t)vtable!=base+0x8aaf10 || vtable[2]!=base+0x4cbe40 ||
        vtable[3]!=base+0x4cbe50) return -1731;
    ScriptCoreUIBindRequest request={game,core_interface,base};
    int status=th_cpcall(ui,script_xp1_core_native_ui_bind,&request);
    if (status) return status; /* Preserve the real outer Lua error on ui. */
    if (th_gettop(thread_registry_root) || th_gettop(game) || th_gettop(ui)) return -1732;
    return 0; /* Nested registration errors are NOT observable in this code. */
}
