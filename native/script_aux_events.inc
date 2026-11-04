/* AUX +0x90 global event delivery for Map Script category 1.
 * EXE source: 0x1404d1890 resolves LuaEvents/LuaEventsByContext and calls
 * event.Call; 0x140974a20/0x1409774b0 create the lazy event object. */
static int __cdecl script_aux_event_add(LuaState* state);
static int __cdecl script_aux_event_call(LuaState* state);
static int __cdecl script_aux_event_remove(LuaState* state);
static int __cdecl script_aux_event_remove_all(LuaState* state);
static int __cdecl script_aux_event_count(LuaState* state);

static int script_aux_listener_mutation_busy(LuaState* state) {
    LuaStackResult string_result = {0};
    th_pushstring(state, &string_result, "__Civ6RL_dispatch_busy");
    th_rawget(state, LUA_UPVALUE(1));
    int busy = th_toboolean(state, -1) != 0;
    th_settop(state, -2);
    return busy;
}
static void script_aux_set_dispatch_busy(LuaState* state, int busy) {
    LuaStackResult string_result = {0};
    th_pushstring(state, &string_result, "__Civ6RL_dispatch_busy");
    if (busy) th_number(state, 1.0); else th_pushnil(state);
    th_rawset(state, LUA_UPVALUE(1));
}

/* Event methods are dot-call closures; listener storage is the closure upvalue. */
static int __cdecl script_aux_event_add(LuaState* state) {
    if (th_gettop(state) != 1 || th_type(state, 1) != 6)
        return th_lerror(state, "LuaEvents.Add expects one function listener");
    if (script_aux_listener_mutation_busy(state))
        return th_lerror(state, "LuaEvents listener mutation during Call is refused");
    th_pushvalue(state, 1); th_rawget(state, LUA_UPVALUE(1));
    if (th_type(state, -1) != 0) {
        th_settop(state, -2);
        return th_lerror(state, "Civ6RL duplicate LuaEvents listener registration is refused");
    }
    th_settop(state, -2);
    th_rawgeti(state, LUA_UPVALUE(1), 1);
    int occupied = th_type(state, -1) != 0;
    th_settop(state, -2);
    if (occupied)
        return th_lerror(state, "Civ6RL AUX event currently supports one listener; additional listeners are refused");
    th_pushvalue(state, 1); th_number(state, 1.0);
    th_rawset(state, LUA_UPVALUE(1));
    th_pushvalue(state, 1); th_rawseti(state, LUA_UPVALUE(1), 1);
    /* EXE 977320 returns its original first argument (the listener). */
    th_settop(state, 1);
    return 1;
}

static int __cdecl script_aux_event_remove(LuaState* state) {
    if (th_gettop(state) != 1 || th_type(state, 1) != 6)
        return th_lerror(state, "LuaEvents.Remove expects one function listener");
    if (script_aux_listener_mutation_busy(state))
        return th_lerror(state, "LuaEvents listener mutation during Call is refused");
    th_pushvalue(state, 1); th_rawget(state, LUA_UPVALUE(1));
    if (th_type(state, -1) == 0) { th_settop(state, -2); return 0; }
    (void)th_checkinteger(state, -1); /* single admitted listener has ordinal one */
    th_settop(state, -2);
    th_pushnil(state); th_rawseti(state, LUA_UPVALUE(1), 1);
    th_pushvalue(state, 1); th_pushnil(state); th_rawset(state, LUA_UPVALUE(1));
    return 0;
}

static int __cdecl script_aux_event_remove_all(LuaState* state) {
    if (th_gettop(state) != 0)
        return th_lerror(state, "LuaEvents.RemoveAll expects no arguments");
    if (script_aux_listener_mutation_busy(state))
        return th_lerror(state, "LuaEvents listener mutation during Call is refused");
    LuaState* s = state;
    th_pushnil(s);
    while (th_next(s, LUA_UPVALUE(1))) {
        th_pushvalue(s, -2); th_pushnil(s);
        th_rawset(s, LUA_UPVALUE(1));
        th_settop(s, -2); /* retain the original iteration key */
    }
    return 0;
}

static int __cdecl script_aux_event_count(LuaState* state) {
    if (th_gettop(state) != 0)
        return th_lerror(state, "LuaEvents.Count expects no arguments");
    th_rawgeti(state, LUA_UPVALUE(1), 1);
    int count = th_type(state, -1) == 0 ? 0 : 1;
    th_settop(state, -2);
    th_number(state, (double)count);
    return 1;
}

static int __cdecl script_aux_event_call(LuaState* state) {
    int nargs = th_gettop(state);
    if (script_aux_listener_mutation_busy(state))
        return th_lerror(state, "Civ6RL recursive LuaEvents.Call is refused");
    th_rawgeti(state, LUA_UPVALUE(1), 1);
    if (th_type(state, -1) == 0) { th_settop(state, -2); return 0; }
    if (th_type(state, -1) != 6)
        return th_lerror(state, "LuaEvents listener registry contains a non-function");
    script_aux_set_dispatch_busy(state, 1);
    for (int arg = 1; arg <= nargs; ++arg) th_pushvalue(state, arg);
    int status = th_pcall(state, nargs, 0, 0);
    script_aux_set_dispatch_busy(state, 0);
    if (status) return th_error(state);
    return 0;
}

