"""Retain native script children through bootstrap and until explicit release.

This is the single-owner portion of EXE161a90/161d20, not a context factory.
No auxiliary slots are installed and no child is advertised as bootstrapped.
The original's valid unique-child path unlinks before destroying the wrapper.
Unknown releases fail before mutation; native release failures poison the owner
and retain diagnostic references instead of claiming successful destruction.
"""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import hashlib
import json
from pathlib import Path
from civ6_host.runtime.native.native_context_notify import verify_loaded_host
CAPTURE_SHA = '69e00f16001ac95c747d634039323dcfa802735073c7d5cdf3cad700ed4711bd'

class RetainedScriptContexts:

    def __init__(self, runtime, *, project_root):
        runtime.registry._check()
        if runtime.closed or runtime.context_owner is not None:
            raise RuntimeError('A live unowned runtime is required')
        capture = _resolve_resource_path(Path(project_root)) / 'work/native-context-lifetime887/capture887.json'
        data = _resolve_resource_path(capture).read_bytes()
        if hashlib.sha256(data).hexdigest() != CAPTURE_SHA:
            raise ValueError('Context lifetime source capture changed')
        source = json.loads(data)['source']
        if hashlib.sha256(_resolve_resource_path(_resolve_resource_path(Path(source['path']))).read_bytes()).hexdigest() != source['sha256']:
            raise ValueError('Installed context lifetime source changed')
        verify_loaded_host(runtime.host)
        self.runtime = runtime
        self._token = object()
        self._contexts = {}
        self._quarantined = {}
        self.closed = False
        runtime.context_owner = self

    def _check(self):
        self.runtime.registry._check()
        if self.closed or self.runtime.closed or self.runtime.context_owner is not self:
            raise RuntimeError('Retained context owner is closed or replaced')
        if self._quarantined:
            raise RuntimeError('Native release failed; context owner is poisoned')

    @property
    def handles(self):
        self._check()
        return tuple(self._contexts)

    def acquire(self):
        self._check()
        child = self.runtime.acquire()
        try:
            self.runtime.registry.claim(child, self._token)
        except BaseException:
            self.runtime.registry.release(child)
            raise
        self._contexts[child.pointer] = child
        return child

    def release(self, pointer):
        self._check()
        if type(pointer) is not int or pointer not in self._contexts:
            raise ValueError('Unknown, foreign or already released context')
        child = self._contexts[pointer]
        self.runtime.registry.validate(child)
        del self._contexts[pointer]
        try:
            self.runtime.registry.release(child, owner=self._token)
        except BaseException:
            self._quarantined[pointer] = child
            raise

    def close(self):
        if self.closed:
            return
        self._check()
        if self._contexts:
            raise RuntimeError('Release retained children before closing their owner')
        self.runtime.context_owner = None
        self.closed = True
