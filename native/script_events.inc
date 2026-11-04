/* EXE 9745b0/974be0: per-category LuaEventFactory and per-context proxies.
 * Event dispatch itself (974a20 -> 9774b0) is deliberately refused until its
 * callback storage/lifetime has been reconstructed. No event is discarded. */
typedef struct ScriptEventRequest { LuaState* child; int category; } ScriptEventRequest;
static int __cdecl script_event_index_refused(LuaState* state) {
    return th_lerror(state, "Civ6RL unresolved Lua event creation/dispatch");
}
static int __cdecl script_events_callback(LuaState* state) {
    ScriptEventRequest* request = (ScriptEventRequest*)th_userdata(state, 1);
    th_getfield(state, LUA_GLOBALS, "LuaEventFactory");
    if (th_type(state, -1) == 0) {
        th_settop(state, -2); th_newtable(state, 0, 0);
        th_pushvalue(state, -1); th_setfield(state, LUA_GLOBALS, "LuaEventFactory");
    }
    if (th_type(state, -1) != 5) return th_lerror(state, "Civ6RL LuaEventFactory is not a table");
    th_rawgeti(state, 2, request->category);
    if (th_type(state, -1) == 0) {
        th_settop(state, -2); th_newtable(state, 0, 0);
        th_newtable(state, 0, 0); /* native indexer cache upvalue */
        th_closure(state, script_event_index_refused, 1, "lEventFactoryIndexer", 0);
        th_setfield(state, -2, "__index");
        th_pushvalue(state, -1); th_rawseti(state, 2, request->category);
    }
    th_remove(state, 2); /* request, category factory */
    if (th_type(state, 2) != 5) return th_lerror(state, "Civ6RL event category factory is not a table");
    th_getfield(state, LUA_GLOBALS, "LuaEventsByContext");
    if (th_type(state, -1) == 0) {
        th_settop(state, -2); th_newtable(state, 1, 0);
        th_pushvalue(state, -1); th_setfield(state, LUA_GLOBALS, "LuaEventsByContext");
    }
    if (th_type(state, -1) != 5) return th_lerror(state, "Civ6RL LuaEventsByContext is not a table");
    th_rawgeti(state, 3, request->category);
    if (th_type(state, -1) == 0) {
        th_settop(state, -2); th_newtable(state, 0, 0);
        th_pushvalue(state, 2); th_setmeta(state, -2);
        th_rawseti(state, 3, request->category);
    } else th_settop(state, -2);
    th_settop(state, 2);
    th_getfield(state, LUA_GLOBALS, "Threads");
    if (th_type(state, -1) != 5) return th_lerror(state, "Civ6RL event thread registry unavailable");
    th_pushnil(state);
    int found = 0;
    while (th_next(state, 3)) {
        if (th_tothread(state, -2) == request->child) { found = 1; break; }
        th_settop(state, -2);
    }
    if (!found || th_type(state, -1) != 5)
        return th_lerror(state, "Civ6RL event environment missing from registry");
    th_newtable(state, 0, 0);
    th_pushvalue(state, 2); th_setmeta(state, -2);
    th_setfield(state, -2, "LuaEvents");
    return 0;
}
__declspec(dllexport) int __cdecl LAB_ScriptEventsInstall(LuaState* root, LuaState* child,
                                                        int category) {
    if (root != thread_registry_root || !script_known_child(child) || th_gettop(root)) return -1003;
    if (category != 1 && category != 2) return -1700;
    ScriptEventRequest request = {child, category};
    return th_cpcall(root, script_events_callback, &request);
}
