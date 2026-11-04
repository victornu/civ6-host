/*
 * Source-backed GameEvents aggregation methods. Candidate include only:
 * root may integrate by including after script_game_events_full.inc and
 * replacing its four aggregation refusal closures with
 * game_events_aggregators_bind_methods(state, event_index, group_index).
 *
 * Full chained EXE bodies: evidence/native-game-event-aggregators.json.
 * Conversion helper: pinned Havok lua_tonumber export RVA 0x3d5f0; it matches
 * hks_obj_tonumber's tag-3 number/tag-4 numeric-string behavior. No DLL is
 * loaded here; we only resolve the export from the already-loaded VM.
 */
#include <emmintrin.h>
#include <limits.h>

typedef enum GameEventAggregateMode {
    GAME_EVENT_ACCUMULATE_FLOAT = 1,
    GAME_EVENT_ACCUMULATE_INT = 2,
    GAME_EVENT_TEST_ANY = 3,
    GAME_EVENT_TEST_ALL = 4
} GameEventAggregateMode;

static double (__cdecl *game_events_aggregator_tonumber)(LuaState*, int) = NULL;

static int game_events_aggregator_bind_conversion(void) {
    if (game_events_aggregator_tonumber) return 1;
    HMODULE module = GetModuleHandleW(L"HavokScript_FinalRelease.dll");
    if (!module) return 0;
    FARPROC proc = GetProcAddress(module, "?lua_tonumber@@YANPEAUlua_State@@H@Z");
    if (!proc || (uintptr_t)proc != (uintptr_t)module + 0x3d5f0) return 0;
    memcpy(&game_events_aggregator_tonumber, &proc, sizeof(proc));
    return game_events_aggregator_tonumber != NULL;
}

static int __cdecl game_events_aggregator_reserve_stack(LuaState* state) {
    const int* count = (const int*)th_userdata(state, 1);
    if (!count || *count < 0 || *count > INT_MAX - 4)
        return th_lerror(state, "Invalid GameEvents aggregation stack reservation");
    th_checkstack(state, *count + 4, "GameEvents aggregation listener stack");
    return 0;
}

