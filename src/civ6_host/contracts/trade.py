"""Portable validators for native trade routes and trader relocation."""

ROUTE_FIELDS = {'kind', 'unit_id', 'origin_owner', 'origin_city', 'destination_owner', 'destination_city', 'x0', 'y0', 'x1', 'y1'}
ORIGIN_FIELDS = {'kind', 'unit_id', 'origin_city', 'source_x', 'source_y', 'destination_city', 'x', 'y', 'plot_id'}
GROUP_SCHEMA = 'civ6-host.trade-inputs.v1'


def uint(value, label, maximum=4294967295):
    if type(value) is not int or not 0 <= value <= maximum:
        raise ValueError('Invalid trade ' + label)
    return value

def _shape(v, fields):
    if type(v) is not dict or set(v) != set(fields.split()):
        raise ValueError('Invalid trade fields')

def _list(v, maximum=4096):
    if type(v) is not list or len(v) > maximum:
        raise ValueError('Unbounded trade list')
    return v

def _number(v):
    if type(v) not in (int, float) or not abs(v) < 1000000000000.0:
        raise ValueError('Invalid trade number')

def _yields(v):
    _shape(v, 'values majority_religion religion_pressure path_bonus tooltip')
    for n in _list(v['values'], 64):
        _number(n)
    if type(v['majority_religion']) is not int or not -1 <= v['majority_religion'] <= 2147483647:
        raise ValueError('Invalid trade religion')
    _number(v['religion_pressure'])
    if type(v['path_bonus']) is not bool or type(v['tooltip']) is not str or len(v['tooltip'].encode()) > 32768:
        raise ValueError('Invalid yield tooltip')

def validate_route_action(a, width=16384, height=16384):
    if type(a) is not dict or set(a) != ROUTE_FIELDS or a['kind'] != 'make_trade_route':
        raise ValueError('Invalid trade action')
    for k in ROUTE_FIELDS - {'kind'}:
        uint(a[k], k, 63 if k.endswith('_owner') else width - 1 if k.startswith('x') else height - 1 if k.startswith('y') else 4294967295)
    return a

def validate_routes(v, pid, turn):
    _shape(v, 'player_id turn width height traders active_routes')
    uint(pid, 'player', 63)
    uint(turn, 'turn', 2147483647)
    if type(v['player_id']) is not int or type(v['turn']) is not int or v['player_id'] != pid or (v['turn'] != turn):
        raise ValueError('Foreign trade catalogue')
    w = uint(v['width'], 'width', 16384)
    h = uint(v['height'], 'height', 16384)
    if not 0 < w * h <= 16384:
        raise ValueError('Invalid trade map')
    active = []
    for r in _list(v['active_routes']):
        _shape(r, 'unit_id origin_owner origin_city destination_owner destination_city')
        for k, n in r.items():
            uint(n, k, 63 if k.endswith('_owner') else 4294967295)
        if r['origin_owner'] != pid:
            raise ValueError('Foreign outgoing trade route')
        active.append(r['unit_id'])
    if active != sorted(set(active)):
        raise ValueError('Duplicate active traders')
    ids = []
    total = 0
    for t in _list(v['traders']):
        _shape(t, 'unit_id x y origin_owner origin_city destinations')
        for k in ('unit_id', 'origin_city'):
            uint(t[k], k)
        uint(t['origin_owner'], 'origin owner', 63)
        uint(t['x'], 'x', w - 1)
        uint(t['y'], 'y', h - 1)
        ids.append(t['unit_id'])
        destinations = []
        for d in _list(t['destinations']):
            _shape(d, 'owner city_id x y name path portal_entrances portal_exits repeat_route can_confirm has_post origin_yields destination_yields')
            uint(d['owner'], 'destination owner', 63)
            uint(d['city_id'], 'destination city')
            uint(d['x'], 'destination x', w - 1)
            uint(d['y'], 'destination y', h - 1)
            if type(d['name']) is not str or len(d['name'].encode()) > 32768:
                raise ValueError('Invalid trade city name')
            if any((type(d[k]) is not bool for k in ('repeat_route', 'can_confirm', 'has_post'))):
                raise ValueError('Invalid trade flags')
            if not d['repeat_route'] and (not d['can_confirm']):
                raise ValueError('Nonrepeat destination blocked')
            path = _list(d['path'], 16384)
            if not path or any((type(n) is not int or not 0 <= n < w * h for n in path)):
                raise ValueError('Invalid native trade path')
            for k in ('portal_entrances', 'portal_exits'):
                steps = []
                for portal in _list(d[k], len(path)):
                    _shape(portal, 'step plot')
                    uint(portal['step'], 'portal step', len(path))
                    if portal['step'] == 0 or type(portal['plot']) is not int or (not -1 <= portal['plot'] < w * h):
                        raise ValueError('Invalid portal')
                    steps.append(portal['step'])
                if steps != sorted(set(steps)):
                    raise ValueError('Duplicate portal step')
            _yields(d['origin_yields'])
            _yields(d['destination_yields'])
            destinations.append((d['owner'], d['city_id']))
            total += 1
        if destinations != sorted(set(destinations)):
            raise ValueError('Duplicate trade destination')
    if ids != sorted(set(ids)) or total > 4096:
        raise ValueError('Duplicate/unbounded trade roster')
    return v

def route_actions(v):
    validate_routes(v, v['player_id'], v['turn'])
    return [dict(kind='make_trade_route', unit_id=t['unit_id'], origin_owner=t['origin_owner'], origin_city=t['origin_city'], destination_owner=d['owner'], destination_city=d['city_id'], x0=d['x'], y0=d['y'], x1=t['x'], y1=t['y']) for t in v['traders'] for d in t['destinations'] if d['can_confirm']]

