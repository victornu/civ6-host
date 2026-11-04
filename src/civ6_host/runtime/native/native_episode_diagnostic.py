"""Observe actual public episode facts without guessing terminal conditions."""
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
from civ6_host.runtime.native import native_episode_facts as facts

def observe_episode_facts(host, player_id):
    if host.ui_child is None or host.actions.pending or host.deferred_events.pending:
        raise RuntimeError('Episode facts require a published view and drained queues')
    if not getattr(host, '_episode_facts_guards_verified', False):
        marker = host.runtime.evaluate_text(host.ui_child, facts.guard_case(), b'@native_episode_facts_guards')
        if marker != b'native-episode-facts-guards-ok':
            raise RuntimeError('Native HKS episode fact guards failed')
        host._episode_facts_guards_verified = True
        host.emit('native_hks_episode_facts_guards_verified', native_gameplay_mutated=False, eligible_for_training=False)
    turn = int(host.runtime.evaluate_text(host.ui_child, b'return string.format("%.0f",Game.GetCurrentGameTurn())', b'@native_episode_facts_turn'))
    result = facts.parse_facts(host.runtime.evaluate_text(host.ui_child, facts.build_source(player_id, turn), b'@native_episode_facts', capacity=facts.MAX_RESPONSE), player_id, turn)
    host.emit('native_episode_facts_observed', facts=result, native_gameplay_mutated=False, eligible_for_training=False)
    return result
