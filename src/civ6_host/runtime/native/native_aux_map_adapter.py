"""Python owner for the isolated AUX+A8 native map snapshot callback.

The callback only copies and validates native ParameterMap data. It never calls
HKS; the C bridge applies the returned bounded opcode buffer after Python has
returned. This is diagnostic transport, not a gameplay mutation API.
"""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import ctypes as C
from collections import Counter
import threading
from typing import Any
from civ6_host.runtime.native.native_aux_map_conversion import PROOF_SHA256
from civ6_host.runtime.native.native_aux_map_conversion import LIST_PROOF_SHA256
from civ6_host.runtime.native.native_aux_map_conversion import STRING_PROOF_SHA256
from civ6_host.runtime.native.native_aux_map_conversion import ARRAY_PROOF_SHA256
from civ6_host.runtime.native.native_aux_map_conversion import STRING_KEYS_PROOF_SHA256
from civ6_host.runtime.native.native_aux_map_conversion import snapshot_parameter_map

class AuxMapOp(C.Structure):
    _fields_ = [('kind', C.c_uint32), ('arg', C.c_uint32), ('payload', C.c_uint64)]
SnapshotCallback = C.CFUNCTYPE(C.c_int, C.c_void_p, C.c_void_p, C.c_void_p, C.c_ubyte, C.POINTER(C.c_void_p), C.POINTER(C.c_uint32))

def _pointer_value(value: Any, label: str) -> int:
    if isinstance(value, C.c_void_p):
        result = value.value
    elif type(value) is int:
        result = value
    else:
        raise TypeError(f'{label} must be a native pointer')
    if result is None or type(result) is not int or (not 0 < result < 1 << 63):
        raise ValueError(f'{label} must be a non-null user-space pointer')
    return result

