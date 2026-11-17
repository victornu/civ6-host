"""Offline composed XP1 production projections; no native execution."""
from copy import deepcopy
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from civ6_host import InformationUnavailable, ProtocolError, SessionClient
from civ6_host.contracts import network_turn, production_info988, production_inputs
from civ6_host.runtime import xp1_production_info, xp1_session_view, xp2_dedications
from civ6_host.runtime import production_inputs as production_reader
from civ6_host.runtime.native import native_saved_production_info988 as quotes_reader
from civ6_host.runtime.configuration_profiles import XP1_CORE_SHA256, XP2_CORE_SHA256
from test_session_capabilities import CapabilityBackend, seal
from test_xp1_dedications import expansion_catalogue


def fixture(faith=False):
    obs, prior = expansion_catalogue()
    pid, turn = obs['player_id'], obs['turn']
    dedication = xp2_dedications.parse_state(f'{pid}|{turn}|0|normal|0'.encode(),pid,turn)
    with patch.object(xp2_dedications,'catalogue',return_value=dedication):
        xp1_session_view._add_dedications(None,obs,prior,actions_closed=False,
            previous_schema=network_turn.CAPABILITY_XP1_UNIT_LEVIES_SCHEMA,
            target_schema=network_turn.CAPABILITY_XP1_DEDICATIONS_SCHEMA)
    if faith:
        from civ6_host.runtime import xp1_plot_purchases, xp1_city_purchases
        action = dict(kind='purchase',city_id=obs['cities'][0]['id'],category='unit',index=55,
                      hash=99,item_type='UNIT_MISSIONARY',currency='YIELD_FAITH',price_token='75')
        offers = [dict(player_id=pid,turn=turn,city_id=action['city_id'],offers=[
            dict(action=action,command_legal=True,can_afford=True)])]
        plots = [dict(player_id=pid,turn=turn,city_id=action['city_id'],offers=[])]
        with (patch.object(xp1_plot_purchases,'catalogue',return_value=plots),
              patch.object(xp1_city_purchases,'catalogue',return_value=offers)):
            xp1_session_view._add_xp1_plot_purchases(
                SimpleNamespace(xp1_city_purchase=True,xp1_faith_purchase=True),obs,prior,
                acting=True,actions_closed=False)
    seal(prior)
    current = dict(schema=production_inputs.CURRENT_SCHEMA,player_id=pid,turn=turn,cities=[])
    for queue in prior['production_queues']:
        head=queue['entries'][0]
        current['cities'].append(dict(city_id=queue['city_id'],state='current',item=dict(
            category=head['category'],index=head['index'],hash=head['hash'],item_type='UNIT_SETTLER',
            name='Settler',formation='single',progress=7,cost=30,turns_left=3,never_completes=False)))
    rows=[]
    for row in quotes_reader.specifications([r['action'] for r in prior['candidates']]):
        unit=row['category']=='unit'
        rows.append(dict(row,raw=dict(cost=30,progress=7,turns_left=3,formation_type=None,
            base_cost=50 if unit else None,base_cost_visible=unit),public=dict(
            cost=50 if unit else 30,progress=None if unit else 7,turns_left=3,
            never_completes=False,cost_kind='base' if unit else 'production')))
    raw=dict(schema=production_info988.SCHEMA,player_id=pid,turn=turn,
        source_sha256=production_info988.PROOF_SHA256,ui_sha256=production_info988.PANEL_SHA256,
        tooltip_sha256=production_info988.TOOLTIP_SHA256,rows=rows)
    return obs,prior,current,raw


def upgraded(obs,prior,current,raw):
    result=deepcopy(prior)
    saved=SimpleNamespace(emit=Mock())
    with (patch.object(xp1_production_info,'_bind'),
          patch.object(production_reader,'read_current',return_value=current),
          patch.object(quotes_reader,'observe',return_value=raw)):
        saved.prefix=object()
        xp1_production_info.attach(saved,obs,result)
    return seal(result),saved


class ProductionBackend(CapabilityBackend):
    def _reply(self,operation,sequence,player,requested=None):
        reply=super()._reply(operation,sequence,player,requested)
        if operation=='close':return reply
        obs,prior,current,raw=fixture(faith=True)
        prior.update(episode_id=reply['episode_id'],game_generation=reply['game_generation'],sequence=sequence)
        reply['observation']=obs
        reply['decisions'],_=upgraded(obs,prior,current,raw)
        return reply


