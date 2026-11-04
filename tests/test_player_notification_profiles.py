"""Offline regressions of the shared Base/XP1 player-notification lease.

The injected call seam never executes native code. Passing these cases verifies
adapter behavior and ABI selection, not populated XP1 player state.
"""
from __future__ import annotations

import ast
import ctypes as C
import struct
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from civ6_host.runtime.configuration_profiles import BASE_CORE_SHA256, XP1_CORE_SHA256
from civ6_host.runtime.paths import resource_root
from civ6_host.runtime import player_notification_profiles as profiles
from civ6_host.runtime.native import native_player_notifications as notifications


def retained_base_tests():
    path = resource_root() / 'tests/test_native_player_notifications.py'
    tree = ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == 'civ6rl.native_player_notifications':
            node.module = 'civ6_host.runtime.native.native_player_notifications'
    namespace = {'__name__': '_retained_base_player_notification_tests', '__file__': str(path)}
    exec(compile(tree, str(path), 'exec'), namespace)
    return namespace['NativePlayerNotificationTests']


RetainedBasePlayerNotificationTests = retained_base_tests()


class NotificationFixture:
    base, manager, player, component = 0x180000000, 0x10000, 0x20000, 0x30000
    player_live, component_live = 0x40000, 0x50000

    def __init__(self, *, player_present=True, component_present=True, core_sha256=XP1_CORE_SHA256):
        self.core_sha256=core_sha256
        self.constants = profiles.notification_abi(core_sha256).constants
        a = self.constants
        self.memory, self.events = {}, []
        self.player_present, self.component_present = player_present, component_present
        for address, value in (
            (self.manager, self.base + a['PLAYER_MANAGER_VTABLE_RVA']),
            (self.player, self.base + a['PLAYER_VTABLE_RVA']),
            (self.component, self.base + a['COMPONENT_VTABLE_RVA']),
        ):
            self.put(address, value)
        for pointer, live in ((self.player, self.player_live), (self.component, self.component_live)):
            self.put(pointer + 8, live)
            self.put(pointer + 0x10, 0)
            self.put_bytes(pointer + 0x18, struct.pack('<I', 1) + b'\xCD' * 4)
        self.put(self.player_live + (0x560 if core_sha256==XP1_CORE_SHA256 else 0x780), self.component_live)
        for vtable, prefix in (
            ('PLAYER_MANAGER_VTABLE_RVA', 'PLAYER_MANAGER_GET_PLAYER'),
            ('PLAYER_VTABLE_RVA', 'PLAYER_GET_COMPONENT'),
            ('PLAYER_VTABLE_RVA', 'PLAYER_RELEASE'),
            ('COMPONENT_VTABLE_RVA', 'COMPONENT_GETTER_18'),
            ('COMPONENT_VTABLE_RVA', 'COMPONENT_GETTER_10'),
            ('COMPONENT_VTABLE_RVA', 'COMPONENT_RELEASE'),
        ):
            self.put(self.base + a[vtable] + a[prefix + '_SLOT'], self.base + a[prefix + '_RVA'])
        self.calls = {
            'get_player': self.get_player,
            'get_component': self.get_component,
            'getter_18': lambda this, out: self.getter('getter_18', this, out, 0x80000001),
            'getter_10': lambda this, out: self.getter('getter_10', this, out, 0xFFFFFFFF),
            'release_component': lambda this: self.events.append(('release_component', this)),
            'release_player': lambda this: self.events.append(('release_player', this)),
        }

    def put(self, address, value):
        self.put_bytes(address, struct.pack('<Q', value))

    def put_bytes(self, address, raw):
        self.memory.update((address + index, byte) for index, byte in enumerate(raw))

    def read(self, address, size):
        return bytes(self.memory[address + index] for index in range(size))

    def get_player(self, this, index):
        self.events.append(('get_player', this, index))
        return self.player if self.player_present else 0

    def get_component(self, this):
        self.events.append(('get_component', this))
        return self.component if self.component_present else 0

    def getter(self, name, this, out, value):
        self.events.append((name, this))
        C.cast(out, C.POINTER(C.c_uint32)).contents.value = value
        return C.cast(out, C.c_void_p).value

    def lease(self, index):
        return notifications.query_player_notification_values(self.base, self.manager, index,
            read=self.read, _calls=self.calls, core_sha256=self.core_sha256)


