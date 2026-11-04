#include "script_event_state_scope.inc"
/* AUX+A8: marshal a copied, source-decoded native ParameterMap to the supplied
 * HKS state. Python only snapshots native memory; it has returned before any
 * VM operation below can throw. As with AUX+A0, the enclosing native protected
 * script call catches HKS errors without unwinding a ctypes callback.
 * These opcodes are host transport, not game instructions or gameplay rules. */
typedef struct AuxMapOp { uint32_t kind, arg; uint64_t payload; } AuxMapOp;
typedef int (__cdecl *AuxMapSnapshot)(void*, LuaState*, const void*, unsigned char,
                                     const AuxMapOp**, uint32_t*);
static AuxMapSnapshot aux_map_snapshot = NULL;
static void* aux_map_owner = NULL;
static DWORD aux_map_thread = 0;
static int aux_map_busy = 0;
#define AUX_MAP_MAX_OPS 262144u
#define AUX_MAP_MAX_STRING_BYTES 65536u
#define AUX_MAP_MAX_TOTAL_STRING_BYTES 1048576u

/* V1 executables do not admit NIL opcode 8. Producers must negotiate this
 * export before sending the extended UTF-16/null-value transport. */
__declspec(dllexport) int __cdecl LAB_AuxMapTransportVersion(void) { return 2; }

__declspec(dllexport) int __cdecl LAB_AuxMapValidateTransport(const AuxMapOp* ops,
                                                            uint32_t count) {
    unsigned char stack[17];
    unsigned int depth = 0, peak = 0;
    uint32_t string_bytes = 0;
    if (!ops || !count || count > AUX_MAP_MAX_OPS) return 0;
    for (uint32_t i = 0; i < count; ++i) {
        AuxMapOp op = ops[i];
        switch (op.kind) {
        case 1:
            if (op.arg > 65536u || op.payload > 4096u || depth >= 16) return 0;
            stack[depth++] = 1; break;
        case 2: {
            double number;
            memcpy(&number, &op.payload, 8);
            if (op.arg || !_finite(number) || depth >= 16) return 0;
            stack[depth++] = 2; break;
        }
        case 3:
            if (op.arg > 255 || op.payload || depth >= 16) return 0;
            stack[depth++] = 3; break;
        case 4:
            if (op.arg > 2 || op.payload || depth >= 16) return 0;
            stack[depth++] = 4; break;
        case 8:
            if (op.arg || op.payload || depth >= 16) return 0;
            stack[depth++] = 5; break;
        case 5:
            if (op.arg || op.payload || depth < 3 || stack[depth-3] != 1 ||
                (stack[depth-2] != 2 && stack[depth-2] != 4)) return 0;
            depth -= 2; break;
        case 6:
            if (!op.arg || op.arg > 65536u || op.payload || depth < 2 ||
                stack[depth-2] != 1) return 0;
            --depth; break;
        case 7: {
            /* Inline copied C-string: no borrowed pointer crosses the ABI.
             * The following records are bytes, not executable opcodes. */
            if (op.arg > AUX_MAP_MAX_STRING_BYTES || op.payload || depth >= 16 ||
                op.arg > AUX_MAP_MAX_TOTAL_STRING_BYTES - string_bytes) return 0;
            uint32_t records = (op.arg + 16u) / 16u;
            if (records > count - i - 1u) return 0;
            const unsigned char* bytes = (const unsigned char*)&ops[i+1];
            for (uint32_t j = 0; j < op.arg; ++j) if (!bytes[j]) return 0;
            for (uint32_t j = op.arg; j < records * 16u; ++j)
                if (bytes[j]) return 0;
            string_bytes += op.arg;
            stack[depth++] = 4;
            i += records;
            break;
        }
        default: return 0;
        }
        if (depth > peak) peak = depth;
    }
    return depth == 1 && stack[0] == 1 ? (int)peak : 0;
}

__declspec(dllexport) int __cdecl LAB_AuxMapInstall(void* owner, AuxMapSnapshot snapshot) {
    if (aux_map_thread && aux_map_thread != GetCurrentThreadId()) return 0;
    if (!owner && !snapshot) {
        aux_map_owner = NULL; aux_map_snapshot = NULL;
        aux_map_thread = 0; aux_map_busy = 0; return 1;
    }
    if (!owner || !snapshot || aux_map_owner || aux_map_snapshot || !thread_api_ready) return 0;
    aux_map_owner = owner; aux_map_snapshot = snapshot;
    aux_map_thread = GetCurrentThreadId(); aux_map_busy = 0; return 1;
}

static void aux_map_push(LuaState* state, const AuxMapOp* ops, uint32_t count, int peak) {
    static const char* const names[] = {"player", "type", "id"};
    int initial = th_gettop(state);
    th_checkstack(state, peak + 2, "AUX+A8 bounded map transport");
    for (uint32_t i = 0; i < count; ++i) {
        AuxMapOp op = ops[i];
        LuaStackResult result;
        switch (op.kind) {
        case 1: th_newtable(state, (int)op.arg, (int)op.payload); break;
        case 2: {
            double number;
            memcpy(&number, &op.payload, 8);
            th_number(state, number); break;
        }
        case 3: th_pushbool(state, &result, op.arg != 0); break;
        case 4: th_pushstring(state, &result, names[op.arg]); break;
        case 5: th_rawset(state, -3); break;
        case 6: th_rawseti(state, -2, (int)op.arg); break;
        case 8: th_pushnil(state); break;
        case 7:
            th_pushstring(state, &result, (const char*)&ops[i+1]);
            i += (op.arg + 16u) / 16u;
            break;
        default: script_aux_a0_error(state, "Invalid AUX+A8 opcode after validation");
        }
    }
    if (th_gettop(state) != initial + 1 || th_type(state, -1) != 5)
        script_aux_a0_error(state, "AUX+A8 must add exactly one native result table");
}

