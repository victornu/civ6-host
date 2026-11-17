"""Bounded XP2 lifetime dependency verification; no engine execution."""
import ast
from collections.abc import Mapping
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from civ6_host.runtime import xp1_loaded_lifetime as life
from civ6_host.runtime import xp2_loaded_lifetime_source as xp2
from civ6_host.runtime.configuration_profiles import XP2_CORE_SHA256, _source
from civ6_host.runtime.native import native_source_cache as cache
from civ6_host.runtime.paths import resource_root
from civ6_host.runtime.resource_resolution import resolve_path

BASELINE = ('work/x1trade/lifetime-memory-repair-stage/60ca004e3412bcc9d5a78a7ecf718f47b6fcb8061be7111914df8a939559e388.json','60ca004e3412bcc9d5a78a7ecf718f47b6fcb8061be7111914df8a939559e388')
UNCHANGED = {'source': '810580debd4caa835d41fdd5fd4dab863cde8144da22c65690f989b5aa96a0ff', 'verify_live': 'a977392e4bf317cb393478f07c5205ee05edf073b56c5a2107a190c1a77598f7', 'LoadedLifetime': '543fc3a4ec1475939e739c594cf624a42af7f0bcbc2082b8a512a3a815c4916c'}


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream,'sha256').hexdigest()


class LifetimeDependencyProjectionTests(unittest.TestCase):
    def test_actual_closure_preserves_all_pins_without_loading_historical_bodies(self):
        expected = dict(_source(BASELINE)['pins'])
        expected = {str(resolve_path(Path(path)).resolve()):value for path,value in expected.items()}
        projection_path = str(resolve_path(resource_root()/life._XP2_DEPENDENCY_PROJECTION[0]).resolve())
        expected[projection_path] = life._XP2_DEPENDENCY_PROJECTION[1]
        cache._clear_cache_for_tests()
        loaded=[];old=cache._load_pinned_json
        def checked(path,expected):
            loaded.append((str(path),path.stat().st_size))
            return old(path,expected)
        with patch.object(cache,'_load_pinned_json',side_effect=checked):
            actual=life.source_dependencies(XP2_CORE_SHA256)
        self.assertEqual(actual,expected)
        self.assertTrue(loaded)
        self.assertLess(max(size for _,size in loaded),512*1024)
        self.assertFalse(any('native-newgame-script-prefix34' in path for path,_ in loaded))
        self.assertFalse(any('native-host-event-registry.json' in path for path,_ in loaded))
        # Clearing the ordinary 64-entry proof cache cannot force full ancestor
        # reparsing. Every original file remains authenticated on the next call.
        cache._clear_cache_for_tests()
        self.assertEqual(life.source_dependencies(XP2_CORE_SHA256),actual)

    def test_projection_contains_exact_children_of_every_reachable_original_json(self):
        projection=_source(life._XP2_DEPENDENCY_PROJECTION)
        seen=set();paths=set()
        def walk(ref):
            path=resolve_path(resource_root()/ref['path']);expected=ref['sha256']
            if (str(path),expected) in paths:return
            paths.add((str(path),expected))
            self.assertEqual(digest(path),expected)
            if path.suffix.lower()!='.json':return
            self.assertLess(path.stat().st_size,8*1024*1024)
            value=json.loads(path.read_text(encoding='utf-8'))
            children=[]
            if isinstance(value,Mapping):
                for key in ('references','parents'):
                    values=value.get(key,{})
                    values=values.values() if hasattr(values,'values') else values
                    for child in values:
                        if hasattr(child,'get') and child.get('path') and child.get('sha256'):
                            children.append(dict(path=child['path'],sha256=child['sha256']))
            self.assertEqual(children,[dict(row) for row in projection['documents'][expected]['children']])
            seen.add(expected)
            for child in children:walk(child)
        for ref in xp2.source()['references']:walk(ref)
        self.assertEqual(seen,set(projection['documents']))
        self.assertEqual(dict(projection['root']),dict(path=xp2.SOURCE[0],sha256=xp2.SOURCE[1]))

    def test_stream_bound_full_digest_mutation_unknown_graph_and_toctou(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'proof.json'
            payload=b'{"body":"'+b'a'*(2*1024*1024)+b'","references":[]}'
            path.write_bytes(payload);expected=hashlib.sha256(payload).hexdigest()
            children=({'path':'child.json','sha256':'a'*64},)
            projection={'documents':{expected:{'children':children}}}
            actual_open=Path.open;reads=[]
            class Reader:
                def __init__(self,stream):self.stream=stream
                def __enter__(self):self.stream.__enter__();return self
                def __exit__(self,*args):return self.stream.__exit__(*args)
                def read(self,size=-1):
                    reads.append(size)
                    if not 0<size<=64*1024:raise AssertionError('Unbounded proof read')
                    return self.stream.read(size)
            def opened(actual,*args,**kw):
                value=actual_open(actual,*args,**kw)
                return Reader(value) if actual==path else value
            with (patch.object(Path,'open',opened),
                  patch.object(Path,'read_bytes',side_effect=AssertionError('Whole proof bytes')),
                  patch.object(Path,'read_text',side_effect=AssertionError('Whole proof text'))):
                self.assertEqual(life._verified_dependency_children(path,expected,projection),children)
            self.assertGreater(len(reads),32);self.assertEqual(max(reads),64*1024)
            path.write_bytes(payload[:-2]+b' }')
            with self.assertRaisesRegex(ValueError,'dependency changed'):
                life._verified_dependency_children(path,expected,projection)
            altered=digest(path)
            with self.assertRaisesRegex(ValueError,'authenticated graph'):
                life._verified_dependency_children(path,altered,projection)
            path.write_bytes(payload)
            identity=cache._stat_identity(path)
            changed=identity[:-1]+(identity[-1]+1,)
            with patch.object(cache,'_stat_identity',side_effect=[identity,changed]):
                with self.assertRaisesRegex(ValueError,'while hashing'):
                    life._verified_dependency_children(path,expected,projection)

    def test_wrong_root_refuses_and_actual_lifetime_abi_and_close_code_are_unchanged(self):
        projection=dict(_source(life._XP2_DEPENDENCY_PROJECTION))
        projection['root']=dict(path=xp2.SOURCE[0],sha256='0'*64)
        original=life._source
        with patch.object(life,'_source',side_effect=lambda ref:projection if ref==life._XP2_DEPENDENCY_PROJECTION else original(ref)):
            with self.assertRaisesRegex(ValueError,'another source'):life.source_dependencies(XP2_CORE_SHA256)
        tree=ast.parse(Path(life.__file__).read_text(encoding='utf-8'))
        for name,expected in UNCHANGED.items():
            node=next(n for n in tree.body if getattr(n,'name',None)==name)
            self.assertEqual(hashlib.sha256(ast.dump(node,include_attributes=False).encode()).hexdigest(),expected)


if __name__=='__main__':unittest.main()
