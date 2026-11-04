"""Pure synthetic writer files and FileClient fixtures; never a live capture."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from civ6_host.runtime import capture_response_continuation as continuation
from civ6_host.runtime.native import file_client, response_file_client as direct
from civ6_host.runtime.native import native_response_file_writer as writer
from civ6_host.runtime.native.file_client import FileTransportError


HOST = Path(__file__).resolve().parents[1]


def status(sequence, request, reason, *, ok=True, **fields):
    return dict(schema_version=1, type='transport_status', sequence=sequence,
                request_id=request, player_id=0, turn=1,
                status='ok' if ok else 'error', reason=reason, **fields)


class CaptureContinuationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(dir=HOST/'work')
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        (self.root/'work').mkdir()
        self.enterContext(patch.object(writer, 'ROOT', self.root))
        self.prepared = writer.prepare_directory(self.root/'work/responses',
            session_id='a'*32, writer_nonce='b'*32, max_records=100,
            max_total_bytes=4*1024*1024)
        self.process = dict(pid=123, creation_filetime=456, image_path='fixture.exe')
        self.install = self.root/'work/installation.json'
        self.install.write_text(json.dumps(dict(player_id=0, turn=1)), encoding='utf-8')
        self.installation = writer.reference(self.install)
        self.enterContext(patch.object(writer, 'validate_installation', return_value=dict(
            status='ui_writer_installed', prepared=self.prepared, process=self.process)))
        self.log = self.root/'work/Lua.log'
        self.inbox = self.root/'work/Civ6RLInbox.lua'
        self.inbox.write_text('-- fixture idle', encoding='ascii')
        self.responses = Path(self.prepared['directory'])
        self.base = [self.hello(19, '1'*32),
            status(23, '2'*32, 'database_capture_read_failed', ok=False,
                   diagnostics=dict(detail='definite bounded fixture refusal')),
            status(24, '3'*32, 'file_transport_closed')]
        self.reset(self.base)
        self.commands = []
        self.change = None

    def hello(self, sequence, request):
        return status(sequence, request, 'file_transport_ready', diagnostics=dict(
            response_mode=direct.MODE, writer_nonce=self.prepared['writer_nonce']))

    def append(self, record):
        raw = json.dumps(record, ensure_ascii=False, allow_nan=False).encode('utf-8')
        self.count += 1
        self.total += len(raw)
        self.sequence = record['sequence']
        name = str(record['sequence'])+'-'+record['request_id']+'.json'
        (self.responses/name).write_bytes(raw)
        receipt = dict(schema=writer.RECEIPT_SCHEMA, status='written',
            writer_nonce=self.prepared['writer_nonce'], session_id=self.prepared['session_id'],
            request_id=record['request_id'], sequence=record['sequence'], filename=name,
            bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest(), count=self.count,
            total_bytes=self.total, durable_flush=False)
        line = 'Civ6RL: CIV6RL_FILE_RECEIPT '+json.dumps(receipt)+'\n'
        with self.log.open('a', encoding='utf-8', newline='') as stream:
            stream.write(line)
        return line

    def reset(self, records):
        # These are synthetic files in this test's unique private directory.
        self.assertTrue(self.responses.is_relative_to(self.root/'work'))
        for path in self.responses.iterdir():
            self.assertEqual(path.parent, self.responses)
            path.unlink()
        self.log.write_text('unrelated fixture log\n', encoding='utf-8')
        self.count = self.total = self.sequence = 0
        for record in records:
            self.append(deepcopy(record))

    def prepare(self, name='predecessor.json'):
        return continuation.prepare_predecessor(self.installation, self.log, self.root/'work'/name)

    def publish(self, inbox, command):
        self.assertEqual(inbox, self.inbox)
        self.assertTrue(self.inbox.with_suffix('.lua.lock').is_file())
        self.commands.append(deepcopy(command))
        sequence = self.sequence+1
        if command['op'] == 'hello':
            record = self.hello(sequence, command['command_id'])
        elif command['op'] == 'observe':
            record = dict(schema_version=1, type='observation', sequence=sequence,
                request_id=command['command_id'], player_id=0, turn=1, event='file_poll',
                observation=dict(units=[], cities=[],
                    economy=dict(science=0, culture=0, gold=0, faith=0),
                    can_end_turn=True, blocker=0))
        else:
            record = status(sequence, command['command_id'],
                'file_transport_closed' if command['op'] == 'close' else 'diagnostics')
        self.append(self.change(command,record) if self.change is not None else record)

    def test_predecessor_replays_native_chain_and_preserves_immutable_files(self):
        originals = {p.name:p.read_bytes() for p in self.responses.iterdir()}
        reference = self.prepare()
        report = continuation.validate_predecessor(reference, self.installation, exact_directory=True)
        self.assertEqual(report['process'], self.process)
        self.assertEqual(report['prepared'], self.prepared)
        self.assertEqual(report['boundary'], dict(player_id=0, turn=1))
        self.assertEqual(report['reader_state'], dict(sequence=24, count=3, total_bytes=self.total))
        self.assertEqual(len(report['receipts']), 3)
        self.assertEqual(report['prefix_snapshot']['bytes'],report['log']['prefix_bytes'])
        self.assertEqual(report['prefix_snapshot']['sha256'],report['log']['prefix_sha256'])
        self.assertEqual(report['terminal']['reason'], 'file_transport_closed')
        self.assertEqual({p.name:p.read_bytes() for p in self.responses.iterdir()}, originals)
        with self.assertRaises(ValueError):self.prepare()

    def test_row_stream_receipt_joins_real_prefix_and_boundary_guards(self):
        row = status(23, '2'*32, 'database_row_stream_read', diagnostics=dict(
            request_id='2'*32, completion='read_only_active_connection'))
        records = [self.hello(19, '1'*32), row,
                   status(24, '3'*32, 'file_transport_closed')]
        self.reset(records)
        reference = self.prepare('row-stream-predecessor.json')
        report = continuation.validate_predecessor(reference, self.installation,
            exact_directory=True)
        self.assertEqual(report['reader_state']['count'], 3)
        self.assertEqual(report['terminal']['reason'], 'file_transport_closed')
        self.assertEqual(report['log']['prefix_bytes'], self.log.stat().st_size)

        for mode, changed in (
            ('player_turn_drift', dict(row, turn=2)),
            ('unknown_reason', status(23, '2'*32, 'database_row_stream_unknown')),
        ):
            with self.subTest(mode=mode):
                self.reset([records[0], changed, records[2]])
                with self.assertRaises((ValueError, FileTransportError)):
                    self.prepare(mode+'.json')

    def test_continued_real_file_client_lock_handshake_observation_and_later_provenance(self):
        reference = self.prepare()
        originals = {p.name:p.read_bytes() for p in self.responses.iterdir()}
        client = continuation.ContinuedResponseFileClient(self.inbox, self.log,
            installation=self.installation, predecessor=reference, timeout=1)
        self.assertEqual(client._collector.reader.count, 3)
        with patch.object(file_client, 'publish_command', side_effect=self.publish):
            with client:
                self.assertEqual(client._collector.reader.count, 4)
                self.assertEqual(client._collector.reader.sequence, 25)
                self.assertEqual(client.observe()['type'], 'observation')
                self.assertEqual(client._collector.reader.count, 5)
        self.assertEqual([c['op'] for c in self.commands], ['hello','observe','close'])
        self.assertEqual(self.commands[0]['session_id'], self.prepared['session_id'])
        self.assertEqual(self.commands[0]['response_mode'], direct.MODE)
        self.assertEqual(self.commands[0]['writer_nonce'], self.prepared['writer_nonce'])
        self.assertFalse(self.commands[0]['resume_hotseat'])
        self.assertFalse(self.inbox.with_suffix('.lua.lock').exists())
        continuation.validate_predecessor(reference, self.installation, exact_directory=False)
        with self.assertRaises(ValueError):
            continuation.validate_predecessor(reference, self.installation, exact_directory=True)
        for name, raw in originals.items():self.assertEqual((self.responses/name).read_bytes(), raw)
        next_reference = self.prepare('second-predecessor.json')
        self.assertEqual(continuation.validate_predecessor(next_reference,self.installation)['connection_count'],2)

    def test_default_client_and_capture_only_guards_are_unchanged(self):
        reference = self.prepare()
        with self.assertRaisesRegex(ValueError, 'not empty'):
            direct.ResponseFileClient(self.inbox,self.log,installation=self.installation)
        with self.assertRaisesRegex(ValueError,'cannot resume'):
            continuation.ContinuedResponseFileClient(self.inbox,self.log,
                installation=self.installation,predecessor=reference,resume_hotseat=True)
        client = continuation.ContinuedResponseFileClient(self.inbox,self.log,
            installation=self.installation,predecessor=reference)
        with patch.object(file_client,'publish_command',side_effect=self.publish):
            for operation in ('action','end_turn','exit_to_menu','city_attack_request','city_capture_arm'):
                with self.subTest(operation=operation),self.assertRaises(FileTransportError):
                    client._publish(operation,'f'*32)
            with self.assertRaises(ValueError):client._publish('hello','f'*32,resume_hotseat=False)
        self.assertFalse(self.commands)

    def test_unclosed_duplicate_wrong_boundary_protocol_and_missing_receipts_are_refused(self):
        cases = {'unclosed':self.base[:-1], 'no_hello':self.base[1:],
                 'double_hello':[self.base[0],self.hello(20,'4'*32),self.base[-1]],
                 'duplicate_id':[self.base[0],self.base[1],status(24,'2'*32,'file_transport_closed')],
                 'wrong_turn':[self.base[0],dict(self.base[1],turn=2),self.base[-1]],
                 'wrong_player':[self.base[0],dict(self.base[1],player_id=1),self.base[-1]],
                 'unsupported':[self.base[0],dict(self.base[1],type='action_result'),self.base[-1]]}
        for mode,records in cases.items():
            with self.subTest(mode=mode):
                self.reset(records)
                with self.assertRaises((ValueError,FileTransportError)):self.prepare(mode+'.json')
        for mode in ('missing','duplicate','nonce','count','bytes','partial','io_error','fallback'):
            with self.subTest(mode=mode):
                self.reset(self.base);lines=self.log.read_text(encoding='utf-8').splitlines(keepends=True)
                if mode=='missing':lines.pop(2)
                elif mode=='duplicate':lines.insert(2,lines[1])
                elif mode in ('nonce','count','bytes'):
                    receipt=json.loads(lines[2].split(continuation._RECEIPT)[1])
                    if mode=='nonce':receipt['writer_nonce']='c'*32
                    elif mode=='count':receipt['count']+=1
                    else:receipt['total_bytes']+=1
                    lines[2]='CIV6RL_FILE_RECEIPT '+json.dumps(receipt)+'\n'
                elif mode=='partial':lines[-1]=lines[-1].rstrip('\n')
                elif mode=='io_error':lines.insert(2,'CIV6RL_IO_ERROR fixture_failed\n')
                else:lines.insert(2,'CIV6RL_FRAME '+self.prepared['session_id']+' forbidden\n')
                self.log.write_text(''.join(lines),encoding='utf-8')
                with self.assertRaises((ValueError,FileTransportError)):self.prepare(mode+'.json')

    def test_payload_report_identity_and_prefix_tampering_are_revalidated(self):
        reference=self.prepare();original=Path(reference['path']).read_bytes()
        for mode in ('process','prepared','counter','lines','log_identity'):
            with self.subTest(mode=mode):
                report=json.loads(original)
                if mode=='process':report['process']['creation_filetime']+=1
                elif mode=='prepared':report['prepared']['writer_nonce']='d'*32
                elif mode=='counter':report['reader_state']['count']+=1
                elif mode=='lines':report['receipts'].pop()
                else:report['log']['inode']+=1
                path=self.root/'work'/('bad-'+mode+'.json');path.write_text(json.dumps(report),encoding='utf-8')
                with self.assertRaises(ValueError):
                    continuation.validate_predecessor(writer.reference(path),self.installation,
                        exact_directory=mode=='log_identity')
        payload=next(self.responses.iterdir());raw=payload.read_bytes()
        payload.write_bytes(raw.replace(b'"turn": 1',b'"turn": 2'))
        with self.assertRaises(ValueError):continuation.validate_predecessor(reference,self.installation)
        payload.write_bytes(raw)
        self.log.write_text(self.log.read_text(encoding='utf-8').replace('unrelated','altered!!'),encoding='utf-8')
        continuation.validate_predecessor(reference,self.installation)
        with self.assertRaises(ValueError):
            continuation.validate_predecessor(reference,self.installation,exact_directory=True)
        snapshot=Path(json.loads(original)['prefix_snapshot']['path'])
        snapshot.write_bytes(snapshot.read_bytes().replace(b'unrelated',b'altered!!'))
        with self.assertRaises(ValueError):continuation.validate_predecessor(reference,self.installation)

    def test_retained_snapshot_remains_valid_after_origin_deletion_and_identical_resource_copy(self):
        reference=self.prepare()
        report=continuation.validate_predecessor(reference,self.installation)
        snapshot=Path(report['prefix_snapshot']['path']);raw=snapshot.read_bytes()
        replacement=snapshot.with_name('copied-prefix.log');replacement.write_bytes(raw)
        replacement.replace(snapshot)  # A resource copy need not retain an inode.
        self.log.unlink()
        self.assertEqual(continuation.validate_predecessor(reference,self.installation),report)
        with patch.object(file_client,'publish_command',side_effect=self.publish):
            with self.assertRaises((OSError,ValueError)):
                continuation.ContinuedResponseFileClient(self.inbox,self.log,
                    installation=self.installation,predecessor=reference)
        self.assertFalse(self.commands)

    def test_live_connect_refuses_rotated_origin_even_when_retained_provenance_validates(self):
        reference=self.prepare()
        client=continuation.ContinuedResponseFileClient(self.inbox,self.log,
            installation=self.installation,predecessor=reference,timeout=1)
        original=self.log.read_bytes()
        self.log.rename(self.log.with_name('rotated-Lua.log'))
        self.log.write_bytes(original)
        continuation.validate_predecessor(reference,self.installation,exact_directory=False)
        with patch.object(file_client,'publish_command',side_effect=self.publish):
            with self.assertRaisesRegex(ValueError,'replaced'):client.connect()
            with self.assertRaises(FileTransportError):client.connect()
        self.assertFalse(self.commands)
        self.assertFalse(self.inbox.with_suffix('.lua.lock').exists())

    def test_changes_after_construction_refuse_under_lock_without_publishing_hello_or_close(self):
        reference=self.prepare()
        client=continuation.ContinuedResponseFileClient(self.inbox,self.log,
            installation=self.installation,predecessor=reference,timeout=1)
        (self.responses/'unreported.tmp').write_bytes(b'extra')
        with patch.object(file_client,'publish_command',side_effect=self.publish):
            with self.assertRaisesRegex(ValueError,'extra'):client.connect()
            with self.assertRaises(FileTransportError):client.connect()
        self.assertTrue(client._failed)
        self.assertFalse(self.commands)
        self.assertFalse(self.inbox.with_suffix('.lua.lock').exists())
        (self.responses/'unreported.tmp').unlink()
        client=continuation.ContinuedResponseFileClient(self.inbox,self.log,
            installation=self.installation,predecessor=reference,timeout=1)
        self.install.write_text('{"changed":true}',encoding='utf-8')
        with patch.object(file_client,'publish_command',side_effect=self.publish):
            with self.assertRaisesRegex(ValueError,'changed'):client.connect()
        self.assertFalse(self.commands)
        self.assertFalse(self.inbox.with_suffix('.lua.lock').exists())

    def test_invalid_new_response_fails_once_and_never_replays_the_capture(self):
        reference=self.prepare()
        client=continuation.ContinuedResponseFileClient(self.inbox,self.log,
            installation=self.installation,predecessor=reference,timeout=1)
        self.change=lambda command,record:dict(record,turn=2) if command['op']=='observe' else record
        with patch.object(file_client,'publish_command',side_effect=self.publish):
            client.connect()
            with self.assertRaisesRegex(ValueError,'player/turn'):client.observe()
            with self.assertRaises(FileTransportError):client.observe()
            with self.assertRaises(FileTransportError):client.connect()
            client.close()
        self.assertTrue(client._failed)
        self.assertEqual([c['op'] for c in self.commands],['hello','observe','close'])
        self.assertFalse(self.inbox.with_suffix('.lua.lock').exists())


if __name__ == '__main__':unittest.main()
