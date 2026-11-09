"""Wire codec and mocked Lua5.1 source checks for XP2 governor queries.

The Lua fixtures below are deterministic doubles, not native receipts. The
official GovernorSupport body is deliberately not copied or reimplemented.
"""
import os
from pathlib import Path
import sys
import unittest

from civ6_host.contracts import governors
from civ6_host.runtime import xp2_governors_query as query


LAB = Path(os.environ.get('CIV6_HOST_RESOURCE_ROOT', Path(__file__).resolve().parents[2] / 'civ6-rl-lab'))
sys.path.insert(0, str(LAB / 'work' / 'lua-test-deps'))
try:
    from lupa.lua51 import LuaError, LuaRuntime
except ImportError:
    LuaError = Exception
    LuaRuntime = None


def _payload(records=(), *, head=None, footer=None):
    lines = [head or 'H|0|17|-2147483648|2147483647|1|0', *records]
    if footer is None:
        footer = f'E|1|{len(lines)}'
    return ('\n'.join([*lines, footer])).encode('ascii')


def _full_records():
    return [
        'G|3|4294967295|1|0|0|1|-2147483648',
        'S|3|-2147483648|0|-2147483648|2147483647|~|~|1|1',
        'P|3|9|4294967295|0|1|1|0|2',
        'T|3|19|2147483647|1',
    ]


class GovernorWireCodecTests(unittest.TestCase):
    def test_complete_catalogue_preserves_signed_counters_and_uint_hashes(self):
        catalogue = query.parse_catalogue(_payload(_full_records()), 0, 17)
        self.assertEqual(catalogue, dict(
            player_id=0, current_game_turn=17,
            points_obtained=-2147483648, points_spent=2147483647,
            can_appoint=True, titles_considered=False,
            governors=[dict(
                index=3, hash=4294967295, appointed=True,
                can_ever_appoint=False, can_promote=False,
                assignment_open=True, turns_to_establish=-2147483648,
                status=dict(neutralized_turns=-2147483648, established=False,
                            turns_to_establish=-2147483648,
                            turns_on_site=2147483647, assigned_city=None,
                            govern_city_state=True, can_assign_to_major_civ=True),
                promotions=[dict(index=9, hash=4294967295, owned=False,
                                 can_earn=True, hidden=True, base_ability=False,
                                 level=2)],
                assignment_targets=[dict(owner=19, city_id=2147483647,
                                         can_assign=True)],
            )],
        ))

    def test_empty_catalogue_is_valid_but_missing_payload_is_not(self):
        payload = _payload([], footer='E|0|1')
        self.assertEqual(query.parse_catalogue(payload, 0, 17)['governors'], [])
        self.assertEqual(governors.actions(None), [])
        for malformed in (b'', payload[:-1], payload + b'\nextra',
                          b'H|0|17|0|0|1|0\nE|0|99'):
            with self.subTest(payload=malformed), self.assertRaises(ValueError):
                query.parse_catalogue(malformed, 0, 17)

    def test_truncated_extra_unknown_and_missing_status_records_are_rejected(self):
        cases = [
            _payload(['G|3|5|1|0|0|1|2'], footer='E|1|1'),
            _payload(['G|3|5|1|0|0|1|2|extra']),
            _payload(['X|3|5']),
            _payload(['S|3|0|0|0|0|~|~|0|0']),
            _payload(['G|3|5|1|0|0|1|2']),  # appointed, but no S status
            _payload(['G|3|5|0|0|0|1|2',
                      'S|3|0|0|0|0|~|4|0|0']),  # partial assigned city
            _payload(['G|3|5|0|0|0|1|2',
                      'S|4|0|0|0|0|~|~|0|0']),  # wrong/nonexistent owner index
        ]
        for payload in cases:
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                query.parse_catalogue(payload, 0, 17)

    def test_bad_indices_hashes_owners_and_noncanonical_integers_are_rejected(self):
        cases = [
            _payload(['G|-1|5|0|0|0|0|0']),
            _payload(['G|2147483648|5|0|0|0|0|0']),
            _payload(['G|1|4294967296|0|0|0|0|0']),
            _payload(['G|1|5|0|0|0|0|0', 'T|1|64|0|1'],
                     footer='E|1|2'),
            _payload(['G|1|5|0|0|0|0|0'], head='H|0|17|-0|0|1|0'),
            _payload(['G|1|5|0|0|0|0|0'], head='H|0|17|01|0|1|0'),
            _payload(['G|1|5|0|0|0|0|0'], head='H|0|17|+1|0|1|0'),
        ]
        for payload in cases:
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                query.parse_catalogue(payload, 0, 17)

    def test_duplicate_governor_and_promotion_identities_are_rejected(self):
        duplicate_hash = [
            'G|3|5|1|0|0|0|0', 'S|3|0|0|0|0|~|~|0|0',
            'G|4|5|0|1|1|0|0',
        ]
        duplicate_promotion = [
            'G|3|5|1|0|0|0|0', 'S|3|0|0|0|0|~|~|0|0',
            'P|3|2|8|0|0|0|0|1', 'P|3|3|8|0|0|0|0|1',
        ]
        for rows, count in ((duplicate_hash, 2), (duplicate_promotion, 1)):
            with self.subTest(rows=rows), self.assertRaises(ValueError):
                query.parse_catalogue(_payload(rows, footer=f'E|{count}|{1+len(rows)}'), 0, 17)

    def test_foreign_or_stale_header_and_record_count_mismatches_are_rejected(self):
        cases = [
            (_payload([], head='H|1|17|0|0|1|0', footer='E|0|1'), 0, 17),
            (_payload([], head='H|0|18|0|0|1|0', footer='E|0|1'), 0, 17),
            (_payload([], footer='E|1|1'), 0, 17),
            (_payload(_full_records(), footer='E|1|4'), 0, 17),
        ]
        for payload, player_id, turn in cases:
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                query.parse_catalogue(payload, player_id, turn)


