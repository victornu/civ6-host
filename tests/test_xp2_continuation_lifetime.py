"""Real continuation/cache/transport lifetime guards; native effects are fixtures."""
import ctypes as C
from contextlib import nullcontext
from dataclasses import replace
import hashlib
from pathlib import Path
import struct
import threading
from types import SimpleNamespace as NS
import unittest
from unittest.mock import Mock,patch

from civ6_host.runtime import xp1_loaded_lifetime as life
from civ6_host.runtime import xp2_loaded_lifetime_source as source
from civ6_host.runtime import xp2_action_transport_source as actions
from civ6_host.runtime import xp1_continuation as continuation
from civ6_host.runtime import xp1_load_capability as capability
from civ6_host.runtime.configuration_profiles import XP1_CORE_SHA256,XP2_CORE_SHA256
from civ6_host.runtime.execution_images import select
from civ6_host.runtime.xp1_action_transport import SavedActionTransport
from civ6_host.runtime.native.native_events import NativeEventRecorder
import test_xp2_loaded_lifetime as post_fixture
from test_xp1_loaded_lifetime import snapshot


class ContinuationLifetimeTests(unittest.TestCase):
    def graph(self):
        f,b,p,lease,pub,view=post_fixture.RawLifetimeTests().postload_graph()
        base=f.core_base
        # Source-backed memory composes the already selected postload and
        # command families under the same actual LoadedCachePublication.
        proof=actions.source();b.core._name=proof['image']['path']
        b.core._civ6_host_execution_image=select(
            'xp2-gamecore-current-092abfbb',core_path=b.core._name)
        for body in proof['functions'].values():
            for frag in body['fragments']:f.put(base+int(frag['start_rva'],16),bytes.fromhex(frag['raw_hex']))
        for row in proof['slots']:f.q(base+row['vtable_rva']+row['slot'],base+row['target_rva'])
        message=proof['message_vtable']
        for i,rva in enumerate(message['entries']):f.q(base+message['rva']+i*8,base+rva)
        for rva,row in proof['literals'].items():f.put(base+int(rva,16),bytes.fromhex(row['raw_hex']))
        sentinel=base+actions.ABI.receive_queue_rva;f.put(sentinel,struct.pack('<QQ',sentinel,sentinel))
        for _,rva,raw in source.fragments(source.source()):f.put(base+rva,raw)
        for key,target in source.SLOTS.items():
            vt,slot=(int(x,16) for x in key.split('+'));f.q(base+vt+slot,base+int(target,16))
        from civ6_host.runtime import xp2_postload_source as post
        static=post.source();active=post.active_source()
        for body in (*static['functions']['xp2'].values(),*active['functions'].values()):
            for frag in body['fragments']:f.put(base+int(frag['start_rva'],16),bytes.fromhex(frag['raw_hex']))
        for row in static['tables']['xp2'].values():f.q(base+row['vtable_rva']+row['slot'],base+row['target_rva'])
        for address,row in static['literals'].items():f.put(base+int(address,16)-0x180000000,row['text'].encode()+b'\0')
        from civ6_host.runtime import xp2_postload_aux90_source as aux
        f.put(base+aux.AUX_SCOPE_RVA,bytes.fromhex(aux.source()['functions']['xp2']['aux_scope']['raw_hex']))
        f.q(base+aux.HOST_GLOBAL_RVA,b.host.pointer);f.q(base+aux.AUX_GLOBAL_RVA,C.addressof(b.host.aux_object))
        p.core_sha256=XP2_CORE_SHA256;p.emit=b.emit=Mock()
        p.runtime.closed=False;p.runtime.database_bound=p.runtime.configuration_bound=p.runtime.locale_bound=True
        b.owner.closed=False
        recorder=NativeEventRecorder.__new__(NativeEventRecorder)
        recorder.closed=False;recorder.lock=threading.RLock();recorder.setter=Mock();recorder.streams={}
        recorder.host=b.host;b.host.event_recorder=recorder
        installed=patch.object(NativeEventRecorder,'_installed',recorder);installed.start();self.addCleanup(installed.stop)
        transport=SavedActionTransport.__new__(SavedActionTransport)
        transport.backend=b;transport.services=p;transport.host=b.host;transport.core=b.core
        transport.context=b.context;transport.read=f.read;transport.transport_abi=actions.ABI
        transport.closed=False;transport.pending=[];transport.recorder=recorder;transport.emit=b.emit
        transport.address=b.host.vtable[0x70//8]
        def fatal(*args):raise AssertionError('original host refusal')
        fatal._native_unavailable=('host',0x70)
        transport.previous=(0x98760,(0x98760,fatal))
        transport.event_source=actions.verify_live(base,f.read,family='log')
        p.actions=transport
        view.result['observation']=dict(player_id=0,turn=0,width=74,height=46,cities=[],units=[])
        c=continuation.SavedContinuation(view)
        c.check_close()
        # The prepared status owner must retain the exact strict slot to restore.
        previous=Mock();previous._native_unavailable=('host',0xC0)
        p.status_messages.previous=(0,(9,previous))
        b.host.archives=NS(entries={});b.host.types=NS(entries={})
        p.contexts=NS(names={})
        b.host._prepare_services.verify_callbacks=Mock()
        return f,b,p,lease,c,transport

    def test_constructor_reuses_exact_postload_sources_and_ready_continuation(self):
        f,b,p,lease,c,t=self.graph()
        token=life.LoadedLifetime(b,c)
        self.assertIs(token.completed,c);self.assertIs(token.action_transport,t)
        self.assertIs(token.lease,lease);self.assertIs(token.player_view,c.view)
        self.assertEqual(token.source_reference,source.SOURCE)
        self.assertEqual(b.stage,continuation.READY)
        self.assertEqual(token.continuation_source_receipt['source_sha256'],actions.SOURCE[1])
        self.assertIs(c.publication.post.aux90_validation,p.validate_postload_aux90.return_value)
        pins=life.source_dependencies(XP2_CORE_SHA256,postload=True,continuation=True,
            execution_image=b.core._civ6_host_execution_image)
        self.assertEqual(token.continuation_source_dependencies,pins)
        for path,digest in pins.items():self.assertEqual(hashlib.sha256(Path(path).read_bytes()).hexdigest(),digest)
        token.phase='wrappers';lease.begin_release(token)
        self.assertEqual(b.stage,'loaded-lifetime-wrappers');token.check_job_snapshot()
        self.assertIs(lease.authorize_publisher_close(p.view_publisher),token)
        with self.assertRaisesRegex(ValueError,'fresh'):life.LoadedLifetime(b,c)
        for kw in ({'continuation':True},{'postload':True,'continuation':True}):
            with self.assertRaises(ValueError):life.source_dependencies(XP1_CORE_SHA256,**kw)

    def test_ready_queues_publication_and_source_are_required_before_install(self):
        f,b,p,lease,c,t=self.graph()
        changes=(('phase',lambda:setattr(b,'stage',continuation.ACTIVE),lambda:setattr(b,'stage',continuation.READY)),
          ('host pending',lambda:t.pending.append(b'real-pending'),lambda:t.pending.clear()),
          ('native pending',lambda:f.q(f.core_base+actions.ABI.receive_queue_rva,123),
             lambda:f.q(f.core_base+actions.ABI.receive_queue_rva,f.core_base+actions.ABI.receive_queue_rva)),
          ('profile',lambda:setattr(t,'transport_abi',replace(actions.ABI)),lambda:setattr(t,'transport_abi',actions.ABI)),
          ('unit source',lambda:c.unit_source.update(source_sha256='f'*64),lambda:c.unit_source.update(source_sha256=actions.SOURCE[1])),
          ('logger source',lambda:t.event_source.update(core_sha256=XP1_CORE_SHA256),lambda:t.event_source.update(core_sha256=XP2_CORE_SHA256)),
          ('publishing',lambda:setattr(c,'publishing',True),lambda:setattr(c,'publishing',False)))
        for label,change,restore in changes:
            with self.subTest(label=label):
                change()
                with self.assertRaises((ValueError,RuntimeError)):life.LoadedLifetime(b,c)
                self.assertFalse(hasattr(b,'_loaded_lifetime'));restore()
        address=f.core_base+actions.ABI.receive_rva;old=f.memory[address];f.memory[address]^=1
        with self.assertRaisesRegex(ValueError,'differs'):life.LoadedLifetime(b,c)
        f.memory[address]=old
        # Attaching command services cannot be hidden behind the earlier publication.
        with self.assertRaises((ValueError,RuntimeError)):life.LoadedLifetime(b,c.publication)

    def test_retained_aux90_and_transport_owners_cannot_be_replaced(self):
        f,b,p,lease,c,t=self.graph();token=life.LoadedLifetime(b,c)
        post=c.publication.post;receipt=post.aux90_validation
        post.aux90_validation=dict(receipt,core_sha256=XP1_CORE_SHA256)
        with self.assertRaisesRegex(ValueError,'AUX90'):token.check_completed()
        post.aux90_validation=receipt
        b.busy=True;b.stage='loaded-lifetime-wrappers';token.phase='wrappers'
        p.actions=object()
        with self.assertRaisesRegex(ValueError,'command owner'):token._owned()
        p.actions=t;token._owned()
        self.assertFalse(t.closed)
        with self.assertRaisesRegex(ValueError,'before actual'):t.close()

    def drive(self,*,fail=None):
        f,b,p,lease,c,t=self.graph();token=life.LoadedLifetime(b,c);events=[]
        def wrapper(obj,field,label):
            def close():
                token.check_wrapper_release(lease);events.append(label)
                if fail==label:raise ValueError('injected '+label)
                setattr(obj,field,True)
            return close
        p.cache_facades.close=wrapper(p.cache_facades,'closed','cache')
        p.view_publisher.close=wrapper(p.view_publisher,'_closed','publisher')
        p.status_messages.close=wrapper(p.status_messages,'closed','status')
        p.event_arguments.consumer.enable_district_events=Mock()
        p.deferred_events.pending=[];p.deferred_events._sequence=0;p.deferred_events.consumed_count=0
        def drain(**kwargs):
            self.assertEqual(p.deferred_events.pending,[]);self.assertIs(kwargs['loaded_lifetime'],token)
            events.append('drain');return 0
        p.deferred_events.drain=drain
        def jobs(phase):
            token.check_job_snapshot();events.append('jobs-'+phase)
            row=snapshot();row['core_identity']={'sha256':XP2_CORE_SHA256,'profile':3}
            from civ6_host.runtime.saved_load_job_observer import XP2_SOURCE
            row['source_proof_sha256']=XP2_SOURCE[1];return row
        b.jobs_snapshot=jobs
        def unload(core,context,emit,*,loaded_lifetime):
            self.assertIs(loaded_lifetime,token);self.assertEqual(token.before_unload(core,context),0x591860)
            events.append('unload')
            if fail=='unload':raise ValueError('injected unload')
            for address in (f.inner+0x60,f.inner+0x1A68):f.q(address,0)
            for rva in token.proof['contract']['unloaded_zero_global_rvas']:f.q(f.core_base+rva,0)
            token.after_unload()
        b.host.context_teardown_receipt={'installed':True}
        def destroy(**kwargs):
            self.assertIs(kwargs['loaded_lifetime'],token);token.before_destroy(b);events.append('destroy')
            for rva in token.proof['contract']['destroyed_zero_global_rvas']:f.q(f.core_base+rva,0)
            b.destroyed=True;token.after_destroy(b)
        b.destroy_context=destroy
        def services_close():
            self.assertTrue(token.destroy_returned);t.close();events.append('transport')
            if fail=='services':raise ValueError('injected services')
            p.closed=True;events.append('services')
        p.close=services_close
        provider=NS(close=lambda **kw:events.append('options') or {'native_destructor_returned':True})
        b.host._saved_load_performance_options=NS(provider=provider)
        b.close_owner=lambda:(setattr(b.owner,'closed',True),events.append('configuration'))
        p.runtime.unbind_services=lambda:events.append('unbind')
        p.runtime.registry.contexts={p.game_child:1,p.ui_child:1};p.runtime.registry._claims={}
        def child_release(child):
            self.assertTrue(token.destroy_returned);p.runtime.registry.contexts.pop(child)
            events.append('ui-child' if child==c.ui_child else 'game-child')
        p.runtime.registry.release=child_release
        p.runtime.close=lambda:(setattr(p.runtime,'closed',True),events.append('lua'))
        token.lock.close=lambda:events.append('lock')
        def database():
            t.recorder.close();events.append('database');return True
        b.finish_database=database
        with patch.object(capability,'capability_source_scope',return_value=nullcontext()), \
             patch('civ6_host.runtime.native.native_host.release_game_services',side_effect=unload):
            if fail:
                with self.assertRaisesRegex(ValueError,'injected'):token.close()
            else:token.close()
        return b,p,lease,token,t,events

    def test_shared_close_orders_wrappers_unload_destroy_transport_ui_and_recorder(self):
        b,p,lease,token,t,events=self.drive()
        self.assertEqual(events,['jobs-before','cache','publisher','status','unload','jobs-after','drain',
            'destroy','transport','services','options','configuration','unbind','ui-child','game-child','lua','lock','database'])
        self.assertTrue(t.closed);self.assertTrue(t.recorder.closed)
        self.assertEqual(b.host.vtable[0x70//8],t.previous[0])
        self.assertTrue(token.report['continuation_closed']);self.assertTrue(token.report['command_transport_closed'])
        self.assertFalse(token.report['postload_candidate_only']);self.assertFalse(token.report['cleanup_inferred_from_process_exit'])
        with self.assertRaisesRegex(ValueError,'cannot replay'):token.close()

    def test_shutdown_failure_poisoned_without_later_steps_or_receipt(self):
        for stage in ('status','unload','services'):
            with self.subTest(stage=stage):
                b,p,lease,token,t,events=self.drive(fail=stage)
                self.assertTrue(token.poisoned);self.assertTrue(lease.poisoned);self.assertTrue(b.poisoned)
                self.assertIsNone(token.report);self.assertNotIn('database',events)
                with self.assertRaisesRegex(ValueError,'cannot replay'):token.close()


if __name__=='__main__':unittest.main(verbosity=2)
