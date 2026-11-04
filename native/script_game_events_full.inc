/*
 * GameEvents listener implementation, derived from the pinned
 * EXE methods at 0x1404db0e0, 0x1404dadf0, 0x1403cecd0, 0x1404db1a0,
 * 0x1404db300 and 0x1404dae50. Included through script_game_events.inc; APIs are hash/RVA checked by
 * LAB_ThreadAPIInitialize. Aggregation helpers have separate source captures.
 *
 * It uses the existing th_* LuaPlus bindings from gamecore_python_host.c.
 */
static int __cdecl game_events_full_require_apis(LuaState* state) {
    if (th_getenv && th_rawequal) return 0;
    return th_lerror(state, "GameEvents listener APIs are not bound");
}

#include "script_game_event_aggregators.inc"

static int __cdecl game_events_full_add(LuaState* state) {
    int top = th_gettop(state);
    if (top < 1) return th_lerror(state, "GameEvents.Add requires a listener value");
    size_t length = th_objlen(state, LUA_UPVALUE(1));
    if (length >= 0x7ffffffeU)
        return th_lerror(state, "GameEvents listener array exceeds native index range");
    th_pushvalue(state, -1);
    th_rawseti(state, LUA_UPVALUE(1), (int)length + 1);
    /* Native Add returns the original top value (not a Boolean). */
    return 1;
}

static int __cdecl game_events_full_count(LuaState* state) {
    th_number(state, (double)(int)th_objlen(state, LUA_UPVALUE(1)));
    return 1;
}

static int __cdecl game_events_full_remove(LuaState* state) {
    if (game_events_full_require_apis(state)) return 0;
    int saved_top = th_gettop(state);
    if (saved_top < 1) return 0;
    size_t length = th_objlen(state, LUA_UPVALUE(1));
    int scan = 0;

    /* The native loop begins with a nil sentinel, then visits 1..objlen.
     * Its comparison operand is the topmost Remove argument. On a match it
     * shifts slots [scan..length] left and then advances scan, matching the
     * source loop's post-remove advance rather than a generalized erase. */
    th_pushnil(state);
    do {
        int argument = saved_top > 0 ? saved_top : 0;
        if (th_rawequal(state, argument, -1)) {
            for (int shift = scan; shift <= (int)length; ++shift) {
                th_rawgeti(state, LUA_UPVALUE(1), shift + 1);
                th_rawseti(state, LUA_UPVALUE(1), shift);
            }
        }
        th_settop(state, -2);
        ++scan;
        th_rawgeti(state, LUA_UPVALUE(1), scan);
    } while (th_type(state, -1) != 0);
    th_settop(state, saved_top);
    return 0;
}

static int __cdecl game_events_full_remove_all(LuaState* state) {
    size_t length = th_objlen(state, LUA_UPVALUE(1));
    for (int index = 1; index <= (int)length; ++index) {
        th_pushnil(state);
        th_rawseti(state, LUA_UPVALUE(1), index);
    }
    return 0;
}

static int __cdecl game_events_reserve_listener_stack(LuaState* state) {
    const int* count = (const int*)th_userdata(state, 1);
    if (!count || *count < 0)
        return th_lerror(state, "Invalid GameEvents listener stack reservation");
    th_checkstack(state, *count + 4, "GameEvents listener stack");
    return 0;
}