@unittest.skipIf(LuaRuntime is None, 'Lua 5.1 fixture dependency unavailable')
class GovernorLuaSourceTests(unittest.TestCase):
    SUPPORT_STUB = b'-- fixture functions already installed'

    def _query_fixture(self, *, signed_hashes=False):
        lua = LuaRuntime(encoding=None)
        setup = br"""
local current_pid, current_turn = 0, 17
Game = {
 GetLocalPlayer=function() return current_pid end,
 GetLocalObserver=function() return current_pid end,
 GetCurrentGameTurn=function() return current_turn end,
}
local function row_iterator(rows)
 local n=0
 return function() n=n+1; if rows[n] then return rows[n] end end
end
local function members(rows)
 local n=0
 return function() n=n+1; if rows[n] then return n,rows[n] end end
end
local function city(owner,id)
 return {GetOwner=function() return owner end, GetID=function() return id end}
end
local current_destination=city(0,11)
local own_target=city(0,12)
local same_id_own=city(0,99)
local same_id_minor=city(19,99)
local minor_target=city(19,11)
local player_cities={Members=function() return members({current_destination,own_target,same_id_own}) end}
local capital_target=own_target
local major_cities={GetCapitalCity=function() return capital_target end}
local diplomacy={HasMet=function(_,id) return id==0 or id==19 end}
local player={
 GetGovernors=function() return manager end,
 GetCities=function() return player_cities end,
 GetDiplomacy=function() return diplomacy end,
}
local governor={
 GetType=function() return 1 end,
 GetNeutralizedTurns=function() return 0 end,
 GetAssignedCity=function() return current_destination end,
 IsEstablished=function() return false end,
 GetTurnsToEstablish=function() return -3 end,
 GetTurnsOnSite=function() return 2 end,
 IsGovernCityState=function() return true end,
 CanAssignToMajorCiv=function() return true end,
 HasPromotion=function(_,hash) return false end,
}
local promotion={Index=8,Hash=4294967295,BaseAbility=false,Level=2}
local definition={Index=1,Hash=1234,GovernorType='GOVERNOR_THE_AMBASSADOR'}
GameInfo={
 Governors=function() return row_iterator({definition}) end,
 GovernorPromotionSets=function()
  return row_iterator({{GovernorType='GOVERNOR_THE_AMBASSADOR',GovernorPromotion='PROMO'}})
 end,
 GovernorPromotions={PROMO=promotion},
}
local function minor(id,can_receive,rows)
 return {
  GetID=function() return id end,
  GetInfluence=function() return {CanReceiveInfluence=function() return can_receive end} end,
  GetCities=function()
   if id==20 or id==21 then error('unmet or non-influence minor cities must not be queried') end
   return {Members=function() return members(rows) end}
  end,
 }
end
PlayerManager={
 GetAliveMinors=function() return {
  minor(19,true,{minor_target,same_id_minor}),
  minor(20,true,{}),
  minor(21,false,{}),
 } end,
 GetAliveMajors=function() return {{GetID=function() return 0 end,
  GetCities=function() return major_cities end}} end,
}
manager={
 GetGovernorPoints=function() return -2 end,
 GetGovernorPointsSpent=function() return 7 end,
 CanAppoint=function() return false end,
 HasTitleBeenConsidered=function() return false end,
 GetGovernorList=function() return true,{governor} end,
 CanEverAppointGovernor=function() return false end,
 HasGovernor=function() return true end,
 CanPromoteGovernor=function() return false end,
 GetTurnsToEstablish=function() return -4 end,
 CanEarnPromotion=function(_,_,_) return true end,
 CanAssignGovernor=function(_,_,target,_) return target:GetOwner()==19 end,
}
Players={[0]=player}
function GetAppointedGovernor(pid,index)
 if pid==0 and index==1 then return governor end
 return nil
end
function IsCannotAssign(def) return false end
function IsPromotionHidden(hash,pid,index) return true end
"""
        if signed_hashes:
            setup = setup.replace(b'Hash=1234', b'Hash=-2147483648')
            setup = setup.replace(b'Hash=4294967295', b'Hash=-1')
        lua.execute(setup)
        return lua

    def test_signed_hash_spellings_preserve_native_arguments_and_canonical_wire_identity(self):
        lua = self._query_fixture(signed_hashes=True)
        lua.execute(b'''manager.CanEarnPromotion=function(_,governor,promotion)
            assert(governor==-2147483648 and promotion==-1)
            return true
        end''')
        catalogue = query.parse_catalogue(lua.execute(
            query.catalogue_source(0, 17, self.SUPPORT_STUB)), 0, 17)
        self.assertEqual(catalogue['governors'][0]['hash'], 0x80000000)
        self.assertEqual(catalogue['governors'][0]['promotions'][0]['hash'], 0xffffffff)

    def test_foreign_observer_refuses_before_query(self):
        lua = self._query_fixture()
        lua.execute(b'Game.GetLocalObserver=function() return 1 end')
        with self.assertRaises(LuaError):
            lua.execute(query.catalogue_source(0, 17, self.SUPPORT_STUB))

    def test_query_source_uses_engine_getters_and_preserves_ui_filtered_targets(self):
        lua = self._query_fixture()
        source = query.catalogue_source(0, 17, self.SUPPORT_STUB)
        payload = lua.execute(source)
        catalogue = query.parse_catalogue(payload, 0, 17)

        self.assertEqual(catalogue['points_obtained'], -2)
        self.assertEqual(catalogue['points_spent'], 7)
        governor = catalogue['governors'][0]
        self.assertEqual(governor['promotions'], [dict(
            index=8, hash=0xffffffff, owned=False, can_earn=True,
            hidden=True, base_ability=False, level=2)])
        self.assertEqual(governor['status']['assigned_city'], dict(owner=0, city_id=11))
        self.assertEqual(governor['assignment_targets'], [
            dict(owner=0, city_id=12, can_assign=True),
            dict(owner=0, city_id=99, can_assign=True),
            dict(owner=19, city_id=11, can_assign=True),
            dict(owner=19, city_id=99, can_assign=True),
        ])
        target_actions = [a for a in governors.actions(catalogue)
                          if a['kind'] == 'assign_governor']
        self.assertEqual([(a['city_owner'], a['city_id']) for a in target_actions],
                         [(0, 12), (0, 99), (19, 11), (19, 99)])

    def test_consideration_source_refuses_stale_context_or_already_considered_before_setter(self):
        def make_lua(pid, turn, already_considered=False, observer=None):
            lua = LuaRuntime(encoding=None)
            lua.execute(f"""
current_pid={pid}; current_turn={turn};
Game={{GetLocalPlayer=function() return current_pid end,
 GetLocalObserver=function() return {pid if observer is None else observer} end,
 GetCurrentGameTurn=function() return current_turn end}}
manager={{considered={str(already_considered).lower()},set_calls=0,
 HasTitleBeenConsidered=function(self) return self.considered end,
 SetTitleConsidered=function(self,value) self.set_calls=self.set_calls+1; self.considered=value end}}
Players={{[0]={{GetGovernors=function() return manager end}}}}
""".encode('ascii'))
            return lua

        for pid, turn, considered, observer in ((1, 17, False, 1), (0, 18, False, 0),
                                               (0, 17, True, 0), (0, 17, False, 1)):
            lua = make_lua(pid, turn, considered, observer)
            source = query.consideration_source(0, 17)
            with self.subTest(pid=pid, turn=turn, considered=considered):
                with self.assertRaises(LuaError):
                    lua.execute(source)
                self.assertEqual(lua.globals()[b'manager'][b'set_calls'], 0)


if __name__ == '__main__':
    unittest.main()
