/*
 * Bounded, read-only receipt for the live ScriptManager path method.
 *
 * Build this translation unit beside the immutable current-image snapshot of
 * localization_query.c produced by tools/build_localization_query.py.  The
 * included provider supplies the exact existing module, PID/creation,
 * prepared root state, owned UI Lua-state and Locale.Lookup guards; this file
 * adds only the path receipt.
 * The EXE method may delegate into its own content resolver.  This helper does
 * not claim those internal operations have no side effects.
 */
#include "localization_query.c"

static int path_receipt_active;

typedef unsigned char (__cdecl *ScriptManagerPathMethod)(
    void *, const wchar_t *, wchar_t *, uint32_t);

static int path_hex(const wchar_t *value, size_t units, char *out, size_t capacity) {
    static const char digits[] = "0123456789abcdef";
    const unsigned char *bytes = (const unsigned char *)value;
    size_t i;
    if (units > (SIZE_MAX - 1) / 4 || capacity < units * 4 + 1) return 0;
    for (i = 0; i < units * sizeof(wchar_t); ++i) {
        out[i * 2] = digits[bytes[i] >> 4];
        out[i * 2 + 1] = digits[bytes[i] & 15];
    }
    out[units * 4] = 0;
    return 1;
}

static int path_nonce_valid(const char *nonce) {
    size_t i;
    if (strlen(nonce) != 32) return 0;
    for (i = 0; i < 32; ++i)
        if (!((nonce[i] >= '0' && nonce[i] <= '9') ||
              (nonce[i] >= 'a' && nonce[i] <= 'f'))) return 0;
    return 1;
}

static int path_utf16_well_formed(const wchar_t *value, size_t units) {
    size_t i;
    for (i = 0; i < units; ++i) {
        unsigned int ch = (unsigned int)value[i];
        if (ch >= 0xd800 && ch <= 0xdbff) {
            unsigned int low;
            if (++i >= units) return 0;
            low = (unsigned int)value[i];
            if (low < 0xdc00 || low > 0xdfff) return 0;
        } else if (ch >= 0xdc00 && ch <= 0xdfff) return 0;
    }
    return 1;
}

static int push_path_receipt(lua_State *L, const char *nonce, DWORD pid,
        uint64_t creation, DWORD thread_id, uintptr_t manager,
        const wchar_t *input, size_t input_units, const wchar_t *output,
        size_t output_units) {
    char input_hex[1041], output_hex[1041], json[4096];
    StackResult result;
    int written;
    if (!path_hex(input, input_units, input_hex, sizeof(input_hex)) ||
        !path_hex(output, output_units, output_hex, sizeof(output_hex)))
        return qlerror(L, "Official script path receipt hex bound failed");
    written = sprintf_s(json, sizeof(json),
        "{\"schema\":\"civ6-host.official_script_path_resolution.v1\","
        "\"status\":\"ok\",\"nonce\":\"%s\",\"pid\":%lu,"
        "\"creation_filetime\":%llu,\"thread_id\":%lu,"
        "\"manager_address\":\"0x%llx\",\"manager_vtable_rva\":\"0xfead18\","
        "\"method_rva\":\"0x4d4510\",\"capacity_utf16_units\":260,"
        "\"input_utf16le_hex\":\"%s\",\"output_utf16le_hex\":\"%s\","
        "\"executable_sha256\":"
        "\"d1a0cfd439e7451be515f47595cfa0b6b983f56d1faf4ea434a4ce3b21491ebe\","
        "\"lua_scope\":\"ui\",\"lua_cs_owned\":true,\"native_method_called\":true,"
        "\"gamecore_function_called_by_helper\":false,"
        "\"output_file_opened_by_helper\":false,"
        "\"exe_method_may_delegate_to_content_resolver\":true,"
        "\"nested_resolver_side_effects_asserted_absent\":false,"
        "\"path_exists_checked\":false}",
        nonce, (unsigned long)pid, (unsigned long long)creation,
        (unsigned long)thread_id, (unsigned long long)manager,
        input_hex, output_hex);
    if (written <= 0 || (size_t)written >= sizeof(json))
        return qlerror(L, "Official script path receipt JSON bound failed");
    qtext(L, &result, json);
    return 1;
}