static int __cdecl game_events_full_call(LuaState* state) {
    if (game_events_full_require_apis(state)) return 0;
    int nargs = th_gettop(state);
    int invoked = 0;
    int aggregate = 1;
    int group_index = LUA_UPVALUE(1);
    th_checkstack(state, nargs + 12, "GameEvents listener transfer stack");

    th_pushnil(state);
    while (th_next(state, group_index)) {
        if (th_type(state, -1) == 5) {
            int listeners_index = th_gettop(state);
            size_t count = th_objlen(state, listeners_index);
            if (count > 0x7ffffffeU)
                return th_lerror(state, "GameEvents listener array exceeds native index range");
            for (int index = 1; index <= (int)count; ++index) {
                int iteration_top = th_gettop(state);
                LuaState* child = th_newthread(state); /* also pushes thread object */
                if (!child)
                    return th_lerror(state, "GameEvents could not create listener thread");
                /* XMove copies raw HKS slots without growing the destination.
                 * Reserve while protected on the destination itself: a stack
                 * allocation failure must not cross an unprotected thread. */
                int reserved = th_cpcall(child, game_events_reserve_listener_stack, &nargs);
                th_settop(child, 0);
                if (reserved)
                    return th_lerror(state, "GameEvents listener stack reservation failed");
                int thread_object = iteration_top + 1;
                th_rawgeti(state, listeners_index, index);
                th_getenv(state, -1); /* function environment */
                th_setenv(state, thread_object);     /* copy it to new thread */

                /* The native implementation copies listener + every Call
                 * argument, preserving their original order, to this thread. */
                th_settop(state, thread_object);
                th_rawgeti(state, listeners_index, index);
                for (int arg = 1; arg <= nargs; ++arg) th_pushvalue(state, arg);
                th_xmove(state, child, nargs + 1);

                invoked = 1; /* native marks a listener attempted before pcall */
                if (!LAB_ScriptLockEnter()) {
                    th_settop(state, iteration_top);
                    return th_lerror(state, "GameEvents listener lock is unavailable");
                }
                int status = th_pcall(child, nargs, 1, 0);
                int lock_left = LAB_ScriptLockLeave();
                if (status == 0 && th_gettop(child) > 0)
                    aggregate = aggregate && (th_toboolean(child, -1) != 0);
                /* Both successful result and protected error object are discarded. */
                th_settop(child, 0);
                th_settop(state, iteration_top); /* preserve next() key/value */
                if (!lock_left)
                    return th_lerror(state, "GameEvents listener lock release failed");
            }
        }
        th_settop(state, -2); /* retain key for the next hks_obj_next */
    }
    if (invoked) {
        LuaStackResult result = {0};
        th_pushbool(state, &result, (unsigned char)(aggregate != 0));
    }
    else th_pushnil(state); /* exact 4DB087 -> 4DB0B3 empty result */
    return 1;
}

static int __cdecl game_events_full_index(LuaState* state) {
    if (th_gettop(state) != 2 || th_type(state, 2) != 4)
        return th_lerror(state, "GameEvents event name must be a string");
    th_pushvalue(state, 2); th_rawget(state, LUA_UPVALUE(1));
    if (th_type(state, -1) == 0) {
        th_settop(state, -2);
        th_newtable(state, 0, 0); /* weak group: each value is a context list */
        th_newtable(state, 0, 1);
        LuaStackResult weak = {0};
        th_pushstring(state, &weak, "v"); th_setfield(state, -2, "__mode");
        th_setmeta(state, -2);
        th_pushvalue(state, 2); th_pushvalue(state, -2); th_rawset(state, LUA_UPVALUE(1));
    }
    if (th_type(state, -1) != 5)
        return th_lerror(state, "GameEvents shared listener group is invalid");
    int group = th_gettop(state);
    size_t contexts = th_objlen(state, group);
    if (contexts >= 64) return th_lerror(state, "GameEvents context bound exceeded");

    th_newtable(state, 0, 9);
    int event = th_gettop(state);
    th_newtable(state, 0, 0);
    int listeners = th_gettop(state);
    th_pushvalue(state, listeners); th_rawseti(state, group, (int)contexts + 1);

    th_pushvalue(state, listeners);
    th_closure(state, game_events_full_add, 1, "func", 0);
    th_setfield(state, event, "Add");
    th_pushvalue(state, listeners);
    th_closure(state, game_events_full_count, 1, "func", 0);
    th_setfield(state, event, "Count");
    th_pushvalue(state, listeners);
    th_closure(state, game_events_full_remove, 1, "func", 0);
    th_setfield(state, event, "Remove");
    th_pushvalue(state, listeners);
    th_closure(state, game_events_full_remove_all, 1, "func", 0);
    th_setfield(state, event, "RemoveAll");
    th_pushvalue(state, group);
    th_closure(state, game_events_full_call, 1, "func", 0);
    th_setfield(state, event, "Call");

    game_events_aggregators_bind_methods(state, event, group);
    th_settop(state, event);
    th_newtable(state, 0, 1); th_newtable(state, 0, 0);
    th_setfield(state, -2, "__metatable"); th_setmeta(state, event);
    th_pushvalue(state, 2); th_pushvalue(state, event); th_rawset(state, 1);
    return 1;
}

/* Integration hook intentionally omitted: the root/child registration policy
 * remains owned by LAB_GameEventsInstall in script_game_events.inc. */
