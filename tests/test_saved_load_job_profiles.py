import hashlib
import json
import struct
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch

from civ6_host.runtime import saved_load_job_observer as jobs
from civ6_host.runtime.configuration_profiles import BASE_CORE_SHA256, XP1_CORE_SHA256, XP2_CORE_SHA256


def _memory_for_proof(proof, base):
    regions=[]
    if proof['schema']=='civ6_host.xp2_victory_job_static_source_profile.v2':
        bodies=proof['bodies'].values()
        table=proof['xp2_class']['vtable']
        table_rva=int(table['rva'],16)
        table_bytes=bytes.fromhex(table['raw_hex'])
    elif proof['schema']=='civ6_host.xp1_job_scheduler_source.v1':
        bodies=proof['functions'].values()
        table=proof['vtable'];table_rva=int(table['rva'],16)
        table_bytes=bytes.fromhex(table['bytes'])
    else:
        descriptor=proof['core_job_descriptor']
        bodies=(descriptor['execute_body'],descriptor['destructor_body'])
        table_rva=int(descriptor['vtable_va'],16)-0x180000000
        table_bytes=(base+int(descriptor['vtable_slots_0x00_and_0x08'][0],16)-0x180000000).to_bytes(8,'little')
        table_bytes+=(base+int(descriptor['vtable_slots_0x00_and_0x08'][1],16)-0x180000000).to_bytes(8,'little')
    if proof['schema'] in ('civ6_host.xp2_victory_job_static_source_profile.v2',
                           'civ6_host.xp1_job_scheduler_source.v1'):
        source_table_bytes=table_bytes
        destroy,execute=struct.unpack('<QQ',source_table_bytes[:16])
        table_bytes=(base+destroy-0x180000000).to_bytes(8,'little')
        table_bytes+=(base+execute-0x180000000).to_bytes(8,'little')+source_table_bytes[16:]
    for body in bodies:
        for fragment in body['fragments']:
            start=fragment.get('start_va')
            if start is None:start=hex(0x180000000+int(fragment['start_rva'],16))
            rva=int(start,16)-0x180000000
            data=b''.join(bytes.fromhex(row['bytes']) for row in fragment['instructions'])
            regions.append((base+rva,data))
    regions.append((base+table_rva,table_bytes))

    def read(address,size):
        for start,data in regions:
            if start<=address and address+size<=start+len(data):
                return data[address-start:address-start+size]
        raise AssertionError(f'unprovided source memory read {address:#x}+{size:#x}')
    return read


