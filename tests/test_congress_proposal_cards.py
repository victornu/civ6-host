"""Lua5.1 projection compared to installed, hash-pinned UI formatter functions."""
import hashlib
import itertools
import json
from pathlib import Path
import re
import unittest

from lupa.lua51 import LuaError, LuaRuntime
from civ6_host.runtime.native import native_world_congress_review as shared
from civ6_host.runtime.configuration_profiles import _source
from civ6_host.runtime.native import native_congress_proposal_cards as cards

SETUP = r'''
localPID=0;reads={};presentations={};fixtureNull=json_null
Locale={Lookup=function(key,...)
 local args={...};local s=assert(key)
 for _,v in ipairs(args)do s=s..'<'..tostring(v)..'>'end
 return s
end,ToUpper=function(s)return string.upper(s)end}
Game={GetLocalPlayer=function()return localPID end}
GetVisiblePlayerName=function(id)return 'UNRENDERED_TARGET_'..id end
GameInfo={ProposalTypes={
 [8]={ProposalType='PROPOSAL_LATE',Name='Later category',Sort=9},
 [7]={ProposalType='PROPOSAL_EARLY',Name='Earlier category',Sort=2}},
 Emergencies_XP2={[4]={EmergencyType='EMERGENCY_FIXTURE',Hostile=true}}}
function fixtureEmergency()
 return {TargetID=2,EmergencyType=4,TurnsLeft=5,bSuccess=false,HasBegun=true,
 ShortDescriptionText='Native final description',ExtraBuffs='Extra temporary effect',ExtraRewards='Extra reward',
 GoalsTable={[0]={Name='HIDDEN_ZERO_GOAL',Completed=true},[1]={Name='Visible goal',Completed=true},[2]={Name='',Completed=false}},
 TargetGoalsTable={[0]={Name='HIDDEN_ZERO_TARGET',Completed=true},[1]={Name='Own target goal',Completed=false}},
 ScoreSourcesTable={[0]='HIDDEN_ZERO_SCORE',[1]='Visible score source'},
 BuffsText={[0]='HIDDEN_ZERO_BUFF',[1]='Visible temporary effect'},
 MemberRewardsTextFirst={[0]='HIDDEN_ZERO_REWARD',[1]='First reward'},
 MemberRewardsTextTop={[1]='Top reward'},MemberRewardsTextBottom={[1]='Bottom reward'},
 MemberRewardsTextExtra={[1]='Extra tier reward'},TargetRewardsText={[1]='Target reward'},
 CompletedText='UNRENDERED_COMPLETED',GoalDescription='UNRENDERED_GOAL_DESCRIPTION',
 TargetCityName='UNRENDERED_CITY',ScoresTables={[2]=987654},NameText='UNRENDERED_NAME',
 MemberTiers={[2]=123456}}
end
emergency=fixtureEmergency()
native={Stage=-1,Proposals={[8]={ProposalsOfType={[1]={Target=2,EmergencyType=44,
 TypeName='WC_EMERGENCY_FIXTURE',Name='Proposal title',Description='OVERWRITTEN_DESCRIPTION',IsNew=-2147483648,
 Sender=57,PerPlayerVotes={[0]=98765}}}}}}
function readEmergency(target,kind)
 reads[#reads+1]={target=target,kind=kind};return emergency
end
function presentTarget(target,name)
 presentations[#presentations+1]=target
 return Locale.Lookup(name,'Title-visible leader'),{player_id=json_null,label='Unmet'}
end
'''


