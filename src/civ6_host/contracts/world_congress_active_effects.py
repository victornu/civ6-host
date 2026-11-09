"""Player-visible Current Effects cards, distinct from historical votes."""
from .world_congress_review import _fields, _integer, _text, _boolean, _rows, _target, _reference

SCHEMA = 'civ6-host.world-congress-active-effects.v1'
STATUSES = ('available','waiting_or_closed','active_effects_ui_unavailable')
PROPOSALS_STATUS = 'available'


def validate_catalogue(value, player_id, turn, sequence):
    _integer(player_id,63);_integer(turn);_integer(sequence,0xffffffff)
    _fields(value,'schema player_id turn sequence turn_segment meeting_turns_left resolutions proposals proposals_status')
    if value['schema'] != SCHEMA:
        raise ValueError('Congress active effects schema differs')
    for key,expected in (('player_id',player_id),('turn',turn),('sequence',sequence)):
        if type(value[key]) is not int or value[key] != expected:
            raise ValueError('Congress active effects crossed observation identity')
    _integer(value['turn_segment'],0xffffffff)
    _integer(value['meeting_turns_left'],minimum=-0x80000000)
    if value['proposals_status'] != PROPOSALS_STATUS:
        raise ValueError('Congress active proposal summary availability differs')
    for index,row in enumerate(_rows(value['resolutions'])):
        _fields(row,'index resolution_type name target_type chosen_option chosen_label chosen_target is_new turns_left')
        if type(row['index']) is not int or row['index'] != index:
            raise ValueError('Congress active effect display index differs')
        for key in ('resolution_type','name','target_type','chosen_option','chosen_label'):_text(row[key])
        _target(row['chosen_target'],row['target_type']=='PlayerType')
        _boolean(row['is_new'])
        _integer(row['turns_left'],0x80000000,1-0x80000000)
        if row['turns_left'] != value['meeting_turns_left']+1:
            raise ValueError('Congress active duration differs from the official display')
    for index,row in enumerate(_rows(value['proposals'])):
        _fields(row,'index category_type category_name type_name name target is_new description turns_left emergency_type goals crisis_details rewards_details')
        if type(row['index']) is not int or row['index'] != index:
            raise ValueError('Congress active proposal display index differs')
        for key in ('category_type','category_name','type_name','name','description','emergency_type'):_text(row[key])
        if row['target'] is not None:_reference(row['target'])
        _boolean(row['is_new']);_integer(row['turns_left'],minimum=-0x80000000)
        for goal in _rows(row['goals']):
            _fields(goal,'name completed');_text(goal['name']);_boolean(goal['completed'])
            if not goal['name']:raise ValueError('Congress active proposal goal is not displayed')
        for key in ('crisis_details','rewards_details'):
            for line in _rows(row[key]):_text(line)
    return value


def compare_own(value, observation, sequence):
    if type(observation) is not dict:
        raise ValueError('Congress active effects require an observation object')
    return validate_catalogue(value,observation.get('player_id'),observation.get('turn'),sequence)


def validate_group(value,status,congress,player_id,turn,sequence):
    if type(status) is not str or status not in STATUSES:
        raise ValueError('Unknown Congress active effects availability')
    if (value is None) != (status != 'available'):
        raise ValueError('Congress active effects data and availability differ')
    if (congress is None) != (status=='waiting_or_closed'):
        raise ValueError('Congress active effects waiting boundary differs')
    if congress is not None:
        from .world_congress import validate_catalogue as validate_congress
        validate_congress(congress,player_id,turn,sequence)
    if value is not None:
        if congress['stage'] != 'ordinary' or congress['paused'] or not congress['local_alive']:
            raise ValueError('Congress active effects are unavailable in this UI phase')
        validate_catalogue(value,player_id,turn,sequence)
        if value['turn_segment'] != congress['turn_segment']:
            raise ValueError('Congress active effects crossed the native turn segment')
    return value
