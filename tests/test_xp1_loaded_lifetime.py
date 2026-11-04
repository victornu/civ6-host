import ast
import copy
import ctypes as C
from contextlib import nullcontext
import hashlib
import struct
from pathlib import Path
from types import SimpleNamespace as NS
import threading
import unittest
from unittest.mock import Mock,patch

from civ6_host.runtime import xp1_loaded_lifetime as life
from civ6_host.runtime import xp1_cache_publication as publication
from civ6_host.runtime import xp1_load_capability as capability
from civ6_host.runtime import xp1_load_options as options
from civ6_host.runtime import saved_load_job_observer as jobs
from civ6_host.runtime import loaded_cache_publication as cache
from civ6_host.runtime.native import native_official_postload as official
import test_xp1_postload_candidate as post_fixture

NATIVE=Path(__file__).resolve().parents[1]/'src/civ6_host/runtime/native'

def snapshot():
    return dict(schema=jobs.SCHEMA,profile=jobs.PROFILE,source_proof_sha256=jobs.SOURCE[1],
        stable_read=True,memory_modified=False,concurrent_scheduler_supported=False,
        native_introspection_only=True,native_methods_called=True,spawn_active=0,
        registry_lock_raw=0,pending_items=0,submission_sequence=23,owner_thread_id=2,
        source_build={'host_sha256':'1'*64},core_identity={'sha256':life.XP1_CORE_SHA256,'profile':2},
        current_executable={'identity':'offline'},host_sha256='1'*64,
        slots=[dict(handle=i,occupied=i in (2,3),count=0,items=[]) for i in range(1,65)],
        groups=[dict(pointer=0x8000,owner=0x9000,pending=0)])

def graph():
    b,a,lease,post=post_fixture.Post160CandidateTests().graph()
    lease.begin_post160(post);lease.finish_post160(post)
    b.stage='post160-candidate-observed-awaiting-controlled-stop';b.busy=False
    post.attempted=post.native_call_attempted=True
    post.candidate_diagnostics={'void_return_ignored':True}
    lease.identity={'inner':0x400000000};a.publisher._facades=object()
    runtime=NS(closed=False,database_bound=True,configuration_bound=True,locale_bound=True)
    runtime.registry=NS(contexts={},_claims={})
    b.host=NS(execution_lock=NS(),context_teardown_receipt={'installed':True})
    b.owner=NS(closed=False,require_context=Mock())
    b.prefix.runtime=runtime;b.prefix.game_child=object();b.prefix.closed=False
    b.prefix.check=Mock();b.emit=Mock()
    previous=Mock();previous._native_unavailable=('host',0xC0)
    b.prefix.status_messages=NS(previous=(0,(9,previous)),closed=False)
    b.prefix.cache_facades=NS(closed=False)
    b.prefix.view_publisher._closed=False
    return b,a,lease,post

def token_graph():
    b,a,lease,post=graph()
    with patch.object(official,'validate_owner'),patch.object(life,'verify_live',return_value={}):
        token=life.LoadedLifetime(b,post)
    return b,a,lease,post,token