class ProposalCardTests(unittest.TestCase):
    def lua(self):
        lua = LuaRuntime(encoding=None, max_memory=16*1024*1024)
        lua.execute((shared._SHARED+SETUP+cards.LUA+r'''
function projectJson()return encode(projectProposalCards(native,localPID,readEmergency,presentTarget))end
function detailsJson()return encode(pcDetails(emergency,localPID))end
function scopeJson()return encode(proposalCardScope(native))end
''').encode())
        return lua

    def official(self, lua):
        proof = _source(cards.SOURCE)
        row = proof['files']['crisis_support']
        raw = Path(row['path']).read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(), row['sha256'])
        source = raw.decode('utf-8-sig')
        names = ('ProcessEmergency','PopulateEmergencyGoals','PopulateHowToScore',
                 'PopulateBuffsAndExtraBuffs','PopulateRewards','ProcessEmergency_WorldCongressPopup')
        for name in names:
            start = source.index('function '+name+'(')
            end = source.find('\nfunction ', start+1)
            block = source[start:end if end>=0 else None]
            block = re.sub(r':\s*(?:number|boolean|table|object|string)\b', '', block)
            lua.execute(block.encode())
        lua.execute(b'''function officialDetails()
 local value=ProcessEmergency_WorldCongressPopup(emergency)
 local crisis,rewards={},{}
 for _,line in ipairs(value.crisisDetails)do crisis[#crisis+1]=line.string end
 for _,line in ipairs(value.rewardsDetails)do rewards[#rewards+1]=line.string end
 return crisis,rewards
end''')

    @staticmethod
    def strings(value):
        return [value[i].decode() for i in range(1,len(value)+1)]

    def test_formatter_matches_official_branches_and_does_not_read_ambiguous_icon(self):
        lua=self.lua();self.official(lua)
        for hostile,success,begun,turns,own in itertools.product((False,True),(False,True),(False,True),(-1,0,5),(False,True)):
            state=lua.globals();state.GameInfo.Emergencies_XP2[4].Hostile=hostile
            e=state.emergency;e.bSuccess=success;e.HasBegun=begun;e.TurnsLeft=turns;e.TargetID=0 if own else 2
            for icon_context in (False,True):
                state.bPlayerisTarget=icon_context
                expected=self.strings(state.officialDetails()[0]),self.strings(state.officialDetails()[1])
                value=json.loads(state.detailsJson())
                self.assertEqual((value['crisis_details'],value['rewards_details']),expected)
                self.assertEqual(value['goals'],[dict(name='Own target goal' if own else 'Visible goal',completed=not own)])
                self.assertNotIn('icon',json.dumps(value));self.assertNotIn('UNRENDERED',json.dumps(value))

    def test_native_zero_keys_holes_and_empty_tables_follow_official_iterators(self):
        lua=self.lua();self.official(lua)
        variations=(
            "emergency.GoalsTable={};emergency.TargetGoalsTable={[1]={Name='not displayed',Completed=true}}",
            "emergency.BuffsText={[0]='zero only'};emergency.ScoreSourcesTable={[0]='zero only'}",
            "emergency.MemberRewardsTextFirst={[0]='zero',[1]='one',[3]='after gap'}",
            "emergency.GoalsTable={[0]={Name='zero',Completed=true},[2]={Name='after gap',Completed=false}}",
            "for _,k in ipairs({'GoalsTable','ScoreSourcesTable','BuffsText','MemberRewardsTextFirst','MemberRewardsTextTop','MemberRewardsTextBottom','MemberRewardsTextExtra','TargetRewardsText'})do emergency[k]={}end;emergency.ExtraBuffs='';emergency.ExtraRewards=''",
        )
        for change in variations:
            lua.execute(('emergency=fixtureEmergency();'+change).encode())
            expected=lua.globals().officialDetails();value=json.loads(lua.globals().detailsJson())
            self.assertEqual(value['crisis_details'],self.strings(expected[0]))
            self.assertEqual(value['rewards_details'],self.strings(expected[1]))
            encoded=json.dumps(value)
            self.assertNotIn('after gap',encoded);self.assertNotIn('zero only',encoded)

    def test_cards_keep_final_description_private_scope_and_exact_getter_arguments(self):
        lua=self.lua();value=json.loads(lua.globals().projectJson());row=value[0]
        self.assertEqual(row['description'],'Native final description')
        self.assertEqual(row['name'],'Proposal title<Title-visible leader>')
        self.assertEqual(row['target'],dict(player_id=None,label='Unmet'))
        self.assertEqual(row['emergency_type'],'EMERGENCY_FIXTURE')
        self.assertEqual(row['category_type'],'PROPOSAL_LATE');self.assertTrue(row['is_new'])
        self.assertEqual((lua.globals().reads[1].target,lua.globals().reads[1].kind),(2,44))
        self.assertEqual(json.loads(lua.globals().scopeJson()),dict(players=[2],leader_ids=[2]))
        self.assertFalse(set(row)&{'Sender','PerPlayerVotes','TargetID','EmergencyType','cost','votes','direction'})
        self.assertNotIn('OVERWRITTEN_DESCRIPTION',json.dumps(value));self.assertNotIn('98765',json.dumps(value))
        lua.execute(b"native.Proposals[7]={ProposalsOfType={[1]=native.Proposals[8].ProposalsOfType[1]}}")
        value=json.loads(lua.globals().projectJson())
        self.assertEqual([r['category_type'] for r in value],['PROPOSAL_EARLY','PROPOSAL_LATE'])
        lua.execute(b'native={Stage=-1}')
        self.assertEqual(json.loads(lua.globals().projectJson()),[])

    def test_absence_cross_target_and_malformed_fields_refuse_without_fallback(self):
        for change,message in (("emergency=nil",'GetSingleEmergency returned no matching'),
                               ("emergency.TargetID=3",'target mismatch'),
                               ("emergency.TurnsLeft=2147483648",'emergency turns'),
                               ("emergency.GoalsTable[1].Completed=1",'goal completion'),
                               ("emergency.bSuccess=1",'success'),
                               ("native.Proposals[8].ProposalsOfType[1].IsNew=nil",'new flag')):
            lua=self.lua();lua.execute(change.encode())
            with self.subTest(change=change),self.assertRaisesRegex(LuaError,message):lua.globals().projectJson()
        lua=self.lua()
        lua.execute(b"presentTarget=function()return 'name',{player_id=9,label='wrong'}end")
        with self.assertRaisesRegex(LuaError,'visible target mismatch'):lua.globals().projectJson()

    def test_final_card_details_match_the_official_popup_consumer(self):
        lua=self.lua();self.official(lua)
        row=_source(cards.SOURCE)['files']['popup'];raw=Path(row['path']).read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(),row['sha256'])
        source=raw.decode('utf-8-sig');start=source.index('function PopulateEmergencyData(')
        end=source.index('\nfunction ',start+1)
        lua.execute(re.sub(r':\s*(?:number|boolean|table|object|string)\b','',source[start:end]).encode())
        lua.execute(b'''m_IsInSession=false
          Game.GetEmergencyManager=function()return {GetSingleEmergency=function(_,target,kind)return readEmergency(target,kind)end}end
          g_kCrisisManagers={};g_kRewardsManagers={};officialCard={}
          PopulateWorldCrisisText=function(_,lines,which)
            local out={};for _,line in ipairs(lines)do out[#out+1]=line.string end
            officialCard[which]=out
          end
          local instance={Description={SetText=function(_,v)officialCard.description=v end},
            TurnsLeft={SetText=function(_,v)officialCard.turns=v end,SetToolTipString=function()end},
            Emergency={CrisisDetailsStack='crisis',RewardsDetailsStack='rewards'}}
          PopulateEmergencyData(instance,2,44)''')
        value=json.loads(lua.globals().projectJson())[0];official=lua.globals().officialCard
        self.assertEqual(value['description'],official.description.decode())
        self.assertEqual('[ICON_TURN]'+str(value['turns_left']),official.turns.decode())
        self.assertEqual(value['crisis_details'],self.strings(official.crisis))
        self.assertEqual(value['rewards_details'],self.strings(official.rewards))

    def test_native_signed_duration_and_explicit_blank_target_are_preserved(self):
        lua=self.lua()
        for turns in (-2147483648,-1,0,2147483647):
            lua.globals().emergency.TurnsLeft=turns
            self.assertEqual(json.loads(lua.globals().projectJson())[0]['turns_left'],turns)
        lua.execute(b'''native.Proposals[8].ProposalsOfType[1].Target=-1;emergency.TargetID=-1
          presentTarget=function(target,name)assert(target==-1);return Locale.Lookup(name),fixtureNull end''')
        self.assertEqual(json.loads(lua.globals().scopeJson()),dict(players=[],leader_ids=[]))
        self.assertIsNone(json.loads(lua.globals().projectJson())[0]['target'])

    def test_source_authority_and_helper_are_only_static_data_projection(self):
        dependencies=cards.source_dependencies()
        self.assertIn(cards.SOURCE[1],dependencies.values())
        for forbidden in ('RequestPlayerOperation','GetReview(','RequestAction','ContextPtr','bPlayerisTarget','PlayerConfigurations['):
            self.assertNotIn(forbidden,cards.LUA)


if __name__=='__main__':unittest.main()
