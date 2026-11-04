/* Ported root-script diagnostics, using the host VM heap and existing HKS API.
 * Include after LuaState/th_* declarations and havok_heap globals. This is a
 * diagnostic stderr sink, not an implementation of ScriptManager categories
 * or its StateName routing semantics.
 */
#define SCRIPT_DIAG_PRINT_LIMIT ((size_t)1048576)

static uint32_t script_diag_num_regions;
static uint32_t script_diag_user_max_bytes;
static uint32_t script_diag_user_current_bytes;
static uint32_t script_diag_heap_allocated_bytes;
static uint32_t script_diag_heap_reserved_bytes;
static uint32_t script_diag_heap_overhead_bytes;
static uint32_t script_diag_heap_uncommitted_bytes;

/* EXE 971cf0 accounts after HeapAlloc even on failure, before HeapFree and
 * before HeapReAlloc. Free also updates the maximum after unsigned wrap. */
static void script_diag_account_alloc(SIZE_T requested) {
    script_diag_user_current_bytes += (uint32_t)requested;
    if (script_diag_user_current_bytes > script_diag_user_max_bytes)
        script_diag_user_max_bytes = script_diag_user_current_bytes;
}

static void script_diag_account_free(SIZE_T old_heap_size) {
    script_diag_user_current_bytes -= (uint32_t)old_heap_size;
    if (script_diag_user_current_bytes > script_diag_user_max_bytes)
        script_diag_user_max_bytes = script_diag_user_current_bytes;
}

static void script_diag_account_realloc(SIZE_T old_heap_size, SIZE_T requested) {
    script_diag_user_current_bytes -= (uint32_t)old_heap_size;
    script_diag_user_current_bytes += (uint32_t)requested;
    if (script_diag_user_current_bytes > script_diag_user_max_bytes)
        script_diag_user_max_bytes = script_diag_user_current_bytes;
}

static int script_diag_append(char** data, size_t* length, size_t* capacity,
                              const char* addition, size_t amount) {
    if (amount > SCRIPT_DIAG_PRINT_LIMIT - *length) return 0;
    size_t needed = *length + amount;
    if (needed > *capacity) {
        size_t next = *capacity ? *capacity : 128;
        while (next < needed) {
            if (next > SCRIPT_DIAG_PRINT_LIMIT / 2) { next = SCRIPT_DIAG_PRINT_LIMIT; break; }
            next *= 2;
        }
        if (next < needed) return 0;
        HANDLE process_heap = GetProcessHeap();
        void* grown = *data ? HeapReAlloc(process_heap, 0, *data, next)
                            : HeapAlloc(process_heap, 0, next);
        if (!grown) return 0;
        *data = (char*)grown;
        *capacity = next;
    }
    if (amount) memcpy(*data + *length, addition, amount);
    *length = needed;
    return 1;
}

static SRWLOCK script_diag_stderr_lock = SRWLOCK_INIT;

/* Byte-preserving JSON escaping: non-ASCII Lua bytes are emitted as \u00XX,
 * avoiding assumptions about the encoding of arbitrary tostring results. */
static void script_diag_emit_print(const char* bytes, size_t length) {
    static const char hex[] = "0123456789abcdef";
    AcquireSRWLockExclusive(&script_diag_stderr_lock);
    fputs("{\"event\":\"lua_print_diagnostic\",\"text\":\"", stderr);
    for (size_t i = 0; i < length; ++i) {
        unsigned char c = (unsigned char)bytes[i];
        if (c == '"' || c == '\\') { fputc('\\', stderr); fputc(c, stderr); }
        else if (c == '\b') fputs("\\b", stderr);
        else if (c == '\f') fputs("\\f", stderr);
        else if (c == '\n') fputs("\\n", stderr);
        else if (c == '\r') fputs("\\r", stderr);
        else if (c == '\t') fputs("\\t", stderr);
        else if (c < 0x20 || c >= 0x80) {
            fputs("\\u00", stderr);
            fputc(hex[c >> 4], stderr);
            fputc(hex[c & 15], stderr);
        } else fputc(c, stderr);
    }
    fputs("\"}\n", stderr);
    fflush(stderr);
    ReleaseSRWLockExclusive(&script_diag_stderr_lock);
}

