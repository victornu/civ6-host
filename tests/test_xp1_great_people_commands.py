"""Offline coverage of the real saved owner and private XP1 action primitive."""

from copy import deepcopy
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import struct
import unittest
from unittest.mock import patch

from lupa.lua51 import LuaRuntime
from civ6_host.runtime.configuration_profiles import XP1_CORE_SHA256
from civ6_host.runtime.execution_images import _XP1_PROFILE
from test_xp1_great_people import Fixture as ReadFixture, _ENV

staged = Path(__file__).with_name('xp1_great_people_commands.py')
if staged.is_file():
    spec = spec_from_file_location('civ6_host.runtime.xp1_great_people_commands', staged)
    gp = module_from_spec(spec)
    spec.loader.exec_module(gp)
else:
    from civ6_host.runtime import xp1_great_people_commands as gp


_RECRUIT = dict(kind='recruit_great_person', individual_index=50, cost=40)
_GOLD = dict(kind='patronize_great_person', individual_index=117, cost=550, currency='YIELD_GOLD')
_FAITH = dict(kind='patronize_great_person', individual_index=117, cost=70, currency='YIELD_FAITH')
_LUA = br'''
rows[1].Claimant=nil
classes[1].UnitType='UNIT_GREAT_PROPHET'
classes[2].UnitType='UNIT_GREAT_SCIENTIST'
GameInfo.Units={
 UNIT_GREAT_PROPHET={UnitType='UNIT_GREAT_PROPHET',Index=13},
 UNIT_GREAT_SCIENTIST={UnitType='UNIT_GREAT_SCIENTIST',Index=17}}
great.GetPatronizeCost=function(_,pid,id,yield) assert(pid==0);return yield==2 and 550 or 70 end
points.IsNoPatronageWith=function()return false end
local PlayerOperations={RECRUIT_GREAT_PERSON=-387427142,PATRONIZE_GREAT_PERSON=-337724938,
 PARAM_GREAT_PERSON_INDIVIDUAL_TYPE=945800002,PARAM_YIELD_TYPE=730511874}
great.GetPastTimeline=function()return {}end
'''


def packet(action, *, pid=0, overrides=None):
    operation = {'recruit_great_person':0xe8e854ba, 'patronize_great_person':0xebdeb9f6}[action['kind']]
    entries = [(0x385fc342, action['individual_index'])]
    if 'currency' in action:
        entries.append((0x2b8aba02, {'YIELD_GOLD':2, 'YIELD_FAITH':5}[action['currency']]))
    if overrides is not None:
        entries = overrides
    return struct.pack('<6I', 0xc45de12f, pid, operation, 2, 0x80000001, len(entries)) + b''.join(
        struct.pack('<II10sI', key, 0x00020000, bytes(10), value) for key, value in entries)


class Fixture(ReadFixture):
    def __init__(self):
        super().__init__()
        self.granted = None
        self.requested = []
        self.observation = dict(player_id=0, turn=8, units=[], economy={'gold':730.75, 'faith':90.125})
        self.stack.enter_context(patch.object(gp, 'request_player_operation', side_effect=self.request))
        self.stack.enter_context(patch.object(gp, 'observe_player', side_effect=self.collect))

    def evaluate(self, child, code, name, **kw):
        if child is not self.token.ui_child or name not in (b'@xp1_public_great_people', b'@xp1_great_person_grant'):
            raise AssertionError('Unexpected owner, Lua context or source')
        self.evaluations.append(name)
        mutation = self.mutation
        if self.granted and name == b'@xp1_great_person_grant':
            individual, class_id = self.granted['individual_index'], self.class_id
            mutation += (f'\ngreat.GetPastTimeline=function() return {{{{Individual={individual},'
                         f'Class={class_id},Claimant=0,TurnGranted=8}}}} end\n'
                         f'great.CountPeopleReceivedByPlayer=function(_,id,pid) assert(id=={class_id} and pid==0);'
                         f'return {3 if class_id==5 else 1} end').encode('ascii')
        return LuaRuntime(encoding=None).execute(_ENV + _LUA + mutation + b'\n' + code)

    def request(self, core, context, pid, operation, parameters, **opts):
        self.requested.append((core, context, pid, operation, parameters, opts))
        if self.can_start:
            self.token.transport.pending.append(self.payload)
        return dict(can_start=self.can_start, request_invoked=self.can_start)

    def virtual(self, core, pointer, slot, rva, result, *args):
        if rva == self.token.transport.transport_abi.drain_rva:
            original = super().virtual(core, pointer, slot, rva, result, *args)

            def drain(ctx):
                original(ctx)
                self.granted = self.choice

            return drain
        return super().virtual(core, pointer, slot, rva, result, *args)

    @property
    def class_id(self):
        return 5 if self.choice['individual_index'] == 50 else 4

    def collect(self, runtime, child, player_id):
        self.assert_observer(runtime, child, player_id)
        out = deepcopy(self.observation)
        if self.granted:
            out['units'].append(dict(owner=0, id=17, type=17 if self.class_id == 5 else 13))
            if 'currency' in self.chosen:
                balance = {'YIELD_GOLD':'gold', 'YIELD_FAITH':'faith'}[self.chosen['currency']]
                out['economy'][balance] -= self.chosen['cost']
        return out

    def assert_observer(self, runtime, child, player_id):
        if (runtime, child, player_id) != (self.token.runtime, self.token.ui_child, 0):
            raise AssertionError('Foreign observation request')

    def start(self, choice):
        self.choice = self.chosen = choice
        self.payload = packet(choice)
        catalogue = gp.catalogue(self.saved, self.observation)
        self.set_active(True)
        return catalogue


