/* Retain the scalar conversion; accept only managed children or an actually
 * active native listener frame in the same root/thread. */
#include "script_event_state_scope.inc"
#define script_known_child(state) script_event_known_state(state)
#include "script_aux_a0_legacy.inc"
#undef script_known_child