/* EXE AUX+B0 -> DB5C00 reads the original map's field count (+0x50),
 * pushing nil for zero and otherwise using the same map conversion as A8.
 * The root TABLE payload preserves that count, including fields whose nil
 * values are omitted. Do not use resulting Lua table cardinality here. */
static int aux_optional_map_root_valid(const AuxMapOp* ops, uint32_t count) {
    return ops && count && ops[0].kind == 1 && ops[0].arg == 0 &&
        ops[0].payload <= 4096u && (ops[0].payload != 0 || count == 1);
}
static void aux_optional_map_push(LuaState* state, const AuxMapOp* ops,
                                  uint32_t count, int peak) {
    if (!aux_optional_map_root_valid(ops, count))
        script_aux_a0_error(state, "AUX+B0 root does not preserve native map count");
    if (ops[0].payload == 0) {
        int initial = th_gettop(state);
        th_checkstack(state, 1, "AUX+B0 empty native map");
        th_pushnil(state);
        if (th_gettop(state) != initial+1 || th_type(state, -1) != 0)
            script_aux_a0_error(state, "AUX+B0 empty map must push exactly one nil");
    } else aux_map_push(state, ops, count, peak);
}

/* Exercise the actual HKS transport with host-owned test values. The checker
 * is a bounded Lua chunk returning a function(table); it runs under cpcall.
 * This checks marshalling only and never reads or modifies a GameCore object. */
typedef struct AuxMapDiagnostic {
    const AuxMapOp* ops;
    uint32_t count;
    int peak;
    const char* checker;
    size_t checker_length;
    int optional;
} AuxMapDiagnostic;
static int __cdecl aux_map_diagnostic_callback(LuaState* state) {
    AuxMapDiagnostic* request = (AuxMapDiagnostic*)th_userdata(state, 1);
    int before = th_gettop(state);
    if (request->optional)
        aux_optional_map_push(state, request->ops, request->count, request->peak);
    else aux_map_push(state, request->ops, request->count, request->peak);
    if (th_gettop(state) != before+1 || th_type(state, 1) != 2)
        return th_lerror(state, "AUX map diagnostic changed the original stack");
    int table_index=th_gettop(state);
    int status=th_loadbuffer(state,request->checker,request->checker_length,"@aux_map_checker");
    if (status) return th_error(state);
    th_call(state,0,1);
    th_pushvalue(state,table_index);
    th_call(state,1,0);
    return 0;
}
static int aux_map_diagnostic(LuaState* state, const AuxMapOp* ops,
        uint32_t count,const char* checker,size_t length,int optional) {
    if (!thread_api_ready || !script_event_known_state(state) || th_gettop(state) != 0)
        return -1700;
    int peak=LAB_AuxMapValidateTransport(ops,count);
    if (!peak || !checker || !length || length>16384 ||
        (optional && !aux_optional_map_root_valid(ops,count))) return -1701;
    AuxMapDiagnostic request={ops,count,peak,checker,length,optional};
    if (!LAB_ScriptLockEnter()) return -1702;
    ++script_protected_depth;
    int status=th_cpcall(state,aux_map_diagnostic_callback,&request);
    --script_protected_depth;
    if (!LAB_ScriptLockLeave()) return -1703;
    return status;
}
__declspec(dllexport) int __cdecl LAB_AuxMapDiagnostic(LuaState* state,
        const AuxMapOp* ops,uint32_t count,const char* checker,size_t length) {
    return aux_map_diagnostic(state,ops,count,checker,length,0);
}
__declspec(dllexport) int __cdecl LAB_AuxOptionalMapDiagnostic(LuaState* state,
        const AuxMapOp* ops,uint32_t count,const char* checker,size_t length) {
    return aux_map_diagnostic(state,ops,count,checker,length,1);
}

static void aux_map_from_snapshot(void* owner,LuaState* state,const void* map,
                                  unsigned char names,int optional) {
    if (!state || !thread_api_ready || !script_event_known_state(state) ||
        owner != aux_map_owner || !aux_map_snapshot || aux_map_busy ||
        aux_map_thread != GetCurrentThreadId() || (!script_protected_depth &&
        !LAB_GameEventsStateIsActive(thread_registry_root,state))) {
        TerminateProcess(GetCurrentProcess(), 78);
        __assume(0);
    }
    const AuxMapOp* ops = NULL;
    uint32_t count = 0;
    aux_map_busy = 1;
    /* No VM call is permitted within this callback. It returns immutable,
     * owner-retained storage, or an explicit failure, never a partial table. */
    int copied = aux_map_snapshot(owner, state, map, names, &ops, &count);
    if (copied != 1) script_aux_a0_error(state, "AUX+A8 native map snapshot refused");
    int peak = LAB_AuxMapValidateTransport(ops, count);
    if (!peak) script_aux_a0_error(state, "AUX+A8 transport validation refused");
    if (optional) aux_optional_map_push(state, ops, count, peak);
    else aux_map_push(state, ops, count, peak);
    aux_map_busy = 0;
}
__declspec(dllexport) void __cdecl LAB_AuxPushMap(void* owner, LuaState* state,
                                                const void* map, unsigned char names) {
    aux_map_from_snapshot(owner,state,map,names,0);
}
__declspec(dllexport) void __cdecl LAB_AuxPushOptionalMap(void* owner,LuaState* state,
                                                        const void* map,unsigned char names) {
    aux_map_from_snapshot(owner,state,map,names,1);
}

#undef AUX_MAP_MAX_OPS
#undef AUX_MAP_MAX_STRING_BYTES
#undef AUX_MAP_MAX_TOTAL_STRING_BYTES
