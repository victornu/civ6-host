"""Bounded SQL row stream decoding, separate from native capture provenance.

The stream replaces neither the native receipt nor the official save/content
bundle. A returned result authenticates the complete supplied file only. No row
is returned before its footer, exact EOF and expected hash have been verified.
The SQL projection preserves the typed-cell semantics of database_capture992;
stored integers/text/blob never rely on native int32 or string coercion.
"""
from __future__ import annotations

import hashlib
import math
import os
from pathlib import Path, PureWindowsPath
import re
import stat
import struct
import copy

from .native.database_capture992 import SERIALIZATION, cell, decode_real

MAGIC = b'C6RS01\r\n'
SCHEMA = 'civ6-host.database-row-stream.v1'
MAX_FILE_BYTES = 32 * 1024 * 1024
MAX_ROWS = 8192
MAX_COLUMNS = 128
MAX_WIRE_COLUMNS = 257
MAX_NAME_BYTES = 256
MAX_CELL_BYTES = 65536
MAX_WIRE_TEXT_BYTES = 131074
MAX_SQL_BYTES = 65536
_TABLE = re.compile(r'[A-Za-z_][A-Za-z0-9_]{0,63}\Z')
_HASH = re.compile(r'[0-9a-f]{64}\Z')
NATIVE_SCHEMA = 'civ6-host.localization_row_stream_native.v1'
# Native State serialization shared with native_localization_export.NATIVE_FIELDS.
# Keeping this pure protocol tuple here avoids importing the capture stack and
# its resource-root resolution when decoding a local artifact.
_NATIVE_FIELDS = (
    'locale', 'dictionary_flag', 'dictionary_address', 'connection_address',
    'lookup_result_address', 'auxiliary_result_address', 'statement_address',
    'icu_address', 'icu_bytes', 'language_address', 'language_index',
    'languages_begin', 'languages_end',
)
_IDENTITY_FIELDS = set(_NATIVE_FIELDS) | {'fallback_policy_sql_sha256', 'icu_sha256'}
_POINTER_FIELDS = (
    'dictionary_address', 'connection_address', 'lookup_result_address',
    'auxiliary_result_address', 'statement_address', 'icu_address',
    'language_address', 'languages_begin', 'languages_end',
)
_RECEIPT_FIELDS = {
    'schema', 'status', 'nonce', 'pid', 'creation_filetime', 'thread_id',
    'lua_state', 'source_before', 'source_after', 'query_sha256', 'rows',
    'bytes', 'sha256', 'milliseconds', 'sqlite_status', 'statement_error',
    'cursor_released', 'source_transactions_modified', 'atomic_snapshot_proven',
    'backup_called',
}


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _integer(value, lower, upper, label):
    _require(type(value) is int and lower <= value <= upper, 'Invalid ' + label)


def _columns(columns):
    _require(type(columns) in (list, tuple) and 1 <= len(columns) <= MAX_COLUMNS,
             'Invalid source columns')
    names = []
    for name in columns:
        _require(type(name) is str and 1 <= len(name) <= MAX_NAME_BYTES
                 and all(32 <= ord(c) <= 126 for c in name), 'Invalid source column name')
        names.append(name)
    _require(len({name.lower() for name in names}) == len(names), 'Duplicate source columns')
    return tuple(names)


def _anchor(after_rowid):
    _require(type(after_rowid) is str, 'Invalid rowid anchor')
    if after_rowid == 'start':
        return None
    cell(after_rowid)
    _require(after_rowid.startswith('i:'), 'Rowid anchor must be canonical INTEGER64')
    return int(after_rowid[2:])


def _options(columns, rowid_alias, after_rowid, limit, max_cell_bytes):
    names = _columns(columns)
    _require(type(rowid_alias) is str and rowid_alias in ('rowid', '_rowid_', 'oid'),
             'Unknown rowid alias')
    _require(rowid_alias not in {name.lower() for name in names}, 'Rowid alias is shadowed')
    anchor = _anchor(after_rowid)
    _integer(limit, 1, MAX_ROWS, 'row limit')
    _integer(max_cell_bytes, 1, MAX_CELL_BYTES, 'cell byte limit')
    return names, anchor


def _identifier(name):
    # Names have already been constrained; quoting additionally preserves names
    # containing a quote, whitespace or SQL punctuation as one identifier.
    return '"' + name.replace('"', '""') + '"'


def _encoded(expression, maximum):
    return ("CASE typeof(" + expression + ") WHEN 'null' THEN 'n'"
            " WHEN 'integer' THEN 'i:'||CAST(" + expression + " AS TEXT)"
            " WHEN 'real' THEN 'r'"
            " WHEN 'text' THEN CASE WHEN length(CAST(" + expression + " AS BLOB))>" + str(maximum) +
            " THEN '!oversize' ELSE 't:'||hex(CAST(" + expression + " AS BLOB)) END"
            " WHEN 'blob' THEN CASE WHEN length(" + expression + ")>" + str(maximum) +
            " THEN '!oversize' ELSE 'b:'||hex(" + expression + ") END ELSE '!' END")


