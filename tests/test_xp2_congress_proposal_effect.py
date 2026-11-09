"""Real SavedLoad guards and pinned code; only native memory/calls are fixtures."""
from copy import deepcopy
import ctypes as C
from dataclasses import replace
import json
import struct
from types import SimpleNamespace as NS
import unittest

import pefile

from civ6_host.runtime import xp2_congress_proposal_effect as effects
from civ6_host.runtime.configuration_profiles import XP2_CORE_SHA256, _copy
from civ6_host.runtime.captured_session_profile import select
from civ6_host.runtime.lan_load import _LAN_MODE, _SIMULTANEOUS_PHASE
from test_xp2_espionage import SpySession


class Fixture(SpySession):
    mapped = None

    def __init__(self):
        super().__init__()
        self.base = 0x190000000  # Deliberately differs from the PE preferred base.
        if Fixture.mapped is None:
            pe = pefile.PE(str(self.image.path))
            pe.relocate_image(self.base)
            Fixture.mapped = pe.get_memory_mapped_image()
        self.memory, self.native_calls, self.native_reads = {}, [], []
        self.call_hook = self.read_hook = None
        self.lookup_override = None
        self.backend.core._handle = self.base
        self.backend.runtime = NS(read=self.read_memory, call=self.call)
        profile = select(XP2_CORE_SHA256)
        inputs = NS(profile=profile.candidate.profile, official_bundle=profile.candidate.reference)
        self.saved.inputs = self.backend.inputs = inputs
        self.backend.captured_bundle = NS(reference=profile.candidate.reference, inputs=inputs)
        self.saved.network_reference = dict(capture_manifest_sha256=profile.candidate.reference[1],
            state=dict(game_mode_u32=_LAN_MODE, turn_phase_u32=_SIMULTANEOUS_PHASE,
                       player_id=0, observer_id=0), major_player_ids=(0, 1), human_player_ids=(0,))
        self.saved.world_congress_diagnostic = True
        self.install_data(turn=17)
        self.activate()

    def install_data(self, *, turn):
        self.game, self.manager, self.player, self.vector = (0x50000000, 0x51000000, 0x52000000, 0x53000000)
        self.table, self.primary, self.secondary = (0x54000000, 0x55000000, 0x56000000)
        self.definitions = (0x57000000, 0x57000100)
        self.hashes = (0x90000011, 0xf0000011)
        self.put(self.base + 0xb8aa68, '<Q', self.game)
        self.put(self.game + 0xc0, '<i', turn)
        self.put(self.player + 0x2c8, '<i', turn-1)
        self.put(self.table, '<QQQQQ', self.primary, self.primary+16, 0,
                 self.secondary, self.secondary+16)
        self.put(self.primary, '<QQ', *self.definitions)
        self.put(self.secondary, '<QQ', *self.definitions)
        for index, (address, key) in enumerate(zip(self.definitions, self.hashes)):
            self.put(address + 0x14, '<iI', index, key)
        self.rows([(0, 2, 0), (1, 63, 1)])

    def put(self, address, shape, *values):
        raw = struct.pack(shape, *values)
        self.memory.update((address+i, v) for i, v in enumerate(raw))

    def rows(self, rows):
        self.put(self.manager + 0x168, '<QIII', self.vector, len(rows), 0, len(rows))
        for index, (sender, target, definition) in enumerate(rows):
            address = self.vector + index * 0x140
            self.put(address + 0x118, '<i', sender)
            if sender == 0:  # Foreign target/type memory deliberately unavailable.
                self.put(address + 0xc, '<i', target)
                self.put(address + 0x138, '<i', definition)

    def read_memory(self, address, size):
        self.native_reads.append((address, size))
        if self.read_hook is not None:
            replacement = self.read_hook(address, size)
            if replacement is not None:
                return replacement
        output = []
        for at in range(address, address+size):
            if at in self.memory:
                output.append(self.memory[at])
            elif 0 <= at-self.base < len(self.mapped):
                output.append(self.mapped[at-self.base])
            else:
                raise AssertionError('Unqualified fixture memory read: '+hex(at))
        return bytes(output)

    def call(self, address, result_type, arg_types, *args):
        rva = address - self.base
        self.native_calls.append((rva, args))
        if self.call_hook:
            self.call_hook(rva, args)
        assert result_type is C.c_void_p
        if rva == 0x3bd000:
            assert arg_types == () and args == ()
            return self.manager
        if rva == 0x26c770:
            assert arg_types == (C.c_int32,) and args == (0,)
            return self.player
        if rva == 0x7d08c0:
            assert arg_types == () and args == ()
            return self.table
        if rva == 0x2209a0:
            assert arg_types == (C.c_void_p, C.c_uint32) and args[0] == self.table
            if self.lookup_override is not None:
                return self.lookup_override
            key = args[1]
            if key < len(self.definitions):
                return self.definitions[key]
            return self.definitions[self.hashes.index(key)] if key in self.hashes else None
        raise AssertionError('Unknown fixture native call: '+hex(rva))

    def snapshot(self, keys=(0xf0000011,)):
        return effects.read(self.saved, type_keys=keys)

    def finish(self):
        self.rows([(0, 2, 0), (1, 60, 0), (0, 3, 1)])
        self.put(self.player + 0x2c8, '<i', 17)
        return self.snapshot()


