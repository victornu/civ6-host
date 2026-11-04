"""Portable action and catalogue contracts for city and district ranged shots."""

LAN_UNQUALIFIED_KINDS = ('city_range_attack', 'district_range_attack')
LAN_UNQUALIFIED_REASON = 'native_lan_ranged_shot_not_yet_qualified'

CITY_FIELDS = {'kind', 'city_id', 'plot_id', 'x', 'y'}

CITY_SHOOTER_FIELDS = {'city_id', 'district_id', 'x', 'y', 'available', 'targets'}


def uint(v, label, maximum=4294967295):
    if type(v) is not int or not 0 <= v <= maximum:
        raise ValueError('Invalid city-shot ' + label)
    return v


def city_validate_action(a, width=16384, height=16384):
    if type(a) is not dict or set(a) != CITY_FIELDS or a['kind'] != 'city_range_attack':
        raise ValueError('Invalid city-shot action')
    for k in CITY_FIELDS - {'kind'}:
        uint(a[k], k)
    if a['x'] >= width or a['y'] >= height or a['plot_id'] >= 16384 or (width != 16384 and a['plot_id'] != a['y'] * width + a['x']):
        raise ValueError('City-shot target outside map')
    return a


def city_validate_catalog(v, pid, turn):
    uint(pid, 'player', 63)
    uint(turn, 'turn', 2147483647)
    if type(v) is not dict or set(v) != {'player_id', 'turn', 'width', 'height', 'cities'} or type(v['player_id']) is not int or (v['player_id'] != pid) or (type(v['turn']) is not int) or (v['turn'] != turn):
        raise ValueError('Foreign city-shot catalogue')
    w = uint(v['width'], 'width', 16384)
    h = uint(v['height'], 'height', 16384)
    if not 0 < w * h <= 16384 or type(v['cities']) is not list or len(v['cities']) > 4096:
        raise ValueError('Unbounded city-shot map/roster')
    ids = []
    districts = []
    total = 0
    for c in v['cities']:
        if type(c) is not dict or set(c) != CITY_SHOOTER_FIELDS or type(c['available']) is not bool:
            raise ValueError('Invalid shooter')
        uint(c['city_id'], 'city')
        uint(c['district_id'], 'center')
        uint(c['x'], 'source x', w - 1)
        uint(c['y'], 'source y', h - 1)
        ids.append(c['city_id'])
        districts.append(c['district_id'])
        targets = c['targets']
        if type(targets) is not list or any((type(t) is not int or not 0 <= t < w * h for t in targets)) or targets != sorted(set(targets)) or (targets and (not c['available'])):
            raise ValueError('Invalid native city targets')
        total += len(targets)
    if ids != sorted(set(ids)) or len(set(districts)) != len(districts) or total > 4096:
        raise ValueError('Duplicate/unbounded city shots')
    return v


def city_actions(v):
    city_validate_catalog(v, v['player_id'], v['turn'])
    return [dict(kind='city_range_attack', city_id=c['city_id'], plot_id=t, x=t % v['width'], y=t // v['width']) for c in v['cities'] for t in c['targets']]


def city_compare_own_cities(v, obs):
    city_validate_catalog(v, obs['player_id'], obs['turn'])
    if (v['width'], v['height']) != (obs['width'], obs['height']) or [(c['city_id'], c['x'], c['y']) for c in v['cities']] != sorted(((c['id'], c['x'], c['y']) for c in obs['cities'])):
        raise ValueError('City-shot map/roster differs from own observation')

DISTRICT_FIELDS = {'kind', 'district_id', 'plot_id', 'x', 'y'}

DISTRICT_ROW_FIELDS = {'district_id', 'city_id', 'type_index', 'x', 'y', 'complete', 'banner_eligible', 'available', 'targets'}


def district_validate_action(a, width=16384, height=16384):
    if type(a) is not dict or set(a) != DISTRICT_FIELDS or a['kind'] != 'district_range_attack':
        raise ValueError('Invalid district-shot action')
    for k in DISTRICT_FIELDS - {'kind'}:
        uint(a[k], k)
    if a['x'] >= width or a['y'] >= height or a['plot_id'] >= 16384 or (width != 16384 and a['plot_id'] != a['y'] * width + a['x']):
        raise ValueError('District-shot target outside map')
    return a


def district_validate_catalog(v, pid, turn):
    uint(pid, 'player', 63)
    uint(turn, 'turn', 2147483647)
    if type(v) is not dict or set(v) != {'player_id', 'turn', 'width', 'height', 'districts'} or type(v['player_id']) is not int or (v['player_id'] != pid) or (type(v['turn']) is not int) or (v['turn'] != turn):
        raise ValueError('Foreign district-shot catalogue')
    w = uint(v['width'], 'width', 16384)
    h = uint(v['height'], 'height', 16384)
    if not 0 < w * h <= 16384 or type(v['districts']) is not list or len(v['districts']) > 4096:
        raise ValueError('Unbounded district-shot map/roster')
    ids = []
    plots = []
    total = 0
    for d in v['districts']:
        if type(d) is not dict or set(d) != DISTRICT_ROW_FIELDS or any((type(d[k]) is not bool for k in ('complete', 'banner_eligible', 'available'))):
            raise ValueError('Invalid district shooter')
        uint(d['district_id'], 'district')
        uint(d['city_id'], 'city')
        uint(d['type_index'], 'type', 2147483647)
        uint(d['x'], 'source x', w - 1)
        uint(d['y'], 'source y', h - 1)
        ids.append(d['district_id'])
        plots.append(d['y'] * w + d['x'])
        if d['available'] and (not d['banner_eligible']) or (d['banner_eligible'] and (not d['complete'])):
            raise ValueError('District shot bypasses banner')
        targets = d['targets']
        if type(targets) is not list or any((type(t) is not int or not 0 <= t < w * h for t in targets)) or targets != sorted(set(targets)) or (targets and (not d['available'])):
            raise ValueError('Invalid native district targets')
        total += len(targets)
    if ids != sorted(set(ids)) or len(set(plots)) != len(plots) or total > 4096:
        raise ValueError('Duplicate/unbounded district shots')
    return v


def district_actions(v):
    district_validate_catalog(v, v['player_id'], v['turn'])
    return [dict(kind='district_range_attack', district_id=d['district_id'], plot_id=t, x=t % v['width'], y=t // v['width']) for d in v['districts'] for t in d['targets']]


def district_compare_own_cities(v, obs):
    district_validate_catalog(v, obs['player_id'], obs['turn'])
    cities = {c['id']: (c['x'], c['y']) for c in obs['cities']}
    if (v['width'], v['height']) != (obs['width'], obs['height']) or any((d['city_id'] not in cities or (d['x'], d['y']) == cities[d['city_id']] for d in v['districts'])):
        raise ValueError('Independent district map/city ownership differs')
