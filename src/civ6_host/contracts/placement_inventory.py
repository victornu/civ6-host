"""Public native placement inventory, separate from host-tracked progress.

This validates a same-boundary read. It does not infer placement dates,
availability of a production action, or completeness of hidden constructs.
"""
from .action_budget import MAP_CELL_LIMIT
from .production_queue import _uint, _type_name

SCHEMA='civ6-host.placement-inventory.v1'
SCOPE='native_visible_own_city'
MAX_ROWS=2*MAP_CELL_LIMIT
FIELDS=frozenset(('schema','scope','player_id','turn','rows'))
ROW_FIELDS=frozenset(('city_id','category','index','hash','item_type','plot_id',
                      'x','y','complete','district_id'))


def validate(value,player_id,turn,*,observation=None):
    """Validate exact public rows; null means that this read was unavailable."""
    _uint(player_id,'inventory player',63);_uint(turn,'inventory turn',2147483647)
    if value is None:return None
    if (type(value) is not dict or set(value)!=FIELDS or value['schema']!=SCHEMA
            or value['scope']!=SCOPE or type(value['player_id']) is not int
            or value['player_id']!=player_id or type(value['turn']) is not int
            or value['turn']!=turn or type(value['rows']) is not list
            or len(value['rows'])>MAX_ROWS):
        raise ValueError('Malformed or foreign native placement inventory')
    own=visible=None
    if observation is not None:
        if (type(observation) is not dict or type(observation.get('player_id')) is not int
                or observation['player_id']!=player_id or type(observation.get('turn')) is not int
                or observation['turn']!=turn):
            raise ValueError('Placement inventory observation boundary differs')
        width,height=observation['width'],observation['height']
        _uint(width,'inventory map width',MAP_CELL_LIMIT)
        _uint(height,'inventory map height',MAP_CELL_LIMIT)
        if width==0 or height==0 or width*height>MAP_CELL_LIMIT:
            raise ValueError('Placement inventory map geometry exceeds the public bound')
        own={r['id'] for r in observation['cities'] if r['owner']==player_id}
        visible={r['index'] for r in observation['plots'] if r['visible'] is True}
    seen=set()
    for row in value['rows']:
        if (type(row) is not dict or set(row)!=ROW_FIELDS
                or row['category'] not in ('district','building')
                or type(row['complete']) is not bool):
            raise ValueError('Malformed native placement inventory row')
        for name in ('city_id','hash'):_uint(row[name],'inventory '+name)
        _uint(row['index'],'inventory index',2147483647)
        for name in ('plot_id','x','y'):_uint(row[name],'inventory '+name,65535)
        _type_name(row['category'],row['item_type'])
        if row['category']=='district':_uint(row['district_id'],'inventory district')
        elif row['district_id'] is not None:
            raise ValueError('Building inventory cannot claim a district instance identity')
        key=(row['city_id'],row['category'],row['plot_id'])
        if key in seen:raise ValueError('Duplicate native placement inventory row')
        seen.add(key)
        if own is not None:
            if row['city_id'] not in own:
                raise ValueError('Placement inventory names a foreign or unobserved own city')
            if (not 0<=row['x']<width or not 0<=row['y']<height
                    or row['plot_id']!=row['y']*width+row['x'] or row['plot_id'] not in visible):
                raise ValueError('Placement inventory differs from the currently visible public map')
    return value
