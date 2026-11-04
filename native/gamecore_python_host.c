/* A Windows executable host for the Python probe, not a game implementation.
 * GameCore resolves platform exports against GetModuleHandle(NULL). A Python
 * extension DLL therefore cannot provide these executable-owned symbols.
 */
#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include <windows.h>
#include <stdint.h>
#include <stddef.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <errno.h>
#include <intrin.h>
#include "telemetry_profile.h"

/* EXE bd050/bd0c0/bf6a0: the SQL Make_Hash callback is EXE-owned;
 * DatabaseDLL owns the registration/SQL execution and deletes this object
 * via its virtual deleting destructor. No Python callback crosses SQLite.
 */
typedef struct GameplayHash GameplayHash;
typedef struct GameplayHashVtable {
    void* (__cdecl *destroy)(GameplayHash*, unsigned int);
    void (__cdecl *invoke)(GameplayHash*, void*);
} GameplayHashVtable;
struct GameplayHash {
    const GameplayHashVtable* vtable;
    uint32_t table[256];
    uint32_t polynomial, initial;
};
static uintptr_t gameplay_database_module = 0;
static size_t gameplay_hash_allocated = 0, gameplay_hash_freed = 0;
static size_t gameplay_hash_calls = 0, gameplay_hash_texts = 0;
static size_t gameplay_hash_nulls = 0, gameplay_hash_errors = 0;

static __declspec(noreturn) void gameplay_abi_refused(void) {
    fprintf(stdout, "{\"stage\":\"gameplay_sql_callback_abi_refused\",\"exit_code\":78}\n");
    fflush(stdout);
    TerminateProcess(GetCurrentProcess(), 78);
    abort();
}

static int gameplay_slot_is(void* object, size_t slot, uintptr_t rva) {
    return object && *(uintptr_t*)(*(uintptr_t*)object + slot) == gameplay_database_module + rva;
}

static void* __cdecl gameplay_hash_destroy(GameplayHash* self, unsigned int flags) {
    uintptr_t saved = (uintptr_t)self;
    if (flags & 1) { ++gameplay_hash_freed; free(self); }
    return (void*)saved;
}

static void __cdecl gameplay_hash_invoke(GameplayHash* self, void* context) {
    typedef int (__cdecl *ArgCount)(void*);
    typedef int (__cdecl *ArgType)(void*, int);
    typedef const unsigned char* (__cdecl *ArgText)(void*, int);
    typedef void (__cdecl *ResultError)(void*, const char*);
    typedef void (__cdecl *ResultNull)(void*);
    typedef void (__cdecl *ResultInt)(void*, int32_t);
    if (!context || *(uintptr_t*)context != gameplay_database_module + 0xb8b50 ||
        !gameplay_slot_is(context, 0x10, 0x3be0) || !gameplay_slot_is(context, 0x18, 0x3bf0) ||
        !gameplay_slot_is(context, 0x20, 0x3d20) || !gameplay_slot_is(context, 0x48, 0x3db0) ||
        !gameplay_slot_is(context, 0x50, 0x3dc0) || !gameplay_slot_is(context, 0x78, 0x3dd0))
        gameplay_abi_refused();
    ++gameplay_hash_calls;
    int argc = ((ArgCount)(gameplay_database_module + 0x3be0))(context);
    int type = argc == 1 ? ((ArgType)(gameplay_database_module + 0x3bf0))(context, 0) : -1;
    if (type == 5) {
        ++gameplay_hash_nulls;
        ((ResultNull)(gameplay_database_module + 0x3dc0))(context);
    } else if (type == 3) {
        const unsigned char* value = ((ArgText)(gameplay_database_module + 0x3d20))(context, 0);
        if (!value) gameplay_abi_refused();
        uint32_t state = UINT32_MAX;
        size_t length = 0;
        while (*value) {
            if (++length > 1048576) gameplay_abi_refused();
            state = (state >> 8) ^ self->table[(state ^ *value++) & 255];
        }
        ++gameplay_hash_texts;
        ((ResultInt)(gameplay_database_module + 0x3dd0))(context, (int32_t)state);
    } else {
        ++gameplay_hash_errors;
        ((ResultError)(gameplay_database_module + 0x3db0))(context, "Invalid Argument(s).");
    }
}
static const GameplayHashVtable gameplay_hash_vtable = { gameplay_hash_destroy, gameplay_hash_invoke };

__declspec(dllexport) int __cdecl LAB_GameplayMemoryInitialize(void* module, void* connection) {
    typedef int (__cdecl *Register)(void*, const char*, int, unsigned char, GameplayHash*);
    typedef unsigned char (__cdecl *Execute)(void*, const char*, int);
    if (!module || !connection ||
        (gameplay_database_module && gameplay_database_module != (uintptr_t)module)) return -1400;
    gameplay_database_module = (uintptr_t)module;
    if (*(uintptr_t*)connection != gameplay_database_module + 0xb8578 ||
        !gameplay_slot_is(connection, 0xf0, 0x2570) || !gameplay_slot_is(connection, 0x20, 0x1ae0) ||
        !gameplay_slot_is(connection, 8, 0x1a80)) return -1401;
    GameplayHash* callback = (GameplayHash*)calloc(1, sizeof(GameplayHash));
    if (!callback) return -1402;
    ++gameplay_hash_allocated;
    callback->vtable = &gameplay_hash_vtable;
    callback->polynomial = 0xedb88320;
    callback->initial = UINT32_MAX;
    for (uint32_t i = 0; i < 256; ++i) {
        uint32_t c = i;
        for (unsigned int j = 0; j < 8; ++j) c = (c >> 1) ^ ((c & 1) ? callback->polynomial : 0);
        callback->table[i] = c;
    }
    /* SQLite registration assumes ownership, including its failure cleanup.
     * The caller still owns/releases the connection if any step fails. */
    int result = ((Register)(gameplay_database_module + 0x2570))(
        connection, "Make_Hash", 1, 1, callback);
    if (result != 0) return -1403;
    Execute execute = (Execute)(gameplay_database_module + 0x1ae0);
    if (!execute(connection, "PRAGMA foreign_keys = ON;", -1)) return -1404;
    if (!execute(connection, "PRAGMA recursive_triggers = ON;", -1)) return -1405;
    return 0;
}

__declspec(dllexport) size_t __cdecl LAB_GameplayHashCounter(unsigned int which) {
    switch (which) {
        case 0: return gameplay_hash_allocated;
        case 1: return gameplay_hash_freed;
        case 2: return gameplay_hash_calls;
        case 3: return gameplay_hash_texts;
        case 4: return gameplay_hash_nulls;
        case 5: return gameplay_hash_errors;
        default: return (size_t)-1;
    }
}

/* EXE 972af0/971cf0: lua_newstate uses a private growable Windows heap,
 * HeapCreate(0, 64 MiB, 0), LFH compatibility mode 2 and flags-zero
 * HeapAlloc/ReAlloc/Free. Keep the allocation callback entirely native.
 * This is only the root VM allocation kernel, not the EXE script factory.
 * One heap per diagnostic process; refuse overlapping ownership/lost blocks.
 */
static HANDLE havok_heap = NULL;
/* EXE DB3560/DB48f0/DB5510 share one recursive Win32 critical section.
 * Its lifetime here is the single owned script runtime, not a fake success. */
static CRITICAL_SECTION script_lock;
static int script_lock_ready = 0;
static DWORD script_lock_owner = 0;
static unsigned int script_lock_depth = 0;
/* EXE host +30/+38/+40 query, temporarily release and reacquire the
 * GameCore execution lock. It is distinct from the HKS lock above. */
static CRITICAL_SECTION core_execution_lock;
static int core_execution_lock_ready = 0;
static DWORD core_execution_lock_owner = 0;
static unsigned int core_execution_lock_depth = 0;
__declspec(dllexport) int __cdecl LAB_CoreLockCreate(void) {
    if (core_execution_lock_ready) return 0;
    InitializeCriticalSection(&core_execution_lock);
    core_execution_lock_owner = UINT32_MAX;
    core_execution_lock_depth = 0;
    core_execution_lock_ready = 1;
    return 1;
}
__declspec(dllexport) int __cdecl LAB_CoreLockOwned(void) {
    if (!core_execution_lock_ready) return -1;
    return core_execution_lock_owner == GetCurrentThreadId();
}
__declspec(dllexport) int __cdecl LAB_CoreLockAcquire(void) {
    if (!core_execution_lock_ready) return 0;
    if (!TryEnterCriticalSection(&core_execution_lock)) EnterCriticalSection(&core_execution_lock);
    ++core_execution_lock_depth;
    core_execution_lock_owner = GetCurrentThreadId();
    return 1;
}
/* EXE host+48 / F7A20: failure must leave ownership and depth unchanged. */
__declspec(dllexport) int __cdecl LAB_CoreLockTryAcquire(void) {
    if (!core_execution_lock_ready) return -1;
    if (!TryEnterCriticalSection(&core_execution_lock)) return 0;
    ++core_execution_lock_depth;
    core_execution_lock_owner = GetCurrentThreadId();
    return 1;
}
__declspec(dllexport) int __cdecl LAB_CoreLockRelease(void) {
    if (!core_execution_lock_ready || !core_execution_lock_depth ||
        core_execution_lock_owner != GetCurrentThreadId()) return 0;
    if (!--core_execution_lock_depth) core_execution_lock_owner = 0;
    LeaveCriticalSection(&core_execution_lock);
    return 1;
}
__declspec(dllexport) int __cdecl LAB_CoreLockDestroy(void) {
    if (!core_execution_lock_ready || core_execution_lock_depth) return 0;
    DeleteCriticalSection(&core_execution_lock);
    core_execution_lock_ready = 0;
    return 1;
}
__declspec(dllexport) int __cdecl LAB_ScriptLockEnter(void) {
    if (!script_lock_ready) return 0;
    EnterCriticalSection(&script_lock);
    script_lock_owner = GetCurrentThreadId();
    ++script_lock_depth;
    return 1;
}
__declspec(dllexport) int __cdecl LAB_ScriptLockLeave(void) {
    if (!script_lock_ready || !script_lock_depth || script_lock_owner != GetCurrentThreadId()) return 0;
    if (!--script_lock_depth) script_lock_owner = 0;
    LeaveCriticalSection(&script_lock);
    return 1;
}
static size_t havok_live_blocks = 0, havok_allocation_calls = 0;
static size_t havok_reallocation_calls = 0, havok_free_calls = 0;
static void script_diag_account_alloc(SIZE_T requested);
static void script_diag_account_free(SIZE_T old_heap_size);
static void script_diag_account_realloc(SIZE_T old_heap_size, SIZE_T requested);

__declspec(dllexport) int __cdecl LAB_HavokHeapCreate(void) {
    if (havok_heap) return 0;
    havok_heap = HeapCreate(0, 0x4000000, 0);
    if (!havok_heap) return 0;
    ULONG mode = 2;
    if (!HeapSetInformation(havok_heap, HeapCompatibilityInformation, &mode, sizeof(mode))) {
        HeapDestroy(havok_heap); havok_heap = NULL; return 0;
    }
    havok_live_blocks = havok_allocation_calls = havok_reallocation_calls = havok_free_calls = 0;
    InitializeCriticalSection(&script_lock);
    script_lock_ready = 1;
    script_lock_owner = script_lock_depth = 0;
    return 1;
}

__declspec(dllexport) void* __cdecl LAB_HavokAllocate(void* userdata, void* pointer,
                                                    size_t old_size, size_t new_size) {
    (void)old_size; /* The EXE allocator ignores the size supplied by Lua. */
    if (!havok_heap || userdata) {
        TerminateProcess(GetCurrentProcess(), 78); return NULL;
    }
    if (!new_size) {
        if (pointer) {
            script_diag_account_free(HeapSize(havok_heap, 0, pointer));
            if (!HeapFree(havok_heap, 0, pointer) || !havok_live_blocks) {
                TerminateProcess(GetCurrentProcess(), 78); return NULL;
            }
            --havok_live_blocks; ++havok_free_calls;
        } else {
            /* Same null-pointer HeapFree call as the pinned EXE. */
            HeapFree(havok_heap, 0, NULL);
        }
        return NULL;
    }
    void* result;
    if (!pointer) {
        result = HeapAlloc(havok_heap, 0, new_size);
        script_diag_account_alloc(new_size);
        ++havok_allocation_calls;
        if (result) ++havok_live_blocks;
    } else {
        script_diag_account_realloc(HeapSize(havok_heap, 0, pointer), new_size);
        result = HeapReAlloc(havok_heap, 0, pointer, new_size);
        ++havok_reallocation_calls;
    }
    return result;
}

__declspec(dllexport) size_t __cdecl LAB_HavokHeapCounter(unsigned int which) {
    switch (which) {
        case 0: return havok_live_blocks;
        case 1: return havok_allocation_calls;
        case 2: return havok_reallocation_calls;
        case 3: return havok_free_calls;
        default: return (size_t)-1;
    }
}

__declspec(dllexport) int __cdecl LAB_HavokHeapDestroy(void) {
    if (!havok_heap || havok_live_blocks || script_lock_depth) return 0;
    if (!HeapDestroy(havok_heap)) return 0;
    havok_heap = NULL;
    DeleteCriticalSection(&script_lock);
    script_lock_ready = 0;
    return 1;
}

/* Thread-registry subset of EXE 9739f3..973b50, 972e10 and 972f20.
 * This is NOT the complete root initializer or the Map Script factory.
 * Protected Lua callbacks stay in C so an HKS error cannot unwind Python.
 */
