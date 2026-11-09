"""Real view.read with retained v38 subreader results and native IO replaced.

No runtime overlay or GameCore. Strategic/tactical permissions are synthetic;
all public family contents come from the pinned d515 native response.
"""
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import unittest
from unittest.mock import patch

from lupa.lua51 import LuaRuntime
from civ6_host.contracts import network_turn as contract
from civ6_host.runtime import xp1_session_view as view
from civ6_host.runtime.native.native_episode_identity import DiagnosticEpisodeIdentity
import test_xp2_session_view as fixtures


TRACE = 'work/host-simultaneous/native-runs/run-d515935668c340e99df6fdb613124726/events.jsonl'
TRACE_SHA256 = 'adb8640469d9a0388eed719e4b94d739c91937544214a44fc89d3a8b00e3c7f8'
DENIED_FIELDS = ('production_queues','production_current','world_input','queued_orders',
    'unit_orders','unit_attacks','unit_upgrades','policies','policy_unlock','government',
    'envoys','trade_origins','city_shots','district_shots')
PRESERVED_FIELDS = ('choice_state','city_focus_catalogs','citizen_catalogs','placements',
    'placement_offers','placement_observation_scope','placement_inventory','unit_promotions',
    'unit_work','unit_work_state','unit_work_info','strategic_resources','plot_purchases',
    'city_purchases','governors','diplomacy_overview','trade_routes','espionage',
    'spy_completion','world_congress','world_congress_review','world_congress_review_status',
    'turn_controls','turn_availability')


def retained():
    raw=(Path(os.environ['CIV6_HOST_RESOURCE_ROOT'])/TRACE).read_bytes()
    if hashlib.sha256(raw).hexdigest()!=TRACE_SHA256:
        raise ValueError('Retained Congress response changed')
    for line in raw.splitlines():
        row=json.loads(line)
        if row.get('stage')=='official_session_response':
            if row['decisions']['schema']!='civ6-host.network-capability-decisions.v38':
                raise ValueError('Retained Congress schema changed')
            return row
    raise ValueError('Retained Congress response absent')


