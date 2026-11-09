"""Player-visible historical Congress results; no session or request ACK.

Identity marks when the public result was observed, never when it was produced.
Availability is governed separately by the source-bound presentation owner.
"""
SCHEMA = 'civ6-host.world-congress-review.v1'
STATUSES = ('available', 'waiting_or_closed', 'review_ui_unavailable')


def _fields(value, fields):
    if type(value) is not dict or set(value) != set(fields.split()):
        raise ValueError('Congress review object fields differ')


def _integer(value, maximum=0x7fffffff, minimum=0):
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError('Congress review integer outside bounds')


def _text(value):
    if type(value) is not str or len(value.encode('utf-8')) > 32768:
        raise ValueError('Congress review text outside bounds')


def _boolean(value):
    if type(value) is not bool:
        raise ValueError('Congress review Boolean differs')


def _rows(value, maximum=4096):
    if type(value) is not list or len(value) > maximum:
        raise ValueError('Congress review rows outside bounds')
    return value


def _reference(value):
    _fields(value, 'player_id label')
    if value['player_id'] is not None:
        _integer(value['player_id'], 63)
    _text(value['label'])


def _target(value, player_target):
    _fields(value, 'player_id value label')
    _text(value['label'])
    if value['player_id'] is not None:
        _integer(value['player_id'], 63)
        if not player_target or value['value'] != str(value['player_id']):
            raise ValueError('Congress review target identity differs')
    elif player_target:
        if value['value'] is not None:
            raise ValueError('Congress review hidden target identity leaked')
    if value['value'] is not None:
        _text(value['value'])
    elif not player_target:
        raise ValueError('Congress review non-player target absent')


def validate_catalogue(value, player_id, turn, sequence):
    """Validate exact public fields without inferring result freshness."""
    _integer(player_id, 63)
    _integer(turn)
    _integer(sequence, 0xffffffff)
    _fields(value, 'schema player_id turn sequence turn_segment history_kind resolutions discussions')
    for key, expected in (('player_id', player_id), ('turn', turn), ('sequence', sequence)):
        if type(value[key]) is not int or value[key] != expected:
            raise ValueError('Congress review crossed observation identity')
    if value['schema'] != SCHEMA or value['history_kind'] != 'last_results':
        raise ValueError('Congress review historical kind differs')
    _integer(value['turn_segment'], 0xffffffff)
    for index, row in enumerate(_rows(value['resolutions'])):
        _fields(row, 'index resolution_type name target_type chosen_option chosen_label chosen_target '
                'rejected_option rejected_label is_new votes_a votes_b tied votes')
        if type(row['index']) is not int or row['index'] != index:
            raise ValueError('Congress review display index differs')
        for key in ('resolution_type', 'name', 'target_type', 'chosen_option', 'chosen_label'):
            _text(row[key])
        player_target = row['target_type'] == 'PlayerType'
        _target(row['chosen_target'], player_target)
        _boolean(row['is_new']); _boolean(row['tied'])
        totals = {1: 0, 2: 0}; seen = set()
        for vote in _rows(row['votes'], 64):
            _fields(vote, 'voter option votes target option_label')
            _reference(vote['voter']); _integer(vote['option'], minimum=-0x80000000)
            _integer(vote['votes'], minimum=-0x80000000)
            _target(vote['target'], player_target); _text(vote['option_label'])
            voter = vote['voter']['player_id']
            if voter is not None:
                if voter in seen: raise ValueError('Duplicate known Congress voter')
                seen.add(voter)
            # Preserve native signed OptionChosen; the official UI uses ==1 / else.
            totals[1 if vote['option'] == 1 else 2] += vote['votes']
        for key in ('rejected_option', 'rejected_label'):
            if row['votes']: _text(row[key])
            elif row[key] is not None: raise ValueError('Hidden rejected result was exported')
        _integer(row['votes_a'], 64 * 0x80000000, -64 * 0x80000000)
        _integer(row['votes_b'], 64 * 0x80000000, -64 * 0x80000000)
        if (row['votes_a'], row['votes_b'], row['tied']) != (totals[1], totals[2], totals[1] == totals[2]):
            raise ValueError('Congress resolution totals differ')
    for index, row in enumerate(_rows(value['discussions'])):
        _fields(row, 'index category_type category_name type_name name description target is_new '
                'votes_up votes_down passed votes')
        if type(row['index']) is not int or row['index'] != index:
            raise ValueError('Congress review display index differs')
        for key in ('category_type', 'category_name', 'type_name', 'name', 'description'):
            _text(row[key])
        if row['target'] is not None: _reference(row['target'])
        _boolean(row['is_new']); _boolean(row['passed'])
        up = down = 0; seen = set()
        for vote in _rows(row['votes'], 64):
            _fields(vote, 'voter votes reason'); _reference(vote['voter'])
            _integer(vote['votes'], minimum=-0x80000000); _text(vote['reason'])
            voter = vote['voter']['player_id']
            if voter is not None:
                if voter in seen: raise ValueError('Duplicate known Congress voter')
                seen.add(voter)
            if vote['votes'] > 0: up += vote['votes']
            else: down -= vote['votes']
            if vote['reason'] and not (voter == player_id and vote['votes'] == 0):
                raise ValueError('Congress review voting reason differs')
        _integer(row['votes_up'], 64 * 0x80000000); _integer(row['votes_down'], 64 * 0x80000000)
        if (row['votes_up'], row['votes_down'], row['passed']) != (up, down, up > down):
            raise ValueError('Congress discussion totals differ')
    return value


def compare_own(value, observation, sequence):
    if type(observation) is not dict:
        raise ValueError('Congress review observation must be an object')
    return validate_catalogue(value, observation.get('player_id'), observation.get('turn'), sequence)


def validate_group(value, status, congress, player_id, turn, sequence):
    """Bind availability and observation identity, never infer a historical ACK."""
    if type(status) is not str or status not in STATUSES:
        raise ValueError('Unknown Congress review availability status')
    if (value is None) != (status != 'available'):
        raise ValueError('Congress review data and availability differ')
    if (congress is None) != (status == 'waiting_or_closed'):
        raise ValueError('Congress review waiting status differs from its boundary')
    if congress is not None:
        from .world_congress import validate_catalogue as validate_congress
        validate_congress(congress, player_id, turn, sequence)
    if value is not None:
        if (congress['stage'] != 'ordinary' or congress['paused'] or not congress['local_alive']):
            raise ValueError('Congress review is unavailable in this UI phase')
        validate_catalogue(value, player_id, turn, sequence)
        if value['turn_segment'] != congress['turn_segment']:
            raise ValueError('Congress review crossed native turn segment')
    return value
