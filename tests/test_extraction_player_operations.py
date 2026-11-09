"""Pure extraction regression checks; no native runtime is imported or called."""
import ast
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import unittest

REPO = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location(
    'extraction_player_operations_tested', REPO / 'tools/extraction_player_operations.py')
transform = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(transform)


def _target():
    override = os.environ.get('CIV6_HOST_PLAYER_OPERATION_PROPOSED')
    return Path(override) if override else REPO / (
        'src/civ6_host/runtime/native/native_player_operation_request.py')


def _reverse(text, edits):
    for before, after in reversed(edits):
        if text.count(after) != 1:
            raise AssertionError('Reverse fixture anchor differs')
        text = text.replace(after, before, 1)
    return text


class PlayerOperationExtractionTests(unittest.TestCase):
    def setUp(self):
        self.proposed = _target().read_text(encoding='utf-8')
        self.legacy = _reverse(self.proposed, transform._CONGRESS_EDITS)
        self.extracted = _reverse(self.legacy, transform._LEGACY_EDITS)

    def test_actual_measured_pipeline_input_and_installed_intermediate_are_pinned(self):
        self.assertEqual(transform._digest(self.extracted), transform.EXTRACTED_SHA256)
        self.assertEqual(transform._digest(self.legacy), transform.INSTALLED_LEGACY_SHA256)
        self.assertEqual(transform._digest(self.proposed), transform.DESTINATION_SHA256)
        self.assertNotIn('allow_empty', self.extracted)
        self.assertIn('allow_empty=False', self.legacy)
        self.assertIn("image=getattr(core,'_civ6_host_execution_image',None)", self.legacy)

    def test_exact_proposed_output_and_historical_provenance_are_retained(self):
        result = transform.parameterize(transform.MODULE, self.extracted)
        self.assertEqual(result, self.proposed)
        old = ast.parse(self.extracted); new = ast.parse(result)
        # The request primitive is the only modified top-level object.
        strip = lambda tree: [ast.dump(n, include_attributes=False) for n in tree.body
            if not isinstance(n, ast.FunctionDef) or n.name != 'request_player_operation']
        self.assertEqual(strip(old), strip(new))
        resource = os.environ.get('CIV6_HOST_RESOURCE_ROOT')
        if resource:
            source = Path(resource) / 'civ6rl/native_player_operation_request.py'
            self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(),
                             transform.HISTORICAL_SOURCE_SHA256)

    def test_unknown_input_and_accidental_second_application_are_rejected(self):
        for raw in (self.extracted + '# changed\n', self.legacy, self.proposed):
            with self.assertRaisesRegex(ValueError, 'input changed'):
                transform.parameterize(transform.MODULE, raw)

    def test_other_destinations_are_unchanged(self):
        for name in ('civ6rl.native_script_runtime', 'civ6rl.native_saved_session',
                     'civ6rl.native_policy_catalog'):
            self.assertEqual(transform.parameterize(name, 'opaque text'), 'opaque text')

    def test_source_map_retains_historical_source_and_adds_one_named_transformation(self):
        manifest = json.loads((REPO / 'src/civ6_host/runtime/source-map.json').read_text())
        rows = [r for r in manifest['sources'] if r['module'] ==
                'civ6_host.runtime.native.native_player_operation_request']
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row['source'], 'civ6rl/native_player_operation_request.py')
        self.assertEqual(row['source_sha256'], transform.HISTORICAL_SOURCE_SHA256)
        self.assertEqual(row['destination_sha256'], transform.DESTINATION_SHA256)
        self.assertEqual(row['transformations'].count(transform.LABEL), 1)

    def test_extractor_hook_preserves_existing_string_and_cleanup_transformations(self):
        raw = (REPO / 'tools/extract_runtime.py').read_text(encoding='utf-8')
        self.assertIn('text=player_operations(name,text)', raw)
        self.assertIn('transformations.append(PLAYER_OPERATION_LABEL)', raw)
        tree = ast.parse(raw)
        prepare = next(n for n in tree.body if isinstance(n, ast.FunctionDef)
                       and n.name == 'prepare_tree')
        body = ast.unparse(prepare)
        for marker in ('supervisor_cleanup', 'close_reaped_process_pipes',
                       'script_event_strings', 'dispatch_strings', 'argument_evidence'):
            self.assertIn(marker, body)


if __name__ == '__main__':
    unittest.main()