class NativeAuxMapAdapter:
    """Install/uninstall the Python snapshot callback consumed by AUX+A8.

    ``owner_pointer`` is the opaque owner token passed to ``LAB_AuxMapInstall``
    and later by ``LAB_AuxPushMap``. It must be stable for this adapter's life.
    ``read`` is an injectable checked native-memory reader for tests; production
    defaults to ``native_setup.local_reader``.
    """

    def __init__(self, host, runtime, core, owner_pointer, emit, *, read=None, core_sha256='d7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3', allow_nested_maps=False, state_validator=None, on_refusal=None):
        from civ6_host.runtime.aux_map_profiles import profile_for_sha
        self.map_abi = profile_for_sha(core_sha256)
        self.core_sha256 = core_sha256
        if type(allow_nested_maps) is not bool:
            raise ValueError('Nested map adapter option must be Boolean')
        self.allow_nested_maps = allow_nested_maps
        if state_validator is not None and (not callable(state_validator)):
            raise TypeError('AUX state validator must be callable')
        if on_refusal is not None and (not callable(on_refusal)):
            raise TypeError('AUX refusal handler must be callable')
        self.state_validator = state_validator
        self.on_refusal = on_refusal
        self.transport_version = 1
        self.host = host
        self.runtime = runtime
        self.core = core
        self.owner_pointer = _pointer_value(owner_pointer, 'AUX owner')
        self.emit = emit
        if read is None:
            from civ6_host.runtime.native.native_setup import local_reader
            read = local_reader()
        if not callable(read):
            raise TypeError('checked native reader must be callable')
        self.read = read
        self._lock = threading.RLock()
        self._buffer = None
        self._callback = SnapshotCallback(self._snapshot_callback)
        self._installed = False
        self._closed = False

    def _emit(self, event, **fields):
        try:
            self.emit(event, **fields)
        except Exception:
            pass

    def install(self):
        with self._lock:
            if self._closed:
                raise RuntimeError('AUX map adapter is closed')
            if self._installed:
                raise RuntimeError('AUX map callback is already installed')
            from civ6_host.runtime.aux_map_profiles import verify_live
            verify_live(self.map_abi, self.core._handle, self.read)
            if hasattr(self.host, 'LAB_AuxMapTransportVersion'):
                version = self.host.LAB_AuxMapTransportVersion
                version.argtypes, version.restype = ([], C.c_int)
                self.transport_version = version()
                if self.transport_version != 2:
                    raise ValueError('Unknown exported AUX map transport version')
            if self.allow_nested_maps and self.transport_version != 2:
                raise ValueError('Nested map adapter requires native V2 transport')
            install = self.host.LAB_AuxMapInstall
            install.argtypes = [C.c_void_p, SnapshotCallback]
            install.restype = C.c_int
            status = install(C.c_void_p(self.owner_pointer), self._callback)
            if status != 1:
                raise RuntimeError('Native AUX map callback installation refused')
            self._installed = True
            self._emit('native_aux_map_callback_installed', core_sha256=self.core_sha256, transport_version=self.transport_version, layout_source_sha256=self.map_abi.source_sha256, callback_abi='owner,state,map,uint8_names,out,count', source_proof_sha256=PROOF_SHA256, list_source_proof_sha256=LIST_PROOF_SHA256, string_source_proof_sha256=STRING_PROOF_SHA256, array_source_proof_sha256=ARRAY_PROOF_SHA256, hks_calls_in_python_callback=False)

    def close(self):
        """Unregister native callback before releasing its retained C buffer."""
        with self._lock:
            if self._closed:
                return
            if self._installed:
                install = self.host.LAB_AuxMapInstall
                install.argtypes = [C.c_void_p, SnapshotCallback]
                install.restype = C.c_int
                status = install(None, C.cast(None, SnapshotCallback))
                if status != 1:
                    raise RuntimeError('Native AUX map callback unregistration refused')
                self._installed = False
            self._buffer = None
            self._callback = None
            self._closed = True
            self._emit('native_aux_map_callback_closed', buffer_released_after_uninstall=True)

    def _snapshot_callback(self, aux, state, map_pointer, names, out_pointer, count_pointer):
        """ctypes ABI. Return 1 only with a fully validated retained snapshot."""
        with self._lock:
            if out_pointer:
                out_pointer[0] = None
            if count_pointer:
                count_pointer[0] = 0
            try:
                if self._closed or not self._installed:
                    raise RuntimeError('AUX map adapter is not active')
                if _pointer_value(aux, 'AUX callback owner') != self.owner_pointer:
                    raise ValueError('AUX callback owner mismatch')
                state_pointer = _pointer_value(state, 'HKS state')
                registry = getattr(self.runtime, 'registry', None)
                contexts = getattr(registry, 'contexts', None)
                if not isinstance(contexts, dict):
                    raise RuntimeError('Script runtime has no active context registry')
                context = contexts.get(state_pointer)
                if context is None:
                    if self.state_validator is None or self.state_validator(state_pointer) is not True:
                        raise ValueError('AUX callback HKS state is not an active runtime child or event frame')
                elif registry.validate(context) != state_pointer:
                    raise ValueError('AUX callback HKS state is not an active runtime child')
                if type(names) is not int or not 0 <= names <= 255:
                    raise ValueError('AUX map names selector is outside uint8')
                if not out_pointer or not count_pointer:
                    raise ValueError('AUX map output pointers are null')
                core_base = _pointer_value(getattr(self.core, '_handle', None), 'GameCore module base')
                pointer = _pointer_value(map_pointer, 'native ParameterMap')
                snapshot = snapshot_parameter_map(core_base, pointer, self.read, use_string_keys=bool(names), core_sha256=self.core_sha256, transport_version=self.transport_version, allow_nested_maps=self.allow_nested_maps)
                raw = snapshot.transport
                if type(raw) is not bytes or not raw or len(raw) % C.sizeof(AuxMapOp):
                    raise ValueError('AUX map conversion returned malformed opcode bytes')
                if len(raw) // C.sizeof(AuxMapOp) > 262144:
                    raise ValueError('AUX map conversion exceeded native operation bound')
                storage = C.create_string_buffer(raw, len(raw))
                address = C.addressof(storage)
                self._buffer = storage
                out_pointer[0] = C.c_void_p(address)
                count_pointer[0] = len(raw) // C.sizeof(AuxMapOp)
                self._emit('native_aux_map_snapshot_ready', field_count=int(snapshot.field_count), operation_count=int(count_pointer[0]), source_bytes_read=int(snapshot.source_bytes_read), transport_bytes=len(raw), variant_type_count=len(snapshot.variant_types), variant_tag_counts={hex(tag): count for tag, count in sorted(Counter((tag for tag, _, _ in snapshot.variant_types)).items())}, source_proof_sha256=PROOF_SHA256, list_source_proof_sha256=LIST_PROOF_SHA256, string_source_proof_sha256=STRING_PROOF_SHA256, array_source_proof_sha256=ARRAY_PROOF_SHA256, string_keys=bool(names), string_key_source_proof_sha256=STRING_KEYS_PROOF_SHA256 if names else None, hks_calls_in_python_callback=False)
                return 1
            except Exception as exc:
                self._emit('native_aux_map_snapshot_refused', reason=str(exc)[:256], hks_calls_in_python_callback=False, fallback_used=False)
                if self.on_refusal is not None:
                    self.on_refusal(str(exc)[:256])
                return 0

    def __enter__(self):
        self.install()
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()
        return False
