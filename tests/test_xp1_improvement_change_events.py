"""Real saved owner, existing plot/configuration readers and FIFO; machine fixtures only."""
import ctypes as C
import struct
import sys
import unittest

from test_xp1_improvement_visibility import Fixture as VisibilityFixture
from test_xp1_placement_events import LAB
from test_xp1_turn_a0 import scalar
from civ6_host.runtime import a0_improvement_changes as admission
from civ6_host.runtime import improvement_change_profile as profile
from civ6_host.runtime.native import native_event_30ae2a3d as improvement
from civ6_host.runtime.native import native_event_7b65ff2e as route


class Fixture(VisibilityFixture):
    def enable(self):
        super().enable()
        sys.path.insert(0, str(LAB / 'tools'))
        from extract_phase31_next_export import pefile
        pe = pefile.PE(profile.verify_source()['image']['path'], fast_load=True)
        old = self.owner.read
        def read(address, size):
            rva = address - self.memory.base
            if 0 <= rva and rva + size <= pe.OPTIONAL_HEADER.SizeOfImage:
                raw = pe.get_data(rva, size)
                if len(raw) == size:
                    return raw
            return old(address, size)
        self.owner.read = read
        try:
            admission.enable(self.owner, self.backend)
        finally:
            self.owner.read = old
            pe.close()

    def __init__(self):
        super().__init__()
        self.fail_query = None
        for i, name in enumerate(('game', 'position')):
            self.objects[name] = 0x79600000 + i * 0x1000
            self.memory.put(self.objects[name], struct.pack('<QQ',
                self.memory.base + self.abi.table(name), 0x79700000))

    def factory(self, result, *args):
        fallback = super().factory(result, *args)
        def bind(target):
            if callable(target):
                return fallback(target)
            for name in ('outer_game', 'release_game', 'position_service',
                         'release_position', 'position_value', 'position_flag'):
                if target == self.backend.core._handle + self.abi.rva(name):
                    return lambda *values: self.position_native(name, *values)
            return fallback(target)
        return bind

    def position_native(self, name, pointer, *args):
        self.calls.append((name, pointer, *args))
        if name == self.fail_query:
            raise RuntimeError('fixture position query failure')
        if name == 'outer_game':
            assert pointer == self.backend.context
            return self.acquire('game')
        if name == 'position_service':
            assert pointer == self.objects['game']
            return self.acquire('position')
        if name in ('release_game', 'release_position'):
            label = name.removeprefix('release_')
            assert pointer == self.objects[label] and self.live[label] > 0
            self.live[label] -= 1
            return None
        assert pointer == self.objects['position'] and len(args) == 1
        assert C.string_at(args[0], 8) == struct.pack('<ii', 3, 4)
        return 0x100000003 if name == 'position_value' else 1

    def native(self, name, pointer, *args):
        if name == 'service_player_type_hash' and args == (0,):
            assert pointer == self.objects['type_service'] and self.live['type_service'] > 0
            self.calls.append((name, pointer, *args))
            return 0x1776
        return super().native(name, pointer, *args)

    def improvement_native(self, name, pointer, *args):
        if name == self.fail_query:
            raise RuntimeError('fixture component query failure')
        return super().improvement_native(name, pointer, *args)

    def emit(self, stage, **details):
        if stage == 'native_deferred_host_event_enqueued' and details.get('dispatch_kind') in ('0x30ae2a3d', '0x7b65ff2e'):
            assert not any(self.live.values())
            self.calls.append(('change_enqueued', details['dispatch_kind']))
        return super().emit(stage, **details)

    def fields_for(self, kind):
        fields = {improvement.POSITION_KEY: self.make_blob(struct.pack('<ii', 3, 4), 0),
                  improvement.SELECTOR_KEY: scalar(3, 0xa5eea1c0)}
        if kind == route.EVENT_KIND:
            fields.update({route.VALUE_KEY: scalar(2, 11), route.TAIL_KEY: scalar(2, 12)})
        return fields


class ImprovementChangeTests(unittest.TestCase):
    def fixture(self):
        f = Fixture()
        self.addCleanup(f.close)
        return f

    def test_component_owner_selects_real_configuration_and_secondary_query(self):
        for owner in (0, -1):
            with self.subTest(component_owner=owner):
                f = self.fixture()
                f.component_owner = owner
                self.assertEqual(f.owner.dispatch(improvement.EVENT_KIND, f.fields_for(improvement.EVENT_KIND), 0), 0)
                record = f.deferred.pending[0]
                self.assertEqual(struct.unpack_from('<II', record), (144, 144))
                expected = (11, owner & 0xffffffff, 12,
                            0x1776 if owner == 0 else 0xffffffff,
                            f.civilization if owner == 0 else 0xffffffff,
                            0xffffffff, 35)
                self.assertEqual(struct.unpack_from('<IIIIIII', record, 104), expected)
                self.assertEqual(record[132:136], bytes((1, 1, 0, 1)))
                self.assertEqual(sum(row[0] == 'civilization' for row in f.calls), int(owner == 0))
                self.assertFalse(any(f.live.values()))
                self.assertIsNone(f.owner._foundation_borrow)
                self.assertEqual(f.deferred.drain(), 1)

    def test_route_reuses_nested_position_query_and_ordered_fifo(self):
        f = self.fixture()
        for kind in (improvement.EVENT_KIND, route.EVENT_KIND):
            self.assertEqual(f.owner.dispatch(kind, f.fields_for(kind), 0), 0)
        self.assertEqual([struct.unpack_from('<II', record) for record in f.deferred.pending], [(144, 144), (128, 153)])
        self.assertEqual(sum(row[0] == 'position_value' for row in f.calls), 1)
        self.assertEqual(sum(row[0] == 'position_flag' for row in f.calls), 1)
        self.assertFalse(any(f.live.values()))
        releases = [row[0] for row in f.calls if row[0] in ('release_position', 'release_game')]
        self.assertEqual(releases, ['release_position', 'release_game'])
        self.assertEqual(f.deferred.drain(), 2)

    def test_failed_native_query_releases_known_owners_without_enqueue(self):
        for kind, failure in ((improvement.EVENT_KIND, 'component18'), (route.EVENT_KIND, 'position_flag')):
            with self.subTest(failure=failure):
                f = self.fixture()
                f.fail_query = failure
                with self.assertRaisesRegex(RuntimeError, 'fixture .* query failure'):
                    f.owner.dispatch(kind, f.fields_for(kind), 0)
                self.assertTrue(f.owner.quarantined)
                self.assertFalse(any(f.live.values()))
                self.assertEqual(f.deferred.pending, [])
                self.assertIsNone(f.owner._foundation_borrow)

    def test_unqualified_notification_scopes_refuse_before_native_queries(self):
        for kind in (improvement.EVENT_KIND, route.EVENT_KIND):
            for n, m in ((1, 0), (0, 1)):
                with self.subTest(kind=kind, n=n, m=m):
                    f = self.fixture()
                    f.deferred.host_notification_counter = n
                    f.deferred.host_metadata_counter = m
                    before = list(f.calls)
                    with self.assertRaises(ValueError):
                        f.owner.dispatch(kind, f.fields_for(kind), 0)
                    self.assertEqual(f.calls, before)
                    self.assertEqual((f.deferred.host_notification_counter, f.deferred.host_metadata_counter), (n, m))
                    self.assertEqual(f.deferred.pending, [])


if __name__ == '__main__':
    unittest.main()
