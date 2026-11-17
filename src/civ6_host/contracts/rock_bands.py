"""Own rock-band stats and the officially available concert command."""

SCHEMA = 'civ6-host.rock-bands.v1'
KIND = 'perform_rock_concert'
FIELDS = frozenset(('kind','unit_id','x','y'))
RESULT_SCHEMA = 'civ6-host.rock-concert-result.v1'


def validate_action(action, observation=None):
    if (type(action) is not dict or set(action)!=FIELDS or action['kind']!=KIND
            or type(action['unit_id']) is not int or not 0<=action['unit_id']<2**32
            or any(type(action[key]) is not int or not 0<=action[key]<2**31 for key in ('x','y'))):
        raise ValueError('Invalid rock concert action')
    if observation is not None and sum(
        (row['owner'],row['id'],row['x'],row['y']) ==
        (observation['player_id'],action['unit_id'],action['x'],action['y'])
        for row in observation['units'])!=1:
        raise ValueError('Rock concert requires an observed own unit at its current position')
    return action


def validate(panel, player, turn, *, observation=None):
    if (type(panel) is not dict or set(panel)!={'schema','player_id','turn','units'}
            or panel['schema']!=SCHEMA or type(panel['player_id']) is not int or panel['player_id']!=player
            or type(panel['turn']) is not int or panel['turn']!=turn
            or type(panel['units']) is not list or len(panel['units'])>4096):
        raise ValueError('Invalid rock-band information boundary')
    previous=-1
    for row in panel['units']:
        if (type(row) is not dict or set(row)!={'unit_id','x','y','level','album_sales','visible','available'}
                or type(row['visible']) is not bool or type(row['available']) is not bool
                or row['available'] and not row['visible']
                or any(type(row[key]) is not int or not -(2**31)<=row[key]<2**31
                       for key in ('level','album_sales'))):
            raise ValueError('Invalid rock-band stats or availability')
        validate_action({key:row[key] for key in ('unit_id','x','y')}|dict(kind=KIND),observation)
        if row['unit_id']<=previous:
            raise ValueError('Rock-band units are repeated or unordered')
        previous=row['unit_id']
    return panel


def actions(panel):
    return [dict(kind=KIND,**{key:row[key] for key in ('unit_id','x','y')})
            for row in panel['units'] if row['available']]


def validate_result(value, player_id, turn, action):
    validate_action(action)
    if (type(player_id) is not int or not 0 <= player_id < 64
            or type(turn) is not int or turn < 0
            or type(value) is not dict
            or set(value) != {'schema','player_id','turn','unit_id','x','y','result_id','tourism'}
            or value['schema'] != RESULT_SCHEMA
            or any(type(value[key]) is not int for key in
                   ('player_id','turn','unit_id','x','y','result_id','tourism'))
            or (value['player_id'],value['turn'],value['unit_id'],value['x'],value['y']) !=
               (player_id,turn,action['unit_id'],action['x'],action['y'])
            or any(not -(2**31)<=value[key]<2**31 for key in ('result_id','tourism'))):
        raise ValueError('Rock concert result belongs to another command or actor')
    return value

