"""Shared district producers on real A0/FIFO, with native calls replaced only."""
import ctypes as C
import struct
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from test_xp1_placement_events import Fixture as PlacementFixture, LAB, NATIVE_CALLBACK
from test_xp1_turn_a0 import scalar
from civ6_host.runtime import a0_district_damage as admission
from civ6_host.runtime import district_damage_profile as profile
from civ6_host.runtime.native import native_event_f74afc79 as damage
from civ6_host.runtime.native import native_event_47261a7d as combat


class Fixture(PlacementFixture):
    def enable(self):
        super().enable()
        sys.path.insert(0,str(LAB/'tools'))
        from extract_phase31_next_export import pefile
        pe=pefile.PE(profile.verify_source()['image']['path'],fast_load=True)
        old=self.owner.read
        def read(address,size):
            rva=address-self.memory.base
            if 0<=rva and rva+size<=pe.OPTIONAL_HEADER.SizeOfImage:
                raw=pe.get_data(rva,size)
                if len(raw)==size:return raw
            return old(address,size)
        self.owner.read=read
        try:admission.enable(self.owner,self.backend)
        finally:self.owner.read=old;pe.close()

    def __init__(self):
        super().__init__()
        self.missing=None;self.fail=None

    def factory(self,result,*args):
        fallback=super().factory(result,*args)
        def bind(target):
            if callable(target):return NATIVE_CALLBACK(result,*args)(target)
            for name,operation in profile.OPERATIONS.items():
                if target==self.backend.core._handle+self.abi.rva(operation):
                    return lambda *values:self.district_call(name,*values)
            return fallback(target)
        return bind

    def district_call(self,name,pointer,*args):
        if name==self.fail:raise RuntimeError('fixture district query failure')
        if (name=='get_player' and self.missing=='player') or (name=='collection_index' and self.missing=='item'):
            self.calls.append((name,pointer,*args));return 0
        if name=='item_position':
            self.calls.append((name,pointer,*args))
            assert pointer==self.objects['district'] and self.live['district']==1
            C.memmove(args[0],struct.pack('<ii',3,4),8);return args[0]
        if name=='item_hash':
            self.calls.append((name,pointer,*args))
            assert pointer==self.objects['district'] and args==(0x5e97d629,)
            return 0xaabbccdd
        return self.native(name,pointer,*args)

    def fields_for(self,kind):
        fields={0xa1e5a149:scalar(3,0x5e97d629 if kind==damage.EVENT_KIND else combat.SELECTOR),
                0xf343dc5a:self.make_blob(struct.pack('<HHI',0,3,13),1024)}
        if kind==damage.EVENT_KIND:
            fields.update({0xd6fcf3e4:scalar(2,27),0xa1fbc372:scalar(2,0)})
        return fields