class PlayerNotificationProfileTests(unittest.TestCase):
    def test_explicit_abi_preserves_base_and_selects_xp1(self):
        base = profiles.notification_abi(BASE_CORE_SHA256).constants
        xp1 = profiles.notification_abi(XP1_CORE_SHA256).constants
        self.assertEqual(set(base), set(xp1))
        self.assertEqual(len(base), 15)
        for name, value in base.items():
            self.assertEqual(value, getattr(notifications, name), name)
        self.assertNotEqual(base['PLAYER_MANAGER_VTABLE_RVA'], xp1['PLAYER_MANAGER_VTABLE_RVA'])
        with self.assertRaises(TypeError):
            xp1['PLAYER_MANAGER_VTABLE_RVA'] = 0
        with self.assertRaises(ValueError):
            profiles.notification_abi('0' * 64)

    def test_static_source_pins_and_referenced_instruction_bodies(self):
        source = profiles.source()
        self.assertFalse(source['validation']['native_execution'])
        profiles.verify_pinned_files(profiles.source_pins())
        profiles.verify_extracted_sources(source['source_pins'].values())
        for name in source['profile']['live_body_sources']:
            with self.subTest(body=name):
                body, field = profiles.body(name)
                instructions = [i for fragment in body['fragments'] for i in fragment['instructions']]
                self.assertIn(field, ('va', 'rva'))
                self.assertTrue(instructions)
                self.assertTrue(all(i[field] and bytes.fromhex(i['bytes']) for i in instructions))

    def test_xp1_order_unsigned_outputs_consumer_then_reverse_releases(self):
        f = NotificationFixture()
        with f.lease(7) as values:
            self.assertEqual(values, {'getter_10_uint32': 0xFFFFFFFF, 'getter_18_uint32': 0x80000001})
            self.assertEqual([event[0] for event in f.events], ['get_player', 'get_component', 'getter_18', 'getter_10'])
            f.events.append(('consumer', dict(values)))
        self.assertEqual([event[0] for event in f.events],
            ['get_player', 'get_component', 'getter_18', 'getter_10', 'consumer', 'release_component', 'release_player'])

    def test_all_uint32_inputs_are_forwarded_without_invented_absence(self):
        for index in (0, 1, 63, 64, 65, 0x80000000, 0xFFFFFFFF):
            with self.subTest(index=index):
                f = NotificationFixture(player_present=True)
                result = notifications.get_native_player_notification_values(f.base, f.manager, index,
                    read=f.read, _calls=f.calls, core_sha256=XP1_CORE_SHA256)
                self.assertIsNotNone(result)
                self.assertEqual(f.events[0], ('get_player', f.manager, index))

    def test_actual_null_player_and_component_have_distinct_release_paths(self):
        f = NotificationFixture(player_present=False)
        with f.lease(0xFFFFFFFF) as values:
            self.assertIsNone(values)
        self.assertEqual(f.events, [('get_player', f.manager, 0xFFFFFFFF)])
        f = NotificationFixture(component_present=False)
        with f.lease(0) as values:
            self.assertIsNone(values)
            self.assertEqual([e[0] for e in f.events], ['get_player', 'get_component'])
        self.assertEqual([e[0] for e in f.events], ['get_player', 'get_component', 'release_player'])

    def test_invalid_player_input_refuses_before_calls(self):
        for index in (-1, 0x100000000, True, 1.5, None):
            with self.subTest(index=index):
                f = NotificationFixture()
                with self.assertRaises(ValueError):
                    with f.lease(index):
                        self.fail('Invalid input yielded')
                self.assertEqual(f.events, [])

    def test_bad_virtual_targets_never_dispatch_unverified_calls(self):
        cases = (
            ('PLAYER_MANAGER_VTABLE_RVA', 'PLAYER_MANAGER_GET_PLAYER', []),
            ('PLAYER_VTABLE_RVA', 'PLAYER_RELEASE', ['get_player']),
            ('PLAYER_VTABLE_RVA', 'PLAYER_GET_COMPONENT', ['get_player']),
            ('COMPONENT_VTABLE_RVA', 'COMPONENT_RELEASE', ['get_player', 'get_component', 'release_player']),
            ('COMPONENT_VTABLE_RVA', 'COMPONENT_GETTER_18', ['get_player', 'get_component', 'release_player']),
            ('COMPONENT_VTABLE_RVA', 'COMPONENT_GETTER_10', ['get_player', 'get_component', 'release_player']),
        )
        for vtable, prefix, expected in cases:
            with self.subTest(prefix=prefix):
                f = NotificationFixture()
                f.put(f.base + f.constants[vtable] + f.constants[prefix + '_SLOT'], 0xDEADBEEF)
                with self.assertRaisesRegex(ValueError, 'vtable slot'):
                    with f.lease(1):
                        self.fail('Unverified slot yielded')
                self.assertEqual([e[0] for e in f.events], expected)

    def test_getter_output_pointer_failures_release_acquired_interfaces(self):
        for name, before in (('getter_18', ['get_player', 'get_component']),
                             ('getter_10', ['get_player', 'get_component', 'getter_18'])):
            with self.subTest(name=name):
                f = NotificationFixture()
                def wrong_pointer(this, out):
                    f.events.append(('wrong_pointer', this))
                    return 0
                f.calls[name] = wrong_pointer
                with self.assertRaisesRegex(RuntimeError, 'output pointer'):
                    with f.lease(2):
                        self.fail('Invalid getter result yielded')
                self.assertEqual([e[0] for e in f.events], before + ['wrong_pointer', 'release_component', 'release_player'])

    def test_consumer_exception_releases_once_in_reverse_order(self):
        f = NotificationFixture()
        with self.assertRaisesRegex(RuntimeError, 'consumer failed'):
            with f.lease(2):
                f.events.append(('consumer',))
                raise RuntimeError('consumer failed')
        self.assertEqual([e[0] for e in f.events][-3:], ['consumer', 'release_component', 'release_player'])

    def test_null_or_mismatched_component_owner_refuses_before_getters(self):
        for component_live, owner_live in ((0, 0), (0, 0x50000), (0x50000, 0), (0x50000, 0x50008)):
            with self.subTest(component_live=component_live, owner_live=owner_live):
                f = NotificationFixture()
                f.put(f.component + 8, component_live)
                f.put(f.player_live + 0x560, owner_live)
                with self.assertRaises((RuntimeError, ValueError)):
                    with f.lease(1):
                        self.fail('Invalid component owner yielded')
                self.assertEqual([e[0] for e in f.events],
                    ['get_player', 'get_component', 'release_component', 'release_player'])

    def test_invalid_player_branch_or_reference_count_releases_before_component_lookup(self):
        for offset, raw in ((8, struct.pack('<Q', 0)), (0x10, struct.pack('<Q', 0x99000)),
                            (0x18, struct.pack('<I', 2))):
            with self.subTest(offset=offset):
                f = NotificationFixture()
                f.put_bytes(f.player + offset, raw)
                with self.assertRaises((RuntimeError, ValueError)):
                    with f.lease(1):
                        self.fail('Invalid player wrapper yielded')
                self.assertEqual([e[0] for e in f.events], ['get_player', 'release_player'])

    def test_native_call_factory_uses_xp1_targets_with_original_ctypes_signatures(self):
        f = NotificationFixture()
        created = []
        def factory(restype, *argtypes):
            def bind(address):
                created.append((address, restype, argtypes))
                return ('mock_function', address)
            return bind
        with patch.object(notifications.C, 'WINFUNCTYPE', side_effect=factory):
            calls = notifications._native_calls(f.base, core_sha256=XP1_CORE_SHA256)
        expected = (
            ('get_player', 'PLAYER_MANAGER_GET_PLAYER_RVA', C.c_void_p, (C.c_void_p, C.c_uint32)),
            ('get_component', 'PLAYER_GET_COMPONENT_RVA', C.c_void_p, (C.c_void_p,)),
            ('getter_18', 'COMPONENT_GETTER_18_RVA', C.c_void_p, (C.c_void_p, C.POINTER(C.c_uint32))),
            ('getter_10', 'COMPONENT_GETTER_10_RVA', C.c_void_p, (C.c_void_p, C.POINTER(C.c_uint32))),
            ('release_component', 'COMPONENT_RELEASE_RVA', None, (C.c_void_p,)),
            ('release_player', 'PLAYER_RELEASE_RVA', None, (C.c_void_p,)),
        )
        self.assertEqual(created, [(f.base + f.constants[key], restype, args) for _, key, restype, args in expected])
        self.assertEqual(calls, {name: ('mock_function', f.base + f.constants[key]) for name, key, _, _ in expected})

    def test_base_shared_dispatch_delegates_original_arguments_without_extra_policy(self):
        from civ6_host.runtime.native.native_host_events import SharedHostEventDispatch
        owner = SimpleNamespace(base=0x180000000, context=0x9000)
        expected = object()
        with patch.object(notifications, 'query_player_notification_values', return_value=expected) as query:
            result = SharedHostEventDispatch._query_player_notification_values(owner, 0xFFFFFFFF)
        self.assertIs(result, expected)
        query.assert_called_once_with(owner.base, owner.context, 0xFFFFFFFF)


if __name__ == '__main__':
    unittest.main()
