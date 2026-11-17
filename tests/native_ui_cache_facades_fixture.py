from __future__ import annotations

import unittest

from civ6_host.runtime.native.native_ui_cache_facades import (
    CACHE_B0_RESULT_VTABLE_RVA,
    CACHE_C0_RESULT_VTABLE_RVA,
    CACHE_SERVICE_VTABLE_RVA,
    GAME_FACADE_VTABLE_RVA,
    NativeUiCacheFacades,
    OUTER_VTABLE_RVA,
    OUTPUT_CANARY_START,
    OUTPUT_SIZE,
    SYSTEM_FACADE_VTABLE_RVA,
    TARGET_RVAS,
    EVIDENCE_PATH,
    EVIDENCE_SHA256,
    _verify_evidence_bytes,
    _verify_static_evidence,
)
from pathlib import Path
from civ6_host.runtime.paths import resource_root

# Static evidence stays a private data resource after this test is extracted.
EVIDENCE_PATH = resource_root() / EVIDENCE_PATH


class FakeBackend:
    core_base = 0x180000000

    def __init__(self, *, overrun=False, invalid_b0=False):
        self.overrun = overrun
        self.invalid_b0 = invalid_b0
        self.alive = True
        self.memory = {}
        self.calls = []
        self.gates = []
        self.b0_results = [0x5000, 0x5100]
        self.c0_results = [0x6000, 0x6100]
        self.objects = {
            0x1000: OUTER_VTABLE_RVA,
            0x2000: GAME_FACADE_VTABLE_RVA,
            0x3000: CACHE_SERVICE_VTABLE_RVA,
            0x4000: SYSTEM_FACADE_VTABLE_RVA,
            0x5000: CACHE_B0_RESULT_VTABLE_RVA,
            0x5100: CACHE_B0_RESULT_VTABLE_RVA,
            0x6000: CACHE_C0_RESULT_VTABLE_RVA,
            0x6100: CACHE_C0_RESULT_VTABLE_RVA,
            0x7000: 0x123456,
        }
        for ptr, vtable_rva in self.objects.items():
            self.memory[ptr] = self.core_base + vtable_rva
        for (vtable_rva, slot), target_rva in TARGET_RVAS.items():
            self.memory[self.core_base + vtable_rva + slot] = self.core_base + target_rva

    def read_qword(self, address):
        try:
            return self.memory[address]
        except KeyError as exc:
            raise ValueError(f"unmapped qword {address:#x}") from exc

    def context_alive(self):
        return self.alive

    def set_public_cache_gate(self, enabled):
        self.gates.append(bool(enabled))
        self.calls.append(("gate", bool(enabled)))

    def call(self, target, *args):
        self.calls.append((target, *args))
        r = lambda vtable, slot: self.core_base + TARGET_RVAS[(vtable, slot)]
        if target == r(OUTER_VTABLE_RVA, 0xA0):
            return 0x2000
        if target == r(OUTER_VTABLE_RVA, 0xB0):
            return 0x3000 if not self.invalid_b0 else 0x7000
        if target == r(OUTER_VTABLE_RVA, 0xD0):
            return 0x4000
        if target == r(GAME_FACADE_VTABLE_RVA, 0x38):
            assert args == (0x2000, 1)
            return None
        if target == r(CACHE_SERVICE_VTABLE_RVA, 0xE8):
            _, output = args
            assert len(output) >= OUTPUT_SIZE
            output[:0x1C] = bytes(range(0x1C))
            if self.overrun:
                output[OUTPUT_CANARY_START] ^= 0xFF
            return 0x11223344
        if target == r(CACHE_SERVICE_VTABLE_RVA, 0xB0):
            result = self.b0_results.pop(0)
            return result
        if target == r(CACHE_SERVICE_VTABLE_RVA, 0xC0):
            result = self.c0_results.pop(0)
            return result
        if target in {
            r(OUTER_VTABLE_RVA, 0x8),
            r(GAME_FACADE_VTABLE_RVA, 0x8),
            r(CACHE_SERVICE_VTABLE_RVA, 0x8),
            r(SYSTEM_FACADE_VTABLE_RVA, 0x8),
            r(CACHE_B0_RESULT_VTABLE_RVA, 0x8),
            r(CACHE_C0_RESULT_VTABLE_RVA, 0x8),
        }:
            return 0
        raise AssertionError(f"unexpected native call target {target:#x}")


