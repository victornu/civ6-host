"""Selected XP2 provider queries; memory/native calls are fixture boundaries."""
import ctypes as C
import struct
from types import SimpleNamespace as NS
import unittest

from civ6_host.runtime import xp2_world_configuration as config
from civ6_host.runtime.configuration_profiles import XP2_CORE_SHA256, configuration_abi
from civ6_host.runtime.native.native_game_configuration import game_configuration_hash


class Fixture:
    def __init__(self, *, multiplayer=True):
        self.source = config.verify_source()
        self.base = 0x50000000
        self.memory, self.calls, self.events = {}, [], []
        self.cursor = 0x20000000
        self.root, self.player = 0x10000000, 0x10000100
        self.state = dict(normalized=self.root, players={1: self.player})
        self.snapshots, self.context_checks, self.changed = 0, [], False
        for fragment in self.source['getter_body']['fragments']:
            for ins in fragment['instructions']:
                self.put(self.base + int(ins['va'], 16) - 0x180000000, bytes.fromhex(ins['bytes']))
        table = self.base + self.source['vtable_rva']
        for pointer in (self.root, self.player):
            self.put(pointer, struct.pack('<Q', table))
        self.put(table + self.source['getter_slot'], struct.pack('<Q', self.base + self.source['getter_rva']))
        self.values = {}
        self.set_int(self.root, 'GAME_MODE', 0 if multiplayer else config.shared._SINGLE_PLAYER_HASH)
        self.set_int(self.player, 'SLOT_STATUS', 3)
        self.set_text(self.player, 'CIVILIZATION_SHORT_DESCRIPTION', 'Rome')
        self.set_text(self.player, 'CIVILIZATION_TYPE_NAME', 'CIVILIZATION_ROME')
        self.set_text(self.player, 'NICK_NAME', 'Joueur humain')
        self.set_int(self.player, 'CIVILIZATION_LEVEL_TYPE_ID', 7)
        app = NS(_configuration_abi=configuration_abi(XP2_CORE_SHA256),
                 require_context=self.require_context, snapshot=self.snapshot)
        self.backend = NS(check_thread=lambda: None, load_abi=NS(core_sha256=XP2_CORE_SHA256),
            poisoned=False, destroyed=False, owner=app, core=NS(_handle=self.base), context=0x1234,
            runtime=NS(read=self.read, call=self.call), emit=lambda stage, **data: self.events.append((stage, data)))

    def put(self, address, data):
        self.memory.update((address + i, byte) for i, byte in enumerate(data))

    def read(self, address, size):
        return bytes(self.memory[address + i] for i in range(size))

    def allocate(self, data):
        address = self.cursor
        self.cursor += len(data) + 32
        self.put(address, data)
        return address

    def set_int(self, provider, key, value):
        raw = bytearray(24)
        struct.pack_into('<H', raw, 0, 3)
        struct.pack_into('<I', raw, 8, value)
        self.values[provider, game_configuration_hash(key)] = self.allocate(raw)

    def set_text(self, provider, key, value):
        text = self.allocate(value.encode('utf-8') + b'\0')
        raw = bytearray(24)
        struct.pack_into('<H', raw, 0, 5)
        struct.pack_into('<Q', raw, 8, text)
        struct.pack_into('<I', raw, 20, 1 << 29)
        self.values[provider, game_configuration_hash(key)] = self.allocate(raw)

    def require_context(self, base, context):
        assert (base, context) == (self.base, 0x1234)
        self.context_checks.append((base, context))

    def snapshot(self):
        self.snapshots += 1
        return dict(self.state, changed=True) if self.changed and self.snapshots > 1 else self.state.copy()

    def call(self, address, result_type, arg_types, receiver, key):
        assert address == self.base + self.source['getter_rva']
        assert result_type is C.c_void_p and arg_types == (C.c_uint32,)
        self.calls.append((receiver, key))
        return self.values[receiver, key]


class WorldConfigurationTests(unittest.TestCase):
    def test_selected_exe_and_provider_sources_and_real_owned_query_composition(self):
        f = Fixture()
        self.assertEqual(f.source['getter_slot'], 0x68)
        # These targets originate in the retained XP2 provider/executable
        # receipts, independent from the fixture's arbitrary memory addresses.
        self.assertEqual(f.source['getter_rva'], 0x99f680)
        self.assertEqual(f.source['vtable_rva'], 0xabf080)
        self.assertGreater(len(config.source_dependencies()), 1)
        before = f.memory.copy()
        result = config.read(f.backend, [1])
        self.assertEqual(result, dict(is_any_multiplayer=True, players={1: dict(
            short_description='Rome', civilization_type_name='CIVILIZATION_ROME',
            is_human=True, player_name='Joueur humain', level_type_id=7)}))
        self.assertEqual(f.memory, before)
        self.assertEqual(len(f.context_checks), 2)
        self.assertEqual(len(f.calls), 6)
        self.assertIn(b'GetPlayerName', config.lua_bindings(result))
        self.assertFalse(f.events[-1][1]['native_configuration_written'])
        self.assertFalse(f.events[-1][1]['native_war_confirmation_qualified'])

    def test_nickname_is_not_read_for_single_player_or_ai(self):
        for multiplayer, human in ((False, True), (True, False)):
            with self.subTest(multiplayer=multiplayer, human=human):
                f = Fixture(multiplayer=multiplayer)
                if not human:
                    f.set_int(f.player, 'SLOT_STATUS', 1)
                key = game_configuration_hash('NICK_NAME')
                del f.values[f.player, key]
                result = config.read(f.backend, [1])
                self.assertIsNone(result['players'][1]['player_name'])
                self.assertNotIn((f.player, key), f.calls)
                self.assertIn(b'GetPlayerName was not read', config.lua_bindings(result))

    def test_wrong_provider_or_method_is_refused_before_native_call(self):
        for change in ('provider', 'method', 'code'):
            with self.subTest(change=change):
                f = Fixture()
                if change == 'provider':
                    f.put(f.root, struct.pack('<Q', 0xDEADBEEF))
                elif change == 'method':
                    f.put(f.base + f.source['vtable_rva'] + 0x68, struct.pack('<Q', f.base + 0x745dc0))
                else:
                    ins = f.source['getter_body']['fragments'][0]['instructions'][0]
                    f.put(f.base + int(ins['va'], 16) - 0x180000000, b'\xcc')
                with self.assertRaises(ValueError):
                    config.read(f.backend, [1])
                self.assertFalse(f.calls)

    def test_changed_snapshot_foreign_profile_and_invalid_player_ids_refused(self):
        f = Fixture()
        f.changed = True
        with self.assertRaisesRegex(RuntimeError, 'provider changed'):
            config.read(f.backend, [1])
        f = Fixture()
        f.backend.load_abi.core_sha256 = 'unknown'
        with self.assertRaises(ValueError):
            config.read(f.backend, [1])
        self.assertFalse(f.calls)
        for ids in ([], [True], [1, 1], [64], None):
            with self.subTest(ids=ids), self.assertRaises(ValueError):
                config.read(Fixture().backend, ids)


if __name__ == '__main__':
    unittest.main()
