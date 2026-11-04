"""Explicit roster bounds for the two existing Base diagnostic profiles."""
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path

def validate_roster(player_ids):
    from civ6_host.runtime.network_owner import roster
    return roster(player_ids)

def validate_player(player_id, player_ids=(0, 1)):
    validate_roster(player_ids)
    if type(player_id) is not int or player_id not in player_ids:
        raise ValueError('Player is outside the explicitly admitted diagnostic roster')
    return player_id
