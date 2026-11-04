/* EXE auxiliary vtable +0xA0 service.
 * Include after script_execution.inc; th_push* and script_known_child must be
 * available. This is native C so HKS lua_error never unwinds through ctypes.
 * Scalar bool/int/float and tagged byte/UTF-16 strings are admitted.
 */
#include <float.h>
#define SCRIPT_AUX_A0_MAX_STRING (1024u * 1024u)
static __declspec(noreturn) void __cdecl script_aux_a0_error(LuaState*, const char*);

/* EXE db5f3a -> 9830d0/9831c0/983360. The official conversion has a
 * 1024-byte destination including NUL. It stops before a whole codepoint
 * that does not fit; the caller ignores the overflow status. Isolated
 * surrogates are encoded as three bytes, rather than replaced or rejected.
 * This is a transport rule, not a gameplay approximation. */
static void script_aux_a0_utf16(LuaState* state, const uint16_t* source) {
    if (!source) { th_pushnil(state); return; }
    size_t length = 0;
    while (length <= SCRIPT_AUX_A0_MAX_STRING && source[length]) ++length;
    if (length > SCRIPT_AUX_A0_MAX_STRING)
        script_aux_a0_error(state, "A0 UTF-16 string exceeds bounded source scan");
    char output[1024];
    size_t written = 0;
    for (size_t index = 0; index < length;) {
        uint32_t code = source[index++];
        if (code >= 0xd800u && code <= 0xdbffu && index < length &&
            source[index] >= 0xdc00u && source[index] <= 0xdfffu) {
            code = 0x10000u + ((code - 0xd800u) << 10) + (source[index++] - 0xdc00u);
        }
        size_t bytes = code < 0x80u ? 1 : code < 0x800u ? 2 : code < 0x10000u ? 3 : 4;
        if (bytes > sizeof(output) - 1 - written) break;
        if (bytes == 1) output[written++] = (char)code;
        else {
            if (bytes == 4) output[written++] = (char)(0xf0u | (code >> 18));
            if (bytes >= 3) output[written++] = (char)((bytes == 3 ? 0xe0u : 0x80u) | ((code >> 12) & (bytes == 3 ? 0x0fu : 0x3fu)));
            output[written++] = (char)((bytes == 2 ? 0xc0u : 0x80u) | ((code >> 6) & (bytes == 2 ? 0x1fu : 0x3fu)));
            output[written++] = (char)(0x80u | (code & 0x3fu));
        }
    }
    output[written] = 0;
    LuaStackResult result;
    th_pushstring(state, &result, output);
}

static __declspec(noreturn) void __cdecl script_aux_a0_error(LuaState* state,
                                                              const char* message) {
    LuaStackResult result;
    th_pushstring(state, &result, message);
    (void)th_error(state);
    /* lua_error is specified not to return; fail closed if that invariant breaks. */
    TerminateProcess(GetCurrentProcess(), 78);
    __assume(0);
}

__declspec(dllexport) void __cdecl LAB_AuxPushVariant(void* auxiliary,
                                                      LuaState* state,
                                                      const void* variant) {
    (void)auxiliary;
    if (!state || !thread_api_ready || !script_known_child(state)) {
        TerminateProcess(GetCurrentProcess(), 78);
        __assume(0);
    }
    if (!variant) {
        script_aux_a0_error(state, "Null Core variant at auxiliary +0xA0");
        return;
    }

    uint16_t tag;
    uint64_t payload;
    uint32_t flags;
    memcpy(&tag, (const unsigned char*)variant, sizeof(tag));
    memcpy(&payload, (const unsigned char*)variant + 8, sizeof(payload));
    memcpy(&flags, (const unsigned char*)variant + 0x14, sizeof(flags));
    int pointer_or_array = (flags & 0x20000000u) != 0;
    LuaStackResult result;

    /* EXE db5c70's scalar fallback: tags 0 and -1 both become numeric zero. */
    if (tag == 0 || tag == 0xffffu) {
        th_number(state, 0.0);
        return;
    }
    if (tag == 1 && !pointer_or_array) {
        th_pushbool(state, &result, *((const unsigned char*)variant + 8) != 0);
        return;
    }
    if ((tag == 2 || tag == 3) && !pointer_or_array) {
        int32_t signed_value;
        memcpy(&signed_value, (const unsigned char*)variant + 8, sizeof(signed_value));
        /* EXE uses cvtdq2pd: signed 32-bit integer to Lua's numeric double. */
        th_number(state, (double)signed_value);
        return;
    }
    if (tag == 4 && !pointer_or_array) {
        float single_value;
        memcpy(&single_value, (const unsigned char*)variant + 8, sizeof(single_value));
        if (!(single_value <= FLT_MAX && single_value >= -FLT_MAX))
            script_aux_a0_error(state, "A0 float is not finite");
        th_number(state, (double)single_value);
        return;
    }
    if (tag == 5 && pointer_or_array) {
        const char* text = (const char*)(uintptr_t)payload;
        if (!text) {
            th_pushnil(state);
            return;
        }
        const char* end = (const char*)memchr(text, 0, SCRIPT_AUX_A0_MAX_STRING + 1u);
        if (!end) {
            script_aux_a0_error(state, "A0 string exceeds 1 MiB bound");
            return;
        }
        th_pushstring(state, &result, text);
        return;
    }
    if (tag == 6 && pointer_or_array) {
        script_aux_a0_utf16(state, (const uint16_t*)(uintptr_t)payload);
        return;
    }
    script_aux_a0_error(state, "Unsupported Core variant at auxiliary +0xA0");
}

#undef SCRIPT_AUX_A0_MAX_STRING
