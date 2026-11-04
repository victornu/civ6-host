/* Retain the original Call/TestAll algorithm. Scope only actual pcall sites;
 * the function-like macro does not replace API-pointer availability checks.
 */
#include "script_event_state_scope.inc"
#define th_pcall(state,nargs,results,errorfunc) game_event_scoped_pcall(state,nargs,results,errorfunc)
#include "script_game_events_full_legacy.inc"
#undef th_pcall
#include "script_event_state_diagnostic.inc"
