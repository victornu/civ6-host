"""XP2 session composition with real saved owners and FIFO, no native process."""
import ast
from contextlib import nullcontext
from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
import struct
import threading
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch
import pefile

from civ6_host.contracts import network_turn, religious_unit_operations as public
from civ6_host.runtime import xp1_religious_unit_operations as adapter
from civ6_host.runtime import xp1_session_view as view, xp1_load_capability
from civ6_host.runtime.configuration_profiles import XP1_CORE_SHA256, XP2_CORE_SHA256
from civ6_host.runtime.execution_images import _PROFILE, _XP1_PROFILE, select, known_path
from civ6_host.runtime.native.network_session import NativeNetworkSession
from civ6_host.runtime.saved_load_services import SavedLoadServices
from civ6_host.runtime.xp1_saved_load_owner import SavedLoadOwner
from civ6_host.runtime.xp1_continuation import SavedContinuation
from civ6_host.runtime.xp2_bundle_inputs import REFERENCE
from civ6_host.runtime import xp2_bbg_inputs
from civ6_host.runtime.workers import network_worker as worker
from civ6_host.runtime.paths import resource_root
from civ6_host.runtime.source_build_identity import CURRENT_UNSIGNED_LOG_HOST_REFERENCE
from test_xp1_network_session import Fixture as ParentFixture, reset_reply
from test_xp1_religious_unit_operations_session import native_state
from xp2_unit_attack_owner_fixture import Fixture as ExistingFixture


def worker_preflight():
    tree=ast.parse(Path(worker.__file__).read_text(encoding='utf-8'))
    body=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='_open_xp1').body
    blocks=[n for n in body if isinstance(n,ast.If) and
            ('xp2_religious_unit_operations'==ast.unparse(n.test) or
             'type(xp2_religious_unit_operations) is not bool'==ast.unparse(n.test))]
    if len(blocks)!=2:raise AssertionError('Expected strict bool and exact XP2 source preflight')
    wrapper=ast.parse('def check(xp2_religious_unit_operations,selected,occupation_image,closure): pass').body[0]
    wrapper.body=blocks;scope={'_Path':Path}
    exec(compile(ast.fix_missing_locations(ast.Module(body=[wrapper],type_ignores=[])),str(worker.__file__),'exec'),scope)
    return scope['check']


