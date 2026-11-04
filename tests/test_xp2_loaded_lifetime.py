"""Actual shared registry/FIFO owners, with native effects confined to fixtures."""
import ctypes as C
import hashlib
from contextlib import nullcontext
from pathlib import Path
import struct
import threading
from types import SimpleNamespace as NS
import unittest
from unittest.mock import Mock,patch

from civ6_host.runtime import xp1_loaded_lifetime as life
from civ6_host.runtime import xp2_loaded_lifetime_source as source
from civ6_host.runtime import xp1_load_capability as capability
from civ6_host.runtime import saved_load_job_observer as jobs
from civ6_host.runtime.configuration_profiles import XP2_CORE_SHA256
from civ6_host.runtime.configuration_profiles import XP1_CORE_SHA256
from civ6_host.runtime.saved_load_profiles import profile_for_sha
from civ6_host.runtime.saved_load_services import SavedLoadServices
from civ6_host.runtime.deferred_service import DeferredService
from civ6_host.runtime.control_input_service import ControlInputService
from civ6_host.runtime.event_argument_service import EventArgumentService
from civ6_host.runtime.native.native_core_lock import NativeCoreLock
from civ6_host.runtime.native.native_official_load import OfficialLoadBackend
from civ6_host.runtime.xp2_load_options_capability_profile import performance_profile
import test_xp2_prepare_services as prepare_fixture
from test_control_input_service import Code
from test_a0_family_service import PROFILE
from test_xp1_loaded_lifetime import snapshot