class XP1ProductionInformationTests(unittest.TestCase):
    def validate(self,obs,value):
        seal(value)
        identity=SimpleNamespace(episode_id=value['episode_id'],game_generation=value['game_generation'])
        return network_turn.validate_capability_catalogue(value,identity,value['sequence'],obs['turn'],
                                                         player_id=obs['player_id'],observation=obs)

    def test_additive_checkpoint_keeps_faith_candidates_and_raw_lane_private(self):
        obs,prior,current,raw=fixture(faith=True)
        value,saved=upgraded(obs,prior,current,raw)
        before=deepcopy(value)
        self.validate(obs,value)
        self.assertEqual(value['candidates'],prior['candidates'])
        self.assertTrue(any(r['action'].get('currency')=='YIELD_FAITH' for r in value['candidates']))
        self.assertTrue(all('raw' not in row for row in value['production_info']['rows']))
        event=saved.emit.call_args.kwargs
        self.assertFalse(event['actor_channel'])
        self.assertEqual(event['production_info'],raw)
        projected,receipt=network_turn.checkpoint_catalogue(value,prior,obs,core_sha256=XP1_CORE_SHA256)
        self.assertEqual(projected,prior)
        self.assertEqual(value,before)
        self.assertEqual(receipt['added_public_fields'],['production_current','production_info'])
        self.assertEqual(network_turn.checkpoint_catalogue(value,value,obs,core_sha256=XP1_CORE_SHA256),(value,None))
        with self.assertRaisesRegex(ValueError,'Rise and Fall'):
            network_turn.checkpoint_catalogue(value,prior,obs,core_sha256=XP2_CORE_SHA256)
        changed=deepcopy(value)
        changed['choice_state']['research']['research']=123
        seal(changed)
        projected,_=network_turn.checkpoint_catalogue(changed,prior,obs,core_sha256=XP1_CORE_SHA256)
        self.assertNotEqual(projected,prior)

    def test_exact_actor_queue_and_candidate_joins_reject_foreign_or_raw_values(self):
        obs,prior,current,raw=fixture()
        value,_=upgraded(obs,prior,current,raw)
        for alter in ('actor','turn','city','queue','raw','missing_quote','unavailable'):
            bad=deepcopy(value)
            if alter=='actor':bad['production_info']['player_id']=1
            elif alter=='turn':bad['production_current']['turn']+=1
            elif alter=='city':bad['production_current']['cities'][0]['city_id']+=1
            elif alter=='queue':bad['production_current']['cities'][0]['item']['hash']+=1
            elif alter=='raw':bad['production_info']['rows'][0]['raw']=raw['rows'][0]['raw']
            elif alter=='unavailable':bad['production_info']=None
            else:bad['production_info']['rows'].pop()
            with self.subTest(alter=alter),self.assertRaises(ValueError):self.validate(obs,bad)

    def test_session_client_public_query_is_detached_and_revision_exact(self):
        backend=ProductionBackend();client=SessionClient(backend,allow_administrative=True)
        view=client.reset();info=client.information('production')
        self.assertEqual(info['data']['schema'],'civ6-host.production-inputs.v3')
        self.assertEqual(info['sequence'],view['sequence'])
        self.assertEqual(info['native_decision_id'],view['decisions']['decision_id'])
        self.assertEqual(info['data']['current']['cities'][0]['item']['progress'],7)
        self.assertEqual(backend.calls,[])
        info['data']['quotes']['rows'].clear()
        self.assertTrue(client.information('production')['data']['quotes']['rows'])
        with self.assertRaises(InformationUnavailable):client.information('production',channel='administrative')
        client._views[0]['decisions']['production_info']['turn']+=1
        with self.assertRaises(ProtocolError):client.information('production')

    def test_unavailable_queue_performs_no_reader_and_keeps_explicit_none(self):
        obs,prior,_,_=fixture()
        prior['production_queues']=None
        saved=SimpleNamespace(emit=Mock())
        with (patch.object(xp1_production_info,'_bind'),
              patch.object(production_reader,'read_current') as current,
              patch.object(quotes_reader,'observe') as quotes):
            xp1_production_info.attach(saved,obs,prior)
        current.assert_not_called();quotes.assert_not_called();saved.emit.assert_not_called()
        self.assertIsNone(prior['production_current']);self.assertIsNone(prior['production_info'])
        from civ6_host.client import _public_contracts
        _public_contracts(prior,obs,False)
        prior['schema']=network_turn.CAPABILITY_XP1_DEDICATIONS_SCHEMA
        with self.assertRaises(ValueError):_public_contracts(prior,obs,False)

    def test_owner_identity_is_checked_before_any_getter(self):
        from civ6_host.runtime.execution_images import _XP1_PROFILE
        from civ6_host.runtime.xp1_saved_load import REFERENCE
        from civ6_host.runtime import xp1_production_profile
        from civ6_host.runtime.native.native_script_runtime import NativeScriptRuntime
        backend=SimpleNamespace(load_abi=SimpleNamespace(core_sha256=XP1_CORE_SHA256),
            captured_bundle=SimpleNamespace(reference=REFERENCE),core=SimpleNamespace(_civ6_host_execution_image=_XP1_PROFILE),
            runtime=SimpleNamespace(read=Mock()))
        # The composed Lua runtime has no process-memory reader. That belongs
        # to the official-load backend; do not invent an attribute in fixtures.
        script_runtime=NativeScriptRuntime.__new__(NativeScriptRuntime)
        self.assertFalse(hasattr(script_runtime,'read'))
        saved=SimpleNamespace(_check_query=Mock(),backend=backend,prefix=SimpleNamespace(runtime=script_runtime))
        with patch.object(xp1_production_profile,'bind_owner') as bind:
            xp1_production_info._bind(saved)
            bind.assert_called_once_with(backend,backend.core,backend.runtime.read)
            backend.captured_bundle.reference=('foreign','other')
            with self.assertRaises(ValueError):xp1_production_info._bind(saved)
            self.assertEqual(bind.call_count,1)

    def test_composed_readers_execute_shared_lua_and_reject_foreign_city(self):
        from lupa.lua51 import LuaRuntime
        from civ6_host.runtime import locale_text
        obs,prior,_,_=fixture()
        lua=LuaRuntime(encoding=None)
        pid,turn,cid=obs['player_id'],obs['turn'],obs['cities'][0]['id']
        lua.execute(f'pid,turn,cid={pid},{turn},{cid}'.encode())
        lua.execute(rb'''
owner=pid
Game={GetLocalPlayer=function()return pid end,GetLocalObserver=function()return pid end,
 GetCurrentGameTurn=function()return turn end}
Locale={Lookup=function(s)return s end}
MilitaryFormationTypes={STANDARD_FORMATION=0,CORPS_FORMATION=1,ARMY_FORMATION=2}
GameInfo={Units={},Buildings={},Districts={},Projects={},Yields={YIELD_PRODUCTION={}}}
q={GetCurrentProductionTypeHash=function()return 100 end,GetPreviousProductionTypeHash=function()return 0 end,
 GetCurrentProductionTypeModifier=function()return 0 end,GetTurnsLeft=function()return 3 end}
for _,kind in ipairs({'Unit','Building','District','Project'})do
 q['Get'..kind..'Cost']=function()return 30 end;q['Get'..kind..'Progress']=function()return 7 end
end
city={GetOwner=function()return owner end,GetID=function()return cid end,GetBuildQueue=function()return q end}
Players={[pid]={GetCities=function()return {Members=function()return ipairs({city})end}end}}
''')
        tables={'unit':('Units','Unit'),'building':('Buildings','Building'),
                'district':('Districts','District'),'project':('Projects','Project')}
        specs=quotes_reader.specifications([r['action'] for r in prior['candidates']])
        specs.append(dict(category='unit',index=0,hash=100,item_type='UNIT_SETTLER'))
        for row in specs:
            table,key=tables[row['category']]
            lua.execute((f"local r={{Index={row['index']},Hash={row['hash']},Cost=50,MustPurchase=false,CanTrain=true,"
                f"Name='{row['item_type']}',{key}Type='{row['item_type']}'}};"
                f"GameInfo.{table}[r.Index]=r;GameInfo.{table}[r.Hash]=r").encode())
        runtime=SimpleNamespace(evaluate_text=lambda child,source,tag,**kw:lua.execute(source))
        saved=SimpleNamespace(prefix=SimpleNamespace(runtime=runtime,ui_child=1),emit=Mock())
        value=deepcopy(prior)
        with (patch.object(xp1_production_info,'_bind'),patch.object(locale_text,'attach'),
              patch.object(quotes_reader,'verified_files')):
            xp1_production_info.attach(saved,obs,value)
            self.validate(obs,value)
            self.assertEqual(value['production_current']['cities'][0]['item']['progress'],7)
            self.assertTrue(value['production_info']['rows'])
            lua.execute(b'owner=pid+1')
            with self.assertRaises(Exception):xp1_production_info.attach(saved,obs,deepcopy(prior))


if __name__=='__main__':unittest.main()
