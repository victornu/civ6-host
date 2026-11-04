"""Full export/consumer fixtures for the explicit row-file producer."""
from contextlib import closing
import copy
import json
from pathlib import Path
import shutil
import sqlite3
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

from civ6_host.runtime.paths import resource_root
from civ6_host.runtime import localization_bulk_export as branch
from civ6_host.runtime import database_bulk_capture as bulk
from civ6_host.runtime.native import native_localization_logical_export as export
from civ6_host.runtime.native import native_official_bundle as consumer
from civ6_host.runtime.native import native_localization_query as provider
import test_database_bulk_capture as bulk_fixture
import test_localization_stream_bridge as bridge_fixture

HOST=Path(__file__).resolve().parents[1];LAB=resource_root()


def retained(name):
    qualified='tests.'+name
    if qualified in sys.modules:return sys.modules[qualified]
    parent=sys.modules.setdefault('tests',types.ModuleType('tests'))
    if not hasattr(parent,'__path__'):parent.__path__=[]
    path=LAB/'tests'/(name+'.py');source=path.read_text(encoding='utf8')
    source=source.replace('from civ6rl import ','from civ6_host.runtime.native import ')
    source=source.replace('from civ6rl.','from civ6_host.runtime.native.')
    module=types.ModuleType(qualified);module.__file__=str(path);sys.modules[qualified]=module
    exec(compile(source,str(path),'exec'),module.__dict__);setattr(parent,name,module)
    return module


def fixtures():
    retained('test_database_capture_bundle993');retained('test_native_localization_capture')
    return retained('test_native_localization_logical_export')


