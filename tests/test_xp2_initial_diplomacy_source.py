import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from civ6_host.runtime import diplomacy_overview, xp2_diplomacy_overview_source as xp2
from civ6_host.runtime.execution_images import _PROFILE as CURRENT_IMAGE

try:
    from lupa.lua51 import LuaRuntime
except ImportError:
    LuaRuntime = None


def selection(key, *, disabled=False, supported=None):
    if supported is None:
        supported = key in xp2.DIRECT_REQUEST_CHOICES
    return dict(key=key, disabled=disabled, supported=supported,
                text='LOC_' + key, tooltip=None, diplomatic_action_type=None)


def configuration(*, paused=False):
    return dict(initiator=1, paused=paused,
                players={0: dict(leader='LEADER_CATHERINE_DE_MEDICI'),
                         1: dict(human=True)})


ROWS = [
    selection('CHOICE_DECLARE_FORMAL_WAR'),
    selection('CHOICE_DECLARE_GOLDEN_AGE_WAR'),
    selection('CHOICE_MAKE_DEAL'),
    selection('CHOICE_ALLIANCE_MILITARY'),
    selection('CHOICE_RENEW_ALLIANCE'),
    selection('CHOICE_EXIT'),
    selection('CHOICE_DENOUNCE', disabled=True),
]


