"""Guard GameEvents state pointers against foreign and stale HKS threads.

The native state query recognizes frames scoped around a synchronous
GameEvents Call/TestAll. This Python owner validates process, root, thread and
pointer shape before asking the source-pinned native helper; it never caches a
positive state result.
"""
from __future__ import annotations

import ctypes as C
import threading

from .source_build_identity import verify_source_build


# The owning native manifest/build will seal these component digests. Keep the
# empty state fail-closed until that exact source identity is supplied.
COMPONENTS: dict[str, str] = {'script_game_events_full_legacy.inc': '228b8679a930eb180990ce92e1237d35cf98337298c04c9c6a4f06bd03b41e69', 'script_aux_a0_legacy.inc': 'ebb8d1ae93cb737037aae18975f56af39423d843c016c272ac71398ea20a4b67', 'script_aux_a0.inc': '3f961c1b74b06cdad7091e4e6240f71f19e75837d754d3f554623f1c4e99a5fa', 'script_aux_a8.inc': 'a31eee3b17833265a43cbd57a193adf59ec538baf6b4a133ee1a34970b6402e1', 'script_game_events_full.inc': 'bf720cb18e4b032cb5aa90d0b8987c351a98424259b0fcf333a94cb88c7ad655', 'script_event_state_scope.inc': 'cc882df725189f7e83a0f06bf43f3ff6d1395e0ba52d76871413a20b423b474a', 'script_event_state_diagnostic.inc': '0bb560c5d3a0e6c9283e9d0833f1d5f65db8ed45230faa1fc46b725a2d845cec'}
SCOPE_VERSION = 1
MAX_USER_POINTER = 1 << 47


def _current_executable():
    from .profile_script_binding import _current_executable as current_executable

    return current_executable()


def _current_module_handle():
    kernel = C.WinDLL("kernel32", use_last_error=True)
    function = kernel.GetModuleHandleW
    function.argtypes, function.restype = [C.c_wchar_p], C.c_void_p
    handle = function(None)
    if not handle:
        raise RuntimeError("Current native host module is unavailable")
    return int(handle)


def _pointer(value, label: str) -> int:
    if isinstance(value, C.c_void_p):
        value = value.value
    if type(value) is not int or not 0 < value < MAX_USER_POINTER:
        raise ValueError(f"{label} is not a bounded native pointer")
    return value


class ActiveEventStates:
    """Query whether a Lua state is active in this root's current event frame."""

    def __init__(self, runtime):
        if not COMPONENTS:
            raise ValueError("GameEvents state native components have not been sealed")
        registry = getattr(runtime, "registry", None)
        if registry is None or not callable(getattr(registry, "_check", None)):
            raise ValueError("GameEvents state owner requires a live thread registry")
        registry._check()
        if getattr(runtime, "closed", True) or getattr(registry, "closed", False):
            raise RuntimeError("GameEvents state owner requires an open runtime")
        root = _pointer(getattr(runtime, "root", None), "Lua root")
        registry_root = _pointer(getattr(registry, "root", None), "registry root")
        if root != registry_root:
            raise ValueError("GameEvents state runtime and registry roots differ")
        native = getattr(runtime, "host", None)
        if native is None:
            raise ValueError("GameEvents state owner lacks its native host")

        # Bind provenance before touching native query exports. This includes
        # the current host executable and the exact components in its build.
        self.native_build = verify_source_build(
            _current_executable(), required_components=dict(COMPONENTS)
        )
        current_module = _current_module_handle()
        if getattr(native, "_handle", None) != current_module:
            raise ValueError("GameEvents state native host is not the current executable")

        version = getattr(native, "LAB_GameEventsStateScopeVersion", None)
        query = getattr(native, "LAB_GameEventsStateIsActive", None)
        if not callable(version) or not callable(query):
            raise ValueError("Native GameEvents state-scope exports are unavailable")
        version.argtypes, version.restype = [], C.c_uint32
        version_result = version()
        if type(version_result) is not int or version_result != SCOPE_VERSION:
            raise ValueError("Unsupported GameEvents state-scope ABI version")
        query.argtypes, query.restype = [C.c_void_p, C.c_void_p], C.c_uint32

        self.runtime = runtime
        self.registry = registry
        self.native = native
        self.host_handle = current_module
        self.root = root
        self.owner_thread = threading.get_ident()
        self.query = query
        self.closed = False

    def _check(self):
        if self.closed:
            raise RuntimeError("GameEvents state owner is closed")
        if threading.get_ident() != self.owner_thread:
            raise RuntimeError("GameEvents state owner belongs to another thread")
        self.registry._check()
        if getattr(self.runtime, "closed", True):
            raise RuntimeError("GameEvents state runtime is closed")
        if getattr(self.runtime, "registry", None) is not self.registry:
            raise RuntimeError("GameEvents state registry ownership changed")
        if getattr(self.runtime, "host", None) is not self.native:
            raise RuntimeError("GameEvents state native host ownership changed")
        if getattr(self.native, "_handle", None) != self.host_handle:
            raise RuntimeError("GameEvents state native host handle changed")
        if _pointer(getattr(self.runtime, "root", None), "Lua root") != self.root:
            raise RuntimeError("GameEvents state root changed")
        if _pointer(getattr(self.registry, "root", None), "registry root") != self.root:
            raise RuntimeError("GameEvents registry root changed")

    def accepts(self, state) -> bool:
        """Return true only while native code marks state in this root's frame."""
        self._check()
        state_pointer = _pointer(state, "Lua state")
        result = self.query(self.root, state_pointer)
        if type(result) is not int or result not in (0, 1):
            raise RuntimeError("Native GameEvents state query returned an unknown result")
        # Deliberately query every time. A Call/TestAll frame ends immediately
        # when the native protected invocation returns, including error paths.
        return result == 1

    def close(self):
        self._check()
        self.closed = True
