"""A private Configuration memory connection borrowing a Gameplay owner cycle.

This diagnostic adapter restores a private copy into DatabaseDLL's shared
memory database. It does not call Database::Initialize/Shutdown and does not
claim that the EXE's Configuration singleton lifecycle has been reproduced.
"""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import ctypes as C
from contextlib import contextmanager
import itertools
from pathlib import Path
import threading
from civ6_host.runtime.native.native_gameplay_database import NativeGameplayDatabase
from civ6_host.runtime.native.native_host import sha256
from civ6_host.runtime.native.native_host import virtual
_uris = itertools.count(1)

class NativeConfigurationDatabase:
    """Restore one private Configuration fixture into a diagnostic memory DB."""

    def __init__(self, owner, path, expected_sha256, emit):
        if not isinstance(owner, NativeGameplayDatabase):
            raise ValueError('Configuration memory database requires a Gameplay owner')
        self.owner = owner
        self.library = owner.library
        self.create = owner.create
        self.path = _resolve_resource_path(Path(path))
        self.expected_sha256 = expected_sha256
        self.emit = emit
        self.thread = threading.get_ident()
        self.connection = None
        self.source = None
        self.uri = None
        self.opened = False
        self._registered = False

    def _check(self):
        if threading.get_ident() != self.thread:
            raise RuntimeError('Cross-thread native configuration database access')
        self.owner._check()
        if not self.owner.initialized or not self.owner.connection:
            raise RuntimeError('Gameplay database owner is not open')

    def __enter__(self):
        self._check()
        if self.opened or self.connection is not None or self.source is not None:
            raise RuntimeError('Configuration database is already open')
        if sha256(self.path) != self.expected_sha256:
            raise ValueError('Configuration database fixture changed before opening')
        self.owner._register_configuration_borrower(self)
        self._registered = True
        try:
            index = next(_uris)
            self.uri = f'file:configuration-diagnostic-{index}?mode=memory&cache=shared'.encode('ascii')
            self.connection = self.create(self.uri, 70, None)
            if not self.connection:
                self.connection = None
                raise RuntimeError('Native Configuration memory connection returned null')
            self.source = self.create(str(self.path).encode('utf-8'), 65, None)
            if not self.source:
                self.source = None
                raise RuntimeError('Native Configuration restore source returned null')
            restore = virtual(self.library, self.connection, 192, 9840, C.c_bool, C.c_void_p)
            if not restore(self.connection, self.source):
                raise RuntimeError('Native Configuration restore failed')
            self._release('source', 'configuration_restore_source_released')
            self.opened = True
            self.emit('configuration_memory_restored', source=str(self.path), source_sha256=self.expected_sha256, uri=self.uri.decode('ascii'), flags=70, source_flags=65, restore_rva='0x2670', retained_connection='memory', source_released=True, owner='gameplay', eligible_for_training=False)
            return self
        except BaseException:
            try:
                self.close()
            except BaseException:
                pass
            raise

    def _release(self, attribute, event):
        connection = getattr(self, attribute)
        if connection is None:
            return
        release = virtual(self.library, connection, 8, 6784, None)
        release(connection)
        setattr(self, attribute, None)
        self.emit(event)

    def _unregister_if_released(self):
        if self._registered and self.source is None and (self.connection is None):
            self.owner._unregister_configuration_borrower(self)
            self._registered = False

    def close(self):
        self._check()
        failure = None
        for attribute, event in (('source', 'configuration_restore_source_released'), ('connection', 'configuration_memory_released')):
            try:
                self._release(attribute, event)
            except BaseException as exc:
                if failure is None:
                    failure = exc
        self.opened = False
        try:
            self._unregister_if_released()
        except BaseException as exc:
            if failure is None:
                failure = exc
        try:
            if sha256(self.path) != self.expected_sha256:
                raise RuntimeError('Native restore changed the Configuration database copy')
        except BaseException as exc:
            if failure is None:
                failure = exc
        if failure is not None:
            raise failure

    def __exit__(self, *_):
        self.close()

@contextmanager
def configuration_database(owner, path, expected_sha256, emit):
    """Open a restored Configuration memory DB under an already-open Gameplay owner."""
    with NativeConfigurationDatabase(owner, path, expected_sha256, emit) as database:
        yield database
