"""Reuse the Base CityPanel focus and PlotInfo MANAGE public contracts."""
from .city_controls_base import focus, citizens

ACTION_FIELDS={'city_focus':frozenset(focus.FIELDS),'city_citizen':frozenset(citizens.FIELDS)}


def validate_action(action):
    if type(action) is not dict or action.get('kind') not in ACTION_FIELDS:
        raise ValueError('Unknown city-control action')
    return (focus.validate_action if action['kind']=='city_focus' else citizens.validate_action)(action)


def validate_catalogs(focus_catalogs,citizen_catalogs,player_id,turn,*,observation,unavailable=False,own_city_ids=None):
    if type(unavailable) is not bool:raise TypeError('City-control availability must be Boolean')
    if unavailable:
        if focus_catalogs is not None or citizen_catalogs is not None:
            raise ValueError('Unavailable city controls cannot substitute observed catalogues')
        return {'city_focus':[],'city_citizen':[]}
    if observation is not None:
        if type(observation) is not dict or observation.get('player_id')!=player_id or observation.get('turn')!=turn:
            raise ValueError('City controls require their actual player observation')
        own=sorted(c['id'] for c in observation['cities'])
        if own_city_ids is not None and own!=own_city_ids:raise ValueError('City controls and current production rosters differ')
    elif type(own_city_ids) is list and own_city_ids==sorted(set(own_city_ids)):
        # The existing protocol revalidates a previously accepted catalogue
        # without its observation. Its validated current-production state still
        # carries the exact own-city roster; no dummy observation is fabricated.
        own=own_city_ids
    else:raise ValueError('City controls require their own-city observation or validated choice roster')
    result={}
    for kind,catalogs,module in (('city_focus',focus_catalogs,focus),('city_citizen',citizen_catalogs,citizens)):
        if catalogs is None:
            result[kind]=[];continue
        if type(catalogs) is not list or len(catalogs)>4096:
            raise ValueError('Unbounded city-control catalogues')
        ids=[];actions=[]
        for catalog in catalogs:
            module.validate_catalog(catalog,player_id,turn);ids.append(catalog['city_id'])
            if kind=='city_citizen' and observation is not None:
                width,height=observation['width'],observation['height']
                for row in catalog['plots']:
                    if not (row['x']<width and row['y']<height and row['plot_id']==row['y']*width+row['x']):
                        raise ValueError('Citizen target is outside its native map coordinates')
            actions.extend(module.actions(catalog))
        if ids!=own or len(set(ids))!=len(ids):
            raise ValueError('City-control catalogues differ from the exact own-city roster')
        result[kind]=actions
    if citizen_catalogs is not None and focus_catalogs is None:
        raise ValueError('Citizen controls require the complete city-focus group')
    return result


def validate_families(value,player_id,turn,*,observation,unavailable):
    offers=validate_catalogs(value['city_focus_catalogs'],value['citizen_catalogs'],player_id,turn,
        observation=observation,unavailable=unavailable,own_city_ids=(
            [r['city_id'] for r in value['choice_state']['production']] if value['choice_state'] is not None else None))
    for kind,key in (('city_focus','city_focus_catalogs'),('city_citizen','citizen_catalogs')):
        family=value['families'].get(kind)
        available=not unavailable and value[key] is not None
        if type(family) is not dict or family.get('status')!=('queried_complete' if available else 'unqualified'):
            raise ValueError('City-control family does not match its actual native query')
        actual=[row['action'] for row in value['candidates'] if row['action']['kind']==kind]
        if actual!=offers[kind]:raise ValueError('City-control candidates omit or invent a displayed native choice')
    return offers
