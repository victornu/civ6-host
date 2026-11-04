"""Bounded, repeated active-connection reads; never an atomic save certificate.

The injected reader has FileClient.read_active_database(request, timeout=...)
semantics. Waiting deadlines are cooperative and do not cancel SQLite work in
the game. No captured SQL is executed. Diagnostic bundles are not actor inputs.
"""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
from dataclasses import asdict
from dataclasses import dataclass
from types import MappingProxyType
from weakref import WeakSet
import hashlib
import json
import math
import os
from pathlib import Path
import re
import sqlite3
import time
from civ6_host.runtime.native.database_capture992 import CONNECTIONS
from civ6_host.runtime.native.database_capture992 import IDENTIFIER
from civ6_host.runtime.native.database_capture992 import SERIALIZATION
from civ6_host.runtime.native.database_capture992 import cell
from civ6_host.runtime.native.database_capture992 import require
from civ6_host.runtime.native.database_capture992 import validate_request
from civ6_host.runtime.native.database_capture992 import validate_response
SCHEMA = 'civ6rl.database_capture_bundle993.v1'

@dataclass(frozen=True)
class Limits:
    page_size: int = 64
    max_requests: int = 20000
    max_tables: int = 2048
    max_rows_per_table: int = 1000000
    max_rows_total: int = 2000000
    max_schema_objects: int = 10000
    max_bytes: int = 512 * 1024 * 1024
    timeout_seconds: float = 600.0
    request_timeout_seconds: float = 15.0
    localization_row_pagination: str = 'offset_v1'

    def validate(self):
        require(self.localization_row_pagination in ('offset_v1', 'rowid_seek_v1'), 'Unknown Localization row pagination version')
        for name in ('page_size', 'max_requests', 'max_tables', 'max_rows_per_table', 'max_rows_total', 'max_schema_objects', 'max_bytes'):
            value = getattr(self, name)
            require(type(value) is int and value > 0, 'Invalid limit ' + name)
        require(self.page_size <= 64, 'Protocol page limit exceeds 64')
        require(self.max_requests <= 1000000, 'Request count exceeds journal filename capacity')
        for name in ('timeout_seconds', 'request_timeout_seconds'):
            value = getattr(self, name)
            require(type(value) in (int, float) and math.isfinite(value) and (value > 0), 'Invalid limit ' + name)
        return self

def _json(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True, allow_nan=False).encode('ascii')

def _hash(value):
    return hashlib.sha256(value).hexdigest()

def _pin(path):
    digest, size = (hashlib.sha256(), 0)
    with _resolve_resource_path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
            size += len(block)
    return {'path': path.name, 'bytes': size, 'sha256': digest.hexdigest()}
_VERIFIED_BUNDLE_TOKEN = object()
_VERIFIED_BUNDLES = WeakSet()

class _VerifiedBundle:
    """Per-call verified manifest and exact pins for one journal directory."""
    __slots__ = ('directory', '_manifest_json', '_files', '__weakref__')

    def __init__(self, token, directory, manifest, files):
        require(token is _VERIFIED_BUNDLE_TOKEN, 'Verified bundle evidence is internal')
        self.directory = _resolve_resource_path(_resolve_resource_path(Path(directory))).resolve(strict=True)
        self._manifest_json = _json(manifest)
        self._files = MappingProxyType(dict(files))
        _VERIFIED_BUNDLES.add(self)

    @property
    def manifest(self):
        return json.loads(self._manifest_json)

    def dependency_pins(self):
        return tuple(((str(self.directory / pin['path']), pin['sha256'], pin['bytes']) for pin in self.manifest['files']))

def _envelope(record, request, nonces, sequence):
    require(type(record) is dict and record.get('type') == 'transport_status' and (record.get('status') == 'ok') and (record.get('reason') == 'database_capture_read'), 'Capture transport refused')
    nonce = record.get('request_id')
    require(type(nonce) is str and re.fullmatch('[A-Za-z0-9_.:-]{1,128}', nonce) and (nonce not in nonces), 'Missing or reused request nonce')
    seq = record.get('sequence')
    require(type(seq) is int and seq > sequence, 'Transport sequence did not increase')
    require(type(record.get('player_id')) is int and record['player_id'] == request['expected_player_id'] and (type(record.get('turn')) is int) and (record['turn'] == request['expected_turn']), 'Envelope boundary differs')
    data = record.get('diagnostics')
    require(type(data) is dict and set(data) == {'database_capture', 'request_id', 'completion', 'native_game_core_busy'} and (data['request_id'] == nonce) and (data['completion'] == 'read_only_active_connection') and (data['native_game_core_busy'] is False), 'Diagnostic nonce or idle witness differs')
    result = validate_response(data['database_capture'], request)
    nonces.add(nonce)
    return (result, seq)

