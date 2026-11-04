/* Profile-selected protected Core registration. The engine installs its own
 * Lua callbacks. No rule implementation or arbitrary callback address is used.
 * Python verifies the exact DLL, source bytes, owner and current Lua lifetime.
 * XP2 source: context590440 -> singletonB8F0E0 / vtableA126C8;
 * +10 ->5A1DA0 forwards the Lua state to5BDAC0.
 */
typedef struct ProfileScriptCoreBinding {
    uint32_t id;
    uintptr_t singleton_rva, vtable_rva, game_method_rva;
} ProfileScriptCoreBinding;
typedef struct ProfileScriptCoreBindRequest {
    ScriptCoreBindRequest base;
    uintptr_t method_rva;
} ProfileScriptCoreBindRequest;

static const ProfileScriptCoreBinding profile_script_core_bindings[] = {
    {2, 0xb8f0e0, 0xa126c8, 0x5a1da0}
};

static int __cdecl profile_script_core_native_bind(LuaState* state) {
    ProfileScriptCoreBindRequest* request=(ProfileScriptCoreBindRequest*)th_userdata(state,1);
    th_newtable(state,0,2); th_setfield(state,LUA_GLOBALS,"MapModData");
    th_newtable(state,0,1); th_setfield(state,LUA_GLOBALS,"GameCoreState");
    typedef void (__cdecl *NativeBind)(void*,LuaState*);
    NativeBind bind=(NativeBind)(request->base.module+request->method_rva);
    bind(request->base.interface_pointer,state);
    return 0;
}

__declspec(dllexport) uint32_t __cdecl LAB_ProfileScriptCoreBindingsVersion(void) {
    return 1;
}

__declspec(dllexport) int __cdecl LAB_ProfileScriptCoreBindingsInstall(
        LuaState* root,LuaState* child,void* core_interface,void* core_module,
        uint32_t profile_id) {
    const ProfileScriptCoreBinding* profile=NULL;
    size_t index;
    for (index=0;index<sizeof(profile_script_core_bindings)/sizeof(profile_script_core_bindings[0]);++index) {
        if (profile_script_core_bindings[index].id==profile_id) {
            profile=&profile_script_core_bindings[index];break;
        }
    }
    if (!profile || !root || root!=thread_registry_root || !script_known_child(child) ||
        th_gettop(root) || th_gettop(child) || !core_interface || !core_module) return -1740;
    uintptr_t base=(uintptr_t)core_module;
    if (base>UINTPTR_MAX-profile->singleton_rva ||
        (uintptr_t)core_interface!=base+profile->singleton_rva) return -1741;
    uintptr_t* vtable=*(uintptr_t**)core_interface;
    if ((uintptr_t)vtable!=base+profile->vtable_rva ||
        vtable[2]!=base+profile->game_method_rva) return -1741;
    ProfileScriptCoreBindRequest request={{child,core_interface,base},profile->game_method_rva};
    int status=th_cpcall(root,script_core_environment,&request.base);
    if (status) return status;
    status=th_cpcall(child,profile_script_core_native_bind,&request);
    if (status) return status;
    if (th_gettop(root) || th_gettop(child)) return -1742;
    /* A returned protected outer call does not prove all subordinate binders
     * succeeded, nor that a Game exists. Native errors and API readbacks remain
     * required by the owning isolated worker. */
    return 0;
}
