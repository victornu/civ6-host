/* Compile/run separately when native validation is scheduled. No GameCore or
 * HKS library is loaded: this includes the real transport and substitutes only
 * HKS calls and map pushing. Module-resolution/real-HKS ABI remain native checks.
 */
#include <windows.h>
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <string.h>
#include <assert.h>

typedef struct LuaState { int unused; } LuaState;
typedef struct LuaStackResult { void* state; int index; int padding; } LuaStackResult;
typedef int (__cdecl *LuaCallback)(LuaState*);
typedef struct AuxMapOp { uint32_t kind, arg; uint64_t payload; } AuxMapOp;
#define LUA_GLOBALS (-10002)

static LuaState fixture_state;
static LuaState* thread_registry_root = &fixture_state;
static int thread_api_ready = 1;
static double (__cdecl *th_checknumber)(LuaState*, int) = NULL;
static void* active_request;
static int called, pushed_maps, pushed_strings, pushed_booleans, pushed_numbers;
static int return_type = 1;
static double last_number;
static size_t last_length;
static unsigned char first_byte, last_byte;

static void* th_userdata(LuaState* state, int index) {
    assert(state == &fixture_state && index == 1); return active_request;
}
static void th_checkstack(LuaState* state, int count, const char* message) {
    (void)state; (void)message; assert(count >= 8 && count <= 72);
}
static void th_getfield(LuaState* state, int index, const char* name) {
    (void)state; (void)index; assert(name && *name);
}
static int th_type(LuaState* state, int index) {
    (void)state; (void)index; return called ? return_type : 6;
}
static int th_lerror(LuaState* state, const char* message, ...) {
    (void)state; (void)message; assert(!"Unexpected protected callback error"); return 99;
}
static LuaStackResult* th_pushbool(LuaState* state, LuaStackResult* result, unsigned char value) {
    (void)state; assert(value == 1); ++pushed_booleans; return result;
}
static void th_number(LuaState* state, double number) {
    (void)state; ++pushed_numbers; last_number = number;
}
static void th_call(LuaState* state, int count, int results) {
    (void)state;
    assert(count == pushed_maps + pushed_strings + pushed_booleans + pushed_numbers);
    assert(results == 1); called = 1;
}
static unsigned char th_toboolean(LuaState* state, int index) {
    (void)state; (void)index; return return_type != 0;
}
static int th_gettop(LuaState* state) { (void)state; return 0; }
static int th_cpcall(LuaState* state, LuaCallback callback, void* request) {
    active_request = request; return callback(state);
}
static int LAB_ScriptLockEnter(void) { return 1; }
static int LAB_ScriptLockLeave(void) { return 1; }
static int LAB_AuxMapValidateTransport(const AuxMapOp* ops, uint32_t count) {
    return ops && count == 1 && ops[0].kind == 1;
}
static void aux_map_push(LuaState* state, const AuxMapOp* ops, uint32_t count, int peak) {
    (void)state; assert(peak == 1 && LAB_AuxMapValidateTransport(ops, count)); ++pushed_maps;
}
static LuaStackResult* fixture_lstring(
    LuaState* state, LuaStackResult* result, const char* data, size_t length) {
    assert(state == &fixture_state && data);
    ++pushed_strings; last_length = length;
    first_byte = length ? (unsigned char)data[0] : 0;
    last_byte = length ? (unsigned char)data[length - 1] : 0;
    result->state = state; result->index = pushed_strings;
    return result;
}

#include "../../native/profiles/xp2-current-strings/script_game_event_dispatch.inc"

static void dispatch_fixture(const ScriptGameEventArgument* arguments, size_t count,
    const ScriptGameEventMap* maps, size_t map_count,
    const ScriptGameEventString* strings, size_t string_count) {
    assert(script_game_event_validate_string_arguments(arguments, count, maps, map_count,
        strings, string_count, 262144u));
    ScriptGameEventRequest request = {"Fixture", NULL, count, 0, 0, "Call",
        arguments, maps, map_count, strings, string_count, fixture_lstring};
    active_request = &request;
    called = pushed_maps = pushed_strings = pushed_booleans = pushed_numbers = 0;
    assert(script_game_event_dispatch_callback(&fixture_state) == 0);
    assert(called && request.valid == (return_type != 0));
    active_request = NULL;
}

