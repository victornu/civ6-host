"""Pinned DatabaseDLL read-only query adapter for isolated diagnostic workers.

The connection is owned by one Python thread. Cursors never escape a query,
and their release runs before the connection can be released or shut down.
This does not establish the provenance of an active game's database.
"""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import ctypes as C
import os
from pathlib import Path
import threading
from civ6_host.runtime.native.native_host import DATABASE_SHA256
from civ6_host.runtime.native.native_host import sha256
from civ6_host.runtime.native.native_host import virtual
from civ6_host.runtime.native.native_localization import CREATE_CONNECTION
PARAMETER_SQL = b'SELECT Name, Value FROM GlobalParameters'

class NativeDatabase:

    def __init__(self, library, path, expected_sha256, emit):
        self.library, self.path, self.emit = (library, _resolve_resource_path(Path(path)), emit)
        self.owner = threading.get_ident()
        self.connection = None
        self.initialized = False
        self.expected_sha256 = expected_sha256
        if sha256(self.path) != expected_sha256:
            raise ValueError('Database fixture changed before opening')
        self.initialize = getattr(library, '?Initialize@Database@@YA_NXZ')
        self.initialize.argtypes, self.initialize.restype = ([], C.c_bool)
        self.shutdown = getattr(library, '?Shutdown@Database@@YA_NXZ')
        self.shutdown.argtypes, self.shutdown.restype = ([], C.c_bool)
        self.create = getattr(library, CREATE_CONNECTION)
        self.create.argtypes = [C.c_char_p, C.c_int, C.c_void_p]
        self.create.restype = C.c_void_p

    def _check(self):
        if threading.get_ident() != self.owner:
            raise RuntimeError('Cross-thread native database access')

    @property
    def initialization_active(self):
        self._check()
        return self.initialized and bool(self.connection)

    def __enter__(self):
        self._check()
        if self.initialized:
            raise RuntimeError('Database is already initialized')
        if not self.initialize():
            raise RuntimeError('Database::Initialize failed')
        self.initialized = True
        try:
            self.connection = self.create(str(self.path).encode('utf-8'), 65, None)
            if not self.connection:
                raise RuntimeError('Database::CreateConnection returned null')
            self.emit('parameter_database_opened', path=str(self.path), flags=65, flags_semantics='opaque source-observed diagnostic flags', sha256=self.expected_sha256, eligible_for_training=False)
            return self
        except BaseException:
            self.close()
            raise

    def rows(self):
        return self.text_rows(PARAMETER_SQL, 2)

    def text_rows(self, sql, columns, *, max_rows=4096):
        """Copy bounded text results; callers supply a known column count.

        Native advance conflates EOF and query failure. Consumers must compare
        expected rows or explicit sentinels; this is not a general SQL API.
        """
        self._check()
        if not self.connection:
            raise RuntimeError('Database connection is closed')
        if not isinstance(sql, bytes) or not sql or b'\x00' in sql or (len(sql) > 65536) or (not isinstance(columns, int)) or (not 1 <= columns <= 128) or (not isinstance(max_rows, int)) or (not 1 <= max_rows <= 65536):
            raise ValueError('Invalid bounded native query')
        query = virtual(self.library, self.connection, 24, 9120, C.c_void_p, C.c_char_p, C.c_int)
        cursor = query(self.connection, sql, -1)
        if not cursor:
            raise RuntimeError('Native parameter query returned null; not an empty row set')
        try:
            release = virtual(self.library, cursor, 8, 17920, None)
        except ValueError:
            try:
                self.emit('parameter_cursor_release_abi_refused', exit_code=78)
            finally:
                os._exit(78)
        try:
            advance = virtual(self.library, cursor, 32, 19984, C.c_bool)
            get_string = virtual(self.library, cursor, 240, 19040, C.c_char_p, C.c_int)
            rows = []
            while advance(cursor):
                if len(rows) >= max_rows:
                    raise RuntimeError('Diagnostic parameter row limit exceeded')
                pair = tuple((get_string(cursor, i) for i in range(columns)))
                if any((value is not None and len(value) > 65536 for value in pair)):
                    raise RuntimeError('Diagnostic parameter value limit exceeded')
                rows.append(pair)
            return rows
        finally:
            release(cursor)

    def close(self):
        self._check()
        if self.connection:
            release = virtual(self.library, self.connection, 8, 6784, None)
            release(self.connection)
            self.connection = None
            self.emit('parameter_database_released')
        if self.initialized:
            if not self.shutdown():
                raise RuntimeError('Database::Shutdown failed')
            self.initialized = False
            self.emit('parameter_database_shutdown')
        if sha256(self.path) != self.expected_sha256:
            raise RuntimeError('Native query changed the diagnostic database')

    def __exit__(self, *_):
        self.close()

def load_database(directory):
    path = _resolve_resource_path(Path(directory)) / 'DatabaseDLL_FinalRelease.dll'
    if sha256(path) != DATABASE_SHA256:
        raise ValueError('Unrecognized DatabaseDLL binary')
    return C.WinDLL(str(path))
