import copy
from contextlib import closing
import hashlib
import json
from pathlib import Path
import shutil
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from civ6_host.runtime import database_bulk_capture as bulk
from civ6_host.runtime.native import database_capture_bundle993 as tables
from civ6_host.runtime.native.database_capture992 import SCHEMA, SERIALIZATION
from civ6_host.runtime.database_row_stream import NATIVE_SCHEMA
import test_database_row_stream as stream_fixtures
wire=stream_fixtures.wire


class Producer:
    """SQLite fixture, never presented as an official UI producer."""
    def __init__(self,path,process,identity):
        self.db=sqlite3.connect(path);self.db.text_factory=bytes
        self.process=process;self.identity=identity;self.sequence=0;self.row_calls=0;self.change=None
    def metadata(self,request,*,timeout):
        assert request['operation']!='rows'
        self.sequence+=1;op=request['operation']
        r=dict(schema=SCHEMA,serialization=SERIALIZATION,connection='localization',operation=op,
            player_id=request['expected_player_id'],turn=request['expected_turn'],atomic_snapshot=False)
        if op=='metadata':
            r.update(sqlite_version='3.13.0',real_encoding='binary53_exponent_v1',text_encoding='UTF-8',
                databases=[dict(seq=0,name='main',file='')])
        elif op=='schema':
            objects=[dict(type=t.decode(),name=n.decode(),table_name=table.decode(),sql_cell='n' if sql is None else 't:'+sql.hex().upper())
                for t,n,table,sql in self.db.execute('SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY type,name')]
            r.update(offset=request['offset'],limit=request['limit'],objects=objects[request['offset']:request['offset']+request['limit']])
        else:
            columns=[dict(cid=cid,name=n.decode(),declared_type=t.decode(),not_null=bool(nn),default_cell='n' if d is None else 't:'+d.hex().upper(),pk=pk)
                for cid,n,t,nn,d,pk in self.db.execute('PRAGMA table_info('+tables._quote(request['table_name'])+')')]
            r.update(table_name=request['table_name'],rowid_alias='rowid',columns=columns)
        nonce='metadata-'+str(self.sequence)
        return dict(type='transport_status',status='ok',reason='database_capture_read',request_id=nonce,
            sequence=self.sequence,player_id=r['player_id'],turn=r['turn'],diagnostics=dict(database_capture=r,
                request_id=nonce,completion='read_only_active_connection',native_game_core_busy=False))
    def rows(self,request,path,*,timeout):
        self.row_calls+=1
        if self.change:self.change(self,request)
        cursor=self.db.execute(request['query'])
        values=[[value.decode('ascii') if type(value)is bytes else value for value in row] for row in cursor.fetchall()]
        data=wire([c[0] for c in cursor.description],values)
        with path.open('xb') as output:output.write(data)
        source={k:v for k,v in self.identity.items() if k not in ('icu_sha256','fallback_policy_sql_sha256')}
        source['sqlite_address']='0x800000'
        return dict(schema=NATIVE_SCHEMA,status='ok',nonce=request['nonce'],pid=self.process['pid'],
            creation_filetime=self.process['creation_filetime'],thread_id=123,lua_state='0x900000',
            source_before=source,source_after=copy.deepcopy(source),query_sha256=hashlib.sha256(request['query'].encode()).hexdigest(),
            rows=len(values),bytes=len(data),sha256=hashlib.sha256(data).hexdigest(),milliseconds=1,
            sqlite_status=101,statement_error=0,cursor_released=True,source_transactions_modified=False,
            atomic_snapshot_proven=False,backup_called=False)


class BulkCaptureTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        self.active=self.root/'active.sqlite';self.template=self.root/'template.sqlite';self.folder=self.root/'capture'
        with closing(sqlite3.connect(self.template)) as db, db:
            db.executescript('CREATE TABLE Words(value,note);CREATE TABLE Empty(x);CREATE VIEW Display AS SELECT value FROM Words;')
            db.execute('INSERT INTO Words VALUES(?,?)',('old','stale'))
        shutil.copyfile(self.template,self.active)
        with closing(sqlite3.connect(self.active)) as db, db:
            db.execute('DELETE FROM Words')
            db.executemany('INSERT INTO Words(rowid,value,note) VALUES(?,?,?)',[
                (-(2**63),-(2**63),None),(-3,2**63-1,b'\0\xff'),(7,1.0000000000000002,'hé\0'),
                (2**63-1,5e-324,'🙂')])
        # Reuse the receipt fixture's declared identity, never native authority.
        fixture=stream_fixtures.NativeRowReceiptTests();fixture.setUp();self.addCleanup(fixture.doCleanups)
        self.process=fixture.process;self.identity=fixture.arguments['runtime_identity']
        self.producer=Producer(self.active,self.process,self.identity);self.addCleanup(self.producer.db.close)
    def capture(self,**kwargs):
        return bulk.capture_bundle(self.producer.metadata,kwargs.pop('reader',self.producer.rows),self.folder,
            process=self.process,runtime_identity=self.identity,expected_player_id=0,expected_turn=1,
            limits=bulk.Limits(page_size=2,row_page_size=2),**kwargs)
    def test_full_capture_replay_compare_and_materialize_reuse_common_algorithms(self):
        manifest=self.capture();self.assertEqual(manifest,bulk.verify_bundle(self.folder))
        self.assertEqual(manifest,tables.verify_bundle(self.folder))
        self.assertFalse(manifest['native_producer_verified'])
        self.assertEqual(manifest['rows_read'],8)
        result=tables.compare_sqlite_export(self.folder,self.active,connection='localization')
        self.assertEqual(result['rows'],4);self.assertEqual(result['capture_schema'],bulk.SCHEMA)
        before=self.template.read_bytes();output=self.root/'output.sqlite'
        materialized=tables.materialize_sqlite_export(self.folder,self.template,output)
        self.assertEqual(materialized['comparison']['status'],'exact_main_content_match')
        self.assertEqual(materialized['capture_schema'],bulk.SCHEMA)
        self.assertEqual(before,self.template.read_bytes())
        self.assertEqual(tables.compare_sqlite_export(self.folder,output,connection='localization'),materialized['comparison'])
        kinds={entry['kind'] for entry in manifest['journal']};self.assertEqual(kinds,{'rows','metadata'})
        for entry in manifest['journal']:
            if entry['kind']=='rows':
                response=json.loads((self.folder/entry['response']['path']).read_bytes())
                self.assertEqual(response['schema'],NATIVE_SCHEMA);self.assertNotIn('diagnostics',response)
    def test_exact_terminal_empty_chunks_and_rows_have_separate_request_kind(self):
        manifest=self.capture();tables_first=manifest['passes'][0][0]['tables']
        self.assertEqual([t['row_count'] for t in tables_first],[0,4])
        self.assertEqual([len(t['row_pages']) for t in tables_first],[1,3])
        evidence=bulk._verify_bundle(self.folder)
        self.assertEqual(len(list(evidence.iter_rows(tables_first[1]))),4)
        self.assertEqual(len(evidence.dependency_pins()),len(manifest['files'])+1)
    def test_second_pass_drift_refused_without_retry(self):
        def change(producer,request):
            if producer.row_calls==5:
                producer.db.execute("UPDATE Words SET note='changed' WHERE rowid=7");producer.db.commit()
        self.producer.change=change
        with self.assertRaisesRegex(ValueError,'changed between'):
            self.capture()
        self.assertEqual(json.loads((self.folder/'manifest.json').read_bytes())['status'],'failed')
    def test_failed_native_receipt_retains_submitted_request_and_refuses(self):
        def corrupt(request,path,*,timeout):
            receipt=self.producer.rows(request,path,timeout=timeout);receipt['query_sha256']='0'*64;return receipt
        with self.assertRaisesRegex(ValueError,'query hash'):
            self.capture(reader=corrupt)
        manifest=json.loads((self.folder/'manifest.json').read_bytes())
        self.assertEqual(manifest['status'],'failed');self.assertEqual(self.producer.row_calls,1)
        self.assertIsNotNone(manifest['journal'][-1]['request'])
    def test_row_and_manifest_mutation_invalidate_verified_evidence(self):
        manifest=self.capture();evidence=bulk._verify_bundle(self.folder)
        table=manifest['passes'][0][0]['tables'][1]
        entry=manifest['journal'][table['row_pages'][0]];path=self.folder/entry['rows']['path']
        path.write_bytes(path.read_bytes()+b'X')
        with self.assertRaisesRegex(ValueError,'changed'):
            list(evidence.iter_rows(table))
        with self.assertRaisesRegex(ValueError,'changed'):
            bulk.verify_bundle(self.folder)
    def test_rehashed_foreign_query_is_rejected_during_replay(self):
        manifest=self.capture();entry=next(e for e in manifest['journal'] if e['kind']=='rows')
        p=self.folder/entry['request']['path'];packet=json.loads(p.read_bytes());packet['query']+=' LIMIT 1'
        p.write_bytes(bulk._json(packet));new=bulk._pin(p)
        old=entry['request'];entry['request']=new
        manifest['files']=[new if x==old else x for x in manifest['files']]
        manifest['journal_bytes']+=new['bytes']-old['bytes']
        (self.folder/'manifest.json').write_bytes(bulk._json(manifest))
        with self.assertRaisesRegex(ValueError,'scope differs'):
            bulk.verify_bundle(self.folder)
    def test_unknown_process_or_attached_source_refuses_before_row_work(self):
        original=self.producer.metadata
        def metadata(request,*,timeout):
            record=original(request,timeout=timeout)
            if request['operation']=='metadata':record['diagnostics']['database_capture']['databases'].append(dict(seq=2,name='other',file=''))
            return record
        with self.assertRaisesRegex(ValueError,'Attached'):
            bulk.capture_bundle(metadata,self.producer.rows,self.folder,process=self.process,runtime_identity=self.identity,
                expected_player_id=0,expected_turn=1)
        self.assertEqual(self.producer.row_calls,0)
        with self.assertRaisesRegex(ValueError,'process identity'):
            bulk.capture_bundle(metadata,self.producer.rows,self.root/'other',process={**self.process,'pid':True},
                runtime_identity=self.identity,expected_player_id=0,expected_turn=1)
        self.assertFalse((self.root/'other').exists())
    def test_parsed_metadata_bytes_are_hashed_even_after_file_pin_succeeds(self):
        manifest=self.capture()
        target=self.folder/manifest['journal'][0]['response']['path'];original=Path.read_bytes
        def changed(path):
            raw=original(path)
            return raw+b' ' if path==target else raw
        with patch.object(Path,'read_bytes',changed), self.assertRaisesRegex(ValueError,'Parsed bulk JSON bytes changed'):
            bulk.verify_bundle(self.folder)


if __name__=='__main__':unittest.main()
