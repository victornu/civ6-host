/* ABI diagnostic only: expose a supplied native provider/primitive through C
 * while Lua executes, to exercise the existing A8/A0 bridges without a game.
 * It does not implement a gameplay API or fabricate game-owned values.
 */
typedef struct EventStateDiagnostic {
    void* owner;
    const void* map;
    unsigned char scalar[24];
} EventStateDiagnostic;

static int __cdecl event_state_diagnostic_get(LuaState* state) {
    EventStateDiagnostic* data=(EventStateDiagnostic*)th_userdata(state,LUA_UPVALUE(1));
    if(!data)return th_lerror(state,"Missing event state diagnostic values");
    LAB_AuxPushMap(data->owner,state,data->map,1);
    LAB_AuxPushVariant(data->owner,state,data->scalar);
    LuaStackResult result={0};
    th_pushbool(state,&result,(unsigned char)LAB_GameEventsStateIsActive(thread_registry_root,state));
    return 3;
}

static int __cdecl event_state_diagnostic_install(LuaState* state) {
    EventStateDiagnostic* input=(EventStateDiagnostic*)th_userdata(state,1);
    EventStateDiagnostic* copy=(EventStateDiagnostic*)th_newuserdata(state,sizeof(*copy));
    memcpy(copy,input,sizeof(*copy));
    th_closure(state,event_state_diagnostic_get,1,"func",0);
    th_setfield(state,LUA_GLOBALS,"CivHostEventStateNativeProbe");
    return 0;
}

__declspec(dllexport) int __cdecl LAB_GameEventsStateDiagnosticInstall(
        LuaState* child,void* owner,const void* map,const void* scalar) {
    if(!script_known_child(child) || th_gettop(child) || !owner || !map || !scalar)return -1980;
    EventStateDiagnostic input={owner,map,{0}};
    memcpy(input.scalar,scalar,sizeof(input.scalar));
    return th_cpcall(child,event_state_diagnostic_install,&input);
}