def _read_pinned_journal_bytes(directory, name, pin):
    path = directory / name
    require(_resolve_resource_path(path).is_file() and (not path.is_symlink()), 'Journal file is missing or linked')
    raw = _resolve_resource_path(path).read_bytes()
    require(type(pin) is dict and pin.get('path') == name and (type(pin.get('bytes')) is int) and (len(raw) == pin['bytes']) and (type(pin.get('sha256')) is str) and (_hash(raw) == pin['sha256']), 'Journal file hash differs')
    return raw

def _pass(exchange, connection, player, turn, limits, row_counter, *, row_exchange=None, row_page_size=None):

    def query(operation, **extra):
        return exchange(dict(connection=connection, operation=operation, expected_player_id=player, expected_turn=turn, **extra))

    def schema():
        objects = []
        offset = 0
        while True:
            page, _ = query('schema', offset=offset, limit=limits.page_size)
            part = page['objects']
            if objects and part:
                require((objects[-1]['type'], objects[-1]['name']) < (part[0]['type'], part[0]['name']), 'Schema repeated or moved across pages')
            objects.extend(part)
            require(len(objects) <= limits.max_schema_objects, 'Schema count limit exceeded')
            if len(part) < limits.page_size:
                return objects
            offset += len(part)
    metadata, _ = query('metadata')
    objects = schema()
    names = [obj['name'] for obj in objects if obj['type'] == 'table']
    require(len(names) <= limits.max_tables and len(names) == len(set(names)), 'Table count/identity differs')
    for name in names:
        require(IDENTIFIER.fullmatch(name), 'Unsupported table name; no silent table omission')
    tables = []
    for name in names:
        columns, columns_index = query('columns', table_name=name)
        offset, last_id = (0, None)
        digest, pages = (hashlib.sha256(), [])
        while True:
            seek = connection == 'localization' and limits.localization_row_pagination == 'rowid_seek_v1'
            anchor = {} if not seek else {'after_rowid': 'start' if last_id is None else 'i:' + str(last_id)}
            if row_exchange is None:
                page, index = query('rows', table_name=name, offset=offset, limit=limits.page_size, **anchor)
            else:
                page, index = row_exchange(dict(connection=connection, operation='rows', expected_player_id=player, expected_turn=turn, table_name=name, offset=offset, limit=row_page_size, **anchor), columns)
            require(page['rowid_alias'] == columns['rowid_alias'] and page['columns'] == [x['name'] for x in columns['columns']], 'Table columns changed during capture')
            rows = page['rows']
            if rows:
                require(last_id is None or int(rows[0]['rowid'][2:]) > last_id, 'Row IDs repeated or moved across pages')
                last_id = int(rows[-1]['rowid'][2:])
            for row in rows:
                digest.update(_json(row) + b'\n')
            pages.append(index)
            offset += len(rows)
            row_counter[0] += len(rows)
            require(offset <= limits.max_rows_per_table and row_counter[0] <= limits.max_rows_total, 'Row capture limit exceeded')
            if len(rows) < (limits.page_size if row_exchange is None else row_page_size):
                break
        after, _ = query('columns', table_name=name)
        require(after == columns, 'Table metadata changed during capture')
        tables.append(dict(name=name, columns=columns, columns_index=columns_index, row_pages=pages, row_count=offset, rows_sha256=digest.hexdigest()))
    require(schema() == objects, 'Schema changed during capture')
    after, _ = query('metadata')
    require(metadata == after, 'Connection metadata changed during capture')
    return dict(connection=connection, metadata=metadata, objects=objects, tables=tables)

def _semantic(result):
    value = json.loads(_json(result))
    for table in value['tables']:
        table.pop('columns_index')
        table.pop('row_pages')
    return value

