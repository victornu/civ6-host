"""Retained slot/owner/caller composition; source ABI has separate live-byte tests."""
import ctypes as C
import struct
from types import SimpleNamespace as NS
import unittest
from unittest.mock import Mock, patch

from civ6_host.runtime import xp2_host_achievement_service as service
from civ6_host.runtime import xp2_host_slot20_source as source
from civ6_host.runtime.configuration_profiles import XP2_CORE_SHA256, XP1_CORE_SHA256
from civ6_host.runtime.native.native_official_load import OfficialLoadBackend
from test_xp1_host_slot78 import HostFixture


def fixture():
    host = HostFixture()
    host.achievement_service_installed = False
    host._bind(host.vtable, 0x20, None, [C.c_void_p], host._unsupported('host', 0x20))
    backend = object.__new__(OfficialLoadBackend)
    backend.__dict__.update(host=host, _saved_load_candidate=True,
        _xp1_commands_requested=True, load_abi=NS(core_sha256=XP2_CORE_SHA256),
        stage='prepared', prefix=None, busy=True, poisoned=False, destroyed=False,
        core=NS(_handle=0x180000000), runtime=NS(read=Mock()),
        check_thread=Mock(), emit=Mock())
    return backend


def admitted_frames():
    return [dict(module='GameCore_XP2_FinalRelease.dll', rva=rva)
            for rva in ('0x17f098', '0x17b387', '0x35b0dc', '0x24025b')]


