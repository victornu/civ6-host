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
