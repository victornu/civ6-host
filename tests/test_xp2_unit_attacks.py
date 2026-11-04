"""Candidate source, shared Lua, actual XP2 owner/FIFO and public/admin checks."""
from copy import deepcopy
import ctypes as C
from dataclasses import replace
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace as NS
import unittest
from unittest.mock import Mock,patch

from civ6_host.runtime import xp1_unit_attack_profile as selector, xp2_unit_attack_source as source
from civ6_host.runtime import xp1_unit_attacks as adapter, xp1_attack_visible_scope as scope
from civ6_host.runtime.configuration_profiles import BASE_CORE_SHA256 as BASE, XP1_CORE_SHA256 as XP1, XP2_CORE_SHA256 as XP2, _copy
from civ6_host.runtime.native import native_combat_actions as units, native_saved_city_targets as cities, native_saved_combat as combat
from test_xp1_unit_attack_readiness import unit_setup,city_setup,CANDIDATE
from lupa.lua51 import LuaRuntime
from xp2_unit_attack_owner_fixture import Fixture


class SourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from extract_phase31_next_export import pefile
        cls.proof=source.verify_source();cls.pe=pefile.PE(cls.proof['image']['path'],fast_load=True)
    @classmethod
    def tearDownClass(cls):cls.pe.close()

    def test_complete_source_and_independent_PE_live_correspondence(self):
        self.assertEqual(len(self.proof['bindings']),53);self.assertEqual(len(self.proof['functions']),151)
        self.assertEqual(len(self.proof['facade_contracts']['query_operations']),35)
        calls=[];base=0x180000000
        def read(address,size):
            calls.append((address,size));self.assertLessEqual(size,4096)
            return self.pe.get_data(address-base,size)
        self.assertEqual(source.verify_live(base,read),576);self.assertEqual(len(calls),577)
        self.assertEqual(hashlib.sha256(Path(self.proof['exe']['path']).read_bytes()).hexdigest(),source.EXE_SHA256)
        self.assertEqual(hashlib.sha256(Path(self.proof['image']['path']).read_bytes()).hexdigest(),XP2)
        self.assertEqual(selector.selected_proof('base',BASE),'base')
        self.assertEqual(selector.selected_proof('base',XP1),selector.SOURCE[1])
        self.assertEqual(selector.selected_proof('base',XP2),source.SOURCE[1])
        from civ6_host.runtime.xp2_world_input_source import SOURCE as queued
        self.assertEqual(selector.selected_queued_proof('base',XP2),queued[1])

    def test_relocated_module_uses_actual_PE_relocations_for_pointer_slots(self):
        import pefile
        self.pe.parse_data_directories(directories=[pefile.DIRECTORY_ENTRY['IMAGE_DIRECTORY_ENTRY_BASERELOC']])
        relocations={row.rva for block in self.pe.DIRECTORY_ENTRY_BASERELOC
                     for row in block.entries if row.type==pefile.RELOCATION_TYPE['IMAGE_REL_BASED_DIR64']}
        base=0x190000000;delta=base-self.pe.OPTIONAL_HEADER.ImageBase
        def read(address,size):
            rva=address-base;raw=bytearray(self.pe.get_data(rva,size))
            for target in relocations:
                if rva<=target and target+8<=rva+size:
                    offset=target-rva;value=int.from_bytes(raw[offset:offset+8],'little')
                    raw[offset:offset+8]=(value+delta).to_bytes(8,'little')
            return bytes(raw)
        self.assertEqual(source.verify_live(base,read),576)

    def test_late_body_literal_precision_enum_and_facade_corruption_refused(self):
        fragments=list(source._live_spans(self.proof))
        checks=[fragments[0][0],int(self.proof['functions']['0x6c1e40']['fragments'][-1]['end_rva_exclusive'],16)-1,
            int(self.proof['bindings']['Unit.GetAttacksRemaining']['name_va'],16)-0x180000000,
            0x9c09f8,0xa11a80+0x110,
            int(self.proof['enum_selection']['enums']['MapLayers.ANY']['site_rva'],16)]
        for changed in checks:
            with self.subTest(rva=hex(changed)):
                def read(address,size):
                    start=address-0x180000000;raw=bytearray(self.pe.get_data(start,size))
                    if start<=changed<start+size:raw[changed-start]^=1
                    return bytes(raw)
                with self.assertRaises(ValueError):source.verify_live(0x180000000,read)
        with self.assertRaises(ValueError):source.verify_source(XP1)
        with self.assertRaises(ValueError):source.verify_live(True,lambda a,n:b'')

    def test_source_schema_registration_and_closed_contract_mutations_refuse(self):
        original=source._source
        for change in ('schema','callback','branch','readiness','war','facade'):
            proof=_copy(self.proof)
            if change=='schema':proof['schema']='foreign'
            elif change=='callback':proof['bindings']['Unit.GetOwner']['callback_rva']='0x6fdd60'
            elif change=='branch':proof['functions']['0xd0290']['all_conditional_targets_captured']=False
            elif change=='readiness':proof['readiness_replacements']['unit_request']['count']=0
            elif change=='war':proof['contracts']['war_confirmation_admitted']=True
            else:proof['facade_contracts']['query_operations']['plot_owner']['slot']='0x18'
            with self.subTest(change=change),patch.object(source,'_source',side_effect=lambda ref:proof if ref==source.SOURCE else original(ref)):
                with self.assertRaises(ValueError):source.verify_source()

    def test_profile_receipt_checks_exact_owner_engine_base_reader_and_thread(self):
        f=Fixture();self.addCleanup(f.close)
        receipt=source.bind_owner(f.backend,f.backend.core,f.read)
        self.assertIs(source.bind_owner(f.backend,f.backend.core,f.read),receipt)
        self.assertIs(receipt.owner,f.backend);self.assertIs(receipt.core,f.backend.core)
        for option in ('core','reader','base','hash','receipt','thread'):
            with self.subTest(option=option):
                core=f.backend.core;read=f.read
                if option=='core':core=NS(_handle=core._handle)
                elif option=='reader':read=lambda a,n:f.read(a,n)
                elif option=='base':f.backend.core=NS(_handle=core._handle+0x1000)
                elif option=='hash':f.backend.load_abi=NS(core_sha256=XP1)
                elif option=='receipt':f.backend._xp2_unit_attack_source_receipt=replace(receipt,owner=object())
                else:f.backend.runtime.thread=lambda:('foreign','thread')
                try:
                    with self.assertRaises((ValueError,RuntimeError)):source.bind_owner(f.backend,core,read)
                finally:
                    f.backend.core=receipt.core
                    from civ6_host.runtime.saved_load_profiles import profile_for_sha
                    f.backend.load_abi=profile_for_sha(XP2)
                    f.backend._xp2_unit_attack_source_receipt=receipt
                    f.backend.runtime.thread=lambda:f.backend.thread