class XP2OptionalAchievementServiceTests(unittest.TestCase):
    def install(self, backend):
        # The source tests execute verify_live against all pinned instructions.
        # Here only the native-address boundary is replaced; the real source
        # selector authenticates the retained attempt-13 stack on every call.
        with patch('civ6_host.runtime.xp2_turn_source.require_prepared_owner') as owner, \
                patch.object(source, 'source_dependencies', return_value={}), \
                patch.object(source, 'verify_live', return_value=10) as live:
            receipt = service.install(backend)
        owner.assert_called_once_with(backend)
        live.assert_called_once_with(backend.core._handle, backend.runtime.read,
                                     host_pointer=backend.host.pointer)
        return receipt

    def test_only20_is_restored_and_real_selector_refuses_unknown_stack(self):
        backend = fixture(); host = backend.host
        before = dict(host._slot_bindings)
        with patch('civ6_host.runtime.native.native_absent_achievements.capture_stack',
                   return_value=admitted_frames()) as stack:
            receipt = self.install(backend)
        changes = {key for key, value in host._slot_bindings.items()
                   if before.get(key) != value}
        self.assertEqual(changes, {(C.addressof(host.vtable), 0x20)})
        self.assertEqual(host.last_signature, (C.c_void_p, [C.c_void_p]))
        callback = host._slot_bindings[C.addressof(host.vtable), 0x20][1]
        self.assertIs(backend._xp2_host20[1], callback)
        self.assertIsNone(callback(host.pointer))
        event = backend.emit.call_args.kwargs
        self.assertIs(event['native_null_branch_used'], True)
        self.assertIs(event['platform_success_reported'], False)
        self.assertEqual(event['source_proof_sha256'], source.SOURCE[1])
        self.assertIs(receipt['unknown_service_fallback'], False)
        self.assertIs(receipt['caller_results_consumed_admitted'], False)
        stack.return_value = [dict(module='GameCore_XP2_FinalRelease.dll', rva='0x17f098'),
                              dict(module='GameCore_XP2_FinalRelease.dll', rva='0x17b386')]
        backend.emit.reset_mock()
        with self.assertRaises(ValueError): callback(host.pointer)
        backend.emit.assert_not_called()
        with self.assertRaises(ValueError): callback(host.pointer + 8)
        host.achievement_service_installed = True
        with self.assertRaises(ValueError): callback(host.pointer)

    def test_formation_uses_same_owned_callback_and_separate_proof(self):
        backend = fixture()
        frames = [dict(module=source.CORE_MODULE,rva=rva) for rva in
                  ("0x17f098","0x17fa97","0x226ed4","0x1a33a5","0x65a217")]
        with patch('civ6_host.runtime.native.native_absent_achievements.capture_stack',
                   return_value=frames):
            self.install(backend)
            callback = backend._xp2_host20[1]
            self.assertIsNone(callback(backend.host.pointer))
        event = backend.emit.call_args.kwargs
        self.assertEqual(event['source_proof_sha256'],source.FORMATION_SOURCE[1])
        self.assertIs(event['platform_request_submitted'],False)
        self.assertIs(event['platform_success_reported'],False)

    def test_native02_composed_callback_uses_source_proved_null_ignored_route(self):
        backend = fixture(); host = backend.host
        frames = [dict(module=source.CORE_MODULE, rva=rva)
                  for rva in source.NATIVE02_OBSERVED_CHAIN]
        with patch('civ6_host.runtime.native.native_absent_achievements.capture_stack',
                   return_value=frames):
            self.install(backend)
            callback = backend._xp2_host20[1]
            self.assertIsNone(callback(host.pointer))
        event = backend.emit.call_args.kwargs
        self.assertEqual(event['source_proof_sha256'], source.NATIVE02_SOURCE[1])
        self.assertIs(event['native_null_branch_used'], True)
        self.assertIs(event['platform_service_installed'], False)
        self.assertIs(event['platform_request_submitted'], False)
        self.assertIs(event['platform_success_reported'], False)
        self.assertIs(event['source_qualified_unused_result_path'], True)
        frames[1]['rva'] = '0x17b387'
        backend.emit.reset_mock()
        with patch('civ6_host.runtime.native.native_absent_achievements.capture_stack',
                   return_value=frames):
            with self.assertRaisesRegex(ValueError, 'Unproved XP2 optional achievement caller chain'):
                callback(host.pointer)
        backend.emit.assert_not_called()

    def test_foreign_engine_owner_binding_and_duplicate_install_refuse(self):
        for field, value in [('stage', 'loaded'), ('busy', False), ('poisoned', True),
                             ('destroyed', True), ('_xp1_commands_requested', False)]:
            with self.subTest(field=field):
                backend = fixture(); setattr(backend, field, value)
                with self.assertRaises(ValueError): self.install(backend)
        backend = fixture(); backend.load_abi.core_sha256 = XP1_CORE_SHA256
        with self.assertRaises(ValueError): self.install(backend)
        backend = fixture(); host = backend.host
        host._bind(host.vtable, 0x20, C.c_void_p, [C.c_void_p], lambda this: None)
        with self.assertRaises(ValueError): self.install(backend)
        backend = fixture()
        self.install(backend)
        with self.assertRaises(ValueError): self.install(backend)

    def test_xp1_routes_only_admit_proved_optional_callers_and_owner(self):
        import pefile
        from civ6_host.runtime import xp1_host_slot20_source as xp1
        from civ6_host.runtime.execution_images import _XP1_PROFILE
        from civ6_host.runtime.xp1_continuation import SavedContinuation

        backend = fixture()
        host = backend.host
        backend.load_abi.core_sha256 = XP1_CORE_SHA256
        backend.configuration_abi = NS(core_sha256=XP1_CORE_SHA256)
        backend.core._civ6_host_execution_image = _XP1_PROFILE
        image = pefile.PE(_XP1_PROFILE.path, fast_load=True)
        self.addCleanup(image.close)
        base = backend.core._handle
        pointer_rva = xp1.source(_XP1_PROFILE)['host_pointer_rva']
        backend.runtime.read.side_effect = lambda address, size: (
            struct.pack('<Q', host.pointer) if (address, size) == (base + pointer_rva, 8)
            else bytes(image.get_data(address - base, size)))
        token = SavedContinuation.__new__(SavedContinuation)
        token.owner = backend
        backend._xp1_continuation = token
        frames = [dict(module=xp1.CORE_MODULE, rva=rva) for rva in xp1.CALLER_PREFIX]
        with (patch('civ6_host.runtime.native.native_absent_achievements.capture_stack',
                    return_value=frames) as stack,
              patch.object(SavedContinuation, 'check', autospec=True) as active):
            receipt = service.install_xp1(backend)
            callback = backend._xp1_host20[1]
            self.assertIsNone(callback(host.pointer))
            active.assert_called_once_with(token, active=True)
            self.assertEqual(receipt['source_sha256'], xp1.SOURCE[1])
            self.assertIs(backend.emit.call_args.kwargs['platform_success_reported'], False)
            stack.return_value = frames[:-1] + [dict(module=xp1.CORE_MODULE, rva='0x205025')]
            with self.assertRaisesRegex(ValueError, 'Unproved XP1'):
                callback(host.pointer)
            worldbuilder = [dict(module=xp1.CORE_MODULE, rva=rva) for rva in xp1.WORLDBUILDER_CALLER]
            stack.return_value = worldbuilder
            self.assertIsNone(callback(host.pointer))
            self.assertEqual(backend.emit.call_args.kwargs['source_proof_sha256'], xp1.ORIGINAL_SOURCE[1])
            self.assertIs(backend.emit.call_args.kwargs['platform_request_submitted'], False)
            stack.return_value = worldbuilder + [dict(module=xp1.CORE_MODULE, rva='0x5238ca')]
            with self.assertRaisesRegex(ValueError, 'Unproved XP1'):
                callback(host.pointer)
            for callers, source in ((xp1.TURN_CALLER, xp1.TURN_SOURCE),
                                    (xp1.BESIEGED_CITY_CALLER, xp1.BESIEGED_CITY_SOURCE),
                                    (xp1.CITY_STATE_CONTACT_CALLER, xp1.CITY_STATE_CONTACT_SOURCE),
                                    (xp1.ENVOY_ASSIGNMENT_CALLER, xp1.ENVOY_ASSIGNMENT_SOURCE)):
                frames = [dict(module=xp1.CORE_MODULE, rva=rva) for rva in callers]
                stack.return_value = frames
                self.assertIsNone(callback(host.pointer))
                self.assertEqual(backend.emit.call_args.kwargs['source_proof_sha256'], source[1])
                self.assertIs(backend.emit.call_args.kwargs['platform_request_submitted'], False)
                # The shared envoy observer is qualified independently of the
                # outer player operation. Missing the observer boundary is not.
                stack.return_value = (frames[:3] if callers in
                                     (xp1.ENVOY_ASSIGNMENT_CALLER, xp1.CITY_STATE_CONTACT_CALLER)
                                     else frames[:-1])
                with self.assertRaisesRegex(ValueError, 'Unproved XP1'):
                    callback(host.pointer)
            shared = xp1._source(xp1.ENVOY_NOTIFICATION_SOURCE)
            for callers in (shared['witness']['observed_core_frames'], xp1.ENVOY_NOTIFICATION_CALLER):
                frames = [dict(module=xp1.CORE_MODULE, rva=rva) for rva in callers]
                stack.return_value = frames
                self.assertIsNone(callback(host.pointer))
                event = backend.emit.call_args.kwargs
                self.assertEqual(event['source_proof_sha256'], xp1.ENVOY_NOTIFICATION_SOURCE[1])
                self.assertIs(event['platform_request_submitted'], False)
                self.assertIs(event['platform_success_reported'], False)
                for index in range(4):
                    changed = [dict(frame) for frame in frames]
                    changed[index]['rva'] = hex(int(changed[index]['rva'], 16) + 1)
                    stack.return_value = changed
                    with self.assertRaisesRegex(ValueError, 'Unproved XP1'):
                        callback(host.pointer)
            for site in ('0x13eb88', '0x13ee1b'):
                frames = [dict(module=xp1.CORE_MODULE, rva=rva)
                          for rva in (xp1.CALLER_PREFIX[0], site, *xp1.TURN_LISTENER_TAIL)]
                stack.return_value = frames
                self.assertIsNone(callback(host.pointer))
                self.assertEqual(backend.emit.call_args.kwargs['source_proof_sha256'],
                                 xp1.TURN_LISTENER_SOURCE[1])
                self.assertFalse(backend.emit.call_args.kwargs['platform_success_reported'])
                stack.return_value = frames[:-1]
                with self.assertRaisesRegex(ValueError, 'Unproved XP1'):
                    callback(host.pointer)
            stack.return_value = [dict(frame, rva='0x13ee1c') if i == 1 else frame
                                  for i, frame in enumerate(frames)]
            with self.assertRaisesRegex(ValueError, 'Unproved XP1'):
                callback(host.pointer)
            for site in xp1.GOVERNMENT_LISTENER_TAGS:
                frames = [dict(module=xp1.CORE_MODULE, rva=rva)
                          for rva in (xp1.CALLER_PREFIX[0], site, *xp1.GOVERNMENT_LISTENER_TAIL)]
                stack.return_value = frames
                self.assertIsNone(callback(host.pointer))
                event = backend.emit.call_args.kwargs
                self.assertEqual(event['source_proof_sha256'], xp1.GOVERNMENT_LISTENER_SOURCE[1])
                self.assertIs(event['platform_request_submitted'], False)
                self.assertIs(event['platform_success_reported'], False)
                for outer in (frames[:4], frames[:-1],
                              frames[:-1] + [dict(frames[-1], rva='0x35f99b')]):
                    stack.return_value = outer
                    self.assertIsNone(callback(host.pointer))
                    self.assertEqual(backend.emit.call_args.kwargs['source_proof_sha256'],
                                     xp1.SHARED_BOUNDARY_SOURCE[1])
                stack.return_value = frames[:3]
                with self.assertRaisesRegex(ValueError, 'Unproved XP1'):
                    callback(host.pointer)
            del backend._xp1_continuation
            with self.assertRaisesRegex(ValueError, 'active saved-game owner'):
                callback(host.pointer)


if __name__ == '__main__': unittest.main()
