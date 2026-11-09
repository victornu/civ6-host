"""Counted strings retain their owned bytes and never become scalar fallbacks."""
import ctypes as C
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch

from civ6_host.runtime.script_event_strings import (
    StringArgument, StringTransport, argument_evidence, pack_strings,
    require_string_transport,
)


class StringArgumentTests(unittest.TestCase):
    def test_empty_binary_and_scalar_arguments_keep_types_and_storage(self):
        values = (StringArgument(b'RESOLUTION_X'), 0xffffffff, True,
                  StringArgument(b'left\0right'), StringArgument(b''))
        packed, maps, strings, keepalive = pack_strings(values)
        self.assertEqual(C.sizeof(StringTransport), 16)
        self.assertEqual([(x.kind,x.value) for x in packed],
                         [(3,0),(0,0xffffffff),(1,1),(3,1),(3,2)])
        self.assertEqual(len(maps), 0)
        self.assertEqual([C.string_at(x.data,x.size) for x in strings],
                         [b'RESOLUTION_X',b'left\0right',b''])
        self.assertTrue(all(x.reserved == 0 for x in strings))
        self.assertEqual(len(keepalive), 3)
        self.assertEqual(argument_evidence(values)['arguments_typed'][3],
                         {'type':'string','bytes':10,'raw_hex':b'left\0right'.hex()})

    def test_input_cannot_keep_a_mutable_or_unbounded_borrow(self):
        with self.assertRaises(ValueError): StringArgument(bytearray(b'x'))
        with self.assertRaises(ValueError): StringArgument(b'x'*65537)
        with self.assertRaisesRegex(ValueError, 'Aggregate'):
            pack_strings((StringArgument(b'x'*65536),)*17)
        with self.assertRaises(ValueError): pack_strings((StringArgument(b''),)*65)

    def test_scalar_and_map_only_callers_are_not_silently_reinterpreted(self):
        with self.assertRaises(ValueError): pack_strings((1,True))
        from civ6_host.runtime.native.native_script_arguments import pack_arguments
        with self.assertRaises(ValueError): pack_arguments((StringArgument(b'x'),))
        with self.assertRaises(ValueError): pack_strings((StringArgument(b'x'),1.5))

    def test_old_native_library_is_refused_without_export_or_version(self):
        with self.assertRaisesRegex(ValueError, 'no string'):
            require_string_transport(NS(host=NS()))
        def old_version(): return 0
        with self.assertRaisesRegex(ValueError, 'version'):
            require_string_transport(NS(host=NS(LAB_GameEventsStringArgumentVersion=old_version)))

    def test_runtime_call_and_testall_reach_new_export_with_their_own_return_shape(self):
        from unittest.mock import Mock
        from civ6_host.runtime.native.native_script_runtime import NativeScriptRuntime
        seen = []
        def dispatch(root,name,args,count,maps,map_count,strings,string_count,method,valid,output):
            seen.append((name,method,C.string_at(strings[0].data,strings[0].size)))
            C.cast(valid,C.POINTER(C.c_uint8))[0] = 1
            C.cast(output,C.POINTER(C.c_uint8))[0] = 1
            return 0
        runtime = object.__new__(NativeScriptRuntime)
        runtime.root, runtime.lua, runtime._status = 1, {'gettop':lambda root:0}, Mock()
        runtime.host = NS(LAB_GameEventsMapArgumentVersion=Mock(return_value=1),
                          LAB_AuxMapTransportVersion=Mock(return_value=2),
                          LAB_GameEventsDispatchMapsResult=Mock(),
                          LAB_GameEventsStringArgumentVersion=Mock(return_value=1),
                          LAB_GameEventsDispatchStringsResult=dispatch)
        value = (StringArgument(b'RESOLUTION_X'),)
        self.assertIs(runtime.dispatch_game_event(b'WC_Test',value),True)
        self.assertEqual(runtime.dispatch_game_event_result(b'WC_Test',value,method='TestAll'),(True,1))
        self.assertEqual(seen,[(b'WC_Test',0,b'RESOLUTION_X'),(b'WC_Test',1,b'RESOLUTION_X')])

    def test_owned_payload_copies_before_native_caller_reuses_its_buffer(self):
        from test_script_event_service import ScriptEventServiceTests
        _, runtime, service, _, _ = ScriptEventServiceTests().fixture()
        def version(): return 1
        runtime.host = NS(LAB_GameEventsStringArgumentVersion=version)
        core = object()
        with patch('civ6_host.runtime.script_event_strings.verify_live', return_value={'source': 'fixture'}):
            service.install_string_arguments(core, read=lambda p,n:C.string_at(p,n))
        factory = service.script_arguments
        auxiliary = C.addressof(service.host.aux_object)
        address = factory._create(auxiliary)
        source = C.create_string_buffer(b'left\0right')
        fn = C.WINFUNCTYPE(C.c_uint32, C.c_void_p, C.c_void_p, C.c_size_t)(
            factory._payloads[address].vtable[0x30//8])
        self.assertEqual(fn(address,C.addressof(source),10),0)
        C.memset(C.addressof(source),ord('x'),10)
        self.assertEqual(factory.arguments(address), (StringArgument(b'left\0right'),))
        self.assertEqual(factory._append_string(address,address,None,0),1)
        with self.assertRaises(ValueError): factory._append_string(address,address+8,None,0)
        with self.assertRaises(ValueError): factory._append_string(address,address,None,1)
        factory._release(auxiliary,address)
        self.assertEqual(factory.live_count,0)
        with self.assertRaises(ValueError): factory.arguments(address)
        service.close()

    def test_mutable_result_uses_explicit_string_export_and_preserves_seed(self):
        from unittest.mock import Mock
        from test_script_event_mutable_map import MutableMapTests, SEED
        fixture_owner = MutableMapTests()
        self.addCleanup(fixture_owner.doCleanups)
        f = fixture_owner.fixture()
        self.addCleanup(f.service.close)
        seen = []
        legacy_native_fixture = f.exports.LAB_GameEventsDispatchMutableMapResult.side_effect
        def string_native(*args):
            seen.append(([C.string_at(args[6][i].data,args[6][i].size) for i in range(args[7])],
                         [(args[2][i].kind,args[2][i].value) for i in range(args[3])],
                         C.string_at(args[8],args[9]*16)))
            return legacy_native_fixture(*args[:6],*args[8:])
        f.exports.LAB_GameEventsStringArgumentVersion = Mock(return_value=1)
        f.exports.LAB_GameEventsDispatchMutableMapStringsResult = Mock(side_effect=string_native)
        result = f.service.mutable_map_dispatcher.dispatch(
            b'WC_Validate_Test', (StringArgument(b'RESOLUTION_X\0tail'),0xffffffff), f.destination)
        self.assertTrue(result.valid)
        self.assertFalse(result.truthiness)
        self.assertEqual(seen, [([b'RESOLUTION_X\0tail'],[(3,0),(0,0xffffffff)],SEED)])
        f.exports.LAB_GameEventsDispatchMutableMapStringsResult.assert_called_once()
        f.exports.LAB_GameEventsDispatchMutableMapResult.assert_not_called()

    def test_saved_load_installs_strings_only_for_the_admitted_new_host(self):
        from contextlib import ExitStack
        from unittest.mock import Mock
        from test_saved_load_services import SavedLoadServicesTests
        from civ6_host.runtime.saved_load_services import SavedLoadServices
        from civ6_host.runtime.configuration_profiles import XP2_CORE_SHA256
        from civ6_host.runtime.source_build_identity import (
            CURRENT_HAVOK_HOST_REFERENCE, CURRENT_STRINGS_HOST_REFERENCE,
        )
        fixture = SavedLoadServicesTests()
        self.addCleanup(fixture.doCleanups)
        backend, runtime, original, _, _ = fixture.fixture()
        original.close()
        backend.configuration_abi.core_sha256 = XP2_CORE_SHA256
        for reference, wanted in ((CURRENT_HAVOK_HOST_REFERENCE, False),
                                  (CURRENT_STRINGS_HOST_REFERENCE, True)):
            with self.subTest(host=reference[0]), ExitStack() as stack:
                events = NS(install_mutable_map_result=Mock(), install_string_arguments=Mock(),
                    mutable_map_dispatcher=NS(proof={'native_host_sha256':reference[1]}))
                stack.enter_context(patch('civ6_host.runtime.saved_load_services.ScriptEventService',
                                          return_value=events))
                stack.enter_context(patch('civ6_host.runtime.xp2_saved_script_services.verify_services',
                                          return_value={}))
                backend.host._saved_load_services = None
                service = SavedLoadServices(backend,runtime,NS(pointer=100),object(),
                    core_sha256=XP2_CORE_SHA256,script_hashes={},bootstrap=Mock(),
                    saved_map_values=(('MAP_SIZE',1),),saved_config_sha='a'*64)
                events.install_mutable_map_result.assert_called_once()
                self.assertIs(service.events, events)
                if wanted:
                    events.install_string_arguments.assert_called_once_with(
                        backend.core,read=backend.runtime.read)
                else:
                    events.install_string_arguments.assert_not_called()

    def test_source_pin_matches_the_registered_image_and_live_bytes(self):
        import json
        from civ6_host.runtime.paths import resource_root
        from civ6_host.runtime.execution_images import select, known_path
        from civ6_host.runtime.script_event_strings import SOURCE, source_dependencies, verify_live
        from civ6_host.runtime.a0_policy_unlock_current import CURRENT_PROFILE_ID
        image = select(CURRENT_PROFILE_ID,core_path=known_path(CURRENT_PROFILE_ID))
        dependencies = source_dependencies(execution_image=image)
        self.assertEqual(dependencies[resource_root()/SOURCE[0]], SOURCE[1])
        proof = json.loads((resource_root()/SOURCE[0]).read_text(encoding='utf-8'))
        base = 0x10000000
        spans = {(base+int(s['start_rva'],16),s['length']):bytes.fromhex(s['raw_hex'])
                 for s in proof['spans'].values() if s['image']=='core'}
        core = NS(_handle=base,_civ6_host_execution_image=image)
        verified = verify_live(core,lambda p,n:spans[p,n])
        self.assertEqual(verified['schema'], proof['schema'])
        self.assertEqual(verified['payload_contract']['slot'], '0x30')
        with self.assertRaisesRegex(ValueError,'Live script string'):
            verify_live(core,lambda p,n:b'\0'*n)


if __name__ == '__main__':
    unittest.main()
