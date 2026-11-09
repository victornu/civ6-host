"""Empty-map ownership fixtures; native ABI/effects need a separate live run."""
import ctypes as C
from pathlib import Path
import struct
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from civ6_host.runtime.configuration_profiles import XP2_CORE_SHA256
from civ6_host.runtime.native.native_player_operation_request import request_player_operation, _METHODS
from civ6_host.runtime.xp1_research_profile import player_operation_abi
from civ6_host.runtime.xp2_policy_controls_source import UNLOCK_POLICIES


class PolicyUnlockEmptyMapTests(unittest.TestCase):
    def invoke(self, *, allowed=1, submit=True, allow_empty=True, operation=UNLOCK_POLICIES):
        base, context = 0x25000000000, 0x12345000
        abi = player_operation_abi(XP2_CORE_SHA256, _METHODS)
        memory = {context: struct.pack('<Q', base+abi.outer)}
        for table, offset, target in abi.slots:
            memory[base+table+offset] = struct.pack('<Q', base+target)
        calls = []

        def ctor(pointer, table, name):
            calls.append(name)
            C.memmove(pointer, struct.pack('<Q', base+table), 8)
            return pointer

        def can_start(owner, player, op, params, visible, reasons):
            self.assertEqual((owner, player, op, visible), (context, 0, UNLOCK_POLICIES, False))
            self.assertEqual(C.string_at(params+8, 24), bytes(24))
            calls.append('can_start')
            return allowed

        def unexpected(*args):
            raise AssertionError('Empty parameters must neither look up nor insert a key')

        api = dict(parameter_ctor=lambda p: ctor(p, abi.parameters, 'parameters'),
            reason_ctor=lambda p: ctor(p, abi.reasons, 'reasons'),
            parameter_dtor=lambda p: calls.append('destroy_parameters'),
            reason_dtor=lambda p: calls.append('destroy_reasons'),
            lookup=unexpected, set_u32=unexpected, can_start=can_start,
            request=lambda *args: calls.append('request'))

        def read(address, size):
            return memory[address][:size] if address in memory else C.string_at(address, size)

        # Replace live code reads only; the selected pointer layout, calls,
        # storage guards and ownership are the real helper implementation.
        with patch('civ6_host.runtime.xp1_research_profile.verify_live'):
            result = request_player_operation(SimpleNamespace(_handle=base), context, 0,
                operation, {}, read=read, native_api=api, core_sha256=XP2_CORE_SHA256,
                submit=submit, allow_empty=allow_empty)
        return result, calls

    def test_empty_map_is_owned_checked_submitted_and_destroyed(self):
        result, calls = self.invoke()
        self.assertEqual(calls, ['parameters', 'reasons', 'can_start', 'request',
                                 'destroy_reasons', 'destroy_parameters'])
        self.assertEqual(result['parameter_count'], 0)
        self.assertTrue(result['request_invoked'])
        self.assertFalse(result['gameplay_outcome_verified'])

    def test_native_refusal_and_query_never_submit(self):
        for options in ({'allowed': 0}, {'submit': False}):
            result, calls = self.invoke(**options)
            self.assertFalse(result['request_invoked'])
            self.assertNotIn('request', calls)
            self.assertEqual(calls[-2:], ['destroy_reasons', 'destroy_parameters'])

    def test_empty_map_requires_the_explicit_known_operation(self):
        with self.assertRaises(ValueError):
            self.invoke(allow_empty=False)
        with self.assertRaisesRegex(ValueError, 'Unqualified empty'):
            self.invoke(operation=1)
