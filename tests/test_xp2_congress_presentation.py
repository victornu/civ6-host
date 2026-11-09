"""Congress presentation source/composition fixtures; no GameCore execution."""
import struct
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch

from civ6_host.runtime import a0_foundation_events as foundation
from civ6_host.runtime import empty_presentation_events as presentation
from civ6_host.runtime import xp2_congress_presentation as source
from civ6_host.runtime.configuration_profiles import _copy
from test_xp1_turn_a0 import scalar


class CongressPresentationTests(unittest.TestCase):
    def fields(self, kind=source.STAGE1, value=0):
        result = {source.SELECTOR_KEY: scalar(3, 0)}
        if kind != source.FINISHED:
            result[source.VALUE_KEY] = scalar(2, value)
        return result

    def execution(self):
        from civ6_host.runtime.execution_images import select, known_path
        name='xp2-gamecore-current-092abfbb'
        return select(name,core_path=known_path(name))

    def graph(self):
        image=self.execution()
        from civ6_host.runtime import foundation_event_profile
        pillage=foundation_event_profile.pillage_source
        def selected_pillage(*args,**kwargs):
            return pillage(execution_image=image)
        original = foundation.enable_turn_units
        def install(owner, backend):
            backend.core._civ6_host_execution_image=image
            memory = owner.read.__self__
            for rva, raw in source.core_fragments():
                memory.put(memory.core_base + rva, raw)
            owner.arguments.reader.core_sha256 = backend.load_abi.core_sha256
            original(owner, backend)
            presentation.enable(owner, backend, source)
        with patch.object(foundation, 'enable_turn_units', install), \
             patch.object(foundation_event_profile,'pillage_source',selected_pillage):
            from test_xp2_turn_notifications import XP2ComposedNotifications
            return XP2ComposedNotifications().graph()

    def test_current_exe_routes_and_empty_receiver_source(self):
        p = source.source()
        from civ6_host.runtime.native.native_host_event_registry import EXE_EVENT_CALLBACKS
        self.assertEqual(set(source.KINDS), {0xdabc2341,0x43b572fb,0x34b2426d,0x6ed99ee8})
        self.assertEqual({k:EXE_EVENT_CALLBACKS[k] for k in source.KINDS}, source.CALLBACKS)
        self.assertEqual(source.CURRENT_CALLBACKS, {source.STAGE1:0x1596f0,
            source.STAGE2:0x1597f0,source.STAGE3:0x1598f0,source.FINISHED:0x159330})
        self.assertNotEqual(source.CURRENT_CALLBACKS, source.CALLBACKS)
        self.assertIn(source.SOURCE[1], source.source_dependencies().values())
        self.assertIn(source.PREVIOUS_SOURCE[1], source.source_dependencies().values())
        self.assertEqual({p['routes'][hex(k)]['record_type'] for k in source.KINDS}, {300,301,302,304})
        for key in ('payload_read_on_empty_path', 'native_gameplay_call_on_empty_path'):
            changed = _copy(p); changed['dispatch'][key] = True
            with self.assertRaises(ValueError): source._verify(changed)
        for kind in source.KINDS:
            for key, value in [('handler_rva','0xd5571'),('callback_getter_calls',True),
                               ('record_size',97),('writer_rva','0x1239e1')]:
                changed = _copy(p); changed['routes'][hex(kind)][key] = value
                with self.assertRaises(ValueError): source._verify(changed)
        changed = _copy(p); changed['stage_producer']['internal_dispatch_before_host'] = False
        with self.assertRaises(ValueError): source._verify(changed)

    def test_retained_failed_stage1_copied_headers_and_full_scalar_domain(self):
        event = source.source()['retained_failure']['event']
        self.assertEqual(event['dispatch_kind'], hex(source.STAGE1))
        fields = {int(k,16):bytes.fromhex(v) for k,v in event['fields'].items()}
        self.assertNotEqual(fields[source.SELECTOR_KEY][4:8], b'\0'*4)
        read = lambda *a: self.fail('presentation requested a gameplay getter/pointer read')
        result = source.decode_fields(source.STAGE1, fields, read)
        self.assertEqual((result.selector,result.value),(0,0))
        for kind in source.KINDS:
            for value in (0,63,64,0x7fffffff,0xffffffff):
                with self.subTest(kind=kind,value=value):
                    result=source.decode_fields(kind,self.fields(kind,value),read)
                    self.assertEqual(result.value,None if kind==source.FINISHED else value)
                    self.assertEqual(result.to_admin()['gameplay_getters_required'],False)
                    self.assertEqual(result.to_admin()['event_name'],source.EVENT_NAMES[kind])

    def test_exact_shapes_reject_malformed_headers_and_unrelated_callbacks(self):
        read = lambda *a: self.fail('decoder dereferenced a scalar')
        for kind in source.KINDS:
            fields=self.fields(kind)
            bad=[{}, {**fields,7:scalar(2,0)},
                 {**fields,source.SELECTOR_KEY:scalar(3,1)},
                 {**fields,source.SELECTOR_KEY:scalar(2,0)},
                 {**fields,source.SELECTOR_KEY:b'\0'*23},
                 {**fields,source.SELECTOR_KEY:bytearray(scalar(3,0))}]
            if kind==source.FINISHED: bad.append({**fields,source.VALUE_KEY:scalar(2,0)})
            else:
                bad.extend([{source.SELECTOR_KEY:scalar(3,0)},
                            {**fields,source.VALUE_KEY:scalar(3,0)}])
            for key in fields:
                for offset in (16,20):
                    raw=bytearray(fields[key]);raw[offset]=1
                    bad.append({**fields,key:bytes(raw)})
            for value in bad:
                with self.subTest(kind=kind,fields=value):
                    with self.assertRaises(ValueError):source.decode_fields(kind,value,read)
        for kind in (0x3b75bad7,0x05c859e1,0x3b627e38,0xdeadbeef,True):
            with self.assertRaises(ValueError):source.decode_fields(kind,self.fields(),read)

    def test_real_shared_owner_all_four_kinds_preserve_fifo_and_scope(self):
        g = self.graph()
        pending = bytes(range(96))
        g.owner.pending.append(pending)
        g.owner.deferred.host_notification_counter=3;g.owner.deferred.host_metadata_counter=2
        before=(g.owner._sequence,tuple(g.owner.pending),
                g.owner.host_notification_counter,g.owner.host_metadata_counter)
        with patch.object(g.owner,'_dispatch_fields',side_effect=AssertionError('gameplay route used')):
            for kind in source.KINDS:
                self.assertTrue(g.owner.handles_kind(kind))
                self.assertEqual(g.owner.dispatch(kind,self.fields(kind),0),0)
        self.assertEqual((g.owner._sequence,tuple(g.owner.pending),
            g.owner.host_notification_counter,g.owner.host_metadata_counter),before)
        self.assertIs(g.owner.pending[0],pending)
        self.assertIsNone(g.owner._foundation_borrow)
        omitted=[row for stage,row in g.event.emitted
                 if stage=='native_empty_presentation_callback_omitted']
        self.assertEqual({row['dispatch_kind'] for row in omitted},{hex(k) for k in source.KINDS})
        self.assertTrue(all(row['records_enqueued']==0 and not row['native_queries_executed']
                            and not row['native_gameplay_written'] for row in omitted))
        self.assertFalse(g.owner.handles_kind(0x05c859e1))
        self.assertFalse(g.owner.handles_kind(0x3b627e38))
        with self.assertRaisesRegex(ValueError,'unknown family'):
            g.owner.dispatch(0xdeadbeef,{},0)

    def test_copied_failure_headers_route_through_actual_argument_owner(self):
        import threading
        from civ6_host.runtime.event_argument_service import EventArgumentReader
        from civ6_host.runtime.native.native_host import DiagnosticHost
        from test_xp2_preload_services import XP2PreloadServices
        g=self.graph()
        g.backend.host._check=DiagnosticHost._check.__get__(g.backend.host)
        from civ6_host.runtime import xp2_preload_source as preload
        for name in ('iterator_next','get_count'):
            for fragment in preload.body(name)['fragments']:
                g.memory.put(g.memory.core_base+int(fragment['start_rva'],16),
                             bytes.fromhex(fragment['raw_hex']))
        g.memory.q(g.memory.core_base+0xABF080+0x1D8,g.memory.core_base+0x84E260)
        reader=EventArgumentReader.__new__(EventArgumentReader)
        reader.core=g.backend.core;reader.base=g.memory.core_base
        reader.core_sha256=source.XP2_CORE_SHA256;reader.read=g.memory.read
        reader.thread=threading.get_ident();reader.closed=False
        g.event.arguments.reader=reader
        tree=XP2PreloadServices();tree.base=g.memory.core_base;tree.put=g.memory.put
        fields={int(k,16):bytes.fromhex(v) for k,v in
                source.source()['retained_failure']['event']['fields'].items()}
        pointer,reader.next_node=tree.tree(fields)
        with patch('civ6_host.runtime.event_argument_service.validate_absent_scalar_a0',
                   side_effect=AssertionError('registered callback used absent fallback')):
            self.assertEqual(g.event.arguments.dispatch(g.backend.host.pointer,
                                                        source.STAGE1,pointer),0)
        self.assertEqual(g.event.arguments.count,1)
        self.assertEqual(g.event.arguments.depth,0)
        self.assertFalse(g.event.arguments.quarantined)
        self.assertEqual((g.owner._sequence,g.owner.pending),(0,[]))

    def test_state_and_hook_deviations_refuse_on_real_owner(self):
        cases=[('observer_registered',True),('state_pointer_nonnull',False),
               ('pre_hook',1),('post_hook',1),('subscriber_count',1),
               ('subscriber_count',False),('state_flags',1),('state_flags',2),
               ('state_flags',False)]
        # Mutate both copies together so the source-specific exact-state guard
        # is exercised too, rather than only the generic profile equality check.
        for key,value in cases:
            with self.subTest(key=key,value=value):
                g=self.graph()
                for name in ('empty_receiver_state','_receiver_profile'):
                    getattr(g.owner,name)[key]=value
                with self.assertRaises((ValueError,RuntimeError)):
                    g.owner.dispatch(source.STAGE1,self.fields(),0)
                self.assertFalse(any(s=='native_empty_presentation_callback_omitted'
                                     for s,_ in g.event.emitted))
        for key,value in [('dynamic_event_registration_present',True),
                          ('normalizer_transform_present',True),
                          ('per_thread_hook_present',True),
                          ('writer_metadata_callback_present',True),
                          ('entity_listener_count',1),('entity_listener_count',False)]:
            with self.subTest(key=key):
                g=self.graph();setattr(g.owner,key,value)
                with self.assertRaises((ValueError,RuntimeError)):
                    g.owner.dispatch(source.STAGE1,self.fields(),0)
                self.assertFalse(g.owner.pending)
        g=self.graph();g.backend._xp2_congress_presentation_source_identity=None
        with self.assertRaises((ValueError,RuntimeError)):
            g.owner.dispatch(source.STAGE1,self.fields(),0)

    def test_source_owner_and_lifetime_guards(self):
        with self.assertRaisesRegex(ValueError,'real shared A0'):
            source.validate_empty_owner(NS())
        memory={}
        def put(addr,raw):memory.update({addr+i:v for i,v in enumerate(raw)})
        def read(addr,n):return bytes(memory[addr+i] for i in range(n))
        core=NS(_handle=0x10000000,_civ6_host_execution_image=self.execution())
        backend=NS(core=core,load_abi=NS(core_sha256=source.XP2_CORE_SHA256),
            stage='prepared',poisoned=False,destroyed=False,check_thread=lambda:None)
        for rva,raw in source.core_fragments():put(core._handle+rva,raw)
        self.assertEqual(source.bind_owner(backend,core,read),source.SOURCE[1])
        for rva in (0x3bfdcd,0x5fc56f,0x3bf7e7,0x5faa1e,0x99ff6f,0x9a008f):
            address=core._handle+rva;memory[address]^=1
            with self.assertRaisesRegex(ValueError,'live producer'):
                source.bind_owner(backend,core,read)
            memory[address]^=1
        with self.assertRaisesRegex(ValueError,'prepared XP2 owner'):
            source.bind_owner(backend,NS(_handle=core._handle),read)
        profile=core._civ6_host_execution_image;core._civ6_host_execution_image=None
        with self.assertRaises(ValueError):source.bind_owner(backend,core,read)
        core._civ6_host_execution_image=profile
        for key,value in [('stage','active'),('poisoned',True),('destroyed',True)]:
            old=getattr(backend,key);setattr(backend,key,value)
            with self.assertRaises(ValueError):source.bind_owner(backend,core,read)
            setattr(backend,key,old)


if __name__=='__main__':unittest.main()
