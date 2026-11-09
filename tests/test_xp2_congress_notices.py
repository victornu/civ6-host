"""Actual shared argument/A0/FIFO composition; native memory is a fixture."""
import struct
import threading
import unittest
from unittest.mock import patch

from civ6_host.runtime import empty_presentation_events as empty
from civ6_host.runtime import xp2_congress_presentation as stages
from civ6_host.runtime import xp2_congress_notice_source as source
from civ6_host.runtime.configuration_profiles import _copy
from civ6_host.runtime.event_argument_service import EventArgumentReader
from civ6_host.runtime.native.native_host import DiagnosticHost
import test_xp2_congress_presentation as stage_tests
import test_xp2_preload_services as preload_tests
from test_xp1_turn_a0 import scalar


class CongressNoticeTests(unittest.TestCase):
    def graph(self,*,corrupt=False):
        original=empty.enable
        def install(owner,backend,profile):
            result=original(owner,backend,profile)
            if profile is stages:
                memory=owner.read.__self__
                for rva,raw in source.core_fragments():memory.put(memory.core_base+rva,raw)
                if corrupt:memory.put(memory.core_base+rva+len(raw)-1,bytes([raw[-1]^1]))
                original(owner,backend,source)
            return result
        with patch.object(empty,'enable',install):return stage_tests.CongressPresentationTests().graph()

    def fields(self,value=0):
        # Unused scalar padding need not be zero, as the retained Stage1
        # header already demonstrates for the same tag-3/tag-2 descriptor ABI.
        result={source.SELECTOR_KEY:scalar(3,0),source.VALUE_KEY:scalar(2,value)}
        for key,raw in result.items():
            changed=bytearray(raw);changed[4:8]=b'PAD!';changed[12:16]=b'KEEP';result[key]=bytes(changed)
        return result

    def test_pinned_routes_only_admit_the_two_joined_producers(self):
        p=source.source()
        self.assertEqual(source.KINDS,frozenset((0x54e4377b,0xfdc05d8b)))
        self.assertIn(source.SOURCE[1],source.source_dependencies().values())
        self.assertEqual(source.CURRENT_CALLBACKS,{0x54e4377b:0x159230,0xfdc05d8b:0x1595f0})
        self.assertEqual(source.CALLBACKS,{0x54e4377b:0x159b40,0xfdc05d8b:0x159f00})
        for change in ('extra_kind','callback','metadata','receiver','return','relocation'):
            bad=_copy(p)
            if change=='extra_kind':bad['qualified_source_kinds'].append('0x697de853')
            elif change=='callback':bad['routes']['0x54e4377b']['callback_rva']='0x159b40'
            elif change=='metadata':bad['routes']['0xfdc05d8b']['metadata_flag']=0
            elif change=='receiver':bad['shared_contract']['receiver_guards']['subscriber_count']=1
            elif change=='return':bad['shared_contract']['explicit_normalizer_return']=1
            else:bad['bodies']['core']['0x5fc4f0']['fragments'][0]['dir64_relocations']=['0x5fc4f0']
            with self.subTest(change=change),self.assertRaises(ValueError):source._verify(bad)

    def test_real_argument_service_routes_both_uint32_scalars_without_cycle_callbacks(self):
        g=self.graph()
        g.backend.host._check=DiagnosticHost._check.__get__(g.backend.host)
        from civ6_host.runtime import xp2_preload_source as preload
        for name in ('iterator_next','get_count'):
            for f in preload.body(name)['fragments']:
                g.memory.put(g.memory.core_base+int(f['start_rva'],16),bytes.fromhex(f['raw_hex']))
        g.memory.q(g.memory.core_base+0xabf080+0x1d8,g.memory.core_base+0x84e260)
        reader=EventArgumentReader.__new__(EventArgumentReader)
        reader.core,reader.base,reader.core_sha256=g.backend.core,g.memory.core_base,source.XP2_CORE_SHA256
        reader.read,reader.thread,reader.closed=g.memory.read,threading.get_ident(),False
        g.event.arguments.reader=reader
        tree=preload_tests.XP2PreloadServices();tree.base=g.memory.core_base;tree.put=g.memory.put
        with patch.object(stages,'record_callback',side_effect=AssertionError('notice entered Stage/Finished observer')), \
             patch('civ6_host.runtime.event_argument_service.validate_absent_scalar_a0',
                   side_effect=AssertionError('registered notice used absent fallback')):
            for kind in sorted(source.KINDS):
                for value in (0,63,64,0x80000000,0xffffffff):
                    pointer,reader.next_node=tree.tree(self.fields(value))
                    self.assertEqual(g.event.arguments.dispatch(g.backend.host.pointer,kind,pointer),0)
        self.assertEqual((g.event.arguments.count,g.event.arguments.depth),(10,0))
        self.assertFalse(g.event.arguments.quarantined)
        self.assertEqual((g.owner._sequence,g.owner.pending),(0,[]))
        rows=[row for stage,row in g.event.emitted if stage=='native_empty_presentation_callback_omitted']
        self.assertEqual(len(rows),10)
        self.assertEqual({row['dispatch_kind'] for row in rows},{hex(k) for k in source.KINDS})
        for row in rows:
            admin=row['administrative_arguments']
            self.assertFalse(admin['congress_stage_or_finished']);self.assertFalse(admin['ballot_acknowledgement'])
            self.assertFalse(row['public_visibility_qualified']);self.assertEqual(row['records_enqueued'],0)

    def test_fifo_and_notification_scope_preserved_with_no_getter(self):
        g=self.graph();pending=bytes(range(96));g.owner.pending.append(pending)
        g.owner.deferred.host_notification_counter=3;g.owner.deferred.host_metadata_counter=2
        before=(g.owner._sequence,tuple(g.owner.pending),g.owner.host_notification_counter,g.owner.host_metadata_counter)
        def unexpected(*args):self.fail('Scalar notice requested native data')
        with patch.object(g.owner,'_dispatch_fields',side_effect=AssertionError('gameplay codec used')), \
             patch.object(stages,'record_callback',side_effect=AssertionError('Stage/Finished observer used')):
            for kind in source.KINDS:
                decoded=source.decode_fields(kind,self.fields(0xffffffff),unexpected)
                self.assertEqual(decoded.value,0xffffffff)
                self.assertEqual(g.owner.dispatch(kind,self.fields(0xffffffff),0),0)
        self.assertEqual((g.owner._sequence,tuple(g.owner.pending),g.owner.host_notification_counter,g.owner.host_metadata_counter),before)
        self.assertIs(g.owner.pending[0],pending);self.assertIsNone(g.owner._foundation_borrow)

    def test_unresolved_kinds_and_malformed_fields_remain_refused(self):
        g=self.graph();fields=self.fields()
        for kind in source.EXCLUDED:
            self.assertFalse(g.owner.handles_kind(kind))
            with self.assertRaises(ValueError):source.decode_fields(kind,fields,g.memory.read)
        for kind in source.KINDS:
            bad=[{},dict(fields,extra=scalar(2,1)),{source.SELECTOR_KEY:scalar(3,0)},
                 {**fields,source.SELECTOR_KEY:scalar(3,1)},
                 {**fields,source.VALUE_KEY:scalar(3,1)},
                 {**fields,source.VALUE_KEY:bytearray(scalar(2,1))}]
            for key in fields:
                for offset in (16,20):
                    raw=bytearray(fields[key]);raw[offset]=1;bad.append({**fields,key:bytes(raw)})
            for value in bad:
                with self.subTest(kind=kind,value=value),self.assertRaises(ValueError):
                    source.decode_fields(kind,value,g.memory.read)
        with self.assertRaises(ValueError):source.decode_fields(True,fields,g.memory.read)

    def test_live_source_foreign_owner_and_nonempty_receiver_refuse(self):
        with self.assertRaisesRegex(ValueError,'live Core source differs'):self.graph(corrupt=True)
        for key,value in (('subscriber_count',1),('pre_hook',1),('state_flags',1)):
            g=self.graph()
            for name in ('empty_receiver_state','_receiver_profile'):getattr(g.owner,name)[key]=value
            with self.subTest(receiver=key),self.assertRaises((ValueError,RuntimeError)):
                g.owner.dispatch(source.EMERGENCY_READY,self.fields(),0)
        for key in ('normalizer_transform_present','per_thread_hook_present','writer_metadata_callback_present'):
            g=self.graph();setattr(g.owner,key,True)
            with self.subTest(hook=key),self.assertRaises((ValueError,RuntimeError)):
                g.owner.dispatch(source.SPECIAL_SESSION,self.fields(),0)
        g=self.graph();g.backend._xp2_congress_notice_source_identity=None
        with self.assertRaises(ValueError):g.owner.dispatch(source.SPECIAL_SESSION,self.fields(),0)
        self.assertFalse(any(stage=='native_empty_presentation_callback_omitted' for stage,_ in g.event.emitted))


if __name__=='__main__':unittest.main()
