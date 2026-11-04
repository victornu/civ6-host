"""Stop a bounded diagnostic on an independently read official native result."""
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
from civ6_host.runtime.native import native_episode_facts as facts
from civ6_host.runtime.native import native_victory_episode as victory
from civ6_host.runtime.native.native_episode_identity import require_episode

class NativeVictoryReached(Exception):
    """Successful episode-policy boundary, distinct from an engine error."""

    def __init__(self, result):
        self.result = result
        super().__init__('First official native victory observed')

def defer_at_completed_round_echo(host, local_player, player_states, echo_player):
    """Only the witnessed two-player pre-update checkpoint may defer a read.

    This leaves the exact captured archive in place for the normal native
    transport. It is not a generic permission to ignore pending actions.
    The next published, drained view must still run observe_victory_boundary.
    """
    ended = [{'player_id': 0, 'active': False, 'complete': False}, {'player_id': 1, 'active': False, 'complete': False}]
    if type(echo_player) is not int or echo_player != 1 or local_player != 1 or (player_states != ended) or (host.ui_child is None) or host.deferred_events.pending:
        raise RuntimeError('Unverified completed-round victory observation checkpoint')
    host.actions.validate_completed_round_echo(echo_player)
    host.emit('native_victory_observation_deferred_until_round_echo', player_id=echo_player, pending_archive_hex=host.actions.pending[0].hex(), archive_consumed=False, action_or_outcome_substituted=False, episode_termination_inferred=False, eligible_for_training=False)

def observe_victory_boundary(host, player_id, turn, expected_winner):
    if host.ui_child is None or host.actions.pending or host.deferred_events.pending:
        raise RuntimeError('Victory boundary requires drained queues and published player state')
    identity = require_episode(host)
    policy = getattr(host, '_first_official_victory_policy', None)
    if policy is not None and policy.episode_id != identity.episode_id:
        raise RuntimeError('Victory policy belongs to another diagnostic episode')
    if not getattr(host, '_victory_reader_guards_verified', False):
        marker = host.runtime.evaluate_text(host.ui_child, victory.guard_case(), b'@native_victory_reader_guards')
        if marker != b'native-episode-facts-guards-ok':
            raise RuntimeError('Native HKS victory reader guards failed')
        host._victory_reader_guards_verified = True
        host.emit('native_hks_victory_reader_guards_verified', native_gameplay_mutated=False, eligible_for_training=False)
    payload = host.runtime.evaluate_text(host.ui_child, victory.build_source(player_id, turn), b'@native_victory_boundary_facts', capacity=facts.MAX_RESPONSE)
    parsed = facts.parse_facts(payload, player_id, turn)
    actual = {key: parsed[key] for key in ('winner_present', 'winning_team', 'victory_type')}
    if type(expected_winner) is not dict or set(expected_winner) != set(actual) or any((type(expected_winner[key]) is not type(actual[key]) for key in actual)) or (expected_winner != actual):
        raise RuntimeError('Consecutive native winner observations disagree')
    if policy is None:
        policy = victory.FirstOfficialVictory(identity.episode_id)
        host._first_official_victory_policy = policy
    result = policy.observe(payload, player_id, turn)
    result['game_generation'] = identity.game_generation
    host.emit('native_victory_episode_policy_observed', result=result, engine_state_modified=False, eligible_for_training=False)
    if result['episode_terminated']:
        raise NativeVictoryReached(result)
    return result

def observe_after_round_echo(host, player_id, turn):
    """Stop on an official result before an explicit next-round GameUpdate.

    EndTurn already calls native GameUpdate internally. A winner can therefore
    be present in the ended-turn view. The exact echo is delivered under 801
    first; another public update must not precede this drained readback.
    """
    if host.ui_child is None or host.actions.pending or host.deferred_events.pending:
        raise RuntimeError('Post-echo victory boundary requires drained published state')
    from civ6_host.runtime.native import native_winning_team as winning
    winner = winning.parse(host.runtime.evaluate_text(host.ui_child, winning.source(), b'@native_winning_team_after_round_echo'))
    return observe_victory_boundary(host, player_id, turn, winner)
