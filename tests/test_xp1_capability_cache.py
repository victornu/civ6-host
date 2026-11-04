import ast
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import struct
import tempfile
import time
from types import SimpleNamespace as NS, MappingProxyType
import unittest
from unittest.mock import Mock, patch

from civ6_host.runtime import xp1_load_capability as candidate
from civ6_host.runtime.native import native_application_configuration as application
from civ6_host.runtime.native import native_host_capability_status as abi
from civ6_host.runtime.native import native_source_cache as cache
from civ6_host.runtime.lan_capabilities import ClosedLanBranch, LAN
from extraction_xp1_capability_cache import parameterize, MODULES


class SourceReceiptTests(unittest.TestCase):
    def owner(self):
        app = application.NativeApplicationConfiguration.__new__(application.NativeApplicationConfiguration)
        app._configuration_abi=candidate.configuration_abi(candidate.XP1_CORE_SHA256)
        app.base=0x180000000;app.pointer=0x10000;app._check_guard=Mock()
        backend=NS(owner=app,captured_bundle=object(),check_thread=Mock(),busy=True,
                   stage='prepared',prefix=None,snapshot_phase='idle')
        with patch.object(candidate,'_owner'):
            candidate._bind_source_receipt(backend)
        return backend

    def test_real_frozen_sources_and_complete_dependency_export(self):
        backend=self.owner();receipt=backend._xp1_capability_sources
        self.assertIsInstance(receipt.profile[0], MappingProxyType)
        self.assertIsInstance(receipt.profile[0]['catalogue_rows'],tuple)
        self.assertEqual(len(receipt.profile[0]['catalogue_rows']),92)
        self.assertEqual(len(receipt.player_keys),64)
        self.assertEqual(len(receipt.catalogue['capabilities']),93)
        self.assertEqual(dict(receipt.dependencies),candidate.source_dependencies())
        self.assertGreater(len(receipt.dependencies),14)
        self.assertIn(candidate.CONVERGENCE[1],dict(receipt.dependencies).values())
        with self.assertRaises(TypeError):receipt.catalogue['new']=True

    def test_export_covers_every_shared_source_loader_dependency(self):
        from civ6_host.runtime import lan_capabilities
        from civ6_host.runtime.native import native_app_ownership
        dependencies=candidate.source_dependencies();seen=set()
        original=cache._stat_identity
        def observe(path):
            seen.add(str(Path(path).resolve()))
            return original(path)
        with patch.object(cache,'_stat_identity',side_effect=observe):
            candidate.source_profile()
            candidate.convergence_source()
            application.verify_source(core_sha256=candidate.XP1_CORE_SHA256)
            abi.request_details(0,0)
            native_app_ownership.verify_producer_source()
            lan_capabilities.verify_source()
        self.assertFalse(seen-set(dependencies),sorted(seen-set(dependencies)))
        (Path(__file__).parent/'source-dependencies.json').write_text(json.dumps(dependencies,indent=2)+'\n')

    def test_metadata_hot_path_reads_no_files_and_preserves_dword_checks(self):
        backend=self.owner()
        with patch.object(candidate,'_owner'),candidate.capability_source_scope(backend,'install'):
            with patch.object(candidate,'_identity',side_effect=AssertionError('hot stat')), \
                 patch.object(candidate,'_source',side_effect=AssertionError('hot JSON')), \
                 patch.object(candidate,'_body',side_effect=AssertionError('hot body')), \
                 patch.object(application,'verify_source',side_effect=AssertionError('hot application proof')), \
                 patch.object(cache,'load_pinned_json',side_effect=AssertionError('hot source')):
                began=time.perf_counter()
                for index in range(106):
                    self.assertEqual(len(candidate.source_profile(backend)[0]['catalogue_rows']),92)
                    self.assertGreater(candidate.candidate_player_key(backend.owner,index%64,backend),0)
                    details=candidate.candidate_details(backend,index%64,0xffffffff)
                    self.assertEqual(details['capability_u32'],0xffffffff)
                elapsed=time.perf_counter()-began
                with self.assertRaisesRegex(ValueError,'unsigned DWORDs'):
                    candidate.candidate_details(backend,True,0)
                with self.assertRaisesRegex(ValueError,'unsigned DWORDs'):
                    candidate.candidate_details(backend,0,-1)
        (Path(__file__).parent/'offline-metadata-timing.json').write_text(json.dumps(dict(
            repetitions=106,elapsed_seconds=elapsed,native_execution=False,
            scope='static receipt access only; owner guard mocked; not native callback throughput'),indent=2)+'\n')

    def test_live_player_lookup_and_provider_identity_remain_fresh(self):
        backend=self.owner();app=backend.owner;receipt=backend._xp1_capability_sources
        profile=receipt.profile[0];native=app._configuration_abi;table=app.base+native.vtable_rva
        nodes={key:0x20000+i*0x100 for i,key in enumerate(receipt.player_keys)}
        pointers={key:0x30000+i*0x100 for i,key in enumerate(receipt.player_keys)}
        memory={app.pointer:struct.pack('<Q',table), table+0x58:struct.pack('<Q',app.base+native.lookup_rva),
                table+0x68:struct.pack('<Q',app.base+profile['slots']['0x68']['target_rva'])}
        for i,key in enumerate(receipt.player_keys):
            memory[app.base+native.player_key_table_rva+i*68]=struct.pack('<I',key)
            memory[nodes[key]]=struct.pack('<H6xQ4xI',10,pointers[key],0x05000000)
            memory[pointers[key]]=struct.pack('<Q',table)
        app.read=Mock(side_effect=lambda address,size:memory[address][:size])
        app.call=Mock(side_effect=lambda address,restype,argtypes,receiver,key:nodes[key])
        with patch.object(candidate,'_owner'),candidate.capability_source_scope(backend,'install'), \
             patch.object(candidate,'validate_lan_candidate',return_value={}), \
             patch('civ6_host.runtime.lan_capabilities.verify_source',return_value={}), \
             patch.object(application,'verify_source',side_effect=AssertionError('hot proof')):
            branch=ClosedLanBranch(app,NS(reference=candidate.REFERENCE),candidate_backend=backend)
            self.assertEqual(len(set(branch.players)),64)
            before=app.call.call_count
            branch.details(0);branch.details(0)
            self.assertEqual(app.call.call_count,before+2)
            key=receipt.player_keys[0];address=app.base+native.player_key_table_rva
            memory[address]=struct.pack('<I',1)
            with self.assertRaisesRegex(ValueError,'PLAYER key changed'):branch.details(0)
            memory[address]=struct.pack('<I',key)
            memory[table+0x58]=struct.pack('<Q',1)
            with self.assertRaisesRegex(ValueError,'lookup identity changed'):branch.details(0)
            memory[table+0x58]=struct.pack('<Q',app.base+native.lookup_rva)
            memory[table+0x68]=struct.pack('<Q',1)
            with self.assertRaisesRegex(ValueError,'scalar getter'):branch.details(0)
            memory[table+0x68]=struct.pack('<Q',app.base+profile['slots']['0x68']['target_rva'])
            memory[nodes[key]]=struct.pack('<H6xQ4xI',10,pointers[receipt.player_keys[1]],0x05000000)
            with self.assertRaisesRegex(ValueError,'provider identity changed'):branch.details(0)

    def test_live_mode_value_is_read_on_every_query(self):
        backend=self.owner();app=backend.owner;receipt=backend._xp1_capability_sources
        p=receipt.profile[0];native=app._configuration_abi;table=app.base+native.vtable_rva
        memory={app.pointer:struct.pack('<Q',table),table+0x58:struct.pack('<Q',app.base+native.lookup_rva),
                table+0x68:struct.pack('<Q',app.base+p['slots']['0x68']['target_rva']),
                app.base+native.root_key_rva:struct.pack('<I',0x871d5b63),
                app.base+p['xp1_mode_key_initializer']['global_rva']:struct.pack('<I',0x0623e593),
                0x40000:struct.pack('<H6xQ4xI',10,0x50000,0x05000000),0x50000:struct.pack('<Q',table),
                0x60000:struct.pack('<H6xQ4xI',2,LAN,0)}
        app.read=Mock(side_effect=lambda address,size:memory[address][:size])
        app.call=Mock(side_effect=lambda address,*args:0x40000 if address==app.base+native.lookup_rva else 0x60000)
        with patch.object(candidate,'_owner'),candidate.capability_source_scope(backend,'install'):
            self.assertEqual(candidate.read_mode(app,backend),LAN)
            memory[0x60000]=struct.pack('<H6xQ4xI',2,1,0)
            self.assertEqual(candidate.read_mode(app,backend),1)
            self.assertEqual(app.call.call_count,4)
            memory[table+0x68]=struct.pack('<Q',1)
            with self.assertRaisesRegex(ValueError,'mode provider changed'):candidate.read_mode(app,backend)

    def test_outside_scope_wrong_owner_and_scope_reentry_fail_closed(self):
        backend=self.owner()
        with patch.object(candidate,'_owner'):
            with self.assertRaisesRegex(ValueError,'active verified owner'):candidate.source_profile(backend)
            with candidate.capability_source_scope(backend,'install'):
                with self.assertRaisesRegex(ValueError,'lifecycle'):
                    with candidate.capability_source_scope(backend,'install'):pass
                with self.assertRaisesRegex(ValueError,'owner/index differs'):
                    candidate.candidate_player_key(object(),0,backend)
            backend.stage='raw-loaded'
            with self.assertRaisesRegex(ValueError,'lifecycle'):
                with candidate.capability_source_scope(backend,'load'):pass
            backend.stage='copied';backend.snapshot_phase='load'
            with candidate.capability_source_scope(backend,'load'):
                self.assertEqual(len(candidate.source_profile(backend)[0]['catalogue_rows']),92)
            backend.owner=object()
            with self.assertRaisesRegex(ValueError,'lifecycle'):
                with candidate.capability_source_scope(backend,'load'):pass

    def test_changed_dependency_refuses_entry_and_exit(self):
        backend=self.owner();original=backend._xp1_capability_sources
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'proof.json';raw=b'{"pin":1}';path.write_bytes(raw)
            digest=hashlib.sha256(raw).hexdigest()
            receipt=replace(original,dependencies=((str(path),digest),),identities=(candidate._identity(path),))
            backend._xp1_capability_sources=receipt
            with patch.object(candidate,'_owner'):
                with self.assertRaisesRegex(ValueError,'source changed'):
                    with candidate.capability_source_scope(backend,'install'):
                        path.write_bytes(b'{"pin":222}')
                self.assertIsNone(backend._xp1_capability_source_scope)
                with self.assertRaisesRegex(ValueError,'source changed'):
                    with candidate.capability_source_scope(backend,'install'):pass
                with self.assertRaisesRegex(RuntimeError,'SHA-256 mismatch'):
                    cache.load_pinned_json(path,digest)

    def test_existing_raw_load_is_wrapped_and_base_branch_unchanged(self):
        host=Path(__file__).resolve().parents[1]
        path=host/'src/civ6_host/runtime/native/native_checkpoint_load.py'
        tree=ast.parse(path.read_text())
        method=next(n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name=='load_raw')
        wrapped=next(n for n in ast.walk(method) if isinstance(n,ast.With))
        self.assertEqual(ast.unparse(wrapped.items[0].context_expr),"capability_source_scope(self, 'load')")
        self.assertEqual(ast.unparse(method.body[-1]),'return self.load_call(self.context, self.reader.pointer)')
        self.assertIn("self.snapshot_phase = 'load'",ast.unparse(method))

    def test_existing_cache_lease_owns_scope_and_poison_always_runs(self):
        backend=self.owner();attempt=NS(owner=backend)
        with patch.object(candidate,'_owner'):
            with self.assertRaisesRegex(ValueError,'existing publication lease'):
                candidate.begin_cache_source_scope(attempt)
            with patch.object(candidate,'_cache_scope_owner',return_value=True):
                candidate.begin_cache_source_scope(attempt)
                self.assertEqual(len(candidate.source_profile(backend)[0]['catalogue_rows']),92)
                candidate.finish_cache_source_scope(attempt)
                self.assertIsNone(backend._xp1_capability_source_scope)
        host=Path(__file__).resolve().parents[1]
        path=host/'src/civ6_host/runtime/native/native_checkpoint_postload_facades.py'
        tree=ast.parse(path.read_text())
        cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='NativeFacadeBackend')
        poison=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='poison')
        self.assertIsInstance(poison.body[0],ast.Try)
        self.assertIn('self.owner.poisoned = True',ast.unparse(poison.body[0].finalbody))
        finish=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='finish')
        self.assertEqual(ast.unparse(finish.body[1]),'finish_cache_source_scope(self)')
