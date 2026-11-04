"""Native Gameplay memory restore, a dependency of the future map service.

Uses DatabaseDLL's own main-to-main restore. A copied source still does not
establish the active ruleset/mod provenance. No game readiness is implied.
"""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import ctypes as C
import itertools
from civ6_host.runtime.native.native_database import NativeDatabase
from civ6_host.runtime.native.native_host import sha256
from civ6_host.runtime.native.native_host import virtual
_uris = itertools.count(1)

class NativeGameplayDatabase(NativeDatabase):

    def __init__(self, library, path, expected_sha256, emit, configure):
        super().__init__(library, path, expected_sha256, emit)
        if not callable(configure):
            raise ValueError('The memory database requires its native SQL initializer')
        self.configure = configure
        self.source = None
        self.uri = None
        self._configuration_borrowers = set()

    def _register_configuration_borrower(self, borrower):
        self._check()
        if not self.initialized or not self.connection:
            raise RuntimeError('Gameplay database owner is not open')
        self._configuration_borrowers.add(borrower)

    def _unregister_configuration_borrower(self, borrower):
        self._check()
        self._configuration_borrowers.discard(borrower)

    def __enter__(self):
        self._check()
        if self.initialized:
            raise RuntimeError('Database is already initialized')
        if sha256(self.path) != self.expected_sha256:
            raise ValueError('Database fixture changed before opening')
        if not self.initialize():
            raise RuntimeError('Database::Initialize failed')
        self.initialized = True
        try:
            index = next(_uris)
            if index > 255:
                raise RuntimeError('Gameplay memory diagnostic URI range exhausted')
            self.uri = f'file:gameplay-{index}?mode=memory&cache=shared'.encode('ascii')
            self.connection = self.create(self.uri, 70, None)
            if not self.connection:
                raise RuntimeError('Native memory connection returned null')
            self.configure(self.library, self.connection)
            self.emit('gameplay_memory_opened', uri=self.uri.decode(), flags=70, eligible_for_training=False)
            self.source = self.create(str(self.path).encode('utf-8'), 65, None)
            if not self.source:
                raise RuntimeError('Native restore source returned null')
            restore = virtual(self.library, self.connection, 192, 9840, C.c_bool, C.c_void_p)
            if not restore(self.connection, self.source):
                raise RuntimeError('Native Gameplay restore failed')
            self._release_source()
            self.emit('gameplay_memory_restored', source=str(self.path), source_sha256=self.expected_sha256, source_released=True, restore_rva='0x2670', retained_connection='memory', eligible_for_training=False)
            return self
        except BaseException:
            self.close()
            raise

    def _release_source(self):
        if self.source:
            release = virtual(self.library, self.source, 8, 6784, None)
            release(self.source)
            self.source = None
            self.emit('gameplay_restore_source_released')

    def execute(self, sql):
        self._check()
        if not self.connection:
            raise RuntimeError('Database connection is closed')
        if not isinstance(sql, bytes) or not sql or b'\x00' in sql or (len(sql) > 65536):
            raise ValueError('Invalid bounded native statement')
        execute = virtual(self.library, self.connection, 32, 6880, C.c_bool, C.c_char_p, C.c_int)
        if not execute(self.connection, sql, -1):
            raise RuntimeError('Native Gameplay SQL execution failed')

    def close(self):
        self._check()
        if self._configuration_borrowers:
            raise RuntimeError('Cannot close Gameplay database while Configuration borrowers are open')
        self._release_source()
        super().close()

def bind_memory_initializer(host):
    initialize = host.LAB_GameplayMemoryInitialize
    initialize.argtypes, initialize.restype = ([C.c_void_p, C.c_void_p], C.c_int)

    def configure(library, connection):
        status = initialize(library._handle, connection)
        if status != 0:
            raise RuntimeError(f'Native Gameplay SQL initialization refused: {status}')
    return configure
