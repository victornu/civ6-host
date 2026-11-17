"""Four religious operations on retained session owners; no native process."""
import ast
from contextlib import nullcontext
from copy import deepcopy
import json
import struct
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from lupa.lua51 import LuaRuntime

from civ6_host.contracts import network_turn, religious_unit_operations as public
from civ6_host.runtime import xp1_religious_unit_operations as adapter
from civ6_host.runtime import xp1_session_view as view, xp1_load_capability
from civ6_host.runtime.configuration_profiles import XP1_CORE_SHA256, XP2_CORE_SHA256
from civ6_host.runtime.execution_images import _XP1_PROFILE
from civ6_host.runtime.native.network_session import NativeNetworkSession
from civ6_host.runtime.saved_load_services import SavedLoadServices
from civ6_host.runtime.xp1_saved_load_owner import SavedLoadOwner
from civ6_host.runtime.xp1_continuation import SavedContinuation
from civ6_host.runtime.xp1_saved_load import REFERENCE
from civ6_host.runtime.workers import network_worker as worker
from test_xp1_network_session import Fixture as ParentFixture
from test_xp1_great_person_activation_public import preceding, state as gp_state
from test_xp1_religion_beliefs_public import terminal_v11, validate, unavailable
from test_xp1_city_religion import religion_fixture
from test_xp1_great_person_activation import Fixture as ExistingFixture
from test_xp1_world_input_owner import Fixture as TransportFixture
from test_session_capabilities import seal


def worker_preflight():
    tree=ast.parse(Path(worker.__file__).read_text(encoding='utf-8'))
    body=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='_open_xp1').body
    blocks=[n for n in body if isinstance(n,ast.If) and isinstance(n.test,ast.Name)
            and n.test.id=='xp1_religious_unit_operations']
    if len(blocks)!=1:raise AssertionError('Expected one religious operation preflight')
    wrapper=ast.parse('def check(xp1_religious_unit_operations,xp1_dedications,selected,occupation_image,closure):\n pass').body[0]
    wrapper.body=blocks;scope={'_Path':Path}
    exec(compile(ast.fix_missing_locations(ast.Module(body=[wrapper],type_ignores=[])),str(worker.__file__),'exec'),scope)
    return scope['check']


def native_state(obs,mode='offered'):
    units=[]
    for unit in sorted(obs['units'],key=lambda row:row['id']):
        units.append(dict(unit_id=unit['id'],x=unit['x'],y=unit['y'],moves_remaining=unit['moves'],
            religion_type=1,spread_charges=3,operations=[] if mode in ('empty','hidden') or unit['moves']<=0 else
            [dict(operation=kind,visible=True,available=mode!='blocked') for kind in public.KINDS]))
    return dict(player_id=obs['player_id'],current_game_turn=obs['turn'],inquisition_started=False,units=units)


