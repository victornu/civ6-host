"""Great People native readback contract with the composed saved owner and Lua fixtures."""

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

from lupa.lua51 import LuaRuntime
from civ6_host.runtime.execution_images import _XP1_PROFILE
from civ6_host.runtime.saved_load_services import SavedLoadServices
from civ6_host.runtime.native.native_script_runtime import NativeScriptRuntime
from test_xp1_pantheon import Fixture as ExistingFixture


staged = Path(__file__).with_name('xp1_great_people.py')
if staged.is_file():
    spec = spec_from_file_location('civ6_host.runtime.xp1_great_people', staged)
    adapter = module_from_spec(spec)
    sys.modules[spec.name] = adapter
    spec.loader.exec_module(adapter)
else:
    from civ6_host.runtime import xp1_great_people as adapter


_ENV = br'''
local function nope() error('readback attempted to submit a game action') end
local cfg={pid=0, turn=8, observer=0, strategic=true, active=true}
local caps={CAPABILITY_GREAT_PEOPLE_CAN_RECRUIT={},
 CAPABILITY_GREAT_PEOPLE_CAN_REJECT={}, CAPABILITY_GREAT_PEOPLE_RECRUIT_WITH_GOLD={},
 CAPABILITY_GREAT_PEOPLE_RECRUIT_WITH_FAITH={}}
local classes={
 {Index=4,GreatPersonClassType='GREAT_PERSON_CLASS_PROPHET',MaxPlayerInstances=1},
 {Index=5,GreatPersonClassType='GREAT_PERSON_CLASS_SCIENTIST'}}
local rows={
 {Individual=117,Class=4,Era=1,Cost=60,Claimant=52},
 {Individual=50,Class=5,Era=1,Cost=40,Claimant=0},
 {Individual=51,Class=5,Era=1,Cost=40,Claimant=21},
 {Class=5,Era=2,Cost=60}}
local function list(data)
 local byID={}
 for _,r in ipairs(data) do byID[r.Index]=r end
 return setmetatable(byID,{__call=function()
  local n=0;return function() n=n+1;return data[n] end
 end})
end
local points={GetPointsTotal=function(_,id) return id==4 and 17.00390625 or 0 end,
 GetPointsPerTurn=function(_,id) return id==4 and 2 or 0 end,
 IsNoPatronageWith=function(_,id) assert(id==2 or id==5); return id==5 end}
local diplomacy={HasMet=function(_,id) assert(id==52 or id==21); return id==21 end}
local actor={IsAlive=function()return true end,IsTurnActive=function()return cfg.active end,
 IsTurnActiveComplete=function()return cfg.active end,GetGreatPeoplePoints=function() return points end,
 GetDiplomacy=function() return diplomacy end}
local foreign=setmetatable({},{__index=function()error('hidden foreign player was inspected')end})
local Players={[0]=actor,[52]=foreign,[21]=foreign}
local great={
 GetTimeline=function() return rows end,
 GetPastTimeline=function() error('past timeline requested by current view') end,
 CanRecruitPerson=function(_,pid,id) assert(pid==0);return id==50 end,
 CanRejectPerson=function(_,pid,id) assert(pid==0);return id==51 end,
 GetRejectCost=function(_,pid,id) assert(pid==0 and id==51);return 2 end,
 CanPatronizePerson=function(_,pid,id,yield) assert(pid==0 and (yield==2 or yield==5));return true end,
 GetPatronizeCost=function(_,pid,id,yield) assert(pid==0);return yield==2 and 550 or 1000000 end,
 CountPeopleReceivedByPlayer=function(_,id,pid) assert(pid==0);return id==5 and 2 or 0 end}
local Game={GetLocalPlayer=function()return cfg.pid end,GetLocalObserver=function()return cfg.observer end,
 GetCurrentGameTurn=function()return cfg.turn end,IsAllowStrategicCommands=function()return cfg.strategic end,
 GetGreatPeople=function()return great end}
local GameInfo={GameCapabilities=caps,GreatPersonClasses=list(classes),GreatPersonIndividuals={
 [117]={Index=117,GreatPersonIndividualType='GREAT_PERSON_INDIVIDUAL_ZOROASTER',
        GreatPersonClassType='GREAT_PERSON_CLASS_PROPHET'},
 [50]={Index=50,GreatPersonIndividualType='GREAT_PERSON_INDIVIDUAL_TEST_50',
       GreatPersonClassType='GREAT_PERSON_CLASS_SCIENTIST'},
 [51]={Index=51,GreatPersonIndividualType='GREAT_PERSON_INDIVIDUAL_TEST_51',
       GreatPersonClassType='GREAT_PERSON_CLASS_SCIENTIST'}},
 Yields={YIELD_GOLD={Index=2},YIELD_FAITH={Index=5}}}
local YieldTypes={GOLD=2,FAITH=5}
local UI={RequestPlayerOperation=nope}
local UnitManager={InitUnit=nope,RequestOperation=nope}
'''