class LuaSelectionTests(unittest.TestCase):
    def test_xp2_exact_three_readiness_transforms_and_base_default(self):
        for kind,(old,new) in selector.READINESS_REPLACEMENTS.items():
            self.assertEqual(selector.selected_readiness_source(old.encode(),BASE,kind),old.encode())
            self.assertEqual(selector.selected_readiness_source(old.encode(),XP2,kind),new.encode())
            for text in (b'changed',old.encode()*2):
                with self.assertRaises(ValueError):selector.selected_readiness_source(text,XP2,kind)
        self.assertEqual(selector.precision_reference(XP2),source.SOURCE)
        self.assertEqual(selector.precision_reference(XP1),selector.PUBLIC_PRECISION_SOURCE)

    def test_native_legal_unready_unit_preserves_all_three_routes(self):
        for melee,modifier in ((False,True),(False,False),(True,True)):
            candidate=dict(CANDIDATE,operation='MOVE_TO' if melee else 'RANGE_ATTACK')
            lua=LuaRuntime(encoding=None);lua.execute(unit_setup(ready=False,melee=melee))
            result=units.parse_candidates(lua.execute(units.candidate_source(0,7,ranged_modifier=modifier,core_sha256=XP2)),0,7,core_sha256=XP2)
            self.assertEqual(result['candidates'],[candidate])
            self.assertEqual(lua.execute(units.request_source(0,7,candidate,width=3,height=2,ranged_modifier=modifier,core_sha256=XP2)),b'submitted')
            self.assertEqual(lua.globals().requests,1)

    def test_hidden_illegal_perspective_and_strategic_gates_remain_native(self):
        changes=(b'UnitManager.CanStartOperation=function()return false end',
            b'PlayersVisibility[0].IsUnitVisible=function()return false end',
            b'PlayersVisibility[0].IsVisible=function()return false end',
            b'Game.GetLocalPlayer=function()return 1 end')
        for change in changes:
            lua=LuaRuntime(encoding=None);lua.execute(unit_setup(ready=False));lua.execute(change)
            from lupa.lua51 import LuaError
            try:raw=lua.execute(units.candidate_source(0,7,core_sha256=XP2))
            except LuaError:pass
            else:self.assertEqual(units.parse_candidates(raw,0,7,core_sha256=XP2)['candidates'],[])
            with self.assertRaises(Exception):lua.execute(units.request_source(0,7,CANDIDATE,width=3,height=2,core_sha256=XP2))
            self.assertEqual(lua.globals().requests,0);self.assertEqual(lua.globals().fixtureForbidden(),0)

    def test_city_catalogue_unready_keeps_raw_defense_and_distinct_routes(self):
        for ranged in (True,False):
            lua=LuaRuntime(encoding=None);lua.execute(city_setup(ready=False,extra=b'' if ranged else b'ranged=false'))
            value=cities.parse(lua.execute(cities.source(7,core_sha256=XP2)),7,0)
            self.assertEqual(value['cities'][0]['defense_strength'],30)
            expected={'dedicated_ranged','world_plot'} if ranged else {'world_plot'}
            self.assertEqual({row['input_route'] for row in value['candidates']},expected)
        for change in (b'Game.IsAllowStrategicCommands=function()return false end',b'Game.GetLocalObserver=function()return 1 end'):
            lua=LuaRuntime(encoding=None);lua.execute(city_setup(ready=False,extra=change))
            with self.assertRaises(Exception):lua.execute(cities.source(7,core_sha256=XP2))