typedef void LuaState;
typedef int (__cdecl *LuaCallback)(LuaState*);
typedef struct LuaStackResult { void* state; int index; int padding; } LuaStackResult;
static void (__cdecl *th_newtable)(LuaState*, int, int);
static void (__cdecl *th_pushvalue)(LuaState*, int);
static void (__cdecl *th_setfield)(LuaState*, int, const char*);
static void (__cdecl *th_getfield)(LuaState*, int, const char*);
static void (__cdecl *th_settable)(LuaState*, int);
static int (__cdecl *th_setmeta)(LuaState*, int);
static int (__cdecl *th_setenv)(LuaState*, int);
static void (__cdecl *th_getenv)(LuaState*, int);
static int (__cdecl *th_rawequal)(LuaState*, int, int);
static LuaState* (__cdecl *th_newthread)(LuaState*);
static void (__cdecl *th_pushnil)(LuaState*);
static LuaStackResult* (__cdecl *th_pushbool)(LuaState*, LuaStackResult*, unsigned char);
static LuaStackResult* (__cdecl *th_pushstring)(LuaState*, LuaStackResult*, const char*);
static void (__cdecl *th_closure)(LuaState*, LuaCallback, int, const char*, int);
static int (__cdecl *th_cpcall)(LuaState*, LuaCallback, void*);
static int (__cdecl *th_pcall)(LuaState*, int, int, int);
static int (__cdecl *th_loadbuffer)(LuaState*, const char*, size_t, const char*);
static void (__cdecl *th_call)(LuaState*, int, int);
static void* (__cdecl *th_userdata)(LuaState*, int);
static LuaState* (__cdecl *th_tothread)(LuaState*, int);
static int (__cdecl *th_pushthread)(LuaState*);
static void (__cdecl *th_xmove)(LuaState*, LuaState*, int);
static int (__cdecl *th_next)(LuaState*, int);
static void (__cdecl *th_remove)(LuaState*, int);
static void (__cdecl *th_settop)(LuaState*, int);
static int (__cdecl *th_type)(LuaState*, int);
static int (__cdecl *th_error)(LuaState*);
static int (__cdecl *th_gc)(LuaState*, int, int);
static int (__cdecl *th_gettop)(LuaState*);
static void (__cdecl *th_openlibs)(LuaState*);
static double (__cdecl *th_checknumber)(LuaState*, int);
static int (__cdecl *th_checkinteger)(LuaState*, int);
static int (__cdecl *th_optinteger)(LuaState*, int, int);
static void (__cdecl *th_checktype)(LuaState*, int, int);
static int (__cdecl *th_lerror)(LuaState*, const char*, ...);
static int (__cdecl *th_argerror)(LuaState*, int, const char*);
static void (__cdecl *th_checkstack)(LuaState*, int, const char*);
static unsigned char (__cdecl *th_toboolean)(LuaState*, int);
static void (__cdecl *th_where)(LuaState*, int);
static void (__cdecl *th_number)(LuaState*, double);
static size_t (__cdecl *th_objlen)(LuaState*, int);
static void (__cdecl *th_rawgeti)(LuaState*, int, int);
static void (__cdecl *th_rawseti)(LuaState*, int, int);
static void (__cdecl *th_rawset)(LuaState*, int);
static void (__cdecl *th_rawget)(LuaState*, int);
static void* (__cdecl *th_newuserdata)(LuaState*, size_t);
static const char* (__cdecl *th_checkstring)(LuaState*, int, size_t*);
static const char* (__cdecl *th_tolstring)(LuaState*, int, size_t*);
static LuaState* thread_registry_root = NULL;
static LuaState* host_threads[64] = {0};
static int thread_api_ready = 0;
static size_t gameinfo_active_cursors = 0;
#define LUA_GLOBALS (-10002)
#define LUA_UPVALUE(n) (LUA_GLOBALS-(n))

__declspec(dllexport) int __cdecl LAB_ThreadAPIInitialize(void* module) {
    if (!module || thread_registry_root) return 0;
    thread_api_ready = 0;
#define THREAD_IMPORT(dst, symbol, rva) do { \
    FARPROC proc = GetProcAddress((HMODULE)module, symbol); \
    if ((uintptr_t)proc != (uintptr_t)module + (rva)) return 0; \
    memcpy(&(dst), &proc, sizeof(proc)); \
} while (0)
    THREAD_IMPORT(th_newtable, "?lua_createtable@@YAXPEAUlua_State@@HH@Z", 0x3cb60);
    THREAD_IMPORT(th_pushvalue, "?lua_pushvalue@@YAXPEAUlua_State@@H@Z", 0x1af10);
    THREAD_IMPORT(th_setfield, "?lua_setfield@@YAXPEAUlua_State@@HPEBD@Z", 0x3d560);
    THREAD_IMPORT(th_getfield, "?lua_getfield@@YAXPEAUlua_State@@HPEBD@Z", 0x3cbd0);
    THREAD_IMPORT(th_settable, "?SetTable@LuaState@LuaPlus@@QEAAXH@Z", 0x1c040);
    THREAD_IMPORT(th_setmeta, "?lua_setmetatable@@YAHPEAUlua_State@@H@Z", 0x3d580);
    THREAD_IMPORT(th_setenv, "?lua_setfenv@@YAHPEAUlua_State@@H@Z", 0x3d550);
    THREAD_IMPORT(th_getenv, "?lua_getfenv@@YAXPEAUlua_State@@H@Z", 0x3cbc0);
    THREAD_IMPORT(th_rawequal, "?lua_rawequal@@YAHPEAUlua_State@@HH@Z", 0x3d4f0);
    THREAD_IMPORT(th_newthread, "?lua_newthread@@YAPEAUlua_State@@PEAU1@@Z", 0x3d410);
    THREAD_IMPORT(th_pushnil, "?lua_pushnil@@YAXPEAUlua_State@@@Z", 0x358a0);
    THREAD_IMPORT(th_pushbool, "?PushBoolean@LuaState@LuaPlus@@QEAA?AVLuaStackObject@2@_N@Z", 0x1a9f0);
    THREAD_IMPORT(th_pushstring, "?PushString@LuaState@LuaPlus@@QEAA?AVLuaStackObject@2@PEBD@Z", 0x1ade0);
    THREAD_IMPORT(th_closure, "?hks_pushnamedcclosure@@YAXPEAUlua_State@@P6AH0@ZHPEBDH@Z", 0x2eeb0);
    THREAD_IMPORT(th_cpcall, "?lua_cpcall@@YAHPEAUlua_State@@P6AH0@ZPEAX@Z", 0x16620);
    THREAD_IMPORT(th_pcall, "?lua_pcall@@YAHPEAUlua_State@@HHH@Z", 0x3d490);
    THREAD_IMPORT(th_loadbuffer, "?luaL_loadbuffer@@YAHPEAUlua_State@@PEBD_K1@Z", 0x33340);
    THREAD_IMPORT(th_call, "?lua_call@@YAXPEAUlua_State@@HH@Z", 0x336e0);
    THREAD_IMPORT(th_userdata, "?lua_touserdata@@YAPEAXPEAUlua_State@@H@Z", 0x3d620);
    THREAD_IMPORT(th_tothread, "?lua_tothread@@YAPEAUlua_State@@PEAU1@H@Z", 0x3d610);
    THREAD_IMPORT(th_pushthread, "?lua_pushthread@@YAHPEAUlua_State@@@Z", 0x358c0);
    THREAD_IMPORT(th_xmove, "?XMove@LuaState@LuaPlus@@QEAAXPEAV12@H@Z", 0x1c8b0);
    THREAD_IMPORT(th_next, "?lua_next@@YAHPEAUlua_State@@H@Z", 0x1a3a0);
    THREAD_IMPORT(th_remove, "?lua_remove@@YAXPEAUlua_State@@H@Z", 0x1b390);
    THREAD_IMPORT(th_settop, "?lua_settop@@YAXPEAUlua_State@@H@Z", 0x36ca0);
    THREAD_IMPORT(th_type, "?lua_type@@YAHPEAUlua_State@@H@Z", 0x3d630);
    THREAD_IMPORT(th_error, "?lua_error@@YAHPEAUlua_State@@@Z", 0x3cbb0);
    THREAD_IMPORT(th_gc, "?lua_gc@@YAHPEAUlua_State@@HH@Z", 0x18d50);
    THREAD_IMPORT(th_gettop, "?lua_gettop@@YAHPEAUlua_State@@@Z", 0x3d280);
    THREAD_IMPORT(th_openlibs, "?luaL_openlibs@@YAXPEAUlua_State@@@Z", 0x3c790);
    THREAD_IMPORT(th_checknumber, "?luaL_checknumber@@YANPEAUlua_State@@H@Z", 0x3bda0);
    THREAD_IMPORT(th_argerror, "?luaL_argerror@@YAHPEAUlua_State@@HPEBD@Z", 0x3bc30);
    THREAD_IMPORT(th_checkstack, "?luaL_checkstack@@YAXPEAUlua_State@@HPEBD@Z", 0x16730);
    THREAD_IMPORT(th_toboolean, "?lua_toboolean@@YA_NPEAUlua_State@@H@Z", 0x3d5a0);
    THREAD_IMPORT(th_checkinteger, "?luaL_checkinteger@@YAHPEAUlua_State@@H@Z", 0x3bd10);
    THREAD_IMPORT(th_optinteger, "?luaL_optinteger@@YAHPEAUlua_State@@HH@Z", 0x3c8e0);
    THREAD_IMPORT(th_checktype, "?luaL_checktype@@YAXPEAUlua_State@@HH@Z", 0x167e0);
    THREAD_IMPORT(th_lerror, "?luaL_error@@YAHPEAUlua_State@@PEBDZZ", 0x33220);
    THREAD_IMPORT(th_where, "?luaL_where@@YAXPEAUlua_State@@H@Z", 0x1c6e0);
    THREAD_IMPORT(th_number, "?lua_pushnumber@@YAXPEAUlua_State@@N@Z", 0x3d4c0);
    THREAD_IMPORT(th_objlen, "?lua_objlen@@YA_KPEAUlua_State@@H@Z", 0x3d480);
    THREAD_IMPORT(th_rawgeti, "?lua_rawgeti@@YAXPEAUlua_State@@HH@Z", 0x3d510);
    THREAD_IMPORT(th_rawseti, "?lua_rawseti@@YAXPEAUlua_State@@HH@Z", 0x3d530);
    THREAD_IMPORT(th_rawset, "?lua_rawset@@YAXPEAUlua_State@@H@Z", 0x3d520);
    THREAD_IMPORT(th_rawget, "?lua_rawget@@YAXPEAUlua_State@@H@Z", 0x3d500);
    THREAD_IMPORT(th_newuserdata, "?lua_newuserdata@@YAPEAXPEAUlua_State@@_K@Z", 0x3d420);
    THREAD_IMPORT(th_checkstring, "?luaL_checklstring@@YAPEBDPEAUlua_State@@HPEA_K@Z", 0x3bd90);
    THREAD_IMPORT(th_tolstring, "?lua_tolstring@@YAPEBDPEAUlua_State@@HPEA_K@Z", 0x3d5e0);
#undef THREAD_IMPORT
    thread_api_ready = 1;
    return 1;
}

static int __cdecl thread_create_closure(LuaState* state) {
    LuaStackResult result;
    /* No arguments are consumed. Positive indices therefore cannot be fixed
     * to 1 and 2: the EXE derives them from the current stack depth. */
    th_pushvalue(state, LUA_UPVALUE(2));
    th_pushvalue(state, LUA_UPVALUE(1));
    th_newthread(state);
    th_pushvalue(state, -1);
    th_pushvalue(state, -1);
    th_newtable(state, 0, 0);
    th_pushvalue(state, -1);
    th_setenv(state, -3);
    th_settable(state, -5);  /* strong[thread] = environment */
    th_pushbool(state, &result, 1);
    th_settable(state, -5);  /* weak[thread] = true */
    return 1;
}

static int __cdecl thread_destroy_closure(LuaState* state) {
    th_pushvalue(state, LUA_UPVALUE(1));
    th_pushvalue(state, 1);
    th_pushnil(state);
    th_settable(state, -3);
    return 0;
}

static int __cdecl thread_install_callback(LuaState* state) {
    LuaStackResult result;
    th_newtable(state, 0, 0); /* strong */
    th_pushvalue(state, -1);
    th_setfield(state, LUA_GLOBALS, "Threads");
    th_pushvalue(state, -1);
    th_newtable(state, 0, 0); /* weak keys */
    th_pushvalue(state, -1);
    th_newtable(state, 0, 0);
    th_pushstring(state, &result, "k");
    th_setfield(state, -2, "__mode");
    th_setmeta(state, -2);
    th_setfield(state, LUA_GLOBALS, "WeakThreads");
    th_closure(state, thread_create_closure, 2, "lCreateThread", 0);
    th_setfield(state, LUA_GLOBALS, "_CreateThread");
    th_closure(state, thread_destroy_closure, 1, "lDestroyThread", 0);
    th_setfield(state, LUA_GLOBALS, "_DestroyThread");
    return 0;
}

__declspec(dllexport) int __cdecl LAB_ThreadRegistryInstall(LuaState* state) {
    if (!state || thread_registry_root || !thread_api_ready) return -1000;
    int status = th_cpcall(state, thread_install_callback, NULL);
    if (!status) thread_registry_root = state;
    return status;
}

