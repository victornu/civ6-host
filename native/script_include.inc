/* Static-source IncludeFileList provider. The embedding host calls
 * LAB_ScriptIncludeSetFiles with bounded paths/source bytes, then
 * LAB_ScriptIncludeInstall for the child VM. No Python or filesystem callback
 * runs while HKS is executing. */
#define SCRIPT_INCLUDE_MAX_FILES 8192
#define SCRIPT_INCLUDE_MAX_NAME 1024
#define SCRIPT_INCLUDE_MAX_SOURCE (16u * 1024u * 1024u)
#define SCRIPT_INCLUDE_MAX_TOTAL (256u * 1024u * 1024u)

typedef struct ScriptIncludeInput {
    const char* name;
    const char* source;
    size_t source_length;
} ScriptIncludeInput;
typedef struct ScriptIncludeOwned {
    char* name;
    char* source;
    size_t source_length;
} ScriptIncludeOwned;
static ScriptIncludeOwned script_include_files[SCRIPT_INCLUDE_MAX_FILES];
static size_t script_include_file_count = 0;
static size_t script_include_total_bytes = 0;

static void script_include_clear_files(void) {
    for (size_t i = 0; i < script_include_file_count; ++i) {
        free(script_include_files[i].name);
        free(script_include_files[i].source);
        memset(&script_include_files[i], 0, sizeof(script_include_files[i]));
    }
    script_include_file_count = script_include_total_bytes = 0;
}

__declspec(dllexport) int __cdecl LAB_ScriptIncludeSetFiles(
    const ScriptIncludeInput* files, size_t count) {
    if ((count && !files) || count > SCRIPT_INCLUDE_MAX_FILES) return -1700;
    size_t total = 0;
    for (size_t i = 0; i < count; ++i) {
        if (!files[i].name || !files[i].source ||
            strnlen(files[i].name, SCRIPT_INCLUDE_MAX_NAME + 1) > SCRIPT_INCLUDE_MAX_NAME ||
            !files[i].name[0] || files[i].source_length > SCRIPT_INCLUDE_MAX_SOURCE ||
            files[i].source_length > SCRIPT_INCLUDE_MAX_TOTAL - total) return -1701;
        for (size_t j = 0; files[i].name[j]; ++j)
            if ((unsigned char)files[i].name[j] < 0x20 || files[i].name[j] == '\\') return -1702;
        total += files[i].source_length;
    }
    /* Validate before replacing the current snapshot. */
    script_include_clear_files();
    for (size_t i = 0; i < count; ++i) {
        size_t name_length = strlen(files[i].name);
        char* name = (char*)malloc(name_length + 1);
        char* source = (char*)malloc(files[i].source_length ? files[i].source_length : 1);
        if (!name || !source) {
            free(name); free(source); script_include_clear_files(); return -1703;
        }
        memcpy(name, files[i].name, name_length + 1);
        if (files[i].source_length) memcpy(source, files[i].source, files[i].source_length);
        script_include_files[i] = (ScriptIncludeOwned){name, source, files[i].source_length};
        ++script_include_file_count;
        script_include_total_bytes += files[i].source_length;
    }
    return 0;
}

static int __cdecl script_include_callback(LuaState* state) {
    if (th_gettop(state)!=1)
        return th_lerror(state,"Civ6RL include diagnostic supports only the verified one-argument map calls");
    size_t pattern_length = 0;
    const char* pattern = th_checkstring(state, 1, &pattern_length);
    if (!pattern || !pattern_length || pattern_length > 1024)
        return th_argerror(state, 1, "string expected");

    int base = th_gettop(state);
    th_getfield(state, LUA_GLOBALS, "string");
    if (th_type(state, -1) != 5) return th_lerror(state, "attempt to index global 'string' (a nil value)");
    th_getfield(state, -1, "find");
    if (th_type(state, -1) != 6 && th_type(state, -1) != 9 && th_type(state, -1) != 10)
        return th_lerror(state, "string.find must be a valid function.");
    th_remove(state, -2); /* retain function */
    int find_function = base + 1;

    int loaded_any = 0;
    for (size_t i = 0; i < script_include_file_count; ++i) {
        th_pushvalue(state, find_function);
        LuaStackResult result;
        th_pushstring(state, &result, script_include_files[i].name);
        /* Native calls string.find(candidate, pattern) with default pattern
         * semantics (no plain=true). The function's first return is a match
         * position or nil; captured return values are discarded. */
        th_pushvalue(state, 1); /* preserve full Lua string bytes, including NUL */
        th_call(state, 2, 2);
        int matched = th_type(state, -2) != 0;
        th_settop(state, find_function);
        if (!matched) continue;

        ScriptIncludeOwned* file = &script_include_files[i];
        if (!file->source_length)
            return th_lerror(state, "Attempt to load empty file. Lua files must not be empty. where=1, file=%s", file->name);
        int status = th_loadbuffer(state, file->source, file->source_length, file->name);
        if (status) return th_error(state);
        th_call(state, 0, 0);
        loaded_any = 1;
    }
    th_settop(state, base);
    (void)loaded_any; /* Native include also returns zero Lua values. */
    return 0;
}

static int __cdecl script_include_install_callback(LuaState* state) {
    th_closure(state, script_include_callback, 0, "lInclude", 0);
    th_setfield(state, LUA_GLOBALS, "include");
    return 0;
}

__declspec(dllexport) int __cdecl LAB_ScriptIncludeInstall(LuaState* child) {
    if (!script_known_child(child) || th_gettop(child) != 0 || !script_include_file_count)
        return -1704;
    return th_cpcall(child, script_include_install_callback, NULL);
}
