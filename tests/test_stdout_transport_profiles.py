"""Shared stdout grammar, source selection and the actual pipe-reader method."""
import hashlib
from copy import deepcopy
import importlib.util
import io
import json
from pathlib import Path
import queue
from types import SimpleNamespace
import tempfile
import unittest

from civ6_host.runtime import stdout_transport_profiles as profiles
from civ6_host.runtime.native import native_stdout_transport as decoder
from civ6_host.runtime.native.native_saved_session import NativeSavedSession
from civ6_host.runtime.provenance import historical_source_file

PREFIX='Chasing target at: 1, 2. Moving Unit ID: 3. Adjacent hex is: 4, 5. Distance: 2147483647'
WAIT='{"stage":"empty_job_set_waited","export":"EXP_JobManager_Wait","first_argument_raw":42,"member8":0,"contract":"null_second_member_only"}'


class StdoutProfiles(unittest.TestCase):
    def test_xp2_selects_its_own_producer_and_host_without_extending_grammar(self):
        proof=profiles.verify_xp2()
        self.assertFalse(proof['native_execution'])
        selected=profiles.selected_profile(profiles.XP2_CORE_SHA256,profiles.XP2_HOST)
        raw=(PREFIX*2+WAIT+'\n').encode()
        event,record=profiles.decode_record(raw,selected,line_number=5)
        self.assertEqual(event,json.loads(WAIT))
        self.assertEqual(record['source_sha256'],profiles.XP2_SOURCE[1])
        self.assertEqual(record['raw_sha256'],hashlib.sha256(raw).hexdigest())
        for changed in (raw.replace(b'2147483647',b'42'),raw[:-1],
                        (PREFIX+'{"stage":"official_action_ack"}\n').encode()):
            with self.assertRaises(ValueError):profiles.decode_record(changed,selected,line_number=5)
        with self.assertRaises(ValueError):
            profiles.selected_profile(profiles.XP2_CORE_SHA256,profiles.XP1_HOST)
        for path,digest in profiles.source_dependencies(core_sha256=profiles.XP2_CORE_SHA256).items():
            self.assertEqual(hashlib.sha256(Path(path).read_bytes()).hexdigest(),digest)

    def decode(self,text,*,xp1=True):
        return decoder.decode_stdout(text,core_sha256=profiles.XP1_CORE_SHA256 if xp1 else profiles.BASE_CORE_SHA256,
                                     host_sha256=profiles.XP1_HOST if xp1 else profiles.BASE_HOST)

    def test_source_and_retained_failed_line_are_exact_without_reclassifying_failure(self):
        proof=profiles.verify_xp1();row=proof['retained_failure']['occurrences'][0]
        result=self.decode(row['raw_line']);decoder.require_complete(result)
        self.assertEqual(result['source_sha256'],profiles.XP1_SOURCE[1])
        self.assertEqual(result['events'],[row['host_event']])
        self.assertEqual(result['stdout_native'][0]['raw_line'],row['raw_line'])
        self.assertEqual(hashlib.sha256(row['raw_line'].encode()).hexdigest(),row['raw_line_sha256'])
        self.assertTrue(row['failed_run_remains_failed']);self.assertFalse(result['semantic_validation_replaced'])

    def test_base_outputs_are_identical_to_retained_decoder(self):
        spec=importlib.util.spec_from_file_location('retained_stdout',historical_source_file('civ6rl/native_stdout_transport.py'))
        old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)
        for text in ('{"stage":"before"}\n',PREFIX+WAIT+'\n',PREFIX*2+WAIT+'\n',PREFIX+'noise'+WAIT+'\n'):
            with self.subTest(text=text[:30]):
                expected=old.decode_stdout(text,core_sha256=profiles.BASE_CORE_SHA256,host_sha256=profiles.BASE_HOST)
                self.assertEqual(self.decode(text,xp1=False),expected)

    def test_unknown_identity_proof_source_and_corrupted_grammar_are_refused(self):
        for core,host in ((profiles.XP1_CORE_SHA256,profiles.BASE_HOST),(profiles.BASE_CORE_SHA256,profiles.XP1_HOST),('0'*64,profiles.XP1_HOST)):
            with self.assertRaises(ValueError):decoder.decode_stdout(WAIT+'\n',core_sha256=core,host_sha256=host)
        with self.assertRaises(ValueError):
            decoder.decode_stdout(PREFIX+WAIT+'\n',core_sha256=profiles.XP1_CORE_SHA256,
                                  host_sha256=profiles.XP1_HOST,source_path=Path(historical_source_file('civ6rl/native_stdout_transport.py')))
        for raw in (PREFIX+WAIT,PREFIX.replace('2147483647','42')+WAIT+'\n',PREFIX+WAIT+'x\n',
                    PREFIX+'{"stage":"official_action_ack"}\n',PREFIX*1025+WAIT+'\n',
                    PREFIX.replace('1, 2','2147483648, 2')+WAIT+'\n'):
            result=self.decode(raw)
            with self.assertRaises(ValueError):decoder.require_complete(result)
        result=self.decode(PREFIX*2+WAIT+'\n');decoder.require_complete(result)
        result['source_sha256']=profiles.BASE_SOURCE[1]
        with self.assertRaises(ValueError):decoder.require_complete(result)

    def test_real_parent_pipe_reader_keeps_raw_bytes_and_only_ingests_wait_event(self):
        raw=(PREFIX*2+WAIT+'\n').encode();failed=[];received=[]
        with tempfile.TemporaryDirectory() as directory:
            owner=SimpleNamespace(run=Path(directory),event_line_limit_bytes=262144,
                stdout_identity=dict(core_sha256=profiles.XP1_CORE_SHA256,host_sha256=profiles.XP1_HOST),
                stdout_native_records=[],responses=queue.Queue(),_fail=lambda *args:failed.append(args),
                _information_store=SimpleNamespace(ingest=received.append))
            NativeSavedSession._read_stream(owner,io.BytesIO(raw),'events.jsonl',1048576,True)
            self.assertFalse(failed);self.assertEqual((owner.run/'events.jsonl').read_bytes(),raw)
            self.assertEqual(received,[json.loads(WAIT)]);self.assertTrue(owner.responses.empty())
            self.assertEqual(owner.stdout_native_records,[dict(line_number=1,
                raw_sha256=hashlib.sha256(raw).hexdigest(),source_sha256=profiles.XP1_SOURCE[1],
                rule='exact-repeated-Chasing-format-plus-exact-empty-Wait')])

    def test_offline_ledger_reader_uses_same_decoder_and_does_not_invent_legacy_profile(self):
        from qualify_xp1_configuration import decode_saved_stdout_record,validate_saved_stdout_profile,saved_load_events
        profile=dict(schema=decoder.SCHEMA,core_sha256=profiles.XP1_CORE_SHA256,
                     host_sha256=profiles.XP1_HOST,source_sha256=profiles.XP1_SOURCE[1])
        raw=(PREFIX+WAIT+'\n').encode();event,record=decode_saved_stdout_record(raw,profile,line_number=7)
        self.assertEqual(event,json.loads(WAIT));self.assertEqual(record['line_number'],7)
        self.assertEqual(record['source_sha256'],profiles.XP1_SOURCE[1])
        with self.assertRaises(json.JSONDecodeError):decode_saved_stdout_record(raw,line_number=7)
        bad=dict(profile,source_sha256=profiles.BASE_SOURCE[1])
        with self.assertRaises(ValueError):validate_saved_stdout_profile(bad)
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'events.jsonl';path.write_bytes(raw)
            expected=dict(record,line_number=1)
            count,events=saved_load_events(path,stdout_transport=profile,stdout_native_records=[expected])
            self.assertEqual(count,1)
            with self.assertRaisesRegex(ValueError,'occurrence ledger'):
                saved_load_events(path,stdout_transport=profile,stdout_native_records=[])

    def test_complete_stream_authenticates_both_historical_rules_and_exact_order(self):
        profile=profiles.selected_profile(profiles.XP1_CORE_SHA256,profiles.XP1_HOST)
        lines=[b'{"stage":"before"}\n',(PREFIX+WAIT+'\n').encode(),(PREFIX*2+WAIT+'\n').encode()]
        records=[profiles.decode_record(line,profile,line_number=index)[1]
                 for index,line in enumerate(lines,1) if index>1]
        self.assertEqual([r['rule'] for r in records],[
            'exact-Chasing-format-plus-exact-empty-Wait',
            'exact-repeated-Chasing-format-plus-exact-empty-Wait'])
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'events.jsonl';path.write_bytes(b''.join(lines))
            def read(ledger,**kwargs):
                return list(profiles.iter_records(path,profile=profile,expected_records=ledger,
                            byte_limit=kwargs.get('byte_limit',1048576),line_limit=kwargs.get('line_limit',262144)))
            self.assertEqual([r[0] for r in read(records)],[1,2,3])
            for mode in ('missing','reordered','raw_hash','position','rule','source','wrong_type'):
                bad=deepcopy(records)
                if mode=='missing':bad.pop()
                elif mode=='reordered':bad.reverse()
                elif mode=='raw_hash':bad[0]['raw_sha256']='0'*64
                elif mode=='position':bad[0]['line_number']=1
                elif mode=='rule':bad[0]['rule']=bad[1]['rule']
                elif mode=='source':bad[0]['source_sha256']=profiles.BASE_SOURCE[1]
                else:bad={}
                with self.subTest(mode=mode),self.assertRaises(ValueError):read(bad)
            with self.assertRaisesRegex(ValueError,'budget'):read(records,byte_limit=10)
            with self.assertRaisesRegex(ValueError,'oversized'):read(records,line_limit=10)
            path.write_bytes(lines[0]+lines[1].rstrip(b'\n'))
            with self.assertRaisesRegex(ValueError,'Incomplete'):read(records[:1])
            path.write_bytes(lines[0]+lines[1]+b'{"stage":"after"}\n')
            # A caller must exhaust the stream. A matching prefix alone cannot
            # authenticate a ledger entry claimed later in the transcript.
            pending=profiles.iter_records(path,profile=profile,expected_records=records,byte_limit=1048576)
            self.assertEqual(next(pending)[2],{'stage':'before'})
            with self.assertRaisesRegex(ValueError,'occurrence ledger'):list(pending)
            original_profile, original_ledger = profile.copy(), deepcopy(records[:1])
            pending=profiles.iter_records(path,profile=original_profile,
                expected_records=original_ledger,byte_limit=1048576)
            self.assertEqual(next(pending)[2],{'stage':'before'})
            original_profile.clear()
            original_ledger[0]['raw_sha256']='0'*64
            self.assertEqual([number for number, _, _ in pending],[2,3])

    def test_retained_parser_refusal_replay_authenticates_native_destroy_and_archived_sources(self):
        from qualify_xp1_configuration import replay_saved_close_parser_refusal
        from civ6_host.runtime.paths import resource_root
        repo=Path(__file__).resolve().parents[1]
        run=resource_root()/'work/xp1t/run-47d392b790a54ecc80f843189b01967d'
        archive=repo/'work/xp1-turn-integration/native-session31/executed-sources.zip'
        if not archive.is_file() or not run.is_dir():self.skipTest('Private retained parser refusal absent')
        raw=(run/'supervisor.json').read_bytes()
        supervisor_sha='569792aae829ef6791742f474d7472cc0fce1a0041acc479a06ccc984d102871'
        archive_sha='54f58a4216e41bc8f6e32f21e262b7ad2f349e3f9ae1f41dc8b0fec6217ccf69'
        report,proof=replay_saved_close_parser_refusal(run,supervisor_sha,
            archive=archive,archive_sha256=archive_sha)
        self.assertTrue(report['normal_destroy_called']);self.assertIsNone(report['error'])
        self.assertTrue(proof['native_lifetime']['native_unload_and_destroy_returned'])
        self.assertFalse(proof['native_calls_during_review']);self.assertTrue(proof['projection_only'])
        self.assertIn('src/civ6_host/runtime/native/network_session.py',proof['executed_host_python_sources'])
        self.assertEqual((run/'supervisor.json').read_bytes(),raw)
        self.assertFalse(json.loads(raw)['normal_destroy_called'])
        for original,archived in (('0'*64,archive_sha),(supervisor_sha,'0'*64)):
            with self.assertRaises(ValueError):replay_saved_close_parser_refusal(run,original,
                archive=archive,archive_sha256=archived)

    def test_reviewed_checkpoint_cannot_use_success_fields_or_change_normal_load_admission(self):
        from qualify_xp1_configuration import replay_saved_close_parser_refusal
        from civ6_host.runtime import network_checkpoint
        from civ6_host.runtime.paths import resource_root
        repo=Path(__file__).resolve().parents[1]
        run=resource_root()/'work/xp1t/run-47d392b790a54ecc80f843189b01967d'
        archive=repo/'work/xp1-turn-integration/native-session31/executed-sources.zip'
        if not archive.is_file() or not run.is_dir():self.skipTest('Private retained parser refusal absent')
        reference=json.loads((run/'checkpoint-result-23.json').read_bytes())['save_result']['manifest']
        with self.assertRaisesRegex(ValueError,'producing process'):network_checkpoint.manifest(reference)
        _,proof=replay_saved_close_parser_refusal(run,
            '569792aae829ef6791742f474d7472cc0fce1a0041acc479a06ccc984d102871',archive=archive,
            archive_sha256='54f58a4216e41bc8f6e32f21e262b7ad2f349e3f9ae1f41dc8b0fec6217ccf69')
        for mode in ('success_fields','original_hash','native_receipt','archive_hash','source_inventory'):
            bad=deepcopy(proof)
            if mode=='success_fields':bad=dict(normal_destroy_authenticated=True,error=None)
            elif mode=='original_hash':bad['original_supervisor']['sha256']='0'*64
            elif mode=='native_receipt':bad['native_lifetime']['native_unload_and_destroy_returned']=False
            elif mode=='archive_hash':bad['executed_sources_archive']['sha256']='0'*64
            else:bad['executed_host_python_sources']={}
            with self.subTest(mode=mode),self.assertRaises(ValueError):
                network_checkpoint.manifest(reference,reviewed_producers={str(run/'supervisor.json'):bad})
        with self.assertRaisesRegex(ValueError,'producing process'):network_checkpoint.manifest(reference)


if __name__=='__main__':unittest.main()
