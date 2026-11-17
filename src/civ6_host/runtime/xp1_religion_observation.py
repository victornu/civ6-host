"""Partial own-player snapshot on the existing saved owner, without actions.

The historical reader requires a present HolyCity to remain owned by the actor.
It therefore does not claim the full religion lifecycle or command family.
"""
from . import xp1_religion_observation_source as source

source_for = source.source_for
supports = source.supports
source_dependencies = source.source_dependencies
require_actions = source.require_actions


def snapshot(saved, observation):
    saved._check_query()
    if type(observation) is not dict:
        raise ValueError('Own religion snapshot requires the actor observation')
    pid, turn = observation.get('player_id'), observation.get('turn')
    if (type(pid) is not int or not 0 <= pid < 64
            or type(turn) is not int or not 0 <= turn <= 0xffffffff):
        raise ValueError('Own religion snapshot actor identity differs')
    source.bind_prefix(saved.prefix)
    value = saved.prefix.inspect_own_religion_snapshot(pid)
    if value['player_id'] != pid or value['current_game_turn'] != turn:
        raise ValueError('Own religion snapshot actor or turn changed')
    return value
