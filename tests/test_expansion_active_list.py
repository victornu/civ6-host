"""Fixture-only multi-engine checks for the read-only active-list boundary.

These tests synthesize bytes from the pinned source profile. They do not start
GameCore, read an installed process, decode nonempty records, or certify an
engine's gameplay behavior.
"""
from __future__ import annotations

import copy
import struct
import unittest
from unittest.mock import patch

from civ6_host.runtime.native import native_gameplay_empty as empty
from civ6_host.runtime import gameplay_active_profiles as active_profiles


BASE = empty.BASE_CORE_SHA256
EXPANSION_CORES = tuple(sorted(active_profiles.SUPPORTED_CORES - {BASE}))


class Memory:
    base = 0x180000000
    exe_base = 0x140000000
    inner = 0x2000000000
    game = 0x2100000000
    manager = 0x2200000000
    auxiliary = 0x2300000000
    storage = 0x2400000000

    def __init__(self, core_sha256=BASE):
        self.core_sha256 = core_sha256
        self.cells = {}
        self.calls = []
        self.source = empty.source_profile(core_sha256=core_sha256)
        self.layout = self.source['layout']
        preferred = int(self.source['image']['image_base'], 16)
        for function in self.source['functions'].values():
            for fragment in function.get('fragments', [function]):
                raw = bytes.fromhex(''.join(row['bytes'] for row in fragment['instructions']))
                self.cells[self.base + int(fragment['start_va'], 16) - preferred] = raw
        for offset, target in self.source['load_vtable_slots']['slots'].items():
            self.qword(self.base + self.layout['inner_vtable_rva'] + int(offset, 16),
                       self.base + int(target, 16) - preferred)
        self.qword(self.base + self.layout['inner_global_rva'], self.inner)
        self.qword(self.inner, self.base + self.layout['inner_vtable_rva'])
        self.cells[self.inner + self.layout['context_initialized_offset']] = b'\1'
        self.cells[self.inner + self.layout['loading_offset']] = b'\0'
        self.qword(self.inner + self.layout['game_offset'], self.game)
        self.qword(self.game, self.base + self.layout['game_vtable_rva'])
        self.cells[self.game + self.layout['game_initialized_offset']] = b'\1'
        self.qword(self.base + self.layout['auxiliary_global_rva'], self.auxiliary)
        self.auxiliary_vtable = self.exe_base + self.layout['auxiliary_exe_vtable_rva']
        self.qword(self.auxiliary, self.auxiliary_vtable)
        self.qword(self.inner + self.layout['script_manager_offset'], self.manager)
        self.qword(self.manager + self.layout['storage_offset'], 0)
        self.header(0, self.layout['sentinel'], self.layout['sentinel'])

    def qword(self, address, value):
        self.cells[address] = struct.pack('<Q', value)

    def header(self, count, head, tail):
        self.cells[self.manager + self.layout['active_count_offset']] = struct.pack(
            '<III', count, head, tail)

    def read(self, address, size):
        self.calls.append((address, size))
        result = self.cells[address]
        if len(result) != size:
            raise AssertionError((address, size, len(result)))
        return result

    def capture(self, **options):
        return empty.read_gameplay_state(self.read, self.base,
            expected_auxiliary_vtable=self.auxiliary_vtable,
            core_sha256=self.core_sha256, **options)


class ProcessFixture:
    def __init__(self, core_sha256=BASE):
        self.core_sha256 = core_sha256
        self.memory = Memory(core_sha256 if core_sha256 in active_profiles.SUPPORTED_CORES else BASE)
        self.identity_value = {'pid': 123, 'creation_filetime': 456,
                               'image_path': 'CivilizationVI.exe'}
        self.exe = {'base': Memory.exe_base, 'name': 'CivilizationVI.exe',
                    'path': 'CivilizationVI.exe', 'bytes': 0x3000000}
        name = 'GameCore_Base_FinalRelease.dll' if core_sha256 == BASE else 'GameCore_Expansion.dll'
        self.core = {'base': Memory.base, 'name': name, 'path': name, 'bytes': 0x1000000}
        self.module_values = [self.exe, self.core]
        self.identity_calls = 0
        self.module_calls = 0

    def identity(self):
        self.identity_calls += 1
        return copy.deepcopy(self.identity_value)

    def modules(self):
        self.module_calls += 1
        return copy.deepcopy(self.module_values)

    def read(self, address, size):
        return self.memory.read(address, size)

    def selection(self):
        return {'schema': 'civ6rl.official_gameplay_selection994.capture.v1',
            'process': self.identity(), 'exe_module': copy.deepcopy(self.exe),
            'gamecore_module': {**self.core, 'sha256': self.core_sha256},
            'execution_proven': False,
            'snapshot': {'schema': 'civ6rl.gameplay_selection994.memory_snapshot.v1',
                'record_count': 0, 'records': [], 'selected_paths': [], 'bounds': {}}}


