"""Public UnitPanel result text and visible own-unit terrain state."""
SCHEMA = 'civ6-host.unit-work-info.v1'
MAX_BYTES = 4 * 1024 * 1024


def validate(value, player_id, turn, *, work_catalog, observation=None, work_state=None):
    if (type(value) is not dict or set(value) != {'schema','player_id','turn','offers','targets'}
            or value['schema'] != SCHEMA or type(value['player_id']) is not int
            or value['player_id'] != player_id or type(value['turn']) is not int
            or value['turn'] != turn):
        raise ValueError('Foreign public unit-work information')
    if (work_catalog is None or work_catalog['player_id'] != player_id
            or work_catalog['turn'] != turn):
        raise ValueError('Unit-work information lacks its exact catalogue')
    rows=value['offers']; targets=value['targets']
    if (type(rows) is not list or len(rows)>4096 or len(rows)!=len(work_catalog['offers'])
            or type(targets) is not list or len(targets)>4096):
        raise ValueError('Unbounded or incomplete unit-work information')
    def text(s):
        if type(s) is not str or len(s.encode('utf-8'))>4096 or '\x00' in s:
            raise ValueError('Invalid public UnitPanel text')
    for row,offer in zip(rows,work_catalog['offers']):
        if (type(row) is not dict or set(row)!={'action','legal','action_name','feature','descriptions','failure_reasons'}
                or type(row['legal']) is not bool or row['legal']!=offer['legal']
                or row['action']!=offer['action']):
            raise ValueError('Unit-work information differs from native offer')
        if row['action_name'] is not None:text(row['action_name'])
        feature=row['feature']
        if feature is not None:
            if (type(feature) is not dict or set(feature)!={'index','name'}
                    or type(feature['index']) is not int or not 0<=feature['index']<2**31):
                raise ValueError('Invalid public UnitPanel feature')
            text(feature['name'])
        for key in ('descriptions','failure_reasons'):
            if type(row[key]) is not list or len(row[key])>64:
                raise ValueError('Unbounded UnitPanel descriptions')
            for s in row[key]:text(s)
        if row['legal'] and row['failure_reasons']:
            raise ValueError('Enabled UnitPanel action exposes undisplayed failures')
    by_unit={}
    for row in targets:
        if type(row) is not dict or set(row)!={'unit_id','plot_id','improvement','improvement_pillaged','route','route_pillaged'}:
            raise ValueError('Invalid public unit-work target')
        for key in ('unit_id','plot_id'):
            if type(row[key]) is not int or not 0<=row[key]<2**32:
                raise ValueError('Invalid work target identity')
        for key in ('improvement','route'):
            if type(row[key]) is not int or not -1<=row[key]<2**31:
                raise ValueError('Invalid work target definition')
            if type(row[key+'_pillaged']) is not bool:
                raise ValueError('Invalid work target pillage state')
        if row['unit_id'] in by_unit:raise ValueError('Duplicate work target unit')
        by_unit[row['unit_id']]=row
    if work_state is not None:
        fields = ('unit_id', 'plot_id', 'improvement', 'improvement_pillaged',
                  'route', 'route_pillaged')
        state_targets = {row['unit_id']: {key: row[key] for key in fields}
                         for row in work_state['units']}
        if state_targets != by_unit:
            raise ValueError('UnitPanel targets differ from own-unit work state')
    if observation is not None:
        if observation['player_id']!=player_id or observation['turn']!=turn:
            raise ValueError('Work information observation differs')
        own={u['id']:u for u in observation['units']}
        plots={p['index']:p for p in observation['plots']}
        if len(own)!=len(observation['units']) or set(own)!=set(by_unit):
            raise ValueError('Work targets do not cover exactly own public units')
        for uid,u in own.items():
            row=by_unit[uid];plot=plots.get(row['plot_id'])
            if (u['owner']!=player_id or row['plot_id']!=u['y']*observation['width']+u['x']
                    or plot is None or plot['visible'] is not True):
                raise ValueError('Work target is not the visible own-unit tile')
    return value