def row_query(table_name, columns, *, rowid_alias='rowid', after_rowid='start',
              limit=MAX_ROWS, max_cell_bytes=MAX_CELL_BYTES):
    """Produce only a bounded main-table SELECT, with exact int64 keyset seek.

    The caller must separately validate ordinary rowid-table metadata and UTF-8
    database encoding, as in the existing capture. This generator does not assert
    that a table exists, that its schema is supported, or that a source is native.
    """
    _require(type(table_name) is str and _TABLE.fullmatch(table_name), 'Unsafe table identifier')
    names, anchor = _options(columns, rowid_alias, after_rowid, limit, max_cell_bytes)
    select = [_encoded(_identifier(rowid_alias), max_cell_bytes) + ' AS capture_rowid']
    for index, name in enumerate(names, 1):
        expression = _identifier(name)
        select.append(_encoded(expression, max_cell_bytes) + ' AS v' + str(index))
        select.append("CASE WHEN typeof(" + expression + ")='real' THEN " + expression +
                      ' END AS r' + str(index))
    suffix = ' FROM main.' + _identifier(table_name)
    if anchor is not None:
        # Reuse validated canonical text; never float conversion or rowid+1.
        suffix += ' WHERE ' + _identifier(rowid_alias) + ' > ' + after_rowid[2:]
    suffix += ' ORDER BY ' + _identifier(rowid_alias) + ' LIMIT ' + str(limit)
    query = 'SELECT ' + ','.join(select) + suffix
    _require(len(query.encode('ascii')) <= MAX_SQL_BYTES, 'SQL projection exceeds byte limit')
    return query


def encode_real(value):
    """Canonical binary53 representation shared with the retained Lua codec."""
    _require(type(value) is float and math.isfinite(value), 'Missing or nonfinite native REAL')
    sign = '-' if math.copysign(1.0, value) < 0 else '+'
    if value == 0:
        encoded = 'r:' + sign + '0p0'
    else:
        fraction, exponent = math.frexp(abs(value))
        whole = int(fraction * 2**53)
        encoded = 'r:' + sign + str(whole) + 'p' + str(exponent - 53)
    cell(encoded)
    _require(struct.pack('<d', decode_real(encoded)) == struct.pack('<d', value),
             'REAL representation loses bits')
    return encoded


class _Reader:
    def __init__(self, stream, expected_bytes):
        self.stream = stream
        self.expected_bytes = expected_bytes
        self.count = 0
        self.digest = hashlib.sha256()

    def take(self, size):
        _require(0 <= size <= self.expected_bytes - self.count, 'Truncated or oversized row stream')
        data = self.stream.read(size)
        _require(len(data) == size, 'Truncated row stream')
        self.count += size
        self.digest.update(data)
        return data

    def uint32(self):
        return struct.unpack('<I', self.take(4))[0]

    def text(self, *, name=False):
        length = self.uint32()
        _require((1 if name else 0) <= length <= (MAX_NAME_BYTES if name else MAX_WIRE_TEXT_BYTES),
                 'Stream name or text exceeds byte limit')
        try:
            return self.take(length).decode('ascii')
        except UnicodeDecodeError as exc:
            raise ValueError('Non-ASCII stream name or text') from exc

    def value(self):
        kind = self.take(1)
        if kind == b'n':
            return None
        if kind == b'i':
            return struct.unpack('<i', self.take(4))[0]
        if kind == b'f':
            value = struct.unpack('<d', self.take(8))[0]
            _require(math.isfinite(value), 'Nonfinite wire REAL')
            return value
        if kind == b't':
            return self.text()
        raise ValueError('Unknown stream value kind')


def _typed_cell(encoded, raw_real, maximum):
    _require(type(encoded) is str, 'Stored SQL cell must use typed text projection')
    if encoded == 'r':
        return encode_real(raw_real)
    _require(raw_real is None, 'Non-REAL stored cell has a raw REAL value')
    _require(not encoded.startswith('r:'), 'Stored REAL bypasses native raw value')
    cell(encoded)
    if encoded.startswith(('t:', 'b:')):
        _require(len(encoded) - 2 <= maximum * 2, 'Stored SQL cell exceeds byte limit')
    return encoded


