"""Counter-independent scope integration and lifecycle fixtures; never calls GameCore."""
import hashlib
import struct
import unittest
from unittest.mock import patch

from civ6_host.runtime.a0_family_source import family_profile
from civ6_host.runtime.a0_notification_scope_source import notification_scope_profile
from civ6_host.runtime.native.native_host_events import SharedHostEventDispatch
import test_a0_family_service as fixtures


SPECIAL = 0x5A9A0329


def scalar(tag, value):
    return struct.pack('<H6xQII', tag, value, 0, 0)


def pointer(tag, address):
    return struct.pack('<H6xQII', tag, address, 8, 0x21000001)


def fields(kind):
    result = {0xA1E5A149: scalar(3, 0xFFFFFFFF)}
    if kind in (0x3FEAAD02, 0xBF48FDA8):
        result.update({0xD6FCF3E4: scalar(2, 0x80000000),
                       0xA1FBC372: scalar(2, 11), 0x38F292C8: scalar(2, 0xFFFFFFFF)})
    if kind in (0x1F943311, 0xB1A27578, 0xF7807FF9, 0x13AE3A55,
                0x265857F7, 0xD857B21B):
        result[0x8C468E3C] = pointer(0, 0xA000)
    if kind in (0xB1A27578, 0xF7807FF9, 0x13AE3A55, 0xD857B21B):
        result[0xD6FCF3E4] = scalar(2, 0x80000000)
    if kind == 0xD857B21B:
        result.update({0xF0548BB7: pointer(0x400, 0xB000),
                       0xA1FBC372: scalar(2, 11), 0x38F292C8: scalar(2, 0xFFFFFFFF)})
    if kind == 0xF26F3ACF:
        result[0xEAB69E5A] = pointer(0x400, 0xB000)
    return result