class SavedLoadJobProfileTests(unittest.TestCase):
    def backend(self, digest, module, proof, *, base=0x180000000):
        read=_memory_for_proof(proof,base)
        backend=NS(profile=NS(core_sha256=digest),load_abi=NS(core_sha256=digest),
                    core=NS(_handle=base,_name=module),runtime=NS(read=read))
        return backend

    def verify_with_source(self, digest, module, source, *, proof=None, base=0x180000000):
        if proof is None:proof=jobs._source(source)
        backend=self.backend(digest,module,proof,base=base)
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/module
            path.write_bytes(b'fixture bytes; never loaded')
            backend.core._name=str(path)
            fake_hash=NS(hexdigest=lambda:digest)
            with patch.object(jobs,'hashlib',NS(sha256=lambda _data:fake_hash)):
                return jobs._verify_core(backend),proof

    def test_three_manual_profiles_keep_existing_ids_and_exact_xp2_slots(self):
        self.assertEqual(jobs.CORE_JOB_PROFILES[BASE_CORE_SHA256]['profile'],1)
        self.assertEqual(jobs.CORE_JOB_PROFILES[XP1_CORE_SHA256]['profile'],2)
        xp2=jobs.CORE_JOB_PROFILES[XP2_CORE_SHA256]
        self.assertEqual((xp2['profile'],xp2['vtable_rva'],xp2['destroy_rva'],
                          xp2['execute_rva'],xp2['completed_offset']),
                         (3,0xA0B7D0,0x535800,0x536B00,0xF0))
        self.assertEqual(xp2['source'],jobs.XP2_SOURCE)

    def test_xp2_job_recipe_retains_the_selected_xp2_script_service_sources(self):
        host=Path(jobs.__file__).resolve().parents[3]
        manifest_path=host/'native/profiles/xp2-jobs/source-manifest.json'
        manifest=json.loads(manifest_path.read_text(encoding='utf-8'))
        files={row['path']:row['sha256'] for row in manifest['sources']}
        self.assertEqual(manifest['qualification'],'unqualified_source_build')
        self.assertEqual(manifest['parent_manifest']['path'],
                         'native/profiles/xp2-script-contexts/source-manifest.json')
        self.assertEqual(files['native/profiles/xp2-jobs/gamecore_python_host.c'],
                         jobs.XP2_HOST_COMPONENT_SHA)
        self.assertEqual(files['native/profiles/xp2-script-api/script_core_bindings_xp1.inc'],
                         '0b23390765c5917580baf79723d6c897457774fea1d357533c68a98de9246c27')
        self.assertEqual(files['native/profiles/xp2-mutable-map/script_game_event_result_map.inc'],
                         'b90214047bf68869cfd13c214d7791c2fc6df5c2c61a7fef1106468bc1a65edd')
        self.assertEqual(files['native/profiles/xp2-script-contexts/script_event_state_scope.inc'],
                         'cc882df725189f7e83a0f06bf43f3ff6d1395e0ba52d76871413a20b423b474a')

    def test_xp2_core_verifies_every_pinned_body_and_vtable_before_binding(self):
        result,proof=self.verify_with_source(XP2_CORE_SHA256,
            'GameCore_XP2_FinalRelease.dll',jobs.XP2_SOURCE)
        self.assertEqual(result['profile'],3)
        self.assertEqual(result['execute_rva'],0x536B00)
        self.assertEqual(result['completed_offset'],0xF0)
        self.assertEqual(result['source_sha256'],jobs.XP2_SOURCE[1])
        self.assertEqual(proof['xp2_class']['vtable']['sha256'],
                         hashlib.sha256(bytes.fromhex(proof['xp2_class']['vtable']['raw_hex'])).hexdigest())

    def test_xp1_and_base_exact_profile_ids_remain_source_selected(self):
        base,base_proof=self.verify_with_source(BASE_CORE_SHA256,
            'GameCore_Base_FinalRelease.dll',jobs.BASE_SCHEDULER_SOURCE)
        xp1,xp1_proof=self.verify_with_source(XP1_CORE_SHA256,
            'GameCore_XP1_FinalRelease.dll',jobs.SOURCE)
        self.assertEqual((base['profile'],base['execute_rva']),(1,0x3D75B0))
        self.assertEqual((xp1['profile'],xp1['execute_rva']),(2,0x465110))
        self.assertEqual(base['source_sha256'],jobs.BASE_SCHEDULER_SOURCE[1])
        self.assertEqual(xp1['source_sha256'],jobs.SOURCE[1])
        self.assertNotEqual(base_proof['schema'],xp1_proof['schema'])

    def test_preferred_image_base_relocation_keeps_all_three_slots_source_bound(self):
        relocated=0x700000000000
        cases=((BASE_CORE_SHA256,'GameCore_Base_FinalRelease.dll',jobs.BASE_SCHEDULER_SOURCE,1,0x3D75B0),
               (XP1_CORE_SHA256,'GameCore_XP1_FinalRelease.dll',jobs.SOURCE,2,0x465110),
               (XP2_CORE_SHA256,'GameCore_XP2_FinalRelease.dll',jobs.XP2_SOURCE,3,0x536B00))
        for digest,module,source,profile,execute in cases:
            with self.subTest(profile=profile):
                result,_=self.verify_with_source(digest,module,source,base=relocated)
                self.assertEqual(result['base'],relocated)
                self.assertEqual((result['profile'],result['execute_rva']),(profile,execute))

    def test_unknown_core_and_mismatched_xp2_profile_refuse_without_fallback(self):
        backend=NS(profile=NS(core_sha256='0'*64),load_abi=NS(core_sha256='0'*64))
        with self.assertRaisesRegex(ValueError,'No exact Base, XP1, or XP2'):
            jobs._verify_core(backend)
        proof=jobs._source(jobs.XP2_SOURCE)
        altered=dict(proof);altered['xp2_class']=dict(proof['xp2_class'],slots={
            '0x00_destructor':'0x463e40','0x08_execute':'0x465110'})
        with patch.object(jobs,'_source',return_value=altered),self.assertRaisesRegex(ValueError,'slots/completion'):
            self.verify_with_source(XP2_CORE_SHA256,'GameCore_XP2_FinalRelease.dll',
                                    jobs.XP2_SOURCE,proof=altered)

    def test_quiescent_snapshot_accepts_only_profile_matched_source_pin(self):
        snapshot=dict(schema=jobs.SCHEMA,profile=jobs.PROFILE,
            source_proof_sha256=jobs.XP2_SOURCE[1],core_identity={'profile':3},
            stable_read=True,memory_modified=False,concurrent_scheduler_supported=False,
            native_introspection_only=True,native_methods_called=True,spawn_active=0,
            registry_lock_raw=0,pending_items=0,
            slots=[dict(handle=i,occupied=False,count=0,items=[]) for i in range(1,65)],
            groups=[],submission_sequence=0)
        self.assertIs(jobs.require_quiescent(snapshot),snapshot)
        for wrong in (jobs.SOURCE[1],jobs.BASE_SCHEDULER_SOURCE[1],'0'*64):
            with self.subTest(wrong=wrong),self.assertRaisesRegex(ValueError,'source-bound'):
                jobs.require_quiescent(dict(snapshot,source_proof_sha256=wrong))

    def test_xp2_loaded_lifetime_owner_does_not_reuse_xp1_raw_leases(self):
        from civ6_host.runtime.xp1_loaded_lifetime import LoadedLifetime
        from civ6_host.runtime.xp2_loaded_lifetime_source import SOURCE as XP2_LIFETIME_SOURCE
        thread=(10,20)
        backend=NS(profile=NS(core_sha256=XP2_CORE_SHA256),load_abi=NS(core_sha256=XP2_CORE_SHA256),
            stage='loaded-lifetime-wrappers',
            busy=True,snapshot_phase='before',runtime=NS(thread=lambda:thread),thread=thread,
            poisoned=False,destroyed=False)
        lifetime=LoadedLifetime.__new__(LoadedLifetime)
        lifetime.owner=backend;lifetime.raw_loaded=True;lifetime.xp2_loaded=True;lifetime.lease=None
        lifetime.source_reference=XP2_LIFETIME_SOURCE;lifetime.check_job_snapshot=Mock()
        backend._loaded_lifetime=lifetime
        observer=jobs.SavedLoadJobObserver.__new__(jobs.SavedLoadJobObserver)
        observer.backend=backend;observer.core={'profile':3,'sha256':XP2_CORE_SHA256}
        self.assertTrue(observer._exclusive())
        lifetime.check_job_snapshot.assert_called_once_with()
        lifetime.lease=object()
        self.assertFalse(observer._exclusive())
        lifetime.lease=None;lifetime.raw_loaded=False
        self.assertFalse(observer._exclusive())
        lifetime.raw_loaded=True;lifetime.source_reference=('wrong','0'*64)
        self.assertFalse(observer._exclusive())

    def test_xp2_loaded_lifetime_snapshot_accepts_only_exact_completed_cache_lease(self):
        from civ6_host.runtime.xp1_loaded_lifetime import LoadedLifetime
        from civ6_host.runtime.loaded_cache_publication import LoadedCachePublication
        from civ6_host.runtime.xp2_loaded_lifetime_source import SOURCE as XP2_LIFETIME_SOURCE
        thread=(10,20);pins={'capture.json':'a'*64}
        backend=NS(profile=NS(core_sha256=XP2_CORE_SHA256),load_abi=NS(core_sha256=XP2_CORE_SHA256),
            stage='loaded-lifetime-wrappers',busy=True,snapshot_phase='before',
            runtime=NS(thread=lambda:thread),thread=thread,poisoned=False,destroyed=False)
        lifetime=LoadedLifetime.__new__(LoadedLifetime)
        lifetime.owner=backend;lifetime.raw_loaded=False;lifetime.xp2_loaded=True
        lifetime.source_reference=XP2_LIFETIME_SOURCE;lifetime.postload_source_dependencies=pins.copy()
        lifetime.check_job_snapshot=Mock()
        lease=LoadedCachePublication.__new__(LoadedCachePublication)
        lease.owner=backend;lease.lifetime=lifetime;lease.core_sha256=XP2_CORE_SHA256
        lifetime.lease=lease;backend._loaded_lifetime=lifetime
        observer=jobs.SavedLoadJobObserver.__new__(jobs.SavedLoadJobObserver)
        observer.backend=backend;observer.core={'profile':3,'sha256':XP2_CORE_SHA256}
        with patch('civ6_host.runtime.xp1_loaded_lifetime.source_dependencies',return_value=pins.copy()):
            self.assertTrue(observer._exclusive())
            lifetime.check_job_snapshot.assert_called_once_with()
            lifetime.postload_source_dependencies={'capture.json':'b'*64}
            self.assertFalse(observer._exclusive())
            lifetime.postload_source_dependencies=pins.copy();lease.lifetime=object()
            self.assertFalse(observer._exclusive())
            lease.lifetime=lifetime;backend.stage='loaded-lifetime-unloaded'
            self.assertTrue(observer._exclusive())


if __name__=='__main__':
    unittest.main()