static int thread_is_registered(LuaState* state, LuaState* child) {
    int top = th_gettop(state), found = 0;
    th_getfield(state, LUA_GLOBALS, "Threads");
    th_pushnil(state);
    while (th_next(state, -2)) {
        if (th_tothread(state, -2) == child && th_type(state, -1) == 5) { found = 1; break; }
        th_settop(state, -2);
    }
    th_settop(state, top);
    return found;
}

static int __cdecl thread_acquire_callback(LuaState* state) {
    LuaState** output = (LuaState**)th_userdata(state, 1);
    th_getfield(state, LUA_GLOBALS, "_CreateThread");
    th_call(state, 0, 1);
    LuaState* child = th_tothread(state, -1);
    if (child && !thread_is_registered(state, child)) {
        LuaStackResult result;
        th_pushstring(state, &result, "Unverified thread absent from native registry");
        return th_error(state);
    }
    *output = child;
    return 0;
}

__declspec(dllexport) int __cdecl LAB_ThreadAcquire(LuaState* state, LuaState** output) {
    if (!state || state != thread_registry_root || !output) return -1000;
    *output = NULL;
    size_t slot = 0;
    while (slot < 64 && host_threads[slot]) ++slot;
    if (slot == 64) return -1002;
    int status = th_cpcall(state, thread_acquire_callback, output);
    if (!status && *output) {
        if (*output == state) { *output = NULL; return -1004; }
        for (size_t i = 0; i < 64; ++i) {
            if (host_threads[i] == *output) { *output = NULL; return -1004; }
        }
        host_threads[slot] = *output;
    }
    return status ? status : (*output ? 0 : -1001);
}

static int __cdecl thread_clear_environment(LuaState* state) {
    if (th_type(state, 1) != 5) return 0;
    th_pushnil(state);
    while (th_next(state, 1)) {
        th_settop(state, -2); /* discard value, retain iteration key */
        th_pushvalue(state, -1);
        th_pushnil(state);
        th_settable(state, 1);
    }
    return 0;
}

static int __cdecl thread_release_callback(LuaState* state) {
    LuaState* child = (LuaState*)th_userdata(state, 1);
    th_getfield(state, LUA_GLOBALS, "_DestroyThread");
    th_getfield(state, LUA_GLOBALS, "Threads");
    th_pushnil(state);
    int found = 0;
    while (th_next(state, 3)) {
        if (th_tothread(state, -2) == child) { found = 1; break; }
        th_settop(state, -2);
    }
    if (!found) {
        LuaStackResult result;
        th_pushstring(state, &result, "Unverified thread absent from native registry");
        return th_error(state);
    }
    th_remove(state, 3); /* remove table from stack; retain thread + env */
    th_closure(state, thread_clear_environment, 0, "pClearLuaEnv", 0);
    th_pushvalue(state, -2);
    th_call(state, 1, 0);
    th_settop(state, -2); /* discard now-empty environment */
    th_call(state, 1, 0);
    if (thread_is_registered(state, child)) {
        LuaStackResult result;
        th_pushstring(state, &result, "Thread still registered after destroy callback");
        return th_error(state);
    }
    return 0;
}

__declspec(dllexport) int __cdecl LAB_ThreadRelease(LuaState* state, LuaState* child) {
    if (!state || state != thread_registry_root || !child || child == state) return -1000;
    size_t slot = 0;
    while (slot < 64 && host_threads[slot] != child) ++slot;
    if (slot == 64) return -1003;
    int status = th_cpcall(state, thread_release_callback, child);
    if (!status) host_threads[slot] = NULL;
    th_gc(state, 2, 0); /* EXE manager 971ef0 collects after protected release */
    return status;
}

/* Called only after lua_close(root). No child lua_close is valid. */
__declspec(dllexport) int __cdecl LAB_ThreadRegistryForget(LuaState* closed_root) {
    if (thread_registry_root != closed_root) return 0;
    thread_registry_root = NULL;
    memset(host_threads, 0, sizeof(host_threads));
    return 1;
}

/* Source-backed root primitives from EXE 973610..973dc8. Diagnostic subset:
 * never returned as a complete Map Script context. See phase36 captures.
 * Keep IEEE unordered/signed-zero behavior; do not compile with /fp:fast.
 */
static int __cdecl root_clamp(LuaState* state) {
    double value = th_checknumber(state, 1);
    double lower = th_checknumber(state, 2);
    double upper = th_checknumber(state, 3);
    double result = value > lower ? value : lower;
    /* MSVC folds even /fp:strict into MINSD, choosing the wrong operand on
     * signed-zero equality. Retain the ordered predicate as an actual value.
     * EXE's COMISD/JB keeps candidate on unordered, selects upper on equality.
     */
    volatile int select_upper = result >= upper;
    if (select_upper) result = upper;
    th_number(state, result);
    return 1;
}

static int __cdecl root_count(LuaState* state) {
    th_checktype(state, 1, 5);
    uint32_t count = 0;
    th_pushnil(state);
    while (th_next(state, 1)) {
        ++count;
        th_settop(state, -2);
    }
    /* EXE wraps its EBP counter and converts a signed 32-bit integer. */
    int32_t signed_count;
    memcpy(&signed_count, &count, sizeof(count));
    th_number(state, (double)signed_count);
    return 1;
}

static int __cdecl root_fill(LuaState* state) {
    int nargs = th_gettop(state), table_index, value_index, count;
    if (nargs != 2 && nargs != 3) return th_lerror(state, "Invalid arguments.");
    count = th_checkinteger(state, nargs);
    /* Explicit bounded-probe guards, NOT asserted Civ6 error semantics.
     * Negative allocation hints and positive writes through non-table objects
     * are withheld until their underlying Havok behavior is established.
     */
    if (count > 1048576 || (nargs == 2 && count < 0))
        return th_lerror(state, "Civ6RL diagnostic refuses unverified table.fill allocation size");
    if (nargs == 2) {
        th_newtable(state, count, 0);
        table_index = 3; value_index = 1;
    } else {
        table_index = 1; value_index = 2;
        if (count > 0 && th_type(state, 1) != 5)
            return th_lerror(state, "Civ6RL diagnostic refuses unverified table.fill non-table write");
    }
    for (int i = 1; i <= count; ++i) {
        th_pushvalue(state, value_index);
        th_rawseti(state, table_index, i);
    }
    th_pushvalue(state, table_index);
    return 1;
}

static int __cdecl root_ipairs_aux(LuaState* state) {
    th_checktype(state, 1, 5);
    uint32_t next_bits = (uint32_t)th_checkinteger(state, 2) + 1u;
    int32_t next_index;
    memcpy(&next_index, &next_bits, sizeof(next_index));
    th_number(state, (double)next_index);
    th_rawgeti(state, 1, next_index);
    return th_type(state, -1) == 0 ? 0 : 2;
}

static int __cdecl root_ipairs(LuaState* state) {
    th_checktype(state, 1, 5);
    th_rawgeti(state, 1, 0);
    int first = th_type(state, -1) == 0 ? 0 : -1;
    th_settop(state, -2);
    th_pushvalue(state, LUA_UPVALUE(1));
    th_pushvalue(state, 1);
    th_number(state, (double)first);
    return 3;
}

static int __cdecl root_where(LuaState* state) {
    th_where(state, th_optinteger(state, 1, 0));
    return 1;
}

#include "script_diagnostics.inc"

static int __cdecl root_primitives_callback(LuaState* state) {
    th_openlibs(state);
    th_getfield(state, LUA_GLOBALS, "math");
    th_closure(state, root_clamp, 0, "pMath_Clamp", 0);
    th_setfield(state, -2, "clamp");
    th_settop(state, -2);
    th_getfield(state, LUA_GLOBALS, "table");
    th_closure(state, root_count, 0, "pTable_Count", 0);
    th_setfield(state, -2, "count");
    th_closure(state, root_fill, 0, "pTable_Fill", 0);
    th_setfield(state, -2, "fill");
    th_settop(state, -2);
    th_closure(state, root_ipairs_aux, 0, "pGlobal_ipairsaux", 0);
    th_closure(state, root_ipairs, 1, "pGlobal_ipairs", 0);
    th_setfield(state, LUA_GLOBALS, "ipairs");
    th_closure(state, root_where, 0, "pGlobal_where", 0);
    th_setfield(state, LUA_GLOBALS, "where");
    const struct { const char* name; LuaCallback callback; } diagnostics[] = {
        {"print", script_diag_print}, {"GetLuaMemoryUsage", script_diag_get_memory_usage},
        {"CollectLuaMemoryUsage", script_diag_collect_memory_usage}};
    for (size_t i = 0; i < sizeof(diagnostics)/sizeof(diagnostics[0]); ++i) {
        th_closure(state, diagnostics[i].callback, 0, diagnostics[i].name, 0);
        th_setfield(state, LUA_GLOBALS, diagnostics[i].name);
    }
    return 0;
}

__declspec(dllexport) int __cdecl LAB_RootPrimitivesInstall(LuaState* state) {
    if (!state || !thread_api_ready || (thread_registry_root && thread_registry_root != state))
        return -1000;
    return th_cpcall(state, root_primitives_callback, NULL);
}

/* Namespace dispatcher EXE 9740e0/974290, environment lookup 974110 and
 * proxy builder 973fe0. This is separate from the still unavailable Map Script
 * factory. Only enumerated, source-backed namespace subsets may be requested.
 */
static int __cdecl namespace_readonly_error(LuaState* state) {
    return th_lerror(state, "Attempt to modify read-only table");
}

static const char* path_ascii_argument(LuaState* state, int index) {
    const char* value = th_checkstring(state, index, NULL);
    /* Native callbacks consume a C-string prefix, convert through two fixed
     * 260-cell buffers, and ignore bytes beyond an embedded NUL. The bounded
     * ASCII subset avoids silently guessing Unicode or truncation behavior.
     */
    size_t i;
    for (i = 0; i < 260 && value[i]; ++i) {
        if ((unsigned char)value[i] > 127)
            th_lerror(state, "Civ6RL Path diagnostic refuses non-ASCII input");
    }
    if (i == 260) th_lerror(state, "Civ6RL Path diagnostic refuses input of 260 or more bytes");
    return value;
}

static const char* path_file_suffix(const char* value) {
    const char* suffix = NULL;
    for (const char* p = value; *p; ++p)
        if (*p == '/' || *p == '\\') suffix = p + 1;
    if (suffix) return suffix;
    /* EXE 7e8d80 strips through the first colon only when no slash exists. */
    const char* colon = strchr(value, ':');
    return colon ? colon + 1 : value;
}

static int __cdecl path_get_file_name(LuaState* state) {
    LuaStackResult result;
    th_pushstring(state, &result, path_file_suffix(path_ascii_argument(state, 1)));
    return 1;
}

static const char* path_extension(const char* value) {
    const char* dot = NULL;
    for (const char* p = value; *p; ++p) {
        if (*p == '/' || *p == '\\') dot = NULL;
        else if (*p == '.') dot = p;
    }
    return dot ? dot : value + strlen(value);
}

static int __cdecl path_get_extension(LuaState* state) {
    LuaStackResult result;
    th_pushstring(state, &result, path_extension(path_ascii_argument(state, 1)));
    return 1;
}

static int __cdecl path_get_directory(LuaState* state) {
    const char* value = path_ascii_argument(state, 1);
    const char* last = NULL;
    for (const char* p = value; *p; ++p)
        if (*p == '/' || *p == '\\') last = p;
    size_t offset = 0;
    if (last) {
        if ((value[0] == '/' || value[0] == '\\') && value[1] == value[0]) {
            offset = 2;
            while (value[offset] && value[offset] != '/' && value[offset] != '\\') ++offset;
        } else {
            for (size_t i = 0; value[i] && value[i] != '/' && value[i] != '\\'; ++i) {
                if (value[i] == ':') { offset = i + 1; break; }
            }
        }
    }
    char directory[260];
    size_t end = last ? (size_t)(last - value) + 1 : 0;
    /* A bare UNC server has offset beyond end; native capacity test declines
     * the negative-length copy and the preinitialized result stays empty. */
    size_t length = end > offset ? end - offset : 0;
    memcpy(directory, value + offset, length); directory[length] = 0;
    LuaStackResult result;
    th_pushstring(state, &result, directory);
    return 1;
}

static int __cdecl path_get_file_without_extension(LuaState* state) {
    const char* value = path_file_suffix(path_ascii_argument(state, 1));
    const char* end = path_extension(value);
    char name[260];
    size_t length = (size_t)(end - value);
    memcpy(name, value, length); name[length] = 0;
    LuaStackResult result;
    th_pushstring(state, &result, name);
    return 1;
}

static int __cdecl path_normalize(LuaState* state) {
    const char* value = path_ascii_argument(state, 1);
    char normalized[260];
    size_t count = 0;
    for (const char* p = value; *p; ++p) {
        char c = *p == '\\' ? '/' : *p;
        if (c == '/' && count && normalized[count-1] == '/' && count != 1) continue;
        normalized[count++] = c;
    }
    normalized[count] = 0;
    LuaStackResult result;
    th_pushstring(state, &result, normalized);
    return 1;
}

