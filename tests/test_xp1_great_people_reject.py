"""Offline verification of the private XP1 Great Person rejection extension."""

from copy import deepcopy
import struct
import unittest

from lupa.lua51 import LuaRuntime
from civ6_host.runtime import xp1_great_people_commands as commands
from civ6_host.runtime.execution_images import _XP1_PROFILE
from test_xp1_great_people import _ENV
from test_xp1_great_people_commands import Fixture as CommandsFixture, _LUA


REJECT = dict(kind='reject_great_person', individual_index=51, cost=2)
BASE = br'''
PlayerOperations.REJECT_GREAT_PERSON=95216200
rows[3].Claimant=0
local rejectCurrent=true
great.CanRecruitPerson=function()return false end
great.CanRejectPerson=function(_,pid,id)assert(pid==0);return id==51 and rejectCurrent end
great.GetRejectCost=function(_,pid,id)assert(pid==0 and id==51);return 2 end
points.GetPointsTotal=function(_,id)return id==5 and 40.25 or 17.00390625 end
'''


class Fixture(CommandsFixture):
    def __init__(self):
        super().__init__()
        self.saved.xp1_great_people_reject = True
        self.payload = bytes.fromhex('2fe15dc40000000048e2ac0502000000010000800100000042c35f38000002000000000000000000000033000000')
        self.choice = REJECT
        self.chosen = REJECT
        self.after = b'''
rows[3].Claimant=21
rows[3].Cost=38
rejectCurrent=false
points.GetPointsTotal=function(_,id)assert(id==5);return 38.25 end
'''

    def evaluate(self, child, code, name, **kw):
        if child is not self.token.ui_child or name not in (b'@xp1_public_great_people', b'@xp1_great_person_rejection'):
            raise AssertionError('Unexpected owner, Lua context or source')
        self.evaluations.append(name)
        source = _ENV + _LUA + BASE + self.mutation
        if self.granted is not None:
            source += self.after
        return LuaRuntime(encoding=None).execute(source + b'\n' + code)

    def collect(self, runtime, child, player_id):
        self.assert_observer(runtime, child, player_id)
        return deepcopy(self.observation)

    def ready(self):
        catalogue = commands.catalogue(self.saved, self.observation)
        self.set_active(True)
        return catalogue


class RejectionTests(unittest.TestCase):
    def fixture(self):
        f = Fixture()
        self.addCleanup(f.close)
        return f

    def test_offer_and_exact_command_without_cost_or_currency_parameter(self):
        f = self.fixture()
        value = f.ready()
        self.assertNotIn(REJECT, commands.actions(value))
        self.assertIn(REJECT, commands.actions(value, include_reject=True))
        self.assertEqual(commands.source_for(REJECT), commands.REJECT_SOURCE)
        self.assertEqual(len(commands.source_dependencies(_XP1_PROFILE)), 11)
        self.assertEqual(len(commands.source_dependencies(_XP1_PROFILE,include_reject=True)), 12)
        self.assertEqual(commands.verify_archive(f.payload, 0, REJECT)['parameters'], {0x385fc342:51})
        for delta in ({'individual_index':True},{'cost':True},{'cost':-2**31-1},
                      {'cost':2**31}, {'currency':'YIELD_GOLD'}):
            with self.assertRaises(ValueError):
                commands.validate_action(dict(REJECT, **delta))
        for cost in (-2**31,-2,0,2**31-1):
            self.assertEqual(commands.validate_action(dict(REJECT,cost=cost))['cost'],cost)

    def test_reassigned_current_or_archived_past_without_revealing_claimant(self):
        for mode in ('other_reservation', 'archived_unclaimed', 'archived_elsewhere'):
            with self.subTest(mode=mode):
                f = self.fixture()
                if mode != 'other_reservation':
                    past = 'nil' if mode=='archived_unclaimed' else '52'
                    f.after = f'''
table.remove(rows,3)
great.GetPastTimeline=function()return {{{{Individual=51,Class=5,Claimant={past},TurnGranted=8}}}}end
rejectCurrent=false
points.GetPointsTotal=function(_,id)assert(id==5);return 38.25 end
'''.encode('ascii')
                f.ready()
                result = commands.apply(f.saved, REJECT, f.observation)
                self.assertEqual(result['status'],'completed')
                self.assertEqual(result['action'],REJECT)
                self.assertEqual(result['observation'],f.observation)
                self.assertEqual(result['source_sha256'],commands.REJECT_SOURCE[1])
                self.assertEqual((result['effect']['points_before'],result['effect']['points_after']),(40.25,38.25))
                self.assertEqual(result['effect']['own_receipts_before'],result['effect']['own_receipts_after'])
                self.assertNotIn('claimant',str(result))
                self.assertEqual(f.token.publication_count,1)
                (_,_,pid,opcode,fields,_), = f.requested
                self.assertEqual((pid,opcode,fields),(0,0x05ace248,{0x385fc342:51}))

    def test_stale_disabled_and_native_refusal_do_not_apply(self):
        f = self.fixture()
        f.ready()
        f.saved.xp1_great_people_reject = False
        with self.assertRaisesRegex(ValueError,'selected Rise and Fall'):
            commands.apply(f.saved,REJECT,f.observation)
        f.saved.xp1_great_people_reject = True
        with self.assertRaisesRegex(RuntimeError,'stale or unavailable'):
            commands.apply(f.saved,dict(REJECT,cost=-2),f.observation)
        self.assertFalse(f.requested)
        f.can_start=False
        result=commands.apply(f.saved,REJECT,f.observation)
        self.assertEqual(result['status'],'refused')
        self.assertEqual(result['refusal_code'],'native_great_person_can_start_false')
        self.assertEqual(result['source_sha256'],commands.REJECT_SOURCE[1])
        self.assertEqual(f.token.publication_count,0)
        self.assertFalse(f.token.transport.pending)

    def test_committed_reservation_loss_and_exact_points_required(self):
        for after in (
            b"points.GetPointsTotal=function()return 38.25 end",
            b"rejectCurrent=false; rows[3].Claimant=nil; rows[3].Cost=38",
            b"rejectCurrent=false; rows[3].Claimant=nil; rows[3].Cost=39; points.GetPointsTotal=function()return 38.25 end",
        ):
            with self.subTest(after=after):
                f=self.fixture()
                f.after=after
                f.ready()
                with self.assertRaisesRegex(RuntimeError,'reservation loss'):
                    commands.apply(f.saved,REJECT,f.observation)
                self.assertEqual(f.token.publication_count,1)

    def test_zero_and_signed_quotes_follow_effect_without_concealing_eligibility(self):
        for quote,end,offered in ((0,40.25,40),(-2,42.25,42),(-2,40.25,42)):
            with self.subTest(quote=quote,end=end):
                f=self.fixture()
                f.mutation=f'\ngreat.GetRejectCost=function()return {quote} end\n'.encode('ascii')
                f.after=(f'\nrejectCurrent=false; rows[3].Claimant=nil; rows[3].Cost={offered};\n'
                          f'points.GetPointsTotal=function()return {end} end\n').encode('ascii')
                action=dict(REJECT,cost=quote)
                state=f.ready()
                self.assertIn(action,commands.actions(state,include_reject=True))
                result=commands.apply(f.saved,action,f.observation)
                self.assertEqual(result['effect']['cost'],quote)
                self.assertEqual(result['effect']['points_after'],end)


if __name__=='__main__':
    unittest.main()
