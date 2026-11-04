"""Disk/source selection only; owner/query/FIFO composition is tested separately."""
import ast
import hashlib
import importlib.util
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
from civ6_host.runtime import improvement_change_profile as source
from civ6_host.runtime.configuration_profiles import BASE_CORE_SHA256 as BASE,XP1_CORE_SHA256 as XP1
from civ6_host.runtime.paths import resource_root

HOST=Path(__file__).resolve().parents[1];LAB=resource_root()


class ImprovementProfileTests(unittest.TestCase):
    def test_exact_source_join_registry_receivers_and_dependencies(self):
        p=source.verify_source();profile=source.event_profile()
        self.assertEqual(set(profile.record_types_by_kind),{0x30ae2a3d,0x7b65ff2e})
        self.assertEqual(dict(profile.record_sizes),{144:144,153:128})
        self.assertEqual(p['families']['30ae2a3d']['shared_query'],'native_event_a625c726.query_native_values_at_position')
        self.assertEqual(p['families']['7b65ff2e']['shared_query'],'native_event_5d0f4014.query_descriptor')
        for path,digest in source.source_dependencies().items():
            with Path(path).open('rb') as stream:self.assertEqual(hashlib.file_digest(stream,'sha256').hexdigest(),digest,path)

    def test_live_source_instructions_include_concrete_rip_targets(self):
        sys.path.insert(0,str(LAB/'tools'))
        from extract_phase31_next_export import pefile
        pe=pefile.PE(source.verify_source()['image']['path'],fast_load=True);self.addCleanup(pe.close)
        base=0x190000000;read=lambda address,size:pe.get_data(address-base,size)
        self.assertGreater(source.verify_live(base,read),100)
        first=next(r for r in source.rows(source.verify_source()['functions']['route_builder']) if 'rip' in r['text'])
        at=base+int(first['va'],16)-0x180000000
        def bad(address,size):
            raw=read(address,size)
            return bytes([raw[0]^1])+raw[1:] if address==at else raw
        with self.assertRaisesRegex(ValueError,'route_builder'):source.verify_live(base,bad)

    def test_base_path_never_loads_xp1_and_unknown_engine_refuses(self):
        with patch.object(source,'verify_source',side_effect=AssertionError('XP1 source consulted')):
            self.assertIsNone(source.ensure_source(BASE))
            self.assertEqual(source.source_sha(BASE,'base-proof'),'base-proof')
            with self.assertRaises(ValueError):source.ensure_source('other')
        self.assertEqual(source.source_sha(XP1,'base-proof'),source.SOURCE[1])

    def test_hook_forwards_engine_only_at_existing_shared_query_boundaries(self):
        path=HOST/'tools/extraction_xp1_improvement_changes.py'
        spec=importlib.util.spec_from_file_location('improvement_hook_under_test',path)
        hook=importlib.util.module_from_spec(spec);spec.loader.exec_module(hook)
        for name,target in (('native_event_30ae2a3d','shared.query_native_values_at_position'),
                            ('native_event_7b65ff2e','_shared.query_descriptor')):
            original=(LAB/'civ6rl'/f'{name}.py').read_text();tree=ast.parse(hook.parameterize(name,original))
            calls=[n for n in ast.walk(tree) if isinstance(n,ast.Call) and ast.unparse(n.func)==target]
            self.assertEqual(len(calls),1)
            self.assertEqual([(k.arg,ast.unparse(k.value)) for k in calls[0].keywords if k.arg=='core_sha256'],[('core_sha256','core_sha256')])
            self.assertFalse(any(k.arg=='candidate_backend' for k in calls[0].keywords))
        old=(LAB/'civ6rl/native_host_events.py').read_text();tree=ast.parse(hook.parameterize('native_host_events',old))
        for kind,target in ((0x30ae2a3d,'produce_record'),(0x7b65ff2e,'query_descriptor')):
            branch=next(n for n in ast.walk(tree) if isinstance(n,ast.If) and ast.unparse(n.test)==f'kind == {kind}')
            call=next(n for n in ast.walk(branch) if isinstance(n,ast.Call) and ast.unparse(n.func)==target)
            self.assertEqual(sum(k.arg=='core_sha256' for k in call.keywords),1)
            self.assertIn('improvement_core_sha256',ast.unparse(call))
            self.assertFalse(any(k.arg=='candidate_backend' for k in call.keywords))


if __name__=='__main__':unittest.main()
