import hashlib,json,struct,unittest
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import Mock,patch
from civ6_host.runtime import a0_emergencies_updated as event
from civ6_host.runtime import a0_family_service
from civ6_host.runtime.deferred_service import DeferredService
from civ6_host.runtime.event_argument_service import EventArgumentService
from civ6_host.runtime.native import native_deferred_empty_profile as receivers
from civ6_host.runtime.native.native_host_events import encode_integer_player_event
from civ6_host.runtime.xp1_cache_publication import SavedCachePublication
from civ6_host.runtime.xp1_postload_candidate import FINISHED_STAGE
from test_deferred_service import Host

STATE=dict(observer_registered=False,state_pointer_nonnull=True,pre_hook=None,post_hook=None,subscriber_count=0,state_flags=0)
def fields():return {event.SELECTOR:struct.pack('<H6xQII',3,0,0,0)}

class PublicationEventsTests(unittest.TestCase):
    def fixture(self):
        host=Host();core=NS(_handle=0x200000000);read=Mock()
        for name in ('cache_update_profiles.verify_dispatch_live','cache_update_profiles.verify_notification_live',
                     'event_argument_source.verify_host_live'):
            patcher=patch('civ6_host.runtime.'+name,return_value={});patcher.start();self.addCleanup(patcher.stop)
        reader=NS(fields=Mock(return_value=fields()),read=read,close=Mock())
        patcher=patch('civ6_host.runtime.event_argument_service.EventArgumentReader',return_value=reader)
        patcher.start();self.addCleanup(patcher.stop)
        profile=NS(record_types_by_kind={0x008152EA:frozenset((0x109,))},record_sizes={0x109:96})
        patcher=patch('civ6_host.runtime.a0_family_source.family_profile',return_value=profile)
        patcher.start();self.addCleanup(patcher.stop)
        d=DeferredService(host,core,0x300000000,core_sha256=event.XP1_CORE_SHA256,read=read,emit=Mock(),
                          optional_preprocessor=None,queue_metadata_service=None)
        a=EventArgumentService(host,core,d.context,d,core_sha256=event.XP1_CORE_SHA256,read=read,emit=Mock(),
                               normalizer_transform=None,dynamic_registrations=())
        c=a.install_consumers(receiver_state=dict(STATE),pre_turn_immediate_state=dict(STATE),entity_listener_count=0)
        b=NS(core=core,context=d.context,prefix=NS(event_arguments=a,deferred_events=d),
             stage=FINISHED_STAGE,busy=False,poisoned=False,destroyed=False,runtime=NS(read=read),
             load_abi=NS(core_sha256=event.XP1_CORE_SHA256))
        publication=SavedCachePublication.__new__(SavedCachePublication)
        publication.owner=b;publication.native_attempted=False;b._xp1_publication_attempt=publication
        p=event.source();memory={}
        for body in (*p['producers'].values(),p['functions']['xp1_emitter'],p['functions']['xp1_map_setter']):
            for row in event.instructions(body):
                raw=bytes.fromhex(row['bytes']);addr=core._handle+int(row['va'],16)-0x180000000
                memory.update({addr+i:v for i,v in enumerate(raw)})
        read.side_effect=lambda addr,n:bytes(memory[addr+i] for i in range(n))
        return host,d,a,c,reader,publication,memory

    def test_actual_source_chain_and_receiver_row(self):
        p=event.source();self.assertEqual(len(p['refresh_direct_scan']),37)
        self.assertEqual(list(p['producers']),['0x76020'])
        self.assertEqual(receivers._ROWS[0x127]['event_name'],'GameCoreEvent::EmergenciesUpdated')
        for path,digest in event.source_dependencies().items():self.assertEqual(hashlib.sha256(Path(path).read_bytes()).hexdigest(),digest)
        r=event.encode(event.EVENT_KIND,fields(),1,normalizer_transform_present=False,optional_callback_present=False,queue_metadata_service=None)
        self.assertEqual(receivers.validate_empty_profile_record(r,**STATE)['record_type'],0x127)

    def test_codec_matches_writer_defined_bytes_and_has_no_cache_gate(self):
        r=event.encode(event.EVENT_KIND,fields(),23,normalizer_transform_present=False,optional_callback_present=False,queue_metadata_service=None)
        expected=bytearray(encode_integer_player_event(23,0,0));struct.pack_into('<I',expected,4,0x127)
        struct.pack_into('<I',expected,72,0)
        self.assertEqual(r,bytes(expected));self.assertEqual(r[84:],bytes(12))
        self.assertNotIn('ui_cache_callbacks_enabled',Path(event.__file__).read_text())

    def test_exact_publication_owner_and_live_code_before_admission(self):
        h,d,a,c,r,p,m=self.fixture()
        with self.assertRaisesRegex(ValueError,'actual saved'):c.enable_publication_events(object())
        p.owner.prefix.event_arguments=object()
        with self.assertRaisesRegex(ValueError,'idle original'):c.enable_publication_events(p)
        p.owner.prefix.event_arguments=a
        address=p.owner.core._handle+0x76020;m[address]^=1
        with self.assertRaisesRegex(ValueError,'emitter changed'):c.enable_publication_events(p)
        self.assertIsNone(c.publication_event_profile)
        m[address]^=1;c.enable_publication_events(p)
        with self.assertRaisesRegex(ValueError,'idle original'):c.enable_publication_events(p)

    def test_real_shared_argument_dispatch_preserves_fifo_and_payload_copy(self):
        h,d,a,c,r,p,m=self.fixture();c.enable_publication_events(p)
        # A preexisting Base integer notification and the expansion event use
        # the same queue/sequence, retaining every record until normal drain.
        original=encode_integer_player_event(1,2,3);d._enqueue(original)
        raw=fields();r.fields.return_value=raw
        self.assertEqual(a.dispatch(h.pointer,event.EVENT_KIND,0x1230),0)
        expected=event.encode(event.EVENT_KIND,fields(),2,normalizer_transform_present=False,optional_callback_present=False,queue_metadata_service=None)
        self.assertEqual(d.pending,[original,expected]);self.assertEqual(a.count,1)
        raw[event.SELECTOR]=bytes(24)
        self.assertEqual(d.pending[1],expected)
        self.assertEqual(d.drain(),2);self.assertEqual(d.pending,[])
        self.assertEqual(d.consumed_digest.hexdigest(),hashlib.sha256(original+expected).hexdigest())
        self.assertEqual(d.consumed_count,2);self.assertEqual(d.drain(),0)
        a.close();d.close()

    def test_event_requires_explicit_admission_before_native_callback(self):
        h,d,a,c,r,p,m=self.fixture()
        self.assertFalse(c.handles_kind(event.EVENT_KIND));self.assertFalse(c.handles_record(0x127))
        with self.assertRaisesRegex(ValueError,'registered EXE callback'):a.dispatch(h.pointer,event.EVENT_KIND,0x1230)
        self.assertEqual(d.pending,[])

    def test_unknown_fields_tags_selectors_and_hooks_are_not_silently_normalized(self):
        cases=[({},{}),({event.SELECTOR:bytes(24)},{}),
               ({event.SELECTOR:struct.pack('<H6xQII',3,1,0,0)},{}),
               (fields(),{'normalizer_transform_present':True}),
               (fields(),{'optional_callback_present':True}),(fields(),{'queue_metadata_service':object()})]
        for raw,overrides in cases:
            with self.subTest(raw=raw,overrides=list(overrides)):
                args=dict(normalizer_transform_present=False,optional_callback_present=False,queue_metadata_service=None);args.update(overrides)
                with self.assertRaises(ValueError):event.encode(event.EVENT_KIND,raw,1,**args)

    def test_nonempty_receiver_and_open_scope_refuse_without_losing_record(self):
        for mutation in ('subscriber','scope'):
            h,d,a,c,r,p,m=self.fixture();c.enable_publication_events(p)
            if mutation=='subscriber':c.empty_receiver_state['subscriber_count']=1
            else:d.host_notification_counter=1
            with self.assertRaises((ValueError,RuntimeError)):a.dispatch(h.pointer,event.EVENT_KIND,0x1230)
            self.assertEqual(d.pending,[]);self.assertTrue(a.quarantined)

    def test_unknown_followup_and_uncertain_consumer_do_not_fake_success(self):
        h,d,a,c,r,p,m=self.fixture();c.enable_publication_events(p)
        self.assertFalse(c.handles_kind(0x281D81D3))
        a.dispatch(h.pointer,event.EVENT_KIND,0x1230)
        with self.assertRaises(RuntimeError):a.close()
        d.emit.side_effect=OSError('receipt failed')
        with self.assertRaises(OSError):d.drain()
        self.assertEqual(d.consumed_count,1)
        with self.assertRaisesRegex(RuntimeError,'poisoned'):d.drain()
