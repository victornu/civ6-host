"""Offline actor, source and composed XP1 majority-religion boundaries."""
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from civ6_host import InformationUnavailable, ProtocolError, SessionClient
from civ6_host.contracts import city_religion, network_turn
from civ6_host.runtime import xp1_city_religion, xp1_production_info, xp1_session_view
from civ6_host.runtime.configuration_profiles import XP1_CORE_SHA256, XP2_CORE_SHA256
from civ6_host.runtime.execution_images import _XP1_PROFILE
from civ6_host.runtime.xp1_saved_load import REFERENCE
from test_session_capabilities import seal
from test_xp1_production_info import fixture, upgraded, ProductionBackend


def state(obs, index=-1):
    return dict(schema=city_religion.SCHEMA,player_id=obs['player_id'],turn=obs['turn'],
        cities=[dict(city_id=row['id'],majority_religion=index) for row in sorted(obs['cities'],key=lambda r:r['id'])])


def religion_fixture():
    obs,older,current,raw=fixture(faith=True)
    prior,_=upgraded(obs,older,current,raw)
    value=deepcopy(prior)
    with patch.object(xp1_city_religion,'read',return_value=state(obs)):
        xp1_city_religion.attach(None,obs,value)
    return obs,older,prior,seal(value)


class ReligionBackend(ProductionBackend):
    def _reply(self,operation,sequence,player,requested=None):
        reply=super()._reply(operation,sequence,player,requested)
        if operation!='close':
            with patch.object(xp1_city_religion,'read',return_value=state(reply['observation'])):
                xp1_city_religion.attach(None,reply['observation'],reply['decisions'])
            seal(reply['decisions'])
        return reply