class LifetimeTests(unittest.TestCase):
    def test_frozen_source_and_recursive_non_json_dependencies(self):
        proof=life.source();refs=life.source_dependencies()
        self.assertTrue(proof['contract']['unload_before_destroy'])
        self.assertGreater(len(refs),5)
        self.assertTrue(any(Path(p).suffix.lower()!='.json' for p in refs))
        for path,digest in refs.items():
            self.assertEqual(hashlib.sha256(Path(path).read_bytes()).hexdigest(),digest)

    def test_verify_live_checks_pinned_instructions_and_slots(self):
        proof=life.source();memory={};base=0x200000000
        bodies=list(proof['bodies'].values())
        for ref in proof['references']:
            if 'deferred-load-static' in ref['path']:
                old=life._source((ref['path'],ref['sha256']))['functions']['xp1']
                bodies.extend(old[n] for n in ('inner_destroy','game_teardown','destroy_host_registry'))
        for body in bodies:
            for fragment in life._body(body)['fragments']:
                for row in fragment['instructions']:
                    for i,v in enumerate(bytes.fromhex(row['bytes'])):
                        memory[base+int(row['va'],16)-0x180000000+i]=v
        for key,value in proof['slots'].items():
            vt,slot=(int(v,16) for v in key.split('+'))
            for i,v in enumerate((base+int(value,16)).to_bytes(8,'little')):memory[base+vt+slot+i]=v
        read=lambda addr,n:bytes(memory[addr+i] for i in range(n))
        b=NS(core=NS(_handle=base),runtime=NS(read=read))
        self.assertEqual(life.verify_live(b),proof)
        memory[base+0x8a8df0+0x48]^=1
        with self.assertRaisesRegex(ValueError,'slot changed'):life.verify_live(b)

    def test_publication_lease_exact_owner_and_single_attempt(self):
        b,a,lease,post=graph();attempt=publication.SavedCachePublication(post)
        lease.begin_publication(attempt)
        self.assertEqual(b.stage,publication.ACTIVE_STAGE)
        self.assertIs(b._saved_load_job_cache_owner,lease)
        with self.assertRaisesRegex(ValueError,'replay'):lease.begin_publication(attempt)
        attempt.owner=object()
        with self.assertRaisesRegex(ValueError,'completed post160'):lease._check()
        attempt.owner=b
        lease.finish_publication(attempt)
        self.assertFalse(b.busy);self.assertEqual(b.stage,publication.COMPLETED_STAGE)
        self.assertTrue(lease.publication_finished)
        self.assertFalse(hasattr(b,'_saved_load_job_cache_owner'))

    def test_lifetime_requires_exact_finished_owner_and_refusal_restore(self):
        b,a,lease,post=graph()
        with patch.object(official,'validate_owner'),patch.object(life,'verify_live') as live:
            with self.assertRaisesRegex(ValueError,'completed native'):life.LoadedLifetime(b,object())
            lease.post160_finished=False
            with self.assertRaisesRegex(ValueError,r'completed \+160'):life.LoadedLifetime(b,post)
            lease.post160_finished=True
            b.prefix.status_messages.previous=(0,(9,Mock()))
            with self.assertRaisesRegex(ValueError,'explicit refusal'):life.LoadedLifetime(b,post)
            live.assert_not_called()

    def test_saved_ui_view_resolves_through_xp1_continuation_publication(self):
        from civ6_host.runtime.xp1_cache_publication import SavedCachePublication
        from civ6_host.runtime.xp1_continuation import SavedContinuation
        from civ6_host.runtime.xp1_ui_binding import SavedPlayerView, SOURCE as ui_source

        b,a,lease,post,token=token_graph()
        publication=SavedCachePublication(post)
        continuation=SavedContinuation.__new__(SavedContinuation)
        continuation.publication=publication
        token.completed=continuation

        child=0x1234
        view=SavedPlayerView.__new__(SavedPlayerView)
        view.owner=b;view.prefix=b.prefix;view.runtime=token.runtime
        view.publication=publication;view.child=child
        view.attempted=view.completed=True
        view.core_sha256=life.XP1_CORE_SHA256;view.source_sha256=ui_source[1]
        view.result=dict(core_sha256=life.XP1_CORE_SHA256,source_sha256=ui_source[1],binding=dict(
            native_ui_registration_returned=True,source_sha256=ui_source[1],method_rva='0x4cbe50'))
        b._xp1_player_view=view;b.prefix.ui_child=child
        token.player_view=view;token.ui_child=child;token.ui_source_dependencies=None
        token.runtime._xp1_ui_bind_entered=True
        token.runtime.registry.validate=Mock(side_effect=lambda pointer:pointer)

        self.assertIs(token._validate_saved_player_view(),view)
        self.assertTrue(token.ui_source_dependencies)
        view.publication=continuation
        with self.assertRaisesRegex(ValueError,'completed child owned by this publication'):
            token._validate_saved_player_view()

    def test_release_and_observer_require_exact_token_and_phase(self):
        b,a,lease,post,token=token_graph();token.phase='wrappers'
        with patch.object(official,'validate_owner'):lease.begin_release(token)
        observer=jobs.SavedLoadJobObserver.__new__(jobs.SavedLoadJobObserver);observer.backend=b
        b.snapshot_phase='before'
        self.assertTrue(observer._exclusive())
        self.assertIs(lease.authorize_publisher_close(a.publisher),token)
        with self.assertRaisesRegex(ValueError,'no qualified'):lease.authorize_publisher_close(object())
        b._loaded_lifetime=NS(owner=b,check_job_snapshot=lambda:True)
        self.assertFalse(observer._exclusive())
        b._loaded_lifetime=token;b.stage='loaded-lifetime-destroying';token.phase='destroy'
        self.assertFalse(observer._exclusive())
        with self.assertRaisesRegex(ValueError,'snapshot outside'):token.check_job_snapshot()
        b.destroyed=True
        self.assertFalse(observer._exclusive())

    def test_host_binding_snapshot_check_is_retained(self):
        # Exact original guard remains present; lifetime is not permission to
        # replace callbacks silently while releasing the two facade owners.
        body=Path(cache.__file__).read_text()
        self.assertIn("tuple(table)!=snapshot",body)
        self.assertIn("b.host._slot_bindings!=self.bindings",body)

    def test_cleanup_jobs_allow_only_quiescent_removals(self):
        before=snapshot();after=copy.deepcopy(before)
        after['slots'][1]['occupied']=False;after['groups']=[]
        report=life.validate_jobs_shutdown(before,after)
        self.assertEqual(report['removed_empty_handles'],[2])
        self.assertFalse(report['ledger_reconciled'])
        self.assertFalse(report['post_destroy_snapshot_available'])
        after=copy.deepcopy(before);after['slots'][3]['occupied']=True
        with self.assertRaisesRegex(ValueError,'created a job list'):life.validate_jobs_shutdown(before,after)
        after=copy.deepcopy(before);after['submission_sequence']+=1
        with self.assertRaisesRegex(ValueError,'identity/submission'):life.validate_jobs_shutdown(before,after)
        after=copy.deepcopy(before);after['groups'][0]['owner']+=8
        with self.assertRaisesRegex(ValueError,'owned job group'):life.validate_jobs_shutdown(before,after)
        after=copy.deepcopy(before);after['slots'][1]['count']=1
        with self.assertRaisesRegex(ValueError,'pending slot'):life.validate_jobs_shutdown(before,after)

    def test_after_destroy_reads_module_globals_only(self):
        b,a,lease,post,token=token_graph()
        b.busy=True;b.destroyed=True;token.destroy_called=True;token.phase='destroy'
        reads=[]
        def read(address,size):
            self.assertIn(address,[b.core._handle+x for x in (0x9f2640,0x9f2648,0x9f2650,0x9f2628,0x9f22e0)])
            self.assertEqual(size,8);reads.append(address);return bytes(8)
        b.runtime.read=read
        token.after_destroy(b)
        self.assertEqual(len(reads),5);self.assertEqual(token.phase,'services')
        self.assertTrue(token.destroy_returned)

    def test_detached_options_allow_only_actual_getter_and_destructor(self):
        b,a,lease,post,token=token_graph()
        b.busy=True;b.destroyed=True;token.destroy_returned=True;token.phase='options'
        borrower=options._LoadOptionsBorrower(b)
        b.host._saved_load_performance_options=NS(borrower=borrower,provider=NS(poisoned=False,closed=False))
        with patch.object(options.setup,'_invoke',return_value=7) as invoke:
            self.assertEqual(borrower._invoke(0x845600,C.c_void_p,(C.c_void_p,),0x8000),7)
            self.assertEqual(borrower._invoke(0x844580,None,(C.c_void_p,),0x8000),7)
            with self.assertRaisesRegex(ValueError,'detached context'):borrower._invoke(0x845601,None,(C.c_void_p,),0x8000)
            self.assertEqual(invoke.call_count,2)
            token.phase='closed'
            with self.assertRaisesRegex(ValueError,'detached context'):borrower._check()

    def test_detached_player_service_requires_own_token_and_no_live_borrower(self):
        from civ6_host.runtime.player_notification_service import PlayerNotificationService
        b,a,lease,post,token=token_graph()
        b.busy=True;b.destroyed=True;token.destroy_returned=True;token.phase='services'
        service=PlayerNotificationService.__new__(PlayerNotificationService)
        service.host=b.host;service.core=b.core;service.context=b.context
        service.thread=threading.get_ident();service.closed=service.quarantined=False
        service.depth=0;service._a0_event_owner=None;service.core_lock=token.lock
        service.lock_slots={0x30:1,0x38:2,0x40:3,0x48:4}
        b.host.vtable=[0]*10
        for slot,value in service.lock_slots.items():b.host.vtable[slot//8]=value
        token.lock.calls={'owned':Mock(return_value=0)}
        b.host._player_notification_owner=service;b.prefix.player_queries=service
        service.check=Mock(side_effect=AssertionError('must not read freed context'))
        service._a0_event_owner=object()
        with self.assertRaisesRegex(ValueError,'consumers'):service.close(loaded_lifetime=token)
        service._a0_event_owner=None
        with self.assertRaisesRegex(ValueError,'Exact loaded lifetime'):service.close(loaded_lifetime=object())
        service.close(loaded_lifetime=token)
        service.check.assert_not_called();self.assertTrue(service.closed)
        self.assertIsNone(b.host._player_notification_owner)

    def test_unloaded_drain_refuses_cache_feedback_without_consuming_any_record(self):
        b,a,lease,post,token=token_graph()
        token.phase='unloaded';token.unload_returned=True
        token._unloaded=Mock();token.check_a0_owner=Mock()
        from civ6_host.runtime.native.native_event_fdf12323 import RECORD_SIZE,RECORD_TYPE
        record=bytearray(RECORD_SIZE);struct.pack_into('<II',record,0,RECORD_SIZE,RECORD_TYPE)
        queue=NS(pending=[bytes(record)],_draining_empty_receivers=False,
                 host_notification_counter=0,host_metadata_counter=0)
        consumer=NS(handles_record=lambda kind:kind in (0x5f,0x62,0xa0),
                    empty_receiver_state=dict(observer_registered=False,state_pointer_nonnull=True,
                    pre_hook=None,post_hook=None,subscriber_count=0,state_flags=0))
        b.prefix.deferred_events=queue;b.prefix.event_arguments=NS(consumer=consumer)
        token.check_deferred_drain(queue)
        for kind in (0x5f,0x62):
            row=bytearray(112);struct.pack_into('<II',row,0,len(row),kind);queue.pending.append(bytes(row))
        token.check_deferred_drain(queue)
        row=bytearray(128);struct.pack_into('<II',row,0,len(row),0x113);queue.pending.append(bytes(row))
        original=list(queue.pending)
        with self.assertRaisesRegex(ValueError,'unqualified receiver'):token.check_deferred_drain(queue)
        self.assertEqual(queue.pending,original)
        queue.pending.pop();token.phase='destroy'
        with self.assertRaisesRegex(ValueError,'unqualified receiver'):token.check_deferred_drain(queue)

    def test_general_destroy_join_retains_provider_and_reports_native_return(self):
        import time
        tree=ast.parse((NATIVE/'native_checkpoint_configuration_only.py').read_text())
        cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='_NativeBackend')
        method=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='destroy_context')
        namespace={'time':time};exec(compile(ast.Module(body=[method],type_ignores=[]),'offline','exec'),namespace)
        b=NS(profile=NS(ruleset='xp1'),owner=NS(closed=False),host=NS(context_teardown_receipt={'installed':True}),
             context=0x300000000,destroy=Mock(),destroyed=False,emit=Mock())
        with self.assertRaisesRegex(ValueError,'provider closed'):namespace['destroy_context'](b)
        b.destroy.assert_not_called()
        token=life.LoadedLifetime.__new__(life.LoadedLifetime);token.owner=b
        seen=[];token.before_destroy=lambda owner:seen.append(('before',owner.destroyed))
        token.after_destroy=lambda owner:seen.append(('after',owner.destroyed))
        namespace['destroy_context'](b,loaded_lifetime=token)
        self.assertEqual(seen,[('before',False),('after',True)])
        b.destroy.assert_called_once_with(b.context)
        self.assertFalse(b.owner.closed)
        self.assertFalse(b.emit.call_args.kwargs['configuration_only'])

    def test_lifetime_metadata_does_not_enable_unrelated_phases(self):
        b,a,lease,post,token=token_graph();b.busy=True
        for phase in ('unload','unloaded','destroy'):
            token.phase=phase;self.assertTrue(capability._lifetime_scope_owner(b))
        token.phase='services'
        with self.assertRaisesRegex(ValueError,'inactive'):capability._lifetime_scope_owner(b)
        b._loaded_lifetime=NS(owner=b,check_metadata_scope=lambda:True)
        with self.assertRaisesRegex(ValueError,'Exact loaded lifetime'):capability._lifetime_scope_owner(b)

    def test_extractor_keeps_base_route_and_invokes_real_unload_before_destroy(self):
        tree=ast.parse((NATIVE/'native_host.py').read_text())
        function=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='release_game_services')
        from civ6_host.runtime.paths import resource_root
        original=ast.parse((resource_root()/'civ6rl/native_host.py').read_text())
        for node in ast.walk(original):
            if isinstance(node,ast.ImportFrom) and node.module and node.module.startswith('civ6rl.'):
                node.module='civ6_host.runtime.native.'+node.module[len('civ6rl.'):]
        old=next(n for n in original.body if isinstance(n,ast.FunctionDef) and n.name==function.name)
        def canonical_body(body):
            rows=[]
            for node in body:
                if isinstance(node,ast.ImportFrom):
                    module=node.module
                    if node.level==1:module='civ6_host.runtime.native.'+module
                    rows.extend(ast.dump(ast.ImportFrom(module=module,names=[alias],level=0)) for alias in node.names)
                else:rows.append(ast.dump(node))
            return rows
        self.assertEqual(canonical_body(function.body[2:]),canonical_body(old.body[1:]))
        token=life.LoadedLifetime.__new__(life.LoadedLifetime)
        token.before_unload=Mock(return_value=0x4be690);token.after_unload=Mock()
        namespace={'C':C};exec(compile(ast.Module(body=[function],type_ignores=[]),'offline','exec'),namespace)
        core=NS(_handle=0x200000000);native=Mock();binder=Mock(return_value=native)
        with patch.object(C,'WINFUNCTYPE',return_value=binder) as signature:
            namespace[function.name](core,0x300000000,Mock(),loaded_lifetime=token)
        signature.assert_called_once_with(None,C.c_void_p)
        binder.assert_called_once_with(core._handle+0x4be690)
        native.assert_called_once_with(0x300000000);token.after_unload.assert_called_once()

    def drive_close(self,fail=None):
        b,a,lease,post,token=token_graph();events=[];before=snapshot();after=copy.deepcopy(before)
        after['slots'][1]['occupied']=False;after['groups']=[]
        b.jobs_snapshot=Mock(side_effect=[before,after]);b.control=Mock()
        p=token.prefix
        p.deferred_events=NS(drain=Mock(return_value=0),_sequence=0,consumed_count=0)
        p.event_arguments=NS(consumer=NS(enable_district_events=Mock()))
        def close_owner(obj,key,name):
            def fn(*args,**kwargs):
                events.append(name)
                if fail==name:raise ValueError('injected '+name)
                setattr(obj,key,True)
            return fn
        p.cache_facades.close=close_owner(p.cache_facades,'closed','cache_facades')
        p.view_publisher.close=close_owner(p.view_publisher,'_closed','publisher')
        p.status_messages.close=close_owner(p.status_messages,'closed','status')
        p.close=close_owner(p,'closed','services')
        b.close_owner=close_owner(b.owner,'closed','configuration')
        provider=NS(closed=False,poisoned=False)
        def close_options(**kwargs):
            self.assertTrue(b.destroyed);self.assertEqual(token.phase,'options')
            self.assertTrue(kwargs['context_destroyed']);events.append('options')
            return {'native_destructor_returned':True,'guards_intact':True,'values':{}}
        provider.close=close_options;b.host._saved_load_performance_options=NS(provider=provider)
        token.runtime.unbind_services=lambda:events.append('unbind')
        token.runtime.registry.release=lambda child:events.append('child_release')
        token.runtime.close=close_owner(token.runtime,'closed','lua')
        token.lock.close=lambda:events.append('lock')
        def database():events.append('database');return False if fail=='database' else True
        b.finish_database=database
        def unload(core,context,emit,*,loaded_lifetime):
            self.assertIs(loaded_lifetime,token);self.assertEqual(token.before_unload(core,context),0x4be690)
            self.assertFalse(p.closed);self.assertFalse(b.owner.closed);self.assertFalse(token.runtime.closed)
            events.append('unload')
            if fail=='unload':raise ValueError('injected unload')
            token.after_unload()
        def destroy(*,loaded_lifetime):
            token.before_destroy(b);events.append('destroy');b.destroyed=True;token.after_destroy(b)
        b.destroy_context=destroy
        b.runtime.read=lambda address,size:bytes(size)
        unloaded=dict(game_object_null=True,cache_service_null=True,rules_manager_null=True)
        with patch.object(official,'validate_owner'),patch.object(token,'_unloaded',return_value=unloaded), \
             patch('civ6_host.runtime.native.native_host.release_game_services',side_effect=unload), \
             patch.object(capability,'capability_source_scope',return_value=nullcontext()):
            if fail:
                with self.assertRaisesRegex(ValueError,'injected|Database shutdown'):token.close()
            else:token.close()
        return b,lease,token,events

    def test_close_orders_three_releases_unload_destroy_and_owned_services(self):
        b,lease,token,events=self.drive_close()
        self.assertEqual(events,['cache_facades','publisher','status','unload','destroy','services',
            'options','configuration','unbind','child_release','lua','lock','database'])
        self.assertTrue(token.report['native_unload_called']);self.assertTrue(token.report['native_destroy_called'])
        self.assertFalse(token.report['cleanup_inferred_from_process_exit'])
        self.assertFalse(token.report['public_loaded_lifetime_admitted'])
        self.assertFalse(token.report['jobs_transition']['ledger_reconciled'])
        self.assertEqual(len(token.report['steps']),9)
        with self.assertRaisesRegex(ValueError,'cannot replay'):token.close()

    def test_failure_stops_at_first_error_and_poison_prevents_retry(self):
        for name in ('status','unload','database'):
            with self.subTest(name=name):
                b,lease,token,events=self.drive_close(fail=name)
                self.assertEqual(events[-1],name);self.assertTrue(token.poisoned)
                self.assertTrue(lease.poisoned);self.assertTrue(b.poisoned)
                self.assertEqual(b.stage,'poisoned');self.assertIsNone(token.report)
                with self.assertRaisesRegex(ValueError,'cannot replay'):token.close()