__declspec(dllexport) int __cdecl civ6rl_official_script_path(lua_State *L) {
    char path_utf8[4096], nonce[64], pid_text[32], creation_text[32];
    wchar_t input[260], output[260];
    uint64_t expected_pid, expected_creation, manager_value, vtable, method;
    FILETIME created, exited, kernel, user;
    ULARGE_INTEGER creation;
    DWORD pid, thread_id;
    int input_units, output_units, i;
    void *manager;
    ScriptManagerPathMethod resolve;
    /* Preparation is a separate, explicit RootTunerMainState call before the
     * native function is handed to UI. Never touch Lua API pointers unless it completed. */
    if (!qready || !qlerror) return 0;
    if (!qexe || !qloc || !qdb || !qhv || qactive || path_receipt_active)
        return qlerror(L, "Official script path helper is not prepared or is reentrant");
    if (qt(L) != 5 || !lua_string(L, 1, qstring, qtype, path_utf8, sizeof(path_utf8)) ||
        !lua_string(L, 2, qstring, qtype, nonce, sizeof(nonce)) || !path_nonce_valid(nonce) ||
        !lua_string(L, 3, qstring, qtype, pid_text, sizeof(pid_text)) ||
        !lua_string(L, 4, qstring, qtype, creation_text, sizeof(creation_text)) ||
        !decimal(pid_text, &expected_pid) || !decimal(creation_text, &expected_creation) ||
        qfunction(L, 5) != (LuaC)((uintptr_t)qexe + 0x4c9c30))
        return qlerror(L, "Official script path arguments refused");
    if (expected_pid != qpid || expected_pid != GetCurrentProcessId() || expected_pid > UINT32_MAX ||
        expected_creation != qcreation || GetModuleHandleW(NULL) != qexe ||
        GetModuleHandleW(L"Localization_FinalRelease.dll") != qloc ||
        GetModuleHandleW(L"DatabaseDLL_FinalRelease.dll") != qdb ||
        GetModuleHandleW(L"HavokScript_FinalRelease.dll") != qhv ||
        !GetProcessTimes(GetCurrentProcess(), &created, &exited, &kernel, &user))
        return qlerror(L, "Official script path process/module identity refused");
    creation.LowPart = created.dwLowDateTime; creation.HighPart = created.dwHighDateTime;
    if (creation.QuadPart != expected_creation || !lua_scope_kind(L, (uintptr_t)qexe, 0))
        return qlerror(L, "Official script path Locale.Lookup/UI scope refused");
    if (!pointer((uintptr_t)qexe + 0x2d09f88, &manager_value) || !manager_value ||
        !qword(manager_value, &vtable) || vtable != (uintptr_t)qexe + 0xfead18 ||
        !qword(vtable + 0x30, &method) || method != (uintptr_t)qexe + 0x4d4510)
        return qlerror(L, "Official ScriptManager vtable/method identity refused");
    pid = GetCurrentProcessId(); thread_id = GetCurrentThreadId();
    input_units = MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, path_utf8, -1,
        input, (int)(sizeof(input) / sizeof(input[0])));
    if (input_units < 2 || input_units > 260)
        return qlerror(L, "Official script path UTF-8/UTF-16 bound refused");
    manager = (void *)(uintptr_t)manager_value;
    resolve = (ScriptManagerPathMethod)(uintptr_t)method;
    for (i = 0; i < 260; ++i) output[i] = (wchar_t)0xffff;
    path_receipt_active = 1;
    (void)resolve(manager, input, output, 260);
    path_receipt_active = 0;
    output_units = 0;
    while (output_units < 260 && output[output_units] != 0) ++output_units;
    /* Only a nonempty, terminated, well-formed result is a success receipt. */
    if (output_units == 0 || output_units >= 260 ||
        !path_utf16_well_formed(output, (size_t)output_units))
        return qlerror(L, "ScriptManager path method returned invalid output after invocation");
    return push_path_receipt(L, nonce, pid, expected_creation, thread_id,
        manager_value, input, (size_t)input_units, output,
        (size_t)output_units + 1);
}
