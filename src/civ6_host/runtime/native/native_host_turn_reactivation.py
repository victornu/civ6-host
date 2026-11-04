"""Host+68 non-timer branch, using the shared owned native controller.

The callback mutates host state. Its return gates real GameCore processing;
it is not a presentation no-op. Timer-dependent requests remain refused.
"""
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import ctypes as C
from pathlib import Path
from civ6_host.runtime.native.native_source_cache import load_pinned_json
ROOT = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_host_turn_reactivation.py')))).resolve().parents[1]
PROOF_SHA256 = '042cf919b8082501ef6545e4e05f0555476b8f1d246e2f7c0110a644aa5511bc'
PROOF_PATH = ROOT / 'evidence/native-host-turn-reactivation' / (PROOF_SHA256 + '.json')
TIMER_REASON = 3591077460
UI_REASON = 4235402789
SIZE = 1200

def verify_source():
    from civ6_host.runtime.native.native_configuration_finalization import CORE_SHA256
    from civ6_host.runtime.native.native_configuration_finalization import EXE_SHA256
    p = load_pinned_json(PROOF_PATH, PROOF_SHA256)
    if p['schema'] != 'civ6rl.host_turn_reactivation949.static.v1' or p['images'] != {'core_sha256': CORE_SHA256, 'exe_sha256': EXE_SHA256} or p['slot']['offset'] != 104 or (p['slot']['target_rva'] != 1874592) or (p['contract']['player_base'] != 76) or (p['contract']['player_stride'] != 16) or (p['contract']['refused_timer_reason'] != TIMER_REASON) or (not p['validation']['all_captured_instructions_match_pinned_pe']):
        raise ValueError('Host turn reactivation source changed')
    return p

def validate_request(player, reason):
    if type(player) is not int or not 0 <= player < 64 or type(reason) is not int or (not 0 <= reason < 2 ** 32):
        raise ValueError('Host+68 requires a bounded player and uint32 reason')
    if reason == TIMER_REASON:
        raise RuntimeError('Host+68 timer-dependent controller branch is not qualified')

def cleared_controller_bytes(raw, player, retained):
    if type(raw) is not bytes or len(raw) != SIZE or type(player) is not int or (not 0 <= player < 64) or (type(retained) is not int) or (not -2 ** 31 <= retained < 2 ** 31):
        raise ValueError('Invalid owned controller state or retained native getter')
    result = bytearray(raw)
    if retained == player:
        result[5] = 0
    result[76 + 16 * player] = 0
    return bytes(result)

def clear_owned(controller, player, retained):
    from civ6_host.runtime.native.native_controller_code import NativeControllerFlag
    if type(controller) is not NativeControllerFlag:
        raise TypeError('Original owned controller required')
    controller._check()
    before = C.string_at(controller.pointer, SIZE)
    expected = cleared_controller_bytes(before, player, retained)
    offsets = ([5] if player == retained else []) + [76 + 16 * player]
    for offset in offsets:
        C.c_uint8.from_address(controller.pointer + offset).value = 0
    controller._check()
    after = C.string_at(controller.pointer, SIZE)
    if after != expected:
        controller.poisoned = True
        raise RuntimeError('Host+68 changed an unexpected owned controller byte')
    return [dict(offset=offset, before=before[offset], after=after[offset]) for offset in offsets]

class HostTurnReactivation:

    def __init__(self, owner):
        verify_source()
        self.owner = owner
        self.prefix = owner.prefix
        self.busy = False
        self.poisoned = False
        self.completed_count = 0
        self.last_receipt = None
        self.host = self.prefix.host
        self.host._bind(self.host.vtable, 104, C.c_uint8, [C.c_void_p, C.c_int32, C.c_uint32], self.callback)

    def receipt_after(self, count, *, player_id=0):
        if type(count) is not int or not 0 <= count <= self.completed_count:
            raise ValueError('Invalid native reactivation boundary')
        if self.busy or self.poisoned:
            raise RuntimeError('Reactivation callback is not quiescent')
        if self.completed_count == count:
            return None
        row = self.last_receipt
        if type(row) is not dict or row.get('player_id') != player_id or row.get('callback_sequence') != self.completed_count or (row.get('source_sha256') != PROOF_SHA256):
            raise RuntimeError('Reactivation belongs to another native player or callback')
        return dict(row)

    def callback(self, receiver, player, reason):
        self.host._check(receiver)
        self.owner.emit('native_host_turn_reactivation_requested', slot='0x68', player_id=player, reason=hex(reason), source_sha256=PROOF_SHA256, eligible_for_training=False)
        validate_request(player, reason)
        if self.busy or self.poisoned:
            raise RuntimeError('Nested or poisoned host+68')
        from civ6_host.runtime.native.native_controller_state import NativeControllerTurnState
        events = self.prefix.deferred_events
        state = events.turn_begin_state
        getter = events.retained_game_getter
        publisher = self.prefix.view_publisher
        if type(state) is not NativeControllerTurnState or state.code is not self.owner.native_controller_code or getattr(getter, '__self__', None) is not publisher or (getattr(getter, '__func__', None) is not type(publisher).read_retained_game_value) or (type(state.service_flags) is not int) or (not 0 <= state.service_flags <= 255):
            raise RuntimeError('Host+68 lacks the retained controller/getter/shared UI state')
        self.busy = True
        try:
            controller = state._ensure()
            retained = getter()
            changes = clear_owned(controller, player, retained)
            before = state.service_flags
            if reason == UI_REASON:
                state.service_flags |= 64
            self.owner.emit('native_host_turn_reactivation_applied', slot='0x68', player_id=player, reason=hex(reason), retained_game_value=retained, owned_controller_writes=changes, service_flags_before=before, service_flags_after=state.service_flags, return_value=1, source_sha256=PROOF_SHA256, same_controller_as_turn_events=True, native_getter_called=True, core_memory_written=False, timer_branch_executed=False, eligible_for_training=False)
            self.completed_count = getattr(self, 'completed_count', 0) + 1
            self.last_receipt = dict(schema='civ6rl.native_turn_reactivation.v1', player_id=player, callback_sequence=self.completed_count, reason=reason, source_sha256=PROOF_SHA256)
            return 1
        except BaseException:
            self.poisoned = True
            raise
        finally:
            self.busy = False

def install(owner):
    if hasattr(owner, 'host_turn_reactivation'):
        raise RuntimeError('Host+68 already installed')
    owner.host_turn_reactivation = HostTurnReactivation(owner)
