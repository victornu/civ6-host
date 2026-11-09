"""Congress query composition with only native memory/calls replaced.

The real configuration readers, lexical serializer, namespace adapter, Lua
reader and parser run together. Neither configuration global is preinstalled.
"""
import ctypes as C
import hashlib
import struct
from types import SimpleNamespace as NS
import unittest

import pefile
from lupa.lua51 import LuaRuntime

from civ6_host.runtime import xp2_congress_configuration as environment
from civ6_host.runtime import xp2_world_congress_source as congress_source
from civ6_host.runtime.execution_images import known_path, select
from civ6_host.runtime.native import native_saved_world_congress as native
from civ6_host.runtime.native.native_game_configuration import game_configuration_hash
from civ6_host.runtime.native.native_script_namespaces import ScriptNamespaces
from test_xp2_world_configuration import Fixture as ConfigurationFixture

PROFILE = 'xp2-gamecore-current-092abfbb'
IMAGE = select(PROFILE, core_path=known_path(PROFILE))

UI_NATIVE = r'''
segment=0;local known={[7]=true}
Game={GetLocalPlayer=function()return 1 end,GetLocalObserver=function()return 1 end,
 GetCurrentGameTurn=function()return 61 end,GetCurrentTurnSegment=function()return segment end,
 GetEras=function()return {GetCurrentEra=function()return 3 end}end}
Players={[1]={IsTurnActive=function()return true end,GetFavor=function()return 100 end,
 GetDiplomacy=function()return {HasMet=function(_,id)return known[id]==true end}end}}
GameInfo={GameCapabilities={CAPABILITY_WORLD_CONGRESS={}},ProposalTypes={A={Sort=1}},
 Resolutions={R={ResolutionType='R',Hash=13,Name='Resolution',Effect1Description='A',Effect2Description='B'}},
 VotingBlockers={},ProposalBlockers={}}
local p={Type=9,TypeName='PROP',Sender=8,Target=7,Name='Proposal',Description='Description'}
local costs={[0]=0,[1]=10,MaxVotes=2}
Game.GetWorldCongress=function()return {
 IsInSession=function()return segment==1 or segment==2 end,
 GetMeetingStatus=function()return {TurnsLeft=3,Percentage=42}end,
 GetVotesandFavorCost=function()return costs end,
 GetResolutions=function()return {{Type='R',TargetType='PlayerType',PossibleTargets={'1','7','8'}}}end,
 GetProposals=function()return {Proposals={A={FavorCost=costs,ProposalsOfType={p}}}}end,
 GetEmergencies=function()return {Proposals={A={FavorCost=20,ProposalsOfType={p}}}}end}end
'''


class Fixture(ConfigurationFixture):
    def __init__(self):
        super().__init__()
        self.backend.core._civ6_host_execution_image = IMAGE
        self.proof = environment.source(execution_image=IMAGE)
        lookup = self.proof['spans']['nullable_lookup']
        self.put(self.base + int(lookup['start_rva'], 16), bytes.fromhex(lookup['raw_hex']))
        self.put(self.base + self.source['vtable_rva'] + 0x58, struct.pack('<Q', self.base + 0x99f570))
        self.sentinel = self.allocate(bytes(24))
        self.foreign = 0x10000200
        self.state['players'][7] = self.foreign
        self.put(self.foreign, struct.pack('<Q', self.base + self.source['vtable_rva']))
        self.set_int(self.root, 'GAME_PAUSED', 0)
        self.set_text(self.player, 'LEADER_NAME', '')
        self.set_text(self.foreign, 'LEADER_NAME', 'Known leader')
        self.lua = LuaRuntime(unpack_returned_tuples=True)
        self.lua.execute(UI_NATIVE)
        self.lua.globals().PlayerOperations = self.lua.table_from(congress_source.enum_values())
        child, host = object(), object()
        self.namespaces, self.chunks = [], []
        registry = NS(root=0x55, _check=lambda: None,
                      validate=lambda item: 0x66 if item is child else self.fail_child(),
                      _status=lambda status, label: self.check_status(status))
        class NativeNamespaceCall:
            def __call__(_, root, pointer, namespace):
                assert (root, pointer) == (0x55, 0x66)
                self.namespaces.append(namespace)
                if namespace == 2:
                    self.lua.execute('GlobalParameters={WORLD_CONGRESS_INITIAL_ERA=2}')
                elif namespace == 4:
                    self.lua.execute("DB={MakeHash=function(key)return ({TURNSEG_WORLDCONGRESS_1=1,TURNSEG_WORLDCONGRESS_2=2,TURNSEG_WORLDCONGRESS_RESOLUTION=3})[key]end}")
                elif namespace == 5:
                    self.lua.execute('Locale={Lookup=function(value,...)return value end}')
                else:
                    raise AssertionError('Unexpected namespace')
                return 0
        namespaces = ScriptNamespaces(registry, NS(LAB_NamespaceRegister=NativeNamespaceCall()))
        # This is the existing UI bootstrap's Locale namespace and the retained
        # length bridge, before the new Congress reader is called.
        namespaces.register(child, 'Locale')
        script = NS(registry=registry, namespaces=namespaces, evaluate_text=self.evaluate,
                    database_bound=True, service_owner=host, shared_dependency_profile=object(), locale_bound=True)
        self.prefix = NS(runtime=script, ui_child=child, backend=self.backend, core=self.backend.core,
                         host=host, closed=False, quarantined=False, length_locale_child=child)
        self.backend.prefix, self.backend.host = self.prefix, host
        # Native memory/calls and script-runtime ownership are distinct objects.
        assert self.backend.runtime is not script

    @staticmethod
    def fail_child():
        raise ValueError('Foreign native child')

    @staticmethod
    def check_status(status):
        if status != 0:
            raise RuntimeError('Native namespace refused')

    def call(self, address, result_type, arg_types, receiver, key):
        assert address in (self.base + 0x99f570, self.base + 0x99f680)
        assert result_type is C.c_void_p and arg_types == (C.c_uint32,)
        self.calls.append((receiver, key, address))
        default = None if address == self.base + 0x99f570 else self.sentinel
        return self.values.get((receiver, key), default)

    def evaluate(self, child, source, label, *, capacity):
        assert child is self.prefix.ui_child
        self.chunks.append(label)
        raw = self.lua.execute(source.decode()).encode()
        assert len(raw) < capacity
        return raw

    def query(self):
        return native.query(self.prefix, 1, 61, 3, backend=self.backend)


