"""Real argument reader/A0 owner/FIFO; source bytes and native memory are fixtures."""
from pathlib import Path
import struct
import threading
import unittest
from unittest.mock import patch

from civ6_host.runtime import empty_presentation_events as empty
from civ6_host.runtime import xp2_congress_presentation as congress
from civ6_host.runtime import xp2_wmd_fallout_source as source
from civ6_host.runtime.configuration_profiles import _copy
from civ6_host.runtime.event_argument_service import EventArgumentReader
from civ6_host.runtime.native.native_host import DiagnosticHost
import test_xp2_congress_presentation as congress_tests
import test_xp2_preload_services as preload_tests


class FalloutTests(unittest.TestCase):
    def graph(self, *, corrupt=False):
        original = empty.enable
        def install(owner, backend, profile):
            result = original(owner, backend, profile)
            if profile is congress:
                memory = owner.read.__self__
                for rva,raw in source.core_fragments():
                    memory.put(memory.core_base+rva,raw)
                if corrupt:
                    memory.put(memory.core_base+rva+len(raw)-1,bytes([raw[-1]^1]))
                original(owner,backend,source)
            return result
        with patch.object(empty,'enable',install):
            return congress_tests.CongressPresentationTests().graph()

    def fields(self, g, *, state=1, value=0, position=(12,34)):
        fields = {int(k,16):bytes.fromhex(v) for k,v in source.source()['retained_failure']['event']['fields'].items()}
        address = 0xa10000
        g.memory.put(address,struct.pack('<ii',*position))
        raw = bytearray(fields[source.POSITION_KEY]);struct.pack_into('<Q',raw,8,address)
        fields[source.POSITION_KEY] = bytes(raw)
        raw = bytearray(fields[source.STATE_KEY]);struct.pack_into('<I',raw,8,state)
        fields[source.STATE_KEY] = bytes(raw)
        raw = bytearray(fields[source.VALUE_KEY]);struct.pack_into('<I',raw,8,value)
        fields[source.VALUE_KEY] = bytes(raw)
        return fields

    def test_exact_current_source_route_and_dependency_pins(self):
        p = source.source()
        self.assertEqual(p['route']['name'],'GameCoreEvent::WMDFalloutChanged')
        self.assertEqual((p['route']['current_callback_rva'],p['route']['writer_rva']),('0x159050','0x138cf0'))
        self.assertEqual((p['route']['record_type'],p['route']['record_size']),(200,96))
        self.assertEqual(source.CALLBACKS[source.KIND],0x159960)
        self.assertIn(source.SOURCE[1],source.source_dependencies().values())
        self.assertIn(source.SCALAR_SOURCE[1],source.source_dependencies().values())
        for mutation in ('callback','return','padding_domain','relocation','receiver'):
            changed = _copy(p)
            if mutation=='callback':changed['route']['current_callback_rva']='0x158f40'
            elif mutation=='return':changed['contract']['normalizer_return']=1
            elif mutation=='padding_domain':changed['contract']['A1_domain']=[0,0xffffffff]
            elif mutation=='relocation':changed['bodies']['core']['0x5fac20']['fragments'][0]['dir64_relocations']=['0x5fac20']
            else:changed['contract']['empty_receiver']['subscriber_count']=1
            with self.subTest(mutation=mutation),self.assertRaises(ValueError):source._verify(changed)
        supplement = source._source(source.SCALAR_SOURCE)
        for mutation in ('domain','conversion','parent','instruction'):
            changed = _copy(supplement)
            if mutation=='domain':changed['admission_change']['fields'][hex(source.STATE_KEY)]['new_domain']['maximum']=255
            elif mutation=='conversion':changed['admission_change']['fields'][hex(source.VALUE_KEY)]['callback_conversion']='D6 == 1'
            elif mutation=='parent':changed['parent']['sha256']='0'*64
            else:changed['instructions'][0]['instructions'][0]['raw_hex']='90'*3
            with self.subTest(supplement=mutation),self.assertRaises(ValueError):source._verify_scalar_source(p,changed)

    def test_real_argument_owner_copies_retained_headers_without_fallback(self):
        g = self.graph()
        g.backend.host._check = DiagnosticHost._check.__get__(g.backend.host)
        from civ6_host.runtime import xp2_preload_source as preload
        for name in ('iterator_next','get_count'):
            for f in preload.body(name)['fragments']:
                g.memory.put(g.memory.core_base+int(f['start_rva'],16),bytes.fromhex(f['raw_hex']))
        g.memory.q(g.memory.core_base+0xabf080+0x1d8,g.memory.core_base+0x84e260)
        reader = EventArgumentReader.__new__(EventArgumentReader)
        reader.core,reader.base,reader.core_sha256 = g.backend.core,g.memory.core_base,source.XP2_CORE_SHA256
        reader.read,reader.thread,reader.closed = g.memory.read,threading.get_ident(),False
        g.event.arguments.reader = reader
        tree = preload_tests.XP2PreloadServices();tree.base=g.memory.core_base;tree.put=g.memory.put
        pointer,reader.next_node = tree.tree(self.fields(g))
        with patch('civ6_host.runtime.event_argument_service.validate_absent_scalar_a0',
                   side_effect=AssertionError('registered event reached absent fallback')):
            self.assertEqual(g.event.arguments.dispatch(g.backend.host.pointer,source.KIND,pointer),0)
        self.assertEqual((g.event.arguments.count,g.event.arguments.depth),(1,0))
        self.assertFalse(g.event.arguments.quarantined)
        self.assertEqual((g.owner._sequence,g.owner.pending),(0,[]))
        omitted = [row for stage,row in g.event.emitted if stage=='native_empty_presentation_callback_omitted'][-1]
        self.assertEqual(omitted['administrative_arguments']['coordinate'],[12,34])
        self.assertEqual(omitted['administrative_arguments']['source_a1_state'],1)
        self.assertFalse(omitted['administrative_arguments']['exe_boolean'])
        self.assertFalse(omitted['public_visibility_qualified'])
        self.assertEqual(omitted['records_enqueued'],0)

    def test_borrowed_pair_is_copied_and_fifo_counters_remain_exact(self):
        g = self.graph();fields = self.fields(g,state=255,position=(-0x80000000,0x7fffffff))
        decoded = source.decode_fields(source.KIND,fields,g.memory.read)
        g.memory.put(0xa10000,b'\0'*8)
        self.assertEqual(decoded.position,(-0x80000000,0x7fffffff))
        self.assertFalse(decoded.to_admin()['borrowed_pointer_retained'])
        pending = bytes(range(96));g.owner.pending.append(pending)
        g.owner.deferred.host_notification_counter=3;g.owner.deferred.host_metadata_counter=2
        before=(g.owner._sequence,tuple(g.owner.pending),g.owner.host_notification_counter,g.owner.host_metadata_counter)
        with patch.object(g.owner,'_dispatch_fields',side_effect=AssertionError('generic gameplay codec used')):
            self.assertEqual(g.owner.dispatch(source.KIND,fields,0),0)
        self.assertEqual((g.owner._sequence,tuple(g.owner.pending),g.owner.host_notification_counter,g.owner.host_metadata_counter),before)
        self.assertIs(g.owner.pending[0],pending)
        self.assertIsNone(g.owner._foundation_borrow)

    def test_unknown_shape_scalar_domains_and_pointer_copy_refuse(self):
        g = self.graph();base = self.fields(g)
        cases=[]
        for key,offset,value in ((source.SELECTOR_KEY,8,1),(source.VALUE_KEY,20,1),
                                (source.STATE_KEY,0,3),(source.STATE_KEY,20,1),
                                (source.POSITION_KEY,16,7),(source.POSITION_KEY,20,0)):
            bad=dict(base);raw=bytearray(bad[key]);struct.pack_into('<I',raw,offset,value);bad[key]=bytes(raw);cases.append(bad)
        bad=dict(base);raw=bytearray(bad[source.POSITION_KEY]);struct.pack_into('<Q',raw,8,0);bad[source.POSITION_KEY]=bytes(raw);cases.append(bad)
        cases += [{k:v for k,v in base.items() if k!=source.STATE_KEY},{**base,7:base[source.VALUE_KEY]}]
        for bad in cases:
            with self.subTest(fields=bad),self.assertRaises(ValueError):
                source.decode_fields(source.KIND,bad,g.memory.read)
        with self.assertRaises(ValueError):source.decode_fields(0xdeadbeef,base,g.memory.read)
        with self.assertRaises(ValueError):source.decode_fields(source.KIND,base,lambda *args:b'')

    def test_uint32_value_uses_native_nonzero_boolean_and_live_source_guard(self):
        g = self.graph()
        for value in (0,2,0x80000000,0xffffffff):
            fields = self.fields(g,value=value,state=value)
            decoded = source.decode_fields(source.KIND,fields,g.memory.read)
            self.assertEqual(decoded.to_admin()['source_d6_value'],value)
            self.assertEqual(decoded.to_admin()['source_a1_state'],value)
            self.assertIs(decoded.to_admin()['exe_boolean'],value!=0)
            self.assertEqual(g.owner.dispatch(source.KIND,fields,0),0)
        with self.assertRaisesRegex(ValueError,'live Core source differs'):
            self.graph(corrupt=True)

    def test_receiver_hooks_and_foreign_owner_or_source_refuse(self):
        for key,value in (('subscriber_count',1),('pre_hook',1),('state_flags',1),('state_pointer_nonnull',False)):
            g=self.graph();fields=self.fields(g)
            for name in ('empty_receiver_state','_receiver_profile'):getattr(g.owner,name)[key]=value
            with self.subTest(receiver=key),self.assertRaises((ValueError,RuntimeError)):
                g.owner.dispatch(source.KIND,fields,0)
        for key in ('normalizer_transform_present','per_thread_hook_present','writer_metadata_callback_present'):
            g=self.graph();fields=self.fields(g)
            setattr(g.owner,key,True)
            with self.subTest(hook=key),self.assertRaises((ValueError,RuntimeError)):
                g.owner.dispatch(source.KIND,fields,0)
        g=self.graph();fields=self.fields(g)
        g.backend._xp2_wmd_fallout_source_identity=None
        with self.assertRaises(ValueError):g.owner.dispatch(source.KIND,fields,0)
        self.assertFalse(any(s=='native_empty_presentation_callback_omitted' for s,_ in g.event.emitted))


if __name__=='__main__':unittest.main()