class Fixture(ExistingFixture):
    """Native reads/calls doubled, actual saved owner, transport, codecs and FIFO."""
    def __init__(self):
        super().__init__()
        self.saved.xp1_religious_unit_operations=True
        for name in ('xp1_prophet_activation','xp1_great_person_activation','xp1_religion_beliefs',
                     'xp1_religion_founding','xp1_religion_custom_names','xp1_pantheon'):
            setattr(self.saved,name,False)
        for unit in self.observation['units']:unit.update(owner=0,moves=1)
        self.token.observation=deepcopy(self.observation)
        self.native=native_state(self.observation);self.earned=2;self.native_index=93
        self.choice=dict(kind='spread_religion',unit_id=17,x=0,y=0)
        self.effect_mode='completed';self.emit_added=True;self.added_owner=0;self.added_unit=17
        self.token.world_input_prompts={};self.token.trade_feedback=None
        self.stack.enter_context(patch.object(adapter,'_catalogue',self.catalogue_native))
        self.stack.enter_context(patch.object(adapter,'_own_entitlement',self.entitlement_native))
        self.stack.enter_context(patch.object(adapter,'observe_player',self.observe_native))
        from civ6_host.runtime.unit_operation_ui_profile import verify_live
        self.token.unit_source=verify_live(self.backend.core._handle,self.backend.runtime.read,core_sha256=XP1_CORE_SHA256)
        # Complete the inherited __new__ fixture with the loader's real shared
        # combat/world-text source profile; no notification fallback is added.
        from civ6_host.runtime.combat_event_profile import bind_owner
        profile=bind_owner(self.backend,self.backend.core,self.read)
        self.owner.combat_event_profile=self.owner._combat_event_profile=profile
        self.owner._combat_producer_poisoned=self.owner._experience_producer_poisoned=False

    def catalogue_native(self,prefix,observation):
        if prefix is not self.saved.prefix:raise AssertionError('Foreign catalogue prefix')
        public.project(self.native,observation['player_id'],observation['turn'],observation=observation)
        return deepcopy(self.native)

    def entitlement_native(self,prefix,pid,turn):
        if prefix is not self.saved.prefix or (pid,turn)!=(0,8):raise AssertionError('Foreign entitlement read')
        return self.earned

    def evaluate(self,child,code,name,**kwargs):
        if name!=b'@explicit_xp1_religious_unit_request':return super().evaluate(child,code,name,**kwargs)
        if child is not self.token.ui_child or kwargs.get('capacity')!=32:raise AssertionError('Foreign request owner')
        self.machine.append(('can_start_operation',self.choice['kind']))
        if self.deny_request:return b'refused'
        self.machine.append(('request_operation',self.choice['kind'],self.choice['unit_id']))
        self.token.transport.pending.append(struct.pack('<IHH5I',adapter.source.ARCHIVE_KIND,0,1,
            self.choice['unit_id'],self.native_index,0xffffffff,0,0))
        return ('submitted|'+str(self.native_index)).encode('ascii')

    def virtual(self,core,pointer,slot,rva,result,*args):
        if rva!=self.token.transport.transport_abi.drain_rva:
            return TransportFixture.virtual(self,core,pointer,slot,rva,result,*args)
        def drain(ctx):
            self.machine.append(('drain',))
            self.memory.put(self.sentinel,struct.pack('<QQ',self.sentinel,self.sentinel))
            if self.emit_added:
                from civ6_host.runtime.native import native_event_15c35863 as event
                address=0x78002000
                self.memory.put(address,struct.pack('<HHI',self.added_owner,1,self.added_unit))
                self.owner.dispatch(event.KIND,event.encode_fields(event.EventFields(0,self.native_index,address)),0)
            kind,uid=self.choice['kind'],self.choice['unit_id']
            if self.effect_mode=='completed':
                row=next(r for r in self.native['units'] if r['unit_id']==uid)
                if kind in ('spread_religion','remove_heresy'):row['spread_charges']-=1
                else:
                    self.native['units']=[r for r in self.native['units'] if r['unit_id']!=uid]
                    self.observation['units']=[r for r in self.observation['units'] if r['id']!=uid]
                    if kind=='evangelize_belief':self.earned+=1
                    else:self.native['inquisition_started']=True
            elif self.effect_mode!='unchanged':raise AssertionError('Unknown fixture effect')
        return drain