class BulkExportTests(unittest.TestCase):
    def setUp(self):
        fixture=fixtures();temp=tempfile.TemporaryDirectory(dir=LAB/'work',prefix='bulk-export-fixture-')
        self.addCleanup(temp.cleanup);self.root=Path(temp.name);self.process=fixture.Process()
        p=patch.object(export.runtime,'_file_digest',self.process.digest);p.start();self.addCleanup(p.stop)
        self.build_path=LAB/'work/official-capture/localization-stream/build03/build.json'
        self.build=provider.verify_build(self.build_path)
        with patch.object(export,'BUILD_PATH',self.build_path),patch.object(export,'_build',return_value=self.build):
            self.installation,self.expected=fixture.installation_fixture(self.root,self.process)
        self.client=fixture.Client(self.root)
        shutil.copyfile(HOST/'work/localization-stream-bridge/staged01/Civ6RLFileTransport.lua',self.client.inbox.parent/'Civ6RLFileTransport.lua')
        self.active=self.root/'active.sqlite';self.cache=self.root/'DebugLocalization.sqlite'
        with closing(sqlite3.connect(self.cache)) as db,db:
            db.execute('CREATE TABLE Sample(x)');db.execute('INSERT INTO Sample VALUES(?)',('stale',))
        shutil.copyfile(self.cache,self.active)
        with closing(sqlite3.connect(self.active)) as db,db:
            db.execute('DELETE FROM Sample');db.executemany('INSERT INTO Sample(rowid,x) VALUES(?,?)',[
                (-(2**63),None),(-4,-(2**63)),(7,2**63-1),(8,5e-324),(99999,'hé\0🙂'),(2**63-1,b'\0\xff')])
        self.producer=bulk_fixture.Producer(self.active,self.process.identity(),export.runtime_identity(self.expected))
        self.addCleanup(self.producer.db.close)
        self.client.read_active_database=self.producer.metadata;self.envelopes=[]
        def read_rows(request,path,*,provider_nonce,timeout,envelope_sink=None):
            self.assertEqual(provider_nonce,'a'*32)
            receipt=self.producer.rows(request,path,timeout=timeout)
            if envelope_sink is not None:
                self.producer.sequence+=1
                record=dict(type='transport_status',status='ok',reason='database_row_stream_read',request_id=request['nonce'],
                    sequence=self.producer.sequence,player_id=0,turn=146)
                self.envelopes.append(record);envelope_sink(record)
            return receipt
        self.client.read_database_rows=read_rows
    def capture(self):
        return export.export_localization(self.client,self.process,self.root/'export',installation_ref=self.installation,
            cache_path=self.cache,expected_player_id=0,expected_turn=146,expected_localization=self.expected,timeout_seconds=60)
    def repin(self,report):
        report=copy.deepcopy(report);reference=report.pop('reference');path=Path(reference['path'])
        path.write_text(json.dumps(report,indent=2)+'\n',encoding='utf8');return export.reference(path)
    def test_full_export_replay_materialization_and_shared_dependency_closure(self):
        original=self.cache.read_bytes();report=self.capture()
        checked=export.validate_export_manifest(report['reference'],expected_process=self.process.identity(),_with_verified_tables=True)
        self.assertEqual(checked['manifest']['comparison']['rows'],6)
        self.assertTrue(bulk.is_verified(checked['_verified_tables']))
        self.assertEqual(checked['manifest']['materialization']['capture_schema'],bulk.SCHEMA)
        self.assertEqual(self.cache.read_bytes(),original)
        self.assertEqual(report['row_files']['schema'],branch.PROFILE)
        refs=export.dependency_references(report['reference']);paths={r['path'] for r in refs}
        self.assertIn(report['row_files']['transport']['path'],paths)
        self.assertTrue(all(r['path'] in paths for r in report['row_files']['sources']))
        parent=consumer._logical_dependency_references_from_validated(export,report['reference'],checked['manifest'],checked['_verified_tables'])
        self.assertTrue(all(r['path'] in {p['path'] for p in parent} for r in report['row_files']['sources']))
    def test_wrong_bulk_source_or_runtime_rejected_after_rehash(self):
        report=self.capture()
        for mutate in (lambda r:r['row_files'].pop('sources'),
                       lambda r:r['row_files']['sources'].pop(),
                       lambda r:r['runtime_identity'].__setitem__('locale','en_US'),
                       lambda r:r['materialization'].__setitem__('capture_schema','legacy'),
                       lambda r:r.pop('row_files')):
            bad=copy.deepcopy(report);mutate(bad)
            with self.assertRaises(ValueError):export.validate_export_manifest(self.repin(bad))
    def test_no_legacy_page_fallback_if_row_method_or_transport_is_missing(self):
        del self.client.read_database_rows
        with self.assertRaisesRegex(ValueError,'Bulk row channel missing'):
            self.capture()
        self.assertEqual(self.producer.sequence,0)
    def test_rehashed_wrong_installed_transport_refuses_before_collection(self):
        path=self.client.inbox.parent/'Civ6RLFileTransport.lua';path.write_text('-- unknown')
        with self.assertRaisesRegex(ValueError,'transport differs'):
            self.capture()
        self.assertEqual(self.producer.sequence,0)
    def test_capture_proxy_retains_native_row_envelopes_in_global_order(self):
        events=[]
        def record(kind,value):
            events.append((kind,value['request_id'],value['sequence']));return value
        def metadata(request,*,timeout):return record('database_capture',self.producer.metadata(request,timeout=timeout))
        proxy=branch.capture_proxy(self.client,self.client.inbox,metadata,record,lambda:30)
        self.client=proxy;report=self.capture()
        self.assertTrue(self.envelopes);self.assertTrue(any(kind=='database_row_stream' for kind,_,_ in events))
        self.assertEqual([seq for _,_,seq in events],sorted(set(seq for _,_,seq in events)))
        self.assertEqual(len(events),json.loads(Path(report['tables_bundle']['path']).read_bytes())['requests'])
    def test_same_data_cannot_hide_producer_switch_across_save(self):
        report=self.capture();same=copy.deepcopy(report);branch.same_profile(report,same)
        for key in ('row_files','build','helper_module','provider_nonce'):
            changed=copy.deepcopy(report);changed.pop(key)
            with self.assertRaisesRegex(ValueError,'changed across'):
                branch.same_profile(report,changed)
        branch.same_profile({}, {})
    def test_capture_preflight_pins_exact_bulk_transport_and_refuses_unknown_source(self):
        from civ6_host.runtime.workers import capture_phase1_bundle994 as capture
        import time
        mod=self.root/'installed-mod'
        for relative in capture.BRIDGE_FILES:
            target=mod/relative;target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(LAB/'mod'/relative,target)
        transport=mod/'UI/Civ6RLFileTransport.lua'
        original=capture._bridge_pins(mod,time.monotonic()+30)
        self.assertEqual(original['UI/Civ6RLFileTransport.lua']['source']['sha256'],original['UI/Civ6RLFileTransport.lua']['installed']['sha256'])
        shutil.copyfile(HOST/'work/localization-stream-bridge/staged01/Civ6RLFileTransport.lua',transport)
        candidate=capture._bridge_pins(mod,time.monotonic()+30)
        item=candidate['UI/Civ6RLFileTransport.lua']
        self.assertEqual(item['source']['sha256'],branch.TRANSPORT_SHA256)
        self.assertEqual(item['installed']['sha256'],branch.TRANSPORT_SHA256)
        self.assertNotEqual(item['source']['path'],original['UI/Civ6RLFileTransport.lua']['source']['path'])
        transport.write_text('-- unrecognized')
        with self.assertRaisesRegex(ValueError,'differs from prepared source'):
            capture._bridge_pins(mod,time.monotonic()+30)


class EnvelopeSinkTests(unittest.TestCase):
    setUp=bridge_fixture.StreamBridgeTests.setUp
    native=bridge_fixture.StreamBridgeTests.native
    def test_actual_framed_client_records_validated_envelope_once(self):
        events=[]
        receipt=self.client.read_database_rows(self.packet,self.path,provider_nonce=self.provider_nonce,
            timeout=.2,envelope_sink=events.append)
        self.assertEqual(len(events),1);self.assertEqual(events[0]['request_id'],self.nonce)
        self.assertEqual(events[0]['reason'],'database_row_stream_read')
        self.assertEqual(receipt['rows'],2);self.assertEqual(self.native_calls,1)
    def test_global_record_refusal_fails_client_after_one_completed_native_file(self):
        def refuse(record):raise ValueError('global sequence refused')
        with self.assertRaisesRegex(ValueError,'global sequence refused'):
            self.client.read_database_rows(self.packet,self.path,provider_nonce=self.provider_nonce,
                timeout=.2,envelope_sink=refuse)
        self.assertTrue(self.path.exists());self.assertTrue(self.client._failed);self.assertEqual(self.native_calls,1)


if __name__=='__main__':unittest.main()
