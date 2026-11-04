/* EXE AUX60: 161910 -> 4DB970 -> protected 4DBDE0.
 * The synchronous GameEvents service is separate from category LuaEvents.
 * Source 4DBDE0 indexes by the supplied name and iterates the payload, without
 * an event-name whitelist. Integer and boolean payloads are source-backed.
 */
typedef struct ScriptGameEventArgument {
    uint32_t kind; /* Host transport tags: 0=DWORD, 1=raw boolean byte. */
    uint32_t value;
} ScriptGameEventArgument;
_Static_assert(sizeof(ScriptGameEventArgument) == 8, "Script argument ABI");

typedef struct ScriptGameEventMap {
    const AuxMapOp* ops;
    uint32_t count;
    uint32_t reserved;
} ScriptGameEventMap;
_Static_assert(sizeof(ScriptGameEventMap) == 16, "Script map argument ABI");

typedef struct ScriptGameEventRequest {
    const char* name;
    const uint32_t* arguments;
    size_t count;
    unsigned char valid;
    unsigned char result;
    const char* method;
    const ScriptGameEventArgument* typed_arguments;
    const ScriptGameEventMap* maps;
    size_t map_count;
} ScriptGameEventRequest;

static int __cdecl script_game_event_dispatch_callback(LuaState* state) {
    ScriptGameEventRequest* request = (ScriptGameEventRequest*)th_userdata(state, 1);
    if (!request) return th_lerror(state, "Missing synchronous GameEvents request");
    th_checkstack(state, (int)request->count + 8, "GameEvents argument stack");
    th_getfield(state, LUA_GLOBALS, "GameEvents");
    th_getfield(state, -1, request->name);
    th_getfield(state, -1, request->method);
    if (th_type(state, -1) != 6)
        return th_lerror(state, "Requested GameEvents method is unavailable");
    for (size_t index = 0; index < request->count; ++index) {
        uint32_t raw_value;
        if (request->typed_arguments) {
            const ScriptGameEventArgument* argument = request->typed_arguments + index;
            if (argument->kind == 2 && request->maps && argument->value < request->map_count) {
                const ScriptGameEventMap* map = request->maps + argument->value;
                int peak = LAB_AuxMapValidateTransport(map->ops, map->count);
                if (!peak || map->reserved)
                    return th_lerror(state, "Invalid GameEvents map transport");
                /* EXE payload type7 -> owned map getter+78 -> AUX+A8(names=1).
                 * Reuse exactly the common map pusher. Python has copied the
                 * owned native clone before entering this protected call. */
                aux_map_push(state, map->ops, map->count, peak);
                continue;
            }
            if (argument->kind == 1 && argument->value <= 255) {
                /* EXE161DC0 normalizes the stored byte; 4DC976 emits HKS bool. */
                LuaStackResult result = {0};
                th_pushbool(state, &result, (unsigned char)(argument->value != 0));
                continue;
            }
            if (argument->kind != 0)
                return th_lerror(state, "Unverified GameEvents argument type");
            raw_value = argument->value;
        } else {
            raw_value = request->arguments[index];
        }
        int32_t signed_value;
        memcpy(&signed_value, &raw_value, sizeof(signed_value));
        /* EXE 4DC9FE/4DCA04 converts the +68 DWORD getter with CVTDQ2PD. */
        th_number(state, (double)signed_value);
    }
    th_call(state, (int)request->count, 1);
    request->result = th_toboolean(state, -1) != 0;
    request->valid = th_type(state, -1) != 0;
    return 0;
}

__declspec(dllexport) int __cdecl LAB_GameEventsDispatch(
    LuaState* root, const char* name, const uint32_t* arguments, size_t count,
    unsigned char* output) {
    if (!output) return -1800;
    *output = 0;
    if (root != thread_registry_root || !name || !*name ||
        strnlen(name, 256) >= 256 || count > 64 || (count && !arguments) || th_gettop(root))
        return -1800;
    ScriptGameEventRequest request = {name, arguments, count, 0, 0, "Call", NULL, NULL, 0};
    if (!LAB_ScriptLockEnter()) return -1601;
    int status = th_cpcall(root, script_game_event_dispatch_callback, &request);
    if (!LAB_ScriptLockLeave()) return -1602;
    if (!status && request.valid) *output = request.result;
    return status;
}

/* AUX80 uses TestAll. Unlike AUX60/Call it leaves *output unchanged when
 * the Lua method returns nil. Both wrappers return the non-nil bit, not
 * protected-call success. EXE 161930 -> 4DBA10 -> 4DBDE0. */