class CongressEnvironmentTests(unittest.TestCase):
    def test_real_composition_supplies_all_external_globals_across_four_phases(self):
        f = Fixture()
        self.assertIsNone(f.lua.globals().PlayerConfigurations)
        self.assertIsNone(f.lua.globals().GameConfiguration)
        self.assertIsNone(f.lua.globals().GlobalParameters)
        self.assertIsNone(f.lua.globals().DB)
        for segment, stage in enumerate(('ordinary', 'regular', 'special', 'resolving')):
            f.lua.globals().segment = segment
            value = f.query()['public']
            self.assertEqual(value['stage'], stage)
            self.assertTrue(value['local_alive'])  # Official nullable default.
            self.assertFalse(value['paused'])
            self.assertEqual(value['current_favor'], 100)
            if stage == 'ordinary':
                self.assertEqual(value['proposals'][0]['target'], dict(player_id=7, label='Known leader'))
                self.assertEqual(value['proposals'][0]['sender']['label'], 'LOC_DIPLOPANEL_UNMET_PLAYER')
            if stage == 'regular':
                self.assertEqual([r['label'] for r in value['resolutions'][0]['targets']],
                                 ['Rome', 'Known leader', 'LOC_DIPLOPANEL_UNMET_PLAYER'])
        self.assertEqual(f.namespaces, [5, 4, 2])  # Native attach once per owner/child.
        self.assertIsNone(f.lua.globals().PlayerConfigurations)  # Lexical, no global replacement.
        self.assertIsNone(f.lua.globals().GameConfiguration)
        self.assertEqual(len(f.chunks), 8)
        self.assertEqual({receiver for receiver, _, _ in f.calls}, {f.root, f.player, f.foreign})
        self.assertIn((f.player, game_configuration_hash('IS_ALIVE'), f.base + 0x99f570), f.calls)
        self.assertIn((f.root, game_configuration_hash('GAME_PAUSED'), f.base + 0x99f680), f.calls)
        self.assertNotIn((f.foreign, game_configuration_hash('IS_ALIVE'), f.base + 0x99f570), f.calls)

    def test_getter_defaults_are_exact_not_substituted_data(self):
        f = Fixture()
        f.set_int(f.player, 'IS_ALIVE', 0)
        f.set_int(f.root, 'GAME_PAUSED', 1)
        f.set_text(f.player, 'LEADER_NAME', 'Primary name')
        result = environment.read(f.backend, [1], local_player_id=1)
        self.assertEqual(result['players'][1], dict(leader_name='Primary name', alive=False))
        self.assertTrue(result['paused'])
        self.assertNotIn((f.player, game_configuration_hash('CIVILIZATION_SHORT_DESCRIPTION'), f.base + 0x99f680), f.calls)
        f.set_text(f.player, 'LEADER_NAME', '')
        del f.values[f.player, game_configuration_hash('CIVILIZATION_SHORT_DESCRIPTION')]
        self.assertEqual(environment.read(f.backend, [1], local_player_id=1)['players'][1]['leader_name'], '')

    def test_alive_uses_source_numeric_mask_and_low_dword(self):
        self.assertTrue(environment.alive(None))
        for tag in range(23):
            raw = bytearray(24);struct.pack_into('<H', raw, 0, tag);struct.pack_into('<I', raw, 8, 1)
            self.assertEqual(environment.alive(bytes(raw)), tag in (1, 2, 3, 5, 20, 21))
            struct.pack_into('<I', raw, 20, 1 << 29)
            self.assertFalse(environment.alive(bytes(raw)))
        raw = bytearray(24);struct.pack_into('<H', raw, 0, 21);struct.pack_into('<Q', raw, 8, 1 << 32)
        self.assertFalse(environment.alive(bytes(raw)))

    def test_new_lookup_target_code_and_foreign_provider_fail_closed(self):
        for kind in ('target', 'code', 'provider'):
            f = Fixture()
            address, raw = {
                'target': (f.base + f.source['vtable_rva'] + 0x58, struct.pack('<Q', f.base + 0x99f680)),
                'code': (f.base + 0x99f570, b'\xcc'),
                'provider': (f.player, struct.pack('<Q', 0x1234)),
            }[kind]
            f.put(address, raw)
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                environment.read(f.backend, [1], local_player_id=1)

    def test_owner_rebinding_and_provider_change_are_refused(self):
        f = Fixture();f.prefix.host = object()
        with self.assertRaisesRegex(ValueError, 'retained'):
            f.query()
        self.assertFalse(f.chunks)
        f = Fixture();f.query();f.prefix.ui_child = object()
        with self.assertRaises(ValueError):
            f.query()
        f = Fixture();f.changed = True
        with self.assertRaisesRegex(RuntimeError, 'provider changed'):
            environment.read(f.backend, [1], local_player_id=1)

    def test_configuration_identity_cannot_silently_redact_new_contact(self):
        f = Fixture()
        original = f.evaluate
        def evaluate(child, chunk, label, *, capacity):
            if label == b'@player_world_congress':
                f.lua.execute('Players[1].GetDiplomacy=function()return {HasMet=function(_,id)return id==7 or id==8 end}end')
            return original(child, chunk, label, capacity=capacity)
        f.prefix.runtime.evaluate_text = evaluate
        with self.assertRaisesRegex(Exception, 'visible configuration was not read'):
            f.query()

    def test_source_dependencies_and_actual_pe_callers_are_independent_of_fixture(self):
        proof = environment.source(execution_image=IMAGE)
        self.assertGreater(len(environment.source_dependencies(execution_image=IMAGE)), 4)
        for which in ('core', 'exe'):
            path = proof['images'][which]['path']
            with open(path, 'rb') as stream:
                raw = stream.read()
            self.assertEqual(hashlib.sha256(raw).hexdigest(), proof['images'][which]['sha256'])
            pe = pefile.PE(data=raw)
            if pe.OPTIONAL_HEADER.DATA_DIRECTORY[5].Size:
                blocks = pe.DIRECTORY_ENTRY_BASERELOC
            else:
                blocks = []
            relocs = [entry.rva for block in blocks for entry in block.entries if entry.type == 10]
            names = ('nullable_lookup', 'default_value_getter') if which == 'core' else ('alive_getter', 'leader_name_getter')
            for name in names:
                row = proof['spans'][name];rva = int(row['start_rva'], 16);expected = bytes.fromhex(row['raw_hex'])
                self.assertEqual(pe.get_data(rva, len(expected)), expected)
                self.assertFalse([position for position in relocs if rva <= position < rva + len(expected)])
            pe.close()
        self.assertEqual(proof['contract']['IsAlive']['provider_slot'], '0x58')
        self.assertTrue(proof['contract']['IsAlive']['lookup_missing_result'])
        self.assertEqual(proof['contract']['GetLeaderName']['provider_slot'], '0x68')
        # Independent EXE consumer: receiver RCX, key EDX, nullable return RAX.
        # In particular, this slot does not take the sret/out-pointer used by
        # unrelated native table methods elsewhere in the host.
        caller = {row['rva']: row['text'] for row in proof['spans']['alive_getter']['instructions']}
        self.assertEqual(caller['0x115304'], 'mov rcx, qword ptr [rcx + 0x18]')
        self.assertTrue(caller['0x115308'].startswith('mov edx, dword ptr [rip + '))
        self.assertEqual(caller['0x115311'], 'call qword ptr [rax + 0x58]')
        self.assertEqual(caller['0x115314'], 'test rax, rax')
        self.assertEqual(caller['0x115337'], 'mov ecx, dword ptr [rax + 8]')


if __name__ == '__main__':
    unittest.main()
