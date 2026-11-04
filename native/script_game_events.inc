/* Native root/child GameEvents factory; source EXE4dbab0/4dc830. */
#include "script_game_events_full.inc"

typedef struct GameEventsInstallRequest { LuaState* child; } GameEventsInstallRequest;
static int __cdecl game_events_install(LuaState* state) {
    GameEventsInstallRequest* request = (GameEventsInstallRequest*)th_userdata(state, 1);
    th_getfield(state, LUA_GLOBALS, "GameEventFactory");
    if (th_type(state, -1) == 0) {
        th_settop(state, -2);
        th_newtable(state, 0, 1); /* prototype shared by root and child proxies */
        th_pushvalue(state, -1); th_setfield(state, LUA_GLOBALS, "GameEventFactory");
        th_newtable(state, 0, 0); th_pushvalue(state, 2); th_setmeta(state, -2);
        th_setfield(state, LUA_GLOBALS, "GameEvents");
        th_newtable(state, 0, 0); /* native indexer cache upvalue */
        th_closure(state, game_events_full_index, 1, "lEventFactoryIndexer", 0);
        th_setfield(state, 2, "__index");
    }
    if (th_type(state, 2) != 5)
        return th_lerror(state, "GameEventFactory is not a table");
    if (!request || !request->child) return 0;
    th_getfield(state, LUA_GLOBALS, "Threads");
    if (th_type(state, 3) != 5)
        return th_lerror(state, "GameEvents thread registry is unavailable");
    th_pushnil(state);
    int found = 0;
    while (th_next(state, 3)) {
        if (th_tothread(state, -2) == request->child) { found = 1; break; }
        th_settop(state, -2);
    }
    if (!found || th_type(state, -1) != 5)
        return th_lerror(state, "GameEvents child environment is unavailable");
    th_newtable(state, 0, 0); th_pushvalue(state, 2); th_setmeta(state, -2);
    th_setfield(state, -2, "GameEvents");
    return 0;
}

__declspec(dllexport) int __cdecl LAB_GameEventsInstall(LuaState* root, LuaState* child) {
    if (root != thread_registry_root || !script_known_child(child) || th_gettop(root)) return -1003;
    GameEventsInstallRequest request = {child};
    return th_cpcall(root, game_events_install, &request);
}