__declspec(dllexport) int __cdecl LAB_GameEventsDispatchResult(
    LuaState* root, const char* name, const uint32_t* arguments, size_t count,
    unsigned int method, unsigned char* valid, unsigned char* output) {
    if (!output || !valid) return -1800;
    *valid = 0;
    if (method > 1 || root != thread_registry_root || !name || !*name ||
        strnlen(name, 256) >= 256 || count > 64 || (count && !arguments) || th_gettop(root))
        return -1800;
    if (method == 0) *output = 0;
    ScriptGameEventRequest request = {name, arguments, count, 0, 0,
                                     method ? "TestAll" : "Call", NULL, NULL, 0};
    if (!LAB_ScriptLockEnter()) return -1601;
    int status = th_cpcall(root, script_game_event_dispatch_callback, &request);
    if (!LAB_ScriptLockLeave()) return -1602;
    if (!status) {
        *valid = request.valid;
        if (request.valid) *output = request.result;
    }
    return status;
}

__declspec(dllexport) int __cdecl LAB_GameEventsDispatchTypedResult(
    LuaState* root, const char* name, const ScriptGameEventArgument* arguments, size_t count,
    unsigned int method, unsigned char* valid, unsigned char* output) {
    if (!output || !valid) return -1800;
    *valid = 0;
    if (method > 1 || root != thread_registry_root || !name || !*name ||
        strnlen(name, 256) >= 256 || count > 64 || (count && !arguments) || th_gettop(root))
        return -1800;
    for (size_t index = 0; index < count; ++index)
        if (arguments[index].kind > 1 ||
            (arguments[index].kind == 1 && arguments[index].value > 255)) return -1800;
    if (method == 0) *output = 0;
    ScriptGameEventRequest request = {name, NULL, count, 0, 0,
                                     method ? "TestAll" : "Call", arguments, NULL, 0};
    if (!LAB_ScriptLockEnter()) return -1601;
    int status = th_cpcall(root, script_game_event_dispatch_callback, &request);
    if (!LAB_ScriptLockLeave()) return -1602;
    if (!status) {
        *valid = request.valid;
        if (request.valid) *output = request.result;
    }
    return status;
}

__declspec(dllexport) int __cdecl LAB_GameEventsDispatchTyped(
    LuaState* root, const char* name, const ScriptGameEventArgument* arguments,
    size_t count, unsigned char* output) {
    unsigned char valid = 0;
    return LAB_GameEventsDispatchTypedResult(root, name, arguments, count, 0, &valid, output);
}

/* Explicit new transport; the retained scalar-only exports still reject kind2. */
__declspec(dllexport) int __cdecl LAB_GameEventsMapArgumentVersion(void) { return 1; }
__declspec(dllexport) int __cdecl LAB_GameEventsDispatchMapsResult(
    LuaState* root, const char* name, const ScriptGameEventArgument* arguments, size_t count,
    const ScriptGameEventMap* maps, size_t map_count, unsigned int method,
    unsigned char* valid, unsigned char* output) {
    if (!output || !valid) return -1800;
    *valid = 0;
    if (method > 1 || root != thread_registry_root || !name || !*name ||
        strnlen(name, 256) >= 256 || count > 64 || !arguments ||
        !map_count || map_count > count || !maps || th_gettop(root)) return -1800;
    uint32_t total_ops = 0;
    for (size_t i = 0; i < map_count; ++i) {
        /* Aggregate transport budget, in addition to each map validator. */
        if (maps[i].reserved || maps[i].count > (4194304u / sizeof(AuxMapOp)) - total_ops ||
            !LAB_AuxMapValidateTransport(maps[i].ops, maps[i].count)) return -1800;
        total_ops += maps[i].count;
    }
    for (size_t i = 0; i < count; ++i)
        if (arguments[i].kind > 2 || (arguments[i].kind == 1 && arguments[i].value > 255) ||
            (arguments[i].kind == 2 && arguments[i].value >= map_count)) return -1800;
    if (method == 0) *output = 0;
    ScriptGameEventRequest request = {name, NULL, count, 0, 0,
                                     method ? "TestAll" : "Call", arguments, maps, map_count};
    if (!LAB_ScriptLockEnter()) return -1601;
    int status = th_cpcall(root, script_game_event_dispatch_callback, &request);
    if (!LAB_ScriptLockLeave()) return -1602;
    if (!status) {
        *valid = request.valid;
        if (request.valid) *output = request.result;
    }
    return status;
}
