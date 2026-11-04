import hashlib
import copy
import math
from pathlib import Path
import sqlite3
import struct
import tempfile
import unittest
from unittest import mock

from civ6_host.runtime.database_row_stream import (
    MAGIC, MAX_FILE_BYTES, MAX_ROWS, NATIVE_SCHEMA, encode_real, read_row_stream, row_query,
    validate_native_row_stream,
)
from civ6_host.runtime.native.database_capture992 import decode_real


def wire(names, rows, *, footer=True, footer_count=None):
    out = bytearray(MAGIC + struct.pack('<I', len(names)))
    for name in names:
        raw = name.encode('ascii')
        out += struct.pack('<I', len(raw)) + raw
    for row in rows:
        out += b'R'
        for value in row:
            if value is None:
                out += b'n'
            elif type(value) is int:
                out += b'i' + struct.pack('<i', value)
            elif type(value) is float:
                out += b'f' + struct.pack('<d', value)
            else:
                raw = value.encode('ascii')
                out += b't' + struct.pack('<I', len(raw)) + raw
    if footer:
        out += b'D' + struct.pack('<Q', len(rows) if footer_count is None else footer_count)
    return bytes(out)


class RowStreamTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / 'rows.bin'

    def parse(self, raw, **kwargs):
        self.path.write_bytes(raw)
        return read_row_stream(self.path, expected_sha256=hashlib.sha256(raw).hexdigest(),
                               expected_bytes=len(raw), columns=kwargs.pop('columns', ['value']), **kwargs)

    def test_sqlite_mixed_storage_and_sparse_int64_seek(self):
        with sqlite3.connect(':memory:') as db:
            db.execute('CREATE TABLE Mixed(value, other)')
            samples = [
                (-(2**63), -(2**63), None), (-17, 2**63 - 1, b'\x00\xff\x80'),
                (0, 'hé\x00llo', 1.0000000000000002), (19, 5e-324, '🙂'),
                (2**63 - 1, 1.7976931348623157e308, b''),
            ]
            db.executemany('INSERT INTO Mixed(rowid,value,other) VALUES(?,?,?)', samples)
            query = row_query('Mixed', ['value', 'other'], limit=3)
            cursor = db.execute(query)
            names = [column[0] for column in cursor.description]
            first = self.parse(wire(names, cursor.fetchall()), columns=['value', 'other'], limit=3)
            self.assertEqual([row['rowid'] for row in first['rows']], ['i:-9223372036854775808', 'i:-17', 'i:0'])
            self.assertEqual(first['rows'][0]['cells'], ['i:-9223372036854775808', 'n'])
            self.assertEqual(first['rows'][1]['cells'], ['i:9223372036854775807', 'b:00FF80'])
            self.assertEqual(first['rows'][2]['cells'][0], 't:' + 'hé\x00llo'.encode().hex().upper())
            self.assertEqual(decode_real(first['rows'][2]['cells'][1]), 1.0000000000000002)
            query = row_query('Mixed', ['value', 'other'], after_rowid='i:0', limit=3)
            cursor = db.execute(query)
            second = self.parse(wire(names, cursor.fetchall()), columns=['value', 'other'], after_rowid='i:0', limit=3)
            self.assertEqual([row['rowid'] for row in second['rows']], ['i:19', 'i:9223372036854775807'])
            self.assertEqual(decode_real(second['rows'][0]['cells'][0]), 5e-324)
            self.assertEqual(decode_real(second['rows'][1]['cells'][0]), 1.7976931348623157e308)
            self.assertTrue(second['artifact_identity_verified'])
            self.assertFalse(second['native_producer_verified'])
            self.assertFalse(second['source_bundle_verified'])
            empty = db.execute(row_query('Mixed', ['value'], after_rowid='i:9223372036854775807'))
            self.assertEqual(self.parse(wire([x[0] for x in empty.description], empty.fetchall()))['rows'], [])

    def test_real_codec_exact_extremes_and_negative_zero(self):
        for value in (0.0, -0.0, 1.0, 1.0000000000000002, 5e-324, -5e-324,
                      2.2250738585072014e-308, 1.7976931348623157e308):
            with self.subTest(value=value):
                encoded = encode_real(value)
                self.assertEqual(struct.pack('<d', decode_real(encoded)), struct.pack('<d', value))
                row = self.parse(wire(['capture_rowid', 'v1', 'r1'], [('i:1', 'r', value)]))
                self.assertEqual(row['rows'][0]['cells'], [encoded])
        self.assertEqual(encode_real(-0.0), 'r:-0p0')

    def test_complete_artifact_required(self):
        good = wire(['capture_rowid', 'v1', 'r1'], [('i:1', 'n', None)])
        corruptions = [good[:-9], good[:-1], good + b'x', b'BADMAGIC' + good[8:],
                       wire(['capture_rowid', 'v1', 'r1'], [('i:1', 'n', None)], footer_count=2)]
        for raw in corruptions:
            with self.subTest(raw=raw):
                with self.assertRaises(ValueError):
                    self.parse(raw)
        self.path.write_bytes(good)
        with self.assertRaisesRegex(ValueError, 'hash'):
            read_row_stream(self.path, expected_sha256='0'*64, expected_bytes=len(good), columns=['value'])
        with self.assertRaisesRegex(ValueError, 'byte count'):
            read_row_stream(self.path, expected_sha256=hashlib.sha256(good).hexdigest(),
                            expected_bytes=len(good)+1, columns=['value'])

    def test_schema_types_and_order_refused(self):
        names = ['capture_rowid', 'v1', 'r1']
        cases = [(['capture_rowid', 'v1', 'v1'], [('i:1', 'n', None)]),
                 (['capture_rowid', 'v1'], [('i:1', 'n')]),
                 (names, [(1, 'n', None)]), (names, [('i:1', 1, None)]),
                 (names, [('i:1', 'r', 1)]), (names, [('i:1', 'r', float('nan'))]),
                 (names, [('i:1', 'r', float('inf'))]), (names, [('i:1', 'n', 0.0)]),
                 (names, [('i:1', 'r:+0p0', None)]), (names, [('i:1', '!oversize', None)]),
                 (names, [('i:01', 'n', None)]), (names, [('i:9223372036854775808', 'n', None)]),
                 (names, [('i:1', 'b:ff', None)]),
                 (names, [('i:1', 'n', None), ('i:1', 'n', None)]),
                 (names, [('i:2', 'n', None), ('i:1', 'n', None)])]
        for header, rows in cases:
            with self.subTest(header=header, rows=rows):
                with self.assertRaises(ValueError):
                    self.parse(wire(header, rows))
        with self.assertRaisesRegex(ValueError, 'anchor'):
            self.parse(wire(names, [('i:-4', 'n', None)]), after_rowid='i:-4')

    def test_wire_bounds_and_unknown_values(self):
        names = ['capture_rowid', 'v1', 'r1']
        raw = wire(names, [('i:1', 'n', None)])
        header = wire(names, [], footer=False)
        corruptions = [MAGIC + struct.pack('<I', 258),
                       MAGIC + struct.pack('<I', 1) + struct.pack('<I', 257) + b'a'*257,
                       header + b'Rq' + b'D' + struct.pack('<Q', 0),
                       header + b'Rt' + struct.pack('<I', 131075) + b'x'*131075,
                       header + b'Rt' + struct.pack('<I', 1) + b'\xff',
                       header + b'Rf' + b'\x00'*3]
        for value in corruptions:
            with self.subTest(size=len(value)):
                with self.assertRaises(ValueError):
                    self.parse(value)
        with self.assertRaisesRegex(ValueError, 'cell exceeds'):
            self.parse(wire(names, [('i:1', 't:4142', None)]), max_cell_bytes=1)
        with self.assertRaisesRegex(ValueError, 'row limit'):
            self.parse(wire(names, [('i:1', 'n', None), ('i:2', 'n', None)]), limit=1)
        self.path.write_bytes(raw)
        with self.assertRaises(ValueError):
            read_row_stream(self.path, expected_sha256='0'*64, expected_bytes=MAX_FILE_BYTES+1, columns=['value'])

    def test_sql_inputs_and_quoting(self):
        with sqlite3.connect(':memory:') as db:
            db.execute('CREATE TABLE Quoted("a""; DROP TABLE Quoted; --", rowid)')
            db.execute('INSERT INTO Quoted VALUES(?,?)', ('safe', 4))
            query = row_query('Quoted', ['a"; DROP TABLE Quoted; --', 'rowid'], rowid_alias='_rowid_')
            cursor = db.execute(query)
            result = self.parse(wire([x[0] for x in cursor.description], cursor.fetchall()),
                                columns=['a"; DROP TABLE Quoted; --', 'rowid'], rowid_alias='_rowid_')
            self.assertEqual(result['rows'][0]['cells'], ['t:73616665', 'i:4'])
        invalid = [dict(table_name='x; DROP TABLE x'), dict(columns=['a', 'A']), dict(columns=[]),
                   dict(columns=['x\x00y']), dict(columns=['é']), dict(after_rowid='i:-0'),
                   dict(after_rowid='i:9223372036854775808'), dict(after_rowid=0),
                   dict(limit=True), dict(limit=MAX_ROWS+1), dict(max_cell_bytes=65537),
                   dict(columns=['rowid'])]
        for change in invalid:
            args = dict(table_name='Table1', columns=['value']); args.update(change)
            with self.subTest(change=change):
                with self.assertRaises(ValueError):
                    row_query(**args)


class NativeRowReceiptTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.path = Path(directory.name) / 'rows.bin'
        raw = wire(['capture_rowid', 'v1', 'r1'], [('i:1', 't:41', None)])
        self.path.write_bytes(raw)
        self.source = dict(
            locale='en_US', dictionary_flag=False, dictionary_address='0x100000',
            connection_address='0x200000', lookup_result_address='0x300000',
            auxiliary_result_address='0x400000', statement_address='0x500000',
            icu_address='0x600000', icu_bytes=1024, language_address='0x700000',
            language_index=0, languages_begin='0x700000', languages_end='0x700190',
            sqlite_address='0x800000',
        )
        identity = {key: value for key, value in self.source.items() if key != 'sqlite_address'}
        identity.update(fallback_policy_sql_sha256='a'*64, icu_sha256='b'*64)
        self.query = row_query('Rows', ['value'])
        self.process = dict(pid=1234, creation_filetime=132000000000000000,
                            image_path=r'C:\Games\CivilizationVI.exe')
        self.nonce = 'c'*32
        self.receipt = dict(
            schema=NATIVE_SCHEMA, status='ok', nonce=self.nonce, pid=self.process['pid'],
            creation_filetime=self.process['creation_filetime'], thread_id=123,
            lua_state='0x900000', source_before=self.source, source_after=copy.deepcopy(self.source),
            query_sha256=hashlib.sha256(self.query.encode('ascii')).hexdigest(), rows=1,
            bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest(), milliseconds=1,
            sqlite_status=101, statement_error=0, cursor_released=True,
            source_transactions_modified=False, atomic_snapshot_proven=False, backup_called=False,
        )
        self.arguments = dict(process=self.process, nonce=self.nonce, runtime_identity=identity,
                              query=self.query, path=self.path, table_name='Rows', columns=['value'])

    def test_complete_receipt_association_is_not_producer_authentication(self):
        result = validate_native_row_stream(self.receipt, **self.arguments)
        self.assertTrue(result['native_receipt_matches'])
        self.assertTrue(result['artifact_identity_verified'])
        self.assertFalse(result['native_producer_verified'])
        self.assertFalse(result['source_bundle_verified'])
        self.assertEqual(result['rows'], [{'rowid': 'i:1', 'cells': ['t:41']}])
        self.receipt['source_before']['locale'] = 'fr_FR'
        self.assertEqual(result['native_receipt']['source_before']['locale'], 'en_US')

    def test_receipt_spoofs_refused_before_opening_file(self):
        changes = [dict(extra=True), dict(status='error'), dict(schema='another'),
                   dict(nonce='d'*32), dict(pid=1235), dict(pid=True), dict(creation_filetime=False),
                   dict(thread_id=True), dict(lua_state='0x3'), dict(lua_state='0x0900000'),
                   dict(rows=True), dict(bytes=True), dict(milliseconds=True), dict(milliseconds=30001),
                   dict(sqlite_status=True), dict(sqlite_status=100), dict(statement_error=False),
                   dict(cursor_released=1), dict(source_transactions_modified=0),
                   dict(atomic_snapshot_proven=True), dict(backup_called=1),
                   dict(query_sha256='0'*64), dict(sha256='A'*64)]
        for change in changes:
            receipt = copy.deepcopy(self.receipt); receipt.update(change)
            with self.subTest(change=change), mock.patch(
                    'civ6_host.runtime.database_row_stream.read_row_stream') as parser:
                with self.assertRaises(ValueError):
                    validate_native_row_stream(receipt, **self.arguments)
                parser.assert_not_called()

    def test_source_owner_and_reference_mismatch_refused(self):
        changes = [('connection_address', '0x200008'), ('language_index', True),
                   ('dictionary_flag', 0), ('icu_bytes', True), ('sqlite_address', '0x1'),
                   ('languages_end', '0x700198'), ('extra', 'unexpected')]
        for key, value in changes:
            receipt = copy.deepcopy(self.receipt)
            receipt['source_before'][key] = value
            receipt['source_after'][key] = value
            with self.subTest(field=key):
                with self.assertRaises(ValueError):
                    validate_native_row_stream(receipt, **self.arguments)
        receipt = copy.deepcopy(self.receipt)
        receipt['source_after']['sqlite_address'] = '0x800008'
        with self.assertRaises(ValueError):
            validate_native_row_stream(receipt, **self.arguments)
        for field, value in [('icu_sha256', 'bad'), ('extra', 'unexpected'),
                             ('connection_address', '0x200008')]:
            arguments = copy.deepcopy(self.arguments)
            arguments['runtime_identity'][field] = value
            with self.subTest(reference=field):
                with self.assertRaises(ValueError):
                    validate_native_row_stream(self.receipt, **arguments)

    def test_query_identity_and_artifact_must_all_match(self):
        changes = [dict(query=self.query+' '), dict(table_name='Another'),
                   dict(after_rowid='i:0'), dict(limit=1), dict(max_cell_bytes=8192),
                   dict(process=dict(self.process, pid=1235)), dict(process=dict(self.process, extra=1))]
        for change in changes:
            args = dict(self.arguments); args.update(change)
            with self.subTest(change=change):
                with self.assertRaises(ValueError):
                    validate_native_row_stream(self.receipt, **args)
        receipt = dict(self.receipt, rows=0)
        with self.assertRaisesRegex(ValueError, 'receipt rows'):
            validate_native_row_stream(receipt, **self.arguments)
        receipt = dict(self.receipt, sha256='0'*64)
        with self.assertRaisesRegex(ValueError, 'hash'):
            validate_native_row_stream(receipt, **self.arguments)
        receipt = dict(self.receipt, bytes=self.receipt['bytes']+1)
        with self.assertRaisesRegex(ValueError, 'byte count'):
            validate_native_row_stream(receipt, **self.arguments)


if __name__ == '__main__':
    unittest.main()
