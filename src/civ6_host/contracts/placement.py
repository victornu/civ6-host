"""Portable shared placement action and tracked-progress contract.

The native adapter delegates its unchanged pure validation to this module.
Offers and completion remain actual engine reads, not inferred legality.
"""
from .production_queue import _uint, _type_name
FIELDS = {'kind','city_id','category','index','hash','item_type','mode','plot_id','x','y'}
RESUME_FIELDS = {'kind','city_id','category','index','hash','item_type'}
ACTION_FIELDS = {'production_placement':FIELDS,'production_resume':RESUME_FIELDS}
UNQUALIFIED_PLACEMENT = ('hidden_placement_targets','purchases','queue_append_placements','multiple_district_repair_locations')
UNQUALIFIED_RESUME = ('purchases','queue_append_placements','multiple_district_repair_locations')
GAPS = {'production_placement':UNQUALIFIED_PLACEMENT,'production_resume':UNQUALIFIED_RESUME}
OBSERVATION_SCOPE = 'host_tracked'


def validate_public(offers, progress, scope, player_id, turn, *, observation=None, unavailable=False):
    """Own, visible placement rows; tracked progress is never a full inventory."""
    if type(unavailable) is not bool:raise ValueError('Placement availability must be Boolean')
    if unavailable:
        if offers is not None or progress is not None or scope is not None:
            raise ValueError('Unavailable placement fields must all be null')
        return
    if scope!=OBSERVATION_SCOPE:raise ValueError('Placement observation scope must remain host_tracked')
    validate_offers(offers,player_id=player_id);validate_progress(progress,turn,player_id=player_id)
    if observation is None:return
    own={c['id'] for c in observation['cities'] if c['owner']==player_id}
    width,height=observation['width'],observation['height']
    visible={p['index'] for p in observation['plots'] if p['visible'] is True}
    for row in [*offers,*progress]:
        if row['city_id'] not in own:raise ValueError('Placement names a foreign or unobserved own city')
        if row.get('kind')=='production_resume':continue
        if (not 0<=row['x']<width or not 0<=row['y']<height
                or row['plot_id']!=row['y']*width+row['x'] or row['plot_id'] not in visible):
            raise ValueError('Placement coordinates differ from the currently visible public map')


def validate_candidates(offers,candidates):
    import json
    actual=[r['action'] for r in candidates if r['action']['kind'] in ACTION_FIELDS]
    expected=[] if offers is None else offers
    key=lambda a:json.dumps(a,sort_keys=True)
    if sorted(actual,key=key)!=sorted(expected,key=key):
        raise ValueError('Placement candidates differ from the exact native offers')

def _player_id(value):
    return _uint(value, 'player', 63)

def validate_action(value, *, player_id=0):
    _player_id(player_id)
    if type(value) is dict and value.get('kind') == 'production_resume':
        if set(value) != RESUME_FIELDS or value['category'] not in ('building', 'district'):
            raise ValueError('Malformed production resumption')
        for key in ('city_id', 'index', 'hash'):
            _uint(value[key], key, 2147483647 if key == 'index' else 4294967295)
        _type_name(value['category'], value['item_type'])
        return value
    if type(value) is not dict or set(value) != FIELDS or value['kind'] != 'production_placement' or (value['category'] not in ('building', 'district')) or (value['mode'] != 'place'):
        raise ValueError('Only explicit fresh placement is admitted')
    for key in ('city_id', 'index', 'hash', 'plot_id', 'x', 'y'):
        maximum = 65535 if key in ('plot_id', 'x', 'y') else 2147483647 if key == 'index' else 4294967295
        _uint(value[key], key, maximum)
    _type_name(value['category'], value['item_type'])
    return value

def validate_offers(rows, *, player_id=0):
    import json
    _player_id(player_id)
    if type(rows) is not list or len(rows) > 4096:
        raise ValueError('Unbounded placement offers')
    seen = set()
    for a in rows:
        validate_action(a, player_id=player_id)
        key = json.dumps(a, sort_keys=True)
        if key in seen:
            raise ValueError('Duplicate placement offer')
        seen.add(key)
    return rows

def validate_progress(rows, turn, *, player_id=0):
    pid = _player_id(player_id)
    if type(rows) is not list or len(rows) > 256:
        raise ValueError('Invalid tracked placement observations')
    seen = set()
    for row in rows:
        if type(row) is not dict or set(row) != {'city_id', 'category', 'index', 'item_type', 'plot_id', 'x', 'y', 'placement_turn', 'observed_turn', 'exists', 'complete'} or row['category'] not in ('building', 'district') or (type(row['exists']) is not bool) or (type(row['complete']) is not bool) or (row['complete'] and (not row['exists'])):
            raise ValueError('Malformed placement progress')
        validate_action(dict(kind='production_placement', mode='place', hash=0, **{k: row[k] for k in ('city_id', 'category', 'index', 'item_type', 'plot_id', 'x', 'y')}))
        for k in ('placement_turn', 'observed_turn'):
            _uint(row[k], k)
        key = (row['city_id'], row['plot_id'])
        if row['observed_turn'] != turn or row['placement_turn'] > turn or key in seen:
            raise ValueError('Stale or duplicate placement progress')
        seen.add(key)
    return rows
