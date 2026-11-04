"""Offline source/cache, catalogue and shared-service strictness checks."""
from pathlib import Path
from types import SimpleNamespace as NS
import hashlib
import sqlite3
import unittest
from unittest.mock import Mock, patch

from civ6_host.runtime import xp1_load_capability as candidate
from civ6_host.runtime.native import native_app_ownership as ownership
from civ6_host.runtime.native import native_host_capability_status as abi
from civ6_host.runtime.lan_capabilities import ClosedLanBranch, LAN
from civ6_host.runtime.native.native_source_cache import load_pinned_json
from civ6_host.runtime.paths import resource_root


class XP1CapabilityTests(unittest.TestCase):
    def test_real_frozen_source_profiles_match_named_subset_and_caller(self):
        proof, caller = candidate.source_profile()
        self.assertIsInstance(proof['catalogue_rows'], tuple)
        self.assertIsInstance(caller['caller']['fragments'], tuple)
        self.assertEqual(len(proof['catalogue_rows']), 92)
        self.assertEqual(caller['caller']['total_length'], 534)
        rows = tuple(r for f in caller['caller']['fragments'] for r in f['instructions'])
        self.assertEqual(len(rows), 119)
        call = [r for r in rows if r['va'] == '0x18003f75e']
        self.assertEqual(len(call), 1)
        self.assertEqual(call[0]['bytes'], 'ff9068010000')
        self.assertEqual(proof['contract']['mode_required'], ownership.HOTSEAT)

    def test_actual_captured_database_is_exact_92_named_xp1_catalogue(self):
        proof, _ = candidate.source_profile()
        path = resource_root()/'work/host-prepared-captures/xp1-lan-20261030/databases/gameplay.sqlite'
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), candidate.DATABASE_PINS['gameplay']['sha256'])
        with sqlite3.connect(path.resolve().as_uri()+'?mode=ro', uri=True) as db:
            db.execute('PRAGMA query_only=ON')
            self.assertEqual(db.execute('SELECT COUNT(*) FROM GameCapabilities').fetchone()[0], 92)
            actual = db.execute('SELECT GC.GameCapability,T.Type,T.Kind,T.Hash FROM GameCapabilities GC JOIN Types T ON GC.GameCapability=T.Type').fetchall()
        expected = sorted((r['name'],r['type'],r['kind'],r['hash_u32']) for r in proof['catalogue_rows'])
        self.assertEqual(sorted((a,b,c,d&0xffffffff) for a,b,c,d in actual), expected)
        self.assertEqual(ownership.read_capability_hashes(path), tuple(sorted(r[3] for r in expected)))

    def test_existing_numeric_projection_never_matches_string_restrictions(self):
        proof = abi.verify_source()
        restrictions = proof['catalogue_evidence']['capability_restrictions']
        self.assertEqual(len(restrictions), 6)
        strings = tuple((0x62D100F0,5,None,r['name']) for r in restrictions)
        catalogue, _ = candidate.source_profile()
        for row in catalogue['catalogue_rows']:
            self.assertIsNone(ownership.numeric_entry(strings, row['hash_u32']))
            numeric = strings+((0x62D100F0,2,0,row['hash_u32']),)
            self.assertIsNotNone(ownership.numeric_entry(numeric,row['hash_u32']))

    def profile(self):
        proof, _ = candidate.source_profile()
        obj = ownership.ClosedBaseOwnership.__new__(ownership.ClosedBaseOwnership)
        obj.application = object(); obj.candidate_backend = object(); obj.required_mode = LAN
        obj.allowed = frozenset(r['hash_u32'] for r in proof['catalogue_rows'])
        obj.restricted = frozenset(r['hash_u32'] for r in abi.verify_source()['catalogue_evidence']['capability_restrictions'])
        obj.entries = (); obj.mode_name = 'LAN'
        obj.lan_branch = NS(details=Mock(return_value={'category':3}))
        return obj

    def test_shared_status_keeps_unknown_restricted_present_and_mode_refusals(self):
        obj = self.profile(); known = next(iter(obj.allowed))
        with patch.object(candidate,'candidate_details',return_value={}), \
             patch.object(ownership,'read_application_mode',return_value=LAN) as mode:
            for value in (0,next(iter(obj.restricted))):
                with self.assertRaisesRegex(ValueError,'unsupported content/ownership'):
                    obj.status(0,value)
            obj.entries = ((0x62D100F0,2,0,known),)
            with self.assertRaisesRegex(ValueError,'real constraint service'):obj.status(0,known)
            obj.entries = (); mode.return_value = ownership.HOTSEAT
            with self.assertRaisesRegex(ValueError,'mode changed'):obj.status(0,known)
            obj.lan_branch.details.assert_not_called()

    def test_candidate_lan_requires_exact_general_effect_proof(self):
        application = object()
        bundle = NS(inputs=NS(profile=NS(mode_name='LAN')),expected_readback={'player_id':0})
        backend = NS()
        with patch.object(candidate,'_owner'), patch.object(candidate,'read_mode',return_value=LAN):
            receipt = candidate.validate_lan_candidate(application,bundle,backend)
            self.assertEqual(receipt['record_copy_convergence_source_sha256'], candidate.CONVERGENCE[1])
            self.assertFalse(receipt['current_exe_record_snapshot_used'])
            self.assertFalse(receipt['allocation_failure_or_oom_equivalence_claimed'])
            with patch.object(candidate,'convergence_source',side_effect=ValueError('missing effect proof')):
                with self.assertRaisesRegex(ValueError,'missing effect proof'):
                    candidate.validate_lan_candidate(application,bundle,backend)
        with patch('civ6_host.runtime.lan_capabilities.verify_source',return_value={}), \
             patch.object(candidate,'validate_lan_candidate',side_effect=ValueError('missing actual record premise')):
            with self.assertRaisesRegex(ValueError,'missing actual record premise'):
                ClosedLanBranch(application,bundle,candidate_backend=backend)

    def test_shared_constructor_uses_actual_92_without_bypassing_inventory_or_lan_gate(self):
        proof, _ = candidate.source_profile()
        db = resource_root()/'work/host-prepared-captures/xp1-lan-20261030/databases/gameplay.sqlite'
        catalogue = dict(capabilities=proof['catalogue_rows'],fixture={'gameplay_database_sha256':candidate.DATABASE_PINS['gameplay']['sha256']})
        manifest = {'databases':{'gameplay':{'path':str(db)}}}
        inventory = tuple({'present':i<35} for i in range(65))
        with patch.object(candidate,'captured_catalogue',return_value=catalogue), \
             patch.object(candidate,'verify_candidate_live'), \
             patch.object(ownership,'read_fixed_inventory',return_value=inventory) as files, \
             patch.object(ownership,'read_application_mode',return_value=LAN), \
             patch.object(ownership,'ClosedLanBranch',side_effect=ValueError('record premise not qualified')) as lan:
            with self.assertRaisesRegex(ValueError,'record premise not qualified'):
                ownership.ClosedBaseOwnership(object(),Path('.'),manifest,required_mode=LAN,captured_bundle=object(),candidate_backend=object())
            self.assertEqual(len(files.call_args.args[1]),65)
            lan.assert_called_once()
            files.return_value = inventory[:-1]
            with self.assertRaisesRegex(ValueError,'inventory is incomplete'):
                ownership.ClosedBaseOwnership(object(),Path('.'),manifest,required_mode=LAN,captured_bundle=object(),candidate_backend=object())

    def test_default_base_catalogue_remains_93(self):
        proof = load_pinned_json(abi.ROOT/'evidence/native-capability-catalogue'/(abi.CATALOGUE_SHA256+'.json'),abi.CATALOGUE_SHA256)
        self.assertEqual(len(proof['capabilities']),93)
        self.assertEqual(len(set(r['hash_u32'] for r in proof['capabilities'])),93)

    def test_xp1_lan_keeps_64_distinct_live_provider_and_getter_checks(self):
        from civ6_host.runtime.native import native_configuration_finalization as config
        proof, _ = candidate.source_profile()
        base = 0x180000000
        table = base + proof['configuration_vtable_rva']
        getter = base + proof['slots']['0x68']['target_rva']
        application = NS(base=base, read=Mock(), player=Mock(side_effect=lambda p,**kw:{'pointer':0x100000+p*0x100}))
        bundle = NS(reference=candidate.REFERENCE)
        with patch.object(candidate,'source_profile',return_value=(proof,{})), \
             patch.object(candidate,'validate_lan_candidate',return_value=candidate.convergence_source()), \
             patch.object(config,'_qword',side_effect=lambda read,address:getter if address==table+0x68 else table):
            branch = ClosedLanBranch(application,bundle,candidate_backend=object())
            self.assertEqual(application.player.call_count,64)
            self.assertEqual(len(set(branch.players)),64)
            branch.details(0)
            details = branch.details(0)
            self.assertIsNone(details['lan_record_source_sha256'])
            self.assertFalse(details['session_record_values_replayed'])
            self.assertIn('historical_base_record_source_sha256',details)
            application.player.side_effect=lambda p,**kw:{'pointer':0x999999}
            with self.assertRaisesRegex(ValueError,'identity changed'):branch.details(0)
            with self.assertRaisesRegex(ValueError,'providers alias'):
                ClosedLanBranch(application,bundle,candidate_backend=object())
        with patch.object(candidate,'source_profile',return_value=(proof,{})), \
             patch.object(config,'_qword',return_value=table):
            with self.assertRaisesRegex(ValueError,'scalar getter'):
                branch._provider(0)