def capture_bundle(reader, directory, *, expected_player_id, expected_turn, connections=('gameplay', 'configuration'), limits=Limits(), clock=time.monotonic):
    """Capture every main-schema table twice, rejecting discrepancies.

    directory must not exist. Failure retains a manifest and published-request
    journal; never retry an uncertain command automatically. No part of this
    function starts Civ6, installs a mod, or changes an active database.
    """
    limits.validate()
    require(type(connections) in (list, tuple) and 1 <= len(connections) <= len(CONNECTIONS) and all((type(c) is str and c in CONNECTIONS for c in connections)) and (len(set(connections)) == len(connections)), 'Invalid connections')
    for connection in connections:
        validate_request(dict(connection=connection, operation='metadata', expected_player_id=expected_player_id, expected_turn=expected_turn))
    directory = _resolve_resource_path(Path(directory))
    directory.mkdir(parents=True, exist_ok=False)
    started = clock()
    manifest = dict(schema=SCHEMA, serialization=SERIALIZATION, status='incomplete', atomic_snapshot=False, save_process_scripts_associated=False, expected_player_id=expected_player_id, expected_turn=expected_turn, connections=list(connections), limits=asdict(limits), journal=[], passes=[], files=[])
    nonces, sequence, total_bytes, rows = (set(), [-1], [0], [0])

    def write(name, data):
        encoded = _json(data)
        require(total_bytes[0] + len(encoded) <= limits.max_bytes, 'Journal byte limit exceeded')
        path = directory / name
        with _resolve_resource_path(path).open('xb') as stream:
            stream.write(encoded)
        total_bytes[0] += len(encoded)
        pin = _pin(path)
        manifest['files'].append(pin)
        return pin

    def exchange(request):
        request = validate_request(request)
        require(len(manifest['journal']) < limits.max_requests, 'Request limit exceeded')
        remaining = limits.timeout_seconds - (clock() - started)
        require(remaining > 0, 'Bundle time budget exhausted before request')
        index = len(manifest['journal'])
        entry = {'request': write(f'{index:06d}.request.json', request), 'response': None, 'nonce': None}
        manifest['journal'].append(entry)
        record = reader(request, timeout=min(limits.request_timeout_seconds, remaining))
        entry['response'] = write(f'{index:06d}.response.json', record)
        result, sequence[0] = _envelope(record, request, nonces, sequence[0])
        entry['nonce'] = record['request_id']
        require(clock() - started <= limits.timeout_seconds, 'Reader exceeded bundle time budget')
        return (result, index)
    try:
        for repeat in range(2):
            current = [_pass(exchange, c, expected_player_id, expected_turn, limits, rows) for c in connections]
            manifest['passes'].append(current)
            if repeat:
                require([_semantic(x) for x in current] == [_semantic(x) for x in manifest['passes'][0]], 'Database content changed between complete reads')
        manifest['status'] = 'repeated_reads_agree'
        return manifest
    except Exception as exc:
        manifest['status'] = 'failed'
        manifest['error'] = type(exc).__name__ + ': ' + str(exc)[:1024]
        raise
    finally:
        manifest['elapsed_seconds'] = clock() - started
        manifest['requests'] = len(manifest['journal'])
        manifest['rows_read'] = rows[0]
        manifest['journal_bytes'] = total_bytes[0]
        manifest['limitations'] = ['Repeated equality detects observed changes, not a transaction, a lock, or changes that reverted.', 'No active PID/save/content/scripts/Localization association; database paths are diagnostic strings.', 'Timeout bounds transport waiting only and cannot stop an in-flight engine SQL query.', 'Only main schema is captured; metadata lists attached databases but their content is not captured.']
        (directory / 'manifest.json').write_bytes(_json(manifest))

