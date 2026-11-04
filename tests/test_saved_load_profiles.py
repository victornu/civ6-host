"""Offline ABI/refusal tests, not evidence of executing an expansion save."""
from __future__ import annotations

import ctypes as C
from dataclasses import FrozenInstanceError, replace
import hashlib
import json
import struct
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from civ6_host.runtime import saved_load_profiles as profiles
from civ6_host.runtime.paths import resource_root
from civ6_host.runtime.resource_resolution import resolve_path
from civ6_host.runtime.native import native_checkpoint_load as loader
from civ6_host.runtime.native import native_host
from civ6_host.runtime.native import native_localization


BASE = profiles.profile_for_sha(profiles.BASE_CORE_SHA256)


def source_documents():
    result = []
    for relative, expected in profiles.SOURCES:
        raw = resolve_path(resource_root() / relative).read_bytes()
        if hashlib.sha256(raw).hexdigest() != expected:
            raise AssertionError('Changed source proof: ' + relative)
        result.append(json.loads(raw))
    return result


def backend_fixture(profile=BASE):
    """Bounded synthetic addresses; no dereference outside this dictionary."""
    obj = loader.NativeLoadBackend.__new__(loader.NativeLoadBackend)
    obj.core = SimpleNamespace(_handle=0x180000000)
    obj.context = 0x2000000000
    inner, game, provider = 0x2100000000, 0x2200000000, 0x2300000000
    obj.load_abi = profile
    obj.check_thread = Mock()
    memory = {}
    q = lambda address, value: memory.update({address: struct.pack('<Q', value)})
    q(obj.context, obj.core._handle + profile.outer_vtable_rva)
    q(obj.context + 8, inner)
    q(inner, obj.core._handle + profile.inner_vtable_rva)
    q(inner + 0x50, 0x11000)
    q(inner + 0x58, 0x12000)
    q(inner + 0x60, game)
    q(inner + 0xE00, provider)
    q(game, obj.core._handle + profile.game_vtable_rva)
    for vtable, slot, target in profile.virtual_targets:
        q(obj.core._handle + vtable + slot, obj.core._handle + target)
    memory[obj.core._handle + profile.game_initialized_rva] = bytes.fromhex('0fb681a4020000c3')
    def read(address, size):
        data = memory[address]
        if len(data) != size:
            raise AssertionError('Unexpected memory-read size')
        return data
    obj.runtime = SimpleNamespace(read=read)
    return obj, memory, inner, game


