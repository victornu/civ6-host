/* Profile-local reuse of the retained dispatcher; source is staged by alias.
 * The legacy source bytes are retained under an explicit staged include alias.
 */
static void __cdecl script_game_event_call_with_seed(LuaState*,int,int);
#define th_call script_game_event_call_with_seed
#include "script_game_event_dispatch_legacy.inc"
#undef th_call
#include "script_game_event_result_map.inc"