class ReligiousUnitOperationSessionTests(unittest.TestCase):
    def fixture(self):
        f=Fixture();self.addCleanup(f.close);return f

    def test_parent_independent_bool_exact_image_and_actual_closure(self):
        with ParentFixture() as f:
            old=f.session();self.assertIs(type(old),NativeNetworkSession)
            self.assertFalse(old.xp1_religious_unit_operations)
            for flag in (0,1,None,'true'):
                with self.subTest(flag=flag),self.assertRaises(ValueError):f.session(xp1_religious_unit_operations=flag)
            with self.assertRaisesRegex(ValueError,'exact installed'):f.session(xp1_religious_unit_operations=True)
            options=dict(xp1_religious_unit_operations=True,execution_image_profile=_XP1_PROFILE.id)
            with patch.object(adapter,'require_actions',side_effect=ValueError('source refused')):
                with self.assertRaisesRegex(ValueError,'source refused'):f.session(**options)
            current=f.session(**options)
            for name in ('xp1_pantheon','xp1_religion_beliefs','xp1_religion_founding','xp1_religion_custom_names',
                         'xp1_prophet_activation','xp1_great_person_activation','xp1_great_people','xp1_great_people_actions'):
                self.assertFalse(getattr(current,name))
            current.reset()
            path=current.run/'closure.json';self.assertLess(path.stat().st_size,8*1024*1024)
            closure=json.loads(path.read_text(encoding='utf-8'))
            self.assertTrue(closure['xp1_religious_unit_operations']);self.assertEqual(len(f.spawns),1)
            for path,digest in adapter.source_dependencies(_XP1_PROFILE).items():
                self.assertEqual(closure['pins'][str(Path(path).resolve())],digest)

    def test_worker_preflight_exact_pins_wire_bool_and_owner_flag(self):
        check=worker_preflight();pins=adapter.source_dependencies(_XP1_PROFILE)
        check(True,True,SimpleNamespace(reference=REFERENCE),_XP1_PROFILE,dict(pins=pins))
        for image,dedications,reference,retained in ((None,True,REFERENCE,pins),
                (_XP1_PROFILE,False,REFERENCE,pins),(_XP1_PROFILE,True,('other','0'*64),pins),
                (_XP1_PROFILE,True,REFERENCE,{})):
            with self.subTest(image=image is None,dedications=dedications,pins=bool(retained)),self.assertRaises(ValueError):
                check(True,dedications,SimpleNamespace(reference=reference),image,dict(pins=retained))
        check(False,False,None,None,{})
        tree=ast.parse(Path(worker.__file__).read_text(encoding='utf-8'))
        entries=[n for n in ast.walk(tree) if isinstance(n,ast.Compare)
            and ast.unparse(n)=="type(closure.get('xp1_religious_unit_operations', False)) is not bool"]
        self.assertEqual(len(entries),1);expr=compile(ast.Expression(entries[0]),str(worker.__file__),'eval')
        for flag in (True,False,0,1,None,'true'):
            self.assertEqual(eval(expr,{'closure':dict(xp1_religious_unit_operations=flag)}),type(flag) is not bool)
        entries=[n for n in ast.walk(tree) if isinstance(n,ast.Assign)
            and ast.unparse(n)=='saved.xp1_religious_unit_operations = xp1_religious_unit_operations']
        self.assertEqual(len(entries),1)

    def test_view_last_group_offers_waiting_closed_terminal_and_checkpoint(self):
        for mode in ('offered','empty','hidden','blocked','waiting','closed'):
            for all_prior in (False,True):
                with self.subTest(mode=mode,all_prior=all_prior):
                    obs,_,_,city=religion_fixture();decisions=deepcopy(city)
                    inactive=mode in ('waiting','closed')
                    if inactive:unavailable(decisions)
                    if all_prior:
                        preceding(decisions,obs,waiting=inactive)
                        network_turn.add_xp1_great_person_activation(decisions,None if inactive else gp_state(obs))
                        seal(decisions)
                    prior=deepcopy(decisions)
                    native=native_state(obs,'offered' if inactive else mode);unchanged=deepcopy(native)
                    saved=SavedLoadOwner.__new__(SavedLoadOwner);saved.explicit_religious_unit_operations={'stale':True}
                    def query(actual,observation):
                        self.assertIs(actual,saved);self.assertIs(observation,obs)
                        saved.explicit_religious_unit_operations=deepcopy(native);return native
                    with patch.object(adapter,'catalogue',side_effect=query) as queried:
                        view._add_xp1_religious_unit_operations(saved,obs,decisions,actions_closed=mode=='closed')
                    validate(obs,decisions,closed=mode=='closed')
                    self.assertIn(decisions['schema'],network_turn.XP1_RELIGIOUS_UNIT_OPERATIONS_SCHEMAS)
                    self.assertEqual(native,unchanged)
                    self.assertEqual({k:v for k,v in decisions['families'].items() if k not in public.KINDS},prior['families'])
                    if inactive:
                        queried.assert_not_called();self.assertIsNone(saved.explicit_religious_unit_operations)
                        self.assertIsNone(decisions['religious_unit_operations'])
                    else:
                        queried.assert_called_once()
                        self.assertEqual(public.actions(decisions['religious_unit_operations']),adapter.actions(native))
                        restored,receipt=network_turn.checkpoint_catalogue(decisions,prior,obs,core_sha256=XP1_CORE_SHA256)
                        self.assertEqual(restored,prior)
                        self.assertEqual(receipt['added_public_fields'],['religious_unit_operations'])
                        self.assertEqual(receipt['added_action_families'],list(public.KINDS))
        obs,_,_,city=religion_fixture();decisions=terminal_v11(city);prior=deepcopy(decisions)
        saved.explicit_religious_unit_operations={'stale':True}
        with patch.object(adapter,'catalogue',side_effect=AssertionError('Closed native query')):
            view._add_xp1_religious_unit_operations(saved,obs,decisions,actions_closed=True)
        self.assertEqual(decisions,prior);self.assertIsNone(saved.explicit_religious_unit_operations)

    def test_real_saved_owner_four_operations_refusal_and_processed_without_effect(self):
        from civ6_host.runtime import xp1_session_inputs
        cases=[(kind,'completed') for kind in public.KINDS]
        cases += [('spread_religion','refused'),('remove_heresy','unchanged'),('spread_religion','no_added')]
        for kind,mode in cases:
            with self.subTest(kind=kind,mode=mode):
                f=self.fixture();f.choice['kind']=kind
                f.effect_mode='unchanged' if mode=='unchanged' else 'completed'
                f.deny_request=mode=='refused';f.emit_added=mode!='no_added'
                raw=adapter.catalogue(f.saved,f.token.observation)
                decisions=dict(candidates=[dict(action=a) for a in adapter.actions(raw)])
                f.saved._running=False
                self.assertIs(type(f.saved),SavedLoadOwner);self.assertIs(type(f.token),SavedContinuation)
                self.assertIs(type(f.backend.prefix),SavedLoadServices)
                with (patch.object(view,'read',return_value=({},f.token.observation,decisions)),
                      patch.object(xp1_load_capability,'capability_source_scope',return_value=nullcontext()),
                      patch.object(xp1_session_inputs,'_write_once',return_value={'fixture':True}),
                      patch.object(f.saved,'execute',wraps=f.saved.execute) as execute):
                    value=worker._execute_xp1(f.saved,f.choice,0,0,Path(__file__).parent/'fixture-closure.json')
                status='refused' if mode=='refused' else 'submitted' if mode in ('unchanged','no_added') else 'completed'
                reason=adapter.REFUSED if mode=='refused' else adapter.UNCONFIRMED if status=='submitted' else None
                self.assertEqual(value,dict(status=status,reason=reason,requested_action=f.choice))
                execute.assert_called_once_with(f.choice)
                self.assertEqual(f.token.sequence,1);self.assertFalse(f.backend.busy);self.assertFalse(f.saved.poisoned)
                self.assertEqual((f.token.transport.pending,f.deferred.pending),([],[]))
                self.assertEqual(f.deferred.consumed_count,0 if mode in ('refused','no_added') else 1)
                self.assertEqual(len([r for r in f.machine if r[0]=='request_operation']),0 if mode=='refused' else 1)
                with f.saved._attempt():after=adapter.catalogue(f.saved,f.token.observation)
                self.assertEqual(after,f.native);f.token.check_close();f.close()

    def test_continuation_requires_explicit_owner_exact_engine_and_scalar_action(self):
        for mode in ('disabled','xp2','bool_id','bool_x','target'):
            f=self.fixture();action=deepcopy(f.choice)
            if mode=='disabled':f.saved.xp1_religious_unit_operations=False
            elif mode=='xp2':f.backend.load_abi=SimpleNamespace(core_sha256=XP2_CORE_SHA256)
            elif mode=='bool_id':action['unit_id']=True
            elif mode=='bool_x':action['x']=True
            else:action['target_id']=19
            with self.subTest(mode=mode),self.assertRaises(ValueError):f.token.execute(action,session=f.saved)
            self.assertEqual(f.machine,[]);f.close()

    def command_result(self,mutate=None,*,status='completed',kind='spread_religion',available=True):
        f=self.fixture();f.choice['kind']=kind
        before=deepcopy(f.token.observation);after=deepcopy(before)
        old=deepcopy(f.native['units'][0]);new=deepcopy(old);new['spread_charges']-=1
        earned_before=earned_after=None;flag=False
        if kind in ('evangelize_belief','launch_inquisition'):
            new=None;after['units']=[r for r in after['units'] if r['id']!=17]
            if kind=='evangelize_belief':earned_before,earned_after=2,3
            else:flag=True
        receipt=dict(archive=dict(archive_sha256='a'*64,size_bytes=28,operation_index=93,parameters={}),
            operation_hash=adapter.source.OPERATIONS[kind][1],operation_added_sequence=1,
            consumed_before=0,consumed_after=1,unit_before=old,unit_after=new,
            beliefs_earned_before=earned_before,beliefs_earned_after=earned_after,
            inquisition_started_before=False,inquisition_started_after=flag)
        effect=dict(status='completed',observation=deepcopy(after),action=deepcopy(f.choice),
                    source_sha256=adapter.SOURCE[1],receipt=receipt)
        if status=='refused':
            after=deepcopy(before)
            effect=dict(status='refused',observation=deepcopy(before),action=deepcopy(f.choice),
                source_sha256=adapter.SOURCE[1],refusal_code=adapter.REFUSED,
                request=dict(can_start=False,request_invoked=False))
        result=dict(action=deepcopy(f.choice),effect=effect,observation_before=before,observation_after=after)
        if mutate:mutate(result)
        decisions=dict(candidates=[dict(action=f.choice)] if available else [])
        from civ6_host.runtime import xp1_session_inputs
        with (patch.object(view,'read',return_value=({},f.token.observation,decisions)),
              patch.object(f.saved,'execute',return_value=result) as execute,
              patch.object(xp1_session_inputs,'_write_once',return_value={'fixture':True})):
            value=worker._execute_xp1(f.saved,f.choice,0,0,Path(__file__).parent/'fixture-closure.json')
        count=execute.call_count;f.close();return value,count

    def test_worker_validates_native_source_receipts_effects_refusals_and_submitted(self):
        for kind in public.KINDS:self.assertEqual(self.command_result(kind=kind)[0]['status'],'completed')
        self.assertEqual(self.command_result(status='refused')[0]['reason'],adapter.REFUSED)
        self.assertEqual(self.command_result(available=False)[1],0)
        def unchanged(result,claimed=False):
            effect=result['effect'];receipt=effect['receipt']
            receipt['unit_after']['spread_charges']=receipt['unit_before']['spread_charges']
            if not claimed:effect.update(status='submitted',refusal_code=adapter.UNCONFIRMED)
        self.assertEqual(self.command_result(unchanged)[0]['status'],'submitted')
        changes=[lambda r:r['effect'].update(source_sha256='0'*64),
                 lambda r:r['effect']['action'].update(x=False),
                 lambda r:r['effect']['receipt']['archive'].update(size_bytes=True),
                 lambda r:r['effect']['receipt']['archive'].update(parameters=[]),
                 lambda r:r['effect']['receipt'].update(operation_hash=True),
                 lambda r:r['effect']['receipt'].update(operation_added_sequence=True),
                 lambda r:r['effect']['receipt'].update(operation_added_sequence=0),
                 lambda r:r['effect']['receipt'].update(consumed_before=2),
                 lambda r:r['effect']['receipt'].update(inquisition_started_after=1),
                 lambda r:r['effect']['receipt']['unit_before'].update(unit_id=True),
                 lambda r:r['effect']['receipt']['unit_after'].update(moves_remaining=False),
                 lambda r:r['effect']['receipt']['unit_before']['operations'][0].update(available=False),
                 lambda r:unchanged(r,claimed=True)]
        for number,change in enumerate(changes):
            with self.subTest(corruption=number),self.assertRaises(RuntimeError):self.command_result(change)
        with self.assertRaises(RuntimeError):
            self.command_result(lambda r:r['effect']['request'].update(can_start=0),status='refused')
        with self.assertRaises(RuntimeError):
            self.command_result(lambda r:r['effect']['receipt'].update(beliefs_earned_after=2),kind='evangelize_belief')
        with self.assertRaises(RuntimeError):
            self.command_result(lambda r:r['effect']['receipt'].update(inquisition_started_after=False),kind='launch_inquisition')


if __name__=='__main__':unittest.main()