class SavedLoadProfilesTests(unittest.TestCase):
    def test_all_engine_targets_match_pinned_binary_sources(self):
        base, dispatch, prepare, active = source_documents()
        for sha in (profiles.BASE_CORE_SHA256, profiles.XP1_CORE_SHA256, profiles.XP2_CORE_SHA256):
            abi = profiles.profile_for_sha(sha)
            d = dispatch['images'][abi.ruleset]
            self.assertEqual(d['image']['sha256'], sha)
            self.assertEqual(int(d['outer_vtable_rva'], 16), abi.outer_vtable_rva)
            self.assertEqual(int(d['inner_vtable_rva'], 16), abi.inner_vtable_rva)
            self.assertEqual(int(d['slots']['outer_load']['target_rva'], 16), abi.load_rva)
            self.assertEqual(int(d['slots']['inner_load']['target_rva'], 16), abi.inner_load_rva)
            self.assertEqual(d['outer_contract']['signature'], 'int32 Load(void *outer_this, void *reader)')
            self.assertIs(d['outer_contract']['input_r8_used'], False)
            if abi.ruleset == 'base':
                for vt, slot, target in abi.virtual_targets:
                    table = base['vtables']['outer' if vt == abi.outer_vtable_rva else 'inner']
                    raw = bytes.fromhex(table['raw_hex'])
                    self.assertEqual(struct.unpack_from('<Q', raw, slot)[0] - 0x180000000, target)
            else:
                p = prepare['profiles'][abi.ruleset]
                self.assertEqual(p['image']['sha256'], sha)
                for vt, slot, target in abi.virtual_targets:
                    table = 'outer_slots' if vt == abi.outer_vtable_rva else 'inner_slots'
                    self.assertEqual(int(p['vtables'][table][hex(slot)]['target_rva'], 16), target)
                a = active['profiles'][sha]
                self.assertEqual(a['layout']['game_vtable_rva'], abi.game_vtable_rva)
                function = a['functions'][hex(0x180000000 + abi.game_initialized_rva)]
                rows = [r for f in function.get('fragments', [function]) for r in f['instructions']]
                self.assertEqual(''.join(r['bytes'] for r in rows), '0fb681a4020000c3')

    def test_selection_has_no_fallback_and_profiles_are_immutable(self):
        for unknown in (None, False, [], '0' * 64, profiles.BASE_CORE_SHA256.upper()):
            with self.assertRaises(ValueError):
                profiles.profile_for_sha(unknown)
        with self.assertRaises(FrozenInstanceError):
            BASE.load_rva = 0
        with self.assertRaises(ValueError):
            profiles.require_saved_load_admission(replace(BASE, load_rva=0))
        self.assertIs(profiles.require_saved_load_admission(BASE), BASE)

    def test_expansion_refused_before_native_setup_or_prepare_localization(self):
        for sha in (profiles.XP1_CORE_SHA256, profiles.XP2_CORE_SHA256):
            abi = profiles.profile_for_sha(sha)
            with patch.object(loader.configuration._NativeBackend, '__init__') as parent:
                with self.assertRaisesRegex(ValueError, 'Expansion saved Load is not admitted'):
                    loader.NativeLoadBackend(None, None, None, None,
                        SimpleNamespace(core_sha256=sha), {}, None)
                parent.assert_not_called()
            with patch.object(native_localization, 'initialize_localization') as initialize:
                with self.assertRaisesRegex(ValueError, 'Expansion saved Load is not admitted'):
                    native_host.prepare_context(None, None, None, saved_load_abi=abi)
                initialize.assert_not_called()

    def test_base_topology_retains_each_virtual_target_check(self):
        obj, memory, inner, game = backend_fixture()
        self.assertEqual(obj.topology(game_required=True),
                         dict(inner=inner, game=game, provider=0x2300000000))
        for vt, slot, _ in BASE.virtual_targets:
            address = obj.core._handle + vt + slot
            original = memory[address]
            memory[address] = struct.pack('<Q', 1)
            with self.assertRaisesRegex(ValueError, 'virtual target differs'):
                obj.topology(game_required=True)
            memory[address] = original
        memory[game] = struct.pack('<Q', obj.core._handle + profiles.profile_for_sha(profiles.XP1_CORE_SHA256).game_vtable_rva)
        with self.assertRaisesRegex(ValueError, 'Game identity differs'):
            obj.topology(game_required=True)

    def test_base_getter_binds_retained_signature_and_checks_bytes_before_call(self):
        obj, memory, _, game = backend_fixture()
        function = Mock(return_value=0)
        binder = Mock(return_value=function)
        with patch.object(C, 'WINFUNCTYPE', return_value=binder) as signature:
            self.assertEqual(obj.game_flag(), 0)
            signature.assert_called_once_with(C.c_uint32, C.c_void_p)
            binder.assert_called_once_with(obj.core._handle + 0x4C3F60)
            function.assert_called_once_with(game)
            memory[obj.core._handle + BASE.game_initialized_rva] = b'\x00' * 8
            with self.assertRaisesRegex(ValueError, 'getter changed'):
                obj.game_flag()
            signature.assert_called_once()

    def test_base_prepare_default_and_explicit_profile_use_same_target(self):
        # Valid local buffers, no game image and no native function invocation.
        inner = C.create_string_buffer(0x68)
        outer = (C.c_void_p * 2)(None, C.addressof(inner))
        core = SimpleNamespace(_diagnostic_host=SimpleNamespace(dll_directory='unused'))
        for kwargs in ({}, {'saved_load_abi': BASE}):
            call = Mock()
            with patch.object(native_localization, 'initialize_localization') as initialize, \
                 patch.object(native_host, 'virtual', return_value=call) as virtual:
                native_host.prepare_context(core, C.addressof(outer), Mock(), **kwargs)
                virtual.assert_called_once_with(core, C.addressof(outer), 0x40, 0x42F5A0, None)
                call.assert_called_once_with(C.addressof(outer))
                initialize.assert_called_once()

    def test_copy_keeps_void_signature_owner_arguments_and_non_alias_checks(self):
        from civ6_host.runtime.native import native_configuration_finalization as setup
        obj, _, _, _ = backend_fixture()
        a = dict(descriptor=101, normalized=102, map_normalized=103, players=tuple(range(104, 168)))
        b = dict(descriptor=201, normalized=202, map_normalized=203, players=tuple(range(204, 268)))
        obj.owner = SimpleNamespace(pointer=201, new_game_entered=False,
                                    require_context=Mock(), snapshot=Mock(return_value=b))
        obj.prefix = SimpleNamespace(configuration_readback_verified=True,
                                     verify_configuration_scalar_marshalling=Mock())
        obj.game_flag = Mock(return_value=0)
        call, binder = Mock(), Mock()
        binder.return_value = call
        with patch.object(C, 'WINFUNCTYPE', return_value=binder) as signature, \
             patch.object(setup, '_linked_snapshot', return_value=a), \
             patch.object(loader.application, 'provider_snapshot', return_value=a):
            self.assertFalse(obj.copy_b_to_a()['new_game_called'])
            signature.assert_called_once_with(None, C.c_void_p, C.c_void_p)
            binder.assert_called_once_with(obj.core._handle + 0x42F470)
            call.assert_called_once_with(obj.context, 201)
            self.assertEqual(obj.stage, 'copied')
            obj.owner.snapshot.return_value = a
            with self.assertRaisesRegex(RuntimeError, 'share native submaps'):
                obj.copy_b_to_a()

    def test_load_reader_keeps_two_argument_int32_binding_and_source_check(self):
        from civ6_host.runtime.native import native_checkpoint_job_observer as observer
        obj, _, _, _ = backend_fixture()
        obj.load_attempted = False
        obj.reader = None
        obj.stage = 'copied'
        obj.streams = []
        obj.thread = (1, 2)
        obj.proofs = {'retained': 'source'}
        obj.control = Mock()
        obj.game_flag = Mock(return_value=0)
        reader = SimpleNamespace(pointer=1234, _check=Mock())
        binder = Mock()
        with patch.object(loader, 'Win64Stream', return_value=reader), \
             patch.object(observer, 'make_job_observer', return_value=Mock()), \
             patch.object(loader, 'check_live_bodies') as code_check, \
             patch.object(C, 'WINFUNCTYPE', return_value=binder) as signature:
            obj.create_reader(SimpleNamespace(game=b'synthetic'))
            signature.assert_called_once_with(C.c_int32, C.c_void_p, C.c_void_p)
            binder.assert_called_once_with(obj.core._handle + 0x42E420)
            code_check.assert_called_once_with(obj.core._handle, obj.runtime.read, obj.proofs)
            obj.control.assert_called_once_with(empty=True)
            reader._check.assert_called_once_with(1234)

    def test_xp1_copy_uses_one_engine_for_dispatch_index_and_provider_readback(self):
        from civ6_host.runtime import configuration_profiles as config
        from civ6_host.runtime.native import native_configuration_finalization as setup
        xp1=profiles.profile_for_sha(profiles.XP1_CORE_SHA256)
        obj,_,_,_=backend_fixture(xp1)
        a=dict(descriptor=101,normalized=102,map_normalized=103,players=tuple(range(104,168)))
        b=dict(descriptor=201,normalized=202,map_normalized=203,players=tuple(range(204,268)))
        obj.owner=SimpleNamespace(pointer=201,new_game_entered=False,
            require_context=Mock(),snapshot=Mock(return_value=b))
        obj.prefix=SimpleNamespace(configuration_readback_verified=True,
            verify_configuration_scalar_marshalling=Mock())
        obj.game_flag=Mock(return_value=0)
        call=Mock();binder=Mock(return_value=call)
        with patch.object(config,'verify_context_copy') as verify, \
             patch.object(C,'WINFUNCTYPE',return_value=binder) as signature, \
             patch.object(setup,'_linked_snapshot',return_value=a) as linked, \
             patch.object(loader.application,'provider_snapshot',return_value=a) as snapshot:
            obj.copy_b_to_a()
            verify.assert_called_once_with(xp1,obj.core._handle,obj.runtime.read)
            signature.assert_called_once_with(None,C.c_void_p,C.c_void_p)
            binder.assert_called_once_with(obj.core._handle+0x4BE570)
            call.assert_called_once_with(obj.context,201)
            self.assertEqual(linked.call_args.kwargs,{'core_sha256':profiles.XP1_CORE_SHA256})
            self.assertEqual(snapshot.call_args.kwargs,{'core_sha256':profiles.XP1_CORE_SHA256})
            self.assertFalse(obj.owner.new_game_entered)
        with patch.object(config,'verify_context_copy',side_effect=ValueError('changed native body')), \
             patch.object(C,'WINFUNCTYPE') as invoke:
            with self.assertRaises(ValueError):obj.copy_b_to_a()
            invoke.assert_not_called()

    def test_xp1_copy_checks_live_source_and_refuses_other_profiles_before_reads(self):
        from civ6_host.runtime import configuration_profiles as config
        xp1=profiles.profile_for_sha(profiles.XP1_CORE_SHA256)
        functions=config.context_copy_source(xp1)
        base=0x190000000;memory={}
        for body in functions.values():
            for fragment in body['fragments']:
                for row in fragment['instructions']:
                    data=bytes.fromhex(row['bytes'])
                    memory[(base+int(row['va'],16)-0x180000000,len(data))]=data
        read=Mock(side_effect=lambda address,size:memory[(address,size)])
        self.assertFalse(config.verify_context_copy(xp1,base,read)['game_load_admitted'])
        first=next(iter(memory));memory[first]=b'\x00'*first[1]
        with self.assertRaisesRegex(ValueError,'live code differs'):
            config.verify_context_copy(xp1,base,read)
        for profile in (BASE,profiles.profile_for_sha(profiles.XP2_CORE_SHA256),replace(xp1,copy_rva=1)):
            read.reset_mock()
            with self.assertRaises(ValueError):config.verify_context_copy(profile,base,read)
            read.assert_not_called()


if __name__ == '__main__':
    unittest.main()
