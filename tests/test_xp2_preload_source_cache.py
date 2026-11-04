"""Scoped immutable verification reuse; all native inputs remain fresh."""
from contextlib import ExitStack, contextmanager
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import tempfile
from types import MappingProxyType
import unittest
from unittest.mock import patch

from civ6_host.runtime import xp2_preload_source as source
from civ6_host.runtime import resource_resolution as resources
from civ6_host.runtime.configuration_profiles import _copy, XP2_CORE_SHA256
from civ6_host.runtime.native.native_cache_update_dispatch import dispatch_cache_update_payload
from civ6_host.runtime.native.native_event_argument_tree import read_event_fields
import test_xp2_preload_services as existing


def digest(raw):return hashlib.sha256(raw).hexdigest()


class PreloadSourceCacheTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original = _copy(source.source())

    def setUp(self):
        source._VALIDATED_SOURCE = None
        self.addCleanup(setattr, source, '_VALIDATED_SOURCE', None)

    @contextmanager
    def fixture(self):
        with tempfile.TemporaryDirectory(prefix='xp2-preload-cache-') as directory:
            root=Path(directory);files={}
            for name,raw in (('dependency.json',b'{"immutable":true}\n'),
                             ('generator.py',b'# source capture generator\n'),
                             ('helper.py',b'# source helper\n'),
                             ('verifier.py',b'# authored verifier identity\n')):
                path=root/name;path.write_bytes(raw);files[name]=path
            def pin(name):
                path=files[name];return dict(path=str(path),sha256=digest(path.read_bytes()))
            capture=dict(images=dict(xp2=dict(sha256=XP2_CORE_SHA256),exe=dict(sha256=source.EXE_SHA)),
                         generator=pin('generator.py'))
            original_capture = source._source((self.original['source']['path'], source.CAPTURE_SHA))
            capture['functions'] = {
                name: _copy(original_capture['functions'][name]) for name in ('iterator_next', 'get_count')
            }
            files['capture.json']=root/'capture.json'
            files['capture.json'].write_text(json.dumps(capture),encoding='utf8')
            proof=_copy(self.original);proof['source']=pin('capture.json')
            proof['references']={'nested_json':pin('dependency.json'),'helper':pin('helper.py')}
            files['profile.json']=root/'profile.json'
            files['profile.json'].write_text(json.dumps(proof),encoding='utf8')
            with ExitStack() as stack:
                stack.enter_context(patch.object(source,'SOURCE',(str(files['profile.json']),pin('profile.json')['sha256'])))
                stack.enter_context(patch.object(source,'CAPTURE_SHA',pin('capture.json')['sha256']))
                stack.enter_context(patch.object(source,'__file__',str(files['verifier.py'])))
                validated=stack.enter_context(patch.object(source,'source',wraps=source.source))
                yield root,files,validated

    def test_warm_private_view_is_frozen_and_public_checks_stay_fresh(self):
        with self.fixture() as (_,files,validate):
            first=source._validated_source()
            self.assertIs(first,source._validated_source());self.assertEqual(validate.call_count,1)
            self.assertIsInstance(first,MappingProxyType)
            detached=_copy(source.source());detached['deferred']['cache_registry']['receiver']=0
            self.assertEqual(validate.call_count,2)
            self.assertEqual(source._validated_source()['deferred']['cache_registry']['receiver'],16)
            self.assertEqual(validate.call_count,2)
            with self.assertRaises(TypeError):first['deferred']['cache_registry']['receiver']=0
            self.assertIs(source.source(),first);self.assertEqual(validate.call_count,3)

    def test_every_selected_JSON_and_generator_change_invalidates_and_refuses(self):
        for name in ('profile.json','capture.json','dependency.json','generator.py','helper.py'):
            with self.subTest(file=name),self.fixture() as (_,files,validate):
                source._VALIDATED_SOURCE=None
                source._validated_source();path=files[name];raw=path.read_bytes()
                path.write_bytes(raw+b'\nchanged')
                with self.assertRaises((RuntimeError,ValueError)):source._validated_source()
                self.assertIsNone(source._VALIDATED_SOURCE)
                path.write_bytes(raw)
                restored=source._validated_source();count=validate.call_count
                self.assertIs(restored,source._validated_source());self.assertEqual(validate.call_count,count)

    def test_same_content_new_metadata_and_verifier_identity_revalidate(self):
        with self.fixture() as (_,files,validate):
            source._validated_source()
            for name in ('dependency.json','generator.py','verifier.py'):
                path=files[name];stat=path.stat();before=validate.call_count
                os.utime(path,ns=(stat.st_atime_ns,stat.st_mtime_ns+1_000_000_000))
                source._validated_source();self.assertEqual(validate.call_count,before+1)
            before=validate.call_count
            with patch.object(source,'_source',wraps=source._source):
                source._validated_source();self.assertEqual(validate.call_count,before+1)
                source._validated_source();self.assertEqual(validate.call_count,before+1)

    def test_warm_nonJSON_bytes_are_rehashed_with_restored_or_unchanged_metadata(self):
        for name in ('generator.py','helper.py'):
            with self.subTest(file=name),self.fixture() as (_,files,validate):
                source._VALIDATED_SOURCE=None
                source._validated_source();path=files[name];raw=path.read_bytes();stat=path.stat()
                identity=source._stat_identity(path);actual_stat=source._stat_identity
                path.write_bytes(bytes([raw[0]^1])+raw[1:])
                os.utime(path,ns=(stat.st_atime_ns,stat.st_mtime_ns))
                self.assertEqual(path.stat().st_size,len(raw))
                self.assertEqual(path.stat().st_mtime_ns,stat.st_mtime_ns)
                # Also hold the shared metadata identity constant: this refusal
                # must come from the retained per-access byte hash, not ctime.
                def unchanged(candidate):
                    return identity if Path(candidate)==path else actual_stat(candidate)
                with patch.object(source,'_stat_identity',side_effect=unchanged):
                    with self.assertRaisesRegex(ValueError,'capture dependency differs'):source._validated_source()
                self.assertEqual(validate.call_count,1)
                self.assertIsNone(source._VALIDATED_SOURCE)

    def test_source_selection_and_modified_schema_never_reuse_success(self):
        with self.fixture() as (_,files,validate):
            proof=source._validated_source();changed=_copy(proof);changed['schema']='changed'
            with patch.object(source,'_source',return_value=changed),self.assertRaises(ValueError):
                source._validated_source()
            self.assertIsNone(source._VALIDATED_SOURCE)
            source._validated_source()
            with patch.object(source,'EXE_SHA','0'*64),self.assertRaises(ValueError):source._validated_source()
            self.assertIsNone(source._VALIDATED_SOURCE)
            source._validated_source();count=validate.call_count
            with patch.object(source,'source',wraps=source.source) as new_validator:
                source._validated_source();self.assertEqual(new_validator.call_count,1)
                source._validated_source();self.assertEqual(new_validator.call_count,1)
            self.assertEqual(validate.call_count,count+1)

    def test_dependency_change_during_full_validation_is_not_cached(self):
        with self.fixture() as (_,files,validate):
            actual=source.source
            def changing():
                result=actual();files['helper.py'].write_bytes(b'# changed while verifying\n');return result
            with patch.object(source,'source',side_effect=changing):
                with self.assertRaises(ValueError):source._validated_source()
            self.assertIsNone(source._VALIDATED_SOURCE)
            with self.assertRaises(ValueError):source._validated_source()
            self.assertIsNone(source._VALIDATED_SOURCE)

    def test_resource_relocation_uses_selected_paths_and_revalidates(self):
        with self.fixture() as (old,files,validate),tempfile.TemporaryDirectory(prefix='xp2-preload-relocated-') as directory:
            original=source._validated_source();count=validate.call_count
            relocated=Path(directory)/'resources';shutil.copytree(old,relocated)
            names={p.name for p in files.values()}
            with (patch.object(resources,'manifest',return_value={'source_root':str(old)}),
                  patch.object(resources,'configured_reference',return_value={'path':str(relocated/'manifest.json'),'sha256':'1'*64}),
                  patch.object(resources,'_FILES',names),patch('civ6_host.runtime.paths.resource_root',return_value=relocated)):
                moved=source._validated_source()
                self.assertIsNot(moved,original);self.assertEqual(moved,original)
                self.assertEqual(validate.call_count,count+1)
                source._validated_source();self.assertEqual(validate.call_count,count+1)
                # A changed relocated dependency cannot be hidden by unchanged
                # original files or by the previously validated original root.
                (relocated/'dependency.json').write_bytes(b'{"immutable":false}\n')
                with self.assertRaises(RuntimeError):source._validated_source()
            self.assertIsNone(source._VALIDATED_SOURCE)
            source._validated_source();self.assertGreater(validate.call_count,count+1)

    def test_warm_source_does_not_cache_live_code_registry_context_or_arguments(self):
        f=existing.XP2PreloadServices();f.memory()
        payload=struct.pack('<IIIII',1,7,0,3,9);calls=[]
        def dispatch():
            return dispatch_cache_update_payload(f.base,f.context,payload,read_memory=f.read,
                invoke=lambda *args:calls.append(tuple(args[-1])),core_sha256=XP2_CORE_SHA256)
        dispatch();self.assertEqual(calls,[(7,0,3,9)])
        for address,raw,error in ((f.base+0xB61E18,struct.pack('<I',0),'uninitialized'),
                                  (f.base+0xB8AA60,struct.pack('<Q',0x2010),'owner'),
                                  (f.base+0xA101E8+0x198,struct.pack('<Q',0),'slot')):
            old=f.read(address,len(raw));f.put(address,raw)
            with self.subTest(address=hex(address)),self.assertRaisesRegex(ValueError,error):dispatch()
            f.put(address,old)
        code=f.base+int(source.body('cache_outer198')['fragments'][0]['start_rva'],16)
        old=f.read(code,1);f.put(code,bytes([old[0]^1]))
        with self.assertRaisesRegex(ValueError,'live code'):dispatch()
        f.put(code,old);dispatch();self.assertEqual(len(calls),2)
        pointer,next_node=f.tree({7:existing.variant(2,9)})
        fields=lambda:read_event_fields(pointer,f.base,f.read,next_node,core_sha256=XP2_CORE_SHA256)
        self.assertEqual(fields()[7],existing.variant(2,9))
        f.put(0x7000+40,existing.variant(2,10));self.assertEqual(fields()[7],existing.variant(2,10))
        f.put(pointer+80,struct.pack('<I',2))
        with self.assertRaisesRegex(ValueError,'fewer_nodes'):fields()

    def test_update_scope_reuses_proof_but_reads_each_borrowed_map_and_live_reader(self):
        f = existing.XP2PreloadServices()
        f.memory()
        first, second = existing.variant(2, 9), existing.variant(2, 10)
        pointer, next_node = f.tree({7: first})
        code = f.base + int(source.body('iterator_next')['fragments'][0]['start_rva'], 16)
        raw = f.read(code, 1)

        def fields():
            return read_event_fields(pointer, f.base, f.read, next_node, core_sha256=XP2_CORE_SHA256)

        with patch.object(source, '_validated_source', wraps=source._validated_source) as check:
            with source.event_reader_scope(f.base, f.read):
                self.assertEqual(fields(), {7: first})
                f.put(0x7000+40, second)
                self.assertEqual(fields(), {7: second})
                with self.assertRaisesRegex(ValueError, 'another owner'):
                    source.verify_reader(f.base, lambda address, size: f.read(address, size))
                f.put(code, bytes([raw[0] ^ 1]))
                with self.assertRaisesRegex(ValueError, 'live code differs'):
                    fields()
                f.put(code, raw)
                slot = f.base+0xABF080+0x1D8
                old_slot = f.read(slot, 8)
                f.put(slot, bytes(8))
                with self.assertRaisesRegex(ValueError, 'count slot differs'):
                    fields()
                f.put(slot, old_slot)
                self.assertEqual(check.call_count, 1)
            self.assertEqual(check.call_count, 2)
        self.assertIsNone(source._EVENT_READER_SCOPE.get())
        self.assertEqual(fields(), {7: second})

    def test_update_scope_rejects_source_change_before_publishing(self):
        with self.fixture() as (_, files, _):
            with self.assertRaisesRegex(ValueError, 'capture dependency differs'):
                with source.event_reader_scope(0x300000000, lambda address, size: None):
                    path = files['helper.py']
                    raw = path.read_bytes()
                    modified = path.stat()
                    path.write_bytes(bytes([raw[0] ^ 1]) + raw[1:])
                    os.utime(path, ns=(modified.st_atime_ns, modified.st_mtime_ns))
        self.assertIsNone(source._EVENT_READER_SCOPE.get())
        self.assertIsNone(source._VALIDATED_SOURCE)

    def test_scopes_accept_revalidated_identical_source_after_cache_eviction(self):
        from civ6_host.runtime.native import native_source_cache

        read = lambda address, size: bytes(size)
        base = 0x300000000
        with tempfile.TemporaryDirectory(prefix='xp2-proof-eviction-') as directory:
            directory = Path(directory)
            for scope in (source.event_reader_scope(base, read),
                          source.cache_dispatch_scope(base, base + 8, read)):
                with self.subTest(scope=scope), scope:
                    initial = source._VALIDATED_SOURCE[1]
                    raw = b'{"source":"independent pinned entry"}\n'
                    for index in range(native_source_cache._MAX_ENTRIES):
                        path = directory / f'entry-{index}.json'
                        path.write_bytes(raw)
                        native_source_cache.load_pinned_json(path, digest(raw))
                self.assertIsNot(source._VALIDATED_SOURCE[1], initial)


if __name__=='__main__':unittest.main()