def read_row_stream(path, *, expected_sha256, expected_bytes, columns,
                    rowid_alias='rowid', after_rowid='start', limit=MAX_ROWS,
                    max_cell_bytes=MAX_CELL_BYTES):
    """Return decoded rows only after complete file authentication.

    The source is read incrementally with bounded strings and rows. The returned
    rows are staged in memory until successful verification; this is intentionally
    not an iterator that could publish rows from an incomplete/error artifact.
    """
    _require(type(expected_sha256) is str and _HASH.fullmatch(expected_sha256),
             'Invalid expected stream hash')
    _integer(expected_bytes, 26, MAX_FILE_BYTES, 'expected stream byte count')
    names, previous = _options(columns, rowid_alias, after_rowid, limit, max_cell_bytes)
    expected_names = ['capture_rowid']
    for index in range(1, len(names) + 1):
        expected_names.extend(('v' + str(index), 'r' + str(index)))
    path = Path(path).resolve(strict=True)
    rows = []
    with path.open('rb') as stream:
        before = os.fstat(stream.fileno())
        _require(stat.S_ISREG(before.st_mode) and before.st_size == expected_bytes,
                 'Stream is not a regular file with the expected byte count')
        reader = _Reader(stream, expected_bytes)
        _require(reader.take(len(MAGIC)) == MAGIC, 'Unknown row stream version')
        width = reader.uint32()
        _integer(width, 1, MAX_WIRE_COLUMNS, 'stream column count')
        header_names = [reader.text(name=True) for _ in range(width)]
        _require(len(set(header_names)) == width, 'Duplicate stream column names')
        _require(header_names == expected_names, 'Stream projection columns differ')
        while True:
            marker = reader.take(1)
            if marker == b'D':
                count = struct.unpack('<Q', reader.take(8))[0]
                _require(count == len(rows), 'Stream footer row count differs')
                break
            _require(marker == b'R', 'Unknown row marker')
            _require(len(rows) < limit, 'Stream exceeds requested row limit')
            values = [reader.value() for _ in range(width)]
            rowid = values[0]
            _require(type(rowid) is str and rowid.startswith('i:'), 'Rowid must use INTEGER64 text')
            cell(rowid)
            value = int(rowid[2:])
            _require(previous is None or value > previous, 'Rows are unordered or at/before anchor')
            previous = value
            cells = [_typed_cell(values[1 + 2*i], values[2 + 2*i], max_cell_bytes)
                     for i in range(len(names))]
            rows.append({'rowid': rowid, 'cells': cells})
        _require(reader.count == expected_bytes and stream.read(1) == b'', 'Trailing stream data')
        _require(reader.digest.hexdigest() == expected_sha256, 'Stream hash differs')
        after = os.fstat(stream.fileno())
        _require((before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) ==
                 (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns),
                 'Stream file changed during verification')
        named = path.stat()
        _require((named.st_dev, named.st_ino, named.st_size, named.st_mtime_ns) ==
                 (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns),
                 'Stream path changed during verification')
    return {
        'schema': SCHEMA, 'serialization': SERIALIZATION,
        'artifact': {'path': str(path), 'sha256': expected_sha256, 'bytes': expected_bytes},
        'artifact_identity_verified': True, 'native_producer_verified': False,
        'source_bundle_verified': False, 'columns': list(names), 'rowid_alias': rowid_alias,
        'after_rowid': after_rowid, 'limit': limit, 'rows': rows,
    }


def _pointer(value, label):
    _require(type(value) is str and re.fullmatch(r'0x[0-9a-f]+', value) is not None,
             'Invalid pointer: ' + label)
    address = int(value, 16)
    _require(0x10000 <= address < 2**47 and address % 8 == 0 and value == hex(address),
             'Invalid pointer: ' + label)
    return address


def _source_identity(value, *, sqlite):
    expected = set(_NATIVE_FIELDS) | ({'sqlite_address'} if sqlite else
                                     {'fallback_policy_sql_sha256', 'icu_sha256'})
    _require(type(value) is dict and set(value) == expected, 'Localization identity fields differ')
    _require(type(value['locale']) is str
             and re.fullmatch(r'[A-Za-z][A-Za-z0-9_@.\-]{0,62}', value['locale']) is not None,
             'Invalid Localization locale')
    _require(type(value['dictionary_flag']) is bool, 'Invalid Localization dictionary flag')
    for field in _POINTER_FIELDS:
        _pointer(value[field], field)
    _integer(value['icu_bytes'], 1, 64 * 1024 * 1024, 'ICU byte count')
    _integer(value['language_index'], 0, 1023, 'language index')
    begin, end = int(value['languages_begin'], 16), int(value['languages_end'], 16)
    address = int(value['language_address'], 16)
    _require(end > begin and (end-begin) % 0x190 == 0 and (end-begin)//0x190 <= 1024
             and address == begin + value['language_index'] * 0x190 and address < end,
             'Localization language owner differs')
    if sqlite:
        _pointer(value['sqlite_address'], 'sqlite_address')
    else:
        for field in ('fallback_policy_sql_sha256', 'icu_sha256'):
            _require(type(value[field]) is str and _HASH.fullmatch(value[field]) is not None,
                     'Invalid Localization identity hash: ' + field)


