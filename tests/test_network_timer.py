import struct
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from civ6_host.runtime import network_timer as timer


def variant(value):
    return b'\x02\x00\x00\x00' + b'\0' * 4 + struct.pack('<I', value)


class NetworkTimerTests(unittest.TestCase):
    def xp1_owner(self, *, corrupt_slot=False, core_sha256=timer.XP1_CORE_SHA256):
        from civ6_host.runtime.configuration_profiles import configuration_abi
        abi = configuration_abi(core_sha256)
        base, target, node = 0x180000000, 5000, 7000
        values = iter((variant(timer.NO_TIMER), variant(123)))
        def read(address, size):
            if (address,size) == (target,8):return (base+abi.vtable_rva).to_bytes(8,'little')
            if (address,size) == (base+abi.vtable_rva+0x58,8):
                return (base+abi.lookup_rva+int(corrupt_slot)).to_bytes(8,'little')
            if (address,size) == (node,12):return next(values)
            raise AssertionError((address,size))
        app=SimpleNamespace(_configuration_abi=abi,require_context=Mock(),
                            snapshot=Mock(return_value={'normalized':target}))
        owner=SimpleNamespace(check_thread=Mock(),emit=Mock(),context=9,
            core=SimpleNamespace(_handle=base),load_abi=SimpleNamespace(core_sha256=core_sha256),
            owner=app,runtime=SimpleNamespace(read=Mock(side_effect=read),call=None))
        return owner,abi

    def test_xp2_selected_provider_and_shared_exe_projection_without_native_claim(self):
        timer.verify_source()
        owner,abi=self.xp1_owner(core_sha256=timer.XP2_CORE_SHA256)
        with patch('civ6_host.runtime.native.native_configuration_finalization._invoke',return_value=7000) as invoke:
            self.assertIs(timer.read(owner,core_sha256=timer.XP2_CORE_SHA256),False)
            self.assertIsNone(timer.read(owner,core_sha256=timer.XP2_CORE_SHA256))
        self.assertEqual(invoke.call_count,2)
        self.assertTrue(all(call.args[1]==owner.core._handle+abi.lookup_rva for call in invoke.call_args_list))
        self.assertEqual(owner.emit.call_args.kwargs['configuration_core_sha256'],timer.XP2_CORE_SHA256)
        for corrupt in ('slot','provider','engine'):
            owner,_=self.xp1_owner(core_sha256=timer.XP2_CORE_SHA256,corrupt_slot=corrupt=='slot')
            if corrupt=='provider':owner.owner._configuration_abi=object()
            if corrupt=='engine':owner.load_abi.core_sha256=timer.XP1_CORE_SHA256
            with patch('civ6_host.runtime.native.native_configuration_finalization._invoke') as invoke:
                with self.assertRaises(ValueError):timer.read(owner,core_sha256=timer.XP2_CORE_SHA256)
                invoke.assert_not_called()

    def test_xp1_uses_its_actual_provider_slot_and_refreshes_each_lookup(self):
        owner,abi=self.xp1_owner()
        with patch.object(timer,'verify_source'), \
             patch('civ6_host.runtime.native.native_player_configuration._checked_object',
                   side_effect=AssertionError('Base provider must not be used')), \
             patch('civ6_host.runtime.native.native_configuration_finalization._invoke',return_value=7000) as invoke:
            self.assertIs(timer.read(owner,core_sha256=timer.XP1_CORE_SHA256),False)
            self.assertIsNone(timer.read(owner,core_sha256=timer.XP1_CORE_SHA256))
        self.assertEqual(invoke.call_count,2)
        self.assertTrue(all(call.args[1]==owner.core._handle+abi.lookup_rva for call in invoke.call_args_list))
        self.assertEqual(owner.runtime.read.call_count,6)
        self.assertEqual(owner.emit.call_args.kwargs['configuration_core_sha256'],timer.XP1_CORE_SHA256)

    def test_xp1_rejects_wrong_slot_or_foreign_provider_before_native_lookup(self):
        for wrong in ('slot','provider','engine'):
            owner,_=self.xp1_owner(corrupt_slot=wrong=='slot')
            if wrong=='provider':owner.owner._configuration_abi=object()
            if wrong=='engine':owner.load_abi.core_sha256=timer.BASE_CORE_SHA256
            with self.subTest(wrong=wrong),patch.object(timer,'verify_source'), \
                 patch('civ6_host.runtime.native.native_configuration_finalization._invoke') as invoke:
                with self.assertRaises(ValueError):timer.read(owner,core_sha256=timer.XP1_CORE_SHA256)
                invoke.assert_not_called()

    def test_no_timer_and_missing_row_follow_distinct_native_branches(self):
        self.assertEqual(timer.elapsed_from_lookup(variant(timer.NO_TIMER)),
                         (False, timer.NO_TIMER))
        self.assertEqual(timer.elapsed_from_lookup(None), (False, None))

    def test_timed_modes_stay_unknown_and_short_reads_fail(self):
        self.assertEqual(timer.elapsed_from_lookup(variant(123)), (None, 123))
        for raw in (b'', b'\0' * 11, b'\0' * 13, False):
            with self.assertRaises(ValueError):
                timer.elapsed_from_lookup(raw)

    def test_native_lookup_is_refreshed_without_replaying_capture(self):
        owner = SimpleNamespace(check_thread=Mock(), emit=Mock(), context=9,
            core=SimpleNamespace(_handle=1000),
            owner=Mock(), runtime=SimpleNamespace(read=Mock(
                side_effect=[variant(timer.NO_TIMER), variant(123)]), call=None))
        owner.owner.snapshot.return_value = {'normalized': 5000}
        with patch.object(timer, 'verify_source'), \
             patch('civ6_host.runtime.native.native_player_configuration._checked_object', return_value=6000) as checked, \
             patch('civ6_host.runtime.native.native_configuration_finalization._invoke', return_value=7000) as invoke:
            self.assertIs(timer.read(owner), False)
            self.assertIsNone(timer.read(owner))
        self.assertEqual(invoke.call_count, 2)
        self.assertEqual(checked.call_args.args[-2], 0x58)
        self.assertEqual(owner.runtime.read.call_count, 2)
        self.assertEqual(owner.emit.call_count, 2)

    def test_read_only_lookup_detects_provider_change(self):
        owner = SimpleNamespace(check_thread=Mock(), emit=Mock(), context=9,
            core=SimpleNamespace(_handle=1000), owner=Mock(),
            runtime=SimpleNamespace(read=Mock(return_value=variant(timer.NO_TIMER)), call=None))
        owner.owner.snapshot.side_effect = [{'normalized':5000}, {'normalized':5001}]
        with patch.object(timer, 'verify_source'), \
             patch('civ6_host.runtime.native.native_player_configuration._checked_object', return_value=6000), \
             patch('civ6_host.runtime.native.native_configuration_finalization._invoke', return_value=7000):
            with self.assertRaisesRegex(RuntimeError, 'provider changed'):
                timer.read(owner)
        owner.emit.assert_not_called()


if __name__ == '__main__':
    unittest.main()