def _verify_bundle(directory):
    """Replay the closed protocol, hashing each exact byte buffer as it is parsed."""
    directory = _resolve_resource_path(_resolve_resource_path(Path(directory))).resolve(strict=True)
    manifest = json.loads(_resolve_resource_path(directory / 'manifest.json').read_bytes())
    if manifest.get('schema') == 'civ6-host.database_bulk_capture.v1':
        from civ6_host.runtime import database_bulk_capture
        return database_bulk_capture._verify_bundle(directory)
    require(manifest.get('schema') == SCHEMA and manifest.get('serialization') == SERIALIZATION and (manifest.get('status') == 'repeated_reads_agree') and (manifest.get('atomic_snapshot') is False) and (manifest.get('save_process_scripts_associated') is False), 'Bundle is incomplete or overclaims provenance')
    limits = Limits(**manifest['limits']).validate()
    connections = manifest['connections']
    require(type(connections) is list and 1 <= len(connections) <= len(CONNECTIONS) and all((type(c) is str and c in CONNECTIONS for c in connections)) and (len(set(connections)) == len(connections)), 'Invalid captured connection set')
    files, byte_count = ({}, 0)
    for pin in manifest['files']:
        name = pin.get('path')
        require(type(name) is str and re.fullmatch('[0-9]{6}\\.(request|response)\\.json', name) and (name not in files), 'Unsafe or duplicate journal filename')
        path = directory / name
        require(_resolve_resource_path(path).is_file() and (not path.is_symlink()) and (type(pin.get('bytes')) is int) and (0 < pin['bytes'] <= 2 * 1024 * 1024) and (type(pin.get('sha256')) is str) and re.fullmatch('[0-9a-f]{64}', pin['sha256']), 'Journal file is missing, linked or has an invalid pin')
        files[name] = pin
        byte_count += pin['bytes']
    require(byte_count <= limits.max_bytes and manifest['journal_bytes'] == byte_count, 'Journal byte count differs')
    position, sequence, rows, nonces, consumed, hashed = ([0], [-1], [0], set(), set(), set())

    def exchange(request):
        index = position[0]
        require(index < len(manifest['journal']) and index < limits.max_requests, 'Journal ended or exceeds request limit')
        entry = manifest['journal'][index]
        require(set(entry) == {'request', 'response', 'nonce'}, 'Invalid journal entry')
        values = []
        for kind in ('request', 'response'):
            pin = entry[kind]
            name = f'{index:06d}.{kind}.json'
            require(type(pin) is dict and files.get(name) == pin and (name not in consumed), 'Journal association differs')
            consumed.add(name)
            values.append(json.loads(_read_pinned_journal_bytes(directory, name, pin)))
            hashed.add(name)
        saved_request, record = values
        require(validate_request(saved_request) == request, 'Journal request order or scope differs')
        response, sequence[0] = _envelope(record, request, nonces, sequence[0])
        require(entry['nonce'] == record['request_id'], 'Journal nonce differs')
        position[0] += 1
        return (response, index)
    passes = [[_pass(exchange, c, manifest['expected_player_id'], manifest['expected_turn'], limits, rows) for c in connections] for _ in range(2)]
    require(position[0] == len(manifest['journal']) == manifest['requests'] and consumed == set(files) and (hashed == set(files)) and (rows[0] == manifest['rows_read']), 'Unconsumed journal or counter mismatch')
    require(passes == manifest['passes'], 'Capture summary differs from journal')
    require([_semantic(x) for x in passes[0]] == [_semantic(x) for x in passes[1]], 'Repeated reads differ')
    return _VerifiedBundle(_VERIFIED_BUNDLE_TOKEN, directory, manifest, files)

def verify_bundle(directory):
    """Check pins and replay the full closed capture protocol without an engine.

    Public return shape remains the historical manifest. Consumers that also
    need comparisons may use the private evidence object within this call path.
    """
    return _verify_bundle(directory).manifest

def _quote(value):
    require(type(value) is str and '\x00' not in value, 'Invalid SQL identifier')
    return '"' + value.replace('"', '""') + '"'

def _typed(kind, value):
    if kind == b'null':
        require(value is None, 'Unexpected SQLite NULL')
        result = 'n'
    elif kind == b'integer':
        require(type(value) is int, 'Unexpected SQLite integer')
        result = 'i:' + str(value)
    elif kind == b'real':
        require(type(value) is float and math.isfinite(value), 'Unsupported SQLite REAL')
        sign = '-' if math.copysign(1, value) < 0 else '+'
        fraction, power = math.frexp(abs(value))
        result = 'r:' + sign + ('0p0' if not value else f'{int(fraction * 2 ** 53)}p{power - 53}')
    elif kind in (b'text', b'blob'):
        require(type(value) is bytes, 'SQLite byte extraction differs')
        result = ('t:' if kind == b'text' else 'b:') + value.hex().upper()
    else:
        raise ValueError('Unknown SQLite storage class')
    cell(result)
    return result

def _is_verified_bundle(value):
    if type(value) is _VerifiedBundle and value in _VERIFIED_BUNDLES:
        return True
    from civ6_host.runtime import database_bulk_capture
    return database_bulk_capture.is_verified(value)

def _iter_captured_rows(verified, table):
    require(_is_verified_bundle(verified), 'Expected an authenticated capture evidence object')
    if type(verified) is not _VerifiedBundle:
        yield from verified.iter_rows(table)
        return
    manifest = verified.manifest
    for index in table['row_pages']:
        pin = manifest['journal'][index]['response']
        require(verified._files.get(pin['path']) == pin, 'Row response is not in verified pins')
        record = json.loads(_read_pinned_journal_bytes(verified.directory, pin['path'], pin))
        yield from record['diagnostics']['database_capture']['rows']

