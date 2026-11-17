"""Public own-religion state and native offered beliefs; no engine imports.

This additive group does not claim prophet activation or religion founding.
Runtime collectors, rather than this contract, determine available choices.
"""
from copy import deepcopy

SCHEMA = 'civ6-host.religion-beliefs.v1'
KIND = 'add_belief'
FIELDS = {'kind', 'index', 'hash', 'class'}
_NATIVE_META = {'observation_only', 'action_effect_verified', 'source_proof_sha256',
                'exposed_to_learner', 'eligible_for_training'}
HOLY_CITY_DISPLAY_LABEL = 'holy_city_display_label'
MAX_HOLY_CITY_LABEL_BYTES = 1024
_OWN_FIELDS = {'religion_type_created', 'has_religious_founding_unit',
               'num_beliefs_earned', 'holy_city', 'holy_city_present', 'own_religion'}


def _int(value, low=0, high=0x7fffffff):
    if type(value) is not int or not low <= value <= high:
        raise ValueError('Religion integer is outside its native domain')
    return value


def _keys(value, expected):
    if type(value) is not dict or set(value) != set(expected):
        raise ValueError('Religion fields differ from the public contract')


def _indices(value):
    if type(value) is not list or len(value)>4096:
        raise ValueError('Invalid belief index list')
    for index in value:
        _int(index)
    if len(set(value)) != len(value):
        raise ValueError('Duplicate belief index')


def holy_city_label_bytes(label):
    if type(label) is not str or not 0 < len(label) <= MAX_HOLY_CITY_LABEL_BYTES or '\x00' in label:
        raise ValueError('Malformed holy city display label')
    raw = label.encode('utf-8')
    if len(raw) > MAX_HOLY_CITY_LABEL_BYTES:
        raise ValueError('Holy city display label exceeds its byte bound')
    return raw


def _own_fields(value):
    if type(value) is dict and HOLY_CITY_DISPLAY_LABEL in value:
        return _OWN_FIELDS | {HOLY_CITY_DISPLAY_LABEL}
    return _OWN_FIELDS


def _own(value, pid, observation):
    _keys(value, _own_fields(value))
    created=_int(value['religion_type_created'],-1)
    _int(value['num_beliefs_earned'])
    if (type(value['has_religious_founding_unit']) is not bool
            or type(value['holy_city_present']) is not bool):
        raise ValueError('Religion flags must be native booleans')
    holy=value['holy_city'];_keys(holy,{'player','type','id'})
    owner=_int(holy['player'],-1,63);city_id=_int(holy['id'],-1)
    if type(holy['type']) is not int or holy['type'] != 2:
        raise ValueError('Holy city descriptor is not a city')
    if not (owner == -1 and city_id == -1 or owner == pid and city_id >= 0):
        raise ValueError('The qualified reader requires an owned or absent holy city')
    if value['holy_city_present'] is not (city_id >= 0):
        raise ValueError('Holy city presence differs from its descriptor')
    if HOLY_CITY_DISPLAY_LABEL in value:
        if created == -1 or city_id != -1:
            raise ValueError('A holy city display label requires a founded religion and no own-city descriptor')
        holy_city_label_bytes(value[HOLY_CITY_DISPLAY_LABEL])
    if observation is not None:
        if (type(observation) is not dict or observation.get('player_id') != pid
                or type(observation.get('player_id')) is not int):
            raise ValueError('Foreign religion observation')
        cities=observation.get('cities')
        if type(cities) is not list or any(type(c) is not dict or type(c.get('id')) is not int
                or type(c.get('owner')) is not int or c['owner']!=pid for c in cities):
            raise ValueError('Malformed public own-city set')
        if city_id >= 0 and not any(c['id']==city_id and c['owner']==pid for c in cities):
            raise ValueError('Holy city is absent from the public own-city set')
    own=value['own_religion']
    if created == -1:
        if own is not None:
            raise ValueError('Absent founded religion contains beliefs')
    else:
        _keys(own,{'religion_index','founder','belief_indices'})
        if (_int(own['religion_index']) != created or _int(own['founder'],0,63) != pid):
            raise ValueError('Foreign founded religion')
        _indices(own['belief_indices'])
    return value


