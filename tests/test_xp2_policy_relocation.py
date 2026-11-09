"""Official Lua row rules and request construction; not native GameCore proof."""
from pathlib import Path
import re
import unittest

from civ6_host.runtime import xp2_policy_relocation as relocation
from civ6_host.runtime.native import native_policy_catalog as catalog

try:
    from lupa.lua51 import LuaRuntime, LuaError
except ImportError:
    LuaRuntime = None


FIXTURE = '''
local specs={'SLOT_ECONOMIC','SLOT_ECONOMIC','SLOT_DIPLOMATIC','SLOT_MILITARY'}
slots={[0]=0,[1]=1,[2]=2,[3]=3}
c={}
function c:GetNumPolicySlots() return 4 end
function c:GetSlotPolicy(i) return slots[i] end
function c:GetSlotType(i) return ({[0]=0,[1]=0,[2]=1,[3]=2})[i] end
function c:PolicyChangeMade() return false end
function c:GetCostToUnlockPolicies() return 0 end
function c:CivicCompletedThisTurn() return true end
function c:GetNumPolicySlotsOpen() return 0 end
function c:IsPolicyUnlocked(h) return true end
function c:IsPolicyObsolete(h) return false end
function c:CanSlotPolicy(h,s) error('Active cards must use the qualified row rule') end
function c:RequestPolicyChanges(clear,add)
 assert(#clear==4)
 for i=1,4 do assert(clear[i]==i-1);slots[i-1]=-1 end
 for i=0,3 do slots[i]=add[i]/10-1 end
 return true
end
local player={}
function player:IsAlive() return true end
function player:IsTurnActive() return true end
function player:IsTurnActiveComplete() return true end
function player:GetCulture() return c end
Players={[0]=player}
Game={GetLocalPlayer=function() return 0 end,GetLocalObserver=function() return 0 end,
 GetCurrentGameTurn=function() return 45 end,IsAllowStrategicCommands=function() return true end}
GameInfo={Policies={},Types={},GovernmentSlots={
 [0]={GovernmentSlotType='SLOT_ECONOMIC'},[1]={GovernmentSlotType='SLOT_DIPLOMATIC'},
 [2]={GovernmentSlotType='SLOT_WILDCARD'}}}
for i=0,3 do
 local name='POLICY_TEST_'..i
 GameInfo.Policies[i]={Index=i,Hash=(i+1)*10,PolicyType=name,GovernmentSlotType=specs[i+1]}
 GameInfo.Types[name]={Hash=(i+1)*10}
end
setmetatable(GameInfo.Policies,{__call=function()
 local i=-1
 return function() i=i+1;return GameInfo.Policies[i] end
end})
'''


