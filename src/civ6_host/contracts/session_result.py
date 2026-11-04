"""Player-visible result projection; no runtime, rules, rewards or private data."""

SCHEMA = 'civ6-host.player-result.v1'
POLICY_ID = 'first-official-native-victory-v1'


def require_same_terminal_result(previous, current):
    """Keep the game result fixed while permitting player-specific projections."""
    if previous is None or not previous['terminated']:
        return
    if not current['terminated']:
        raise ValueError('Official result disappeared within the episode')
    before = previous['native_victory']
    after = current['native_victory']
    fields = ('current_game_turn', 'winning_team', 'victory_type')
    if any(before[field] != after[field] for field in fields):
        raise ValueError('Official result changed within the episode')


def project_terminal_result(outcome, *, episode_id, game_generation, player_id, turn):
    """Project an official winner for its exact actor, never infer elimination.

    The wire keeps native provenance separately. This allowlist is the only
    result information added to the public actor view. A truncation or absence
    of a winner must not be turned into a loss.
    """
    if type(outcome) is not dict or type(outcome.get('terminated')) is not bool:
        raise ValueError('Exact episode outcome required')
    if not outcome['terminated']:
        return None
    native = outcome.get('native_victory')
    if (outcome.get('truncated') is not False
            or outcome.get('reason') != 'official_native_victory'
            or type(native) is not dict
            or native.get('schema') != 'civ6rl.native_victory_episode.observation.v1'
            or native.get('policy_id') != POLICY_ID
            or native.get('episode_id') != episode_id
            or native.get('game_generation') != game_generation
            or type(native.get('player_id')) is not int or native['player_id'] != player_id
            or type(native.get('current_game_turn')) is not int or native['current_game_turn'] != turn
            or native.get('episode_terminated') is not True
            or native.get('winner_present') is not True
            or native.get('was_ever_alive') is not True
            or type(native.get('is_alive')) is not bool):
        raise ValueError('Official result belongs to another actor/boundary or is incomplete')
    team, winner, victory = (native.get(k) for k in ('team_id', 'winning_team', 'victory_type'))
    if (type(team) is not int or not 0 <= team < 64
            or type(winner) is not int or not -(2**31) <= winner < 2**31 or winner == -1
            or type(victory) is not int or not -(2**31) <= victory < 2**31
            or type(native.get('winner_matches_player_team')) is not bool
            or native['winner_matches_player_team'] != (winner == team)):
        raise ValueError('Native winner/team relationship differs')
    return dict(schema=SCHEMA, player_id=player_id, turn=turn, team_id=team,
        status='won' if winner == team else 'lost', winning_team=winner,
        victory_type=victory, is_alive=native['is_alive'])
