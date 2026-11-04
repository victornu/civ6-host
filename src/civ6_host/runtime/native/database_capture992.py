"""Strict read-only active-database diagnostic protocol, outside actor inputs.

One page is not a transaction or a save/DB/script provenance certificate.
INTEGER64 and SQL TEXT/BLOB bytes never cross Lua's numeric/string coercions.
"""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import copy, json, math, re
SCHEMA = 'civ6rl.database_capture992.v1'
SERIALIZATION = 'sqlite_typed_cells992.v2'
CONNECTIONS = ('gameplay', 'configuration', 'localization')
IDENTIFIER = re.compile('[A-Za-z_][A-Za-z0-9_]{0,63}\\Z')
INTEGER = re.compile('(?:0|[1-9][0-9]*|-[1-9][0-9]*)\\Z')
REAL = re.compile('([+-])(0|[1-9][0-9]{0,15})p(0|-?[1-9][0-9]{0,3})\\Z')
HEX = re.compile('(?:[0-9A-F]{2})*\\Z')

def require(ok, message):
    if not ok:
        raise ValueError(message)

def integer(value, low, high, label):
    require(type(value) is int and low <= value <= high, 'Invalid ' + label)

def validate_request(request):
    require(type(request) is dict, 'Database capture request must be an object')
    common = {'connection', 'operation', 'expected_player_id', 'expected_turn'}
    operation = request.get('operation')
    require(operation in ('metadata', 'schema', 'columns', 'rows'), 'Unsupported capture operation')
    fields = common | ({'offset', 'limit'} if operation in ('schema', 'rows') else set())
    if operation in ('columns', 'rows'):
        fields |= {'table_name'}
    if 'after_rowid' in request:
        require(operation == 'rows' and request.get('connection') == 'localization', 'Rowid seek is only available for Localization rows')
        fields |= {'after_rowid'}
    require(set(request) == fields, 'Database capture request fields differ')
    require(request['connection'] in CONNECTIONS, 'Unsupported active connection')
    integer(request['expected_player_id'], 0, 63, 'player')
    integer(request['expected_turn'], 0, 1000000, 'turn')
    if 'offset' in fields:
        integer(request['offset'], 0, 10000000, 'offset')
        integer(request['limit'], 1, 64, 'limit')
    if 'table_name' in fields:
        require(type(request['table_name']) is str and IDENTIFIER.fullmatch(request['table_name']), 'Unsupported table identifier')
    if 'after_rowid' in request:
        anchor = request['after_rowid']
        require(type(anchor) is str, 'Invalid rowid seek anchor')
        if anchor == 'start':
            require(request['offset'] == 0, 'Initial seek anchor requires offset zero')
        else:
            cell(anchor)
            require(anchor.startswith('i:') and request['offset'] > 0, 'Invalid rowid seek anchor')
    return copy.deepcopy(request)

def cell(value):
    require(type(value) is str and len(value) <= 512 * 1024, 'Invalid typed SQL cell')
    if value == 'n':
        return
    require(len(value) >= 2 and value[1] == ':', 'Missing SQL cell type')
    tag, data = (value[0], value[2:])
    if tag == 'i':
        require(len(data) <= 20 and INTEGER.fullmatch(data) and (-2 ** 63 <= int(data) < 2 ** 63), 'Invalid SQL int64')
    elif tag == 'r':
        decode_real(value)
    elif tag in ('t', 'b'):
        require(HEX.fullmatch(data), 'Invalid SQL byte encoding')
    else:
        raise ValueError('Unknown SQL cell type')

def decode_real(value):
    """Reconstruct exact native binary64, with a canonical frexp representation."""
    require(type(value) is str and value.startswith('r:') and (len(value) <= 64), 'Invalid REAL cell')
    match = REAL.fullmatch(value[2:])
    require(match is not None, 'Invalid binary REAL representation')
    sign, number, power = match.groups()
    mantissa = int(number)
    exponent = int(power)
    if mantissa == 0:
        require(exponent == 0, 'Noncanonical zero REAL')
        return -0.0 if sign == '-' else 0.0
    require(2 ** 52 <= mantissa < 2 ** 53 and -1126 <= exponent <= 971, 'REAL component outside binary64 range')
    try:
        result = math.ldexp(mantissa, exponent)
    except OverflowError as exc:
        raise ValueError('REAL overflow') from exc
    require(math.isfinite(result) and result != 0, 'REAL not finite/nonzero')
    fraction, power = math.frexp(result)
    require(int(fraction * 2 ** 53) == mantissa and power - 53 == exponent, 'REAL representation loses bits or is noncanonical')
    return -result if sign == '-' else result

def text_cell(value, nullable=False):
    cell(value)
    require(value.startswith('t:') or (nullable and value == 'n'), 'Expected SQL text cell')

def _text(value, label, maximum=4096):
    require(type(value) is str and len(value.encode('utf8')) <= maximum, 'Invalid ' + label)