class XP2InitialDiplomacySourceTests(unittest.TestCase):
    def generated(self, paused=False):
        with patch.object(xp2, '_helpers', return_value=b''), \
                patch.object(diplomacy_overview, '_verify_capability_source'):
            return xp2.source(0, 8, configuration=configuration(paused=paused),
                              execution_image=CURRENT_IMAGE)

    def generated_request(self, key):
        with patch.object(xp2, '_helpers', return_value=b''), \
                patch.object(diplomacy_overview, '_verify_capability_source'):
            return xp2.request_source(0, 8, 2, key, configuration=configuration(),
                                      execution_image=CURRENT_IMAGE)

    def test_profile_pins_selected_xp1_dispatch_and_base_fallback(self):
        profile = xp2._load_profile()
        self.assertEqual(profile['official_files']['xp1_view']['sha256'],
                         'aee6e35dba8a732a7a98674153965bd197fe90f4cfee3c51fecaf57167dc0e6a')
        self.assertEqual(profile['official_files']['xp2_view']['sha256'],
                         '652552cff5f5bb18634ed16ce4951a4f18d4ca33e7085b18371490b4555d2648')
        xp1_dispatch = xp2._function(profile, 'xp1', 'OnSelectInitialDiplomacyStatement')
        base_dispatch = xp2._function(profile, 'base', 'OnSelectInitialDiplomacyStatement')
        self.assertIn(b'BASE_OnSelectInitialDiplomacyStatement(key)', xp1_dispatch)
        self.assertIn(b'CHOICE_DECLARE_GOLDEN_AGE_WAR', xp1_dispatch)
        self.assertIn(b'CHOICE_DECLARE_WAR_OF_RETRIBUTION', xp1_dispatch)
        self.assertIn(b'CHOICE_DECLARE_IDEOLOGICAL_WAR', xp1_dispatch)
        self.assertIn(b'function OnSelectInitialDiplomacyStatement', base_dispatch)
        self.assertIn('GetInitialStatementOptions', profile['functions']['xp1'])
        self.assertIn('IsWarChoice', profile['functions']['xp1'])
        self.assertIn('GetWarType', profile['functions']['xp1'])

    @unittest.skipIf(LuaRuntime is None, 'Lua 5.1 fixture unavailable')
    def test_overview_filters_targets_preserves_order_disabled_state_and_unsupported_rows(self):
        lua = LuaRuntime(unpack_returned_tuples=True)
        lua.execute(LUA_FIXTURE)
        data = xp2.parse(lua.execute(self.generated()).encode(), 0, 8)
        self.assertEqual([t['player_id'] for t in data['targets']], [2])
        rows = data['targets'][0]['selections']
        self.assertEqual([r['key'] for r in rows], [r['key'] for r in ROWS if r['key'] != 'CHOICE_EXIT'])
        self.assertEqual([r['supported'] for r in rows], [True, True, False, False, False, True])
        self.assertTrue(rows[-1]['disabled'])
        self.assertEqual([row['choice'] for row in xp2.candidates(data)], [
            'CHOICE_DECLARE_FORMAL_WAR', 'CHOICE_DECLARE_GOLDEN_AGE_WAR'])
        for row in rows[2:5]:
            self.assertFalse(row['supported'])

    @unittest.skipIf(LuaRuntime is None, 'Lua 5.1 fixture unavailable')
    def test_xp1_direct_branch_and_base_fallback_each_request_exact_native_type(self):
        for key, kind in (
                ('CHOICE_DECLARE_GOLDEN_AGE_WAR', 'DECLARE_GOLDEN_WAR'),
                ('CHOICE_DENOUNCE', 'DENOUNCE')):
            with self.subTest(key=key):
                lua = LuaRuntime(unpack_returned_tuples=True)
                lua.execute(LUA_FIXTURE + ('\ndenounceDisabled=false' if key == 'CHOICE_DENOUNCE' else ''))
                result = lua.execute(self.generated_request(key))
                self.assertEqual(result, 'requested')
                self.assertEqual(lua.eval('#nativeRequests'), 1)
                self.assertEqual(lua.eval('nativeRequests[1][1]'), 0)
                self.assertEqual(lua.eval('nativeRequests[1][2]'), 2)
                self.assertEqual(lua.eval('nativeRequests[1][3]'), kind)

    @unittest.skipIf(LuaRuntime is None, 'Lua 5.1 fixture unavailable')
    def test_native_refusal_is_a_distinct_receipt_and_unsupported_deals_cannot_execute(self):
        lua = LuaRuntime(unpack_returned_tuples=True)
        lua.execute(LUA_FIXTURE + '\nrequestAccepted=false')
        result = lua.execute(self.generated_request('CHOICE_DECLARE_GOLDEN_AGE_WAR'))
        self.assertEqual(result, 'not_requested')
        self.assertEqual(lua.eval('#nativeRequests'), 1)
        for key in ('CHOICE_MAKE_DEAL', 'CHOICE_ALLIANCE_MILITARY',
                    'CHOICE_RENEW_ALLIANCE', 'CHOICE_EXIT'):
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.generated_request(key)

    def test_source_dependencies_and_foreign_images_fail_closed(self):
        dependencies = xp2.source_dependencies(execution_image=CURRENT_IMAGE)
        self.assertIn(str(xp2.resource_root() / xp2.PROFILE_PATH), dependencies)
        self.assertTrue(any(path.endswith('DiplomacyActionView_Expansion1.lua')
                            for path in dependencies))
        profile = xp2._load_profile()
        with patch.object(xp2, '_official_bytes', return_value=b'changed source'), \
                self.assertRaises(ValueError):
            xp2._function(profile, 'xp1', 'OnSelectInitialDiplomacyStatement')
        for wrong in (None, SimpleNamespace(id='xp2-other-image')):
            with self.subTest(image=wrong), self.assertRaises(ValueError):
                xp2.source(0, 8, configuration=configuration(), execution_image=wrong)
            with self.subTest(image=wrong), self.assertRaises(ValueError):
                xp2.source_dependencies(execution_image=wrong)

    def test_parser_rejects_forged_support_identity_and_exit(self):
        data = dict(schema=xp2.SCHEMA, player_id=0, turn=8, capability=True,
                    paused=False, targets=[dict(player_id=2, selections=[
                        selection('CHOICE_MAKE_DEAL', supported=True)])],
                    complete_action_space=False)
        with self.assertRaises(ValueError):
            xp2.parse(json.dumps(data).encode(), 0, 8)
        data['targets'][0]['selections'] = [selection('CHOICE_EXIT')]
        with self.assertRaises(ValueError):
            xp2.parse(json.dumps(data).encode(), 0, 8)


