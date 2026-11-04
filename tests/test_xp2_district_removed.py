"""XP2 native-query selection and actual shared codec/lease; no DLL calls."""
import ctypes as C
import hashlib
from pathlib import Path
import struct
import unittest
from unittest.mock import patch
from civ6_host.runtime import a0_district_removed as event
from civ6_host.runtime import xp2_district_removed_source as source
from civ6_host.runtime.configuration_profiles import XP2_CORE_SHA256
import test_a0_district_removed as legacy


class XP2DistrictTests(unittest.TestCase):
    def fixture(self,**kw):return legacy.memory_fixture(tables=source.TABLES,**kw)
    def lease(self,f,diagnostic,**kw):
        return event.record_lease(19,f[0],20480,legacy.fields(),read=f[1],native_api=f[2],
            empty_receiver_state=dict(legacy.PROFILE),query_diagnostic=diagnostic,
            core_sha256=XP2_CORE_SHA256,**kw)

    def test_exact_source_profile_and_complete_retained_teardown_inventory(self):
        p=source.source();pins=event.source_dependencies(XP2_CORE_SHA256)
        self.assertTrue(all(hashlib.sha256(Path(path).read_bytes()).hexdigest()==digest for path,digest in pins.items()))
        self.assertEqual(len(p['bodies']),24)
        self.assertEqual(event.event_profile(XP2_CORE_SHA256).source_sha256,source.SOURCE[1])
        self.assertEqual([(r['kind'],r['queue'],r['count']) for r in p['retained_xp1_interval']['notifications']],
                         [('0x92492f56','0x62',14),('0xfdf12323','0xa0',14),('0x2842ce14','0x5f',9)])
        self.assertFalse(p['comparisons']['player_collection']['normalized_instructions_equal'])

    def test_live_verification_includes_leaf_targets_after_first_return(self):
        f=self.fixture();memory=f[4];base=f[0]._handle
        for body in source.source()['bodies'].values():
            for fragment in body['fragments']:
                for row in fragment['instructions']:memory[base+int(row['rva'],16)]=bytes.fromhex(row['bytes'])
        event.verify_live(base,20480,f[1],core_sha256=XP2_CORE_SHA256)
        for address in (base+0x58daa0,base+0x59ed97,base+0x596587,base+0xa11a80+0x130):
            with self.subTest(address=hex(address)):
                before=memory[address];memory[address]=bytes([before[0]^1])+before[1:]
                with self.assertRaises(ValueError):event.verify_live(base,20480,f[1],core_sha256=XP2_CORE_SHA256)
                memory[address]=before

    def test_native_api_uses_all_eight_xp2_targets_and_original_signatures(self):
        seen=[]
        def factory(result,*args):
            def bind(address):seen.append((address,result,args));return lambda *values:None
            return bind
        with patch.object(C,'WINFUNCTYPE',side_effect=factory):
            api=event._api(0x180000000,None,entries=source.ENTRIES)
        self.assertEqual(set(api),set(source.ENTRIES))
        self.assertEqual({address-0x180000000 for address,_,_ in seen},set(source.ENTRIES.values()))
        self.assertEqual(next(row[2] for row in seen if row[0]==0x180590360),(C.c_void_p,C.c_int32))

    def test_positive_native_queries_keep_item_owned_until_record_enqueue(self):
        f=self.fixture();diagnostic={}
        with self.lease(f,diagnostic) as record:
            self.assertEqual(record,event.codec.encode_record(19,legacy.fields(),event.codec.NativeValues(struct.pack('<HHI',0,2,22),5),**event.PROFILE))
            self.assertNotIn('release_item',[name for name,_ in f[3]])
            f[3].append(('enqueue',()))
        self.assertEqual([name for name,_ in f[3]],['get_player','player_collection','collection_index','release_collection','release_player','item_variant','item_raw','enqueue','release_item'])
        self.assertEqual(diagnostic['source_sha256'],source.SOURCE[1])

    def test_observed_native_null_branches_preserve_explicit_empty_receiver_policy(self):
        for null_player in (True,False):
            f=self.fixture(null_player=null_player,null_item=not null_player);diagnostic={}
            with self.lease(f,diagnostic) as record:
                self.assertEqual(record[104:120],bytes(8)+bytes.fromhex('ffff0000ffffffff'))
            self.assertEqual(diagnostic['read_skipped_reason'],'player-null' if null_player else 'item-null')
            self.assertTrue(diagnostic['native_null_result_observed'])
            self.assertNotIn('item_raw',[name for name,_ in f[3]])

    def test_foreign_xp1_facade_and_failed_native_query_cannot_publish(self):
        f=legacy.memory_fixture()
        with self.assertRaisesRegex(ValueError,'facade'):
            with self.lease(f,{}):self.fail('wrong engine published')
        f=self.fixture();f[2]['item_raw']=lambda _:(_ for _ in ()).throw(RuntimeError('native failure'))
        with self.assertRaisesRegex(RuntimeError,'native failure'):
            with self.lease(f,{}):self.fail('failed query published')
        self.assertEqual(f[3][-1][0],'release_item')


if __name__=='__main__':unittest.main()
