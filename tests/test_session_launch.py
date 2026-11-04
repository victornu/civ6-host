"""Bounded launch integration without starting a native process."""
import ast
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import time
import unittest
from unittest.mock import patch

from civ6_host.runtime import session_launch as target
from civ6_host.runtime import xp1_session_inputs as inputs


class LaunchTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.events = []
        self.response = dict(episode_id='00000000-0000-4000-8000-000000000001',
            game_generation='native-00000000-0000-4000-8000-000000000001',
            outcome=dict(terminated=False))
        self.child = SimpleNamespace(stdout=object(), stderr=object(), stdin=object())
        self.owner = SimpleNamespace(run=Path(self.tmp.name), stdout_limit_bytes=64*1024*1024,
            nonce='1'*32, reset_timings_seconds={},
            win=SimpleNamespace(job=self.job), _read_stream=lambda *a:None,
            _watch=lambda:None, _send=lambda data:self.events.append(('send',data)),
            _receive=lambda:self.response,
            protocol_class=lambda identity,nonce,round_limit:SimpleNamespace(identity=identity),
            response_validator=self.validate,
            _accepted_response=lambda response:self.events.append(('accept',response)),
            _fail=lambda *args:self.events.append(('fail',args)),
            _finish=lambda:self.events.append(('finish',)))
        self.addCleanup(lambda: getattr(self.owner,'command_log',None) and self.owner.command_log.close())

    def job(self,child,limit):
        self.assertIs(child,self.child)
        self.events.append(('job',limit))
        return object()

    def validate(self,response,protocol,operation):
        self.assertEqual(operation,'reset')
        self.assertEqual(protocol.initial_turn,17)
        self.events.append(('validate',))

    def run_launch(self, *, spawn_error=None):
        thread = SimpleNamespace(start=lambda:None)
        with patch.object(target.subprocess,'Popen',side_effect=spawn_error,return_value=self.child) as popen, \
             patch.object(target.threading,'Thread',return_value=thread):
            result = target.launch(self.owner,Path('host.exe'),Path('worker.py'),
                dict(rounds=8,initial_turn=17),{},object(),time.perf_counter())
        return result,popen.call_args

    def test_job_is_assigned_before_handshake_and_reply_validation(self):
        result,args=self.run_launch()
        self.assertEqual([row[0] for row in self.events],['job','send','validate','accept'])
        self.assertEqual(self.events[0][1],512*1024*1024)
        self.assertEqual(self.events[1][1],b'go\n')
        self.assertTrue(args.kwargs['creationflags'] & target.subprocess.CREATE_NO_WINDOW)
        self.assertEqual(len(self.owner.threads),3)
        self.assertIsNot(result,self.response)
        result['outcome']['terminated']=True
        self.assertFalse(self.owner.last['outcome']['terminated'])

    def test_spawn_failure_uses_existing_failure_and_reaper(self):
        with self.assertRaisesRegex(OSError,'spawn failure'):
            self.run_launch(spawn_error=OSError('spawn failure'))
        self.assertEqual([row[0] for row in self.events],['fail','finish'])

    def test_invalid_initial_reply_uses_existing_failure_and_reaper(self):
        def reject(*args):raise ValueError('wrong initial reply')
        self.owner.response_validator=reject
        with self.assertRaisesRegex(ValueError,'wrong initial reply'):self.run_launch()
        self.assertEqual([row[0] for row in self.events],['job','send','fail','finish'])

    def test_explicit_protocol_profile_selected_before_shared_validation(self):
        def initial(identity, closure):
            self.events.append(('profile', closure['rounds']))
            return SimpleNamespace(identity=identity, core_sha256='xp1')
        self.owner._initial_protocol = initial
        self.run_launch()
        self.assertEqual([row[0] for row in self.events],
                         ['job', 'send', 'profile', 'validate', 'accept'])
        self.assertEqual(self.owner.protocol.core_sha256, 'xp1')


class InputsTests(unittest.TestCase):
    def test_fixture_json_is_write_once_and_hash_bound(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'fixture.json'
            receipt=inputs._write_once(path,{'value':1})
            self.assertEqual(json.loads(path.read_bytes()),{'value':1})
            self.assertEqual(receipt['sha256'],hashlib.sha256(path.read_bytes()).hexdigest())
            with self.assertRaises(FileExistsError):inputs._write_once(path,{'value':2})
            pins={};inputs.saved_load_pin(pins,path,receipt['sha256'])
            path.write_text('{"value":2}')
            with self.assertRaises(ValueError):inputs.saved_load_pin(pins,path)

    def test_incomplete_phase_dependencies_refused_before_reading_inputs(self):
        for flags in ((False,True,False,False,False),(True,False,True,True,False),
                      (True,True,True,False,True),(1,True,True,True,True)):
            with self.subTest(flags=flags),self.assertRaises(ValueError):
                inputs.prepare_sources(None,None,**dict(zip(('postload160','publish_cache',
                    'close_loaded','observe_player','unit_commands'),flags)))


if __name__=='__main__':unittest.main()
