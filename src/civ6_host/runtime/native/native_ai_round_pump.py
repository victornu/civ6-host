"""Bounded diagnostic use of Game+30 while native AI players finish a turn.

Only GameCore computes AI work and emits completion. This orchestrator neither
implements AI decisions nor claims to reproduce the original EXE scheduler.
The update limit is a failure bound, never a completion or victory condition.
"""
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
from pathlib import Path
from civ6_host.runtime.native.native_source_cache import load_pinned_json
PROOF_SHA256 = '8591d5d56fcf7f173d0a3189ad35a094ac94a57b2f27a07f872bcd320856c3ba'
_ROOT = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_ai_round_pump.py')))).resolve().parents[1]
_ENDED = [dict(player_id=0, active=False, complete=False), dict(player_id=1, active=False, complete=False)]
OBSERVER_SOURCE = b"\nlocal function one(label,...)\n assert(select('#',...)==1,'AI wait invalid '..label..' arity')\n return ...\nend\nlocal player=one('local player',Game.GetLocalPlayer())\nlocal observer=one('local observer',Game.GetLocalObserver())\nassert(type(player)=='number' and type(observer)=='number' and\n       player==1 and observer==1,'AI wait local player/observer changed')\nreturn '1|1'\n"

def verify_source_evidence():
    proof = load_pinned_json(_ROOT / 'evidence/native-ai-turn-progression' / (PROOF_SHA256 + '.json'), PROOF_SHA256)
    if proof.get('schema') != 'civ6rl.native_ai_turn_progression.static.v1' or proof.get('core_sha256') != 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3' or proof.get('exe_sha256') != 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63' or (proof['bodies']['core']['automatic_player_update_gate']['code_sha256'] != 'b55cc5924474b8e0583a8251724cd6d6d384bf1c62d0981baaaf4c5318786840') or (proof['capture_integrity']['hashes_checked'] is not True) or (proof['capture_integrity']['instruction_count_revalidated'] != 3272):
        raise RuntimeError('Native AI progression source contract changed')
    slots = {(row['table_va'], row['slot']): row['target_va'] for row in proof['public_slots']}
    if slots.get(('0x18079e020', '0x90')) != '0x18042dee0' or slots.get(('0x18079ecd8', '0x30')) != '0x180435060' or proof['instruction_guards']['turn_processor']['0x18004110d'] != 'call 0x1800545d0' or (proof['instruction_guards']['end_game_turn']['0x18003f8a9'] != 'call 0x180052ec0'):
        raise RuntimeError('Native AI progression update/completion route changed')
    return proof

def _waiting_state(state, turn):
    if type(state) is not dict or type(state.get('current_game_turn')) is not int or state['current_game_turn'] != turn or (type(state.get('local_player')) is not int) or (state['local_player'] != 1) or (state.get('players') != _ENDED) or any((type(row.get('player_id')) is not int or type(row.get('active')) is not bool or type(row.get('complete')) is not bool for row in state['players'])):
        raise RuntimeError('Native AI waiting state changed turn, perspective, or human state')

def wait_for_completed_round_echo(host, turn, *, max_updates=128):
    """Return a published ended-human state with its real echo still queued.

    Caller publishes the initial post-EndTurn view. Subsequent iterations use
    public GameUpdate, drain the existing native notifications, then publish.
    The caller must deliver the captured echo BEFORE another update. This
    diagnostic is scoped to two human actors followed by native AI actors.
    """
    if type(turn) is not int or not 0 <= turn <= 2147483647 or type(max_updates) is not int or (not 0 <= max_updates <= 256):
        raise ValueError('Unverified turn or diagnostic update bound')
    verify_source_evidence()
    from civ6_host.runtime.native.native_episode_facts import verify_source as verify_observer_source
    verify_observer_source()
    if host.ui_child is None:
        raise RuntimeError('Native AI wait requires the current published UI view')
    for updates in range(max_updates + 1):
        if host.deferred_events.pending:
            raise RuntimeError('Native AI wait requires drained deferred callbacks')
        echo = bool(host.actions.pending)
        if echo:
            flags = host.actions.validate_completed_round_echo(1)
        else:
            flags = host.actions.read(host.actions.core._handle + 9156608, 4)
            if flags != b'\x00' * 4:
                raise RuntimeError('Unverified native AI processor phase without completion archive')
        state = host.inspect_player_view(**{'completed_round_echo_player': 1} if echo else {})
        _waiting_state(state, turn)
        perspective = host.runtime.evaluate_text(host.ui_child, OBSERVER_SOURCE, b'@native_ai_round_observer')
        if perspective != b'1|1':
            raise RuntimeError('Native AI wait local observer checkpoint is unavailable')
        if echo:
            host.actions.validate_completed_round_echo(1)
            if host.deferred_events.pending:
                raise RuntimeError('Native AI echo readback produced deferred work')
            host.emit('native_ai_round_completion_wait_verified', current_game_turn=turn, local_player=1, local_observer=1, additional_public_updates=updates, original_archive_hex=host.actions.pending[0].hex(), processor_flags=list(flags), archive_delivered=False, source_proof_sha256=PROOF_SHA256, perspective_verified_by_native_getters=True, full_exe_scheduler_reproduced=False, diagnostic_boundary_only=True, native_round_increment_verified=False, eligible_for_training=False)
            return state
        if updates == max_updates:
            raise RuntimeError('Native AI completion exceeded the diagnostic update bound')
        if host.actions.pending or host.deferred_events.pending:
            raise RuntimeError('Native AI readback unexpectedly produced pending work')
        if host.actions.read(host.actions.core._handle + 9156608, 4) != flags:
            raise RuntimeError('Native AI processor phase changed across readback')
        host.emit('before_native_ai_round_wait_update', current_game_turn=turn, update_number=updates + 1, diagnostic_update_bound=max_updates, source_proof_sha256=PROOF_SHA256, full_exe_scheduler_reproduced=False, diagnostic_boundary_only=True, eligible_for_training=False)
        host.actions.update_game_once()
        host.deferred_events.drain_empty_receivers()
        host.view_publisher.publish()
