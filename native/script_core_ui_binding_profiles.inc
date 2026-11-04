/* Official UI registration, selected by the same immutable Core profile ID.
 * XP2 source cfbf441b0b279dfe48b1b6fd674f6305e5ba0ad57d84ed1d0ff0fb5b870fb1fa:
 * singleton B8F0E0 / vtable A126C8 +18 ->5A1DB0 ->5BDD80.
 * Native code retains its registration order, mode, lock and error writer.
 * No Lua gameplay tables or callbacks are synthesized here.
 */
typedef struct ProfileScriptCoreUIBindRequest {
    ScriptCoreUIBindRequest base;
    uintptr_t method_rva;
} ProfileScriptCoreUIBindRequest;

static int __cdecl profile_script_core_native_ui_bind(LuaState* state) {
    ProfileScriptCoreUIBindRequest* request=(ProfileScriptCoreUIBindRequest*)th_userdata(state,1);
    typedef void (__cdecl *NativeUIBind)(void*,LuaState*,LuaState*);
    NativeUIBind bind=(NativeUIBind)(request->base.module+request->method_rva);
    bind(request->base.interface_pointer,request->base.game,state);
    return 0;
}

__declspec(dllexport) int __cdecl LAB_ProfileScriptCoreUIBindingsInstall(
        LuaState* game,LuaState* ui,void* core_interface,void* core_module,
        uint32_t profile_id) {
    const ProfileScriptCoreBinding* profile=NULL;
    uintptr_t ui_method_rva;
    size_t index;
    /* No caller-supplied native address and no fallback to another engine. */
    if (profile_id!=2) return -1750;
    ui_method_rva=0x5a1db0;
    for (index=0;index<sizeof(profile_script_core_bindings)/sizeof(profile_script_core_bindings[0]);++index) {
        if (profile_script_core_bindings[index].id==profile_id) {
            profile=&profile_script_core_bindings[index];break;
        }
    }
    if (!profile || !thread_api_ready || !thread_registry_root ||
        !script_known_child(game) || !script_known_child(ui) || game==ui ||
        th_gettop(thread_registry_root) || th_gettop(game) || th_gettop(ui) ||
        !core_interface || !core_module) return -1750;
    uintptr_t base=(uintptr_t)core_module;
    if (base>UINTPTR_MAX-profile->singleton_rva ||
        (uintptr_t)core_interface!=base+profile->singleton_rva) return -1751;
    uintptr_t* vtable=*(uintptr_t**)core_interface;
    if ((uintptr_t)vtable!=base+profile->vtable_rva ||
        vtable[2]!=base+profile->game_method_rva ||
        vtable[3]!=base+ui_method_rva) return -1751;
    ProfileScriptCoreUIBindRequest request={{game,core_interface,base},ui_method_rva};
    int status=th_cpcall(ui,profile_script_core_native_ui_bind,&request);
    if (status) return status; /* Keep the actual outer error on the UI child. */
    if (th_gettop(thread_registry_root) || th_gettop(game) || th_gettop(ui)) return -1752;
    /* The native enclosing body ignores subordinate protected statuses.
     * This result therefore proves only that the outer frame returned. */
    return 0;
}
