"""Retained full-source comparison for one exact non-parser checkpoint change."""
import ast,copy,hashlib,json,unittest,zipfile
from pathlib import Path
from civ6_host.runtime import capture_admission as admission
from civ6_host.runtime.paths import resource_root


class ReaderTransitionTests(unittest.TestCase):
    def test_only_two_exact_nonparser_edits_differ_from_recorded_producer(self):
        host=Path(__file__).resolve().parents[1]
        key='runtime/native/native_official_bundle.py'
        archive=host/'work/xp1-turn-integration/native-session12/executed-sources.zip'
        self.assertEqual(hashlib.sha256(archive.read_bytes()).hexdigest(),
            'bbdeb49dc24b5cbd72441a076e8bcf9edf4b9e6cf79422bbb75db687d135748f')
        with zipfile.ZipFile(archive) as z:old=z.read('src/civ6_host/'+key)
        self.assertEqual(hashlib.sha256(old).hexdigest(),'0f9ad559341707cebd6ce0e9a76f27ccdc2dfecee6cc65ab2f385eaba93ce51b')
        intermediate_archive=host/'work/xp1-turn-integration/native-session15/executed-sources.zip'
        self.assertEqual(hashlib.sha256(intermediate_archive.read_bytes()).hexdigest(),
            '41fca4d203d12cc08c34e9674b7da77032c2b728facf7418f9eabd051dc92923')
        with zipfile.ZipFile(intermediate_archive) as z:
            intermediate=z.read('src/civ6_host/'+key)
        self.assertEqual(hashlib.sha256(intermediate).hexdigest(),
            '55c05c15c7dc08b776f9e52ba379d1f13e5a83bce83d41787f32c2bd9626a89a')
        expected=old.decode('utf-8').replace(
            'map_values=inputs.map_values, official_bundle=inputs.official_bundle)',
            'map_values=inputs.map_values, official_bundle=inputs.official_bundle, checkpoint=inputs.checkpoint)')
        expected=expected.replace("    if closure.get('input_profile') == 'lan':\n",
                                  "    if closure.get('input_profile') in ('lan', 'xp1-lan'):\n")
        self.assertEqual(ast.dump(ast.parse(expected)),ast.dump(ast.parse(intermediate)))
        manifest=json.loads((resource_root()/'work/host-prepared-captures/xp1-lan-20261030/manifest.json').read_bytes())
        producer=manifest['validation_identity'];consumer=admission.validation_identity()
        provenance=admission.admit_producer(producer,consumer)
        rows=admission._check_xp1_prepared_reader(producer,consumer,provenance,manifest)
        self.assertEqual(len(rows),1);self.assertFalse(rows[0]['producer_identity_substituted'])
        bad=copy.deepcopy(producer);bad['runtime_sources'][key]='a'*64
        with self.assertRaisesRegex(ValueError,'raw revalidation'):
            admission._check_xp1_prepared_reader(bad,consumer,provenance,manifest)
        bad=copy.deepcopy(consumer);bad['runtime_sources'][key]='b'*64
        with self.assertRaisesRegex(ValueError,'current input validator changed'):
            admission._check_xp1_prepared_reader(producer,bad,provenance,manifest)
        bad=copy.deepcopy(producer);bad['runtime_sources']['runtime/native/official_save.py']='c'*64
        with self.assertRaisesRegex(ValueError,'raw revalidation'):
            admission._check_xp1_prepared_reader(bad,consumer,provenance,manifest)


if __name__=='__main__':unittest.main()