LUA_FIXTURE = r'''
requestAccepted=true
denounceDisabled=true
Game={GetLocalPlayer=function() return 0 end,
 GetLocalObserver=function() return 0 end,
 GetCurrentGameTurn=function() return 8 end}
GameInfo={GameCapabilities={CAPABILITY_DIPLOMACY=true}}
GameConfiguration={IsPaused=function() return false end}
DiplomacyMoodTypes={ANY=1}
DiplomacyInitiatorTypes={HUMAN=1}
local localDiplomacy={HasMet=function(self,id) return id==2 end}
Players={}
Players[0]={GetID=function(self) return 0 end,
 GetDiplomacy=function(self) return localDiplomacy end}
local p2={GetID=function(self) return 2 end,
 IsMajor=function(self) return true end}
local p3={GetID=function(self) return 3 end,
 IsMajor=function(self) return true end}
local p4={GetID=function(self) return 4 end,
 IsMajor=function(self) return false end}
Players[2]=p2; Players[3]=p3; Players[4]=p4
PlayerManager={GetAliveMajors=function(self) return {p2,p3,p4} end}
local greeting={Selections={
 {Key='CHOICE_DECLARE_FORMAL_WAR',Sort=1,Text='LOC_FORMAL',Tooltip=nil,DiplomaticActionType='FORMAL',IsDisabled=false},
 {Key='CHOICE_DECLARE_GOLDEN_AGE_WAR',Sort=2,Text='LOC_GOLDEN',Tooltip=nil,DiplomaticActionType='GOLDEN',IsDisabled=false},
 {Key='CHOICE_MAKE_DEAL',Sort=3,Text='LOC_DEAL',Tooltip=nil,DiplomaticActionType='MAKE_DEAL',IsDisabled=false},
 {Key='CHOICE_ALLIANCE_MILITARY',Sort=4,Text='LOC_ALLIANCE',Tooltip=nil,DiplomaticActionType='MAKE_DEAL',IsDisabled=false},
 {Key='CHOICE_RENEW_ALLIANCE',Sort=5,Text='LOC_RENEW',Tooltip=nil,DiplomaticActionType='RENEW',IsDisabled=false},
 {Key='CHOICE_EXIT',Sort=6,Text='LOC_EXIT',Tooltip=nil,DiplomaticActionType=nil,IsDisabled=false},
 {Key='CHOICE_DENOUNCE',Sort=7,Text='LOC_DENOUNCE',Tooltip=nil,DiplomaticActionType='DENOUNCE',IsDisabled=false},
}}
local handler={}
handler.ExtractStatement=function(self,kind,subtype,initiator,mood,initiatorType)
 assert(kind=='GREETING' and subtype=='NONE' and initiator==0 and mood==1 and initiatorType==1)
 local copy={Selections={}}
 for i,s in ipairs(greeting.Selections) do
  copy.Selections[i]={Key=s.Key,Sort=s.Sort,Text=s.Text,Tooltip=s.Tooltip,
   DiplomaticActionType=s.DiplomaticActionType,
   IsDisabled=(s.Key=='CHOICE_DENOUNCE' and denounceDisabled) or s.IsDisabled}
 end
 return copy
end
handler.RemoveInvalidSelections=function(self,parsed,player,target) end
GetStatementHandler=function(kind) assert(kind=='GREETING'); return handler end
DiplomacySupport_RemoveSelectionByKey=function(parsed,key)
 for i=#parsed.Selections,1,-1 do
  if parsed.Selections[i].Key==key then table.remove(parsed.Selections,i) end
 end
end
nativeRequests={}
DiplomacyManager={RequestSession=function(attacker,target,kind)
 nativeRequests[#nativeRequests+1]={attacker,target,kind}; return requestAccepted
end}
'''


if __name__ == '__main__':
    unittest.main()
