"""Grouped transport-extension tests using explicit native-call fixtures."""
import ast
import ctypes as C
import hashlib
from pathlib import Path
import struct
import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch

from civ6_host.runtime import turn_requests as requests


class TurnRequestTests(unittest.TestCase):
    def setUp(self):
        self.events = []
        self.calls = []
        self.wrapper = b'offline ABI fixture, not game code'
        self.transport = SimpleNamespace(
            core=SimpleNamespace(_handle=0x10000000), context=0x20000000,
            pending=[], read=lambda address, size: self.wrapper,
            emit=lambda stage, **fields: self.events.append((stage, fields)))
        self.effect = lambda: self.transport.pending.append(
            struct.pack('<II', 0xE8A26B84, 1))
        native = ModuleType('civ6_host.runtime.native.native_host')
        native.virtual = self.virtual
        self.addCleanup(patch.stopall)
        patch.dict(sys.modules, {native.__name__: native}).start()
        patch.object(requests, '_WRAPPER_SHA256',
                     hashlib.sha256(self.wrapper).hexdigest()).start()

    def virtual(self, core, context, slot, rva, result, *arguments):
        self.assertEqual((core, context), (self.transport.core, self.transport.context))
        self.assertEqual((slot, rva, result, arguments),
                         (0x200, 0x42E570, None, (C.c_uint32, C.c_int32)))
        def call(*args):
            self.assertEqual(args, (self.transport.context, 0xBDAB643D, 1))
            self.calls.append(args)
            self.effect()
        return call

    def test_generated_transport_method_preserves_queue_and_only_reports_emission(self):
        source = Path(__file__).resolve().parents[1] / 'src/civ6_host/runtime/native/native_action_transport.py'
        cls = next(n for n in ast.parse(source.read_text()).body
                   if isinstance(n, ast.ClassDef) and n.name == 'NativeActionTransport')
        method = next(n for n in cls.body if isinstance(n, ast.FunctionDef)
                      and n.name == 'request_unready_turn')
        namespace = {}
        exec(compile(ast.Module(body=[method], type_ignores=[]), str(source), 'exec'), namespace)
        self.transport.pending = [b'previous command']
        value = namespace['request_unready_turn'](self.transport, 1)
        self.assertEqual(value['status'], 'queued')
        self.assertEqual(value['archive_hex'], struct.pack('<II', 0xE8A26B84, 1).hex())
        self.assertEqual(self.transport.pending[0], b'previous command')
        self.assertEqual(len(self.transport.pending), 2)
        self.assertEqual(len(self.calls), 1)
        self.assertFalse(value['action_applied'])
        self.assertFalse(value['native_outcome_verified'])

    def test_no_emission_is_not_reported_as_applied_or_retried(self):
        self.effect = lambda: None
        value = requests.request_unready_turn(self.transport, 1)
        self.assertEqual(value['status'], 'not_queued')
        self.assertFalse(value['queued'])
        self.assertFalse(value['action_applied'])
        self.assertNotIn('rejection_reason', value)
        self.assertEqual(self.transport.pending, [])
        self.assertEqual(len(self.calls), 1)

    def test_unexpected_archives_are_not_discarded_or_accepted(self):
        for archives in ([struct.pack('<III', 0xE8A26B84, 1, 0)],
                         [struct.pack('<II', 0xE8A26B84, 0)],
                         [struct.pack('<II', 0xE8A26B84, 1)] * 2):
            with self.subTest(archives=archives):
                self.transport.pending = []
                self.events.clear()
                self.effect = lambda: self.transport.pending.extend(archives)
                with self.assertRaisesRegex(RuntimeError, 'unexpected native archive'):
                    requests.request_unready_turn(self.transport, 1)
                self.assertEqual(self.transport.pending, archives)
                self.assertEqual(len(self.events), 1)

    def test_prefix_mutation_or_native_exception_cannot_produce_a_receipt(self):
        self.transport.pending = [b'old']
        self.effect = lambda: self.transport.pending.__setitem__(0, b'new')
        with self.assertRaisesRegex(RuntimeError, 'earlier pending command'):
            requests.request_unready_turn(self.transport, 1)
        self.assertEqual(len(self.events), 1)
        def fail():
            raise RuntimeError('uncertain native call')
        self.events.clear()
        self.effect = fail
        with self.assertRaisesRegex(RuntimeError, 'uncertain native call'):
            requests.request_unready_turn(self.transport, 1)
        self.assertEqual(len(self.events), 1)

    def test_invalid_abi_roster_and_full_queue_fail_before_native_execution(self):
        self.transport.read = lambda address, size: b'changed wrapper'
        with self.assertRaisesRegex(RuntimeError, 'pinned Core'):
            requests.request_unready_turn(self.transport, 1)
        self.transport.read = lambda address, size: self.wrapper
        for player, roster in ((True, (0, 1)), (3, (0, 1)), (1, (0, 1, 4))):
            with self.subTest(player=player, roster=roster):
                with self.assertRaises(ValueError):
                    requests.request_unready_turn(self.transport, player, player_ids=roster)
        self.transport.pending = [b'pending'] * 64
        with self.assertRaisesRegex(RuntimeError, 'bounded pending'):
            requests.request_unready_turn(self.transport, 1)
        self.assertEqual(self.calls, [])
        self.assertEqual(self.events, [])


if __name__ == '__main__':
    unittest.main()