class XP1CityReligionTests(unittest.TestCase):
    def validate_catalogue(self,obs,value):
        seal(value)
        identity=SimpleNamespace(episode_id=value['episode_id'],game_generation=value['game_generation'])
        return network_turn.validate_capability_catalogue(value,identity,value['sequence'],obs['turn'],
            player_id=obs['player_id'],observation=obs)

    def test_public_contract_preserves_signed_native_domain_without_inference(self):
        obs,*_=fixture()
        for index in (-2147483648,-1,0,1,2147483647):
            value=state(obs,index)
            self.assertIs(city_religion.validate(value,obs['player_id'],obs['turn'],observation=obs),value)
            payload=f"city-religion-v1|{obs['player_id']}|{obs['turn']}\n{obs['cities'][0]['id']}|{index}".encode()
            self.assertEqual(xp1_city_religion.parse_readback(payload,obs['player_id'],obs['turn'],obs),value)
        for index in (True,None,1.5,-2147483649,2147483648):
            with self.subTest(index=index),self.assertRaises(ValueError):
                city_religion.validate(state(obs,index),obs['player_id'],obs['turn'],observation=obs)

    def test_exact_own_city_set_boundary_and_field_allowlist(self):
        obs,*_=fixture()
        for change in ('foreign','missing','duplicate','extra','actor','turn','foreign_observation','bool_owner'):
            value=state(obs);observation=deepcopy(obs)
            if change=='foreign':value['cities'][0]['city_id']+=1
            elif change=='missing':value['cities']=[]
            elif change=='duplicate':value['cities']*=2
            elif change=='extra':value['cities'][0]['followers']=99
            elif change=='actor':value['player_id']+=1
            elif change=='turn':value['turn']+=1
            elif change=='foreign_observation':observation['cities'][0]['owner']+=1
            else:observation['cities'][0]['owner']=False
            with self.subTest(change=change),self.assertRaises(ValueError):
                city_religion.validate(value,obs['player_id'],obs['turn'],observation=observation)
        empty=deepcopy(obs);empty['cities']=[]
        self.assertEqual(city_religion.validate(state(empty),obs['player_id'],obs['turn'],observation=empty)['cities'],[])

    def test_versioned_catalogue_composes_production_faith_and_checkpoint_projection(self):
        obs,older,prior,value=religion_fixture()
        original=deepcopy(value)
        self.validate_catalogue(obs,value)
        self.assertEqual(value['candidates'],prior['candidates'])
        self.assertTrue(any(row['action'].get('currency')=='YIELD_FAITH' for row in value['candidates']))
        for target,fields in ((prior,['city_religion']),
                              (older,['production_current','production_info','city_religion'])):
            projected,receipt=network_turn.checkpoint_catalogue(value,target,obs,core_sha256=XP1_CORE_SHA256)
            self.assertEqual(projected,target)
            self.assertEqual(receipt['added_public_fields'],fields)
            self.assertTrue(receipt['historical_fields_unchanged'])
        self.assertEqual(value,original)
        self.assertEqual(network_turn.checkpoint_catalogue(value,value,obs,core_sha256=XP1_CORE_SHA256),(value,None))
        with self.assertRaisesRegex(ValueError,'Rise and Fall'):
            network_turn.checkpoint_catalogue(value,prior,obs,core_sha256=XP2_CORE_SHA256)
        bad=deepcopy(value);bad['choice_state']['research']['research']=123;seal(bad)
        self.assertNotEqual(network_turn.checkpoint_catalogue(bad,prior,obs,core_sha256=XP1_CORE_SHA256)[0],prior)
        for change in ('missing','foreign','old_schema'):
            bad=deepcopy(value)
            if change=='missing':del bad['city_religion']
            elif change=='foreign':bad['city_religion']['cities'][0]['city_id']+=1
            else:bad['schema']=prior['schema']
            with self.subTest(change=change),self.assertRaises(ValueError):self.validate_catalogue(obs,bad)
        no_queue=deepcopy(value)
        no_queue['production_queues']=no_queue['production_current']=no_queue['production_info']=None
        from civ6_host.client import _public_contracts
        _public_contracts(no_queue,obs,False)

    def test_session_client_revision_detachment_and_public_only_query(self):
        backend=ReligionBackend();client=SessionClient(backend,allow_administrative=True)
        view=client.reset();result=client.information('city_religion')
        self.assertEqual(result['data'],state(view['observation']))
        self.assertEqual(result['sequence'],view['sequence'])
        self.assertEqual(result['native_decision_id'],view['decisions']['decision_id'])
        self.assertEqual(result['source_contracts'],{'city_religion':city_religion.SCHEMA,
            'decision_catalogue':view['decisions']['schema']})
        self.assertEqual(backend.calls,[])
        result['data']['cities'][0]['majority_religion']=99
        self.assertEqual(client.information('city_religion')['data']['cities'][0]['majority_religion'],-1)
        self.assertEqual(client.information('production')['data']['schema'],'civ6-host.production-inputs.v3')
        with self.assertRaises(InformationUnavailable):client.information('city_religion',channel='administrative')
        client._views[0]['decisions']['city_religion']['turn']+=1
        with self.assertRaises(ProtocolError):client.information('city_religion')
        prior_client=SessionClient(ProductionBackend());prior_client.reset()
        with self.assertRaises(InformationUnavailable):prior_client.information('city_religion')

    def test_historical_and_other_images_keep_old_schema_without_readers(self):
        obs,prior,_,_=fixture()
        for core_sha,image in ((XP1_CORE_SHA256,None),(XP1_CORE_SHA256,object()),
                               (XP2_CORE_SHA256,_XP1_PROFILE)):
            value=deepcopy(prior)
            saved=SimpleNamespace(backend=SimpleNamespace(load_abi=SimpleNamespace(core_sha256=core_sha),
                core=SimpleNamespace(_civ6_host_execution_image=image)))
            with (patch.object(xp1_production_info,'attach') as production,
                  patch.object(xp1_city_religion,'attach') as religion):
                xp1_session_view._attach_installed_xp1_information(saved,obs,value)
            production.assert_not_called();religion.assert_not_called()
            self.assertEqual(value,prior)
        saved.backend.load_abi.core_sha256=XP1_CORE_SHA256
        def production_attach(owner,observation,decisions):
            decisions['schema']=network_turn.XP1_PRODUCTION_INFO_SCHEMA_BY_BASE[decisions['schema']]
        with (patch.object(xp1_production_info,'attach',side_effect=production_attach) as production,
              patch.object(xp1_city_religion,'attach') as religion):
            xp1_session_view._attach_installed_xp1_information(saved,obs,deepcopy(prior))
        production.assert_called_once();religion.assert_called_once()
        with (patch.object(xp1_production_info,'source_dependencies') as production,
              patch.object(xp1_city_religion,'source_dependencies') as religion):
            xp1_session_view.source_dependencies(core_sha256=XP1_CORE_SHA256,execution_image=None)
        production.assert_not_called();religion.assert_not_called()

    def test_lua_owner_guards_precede_religion_and_check_afterwards(self):
        from lupa.lua51 import LuaRuntime
        obs,*_=fixture();pid,turn,cid=obs['player_id'],obs['turn'],obs['cities'][0]['id']
        lua=LuaRuntime(encoding=None)
        lua.execute(f'pid,turn,cid,width,height={pid},{turn},{cid},{obs["width"]},{obs["height"]}'.encode())
        lua.execute(rb'''
owner=pid;majority=-1;reads=0;duplicate=false;mutate=false
Game={GetLocalPlayer=function()return pid end,GetLocalObserver=function()return pid end,
 GetCurrentGameTurn=function()return turn end}
Map={GetGridSize=function()return width,height end,GetPlotCount=function()return width*height end}
local religion={GetMajorityReligion=function()reads=reads+1;if mutate then owner=pid+1 end;return majority end}
city={GetOwner=function()return owner end,GetID=function()return cid end,
 GetReligion=function()reads=reads+1;return religion end}
Players={[pid]={GetCities=function()return {Members=function()return ipairs(duplicate and {city,city} or {city})end}end}}
''')
        runtime=SimpleNamespace(evaluate_text=lambda child,source,tag,**kw:lua.execute(source))
        saved=SimpleNamespace(prefix=SimpleNamespace(runtime=runtime,ui_child=1))
        with patch.object(xp1_city_religion,'_bind'):
            self.assertEqual(xp1_city_religion.read(saved,obs),state(obs))
            lua.execute(b'majority=0')
            self.assertEqual(xp1_city_religion.read(saved,obs),state(obs,0))
            for change in (b'owner=pid+1',b'owner=pid;duplicate=true',b'duplicate=false;turn=turn+1'):
                lua.execute(change+b';reads=0')
                with self.assertRaises(Exception):xp1_city_religion.read(saved,obs)
                self.assertEqual(lua.eval(b'reads'),0)
            lua.execute(b'turn=turn-1;owner=pid;mutate=true')
            with self.assertRaises(Exception):xp1_city_religion.read(saved,obs)

    def test_bounded_parser_and_catalogue_actor_guard(self):
        obs,*_=fixture();pid,turn=obs['player_id'],obs['turn']
        for raw in (b'',b'city-religion-v1|99|0',b'x'*131073,
                    f'city-religion-v1|{pid}|{turn}\n1|nan'.encode(),
                    f'city-religion-v1|{pid}|{turn}\n1|+1'.encode()):
            with self.subTest(raw=raw[:25]),self.assertRaises(ValueError):
                xp1_city_religion.parse_readback(raw,pid,turn,obs)
        _,_,prior,_=religion_fixture()
        for key in ('player_id','turn'):
            value=deepcopy(prior);value[key]+=1
            with patch.object(xp1_city_religion,'read') as reader,self.assertRaises(ValueError):
                xp1_city_religion.attach(None,obs,value)
            reader.assert_not_called()

    def test_live_binding_pins_all_proven_spans_and_complete_accessor(self):
        import pefile
        image=pefile.PE(_XP1_PROFILE.path,fast_load=True)
        base=0x180000000
        memory=Mock(side_effect=lambda address,size:image.get_data(address-base,size))
        backend=SimpleNamespace(load_abi=SimpleNamespace(core_sha256=XP1_CORE_SHA256),
            captured_bundle=SimpleNamespace(reference=REFERENCE),runtime=SimpleNamespace(read=memory),
            core=SimpleNamespace(_handle=base,_civ6_host_execution_image=_XP1_PROFILE))
        from civ6_host.runtime.native.native_script_runtime import NativeScriptRuntime
        script_runtime=NativeScriptRuntime.__new__(NativeScriptRuntime)
        self.assertFalse(hasattr(script_runtime,'read'))
        saved=SimpleNamespace(_check_query=Mock(),backend=backend,
            prefix=SimpleNamespace(runtime=script_runtime))
        xp1_city_religion._bind(saved)
        self.assertEqual(memory.call_count,5)
        memory.assert_any_call(base+0x7a14a0,4)
        xp1_city_religion._bind(saved);self.assertEqual(memory.call_count,5)
        saved.prefix=object();memory.side_effect=lambda address,size:b'\0'*size
        with self.assertRaisesRegex(ValueError,'binding differs'):xp1_city_religion._bind(saved)
        for foreign in ('image','capture','core'):
            memory.reset_mock();backend.captured_bundle.reference=REFERENCE
            backend.core._civ6_host_execution_image=_XP1_PROFILE;backend.load_abi.core_sha256=XP1_CORE_SHA256
            if foreign=='image':backend.core._civ6_host_execution_image=None
            elif foreign=='capture':backend.captured_bundle.reference=('foreign','other')
            else:backend.load_abi.core_sha256=XP2_CORE_SHA256
            with self.assertRaisesRegex(ValueError,'exact installed'):xp1_city_religion._bind(saved)
            memory.assert_not_called()
        image.close()

    def test_exact_sources_are_verified_and_source_proof_is_not_generic(self):
        pins=xp1_city_religion.source_dependencies(_XP1_PROFILE)
        self.assertEqual(len(pins),5)
        self.assertEqual(pins[str(Path(_XP1_PROFILE.path).resolve())],_XP1_PROFILE.image_sha256)
        self.assertIn(xp1_city_religion.CITY_UI[1],pins.values())
        composed=xp1_session_view.source_dependencies(core_sha256=XP1_CORE_SHA256,execution_image=_XP1_PROFILE)
        for path,digest in pins.items():self.assertEqual(composed[path],digest)
        rows=xp1_city_religion.verify_source()
        self.assertEqual({row['method']:row['registration']['rva'] for row in rows},
            {'City.GetReligion':'0x5a5c7f','CityReligion.GetMajorityReligion':'0x5ad903'})
        with self.assertRaisesRegex(ValueError,'exact installed'):xp1_city_religion.source_dependencies(None)
        proof={'schema':'foreign'}
        with patch.object(xp1_city_religion,'_source',return_value=proof),self.assertRaises(ValueError):
            xp1_city_religion.verify_source()


if __name__=='__main__':unittest.main()