static int __cdecl path_uses_extension(LuaState* state) {
    const char* path = path_ascii_argument(state, 1);
    size_t wanted_length = 0;
    const char* wanted = th_checkstring(state, 2, &wanted_length);
    if (wanted_length >= 260)
        return th_lerror(state, "Civ6RL Path diagnostic refuses input of 260 or more bytes");
    for (size_t i = 0; i < wanted_length; ++i)
        if ((unsigned char)wanted[i] > 127)
            return th_lerror(state, "Civ6RL Path diagnostic refuses non-ASCII input");
    const char* ext = path_extension(path);
    size_t length = strlen(ext);
    unsigned char same = (unsigned char)(length == wanted_length && !_strnicmp(ext, wanted, length));
    LuaStackResult result;
    th_pushbool(state, &result, same);
    return 1;
}

static int __cdecl namespace_create_path(LuaState* state) {
    static const struct { const char* name; const char* debug; LuaCallback callback; } methods[] = {
        {"GetDirectoryName", "lGetDirectoryName", path_get_directory},
        {"GetExtension", "lGetExtension", path_get_extension},
        {"GetFileName", "lGetFileName", path_get_file_name},
        {"GetFileNameWithoutExtension", "lGetFileNameWithoutExtension", path_get_file_without_extension},
        {"NormalizePath", "lNormalizePath", path_normalize},
        {"UsesExtension", "lUsesExtension", path_uses_extension},
    };
    th_newtable(state, 0, 6);
    for (size_t i = 0; i < sizeof(methods)/sizeof(methods[0]); ++i) {
        th_closure(state, methods[i].callback, 0, methods[i].debug, 0);
        th_setfield(state, -2, methods[i].name);
    }
    return 1;
}

typedef struct NamespaceRequest {
    LuaState* child;
    const char* name;
    LuaCallback create;
} NamespaceRequest;

/* EXE 2a3540 / 2a2cf0 / 2a0a60: GlobalParameters table/cache and row
 * conversion. The DB dependency is borrowed and explicitly bound by the
 * diagnostic owner. It is not a substitute for the EXE's active DB service.
 */
static void* parameter_connection = NULL;
static uintptr_t parameter_module = 0;
static void* parameter_cursor = NULL;
static void* db_configuration_connection = NULL;
static int32_t db_configuration_base = 0;
static size_t parameter_queries = 0, parameter_releases = 0, parameter_rows = 0;
typedef void* (__cdecl *ParameterQuery)(void*, const char*, int);
typedef unsigned char (__cdecl *ParameterAdvance)(void*);
typedef const char* (__cdecl *ParameterString)(void*, int);
typedef void (__cdecl *ParameterRelease)(void*);

static int parameter_slot_is(void* object, size_t slot, uintptr_t rva) {
    return object && *(uintptr_t*)(*(uintptr_t*)object + slot) == parameter_module + rva;
}

__declspec(dllexport) int __cdecl LAB_ParameterDatabaseBind(LuaState* root, void* module,
                                                         void* connection) {
    if (!root || root != thread_registry_root || parameter_cursor || gameinfo_active_cursors) return -1000;
    if (!module && !connection) {
        if (db_configuration_connection) return -1500;
        parameter_connection = NULL; parameter_module = 0; return 0;
    }
    if (!module || !connection || parameter_connection) return -1200;
    uintptr_t base = (uintptr_t)module;
    if (*(uintptr_t*)connection != base + 0xb8578) return -1201;
    parameter_module = base;
    if (!parameter_slot_is(connection, 0x18, 0x23a0) ||
        !parameter_slot_is(connection, 8, 0x1a80)) {
        parameter_module = 0; return -1201;
    }
    parameter_connection = connection;
    return 0;
}

static void parameter_close_cursor(void) {
    if (parameter_cursor) {
        ParameterRelease release = (ParameterRelease)(parameter_module + 0x4600);
        release(parameter_cursor); parameter_cursor = NULL; ++parameter_releases;
    }
}

__declspec(dllexport) size_t __cdecl LAB_ParameterCounter(unsigned int which) {
    switch (which) {
        case 0: return parameter_queries;
        case 1: return parameter_releases;
        case 2: return parameter_rows;
        case 3: return parameter_cursor != NULL;
        default: return (size_t)-1;
    }
}

static void parameter_push_value(LuaState* state, const char* value) {
    if (!value || !value[0] || !_strnicmp(value, "NULL", 4)) {
        th_pushnil(state); return;
    }
    size_t length = strnlen(value, 65537);
    if (length > 65536) {
        th_lerror(state, "Civ6RL parameter diagnostic refuses long values"); return;
    }
    int decimal = 0, number = 1;
    for (size_t i = 0; i < length; ++i) {
        unsigned char c = (unsigned char)value[i];
        if (c >= '0' && c <= '9') continue;
        if (c == '.' && !decimal && value[i+1] >= '0' && value[i+1] <= '9') {
            decimal = 1; continue;
        }
        number = 0; break;
    }
    if (!number) {
        LuaStackResult result;
        th_pushstring(state, &result, value); return;
    }
    char* end = NULL;
    errno = 0;
    double result;
    if (decimal) {
        float single = strtof(value, &end);
        result = (double)single;
    } else {
        long integer = strtol(value, &end, 10); /* Win64 long is signed 32-bit. */
        result = (double)integer;
    }
    if (errno == ERANGE || end == value || *end) {
        /* Original throws C++ invalid/range exceptions. Do not invent the
         * surrounding EXE exception routing inside this protected C subset. */
        th_lerror(state, "Civ6RL parameter diagnostic refuses native C++ numeric exception path");
        return;
    }
    th_number(state, result);
}

static int __cdecl namespace_create_parameters(LuaState* state) {
    if (!parameter_connection)
        return th_lerror(state, "Civ6RL parameter database service is not bound");
    th_getfield(state, LUA_GLOBALS, "GlobalParameters_Data");
    if (th_type(state, -1) == 0) {
        th_settop(state, -2); th_newtable(state, 0, 0);
        th_pushvalue(state, -1); th_setfield(state, LUA_GLOBALS, "GlobalParameters_Data");
    }
    if (th_type(state, -1) != 5)
        return th_lerror(state, "Civ6RL parameter diagnostic refuses non-table data cache");
    int table_index = th_gettop(state);
    ParameterQuery query = (ParameterQuery)(parameter_module + 0x23a0);
    void* cursor = query(parameter_connection, "SELECT Name, Value FROM GlobalParameters", -1);
    if (!cursor)
        return th_lerror(state, "Civ6RL parameter query returned null (diagnostic refusal)");
    if (*(uintptr_t*)cursor != parameter_module + 0xb8cc8 ||
        !parameter_slot_is(cursor, 8, 0x4600) ||
        !parameter_slot_is(cursor, 0x20, 0x4e10) ||
        !parameter_slot_is(cursor, 0xf0, 0x4a60)) {
        /* Its release ABI is untrusted too. Stop this disposable worker;
         * never resume or guess a destructor for the returned object. */
        TerminateProcess(GetCurrentProcess(), 78); return 0;
    }
    parameter_cursor = cursor; ++parameter_queries;
    ParameterAdvance advance = (ParameterAdvance)(parameter_module + 0x4e10);
    ParameterString get_string = (ParameterString)(parameter_module + 0x4a60);
    size_t rows = 0;
    while (advance(cursor)) {
        if (++rows > 4096)
            return th_lerror(state, "Civ6RL parameter diagnostic refuses more than 4096 rows");
        const char* key = get_string(cursor, 0);
        if (!key || strnlen(key, 65537) > 65536)
            return th_lerror(state, "Civ6RL parameter diagnostic refuses invalid key");
        LuaStackResult result;
        th_pushstring(state, &result, key);
        parameter_push_value(state, get_string(cursor, 1));
        th_rawset(state, table_index);
        ++parameter_rows;
    }
    parameter_close_cursor();
    return 1;
}

/* GameInfo_Data, EXE 2a18f0..2a2ce1. Native SQL and HKS tables; no Python
 * callbacks may be unwound by Lua. Unresolved types/limits fail explicitly.
 * The diagnostic binding is not yet the GameCore Map Script service. */
static void* gameinfo_cursors[8] = {0};
static size_t gameinfo_queries = 0, gameinfo_releases = 0, gameinfo_rows = 0;
typedef int (__cdecl *GiInt)(void*, int);
typedef int (__cdecl *GiIntName)(void*, const char*);
typedef int (__cdecl *GiCount)(void*);
typedef unsigned char (__cdecl *GiBool)(void*, int);
typedef double (__cdecl *GiReal)(void*, int);
typedef const char* (__cdecl *GiStringName)(void*, const char*);
typedef unsigned char (__cdecl *GiReset)(void*);
typedef unsigned char (__cdecl *GiBindInt)(void*, int, int);
typedef unsigned char (__cdecl *GiBindText)(void*, int, const char*, int);
#define GI_FN(type, rva) ((type)(parameter_module + (rva)))

static void gi_close(void* cursor) {
    for (size_t i = 0; i < 8; ++i) if (gameinfo_cursors[i] == cursor && cursor) {
        GI_FN(ParameterRelease, 0x4600)(cursor);
        gameinfo_cursors[i] = NULL; --gameinfo_active_cursors; ++gameinfo_releases;
        return;
    }
}
static void gi_close_all(void) {
    for (size_t i = 8; i > 0; --i) gi_close(gameinfo_cursors[i-1]);
}
__declspec(dllexport) size_t __cdecl LAB_GameInfoCounter(unsigned int which) {
    switch (which) {
        case 0: return gameinfo_queries;
        case 1: return gameinfo_releases;
        case 2: return gameinfo_rows;
        case 3: return gameinfo_active_cursors;
        default: return (size_t)-1;
    }
}
static void* gi_open(LuaState* state, void* connection, const char* sql, int allow_null) {
    size_t index = 0;
    while (index < 8 && gameinfo_cursors[index]) ++index;
    if (index == 8 || !sql || strnlen(sql, 65537) > 65536) {
        th_lerror(state, "Civ6RL GameInfo query bounds refused"); return NULL;
    }
    void* cursor = GI_FN(ParameterQuery, 0x23a0)(connection, sql, -1);
    if (!cursor) {
        if (!allow_null) th_lerror(state, "Civ6RL GameInfo query returned null");
        return NULL;
    }
    static const size_t slots[][2] = {
        {8,0x4600},{0x20,0x4e10},{0x38,0x4dd0},{0x58,0x40a0},{0x90,0x4350},
        {0xb8,0x4400},{0xc0,0x4410},{0xd0,0x4480},{0xe0,0x4420},{0xe8,0x4a70},
        {0xf0,0x4a60},{0x100,0x46c0},{0x108,0x4940},{0x110,0x4930},{0x130,0x49c0}
    };
    int valid = *(uintptr_t*)cursor == parameter_module + 0xb8cc8;
    for (size_t i = 0; i < sizeof(slots)/sizeof(slots[0]); ++i)
        valid = valid && parameter_slot_is(cursor, slots[i][0], slots[i][1]);
    if (!valid) { TerminateProcess(GetCurrentProcess(), 78); return NULL; }
    gameinfo_cursors[index] = cursor; ++gameinfo_active_cursors; ++gameinfo_queries;
    return cursor;
}
static void* gi_query(LuaState* state, const char* sql) {
    return gi_open(state, parameter_connection, sql, 0);
}
static int gi_next(void* cursor) { return GI_FN(ParameterAdvance, 0x4e10)(cursor) != 0; }
static int gi_int(void* cursor, int col) { return GI_FN(GiInt, 0x4930)(cursor, col); }
static const char* gi_text(void* cursor, int col) {
    return GI_FN(ParameterString, 0x4a60)(cursor, col);
}
static void gi_push_string(LuaState* state, const char* value) {
    if (!value) { th_pushnil(state); return; }
    if (strnlen(value, 65537) > 65536) {
        th_lerror(state, "Civ6RL GameInfo string bound refused"); return;
    }
    LuaStackResult result; th_pushstring(state, &result, value);
}
static void gi_value(LuaState* state, void* cursor, int column) {
    int kind = GI_FN(GiInt, 0x4480)(cursor, column);
    LuaStackResult result;
    switch (kind) {
        case 1: th_number(state, (double)gi_int(cursor, column)); break;
        case 2: th_number(state, GI_FN(GiReal, 0x49c0)(cursor, column)); break;
        case 3: gi_push_string(state, gi_text(cursor, column)); break;
        case 5: th_pushnil(state); break;
        case 6: th_pushbool(state, &result, GI_FN(GiBool, 0x46c0)(cursor, column) != 0); break;
        default: th_lerror(state, "Civ6RL GameInfo unsupported native column type %d", kind);
    }
}
static void gi_identifier_sql(LuaState* state, char* buffer, size_t size,
                              const char* format, const char* name) {
    /* Match the unquoted SQL in the EXE only for safe ordinary identifiers.
     * A name outside this diagnostic scope is not silently escaped/replaced. */
    if (!name || !name[0] || strnlen(name, 257) > 256) {
        th_lerror(state, "Civ6RL GameInfo table name bound refused"); return;
    }
    for (const unsigned char* p = (const unsigned char*)name; *p; ++p)
        if (!((*p >= 'a' && *p <= 'z') || (*p >= 'A' && *p <= 'Z') ||
              (*p >= '0' && *p <= '9') || *p == '_')) {
            th_lerror(state, "Civ6RL GameInfo non-identifier table refused"); return;
        }
    if (snprintf(buffer, size, format, name) < 0) th_lerror(state, "GameInfo SQL formatting failed");
}