int main(void) {
    assert(sizeof(ScriptGameEventArgument) == 8 && sizeof(ScriptGameEventString) == 16);
    assert(LAB_GameEventsStringArgumentVersion() == 1);
    const char binary[] = {'a', '\0', 'z'}; /* deliberately not NUL-terminated */
    AuxMapOp ops = {1, 0, 0};
    ScriptGameEventMap map = {&ops, 1, 0};
    ScriptGameEventString string = {binary, sizeof(binary), 0};
    ScriptGameEventArgument mixed[] = {{0, 0xffffffffu}, {1, 0x7f}, {2, 0}, {3, 0}};
    dispatch_fixture(mixed, 4, &map, 1, &string, 1);
    assert(last_number == -1.0 && pushed_booleans == 1 && pushed_maps == 1);
    assert(pushed_strings == 1 && last_length == 1 && first_byte == 'a' && last_byte == 'a');
    assert(binary[2] == 'z' && string.size == 3); /* owned raw payload is preserved */

    ScriptGameEventArgument argument = {3, 0};
    string.data = NULL; string.size = 0;
    dispatch_fixture(&argument, 1, NULL, 0, &string, 1);
    assert(last_length == 0 && first_byte == 0);

    static char bounded[65537];
    memset(bounded, 'x', sizeof(bounded));
    string.data = bounded; string.size = 65536;
    dispatch_fixture(&argument, 1, NULL, 0, &string, 1);
    assert(last_length == 65536 && first_byte == 'x' && last_byte == 'x');
    string.size = 65537;
    assert(!script_game_event_validate_string_arguments(&argument, 1, NULL, 0, &string, 1, 262144));
    string.data = NULL; string.size = 1;
    assert(!script_game_event_validate_string_arguments(&argument, 1, NULL, 0, &string, 1, 262144));
    string.data = bounded; string.size = 1; string.reserved = 1;
    assert(!script_game_event_validate_string_arguments(&argument, 1, NULL, 0, &string, 1, 262144));
    string.reserved = 0; argument.value = 1;
    assert(!script_game_event_validate_string_arguments(&argument, 1, NULL, 0, &string, 1, 262144));
    argument.kind = 2; argument.value = 1;
    assert(!script_game_event_validate_string_arguments(&argument, 1, &map, 1, NULL, 0, 262144));
    argument.kind = 1; argument.value = 256;
    assert(!script_game_event_validate_string_arguments(&argument, 1, NULL, 0, NULL, 0, 262144));
    argument.kind = 4; argument.value = 0;
    assert(!script_game_event_validate_string_arguments(&argument, 1, NULL, 0, NULL, 0, 262144));
    argument.kind = 3;

    ScriptGameEventString strings[17];
    ScriptGameEventArgument arguments[17];
    for (uint32_t i = 0; i < 17; ++i) {
        strings[i] = (ScriptGameEventString){bounded, 65536, 0};
        arguments[i] = (ScriptGameEventArgument){3, i};
    }
    assert(script_game_event_validate_string_arguments(arguments, 16, NULL, 0, strings, 16, 262144));
    assert(!script_game_event_validate_string_arguments(arguments, 17, NULL, 0, strings, 17, 262144));
    for (size_t i = 0; i < 17; ++i) arguments[i].value = 0;
    assert(!script_game_event_validate_string_arguments(arguments, 17, NULL, 0, strings, 1, 262144));

    unsigned char valid = 9, output = 0xa5;
    assert(LAB_GameEventsDispatchTypedResult(&fixture_state, "Fixture", &argument, 1,
        0, &valid, &output) == -1800 && !valid && output == 0xa5);
    assert(LAB_GameEventsDispatchMapsResult(&fixture_state, "Fixture", &argument, 1,
        &map, 1, 0, &valid, &output) == -1800 && !valid && output == 0xa5);
    puts("script_game_event_strings_fixture: passed");
    return 0;
}
