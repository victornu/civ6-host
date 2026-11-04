"""Offline checks for the staged qualifier insertion; no product/native imports."""
import ast
import hashlib
import json
import shutil
from pathlib import Path
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]
SOURCE = (REPO/'tools/qualify_xp1_configuration.py').read_text(encoding='utf-8')
TREE = ast.Module(body=[n for n in ast.parse(SOURCE).body if isinstance(n, ast.FunctionDef) and n.name.startswith('saved_load_')], type_ignores=[])


def helpers():
    selected = [node for node in TREE.body if isinstance(node, ast.FunctionDef)
                and node.name in ('saved_load_events', 'saved_load_result_file', 'saved_load_private_icu')]
    def pin(pins, path, expected):
        path = Path(path)
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != expected:
            raise ValueError('Fixture pin differs')
        pins[str(path)] = actual
        return path
    namespace = dict(json=json, hashlib=hashlib, Path=Path, shutil=shutil, saved_load_pin=pin,
                     digest=lambda raw: hashlib.sha256(raw).hexdigest())
    exec(compile(ast.Module(body=selected, type_ignores=[]), '<staged pure helpers>', 'exec'), namespace)
    return namespace


class SavedLoadQualification(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.run = Path(self.temp.name)
        self.helpers = helpers()

    def events(self, raw):
        path = self.run/'events.jsonl'
        path.write_bytes(raw)
        return self.helpers['saved_load_events'](path)

    def test_native_refusal_remains_visible_without_completed_load_interval(self):
        count, events = self.events(b'{"stage":"before_official_gamecore_load","game_bytes":12}\n'
            b'{"stage":"unsupported_host_contract","interface":"logger","slot":"0x38"}\n')
        self.assertEqual(count, 2)
        self.assertEqual(events['unsupported_host_contract']['slot'], '0x38')
        self.assertNotIn('load_job_interval', events)
        with self.assertRaisesRegex(ValueError, 'Incomplete native Load'):
            self.helpers['saved_load_events'](self.run/'events.jsonl', require_load_interval=True)

    def test_distinct_load_and_cache_receipts(self):
        count, events = self.events(b'{"stage":"other_native_event"}\n'
            b'{"stage":"xp1_saved_raw_load_observed","receipt":{}}\n'
            b'{"stage":"xp1_saved_cache_observed","receipt":{}}\n')
        self.assertEqual(count, 3)
        self.assertEqual(len(events), 2)

    def test_unknown_plain_stdout_is_refused(self):
        with self.assertRaises(ValueError):
            self.events(b'guessed native output\n')

    def test_partial_stdout_is_refused(self):
        with self.assertRaises(ValueError):
            self.events(b'{"stage":"xp1_saved_raw_load_observed"}')

    def test_duplicate_result_is_refused(self):
        with self.assertRaises(ValueError):
            self.events(b'{"stage":"xp1_saved_raw_load_observed"}\n'*2)

    def test_result_file_requires_own_exact_path_and_hash(self):
        path = self.run/'raw-load-result.json'
        path.write_bytes(b'{"saved_game_loaded":true}')
        reference = dict(path=str(path), sha256=hashlib.sha256(path.read_bytes()).hexdigest())
        read = self.helpers['saved_load_result_file']
        self.assertTrue(read(self.run, dict(receipt=reference), path.name)['saved_game_loaded'])
        with self.assertRaises(ValueError):
            read(self.run, dict(receipt=dict(reference, sha256='0'*64)), path.name)
        with self.assertRaises(ValueError):
            read(self.run, dict(receipt=dict(reference, path=str(self.run/'other.json'))), path.name)
        self.assertIsNone(read(self.run, None, path.name))

    def test_existing_product_backend_and_candidate_cache_are_shared(self):
        worker = next(n for n in TREE.body if isinstance(n, ast.FunctionDef) and n.name == 'saved_load_worker')
        calls = [n for n in ast.walk(worker) if isinstance(n, ast.Call)]
        self.assertEqual(sum(isinstance(n.func, ast.Name) and n.func.id == 'open_official_backend' for n in calls), 1)
        facade = next(n for n in calls if isinstance(n.func, ast.Name) and n.func.id == 'OfficialFacadeBackend')
        self.assertEqual([n.id for n in facade.args], ['backend', 'receipt'])
        self.assertEqual({k.arg:ast.literal_eval(k.value) for k in facade.keywords}, {'publication_mode':'candidate'})
        self.assertNotIn('run_postload', ast.unparse(worker))
        self.assertNotIn('.close(', ast.unparse(worker))
        self.assertNotIn('.destroy(', ast.unparse(worker))

    def test_private_icu_preserves_all_metadata(self):
        original = self.run/'source.dat'
        original.write_bytes(b'bounded fake ICU for copy-only unit test')
        folder = self.run/'worker'
        folder.mkdir()
        path = folder/'manifest.json'
        icu = dict(path=str(original), sha256=hashlib.sha256(original.read_bytes()).hexdigest(),
                   bytes=original.stat().st_size, provenance='unchanged')
        fixture = dict(localization_bootstrap=dict(icu_data=icu, locale='fr_FR', dictionary_flag=False), other=3)
        path.write_text(json.dumps(fixture), encoding='utf-8')
        private, pins = {}, {}
        self.helpers['saved_load_private_icu'](path, pins, private)
        actual = json.loads(path.read_bytes())
        self.assertEqual(Path(actual['localization_bootstrap']['icu_data']['path']).read_bytes(), original.read_bytes())
        actual['localization_bootstrap']['icu_data']['path'] = str(original)
        self.assertEqual(actual, fixture)
        self.assertEqual(private['manifest_sha256'], hashlib.sha256(path.read_bytes()).hexdigest())
        with self.assertRaises(ValueError):
            self.helpers['saved_load_private_icu'](path, pins, private)

    def test_one_hidden_process_and_shared_supervision(self):
        fn = next(n for n in TREE.body if isinstance(n, ast.FunctionDef) and n.name == 'saved_load_supervisor')
        text = ast.unparse(fn)
        self.assertEqual(text.count('subprocess.Popen('), 1)
        for required in ('session._read_stream', 'session._watch', 'session._finish()',
                         'session.win.job(', 'subprocess.CREATE_NO_WINDOW',
                         'subprocess.BELOW_NORMAL_PRIORITY_CLASS', "session._send(b'go\\n')"):
            self.assertIn(required, text)
        self.assertNotIn('session.reset(', text)

    def test_preparation_is_not_replayed_and_candidate_stays_nonpublic(self):
        text = ast.unparse(TREE)
        self.assertIn('xp1_saved_load.consume_input_handoff(package)', text)
        self.assertNotIn('prepare_official_bundle(', text)
        self.assertNotIn('read_bundle(', text)
        self.assertIn('prepare_init_fixture_copies(fixture_source, 1, isolation_root=run)', text)
        self.assertIn('public_runtime_admitted=False', text)
        self.assertIn('prepared_service_group_reused_as_load_evidence=False', text)


if __name__ == '__main__':
    unittest.main()