static void gi_load_rows(LuaState* state, int all_rows) {
    void* hashes = gi_query(state, "select Hash from Types where Type = ? LIMIT 1");
    void* tables = gi_query(state, "select name from sqlite_master where type = \"table\" and name <> \"NavigationProperties\"");
    int table_count = 0;
    while (gi_next(tables)) {
        if (++table_count > 1024) th_lerror(state, "Civ6RL GameInfo table bound refused");
        int start = th_gettop(state);
        const char* name = gi_text(tables, 0);
        char sql[1024], primary_key[65537] = {0};
        gi_identifier_sql(state, sql, sizeof(sql), "pragma table_info(%s);", name);
        void* metadata = gi_query(state, sql);
        while (gi_next(metadata)) {
            int pk = GI_FN(GiIntName, 0x4940)(metadata, "pk");
            if (pk > 1) { primary_key[0] = 0; break; }
            if (pk == 1) {
                const char* key = GI_FN(GiStringName, 0x4a70)(metadata, "name");
                if (!key || strnlen(key, sizeof(primary_key)) >= sizeof(primary_key))
                    th_lerror(state, "Civ6RL GameInfo primary key bound refused");
                strcpy(primary_key, key);
            }
        }
        gi_close(metadata);
        th_newtable(state, 0, 0); int rows = th_gettop(state);
        gi_identifier_sql(state, sql, sizeof(sql), "SELECT rowid, * FROM %s order by rowid", name);
        void* data = gi_query(state, sql);
        int ordinal = 0;
        while (gi_next(data)) {
            if (ordinal >= 65536) th_lerror(state, "Civ6RL GameInfo row bound refused");
            int columns = GI_FN(GiCount, 0x4400)(data);
            if (columns < 1 || columns > 128) th_lerror(state, "Civ6RL GameInfo column bound refused");
            int row_id = gi_int(data, 0);
            th_newtable(state, 0, columns+4); int row = th_gettop(state);
            th_number(state, row_id); th_setfield(state, row, "RowId");
            th_number(state, ordinal++); th_setfield(state, row, "Index");
            if (primary_key[0]) {
                int pkcol = GI_FN(GiIntName, 0x4420)(data, primary_key);
                if (pkcol >= 0 && GI_FN(GiInt, 0x4480)(data, pkcol) == 3) {
                    const char* value = gi_text(data, pkcol);
                    gi_push_string(state, value); th_setfield(state, row, "PrimaryKey");
                    if (!GI_FN(GiBindText, 0x4350)(hashes, 1, value, -1))
                        th_lerror(state, "Civ6RL GameInfo hash binding failed");
                    if (gi_next(hashes)) { th_number(state, gi_int(hashes, 0)); th_setfield(state, row, "Hash"); }
                    if (!GI_FN(GiReset, 0x4dd0)(hashes))
                        th_lerror(state, "Civ6RL GameInfo hash query reset failed");
                }
            }
            for (int col = 0; col < columns; ++col) {
                gi_push_string(state, GI_FN(ParameterString, 0x4410)(data, col));
                gi_value(state, data, col); th_rawset(state, row);
            }
            th_rawseti(state, rows, row_id); ++gameinfo_rows;
        }
        gi_close(data);
        gi_push_string(state, name); th_pushvalue(state, rows); th_rawset(state, all_rows);
        th_settop(state, start);
    }
    gi_close(tables); gi_close(hashes);
}

static void gi_navigation(LuaState* state, int all_rows) {
    void* nav = gi_query(state, "SELECT BaseTable, PropertyName, TargetTable, IsCollection, Query from NavigationProperties;");
    size_t properties = 0;
    while (gi_next(nav)) {
        if (++properties > 4096) th_lerror(state, "Civ6RL GameInfo navigation bound refused");
        int start = th_gettop(state);
        gi_push_string(state, gi_text(nav, 0)); th_rawget(state, all_rows);
        int base = th_gettop(state); th_checktype(state, base, 5);
        gi_push_string(state, gi_text(nav, 2)); th_rawget(state, all_rows);
        int target = th_gettop(state); th_checktype(state, target, 5);
        const char* property = gi_text(nav, 1);
        if (!property || strnlen(property, 65537) > 65536)
            th_lerror(state, "Civ6RL GameInfo navigation property refused");
        int collection = GI_FN(GiBool, 0x46c0)(nav, 3) != 0;
        void* query = gi_query(state, gi_text(nav, 4));
        th_pushnil(state);
        while (th_next(state, base)) {
            int row = th_gettop(state);
            if (!GI_FN(GiBindInt, 0x40a0)(query, 1, th_checkinteger(state, row-1)))
                th_lerror(state, "Civ6RL GameInfo navigation binding failed");
            if (collection) {
                th_newtable(state, 20, 0); int items = th_gettop(state), index = 0;
                while (gi_next(query)) {
                    if (++index > 65536) th_lerror(state, "Civ6RL GameInfo collection bound refused");
                    th_rawgeti(state, target, gi_int(query, 0)); th_rawseti(state, items, index);
                }
                th_setfield(state, row, property);
            } else if (gi_next(query)) {
                th_rawgeti(state, target, gi_int(query, 0)); th_setfield(state, row, property);
            }
            if (!GI_FN(GiReset, 0x4dd0)(query))
                th_lerror(state, "Civ6RL GameInfo navigation query reset failed");
            th_settop(state, row-1);
        }
        gi_close(query); th_settop(state, start);
    }
    gi_close(nav);
}

static int __cdecl gi_index(LuaState* state) {
    if (th_type(state, 2) == 3) {
        for (int i = 1; i <= 4; ++i) {
            th_pushvalue(state, 2); th_rawget(state, LUA_UPVALUE(i));
            if (th_type(state, -1) != 0) return 1;
            th_settop(state, -2);
        }
        return 0;
    }
    th_pushvalue(state, 2); th_rawget(state, LUA_UPVALUE(3)); return 1;
}
static int __cdecl gi_length(LuaState* state) { th_pushvalue(state, LUA_UPVALUE(1)); return 1; }
static int __cdecl gi_readonly(LuaState* state) {
    return th_lerror(state, "Table is read-only.");
}
static int __cdecl gi_iterate_next(LuaState* state) {
    th_rawgeti(state, LUA_UPVALUE(1), 1);
    if (!th_next(state, LUA_UPVALUE(2))) {
        th_pushnil(state); th_rawseti(state, LUA_UPVALUE(1), 1); return 0;
    }
    th_pushvalue(state, -2); th_rawseti(state, LUA_UPVALUE(1), 1); return 1;
}
static int __cdecl gi_iterate(LuaState* state) {
    th_newtable(state, 1, 0); th_pushvalue(state, LUA_UPVALUE(1));
    th_closure(state, gi_iterate_next, 2, "lGameInfo_IterateTableAux", 0); return 1;
}
static void gi_public_tables(LuaState* state, int all_rows, int backend) {
    th_pushnil(state);
    while (th_next(state, all_rows)) {
        int rows = th_gettop(state);
        th_newuserdata(state, 4); int proxy = th_gettop(state);
        th_newtable(state, 0, 4); int meta = th_gettop(state), count = 0;
        th_pushnil(state);
        while (th_next(state, rows)) { ++count; th_settop(state, -2); }
        th_number(state, count); th_closure(state, gi_length, 1, "lGameInfo_ReturnValue", 0);
        th_setfield(state, meta, "__len");
        th_closure(state, gi_readonly, 0, "lGameInfo_ErrorReadOnly", 0);
        th_setfield(state, meta, "__newindex");
        th_pushvalue(state, rows); th_closure(state, gi_iterate, 1, "lGameInfo_IterateTable", 0);
        th_setfield(state, meta, "__call");
        for (int i = 0; i < 4; ++i) th_newtable(state, 0, 0);
        int maps = th_gettop(state)-3;
        th_pushnil(state);
        while (th_next(state, rows)) {
            int row = th_gettop(state);
            th_pushvalue(state, row-1); th_pushvalue(state, row); th_rawset(state, maps+3);
            static const char* fields[3] = {"Hash", "Index", "PrimaryKey"};
            for (int i = 0; i < 3; ++i) {
                th_getfield(state, row, fields[i]);
                if (th_type(state, -1) != 0) { th_pushvalue(state, row); th_rawset(state, maps+i); }
                else th_settop(state, -2);
            }
            th_settop(state, row-1);
        }
        th_closure(state, gi_index, 4, "lGameInfo_IndexTable", 0);
        th_setfield(state, meta, "__index"); th_setmeta(state, proxy);
        th_pushvalue(state, rows-1); th_pushvalue(state, proxy); th_settable(state, backend);
        th_settop(state, rows-1);
    }
}
static int __cdecl namespace_create_gameinfo(LuaState* state) {
    if (!parameter_connection) return th_lerror(state, "Civ6RL GameInfo database service is not bound");
    th_getfield(state, LUA_GLOBALS, "GameInfo_Data");
    if (th_type(state, -1) == 0) {
        th_settop(state, -2); th_newtable(state, 0, 0);
        th_pushvalue(state, -1); th_setfield(state, LUA_GLOBALS, "GameInfo_Data");
    }
    if (th_type(state, -1) != 5) return th_lerror(state, "Civ6RL GameInfo non-table data cache refused");
    int backend = th_gettop(state);
    th_newtable(state, 0, 300); int all_rows = th_gettop(state);
    gi_load_rows(state, all_rows);
    gi_navigation(state, all_rows);
    gi_public_tables(state, all_rows, backend);
    th_settop(state, backend); return 1;
}

/* EXE 2a31b0, 2a0ca0..2a18b8. DB.Query materializes rows eagerly.
 * The connections below are borrowed from the Python diagnostic owner;
 * these bindings do not yet replace the EXE's database singleton services. */
