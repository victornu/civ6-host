"""Focused XP2 religion owner/codec guards; no native process is launched."""
from copy import deepcopy
from dataclasses import replace
from hashlib import sha256
import json
import struct
import unittest

from civ6_host.runtime import xp2_religious_chain_source as chain
from civ6_host.runtime import xp1_prophet_activation_source as activation_source
from civ6_host.runtime import xp1_religion_founding_source as founding_source
from civ6_host.runtime import xp1_religion_beliefs_source as beliefs_source
from civ6_host.runtime import xp1_religion_observation_source as observation_source
from civ6_host.runtime.a0_family_service import A0FamilyService
from civ6_host.runtime.execution_images import _PROFILE
from civ6_host.runtime.paths import resource_root
from civ6_host.runtime.xp1_saved_load_owner import SavedLoadOwner
from test_xp2_religious_chain_session import Fixture


class XP2ReligiousChainRuntimeTests(unittest.TestCase):
    def test_holy_city_script_guard_uses_its_own_lookup_in_live_lua_environment(self):
        from lupa.lua51 import LuaRuntime
        from civ6_host.runtime.native import native_religion_observation as reader

        lua = LuaRuntime(encoding=None)
        real_game_lookups = []
        lua.globals()[b'real_game_city_lookup'] = real_game_lookups.append
        lua.execute(b'CityManager={GetCity=function(raw) real_game_city_lookup(raw.id);return nil end}')
        result = lua.execute(reader.guard_case(core_sha256=reader.XP2_CORE_SHA256))
        self.assertEqual(result, b'native-religion-observation-guards-ok')
        self.assertEqual(real_game_lookups, [])

    def test_city_absent_callback_uses_real_owner_without_fifo_or_cache_mutation(self):
        fixture = Fixture(0)
        self.addCleanup(fixture.close)
        self.assertIs(type(fixture.owner), A0FamilyService)
        self.assertIs(type(fixture.saved), SavedLoadOwner)
        self.assertIs(fixture.arguments.consumer, fixture.owner)
        self.assertIs(fixture.owner.deferred, fixture.deferred)
        pointer = 0x78004000
        # The descriptor's input type is ignored by this native normalizer:
        # its complete output is a CITY descriptor, not a fabricated callback.
        fixture.memory.put(pointer, struct.pack('<HHI', 0, 1, 65536))
        fields = {
            0xa1e5a149: struct.pack('<H6xQ4xI', 3, 0, 0),
            0x23739f42: struct.pack('<H6xQII', 1024, pointer, 8, 0x21000001),
        }
        memory = dict(fixture.memory.memory)
        observation = deepcopy(fixture.token.observation)
        pending = list(fixture.deferred.pending)
        archives = list(fixture.token.transport.pending)
        machine = list(fixture.machine)
        counters = (fixture.owner.host_notification_counter, fixture.owner.host_metadata_counter,
                    fixture.owner._sequence, fixture.deferred.consumed_count)
        self.assertEqual(fixture.owner.dispatch(0x305c2e09, fields, 0), 0)
        event = next(payload for stage, payload in reversed(fixture.graph.event.emitted)
                     if stage == 'native_host_event_without_registered_callback')
        self.assertEqual(event['dispatch_kind'], '0x305c2e09')
        normalized = event['normalized_fields']
        self.assertEqual(normalized['normalized_descriptor_hex'], struct.pack('<HHI', 0, 2, 65536).hex())
        self.assertFalse(normalized['callback_registered'])
        self.assertFalse(normalized['callback_invoked'])
        self.assertEqual(normalized['queue_records_produced'], 0)
        self.assertFalse(normalized['gameplay_success_asserted'])
        self.assertEqual(fixture.memory.memory, memory)
        self.assertEqual(fixture.token.observation, observation)
        self.assertEqual(fixture.deferred.pending, pending)
        self.assertEqual(fixture.token.transport.pending, archives)
        self.assertEqual(fixture.machine, machine)
        self.assertEqual((fixture.owner.host_notification_counter, fixture.owner.host_metadata_counter,
                          fixture.owner._sequence, fixture.deferred.consumed_count), counters)
        self.assertIsNone(fixture.owner.active_kind)
        self.assertFalse(fixture.owner.quarantined)
        with self.assertRaisesRegex(ValueError, 'unknown family'):
            fixture.owner.dispatch(0xdec0adde, fields, 0)
        self.assertFalse(fixture.owner.quarantined)
        with self.assertRaisesRegex(ValueError, 'two complete typed fields'):
            fixture.owner.dispatch(0x305c2e09, {0xa1e5a149: fields[0xa1e5a149]}, 0)
        self.assertTrue(fixture.owner.quarantined)
        self.assertEqual(fixture.deferred.pending, pending)
        self.assertEqual(fixture.token.transport.pending, archives)
        self.assertEqual(fixture.memory.memory, memory)
        self.assertEqual(fixture.token.observation, observation)

    def test_player_archive_exact_two_parameter_map_and_typed_corruption_refusal(self):
        # These are retained native XP1 archives, independently pinned by the
        # XP2 ABI supplement. Their bytes do not claim an XP2 native execution.
        retained = chain._archive_source(chain.verify_source())['retained']['XP1_religious']
        path = resource_root() / retained['path']
        self.assertLess(path.stat().st_size, 64 * 1024**2)
        wanted = {row['line']: operation for operation, row in retained['matched_archives'].items()}
        digest, payloads = sha256(), {}
        with path.open('rb') as stream:
            for number, line in enumerate(stream, 1):
                digest.update(line)
                self.assertLess(len(line), 8 * 1024**2)
                if number in wanted:
                    event = json.loads(line.decode('utf-8'))
                    self.assertEqual(event['stage'], 'native_command_archive_queued')
                    self.assertEqual(event['bytes'], 68)
                    payloads[wanted[number]] = bytes.fromhex(event['archive_hex'])
        self.assertEqual(digest.hexdigest(), retained['sha256'])
        self.assertEqual(set(payloads), set(retained['matched_archives']))
        insert, exclusive = 0xac2fdc09, 0x97fea5c6
        for operation, choice_key in ((0xa4daffb5, 0x22a25b8b), (0xf8828e24, 0xa44b2907)):
            reference = retained['matched_archives'][hex(operation)]
            parameters = {int(key, 16): int(value, 16) for key, value in reference['parameters'].items()}
            payload = payloads[hex(operation)]
            self.assertEqual(len(payload), 68)
            self.assertEqual(sha256(payload).hexdigest(), reference['raw_sha256'])
            self.assertEqual(set(parameters), {choice_key, insert})
            self.assertEqual(parameters[insert], exclusive)
            self.assertIsNone(chain.verify_player_archive(payload, 0, operation, parameters))
            # Ordering is map transport, not a restriction on the two keys.
            reversed_payload = payload[:24] + payload[46:] + payload[24:46]
            self.assertIsNone(chain.verify_player_archive(reversed_payload, 0, operation, parameters))
            corrupt = [payload[:-1], payload + b'\0']
            for offset, fmt, value in ((0, '<I', 0), (4, '<I', 1), (20, '<I', 1),
                                       (28, '<H', 1), (30, '<H', 3), (32, '<B', 1),
                                       (42, '<I', 0), (46, '<I', struct.unpack_from('<I', payload, 24)[0])):
                bad = bytearray(payload)
                struct.pack_into(fmt, bad, offset, value)
                corrupt.append(bytes(bad))
            for bad in corrupt:
                with self.subTest(operation=operation, payload=bad.hex()), self.assertRaises(ValueError):
                    chain.verify_player_archive(bad, 0, operation, parameters)
            invalid_calls = (
                (bytearray(payload), 0, operation, parameters),
                (payload, False, operation, parameters),
                (payload, 0, True, parameters),
                (payload, 0, operation, {choice_key: True, insert: exclusive}),
                (payload, 0, operation, {choice_key: -1, insert: exclusive}),
                (payload, 0, operation, {choice_key: 0x100000000, insert: exclusive}),
                (payload, 0, operation, {choice_key: 0xffffffff, insert: 0}),
                (payload, 0, operation, {str(choice_key): 0xffffffff, insert: exclusive}),
            )
            for args in invalid_calls:
                with self.subTest(operation=operation, args=args[1:]), self.assertRaises(ValueError):
                    chain.verify_player_archive(*args)

    def test_all_four_source_guards_refuse_foreign_execution_identity(self):
        copied_profile = replace(_PROFILE)
        self.assertEqual(copied_profile, _PROFILE)
        self.assertIsNot(copied_profile, _PROFILE)
        for source in (activation_source, founding_source, beliefs_source, observation_source):
            for image in (object(), copied_profile):
                with self.subTest(source=source.__name__, image=type(image).__name__):
                    with self.assertRaisesRegex(ValueError, 'Unqualified saved religion execution image'):
                        source.require_actions(image=image)


if __name__ == '__main__':
    unittest.main()
