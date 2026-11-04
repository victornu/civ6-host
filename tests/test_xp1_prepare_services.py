"""Admission and source closure for the shared XP1 service group."""
import importlib.util
import json
import os
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from civ6_host.runtime import xp1_prepare
from civ6_host.runtime.paths import resource_root
from civ6_host.runtime.native import native_host, native_core_context_profiles
from civ6_host.runtime.native import native_xp1_prepare_type_registry as registry
from civ6_host.runtime.native import native_xp1_archive_access as access
from civ6_host.runtime.native import native_xp1_archive_registration as registration
from civ6_host.runtime.native import native_xp1_prepare_dispatch as dispatch


class XP1PreparationTests(unittest.TestCase):
    def test_default_null_tuner_refuses_and_explicit_scope_is_not_gameplay(self):
        host = SimpleNamespace(tuner_unavailable_probe=True)
        for enabled in (False, None, 1, 'true'):
            with self.assertRaises(ValueError):
                xp1_prepare.require_null_tuner_diagnostic(host, enabled)
        receipt = xp1_prepare.require_null_tuner_diagnostic(host, True)
        self.assertFalse(receipt['gameplay_optional_proven'])
        self.assertFalse(receipt['eligible_for_training'])
        with self.assertRaises(ValueError):
            xp1_prepare.require_null_tuner_diagnostic(SimpleNamespace(), True)

    def test_changed_proof_refuses(self):
        with patch.object(Path, 'read_bytes', return_value=b'{}'):
            with self.assertRaisesRegex(ValueError, 'proof changed'):
                xp1_prepare.require_null_tuner_diagnostic(SimpleNamespace(tuner_unavailable_probe=True), True)

    def test_saved_load_cannot_borrow_context_only_admission(self):
        with patch.object(xp1_prepare, 'prepare') as prepare:
            with self.assertRaises(ValueError):
                native_host.prepare_context(object(), 1, Mock(), context_profile=object(), saved_load_abi=object())
            with self.assertRaises(ValueError):
                native_host.prepare_context(object(), 1, Mock(), null_tuner_diagnostic=True)
            prepare.assert_not_called()

    def test_profile_mismatch_and_ordinary_null_refuse_before_services(self):
        profile = SimpleNamespace(ruleset='xp1', mode='context')
        host = SimpleNamespace(dll_directory='.', tuner_unavailable_probe=True)
        core = SimpleNamespace(_name='core.dll')
        with patch.object(native_core_context_profiles,'profile_for_core',return_value=profile), \
             patch.object(registry,'install_prepare_type_registry') as install:
            with self.assertRaises(ValueError):
                xp1_prepare.prepare(core,1,host,object(),Mock())
            with self.assertRaisesRegex(ValueError,'Absent Tuner'):
                xp1_prepare.prepare(core,1,host,profile,Mock())
            install.assert_not_called()

    def test_exact_source_migration_preserves_historical_archive_proof(self):
        for module in (registry, access, registration, dispatch):
            self.assertIsInstance(module.verify_source(resource_root()), dict)

    def test_stage_adapts_existing_worker_without_configuration_replay(self):
        path=Path(__file__).resolve().parents[1]/'tools/qualify_xp1_configuration.py'
        spec=importlib.util.spec_from_file_location('_xp1_qualification_test',path)
        qualifier=importlib.util.module_from_spec(spec);spec.loader.exec_module(qualifier)
        with patch.dict(os.environ,{qualifier.STAGE_ENV:'scripts'}):
            reference,_=qualifier.load_reference()
            qualifier.use_common_lifecycle(reference)
            self.assertEqual(reference.HOST_SHA256,qualifier.SCRIPT_HOST[1])
            self.assertIn('_close_script_group',reference._worker_run.__code__.co_names)
            self.assertEqual(reference._configuration_provider_delivery.__closure__[0].cell_contents, 'scripts')

    def test_retained_native_telemetry_parser_refuses_unknown_or_nonempty_jobs(self):
        path=Path(__file__).resolve().parents[1]/'tools/qualify_xp1_configuration.py'
        spec=importlib.util.spec_from_file_location('_xp1_stdout_test',path)
        qualifier=importlib.util.module_from_spec(spec);spec.loader.exec_module(qualifier)
        path=resource_root()/'work/native-xp1-context822-runs/run-20261030T142038Z-f09f57982cf0/supervisor.json'
        stdout=json.loads(path.read_text(encoding='utf-8'))['stdout']
        worker,line,telemetry=qualifier.parse_script_stdout(stdout)
        self.assertEqual(worker['status'],'completed_diagnostic')
        self.assertEqual(telemetry['member0'],0)
        for corrupt in ('unknown\n'+stdout, stdout+'extra\n',
                        stdout.replace('"member0":0','"member0":1'),
                        stdout.replace('"member0":0','"member0":0,"member0":0')):
            with self.assertRaises(ValueError):qualifier.parse_script_stdout(corrupt)


if __name__ == '__main__':
    unittest.main()
