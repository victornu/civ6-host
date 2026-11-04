"""Bounded enumeration of ordinary choices and unfiltered map coordinates.

This only checks transport capacity. Native legality and exact world-input
candidate validation remain with their existing validators.
"""

ORDINARY_ACTION_LIMIT = 4096
MAP_CELL_LIMIT = 16384
LAN_EVENT_LINE_BYTES = 16 * 1024 * 1024


def validate_action_count(actions, *, world_input=None, map_coordinates=False):
    if type(map_coordinates) is not bool or type(actions) is not list:
        raise ValueError('Invalid action-budget input')
    if not map_coordinates:
        if len(actions) > ORDINARY_ACTION_LIMIT:
            raise ValueError('Legacy action catalogue exceeds 4096 choices')
        return
    clicks = sum(type(action) is dict and action.get('kind') == 'world_plot_click'
                 for action in actions)
    if len(actions) - clicks > ORDINARY_ACTION_LIMIT:
        raise ValueError('Ordinary action catalogue exceeds 4096 choices')
    if not clicks:
        return
    if type(world_input) is not dict or world_input.get('selected_unit_id') is None:
        raise ValueError('Map-coordinate choices require a selected unit')
    width, height = world_input.get('width'), world_input.get('height')
    if (type(width) is not int or type(height) is not int
            or not 1 <= width <= 512 or not 1 <= height <= 512
            or width * height > MAP_CELL_LIMIT or clicks > width * height):
        raise ValueError('Map-coordinate action budget exceeds declared geometry')