static int __cdecl script_aux_event_factory_index(LuaState* state) {
    if (th_gettop(state) != 2 || th_type(state, 2) != 4)
        return th_lerror(state, "LuaEvents event keys must be strings");
    th_pushvalue(state, 2); th_rawget(state, LUA_UPVALUE(1));
    if (th_type(state, -1) != 0) {
        th_pushvalue(state, 2); th_pushvalue(state, -2); th_rawset(state, 1);
        return 1;
    }
    th_settop(state, -2);

    th_newtable(state, 0, 5); /* event object */
    int event = th_gettop(state);
    th_newtable(state, 0, 0); /* stable ordinal + ordered listener array */
    int listeners = th_gettop(state);
    th_pushvalue(state, listeners);
    th_closure(state, script_aux_event_add, 1, "lAdd", 0); th_setfield(state, event, "Add");
    th_pushvalue(state, listeners);
    th_closure(state, script_aux_event_call, 1, "lCall", 0); th_setfield(state, event, "Call");
    th_pushvalue(state, listeners);
    th_closure(state, script_aux_event_remove, 1, "lRemove", 0); th_setfield(state, event, "Remove");
    th_pushvalue(state, listeners);
    th_closure(state, script_aux_event_remove_all, 1, "lRemoveAll", 0); th_setfield(state, event, "RemoveAll");
    th_pushvalue(state, listeners);
    th_closure(state, script_aux_event_count, 1, "lCount", 0); th_setfield(state, event, "Count");
    th_settop(state, event);
    th_pushvalue(state, 2); th_pushvalue(state, event); th_rawset(state, LUA_UPVALUE(1));
    th_pushvalue(state, 2); th_pushvalue(state, event); th_rawset(state, 1);
    return 1;
}

/* Replaces only category 1's lazy factory callback; child proxies created by
 * LAB_ScriptEventsInstall already point at this shared category factory. */
static int __cdecl script_aux_events_install_callback(LuaState* state) {
    th_getfield(state, LUA_GLOBALS, "LuaEventFactory");
    if (th_type(state, -1) != 5)
        return th_lerror(state, "Civ6RL LuaEventFactory is unavailable");
    th_rawgeti(state, 2, 1);
    if (th_type(state, -1) != 5)
        return th_lerror(state, "Civ6RL Map Script event factory is unavailable");
    int factory = th_gettop(state);
    th_getfield(state, factory, "_Civ6RLCache");
    if (th_type(state, -1) == 0) {
        th_settop(state, -2);
        th_newtable(state, 0, 0);
        th_newtable(state, 0, 1);
        LuaStackResult weak_mode = {0};
        th_pushstring(state, &weak_mode, "v");
        th_setfield(state, -2, "__mode");
        th_setmeta(state, -2);
        th_pushvalue(state, -1); th_setfield(state, factory, "_Civ6RLCache");
    }
    if (th_type(state, -1) != 5)
        return th_lerror(state, "Civ6RL category event cache is invalid");
    int cache = th_gettop(state);
    th_pushvalue(state, cache);
    th_closure(state, script_aux_event_factory_index, 1, "lEventFactoryIndexer", 0);
    th_setfield(state, factory, "__index");

    th_getfield(state, LUA_GLOBALS, "LuaEventsByContext");
    if (th_type(state, -1) != 5)
        return th_lerror(state, "Civ6RL LuaEventsByContext registry is unavailable");
    th_rawgeti(state, -1, 1);
    if (th_type(state, -1) != 5)
        return th_lerror(state, "Civ6RL Map Script event context is unavailable");
    return 0;
}

__declspec(dllexport) int __cdecl LAB_AuxEventsInstall(LuaState* root) {
    if (root != thread_registry_root || th_gettop(root)) return -1700;
    return th_cpcall(root, script_aux_events_install_callback, NULL);
}

typedef struct ScriptAuxEventRequest { const char* name; int category; } ScriptAuxEventRequest;
static int __cdecl script_aux_event_dispatch_callback(LuaState* state) {
    ScriptAuxEventRequest* request = (ScriptAuxEventRequest*)th_userdata(state, 1);
    if (!request || request->category != 1 || !request->name || !*request->name)
        return th_lerror(state, "Civ6RL AUX event request is invalid");
    th_getfield(state, LUA_GLOBALS, "LuaEventsByContext");
    if (th_type(state, -1) != 5)
        return th_lerror(state, "Civ6RL LuaEventsByContext registry is unavailable");
    th_rawgeti(state, -1, request->category);
    if (th_type(state, -1) != 5)
        return th_lerror(state, "Civ6RL Map Script event context is unavailable");
    th_getfield(state, -1, request->name);
    if (th_type(state, -1) != 5)
        return th_lerror(state, "Civ6RL AUX event object is not registered");
    th_getfield(state, -1, "Call");
    if (th_type(state, -1) != 6)
        return th_lerror(state, "Civ6RL AUX event Call method is unavailable");
    th_call(state, 0, 0);
    return 0;
}

/* The engine's kind-zero AUX callback passes a name and no event arguments.
 * Route that request to the source-backed category-1 registry above. */
__declspec(dllexport) int __cdecl LAB_Aux90Dispatch(LuaState* root, const char* event_name) {
    if (root != thread_registry_root || !event_name || !*event_name || th_gettop(root))
        return -1700;
    ScriptAuxEventRequest request = {event_name, 1};
    if (!LAB_ScriptLockEnter()) return -1601;
    int status = th_cpcall(root, script_aux_event_dispatch_callback, &request);
    if (!LAB_ScriptLockLeave()) return -1602;
    return status;
}