static int db_configuration_baseline_known = 0;
__declspec(dllexport) int __cdecl LAB_DBConfigurationBind(LuaState* root, void* module,
                                                        void* connection, int32_t baseline) {
    if (!root || root != thread_registry_root || parameter_cursor || gameinfo_active_cursors) return -1000;
    if (!module && !connection) {
        db_configuration_connection = NULL; db_configuration_base = 0;
        db_configuration_baseline_known = 0; return 0;
    }
    if (!connection || !parameter_connection || (uintptr_t)module != parameter_module ||
        db_configuration_connection) return -1500;
    if (*(uintptr_t*)connection != parameter_module + 0xb8578 ||
        !parameter_slot_is(connection, 8, 0x1a80) ||
        !parameter_slot_is(connection, 0x18, 0x23a0) ||
        !parameter_slot_is(connection, 0x30, 0x2950) ||
        !parameter_slot_is(connection, 0x50, 0x23f0) ||
        !parameter_slot_is(connection, 0x58, 0x24a0)) return -1201;
    db_configuration_connection = connection; db_configuration_base = baseline;
    db_configuration_baseline_known = 1;
    return 0;
}
__declspec(dllexport) int __cdecl LAB_DBConfigurationBorrow(LuaState* root, void* module,
                                                          void* connection) {
    int status = LAB_DBConfigurationBind(root, module, connection, 0);
    if (!status) db_configuration_baseline_known = 0;
    return status;
}
static void* db_connection(LuaState* state, int configuration) {
    void* connection = configuration ? db_configuration_connection : parameter_connection;
    if (!connection) th_lerror(state, "Civ6RL DB database service is not bound");
    return connection;
}
static int __cdecl db_query_inner(LuaState* state) {
    int configuration = th_checkinteger(state, LUA_UPVALUE(1));
    const char* sql = th_checkstring(state, 1, NULL);
    int nargs = th_gettop(state);
    void* cursor = gi_open(state, db_connection(state, configuration), sql, 1);
    if (!cursor) return 0; /* The EXE returns zero values for failed preparation. */
    for (int arg = 2; arg <= nargs; ++arg) {
        int kind = th_type(state, arg), index = arg - 1;
        switch (kind) {
            case -1: case 0: break; /* nil is deliberately not bound. */
            case 1:
                GI_FN(GiBindInt, 0x40a0)(cursor, index, th_toboolean(state, arg) != 0); break;
            case 3: {
                typedef unsigned char (__cdecl *BindReal)(void*, int, double);
                if (!parameter_slot_is(cursor, 0x60, 0x40f0)) gameplay_abi_refused();
                GI_FN(BindReal, 0x40f0)(cursor, index, th_checknumber(state, arg)); break;
            }
            case 4:
                GI_FN(GiBindText, 0x4350)(cursor, index, th_checkstring(state, arg, NULL), -1); break;
            default: return th_argerror(state, arg, "Invalid argument for database query.");
        }
        /* Native callers ignore the bind status, including surplus arguments. */
    }
    th_newtable(state, 0, 0); int output = th_gettop(state), ordinal = 0;
    while (gi_next(cursor)) {
        if (++ordinal > 65536) return th_lerror(state, "Civ6RL DB row bound refused");
        int columns = GI_FN(GiCount, 0x4400)(cursor);
        if (columns < 0 || columns > 128) return th_lerror(state, "Civ6RL DB column bound refused");
        th_newtable(state, 0, columns); int row = th_gettop(state);
        for (int col = 0; col < columns; ++col) {
            gi_push_string(state, GI_FN(ParameterString, 0x4410)(cursor, col));
            int kind = GI_FN(GiInt, 0x4480)(cursor, col);
            if (kind == 1 || kind == 2 || kind == 3 || kind == 6) gi_value(state, cursor, col);
            else th_pushnil(state); /* Native DB handles BLOB/NULL as nil. */
            th_rawset(state, row);
        }
        th_rawseti(state, output, ordinal);
    }
    gi_close(cursor); return 1;
}
static int db_query_protected(LuaState* state, int configuration) {
    if (parameter_cursor || gameinfo_active_cursors)
        return th_lerror(state, "Civ6RL DB reentrant query refused");
    int nargs = th_gettop(state);
    if (nargs > 128) return th_lerror(state, "Civ6RL DB argument bound refused");
    th_checkstack(state, nargs + 2, "Civ6RL DB protected query stack");
    th_number(state, configuration);
    th_closure(state, db_query_inner, 1, "DB.Query protected body", 0);
    for (int arg = 1; arg <= nargs; ++arg) th_pushvalue(state, arg);
    int status = th_pcall(state, nargs, -1, 0);
    /* Keep Lua longjmp entirely inside C and release cursors after any error. */
    gi_close_all();
    if (status) return th_error(state);
    return th_gettop(state) - nargs;
}
static int __cdecl db_query(LuaState* state) { return db_query_protected(state, 0); }
static int __cdecl db_configuration_query(LuaState* state) { return db_query_protected(state, 1); }
static int db_query_count(LuaState* state, int configuration) {
    void* connection = db_connection(state, configuration);
    if (!parameter_slot_is(connection, 0x50, 0x23f0)) gameplay_abi_refused();
    th_number(state, (double)GI_FN(GiCount, 0x23f0)(connection)); return 1;
}
static int __cdecl db_count(LuaState* state) { return db_query_count(state, 0); }
static int __cdecl db_configuration_count(LuaState* state) { return db_query_count(state, 1); }
static int db_query_sql(LuaState* state, int configuration) {
    int index = th_checkinteger(state, 1);
    void* connection = db_connection(state, configuration);
    if (!parameter_slot_is(connection, 0x58, 0x24a0)) gameplay_abi_refused();
    gi_push_string(state, GI_FN(ParameterString, 0x24a0)(connection, index)); return 1;
}
static int __cdecl db_sql(LuaState* state) { return db_query_sql(state, 0); }
static int __cdecl db_configuration_sql(LuaState* state) { return db_query_sql(state, 1); }
static int __cdecl db_configuration_changes(LuaState* state) {
    if (!db_configuration_connection) return 0;
    if (!db_configuration_baseline_known)
        return th_lerror(state, "Civ6RL unresolved configuration change baseline");
    if (!parameter_slot_is(db_configuration_connection, 0x30, 0x2950)) gameplay_abi_refused();
    /* Diagnostic baseline is explicit. Its live EXE lifecycle is unresolved. */
    uint32_t changes = (uint32_t)GI_FN(GiCount, 0x2950)(db_configuration_connection);
    th_number(state, (double)(int32_t)(changes + (uint32_t)db_configuration_base)); return 1;
}
static int __cdecl db_hash(LuaState* state) {
    const unsigned char* text = (const unsigned char*)th_checkstring(state, 1, NULL);
    size_t length = strnlen((const char*)text, 65537);
    if (length > 65536) return th_lerror(state, "Civ6RL DB hash string bound refused");
    uint32_t hash = UINT32_MAX;
    for (size_t i = 0; i < length; ++i) {
        hash ^= text[i];
        for (int bit = 0; bit < 8; ++bit) hash = (hash >> 1) ^ ((hash & 1) ? 0xedb88320u : 0);
    }
    th_number(state, (double)(int32_t)hash); return 1;
}
static int __cdecl db_memory_usage(LuaState* state) {
    return th_lerror(state, "GetMemoryUsage has not been migrated over, yet.");
}
static int __cdecl db_collect_memory_usage(LuaState* state) {
    return th_lerror(state, "CollectMemoryUsage has not been migrated over, yet.");
}
static int __cdecl namespace_create_db(LuaState* state) {
    static const struct { const char* name; LuaCallback function; } methods[] = {
        {"GetMemoryUsage",db_memory_usage},{"CollectMemoryUsage",db_collect_memory_usage},
        {"QueryCount",db_count},{"ConfigurationQueryCount",db_configuration_count},
        {"QuerySQL",db_sql},{"ConfigurationQuerySQL",db_configuration_sql},
        {"Query",db_query},{"ConfigurationQuery",db_configuration_query},
        {"ConfigurationChanges",db_configuration_changes},{"MakeHash",db_hash}
    };
    th_newtable(state, 0, 10);
    for (size_t i = 0; i < sizeof(methods)/sizeof(methods[0]); ++i) {
        th_closure(state, methods[i].function, 0, methods[i].name, 0);
        th_setfield(state, -2, methods[i].name);
    }
    return 1;
}

#include "script_locale.inc"

static int __cdecl namespace_register_callback(LuaState* state) {
    NamespaceRequest* request = (NamespaceRequest*)th_userdata(state, 1);
    th_getfield(state, LUA_GLOBALS, "Threads");
    if (th_type(state, -1) != 5)
        return th_lerror(state, "Civ6RL namespace registry is not a table");
    th_pushnil(state);
    int found = 0;
    while (th_next(state, 2)) {
        if (th_tothread(state, -2) == request->child) { found = 1; break; }
        th_settop(state, -2);
    }
    if (!found || th_type(state, -1) != 5)
        return th_lerror(state, "Civ6RL namespace child environment missing from registry");
    th_remove(state, 2); /* userdata, thread, environment */
    th_getfield(state, LUA_GLOBALS, request->name);
    if (th_type(state, -1) == 0) {
        th_settop(state, -2);
        th_closure(state, request->create, 0, "pData->createFunc", 0);
        th_call(state, 0, 1);
        th_pushvalue(state, -1);
        th_setfield(state, LUA_GLOBALS, request->name);
    }
    /* Every attachment makes a fresh shallow proxy. The root backend remains
     * shared. rawset can still shadow proxy fields, as in the source. */
    LuaStackResult result;
    th_newtable(state, 0, 0);
    th_newtable(state, 0, 0);
    th_pushvalue(state, -3);
    th_setfield(state, -2, "__index");
    th_pushbool(state, &result, 0);
    th_setfield(state, -2, "__metatable");
    th_closure(state, namespace_readonly_error, 0, "lReadOnlyError", 0);
    th_setfield(state, -2, "__newindex");
    th_setmeta(state, -2);
    th_remove(state, -2); /* replace backend by its proxy */
    th_setfield(state, -2, request->name);
    return 0;
}

__declspec(dllexport) int __cdecl LAB_NamespaceRegister(LuaState* state, LuaState* child,
                                                      unsigned int namespace_id) {
    if (!state || state != thread_registry_root || !child || state == child) return -1000;
    size_t slot = 0;
    while (slot < 64 && host_threads[slot] != child) ++slot;
    if (slot == 64) return -1003;
    if (namespace_id < 1 || namespace_id > 6) return -1100;
    if (parameter_cursor || gameinfo_active_cursors) return -1202;
    NamespaceRequest request = namespace_id == 1
        ? (NamespaceRequest){child, "Path", namespace_create_path}
        : namespace_id == 2 ? (NamespaceRequest){child, "GlobalParameters", namespace_create_parameters}
        : namespace_id == 3 ? (NamespaceRequest){child, "GameInfo", namespace_create_gameinfo}
        : namespace_id == 4 ? (NamespaceRequest){child, "DB", namespace_create_db}
        : namespace_id == 5 ? (NamespaceRequest){child, "Locale", namespace_create_locale}
        : (NamespaceRequest){child, "Achievements", namespace_create_achievements};
    int status = th_cpcall(state, namespace_register_callback, &request);
    /* A Lua longjmp may leave the query open. Release in this outer C frame,
     * after Havok has caught it, before Python can release the connection. */
    parameter_close_cursor();
    gi_close_all();
    return status;
}

#include "script_execution.inc"
#include "script_aux_a0.inc"
#include "script_aux_a8.inc"
#include "script_events.inc"
#include "script_aux_events.inc"
#include "script_game_events.inc"
#include "script_game_event_dispatch.inc"
#include "script_libraries.inc"
#include "script_ui_attach.inc"
#include "script_core_bindings.inc"
#include "script_include.inc"

/* The EXE writer +10/+20 methods are variadic. ctypes callbacks cannot
 * capture Win64 varargs: retain that ABI in C and call Python only with a
 * fixed signature. The two callbacks are owned by each adapter writer.
 * Gate runs before touching the text, including for disabled channels.
 */
typedef int (__cdecl *LogGate)(void*, const char*, unsigned int);
typedef void (__cdecl *LogSink)(void*, const char*, size_t, unsigned int);
typedef struct AdapterLogWriter {
    void** vtable;
    LogGate gate;
    LogSink sink;
} AdapterLogWriter;

__declspec(noreturn) static void unsupported_log(const char* reason) {
    fprintf(stdout, "{\"stage\":\"unsupported_log_bridge\",\"reason\":\"%s\"}\n", reason);
    fflush(stdout);
    TerminateProcess(GetCurrentProcess(), 78);
    ExitProcess(78);
}

/* Bounded diagnostics stop explicitly instead of truncating output. The
 * proven subset is literal text, %% and bare %d/%i/%s, plus exact %3.1f from
 * City_BuildQueue (native-city-production-printf.json). Broaden it
 * only with caller/formatter evidence; it must never swallow a conversion.
 */
static size_t checked_log_text(const char* text, int format) {
    size_t length = 0;
    __try {
        for (; length < 65536 && text[length]; ++length) {
            if (format && text[length] == '%') {
                ++length;
                if (length >= 65536) unsupported_log("log text exceeds diagnostic limit");
                if (text[length] == '%' || text[length] == 'd' || text[length] == 'i' || text[length] == 's') continue;
                if (length <= 65532 && text[length] == '3' && text[length+1] == '.' &&
                    text[length+2] == '1' && text[length+3] == 'f') {
                    length += 3;
                    continue;
                }
                unsupported_log("unverified printf conversion");
            }
        }
    } __except(EXCEPTION_EXECUTE_HANDLER) {
        unsupported_log("unreadable log text");
    }
    if (length >= 65536) unsupported_log("log text exceeds diagnostic limit");
    return length;
}

static void checked_log_arguments(const char* format, va_list args) {
    /* Core23C80D supplies the narrow Player_Stats name in R9 and integers in
     * the rest of the Win64 variadic area. Validate every admitted %s before
     * either CRT pass; unrelated conversions remain explicitly unsupported.
     * Source: native-player-stats-printf.json and phase31-log-runtime.json.
     * Bare %i is also signed int: native-setup-printf.json, Core17DEEC. */
    va_list check_args;
    va_copy(check_args, args);
    __try {
        for (size_t i = 0; format[i]; ++i) {
            if (format[i] != '%') continue;
            ++i;
            if (format[i] == 'd' || format[i] == 'i') (void)va_arg(check_args, int);
            else if (format[i] == '3' && format[i+1] == '.' && format[i+2] == '1' && format[i+3] == 'f') {
                /* Core B7B6F..79 promotes all three floats to doubles before
                 * stack stores B7B80/B7B9D/B7BA8. The CRT keeps native format. */
                (void)va_arg(check_args, double);
                i += 3;
            }
            else if (format[i] == 's') {
                const char* value = va_arg(check_args, const char*);
                /* The original getters may pass NULL for a missing name.
                 * Keep that exact argument for the CRT's documented (null)
                 * formatting. A nonnull unreadable string still aborts. */
                if (value) checked_log_text(value, 0);
            }
        }
    } __except(EXCEPTION_EXECUTE_HANDLER) {
        unsupported_log("unreadable variadic log argument");
    }
    va_end(check_args);
}

static void format_log(AdapterLogWriter* writer, const char* format,
                       va_list args, unsigned int slot) {
    if (!writer->gate(writer, format, slot)) return;
    checked_log_text(format, 1);
    checked_log_arguments(format, args);
    va_list count_args, write_args;
    va_copy(count_args, args);
    int length = _vscprintf(format, count_args);
    va_end(count_args);
    if (length < 0 || length > 1048576)
        unsupported_log("formatted log exceeds diagnostic limit");
    char* buffer = (char*)malloc((size_t)length + 1);
    if (!buffer) unsupported_log("log allocation failed");
    va_copy(write_args, args);
    int actual = vsnprintf(buffer, (size_t)length + 1, format, write_args);
    va_end(write_args);
    if (actual != length) unsupported_log("log formatting length mismatch");
    writer->sink(writer, buffer, (size_t)length, slot);
    free(buffer);
}

__declspec(dllexport) void __cdecl LAB_LogPrintf10(AdapterLogWriter* writer, const char* format, ...) {
    va_list args;
    va_start(args, format);
    format_log(writer, format, args, 0x10);
    va_end(args);
}
__declspec(dllexport) void __cdecl LAB_LogPrintf20(AdapterLogWriter* writer, const char* format, ...) {
    va_list args;
    va_start(args, format);
    format_log(writer, format, args, 0x20);
    va_end(args);
}
__declspec(dllexport) void __cdecl LAB_LogText18(AdapterLogWriter* writer, const char* text) {
    if (!writer->gate(writer, text, 0x18)) return;
    size_t length = checked_log_text(text, 0);
    writer->sink(writer, text, length, 0x18);
}

/* GameCore 73a1b0 obtains this sentinel; 739d80/739e60 test pointer identity
 * before freeing. Length/capacity are read at data-4/data-8, respectively.
 * EXE storage evidence is recorded separately in the phase22 source index.
 */
typedef struct EmptyBasicString {
    uint32_t capacity;
    uint32_t length;
    char data[8];
} EmptyBasicString;
static EmptyBasicString empty_basic_string = {0, 0, {0}};
typedef char assert_data_offset_is_eight[(offsetof(EmptyBasicString, data) == 8) ? 1 : -1];