class CommandPermissionCompositionTests(unittest.TestCase):
    def setUp(self):
        owner=fixtures.XP2SessionView(methodName='runTest')
        self.addCleanup(owner.doCleanups);owner.setUp()
        self.f=f=owner.fixture;self.saved=s=f.saved
        self.response=retained();self.old=d=self.response['decisions']
        self.observed=o=deepcopy(self.response['observation'])
        f.observation=deepcopy(o)
        s.continuation.observation=deepcopy(o)
        s.continuation.observation['economy']['gold']=-999 # Detect stale observation reuse.
        s.continuation.world_input_prompts={}
        s.continuation.identity=DiagnosticEpisodeIdentity(d['episode_id'],d['game_generation'])
        s._expansion_city_controls_requested=(True,True)
        for flag in ('governors_diagnostic','diplomacy_overview_diagnostic','trade_diagnostic',
                     'espionage_diagnostic','world_congress_diagnostic','world_congress_review_diagnostic'):
            setattr(s,flag,True)
        f.activity=f"{o['turn']}|0|0|0,1,1,0;1,0,0,0".encode()
        f.timer.return_value=d['turn_controls']['timer_elapsed']
        f.turn_gates.return_value=dict(turn_availability=deepcopy(d['turn_availability']))
        f.inventory.side_effect=None
        f.inventory.return_value=deepcopy(d['placement_inventory'])
        self.preserved={};self.denied={};self.permission_calls=0;self.flip_permission=False
        self.lua=LuaRuntime(encoding=None)
        self.lua.execute(f"""
          currentTurn={o['turn']};strategic=false;tactical=true
          Game={{GetLocalPlayer=function()return 0 end,GetLocalObserver=function()return 0 end,
            GetCurrentGameTurn=function()return currentTurn end,
            IsAllowStrategicCommands=function(id)assert(id==0);return strategic end,
            IsAllowTacticalCommands=function(id)assert(id==0);return tactical end}}
        """.encode())
        def evaluate(child,source,label,*,capacity):
            if label==b'@native_command_permissions':
                self.assertIs(child,s.prefix.ui_child);self.assertEqual(capacity,32)
                self.permission_calls+=1
                if self.flip_permission and self.permission_calls==2:
                    self.lua.globals().strategic=True
                return self.lua.execute(source)
            return f.evaluate(child,source,label,capacity=capacity)
        f.runtime.evaluate_text=evaluate
        def candidates(kinds):
            return deepcopy([r for r in d['candidates'] if r['action']['kind'] in kinds])
        f.choices.side_effect=lambda saved,obs:(candidates(('research','civic','production')),
            deepcopy({k:d['families'][k] for k in ('research','civic','production')}),deepcopy(d['choice_state']))
        f.placements.return_value={**deepcopy({k:d[k] for k in
            ('placement_offers','placements','placement_observation_scope')}),
            'actions':[r['action'] for r in candidates(('production_placement','production_resume'))]}
        for name,mock in [('world',f.world),('orders',f.orders),('attacks',f.attacks),
                          ('production_queues',f.production_queues),('attack_admin',f.attack_admin)]:
            mock.side_effect=AssertionError('Strategic reader invoked: '+name)
            self.denied[name]=mock
        blocked=('xp2_policies.read','xp2_policy_unlock.read','xp2_government.read',
            'xp2_unit_upgrades.catalogue','xp2_envoys.catalogue','production_inputs.read_current',
            'native.native_saved_city_shot.catalog','native.native_saved_district_shot.catalog',
            'native.native_saved_city_targets.catalog')
        for name in blocked:
            self.denied[name]=f.stack.enter_context(patch('civ6_host.runtime.'+name,
                side_effect=AssertionError('Strategic reader invoked: '+name)))
        outputs={
            'expansion_city_controls.read':dict(city_focus_catalogs=deepcopy(d['city_focus_catalogs']),
                citizen_catalogs=deepcopy(d['citizen_catalogs']),
                actions=[r['action'] for r in candidates(('city_focus','city_citizen'))]),
            'xp2_strategic_resources.observe':d['strategic_resources'],
            'xp2_promotions.catalogue':d['unit_promotions'],
            'xp2_plot_purchases.catalogue':(d['plot_purchases'],d['city_purchases']),
            'unit_work_info.read_catalog':(d['unit_work'],d['unit_work_info']),
            'unit_work_state.observe':d['unit_work_state'],
            'xp2_governors.catalogue':d['governors'],
            'xp2_diplomacy_overview.catalogue':d['diplomacy_overview'],
            'xp2_espionage.catalogue':d['espionage'],
            'xp2_spy_completion.catalogue':d['spy_completion'],
            'xp2_world_congress.catalogue':d['world_congress'],
        }
        for name,value in outputs.items():
            self.preserved[name]=f.stack.enter_context(patch('civ6_host.runtime.'+name,
                side_effect=lambda *a,_value=value,**kw:deepcopy(_value)))
        def trade(saved,obs,*,include_origins):
            self.assertIs(saved,s);self.assertEqual(obs,o);self.assertIs(include_origins,False)
            return dict(trade_routes=deepcopy(d['trade_routes']),trade_origins=None)
        self.preserved['xp2_trade.catalogue']=f.stack.enter_context(patch(
            'civ6_host.runtime.xp2_trade.catalogue',side_effect=trade))
        def review(saved,obs,*,sequence,congress):
            self.assertEqual(obs,o);self.assertEqual(sequence,d['sequence'])
            if congress is None:
                return dict(world_congress_review=None,world_congress_review_status='waiting_or_closed')
            self.assertEqual(congress,d['world_congress'])
            return deepcopy({k:d[k] for k in ('world_congress_review','world_congress_review_status')})
        self.preserved['xp2_world_congress_review.catalogue']=f.stack.enter_context(patch(
            'civ6_host.runtime.xp2_world_congress_review.catalogue',side_effect=review))
        def effects(saved,obs,*,sequence,congress):
            self.assertIs(saved,s);self.assertEqual(obs,o);self.assertEqual(sequence,d['sequence'])
            if congress is None:
                return dict(world_congress_active_effects=None,world_congress_active_effects_status='waiting_or_closed')
            # Synthetic new result only; all pre-v40 fields above remain retained native data.
            from test_world_congress_active_effects import catalogue as effect_fixture
            value=effect_fixture(o['player_id'],o['turn'],sequence,congress['turn_segment'])
            return dict(world_congress_active_effects=value,world_congress_active_effects_status='available')
        self.preserved['xp2_world_congress_active_effects.catalogue']=f.stack.enter_context(patch(
            'civ6_host.runtime.xp2_world_congress_active_effects.catalogue',side_effect=effects))

    def read(self,**kwargs):
        return view.read(self.saved,0,self.old['sequence'],**kwargs)

    def test_denied_strategic_readers_never_run_but_independent_readers_stay_fresh(self):
        session,observed,value=self.read()
        self.assertEqual(value['schema'],'civ6-host.network-capability-decisions.v40')
        self.assertEqual(session,self.response['session']);self.assertEqual(observed,self.observed)
        self.assertNotEqual(observed,self.saved.continuation.observation)
        self.assertEqual(value['native_command_permissions'],dict(player_id=0,turn=61,sequence=0,
            allow_strategic=False,allow_tactical=True))
        self.assertEqual(self.permission_calls,2)
        self.assertTrue(value['turn_controls']['active']);self.assertTrue(value['turn_controls']['active_complete'])
        for name,mock in self.denied.items():mock.assert_not_called()
        self.assertNotIn(b'@native_found_city_catalog',self.f.labels())
        for name,mock in self.preserved.items():
            with self.subTest(reader=name):mock.assert_called_once()
        self.f.choices.assert_called_once_with(self.saved,observed)
        self.f.placements.assert_called_once_with(self.saved,observed)
        self.f.inventory.assert_called_once()
        for field in DENIED_FIELDS:self.assertIsNone(value[field],field)
        for field in PRESERVED_FIELDS:self.assertEqual(value[field],self.old[field],field)
        for family in contract.STRATEGIC_READER_FAMILIES & value['families'].keys():
            self.assertEqual(value['families'][family],dict(status='unqualified',
                reason=contract.NATIVE_STRATEGIC_READER_UNAVAILABLE))
        actual={r['candidate_id'] for r in value['candidates']}
        expected={r['candidate_id'] for r in self.old['candidates']
            if r['action']['kind'] not in contract.STRATEGIC_READER_FAMILIES}
        self.assertEqual(actual,expected)
        contract.validate_capability_catalogue(value,self.saved.continuation.identity,0,61,
            player_id=0,observation=observed)

    def test_permission_change_during_collection_refuses_result(self):
        self.flip_permission=True
        with self.assertRaisesRegex(ValueError,'permissions changed'):
            self.read()
        self.assertEqual(self.permission_calls,2)

    def test_closed_view_keeps_v38_without_reading_or_fabricating_permission(self):
        _,observed,value=self.read(actions_closed=True)
        self.assertEqual(value['schema'],'civ6-host.network-capability-decisions.v38')
        self.assertNotIn('native_command_permissions',value)
        self.assertEqual(self.permission_calls,0)
        self.assertEqual(observed,self.observed)
        self.assertEqual(value['world_congress_review_status'],'waiting_or_closed')
        self.preserved['xp2_world_congress.catalogue'].assert_not_called()
        self.preserved['xp2_world_congress_active_effects.catalogue'].assert_not_called()
        self.f.choices.assert_not_called()
        for mock in self.denied.values():mock.assert_not_called()
        contract.validate_capability_catalogue(value,self.saved.continuation.identity,0,61,
            player_id=0,observation=observed,actions_closed=True)


if __name__=='__main__':unittest.main()