class TestNativeUiCacheFacades(unittest.TestCase):
    def test_construction_evidence_is_content_addressed_and_image_pinned(self):
        report = _verify_static_evidence()
        self.assertEqual(report["schema"], "civ6rl.native_ui_cache_facades.static.v1")
        self.assertEqual(Path(EVIDENCE_PATH).name, EVIDENCE_SHA256 + ".json")
        raw = (Path(__file__).resolve().parents[1] / EVIDENCE_PATH).read_bytes()
        with self.assertRaisesRegex(RuntimeError, "hash mismatch"):
            _verify_evidence_bytes(raw + b" ")

    def test_refresh_and_close_follow_pinned_order_and_preserve_canary(self):
        backend = FakeBackend()
        facades = NativeUiCacheFacades(backend, 0x1000)
        result = facades.refresh()
        self.assertEqual(result.copied_value, 0x11223344)
        self.assertEqual(result.output, bytes(range(0x1C)))
        self.assertEqual(backend.gates, [True])

        facades.close()
        self.assertEqual(backend.gates, [True, False])
        targets = [event[0] for event in backend.calls]
        self.assertLess(
            targets.index(backend.core_base + TARGET_RVAS[(GAME_FACADE_VTABLE_RVA, 0x38)]),
            targets.index(backend.core_base + TARGET_RVAS[(CACHE_SERVICE_VTABLE_RVA, 0xE8)]))
        releases = [event[1] for event in backend.calls if event[0] in {
            backend.core_base + TARGET_RVAS[(CACHE_B0_RESULT_VTABLE_RVA, 0x8)],
            backend.core_base + TARGET_RVAS[(CACHE_C0_RESULT_VTABLE_RVA, 0x8)],
            backend.core_base + TARGET_RVAS[(GAME_FACADE_VTABLE_RVA, 0x8)],
            backend.core_base + TARGET_RVAS[(CACHE_SERVICE_VTABLE_RVA, 0x8)],
            backend.core_base + TARGET_RVAS[(SYSTEM_FACADE_VTABLE_RVA, 0x8)],
        }]
        self.assertEqual(releases, [0x5000, 0x6000, 0x2000, 0x3000, 0x4000])
        self.assertNotIn((backend.core_base + TARGET_RVAS[(OUTER_VTABLE_RVA, 0x8)], 0x1000), backend.calls)
        facades.close()  # idempotent, no second releases

    def test_rejects_copy_past_proven_extent_and_still_releases(self):
        backend = FakeBackend(overrun=True)
        facades = NativeUiCacheFacades(backend, 0x1000)
        with self.assertRaisesRegex(BufferError, "past its proven"):
            facades.refresh()
        facades.close()
        self.assertEqual(backend.gates, [False])
        self.assertFalse(facades.game_facade)
        self.assertFalse(facades.outer)

    def test_second_refresh_releases_previous_result_references_after_replacement(self):
        backend = FakeBackend()
        facades = NativeUiCacheFacades(backend, 0x1000)
        facades.refresh()
        facades.refresh()
        b0_release = backend.core_base + TARGET_RVAS[(CACHE_B0_RESULT_VTABLE_RVA, 0x8)]
        c0_release = backend.core_base + TARGET_RVAS[(CACHE_C0_RESULT_VTABLE_RVA, 0x8)]
        self.assertIn((b0_release, 0x5000), backend.calls)
        self.assertIn((c0_release, 0x6000), backend.calls)
        self.assertEqual((facades.cache_b0_result, facades.cache_c0_result), (0x5100, 0x6100))
        facades.close()
        self.assertIn((b0_release, 0x5100), backend.calls)
        self.assertIn((c0_release, 0x6100), backend.calls)

    def test_rejects_unexpected_returned_facade_without_calling_unknown_release(self):
        backend = FakeBackend(invalid_b0=True)
        with self.assertRaisesRegex(ValueError, "B0 cache service"):
            NativeUiCacheFacades(backend, 0x1000)
        # Known A0 is released; unknown B0 and borrowed outer are not released.
        releases = [event[1] for event in backend.calls if isinstance(event[0], int) and
                    event[0] == backend.core_base + TARGET_RVAS[(GAME_FACADE_VTABLE_RVA, 0x8)]]
        self.assertEqual(releases, [0x2000])

    def test_refuses_changed_static_vtable_slot_before_facade_calls(self):
        backend = FakeBackend()
        backend.memory[backend.core_base + OUTER_VTABLE_RVA + 0xD0] ^= 8
        with self.assertRaisesRegex(ValueError, "slot changed"):
            NativeUiCacheFacades(backend, 0x1000)
        self.assertFalse(backend.calls)

    def test_dead_root_context_blocks_init_refresh_and_close_native_calls(self):
        backend = FakeBackend()
        facades = NativeUiCacheFacades(backend, 0x1000)
        facades.refresh()
        call_count = len(backend.calls)
        backend.alive = False
        with self.assertRaisesRegex(RuntimeError, "not alive"):
            facades.refresh()
        self.assertEqual(len(backend.calls), call_count)
        with self.assertRaisesRegex(RuntimeError, "not alive"):
            facades.close()
        self.assertEqual(len(backend.calls), call_count)
        self.assertTrue(facades._closed)


if __name__ == "__main__":
    unittest.main()