/* EXE 985550/9857b0 use a process-local table of 64 records with one-based
 * handles. Storage here belongs to this host; it is never an EXE address.
 * Native callbacks execute in the explicit serial diagnostic profile below.
 */
typedef struct JobListSlot {
    void* head;
    void** tail;
    struct JobListSlot* next;
    unsigned char occupied;
    unsigned char padding[7];
} JobListSlot;
typedef char assert_job_slot_size[(sizeof(JobListSlot) == 32) ? 1 : -1];
typedef char assert_job_slot_link[(offsetof(JobListSlot, next) == 16) ? 1 : -1];
typedef char assert_job_slot_occupied[(offsetof(JobListSlot, occupied) == 24) ? 1 : -1];
static JobListSlot job_slots[64];
static JobListSlot* free_job_slots = NULL;
static JobListSlot* active_job_slots = NULL;
static SRWLOCK job_registry_lock = SRWLOCK_INIT;
static DWORD job_runtime_thread=0;
static volatile LONG job_spawn_active=0;

/* The TBB wrapper and group are private to the executable. The Core shares
 * only the job's wrapper/set pointers and its two-word set handle. This
 * diagnostic queue owns pending storage and follows explicit Core Spawn calls;
 * it does not claim equivalent TBB concurrency or timing. */
typedef struct DiagnosticJobNode {
    struct DiagnosticJobNode* next;
    void* job;
    uintptr_t* job_set;
    uintptr_t descriptor[2];
    uintptr_t execute;
    uint64_t sequence;
} DiagnosticJobNode;
typedef struct DiagnosticJobGroup {
    struct DiagnosticJobGroup* next;
    uint64_t magic;
    uintptr_t* owner;
    size_t pending;
} DiagnosticJobGroup;
#define DIAGNOSTIC_JOB_MAGIC UINT64_C(0x434956364A4F4231)
static DiagnosticJobGroup* owned_job_groups=NULL;
static uint64_t job_submission_sequence=0;
static DiagnosticJobGroup* find_owned_job_group(uintptr_t address, uintptr_t owner) {
    for(DiagnosticJobGroup* group=owned_job_groups;group;group=group->next)
        if((uintptr_t)group==address && (uintptr_t)group->owner==owner &&
           group->magic==DIAGNOSTIC_JOB_MAGIC) return group;
    return NULL;
}
static int native_job_address_is(uintptr_t address,uintptr_t core,int executable) {
    MEMORY_BASIC_INFORMATION info={0};
    if(!address || !core || !VirtualQuery((void*)address,&info,sizeof(info)) ||
       (uintptr_t)info.AllocationBase!=core || info.Type!=MEM_IMAGE ||
       info.State!=MEM_COMMIT || info.Protect&(PAGE_GUARD|PAGE_NOACCESS)) return 0;
    DWORD protection=info.Protect&0xFF;
    return executable ? (protection==PAGE_EXECUTE || protection==PAGE_EXECUTE_READ ||
                          protection==PAGE_EXECUTE_READWRITE || protection==PAGE_EXECUTE_WRITECOPY)
                      : (protection==PAGE_READONLY || protection==PAGE_WRITECOPY);
}

/* EXE CRT initializer 0241a0..024221 clears all 64 slots, assigns tail=&head,
 * chains slot 0 through slot 63 in ascending order, then assigns free_head to
 * slot 0. It is a leaf outside .pdata. Run once before embedded Python starts;
 * never reset a live registry and never emit an unsolicited startup event.
 */
static void initialize_job_registry(void) {
    job_runtime_thread=GetCurrentThreadId();
    for (size_t i = 0; i < 64; ++i) {
        job_slots[i].head = NULL;
        job_slots[i].tail = &job_slots[i].head;
        job_slots[i].occupied = 0;
        job_slots[i].next = i + 1 < 64 ? &job_slots[i + 1] : NULL;
    }
    free_job_slots = &job_slots[0];
    active_job_slots = NULL;
}

__declspec(noreturn) static void unsupported_job_export(const char* name, const char* reason) {
    fprintf(stdout, "{\"stage\":\"unsupported_executable_export\","
            "\"export\":\"%s\",\"implemented\":false,\"reason\":\"%s\"}\n", name, reason);
    fflush(stdout);
    TerminateProcess(GetCurrentProcess(), 78);
    ExitProcess(78);
}

/* Core7380a0 resolves this getter, calls it, then tail-calls its returned
 * function with name/payload/uint32 arguments. EXE98a030 returns the default
 * callback9899b0 (image data1284988). Its active stream path is NOT yet
 * implemented: return an explicit diagnostic guard, never a silent no-op.
 * The default callback's NULL-name early return is source-backed.
 */
static void __cdecl guarded_log_event(const void* name, const void* payload, uint32_t size) {
    if (!name) return;
    void* caller = _ReturnAddress();
    HMODULE module = NULL;
    GetModuleHandleExW(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS |
                     GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT,
                     (LPCWSTR)caller, &module);
    fprintf(stdout, "{\"stage\":\"native_log_event_request\","
            "\"name_pointer\":%llu,\"payload_pointer\":%llu,\"size_argument\":%u,"
            "\"caller_module_base\":%llu,\"caller_rva\":%llu,\"input_dereferenced\":false}\n",
            (unsigned long long)(uintptr_t)name,(unsigned long long)(uintptr_t)payload,size,
            (unsigned long long)(uintptr_t)module,
            (unsigned long long)((uintptr_t)caller-(uintptr_t)module));
    fflush(stdout);
    unsupported_job_export("EXP_GetLogEventCallback callback", "active event stream not implemented");
}
typedef void (__cdecl *LogEventCallback)(const void*, const void*, uint32_t);
static LogEventCallback log_event_callback = guarded_log_event;
static SRWLOCK log_event_callback_lock = SRWLOCK_INIT;
__declspec(dllexport) LogEventCallback __cdecl EXP_GetLogEventCallback(void) {
    AcquireSRWLockExclusive(&log_event_callback_lock);
    LogEventCallback callback = log_event_callback;
    ReleaseSRWLockExclusive(&log_event_callback_lock);
    return callback;
}
/* EXE98a0a0: NULL resets the default, otherwise retain the supplied callback.
 * The callback is invoked by the caller after the getter releases its lock.
 * The host's default remains fail-closed until Python installs its recorder.
 */
__declspec(dllexport) void __cdecl EXP_SetLogEventCallback(LogEventCallback callback) {
    AcquireSRWLockExclusive(&log_event_callback_lock);
    log_event_callback = callback ? callback : guarded_log_event;
    ReleaseSRWLockExclusive(&log_event_callback_lock);
}

__declspec(dllexport) const char* __cdecl EXP_GetEmptyBasicString(void) {
    return empty_basic_string.data;
}

/* EXE 985e20 reads only job_set+8. If NULL it returns without writing any
 * fields and without using its caller's extra argument. Implement only this
 * empty wait path plus completed owned groups. Pending work is never marked
 * complete by Wait; it must have returned from the real native callback.
 */
__declspec(dllexport) void __cdecl EXP_JobManager_Wait(uintptr_t job_set) {
    uintptr_t second = 0;
    int readable = 0;
    __try {
        second = ((volatile uintptr_t*)job_set)[1];
        readable = 1;
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        readable = 0;
    }
    if (readable && !second) {
        fprintf(stdout, "{\"stage\":\"empty_job_set_waited\","
                "\"export\":\"EXP_JobManager_Wait\","
                "\"first_argument_raw\":%llu,\"member8\":0,"
                "\"contract\":\"null_second_member_only\"}\n",
                (unsigned long long)job_set);
        fflush(stdout);
        return;
    }
    if (readable) {
        if(GetCurrentThreadId()!=job_runtime_thread || job_spawn_active)
            unsupported_job_export("EXP_JobManager_Wait", "unsupported concurrent or recursive job wait");
        AcquireSRWLockExclusive(&job_registry_lock);
        DiagnosticJobGroup* group=find_owned_job_group(second,job_set);
        if (group && !group->pending && ((uintptr_t*)job_set)[0]==second) {
            ((uintptr_t*)job_set)[1]=0;
            ReleaseSRWLockExclusive(&job_registry_lock);
            fputs("{\"stage\":\"native_job_set_wait_completed\",\"pending_jobs\":0,"
                  "\"profile\":\"diagnostic_serial_native_callbacks\"}\n",stdout);
            fflush(stdout);
            return;
        }
        ReleaseSRWLockExclusive(&job_registry_lock);
    }
    fprintf(stdout, "{\"stage\":\"unsupported_executable_export\","
            "\"export\":\"EXP_JobManager_Wait\","
            "\"first_argument_raw\":%llu,\"member8_readable\":%s,"
            "\"member8\":%llu,\"implemented\":false}\n",
            (unsigned long long)job_set, readable ? "true" : "false",
            (unsigned long long)second);
    fflush(stdout);
    TerminateProcess(GetCurrentProcess(), 78);
    ExitProcess(78);
}

/* EXE 986050 -> 9857b0 computes uint32(handle-1) BEFORE its range test, so
 * high-bit aliases are preserved. Invalid/inactive IDs are no-ops. We serialize
 * the occupied check too; racing duplicate frees of one handle are outside the
 * verified ownership contract. Distinct owned handles may be used concurrently.
 */
__declspec(dllexport) void __cdecl EXP_JobManager_FreeJobList(uintptr_t handle) {
    if(job_spawn_active)
        unsupported_job_export("EXP_JobManager_FreeJobList", "free during native job execution");
    if (!handle) {
        fputs("{\"stage\":\"null_job_list_freed\","
              "\"export\":\"EXP_JobManager_FreeJobList\","
              "\"handle\":0,\"contract\":\"zero_handle_only\"}\n", stdout);
        fflush(stdout);
        return;
    }
    uint32_t index = (uint32_t)(handle - 1);
    const char* ignored = NULL;
    AcquireSRWLockExclusive(&job_registry_lock);
    if (index >= 64) {
        ignored = "out_of_range";
    } else if (!job_slots[index].occupied) {
        ignored = "inactive";
    } else {
        JobListSlot* slot = &job_slots[index];
        if (slot->head) {
            ReleaseSRWLockExclusive(&job_registry_lock);
            unsupported_job_export("EXP_JobManager_FreeJobList", "queued jobs require scheduler");
        }
        JobListSlot** link = &active_job_slots;
        while (*link && *link != slot) link = &(*link)->next;
        if (*link == slot) *link = slot->next;
        slot->occupied = 0;
        slot->head = NULL;
        slot->tail = &slot->head;
        slot->next = free_job_slots;
        free_job_slots = slot;
    }
    ReleaseSRWLockExclusive(&job_registry_lock);
    if (ignored) {
        fprintf(stdout, "{\"stage\":\"job_list_free_ignored\","
                "\"export\":\"EXP_JobManager_FreeJobList\",\"handle\":%llu,\"reason\":\"%s\"}\n",
                (unsigned long long)handle, ignored);
    } else {
        fprintf(stdout, "{\"stage\":\"job_list_freed\","
                "\"export\":\"EXP_JobManager_FreeJobList\",\"handle\":%llu,"
                "\"canonical_handle\":%u,\"queued_jobs\":0}\n", (unsigned long long)handle, index + 1);
    }
    fflush(stdout);
}

/* Source-backed pop of the free list, push onto active list and slot index.
 * Exhaustion returns zero exactly as EXE 985550. No jobs are executed here.
 */
__declspec(dllexport) uintptr_t __cdecl EXP_JobManager_CreateJobList(void) {
    uintptr_t handle = 0;
    AcquireSRWLockExclusive(&job_registry_lock);
    JobListSlot* slot = free_job_slots;
    if (slot) {
        free_job_slots = slot->next;
        slot->occupied = 1;
        slot->next = active_job_slots;
        active_job_slots = slot;
        handle = (uintptr_t)(slot - job_slots) + 1;
    }
    ReleaseSRWLockExclusive(&job_registry_lock);
    fprintf(stdout, "{\"stage\":\"job_list_created\","
            "\"export\":\"EXP_JobManager_CreateJobList\",\"handle\":%llu}\n",
            (unsigned long long)handle);
    fflush(stdout);
    return handle;
}

/* Source985B20 queues, 985BF0 submits and 985EC0 invokes the job's vtable+8.
 * The direct AddJob path is still unsupported. Queue/Spawn execute Core jobs
 * only, preserving their shared fields in an explicit serial diagnostic host.
 */
