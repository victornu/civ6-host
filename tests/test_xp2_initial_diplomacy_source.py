import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from civ6_host.runtime import diplomacy_overview, xp2_diplomacy_overview_source as xp2
from civ6_host.runtime.execution_images import _PROFILE as CURRENT_IMAGE

try:
    from lupa.lua51 import LuaError, LuaRuntime
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
    selection('CHOICE_DECLARE_FRIENDSHIP'),
]


class XP2InitialDiplomacySourceTests(unittest.TestCase):
    def generated(self, paused=False):
        with patch.object(xp2, '_helpers', return_value=b''), \
                patch.object(diplomacy_overview, '_verify_capability_source'):
            return xp2.source(0, 8, configuration=configuration(paused=paused),
                              execution_image=CURRENT_IMAGE)

    def generated_request(self, key, **options):
        with patch.object(xp2, '_helpers', return_value=b''), \
                patch.object(diplomacy_overview, '_verify_capability_source'):
            return xp2.request_source(0, 8, 2, key, configuration=configuration(),
                                      execution_image=CURRENT_IMAGE, **options)

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
        self.assertEqual([r['supported'] for r in rows], [True, True, False, False, False, True, True])
        self.assertTrue(rows[-2]['disabled'])
        self.assertEqual([row['choice'] for row in xp2.candidates(data)], [
            'CHOICE_DECLARE_FORMAL_WAR', 'CHOICE_DECLARE_GOLDEN_AGE_WAR', 'CHOICE_DECLARE_FRIENDSHIP'])
        for row in rows[2:5]:
            self.assertFalse(row['supported'])

    @unittest.skipIf(LuaRuntime is None, 'Lua 5.1 fixture unavailable')
    def test_xp1_direct_branch_and_base_fallback_each_request_exact_native_type(self):
        for key, kind in (
                ('CHOICE_DECLARE_GOLDEN_AGE_WAR', 'DECLARE_GOLDEN_WAR'),
                ('CHOICE_DENOUNCE', 'DENOUNCE'),
                ('CHOICE_DECLARE_FRIENDSHIP', 'DECLARE_FRIEND')):
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
    def test_stock_promise_choices_use_the_official_warning_requests(self):
        cases = dict(CHOICE_DEMAND_PROMISE_DONT_SPY='WARNING_STOP_SPYING_ON_ME',
            CHOICE_DEMAND_PROMISE_DONT_SETTLE_TOO_NEAR='WARNING_DONT_SETTLE_NEAR_ME',
            CHOICE_DEMAND_PROMISE_DONT_CONVERT_CITY='WARNING_STOP_CONVERTING_MY_CITIES',
            CHOICE_DEMAND_PROMISE_DONT_DIG_ARTIFACTS='WARNING_STOP_DIGGING_UP_ARTIFACTS')
        for key, kind in cases.items():
            with self.subTest(key=key):
                lua = LuaRuntime(unpack_returned_tuples=True)
                lua.execute(LUA_FIXTURE + '\n' +
                            'table.insert(greeting.Selections,{Key="' + key + '",Sort=9,IsDisabled=false})')
                self.assertEqual(lua.execute(self.generated_request(key)), 'requested')
                self.assertEqual(lua.eval('#nativeRequests'), 1)
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

    @unittest.skipIf(LuaRuntime is None, 'Lua 5.1 fixture unavailable')
    def test_empty_deal_dispatch_checks_counterparty_before_clearing_and_requests_once(self):
        code = self.generated_request('CHOICE_MAKE_DEAL', deal_draft=True)
        lua = LuaRuntime(unpack_returned_tuples=True)
        lua.execute(LUA_FIXTURE + """
human=false; pendingDeal=false; clears=0
Players[2].IsHuman=function() return human end
DealDirection={OUTGOING=0}
DealManager={HasPendingDeal=function(a,b) assert(a==0 and b==2); return pendingDeal end,
 ClearWorkingDeal=function(direction,a,b)
  assert(direction==0 and a==0 and b==2 and #nativeRequests==0)
  clears=clears+1
 end}
""")
        for guard in ('human=true', 'human=false; pendingDeal=true'):
            lua.execute(guard)
            with self.assertRaises(LuaError):
                lua.execute(code)
            self.assertEqual(lua.eval('clears+#nativeRequests'), 0)
        lua.execute('pendingDeal=false')
        self.assertEqual(lua.execute(code), 'requested')
        self.assertEqual(lua.eval('clears'), 1)
        self.assertEqual(lua.eval('#nativeRequests'), 1)
        self.assertEqual(lua.eval('nativeRequests[1][3]'), 'MAKE_DEAL')

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

    @unittest.skipIf(LuaRuntime is None, 'Lua 5.1 fixture unavailable')
    def test_major_peace_dispatch_requires_native_locked_reciprocal_terms_before_request(self):
        from civ6_host.runtime import xp2_deal_peace as peace

        code = self.generated_request('CHOICE_MAKE_PEACE', deal_draft=True)
        lua = LuaRuntime()
        lua.execute(LUA_FIXTURE + """
local selected={Key='CHOICE_MAKE_PEACE', IsDisabled=true}
greeting.Selections[#greeting.Selections+1]=selected
function enablePeace() selected.IsDisabled=false end
human=false; pendingDeal=false; addReciprocal=false; clears=0
Players[2].IsHuman=function() return human end
DealDirection={OUTGOING=0}
DealItemTypes={AGREEMENTS=2344584396-4294967296}
DealAgreementTypes={MAKE_PEACE=547027585}
local items={}
local function item(giver)
 local subtype,locked=nil,false
 return {giver=giver,SetSubType=function(_,v) subtype=v end,GetSubType=function() return subtype end,
  SetLocked=function(_,v) locked=v end,IsLocked=function() return locked end,GetDuration=function() return 10 end}
end
working={
 AddItemOfType=function(_,kind,giver)
  assert(kind==DealItemTypes.AGREEMENTS and giver==0 and #items==0)
  items[1]=item(giver); return items[1]
 end,
 Validate=function()
  assert(items[1]:IsLocked() and items[1]:GetSubType()==DealAgreementTypes.MAKE_PEACE)
  if addReciprocal then
   items[2]=item(2); items[2]:SetSubType(DealAgreementTypes.MAKE_PEACE); items[2]:SetLocked(true)
  end
 end,
 GetItemCount=function() return #items end,
 FindItemsByType=function(_,kind,subtype,giver)
  assert(kind==DealItemTypes.AGREEMENTS and subtype==DealAgreementTypes.MAKE_PEACE)
  for _,entry in ipairs(items) do if entry.giver==giver then return {entry} end end
  return {}
 end,
}
DealManager={
 HasPendingDeal=function(a,b) assert(a==0 and b==2); return pendingDeal end,
 ClearWorkingDeal=function(direction,a,b)
  assert(direction==0 and a==0 and b==2 and #nativeRequests==0)
  clears=clears+1; items={}
 end,
 GetWorkingDeal=function(direction,a,b)
  assert(direction==0 and a==0 and b==2)
  return working
 end,
}
pDealItem='prior global'
""")
        with self.assertRaises(LuaError):
            lua.execute(code)
        self.assertEqual(lua.eval('clears+#nativeRequests'), 0)
        lua.execute('enablePeace(); pendingDeal=true')
        with self.assertRaises(LuaError):
            lua.execute(code)
        self.assertEqual(lua.eval('clears+#nativeRequests'), 0)
        lua.execute('pendingDeal=false')
        with self.assertRaises(LuaError):
            lua.execute(code)
        self.assertEqual(lua.eval('#nativeRequests'), 0)
        lua.execute('addReciprocal=true')
        self.assertEqual(lua.execute(code), 'requested')
        self.assertEqual(lua.eval('#nativeRequests'), 1)
        self.assertEqual(lua.eval('nativeRequests[1][3]'), 'MAKE_DEAL')
        self.assertEqual(lua.eval('pDealItem'), 'prior global')
        raw = lua.execute(b'local deal,me,other,queued=working,0,2,false\n' + peace.READ_OPENING).encode()
        self.assertEqual(peace.parse_opening(raw), (False, [
            {'direction':'outgoing','duration':10,'locked':True},
            {'direction':'incoming','duration':10,'locked':True},
        ]))

    def test_gold_deal_source_verifies_the_installed_pe_binding_spans(self):
        import pefile
        from civ6_host.runtime import execution_images, xp2_deal_gold

        image = execution_images.select(CURRENT_IMAGE.id, core_path=execution_images._GAMECORE_PATH)
        pe = pefile.PE(image.path, fast_load=True)
        self.addCleanup(pe.close)
        base = pe.OPTIONAL_HEADER.ImageBase
        runtime = SimpleNamespace(read=lambda address,size: pe.get_data(address-base,size))
        saved = SimpleNamespace(backend=SimpleNamespace(core=SimpleNamespace(_handle=base),runtime=runtime))
        xp2_deal_gold.verify(saved, image)
        runtime.read = lambda address,size: bytes(size)
        with self.assertRaisesRegex(ValueError, 'Live native gold deal source changed'):
            xp2_deal_gold.verify(saved, image)

    @unittest.skipIf(LuaRuntime is None, 'Lua 5.1 fixture unavailable')
    def test_gold_draft_edit_uses_native_maximum_and_inspects_before_finalize(self):
        from civ6_host.runtime import xp2_deal_gold as gold

        lua = LuaRuntime()
        lua.execute("""
DealItemTypes={GOLD=0}; DealItemSubTypes={NONE=0}
DealProposalAction={ACCEPTED=1,REJECTED=2,ADJUSTED=3,PROPOSED=4,EQUALIZE=6,INSPECT=7,EQUALIZE_FAILED=10}
Players={[0]={GetTreasury=function() return {GetGoldBalance=function() return 147.8 end} end}}
local current=nil
requests={}
working={
 GetItemCount=function(self,from) return current and from~=1 and 1 or 0 end,
 FindItemsByType=function(self,t,s,p) return current and {current} or nil end,
 AddItemOfType=function(self,t,p)
  assert(current==nil and t==0 and p==0)
  local n,d=0,100
  current={SetDuration=function(self,v) d=v end, GetDuration=function() return d end,
           SetAmount=function(self,v) n=v end, GetAmount=function() return n end,
           GetMaxAmount=function() assert(d==0); return 143 end, GetID=function() return 12 end}
  return current
 end,
 RemoveItemByID=function(self,id) assert(id==12); current=nil end,
 Validate=function() assert(current:GetAmount()>0) end,
 IsValid=function() return current~=nil end, HasUnacceptableItems=function() return false end
}
DealManager={
 GetPossibleDealItems=function(me,other,kind,deal)
  assert(me==0 and other==1 and kind==0 and deal==working)
  return {{Duration=0}}
 end,
 SendWorkingDeal=function(action,me,other)
  assert(action==7 or action==4 or action==1)
  assert(me==0 and other==1 and current:GetAmount()==17)
  table.insert(requests,action); return 1
 end,
 AreWorkingDealsEqual=function() return true end
}
""")
        prefix = b'local me,other,deal,queued=0,1,working,false\n'
        self.assertEqual(lua.execute(gold.edit_source(prefix, 145)), 'unavailable')
        self.assertEqual(lua.eval('working:GetItemCount()'), 0)
        self.assertEqual(lua.execute(gold.edit_source(prefix, 17)), 'inspected')
        self.assertEqual(lua.execute(gold.read_source(prefix,'accepted',acceptance_ready=False)),
                         'closable|17|143|none')
        self.assertEqual(lua.execute(gold.read_source(prefix,'accepted',acceptance_ready=True)),
                         'closable|17|143|accept')
        self.assertEqual(lua.execute(gold.read_source(prefix,'equalize_failed',acceptance_ready=True,
                                                     negotiation=True)), 'closable|17|143|none|fixed')
        self.assertEqual(lua.execute(gold.finalize_source(prefix,'accept')), 'sent')
        self.assertEqual(lua.eval('requests[1]'), 7)
        self.assertEqual(lua.eval('requests[2]'), 1)
        self.assertEqual(lua.execute(gold.edit_source(prefix, 0)), 'removed')
        self.assertEqual(lua.eval('#requests'), 2)

    @unittest.skipIf(LuaRuntime is None, 'Lua 5.1 fixture unavailable')
    def test_recurring_gold_draft_changes_only_the_selected_term(self):
        from civ6_host.runtime import xp2_deal_gold as gold

        lua = LuaRuntime()
        lua.execute("""
DealItemTypes={GOLD=0}; DealItemSubTypes={NONE=0}
DealDirection={INCOMING=1}
DealProposalAction={ACCEPTED=1,REJECTED=2,PROPOSED=4,INSPECT=7}
Players={[0]={GetTreasury=function() return {GetGoldBalance=function() return 93.8 end} end},
         [1]={GetTreasury=function() return {GetGoldBalance=function() return 41.2 end} end}}
local terms={}
local nextID=0
inspections=0
working={
 GetItemCount=function() return #terms end,
 FindItemsByType=function(self,kind,subkind,giver)
  local items={}
  for _,term in ipairs(terms) do if term.giver==giver then items[#items+1]=term end end
  return items
 end,
 AddItemOfType=function(self,kind,player)
  local amount,duration,id=0,0,nextID
  nextID=nextID+1
  local item={giver=player, GetID=function() return id end,
   SetAmount=function(self,n) amount=n end, GetAmount=function() return amount end,
   SetDuration=function(self,n) duration=n end, GetDuration=function() return duration end,
   GetMaxAmount=function() return duration==0 and (player==0 and 93 or 41) or 8 end}
  terms[#terms+1]=item; return item
 end,
 RemoveItemByID=function(self,id)
  for i,term in ipairs(terms) do if term:GetID()==id then table.remove(terms,i); return end end
  error('Unknown term')
 end,
 Validate=function() end, IsValid=function() return #terms>0 end,
 HasUnacceptableItems=function() return false end
}
DealManager={
 GetPossibleDealItems=function() return {{Duration=0}, {Duration=1,MaxAmount=9}} end,
 SendWorkingDeal=function(action)
  assert(action==7); inspections=inspections+1; return 1
 end,
 GetWorkingDeal=function(direction) assert(direction==1); return working end,
 CopyIncomingToOutgoingWorkingDeal=function() end,
 AreWorkingDealsEqual=function() return true end
}
""")
        prefix = b'local me,other,deal,queued=0,1,working,false\n'
        self.assertEqual(lua.execute(gold.edit_source(prefix,9,recurring=True,edit_recurring=True)), 'unavailable')
        self.assertEqual(lua.execute(gold.edit_source(prefix,5,recurring=True,edit_recurring=True)), 'inspected')
        self.assertEqual(lua.execute(gold.edit_source(prefix,90,recurring=True)), 'inspected')
        self.assertEqual(lua.execute(gold.copy_source(prefix,90,5)), 'verified')
        with self.assertRaisesRegex(LuaError, 'AI changed the proposed gold amount or duration'):
            lua.execute(gold.copy_source(prefix,90,6))
        self.assertEqual(lua.execute(gold.edit_source(prefix,0,recurring=True,edit_recurring=True)), 'inspected')
        self.assertEqual(lua.execute(gold.copy_source(prefix,90)), 'verified')
        self.assertEqual(lua.eval('inspections'), 3)
        self.assertEqual(lua.execute(gold.edit_source(prefix,8,recurring=True,bilateral=True,edit_requested=True)),
                         'inspected')
        result = lua.execute(gold.read_source(prefix,'accepted',acceptance_ready=True,recurring=True,bilateral=True))
        _, lump, _, requested, _ = gold.parse(result.encode(), 'accepted', recurring=True,bilateral=True)
        self.assertEqual((lump['amount'],requested), (90,dict(amount=8,max_amount=41)))
        self.assertEqual(lua.execute(gold.copy_source(prefix,90,requested=(8,0))), 'verified')
        with self.assertRaisesRegex(LuaError, 'AI changed the proposed gold amount or duration'):
            lua.execute(gold.copy_source(prefix,8,requested=(90,0)))


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
 {Key='CHOICE_DECLARE_FRIENDSHIP',Sort=8,Text='LOC_FRIEND',Tooltip=nil,DiplomaticActionType='DIPLOACTION_DECLARE_FRIENDSHIP',IsDisabled=false},
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
