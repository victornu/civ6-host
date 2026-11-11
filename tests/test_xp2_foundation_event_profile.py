import unittest
import struct
import importlib
import sys
from unittest.mock import patch
from types import SimpleNamespace

from civ6_host.runtime.saved_load_profiles import XP2_CORE_SHA256
from civ6_host.runtime.foundation_event_profile import (PROJECT_KIND, PROJECT_SOURCE, event_profile,
                                                     source_dependencies)
from civ6_host.runtime.turn_unit_event_profile import event_profile as turn_profile
from civ6_host.runtime.configuration_profiles import XP1_CORE_SHA256


class XP2FoundationEventProfileTests(unittest.TestCase):
    def test_current_player_restored_record_passes_the_composed_fifo(self):
        import test_a0_family_service as shared
        from civ6_host.runtime.a0_family_source import family_profile
        from civ6_host.runtime import xp2_player_restored as restored
        from civ6_host.runtime.execution_images import _PROFILE

        self.profile = family_profile()
        _, deferred, _, owner, _, _, _ = shared.A0FamilyServiceTests.fixture(self, XP2_CORE_SHA256)
        deferred.core._civ6_host_execution_image = _PROFILE
        profile = event_profile(core_sha256=XP2_CORE_SHA256, execution_image=_PROFILE)
        owner.foundation_event_profile = owner._foundation_event_profile = profile
        owner.active_kind = restored.KIND
        selector = bytearray(shared.scalar(3, 0xd2022433))
        selector[4:8] = b'alue'
        fields = {restored.SELECTOR: bytes(selector), restored.PLAYER: shared.scalar(2, 2)}
        backend = SimpleNamespace(core=deferred.core)
        with patch('civ6_host.runtime.a0_foundation_events.require_borrow',
                   return_value=SimpleNamespace(owner=backend)):
            self.assertEqual(restored.dispatch(owner, fields), 0)
        record, = deferred.pending
        self.assertEqual(struct.unpack_from('<IIII', record), (96, 19, 1, 0))
        self.assertEqual(struct.unpack_from('<I', record, 72), (6,))
        self.assertEqual(struct.unpack_from('<III', record, 80), (1, 2, 0xd2022433))
        owner.active_kind = None
        self.assertEqual(deferred.drain(), 1)
        self.assertEqual(deferred.pending, [])
        self.assertEqual(deferred.consumed_count, 1)
        calls = [call for call in deferred.emit.call_args_list
                 if call.args and call.args[0] == 'native_deferred_empty_record_consumed']
        self.assertEqual(calls[-1].kwargs['event_name'], 'GameCoreEvent::PlayerRestored')

    def test_current_player_notification_preserves_player_and_boolean_branch(self):
        from civ6_host.runtime import xp2_player_can_construct_event as player
        from civ6_host.runtime.execution_images import _PROFILE
        from civ6_host.runtime.native.native_deferred_empty_profile import resolve_empty_receiver_row

        current = event_profile(core_sha256=XP2_CORE_SHA256, execution_image=_PROFILE)
        self.assertEqual(current.record_types_by_kind[player.KIND], frozenset((0x110, 0x111)))

        def scalar(tag, value):
            return struct.pack('<H6xI12x', tag, value)

        fields = {player.SELECTOR: scalar(3, 0), player.PLAYER: scalar(2, 2)}
        for active, record_type, name in ((0, 0x110, 'PlayerDestroyed'), (1, 0x111, 'PlayerRevived')):
            record = player.encode_record(7, fields | {player.AVAILABLE: scalar(1, active)})
            self.assertEqual(current.record_sizes[record_type], 96)
            row = resolve_empty_receiver_row(record_type, execution_image=_PROFILE)
            self.assertEqual(row['event_name'], 'GameCoreEvent::' + name)
            self.assertEqual(struct.unpack_from('<IIII', record), (96, record_type, 7, 0))
            self.assertEqual(record[80:], struct.pack('<IIII', 7, 2, 0, 0))
        with self.assertRaisesRegex(ValueError, 'boolean'):
            player.encode_record(7, fields | {player.AVAILABLE: scalar(1, 2)})
        with self.assertRaisesRegex(ValueError, 'selector'):
            player.encode_record(7, fields | {player.AVAILABLE: scalar(1, 1),
                                              player.SELECTOR: scalar(3, 1)})

    def test_current_building_removal_uses_building_receiver_and_holds_plot_through_enqueue(self):
        from contextlib import contextmanager
        from unittest.mock import Mock
        from civ6_host.runtime import xp2_building_removal as removal
        from civ6_host.runtime.a0_family_service import A0FamilyService
        from civ6_host.runtime.execution_images import _PROFILE
        from civ6_host.runtime.native.native_event_15c35863 import encode_scalar
        from civ6_host.runtime.native.native_deferred_empty_profile import (
            resolve_empty_receiver_row, validate_empty_profile_record)

        current = event_profile(core_sha256=XP2_CORE_SHA256, execution_image=_PROFILE)
        self.assertEqual(current.record_types_by_kind[removal.KIND], frozenset((0xa8,)))
        self.assertEqual(current.record_types_by_kind[0x037a1bee], frozenset((0xa7,)))
        self.assertEqual(resolve_empty_receiver_row(0xa7)['handler_va'], '0x1400d9d90')
        self.assertEqual(resolve_empty_receiver_row(0xa8, execution_image=_PROFILE)['handler_va'],
                         '0x1400d9530')

        position = struct.pack('<ii', 22, 12)
        raw_pointer = struct.pack('<H6xQII', 0, 123, 8, 0x21000001)
        fields = {removal.SELECTOR: encode_scalar(3, 0), removal.POSITION: raw_pointer,
                  removal.VALUE: encode_scalar(2, 17)}
        state = dict(observer_registered=False, state_pointer_nonnull=True, pre_hook=None,
                     post_hook=None, subscriber_count=0, state_flags=0)
        core = SimpleNamespace(_civ6_host_execution_image=_PROFILE)
        pending = []
        lifetime = []

        def read(pointer, size):
            self.assertEqual((pointer, size), (123, 8))
            return position

        @contextmanager
        def lease(passed_core, context, decoded, *, core_sha256, read):
            self.assertIs(passed_core, core)
            self.assertEqual(core_sha256, XP2_CORE_SHA256)
            self.assertEqual(decoded['position_bytes'], position)
            lifetime.append('acquire')
            yield dict(owner=2, city_id=15, district_id=16, flag148=1)
            self.assertEqual(len(pending), 1)
            lifetime.append('release')

        consumed = []
        deferred = SimpleNamespace(core=core, _consume_empty_record=lambda raw, seq, *,
            empty_receiver_state: consumed.append(validate_empty_profile_record(raw, **empty_receiver_state)))
        owner = SimpleNamespace(_check=Mock(), active_kind=removal.KIND, _sequence=6,
            core=core, context=13, _require_no_f391_reentry=Mock(),
            foundation_core_sha256=XP2_CORE_SHA256, ui_cache_callbacks_enabled=True,
            pending=pending, limit=1, empty_receiver_state=state, read=read,
            host_notification_counter=0, normalizer_transform_present=False,
            per_thread_hook_present=False, writer_metadata_callback_present=False,
            _enqueue=pending.append, emit=Mock(), deferred=deferred,
            handles_record=lambda kind: kind == 0xa8, policy_unlock_event_profile=None,
            bbg_trade_event_profile=None, climate_event_profile=None)
        with (patch('civ6_host.runtime.a0_foundation_events.require_borrow',
                    return_value=SimpleNamespace(owner=SimpleNamespace(core=core))),
              patch('civ6_host.runtime.xp2_building_removal.plot_snapshot', lease)):
            with self.assertRaisesRegex(ValueError, 'three witnessed fields'):
                removal.dispatch(owner, fields | {0xa1fbc372: encode_scalar(2, 1)})
            self.assertEqual(lifetime, [])
            self.assertEqual(removal.dispatch(owner, fields), 0)
        self.assertEqual(lifetime, ['acquire', 'release'])
        record, = pending
        self.assertEqual(struct.unpack_from('<IIII', record), (128, 0xa8, 7, 0))
        self.assertEqual(record[80:], struct.pack('<I4x8sHHIHHIB3xI8x',
            7, position, 2, 2, 15, 2, 3, 16, 1, 17))
        owner.active_kind = None
        A0FamilyService.consume(owner, record, 7)
        self.assertEqual(consumed[0]['handler_va'], '0x1400d9530')

    def test_current_city_transfer_preserves_descriptor_previous_owner_and_type(self):
        from civ6_host.runtime import xp2_city_occupation_event as occupation
        from civ6_host.runtime.execution_images import _PROFILE
        from civ6_host.runtime.native.native_deferred_empty_profile import resolve_empty_receiver_row
        from civ6_host.runtime.native.native_event_15c35863 import encode_blob_pointer, encode_scalar

        current = event_profile(core_sha256=XP2_CORE_SHA256, execution_image=_PROFILE)
        self.assertEqual(current.record_types_by_kind[occupation.KIND], frozenset((0x73,)))
        self.assertEqual(current.record_sizes[0x73], 112)
        self.assertEqual(resolve_empty_receiver_row(0x73, execution_image=_PROFILE), occupation.receiver_row())
        self.assertNotEqual(resolve_empty_receiver_row(0x73), occupation.receiver_row())
        descriptor = struct.pack('<HHI', 4, 2, 65536)
        fields = {
            occupation.SELECTOR: encode_scalar(3, 0),
            occupation.CITY: encode_blob_pointer(123),
            occupation.PRIOR_OWNER: encode_scalar(2, 14),
            occupation.TRANSFER: encode_scalar(2, 2),
        }

        def read(pointer, size):
            self.assertEqual((pointer, size), (123, 8))
            return descriptor

        record = occupation.encode_record(7, fields, read)
        self.assertEqual(struct.unpack_from('<IIII', record), (112, 0x73, 7, 0))
        self.assertEqual(record[80:], struct.pack('<I4x8sII8x', 7, descriptor, 14, 2))
        from civ6_host.runtime.a0_family_service import A0FamilyService
        from civ6_host.runtime.native.native_deferred_empty_profile import validate_empty_profile_record
        from unittest.mock import Mock

        state = dict(observer_registered=False, state_pointer_nonnull=True, pre_hook=None,
                     post_hook=None, subscriber_count=0, state_flags=0)
        observed = []
        deferred = SimpleNamespace(core=SimpleNamespace(_civ6_host_execution_image=_PROFILE),
            _consume_empty_record=lambda raw, seq, *, empty_receiver_state:
                observed.append((seq, validate_empty_profile_record(raw, **empty_receiver_state))))
        a0 = SimpleNamespace(_check=Mock(), active_kind=None, handles_record=lambda k: k == 0x73,
            policy_unlock_event_profile=None, bbg_trade_event_profile=None, climate_event_profile=None,
            empty_receiver_state=state, deferred=deferred)
        A0FamilyService.consume(a0, record, 7)
        self.assertEqual(observed[0][1]['handler_va'], '0x1400d8150')
        self.assertNotIn('execution_image', state)
        with self.assertRaises(ValueError):
            occupation.encode_record(7, {**fields, occupation.TRANSFER: encode_scalar(3, 2)}, read)
        with self.assertRaises(ValueError):
            occupation.encode_record(7, fields, lambda *_: struct.pack('<HHI', 4, 1, 65536))

    def test_common_exe_membership_is_separate_from_xp2_turn_notifications(self):
        foundation = event_profile(core_sha256=XP2_CORE_SHA256)
        turn = turn_profile(core_sha256=XP2_CORE_SHA256)
        self.assertEqual(len(foundation.record_types_by_kind), 20)
        self.assertEqual(len(foundation.record_sizes), 26)
        self.assertFalse(set(foundation.record_types_by_kind) & set(turn.record_types_by_kind))
        self.assertFalse(set(foundation.record_sizes) & set(turn.record_sizes))

    def test_xp2_dependency_closure_selects_xp2_facade_and_civilization(self):
        pins = source_dependencies(core_sha256=XP2_CORE_SHA256)
        project_path = PROJECT_SOURCE[0].replace('/', chr(92))
        self.assertEqual([sha for path, sha in pins.items() if path.endswith(project_path)],
                         [PROJECT_SOURCE[1]])
        self.assertTrue(any(path.endswith('xp2-turn-notifications-static\\source-profile-v1.json')
                            for path in pins))
        self.assertTrue(any(path.endswith('xp2-application-mirror\\source-profile-v1.json')
                            for path in pins))
        self.assertTrue(any(path.endswith('xp2-configuration-static\\xp2_configuration_source_v1.json')
                            for path in pins))

    def test_unknown_engine_fails_closed(self):
        with self.assertRaises(ValueError):
            event_profile(core_sha256='0' * 64)

    def test_xp2_foundation_enable_and_real_a0_dispatch_share_the_prepared_owner(self):
        from civ6_host.runtime import a0_foundation_events as foundation
        from test_extraction_found_unit_event import render_imported_module

        rendered_module, _ = render_imported_module()
        module_name = 'civ6_host.runtime.native.native_found_city_event'
        native_package = importlib.import_module('civ6_host.runtime.native')
        previous_module = sys.modules.get(module_name)
        previous_package_module = getattr(native_package, 'native_found_city_event', None)
        sys.modules[module_name] = rendered_module
        native_package.native_found_city_event = rendered_module
        import test_xp2_turn_notifications as turn_notifications
        from test_xp1_private_notifications import fixture as base_fixture
        from civ6_host.runtime import xp2_foundation_optional_source as optional_source
        from test_xp2_cache_publication import XP2CacheTests
        original_turn_enable = foundation.enable_turn_units
        original_cache_graph = XP2CacheTests.graph

        def cache_graph_with_optional_position(self):
            graph_parts = original_cache_graph(self)
            memory = graph_parts[0]
            from civ6_host.runtime import xp2_foundation_query_source, xp2_wmd_fallout_visibility
            from civ6_host.runtime import xp2_wonder_completion
            query = xp2_foundation_query_source.source()
            for body in query['functions'].values():
                for fragment in body['fragments']:
                    memory.put(memory.core_base + int(fragment['start_rva'], 16),
                               bytes.fromhex(fragment['raw_hex']))
            for table in query['tables'].values():
                for slot, rva in table['slots'].items():
                    memory.q(memory.core_base + int(table['vtable_rva'], 16) + int(slot, 16),
                             memory.core_base + int(rva, 16))
            for body in xp2_wmd_fallout_visibility.source()['bodies']['core'].values():
                for fragment in body.get('fragments') or (body,):
                    memory.put(memory.core_base + int(fragment['start_rva'], 16),
                               bytes.fromhex(fragment['raw_hex']))
            for body in xp2_wonder_completion.source()[1]['functions'].values():
                for fragment in body['fragments']:
                    memory.put(memory.core_base + int(fragment['start_rva'], 16),
                               bytes.fromhex(fragment['raw_hex']))
            target = optional_source.source()
            memory.put(memory.core_base + optional_source.TABLE_RVA + optional_source.SLOT,
                       (memory.core_base + optional_source.TARGET_RVA).to_bytes(8, 'little'))
            for fragment in target['function']['fragments']:
                memory.put(memory.core_base + int(fragment['start_rva'], 16),
                           bytes.fromhex(fragment['raw_hex']))
            return graph_parts

        def install_both(owner, backend):
            foundation.enable(owner, backend)
            return original_turn_enable(owner, backend)

        # The existing composed fixture supplies a real SavedContinuation,
        # LoadedCachePublication and XP2 source-backed memory. Install the
        # foundation family at the same prepared-stage seam as turn units.
        try:
            with patch.object(foundation, 'enable_turn_units', install_both), \
                    patch.object(XP2CacheTests, 'graph', cache_graph_with_optional_position):
                graph = turn_notifications.XP2ComposedNotifications().graph()
        finally:
            if previous_module is None:
                sys.modules.pop(module_name, None)
            else:
                sys.modules[module_name] = previous_module
            if previous_package_module is None:
                native_package.__dict__.pop('native_found_city_event', None)
            else:
                native_package.native_found_city_event = previous_package_module

        profile = graph.owner.foundation_event_profile
        self.assertIs(profile, graph.owner._foundation_event_profile)
        self.assertIs(graph.owner._foundation_backend, graph.backend)
        self.assertEqual(profile.record_types_by_kind[PROJECT_KIND], frozenset((96, 99, 100)))
        self.assertIn(490036867, profile.record_types_by_kind)
        self.assertEqual(graph.backend.load_abi.core_sha256, XP2_CORE_SHA256)

        scalar = base_fixture.scalar
        city_ptr = 0xA10000
        def descriptor(tag, pointer):
            return struct.pack('<H6xQII', tag, pointer, 8, 553648129)

        graph.memory.put(city_ptr, struct.pack('<HHI', 2, 0, 55))
        raw_fields = {
            594779970: descriptor(1024, city_ptr),
            2716180809: scalar(3, 0),
            3606901732: scalar(2, 42),
        }
        self.assertEqual(graph.owner.dispatch(490036867, raw_fields, 0), 0)
        self.assertEqual(len(graph.event.deferred.pending), 1)
        record = graph.event.deferred.pending[0]
        self.assertEqual(struct.unpack_from('<II', record), (128, 92))
        self.assertEqual(struct.unpack_from('<HHI', record, 88), (2, 2, 55))
        self.assertIsNone(graph.owner._foundation_borrow)

    def test_enable_keeps_base_and_foreign_load_abis_closed(self):
        from civ6_host.runtime.a0_foundation_events import enable

        for core_sha in ('d7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3',
                         '0' * 64):
            owner = SimpleNamespace(
                _check=lambda: None,
                arguments=SimpleNamespace(depth=0, host=object()),
                active_kind=None, pending=[], deferred=SimpleNamespace(_draining_empty_receivers=False,
                                                                         core=object(), context=7),
                host_notification_counter=0, host_metadata_counter=0,
                foundation_event_profile=None, read=lambda address, size: b'\0' * size)
            backend = SimpleNamespace(
                check_thread=lambda: None,
                load_abi=SimpleNamespace(core_sha256=core_sha), stage='prepared', prefix=None,
                host=owner.arguments.host, core=owner.deferred.core, context=7,
                _xp1_commands_requested=True)
            with self.assertRaises(ValueError):
                enable(owner, backend)
            self.assertIsNone(owner.foundation_event_profile)

    def test_xp2_found_unit_real_a0_dispatch_uses_its_selected_source_pin(self):
        import ctypes as C
        import struct
        import test_xp2_turn_notifications as turn_notifications
        from civ6_host.runtime import found_unit_event_profiles as query_profiles
        from civ6_host.runtime import xp2_turn_notification_source as turn_source
        from civ6_host.runtime import a0_found_unit_event as found_unit
        from civ6_host.runtime.native import native_found_city_event as codec
        from civ6_host.runtime.execution_images import known_path, select

        graph = turn_notifications.XP2ComposedNotifications().graph()
        image = select('xp2-gamecore-current-092abfbb',
            core_path=known_path('xp2-gamecore-current-092abfbb'))
        graph.owner.deferred.core._civ6_host_execution_image = image
        proof = query_profiles._xp2_source(execution_image=image)
        query_abi = query_profiles.query_abi(XP2_CORE_SHA256,
            execution_image=image)
        bodies = list(proof['unit']['bodies'].values())
        bodies.extend(proof['query_map']['bodies'].values())
        bodies.extend(proof['application']['bodies'][name] for name in ('constructor', 'delete'))
        for rva, raw in query_profiles._xp2_instruction_spans(bodies):
            graph.memory.put(graph.memory.core_base + rva, raw)
        for vtable, slots in query_abi.tables.values():
            for slot, target in slots.items():
                graph.memory.q(graph.memory.core_base + vtable + slot,
                               graph.memory.core_base + target)
        lookup_slot = query_abi.constants['CORE_PARAMETER_VTABLE'] + 0x60
        graph.memory.q(graph.memory.core_base + lookup_slot,
                       graph.memory.core_base + query_abi.constants['CORE_PARAMETER_LOOKUP'])

        found_unit.enable(graph.owner)
        identity_address = 0xA20000
        graph.memory.put(identity_address, struct.pack('<HHI', 1, 1, 9))
        scalar = turn_notifications.private_tests.fixture.scalar
        fields = {
            codec.SELECTOR_KEY: scalar(3, 0),
            codec.ENTITY_KEY: struct.pack('<H6xQII', 1024, identity_address, 8, 553648129),
        }
        objects = {name: 0x800000 + 0x1000 * index
                   for index, name in enumerate(turn_source.TABLES)}
        objects['outer'] = graph.backend.context
        calls = []

        def parameter_ctor(pointer):
            C.memmove(pointer, (graph.memory.core_base + query_abi.constants['CORE_PARAMETER_VTABLE']).to_bytes(8, 'little'), 8)
            return pointer

        buffers = {}
        create_buffer = C.create_string_buffer

        def tracked_buffer(*args):
            value = create_buffer(*args)
            buffers[C.addressof(value)] = value
            return value

        original_read = graph.owner.read

        def read_with_native_buffers(address, size):
            for pointer, value in buffers.items():
                if pointer <= address and address + size <= pointer + C.sizeof(value):
                    return C.string_at(address, size)
            return original_read(address, size)

        graph.owner.read = read_with_native_buffers

        targets = {
            **{rva: (table, slot) for table, (vtable, slots) in query_abi.tables.items()
               for slot, rva in slots.items()},
            **{query_abi.constants[name]: ('native', name) for name in (
                'CORE_PARAMETER_CTOR', 'CORE_PARAMETER_DTOR', 'CORE_PARAMETER_LOOKUP',
                'CORE_UNIT_A8', 'CORE_UNIT_B0')},
        }

        def factory(result, *arg_types):
            def bind(target):
                rva = target - graph.memory.core_base
                table, slot = targets[rva]
                def call(*args):
                    calls.append((table, slot, args))
                    if (table, slot) == ('outer', 0xB8): return objects['player']
                    if (table, slot) == ('player', 0x110): return objects['units']
                    if (table, slot) == ('units', 0x10): return objects['unit']
                    if (table, slot) == ('native', 'CORE_UNIT_A8'): return 0x1234
                    if (table, slot) == ('native', 'CORE_UNIT_B0'): return None
                    if (table, slot) == ('native', 'CORE_PARAMETER_CTOR'):
                        return parameter_ctor(args[0])
                    if (table, slot) == ('native', 'CORE_PARAMETER_LOOKUP'): return 0
                    if (table, slot) == ('native', 'CORE_PARAMETER_DTOR'): return None
                    if slot == 8 or (table, slot) == ('unit', 0x10):
                        return None
                    raise AssertionError(f'unexpected query facade call {(table, slot)}')
                return call
            return bind

        for selector, should_query in ((codec.SELECTOR, True), (0x15D11E18, False)):
            with self.subTest(selector=hex(selector)):
                fields[codec.SELECTOR_VALUE] = scalar(2, selector)
                before = len(calls)
                with patch.object(C, 'WINFUNCTYPE', factory), \
                        patch.object(C, 'create_string_buffer', side_effect=tracked_buffer):
                    self.assertEqual(graph.owner.dispatch(codec.EVENT_KIND, fields, None), 0)
                self.assertEqual(len(calls) > before, should_query)
                record = graph.owner.pending[-1]
                self.assertEqual(struct.unpack_from('<II', record), (128, 0x23))
                self.assertEqual(struct.unpack_from('<I', record, 96)[0], selector)
                self.assertEqual(struct.unpack_from('<I', record, 100)[0], 0x1234 if should_query else 0)
        self.assertEqual(len(graph.owner.pending), 2)
        self.assertTrue(any((table, slot) == ('outer', 0xB8) for table, slot, _ in calls))
        self.assertEqual(graph.owner.found_unit_event_profile.source_sha256,
                         query_profiles.XP2_MAP_SOURCE[1])
        self.assertFalse(graph.owner.quarantined)


if __name__ == '__main__':
    unittest.main()