__declspec(dllexport) __declspec(noreturn) void __cdecl EXP_JobManager_AddJob(void) {
    unsupported_job_export("EXP_JobManager_AddJob", "job submission not implemented");
}
__declspec(dllexport) void __cdecl EXP_JobManager_PushJobOntoList(
        uintptr_t handle, void* job, void* job_set, const void* descriptor) {
    if(GetCurrentThreadId()!=job_runtime_thread || job_spawn_active)
        unsupported_job_export("EXP_JobManager_PushJobOntoList", "unsupported concurrent or recursive job submission");
    /* Source985B20 and Core7389D0 establish all four fixed arguments. This
     * diagnostic observes them before the explicit refusal; it runs no job. */
    uintptr_t values[5]={0}, table[2]={0}, set_values[2]={0}, desc[2]={0};
    int readable=0;
    __try {
        memcpy(values,job,sizeof(values));
        memcpy(table,(const void*)values[0],sizeof(table));
        memcpy(set_values,job_set,sizeof(set_values));
        memcpy(desc,descriptor,sizeof(desc));
        readable=1;
    } __except(EXCEPTION_EXECUTE_HANDLER) { readable=0; }
    fprintf(stdout,"{\"stage\":\"native_job_submission_observed\",\"handle\":%llu,"
            "\"job\":%llu,\"job_set\":%llu,\"readable\":%s,\"job_words\":[%llu,%llu,%llu,%llu,%llu],"
            "\"vtable_slots\":[%llu,%llu],\"set_words\":[%llu,%llu],\"descriptor_words\":[%llu,%llu],"
            "\"executed\":false}\n",(unsigned long long)handle,
            (unsigned long long)(uintptr_t)job,(unsigned long long)(uintptr_t)job_set,
            readable?"true":"false",(unsigned long long)values[0],(unsigned long long)values[1],
            (unsigned long long)values[2],(unsigned long long)values[3],(unsigned long long)values[4],
            (unsigned long long)table[0],(unsigned long long)table[1],
            (unsigned long long)set_values[0],(unsigned long long)set_values[1],
            (unsigned long long)desc[0],(unsigned long long)desc[1]);
    fflush(stdout);
    /* Probe loader verifies the DLL hash. EXE985EC0's common job interface
     * invokes vtable+8(this,worker_index), irrespective of concrete subclass.
     * Validate the native vtable/function image ownership; never translate
     * the task body. Source985B20 queues without executing. */
    uintptr_t core=(uintptr_t)GetModuleHandleW(L"GameCore_Base_FinalRelease.dll");
    if (!readable || !core || !native_job_address_is(values[0],core,0) ||
        !native_job_address_is(table[0],core,1) || !native_job_address_is(table[1],core,1) ||
        values[1] || values[2] || !native_job_address_is(desc[0],core,0) ||
        desc[1] != UINT64_C(0x1F00000000))
        unsupported_job_export("EXP_JobManager_PushJobOntoList", "unverified native job contract");
    uint32_t index=(uint32_t)(handle-1);
    AcquireSRWLockExclusive(&job_registry_lock);
    if (index >= 64 || !job_slots[index].occupied) {
        ReleaseSRWLockExclusive(&job_registry_lock);
        unsupported_job_export("EXP_JobManager_PushJobOntoList", "inactive job list");
    }
    DiagnosticJobGroup* group=find_owned_job_group(set_values[0],(uintptr_t)job_set);
    if ((set_values[0] && !group) || (set_values[1] && set_values[1]!=set_values[0])) {
        ReleaseSRWLockExclusive(&job_registry_lock);
        unsupported_job_export("EXP_JobManager_PushJobOntoList", "nonempty job set ownership unverified");
    }
    if(!group) {
        group=(DiagnosticJobGroup*)calloc(1,sizeof(*group));
        if(group) {
            group->magic=DIAGNOSTIC_JOB_MAGIC;
            group->owner=(uintptr_t*)job_set;
            group->next=owned_job_groups;
            owned_job_groups=group;
        }
    }
    DiagnosticJobNode* node=(DiagnosticJobNode*)calloc(1,sizeof(*node));
    if (!group || !node) {
        ReleaseSRWLockExclusive(&job_registry_lock);
        unsupported_job_export("EXP_JobManager_PushJobOntoList", "job queue allocation failed");
    }
    group->pending++;
    node->job=job;
    node->execute=table[1];
    node->sequence=++job_submission_sequence;
    node->job_set=(uintptr_t*)job_set;
    memcpy(node->descriptor,desc,sizeof(desc));
    int stored=0;
    __try {
        ((uintptr_t*)job_set)[0]=(uintptr_t)group;
        ((uintptr_t*)job_set)[1]=(uintptr_t)group;
        ((uintptr_t*)job)[1]=(uintptr_t)node;
        ((uintptr_t*)job)[2]=(uintptr_t)job_set;
        memcpy((unsigned char*)job+0x18,desc,sizeof(desc));
        stored=1;
    } __except(EXCEPTION_EXECUTE_HANDLER) { stored=0; }
    if (!stored) {
        ReleaseSRWLockExclusive(&job_registry_lock);
        unsupported_job_export("EXP_JobManager_PushJobOntoList", "job queue shared fields not writable");
    }
    JobListSlot* slot=&job_slots[index];
    *slot->tail=node;
    slot->tail=(void**)&node->next;
    ReleaseSRWLockExclusive(&job_registry_lock);
    fprintf(stdout,"{\"stage\":\"native_job_queued\",\"handle\":%u,"
            "\"job\":%llu,\"job_set\":%llu,\"execute_rva\":\"0x%llx\","
            "\"profile\":\"diagnostic_serial_native_callbacks\",\"executed\":false,"
            "\"submission_sequence\":%llu,\"native_scheduling_cadence_verified\":false}\n",index+1,
            (unsigned long long)(uintptr_t)job,(unsigned long long)(uintptr_t)job_set,
            (unsigned long long)(node->execute-core),(unsigned long long)node->sequence);
    fflush(stdout);
}
__declspec(dllexport) void __cdecl EXP_JobManager_SpawnList(uintptr_t handle) {
    if(GetCurrentThreadId()!=job_runtime_thread ||
       InterlockedCompareExchange(&job_spawn_active,1,0)!=0)
        unsupported_job_export("EXP_JobManager_SpawnList", "unsupported concurrent or recursive job spawn");
    void* frames[12]={0};
    USHORT count=CaptureStackBackTrace(0,12,frames,NULL);
    uintptr_t core=(uintptr_t)GetModuleHandleW(L"GameCore_Base_FinalRelease.dll");
    fprintf(stdout,"{\"stage\":\"native_job_spawn_requested\",\"handle\":%llu,"
            "\"core_base\":%llu,\"stack_pointers\":[",(unsigned long long)handle,
            (unsigned long long)core);
    for(USHORT i=0;i<count;++i) fprintf(stdout,"%s%llu",i?",":"",(unsigned long long)(uintptr_t)frames[i]);
    fputs("],\"executed\":false}\n",stdout);
    fflush(stdout);
    uint32_t index=(uint32_t)(handle-1), completed=0;
    for(;;) {
        AcquireSRWLockExclusive(&job_registry_lock);
        if(index>=64 || !job_slots[index].occupied) {
            ReleaseSRWLockExclusive(&job_registry_lock);
            unsupported_job_export("EXP_JobManager_SpawnList", "inactive job list");
        }
        JobListSlot* slot=&job_slots[index];
        DiagnosticJobNode* node=(DiagnosticJobNode*)slot->head;
        if(!node) {
            ReleaseSRWLockExclusive(&job_registry_lock);
            break;
        }
        DiagnosticJobGroup* group=find_owned_job_group(node->job_set[1],(uintptr_t)node->job_set);
        if(!group || !group->pending || completed>=1024 ||
           !native_job_address_is(*(uintptr_t*)node->job,core,0) ||
           *(uintptr_t*)(*(uintptr_t*)node->job+8)!=node->execute ||
           ((uintptr_t*)node->job)[1]!=(uintptr_t)node ||
           ((uintptr_t*)node->job)[2]!=(uintptr_t)node->job_set) {
            ReleaseSRWLockExclusive(&job_registry_lock);
            unsupported_job_export("EXP_JobManager_SpawnList", "unverified queued job ownership");
        }
        slot->head=node->next;
        if(!slot->head) slot->tail=&slot->head;
        /* EXE985EC0 clears the Core job backreferences before vtable+8. */
        ((uintptr_t*)node->job)[1]=0;
        ((uintptr_t*)node->job)[2]=0;
        ReleaseSRWLockExclusive(&job_registry_lock);
        fprintf(stdout,"{\"stage\":\"before_native_job_execute\",\"handle\":%u,"
                "\"execute_rva\":\"0x%llx\",\"thread_index\":0,"
                "\"submission_sequence\":%llu,\"job\":%llu}\n",index+1,
                (unsigned long long)(node->execute-core),(unsigned long long)node->sequence,
                (unsigned long long)(uintptr_t)node->job);
        fflush(stdout);
        /* A native SpawnList request is the trigger; Push never runs the job.
         * Serial completion is a diagnostic scheduling profile, not a claim
         * to reproduce TBB timing or arbitrary multithreaded job ordering. */
        ((void(__cdecl*)(void*,uint32_t))node->execute)(node->job,0);
        if(node->execute==core+0x3D75B0 && *((unsigned char*)node->job+0xF0)!=1)
            unsupported_job_export("EXP_JobManager_SpawnList", "native Victory job did not mark completion");
        AcquireSRWLockExclusive(&job_registry_lock);
        group->pending--;
        ReleaseSRWLockExclusive(&job_registry_lock);
        fprintf(stdout,"{\"stage\":\"native_job_executed\",\"handle\":%u,"
                "\"execute_rva\":\"0x%llx\",\"callback_returned\":true,"
                "\"victory_completion_checked\":%s,"
                "\"submission_sequence\":%llu,\"job\":%llu,"
                "\"profile\":\"diagnostic_serial_native_callbacks\",\"eligible_for_training\":false}\n",index+1,
                (unsigned long long)(node->execute-core),node->execute==core+0x3D75B0?"true":"false",
                (unsigned long long)node->sequence,(unsigned long long)(uintptr_t)node->job);
        fflush(stdout);
        free(node);
        completed++;
    }
    fprintf(stdout,"{\"stage\":\"native_job_spawn_completed\",\"handle\":%u,"
            "\"native_jobs_executed\":%u,\"eligible_for_training\":false}\n",index+1,completed);
    fflush(stdout);
    InterlockedExchange(&job_spawn_active,0);
}

/* Empty objects and completed host-owned groups follow EXE985660. With both member
 * pointers NULL, either global-manager branch reaches 985711/985714 and only
 * stores zero to these two fields. Unknown groups and incomplete work refuse.
 * Inaccessible storage fails closed before returning to
 * GameCore. SEH covers the real stores too; readable is not necessarily writable.
 */
__declspec(dllexport) void __cdecl EXP_JobManager_DestroyJobSet(uintptr_t job_set) {
    uintptr_t first = 0, second = 0;
    int readable = 0, completed = 0;
    __try {
        volatile uintptr_t* fields = (volatile uintptr_t*)job_set;
        first = fields[0];
        second = fields[1];
        readable = 1;
        if (!first && !second) {
            fields[0] = 0;
            fields[1] = 0;
            completed = 1;
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        completed = 0;
    }
    if (completed) {
        fprintf(stdout, "{\"stage\":\"empty_job_set_destroyed\","
                "\"export\":\"EXP_JobManager_DestroyJobSet\","
                "\"first_argument_raw\":%llu,\"member0\":0,\"member8\":0,"
                "\"contract\":\"two_null_members_only\"}\n",
                (unsigned long long)job_set);
        fflush(stdout);
        return;
    }
    if (readable && first && (!second || second==first)) {
        if(GetCurrentThreadId()!=job_runtime_thread || job_spawn_active)
            unsupported_job_export("EXP_JobManager_DestroyJobSet", "unsupported concurrent or recursive job destruction");
        AcquireSRWLockExclusive(&job_registry_lock);
        DiagnosticJobGroup* group=find_owned_job_group(first,job_set);
        if(group && !group->pending) {
            DiagnosticJobGroup** link=&owned_job_groups;
            while(*link && *link!=group) link=&(*link)->next;
            if(*link) *link=group->next;
            ((uintptr_t*)job_set)[0]=0;
            ((uintptr_t*)job_set)[1]=0;
            group->magic=0;
            free(group);
            ReleaseSRWLockExclusive(&job_registry_lock);
            fputs("{\"stage\":\"native_job_set_destroyed\",\"pending_jobs\":0,"
                  "\"profile\":\"diagnostic_serial_native_callbacks\"}\n",stdout);
            fflush(stdout);
            return;
        }
        ReleaseSRWLockExclusive(&job_registry_lock);
    }
    fprintf(stdout, "{\"stage\":\"unsupported_executable_export\","
            "\"export\":\"EXP_JobManager_DestroyJobSet\","
            "\"first_argument_raw\":%llu,\"members_readable\":%s,"
            "\"member0\":%llu,\"member8\":%llu,\"implemented\":false}\n",
            (unsigned long long)job_set, readable ? "true" : "false",
            (unsigned long long)first, (unsigned long long)second);
    fflush(stdout);
    TerminateProcess(GetCurrentProcess(), 78);
    ExitProcess(78);
}

int wmain(int argc, wchar_t** argv) {
    SetErrorMode(SEM_FAILCRITICALERRORS | SEM_NOGPFAULTERRORBOX | SEM_NOOPENFILEERRORBOX);
    initialize_job_registry();
    wchar_t home[32768];
    DWORD length = GetEnvironmentVariableW(L"CIV6RL_PYTHON_HOME", home, 32768);
    if (!length || length >= 32768) {
        fputs("CIV6RL_PYTHON_HOME must identify the matching 64-bit Python runtime\n", stderr);
        return 2;
    }
    PyConfig config;
    PyConfig_InitPythonConfig(&config);
    PyStatus status = PyConfig_SetString(&config, &config.home, home);
    if (!PyStatus_Exception(status)) status = PyConfig_SetString(&config, &config.executable, argv[0]);
    if (!PyStatus_Exception(status)) status = PyConfig_SetString(&config, &config.program_name, argv[0]);
    if (!PyStatus_Exception(status)) status = PyConfig_SetArgv(&config, argc, argv);
    if (!PyStatus_Exception(status)) status = Py_InitializeFromConfig(&config);
    PyConfig_Clear(&config);
    if (PyStatus_Exception(status)) Py_ExitStatusException(status);
    return Py_RunMain();
}
