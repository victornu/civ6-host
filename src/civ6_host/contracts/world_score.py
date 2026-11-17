"""Human-visible score tab data. Unmet rows carry no player or team ID."""

import re

SCHEMA = 'civ6-host.world-score.v1'
MAX_FRAME_BYTES = 65536


def _integer(value, lower, upper):
    return type(value) is int and lower <= value <= upper


def validate(value, player_id, turn):
    if (type(value) is not dict
            or set(value) != {'schema', 'player_id', 'turn', 'score_victory_enabled',
                              'max_game_turns', 'categories', 'teams'}
            or value['schema'] != SCHEMA
            or not _integer(value['player_id'], 0, 63) or value['player_id'] != player_id
            or not _integer(value['turn'], 0, 2**31-1) or value['turn'] != turn
            or type(value['score_victory_enabled']) is not bool
            or not _integer(value['max_game_turns'], -2**31, 2**31-1)):
        raise ValueError('Invalid public world score boundary')
    categories = value['categories']
    if (type(categories) is not list or len(categories) > 64
            or any(type(name) is not str or not re.fullmatch(r'[A-Z][A-Z0-9_]{0,95}', name)
                   for name in categories)
            or len(set(categories)) != len(categories)):
        raise ValueError('Invalid public score categories')
    teams = value['teams']
    if type(teams) is not list or not 1 <= len(teams) <= 64:
        raise ValueError('Invalid public score teams')
    seen = set()
    player_count = 0
    previous_team_score = 64 * 2**31
    for team in teams:
        if (type(team) is not dict or set(team) != {'score', 'players'}
                or not _integer(team['score'], -64 * 2**31, previous_team_score)
                or type(team['players']) is not list or not team['players']):
            raise ValueError('Invalid public score team')
        player_count += len(team['players'])
        if player_count > 64:
            raise ValueError('Public score roster exceeds its bound')
        previous_player_score = 2**31-1
        total = 0
        for player in team['players']:
            if (type(player) is not dict or set(player) != {'player_id', 'score', 'category_scores'}
                    or not _integer(player['score'], -2**31, previous_player_score)
                    or type(player['category_scores']) is not list
                    or len(player['category_scores']) != len(categories)
                    or any(not _integer(score, -2**31, 2**31-1) for score in player['category_scores'])):
                raise ValueError('Invalid public player score')
            pid = player['player_id']
            if pid is not None:
                if not _integer(pid, 0, 63) or pid in seen:
                    raise ValueError('Invalid or repeated public score player')
                seen.add(pid)
            previous_player_score = player['score']
            total += player['score']
        if total != team['score']:
            raise ValueError('Team score differs from its displayed members')
        previous_team_score = total
    if player_id not in seen:
        raise ValueError('Public score is missing its own local player')
    return value
