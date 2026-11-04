"""Exact native GameplayScripts names mapped to pinned physical Lua sources."""
from copy import deepcopy
import ctypes as C
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from civ6_host.runtime import capture_admission, xp2_bundle_inputs as xp2
from civ6_host.runtime.native.native_gameplay_script_registry import (
    GameplayScriptEntry, NativeGameplayScriptRegistry,
)
from civ6_host.runtime.paths import resource_root
from civ6_host.runtime import script_wire_paths
from civ6_host.runtime.script_context_service import script_name
import test_script_context_service as context_tests


LAB = resource_root()
CAPTURE_PATH = LAB / xp2.REFERENCE[0]
PREPARED_PATH = LAB / 'work/host-prepared-captures/xp2-gs-lan-rows-20261102/manifest.json'
PREPARED_SHA256 = '6468bf13145fa712438bd276896273630789ca4afb6003d904b66a8aa29e2020'
WIRE = xp2.SELECTED_PATHS[0]


def _utf16_pointer(value):
    raw = value if isinstance(value, bytes) else value.encode('utf-16-le', 'strict')
    return C.create_string_buffer(raw + b'\0\0')


class ScriptWirePathTests(unittest.TestCase):
    def test_registry_preserves_wire_order_duplicates_and_buffer_bytes(self):
        with tempfile.TemporaryDirectory(dir=LAB / 'work') as temporary:
            root = Path(temporary)
            first = root / 'captured-a.lua'
            second = root / 'captured-b.lua'
            first.write_bytes(b'a=1')
            second.write_bytes(b'b=2')
            wire = ('../../../DLC/Expansion2/Scripts/WorldCongress.lua',
                    'Mods/Example/Scenario.lua',
                    '../../../DLC/Expansion2/Scripts/WorldCongress.lua')
            registry = NativeGameplayScriptRegistry(
                [root], selected_scripts=[GameplayScriptEntry(root, p.name) for p in (first, second, first)],
                wire_paths=wire)
            try:
                self.assertEqual(registry.count(), 3)
                self.assertEqual(registry.paths, (first, second, first))
                self.assertEqual(registry.wire_paths, wire)
                for i, name in enumerate(wire):
                    encoded = name.encode('utf-16-le')
                    self.assertEqual(C.string_at(registry.get(i), len(encoded)), encoded)
                self.assertEqual(C.string_at(registry.get(0), len(WIRE.encode('utf-16-le'))),
                                 C.string_at(registry.get(2), len(WIRE.encode('utf-16-le'))))
                self.assertIsNone(registry.get(3))
            finally:
                registry.close()

    def test_wire_names_are_bounded_and_physical_entries_stay_under_root(self):
        self.assertEqual(script_wire_paths.encode_wire_path('A' * 255 + '.lua'),
                         ('A' * 255 + '.lua').encode('utf-16-le'))
        for bad in ('', 'NoExtension', 'x\0.lua', 'A' * 256 + '.lua'):
            with self.subTest(value=bad[:20]), self.assertRaises((ValueError, UnicodeError)):
                script_wire_paths.encode_wire_path(bad)
        with self.assertRaises((ValueError, UnicodeError)):
            script_wire_paths.encode_wire_path('bad\ud800.lua')
        with tempfile.TemporaryDirectory(dir=LAB / 'work') as temporary:
            base = Path(temporary)
            root = base / 'approved'
            root.mkdir()
            outside = base / 'outside.lua'
            outside.write_bytes(b'outside')
            with self.assertRaises(ValueError):
                NativeGameplayScriptRegistry([root], selected_scripts=[
                    GameplayScriptEntry(root, '../outside.lua')], wire_paths=('Outside.lua',))

    def test_service_uses_exact_wire_name_for_lookup_context_and_chunk(self):
        harness = context_tests.ContextServiceTests()
        host, runtime, service, registry, physical = harness.fixture(wire_paths=(WIRE, WIRE))
        self.addCleanup(harness.doCleanups)
        try:
            self.assertEqual(service.paths, (physical, physical))
            self.assertEqual(service.wire_paths, (WIRE, WIRE))
            address = service.script_path(service.receiver, 0)
            self.assertEqual(C.string_at(address, len(WIRE.encode('utf-16-le'))), WIRE.encode('utf-16-le'))
            self.assertEqual(service.file_exists(service.receiver, address, 1), 1)
            self.assertEqual(service.wire_sources[WIRE], physical)
            context = service.acquire(service.receiver, script_name(WIRE), 0)
            self.assertEqual(service.load(service.receiver, context, address), 1)
            self.assertEqual(runtime.execute.call_args.args[1], b'answer=42')
            self.assertEqual(runtime.execute.call_args.args[2], WIRE.encode('utf-8'))
            service.release(service.receiver, context)
            service.close()
            with self.assertRaises(RuntimeError):
                service.script_count(service.receiver)
        finally:
            if not service.closed:
                service.close()

    def test_unknown_case_changed_nul_surrogate_and_overlong_wire_paths_refuse(self):
        harness = context_tests.ContextServiceTests()
        host, runtime, service, registry, physical = harness.fixture(wire_paths=(WIRE, WIRE))
        self.addCleanup(harness.doCleanups)
        unknown = (
            'other.lua',
            WIRE.swapcase(),
            WIRE[:8] + '\0' + WIRE[8:] + '.lua',
            b'B\x00a\x00d\x00\x00\xd8\x00\x00',  # lone UTF-16 high surrogate followed by NUL
            'A' * 256 + '.lua',
        )
        try:
            for value in unknown:
                with self.subTest(value=value if isinstance(value, str) else value.hex()):
                    if isinstance(value, str) and len(value.encode('utf-16-le')) // 2 > 259:
                        value = value[:]
                        raw = value.encode('utf-16-le') + b'\0\0'
                    else:
                        raw = value if isinstance(value, bytes) else value.encode('utf-16-le') + b'\0\0'
                    buffer = C.create_string_buffer(raw)
                    with self.assertRaises((ValueError, UnicodeError)):
                        service._path(C.addressof(buffer))
            buffer = _utf16_pointer(WIRE.swapcase())
            with self.assertRaisesRegex(ValueError, 'unselected'):
                service.file_exists(service.receiver, C.addressof(buffer), 1)
            service.close()
        finally:
            if not service.closed:
                service.close()

    def test_wire_collision_cannot_bind_two_physical_files(self):
        harness = context_tests.ContextServiceTests()
        _, _, service, _, first = harness.fixture()
        service.close()
        second = first.with_name('Different.lua')
        second.write_bytes(b'other=9')
        with self.assertRaisesRegex(ValueError, 'different physical sources'):
            NativeGameplayScriptRegistry([first.parent], selected_scripts=[
                GameplayScriptEntry(first.parent, first.name), GameplayScriptEntry(first.parent, second.name)],
                wire_paths=(WIRE, WIRE))
        harness.doCleanups()

    def test_registry_mutation_is_detected_while_contexts_are_retained(self):
        harness = context_tests.ContextServiceTests()
        host, runtime, service, registry, physical = harness.fixture(wire_paths=(WIRE, WIRE))
        self.addCleanup(harness.doCleanups)
        original = registry._wire_paths
        registry._wire_paths = ('Changed.lua', 'Changed.lua')
        with self.assertRaisesRegex(RuntimeError, 'selection changed'):
            service.script_count(service.receiver)
        registry._wire_paths = original
        service.close()
        registry.close()
        with self.assertRaises(RuntimeError):
            service.script_count(service.receiver)

    def test_actual_xp2_capture_maps_logical_world_congress_to_pinned_copy(self):
        capture = json.loads(CAPTURE_PATH.read_text(encoding='utf-8'))
        scripts_reference = capture['selected_gameplay_sources']['manifest']
        scripts = json.loads(Path(scripts_reference['path']).read_text(encoding='utf-8'))
        process = capture['preflight']['process']
        registry, hashes, dependencies = script_wire_paths.registry_from_capture(scripts_reference, process=process)
        self.addCleanup(registry.close)
        self.assertEqual(registry.wire_paths, xp2.SELECTED_PATHS)
        self.assertEqual(len(registry.paths), 1)
        physical = registry.paths[0]
        self.assertEqual(physical.name, xp2.SCRIPT_SHA256 + '.lua')
        self.assertEqual(hashes, {physical: xp2.SCRIPT_SHA256})
        self.assertEqual(len(physical.read_bytes()), xp2.SCRIPT_BYTES)
        self.assertEqual(hashlib.sha256(physical.read_bytes()).hexdigest(), xp2.SCRIPT_SHA256)
        self.assertEqual(scripts['selected_paths'], list(registry.wire_paths))
        self.assertEqual(scripts['records'][0]['copy'], physical.name)
        self.assertIn(str(Path(scripts_reference['path']).resolve()), dependencies)
        self.assertIn(str(physical.resolve()), dependencies)

    def test_actual_capture_manifest_and_process_must_match_pins(self):
        capture = json.loads(CAPTURE_PATH.read_text(encoding='utf-8'))
        process = deepcopy(capture['preflight']['process'])
        scripts_reference = capture['selected_gameplay_sources']['manifest']
        with self.assertRaises(ValueError):
            script_wire_paths.registry_from_capture(dict(scripts_reference, sha256='0' * 64), process=process)
        process['identity']['pid'] += 1
        with self.assertRaises(ValueError):
            script_wire_paths.registry_from_capture(scripts_reference, process=process)

    def test_known_xp2_input_package_keeps_reader_parsers_unchanged(self):
        raw = PREPARED_PATH.read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(), PREPARED_SHA256)
        manifest = json.loads(raw)
        producer = manifest['validation_identity']
        consumer = capture_admission.validation_identity()
        reference = {'path': str(PREPARED_PATH), 'sha256': PREPARED_SHA256}
        admission = {
            'private_input_profile': 'xp2-lan',
            'native_session_qualified': False,
            'origin_path': manifest['origin']['path'],
            'origin_sha256': manifest['origin']['sha256'],
            'package_sha256': PREPARED_SHA256,
        }
        transitions = capture_admission._check_xp2_prepared_reader(
            producer, consumer, admission, manifest, reference)
        self.assertEqual(len(transitions), 1)
        self.assertEqual(transitions[0]['transition'], 'xp2_exact_input_reader_identity_v1')
        self.assertFalse(transitions[0]['native_session_admitted'])
        self.assertFalse(transitions[0]['producer_identity_substituted'])

        for bad_admission, bad_manifest, bad_reference in (
            (dict(admission, package_sha256='0' * 64), manifest, reference),
            (admission, manifest, dict(reference, sha256='0' * 64)),
            (admission, dict(manifest, origin=dict(manifest['origin'], sha256='0' * 64)), reference),
            (admission, dict(manifest, input_profile='lan'), reference),
        ):
            with self.subTest(package=bad_admission['package_sha256'], profile=bad_manifest['input_profile']), \
                 self.assertRaises(ValueError):
                capture_admission._check_xp2_prepared_reader(
                    producer, consumer, bad_admission, bad_manifest, bad_reference)

        bad_consumer = deepcopy(consumer)
        parser_key = 'runtime/native/official_configuration.py'
        bad_consumer['runtime_sources'][parser_key] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'input validator changed'):
            capture_admission._check_xp2_prepared_reader(
                producer, bad_consumer, admission, manifest, reference)
        bad_producer = deepcopy(producer)
        bad_producer['runtime_sources'][parser_key] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'input validator changed'):
            capture_admission._check_xp2_prepared_reader(
                bad_producer, consumer, admission, manifest, reference)


if __name__ == '__main__':
    unittest.main()
