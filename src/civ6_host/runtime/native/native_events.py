"""Bounded event stream adapter for the SHA-pinned EXE9899b0 callback.

Names are hashed as raw UTF-16LE bytes; the registry uses the hash alone.
Payloads are written verbatim at reserved offsets. This is diagnostic hosting,
not game logic: unsupported/error paths stop instead of simulating success.
"""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import ctypes as C
from dataclasses import dataclass
from pathlib import Path
import threading
from civ6_host.runtime.native.native_logging import LogOverlapped

def event_name_hash(raw: bytes) -> int:
    """EXE9825b0 FNV-1a; caller hashes twice the wchar length, excluding NUL."""
    value = 2166136261
    for byte in raw:
        value = (value ^ byte) * 16777619 & 4294967295
    return value

@dataclass
class EventStream:
    name: str
    handle: int
    path: Path
    reserved: int = 0

class NativeEventRecorder:
    MAX_NAME_UNITS = 259
    MAX_PAYLOAD = 1024 * 1024
    MAX_STREAMS = 32
    MAX_TOTAL_BYTES = 16 * 1024 * 1024
    _installed = None

    def __init__(self, root, host):
        self.host = host
        self.root = _resolve_resource_path(_resolve_resource_path(Path(root))).resolve()
        work = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_events.py')))).resolve().parents[1] / 'work'
        if not self.root.is_relative_to(_resolve_resource_path(work).resolve()):
            raise ValueError('Native events must remain within project work')
        self.root.mkdir(exist_ok=False)
        self.streams = {}
        self.lock = threading.RLock()
        self.closed = False
        self.setter = None
        self.total_reserved = 0
        self.kernel = C.WinDLL('kernel32', use_last_error=True)
        for name, args, result in (('ReadProcessMemory', [C.c_void_p, C.c_void_p, C.c_void_p, C.c_size_t, C.POINTER(C.c_size_t)], C.c_int), ('CreateFileW', [C.c_wchar_p, C.c_uint32, C.c_uint32, C.c_void_p, C.c_uint32, C.c_uint32, C.c_void_p], C.c_void_p), ('GetFileSizeEx', [C.c_void_p, C.POINTER(C.c_int64)], C.c_int), ('WriteFile', [C.c_void_p, C.c_void_p, C.c_uint32, C.POINTER(C.c_uint32), C.c_void_p], C.c_int), ('CloseHandle', [C.c_void_p], C.c_int), ('GetModuleHandleW', [C.c_wchar_p], C.c_void_p), ('GetProcAddress', [C.c_void_p, C.c_char_p], C.c_void_p)):
            function = getattr(self.kernel, name)
            function.argtypes = args
            function.restype = result

    def install(self):
        module = self.kernel.GetModuleHandleW(None)
        address = self.kernel.GetProcAddress(module, b'EXP_SetLogEventCallback')
        if not address or self.setter is not None or NativeEventRecorder._installed is not None:
            raise RuntimeError('Event recorder requires its compiled setter and single installation')
        self.setter = C.CFUNCTYPE(None, C.c_void_p)(address)
        self.callback = C.CFUNCTYPE(None, C.c_void_p, C.c_void_p, C.c_uint32)(self._guarded)
        self.host.functions.append(self.callback)
        self.setter(C.cast(self.callback, C.c_void_p).value)
        NativeEventRecorder._installed = self
        self.host.emit('native_event_recorder_installed', root=str(self.root), capacity=self.MAX_STREAMS)

    def _guarded(self, name, payload, size):
        try:
            self.receive(name, payload, size)
        except BaseException as exc:
            self.host._fatal('native event callback failed', error=repr(exc))

    def _read(self, pointer, length):
        if not length:
            return b''
        out = C.create_string_buffer(length)
        copied = C.c_size_t()
        if not self.kernel.ReadProcessMemory(C.c_void_p(-1), pointer, out, length, C.byref(copied)) or copied.value != length:
            self.host._fatal('unreadable native event input', pointer=pointer, length=length)
        return out.raw

    def _name(self, pointer):
        raw = bytearray()
        for index in range(self.MAX_NAME_UNITS + 1):
            unit = self._read(pointer + 2 * index, 2)
            if unit == b'\x00\x00':
                return (bytes(raw), raw.decode('utf-16-le', errors='surrogatepass'))
            raw.extend(unit)
        self.host._fatal('native event name exceeds diagnostic limit')

    def _open(self, name):
        if not name or _resolve_resource_path(Path(name)).name != name or any((c in name for c in '/\\:')) or (name in ('.', '..')):
            self.host._fatal('unverified native event filename', name=name)
        path = self.root / name
        win32_path = str(path)
        path_units = len(win32_path.encode('utf-16-le', errors='surrogatepass')) // 2
        if path_units >= 260 and not win32_path.startswith('\\\\?\\'):
            if win32_path.startswith('\\\\'):
                win32_path = '\\\\?\\UNC\\' + win32_path[2:]
            else:
                win32_path = '\\\\?\\' + win32_path
        if Path(win32_path).exists():
            self.host._fatal('native event file already exists', name=name)
        handle = self.kernel.CreateFileW(win32_path, 1073741824, 1, None, 2, 134217856, None)
        if handle in (None, C.c_void_p(-1).value):
            self.host._fatal('native event open failed', name=name, error=C.get_last_error(),
                             path_utf16_units=path_units)
        size = C.c_int64()
        if not self.kernel.GetFileSizeEx(handle, C.byref(size)) or size.value:
            self.kernel.CloseHandle(handle)
            self.host._fatal('native event initial size failed', name=name)
        return EventStream(name, handle, path)

    def receive(self, name_pointer, payload_pointer, size):
        if not name_pointer:
            return
        with self.lock:
            if self.closed:
                self.host._fatal('native event after recorder shutdown')
            raw, name = self._name(name_pointer)
            key = event_name_hash(raw)
            if key == 0:
                self.host._fatal('unverified zero-hash event record', name=name)
            entry = self.streams.get(key)
            if entry is None:
                if len(self.streams) == self.MAX_STREAMS:
                    self.host.emit('native_event_capacity_drop', name=name, name_hash=hex(key))
                    return
                entry = self._open(name)
                self.streams[key] = entry
                self.host.emit('native_event_file_opened', name=name, name_hash=hex(key), path=str(entry.path))
            if not 0 <= size <= self.MAX_PAYLOAD:
                self.host._fatal('native event payload exceeds diagnostic limit', size=size)
            if self.total_reserved + size > self.MAX_TOTAL_BYTES:
                self.host._fatal('native event stream total exceeds diagnostic limit')
            data = self._read(payload_pointer, size) if payload_pointer else b''
            offset = entry.reserved
            entry.reserved += size
            self.total_reserved += size
            if entry.reserved > 18446744073709551615:
                self.host._fatal('native event offset overflow')
            overlapped = LogOverlapped(0, 0, offset & 4294967295, offset >> 32, None)
            written = C.c_uint32()
            if not self.kernel.WriteFile(entry.handle, data, len(data), C.byref(written), C.byref(overlapped)) or written.value != len(data):
                self.host._fatal('native event write failed', name=name, error=C.get_last_error())
            self.host.emit('native_event_written', name=name, stream_name=entry.name, name_hash=hex(key), path=str(entry.path), offset=offset, reserved_bytes=size, written_bytes=len(data), payload_hex=data.hex())

    def close(self):
        with self.lock:
            if self.setter is not None:
                self.setter(None)
                self.setter = None
                NativeEventRecorder._installed = None
            for entry in self.streams.values():
                if not self.kernel.CloseHandle(entry.handle):
                    self.host._fatal('native event close failed', name=entry.name)
                self.host.emit('native_event_file_closed', name=entry.name, path=str(entry.path))
            self.streams.clear()
            self.closed = True