class Fixture(ExistingFixture):
    def __init__(self):
        super().__init__()
        self.saved.xp1_great_people = True
        self.mutation = b''
        self.evaluations = []

    def evaluate(self, child, code, name, **kw):
        if child is not self.token.ui_child or name != b'@xp1_public_great_people':
            raise AssertionError('Unexpected owner, Lua context or source')
        self.evaluations.append(name)
        if kw != {'capacity': adapter._MAX_RESPONSE}:
            raise AssertionError('Wire bound changed')
        return LuaRuntime(encoding=None).execute(_ENV + self.mutation + b'\n' + code)


class GreatPeopleTests(unittest.TestCase):
    def fixture(self):
        fixture = Fixture()
        self.addCleanup(fixture.close)
        return fixture

    def test_pins_and_actual_owner_with_fractional_points_and_own_roster_only(self):
        proof = adapter.verify_source()
        self.assertEqual(len(proof['bindings']), 15)
        self.assertEqual(len(proof['core_bodies']), 31)
        self.assertEqual(len(adapter.source_dependencies(_XP1_PROFILE)), 10)
        fixture = self.fixture()
        self.assertIs(type(fixture.saved.prefix), SavedLoadServices)
        self.assertIs(type(fixture.saved.prefix.runtime), NativeScriptRuntime)
        value = adapter.read(fixture.saved, fixture.token.observation)
        self.assertEqual((value['player_id'], value['turn']), (0, 8))
        self.assertEqual(value['own_points'][0], dict(class_index=4, class_type='GREAT_PERSON_CLASS_PROPHET',
            max_instances=1, instances_earned=0, points_total=17.00390625, points_per_turn=2))
        prophet, recruited, rejected, placeholder = value['timeline']
        self.assertEqual(prophet['individual_index'], 117)
        self.assertTrue(prophet['claimed'])
        self.assertIsNone(prophet['claimant_player_id'])
        self.assertEqual(recruited['claimant_player_id'], 0)
        self.assertEqual(rejected['claimant_player_id'], 21)
        self.assertTrue(recruited['recruitment']['available'])
        self.assertTrue(rejected['rejection']['available'])
        self.assertEqual(placeholder['class_index'], 5)
        self.assertIsNone(placeholder['individual_index'])
        self.assertEqual(fixture.machine, [])
        self.assertEqual(fixture.saved.prefix.actions.pending, [])
        self.assertEqual(fixture.saved.prefix.deferred_events.pending, [])

    def test_separate_native_flags_and_visible_currency_quotes(self):
        fixture = self.fixture()
        value = adapter.read(fixture.saved, fixture.token.observation)
        prophet, recruited, rejected, _ = value['timeline']
        gold, faith = (prophet['patronage'][y] for y in ('YIELD_GOLD', 'YIELD_FAITH'))
        self.assertEqual(gold, dict(cost=550, native_can_patronize=True, visible=True,
                                   available=True, no_patronage=False))
        self.assertEqual(faith, dict(cost=1000000, native_can_patronize=True, visible=False,
                                    available=False, no_patronage=True))
        self.assertFalse(recruited['patronage']['YIELD_GOLD']['visible'])
        self.assertFalse(rejected['patronage']['YIELD_GOLD']['visible'])
        fixture.mutation = b'caps.CAPABILITY_GREAT_PEOPLE_RECRUIT_WITH_GOLD=nil'
        value = adapter.read(fixture.saved, fixture.token.observation)
        self.assertEqual(value['timeline'][0]['patronage']['YIELD_GOLD']['cost'], 550)
        self.assertFalse(value['timeline'][0]['patronage']['YIELD_GOLD']['visible'])

    def test_inactive_wrong_image_foreign_actor_or_pending_queues_refuse(self):
        fixture = self.fixture()
        fixture.saved.xp1_great_people = False
        with self.assertRaisesRegex(ValueError, 'exact Rise and Fall'):
            adapter.read(fixture.saved, fixture.token.observation)
        fixture.saved.xp1_great_people = True
        fixture.saved.prefix.actions.pending.append(b'pending')
        with self.assertRaisesRegex(RuntimeError, 'drained queues'):
            adapter.read(fixture.saved, fixture.token.observation)
        fixture.saved.prefix.actions.pending.clear()
        fixture.backend.core._civ6_host_execution_image = None
        with self.assertRaisesRegex(ValueError, 'exact Rise and Fall'):
            adapter.read(fixture.saved, fixture.token.observation)
        fixture.backend.core._civ6_host_execution_image = _XP1_PROFILE
        for pid in (True, -1, 64):
            with self.assertRaisesRegex(ValueError, 'foreign|Foreign'):
                adapter.read(fixture.saved, dict(player_id=pid, turn=8))
        self.assertEqual(fixture.evaluations, [])
        for mutation, message in ((b'cfg.active=false', 'not ready'),
                                  (b'cfg.observer=1', 'observer mismatch'),
                                  (b'Game.GetCurrentGameTurn=function() return 9 end', 'stale')):
            fixture.mutation = mutation
            with self.assertRaisesRegex(Exception, message):
                adapter.read(fixture.saved, fixture.token.observation)
        self.assertEqual(fixture.machine, [])

    def test_runtime_binding_and_bad_timeline_fail_before_action(self):
        fixture = self.fixture()
        unchanged = fixture.backend.runtime.read
        target = fixture.backend.core._handle + adapter.verify_source()['core_bodies'][0]['rva']

        def read(address, size):
            return bytes(size) if address == target else unchanged(address, size)

        with patch.object(fixture.backend.runtime, 'read', side_effect=read):
            with self.assertRaisesRegex(ValueError, 'Live Rise and Fall'):
                adapter.read(fixture.saved, fixture.token.observation)
        self.assertEqual(fixture.evaluations, [])
        for mutation, message in ((b'rows[5]=rows[1]', 'duplicate'),
                                  (b'rows[3]=nil', 'non-dense'),
                                  (b'YieldTypes.GOLD=42', 'currency selectors differ')):
            fixture.mutation = mutation
            with self.assertRaisesRegex(Exception, message):
                adapter.read(fixture.saved, fixture.token.observation)
        self.assertEqual(fixture.machine, [])

    def test_wire_identity_and_no_hidden_fields(self):
        identity = b'great-people-v1|0|8|1|1|1|1|0|1'
        points = b'P|4|GREAT_PERSON_CLASS_PROPHET|1|0|1.75|2'
        foreign = identity.replace(b'|0|8|', b'|1|8|', 1)
        for rows in ((foreign, points), (identity, points, points),
                     (identity, points, b'T|9|3|-'), (identity, points + b'|foreign_private_field'),
                     (identity, points.replace(b'1.75', b'1.123'))):
            with self.assertRaises(ValueError):
                adapter.parse(b'\n'.join(rows), 0, 8)


if __name__ == '__main__':
    unittest.main()
