import struct
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch

from civ6_host.runtime.cache_facade_service import CacheFacadeService
from civ6_host.runtime.configuration_profiles import XP1_CORE_SHA256
from civ6_host.runtime.native.native_ui_cache_backend import NativeCacheFacadeBackend
from test_cache_facade_profiles import XP1FixtureBackend


class CacheFacadeServiceTests(unittest.TestCase):
    def fixture(self):
        fixture=XP1FixtureBackend()
        mocked=patch.object(NativeCacheFacadeBackend,'call',side_effect=fixture.call)
        mocked.start();self.addCleanup(mocked.stop)
        service=CacheFacadeService(NS(_handle=fixture.core_base),fixture.outer,
            core_sha256=XP1_CORE_SHA256,read=fixture.read,context_alive=fixture.context_alive)
        fixture.retained=service.facades
        return fixture,service

    def test_same_native_sequence_checks_actual_owners_and_closes_before_context(self):
        f,s=self.fixture()
        for _ in range(2):self.assertEqual(s.copy_cached_metadata().output,f.output)
        self.assertFalse(s.public_cache_ready)
        self.assertFalse(s.closed)
        s.close();n=len(f.calls);s.close()
        self.assertEqual(len(f.calls),n)
        self.assertTrue(s.closed)
        with self.assertRaises(RuntimeError):s.copy_cached_metadata()

    def test_replaced_owner_refuses_without_more_calls_and_cannot_recover(self):
        f,s=self.fixture();n=len(f.calls)
        f.q(f.owner+s.profile['ownership']['owner_cache_member_offset'],f.member+0x1000)
        with self.assertRaises((RuntimeError,ValueError,KeyError)):s.copy_cached_metadata()
        self.assertEqual(len(f.calls),n)
        self.assertTrue(s.quarantined)
        f.q(f.owner+s.profile['ownership']['owner_cache_member_offset'],f.member)
        with self.assertRaisesRegex(RuntimeError,'quarantined'):s.copy_cached_metadata()

    def test_wrong_wrapper_owner_is_not_released(self):
        f,s=self.fixture();n=len(f.calls)
        f.q(s.facades.game_facade+16,f.member)
        with self.assertRaisesRegex(ValueError,'owner'):s.close()
        self.assertEqual(len(f.calls),n)

    def test_callback_failure_after_native_effect_quarantines_and_prevents_cleanup(self):
        f,s=self.fixture();original=f.call
        def effect_then_fail(target,*args):
            result=original(target,*args)
            if target-f.core_base==f.abi.copy_rva:raise RuntimeError('uncertain effect')
            return result
        with patch.object(NativeCacheFacadeBackend,'call',side_effect=effect_then_fail):
            with self.assertRaisesRegex(RuntimeError,'uncertain'):s.copy_cached_metadata()
        self.assertTrue(s.quarantined);n=len(f.calls)
        with self.assertRaises(RuntimeError):s.close()
        self.assertEqual(len(f.calls),n)

    def test_foreign_result_owner_quarantines_without_releasing_uncertain_factory(self):
        f,s=self.fixture();f.q(f.b0_results[0]+16,f.owner)
        with self.assertRaisesRegex(ValueError,'owner'):s.copy_cached_metadata()
        self.assertTrue(s.quarantined)
        self.assertFalse(any(type(r[0]) is int and r[0]-f.core_base in f.abi.release_rvas for r in f.calls))

    def test_dead_context_and_wrong_thread_refuse_before_calls(self):
        f,s=self.fixture();n=len(f.calls);f.alive=False
        with self.assertRaises(RuntimeError):s.copy_cached_metadata()
        f.alive=True;s.thread=-1
        with self.assertRaises(RuntimeError):s.close()
        self.assertEqual(len(f.calls),n)

    def test_full_publication_and_borrowed_context_release_refused_without_poison(self):
        f,s=self.fixture();n=len(f.calls)
        with self.assertRaises(ValueError):s.facades.refresh()
        with self.assertRaises(ValueError):s.backend.call(f.core_base+f.abi.publish_rva,s.facades.game_facade,1)
        with self.assertRaises(ValueError):s.backend.call(f.target(f.abi.outer_vtable_rva,8),f.outer)
        with self.assertRaises(ValueError):s.backend.set_public_cache_gate(True)
        self.assertFalse(s.quarantined);self.assertEqual(len(f.calls),n)
        s.close()
