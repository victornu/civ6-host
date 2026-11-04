"""Source-backed log writers with a bounded, opt-in native printf/file bridge.

EXE 15abd0 returns a registered channel's writer even when opening it returned
false because logging was disabled. Returning NULL for that case is incorrect.
Inactive writers preserve the early returns. Active diagnostic writers support
new private files with source-verified flags 0 or 5, literal text / %% / bare
%d and %s, and the exact native production-log conversion %3.1f.
Unknown methods, configurations and formats stop the worker explicitly.
"""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import ctypes as C
from pathlib import Path
import threading

class DisabledLogWriters:

    def __init__(self, host):
        self.host = host
        self.objects = {}
        self.channels_by_pointer = {}
        self.active_sink = None
        self.locks = {}
        self.vtable = (C.c_void_p * 32)()
        for index in range(len(self.vtable)):
            host._bind(self.vtable, index * 8, None, [C.c_void_p], host._unsupported('log writer', index * 8))
        for slot in (16, 24, 32):
            host._bind(self.vtable, slot, None, [C.c_void_p, C.c_void_p], self._write_callback(slot))
        host._bind(self.vtable, 56, C.c_uint32, [C.c_void_p], self.enabled)
        host._bind(self.vtable, 64, C.c_uint32, [C.c_void_p, C.c_uint8], self.set_enabled)

    def _channel(self, this):
        if this not in self.channels_by_pointer:
            self.host._fatal('unverified log writer pointer', pointer=this)
        return self.channels_by_pointer[this]

    def lookup(self, this, channel):
        if this != C.addressof(self.host.logger_object):
            self.host._fatal('unverified logger writer-lookup arguments')
        entry = self.host.log_channels.get(channel)
        if not self.host.log_global_enabled or entry is None:
            self.host.emit('host_log_writer_absent', channel=hex(channel), reason='global_disabled' if not self.host.log_global_enabled else 'missing_channel')
            return None
        if entry['enabled'] and self.active_sink is None:
            self.host._fatal('enabled log writer requires file sink', channel=hex(channel))
        if channel not in self.objects:
            obj = (C.c_void_p * 3)(C.addressof(self.vtable), getattr(self, 'gate_pointer', None), getattr(self, 'sink_pointer', None))
            self.objects[channel] = obj
            self.channels_by_pointer[C.addressof(obj)] = channel
            self.locks[channel] = threading.RLock()
        pointer = C.addressof(self.objects[channel])
        if entry['enabled']:
            with self.locks[channel]:
                opened = _resolve_resource_path(self.active_sink).open(channel, entry)
                if opened:
                    header = self.host.log_headers.get(channel)
                    if header:
                        if b'%' in header.replace(b'%%', b''):
                            self.host._fatal('unverified variadic log header', channel=hex(channel))
                        storage = C.create_string_buffer(header)
                        C.CFUNCTYPE(None, C.c_void_p, C.c_void_p)(self.vtable[2])(pointer, C.addressof(storage))
            self.host.emit('host_log_writer_active', channel=hex(channel), pointer=pointer)
            return pointer
        self.host.emit('host_log_writer_inactive', channel=hex(channel), pointer=pointer, native_open_result=False, pointer_is_null=False)
        return pointer

    def _write_callback(self, slot):

        def callback(this, text):
            self.write(this, text, slot)
        return callback

    def write(self, this, text, slot):
        if slot not in (16, 24, 32):
            self.host._fatal('unverified log writer method', slot=hex(slot))
        channel = self._channel(this)
        enabled = self.host.log_channels[channel]['enabled']
        if self.host.log_global_enabled and enabled and text:
            self.host._fatal('enabled log writer requires file sink', channel=hex(channel), slot=hex(slot))
        reason = 'global_disabled' if not self.host.log_global_enabled else 'channel_disabled' if not enabled else 'null_text'
        self.host.emit('host_log_writer_early_return', channel=hex(channel), slot=hex(slot), reason=reason, input_dereferenced=False)

    def enabled(self, this):
        channel = self._channel(this)
        value = self.host.log_channels[channel]['enabled']
        self.host.emit('host_log_writer_enabled', channel=hex(channel), enabled_byte=value)
        return value

    def set_enabled(self, this, value):
        channel = self._channel(this)
        entry = self.host.log_channels[channel]
        previous = entry['enabled']
        entry['enabled'] = int(value)
        self.host.emit('host_log_writer_enable', channel=hex(channel), previous_byte=previous, enabled_byte=int(value))
        return previous

    def enable_native_sink(self, root):
        """Install the compiled variadic bridge, only for a fresh private root."""
        if self.objects or self.active_sink is not None:
            raise RuntimeError('Install native log sink before exposing writer objects')
        kernel = C.WinDLL('kernel32', use_last_error=True)
        kernel.GetModuleHandleW.argtypes, kernel.GetModuleHandleW.restype = ([C.c_wchar_p], C.c_void_p)
        kernel.GetProcAddress.argtypes, kernel.GetProcAddress.restype = ([C.c_void_p, C.c_char_p], C.c_void_p)
        module = kernel.GetModuleHandleW(None)
        bridges = {slot: kernel.GetProcAddress(module, name) for slot, name in ((16, b'LAB_LogPrintf10'), (24, b'LAB_LogText18'), (32, b'LAB_LogPrintf20'))}
        if not all(bridges.values()):
            raise RuntimeError('Native log sink requires the compiled variadic bridge')
        gate = C.CFUNCTYPE(C.c_int, C.c_void_p, C.c_void_p, C.c_uint32)(self._active_gate)
        sink = C.CFUNCTYPE(None, C.c_void_p, C.c_void_p, C.c_size_t, C.c_uint32)(self._active_write)
        self.host.functions.extend((gate, sink))
        self.gate_pointer = C.cast(gate, C.c_void_p).value
        self.sink_pointer = C.cast(sink, C.c_void_p).value
        self.active_sink = PrivateLogFiles(root, self.host)
        for slot, address in bridges.items():
            self.vtable[slot // 8] = address

    def _active_gate(self, this, text, slot):
        try:
            channel = self._channel(this)
            if not self.host.log_global_enabled or not self.host.log_channels[channel]['enabled'] or (not text):
                self.write(this, text, slot)
                return 0
            if channel not in self.active_sink.handles:
                self.host._fatal('active log writer has no open file', channel=hex(channel))
            base = getattr(self.host, 'core_base', 0)
            self.host.emit('host_log_writer_request', channel=hex(channel), slot=hex(slot), text_pointer=text, core_text_rva=hex(text - base) if base and base <= text < base + 9826304 else None)
            self.locks[channel].acquire()
            return 1
        except BaseException as exc:
            self.host._fatal('log gate failed', error=str(exc))

    def _active_write(self, this, text, length, slot):
        channel = self._channel(this)
        try:
            data = C.string_at(text, length)
            self.active_sink.write(channel, data)
            self.host.emit('host_log_writer_output', channel=hex(channel), slot=hex(slot), message_hex=data.hex(), message_bytes=length)
        except BaseException as exc:
            self.host._fatal('log sink failed', error=str(exc))
        finally:
            self.locks[channel].release()

    def close(self):
        if self.active_sink is not None:
            self.active_sink.close()

class PrivateLogFiles:
    """Source-backed successful file path; failures abort this diagnostic."""

    def __init__(self, root, host):
        self.root = _resolve_resource_path(_resolve_resource_path(Path(root))).resolve()
        work = _resolve_resource_path(_resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_logging.py')))).resolve().parents[1] / 'work').resolve()
        if not self.root.is_relative_to(work):
            raise ValueError('Native logs must stay within project work')
        self.root.mkdir(exist_ok=False)
        self.host = host
        self.handles = {}
        self.paths = {}
        self.offsets = {}
        self.options = {}
        self.kernel = C.WinDLL('kernel32', use_last_error=True)
        for name, args, result in (('CreateFileW', [C.c_wchar_p, C.c_uint32, C.c_uint32, C.c_void_p, C.c_uint32, C.c_uint32, C.c_void_p], C.c_void_p), ('WriteFile', [C.c_void_p, C.c_void_p, C.c_uint32, C.POINTER(C.c_uint32), C.c_void_p], C.c_int), ('CloseHandle', [C.c_void_p], C.c_int), ('GetFileSizeEx', [C.c_void_p, C.POINTER(C.c_int64)], C.c_int), ('GetSystemTimeAsFileTime', [C.c_void_p], None)):
            fn = getattr(self.kernel, name)
            fn.argtypes = args
            fn.restype = result

    @staticmethod
    def timestamp_from_filetime(ticks):
        delta = ticks - 116444736000000000
        millis = abs(delta) // 10000 * (-1 if delta < 0 else 1)
        return f'[{(millis & 4294967295) * 0.001:.3f}] '.encode('ascii')

    def open(self, channel, entry):
        options = (entry['filename'], entry['flags'])
        if channel in self.handles:
            if options != self.options[channel]:
                self.host._fatal('unverified active log reconfiguration', channel=hex(channel))
            return False
        filename = entry['filename']
        if entry['flags'] not in (0, 5) or not filename or _resolve_resource_path(Path(filename)).name != filename or any((ch in filename for ch in '/\\:')) or (filename in ('.', '..')):
            self.host._fatal('unverified active log channel options', channel=hex(channel), **entry)
        path = self.root / filename
        if _resolve_resource_path(path).exists():
            self.host._fatal('native log path already exists', filename=filename)
        handle = self.kernel.CreateFileW(str(path), 1073741824, 1, None, 2, 134217856, None)
        if handle in (None, C.c_void_p(-1).value):
            self.host._fatal('native log open failed', error=C.get_last_error())
        size = C.c_int64()
        if not self.kernel.GetFileSizeEx(handle, C.byref(size)) or size.value != 0:
            self.kernel.CloseHandle(handle)
            self.host._fatal('native log initial size failed', error=C.get_last_error())
        self.handles[channel] = handle
        self.paths[channel] = path
        self.offsets[channel] = 0
        self.options[channel] = options
        self.host.emit('host_log_file_opened', channel=hex(channel), path=str(path), flags=entry['flags'])
        return True

    def write(self, channel, data):
        entry = self.host.log_channels[channel]
        if self.options[channel] != (entry['filename'], entry['flags']):
            self.host._fatal('unverified active log reconfiguration', channel=hex(channel))
        if not data:
            return
        flags = self.options[channel][1]
        chunks = []
        if flags & 1:
            ticks = C.c_uint64()
            self.kernel.GetSystemTimeAsFileTime(C.byref(ticks))
            chunks.append(self.timestamp_from_filetime(ticks.value))
        chunks.append(data)
        if not data.endswith(b'\n'):
            chunks.append(b'\n')
        for chunk in chunks:
            written = C.c_uint32()
            offset = self.offsets[channel]
            overlapped = LogOverlapped(0, 0, offset & 4294967295, offset >> 32, None)
            if not self.kernel.WriteFile(self.handles[channel], chunk, len(chunk), C.byref(written), C.byref(overlapped)) or written.value != len(chunk):
                self.host._fatal('native log write failed', error=C.get_last_error())
            self.offsets[channel] += written.value

    def close(self):
        for channel, handle in list(self.handles.items()):
            if not self.kernel.CloseHandle(handle):
                self.host._fatal('native log close failed', error=C.get_last_error())
            del self.handles[channel]
            self.host.emit('host_log_file_closed', channel=hex(channel), path=str(self.paths[channel]))

class LogOverlapped(C.Structure):
    _fields_ = [('internal', C.c_size_t), ('internal_high', C.c_size_t), ('offset', C.c_uint32), ('offset_high', C.c_uint32), ('event', C.c_void_p)]
