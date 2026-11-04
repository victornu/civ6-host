/* EXE auxiliary+10:161d00 -> manager+20:9720a0. Notification only.
 * The constructor971a40 initializes the optional context/callback pair to0.
 * This component owns that pair; it is NOT a Tuner context factory or debugger.
 * Unknown receivers/children and the malformed context-without-function state
 * are refused. Never infer complete script initialization from return code0.
 */
typedef void (__cdecl *ScriptContextNotifyCallback)(void*,LuaState*);
typedef struct ScriptContextNotifyState {
    LuaState* root;
    void* receiver;
    void* context;
    ScriptContextNotifyCallback callback;
} ScriptContextNotifyState;
static ScriptContextNotifyState script_context_notify;

static int script_context_notify_dispatch(void* context,ScriptContextNotifyCallback callback,LuaState* child) {
    if (!child) return 0;
    if (context || callback) {
        if (!callback) return -1886; /* Native malformed pair would jump toNULL. */
        callback(context,child);
    }
    return 0;
}
__declspec(dllexport) int __cdecl LAB_ScriptContextNotifyBind(LuaState* root,void* receiver) {
    if (!root || root!=thread_registry_root || !thread_api_ready || th_gettop(root) ||
        !receiver || script_context_notify.root) return -1887;
    script_context_notify=(ScriptContextNotifyState){root,receiver,NULL,NULL};
    return 0;
}
__declspec(dllexport) int __cdecl LAB_ScriptContextNotifySetHook(LuaState* root,void* context,
        ScriptContextNotifyCallback callback) {
    if (!root || root!=script_context_notify.root || root!=thread_registry_root ||
        th_gettop(root) || (context && !callback)) return -1887;
    script_context_notify.context=context;script_context_notify.callback=callback;
    return 0;
}
__declspec(dllexport) int __cdecl LAB_ScriptContextNotify(LuaState* root,void* receiver,LuaState* child) {
    if (!root || root!=thread_registry_root || root!=script_context_notify.root ||
        !receiver || receiver!=script_context_notify.receiver || th_gettop(root) ||
        (child && !script_known_child(child))) return -1887;
    return script_context_notify_dispatch(script_context_notify.context,script_context_notify.callback,child);
}
__declspec(dllexport) int __cdecl LAB_ScriptContextNotifyUnbind(LuaState* root,void* receiver) {
    if (!root || root!=script_context_notify.root || root!=thread_registry_root ||
        !receiver || receiver!=script_context_notify.receiver || th_gettop(root)) return -1887;
    script_context_notify=(ScriptContextNotifyState){0};return 0;
}