def compare_sqlite_export(directory, export, *, connection, _verified=None):
    """Exact main schema, columns, rowids and typed-cell comparison; read-only.

    This compares bytes/values of a standalone file, not its provenance. Never
    executes stored CREATE/trigger/view SQL and never reconstructs a database.
    The comparator's SQLite version and file names need not match native ones.
    """
    if _verified is None:
        _verified = _verify_bundle(directory)
    require(_is_verified_bundle(_verified) and (_resolve_resource_path(_resolve_resource_path(Path(directory))).resolve(strict=True) == _verified.directory), 'Verified journal evidence belongs to a different directory')
    manifest = _verified.manifest
    directory, export = (_resolve_resource_path(Path(directory)), _resolve_resource_path(_resolve_resource_path(Path(export))).resolve(strict=True))
    require(connection in manifest['connections'], 'Connection absent from capture')
    require(_resolve_resource_path(export).is_file(), 'Export must be a file')
    for suffix in ('-wal', '-journal'):
        require(not _resolve_resource_path(_resolve_resource_path(Path(str(export) + suffix))).exists(), 'Export has live journal/WAL; provide a standalone snapshot')
    before = _pin(export)
    db = sqlite3.connect(export.as_uri() + '?mode=ro', uri=True)
    db.text_factory = bytes
    cursor = None
    result = next((x for x in manifest['passes'][0] if x['connection'] == connection))
    try:
        db.execute('PRAGMA query_only=ON')
        db.execute('PRAGMA trusted_schema=OFF')
        db.execute('BEGIN')
        require(db.execute('PRAGMA encoding').fetchone() == (b'UTF-8',), 'Export encoding differs')
        objects = []
        for kind, name, table, sql in db.execute('SELECT type,name,tbl_name,sql FROM main.sqlite_master ORDER BY type,name'):
            objects.append(dict(type=kind.decode('utf8'), name=name.decode('utf8'), table_name=table.decode('utf8'), sql_cell='n' if sql is None else 't:' + sql.hex().upper()))
        require(objects == result['objects'], 'Export schema differs')
        table_types = {row[1].decode('utf8'): row for row in db.execute('PRAGMA main.table_list')}
        require(table_types, 'Comparator needs SQLite table_list support')
        count = 0
        for table in result['tables']:
            name, alias = (table['name'], table['columns']['rowid_alias'])
            descriptor = table_types.get(name)
            require(descriptor is not None and descriptor[2] == b'table' and (descriptor[4] == 0), 'Export table is virtual/shadow/without-rowid')
            columns = []
            for cid, col, declared, notnull, default, pk, hidden in db.execute('PRAGMA main.table_xinfo(' + _quote(name) + ')'):
                require(hidden == 0, 'Export generated/hidden column is unsupported')
                columns.append(dict(cid=cid, name=col.decode('utf8'), declared_type=declared.decode('utf8'), not_null=bool(notnull), default_cell='n' if default is None else 't:' + default.hex().upper(), pk=pk))

            def comparable(items):
                return [{**item, 'declared_type': item['declared_type'].translate(str.maketrans('abcdefghijklmnopqrstuvwxyz', 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'))} for item in items]
            require(comparable(columns) == comparable(table['columns']['columns']), 'Export columns differ in ' + name)
            folded = {c['name'].lower() for c in columns}
            require(alias not in folded, 'Export rowid alias is shadowed')
            selections = [_quote(alias)]
            for col in columns:
                selections.extend(('typeof(' + _quote(col['name']) + ')', _quote(col['name'])))
            cursor = db.execute('SELECT ' + ','.join(selections) + ' FROM main.' + _quote(name) + ' ORDER BY ' + _quote(alias))
            for expected in _iter_captured_rows(_verified, table):
                raw = cursor.fetchone()
                require(raw is not None, 'Export has fewer rows')
                actual = dict(rowid='i:' + str(raw[0]), cells=[_typed(raw[i], raw[i + 1]) for i in range(1, len(raw), 2)])
                require(actual == expected, 'Export typed row differs in ' + name + ' at ' + expected['rowid'])
                count += 1
            require(cursor.fetchone() is None, 'Export has extra rows')
            cursor.close()
            cursor = None
        require(_pin(export) == before, 'Export file changed during comparison')
        for suffix in ('-wal', '-journal'):
            require(not _resolve_resource_path(_resolve_resource_path(Path(str(export) + suffix))).exists(), 'Export acquired a journal/WAL during comparison')
        return dict(**({'capture_schema': manifest['schema']} if manifest['schema'] != SCHEMA else {}), schema='civ6rl.database_export_comparison993.v1', status='exact_main_content_match', connection=connection, export=before, tables=len(result['tables']), rows=count, capture_manifest_sha256=_hash(_resolve_resource_path(directory / 'manifest.json').read_bytes()), atomic_snapshot=False, save_process_scripts_associated=False, comparison_scope='main schema SQL bytes, column attributes (declared-type ASCII case normalized), rowids and exact typed cells; no source SQL executed', excluded=['SQLite engine version', 'database file names', 'attached database contents', 'save/PID/scripts provenance'])
    finally:
        if cursor is not None:
            cursor.close()
        db.close()
MATERIALIZE_MAX_DATABASE_BYTES = 128 * 1024 * 1024
MATERIALIZE_MAX_JOURNAL_BYTES = 512 * 1024 * 1024
MATERIALIZE_MAX_MANIFEST_BYTES = 16 * 1024 * 1024
MATERIALIZE_SECONDS = 300

def _materialization_path(value, *, existing):
    path = _resolve_resource_path(Path(value)).absolute()
    require('..' not in path.parts, 'Materialization path contains parent traversal')
    for component in (path, *path.parents):
        require(not component.is_symlink() and (not getattr(component, 'is_junction', lambda: False)()), 'Materialization paths cannot contain symlinks or junctions')
    return _resolve_resource_path(path).resolve(strict=existing)

def _materialization_layout(db, captured):
    """Inspect an existing schema, without executing any captured schema SQL."""
    require(db.execute('PRAGMA encoding').fetchone() == (b'UTF-8',), 'Template encoding differs')
    objects = [dict(type=kind.decode('utf8'), name=name.decode('utf8'), table_name=table.decode('utf8'), sql_cell='n' if sql is None else 't:' + sql.hex().upper()) for kind, name, table, sql in db.execute('SELECT type,name,tbl_name,sql FROM main.sqlite_master ORDER BY type,name')]
    require(objects == captured['objects'], 'Template schema differs')
    tokens = re.compile('--[^\\r\\n]*|/\\*.*?\\*/|\'(?:\'\'|[^\'])*\'|\\"(?:\\"\\"|[^\\"])*\\"|`(?:``|[^`])*`|\\[[^\\]]*\\]|[A-Za-z_][A-Za-z0-9_]*|\\S', re.DOTALL)
    for obj in objects:
        if obj['sql_cell'] == 'n':
            continue
        pending = False
        for match in tokens.finditer(bytes.fromhex(obj['sql_cell'][2:]).decode('utf8')):
            token = match.group()
            if token.startswith(('--', '/*')):
                continue
            if pending:
                if token[:1] in ('"', '`', '[', "'"):
                    quote = token[0]
                    token = token[1:-1].replace(quote * 2, quote)
                require(token.upper() in ('BINARY', 'NOCASE', 'RTRIM'), 'Template uses an unsupported collation')
                pending = False
            elif token.upper() == 'COLLATE':
                pending = True
        require(not pending, 'Incomplete template collation')
    descriptors = {r[1].decode('utf8'): r for r in db.execute('PRAGMA main.table_list')}
    result = []
    for table in captured['tables']:
        name = table['name']
        descriptor = descriptors.get(name)
        require(descriptor is not None and descriptor[2] == b'table' and (descriptor[4] == 0) and (not name.lower().startswith('sqlite_')), 'Template table is virtual/shadow/without-rowid or internal')
        columns = []
        for cid, col, declared, notnull, default, pk, hidden in db.execute('PRAGMA main.table_xinfo(' + _quote(name) + ')'):
            require(hidden == 0, 'Template generated/hidden column is unsupported')
            columns.append(dict(cid=cid, name=col.decode('utf8'), declared_type=declared.decode('utf8'), not_null=bool(notnull), default_cell='n' if default is None else 't:' + default.hex().upper(), pk=pk))

        def normalized(items):
            return [{**x, 'declared_type': x['declared_type'].translate(str.maketrans('abcdefghijklmnopqrstuvwxyz', 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'))} for x in items]
        require(normalized(columns) == normalized(table['columns']['columns']), 'Template columns differ in ' + name)
        alias = table['columns']['rowid_alias']
        require(alias not in {c['name'].lower() for c in columns}, 'Template rowid alias is shadowed')
        for index in db.execute('PRAGMA main.index_list(' + _quote(name) + ')').fetchall():
            for detail in db.execute('PRAGMA main.index_xinfo(' + _quote(index[1].decode('utf8')) + ')'):
                require(detail[4] is None or detail[4].upper() in (b'BINARY', b'NOCASE', b'RTRIM'), 'Template uses an unsupported collation')
        result.append((table, columns))
    require(result, 'Template has no captured ordinary tables')
    return result

def materialize_sqlite_export(directory, template, output, *, connection='localization'):
    """Replace rows in a private copy of an exact official schema, then compare.

    This is a logical reconstruction, never a bit-identical cache export.
    Captured SQL is only compared as bytes; all executed DML is generated here
    and targets verified ordinary tables. Failure removes only our new output.
    """
    from civ6_host.runtime.native.database_capture992 import decode_real
    directory = _materialization_path(directory, existing=True)
    template = _materialization_path(template, existing=True)
    output = _materialization_path(output, existing=False)
    require(_resolve_resource_path(directory).is_dir() and _resolve_resource_path(template).is_file(), 'Capture directory/template file required')
    require(output != template and (not _resolve_resource_path(output).exists()) and _resolve_resource_path(output.parent).is_dir(), 'Materialization output must be a new distinct file')
    manifest_path = directory / 'manifest.json'
    require(not manifest_path.is_symlink() and 0 < _resolve_resource_path(manifest_path).stat().st_size <= MATERIALIZE_MAX_MANIFEST_BYTES, 'Materialization manifest byte bound')
    preflight = json.loads(_resolve_resource_path(manifest_path).read_bytes())
    if preflight.get('schema') != 'civ6-host.database_bulk_capture.v1':
        require(type(preflight.get('journal_bytes')) is int and 0 <= preflight['journal_bytes'] <= MATERIALIZE_MAX_JOURNAL_BYTES, 'Materialization journal byte bound')
        require(type(preflight.get('requests')) is int and 0 <= preflight['requests'] <= 20000 and (type(preflight.get('files')) is list) and (len(preflight['files']) <= 40000) and all((type(p) is dict and type(p.get('bytes')) is int and (0 < p['bytes'] <= 2 * 1024 * 1024) for p in preflight['files'])) and (sum((p['bytes'] for p in preflight['files'])) <= MATERIALIZE_MAX_JOURNAL_BYTES), 'Materialization journal entry bounds')
    require(0 < _resolve_resource_path(template).stat().st_size <= MATERIALIZE_MAX_DATABASE_BYTES, 'Materialization template byte bound')
    for path in (template, output):
        for suffix in ('-wal', '-shm', '-journal'):
            require(not _resolve_resource_path(_resolve_resource_path(Path(str(path) + suffix))).exists(), 'Materialization requires standalone databases')
    started = time.monotonic()
    deadline = started + MATERIALIZE_SECONDS
    manifest_pin = _pin(manifest_path)
    _verified = _verify_bundle(directory)
    manifest = _verified.manifest
    require(connection in manifest['connections'], 'Connection absent from capture')
    captured = next((x for x in manifest['passes'][0] if x['connection'] == connection))
    require(time.monotonic() < deadline, 'Materialization time budget exhausted')
    template_before = {**_pin(template), 'path': str(template)}
    db = sqlite3.connect(template.as_uri() + '?mode=ro', uri=True)
    try:
        db.enable_load_extension(False)
        db.text_factory = bytes
        db.execute('PRAGMA query_only=ON')
        db.execute('PRAGMA trusted_schema=OFF')
        layout = _materialization_layout(db, captured)
    finally:
        db.close()
    require({**_pin(template), 'path': str(template)} == template_before, 'Template changed during schema inspection')
    created = False
    success = False
    db = None
    created_identity = None
    try:
        with _resolve_resource_path(template).open('rb') as source, _resolve_resource_path(output).open('xb') as target:
            created = True
            created_identity = (os.fstat(target.fileno()).st_dev, os.fstat(target.fileno()).st_ino)
            copied = 0
            while (chunk := source.read(1024 * 1024)):
                copied += len(chunk)
                require(copied <= MATERIALIZE_MAX_DATABASE_BYTES, 'Materialization copy byte bound')
                target.write(chunk)
        require(_pin(output)['sha256'] == template_before['sha256'] and {**_pin(template), 'path': str(template)} == template_before, 'Template changed during copy')
        db = sqlite3.connect(output, cached_statements=32)
        db.enable_load_extension(False)
        db.text_factory = bytes
        db.setlimit(sqlite3.SQLITE_LIMIT_LENGTH, 1024 * 1024)
        db.setlimit(sqlite3.SQLITE_LIMIT_SQL_LENGTH, 1024 * 1024)
        db.setlimit(sqlite3.SQLITE_LIMIT_VARIABLE_NUMBER, 256)
        db.setlimit(sqlite3.SQLITE_LIMIT_ATTACHED, 0)
        db.execute('PRAGMA trusted_schema=OFF')
        db.execute('PRAGMA foreign_keys=OFF')
        db.execute('PRAGMA journal_mode=DELETE')
        db.execute('PRAGMA synchronous=FULL')
        db.execute('PRAGMA cache_size=-8192')
        db.execute('PRAGMA temp_store=MEMORY')
        page_size = db.execute('PRAGMA page_size').fetchone()[0]
        max_pages = MATERIALIZE_MAX_DATABASE_BYTES // page_size
        require(db.execute('PRAGMA max_page_count=' + str(max_pages)).fetchone()[0] <= max_pages, 'Materialization database page bound')
        allowed_tables = {table['name'] for table, _ in layout}
        denied = []

        def authorize(action, arg1, arg2, database, origin):
            allowed = origin is None and (action in (sqlite3.SQLITE_TRANSACTION, sqlite3.SQLITE_SELECT) or (action in (sqlite3.SQLITE_DELETE, sqlite3.SQLITE_INSERT, sqlite3.SQLITE_READ) and database == 'main' and (arg1 in allowed_tables)))
            if not allowed:
                if len(denied) < 16:
                    denied.append((action, arg1, arg2, database, origin))
                return sqlite3.SQLITE_DENY
            return sqlite3.SQLITE_OK
        db.set_authorizer(authorize)
        db.set_progress_handler(lambda: int(time.monotonic() >= deadline), 1000)
        for table, columns in layout:
            names = [table['columns']['rowid_alias']] + [c['name'] for c in columns]
            sql = 'EXPLAIN INSERT INTO main.' + _quote(table['name']) + '(' + ','.join(map(_quote, names)) + ') VALUES(' + ','.join(('?' for _ in names)) + ')'
            db.execute(sql, [None] * len(names)).close()
        db.execute('BEGIN IMMEDIATE')
        for table, _ in layout:
            db.execute('DELETE FROM main.' + _quote(table['name']))
        row_count = 0
        for table, columns in layout:
            names = [table['columns']['rowid_alias']] + [c['name'] for c in columns]
            prefix = 'INSERT INTO main.' + _quote(table['name']) + '(' + ','.join(map(_quote, names)) + ') VALUES('
            for row in _iter_captured_rows(_verified, table):
                require(time.monotonic() < deadline, 'Materialization time budget exhausted')
                expressions = ['?']
                values = [int(row['rowid'][2:])]
                for encoded in row['cells']:
                    cell(encoded)
                    expressions.append('CAST(? AS TEXT)' if encoded.startswith('t:') else '?')
                    if encoded == 'n':
                        value = None
                    elif encoded.startswith('i:'):
                        value = int(encoded[2:])
                    elif encoded.startswith('r:'):
                        value = decode_real(encoded)
                    else:
                        value = bytes.fromhex(encoded[2:])
                    values.append(value)
                db.execute(prefix + ','.join(expressions) + ')', values)
                row_count += 1
        db.commit()
        require(not denied, 'Materialization attempted a forbidden SQLite operation')
        db.close()
        db = None
        require(_resolve_resource_path(output).stat().st_size <= MATERIALIZE_MAX_DATABASE_BYTES, 'Materialization output byte bound')
        comparison = compare_sqlite_export(directory, output, connection=connection, _verified=_verified)
        require(time.monotonic() < deadline, 'Materialization time budget exhausted')
        require(_pin(manifest_path) == manifest_pin, 'Capture manifest changed during materialization')
        template_after = {**_pin(template), 'path': str(template)}
        require(template_after == template_before, 'Template changed during materialization')
        require(comparison['rows'] == row_count, 'Materialization row count differs')
        success = True
        return dict(**({'capture_schema': manifest['schema']} if manifest['schema'] != SCHEMA else {}), schema='civ6rl.database_materialization993.v1', connection=connection, database_production='verified_native_rows_into_private_template_v1', template=template_before, template_after=template_after, template_unchanged=True, database={**_pin(output), 'path': str(output)}, comparison=comparison, capture_manifest_sha256=manifest_pin['sha256'], tables=len(layout), rows=row_count, elapsed_seconds=time.monotonic() - started, limits=dict(database_bytes=MATERIALIZE_MAX_DATABASE_BYTES, journal_bytes=MATERIALIZE_MAX_JOURNAL_BYTES, cache_kib=8192, cooperative_seconds=MATERIALIZE_SECONDS), captured_schema_sql_executed=False, trigger_or_view_execution_allowed=False, atomic_snapshot=False, save_process_scripts_associated=False)
    finally:
        if db is not None:
            db.close()
        if created and (not success):
            stat = _resolve_resource_path(output).stat(follow_symlinks=False) if _resolve_resource_path(output).exists() else None
            if stat is not None and (stat.st_dev, stat.st_ino) == created_identity:
                output.unlink()