class ComposedOwnerTests(unittest.TestCase):
    def fixture(self):
        f=Fixture();self.addCleanup(f.close);return f

    def test_xp2_attack_real_transport_fifo_publication_readback_and_detached_catalogue(self):
        f=self.fixture();maps,invoke=f.install_maps();self.addCleanup(maps.close)
        self.assertEqual(invoke(),(1,{7:1}));self.assertEqual(invoke(0x720008),(0,None))
        self.assertIs(f.token.prefix.maps,maps);self.assertIs(f.host._map_service_owner,maps)
        offers=f.prepare();self.assertEqual(len(offers['actions']),2)
        offers['unit_attacks']['units'][0]['damage']=99
        self.assertEqual(f.token.explicit_combat_units[0]['damage'],0)
        result=f.execute_attack();receipt=result['receipt']
        self.assertEqual(result['status'],'completed');self.assertEqual(receipt['source_proof_sha256'],source.SOURCE[1])
        self.assertTrue(receipt['effect']['target_visible_damage_increased'])
        self.assertEqual((f.token.publication_count,f.deferred.consumed_count),(1,1))
        self.assertEqual(f.token.sequence,1);self.assertFalse(f.saved._running)
        self.assertEqual(f.last_transition['observation_after'],result['observation'])
        self.assertEqual([row[0] for row in f.machine],['view_ctor','receive','view_dtor','drain','ensure','publish'])
        self.assertEqual(f.token.transport.pending,[]);self.assertEqual(f.deferred.pending,[])
        self.assertIsNone(f.token._xp1_unit_attack_catalogue)
        for name in ('selected_defender_claimed','death_or_capture_inferred_from_absence',
                     'combat_resolution_inferred_from_queue','combat_resolution_inferred_from_lifecycle'):
            self.assertIs(receipt['effect'][name],False)

    def test_xp2_public_rounding_admin_raw_pin_and_raw_effect_revalidation(self):
        f=self.fixture();f.city_target=True
        f.observation['visible_enemy_units']=[];f.token.observation=deepcopy(f.observation)
        offers=f.prepare();self.assertEqual(offers['unit_attacks']['cities'][0]['defense_strength'],21)
        event=adapter.administrative_readback(f.saved,f.token.observation,13)
        self.assertFalse(event['actor_channel']);self.assertEqual(event['source_sha256'],source.SOURCE[1])
        self.assertEqual(event['cities'][0]['defense_strength'],20.5)
        event['cities'][0]['defense_strength']=99
        self.assertEqual(f.token.explicit_combat_cities[0]['defense_strength'],20.5)
        result=f.execute_attack();effect=result['receipt']['effect']
        self.assertEqual(effect['visible_cities_before'][0]['defense_strength'],20.5)
        self.assertEqual(effect['visible_cities_after'][0]['garrison_damage'],20)

    def test_xp2_scope_and_catalogue_reject_cross_revision_core_and_FIFO(self):
        f=self.fixture();f.prepare()
        for changed in ('sequence','publication','fifo','core','engine'):
            with self.subTest(changed=changed):
                with scope.capture(f.saved,f.token.observation) as selected:
                    old=(f.token.sequence,f.token.publication_count,f.deferred._sequence,f.backend.core,f.backend.load_abi)
                    if changed=='sequence':f.token.sequence+=1
                    elif changed=='publication':f.token.publication_count+=1
                    elif changed=='fifo':f.deferred._sequence+=1
                    elif changed=='core':f.backend.core=NS(_handle=old[3]._handle)
                    else:f.backend.load_abi=NS(core_sha256=XP1)
                    try:
                        with self.assertRaises((ValueError,RuntimeError)):scope.check(selected,f.token.prefix,8,0,XP2)
                    finally:
                        f.token.sequence,f.token.publication_count,f.deferred._sequence,f.backend.core,f.backend.load_abi=old
        catalogue=f.token._xp1_unit_attack_catalogue;action=deepcopy(catalogue.actions[0]);f.set_active(True)
        for field in ('publication_count','_sequence','consumed_count'):
            obj=f.token if field=='publication_count' else f.deferred;old=getattr(obj,field)
            setattr(obj,field,old+1)
            try:
                with self.assertRaises(ValueError):adapter.apply(f.saved,action,catalogue.observation)
            finally:setattr(obj,field,old)
        self.assertEqual(f.machine,[])

    def test_xp2_no_effect_refuses_and_poison_prevents_replay(self):
        f=self.fixture();f.no_effect=True
        with self.assertRaisesRegex(RuntimeError,'no-change readback is unqualified'):f.execute_attack()
        self.assertTrue(f.saved.poisoned);self.assertEqual(f.token.publication_count,1)
        self.assertIsNone(f.token._xp1_unit_attack_catalogue)
        self.assertFalse(any(stage=='official_explicit_unit_attack_effect' for stage,_ in f.emitted))
        with self.assertRaises((ValueError,RuntimeError)):f.prepare()

    def test_xp2_uncertain_native_failure_poison_prevents_publication_and_replay(self):
        f=self.fixture();f.fail_after_receive=True
        with self.assertRaisesRegex(RuntimeError,'XP2 combat did not return'):f.execute_attack()
        self.assertTrue(f.saved.poisoned and f.backend.poisoned)
        self.assertEqual(f.token.publication_count,0);self.assertIsNone(f.token._xp1_unit_attack_catalogue)
        machine=list(f.machine)
        with self.assertRaises((ValueError,RuntimeError)):f.prepare()
        self.assertEqual(f.machine,machine)

    def test_xp2_backend_only_combat_admin_and_action_gate(self):
        from civ6_host.runtime.backend import NetworkBackend
        from civ6_host.runtime.xp1_continuation import SavedContinuation
        with patch('civ6_host.runtime.backend._prepare_runtime'),patch('civ6_host.runtime.native.network_session.NativeNetworkSession') as native:
            backend=NetworkBackend(resources='fixture',official_bundle={},input_profile='xp2-lan',administrative_information=True)
            self.assertIs(backend._information_store,native.return_value._information_store)
            self.assertEqual(backend._information_store._pins,{'combat':source.SOURCE[1]})
        owner=SavedContinuation.__new__(SavedContinuation);owner.owner=NS(load_abi=NS(core_sha256=XP2))
        action=dict(kind='unit_attack',unit_id=17,operation='RANGE_ATTACK',input_route='enemy_flag',plot_id=1,x=1,y=0)
        with patch.object(owner,'_transition') as transition:
            owner.execute(action);transition.assert_called_once_with(action,session=None,pump=False)


class SessionViewTests(unittest.TestCase):
    def test_xp2_v11_family_and_closed_read_preserve_current_view_contract(self):
        from test_xp2_session_view import XP2SessionView
        from civ6_host.runtime import xp1_session_view as view
        from civ6_host.contracts import network_turn as contract
        fixture=XP2SessionView(methodName='runTest');fixture.setUp();self.addCleanup(fixture.doCleanups)
        f=fixture.fixture
        _,obs,catalogue=view.read(f.saved,0,9)
        self.assertEqual(catalogue['schema'],contract.CAPABILITY_COMBAT_READINESS_SCHEMA)
        self.assertEqual(catalogue['families']['unit_attack']['status'],'queried_partial')
        self.assertIn('unit_attacks',catalogue);f.attacks.assert_called_once_with(f.saved,obs)
        f.attacks.reset_mock()
        _,obs,catalogue=view.read(f.saved,0,10,actions_closed=True)
        self.assertIsNone(catalogue['unit_attacks']);f.attacks.assert_not_called()
        contract.validate_capability_catalogue(catalogue,f.saved.continuation.identity,10,1,
            player_id=0,actions_closed=True,observation=obs)


if __name__=='__main__':unittest.main(verbosity=2)
