"""Source/process/root guards for native GameEvents Lua-state scopes."""
import threading
from types import SimpleNamespace as NS
import unittest
from unittest.mock import Mock, patch

from civ6_host.runtime import script_event_state as states


class ActiveEventStateTests(unittest.TestCase):
    def fixture(self, *, active=1, version=1, host_handle=0x5000):
        order = []

        def version_call():
            order.append("version")
            return version

        def query_call(root, state):
            order.append(("query", root, state))
            return active() if callable(active) else active

        native = NS(
            _handle=host_handle,
            LAB_GameEventsStateScopeVersion=Mock(side_effect=version_call),
            LAB_GameEventsStateIsActive=Mock(side_effect=query_call),
        )
        registry = NS(root=0x1000, closed=False, _check=Mock())
        runtime = NS(root=0x1000, registry=registry, host=native, closed=False)
        return NS(runtime=runtime, registry=registry, native=native, order=order)

    def owner(self, fixture):
        with patch.object(states, "COMPONENTS", {"game_events_state_scope.inc": "a" * 64}), \
             patch.object(states, "_current_executable", return_value="host.exe"), \
             patch.object(states, "_current_module_handle", return_value=0x5000), \
             patch.object(states, "verify_source_build", side_effect=lambda *a, **k: {
                 "host_sha256": "b" * 64, "native_compatibility_claimed": False
             }) as verify:
            owner = states.ActiveEventStates(fixture.runtime)
        return owner, verify

    def test_build_authentication_precedes_scope_version_and_state_query(self):
        f = self.fixture()
        with patch.object(states, "COMPONENTS", {"game_events_state_scope.inc": "a" * 64}), \
             patch.object(states, "_current_executable", side_effect=lambda: f.order.append("path") or "host.exe"), \
             patch.object(states, "_current_module_handle", side_effect=lambda: f.order.append("module") or 0x5000), \
             patch.object(states, "verify_source_build", side_effect=lambda *a, **k: f.order.append("source") or {
                 "host_sha256": "b" * 64
             }) as verify:
            owner = states.ActiveEventStates(f.runtime)
        self.assertEqual(f.order, ["path", "source", "module", "version"])
        self.assertEqual(verify.call_args.kwargs["required_components"],
                         {"game_events_state_scope.inc": "a" * 64})
        self.assertTrue(owner.accepts(0x2000))
        self.assertEqual(f.order[-1], ("query", 0x1000, 0x2000))

    def test_unsealed_components_refuse_before_source_verifier_or_native_query(self):
        f = self.fixture()
        with patch.object(states, "COMPONENTS", {}), \
             patch.object(states, "verify_source_build") as verify:
            with self.assertRaisesRegex(ValueError, "not been sealed"):
                states.ActiveEventStates(f.runtime)
        verify.assert_not_called()
        f.native.LAB_GameEventsStateScopeVersion.assert_not_called()
        f.native.LAB_GameEventsStateIsActive.assert_not_called()

    def test_source_preflight_failure_precedes_both_native_exports(self):
        f = self.fixture()
        with patch.object(states, "COMPONENTS", {"game_events_state_scope.inc": "a" * 64}), \
             patch.object(states, "_current_executable", return_value="host.exe"), \
             patch.object(states, "verify_source_build", side_effect=ValueError("unregistered source")):
            with self.assertRaisesRegex(ValueError, "unregistered source"):
                states.ActiveEventStates(f.runtime)
        f.native.LAB_GameEventsStateScopeVersion.assert_not_called()
        f.native.LAB_GameEventsStateIsActive.assert_not_called()

    def test_runtime_host_must_be_current_executable_before_query_exports(self):
        f = self.fixture(host_handle=0x5001)
        with patch.object(states, "COMPONENTS", {"game_events_state_scope.inc": "a" * 64}), \
             patch.object(states, "_current_executable", return_value="host.exe"), \
             patch.object(states, "_current_module_handle", return_value=0x5000), \
             patch.object(states, "verify_source_build", return_value={"host_sha256": "b" * 64}):
            with self.assertRaisesRegex(ValueError, "not the current executable"):
                states.ActiveEventStates(f.runtime)
        f.native.LAB_GameEventsStateScopeVersion.assert_not_called()
        f.native.LAB_GameEventsStateIsActive.assert_not_called()

    def test_wrong_root_or_runtime_owner_refuses_before_source_authentication(self):
        f = self.fixture()
        f.runtime.registry.root += 8
        with patch.object(states, "COMPONENTS", {"x": "y"}), \
             patch.object(states, "verify_source_build") as verify:
            with self.assertRaisesRegex(ValueError, "roots differ"):
                states.ActiveEventStates(f.runtime)
        verify.assert_not_called()

        f = self.fixture()
        f.runtime.closed = True
        with patch.object(states, "COMPONENTS", {"x": "y"}), \
             patch.object(states, "verify_source_build") as verify:
            with self.assertRaisesRegex(RuntimeError, "open runtime"):
                states.ActiveEventStates(f.runtime)
        verify.assert_not_called()

    def test_scope_version_must_match_and_query_is_never_cached(self):
        f = self.fixture(version=2)
        with patch.object(states, "COMPONENTS", {"x": "y"}), \
             patch.object(states, "_current_executable", return_value="host.exe"), \
             patch.object(states, "_current_module_handle", return_value=0x5000), \
             patch.object(states, "verify_source_build", return_value={"host_sha256": "b" * 64}):
            with self.assertRaisesRegex(ValueError, "ABI version"):
                states.ActiveEventStates(f.runtime)
        f.native.LAB_GameEventsStateIsActive.assert_not_called()

        responses = iter((1, 0))
        f = self.fixture(active=lambda: next(responses))
        owner, _ = self.owner(f)
        self.assertTrue(owner.accepts(0x2220))
        self.assertFalse(owner.accepts(0x2220))
        self.assertEqual(f.native.LAB_GameEventsStateIsActive.call_count, 2)

    def test_invalid_results_and_foreign_or_null_state_pointers_refuse(self):
        for result in (2, True, None):
            f = self.fixture(active=result)
            owner, _ = self.owner(f)
            with self.subTest(result=result), self.assertRaisesRegex(RuntimeError, "unknown result"):
                owner.accepts(0x2000)

        f = self.fixture(active=1)
        owner, _ = self.owner(f)
        for state in (None, 0, -1, True, 1 << 47, "0x2000"):
            with self.subTest(state=state), self.assertRaisesRegex(ValueError, "Lua state"):
                owner.accepts(state)
        f.native.LAB_GameEventsStateIsActive.assert_not_called()

    def test_each_query_rechecks_thread_root_host_runtime_and_registry(self):
        f = self.fixture(active=1)
        owner, _ = self.owner(f)
        owner.runtime.root += 8
        with self.assertRaisesRegex(RuntimeError, "root changed"):
            owner.accepts(0x2000)
        owner.runtime.root = owner.root

        owner.registry.root += 8
        with self.assertRaisesRegex(RuntimeError, "registry root changed"):
            owner.accepts(0x2000)
        owner.registry.root = owner.root

        owner.runtime.host = object()
        with self.assertRaisesRegex(RuntimeError, "host ownership changed"):
            owner.accepts(0x2000)
        owner.runtime.host = owner.native

        owner.native._handle += 8
        with self.assertRaisesRegex(RuntimeError, "host handle changed"):
            owner.accepts(0x2000)
        owner.native._handle -= 8

        owner.runtime.closed = True
        with self.assertRaisesRegex(RuntimeError, "runtime is closed"):
            owner.accepts(0x2000)
        owner.runtime.closed = False

        owner.registry._check.side_effect = RuntimeError("registry closed")
        with self.assertRaisesRegex(RuntimeError, "registry closed"):
            owner.accepts(0x2000)
        owner.registry._check.side_effect = None

        errors = []
        thread = threading.Thread(target=lambda: self._query_from_other_thread(owner, errors))
        thread.start()
        thread.join()
        self.assertEqual(len(errors),1)
        self.assertIn("another thread",errors[0])
        f.native.LAB_GameEventsStateIsActive.assert_not_called()

    @staticmethod
    def _query_from_other_thread(owner, errors):
        try:
            owner.accepts(0x2000)
        except RuntimeError as exc:
            errors.append(str(exc))

    def test_close_is_terminal_and_does_not_query_native_state(self):
        f = self.fixture(active=1)
        owner, _ = self.owner(f)
        owner.close()
        with self.assertRaisesRegex(RuntimeError, "owner is closed"):
            owner.accepts(0x2000)
        f.native.LAB_GameEventsStateIsActive.assert_not_called()


if __name__ == "__main__":
    unittest.main(verbosity=2)
