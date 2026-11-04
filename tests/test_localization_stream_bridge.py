"""Retained Lua bridge + actual Python transport; native callback is a fixture."""
import copy
import ast
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import types
import unittest
from zipfile import ZipFile
from unittest.mock import patch

from civ6_host.runtime.paths import resource_root
from civ6_host.runtime import localization_stream_bridge as stream
from civ6_host.runtime import database_bulk_capture as bulk
from civ6_host.runtime.native import native_localization_query as provider
from civ6_host.runtime.native.file_client import FileClient,FileTransportError,FileTimeout,_lua
from civ6_host.runtime.native.log_frames import LogFrameCollector
import test_database_bulk_capture as bulk_fixtures

HOST=Path(__file__).resolve().parents[1];LAB=resource_root()


def retained_lua_fixture():
    path=LAB/'tests/test_lua_file_transport.py';source=path.read_text(encoding='utf8')
    source=source.replace('from civ6rl.log_frames','from civ6_host.runtime.native.log_frames')
    source=source.replace('from civ6rl.protocol','from civ6_host.runtime.native.protocol')
    module=types.ModuleType('retained_transport_fixture');module.__file__=str(path)
    exec(compile(source,str(path),'exec'),module.__dict__)
    return module


class StreamBridgeTests(unittest.TestCase):
    def setUp(self):
        self.data=bulk_fixtures.BulkCaptureTests();self.data.setUp();self.addCleanup(self.data.doCleanups)
        self.path=self.data.root/'000000.rows.bin';self.nonce='c'*32;self.provider_nonce='d'*32
        core=dict(connection='localization',operation='rows',expected_player_id=0,expected_turn=12,
            table_name='Words',offset=0,limit=2,after_rowid='start')
        col=self.data.producer.metadata({**core,'operation':'columns'},timeout=1)['diagnostics']['database_capture']
        self.packet=bulk._row_request(core,col,self.data.process,self.data.identity,self.nonce,self.path.name)
        self.build_path=LAB/'work/official-capture/localization-stream/build03/build.json'
        self.build=provider.verify_build(self.build_path)
        self.registration=dict(status='registered_at_menu',nonce=self.provider_nonce,process=self.data.process,
            build=dict(path=str(self.build_path)),helper_module=self.build['dll'])
        event,command=provider.registration_command(self.build,self.data.process,self.provider_nonce)
        self.registration['event']=event
        fixture=retained_lua_fixture();self.host=fixture.LuaFileTransportTests('runTest')
        candidate=HOST/'work/localization-stream-bridge/staged01/Civ6RLFileTransport.lua'
        original=Path.read_text
        def staged(path,*args,**kwargs):
            return original(candidate,*args,**kwargs) if path==LAB/'mod/UI/Civ6RLFileTransport.lua' else original(path,*args,**kwargs)
        with patch.object(Path,'read_text',staged):self.host.start()
        lua=self.host.lua;g=lua.globals();self.native_calls=0
        lua.execute('''
          UI.IsGameCoreBusy=function() return State.busy end
          Locale={Lookup=function()return 'ui lookup' end}
          RootEnvironment=setmetatable({Locale={Lookup=function()return 'root lookup' end}}, {__index=_G})
          function RunRoot(source)local f=assert(loadstring(source));setfenv(f,RootEnvironment);return f() end
          function RunUI(source)local f=assert(loadstring(source));return f() end
        ''')
        g.EventName=event
        lua.execute('''LuaEvents[EventName]={Add=function(fn)FixtureListener=fn end,Call=function(box)return FixtureListener(box) end}''')
        prep=json.dumps(dict(schema='civ6rl.localization_query_preparation.v1',status='ok',nonce=self.provider_nonce,
            database_function_called=False,module_file_pins_retained=True))
        g.PreparationReceipt=prep;g.NativeFixture=self.native
        lua.execute('''
          package.loadlib=function(path,symbol)
            if symbol=='civ6rl_localization_query_prepare' then return function()return PreparationReceipt end end
            if symbol=='civ6rl_localization_query' then return function()return {{version='fixture'}} end end
            if symbol=='civ6rl_localization_row_stream' then return function(...)return NativeFixture(...) end end
            error('unexpected native symbol')
          end
        ''')
        g.RunRoot(command)
        g.RunUI(provider.install_command(self.registration,player_id=0,turn=12))
        self.host.hello();self.message_cursor=len(self.host.state.messages)
        inbox=self.data.root/'Civ6RLInbox.lua';inbox.write_text('Civ6RL_Inbox={op="idle"}')
        self.client=FileClient(inbox,self.data.root/'Lua.log',timeout=.2)
        self.client.session='test-session';self.client._connected=True
        self.client._collector=LogFrameCollector('test-session')
        outer=self
        class Tail:
            def read_lines(self):
                outer.host.lua.globals().InboxScript=inbox.read_text()
                outer.host.transport.Tick()
                end=len(outer.host.state.messages)
                lines=[outer.host.state.messages[i] for i in range(outer.message_cursor+1,end+1)]
                outer.message_cursor=end;return lines
        self.client._tail=Tail()
    def native(self,sql,path,nonce,pid,created,lookup):
        self.native_calls+=1
        self.assertEqual(sql,self.packet['query']);self.assertEqual(nonce,self.nonce)
        self.assertEqual((pid,created),(str(self.data.process['pid']),str(self.data.process['creation_filetime'])))
        self.assertEqual(lookup(),'ui lookup')
        receipt=self.data.producer.rows(self.packet,Path(path),timeout=1)
        if getattr(self,'bad_query',False):receipt['query_sha256']='0'*64
        if getattr(self,'drift',False):self.host.state.turn=13
        return json.dumps(receipt)
    def read(self):
        return self.client.read_database_rows(self.packet,self.path,provider_nonce=self.provider_nonce,timeout=.2)
    def test_python_to_real_lua_bridge_frames_and_native_receipt_file(self):
        receipt=self.read();self.assertEqual(receipt['rows'],2);self.assertEqual(self.native_calls,1)
        text=self.client.inbox.read_text();self.assertIn('sql_hex=',text);self.assertNotIn('SELECT ',text)
        self.assertIsNone(self.host.lua.eval('rawget(RootEnvironment,"Civ6RL_LocalizationRowStream")'))
        other=self.data.root/'other';other.mkdir()
        with self.assertRaisesRegex(FileTransportError,'already submitted'):
            self.client.read_database_rows(self.packet,other/self.path.name,provider_nonce=self.provider_nonce)
        self.assertEqual(self.native_calls,1)
    def test_idle_and_exact_provider_are_required_before_callback(self):
        self.host.state.busy=True
        self.host.lua.execute('UI.IsProcessingMessages=function()return false end')
        with self.assertRaisesRegex(FileTransportError,'not_idle'):self.read()
        self.assertEqual(self.native_calls,0);self.assertTrue(self.client._failed)
    def test_missing_provider_never_falls_back_to_query(self):
        self.host.lua.globals().Civ6RL_LocalizationRowStream=None
        with self.assertRaisesRegex(FileTransportError,'provider_unavailable'):self.read()
        self.assertEqual(self.native_calls,0)
    def test_boundary_drift_and_native_receipt_mismatch_fail_client(self):
        self.drift=True
        with self.assertRaisesRegex(FileTransportError,'boundary_changed'):self.read()
        self.assertEqual(self.native_calls,1);self.assertTrue(self.client._failed)
    def test_native_query_mismatch_is_not_admitted(self):
        self.bad_query=True
        with self.assertRaisesRegex(ValueError,'query hash'):self.read()
        self.assertTrue(self.client._failed)
    def test_uncertain_wait_refuses_replay(self):
        self.host.lua.globals().Civ6RL_LocalizationRowStream=lambda *args:None
        # No observation or command re-submission: a lost reply is uncertain.
        self.client._tail=types.SimpleNamespace(read_lines=lambda:[])
        with self.assertRaises(FileTimeout):self.read()
        self.assertTrue(self.client._failed);self.assertEqual(self.native_calls,0)
        with self.assertRaises(FileTransportError):self.read()
    def test_raw_sql_and_bad_serialization_are_refused_before_publish(self):
        packet=copy.deepcopy(self.packet);packet['query']='DELETE FROM Words'
        before=self.client.inbox.read_bytes()
        with self.assertRaisesRegex(ValueError,'Noncanonical'):
            self.client.read_database_rows(packet,self.path,provider_nonce=self.provider_nonce)
        self.assertEqual(before,self.client.inbox.read_bytes());self.assertEqual(self.native_calls,0)
    def test_row_stream_composes_with_continued_publication_nonce_guard(self):
        from civ6_host.runtime.capture_response_continuation import ContinuedResponseFileClient

        continued=ContinuedResponseFileClient.__new__(ContinuedResponseFileClient)
        continued.__dict__.update(self.client.__dict__)
        continued._hello_published=True

        receipt=stream.read_rows(continued,self.packet,self.path,
            provider_nonce=self.provider_nonce,timeout=.2)
        self.assertEqual(receipt['rows'],2)
        self.assertEqual(self.native_calls,1)
        self.assertIn(self.nonce,continued._used)
        self.assertIn(self.nonce,continued._row_stream_used)
        command=self.client.inbox.read_text()
        self.assertIn('op="database_row_stream"',command)
        self.assertIn(f'command_id="{self.nonce}"',command)

        replay=copy.deepcopy(self.packet)
        replay['output']='000001.rows.bin'
        replay_path=self.data.root/replay['output']
        continued._row_stream_used.remove(self.nonce)
        before=self.client.inbox.read_bytes()
        with self.assertRaisesRegex(FileTransportError,'already submitted'):
            stream.read_rows(continued,replay,replay_path,
                provider_nonce=self.provider_nonce,timeout=.2)
        self.assertEqual(before,self.client.inbox.read_bytes())
        self.assertEqual(self.native_calls,1)
    def test_legacy_command_generation_and_direct_transport_admission(self):
        original='unchanged legacy command'
        self.assertEqual(stream.registration_command(original,dict(dll=dict(sha256='a'*64)),{},'b'*32),original)
        self.assertEqual(stream.install_command(original,dict(status='registered_at_menu'),0,12),original)
        from civ6_host.runtime.native.response_file_client import ALLOWED_OPERATIONS
        self.assertIn('database_row_stream',ALLOWED_OPERATIONS);self.assertNotIn('action',ALLOWED_OPERATIONS)
    def test_actual_legacy_commands_match_retained_source_bytes(self):
        with ZipFile(HOST/'work/localization-stream-bridge/before.zip') as z:
            source=z.read('src/civ6_host/runtime/native/native_localization_query.py').decode()
        tree=ast.parse(source);functions=[n for n in tree.body if isinstance(n,ast.FunctionDef)
            and n.name in ('registration_command','install_command')]
        namespace=dict(provider.__dict__)
        exec(compile(ast.Module(body=functions,type_ignores=[]),'retained query command functions','exec'),namespace)
        old_build=copy.deepcopy(self.build);old_build['dll']['sha256']='a'*64
        old_reg=dict(status='registered_at_menu',process=self.data.process,nonce='b'*32,event='test_event')
        self.assertEqual(provider.registration_command(old_build,self.data.process,'b'*32),
            namespace['registration_command'](old_build,self.data.process,'b'*32))
        self.assertEqual(provider.install_command(old_reg,player_id=0,turn=12),
            namespace['install_command'](old_reg,player_id=0,turn=12))


if __name__=='__main__':unittest.main()
