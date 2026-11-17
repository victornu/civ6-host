"""Public UnitPanel result text and visible own-unit terrain state."""
SCHEMA = 'civ6-host.unit-work-info.v1'
VISIBLE_WORK_SCHEMA = 'civ6-host.unit-work-info.v2'
MAX_BYTES = 4 * 1024 * 1024
_PLOT_FIELDS = {'plot_id', 'improvement', 'improvement_pillaged', 'route', 'route_pillaged'}


def validate(value, player_id, turn, *, work_catalog, observation=None, work_state=None,
             visible_work=False):
    fields = {'schema', 'player_id', 'turn', 'offers', 'targets'}
    if visible_work:
        fields.add('visible_plots_with_work')
    if (type(value) is not dict or set(value) != fields
            or value['schema'] != (VISIBLE_WORK_SCHEMA if visible_work else SCHEMA)
            or type(value['player_id']) is not int
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
    if visible_work:
        visible = value['visible_plots_with_work']
        if type(visible) is not list or len(visible) > 16384:
            raise ValueError('Unbounded visible work plots')
        sparse = {}
        previous = -1
        for row in visible:
            if (type(row) is not dict or set(row) != _PLOT_FIELDS
                    or type(row['plot_id']) is not int or not previous < row['plot_id'] < 16384
                    or (observation is not None
                        and (row['plot_id'] not in plots or plots[row['plot_id']]['visible'] is not True))):
                raise ValueError('Visible work plot identity differs')
            previous = row['plot_id']
            for key in ('improvement', 'route'):
                if (type(row[key]) is not int or not -1 <= row[key] < 2**31
                        or type(row[key + '_pillaged']) is not bool):
                    raise ValueError('Invalid visible plot work')
            if row['improvement'] == row['route'] == -1 and not (
                    row['improvement_pillaged'] or row['route_pillaged']):
                raise ValueError('Sparse visible work has a default row')
            sparse[previous] = row
        for row in targets:
            blank = dict(plot_id=row['plot_id'], improvement=-1, route=-1,
                         improvement_pillaged=False, route_pillaged=False)
            if sparse.get(row['plot_id'], blank) != {key: row[key] for key in _PLOT_FIELDS}:
                raise ValueError('Visible work differs from the own-unit tile')
    return value
