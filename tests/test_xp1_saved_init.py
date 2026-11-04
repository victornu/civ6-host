"""Pure captured Init input checks; no engine, DB DLL or process execution."""
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace as NS
import hashlib
import os
import tempfile
import unittest
from unittest.mock import Mock, patch

from civ6_host.runtime import xp1_saved_init as binding
from civ6_host.runtime import xp1_saved_load as saved
from civ6_host.runtime.native import native_official_bundle as original
from civ6_host.runtime.native import native_checkpoint_configuration_only as config
from civ6_host.runtime.native import native_host as host_module
from civ6_host.runtime.native import native_xp1_context_init as init
from civ6_host.runtime.native import native_xp1_teardown_adapter as teardown
import test_xp1_saved_load_boundary as boundary_tests


class CapturedInitTests(unittest.TestCase):
    def fixture(self, *, register=True):
        _, bundle = boundary_tests.XP1SavedLoadBoundaryTests.fixture(self)
        directory = tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent)
        self.addCleanup(directory.cleanup)
        root = Path(directory.name).resolve()
        package, private = root / 'package', root / 'worker'
        package.mkdir(); private.mkdir()
        pins, source_rows, copied_rows = {}, {}, {}
        for role in ('configuration', 'gameplay', 'localization'):
            data = init.SQLITE_HEADER + role.encode('ascii')
            source, copy = package / (role + '.sqlite'), private / (role + '.sqlite')
            source.write_bytes(data); copy.write_bytes(data)
            pins[role] = dict(sha256=hashlib.sha256(data).hexdigest(), size_bytes=len(data))
            source_rows[role] = dict(path=str(source), **pins[role])
            copied_rows[role] = dict(path=str(copy), **pins[role])
        bundle.fixture.update(official_bundle=dict(path=saved.REFERENCE[0], sha256=saved.REFERENCE[1]), databases=source_rows)
        bundle.content_profile['final_databases'] = deepcopy(pins)
        for p in (patch.object(binding, 'DATABASE_PINS', pins),
                  patch.object(original, '_prepared_bundle_validator_digests', return_value={key:'a'*64 for key in original._PREPARED_BUNDLE_VALIDATOR_PATHS}),
                  patch('civ6_host.runtime.xp1_bundle_inputs.reader_validator_digests', return_value={'test-input':'b'*64})):
            p.start(); self.addCleanup(p.stop)
        if register:
            original._remember_prepared_bundle(bundle, 'xp1-lan', original._prepared_bundle_validator_digests(),
                _token=original._PARENT_ADMISSION_TOKEN, _input_only=True)
        host = NS(manifest=dict(bundle.fixture, databases=copied_rows), pointer=123,
            native_aligned_free=None, event_recorder=None, vtable=[1]*64,
            logger_vtable=[1]*9, logger_object=[1], filters=NS(entries={}),
            paths={312:os.fsencode(copied_rows['gameplay']['path']), 320:os.fsencode(copied_rows['configuration']['path'])})
        return bundle, host, Path(copied_rows['configuration']['path']), Path(copied_rows['gameplay']['path']), private

    def test_candidate_uses_exact_owner_and_actual_hashes_without_relabelling_sources(self):
        bundle, host, configuration, gameplay, root = self.fixture()
        historical = (init.XP1_CONFIG_SHA256, init.XP1_GAMEPLAY_SHA256, deepcopy(init.PROOF_PINS))
        receipt = init.validate_private_inputs(host, configuration, gameplay, root, candidate_bundle=bundle)
        self.assertEqual(receipt['configuration_sha256'], hashlib.sha256(configuration.read_bytes()).hexdigest())
        self.assertEqual(receipt['captured_input_binding']['origin']['sha256'], saved.REFERENCE[1])
        self.assertFalse(receipt['captured_input_binding']['historical_diagnostic_fixture_reused'])
        self.assertEqual(historical, (init.XP1_CONFIG_SHA256, init.XP1_GAMEPLAY_SHA256, init.PROOF_PINS))

    def test_default_retains_historical_pins_and_receipt_shape(self):
        _, host, configuration, gameplay, root = self.fixture()
        self.assertEqual(init.XP1_CONFIG_SHA256, '95b68bf37549690e6771925cfa189da87e810c94a09c6508059fa3f6583f3faf')
        self.assertEqual(init.XP1_GAMEPLAY_SHA256, '637f3f53b4d8609bc0325de5dac2008f80f7a7437d3ef4b6d26d31576563717e')
        with self.assertRaisesRegex(ValueError, 'pinned private diagnostic'):
            init.validate_private_inputs(host, configuration, gameplay, root)
        with patch.object(init, 'XP1_CONFIG_SHA256', binding.DATABASE_PINS['configuration']['sha256']), \
             patch.object(init, 'XP1_CONFIG_BYTES', configuration.stat().st_size), \
             patch.object(init, 'XP1_GAMEPLAY_SHA256', binding.DATABASE_PINS['gameplay']['sha256']), \
             patch.object(init, 'XP1_GAMEPLAY_BYTES', gameplay.stat().st_size):
            self.assertNotIn('captured_input_binding', init.validate_private_inputs(host, configuration, gameplay, root))

    def test_unregistered_or_changed_bundle_never_selects_new_pins(self):
        bundle, host, configuration, gameplay, root = self.fixture(register=False)
        with self.assertRaisesRegex(ValueError, 'parent-admitted'):
            init.validate_private_inputs(host, configuration, gameplay, root, candidate_bundle=bundle)
        original._remember_prepared_bundle(bundle, 'xp1-lan', original._prepared_bundle_validator_digests(),
            _token=original._PARENT_ADMISSION_TOKEN, _input_only=True)
        bundle.dependencies['tampered'] = 'f'*64
        with self.assertRaisesRegex(ValueError, 'contents changed'):
            init.validate_private_inputs(host, configuration, gameplay, root, candidate_bundle=bundle)

    def test_private_bytes_still_use_existing_hash_and_sqlite_guards(self):
        bundle, host, configuration, gameplay, root = self.fixture()
        configuration.write_bytes(b'X' + configuration.read_bytes()[1:])
        with self.assertRaisesRegex(ValueError, 'Configuration candidate differs'):
            init.validate_private_inputs(host, configuration, gameplay, root, candidate_bundle=bundle)

    def test_manifest_and_callback_paths_remain_bound_to_private_copies(self):
        bundle, host, configuration, gameplay, root = self.fixture()
        original_path = host.manifest['databases']['configuration']['path']
        host.manifest['databases']['configuration']['path'] = bundle.fixture['databases']['configuration']['path']
        with self.assertRaisesRegex(ValueError, 'independent private'):
            init.validate_private_inputs(host, configuration, gameplay, root, candidate_bundle=bundle)
        host.manifest['databases']['configuration']['path'] = original_path
        host.paths[320] = os.fsencode(gameplay)
        with self.assertRaisesRegex(ValueError, 'path callbacks'):
            init.validate_private_inputs(host, configuration, gameplay, root, candidate_bundle=bundle)

    def test_unknown_host_state_is_not_accepted_by_candidate_binding(self):
        bundle, host, configuration, gameplay, root = self.fixture()
        host.filters.entries[123] = 1
        with self.assertRaisesRegex(ValueError, 'must be empty before Init'):
            init.validate_private_inputs(host, configuration, gameplay, root, candidate_bundle=bundle)
        host.filters.entries.clear(); host.native_aligned_free = object()
        with self.assertRaisesRegex(ValueError, 'keep it unbound'):
            init.validate_private_inputs(host, configuration, gameplay, root, candidate_bundle=bundle)

    def test_teardown_requires_same_actual_receipt_and_keeps_native_state_checks(self):
        bundle, host, configuration, gameplay, root = self.fixture()
        inputs = init.validate_private_inputs(host, configuration, gameplay, root, candidate_bundle=bundle)
        receipt = dict(schema='civ6rl.native_xp1_context_init_receipt.v1', inputs=inputs,
            status='xp1_context_initialized_diagnostic_only', core_sha256=init.XP1_CORE_SHA256,
            init_called=True, init_returned=True, initialized_after=True, host_setter_called=True,
            context_may_require_destroy=True, game_created=False, newgame_called=False,
            prepare_called=False, simulation_ready=False, eligible_for_training=False,
            connections=dict(configuration_slot='inner+0x50', configuration_nonnull=True,
                             gameplay_slot='inner+0x58', gameplay_nonnull=True))
        host.context_init_receipt = receipt
        binding.validate_init_receipt_binding(bundle, host, receipt)
        with self.assertRaisesRegex(ValueError, 'retained Init receipt owner'):
            binding.validate_init_receipt_binding(bundle, host, deepcopy(receipt))
        with self.assertRaisesRegex(ValueError, 'does not restrict host'):
            teardown._check_init_receipt(receipt, host, candidate_bundle=bundle)
        receipt['connections']['gameplay_nonnull'] = False
        with self.assertRaisesRegex(ValueError, 'non-null'):
            teardown._check_init_receipt(receipt, host, candidate_bundle=bundle)
        receipt['connections']['gameplay_nonnull'] = True
        inputs['configuration_sha256'] = init.XP1_CONFIG_SHA256
        with self.assertRaisesRegex(ValueError, 'captured database binding'):
            teardown._check_init_receipt(receipt, host, candidate_bundle=bundle)

    def test_backend_passes_only_explicit_candidate_owner(self):
        backend = config._NativeBackend.__new__(config._NativeBackend)
        backend.core, backend.context, backend.fixture = object(), 123, 'fixture'
        backend.dll_directory, backend.emit, backend.profile = 'shared', Mock(), object()
        with patch.object(config, 'initialize_context', return_value=object()) as call:
            backend.initialize()
            self.assertNotIn('candidate_bundle', call.call_args.kwargs)
            backend._saved_load_candidate = True
            with self.assertRaisesRegex(ValueError, 'lost its captured input owner'):backend.initialize()
            backend.captured_bundle = object(); backend.initialize()
            self.assertIs(call.call_args.kwargs['candidate_bundle'], backend.captured_bundle)

    def test_candidate_cannot_change_base_initialization_before_native_calls(self):
        with patch.object(host_module.C, 'WinDLL') as dll:
            with self.assertRaisesRegex(ValueError, 'explicit XP1 context'):
                host_module.initialize_context(NS(), 1, 'fixture', '.', Mock(), candidate_bundle=object())
            dll.assert_not_called()

    def test_host_validates_candidate_before_database_and_forwards_same_owner(self):
        from test_context_lifecycle import profile
        from civ6_host.runtime.native import native_core_context_profiles as profiles
        from civ6_host.runtime.native import native_probe
        selected, candidate, order = profile(), object(), []
        core = NS(_name='xp1.dll', _handle=100)
        database = NS()
        setattr(database, '?Initialize@Database@@YA_NXZ', Mock(side_effect=lambda: order.append('database') or True))
        adapter = NS(log_writers=NS(enable_native_sink=Mock()))
        manifest = {'databases': {'configuration': {'path': 'config.db'}, 'gameplay': {'path': 'game.db'}}}
        receipt = {'actual-init-receipt': True}
        def initialize(*args, **kwargs):
            self.assertIs(kwargs['candidate_bundle'], candidate)
            order.append('init')
            return receipt
        def close_binding(*args, **kwargs):
            self.assertIs(kwargs['candidate_bundle'], candidate)
            self.assertIs(adapter.context_init_receipt, receipt)
            order.append('teardown-binding')
            return {'installed': True}
        with patch.object(profiles, 'profile_for_core', return_value=selected), \
             patch.object(saved, 'bind_candidate', side_effect=lambda *a: order.append('capture')) as capture, \
             patch.object(host_module, 'validate_fixture', return_value=manifest), \
             patch.object(host_module, 'sha256', return_value=host_module.DATABASE_SHA256), \
             patch.object(host_module.C, 'WinDLL', return_value=database), \
             patch.object(host_module, 'DiagnosticHost', return_value=adapter), \
             patch.object(init, 'initialize_xp1_context', side_effect=initialize), \
             patch.object(teardown, 'install_xp1_teardown_callbacks', side_effect=close_binding), \
             patch.object(native_probe, 'Windows', return_value=NS(modules=lambda: [])):
            host_module.initialize_context(core, 1, 'manifest', '.', Mock(),
                context_profile=selected, candidate_bundle=candidate)
            capture.assert_called_once_with(candidate, selected, 'manifest')
            self.assertEqual(order, ['capture', 'database', 'init', 'teardown-binding'])
