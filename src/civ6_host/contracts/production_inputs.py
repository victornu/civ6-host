"""Player production inputs; diagnostic getter rows never enter this schema."""
import copy
from . import production_info988 as legacy

INFO_SCHEMA = 'civ6-host.production-info.v1'
CURRENT_SCHEMA = 'civ6-host.current-production.v1'


def _int(value, minimum=0, maximum=0x7fffffff):
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError('Invalid production integer')
    return value


def _own(observation, pid, turn):
    if (type(observation) is not dict or observation.get('player_id') != pid
            or observation.get('turn') != turn or type(observation.get('cities')) is not list):
        raise ValueError('Production observation identity differs')
    ids=[]
    for row in observation['cities']:
        if type(row) is not dict or row.get('owner') != pid:
            raise ValueError('Foreign production city')
        ids.append(_int(row.get('id'),maximum=0xffffffff))
    if len(ids)>4096 or len(ids)!=len(set(ids)):
        raise ValueError('Unbounded or duplicate production cities')
    return set(ids)


def project_quotes(value, pid, turn, **kwargs):
    """Validate the original source-bound values before dropping the raw lane."""
    legacy.validate(value,pid,turn,**kwargs)
    result={k:copy.deepcopy(v) for k,v in value.items() if k not in ('rows','schema')}
    result.update(schema=INFO_SCHEMA,rows=[{k:copy.deepcopy(v) for k,v in r.items() if k!='raw'} for r in value['rows']])
    return validate_quotes(result,pid,turn,**kwargs)


def validate_quotes(value,pid,turn,candidates=None,observation=None,*,ended=False):
    _int(pid,maximum=63);_int(turn)
    fields={'schema','player_id','turn','source_sha256','ui_sha256','tooltip_sha256','rows'}
    if (type(value) is not dict or set(value)!=fields or value['schema']!=INFO_SCHEMA
            or type(value['player_id']) is not int or value['player_id']!=pid
            or type(value['turn']) is not int or value['turn']!=turn or type(ended) is not bool
            or value['source_sha256']!=legacy.PROOF_SHA256 or value['ui_sha256']!=legacy.PANEL_SHA256
            or value['tooltip_sha256']!=legacy.TOOLTIP_SHA256):
        raise ValueError('Unknown public production information')
    rows=value['rows']
    if type(rows) is not list or len(rows)>legacy.MAX_ROWS:raise ValueError('Unbounded production quotes')
    keys=[]
    for row in rows:
        if type(row) is not dict or set(row)!=set(legacy._KEYS)|{'public'}:
            raise ValueError('Production quote contains raw or unknown fields')
        keys.append(legacy.quote_key(row));p=row['public']
        if type(p) is not dict or set(p)!=legacy._PUBLIC_FIELDS:raise ValueError('Unknown displayed production fields')
        for key in ('cost','progress','turns_left'):
            if p[key] is not None:_int(p[key],minimum=-(1<<31))
        if type(p['never_completes']) is not bool or p['never_completes']!=(p['turns_left'] is None):
            raise ValueError('Production turn display differs')
        if p['cost_kind'] not in (None,'base','production') or (p['cost'] is None)!=(p['cost_kind'] is None):
            raise ValueError('Production cost display differs')
        if p['progress'] is not None and (p['progress']<=0 or p['cost_kind']!='production'):
            raise ValueError('Progress is not displayed by the official tooltip')
        if p['cost_kind']=='base' and row['category']!='unit':raise ValueError('Non-unit base tooltip cost')
    if keys!=sorted(set(keys)):raise ValueError('Production quote identity order differs')
    if observation is not None:
        own=_own(observation,pid,turn)
        if any(k[0] not in own for k in keys):raise ValueError('Production quote belongs to a foreign city')
    if candidates is not None:
        offered,_=legacy._candidate_keys(candidates)
        if (ended and candidates) or (not ended and offered!=set(keys)):
            raise ValueError('Production quotes do not match available actions')
    return value


def validate(value,pid,turn,**kwargs):
    """Explicit compatibility for preserved historical diagnostic protocols."""
    if type(value) is dict and value.get('schema')==INFO_SCHEMA:
        return validate_quotes(value,pid,turn,**kwargs)
    return legacy.validate(value,pid,turn,**kwargs)


def validate_current(value,pid,turn,*,observation=None,queues=None):
    _int(pid,maximum=63);_int(turn)
    if (type(value) is not dict or set(value)!={'schema','player_id','turn','cities'}
            or value['schema']!=CURRENT_SCHEMA or type(value['player_id']) is not int or value['player_id']!=pid
            or type(value['turn']) is not int or value['turn']!=turn
            or type(value['cities']) is not list or len(value['cities'])>4096):
        raise ValueError('Malformed public current production')
    ids=[]
    for row in value['cities']:
        if type(row) is not dict or set(row)!={'city_id','state','item'}:raise ValueError('Unknown current production fields')
        ids.append(_int(row['city_id'],maximum=0xffffffff));item=row['item']
        if row['state']=='empty':
            if item is not None:raise ValueError('Empty production has an item')
            continue
        if row['state'] not in ('current','completed'):raise ValueError('Unknown production display state')
        if type(item) is not dict or set(item)!={'category','index','hash','item_type','name','formation','progress','cost','turns_left','never_completes'}:
            raise ValueError('Unknown current production item fields')
        legacy.quote_key(dict(item,city_id=row['city_id']))
        if type(item['name']) is not str or not 1<=len(item['name'].encode('utf-8'))<=4096:raise ValueError('Invalid production name')
        if item['formation'] not in (None,'single','corps','army','unsuffixed') or (item['formation'] is None)!=(item['category']!='unit'):
            raise ValueError('Unknown displayed military formation')
        if item['formation']=='unsuffixed' and item['cost']!=0:
            raise ValueError('Unclassified formation differs from official zero-cost display')
        _int(item['progress'],minimum=-(1<<31));_int(item['cost'],minimum=-(1<<31))
        if item['turns_left'] is not None:_int(item['turns_left'],minimum=-(1<<31))
        if type(item['never_completes']) is not bool or item['never_completes']!=(item['turns_left'] is None):
            raise ValueError('Current production turns differ')
    if ids!=sorted(set(ids)):raise ValueError('Production cities are not uniquely sorted')
    if observation is not None and set(ids)!=_own(observation,pid,turn):raise ValueError('Current production city roster differs')
    if queues is not None:
        if type(queues) is not list or len(queues)!=len(ids):raise ValueError('Missing production queue roster')
        by_id={q['city_id']:q for q in queues}
        if set(by_id)!=set(ids):raise ValueError('Production queue identities differ')
        for row in value['cities']:
            entries=by_id[row['city_id']]['entries']
            if bool(entries)!=(row['state']=='current'):raise ValueError('Queue head and production display state differ')
            if entries:
                head=entries[0];item=row['item']
                if any(head[k]!=item[k] for k in ('category','index','hash')):raise ValueError('Production display differs from queue head')
    return value