class RawLifetimeTests(unittest.TestCase):
    def graph(self):
        f=prepare_fixture.XP2PrepareServicesTests();h=f.fixture();f.invoke();self.f=f
        b=OfficialLoadBackend.__new__(OfficialLoadBackend)
        b.host=h;b.core=f.core;b.context=f.context;b.profile=f.profile
        b.load_abi=profile_for_sha(XP2_CORE_SHA256);b.configuration_abi=NS(core_sha256=XP2_CORE_SHA256)
        for vt,slot,target in b.load_abi.virtual_targets:f.q(f.base+vt+slot,f.base+target)
        f.q(f.inner+0xe00,0x8888)
        for _,rva,raw in source.fragments(source.source()):f.put(f.base+rva,raw)
        from civ6_host.runtime import xp2_district_removed_source as district
        for body in district.source()['bodies'].values():
            for fragment in body['fragments']:f.put(f.base+int(fragment['start_rva'],16),bytes.fromhex(fragment['raw_hex']))
        for table,slots in district.TABLES.values():
            for slot,rva in slots:f.q(f.base+table+slot,f.base+rva)
        for key,value in source.SLOTS.items():
            vt,slot=(int(s,16) for s in key.split('+'));f.q(f.base+vt+slot,f.base+int(value,16))
        for rva in source.source()['contract']['unloaded_zero_global_rvas']:f.q(f.base+rva,0)
        f.q(f.base+0xb8aa68,f.archive_pointer-0x20)
        f.put(f.archive_pointer-0x20+0x2a4,b'\1');f.q(f.inner+0x1a68,0)
        b.thread=(threading.get_ident(),2);b.runtime=NS(thread=lambda:b.thread,read=f.read)
        b.destroyed=b.poisoned=b.busy=False;b.stage='raw-loaded';b.snapshot_phase='postflight'
        b.load_attempted=b._saved_load_candidate=True;b.emit=Mock()
        from civ6_host.runtime.native.native_official_bundle import PreparedBundle
        b.captured_bundle=PreparedBundle.__new__(PreparedBundle)
        object.__setattr__(b.captured_bundle,'content_profile',{'engine':{'gamecore_sha256':XP2_CORE_SHA256}})
        b.inputs=NS(game=b'complete saved bytes');b.reader=NS(transport=NS(closed=True,cursor=len(b.inputs.game)))
        b.load_source_sha256='fixture-load-source';b.raw_load_result=dict(status=0,bytes_consumed=len(b.inputs.game),
            game_initialized=1,load_source_sha256=b.load_source_sha256)
        b.game_flag=lambda:f.read(f.archive_pointer-0x20+0x2a4,1)[0]
        b.bound_identity=b.topology(game_required=True)
        b.owner=NS(closed=False,require_context=Mock())
        lock=NativeCoreLock.__new__(NativeCoreLock);lock.host=h;lock.calls={'owned':Mock(return_value=0)}
        lock.close=Mock();h.execution_lock=lock
        p=SavedLoadServices.__new__(SavedLoadServices)
        p.backend=b;p.host=h;p.core=b.core;p.context=b.context;p.core_sha256=XP2_CORE_SHA256
        p.closed=p.quarantined=False;p.game_child=object();p.emit=b.emit
        p.runtime=NS(closed=False,service_owner=h,database_bound=True,configuration_bound=True,locale_bound=True,
            registry=NS(validate=Mock(),_check=Mock(),contexts={},_claims={},release=Mock()),unbind_services=Mock())
        p.runtime.close=lambda:setattr(p.runtime,'closed',True)
        b.prefix=p;h._saved_load_services=p
        p.contexts=NS(names={},depth=0,lock_depth=0,quarantined=False,receiver=123,check=Mock(),close=Mock())
        p.events=NS(dispatch_depth=0,script_arguments=NS(live_count=0),_check=Mock(),close=Mock())
        p.map_arguments=NS(live={},check=Mock(),close=Mock());p.maps=NS(close=Mock());p.scalars=NS(close=Mock())
        p.application_mirror=NS(close=Mock())
        # Native instructions/lock bytecode are individually tested elsewhere;
        # the shared transport/controller/A0 objects here are actual instances.
        for name in ('cache_update_profiles.verify_dispatch_live','cache_update_profiles.verify_notification_live',
                     'xp2_preload_source.verify_control','event_argument_source.verify_host_live',
                     'event_argument_source.verify_reader_live'):
            patcher=patch('civ6_host.runtime.'+name,return_value={});patcher.start();self.addCleanup(patcher.stop)
        for name in ('control_input_service.NativeControllerCode','native.native_controller_state.NativeControllerCode'):
            patcher=patch('civ6_host.runtime.'+name,Code);patcher.start();self.addCleanup(patcher.stop)
        d=DeferredService(h,b.core,b.context,core_sha256=XP2_CORE_SHA256,read=f.read,emit=b.emit,
            optional_preprocessor=None,queue_metadata_service=None)
        ctl=ControlInputService(h,b.core,b.context,d,core_sha256=XP2_CORE_SHA256,local_player_id=0,read=f.read,emit=b.emit)
        args=EventArgumentService(h,b.core,b.context,d,core_sha256=XP2_CORE_SHA256,read=f.read,emit=b.emit,
            normalizer_transform=None,dynamic_registrations=())
        a0=args.install_consumers(receiver_state=PROFILE,pre_turn_immediate_state=PROFILE,entity_listener_count=0)
        a0.enable_controller_events(ctl)
        p.deferred_events=d;p.control_inputs=ctl;p.event_arguments=args
        provider=NS(poisoned=False,closed=False,proof=performance_profile()[1])
        borrower=NS(backend=b,base=f.base,runtime=b.runtime,read=b.runtime.read)
        h._saved_load_performance_options=NS(provider=provider,borrower=borrower)
        self.events=[]
        def options_close(**kw):
            token=b._loaded_lifetime;self.assertTrue(kw['context_destroyed'])
            for rva in (None,0x99f680,0x99e5d0):token.check_options_cleanup(borrower,rva)
            provider.closed=True;self.events.append('options');return {'native_destructor_returned':True}
        provider.close=options_close
        def close_owner():b.owner.closed=True;self.events.append('configuration')
        b.close_owner=close_owner;b.finish_database=lambda:self.events.append('database') or True
        return b

    def queue(self,b,kind=0x5f):
        row=bytearray(112);struct.pack_into('<II',row,0,len(row),kind)
        # Fixture native producer supplies the serialized row and sequence;
        # production consumption still runs the actual shared FIFO codec.
        b.prefix.deferred_events._sequence+=1
        struct.pack_into('<I',row,8,b.prefix.deferred_events._sequence)
        b.prefix.deferred_events.pending.append(bytes(row))
        return bytes(row)

    def native_unload(self,b,*,retain_archive=False,unknown_record=False,district_removed=False):
        f=self.f;token=b._loaded_lifetime
        self.assertEqual(token.before_unload(b.core,b.context),0x591860)
        self.events.append('unload')
        if district_removed:
            from civ6_host.runtime import a0_district_removed as event
            # Native Unload clears the flag before its real callback. Only
            # the native query and argument-tree read are replaced here.
            f.put(f.archive_pointer-0x20+0x2a4,b'\0')
            descriptor,position=0x990000,0x990100
            f.put(descriptor,struct.pack('<HHI',0,3,65536));f.put(position,struct.pack('<ii',28,18))
            scalar=lambda tag,value:struct.pack('<H6xQII',tag,value,0,0)
            pointer=lambda tag,value:struct.pack('<H6xQII',tag,value,8,0x21000001)
            fields={0xf343dc5a:pointer(0x400,descriptor),0x8c468e3c:pointer(0,position),
                    0xa1e5a149:scalar(3,0),0xa1fbc372:scalar(2,0),0xd6fcf3e4:scalar(2,0)}
            def player(context,owner):
                self.assertEqual((context,owner),(b.context,0));self.assertEqual(b.game_flag(),0)
                self.events.append('native-null-player');return None
            api={name:Mock(side_effect=AssertionError('Unreached native item query')) for name in event.ENTRIES}
            api['get_player']=player
            with patch.object(b.prefix.event_arguments.reader,'fields',return_value=fields),patch.object(event,'_api',return_value=api):
                self.assertEqual(b.prefix.event_arguments.dispatch(b.host.pointer,event.codec.EVENT_KIND,0x991000),0)
            self.assertEqual(struct.unpack_from('<I',b.prefix.deferred_events.pending[-1],4)[0],0xa0)
        if not retain_archive:
            b.host._xp2_prepare_services.remove_archive(C.addressof(b.host.descriptor_object),f.archive_pointer)
        f.q(f.inner+0x60,0);f.q(f.inner+0x1a68,0)
        for rva in token.proof['contract']['unloaded_zero_global_rvas']:f.q(f.base+rva,0)
        self.queue(b,0x113 if unknown_record else 0x5f)
        token.after_unload()

    def native_destroy(self,b,*,retain_type=False):
        token=b._loaded_lifetime;token.before_destroy(b)
        self.events.append('destroy')
        for name in b.host._xp2_prepare_services.names[:-1] if retain_type else b.host._xp2_prepare_services.names:
            descriptor,_=self.f.string(name)
            b.host._remove_type(C.addressof(b.host.registrar_object),descriptor)
        for rva in token.proof['contract']['destroyed_zero_global_rvas']:self.f.q(self.f.base+rva,0)
        b.destroyed=True
        old=b.runtime.read
        def no_freed_read(address,size):
            if address<self.f.base:raise AssertionError('read freed native object')
            return old(address,size)
        b.runtime.read=no_freed_read
        b.host._saved_load_performance_options.borrower.read=b.runtime.read
        token.after_destroy(b)

    def drive(self,b,**unload_options):
        def snapshot_call(phase):
            b.snapshot_phase=phase;b._loaded_lifetime.check_job_snapshot()
            self.events.append('jobs-'+phase)
            result=snapshot();result['source_proof_sha256']=jobs.XP2_SOURCE[1]
            result['core_identity']={'sha256':XP2_CORE_SHA256,'profile':3}
            return result
        b.jobs_snapshot=snapshot_call
        b.destroy_context=lambda **kw:self.native_destroy(b)
        with patch.object(capability,'capability_source_scope',return_value=nullcontext()), \
             patch('civ6_host.runtime.native.native_host.release_game_services',
                   side_effect=lambda *a,**k:self.native_unload(b,**unload_options)):
            return life.close_raw_loaded(b)

    def test_source_pins_full_bodies_late_branch_and_dispatch(self):
        refs=life.source_dependencies(XP2_CORE_SHA256)
        self.assertGreater(len(refs),15)
        for path,digest in refs.items():self.assertEqual(hashlib.sha256(Path(path).read_bytes()).hexdigest(),digest)
        b=self.graph();self.assertEqual(life.verify_live(b),source.source())
        body=source.source()['bodies']['event_interface_clear']
        self.assertEqual(body['boundary_method'],'complete-reachable-leaf-cfg-v1')
        last=body['fragments'][-1];address=self.f.base+int(last['start_rva'],16)+last['length']-1
        self.f.put(address,b'\xcc')
        with self.assertRaisesRegex(ValueError,'code differs'):life.verify_live(b)

    def test_postload_source_closure_and_live_verification_cover_all_selected_families(self):
        from civ6_host.runtime import xp2_loaded_lifetime_source as postlife
        from civ6_host.runtime import xp2_postload_source, xp2_cache_source
        from civ6_host.runtime import xp2_postload_aux90_source

        refs=life.source_dependencies(XP2_CORE_SHA256,postload=True)
        self.assertGreater(len(refs),100)
        for path,digest in refs.items():
            self.assertEqual(hashlib.sha256(Path(path).read_bytes()).hexdigest(),digest)
        with self.assertRaisesRegex(ValueError,'XP2-only'):
            life.source_dependencies(XP1_CORE_SHA256,postload=True)

        b=self.graph();f=self.f;base=f.base
        post=xp2_postload_source.source();active=xp2_postload_source.active_source()
        bodies=dict(post['functions']['xp2']);bodies.update(active['functions'])
        for fn in bodies.values():
            for fragment in fn['fragments']:
                f.put(base+int(fragment['start_rva'],16),bytes.fromhex(fragment['raw_hex']))
        for row in post['tables']['xp2'].values():
            f.q(base+row['vtable_rva']+row['slot'],base+row['target_rva'])
        for address,literal in post['literals'].items():
            data=literal['text'].encode('ascii')+b'\0'
            self.assertEqual(len(data),literal['bytes'])
            f.put(base+int(address,16)-0x180000000,data)

        cache=xp2_cache_source.source()
        for _,body in xp2_cache_source.bodies(cache):
            for fragment in body['fragments']:
                f.put(base+int(fragment['start_rva'],16),bytes.fromhex(fragment['raw_hex']))
        for row in cache['slots']:
            f.q(base+row['vtable_rva']+row['slot'],base+row['target_rva'])
        aux=xp2_postload_aux90_source.source()
        body=aux['functions']['xp2']['aux_scope']
        f.put(base+xp2_postload_aux90_source.AUX_SCOPE_RVA,bytes.fromhex(body['raw_hex']))
        f.q(base+xp2_postload_aux90_source.HOST_GLOBAL_RVA,b.host.pointer)
        f.q(base+xp2_postload_aux90_source.AUX_GLOBAL_RVA,C.addressof(b.host.aux_object))

        proof=postlife.verify_postload_live(b)
        self.assertFalse(proof['native_calls_made'])
        self.assertFalse(proof['saved_load_admitted'])
        self.assertEqual(proof['post160']['core_sha256'],XP2_CORE_SHA256)
        self.assertEqual(proof['loaded_cache_abi'].core_sha256,XP2_CORE_SHA256)
        self.assertEqual(proof['source_dependencies'],postlife.postload_source_dependencies())

        changed=next(iter(cache['functions'].values()))['body']['fragments'][0]
        address=base+int(changed['start_rva'],16)
        f.put(address,b'\xcc')
        with self.assertRaisesRegex(ValueError,'XP2 cache instructions differ'):
            postlife.verify_postload_live(b)

    def postload_graph(self):
        from civ6_host.runtime import xp1_postload_candidate as candidate
        from civ6_host.runtime import xp1_cache_publication as publication
        from civ6_host.runtime.cache_facade_service import CacheFacadeService
        from civ6_host.runtime.player_notification_service import PlayerNotificationService
        from civ6_host.runtime.status_message_service import StatusMessageService
        from civ6_host.runtime.native.native_player_view import NativePlayerViewPublisher
        from civ6_host.runtime.native.native_ui_cache_backend import NativeCacheFacadeBackend
        from civ6_host.runtime.native.native_official_postload import OfficialPost160Backend
        from civ6_host.runtime.native.native_official_load import OfficialLoadBackend
        from civ6_host.runtime.event_argument_service import EventArgumentService
        from civ6_host.runtime.a0_family_service import A0FamilyService
        from civ6_host.runtime.prepare_services import PrepareServices
        from civ6_host.runtime.loaded_cache_publication import LoadedCachePublication
        from civ6_host.runtime.xp1_cache_publication import SavedCachePublication
        from civ6_host.runtime.native.native_checkpoint_postload_facades import NativeFacadeBackend
        from civ6_host.runtime.loaded_cache_profiles import loaded_cache_abi
        from civ6_host.runtime.saved_load_profiles import profile_for_sha
        import test_xp2_cache_publication as cache_fixture
        from test_xp2_postload_candidate import XP2Post160CandidateTests

        if not hasattr(XP2Post160CandidateTests,'bundle'):
            XP2Post160CandidateTests.setUpClass()
        f,attempt,_=cache_fixture.XP2CacheTests().graph()
        previous=attempt.owner
        owner=OfficialLoadBackend.__new__(OfficialLoadBackend)
        owner.__dict__.update(previous.__dict__)
        owner.core=NS(_handle=f.core_base);owner.context=f.outer;owner.host=previous.host
        owner.load_abi=profile_for_sha(XP2_CORE_SHA256);owner.configuration_abi=NS(core_sha256=XP2_CORE_SHA256)
        owner.inputs=XP2Post160CandidateTests.bundle.inputs
        owner.captured_bundle=XP2Post160CandidateTests.bundle;owner._saved_load_candidate=True
        owner.reader.transport.closed=True;owner.reader.transport.cursor=len(owner.inputs.game)
        owner.bound_identity=dict(f.identity);owner.stage='facades-candidate-observed';owner.busy=True
        owner.check_thread=Mock();owner.control=Mock();owner.topology=lambda **kw:owner.bound_identity
        owner.game_flag=lambda:1
        owner.runtime.read=f.read;owner.runtime.thread=lambda:owner.thread
        owner.runtime.service_owner=owner.host
        owner.runtime.registry=NS(validate=Mock())
        prefix=owner.prefix;prefix.backend=owner;prefix.host=owner.host;prefix.core=owner.core
        prefix.context=owner.context;prefix.runtime=owner.runtime;prefix.configuration_readback_verified=True
        prefix.game_child=987;prefix.check=lambda:prefix.runtime.registry.validate(prefix.game_child)
        prefix.deferred_events.core=owner.core;prefix.deferred_events.context=owner.context
        prefix.deferred_events.cache_core_sha256=XP2_CORE_SHA256
        owner.host._saved_load_services=prefix
        attempt.owner=owner;attempt.cache_abi=loaded_cache_abi(XP2_CORE_SHA256)
        attempt.publication_mode='candidate';attempt.publication_owner=None
        lease=LoadedCachePublication(attempt)

        facades=f.acquire();facades._copy_cache_outputs()
        publisher=NativePlayerViewPublisher(owner.core,owner.context,Mock(),read=f.read,
            core_sha256=XP2_CORE_SHA256)
        publisher._facades=facades;facades.backend=None
        native_backend=NativeCacheFacadeBackend(owner.core,Mock(),context_alive=lambda:True,
            read=f.read,core_sha256=XP2_CORE_SHA256,publication_owner=lease)
        facades.backend=native_backend
        prefix.view_publisher=publisher;attempt.publisher=publisher
        lease.attach(publisher,native_backend);attempt.publication_owner=lease
        lease.entered=lease.returned=lease.copied=True
        owner.busy=False

        post=OfficialPost160Backend.__new__(OfficialPost160Backend)
        post.owner=owner;post.facade=attempt;post.postload_mode='candidate';post._candidate_cache_lease=lease
        post.attempted=post.native_call_attempted=True;post.candidate_diagnostics={'void_return_ignored':True}
        owner._xp1_post160_attempt=post
        lease.begin_post160(post);lease.finish_post160(post)
        owner.stage=candidate.FINISHED_STAGE;owner.busy=False
        attempt.publication_owner=lease
        saved_publication=SavedCachePublication(post)
        lease.begin_publication(saved_publication)
        saved_publication.attempted=saved_publication.native_attempted=True
        saved_publication.native_returned=saved_publication.completed=True
        saved_publication.result={'native_returned':True}
        lease.finish_publication(saved_publication)

        cache=CacheFacadeService.__new__(CacheFacadeService)
        cache.closed=cache.quarantined=False;cache.core=owner.core;cache.context=owner.context
        player=PlayerNotificationService.__new__(PlayerNotificationService)
        lock=NS(host=owner.host);owner.host.execution_lock=lock
        player.closed=player.quarantined=False;player.host=owner.host;player.core=owner.core
        player.context=owner.context;player.core_lock=lock
        status=StatusMessageService.__new__(StatusMessageService)
        arguments=EventArgumentService.__new__(EventArgumentService);arguments.host=owner.host
        arguments.deferred=prefix.deferred_events
        a0=A0FamilyService.__new__(A0FamilyService);a0.player_query_owner=player
        arguments.consumer=a0;player._a0_event_owner=a0
        status.closed=status.quarantined=False;status.host=owner.host
        status.arguments=arguments;status.deferred=prefix.deferred_events
        prefix.cache_facades=cache;prefix.player_queries=player;prefix.status_messages=status
        prefix.event_arguments=arguments;prefix.actions=None
        del prefix.actions
        receipt={'core_sha256':XP2_CORE_SHA256,'native_calls_made':False,'dependencies':{'pin':'a'*64}}
        prefix.validate_postload_aux90=Mock(return_value=receipt);post.aux90_validation=receipt
        prepare=PrepareServices.__new__(PrepareServices);prepare.host=owner.host;prepare.base=owner.core._handle
        prepare.require_complete=Mock(return_value=True)
        owner.host._xp2_prepare_services=owner.host._prepare_services=prepare

        from civ6_host.runtime.xp1_ui_binding import SavedPlayerView
        from civ6_host.runtime.xp2_ui_binding_source import SOURCE as ui_source
        ui_child=988;prefix.game_child=987;prefix.ui_child=ui_child
        owner.runtime._xp2_ui_bind_entered=True
        owner.runtime.registry.validate.side_effect=lambda child:child
        owner.runtime.registry.release=Mock()
        view=SavedPlayerView.__new__(SavedPlayerView)
        view.publication=saved_publication;view.owner=owner;view.prefix=prefix
        view.runtime=owner.runtime;view.child=ui_child;view.attempted=view.completed=True
        view.core_sha256=XP2_CORE_SHA256;view.source_sha256=ui_source[1]
        view.result=dict(core_sha256=XP2_CORE_SHA256,source_sha256=ui_source[1],binding=dict(
            native_ui_registration_returned=True,source_sha256=ui_source[1],method_rva='0x5a1db0'))
        owner._xp1_player_view=view
        return f,owner,prefix,lease,saved_publication,view

    def test_completed_xp2_publication_enters_shared_loaded_lifetime_and_wrapper_stage(self):
        f,owner,prefix,lease,saved_publication,view=self.postload_graph()
        lock=owner.host.execution_lock;ui_child=view.child;prepare=owner.host._xp2_prepare_services
        token=life.LoadedLifetime.__new__(life.LoadedLifetime)
        token.owner=owner;token.prefix=prefix;token.lease=lease;token.completed=saved_publication
        token.xp2_loaded=True;token.raw_loaded=False;token.source_reference=source.SOURCE
        token.player_view=view;token.ui_child=ui_child;token.ui_source_dependencies=None
        token.host=owner.host;token.core=owner.core;token.context=owner.context;token.runtime=owner.runtime
        token.application=owner.owner;token.child=prefix.game_child
        token.lock=lock;token.inner=owner.bound_identity['inner'];token.thread=threading.get_ident()
        token.phase='wrappers';token.poisoned=False;token.unload_called=False;token.steps=[]
        token.check_completed()
        self.assertEqual(prefix.validate_postload_aux90.call_count,2)
        self.assertIs(token.prepare_services,prepare)

        owner._loaded_lifetime=token
        lease.begin_release(token)
        self.assertEqual(owner.stage,'loaded-lifetime-wrappers')
        self.assertTrue(owner.busy)
        token.check_job_snapshot()
        with self.assertRaisesRegex(ValueError,'completed native Destroy'):
            token._release_saved_player_view()
        token.phase='lua';token.destroy_returned=True;owner.destroyed=True
        self.assertTrue(token._release_saved_player_view())
        owner.runtime.registry.release.assert_called_once_with(ui_child)
        self.assertIsNone(prefix.ui_child);self.assertIsNone(token.ui_child)

    def test_complete_raw_close_drains_real_fifo_preserves_shared_owners_and_no_wrappers(self):
        b=self.graph();self.queue(b);original=b.prefix.deferred_events.pending[0]
        result=self.drive(b)
        self.assertEqual(self.events,['jobs-before','unload','jobs-after','destroy','options','configuration','database'])
        self.assertTrue(result['native_unload_called']);self.assertTrue(result['native_destroy_called'])
        self.assertEqual((result['loaded_notifications_consumed'],result['unloaded_notifications_consumed']),(1,1))
        self.assertEqual(b.prefix.deferred_events.consumed_count,2)
        self.assertEqual(b.prefix.deferred_events.pending,[])
        self.assertEqual(b.prefix.deferred_events.consumed_bytes,2*len(original))
        self.assertTrue(b.prefix.closed);self.assertTrue(b.prefix.event_arguments.consumer.closed)
        self.assertTrue(b.prefix.control_inputs.closed);self.assertTrue(b.prefix.deferred_events.closed)
        self.assertFalse(result['cache_wrappers_present']);self.assertFalse(result['cache_wrappers_released'])
        self.assertFalse(result['post160_called']);self.assertFalse(result['cleanup_inferred_from_process_exit'])
        self.assertIsNone(b._loaded_lifetime.lease)
        with self.assertRaisesRegex(ValueError,'fresh'):life.close_raw_loaded(b)

    def test_district_removed_during_real_close_owner_enqueues_then_drains_after_unload(self):
        b=self.graph();result=self.drive(b,district_removed=True)
        self.assertIn('native-null-player',self.events)
        self.assertEqual(result['unloaded_notifications_consumed'],2)
        self.assertEqual(b.prefix.deferred_events.consumed_count,2)
        self.assertEqual(b.prefix.deferred_events.pending,[])
        self.assertTrue(b.prefix.event_arguments.consumer.closed)
        self.assertTrue(result['native_destroy_called'])

    def test_invalid_load_or_unqualified_optional_owner_refused_before_cleanup(self):
        changes=(lambda b:setattr(b.reader.transport,'closed',False),lambda b:setattr(b,'load_attempted',False),
            lambda b:b.raw_load_result.update(status=1),lambda b:setattr(b,'stage','copied'),
            lambda b:setattr(b.prefix,'cache_facades',object()),lambda b:b.bound_identity.update(game=1))
        for change in changes:
            with self.subTest(change=change):
                b=self.graph();change(b)
                with self.assertRaises(ValueError):life.close_raw_loaded(b)
                self.assertEqual(self.events,[]);self.assertFalse(b.destroyed)

    def test_unknown_record_before_unload_kept_and_poisoned_without_retry(self):
        b=self.graph();row=self.queue(b,0xdead)
        with self.assertRaisesRegex(ValueError,'no decoder'):self.drive(b)
        self.assertEqual(self.events,[]);self.assertEqual(b.prefix.deferred_events.pending,[row])
        self.assertTrue(b.poisoned);self.assertTrue(b.prefix.quarantined)
        self.assertFalse(b._loaded_lifetime.unload_called)

    def test_cache_feedback_after_unload_refused_without_queue_loss_or_destroy(self):
        b=self.graph()
        with self.assertRaisesRegex(ValueError,'unqualified receiver'):self.drive(b,unknown_record=True)
        self.assertEqual(self.events,['jobs-before','unload','jobs-after'])
        self.assertFalse(b.destroyed);self.assertEqual(len(b.prefix.deferred_events.pending),1)
        self.assertEqual(b.prefix.deferred_events.consumed_count,0)
        self.assertTrue(b._loaded_lifetime.unload_called);self.assertFalse(b._loaded_lifetime.destroy_called)

    def test_native_archive_retention_and_wrong_options_rvas_refuse(self):
        b=self.graph()
        with self.assertRaisesRegex(ValueError,'retained archive'):self.drive(b,retain_archive=True)
        self.assertFalse(b.destroyed);self.assertTrue(b.host.archives.entries)
        b=self.graph();token=life.LoadedLifetime(b,b,raw_loaded=True)
        b.busy=True;b.destroyed=True;token.phase='options';token.destroy_returned=True
        borrower=b.host._saved_load_performance_options.borrower
        for rva in (0x845600,0x844580,0x99fee0):
            with self.assertRaisesRegex(ValueError,'Performance map teardown'):token.check_options_cleanup(borrower,rva)
        token.check_options_cleanup(borrower,0x99f680)
        token.check_options_cleanup(borrower,0x99e5d0)

    def test_xp2_postload_options_cleanup_keeps_xp2_provider_abi(self):
        b=self.graph();token=life.LoadedLifetime(b,b,raw_loaded=True)
        token.raw_loaded=False;token.xp2_loaded=True;token.phase='options';token.destroy_returned=True
        b.busy=True;b.destroyed=True
        borrower=b.host._saved_load_performance_options.borrower
        contract=performance_profile()[1]['contract']
        token.check_options_cleanup(borrower,contract['slots']['0x68'])
        token.check_options_cleanup(borrower,contract['destructor_rva'])
        for rva in (0x845600,0x844580):
            with self.assertRaisesRegex(ValueError,'Performance map teardown'):
                token.check_options_cleanup(borrower,rva)


if __name__=='__main__':unittest.main()
