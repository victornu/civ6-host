"""Captured XP2 Load selection and source binding; no GameCore execution."""
from dataclasses import replace
from copy import deepcopy
from types import SimpleNamespace as NS
import hashlib
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from civ6_host.runtime import capture_admission, captured_saved_load as m, xp2_bundle_inputs as inputs
from civ6_host.runtime.paths import resource_root
from civ6_host.runtime.saved_load_services import SavedLoadServices


class CapturedSavedLoad(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bundle = inputs.consume_input_handoff(dict(
            path=str(resource_root()/'work/host-prepared-captures/xp2-gs-lan-rows-20261102/manifest.json'),
            sha256='6468bf13145fa712438bd276896273630789ca4afb6003d904b66a8aa29e2020'))

    def test_preload_scope_uses_prepared_inputs_before_backend_binding(self):
        closure=dict(input_profile='xp2-lan',raw_only_candidate=True,
            post160_candidate=True,publish_cache_candidate=True,
            observe_player_candidate=True,close_loaded_candidate=True)
        backend=NS(captured_bundle=self.bundle,inputs=None,
            load_abi=NS(core_sha256=m.XP2_CORE_SHA256))
        m.configure_requested(backend,closure)
        self.assertIsNone(backend.inputs)
        self.assertIs(backend._xp2_postload_requested,True)
        self.assertIs(backend._xp1_commands_requested,False)
        with self.assertRaisesRegex(ValueError,'already selected'):
            m.configure_requested(backend,closure)
        wrong=NS(captured_bundle=self.bundle,inputs=None,
            load_abi=NS(core_sha256=m.XP1_CORE_SHA256))
        with self.assertRaisesRegex(ValueError,'selected engine'):
            m.configure_requested(wrong,closure)
        self.assertFalse(hasattr(wrong,'_xp1_commands_requested'))

        foreign = NS(captured_bundle=self.bundle, inputs=None,
                     load_abi=NS(core_sha256=m.XP2_CORE_SHA256))
        with patch('civ6_host.runtime.session_configuration.read_saved_roster',
                   return_value={'taken_slot_ids': [0, 1]}), patch(
                       'civ6_host.runtime.xp1_action_transport.configure_requested') as configure:
            with self.assertRaisesRegex(ValueError, 'Saved taken seats differ'):
                m.configure_requested(foreign, closure)
            configure.assert_not_called()

    def test_worker_refuses_unadmitted_xp2_scopes_before_native_loading(self):
        from civ6_host.runtime.workers import run_official_postload909 as worker
        closure=dict(input_profile='xp2-lan',raw_only_candidate=True)
        with patch.object(worker.C,'WinDLL',side_effect=AssertionError('DLL forbidden')) as load:
            for key, reason in (
                    ('network_checkpoint', 'Unsupported LAN checkpoint closure'),
                    ('resume_checkpoint', 'cannot inherit a historical Base checkpoint')):
                with self.subTest(key=key), self.assertRaisesRegex(ValueError, reason):
                    worker.open_official_backend(dict(closure,**{key:{}}),None,None)
            with self.assertRaisesRegex(ValueError,'dependencies are incomplete'):
                worker.open_official_backend(dict(closure,unit_commands_candidate=True),None,None)
            load.assert_not_called()
        self.assertEqual(m.select_load_closure(closure).core_sha256,m.XP2_CORE_SHA256)
        self.assertEqual(m.select_load_closure(dict(closure,input_profile='xp1-lan',
            network_checkpoint={})).core_sha256,m.XP1_CORE_SHA256)

    def test_actual_retained_inputs_engine_and_roster_without_native_claim(self):
        b = self.bundle
        self.assertIs(m.validate_candidate_inputs(b.inputs, b), inputs.XP2_LAN_PROFILE)
        with self.assertRaises(ValueError):
            m.validate_candidate_inputs(replace(b.inputs), b)
        with self.assertRaises(ValueError):
            m.validate_candidate_inputs(b.inputs, replace(b, initial_turn=2))
        backend = NS(captured_bundle=b, inputs=b.inputs, host=NS(configured_local_player_id=0))
        receipt = m.validate_loaded_roster(backend, b'1|44|26|0|1', b'0=1|1=0')
        self.assertFalse(receipt['public_session_admitted'])
        for roster in (b'2|44|26|0|1', b'1|74|46|0|1|2|3|4|5', b'1|44|26|0|1|2'):
            with self.assertRaises(ValueError):
                m.validate_loaded_roster(backend, roster, b'0=1|1=0')

    def test_parent_binding_round_trips_through_prepared_worker_admission(self):
        package = capture_admission.configured_reference()
        closure = dict(input_profile='xp2-lan', pins={package['path']: package['sha256']},
                       official_bundle=dict(zip(('path', 'sha256'), self.bundle.reference)))
        self.assertTrue(capture_admission.configure_prepared_closure(closure, self.bundle))
        serialized = json.loads(json.dumps(closure))
        key = capture_admission.XP2_LAUNCH_FIELD
        self.assertEqual(serialized[key]['saved_geometry'], dict(
            turn=1, width=44, height=26, local_player_id=0, major_player_ids=[0, 1], taken_player_ids=[0]))
        receipt = capture_admission.consume_prepared_closure(serialized, _candidate_profile='xp2-lan')
        self.assertEqual(receipt[key], serialized[key])
        self.assertEqual(receipt[key]['configuration_sha256'], hashlib.sha256(self.bundle.inputs.configuration).hexdigest())
        self.assertEqual(receipt[key]['gamecore_sha256'], hashlib.sha256(self.bundle.inputs.game).hexdigest())

    def test_tampered_launch_binding_is_refused_by_the_shared_worker_before_dll(self):
        from civ6_host.runtime.workers import run_official_postload909 as worker
        package = capture_admission.configured_reference()
        closure = dict(input_profile='xp2-lan', raw_only_candidate=True, initial_turn=1,
                       pins={package['path']: package['sha256']},
                       official_bundle=dict(zip(('path', 'sha256'), self.bundle.reference)))
        capture_admission.configure_prepared_closure(closure, self.bundle)
        key = capture_admission.XP2_LAUNCH_FIELD
        for field, value in (('width', 45), ('local_player_id', False), ('gamecore_sha256', 'a' * 64)):
            modified = deepcopy(closure)
            target = modified[key] if field == 'gamecore_sha256' else modified[key]['saved_geometry']
            target[field] = value
            with self.subTest(field=field), patch.object(worker.C, 'WinDLL') as load:
                with self.assertRaisesRegex(ValueError, 'launch binding differs'):
                    worker.open_official_backend(modified, lambda *args, **kwargs: None, None)
                load.assert_not_called()

    def test_current_network_worker_requires_the_launch_binding(self):
        from civ6_host.runtime.workers import network_worker
        from civ6_host.runtime.xp1_session_inputs import SAVED_LOAD_CLOSURE_ENV
        closure = dict(input_profile='xp2-lan', raw_only_candidate=True)
        raw = json.dumps(closure).encode()
        with TemporaryDirectory() as directory:
            path = Path(directory) / 'closure.json'
            path.write_bytes(raw)
            with patch.dict(os.environ, {SAVED_LOAD_CLOSURE_ENV: hashlib.sha256(raw).hexdigest()}):
                with self.assertRaisesRegex(ValueError, 'requires its prepared launch binding'):
                    network_worker._open_xp1(closure, path, lambda *args, **kwargs: None, None)

    def test_exact_engine_source_and_changed_instruction_refusal(self):
        base = 0x100000000
        proof = m.proofs_for_candidate(m.XP2_CORE_SHA256)
        memory = {}
        for body in m.xp1._source_bodies(m.XP2_CORE_SHA256).values():
            for f in body['fragments']:
                for r in f['instructions']:
                    memory[base + int(r['va'],16)-0x180000000] = bytes.fromhex(r['bytes'])
        read = lambda addr, size: memory.get(addr, b'')[:size]
        result = m.verify_live(base, read, proof)
        self.assertFalse(result['native_call_made'])
        with self.assertRaises(ValueError):
            m.verify_live(base, read, m.xp1.proofs_for_candidate())
        for changed in ({**proof, 'saved_load_engine_sha256':m.XP1_CORE_SHA256},
                        {**proof, 'xp1_saved_load_sources':m.SOURCES}):
            with self.assertRaises(ValueError):
                m.verify_live(base, read, changed)
        key = min(memory);memory[key] = b'\xcc' * len(memory[key])
        with self.assertRaises(ValueError):
            m.verify_live(base, read, proof)

    def test_nonempty_official_script_cannot_be_dropped_or_replaced(self):
        from civ6_host.runtime.script_wire_paths import registry_from_capture
        capture = json.loads((resource_root()/inputs.REFERENCE[0]).read_bytes())
        registry, hashes, _ = registry_from_capture(capture['selected_gameplay_sources']['manifest'],
                                                  process=capture['preflight']['process'])
        self.assertEqual(tuple(registry.wire_paths), inputs.SELECTED_PATHS)
        backend = NS(captured_bundle=self.bundle, inputs=self.bundle.inputs)
        services = SavedLoadServices.__new__(SavedLoadServices)
        services.backend = backend;services.core_sha256 = m.XP2_CORE_SHA256
        services.saved_config_sha = hashlib.sha256(backend.inputs.configuration).hexdigest()
        services.saved_map_values = backend.inputs.map_values
        path = registry.paths[0]
        services.contexts = NS(wire_paths=tuple(registry.wire_paths),
            wire_sources={inputs.SELECTED_PATHS[0]:path}, sources={path:path.read_bytes()})
        with patch.object(SavedLoadServices, 'attach') as attach:
            m.attach_services(backend, services)
            attach.assert_called_once_with(backend)
            services.contexts.wire_paths = ()
            with self.assertRaises(ValueError):m.attach_services(backend, services)
            services.contexts.wire_paths = inputs.SELECTED_PATHS
            services.contexts.sources[path] += b'\n-- modified'
            with self.assertRaises(ValueError):m.attach_services(backend, services)
            self.assertEqual(attach.call_count, 1)


if __name__ == '__main__':unittest.main()