static int __cdecl script_diag_print(LuaState* state) {
    int top = th_gettop(state);
    if (top > 4096) return th_lerror(state, "Civ6RL print argument bound refused");
    th_checkstack(state, 3, "Civ6RL print tostring call");
    char* joined = NULL;
    size_t length = 0, capacity = 0;
    th_getfield(state, LUA_GLOBALS, "tostring"); /* Native captures this once per print call. */
    for (int argument = 1; argument <= top; ++argument) {
        th_pushvalue(state, top + 1);
        th_pushvalue(state, argument);
        int status = th_pcall(state, 1, 1, 0);
        if (status) {
            if (joined) HeapFree(GetProcessHeap(), 0, joined);
            th_remove(state, top + 1); /* Drop captured tostring, retain the original error object. */
            return th_error(state); /* Re-raise the exact original tostring error. */
        }
        if (th_type(state, -1) != 4) {
            if (joined) HeapFree(GetProcessHeap(), 0, joined);
            th_settop(state, top);
            return th_lerror(state, "'tostring' must return a string to 'print'");
        }
        size_t text_length = 0;
        const char* text = th_checkstring(state, -1, &text_length);
        if ((argument > 1 && !script_diag_append(&joined, &length, &capacity, "\t", 1)) ||
            !script_diag_append(&joined, &length, &capacity, text, text_length)) {
            if (joined) HeapFree(GetProcessHeap(), 0, joined);
            return th_lerror(state, "Civ6RL diagnostic print size bound refused");
        }
        th_settop(state, top + 1); /* Keep the captured function; discard only this result. */
    }
    th_settop(state, top);
    script_diag_emit_print(joined ? joined : "", length);
    if (joined) HeapFree(GetProcessHeap(), 0, joined);
    return 0;
}

static void script_diag_collect_heap(void) {
    script_diag_num_regions = 0;
    script_diag_heap_allocated_bytes = 0;
    script_diag_heap_reserved_bytes = 0;
    script_diag_heap_overhead_bytes = 0;
    script_diag_heap_uncommitted_bytes = 0;
    if (!havok_heap || !HeapLock(havok_heap)) return;

    PROCESS_HEAP_ENTRY entry;
    ZeroMemory(&entry, sizeof(entry));
    while (HeapWalk(havok_heap, &entry)) {
        if (entry.wFlags & PROCESS_HEAP_ENTRY_BUSY)
            script_diag_heap_allocated_bytes += (uint32_t)entry.cbData;
        if (entry.wFlags & PROCESS_HEAP_REGION) {
            script_diag_heap_reserved_bytes += entry.Region.dwCommittedSize;
            ++script_diag_num_regions;
            script_diag_heap_uncommitted_bytes += entry.Region.dwUnCommittedSize;
        }
        if (entry.wFlags & (PROCESS_HEAP_ENTRY_BUSY | PROCESS_HEAP_REGION))
            script_diag_heap_overhead_bytes += entry.cbOverhead;
    }
    HeapUnlock(havok_heap);
}

static void script_diag_set_number(LuaState* state, const char* key, uint32_t value) {
    LuaStackResult result;
    th_pushstring(state, &result, key);
    th_number(state, (double)value);
    th_rawset(state, -3);
}

static int __cdecl script_diag_get_memory_usage(LuaState* state) {
    th_checkstack(state, 16, "Civ6RL memory statistics");
    th_newtable(state, 0, 7);
    script_diag_set_number(state, "NumRegions", script_diag_num_regions);
    script_diag_set_number(state, "MaxUserAllocatedBytes", script_diag_user_max_bytes);
    script_diag_set_number(state, "CurrentUserAllocatedBytes", script_diag_user_current_bytes);
    script_diag_set_number(state, "CurrentAllocatedBytes", script_diag_heap_allocated_bytes);
    script_diag_set_number(state, "CurrentReservedBytes", script_diag_heap_reserved_bytes);
    script_diag_set_number(state, "CurrentOverheadBytes", script_diag_heap_overhead_bytes);
    script_diag_set_number(state, "CurrentUncommitedBytes", script_diag_heap_uncommitted_bytes);
    return 1;
}

static int __cdecl script_diag_collect_memory_usage(LuaState* state) {
    (void)state;
    script_diag_collect_heap();
    return 0;
}

#undef SCRIPT_DIAG_PRINT_LIMIT
