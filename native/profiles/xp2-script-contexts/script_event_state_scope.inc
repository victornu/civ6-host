#ifndef LAB_GAME_EVENT_STATE_SCOPE_INCLUDED
#define LAB_GAME_EVENT_STATE_SCOPE_INCLUDED
/* Scope the real temporary HKS threads used by retained GameEvents methods.
 * This records host ownership only; no game state or gameplay rule is changed.
 * A frame exists exclusively during the protected native listener call.
 */
typedef struct GameEventStateScope {
    LuaState* root;
    LuaState* state;
    DWORD thread;
    struct GameEventStateScope* previous;
} GameEventStateScope;
static __declspec(thread) GameEventStateScope* game_event_state_scope=NULL;

static int __cdecl game_event_scoped_pcall(LuaState* state,int nargs,int results,int errorfunc) {
    GameEventStateScope frame={thread_registry_root,state,GetCurrentThreadId(),game_event_state_scope};
    game_event_state_scope=&frame;
    /* lua_pcall catches Lua errors before returning to this C frame. */
    int status=th_pcall(state,nargs,results,errorfunc);
    game_event_state_scope=frame.previous;
    return status;
}

__declspec(dllexport) uint32_t __cdecl LAB_GameEventsStateScopeVersion(void) {return 1;}

__declspec(dllexport) uint32_t __cdecl LAB_GameEventsStateIsActive(LuaState* root,LuaState* state) {
    if(!root || !state || root!=thread_registry_root)return 0;
    DWORD thread=GetCurrentThreadId();
    for(GameEventStateScope* frame=game_event_state_scope;frame;frame=frame->previous)
        if(frame->root==root && frame->state==state && frame->thread==thread)return 1;
    return 0;
}

static int script_event_known_state(LuaState* state) {
    return script_known_child(state) || LAB_GameEventsStateIsActive(thread_registry_root,state);
}
#endif
