/* AUX60 -> official owned Lua root -> locked protected call.
 * Reuse the typed dispatcher callback, with the surrounding frame intact.
 * This entry is only for recursive delivery from a live GameEvents listener.
 */
__declspec(dllexport) int __cdecl LAB_BBGGameEventsDispatchNestedTypedResult(
    LuaState* root, const char* name, const ScriptGameEventArgument* arguments, size_t count,
    unsigned int method, unsigned char* valid, unsigned char* output) {
    if (!root || root != thread_registry_root || !name || !*name ||
        strnlen(name, 256) >= 256 || count > 64 || (count && !arguments) ||
        method > 1 || !valid || !output) return -1860;

    DWORD thread = GetCurrentThreadId();
    if (script_lock_owner != thread || !script_lock_depth || !game_event_state_scope)
        return -1861;
    unsigned int depth = 0;
    for (GameEventStateScope* frame = game_event_state_scope; frame; frame = frame->previous)
        if (frame->root != root || frame->thread != thread || ++depth > 8)
            return -1861;
    int saved_top = th_gettop(root);
    if (saved_top <= 0) return -1861;
    for (size_t i = 0; i < count; ++i)
        if (arguments[i].kind > 1 ||
            (arguments[i].kind == 1 && arguments[i].value > 255)) return -1860;

    *valid = 0;
    if (method == 0) *output = 0;
    ScriptGameEventRequest request = {name, NULL, count, 0, 0,
                                     method ? "TestAll" : "Call", arguments, NULL, 0};
    if (!LAB_ScriptLockEnter()) return -1601;
    int status = th_cpcall(root, script_game_event_dispatch_callback, &request);
    int actual_top = th_gettop(root);
    if (status && actual_top == saved_top + 1) {
        size_t length = 0;
        const char* error = th_type(root, -1) == 4 ? th_tolstring(root, -1, &length) : NULL;
        if (error) fprintf(stderr, "Nested GameEvents %s: %.*s\n", name,
                           (int)(length < 512 ? length : 512), error);
        th_settop(root, saved_top);
        actual_top = th_gettop(root);
    }
    if (!LAB_ScriptLockLeave()) return -1602;
    if (actual_top != saved_top) return -1862;
    if (!status) {
        *valid = request.valid;
        if (request.valid) *output = request.result;
    }
    return status;
}