def attach_memory(graph):
    """Add only native bytes/calls to an existing real CycleTests.graph owner.

    Caller retains its owner/reference/mode setup. Existing memory and all
    unrelated native calls are preserved; no reader or comparer is mocked.
    """
    f = object.__new__(Fixture)
    f.saved, f.backend, f.prefix, f.continuation = (
        graph.saved, graph.backend, graph.prefix, graph.continuation)
    f.image = graph.backend.core._civ6_host_execution_image
    f.base = graph.backend.core._handle
    f.memory, f.native_calls, f.native_reads = {}, [], []
    f.call_hook = f.read_hook = f.lookup_override = None
    original_call = getattr(graph.backend.runtime, 'call', None)
    pe = pefile.PE(str(f.image.path))
    for span in effects._spans(effects.source(execution_image=f.image)):
        rva = int(span['rva'], 16)
        graph.memory.put(f.base+rva, pe.get_data(rva, span['bytes']))
    def put(address, shape, *values):
        graph.memory.put(address, struct.pack(shape, *values))
    def call(address, result_type, arg_types, *args):
        if address-f.base in effects._CALLS:
            return f.call(address, result_type, arg_types, *args)
        if original_call is not None:
            return original_call(address, result_type, arg_types, *args)
        raise AssertionError('Unknown composed fixture native call')
    f.put = put
    f.install_data(turn=graph.continuation.observation['turn'])
    graph.backend.runtime.call = call
    return f


