"""Gathering Storm military levy source and transport guard tests."""

import ctypes as C
from copy import deepcopy
from pathlib import Path
import struct
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from civ6_host.contracts import city_state_levies as contract
from civ6_host.runtime import execution_images, xp1_city_state_levies as shared
from civ6_host.runtime import xp2_city_state_levies as xp2
from civ6_host.runtime.configuration_profiles import XP1_CORE_SHA256, XP2_CORE_SHA256
from civ6_host.runtime.native import native_player_operation_request as transport
from civ6_host.runtime.xp1_research_profile import player_operation_abi


class LevyRequestTests(unittest.TestCase):
    def setUp(self):
        self.image = execution_images.select_pair(xp2.INSTALLED_CORE_SHA256, XP2_CORE_SHA256)
        self.core = SimpleNamespace(_handle=0x25000000000, _civ6_host_execution_image=self.image)
        self.context = 0x12345000
        self.observation = dict(player_id=0, turn=52)
        self.offer = shared.parse(b'0:52:1|2:1:85:30:0', 0, 52)
        self.action = dict(kind=contract.ACTION, target_player_id=2)
        self.saved = SimpleNamespace(
            backend=SimpleNamespace(core=self.core, context=self.context),
            continuation=SimpleNamespace(observation=self.observation,
                                         explicit_city_state_levies=self.offer),
        )
        with patch.object(xp2, 'bind_owner'):
            self.permit = xp2.request_permit(self.saved, self.observation, self.action, self.offer)

    def invoke(self, operation, target, **kwargs):
        abi = player_operation_abi(XP2_CORE_SHA256, transport._METHODS)
        base = self.core._handle
        pointers = {self.context: struct.pack('<Q', base + abi.outer)}
        for table, slot, target_rva in abi.slots:
            pointers[base + table + slot] = struct.pack('<Q', base + target_rva)
        calls = []
        values = {}

        def ctor(pointer, table):
            C.memmove(pointer, struct.pack('<Q', base + table), 8)
            return pointer

        def set_u32(_pointer, key, value):
            values[key] = C.create_string_buffer(struct.pack('<H6xI12x', 2, value))
            return C.addressof(values[key])

        def can_start(*_):
            calls.append('can_start')
            return 1

        def request(context, player, opcode, _):
            self.assertEqual((context, player, opcode), (self.context, 0, operation))
            calls.append('request')

        def read(pointer, size):
            return pointers[pointer][:size] if pointer in pointers else C.string_at(pointer, size)

        api = dict(parameter_ctor=lambda p: ctor(p, abi.parameters), parameter_dtor=lambda _: None,
                   reason_ctor=lambda p: ctor(p, abi.reasons), reason_dtor=lambda _: None,
                   lookup=lambda _, key: C.addressof(values[key]) if key in values else 0,
                   set_u32=set_u32, can_start=can_start, request=request)
        with patch('civ6_host.runtime.xp1_research_profile.verify_live'):
            result = transport.request_player_operation(
                self.core, self.context, 0, operation, {xp2.TARGET_PARAMETER: target},
                read=read, native_api=api, core_sha256=XP2_CORE_SHA256, **kwargs)
        return result, calls

    def test_only_exact_levy_permit_uses_direct_request(self):
        ordinary, calls = self.invoke(2582383566, 2)
        self.assertTrue(ordinary['can_start'])
        self.assertEqual(calls, ['can_start', 'request'])
        levy, calls = self.invoke(xp2.OPERATION, 2, levy_permit=self.permit)
        self.assertIsNone(levy['can_start'])
        self.assertIs(levy['native_can_start_called'], False)
        self.assertEqual(levy['source_qualified_request_only'], 'LEVY_MILITARY')
        self.assertEqual(calls, ['request'])
        self.assertFalse(levy['gameplay_outcome_verified'])
        with self.assertRaisesRegex(ValueError, 'exact Gathering Storm'):
            self.invoke(xp2.OPERATION, 3, levy_permit=self.permit)
        with self.assertRaisesRegex(ValueError, 'exact Gathering Storm'):
            self.invoke(2582383566, 2, levy_permit=self.permit)

    def test_foreign_core_or_stale_offer_cannot_use_direct_request(self):
        for core, digest in ((object(), XP2_CORE_SHA256), (self.core, XP1_CORE_SHA256)):
            with self.assertRaisesRegex(ValueError, 'exact Gathering Storm'):
                xp2.authorize_request(
                    self.permit, core, self.context, 0, xp2.OPERATION, {xp2.TARGET_PARAMETER: 2},
                    core_sha256=digest, submit=True, allow_empty=False)
        with patch.object(xp2, 'bind_owner'):
            with self.assertRaisesRegex(ValueError, 'exact live offer'):
                xp2.request_permit(self.saved, self.observation, self.action, deepcopy(self.offer))
            with self.assertRaisesRegex(ValueError, 'exact live offer'):
                xp2.request_permit(self.saved, dict(self.observation, turn=53), self.action, self.offer)

    def test_levy_query_can_omit_the_unrelated_strategic_predicate(self):
        default = shared.query_source(0, 52)
        xp2_query = shared.query_source(0, 52, require_strategic=False)
        guard = b" assert(Game.IsAllowStrategicCommands(pid)==true,'influence commands unavailable')\n"
        self.assertEqual(default.count(guard), 1)
        self.assertEqual(xp2_query, default.replace(guard, b''))
        self.assertIn(b'influence:CanLevyMilitary(target)', xp2_query)
        self.assertIn(b'Game.GetLocalObserver()==pid', xp2_query)

    def test_worker_revalidates_quote_and_requires_delivered_effect(self):
        from civ6_host.runtime.workers.network_worker import _execute_xp1

        self.saved.backend.load_abi = SimpleNamespace(core_sha256=XP2_CORE_SHA256)
        self.saved.emit = Mock()
        self.saved.execute = Mock()
        decisions = dict(candidates=[dict(action=self.action)])

        def reread(offer):
            self.saved.continuation.explicit_city_state_levies = offer
            return {}, self.observation, decisions

        with (patch('civ6_host.runtime.xp1_session_view.read',
                    side_effect=lambda *_: reread(shared.parse(b'0:52:1|2:1:86:30:0', 0, 52))),
              patch('civ6_host.runtime.xp1_session_inputs._write_once', return_value={}),
              patch('civ6_host.runtime.workers.network_worker._retain_xp2_diplomacy_if_ready')):
            refused = _execute_xp1(self.saved, self.action, 0, 0, Path('closure.json'))
            self.assertEqual(refused['reason'], 'native_city_state_levy_offer_changed')
            self.saved.execute.assert_not_called()
        self.saved.continuation.explicit_city_state_levies = self.offer
        effect = dict(target_player_id=2, gold_spent=85, controlled_unit_ids=[10],
                      native_archive_sha256='d' * 64, native_effect_readback=False)
        self.saved.execute.return_value = dict(action=self.action, effect=dict(effect=effect))
        with (patch('civ6_host.runtime.xp1_session_view.read',
                    side_effect=lambda *_: reread(self.offer)),
              patch('civ6_host.runtime.xp1_session_inputs._write_once', return_value={}),
              patch('civ6_host.runtime.workers.network_worker._retain_xp2_diplomacy_if_ready')):
            with self.assertRaisesRegex(RuntimeError, 'no matching native archive and effect'):
                _execute_xp1(self.saved, self.action, 0, 0, Path('closure.json'))
            effect['native_effect_readback'] = True
            effect['gold_spent'] = 86
            with self.assertRaisesRegex(RuntimeError, 'no matching native archive and effect'):
                _execute_xp1(self.saved, self.action, 0, 0, Path('closure.json'))
            effect['gold_spent'] = 85
            reply = _execute_xp1(self.saved, self.action, 0, 0, Path('closure.json'))
            self.assertEqual(reply, dict(status='completed', reason=None, requested_action=self.action))