def compare_routes(v, obs):
    validate_routes(v, obs['player_id'], obs['turn'])
    units = {u['id']: (u['x'], u['y']) for u in obs['units']}
    cities = {c['id'] for c in obs['cities']}
    if (v['width'], v['height']) != (obs['width'], obs['height']) or any((units.get(t['unit_id']) != (t['x'], t['y']) for t in v['traders'])):
        raise ValueError('Trade roster differs from own observation')
    if any((r['origin_city'] not in cities for r in v['active_routes'])):
        raise ValueError('Outgoing route from absent own city')

def validate_origin_action(a, width, height):
    if type(a) is not dict or set(a) != ORIGIN_FIELDS or a['kind'] != 'change_trade_origin':
        raise ValueError('Malformed origin action')
    for k in ('unit_id', 'origin_city', 'destination_city'):
        uint(a[k], k)
    for k in ('x', 'source_x'):
        uint(a[k], k, width - 1)
    for k in ('y', 'source_y'):
        uint(a[k], k, height - 1)
    uint(a['plot_id'], 'plot', width * height - 1)
    if a['plot_id'] != a['y'] * width + a['x'] or a['destination_city'] == a['origin_city'] or (a['x'], a['y']) == (a['source_x'], a['source_y']):
        raise ValueError('Invalid origin destination')
    return a

def validate_origins(v, pid, turn):
    if type(v) is not dict or set(v) != {'player_id', 'turn', 'width', 'height', 'units'}:
        raise ValueError('Malformed origin catalogue')
    if type(v['player_id']) is not int or type(v['turn']) is not int or v['player_id'] != pid or (v['turn'] != turn):
        raise ValueError('Foreign origin catalogue')
    w = uint(v['width'], 'width', 16384)
    h = uint(v['height'], 'height', 16384)
    if not w or not h or w * h > 16384 or (type(v['units']) is not list) or (len(v['units']) > 4096):
        raise ValueError('Unbounded origin catalogue')
    ids = []
    total = 0
    for u in v['units']:
        if type(u) is not dict or set(u) != {'unit_id', 'origin_city', 'x', 'y', 'available', 'targets', 'map_targets'}:
            raise ValueError('Malformed origin unit')
        ids.append(uint(u['unit_id'], 'unit'))
        uint(u['origin_city'], 'city')
        uint(u['x'], 'x', w - 1)
        uint(u['y'], 'y', h - 1)
        if type(u['available']) is not bool or type(u['targets']) is not list or type(u['map_targets']) is not list:
            raise ValueError('Malformed origin targets')
        if len(u['map_targets']) > w * h or any((type(p) is not int or not 0 <= p < w * h for p in u['map_targets'])) or u['map_targets'] != sorted(set(u['map_targets'])):
            raise ValueError('Invalid origin highlights')
        if not u['available'] and (u['targets'] or u['map_targets']):
            raise ValueError('Unavailable origin exposes choices')
        cities = []
        for d in u['targets']:
            if type(d) is not dict or set(d) != {'city_id', 'x', 'y', 'plot_id', 'name'} or type(d['name']) is not str or (len(d['name'].encode('utf8')) > 32768):
                raise ValueError('Malformed origin city')
            validate_origin_action(_action(u, d), w, h)
            cities.append(d['city_id'])
            total += 1
        if cities != sorted(set(cities)):
            raise ValueError('Duplicate origin city')
    if ids != sorted(set(ids)) or total > 4096:
        raise ValueError('Duplicate/unbounded origin units')
    return v

def _action(u, d):
    return dict(kind='change_trade_origin', unit_id=u['unit_id'], origin_city=u['origin_city'], source_x=u['x'], source_y=u['y'], destination_city=d['city_id'], x=d['x'], y=d['y'], plot_id=d['plot_id'])

def origin_actions(v):
    validate_origins(v, v['player_id'], v['turn'])
    return [_action(u, d) for u in v['units'] for d in u['targets']]

def compare_origins(v, obs):
    validate_origins(v, obs['player_id'], obs['turn'])
    units = {u['id']: (u['x'], u['y']) for u in obs['units']}
    cities = {c['id']: (c['x'], c['y']) for c in obs['cities']}
    if (v['width'], v['height']) != (obs['width'], obs['height']):
        raise ValueError('Origin grid differs')
    for u in v['units']:
        if units.get(u['unit_id']) != (u['x'], u['y']) or cities.get(u['origin_city']) != (u['x'], u['y']):
            raise ValueError('Origin unit/city absent from own observation')
        if any((cities.get(d['city_id']) != (d['x'], d['y']) for d in u['targets'])):
            raise ValueError('Origin destination is not an observed own city')


def validate_decisions(decisions, observation, *, actions_closed):
    """Bind trade state and offered commands to this player's observation."""
    catalogue_families = (
        ('trade_routes', 'make_trade_route', compare_routes, route_actions),
        ('trade_origins', 'change_trade_origin', compare_origins, origin_actions),
    )
    for field, kind, compare, actions in catalogue_families:
        offered = [row['action'] for row in decisions['candidates'] if row['action'].get('kind') == kind]
        catalogue = decisions.get(field)
        if catalogue is None:
            if offered:
                raise ValueError('Trade action lacks its native catalogue: ' + kind)
            continue
        compare(catalogue, observation)
        expected = [] if actions_closed else actions(catalogue)
        if offered != expected:
            raise ValueError('Trade choices differ from the native catalogue: ' + kind)