class DistrictDamageTests(unittest.TestCase):
    def fixture(self):
        f=Fixture();self.addCleanup(f.close);return f

    def test_real_shared_producers_keep_native_item_alive_through_fifo_append(self):
        f=self.fixture();seen=[];append=f.deferred._enqueue
        def enqueue(record):
            seen.append((struct.unpack_from('<I',record,4)[0],dict(f.live)))
            return append(record)
        with patch.object(f.deferred,'_enqueue',side_effect=enqueue):
            for event in (damage,combat):
                self.assertEqual(f.owner.dispatch(event.EVENT_KIND,f.fields_for(event.EVENT_KIND),0),0)
        self.assertEqual([r[0] for r in seen],[159,161])
        for _,live in seen:
            self.assertEqual(live['district'],1)
            self.assertEqual(live['player'],0);self.assertEqual(live['district_collection'],0)
        first,second=f.deferred.pending
        self.assertEqual(struct.unpack_from('<iiI',first,96),(3,4,13))
        self.assertEqual(struct.unpack_from('<IIII',first,120),(0x5e97d629,27,0,0xaabbccdd))
        self.assertEqual(struct.unpack_from('<I',second,112)[0],13)
        self.assertFalse(any(f.live.values()))
        receipts=[r for s,r in f.emitted if s in ('native_district_damage_change_query_completed','native_district_combat_change_query_completed')]
        self.assertEqual(len(receipts),2)
        self.assertTrue(all(r['source_proof_sha256']==profile.SOURCE[1] for r in receipts))
        self.assertEqual(f.deferred.drain(),2)
        self.assertFalse(f.owner.pending);self.assertIsNone(f.owner._foundation_borrow)

    def test_genuine_null_lookup_keeps_native_sentinel_and_releases_prior_wrappers(self):
        for event in (damage,combat):
            for missing in ('player','item'):
                with self.subTest(event=event.EVENT_KIND,missing=missing):
                    f=self.fixture();f.missing=missing
                    f.owner.dispatch(event.EVENT_KIND,f.fields_for(event.EVENT_KIND),0)
                    record=f.deferred.pending[0]
                    self.assertEqual(struct.unpack_from('<ii',record,96 if event is damage else 104),(-9999,-9999))
                    self.assertFalse(any(f.live.values()))
                    self.assertFalse(any(c[0].startswith('item_') for c in f.calls))
                    self.assertEqual(f.deferred.drain(),1)

    def test_query_and_append_failures_release_owned_item_and_poison_actual_owner(self):
        for event,failure in ((damage,'item_hash'),(combat,'item_raw'),(damage,'append')):
            with self.subTest(event=event.EVENT_KIND,failure=failure):
                f=self.fixture();f.fail=failure
                with patch.object(f.deferred,'_enqueue',side_effect=RuntimeError('fixture append failure')) if failure=='append' else patch.object(f,'missing',f.missing):
                    with self.assertRaisesRegex(RuntimeError,'fixture'):
                        f.owner.dispatch(event.EVENT_KIND,f.fields_for(event.EVENT_KIND),0)
                self.assertFalse(any(f.live.values()));self.assertFalse(f.deferred.pending)
                self.assertTrue(f.owner.quarantined)
                name='damage' if event is damage else 'combat'
                self.assertTrue(getattr(f.owner,'_district_'+name+'_poisoned'))
                self.assertFalse(getattr(f.owner,'_district_'+name+'_producing'))
                self.assertIsNone(f.owner._foundation_borrow)

    def test_counters_bad_selector_poison_and_receiver_refuse_before_queries(self):
        for event in (damage,combat):
            for what in ('N','M','poison','reentry'):
                with self.subTest(event=event.EVENT_KIND,what=what):
                    f=self.fixture();before=list(f.calls)
                    if what=='N':f.deferred.host_notification_counter=1
                    elif what=='M':f.deferred.host_metadata_counter=1
                    else:setattr(f.owner,'_district_'+('damage' if event is damage else 'combat')+'_'+('poisoned' if what=='poison' else 'producing'),True)
                    with self.assertRaises((ValueError,RuntimeError)):
                        f.owner.dispatch(event.EVENT_KIND,f.fields_for(event.EVENT_KIND),0)
                    self.assertEqual(f.calls,before);self.assertFalse(f.owner.pending)
        f=self.fixture();fields=f.fields_for(combat.EVENT_KIND);fields[0xa1e5a149]=scalar(3,0)
        with self.assertRaisesRegex(ValueError,'selector'):
            f.owner.dispatch(combat.EVENT_KIND,fields,0)
        self.assertFalse(f.calls);self.assertFalse(f.owner.pending)

    def test_source_identity_facade_selection_and_base_defaults(self):
        f=self.fixture()
        self.assertIs(profile.select_tables(profile.BASE_CORE_SHA256,damage._TABLES),damage._TABLES)
        selected=profile.select_tables(profile.XP1_CORE_SHA256,damage._TABLES)
        self.assertEqual(selected['item'][0],f.abi.table('district'))
        self.assertEqual(dict(selected['item'][1])[88],f.abi.rva('district_hash'))
        self.assertEqual(set(profile.event_profile().record_types_by_kind),{damage.EVENT_KIND,combat.EVENT_KIND})
        with self.assertRaisesRegex(ValueError,'Unqualified'):
            profile.select_tables('unknown',damage._TABLES)
        row=next(iter(profile.verify_source()['functions'].values()))['instructions'][0]
        address=f.memory.base+int(row['va'],16)-0x180000000
        original=f.read
        def corrupt(ptr,size):
            raw=original(ptr,size)
            if ptr<=address<ptr+size:
                raw=bytearray(raw);raw[address-ptr]^=1;return bytes(raw)
            return raw
        with self.assertRaisesRegex(ValueError,'source bytes'):
            profile.verify_live(f.memory.base,corrupt)
        with self.assertRaisesRegex(ValueError,'owner mismatch'):
            profile.bind_owner(f.backend,object(),f.read)

    def test_unknown_engine_refuses_before_memory_and_base_api_addresses_stay_original(self):
        for event in (damage,combat):
            with self.subTest(event=event.EVENT_KIND):
                fields=event.Fields(0,13,0x5e97d629,27,0) if event is damage else event.Fields(0,13,combat.SELECTOR)
                read=lambda *args:(_ for _ in ()).throw(AssertionError('unknown engine read'))
                with self.assertRaisesRegex(ValueError,'Unqualified'):
                    with event.produce_record_lease(1,fields,core=SimpleNamespace(_handle=0x180000000),
                            context=1,read=read,normalizer_transform_present=False,profile={},core_sha256='unknown'):
                        self.fail('unknown engine admitted')
                with patch.object(C,'WINFUNCTYPE',side_effect=lambda result,*args:lambda address:address):
                    addresses=event.build_native_api(0x180000000)
                self.assertEqual(addresses['get_player'],0x180000000+4382880)
                self.assertEqual(addresses['item_raw'],0x180000000+4372864)
                self.assertEqual(addresses['item_variant'],0x180000000+4407024)
                self.assertEqual(len(addresses),10 if event is damage else 8)


if __name__=='__main__':unittest.main()
