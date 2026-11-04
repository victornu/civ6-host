"""Owned auxiliary+0x10 context notification, not a Tuner context factory.

The pinned EXE initializes this optional callback pair empty. The adapter admits
that explicit initial state; it does not infer that the full application never
installs a callback. A future debugger integration must supply its own evidence.
"""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import ctypes as C
import hashlib
import json
from pathlib import Path
CAPTURE_SHA = '916b1d85cf97eff0f0a5684d978386fc66718eaf2bf9488db4adad1cad13b37e'
COMPONENT_SHA = '4806f9c630cc03179308acee44de7b4e696660be3cf7b0b927ba923b1474dc2c'
BUILD_SHA = 'f52124cb0e81524e9bb8902ca30a0bf94364603b78a070a369221c19ed2dae0d'
ADMITTED_BUILDS = frozenset((BUILD_SHA, '8b94513b96926a60e20aa0f62943adf903e9d5fc8799ebd05bf587e4364b7e9d'))

def verify_loaded_host(host):
    from civ6_host.runtime.script_context_source import verify_notification_host
    verify_notification_host(host)

class NativeContextNotification:
    """Borrow a live script root and own only its notification-service binding."""

    def __init__(self, runtime, native_host, *, project_root):
        if runtime.closed or runtime.notification_service is not None:
            raise RuntimeError('Notification service requires an unbound live script root')
        capture = _resolve_resource_path(Path(project_root)) / 'work/native-context-notify886/capture886.json'
        data = _resolve_resource_path(capture).read_bytes()
        if hashlib.sha256(data).hexdigest() != CAPTURE_SHA:
            raise ValueError('Context notification source capture changed')
        source = json.loads(data)['source']
        if hashlib.sha256(_resolve_resource_path(_resolve_resource_path(Path(source['path']))).read_bytes()).hexdigest() != source['sha256']:
            raise ValueError('Installed context notification source binary changed')
        verify_loaded_host(runtime.host)
        self.runtime, self.native_host = (runtime, native_host)
        self.receiver = C.addressof(native_host.aux_object)
        self.original = native_host.aux_vtable[2]
        self.slot_key = (C.addressof(native_host.aux_vtable), 16)
        self.original_binding = getattr(native_host, '_slot_bindings', {}).get(self.slot_key)
        if not self.original and self.original_binding is not None:
            raise RuntimeError('Empty context notification slot has stale ownership metadata')
        if self.original and (not self.original_binding or self.original_binding[0] != self.original or getattr(self.original_binding[1], '_native_unavailable', None) != ('auxiliary', 16)):
            raise RuntimeError('Context notification slot is already owned or unrecognized')
        self.closed = True
        self.bind = runtime.host.LAB_ScriptContextNotifyBind
        self.bind.argtypes, self.bind.restype = ([C.c_void_p, C.c_void_p], C.c_int)
        self.dispatch = runtime.host.LAB_ScriptContextNotify
        self.dispatch.argtypes, self.dispatch.restype = ([C.c_void_p] * 3, C.c_int)
        self.unbind = runtime.host.LAB_ScriptContextNotifyUnbind
        self.unbind.argtypes, self.unbind.restype = ([C.c_void_p, C.c_void_p], C.c_int)
        if self.bind(runtime.root, self.receiver):
            raise RuntimeError('Native notification ownership refused')
        try:
            native_host._bind(native_host.aux_vtable, 16, None, [C.c_void_p, C.c_void_p], self.notify)
        except BaseException:
            self.unbind(runtime.root, self.receiver)
            native_host.aux_vtable[2] = self.original
            raise
        self.closed = False
        self.installed = native_host.aux_vtable[2]
        runtime.notification_service = self

    def notify(self, receiver, child):
        if self.closed or self.runtime.closed:
            raise RuntimeError('Notification service is closed')
        if self.native_host.aux_vtable[2] != self.installed:
            raise RuntimeError('Notification service binding was replaced')
        result = self.dispatch(self.runtime.root, receiver, child)
        if result:
            raise RuntimeError(f'Native context notification refused: {result}')

    def close(self):
        if self.closed:
            return
        if self.runtime.closed or self.runtime.notification_service is not self:
            raise RuntimeError('Notification service owner is no longer live')
        if self.native_host.aux_vtable[2] != self.installed:
            raise RuntimeError('Notification service binding was replaced; refusing to overwrite it')
        if self.unbind(self.runtime.root, self.receiver):
            raise RuntimeError('Native notification unbind refused')
        self.native_host.aux_vtable[2] = self.original
        if self.original_binding is None:
            self.native_host._slot_bindings.pop(self.slot_key, None)
        else:
            self.native_host._slot_bindings[self.slot_key] = self.original_binding
        self.runtime.notification_service = None
        self.closed = True