class ProposalEffectTests(unittest.TestCase):
    def fixture(self):
        result = Fixture()
        self.addCleanup(result.close)
        return result

    def test_source_header_abi_and_aslr_safe_live_bytes(self):
        f = self.fixture()
        proof = effects.source(execution_image=f.image)
        self.assertTrue(all(not s['dir64_relocations'] for s in effects._spans(proof)))
        f.snapshot()
        self.assertEqual(f.native_calls, [(0x3bd000, ()), (0x26c770, (0,)),
            (0x7d08c0, ()), (0x2209a0, (f.table, 0xf0000011))])
        for corrupt in ('schema', 'offset', 'abi', 'relocation'):
            changed = _copy(proof)
            if corrupt == 'schema': changed['schema'] += '.unknown'
            elif corrupt == 'offset': changed['correspondence']['tuple_layout']['target'] = '0x10'
            elif corrupt == 'abi': changed['minimal_private_read_option']['accessors'][0]['abi'] = 'void* getter(void*)'
            else: changed['functions']['definition_lookup']['spans'][0]['dir64_relocations'] = ['0x2209a0']
            with self.subTest(corrupt=corrupt), self.assertRaises(ValueError):
                effects._verify(changed)

    def test_exact_delta_and_own_only_projection_with_index_or_hash_lookup(self):
        f = self.fixture()
        before = f.snapshot((1, f.hashes[1]))
        self.assertEqual(before.resolved_types, ((1, 1), (f.hashes[1], 1)))
        self.assertEqual(before.own_rows, ((0, 2, 0),))
        f.rows([(0, 3, 1), (1, 60, 0), (0, 2, 0)])  # Multiset, not invented ordering.
        f.put(f.player + 0x2c8, '<i', 17)
        after = f.snapshot((1, f.hashes[1]))
        result = effects.compare(f.saved, before, after, selections=[dict(target=3, type_key=1)])
        self.assertTrue(result['own_state_matches'])
        self.assertEqual(result['looked_effect'], 'changed')
        self.assertFalse(result['transport_acknowledged'])
        self.assertFalse(result['congress_completion_claimed'])
        self.assertFalse(result['checkpoint_release_qualified'])
        self.assertNotIn('60', json.dumps(result))
        self.assertEqual(f.delivered, [])

    def test_close_idempotent_marker_is_not_a_new_write(self):
        f = self.fixture()
        f.put(f.player + 0x2c8, '<i', 17)
        before, after = f.snapshot(()), f.snapshot(())
        result = effects.compare(f.saved, before, after)
        self.assertTrue(result['own_state_matches'])
        self.assertEqual(result['looked_effect'], 'already_satisfied')
        self.assertNotIn(0x7d08c0, [rva for rva, _ in f.native_calls])

    def test_missing_extra_removed_or_duplicate_selection_is_unresolved(self):
        for rows in ([(0, 2, 0)], [(0, 3, 1)], [(0, 2, 0), (0, 3, 1), (0, 4, 0)],
                     [(0, 2, 0), (0, 3, 1), (0, 3, 1)]):
            with self.subTest(rows=rows):
                f = self.fixture(); before = f.snapshot()
                f.rows(rows); f.put(f.player + 0x2c8, '<i', 17)
                result = effects.compare(f.saved, before, f.snapshot(),
                    selections=[dict(target=3, type_key=f.hashes[1])])
                self.assertFalse(result['own_state_matches'])
                self.assertFalse(result['selection_effect_observed'])

    def test_missing_marker_never_infers_effect_from_tuple_or_delivery(self):
        f = self.fixture(); before = f.snapshot()
        f.rows([(0, 2, 0), (0, 3, 1)])
        result = effects.compare(f.saved, before, f.snapshot(),
            selections=[dict(target=3, type_key=f.hashes[1])])
        self.assertFalse(result['own_state_matches'])
        self.assertTrue(result['selection_effect_observed'])
        self.assertEqual(result['looked_effect'], 'not_observed')

    def test_foreign_owner_copied_or_mutated_snapshot_refuses(self):
        f = self.fixture(); other = self.fixture(); before = f.snapshot(); after = f.finish()
        for candidate in (other.snapshot(), replace(before)):
            with self.assertRaisesRegex(ValueError, 'foreign, mutated or stale'):
                effects.compare(f.saved, candidate, after)
        object.__setattr__(before, 'marker_turn', 17)
        with self.assertRaisesRegex(ValueError, 'foreign, mutated or stale'):
            effects.compare(f.saved, before, after)

    def test_changed_revision_turn_runtime_and_reference_refuse(self):
        for mutation in ('sequence', 'turn', 'runtime', 'observer'):
            with self.subTest(mutation=mutation):
                f = self.fixture(); before = f.snapshot(); after = f.finish()
                if mutation == 'sequence': f.continuation.sequence += 1
                elif mutation == 'turn': f.continuation.observation['turn'] += 1
                elif mutation == 'runtime': f.backend.runtime = NS(read=f.read_memory, call=f.call)
                else: f.saved.network_reference['state']['observer_id'] = 1
                with self.assertRaises(ValueError): effects.compare(f.saved, before, after)

    def test_live_code_changed_prevents_all_accessor_calls(self):
        f = self.fixture(); f.put(f.base + 0x2209a0, '<B', 0xcc)
        with self.assertRaisesRegex(ValueError, 'live source differs'): f.snapshot()
        self.assertEqual(f.native_calls, [])

    def test_unknown_call_and_arguments_refuse(self):
        f = self.fixture()
        for rva, args in ((0x3c0a00, ()), (0x26c770, ()), (0x3bd000, (0,))):
            with self.assertRaisesRegex(ValueError, 'Unknown Congress read accessor'):
                effects._call(f.backend.runtime, f.base, rva, *args)
        for keys in ((-1,), (True,), (0x100000000,), (1, 1)):
            with self.assertRaises(ValueError): f.snapshot(keys)
        self.assertEqual(f.native_calls, [])

    def test_native_bounds_null_and_incomplete_reads_refuse(self):
        for kind in ('count', 'capacity', 'overflow', 'null', 'short', 'game_turn'):
            with self.subTest(kind=kind):
                f = self.fixture()
                if kind == 'count': f.put(f.manager + 0x178, '<I', 3)
                elif kind == 'capacity': f.put(f.manager + 0x170, '<I', 4097)
                elif kind == 'overflow': f.put(f.manager + 0x168, '<Q', 0x7fffffffff00)
                elif kind == 'null': f.manager = 0
                elif kind == 'short': f.read_hook = lambda at, size: b'' if at == f.player+0x2c8 else None
                else: f.put(f.game + 0xc0, '<i', 18)
                with self.assertRaises(ValueError): f.snapshot()

    def test_definition_bounds_unknown_results_and_changed_type_refuse(self):
        for kind in ('reversed', 'oversize', 'null_row', 'unknown_return', 'missing_key', 'wrong_index'):
            with self.subTest(kind=kind):
                f = self.fixture()
                if kind == 'reversed': f.put(f.table+8, '<Q', f.primary-8)
                elif kind == 'oversize': f.put(f.table+8, '<Q', f.primary+4097*8)
                elif kind == 'null_row': f.put(f.primary, '<Q', 0)
                elif kind == 'unknown_return': f.lookup_override = f.definitions[0]
                elif kind == 'wrong_index': f.put(f.definitions[1]+0x14, '<i', -1)
                with self.assertRaises(ValueError):
                    f.snapshot((0x12345678,) if kind == 'missing_key' else (f.hashes[1],))

    def test_mutation_during_read_refuses_and_after_must_be_later(self):
        f = self.fixture()
        f.call_hook = lambda rva, args: setattr(f.continuation, 'sequence', 8) if rva == 0x2209a0 else None
        with self.assertRaisesRegex(ValueError, 'revision changed'): f.snapshot()
        f.call_hook = None
        before = f.snapshot()
        with self.assertRaisesRegex(ValueError, 'not ordered'): effects.compare(f.saved, before, before)


if __name__ == '__main__':
    unittest.main()