class GreatPersonCommandsTest(unittest.TestCase):
    def fixture(self):
        fixture = Fixture()
        self.addCleanup(fixture.close)
        return fixture

    def test_known_base_archive_and_strict_xp1_shape(self):
        archive = bytes.fromhex('2fe15dc400000000ba54e8e802000000010000800100000042c35f38000002000000000000000000000075000000')
        evidence = gp.verify_archive(archive, 0, dict(_RECRUIT, individual_index=117))
        self.assertEqual(evidence['parameters'], {0x385fc342:117})
        for choice in (_RECRUIT, _GOLD, _FAITH):
            raw = packet(choice)
            self.assertEqual(gp.verify_archive(raw, 0, choice)['size_bytes'], len(raw))
            for wrong in (raw[:-1], raw+b'\0', packet(choice, pid=1),
                          raw[:12]+b'\0\0\0\0'+raw[16:], raw[:28]+bytes(4)+raw[32:]):
                with self.assertRaises(RuntimeError):
                    gp.verify_archive(wrong, 0, choice)
        for bad in (packet(_FAITH), packet(_GOLD, overrides=[(0x385fc342,117),(0x385fc342,117)])):
            with self.assertRaises(RuntimeError):
                gp.verify_archive(bad, 0, _GOLD)

    def test_full_saved_owner_explicit_recruit_and_both_patronage_currencies(self):
        self.assertEqual(len(gp.source_dependencies(_XP1_PROFILE)), 11)
        for action in (_RECRUIT, _GOLD, _FAITH):
            with self.subTest(action=action):
                fixture = self.fixture()
                frame = fixture.start(action)
                self.assertIn(action, gp.actions(frame))
                result = gp.apply(fixture.saved, action, fixture.observation)
                self.assertEqual(result['status'], 'completed')
                self.assertEqual(result['action'], action)
                self.assertEqual(result['effect']['unit_id'], 17)
                self.assertEqual(result['effect']['individual_index'], action['individual_index'])
                if action['kind'] == gp.PATRONIZE:
                    self.assertEqual(result['effect']['amount_paid'], action['cost'])
                args, = fixture.requested
                self.assertIs(args[0], fixture.backend.core)
                self.assertEqual(args[1:3], (fixture.backend.context, 0))
                self.assertEqual(args[-1]['core_sha256'], XP1_CORE_SHA256)
                self.assertEqual(fixture.token.publication_count, 1)
                self.assertFalse(fixture.token.transport.pending)
                self.assertFalse(fixture.deferred.pending)

    def test_refused_stale_and_wrong_archive_never_deliver(self):
        f = self.fixture()
        f.start(_GOLD)
        f.can_start = False
        result = gp.apply(f.saved, _GOLD, f.observation)
        self.assertEqual(result['status'], 'refused')
        self.assertEqual(result['refusal_code'], 'native_great_person_can_start_false')
        self.assertEqual(result['observation'], f.observation)
        self.assertEqual(f.token.publication_count, 0)
        f.requested.clear()
        with self.assertRaisesRegex(RuntimeError, 'stale or unavailable'):
            gp.apply(f.saved, dict(_GOLD, cost=549), f.observation)
        self.assertFalse(f.requested)
        f.can_start = True
        f.payload = packet(_FAITH)
        with self.assertRaisesRegex(RuntimeError, 'parameters differ'):
            gp.apply(f.saved, _GOLD, f.observation)
        self.assertEqual(f.token.publication_count, 0)
        self.assertIsNone(f.granted)
        f.token.transport.pending.clear()

    def test_live_source_and_committed_grant_fail_closed(self):
        f = self.fixture()
        f.start(_GOLD)
        prev = f.backend.runtime.read
        target = f.backend.core._handle + gp.verify_source()['core_bodies'][0]['rva']
        with patch.object(f.backend.runtime, 'read', side_effect=lambda a,n: bytes(n) if a==target else prev(a,n)):
            with self.assertRaisesRegex(ValueError, 'command body differs'):
                gp.apply(f.saved, _GOLD, f.observation)
        self.assertFalse(f.requested)
        f.chosen = dict(_GOLD, cost=549)
        with self.assertRaisesRegex(RuntimeError, 'debit differs'):
            gp.apply(f.saved, _GOLD, f.observation)

    def test_action_syntax_no_hash_or_class_override(self):
        for bad in (dict(_RECRUIT, individual_index=True), dict(_GOLD, currency='gold'),
                    dict(_RECRUIT, individual=50), dict(_RECRUIT, hash=1234),
                    dict(_RECRUIT, kind='activate_great_person'), dict(_FAITH, cost=-1)):
            with self.assertRaises(ValueError):
                gp.validate_action(bad)


if __name__ == '__main__':
    unittest.main()