class ExpansionActiveListTests(unittest.TestCase):
    def test_supported_profiles_are_base_plus_two_expansions(self):
        self.assertEqual(len(active_profiles.SUPPORTED_CORES), 3)
        self.assertIn(BASE, active_profiles.SUPPORTED_CORES)
        self.assertEqual(len(EXPANSION_CORES), 2)
        for core_sha256 in active_profiles.SUPPORTED_CORES:
            self.assertEqual(len(active_profiles.source_digest(core_sha256)), 64)
            profile = empty.source_profile(core_sha256=core_sha256)
            self.assertTrue({'status', 'image', 'layout', 'functions',
                             'load_vtable_slots', 'checks'}.issubset(profile))
            self.assertEqual(profile['image']['sha256'], core_sha256)
            self.assertEqual(profile['status'],
                'base_empty_active_list_and_load_consumption_source_verified'
                if core_sha256 == BASE else 'static_layout_verified_no_execution')

    def test_base_reader_output_schema_and_source_remain_unchanged(self):
        memory = Memory(BASE)
        value = memory.capture()
        self.assertEqual(value['schema'], empty.STATE_SCHEMA)
        self.assertEqual(value['schema'], active_profiles.state_schema(BASE))
        self.assertEqual(value['source_sha256'], empty.SOURCE_SHA256)
        self.assertEqual(value['core_sha256'], BASE)
        self.assertTrue(value['active_list_empty'])
        self.assertFalse(value['execution_proven'])
        self.assertFalse(value['load_completion_proven'])

    def test_expansion_empty_and_nonempty_headers_are_bounded_unqualified_witnesses(self):
        for core_sha256 in EXPANSION_CORES:
            with self.subTest(core_sha256=core_sha256):
                memory = Memory(core_sha256)
                empty_state = memory.capture()
                self.assertEqual(empty_state['schema'], active_profiles.state_schema(core_sha256))
                self.assertEqual(empty_state['core_sha256'], core_sha256)
                self.assertTrue(empty_state['active_list_empty'])
                self.assertFalse(empty_state['execution_proven'])
                self.assertFalse(empty_state['load_completion_proven'])
                self.assertFalse(empty_state['training_eligible'])
                self.assertLessEqual(len(memory.calls), empty.MAX_READ_CALLS)

                memory = Memory(core_sha256)
                memory.qword(memory.manager + memory.layout['storage_offset'], Memory.storage)
                memory.header(2, 7, 9)
                nonempty = memory.capture()
                self.assertFalse(nonempty['active_list_empty'])
                self.assertEqual(nonempty['active_count'], 2)
                self.assertFalse(any(address >= Memory.storage for address, _ in memory.calls))
                self.assertFalse(nonempty['execution_proven'])

    def test_expansion_loading_and_uninitialized_state_are_refused(self):
        for core_sha256 in EXPANSION_CORES:
            for key, owner, value in (
                ('loading_offset', 'inner', b'\1'),
                ('context_initialized_offset', 'inner', b'\0'),
                ('game_initialized_offset', 'game', b'\0'),
                ('game_initialized_offset', 'game', b'\2'),
            ):
                memory = Memory(core_sha256)
                address = getattr(memory, owner) + memory.layout[key]
                memory.cells[address] = value
                with self.subTest(core=core_sha256, key=key), self.assertRaisesRegex(
                        empty.ContentSnapshotError, 'uninitialized or loading'):
                    memory.capture()

    def test_expansion_patched_method_and_dispatch_are_refused(self):
        for core_sha256 in EXPANSION_CORES:
            memory = Memory(core_sha256)
            address = next(iter(memory.cells))
            memory.cells[address] = b'\x90' * len(memory.cells[address])
            with self.subTest(core=core_sha256, case='code'), self.assertRaisesRegex(
                    empty.ContentSnapshotError, 'method differs'):
                memory.capture()

            memory = Memory(core_sha256)
            offset = next(iter(memory.source['load_vtable_slots']['slots']))
            address = memory.base + memory.layout['inner_vtable_rva'] + int(offset, 16)
            memory.qword(address, memory.base + 0x1230)
            with self.subTest(core=core_sha256, case='vtable'), self.assertRaisesRegex(
                    empty.ContentSnapshotError, 'dispatch differs'):
                memory.capture()

    def test_source_identity_must_match_the_selected_engine(self):
        for core_sha256 in EXPANSION_CORES:
            with self.subTest(core=core_sha256):
                original_source = active_profiles.SOURCE
                with patch.object(active_profiles, 'SOURCE',
                        (original_source[0], '0' * 64)):
                    with self.assertRaises(ValueError):
                        empty.source_profile(core_sha256=core_sha256)
                process = ProcessFixture(core_sha256)
                selected = process.selection()
                with patch.object(empty, 'capture_selection_process',
                        side_effect=[selected, copy.deepcopy(selected)]), \
                     patch.object(empty, '_file_digest',
                        side_effect=[empty.EXE_SHA, core_sha256]):
                    report = empty.capture_process(process)
                empty.stable_capture_identity(report)
                report['state']['source_sha256'] = 'f' * 64
                with self.assertRaises(empty.ContentSnapshotError):
                    empty.stable_capture_identity(report)
                process = ProcessFixture(core_sha256)
                selected = process.selection()
                with patch.object(empty, 'capture_selection_process',
                        side_effect=[selected, copy.deepcopy(selected)]), \
                     patch.object(empty, '_file_digest',
                        side_effect=[empty.EXE_SHA, core_sha256]):
                    report = empty.capture_process(process)
                report['gamecore_module']['sha256'] = EXPANSION_CORES[1] if core_sha256 == EXPANSION_CORES[0] else EXPANSION_CORES[0]
                with self.assertRaises(empty.ContentSnapshotError):
                    empty.stable_capture_identity(report)

    def test_capture_process_selects_only_the_matching_known_engine_reader(self):
        for core_sha256 in EXPANSION_CORES:
            process = ProcessFixture(core_sha256)
            selected = process.selection()
            state = process.memory.capture()
            with patch.object(empty, 'capture_selection_process',
                    side_effect=[selected, copy.deepcopy(selected)]), \
                 patch.object(empty, '_file_digest', side_effect=[empty.EXE_SHA, core_sha256]):
                report = empty.capture_process(process)
            self.assertEqual(report['gamecore_module']['sha256'], core_sha256)
            self.assertEqual(report['state'], state)
            self.assertTrue(report['selected_and_active_empty'])
            stable = empty.stable_capture_identity(report)
            self.assertEqual(stable['gamecore_module']['sha256'], core_sha256)

    def test_unknown_engine_remains_unsupported_and_direct_read_refuses(self):
        unknown = 'f' * 64
        with self.assertRaises(ValueError):
            empty.source_profile(core_sha256=unknown)
        memory = Memory(BASE)
        with self.assertRaises(ValueError):
            empty.read_gameplay_state(memory.read, memory.base, core_sha256=unknown)
        process = ProcessFixture(unknown)
        selected = process.selection()
        with patch.object(empty, 'capture_selection_process',
                side_effect=[selected, copy.deepcopy(selected)]), \
             patch.object(empty, '_file_digest', side_effect=[empty.EXE_SHA, unknown]), \
             patch.object(empty, 'read_gameplay_state', side_effect=AssertionError(
                 'Unknown engine must not select a reader')):
            report = empty.capture_process(process)
        self.assertIsNone(report['state'])
        self.assertIsNone(report['selected_and_active_empty'])
        self.assertEqual(report['status'], 'unsupported_gamecore')
        self.assertEqual(report['source_sha256'], active_profiles.source_digest(BASE))
        self.assertEqual(empty.stable_capture_identity(report)['status'], 'unsupported_gamecore')


if __name__ == '__main__':
    unittest.main()