def project_snapshot(native, player_id, turn, *, observation=None):
    """Remove diagnostic/proof metadata explicitly from the actor-facing value."""
    _int(player_id,0,63);_int(turn,0,0xffffffff)
    fields = _own_fields(native)
    _keys(native, fields | _NATIVE_META | {'player_id','current_game_turn'})
    if (_int(native['player_id'],0,63) != player_id
            or _int(native['current_game_turn'],0,0xffffffff) != turn):
        raise ValueError('Foreign or stale own-religion snapshot')
    if observation is not None:
        if type(observation) is not dict or type(observation.get('turn')) is not int or observation['turn']!=turn:
            raise ValueError('Stale public religion observation')
    if any(type(native[k]) is not bool for k in _NATIVE_META-{'source_proof_sha256'}):
        raise ValueError('Malformed diagnostic metadata')
    digest=native['source_proof_sha256']
    if type(digest) is not str or len(digest)!=64 or any(c not in '0123456789abcdef' for c in digest):
        raise ValueError('Malformed source identity')
    result=deepcopy({k:native[k] for k in fields})
    return _own(result,player_id,observation)


def validate_action(action):
    _keys(action,FIELDS)
    if action['kind'] != KIND:
        raise ValueError('Unexpected religious action')
    _int(action['index']);_int(action['hash'],0,0xffffffff)
    cls=action['class']
    if type(cls) is not str or not 0<len(cls)<=64 or any(c not in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_' for c in cls):
        raise ValueError('Malformed native belief class')
    return action


def _beliefs(value, own, pid, turn):
    if own['religion_type_created'] == -1:
        if value is not None:
            raise ValueError('Belief choices lack an own founded religion')
        return
    common={'status','player_id','current_game_turn','religion_index','num_beliefs_earned',
            'equipped_count','equipped_beliefs','candidates'}
    if type(value) is not dict:
        raise ValueError('Founded religion lacks its queried belief state')
    if value.get('status')=='not_due':
        _keys(value,common|{'reason'})
        if value['reason']!='no_unspent_belief' or value['candidates']!=[] or value['equipped_beliefs']!=[]:
            raise ValueError('Malformed not-due native belief state')
    elif value.get('status')=='catalog':
        _keys(value,common|{'remaining_slots','operation','belief_parameter','insert_parameter','exclusive_value'})
        _int(value['num_beliefs_earned']);_int(value['equipped_count'],0,4096)
        for k in ('operation','belief_parameter','insert_parameter','exclusive_value'):
            _int(value[k],0,0xffffffff)
        if value['belief_parameter']==value['insert_parameter']:
            raise ValueError('Belief parameter keys collide')
        if _int(value['remaining_slots'],1)!=value['num_beliefs_earned']-value['equipped_count']:
            raise ValueError('Native belief counters disagree')
        if value['equipped_beliefs']!=own['own_religion']['belief_indices']:
            raise ValueError('Belief catalogue differs from own native beliefs')
    else:
        raise ValueError('Unknown native belief query state')
    if (_int(value['player_id'],0,63)!=pid or _int(value['current_game_turn'],0,0xffffffff)!=turn
            or _int(value['religion_index'])!=own['religion_type_created']
            or _int(value['num_beliefs_earned'])!=own['num_beliefs_earned']
            or _int(value['equipped_count'],0,4096)!=len(own['own_religion']['belief_indices'])):
        raise ValueError('Foreign or inconsistent belief catalogue')
    _indices(value['equipped_beliefs'])
    if value['status']=='not_due' and value['num_beliefs_earned']!=value['equipped_count']:
        raise ValueError('Not-due native state has unspent beliefs')
    rows=value['candidates']
    if type(rows) is not list or len(rows)>4096 or value['status']=='catalog' and not rows:
        raise ValueError('Malformed native belief candidates')
    indices=[];hashes=[]
    for row in rows:
        _keys(row,{'index','hash','class'});validate_action(dict(kind=KIND,**row))
        indices.append(row['index']);hashes.append(row['hash'])
    if indices!=sorted(set(indices)) or len(set(hashes))!=len(hashes) or set(indices)&set(value['equipped_beliefs']):
        raise ValueError('Duplicate, unordered or equipped belief offered')


def validate(value, player_id, turn, *, observation=None):
    _int(player_id,0,63);_int(turn,0,0xffffffff)
    _keys(value,{'schema','player_id','turn','own','beliefs'})
    if (value['schema']!=SCHEMA or _int(value['player_id'],0,63)!=player_id
            or _int(value['turn'],0,0xffffffff)!=turn):
        raise ValueError('Foreign public religion boundary')
    if observation is not None:
        if type(observation) is not dict or type(observation.get('turn')) is not int or observation['turn']!=turn:
            raise ValueError('Stale public religion observation')
    _own(value['own'],player_id,observation)
    _beliefs(value['beliefs'],value['own'],player_id,turn)
    return value


def actions(value):
    if value is None or value['beliefs'] is None:
        return []
    return [dict(kind=KIND,**row) for row in value['beliefs']['candidates']]