class A0NotificationScopeServiceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.profile = family_profile()
        cls.scope = notification_scope_profile()

    def fixture(self, *, enable=True):
        h,d,a,c,r,before,bindings = fixtures.A0FamilyServiceTests.fixture(self)
        def read(address, size):
            self.assertEqual(size, 8)
            return {0xA000: struct.pack('<ii', -17, 42),
                    0xB000: struct.pack('<HHI', 3, 0xBEEF, 0x20001)}[address]
        r.read.side_effect = read
        if enable:
            c.enable_notification_scopes()
        return h,d,a,c,r,before,bindings

    def send(self, h, a, r, kind):
        r.fields.return_value = fields(kind)
        return a.dispatch(h.pointer, kind, 0x9000)

    def test_profile_is_exact_immutable_subset_and_dispatcher_is_shared(self):
        self.assertEqual(len(self.scope.records), 10)
        self.assertEqual(set(self.scope.records), {
            0x1F943311, 0x3FEAAD02, 0xBF48FDA8, 0x8FEF0D8E,
            0xB1A27578, 0xF7807FF9, 0x13AE3A55, 0x265857F7, 0xD857B21B, 0xF26F3ACF})
        self.assertEqual([k for k, v in self.scope.records.items() if v[2] == 4],
                         [0x3FEAAD02, 0xBF48FDA8, 0xF26F3ACF])
        with self.assertRaises(TypeError):
            self.scope.records[1] = (1, 96, 0)
        h,d,a,c,r,_,_ = self.fixture()
        self.assertIs(type(c)._dispatch_fields, SharedHostEventDispatch._dispatch_fields)
        a.close(); d.close()

    def test_enable_is_explicit_idle_only_and_does_not_repair_scope(self):
        for fault in ('duplicate', 'pending', 'dispatch', 'arguments', 'drain', 'N', 'M'):
            with self.subTest(fault=fault):
                h,d,a,c,r,_,_ = self.fixture(enable=fault == 'duplicate')
                if fault == 'pending': d.pending.append(b'existing')
                if fault == 'dispatch': c.active_kind = 1
                if fault == 'arguments': a.depth = 1
                if fault == 'drain': d._draining_empty_receivers = True
                if fault == 'N': d.host_notification_counter = 2
                if fault == 'M': d.host_metadata_counter = 3
                before = (d.host_notification_counter, d.host_metadata_counter, list(d.pending))
                with self.assertRaises(ValueError): c.enable_notification_scopes()
                self.assertEqual(before, (d.host_notification_counter, d.host_metadata_counter, d.pending))

    def test_scoped_records_match_zero_scope_bytes_and_preserve_all_counter_cases(self):
        for kind, (record_type, size, flag) in self.scope.records.items():
            h0,d0,a0,c0,r0,_,_ = self.fixture(enable=False)
            self.send(h0,a0,r0,kind); expected = d0.pending[0]
            d0.drain(); a0.close(); d0.close()
            for n,m in ((1,0), (2,1), (2,7), (0,7), (0xFFFFFFFF,0xFFFFFFFF)):
                with self.subTest(kind=hex(kind), N=n, M=m):
                    h,d,a,c,r,before,bindings = self.fixture()
                    d.host_notification_counter, d.host_metadata_counter = n,m
                    self.assertEqual(self.send(h,a,r,kind), 0)
                    self.assertEqual(d.pending, [expected])
                    self.assertEqual(struct.unpack_from('<III',expected), (size,record_type,1))
                    self.assertEqual(struct.unpack_from('<I',expected,72)[0], flag)
                    self.assertEqual((d.host_notification_counter,d.host_metadata_counter), (n,m))
                    reads = r.read.call_count
                    self.assertEqual(d.drain(),1); self.assertEqual(r.read.call_count,reads)
                    self.assertEqual(d.consumed_digest.hexdigest(),hashlib.sha256(expected).hexdigest())
                    # Fixture cleanup only; no claim that an engine resets open scopes.
                    d.host_notification_counter=d.host_metadata_counter=0
                    a.close();d.close()
                    self.assertEqual(list(h.vtable),before);self.assertEqual(h._slot_bindings,bindings)

    def test_nested_host_callbacks_preserve_fifo_and_do_not_flush(self):
        h,d,a,c,r,_,_ = self.fixture()
        d.host_notification(h.pointer,SPECIAL); d.host_notification(h.pointer,SPECIAL)
        self.send(h,a,r,0x3FEAAD02)
        d.host_notification_end(h.pointer,SPECIAL)
        self.assertEqual((d.host_notification_counter,d.host_metadata_counter),(1,1))
        self.send(h,a,r,0x8FEF0D8E)
        d.host_notification_end(h.pointer,SPECIAL)
        self.assertEqual((d.host_notification_counter,d.host_metadata_counter),(0,0))
        self.assertEqual((len(d.pending),d.consumed_count),(2,0))
        self.assertEqual([struct.unpack_from('<I',r,8)[0] for r in d.pending],[1,2])
        self.assertEqual(d.drain(),2);a.close();d.close()

    def test_unenabled_nonmembers_and_resource_variant_refuse_before_pointer_read(self):
        for enabled,kind,extra in ((False,0x1F943311,False),(True,0x52E2805C,False),
                                    (True,0x30AE2A3D,False),(True,0x265857F7,True)):
            h,d,a,c,r,_,_ = self.fixture(enable=enabled); d.host_notification_counter=1
            r.fields.return_value=fields(kind)
            if extra:
                r.fields.return_value[0x74C62F28]=scalar(2,1)
                r.fields.return_value[0x8C468E3C]=pointer(13,0xA000)
            with self.assertRaises(ValueError):a.dispatch(h.pointer,kind,0x9000)
            r.read.assert_not_called();self.assertEqual(d.pending,[])
            self.assertEqual(d.host_notification_counter,1)

    def test_resource_typed_position_variant_retains_existing_zero_scope_behavior(self):
        h,d,a,c,r,_,_=self.fixture()
        r.fields.return_value=fields(0x265857F7)
        r.fields.return_value[0x74C62F28]=scalar(2,1)
        r.fields.return_value[0x8C468E3C]=pointer(13,0xA000)
        self.assertEqual(a.dispatch(h.pointer,0x265857F7,0x9000),0)
        self.assertEqual(struct.unpack_from('<II',d.pending[0]),(96,0x8D))
        self.assertEqual(d.drain(),1);a.close();d.close()

    def test_bad_counter_and_capacity_refuse_before_borrow(self):
        for value in (True,-1,1<<32,1.5):
            for name in ('host_notification_counter','host_metadata_counter'):
                h,d,a,c,r,_,_=self.fixture();setattr(d,name,value)
                with self.assertRaises(ValueError):self.send(h,a,r,0x1F943311)
                r.read.assert_not_called();self.assertEqual(d.pending,[])
        h,d,a,c,r,_,_=self.fixture();d.host_notification_counter=1;d.limit=0
        with self.assertRaises(RuntimeError):self.send(h,a,r,0x1F943311)
        r.read.assert_not_called();self.assertEqual(d.pending,[])

    def test_metadata_or_counter_mutation_before_enqueue_is_refused(self):
        for mutation in ('flag','counter'):
            h,d,a,c,r,_,_=self.fixture();d.host_notification_counter=1
            from civ6_host.runtime.native import native_event_8fef0d8e as event
            original=event.encode_record
            def altered(*args,**kwargs):
                record=bytearray(original(*args,**kwargs))
                if mutation=='flag':struct.pack_into('<I',record,72,4)
                else:d.host_metadata_counter=9
                return bytes(record)
            with patch.object(event,'encode_record',side_effect=altered):
                with self.assertRaises(RuntimeError):self.send(h,a,r,0x8FEF0D8E)
            self.assertEqual(d.pending,[]);self.assertTrue(a.quarantined and c.quarantined)

    def test_m_only_post_enqueue_failure_retains_record_and_forbids_replay(self):
        h,d,a,c,r,_,_=self.fixture();d.host_metadata_counter=7
        original=d._enqueue
        def enqueue(record):
            original(record);d.host_metadata_counter=8
        d._enqueue=enqueue
        with self.assertRaises(RuntimeError):self.send(h,a,r,0x8FEF0D8E)
        self.assertEqual((len(d.pending),d._sequence),(1,1))
        self.assertEqual(d.host_metadata_counter,8)
        with self.assertRaises(RuntimeError):self.send(h,a,r,0x8FEF0D8E)
        self.assertEqual(len(d.pending),1)

    def test_replaced_profile_is_not_repaired(self):
        h,d,a,c,r,_,_=self.fixture();c.notification_scope_profile=object()
        with self.assertRaises(RuntimeError):self.send(h,a,r,0x8FEF0D8E)
        self.assertEqual(d.pending,[])

    def test_separately_admitted_controller_and_player_kinds_still_cannot_enter_scope(self):
        for kind in (0x21535587,0x8953F126,0x20F2116E):
            h,d,a,c,r,_,_=self.fixture();d.host_notification_counter=1
            # Model membership from another installed family, without native ownership.
            with patch.object(c,'handles_kind',return_value=True), patch.object(c,'_dispatch_fields') as dispatch:
                with self.assertRaises(ValueError):c.dispatch(kind,{},None)
                dispatch.assert_not_called()
            self.assertEqual(d.pending,[]);self.assertEqual(d.host_notification_counter,1)

    def test_nonempty_receiver_and_bad_source_shape_remain_refusals(self):
        for fault in ('receiver','hook','F054'):
            h,d,a,c,r,_,_=self.fixture();d.host_notification_counter=1
            if fault=='receiver':c.empty_receiver_state['subscriber_count']=1
            if fault=='hook':c.empty_receiver_state['pre_hook']=123
            r.fields.return_value=fields(0xB1A27578)
            if fault=='F054':r.fields.return_value[0xF0548BB7]=pointer(0x400,0xB000)
            with self.assertRaises((ValueError,RuntimeError)):a.dispatch(h.pointer,0xB1A27578,0x9000)
            self.assertEqual(d.pending,[]);r.read.assert_not_called()
            self.assertEqual((d.host_notification_counter,d.host_metadata_counter),(1,0))

    def test_scoped_consumer_failure_is_not_replayed(self):
        h,d,a,c,r,_,_=self.fixture();d.host_notification_counter=1
        self.send(h,a,r,0x8FEF0D8E)
        d.emit.side_effect=OSError('receipt sink failed after consume')
        with self.assertRaises(OSError):d.drain()
        self.assertEqual((d.consumed_count,len(d.pending)),(1,0))
        self.assertEqual(d.host_notification_counter,1)
        with self.assertRaises(RuntimeError):d.drain()
        self.assertEqual(d.emit.call_count,1)

    def test_notification_descriptor_is_copied_once_before_enqueue_and_drain(self):
        h,d,a,c,r,before,bindings=self.fixture()
        memory=bytearray(struct.pack('<HHI',3,0x26,0x20001))
        r.read.side_effect=lambda address,size:bytes(memory)
        d.host_notification(h.pointer,SPECIAL)
        enqueue=d._enqueue
        def expire_pointer(record):
            self.assertTrue(c._found_city_producing)
            self.assertEqual((d.host_notification_counter,d.host_metadata_counter),(1,0))
            self.assertEqual(record[88:96],bytes(memory))
            memory[:]=b'\xff'*8
            return enqueue(record)
        d._enqueue=expire_pointer
        self.assertEqual(self.send(h,a,r,0xF26F3ACF),0)
        r.read.assert_called_once_with(0xB000,8)
        self.assertEqual(struct.unpack_from('<HHI',d.pending[0],88),(3,0x26,0x20001))
        self.assertFalse(c._found_city_producing or c._found_city_poisoned)
        d.host_notification_end(h.pointer,SPECIAL)
        self.assertEqual(d.drain(),1)
        r.read.assert_called_once_with(0xB000,8)
        a.close();d.close()
        self.assertEqual(list(h.vtable),before);self.assertEqual(h._slot_bindings,bindings)

    def test_notification_live_copy_refuses_reentry_across_actual_service_owners(self):
        h,d,a,c,r,_,_=self.fixture()
        d.host_notification(h.pointer,SPECIAL)
        def read(address,size):
            self.assertTrue(c._found_city_producing)
            for operation in (
                    lambda:a.dispatch(h.pointer,0xF26F3ACF,0x9000),
                    lambda:d.host_notification(h.pointer,SPECIAL),
                    lambda:d.host_notification_end(h.pointer,SPECIAL),
                    lambda:d.cache_update(h.pointer,0,0),
                    d.drain,d.close,c.close):
                with self.assertRaises(RuntimeError):operation()
                self.assertEqual((d.host_notification_counter,d.host_metadata_counter,
                                  d._sequence,len(d.pending)),(1,0,0,0))
            return struct.pack('<HHI',3,0x26,17)
        r.read.side_effect=read
        self.assertEqual(self.send(h,a,r,0xF26F3ACF),0)
        d.host_notification_end(h.pointer,SPECIAL)
        self.assertEqual(d.drain(),1);a.close();d.close()

    def test_notification_failure_keeps_fifo_and_poison_no_replay_or_close(self):
        h,d,a,c,r,_,_=self.fixture();d.host_metadata_counter=7
        c.emit.side_effect=OSError('receipt failed after real enqueue')
        with self.assertRaises(OSError):self.send(h,a,r,0xF26F3ACF)
        self.assertTrue(c._found_city_poisoned and c.quarantined and a.quarantined)
        self.assertFalse(c._found_city_producing)
        self.assertEqual((len(d.pending),d._sequence,d.consumed_count),(1,1,0))
        self.assertEqual(d.host_metadata_counter,7)
        for operation in (lambda:self.send(h,a,r,0xF26F3ACF),d.drain,d.close,c.close):
            with self.assertRaises(RuntimeError):operation()
        self.assertEqual((len(d.pending),d._sequence,d.consumed_count),(1,1,0))

    def test_notification_refuses_nonempty_receiver_or_unqualified_envelope(self):
        for fault in ('listener','subscriber','tag','flags','size','missing_selector'):
            with self.subTest(fault=fault):
                h,d,a,c,r,_,_=self.fixture();d.host_metadata_counter=3
                raw=fields(0xF26F3ACF)
                if fault=='listener':c.entity_listener_count=1
                if fault=='subscriber':c.empty_receiver_state['subscriber_count']=1
                if fault=='tag':raw[0xEAB69E5A]=pointer(0,0xB000)
                if fault=='flags':raw[0xEAB69E5A]=struct.pack('<H6xQII',0x400,0xB000,8,1)
                if fault=='size':raw[0xEAB69E5A]=struct.pack('<H6xQII',0x400,0xB000,4,0x21000001)
                if fault=='missing_selector':del raw[0xA1E5A149]
                r.fields.return_value=raw
                with self.assertRaises((ValueError,RuntimeError)):a.dispatch(h.pointer,0xF26F3ACF,0x9000)
                r.read.assert_not_called();self.assertEqual(d.pending,[])
                self.assertEqual((d.host_notification_counter,d.host_metadata_counter),(0,3))

    def test_notification_scope_proof_and_parents_join_parent_source_closure(self):
        from civ6_host.runtime.a0_notification_scope_source import source_dependencies
        from civ6_host.runtime.native import native_f26f3acf_counter_scope as notification
        from qualify_xp1_configuration import notification_scope_source_pins
        from civ6_host.runtime.resource_resolution import resolve_path
        from civ6_host.runtime.paths import resource_root
        pins=source_dependencies()
        self.assertEqual(pins,notification_scope_source_pins())
        self.assertEqual(pins[str(resolve_path(notification.PROOF_PATH).resolve())],
                         notification.PROOF_SHA256)
        proof=notification.verify_source_evidence()
        for row in proof['parents'].values():
            self.assertEqual(pins[str(resolve_path(resource_root()/row['path']).resolve())],row['sha256'])