def validate_response(response, request):
    request = validate_request(request)
    require(type(response) is dict, 'Database capture response must be an object')
    require(len(json.dumps(response, ensure_ascii=True, allow_nan=False).encode('ascii')) <= 1024 * 1024, 'Database capture response exceeds transport bound')
    common = {'schema', 'connection', 'operation', 'player_id', 'turn', 'serialization', 'atomic_snapshot'}
    operation = request['operation']
    extra = {'metadata': {'sqlite_version', 'databases', 'real_encoding', 'text_encoding'}, 'schema': {'offset', 'limit', 'objects'}, 'columns': {'table_name', 'rowid_alias', 'columns'}, 'rows': {'table_name', 'offset', 'limit', 'rowid_alias', 'columns', 'rows'}}[operation]
    if 'after_rowid' in request:
        extra = extra | {'after_rowid'}
    require(set(response) == common | extra, 'Database response fields differ')
    require(response['schema'] == SCHEMA and response['serialization'] == SERIALIZATION, 'Unknown capture schema')
    require(response['atomic_snapshot'] is False, 'Capture cannot certify transaction isolation')
    require(type(response['player_id']) is int and response['player_id'] == request['expected_player_id'] and (type(response['turn']) is int) and (response['turn'] == request['expected_turn']), 'Capture boundary differs')
    require(response['connection'] == request['connection'] and response['operation'] == operation, 'Capture operation differs')
    for key in ('table_name', 'offset', 'limit', 'after_rowid'):
        if key in extra:
            require(type(response[key]) is type(request[key]) and response[key] == request[key], 'Capture ' + key + ' differs')
    if operation == 'metadata':
        _text(response['sqlite_version'], 'SQLite version')
        require(response['real_encoding'] == 'binary53_exponent_v1', 'Unknown real encoding')
        require(response['text_encoding'] == 'UTF-8', 'Only qualified UTF-8 SQLite text encoding is supported')
        rows = response['databases']
        require(type(rows) is list and 1 <= len(rows) <= 32, 'Invalid database list')
        names = set()
        seqs = set()
        for row in rows:
            require(type(row) is dict and set(row) == {'seq', 'name', 'file'}, 'Invalid attached database')
            integer(row['seq'], 0, 2147483647, 'database index')
            _text(row['name'], 'database name')
            _text(row['file'], 'database file', 32768)
            require(row['name'] not in names and row['seq'] not in seqs, 'Duplicate attached database')
            names.add(row['name'])
            seqs.add(row['seq'])
        require('main' in names, 'Main active database missing')
    elif operation == 'schema':
        rows = response['objects']
        require(type(rows) is list and len(rows) <= request['limit'], 'Invalid schema page')
        keys = []
        for row in rows:
            require(type(row) is dict and set(row) == {'type', 'name', 'table_name', 'sql_cell'}, 'Invalid schema object')
            require(row['type'] in ('table', 'index', 'view', 'trigger'), 'Unknown SQLite object')
            _text(row['name'], 'object name')
            _text(row['table_name'], 'object table')
            text_cell(row['sql_cell'], nullable=True)
            keys.append((row['type'], row['name']))
        require(keys == sorted(set(keys)), 'Schema objects must be ordered and unique')
    else:
        require(response['rowid_alias'] in ('rowid', '_rowid_', 'oid'), 'Unknown rowid alias')
        columns = response['columns']
        require(type(columns) is list and 1 <= len(columns) <= 128, 'Invalid columns')
        if operation == 'columns':
            names = []
            for index, row in enumerate(columns):
                require(type(row) is dict and set(row) == {'cid', 'name', 'declared_type', 'not_null', 'default_cell', 'pk'}, 'Invalid table column')
                require(type(row['cid']) is int and row['cid'] == index, 'Noncontiguous column IDs')
                _text(row['name'], 'column name')
                _text(row['declared_type'], 'declared type')
                require(type(row['not_null']) is bool, 'Invalid not null flag')
                integer(row['pk'], 0, 128, 'primary key order')
                text_cell(row['default_cell'], nullable=True)
                names.append(row['name'])
        else:
            names = columns
            for name in names:
                _text(name, 'column name')
            rows = response['rows']
            require(type(rows) is list and len(rows) <= request['limit'], 'Invalid row page')
            ids = []
            for row in rows:
                require(type(row) is dict and set(row) == {'rowid', 'cells'}, 'Invalid table row')
                cell(row['rowid'])
                require(row['rowid'].startswith('i:'), 'Invalid native rowid')
                ids.append(int(row['rowid'][2:]))
                require(type(row['cells']) is list and len(row['cells']) == len(names), 'Row width differs')
                for value in row['cells']:
                    cell(value)
            require(ids == sorted(set(ids)), 'Native rows must be ordered and unique')
            anchor = request.get('after_rowid', 'start')
            if anchor != 'start' and ids:
                require(ids[0] > int(anchor[2:]), 'Rowid seek returned a row at/before its anchor')
        require(len(names) == len(set(names)), 'Duplicate columns')
    return copy.deepcopy(response)