@unittest.skipIf(LuaRuntime is None, 'The existing Lua5.1 fixture dependency is required')
class PolicyRelocationLuaTests(unittest.TestCase):
    def runtime(self):
        lua=LuaRuntime(encoding=None)
        lua.execute(FIXTURE.encode())
        return lua

    def test_active_options_and_atomic_swap_execute_the_shared_request(self):
        lua=self.runtime()
        raw=lua.execute(relocation.catalog_source(0,45))
        value=catalog.parse_catalog(raw,0,45,allow_relocation=True)
        self.assertEqual([[r['index'] for r in slot['options']] for slot in value['slots']],
                         [[0,1],[0,1],[2],[0,1,2,3]])
        from civ6_host.contracts.policies import choose
        candidate=choose(value['slots'],[20,10,30,40],0,45,allow_relocation=True)
        self.assertEqual(lua.execute(relocation.request_source(0,candidate)),b'accepted,0,45,4')
        self.assertEqual([lua.globals()[b'slots'][i] for i in range(4)],[1,0,2,3])
        with self.assertRaises(LuaError):
            lua.execute(relocation.request_source(0,candidate))  # Stale prior occupants.

    def test_official_ui_row_truth_table_matches_without_native_slot_mutation(self):
        proof=relocation.verify_ui_source()
        from civ6_host.runtime.paths import resource_root
        from civ6_host.runtime.resource_resolution import resolve_path
        ui=resolve_path(resource_root()/proof['ui']['path']).read_text(encoding='utf-8-sig')
        start=ui.index('function IsSlotTypeLegalInRow(')
        end=ui.index('function IsPolicyTypeLegalInRow(',start)
        function=re.sub(r':\s*(?:number|string)\b','',ui[start:end])
        lua=LuaRuntime(encoding=None)
        official=lua.execute(('''
local m_isAllowWildcardsAnywhere=false
local m_isAllowAnythingInWildcardSlot=true
local m_ActivePolicyRows={{SlotArray={1}},{SlotArray={1}},{SlotArray={1}},{SlotArray={1}}}
ROW_INDEX={MILITARY=1,ECONOMIC=2,DIPLOMAT=3,WILDCARD=4}
ROW_SLOT_TYPES={'SLOT_MILITARY','SLOT_ECONOMIC','SLOT_DIPLOMATIC','SLOT_WILDCARD'}
'''+function+'\nreturn IsSlotTypeLegalInRow').encode())
        ours=lua.execute(relocation.SLOT_LEGALITY+b'''
return function(policyType,slotType)
 GameInfo={Policies={[0]={GovernmentSlotType=policyType}},
  GovernmentSlots={[0]={GovernmentSlotType=slotType}}}
 return policyFitsAfterClear({GetSlotType=function() return 0 end},{index=0},0)
end
''')
        types=[b'SLOT_MILITARY',b'SLOT_ECONOMIC',b'SLOT_DIPLOMATIC',b'SLOT_WILDCARD']
        for i,target in enumerate(types,1):
            for policy in [*types,b'SLOT_GREAT_PERSON']:
                self.assertEqual(ours(policy,target),official(i,policy),(policy,target))
        with self.assertRaises(LuaError): ours(b'SLOT_UNKNOWN',types[0])

    def test_catalogue_legacy_default_still_rejects_relocation(self):
        raw=self.runtime().execute(relocation.catalog_source(0,45))
        with self.assertRaisesRegex(ValueError,'relocation'):
            catalog.parse_catalog(raw,0,45)

    def test_unchanged_confirmation_requires_explicit_new_mode_and_keeps_window_guards(self):
        from civ6_host.contracts.policies import choose
        lua=self.runtime()
        value=catalog.parse_catalog(lua.execute(relocation.catalog_source(0,45)),0,45,
                                    allow_relocation=True)
        candidate=choose(value['slots'],[10,20,30,40],0,45,
                         allow_relocation=True,allow_unchanged=True)
        with self.assertRaisesRegex(LuaError,'unchanged policy assignments'):
            lua.execute(relocation.request_source(0,candidate))
        lua.execute(b'''requests=0
local original=c.RequestPolicyChanges
function c:RequestPolicyChanges(clear,add)
 requests=requests+1;return original(self,clear,add)
end''')
        raw=lua.execute(relocation.request_source(0,candidate,allow_unchanged=True))
        self.assertEqual(raw,b'accepted,0,45,4')
        self.assertEqual(lua.globals()[b'requests'],1)
        self.assertEqual([lua.globals()[b'slots'][i] for i in range(4)],[0,1,2,3])
        lua.execute(b'function c:PolicyChangeMade() return true end')
        with self.assertRaisesRegex(LuaError,'policy changes already submitted'):
            lua.execute(relocation.request_source(0,candidate,allow_unchanged=True))


class PolicyConfirmationStateTests(unittest.TestCase):
    def test_window_state_parser_is_exact_and_bound_to_player_turn(self):
        expected=dict(player_id=0,turn=45,slot_count=4,changed=True,open_slots=0,
                      civic_completed=True,unlock_cost=0)
        self.assertEqual(relocation.parse_confirmation_state(b'0|45|4|1|0|1|0',0,45),expected)
        for raw in (b'0|45|4|2|0|1|0',b'0|45|4|1|5|1|0',b'0|45|4|1|0|1|-1',
                    b'0|44|4|1|0|1|0',b'1|45|4|1|0|1|0',b'0|45|4|1|0|1|0\n'):
            with self.subTest(raw=raw),self.assertRaises(ValueError):
                relocation.parse_confirmation_state(raw,0,45)
        with self.assertRaises(ValueError):
            relocation.parse_confirmation_state(b'0|45|4|1|0|1|0',False,45)


if __name__=='__main__': unittest.main()