def validate_native_row_stream(receipt, *, process, nonce, runtime_identity, query,
                               path, table_name, columns, rowid_alias='rowid',
                               after_rowid='start', limit=MAX_ROWS,
                               max_cell_bytes=MAX_CELL_BYTES):
    """Associate one complete artifact with a native-shaped receipt and query.

    This is an offline consistency check, not authentication of a native
    producer. The caller must separately authenticate the installed helper,
    source/module builds, process witness and supplied runtime identity. A dict
    alone cannot establish that the official process emitted it. The 30-second
    receipt sanity bound is not a cancellable native-call deadline.
    """
    _require(type(receipt) is dict and set(receipt) == _RECEIPT_FIELDS,
             'Native row receipt fields differ')
    _require(type(receipt['schema']) is str and receipt['schema'] == NATIVE_SCHEMA
             and type(receipt['status']) is str and receipt['status'] == 'ok',
             'Native row stream did not succeed')
    _require(type(process) is dict and set(process) == {'pid', 'creation_filetime', 'image_path'},
             'Invalid exact process identity')
    for owner in (process, receipt):
        _integer(owner['pid'], 1, 2**32-1, 'process ID')
        _integer(owner['creation_filetime'], 1, 2**64-1, 'process creation time')
    image = process['image_path']
    _require(type(image) is str and 1 <= len(image) <= 32767 and '\0' not in image
             and (PureWindowsPath(image).is_absolute() or Path(image).is_absolute()),
             'Invalid process image path')
    _require(type(nonce) is str and re.fullmatch(r'[0-9a-f]{32}', nonce) is not None
             and type(receipt['nonce']) is str and receipt['nonce'] == nonce,
             'Native row receipt nonce differs')
    _require(receipt['pid'] == process['pid']
             and receipt['creation_filetime'] == process['creation_filetime'],
             'Native row receipt process differs')
    _integer(receipt['thread_id'], 1, 2**32-1, 'native thread ID')
    _pointer(receipt['lua_state'], 'lua_state')
    _source_identity(runtime_identity, sqlite=False)
    before, after = receipt['source_before'], receipt['source_after']
    _source_identity(before, sqlite=True)
    _source_identity(after, sqlite=True)
    _require(all(type(before[k]) is type(after[k]) and before[k] == after[k] for k in before),
             'Native Localization source changed')
    _require(all(type(before[k]) is type(runtime_identity[k]) and before[k] == runtime_identity[k]
                 for k in _NATIVE_FIELDS), 'Native row receipt Localization owner differs')
    canonical = row_query(table_name, columns, rowid_alias=rowid_alias,
                          after_rowid=after_rowid, limit=limit, max_cell_bytes=max_cell_bytes)
    _require(type(query) is str and query == canonical, 'Native row query is not the requested projection')
    query_sha = hashlib.sha256(query.encode('ascii')).hexdigest()
    _require(type(receipt['query_sha256']) is str and _HASH.fullmatch(receipt['query_sha256'])
             and receipt['query_sha256'] == query_sha, 'Native row receipt query hash differs')
    _integer(receipt['rows'], 0, limit, 'native row count')
    _integer(receipt['bytes'], 26, MAX_FILE_BYTES, 'native byte count')
    _require(type(receipt['sha256']) is str and _HASH.fullmatch(receipt['sha256']),
             'Invalid native stream hash')
    _integer(receipt['milliseconds'], 0, 30000, 'native elapsed milliseconds')
    _require(type(receipt['sqlite_status']) is int and receipt['sqlite_status'] == 101
             and type(receipt['statement_error']) is int and receipt['statement_error'] == 0,
             'Native statement did not complete with SQLITE_DONE')
    _require(receipt['cursor_released'] is True, 'Native result cursor was not released')
    for field in ('source_transactions_modified', 'atomic_snapshot_proven', 'backup_called'):
        _require(receipt[field] is False, 'Native stream changed or overclaims ' + field)
    result = read_row_stream(path, expected_sha256=receipt['sha256'], expected_bytes=receipt['bytes'],
                             columns=columns, rowid_alias=rowid_alias, after_rowid=after_rowid,
                             limit=limit, max_cell_bytes=max_cell_bytes)
    _require(len(result['rows']) == receipt['rows'], 'Native receipt rows differ from complete artifact')
    result.update(native_receipt_matches=True, native_receipt=copy.deepcopy(receipt),
                  query_sha256=query_sha, process=copy.deepcopy(process))
    return result
