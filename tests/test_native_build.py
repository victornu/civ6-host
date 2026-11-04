"""Only timestamp metadata may differ when reproducing the retained host."""
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('host_builder',ROOT/'tools/build_native_host.py')
builder=importlib.util.module_from_spec(spec);spec.loader.exec_module(builder)


class NativeBuildTests(unittest.TestCase):
    def fixture(self):
        raw=bytearray(1024);raw[:2]=b'MZ';struct.pack_into('<I',raw,0x3c,128)
        raw[128:132]=b'PE\0\0';struct.pack_into('<HH',raw,132,0x8664,1)
        struct.pack_into('<H',raw,148,240);struct.pack_into('<H',raw,152,0x20b)
        struct.pack_into('<I',raw,264,0x1000)
        struct.pack_into('<II',raw,312,0x1100,28)
        struct.pack_into('<IIII',raw,400,512,0x1000,512,512)
        fields=builder.timestamp_fields(raw)
        for off in fields.values():struct.pack_into('<I',raw,off,7)
        reference=dict(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),
            canonical_metadata_fields=[dict(name=n,offset=o,bytes=4,value=7) for n,o in fields.items()])
        return bytes(raw),reference

    def test_timestamp_only_variation_reproduces_exact_reference(self):
        original,ref=self.fixture();changed=bytearray(original)
        for row in ref['canonical_metadata_fields']:struct.pack_into('<I',changed,row['offset'],99)
        result,edits=builder.canonicalize(changed,ref)
        self.assertEqual(result,original);self.assertEqual(len(edits),3)

    def test_code_change_and_arbitrary_patch_are_refused(self):
        original,ref=self.fixture();changed=bytearray(original);changed[900]=1
        with self.assertRaisesRegex(ValueError,'machine code/data differ'):builder.canonicalize(changed,ref)
        ref['canonical_metadata_fields'][0]['offset']=900
        with self.assertRaisesRegex(ValueError,'location differs'):builder.canonicalize(original,ref)

    def test_current_build_never_inherits_retained_qualification(self):
        raw,ref=self.fixture()
        result,edits,status,admitted=builder.finalize_executable(raw,{'qualification':'unqualified_source_build'})
        self.assertEqual(status,'source_build_unqualified');self.assertFalse(admitted)
        for off in builder.timestamp_fields(result).values():
            self.assertEqual(struct.unpack_from('<I',result,off)[0],0)
        with self.assertRaises(ValueError):builder.finalize_executable(raw,{})
        self.assertTrue(builder.finalize_executable(raw,{'reference_executable':ref})[3])

    def test_extracted_sources_match_their_complete_include_closure(self):
        for profile in ('native/source-manifest.json','native/profiles/xp1/source-manifest.json','native/source-current.json',
                        'native/profiles/xp2-jobs/source-manifest.json'):
            with self.subTest(profile=profile):
                manifest=json.loads((ROOT/profile).read_text(encoding='utf-8'))
                inputs=builder.source_inputs(ROOT,manifest)
                self.assertEqual(len(inputs),len(manifest['sources']))

    def source_fixture(self,root):
        rows=[]
        for name,target,data in (
            ('native/profiles/xp1/gamecore_python_host.c','gamecore_python_host.c',b'#include "shared.inc"\n'),
            ('native/shared.inc','shared.inc',b'int example;\n')):
            path=root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
            rows.append(dict(path=name,build_path=target,bytes=len(data),sha256=builder.sha(data)))
        return {'sources':rows}

    def test_variant_build_reuses_shared_sources_without_copying_them(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);manifest=self.source_fixture(root)
            inputs=builder.source_inputs(root,manifest)
            staged=builder.staging_paths(root,manifest)
            self.assertEqual({str(n) for n in staged.values()},{'gamecore_python_host.c','shared.inc'})
            self.assertEqual(inputs[(root/'native/shared.inc').resolve()],b'int example;\n')

    def test_staging_rejects_escape_alias_and_duplicate_paths(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);manifest=self.source_fixture(root)
            for path in ('../escape.inc','/absolute.inc','C:/escape.inc','sub\\escape.inc',
                         'sub/../escape.inc','sub//escape.inc','GAMECORE_PYTHON_HOST.C'):
                with self.subTest(path=path):
                    manifest['sources'][1]['build_path']=path
                    with self.assertRaises(ValueError):builder.source_inputs(root,manifest)

    def test_missing_include_and_extra_unreferenced_file_refuse(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);manifest=self.source_fixture(root)
            manifest['sources'][1]['build_path']='unreferenced.inc'
            with self.assertRaisesRegex(ValueError,'Unmanifested native include'):
                builder.source_inputs(root,manifest)
            manifest['sources'][1]['build_path']='shared.inc'
            data=b'int unused;\n';(root/'native/extra.inc').write_bytes(data)
            manifest['sources'].append(dict(path='native/extra.inc',bytes=len(data),sha256=builder.sha(data)))
            with self.assertRaisesRegex(ValueError,'transitive include closure'):
                builder.source_inputs(root,manifest)


if __name__=='__main__':unittest.main()