static int __cdecl game_events_aggregator_callback(LuaState* state, int mode) {
    int nargs = th_gettop(state);
    if (nargs < 0 || nargs > INT_MAX - 12)
        return th_lerror(state, "GameEvents aggregation argument count is out of range");
    if (!game_events_aggregator_bind_conversion())
        return th_lerror(state, "GameEvents numeric conversion export is unavailable");
    if (!th_getenv || !th_setenv || !th_next || !th_newthread || !th_xmove ||
        !th_pcall || !th_cpcall || !th_checkstack || !th_objlen)
        return th_lerror(state, "GameEvents aggregation Lua APIs are unavailable");

    int group_index = LUA_UPVALUE(1);
    th_checkstack(state, nargs + 12, "GameEvents aggregation parent stack");

    volatile float float_sum = 0.0f;
    uint32_t int_sum_bits = 0;
    unsigned char any_result = 0;
    unsigned char all_result = 1;
    int has_listeners = 0;

    th_pushnil(state);
    while (th_next(state, group_index)) {
        /* The shared native group maps context keys to listener arrays. */
        if (th_type(state, -1) == 5) {
            int listeners_index = th_gettop(state);
            size_t count = th_objlen(state, listeners_index);
            if (count > 0x7ffffffeU)
                return th_lerror(state, "GameEvents aggregation listener count exceeds native range");
            if (count) has_listeners = 1; /* Set before callbacks, including erroring ones. */

            for (int index = 1; index <= (int)count; ++index) {
                int iteration_top = th_gettop(state);
                LuaState* child = th_newthread(state);
                if (!child)
                    return th_lerror(state, "GameEvents aggregation could not create listener thread");
                int reserved = th_cpcall(child, game_events_aggregator_reserve_stack, &nargs);
                th_settop(child, 0);
                if (reserved)
                    return th_lerror(state, "GameEvents aggregation listener stack reservation failed");

                int thread_object = iteration_top + 1;
                th_rawgeti(state, listeners_index, index);
                th_getenv(state, -1);
                th_setenv(state, thread_object);

                /* Call closure receives exactly this method's arguments. */
                th_settop(state, thread_object);
                th_rawgeti(state, listeners_index, index);
                for (int arg = 1; arg <= nargs; ++arg) th_pushvalue(state, arg);
                th_xmove(state, child, nargs + 1);

                if (!LAB_ScriptLockEnter()) {
                    th_settop(state, iteration_top);
                    return th_lerror(state, "GameEvents aggregation script lock is unavailable");
                }
                int status = th_pcall(child, nargs, 1, 0);
                int lock_left = LAB_ScriptLockLeave();

                if (status == 0 && th_gettop(child) > 0) {
                    if (mode == GAME_EVENT_ACCUMULATE_FLOAT) {
                        float converted = (float)game_events_aggregator_tonumber(child, -1);
                        float_sum = float_sum + converted;
                    } else if (mode == GAME_EVENT_ACCUMULATE_INT) {
                        double converted = game_events_aggregator_tonumber(child, -1);
                        int32_t truncated = _mm_cvttsd_si32(_mm_set_sd(converted));
                        int_sum_bits += (uint32_t)truncated;
                    } else {
                        unsigned char truth = th_toboolean(child, -1) != 0;
                        if (mode == GAME_EVENT_TEST_ANY) any_result |= truth;
                        else all_result &= truth;
                    }
                }
                th_settop(child, 0); /* discard both results and protected errors */
                th_settop(state, iteration_top); /* keep next() key/value */
                if (!lock_left)
                    return th_lerror(state, "GameEvents aggregation script lock release failed");
            }
        }
        th_settop(state, -2); /* retain the key for the next table iteration */
    }

    if (!has_listeners) {
        th_pushnil(state);
    } else if (mode == GAME_EVENT_ACCUMULATE_FLOAT) {
        th_number(state, (double)float_sum);
    } else if (mode == GAME_EVENT_ACCUMULATE_INT) {
        int32_t signed_sum;
        memcpy(&signed_sum, &int_sum_bits, sizeof(signed_sum));
        th_number(state, (double)signed_sum);
    } else {
        LuaStackResult result = {0};
        unsigned char value = mode == GAME_EVENT_TEST_ANY ? any_result : all_result;
        th_pushbool(state, &result, value != 0);
    }
    return 1;
}

static int __cdecl game_events_aggregate_float_callback(LuaState* state) {
    return game_events_aggregator_callback(state, GAME_EVENT_ACCUMULATE_FLOAT);
}
static int __cdecl game_events_aggregate_int_callback(LuaState* state) {
    return game_events_aggregator_callback(state, GAME_EVENT_ACCUMULATE_INT);
}
static int __cdecl game_events_test_any_callback(LuaState* state) {
    return game_events_aggregator_callback(state, GAME_EVENT_TEST_ANY);
}
static int __cdecl game_events_test_all_callback(LuaState* state) {
    return game_events_aggregator_callback(state, GAME_EVENT_TEST_ALL);
}

static void game_events_aggregators_bind_methods(LuaState* state,
                                                int event_index,
                                                int group_index) {
    th_pushvalue(state, group_index);
    th_closure(state, game_events_aggregate_float_callback, 1, "GameEvent::Accumulate", 0);
    th_setfield(state, event_index, "Accumulate");
    th_pushvalue(state, group_index);
    th_closure(state, game_events_aggregate_int_callback, 1, "GameEvent::AccumulateINT", 0);
    th_setfield(state, event_index, "AccumulateINT");
    th_pushvalue(state, group_index);
    th_closure(state, game_events_test_any_callback, 1, "GameEvent::TestAny", 0);
    th_setfield(state, event_index, "TestAny");
    th_pushvalue(state, group_index);
    th_closure(state, game_events_test_all_callback, 1, "GameEvent::TestAll", 0);
    th_setfield(state, event_index, "TestAll");
}
