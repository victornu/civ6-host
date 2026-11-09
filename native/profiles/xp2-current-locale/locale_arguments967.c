/* Additive protected Locale callback. The executable/JobManager ABI stays
 * Host41. This module remains loaded until the worker process exits; it does
 * not own the Lua VM, localization lifetime, databases, or simulation state.
 * Reuses script_locale.inc's bounded String lifetime and native formatting.
 */
#include <windows.h>
#include <stdint.h>
#include <stddef.h>
#include <string.h>
typedef void LuaState;
typedef int (__cdecl *LuaCallback)(LuaState*);
typedef struct LuaStackResult { void* state; int index; int padding; } LuaStackResult;
#define LUA_GLOBALS (-10002)
#define LUA_UPVALUE(n) (LUA_GLOBALS-(n))
static LuaState* thread_registry_root;
static void (__cdecl *th_newtable)(LuaState*, int, int);
static void (__cdecl *th_getfield)(LuaState*, int, const char*);
static void (__cdecl *th_setfield)(LuaState*, int, const char*);
static LuaStackResult* (__cdecl *th_pushbool)(LuaState*, LuaStackResult*, unsigned char);
static LuaStackResult* (__cdecl *th_pushstring)(LuaState*, LuaStackResult*, const char*);
static LuaStackResult* (__cdecl *th_pushlstring)(LuaState*, LuaStackResult*, const char*, size_t);
static void (__cdecl *th_closure)(LuaState*, LuaCallback, int, const char*, int);
static int (__cdecl *th_cpcall)(LuaState*, LuaCallback, void*);
static int (__cdecl *th_pcall)(LuaState*, int, int, int);
static void* (__cdecl *th_userdata)(LuaState*, int);
static int (__cdecl *th_type)(LuaState*, int);
static int (__cdecl *th_error)(LuaState*);
static int (__cdecl *th_gettop)(LuaState*);
static double (__cdecl *th_checknumber)(LuaState*, int);
static int (__cdecl *th_lerror)(LuaState*, const char*, ...);
static void* (__cdecl *th_newuserdata)(LuaState*, size_t);
static const char* (__cdecl *th_checkstring)(LuaState*, int, size_t*);
#include "script_locale.inc"

static int __cdecl install_lookup(LuaState* state) {
    th_getfield(state, LUA_GLOBALS, "Locale");
    if (th_type(state, -1) != 5)
        return th_lerror(state, "Locale root backend must already be registered");
    th_getfield(state, -1, "Lookup");
    if (th_type(state, -1) != 6)
        return th_lerror(state, "Locale.Lookup backend is not a function");
    /* Keep the previous function on the stack; backend is now at -2. */
    th_closure(state, locale_lookup_key, 0, "Locale.Lookup native numeric arguments", 0);
    th_setfield(state, -3, "Lookup");
    return 0;
}

__declspec(dllexport) int __cdecl LAB_LocaleArgumentsInstall(void* core, void* localization, LuaState* root) {
    if (!core || !localization || !root || thread_registry_root) return -1700;
#define BIND(dst, symbol, rva) do { \
    FARPROC proc = GetProcAddress((HMODULE)core, symbol); \
    if (!proc || (uintptr_t)proc != (uintptr_t)core + (rva)) return -1701; \
    memcpy(&(dst), &proc, sizeof(proc)); \
} while (0)
    BIND(th_newtable, "?lua_createtable@@YAXPEAUlua_State@@HH@Z", 0x31820);
    BIND(th_getfield, "?lua_getfield@@YAXPEAUlua_State@@HPEBD@Z", 0x3a4c0);
    BIND(th_setfield, "?lua_setfield@@YAXPEAUlua_State@@HPEBD@Z", 0x3ad80);
    BIND(th_pushbool, "?PushBoolean@LuaState@LuaPlus@@QEAA?AVLuaStackObject@2@_N@Z", 0x18b60);
    BIND(th_pushstring, "?PushString@LuaState@LuaPlus@@QEAA?AVLuaStackObject@2@PEBD@Z", 0x18f50);
    BIND(th_pushlstring, "?PushLString@LuaState@LuaPlus@@QEAA?AVLuaStackObject@2@PEBD_K@Z", 0x18e50);
    BIND(th_closure, "?hks_pushnamedcclosure@@YAXPEAUlua_State@@P6AH0@ZHPEBDH@Z", 0x2cfb0);
    BIND(th_cpcall, "?lua_cpcall@@YAHPEAUlua_State@@P6AH0@ZPEAX@Z", 0x14720);
    BIND(th_pcall, "?lua_pcall@@YAHPEAUlua_State@@HHH@Z", 0x3ac80);
    BIND(th_userdata, "?lua_touserdata@@YAPEAXPEAUlua_State@@H@Z", 0x3ae30);
    BIND(th_type, "?lua_type@@YAHPEAUlua_State@@H@Z", 0x3ae40);
    BIND(th_error, "?lua_error@@YAHPEAUlua_State@@@Z", 0x31a00);
    BIND(th_gettop, "?lua_gettop@@YAHPEAUlua_State@@@Z", 0x175f0);
    BIND(th_checknumber, "?luaL_checknumber@@YANPEAUlua_State@@H@Z", 0x39650);
    BIND(th_lerror, "?luaL_error@@YAHPEAUlua_State@@PEBDZZ", 0x39910);
    BIND(th_newuserdata, "?lua_newuserdata@@YAPEAXPEAUlua_State@@_K@Z", 0x33140);
    BIND(th_checkstring, "?luaL_checklstring@@YAPEBDPEAUlua_State@@HPEA_K@Z", 0x14800);
#undef BIND
    thread_registry_root = root;
    int status = LAB_LocaleBind(root, localization);
    if (status) return status;
    return th_cpcall(root, install_lookup, NULL);
}