class Fixture(ExistingFixture):
    """The retained XP2 owner, ABI, cache and transport; only native boundaries doubled."""
    def __init__(self):
        image=select(_PROFILE.id,core_path=known_path(_PROFILE.id))
        from civ6_host.runtime import foundation_event_profile
        pillage=foundation_event_profile.pillage_source
        # The existing fixture predates execution-image selection. Keep the
        # exact source validator, with the admitted current image argument.
        from xp2_unit_attack_owner_fixture import XP2ComposedNotifications
        original_graph=XP2ComposedNotifications.graph
        def current_graph(actual):
            graph=original_graph(actual)
            graph.backend.core._civ6_host_execution_image=image
            graph.backend.core._name=image.path
            return graph
        with (patch.object(foundation_event_profile,'pillage_source',
                side_effect=lambda **kw:pillage(execution_image=image)),
              patch.object(XP2ComposedNotifications,'graph',current_graph)):
            super().__init__()
        self.backend.core._name=image.path
        self.backend.core._civ6_host_execution_image=image
        # Use the actual installed PE and its normal relocations for new source
        # checks. Existing XP2 memory and service objects stay under ABI324.
        self.pe.close();self.pe=pefile.PE(image.path,fast_load=True)
        proof=adapter.source.xp2.verify_source()
        ordinal=adapter.source.xp2._ordinal_source(proof)
        tables=[(int(row['rva'],16),range(len(row['target_rvas'])))
                for row in proof['callable_vtables'].values()]
        manager=ordinal['manager_vtable']
        tables.append((int(manager['rva'],16),[int(slot,16)//8 for slot in manager['slots']]))
        for rva,slots in tables:
            for slot in slots:
                value=struct.unpack('<Q',self.pe.get_data(rva+slot*8,8))[0]
                self.memory.put(self.memory.core_base+rva+slot*8,struct.pack('<Q',
                    value-self.pe.OPTIONAL_HEADER.ImageBase+self.memory.core_base))
        self.stack.enter_context(patch('civ6_host.runtime.profile_script_binding._current_executable',
            return_value=resource_root()/CURRENT_UNSIGNED_LOG_HOST_REFERENCE[0]))
        # Complete the existing __new__ graph with the real Lua owner and its
        # borrowed-service receipt. Only native connection inspection is doubled.
        from civ6_host.runtime.native.native_script_runtime import NativeScriptRuntime
        from civ6_host.runtime import core_script_services as services
        from civ6_host.runtime.native import native_setup
        prefix=self.saved.prefix;old=prefix.runtime
        runtime=NativeScriptRuntime.__new__(NativeScriptRuntime);runtime.__dict__.update(old.__dict__)
        runtime.root=0x720000;runtime.closed=False;runtime.emit=self.emit
        runtime.database_bound=runtime.configuration_bound=runtime.locale_bound=True
        prefix.runtime=self.token.runtime=runtime
        self.token.lease.script_runtime=runtime
        prefix.events.runtime=prefix.contexts.runtime=runtime
        self.arguments.reader.core=self.backend.core
        self.host.localization_initialized=True;self.host.database=object()
        inner,configuration,gameplay=0xd10000,0xd20000,0xd30000
        self.stack.enter_context(patch.object(native_setup,'local_reader',return_value=self.read))
        def inspect(core,context,database,read):
            if (core is not self.backend.core or context!=self.backend.context
                    or database is not self.host.database or read!=self.read):
                raise AssertionError('Foreign borrowed native connection')
            return inner,configuration,gameplay
        self.stack.enter_context(patch.object(services,'_inspect',side_effect=inspect))
        lease=services.BorrowedCoreServices(runtime,self.host,self.backend.core,runtime.root,
            self.backend.context,inner,configuration,gameplay,threading.get_ident(),
            services.INIT_SOURCE[1],services.TYPE_SOURCE[1])
        services.commit(runtime,lease)
        # Constructor-owned event profiles are source-selected, never fabricated
        # callback answers. Record67 still uses the original composed service.
        from civ6_host.runtime import xp2_placement_event_source,combat_event_profile
        profiles={
            'foundation':foundation_event_profile.event_profile(core_sha256=XP2_CORE_SHA256,execution_image=image),
            'placement':xp2_placement_event_source.event_profile(core_sha256=XP2_CORE_SHA256,execution_image=image),
            'combat':combat_event_profile.event_profile(XP2_CORE_SHA256,execution_image=image),
        }
        for name,profile in profiles.items():
            setattr(self.owner,name+'_event_profile',profile)
            setattr(self.owner,'_'+name+'_event_profile',profile)
        self.owner._combat_producer_poisoned=self.owner._experience_producer_poisoned=False
        self.saved.xp2_religious_unit_operations=True
        self.saved.xp1_religious_unit_operations=False
        self.token.world_input_prompts={};self.token.trade_feedback=None
        for unit in self.observation['units']:unit.update(owner=0,moves=1)
        self.token.observation=deepcopy(self.observation)
        self.native=native_state(self.observation);self.earned=2;self.native_index=38
        self.choice=dict(kind='spread_religion',unit_id=17,x=0,y=0)
        self.effect_mode='completed';self.emit_added=True;self.deny_request=False
        self.added_owner=0;self.added_unit=17
        self.stack.enter_context(patch.object(adapter,'_catalogue',self.catalogue_native))
        self.stack.enter_context(patch.object(adapter,'_own_entitlement',self.entitlement_native))
        self.stack.enter_context(patch.object(adapter,'observe_player',self.observe_native))

    def catalogue_native(self,prefix,observation):
        if prefix is not self.saved.prefix:raise AssertionError('Foreign catalogue owner')
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
            return super().virtual(core,pointer,slot,rva,result,*args)
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


class XP2ReligiousUnitOperationSessionTests(unittest.TestCase):
    def fixture(self):
        f=Fixture();self.addCleanup(f.close);return f

    def test_parent_strict_independent_option_exact_image_and_source_closure(self):
        with ParentFixture() as f:
            f.captured.reference=REFERENCE
            f.executable=resource_root()/CURRENT_UNSIGNED_LOG_HOST_REFERENCE[0]
            options=dict(input_profile='xp2-lan',official_bundle=dict(zip(('path','sha256'),REFERENCE)))
            self.assertFalse(f.session(**options).xp2_religious_unit_operations)
            for flag in (0,1,None,'true'):
                with self.subTest(flag=flag),self.assertRaises(ValueError):
                    f.session(**options,xp2_religious_unit_operations=flag)
            with self.assertRaises(ValueError):f.session(xp2_religious_unit_operations=True)
            with self.assertRaisesRegex(ValueError,'exact admitted'):
                f.session(**options,xp2_religious_unit_operations=True)
            options.update(xp2_religious_unit_operations=True,execution_image_profile=_PROFILE.id)
            with patch.object(adapter,'require_actions',side_effect=ValueError('source refused')):
                with self.assertRaisesRegex(ValueError,'source refused'):f.session(**options)
            current=f.session(**options)
            for name in ('xp1_religious_unit_operations','xp1_religion_founding','xp1_great_person_activation',
                         'xp1_faith_purchase','trade_diagnostic','standard_trade','governors_diagnostic'):
                self.assertFalse(getattr(current,name))
            from civ6_host.runtime.xp1_session_result import result_provenance
            def reply(session):
                value=reset_reply(session)
                value['outcome']['native_victory'].update(result_provenance(XP2_CORE_SHA256))
                return value
            with patch.object(NativeNetworkSession,'_receive',reply):current.reset()
            path=current.run/'closure.json';self.assertLess(path.stat().st_size,8*1024*1024)
            closure=json.loads(path.read_text(encoding='utf-8'))
            self.assertIs(closure['xp2_religious_unit_operations'],True);self.assertEqual(len(f.spawns),1)
            self.assertNotIn('xp1_religious_unit_operations',closure)
            for path,digest in adapter.source_dependencies(_PROFILE,reference=REFERENCE).items():
                self.assertEqual(closure['pins'][str(Path(path).resolve())],digest)

    def test_worker_preflight_both_captures_exact_flags_pins_and_saved_owner(self):
        check=worker_preflight()
        for reference in (REFERENCE,xp2_bbg_inputs.REFERENCE):
            pins=adapter.source_dependencies(_PROFILE,reference=reference)
            check(True,NS(reference=reference,family='xp2-lan'),_PROFILE,dict(pins=pins))
            for image,family,ref,retained in ((None,'xp2-lan',reference,pins),
                    (_XP1_PROFILE,'xp2-lan',reference,pins),(_PROFILE,'xp1-lan',reference,pins),
                    (replace(_PROFILE),'xp2-lan',reference,pins),(_PROFILE,'xp2-lan',('other','0'*64),pins),
                    (_PROFILE,'xp2-lan',reference,{})):
                with self.subTest(reference=reference[1],family=family,image=image),self.assertRaises(ValueError):
                    check(True,NS(reference=ref,family=family),image,dict(pins=retained))
        for flag in (0,1,None,'true'):
            with self.assertRaises(ValueError):check(flag,None,None,{})
        check(False,None,None,{})
        tree=ast.parse(Path(worker.__file__).read_text(encoding='utf-8'))
        entries=[n for n in ast.walk(tree) if isinstance(n,ast.Compare)
            and ast.unparse(n)=="type(closure.get('xp2_religious_unit_operations', False)) is not bool"]
        self.assertEqual(len(entries),1);expr=compile(ast.Expression(entries[0]),str(worker.__file__),'eval')
        for flag in (True,False,0,1,None,'true'):
            self.assertEqual(eval(expr,{'closure':dict(xp2_religious_unit_operations=flag)}),type(flag) is not bool)
        entries=[n for n in ast.walk(tree) if isinstance(n,ast.Assign)
            and ast.unparse(n)=='saved.xp2_religious_unit_operations = xp2_religious_unit_operations']
        self.assertEqual(len(entries),1)

    def test_view_stock_bbg_levies_permissions_closed_and_checkpoint(self):
        from test_xp2_religious_unit_operations_public import preceding, permissions_preceding, validate
        from test_xp1_religion_beliefs_public import terminal_v11
        from test_session_capabilities import seal
        for index in range(3):
            for levy in (False,True):
                for mode in ('offered','empty','blocked'):
                    with self.subTest(index=index,levy=levy,mode=mode):
                        decisions,obs=preceding(index,levy=levy);prior=deepcopy(decisions)
                        native=native_state(obs,mode);saved=SavedLoadOwner.__new__(SavedLoadOwner)
                        saved.explicit_religious_unit_operations={'stale':True}
                        def query(actual,observation):
                            self.assertIs(actual,saved);self.assertIs(observation,obs)
                            saved.explicit_religious_unit_operations=deepcopy(native);return native
                        with patch.object(adapter,'catalogue',side_effect=query) as queried:
                            view._add_xp2_religious_unit_operations(saved,obs,decisions)
                        queried.assert_called_once();seal(decisions);validate(decisions,obs)
                        self.assertIn(decisions['schema'],network_turn.XP2_RELIGIOUS_UNIT_OPERATIONS_SCHEMAS)
                        self.assertEqual(public.actions(decisions['religious_unit_operations']),adapter.actions(native))
                        self.assertEqual({k:v for k,v in decisions['families'].items() if k not in public.KINDS},prior['families'])
                        restored,receipt=network_turn.checkpoint_catalogue(decisions,prior,obs,core_sha256=XP2_CORE_SHA256)
                        self.assertEqual(restored,prior)
                        self.assertEqual(receipt['added_public_fields'],['religious_unit_operations'])
                        self.assertEqual(receipt['added_action_families'],list(public.KINDS))
                        exact,change=network_turn.checkpoint_catalogue(decisions,decisions,obs,core_sha256=XP2_CORE_SHA256)
                        self.assertEqual(exact,decisions);self.assertIsNone(change)
        for mode in ('active','waiting','closed'):
            for strategic,tactical in ((True,True),(False,True),(True,False),(False,False)):
                with self.subTest(mode=mode,strategic=strategic,tactical=tactical):
                    decisions,obs=permissions_preceding(strategic=strategic,tactical=tactical,state=mode)
                    saved=SavedLoadOwner.__new__(SavedLoadOwner);saved.explicit_religious_unit_operations={'stale':True}
                    unavailable=mode!='active' or not strategic
                    with patch.object(adapter,'catalogue',return_value=native_state(obs)) as query:
                        view._add_xp2_religious_unit_operations(saved,obs,decisions,actions_closed=mode=='closed')
                    seal(decisions);validate(decisions,obs,closed=mode=='closed')
                    self.assertEqual(query.call_count,0 if unavailable else 1)
                    if unavailable:
                        self.assertIsNone(decisions['religious_unit_operations'])
                        self.assertIsNone(saved.explicit_religious_unit_operations)
        prior,obs=preceding();decisions=terminal_v11(prior);before=deepcopy(decisions)
        saved.explicit_religious_unit_operations={'stale':True}
        with patch.object(adapter,'catalogue',side_effect=AssertionError('Closed query')):
            view._add_xp2_religious_unit_operations(saved,obs,decisions,actions_closed=True)
        self.assertEqual(decisions,before);self.assertIsNone(saved.explicit_religious_unit_operations)

    def test_actual_xp2_owner_four_operations_native_refusal_and_unconfirmed_ready(self):
        from civ6_host.runtime import xp1_session_inputs
        cases=[(kind,'completed') for kind in public.KINDS]
        cases += [('spread_religion','refused'),('remove_heresy','unchanged'),('spread_religion','no_added')]
        for kind,mode in cases:
            with self.subTest(kind=kind,mode=mode):
                f=self.fixture();f.choice['kind']=kind
                f.native_index=adapter.source.xp2.expected_ordinal(REFERENCE,kind)
                f.effect_mode='unchanged' if mode=='unchanged' else 'completed'
                f.deny_request=mode=='refused';f.emit_added=mode!='no_added'
                raw=adapter.catalogue(f.saved,f.token.observation)
                decisions=dict(candidates=[dict(action=a) for a in adapter.actions(raw)])
                f.saved._running=False
                self.assertIs(type(f.saved),SavedLoadOwner);self.assertIs(type(f.token),SavedContinuation)
                self.assertIs(type(f.backend.prefix),SavedLoadServices)
                self.assertEqual(f.backend.load_abi.core_sha256,XP2_CORE_SHA256)
                self.assertEqual(f.token.transport.transport_abi.core_sha256,XP2_CORE_SHA256)
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

    def test_continuation_never_inherits_xp1_flag_or_accepts_foreign_owner(self):
        for mode in ('disabled','nonbool','xp1_only','no_owner','foreign_image','bool_id','bool_x','target'):
            f=self.fixture();action=deepcopy(f.choice);session=f.saved
            if mode=='disabled':f.saved.xp2_religious_unit_operations=False
            elif mode=='nonbool':f.saved.xp2_religious_unit_operations=1
            elif mode=='xp1_only':f.saved.xp2_religious_unit_operations=False;f.saved.xp1_religious_unit_operations=True
            elif mode=='no_owner':session=None
            elif mode=='foreign_image':f.backend.core._civ6_host_execution_image=_XP1_PROFILE
            elif mode=='bool_id':action['unit_id']=True
            elif mode=='bool_x':action['x']=True
            else:action['target_id']=19
            with self.subTest(mode=mode),self.assertRaises((ValueError,RuntimeError)):
                f.token.execute(action,session=session)
            self.assertEqual(f.machine,[]);f.close()

    def test_worker_rejects_xp1_receipt_and_corrupt_effect_attribution(self):
        f=self.fixture();before=deepcopy(f.token.observation);after=deepcopy(before)
        old=deepcopy(f.native['units'][0]);new=deepcopy(old);new['spread_charges']-=1
        receipt=dict(archive=dict(archive_sha256='a'*64,size_bytes=28,operation_index=38,parameters={}),
            operation_hash=adapter.source.OPERATIONS[f.choice['kind']][1],operation_added_sequence=1,
            consumed_before=0,consumed_after=1,unit_before=old,unit_after=new,
            beliefs_earned_before=None,beliefs_earned_after=None,
            inquisition_started_before=False,inquisition_started_after=False)
        effect=dict(status='completed',observation=deepcopy(after),action=deepcopy(f.choice),
                    source_sha256=adapter.source_for(_PROFILE)[1],receipt=receipt)
        result=dict(action=deepcopy(f.choice),effect=effect,observation_before=before,observation_after=after)
        decisions=dict(candidates=[dict(action=f.choice)])
        from civ6_host.runtime import xp1_session_inputs
        changes=(lambda r:None,lambda r:r['effect'].update(source_sha256=adapter.SOURCE[1]),
            lambda r:r['effect']['action'].update(unit_id=True),
            lambda r:r['effect']['receipt'].update(operation_added_sequence=0),
            lambda r:r['effect']['receipt']['unit_before'].update(unit_id=19),
            lambda r:r['effect']['receipt']['unit_after'].update(spread_charges=3))
        for index,change in enumerate(changes):
            value=deepcopy(result);change(value)
            with (self.subTest(index=index),patch.object(view,'read',return_value=({},f.token.observation,decisions)),
                  patch.object(f.saved,'execute',return_value=value),
                  patch.object(xp1_session_inputs,'_write_once',return_value={'fixture':True})):
                if index:
                    with self.assertRaises(RuntimeError):worker._execute_xp1(f.saved,f.choice,0,0,Path('fixture-closure.json'))
                else:self.assertEqual(worker._execute_xp1(f.saved,f.choice,0,0,Path('fixture-closure.json'))['status'],'completed')


if __name__=='__main__':unittest.main()
