"""Real scoped Lua reader/provider pipeline with native memory and calls mocked."""
from copy import deepcopy
import hashlib
import json
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch

from lupa.lua51 import LuaRuntime,LuaError
from civ6_host.runtime.native import native_world_congress_active_effects as native
from civ6_host.runtime.native import native_world_congress_review as shared
from civ6_host.runtime import xp2_congress_review_configuration as environment
from civ6_host.runtime.execution_images import known_path,select
from civ6_host.runtime.native.native_game_configuration import game_configuration_hash
import test_congress_private_targets as setup
import test_xp2_world_configuration as provider


def admission():
    return dict(public=dict(player_id=0,turn=61,sequence=19,turn_segment=123,
        stage='ordinary',paused=False,local_alive=True),
        private=dict(popup=dict(capability=True,current_era=4,initial_era=3)))


class ActiveEffectsReaderTests(unittest.TestCase):
    def lua(self):
        lua=LuaRuntime(encoding=None,max_memory=12*1024*1024);lua.execute(setup.REVIEW_SETUP.encode())
        lua.execute(b'''state.activeReads=0;state.meetingReads=0;state.proposalReads=0;state.emergencyReads=0;state.meetingTurns=5
          state.proposals={Stage=-1}
          GameInfo.Resolutions[7]=GameInfo.Resolutions.RES_ONE
          state.effects={Stage=4,[1]={Type=7,TargetType='PlayerType',ChosenThing='1',
            ChosenOption='Effect text',ChosenLabel='Localized label',IsNew=true}}
          Game.GetWorldCongress=function()return {
            GetResolutions=function(_,id)assert(id==state.pid);state.activeReads=state.activeReads+1;return state.effects end,
            GetMeetingStatus=function()state.meetingReads=state.meetingReads+1;return {TurnsLeft=state.meetingTurns}end,
            GetReview=function()error('Active effects must not read Review')end,
            GetProposals=function(_,id)assert(id==state.pid);state.proposalReads=state.proposalReads+1;return state.proposals end}end
          Game.GetEmergencyManager=function()state.emergencyReads=state.emergencyReads+1
           return {GetSingleEmergency=function(_,target,kind)
            assert(target==state.emergencyTarget and kind==state.emergencyKind,'Exact native emergency arguments differ')
            return state.emergency end}end''')
        return lua

    def parsed(self,lua):
        return native.parse(lua.execute(native.source(0,61,19)),0,61,19)

    def proposals(self,lua,target=2):
        lua.execute(b'''GameInfo.Emergencies_XP2={[4]={EmergencyType='EMERGENCY_FIXTURE',Hostile=true}}
          state.emergencyTarget=2;state.emergencyKind=44
          state.proposals={Stage=-1,Proposals={[7]={ProposalsOfType={[1]={Target=2,EmergencyType=44,
            TypeName='WC_EMERGENCY_FIXTURE',Name='Public title',Description='OVERWRITTEN',IsNew=-1,
            Sender=57,PerPlayerVotes={[0]=98765}}}}}}
          state.emergency={TargetID=2,EmergencyType=4,TurnsLeft=5,bSuccess=false,HasBegun=true,
            ShortDescriptionText='Final emergency description',ExtraBuffs='',ExtraRewards='',
            GoalsTable={[0]={Name='HIDDEN_ZERO_GOAL',Completed=false},[1]={Name='Visible goal',Completed=true}},
            TargetGoalsTable={[1]={Name='Own target goal',Completed=false}},ScoreSourcesTable={},
            BuffsText={[0]='HIDDEN_ZERO_BUFF',[1]='Visible buff'},MemberRewardsTextFirst={},
            MemberRewardsTextTop={},MemberRewardsTextBottom={},MemberRewardsTextExtra={},TargetRewardsText={}}''')
        lua.globals().state.emergencyTarget=target;lua.globals().state.emergency.TargetID=target
        lua.globals().state.proposals.Proposals[7].ProposalsOfType[1].Target=target

    def test_exact_native_fields_signed_duration_and_no_inferred_ballots(self):
        lua=self.lua()
        for turns in (-0x80000000,-1,0,0x7fffffff):
            lua.globals().state.meetingTurns=turns
            value=self.parsed(lua);row=value['resolutions'][0]
            self.assertEqual((value['meeting_turns_left'],row['turns_left']),(turns,turns+1))
            self.assertEqual(row['resolution_type'],'RES_ONE');self.assertTrue(row['is_new'])
            self.assertEqual(row['chosen_label'],'Localized label');self.assertNotIn('votes',row)
            self.assertEqual(value['proposals'],[]);self.assertEqual(value['proposals_status'],'available')
        lua.execute(b'state.effects[1].IsNew=0')
        with self.assertRaises(LuaError):self.parsed(lua)
        lua.execute(b'state.effects={Stage=4}')
        self.assertEqual(self.parsed(lua)['resolutions'],[])

    def test_negative_unknown_and_nonplayer_targets_preserve_public_boundary(self):
        lua=self.lua()
        for target,label in ((-1,''),(-2,'LOC_WORLD_CONGRESS_SELECT_TARGET'),
                             (2,'LOC_DIPLOPANEL_UNMET_PLAYER')):
            lua.execute(("state.effects[1].ChosenThing='%d'"%target).encode())
            row=self.parsed(lua)['resolutions'][0]['chosen_target']
            self.assertEqual(row,dict(player_id=None,value=None,label=label))
            scope=shared.parse_scope(lua.execute(native.scope_source(0,61,19)))
            self.assertEqual(scope['players'],[] if target<0 else [2])
            self.assertEqual(scope['leader_ids'],[])
        lua.execute(b"state.effects[1].TargetType='ResourceType';state.effects[1].ChosenThing=''")
        self.assertEqual(self.parsed(lua)['resolutions'][0]['chosen_target'],dict(player_id=None,value='',label=''))
        lua.execute(b"state.effects[1].TargetType='PlayerType';state.effects[1].ChosenThing='2';state.multiplayer=true")
        self.assertEqual(self.parsed(lua)['resolutions'][0]['chosen_target']['label'],
                         'LOC_DIPLOPANEL_UNMET_PLAYER (User2)')

    def test_gates_precede_both_getters_and_scope_or_phase_change_refuses(self):
        for phase in (11,12,13):
            lua=self.lua();lua.globals().state.segment=phase
            with self.assertRaisesRegex(LuaError,'unavailable during session'):
                lua.execute(native.scope_source(0,61,19))
            self.assertEqual((lua.globals().state.activeReads,lua.globals().state.meetingReads,
                              lua.globals().state.proposalReads,lua.globals().state.emergencyReads),(0,0,0,0))
        for change in (lambda a:a['public'].update(stage='regular'),lambda a:a['public'].update(paused=True),
                       lambda a:a['public'].update(local_alive=False),lambda a:a['private']['popup'].update(capability=False),
                       lambda a:a['private']['popup'].update(current_era=2)):
            a=admission();change(a)
            self.assertIsNone(shared.query(None,0,61,19,backend=None,environment=None,admission=a,projection=native))
        lua=self.lua();scope=shared.parse_scope(lua.execute(native.scope_source(0,61,19)))
        lua.execute(b"state.effects[1].ChosenThing='2'")
        with self.assertRaisesRegex(LuaError,'scope changed'):
            lua.execute(native.source(0,61,19,expected_scope=scope))
        with self.assertRaises(ValueError):shared.query(None,0,61,19,backend=None,environment=None,admission=admission(),projection=object())
        with self.assertRaises(ValueError):shared.query(None,0,61,19,backend=None,environment=None,admission=admission(),projection=native,administrative=True)

    def test_shared_pipeline_uses_real_configuration_conversions_and_scoped_bindings(self):
        f=provider.Fixture(multiplayer=True)
        profile='xp2-gamecore-current-092abfbb'
        f.backend.core._civ6_host_execution_image=select(profile,core_path=known_path(profile))
        f.set_text(f.player,'LEADER_NAME','')
        lua=self.lua();lua.execute(b'PlayerConfigurations=nil;GameConfiguration=nil')
        labels=[]
        def evaluate(child,chunk,name,capacity):
            self.assertEqual(child,'owned-child');labels.append(name);return lua.execute(chunk)
        prefix=NS(ui_child='owned-child',runtime=NS(evaluate_text=evaluate));before=f.memory.copy()
        with patch('civ6_host.runtime.xp2_congress_configuration.attach_namespaces') as attach:
            value=shared.query(prefix,0,61,19,backend=f.backend,environment=environment,
                               admission=admission(),projection=native)
            attach.assert_called_once_with(prefix,f.backend)
        self.assertEqual(value['resolutions'][0]['chosen_target'],dict(player_id=1,value='1',label='Rome (Joueur humain)'))
        self.assertEqual(len(labels),2);self.assertTrue(all(b'active_effects' in name for name in labels))
        self.assertEqual(f.memory,before);self.assertIn((f.player,game_configuration_hash('LEADER_NAME')),f.calls)
        self.assertIsNone(lua.globals().PlayerConfigurations);self.assertIsNone(lua.globals().GameConfiguration)

    def test_proposals_join_exact_native_arguments_scope_and_only_rendered_details(self):
        lua=self.lua();self.proposals(lua)
        scope=shared.parse_scope(lua.execute(native.scope_source(0,61,19)))
        self.assertEqual(scope,dict(segment=123,players=[1,2],leader_ids=[1,2]))
        self.assertEqual(lua.globals().state.emergencyReads,0)
        value=native.parse(lua.execute(native.source(0,61,19,expected_scope=scope)),0,61,19)
        card=value['proposals'][0]
        self.assertEqual(card['name'],'Public title[Leader2]')
        self.assertEqual(card['target'],dict(player_id=None,label='LOC_DIPLOPANEL_UNMET_PLAYER'))
        self.assertEqual(card['description'],'Final emergency description');self.assertTrue(card['is_new'])
        self.assertEqual(card['goals'],[dict(name='Visible goal',completed=True)])
        self.assertNotIn('HIDDEN_ZERO',json.dumps(value));self.assertNotIn('OVERWRITTEN',json.dumps(value))
        self.assertNotIn('Sender',card);self.assertNotIn('PerPlayerVotes',card)
        self.assertEqual(lua.globals().state.emergencyReads,1)
        self.proposals(lua,-1);value=self.parsed(lua)
        self.assertEqual(value['proposals'][0]['name'],'Public title');self.assertIsNone(value['proposals'][0]['target'])

    def test_proposal_missing_native_method_result_and_changed_phase_refuse(self):
        for change,message in ((b'state.emergency=nil','no matching emergency'),
                               (b'state.emergency.TargetID=3','target mismatch'),
                               (b'Game.GetEmergencyManager=nil','namespace absent'),
                               (b'Game.GetEmergencyManager=function()return nil end','manager absent'),
                               (b'Game.GetEmergencyManager=function()return {}end','method absent'),
                               (b'''Game.GetEmergencyManager=function()return {GetSingleEmergency=function()
                                 state.segment=456;return state.emergency end}end''','perspective changed')):
            lua=self.lua();self.proposals(lua);lua.execute(change)
            with self.assertRaisesRegex(LuaError,message):self.parsed(lua)
        lua=self.lua();scope=shared.parse_scope(lua.execute(native.scope_source(0,61,19)))
        self.proposals(lua)
        with self.assertRaisesRegex(LuaError,'scope changed'):
            lua.execute(native.source(0,61,19,expected_scope=scope))
        self.assertEqual(lua.globals().state.emergencyReads,0)

    def test_proposal_title_uses_actual_provider_scope_without_exposing_unmet_id(self):
        f=provider.Fixture(multiplayer=True);profile='xp2-gamecore-current-092abfbb'
        f.backend.core._civ6_host_execution_image=select(profile,core_path=known_path(profile))
        f.set_text(f.player,'LEADER_NAME','')
        lua=self.lua();self.proposals(lua,1)
        lua.execute(b'state.met[1]=false;PlayerConfigurations=nil;GameConfiguration=nil')
        prefix=NS(ui_child='owned-child',runtime=NS(evaluate_text=lambda child,chunk,name,capacity:lua.execute(chunk)))
        with patch('civ6_host.runtime.xp2_congress_configuration.attach_namespaces'):
            result=shared.query(prefix,0,61,19,backend=f.backend,environment=environment,
                                admission=admission(),projection=native)
        card=result['proposals'][0]
        self.assertEqual(card['name'],'Public title[Rome]')
        self.assertEqual(card['target'],dict(player_id=None,label='LOC_DIPLOPANEL_UNMET_PLAYER (Joueur humain)'))
        self.assertEqual(result['resolutions'][0]['chosen_target']['player_id'],None)
        self.assertIn((f.player,game_configuration_hash('LEADER_NAME')),f.calls)

    def test_shared_query_keeps_default_review_and_private_sidecar_behavior(self):
        f=provider.Fixture(multiplayer=True);profile='xp2-gamecore-current-092abfbb'
        f.backend.core._civ6_host_execution_image=select(profile,core_path=known_path(profile))
        f.set_text(f.player,'LEADER_NAME','')
        lua=LuaRuntime(encoding=None,max_memory=12*1024*1024);lua.execute(setup.REVIEW_SETUP.encode())
        lua.execute(b'''local r=fixtureResolution();r.PlayerSelections={};state.review.Resolutions[0]=r
          PlayerConfigurations=nil;GameConfiguration=nil''')
        labels=[]
        def evaluate(child,chunk,name,capacity):labels.append(name);return lua.execute(chunk)
        prefix=NS(ui_child='owned-child',runtime=NS(evaluate_text=evaluate))
        with patch('civ6_host.runtime.xp2_congress_configuration.attach_namespaces'):
            result=shared.query(prefix,0,61,19,backend=f.backend,environment=environment,
                                admission=admission(),administrative=True)
        self.assertEqual(result['public']['schema'],shared.SCHEMA)
        self.assertEqual(result['public']['resolutions'][0]['chosen_target']['label'],'Rome (Joueur humain)')
        self.assertEqual(result['private']['resolutions'],[])
        self.assertEqual(lua.globals().state.reads,2)
        self.assertTrue(all(b'active_effects' not in name for name in labels))


if __name__=='__main__':unittest.main()
