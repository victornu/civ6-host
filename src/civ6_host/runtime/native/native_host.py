"""Version-specific, fail-closed GameCore host bootstrap for diagnostic probes.

This is not a game environment. Unsupported callbacks terminate the disposable
worker instead of pretending a gameplay service succeeded.
"""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import ctypes as C
import hashlib
import json
import os
import time
from pathlib import Path
from typing import Collection
HOST_IID = bytes.fromhex('c299ce27a878d54191a2567c083e47af')
DATABASE_SHA256 = 'e6577e873f946224df65c02f6c4bc3b385607e2a82d957b0fd613e01cbe78b0c'
BOOTSTRAP_TYPE_NAMES = frozenset(('Unit', 'Formation', 'City::Instance', 'Trade::Edge', 'Control::Contract', 'District::Instance', 'AI::CityBuild', 'BehaviorTree', 'AI::Operation', 'DynamicModifier'))

def sha256(path):
    digest = hashlib.sha256()
    with _resolve_resource_path(_resolve_resource_path(Path(path))).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()

class EventFilterRegistry:
    """EXE 11d5a0 updates matching pairs, then appends even when one existed."""

    def __init__(self):
        self.entries: dict[int, list[tuple[int, int]]] = {}

    def declare(self, event: int, filter_id: int, value: int):
        if any((not 0 <= n <= 4294967295 for n in (event, filter_id, value))):
            raise ValueError('Event registry fields must be unsigned 32-bit values')
        pairs = self.entries.setdefault(event, [])
        for index, (existing_id, _) in enumerate(pairs):
            if existing_id == filter_id:
                pairs[index] = (filter_id, value)
        pairs.append((filter_id, value))

class ArchiveRegistry:
    """EXE 7f5e70/7f78b0 identity map used by the native autoarchives.

    The Core owns archive storage and its active byte. The host only retains
    identities. Re-registering the same identity is allowed; ID collisions are
    rejected without replacing the original pointer.
    """

    def __init__(self):
        self.entries: dict[int, int] = {}

    def register(self, key: int, pointer: int) -> bool:
        if not 0 <= key <= 18446744073709551615 or pointer < 0:
            raise ValueError('Invalid native archive identity')
        if not key or not pointer:
            return False
        if key in self.entries and self.entries[key] != pointer:
            return False
        self.entries[key] = pointer
        return True

    def remove(self, key: int, pointer: int, active: bool):
        if active and key and (self.entries.get(key) == pointer):
            del self.entries[key]

def type_name_hash(name: str) -> int:
    """Return the EXE TypeRegistry's case-sensitive ASCII FNV-1a hash."""
    if not isinstance(name, str):
        raise TypeError('Type name must be text')
    try:
        encoded = name.encode('ascii')
    except UnicodeEncodeError as exc:
        raise ValueError('Type names must be ASCII') from exc
    value = 2166136261
    for byte in encoded:
        value = (value ^ byte) * 16777619 & 4294967295
    return value

class TypeRegistry:
    """Pure mirror of the EXE TypeRegistry's hash-keyed callback records.

    The optional allowlist narrows the diagnostic adapter to the ten observed
    bootstrap type names. Callbacks are retained as opaque integer addresses;
    this class never invokes them.
    """

    def __init__(self, allowed_names: Collection[str] | None=None):
        self.allowed_names = None if allowed_names is None else frozenset(allowed_names)
        self.entries: dict[int, tuple[str, int, int]] = {}

    def _validate_name(self, name: str) -> int:
        hashed = type_name_hash(name)
        if self.allowed_names is not None and name not in self.allowed_names:
            raise ValueError('Type name is outside the validated registry contract')
        if '\x00' in name:
            raise ValueError('Type names cannot contain NUL')
        return hashed

    @staticmethod
    def _validate_callback(callback: int) -> int:
        if isinstance(callback, bool) or not isinstance(callback, int) or (not 0 <= callback <= 18446744073709551615):
            raise ValueError('Type callbacks must be unsigned 64-bit addresses')
        return callback

    def register(self, name: str, callback1: int, callback2: int) -> bool:
        """Store or replace the hash entry; return whether the hash existed."""
        hashed = self._validate_name(name)
        first = self._validate_callback(callback1)
        second = self._validate_callback(callback2)
        replaced = hashed in self.entries
        self.entries[hashed] = (name, first, second)
        return replaced

    def remove(self, name: str) -> bool:
        """Remove by hash only, matching the native unregister lookup."""
        hashed = self._validate_name(name)
        return self.entries.pop(hashed, None) is not None

class DiagnosticHost:
    """Only implements the source-backed installation/bootstrap callbacks."""

    def __init__(self, configuration: Path, gameplay: Path, emit, native_aligned_free=None):
        if os.name != 'nt':
            raise RuntimeError('Native host requires Windows x64')
        self.emit = emit
        self.terminate = C.WinDLL('kernel32').TerminateProcess
        self.terminate.argtypes, self.terminate.restype = ([C.c_void_p, C.c_uint32], C.c_int)
        self.functions = []
        self.filters = EventFilterRegistry()
        self.references = 1
        self.paths = {320: C.create_string_buffer(str(configuration).encode('utf-8')), 312: C.create_string_buffer(str(gameplay).encode('utf-8'))}
        self.vtable = (C.c_void_p * 128)()
        self.object = (C.c_void_p * 2)(C.addressof(self.vtable), self.references)
        self.aux_vtable = (C.c_void_p * 32)()
        self.aux_object = (C.c_void_p * 2)(C.addressof(self.aux_vtable), 1)
        self.logger_vtable = (C.c_void_p * 32)()
        self.logger_object = (C.c_void_p * 2)(C.addressof(self.logger_vtable), 1)
        self.log_channels = {}
        self.log_headers: dict[int, bytes] = {}
        self.log_global_enabled = 1
        self.archives = ArchiveRegistry()
        self.types = TypeRegistry(BOOTSTRAP_TYPE_NAMES)
        self.native_aligned_free = native_aligned_free
        self.registrar_vtable = (C.c_void_p * 3)()
        self.registrar_object = (C.c_void_p * 1)(C.addressof(self.registrar_vtable))
        self.descriptor_vtable = (C.c_void_p * 32)()
        self.descriptor_object = (C.c_void_p * 1)(C.addressof(self.descriptor_vtable))
        for index in range(len(self.vtable)):
            self._bind(self.vtable, index * 8, None, [C.c_void_p], self._unsupported('host', index * 8))
        for index in range(len(self.aux_vtable)):
            self._bind(self.aux_vtable, index * 8, None, [C.c_void_p], self._unsupported('auxiliary', index * 8))
        for index in range(len(self.logger_vtable)):
            self._bind(self.logger_vtable, index * 8, None, [C.c_void_p], self._unsupported('logger', index * 8))
        for index in range(len(self.registrar_vtable)):
            self._bind(self.registrar_vtable, index * 8, None, [C.c_void_p], self._unsupported('type registrar', index * 8))
        for index in range(len(self.descriptor_vtable)):
            self._bind(self.descriptor_vtable, index * 8, None, [C.c_void_p], self._unsupported('autoarchive registry', index * 8))
        self._bind(self.descriptor_vtable, 0, C.c_bool, [C.c_void_p, C.c_void_p], self._archive_register)
        self._bind(self.descriptor_vtable, 8, None, [C.c_void_p, C.c_void_p], self._archive_remove)
        self._bind(self.registrar_vtable, 0, None, [C.c_void_p, C.c_void_p, C.c_void_p, C.c_void_p], self._register_type)
        self._bind(self.registrar_vtable, 8, None, [C.c_void_p, C.c_void_p], self._remove_type)
        self._bind(self.logger_vtable, 64, None, [C.c_void_p, C.c_uint32, C.c_wchar_p, C.c_uint32, C.c_void_p], self._log_register)
        self._bind(self.logger_vtable, 40, None, [C.c_void_p, C.c_uint32, C.c_uint8], self._log_enable)
        self._bind(self.logger_vtable, 56, C.c_uint32, [C.c_void_p, C.c_uint32], self._log_level)
        self._bind(self.logger_vtable, 16, C.c_uint8, [C.c_void_p, C.c_uint32], self._log_enabled)
        from civ6_host.runtime.native.native_logging import DisabledLogWriters
        self.log_writers = DisabledLogWriters(self)
        self._bind(self.logger_vtable, 80, C.c_void_p, [C.c_void_p, C.c_uint32], self.log_writers.lookup)
        self._bind(self.logger_vtable, 32, None, [C.c_void_p, C.c_uint8], self._log_global_enable)
        self._bind(self.logger_vtable, 24, C.c_uint8, [C.c_void_p], self._log_global_enabled)
        self._bind(self.vtable, 0, C.c_void_p, [C.c_void_p, C.c_void_p], self._query)
        self._bind(self.vtable, 8, C.c_uint32, [C.c_void_p], self._release)
        self._bind(self.vtable, 16, C.c_void_p, [C.c_void_p], self._auxiliary)
        self._bind(self.vtable, 24, C.c_void_p, [C.c_void_p], self._logger)
        self.achievement_service_installed = False
        self._bind(self.vtable, 32, C.c_void_p, [C.c_void_p], self._achievement_service)
        self._bind(self.vtable, 120, C.c_uint32, [C.c_void_p, C.c_uint32], self._constant_zero_slot78)
        self._bind(self.vtable, 152, None, [C.c_void_p, C.c_uint32, C.c_uint32, C.c_uint32], self._declare)
        self._bind(self.vtable, 272, C.c_void_p, [C.c_void_p], self._registrar)
        self._bind(self.vtable, 264, C.c_void_p, [C.c_void_p], self._descriptor_context)
        self._bind(self.vtable, 336, C.c_bool, [C.c_void_p, C.c_void_p, C.c_void_p], self._script_descriptor)
        for offset in self.paths:
            self._bind(self.vtable, offset, C.c_void_p, [C.c_void_p], self._path_callback(offset))

    @property
    def pointer(self):
        return C.addressof(self.object)

    def _achievement_service(self, this):
        self._check(this)
        from civ6_host.runtime.native import native_absent_achievements as achievements
        frames = achievements.capture_stack()
        source_proof_sha256 = achievements.select_contract(frames, service_installed=self.achievement_service_installed)
        result = None
        self.emit('native_optional_achievement_service_absent', slot='0x20', native_stack=frames, native_null_branch_used=True, platform_service_installed=False, platform_request_submitted=False, platform_success_reported=False, real_exe_field_initialization_claimed=False, source_proof_sha256=source_proof_sha256, eligible_for_training=False)
        return result

    def _constant_zero_slot78(self, this, key):
        self._check(this)
        self.emit('native_host_constant_zero', slot='0x78', key=hex(key), source_callback_rva='0x9744b0', result=0)
        return 0

    def configure_local_player_id(self, player_id):
        """Provide the host input named GetLocalPlayerID by the pinned EXE.

        This selects the host's perspective; it neither creates a player nor
        supplies the native player/game configuration. No implicit ID is used.
        Evidence: phase33-local-player (EXE26af00 -> 27ceb0 -> session+270).
        """
        if type(player_id) is not int or not -1 <= player_id <= 64:
            raise ValueError('Local player ID must be an integer in -1..64')
        if hasattr(self, 'configured_local_player_id'):
            raise RuntimeError('Diagnostic local player ID is already configured')
        self.configured_local_player_id = player_id

        def get_local_player(this):
            self._check(this)
            self.emit('host_local_player_id', slot='0xd0', player_id=player_id, native_player_configuration_validated=False)
            return player_id & 4294967295
        self._bind(self.vtable, 208, C.c_uint32, [C.c_void_p], get_local_player)
        self.emit('host_local_player_configured', player_id=player_id, native_player_configuration_validated=False)

    def _script_descriptor(self, this, input_pointer, output_pointer):
        self._check(this)
        first = None
        if input_pointer:
            from civ6_host.runtime.native.native_setup import local_reader
            first = int.from_bytes(local_reader()(input_pointer, 2), 'little')
        if first == ord('{'):
            self._fatal('JSON script descriptor is not implemented', interface='host', slot='0x150')
        self.emit('host_script_descriptor_rejected', slot='0x150', first_utf16_unit=first, input_null=not bool(input_pointer), output_modified=False)
        return False

    def _fatal(self, reason, **details):
        frames = []
        try:
            kernel = C.WinDLL('kernel32')
            capture = kernel.RtlCaptureStackBackTrace
            capture.argtypes, capture.restype = ([C.c_uint32, C.c_uint32, C.c_void_p, C.c_void_p], C.c_uint16)
            get_module = kernel.GetModuleHandleExW
            get_module.argtypes, get_module.restype = ([C.c_uint32, C.c_void_p, C.POINTER(C.c_void_p)], C.c_int)
            get_name = kernel.GetModuleFileNameW
            get_name.argtypes, get_name.restype = ([C.c_void_p, C.c_wchar_p, C.c_uint32], C.c_uint32)
            addresses = (C.c_void_p * 96)()
            count = capture(0, len(addresses), addresses, None)
            for address in addresses[:count]:
                module, name = (C.c_void_p(), C.create_unicode_buffer(32768))
                if get_module(6, address, C.byref(module)) and get_name(module, name, len(name)):
                    frames.append({'module': _resolve_resource_path(Path(name.value)).name, 'rva': hex(address - module.value)})
        except Exception as exc:
            details['stack_capture_error'] = repr(exc)
        self.emit('unsupported_host_contract', reason=reason, native_stack=frames, **details)
        self.terminate(C.c_void_p(-1), 78)
        os._exit(78)

    def _unsupported(self, interface, offset):

        def call(this):
            self._fatal('unimplemented native service', interface=interface, slot=hex(offset))
        call._native_unavailable = (interface, offset)
        return call

    def _bind(self, table, offset, result, arguments, callback):

        def guarded(*args):
            try:
                return callback(*args)
            except BaseException as exc:
                import traceback
                self._fatal('host callback exception', slot=hex(offset), error=repr(exc), python_traceback=traceback.format_exc(limit=12))
        fn = C.WINFUNCTYPE(result, *arguments)(guarded)
        self.functions.append(fn)
        table[offset // 8] = C.cast(fn, C.c_void_p).value
        if not hasattr(self, '_slot_bindings'):
            self._slot_bindings = {}
        self._slot_bindings[C.addressof(table), offset] = (table[offset // 8], callback)

    def _check(self, this):
        if this != self.pointer:
            raise ValueError('Host method received a different interface pointer')

    def _query(self, this, iid):
        self._check(this)
        requested = C.string_at(iid, 16)
        self.emit('host_query_interface', iid_hex=requested.hex())
        if requested != HOST_IID:
            self._fatal('unverified requested host interface', iid_hex=requested.hex())
        self.references += 1
        self.object[1] = self.references
        return self.pointer

    def _release(self, this):
        self._check(this)
        if self.references <= 1:
            self._fatal('host reference underflow')
        self.references -= 1
        self.object[1] = self.references
        self.emit('host_release', references=self.references)
        return self.references

    def _auxiliary(self, this):
        self._check(this)
        self.emit('host_auxiliary', contract='explicit unavailable-Tuner fault injection' if getattr(self, 'tuner_unavailable_probe', False) else 'diagnostic object; any method aborts')
        return C.addressof(self.aux_object)

    def enable_tuner_unavailable_probe(self):
        """Exercise Core's observed null-service branch, not EXE equivalence.

        Core 48e6e0 guards the Tuner setup callback after slot+0 returns null;
        48ed80 guards release. Only the named bounded fault probe enables this.
        Other contexts and all other script-service methods still fail closed.
        """
        self.tuner_unavailable_probe = True
        self._bind(self.aux_vtable, 0, C.c_void_p, [C.c_void_p, C.c_char_p, C.c_uint8], self._tuner_unavailable)
        self.emit('diagnostic_fault_enabled', fault='GameCore_Tuner unavailable', script_service_reproduced=False, eligible_for_training=False)

    def _tuner_unavailable(self, this, name, flag):
        if not getattr(self, 'tuner_unavailable_probe', False) or this != C.addressof(self.aux_object) or name != b'GameCore_Tuner' or (flag != 1):
            self._fatal('request outside bounded unavailable-Tuner diagnostic', name=repr(name), flag=flag)
        self.emit('diagnostic_tuner_unavailable', name='GameCore_Tuner', flag=flag, returned_null=True, script_service_reproduced=False, eligible_for_training=False)
        return None

    def _logger(self, this):
        self._check(this)
        self.emit('host_logger', scope='channel registry; unsupported logger methods abort')
        return C.addressof(self.logger_object)

    def _read_log_header(self, pointer):
        kernel = C.WinDLL('kernel32', use_last_error=True)
        read = kernel.ReadProcessMemory
        read.argtypes = [C.c_void_p, C.c_void_p, C.c_void_p, C.c_size_t, C.POINTER(C.c_size_t)]
        read.restype = C.c_int
        data = bytearray()
        byte, count = (C.c_ubyte(), C.c_size_t())
        for index in range(256):
            if not read(C.c_void_p(-1), pointer + index, C.byref(byte), 1, C.byref(count)) or count.value != 1:
                self._fatal('unreadable logger header', pointer=pointer, offset=index)
            if byte.value == 0:
                return bytes(data[:255])
            data.append(byte.value)
        return bytes(data[:255])

    def _log_register(self, this, channel, filename, flags, header):
        if this != C.addressof(self.logger_object):
            self._fatal('unverified logger registration arguments')
        header_bytes = self._read_log_header(header) if header else None
        entry = self.log_channels.setdefault(channel, {'filename': None, 'flags': 0, 'enabled': 1, 'level': 0})
        if filename is not None:
            entry['filename'] = filename
        entry['flags'] = flags
        if header_bytes is not None:
            self.log_headers[channel] = header_bytes
        self.emit('host_log_register', channel=hex(channel), filename=filename, flags=flags, enabled=bool(entry['enabled']), level=entry['level'], header_hex=self.log_headers.get(channel, b'').hex(), header_updated=header_bytes is not None)

    def _log_enable(self, this, channel, enabled):
        if this != C.addressof(self.logger_object):
            self._fatal('unverified logger enable arguments')
        entry = self.log_channels.get(channel)
        if entry is not None:
            entry['enabled'] = int(enabled)
        elif enabled:
            self.log_channels[channel] = {'filename': None, 'flags': 0, 'enabled': 1, 'level': 0}
        self.emit('host_log_enable', channel=hex(channel), enabled=bool(enabled), enabled_byte=int(enabled))

    def _log_level(self, this, channel):
        if this != C.addressof(self.logger_object):
            self._fatal('unverified logger level arguments')
        entry = self.log_channels.get(channel)
        level = entry['level'] if entry is not None else 0
        self.emit('host_log_level', channel=hex(channel), found=entry is not None, level=level)
        return level

    def _log_enabled(self, this, channel):
        if this != C.addressof(self.logger_object):
            self._fatal('unverified logger enabled-query arguments')
        entry = self.log_channels.get(channel)
        enabled = entry['enabled'] if entry is not None else 0
        self.emit('host_log_enabled', channel=hex(channel), found=entry is not None, enabled=bool(enabled), enabled_byte=enabled)
        return enabled

    def _log_global_enable(self, this, value):
        if this != C.addressof(self.logger_object):
            self._fatal('unverified logger global-enable arguments')
        self.log_global_enabled = int(value)
        self.emit('host_log_global_enable', enabled_byte=int(value))

    def _log_global_enabled(self, this):
        if this != C.addressof(self.logger_object):
            self._fatal('unverified logger global-enable query arguments')
        self.emit('host_log_global_enabled', enabled_byte=self.log_global_enabled)
        return self.log_global_enabled

    def _declare(self, this, event, filter_id, value):
        self._check(this)
        self.filters.declare(event, filter_id, value)
        self.emit('host_event_filter', event=hex(event), filter_id=hex(filter_id), value=value, pair_count=len(self.filters.entries[event]))

    def _registrar(self, this):
        self._check(this)
        return C.addressof(self.registrar_object)

    def _descriptor_context(self, this):
        self._check(this)
        self.emit('host_descriptor_context', contract='autoarchive identity registration; other methods abort')
        return C.addressof(self.descriptor_object)

    def _archive_register(self, this, descriptor):
        if this != C.addressof(self.descriptor_object):
            self._fatal('wrong archive registry interface')
        key = C.c_uint64.from_address(descriptor + 88).value if descriptor else 0
        accepted = self.archives.register(key, descriptor or 0)
        self.emit('host_archive_register', key=hex(key), accepted=accepted, registered=len(self.archives.entries))
        return accepted

    def _archive_remove(self, this, descriptor):
        if this != C.addressof(self.descriptor_object):
            self._fatal('wrong archive registry interface')
        key = C.c_uint64.from_address(descriptor + 88).value if descriptor else 0
        active = bool(C.c_uint8.from_address(descriptor + 72).value) if descriptor else False
        self.archives.remove(key, descriptor or 0, active)
        self.emit('host_archive_remove', key=hex(key), active=active, registered=len(self.archives.entries))

    def _copy_type_name(self, descriptor):
        if not descriptor:
            raise ValueError('missing native type range-string')
        begin, end, capacity = (C.c_void_p * 3).from_address(descriptor)
        if not begin or not end or (not capacity) or (not 0 < end - begin < capacity - begin <= 256):
            raise ValueError('unverified type range-string layout')
        raw_name = C.string_at(begin, end - begin)
        if b'\x00' in raw_name or C.string_at(end, 1) != b'\x00':
            raise ValueError('invalid type range-string termination')
        name = raw_name.decode('ascii')
        if name not in BOOTSTRAP_TYPE_NAMES:
            raise ValueError(f'unverified bootstrap type name: {name}')
        return (begin, name)

    def _register_type(self, this, descriptor, callback1, callback2):
        if this != C.addressof(self.registrar_object) or not self.native_aligned_free:
            self._fatal('type registration requires verified native string allocator')
        try:
            begin, name = self._copy_type_name(descriptor)
            replaced = self.types.register(name, 0 if callback1 is None else int(callback1), 0 if callback2 is None else int(callback2))
        except (ValueError, TypeError) as exc:
            self._fatal('unverified type registration arguments', error=str(exc))
        self.native_aligned_free(begin)
        self.emit('host_type_register', name=name, replaced=replaced, callback1=0 if callback1 is None else int(callback1), callback2=0 if callback2 is None else int(callback2), native_string_consumed=True)

    def _remove_type(self, this, descriptor):
        if this != C.addressof(self.registrar_object) or not self.native_aligned_free:
            self._fatal('type removal requires verified native string allocator')
        try:
            begin, name = self._copy_type_name(descriptor)
            found = self.types.remove(name)
        except (ValueError, TypeError) as exc:
            self._fatal('unverified type removal arguments', error=str(exc))
        self.native_aligned_free(begin)
        self.emit('host_type_remove', name=name, found=found, native_string_consumed=True)

    def _path_callback(self, offset):

        def path(this):
            self._check(this)
            self.emit('host_database_path', slot=hex(offset))
            return C.addressof(self.paths[offset])
        return path

def validate_fixture(manifest_path):
    manifest = json.loads(_resolve_resource_path(_resolve_resource_path(Path(manifest_path))).read_text(encoding='utf-8-sig'))
    if manifest.get('schema') != 'civ6rl.native-fixture.v1' or not str(manifest.get('purpose', '')).startswith('diagnostic'):
        raise ValueError('Expected a diagnostic native-fixture manifest')
    if manifest.get('eligible_for_training') is not False:
        raise ValueError('Bootstrap fixture must explicitly be ineligible for training')
    if 'DebugConfiguration' in manifest['databases']:
        manifest = {**manifest, 'databases': {name: manifest['databases'][key]['copy'] for name, key in (('configuration', 'DebugConfiguration'), ('gameplay', 'DebugGameplay'), ('localization', 'DebugLocalization'))}}
    work_root = _resolve_resource_path(_resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_host.py')))).resolve().parent.parent / 'work').resolve()
    for name in ('configuration', 'gameplay'):
        entry = manifest['databases'][name]
        path = _resolve_resource_path(_resolve_resource_path(Path(entry['path']))).resolve()
        if not path.is_relative_to(work_root):
            raise ValueError('Native bootstrap only opens workspace fixture copies')
        if sha256(path) != entry['sha256']:
            raise ValueError(f'Changed {name} database fixture')
        with _resolve_resource_path(path).open('rb') as stream:
            header = stream.read(16)
        if header != b'SQLite format 3\x00':
            raise ValueError(f'Invalid {name} SQLite header')
    return manifest

def virtual(core, object_pointer, slot, expected_rva, result, *arguments):
    vtable = C.c_void_p.from_address(object_pointer).value
    address = C.c_void_p.from_address(vtable + slot).value
    if address != core._handle + expected_rva:
        raise ValueError(f'Unverified native method at slot {hex(slot)}')
    return C.WINFUNCTYPE(result, C.c_void_p, *arguments)(address)

def initialize_context(core, context, manifest_path, dll_directory, emit, *, context_profile=None, candidate_bundle=None):
    expansion = False
    if context_profile is not None:
        from civ6_host.runtime.native.native_core_context_profiles import NativeCoreContextProfile
        from civ6_host.runtime.native.native_core_context_profiles import profile_for_core
        from civ6_host.runtime.native.native_core_context_profiles import require_executable_profile
        if type(context_profile) is not NativeCoreContextProfile:
            raise ValueError('Expected an exact native context profile')
        if (context_profile.ruleset, context_profile.mode) not in (('base', 'init'), ('xp1', 'context'), ('xp2', 'context')):
            raise ValueError('Context initialization profile is not admitted')
        if context_profile.ruleset == 'xp2':
            from civ6_host.runtime.saved_load_profiles import XP2_CORE_SHA256
            if context_profile.source_core_sha256 != XP2_CORE_SHA256:
                raise ValueError('XP2 context profile engine identity differs')
        if context_profile.execution_image is not getattr(core, '_civ6_host_execution_image', None):
            raise ValueError('Context profile differs from the retained loaded execution identity')
        require_executable_profile(context_profile)
        actual_profile = profile_for_core(core._name, mode=context_profile.mode,
            shared_dependency_directory=dll_directory,
            execution_image=context_profile.execution_image)
        if actual_profile != context_profile:
            raise ValueError('Context profile differs from installed source-bound engine')
        expansion = context_profile.ruleset in ('xp1', 'xp2')
    if candidate_bundle is not None:
        if not expansion:
            raise ValueError('Captured Init inputs require the explicit XP1 context candidate')
        if context_profile.ruleset == 'xp2':
            from civ6_host.runtime.xp2_saved_init import bind_candidate
        else:
            from civ6_host.runtime.xp1_saved_load import bind_candidate
        bind_candidate(candidate_bundle, context_profile, manifest_path)
    if expansion and context_profile.ruleset == 'xp2' and candidate_bundle is None:
        raise ValueError('XP2 Init requires an explicit captured input owner')
    manifest = validate_fixture(manifest_path)
    db_path = _resolve_resource_path(Path(dll_directory)) / 'DatabaseDLL_FinalRelease.dll'
    shared_dependencies = (context_profile.shared_dependency_profile
        if context_profile is not None else None)
    if shared_dependencies is not None:
        db_path = shared_dependencies.verify_library_path('DatabaseDLL_FinalRelease.dll', db_path)
        database_sha256 = shared_dependencies.dependency_sha256['DatabaseDLL_FinalRelease.dll']
    else:
        database_sha256 = DATABASE_SHA256
    if sha256(db_path) != database_sha256:
        raise ValueError('Unrecognized Database DLL')
    database = C.WinDLL(str(db_path))
    initialize = getattr(database, '?Initialize@Database@@YA_NXZ')
    initialize.argtypes, initialize.restype = ([], C.c_bool)
    emit('before_database_initialize')
    if not initialize():
        raise RuntimeError('Native Database::Initialize returned false')
    emit('database_initialized', dll_sha256=database_sha256)
    native_free = None
    if not expansion:
        free_address = C.c_void_p.from_address(core._handle + 7722592).value
        if not free_address:
            raise RuntimeError('Missing pinned GameCore aligned-free import')
        native_free = C.WINFUNCTYPE(None, C.c_void_p)(free_address)
    host = DiagnosticHost(_resolve_resource_path(Path(manifest['databases']['configuration']['path'])), _resolve_resource_path(Path(manifest['databases']['gameplay']['path'])), emit, native_free)
    host.log_writers.enable_native_sink(_resolve_resource_path(_resolve_resource_path(Path(manifest_path))).resolve().parent / 'native-logs')
    host.core_base = core._handle
    if not expansion:
        from civ6_host.runtime.native.native_events import NativeEventRecorder
        host.event_recorder = NativeEventRecorder(_resolve_resource_path(_resolve_resource_path(Path(manifest_path))).resolve().parent / 'native-events', host)
        host.event_recorder.install()
    host.database = database
    host.manifest = manifest
    host.dll_directory = _resolve_resource_path(Path(dll_directory))
    if context_profile is not None:
        host.context_profile = context_profile
    if shared_dependencies is not None:
        host._civ6_host_shared_dependencies = shared_dependencies
        core._civ6_host_shared_dependencies = shared_dependencies
    core._diagnostic_host = host
    if expansion and context_profile.ruleset == 'xp2':
        from civ6_host.runtime.xp2_context_lifecycle import initialize_xp2_context, install_xp2_teardown_callbacks
        from civ6_host.runtime.native.native_probe import Windows
        paths = Windows().modules()
        host.context_init_receipt = initialize_xp2_context(core, context, host,
            configuration_path=_resolve_resource_path(Path(manifest['databases']['configuration']['path'])),
            gameplay_path=_resolve_resource_path(Path(manifest['databases']['gameplay']['path'])),
            private_root=_resolve_resource_path(Path(manifest_path)).resolve().parent,
            module_paths=paths, emit=emit, candidate_bundle=candidate_bundle)
        emit('xp2_adapter_receipt', receipt=host.context_init_receipt)
        host.context_teardown_receipt = install_xp2_teardown_callbacks(core, context, host,
            host.context_init_receipt, module_paths=paths, emit=emit, candidate_bundle=candidate_bundle)
        if host.context_teardown_receipt.get('installed') is not True:
            raise RuntimeError('XP2 teardown binding did not complete')
        return host
    if expansion:
        from civ6_host.runtime.native.native_xp1_context_init import initialize_xp1_context
        from civ6_host.runtime.native.native_xp1_teardown_adapter import install_xp1_teardown_callbacks
        from civ6_host.runtime.native.native_probe import Windows
        root = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_host.py')))).resolve().parents[1]
        host.context_init_receipt = initialize_xp1_context(core, context, host, configuration_path=_resolve_resource_path(Path(manifest['databases']['configuration']['path'])), gameplay_path=_resolve_resource_path(Path(manifest['databases']['gameplay']['path'])), private_root=_resolve_resource_path(_resolve_resource_path(Path(manifest_path))).resolve().parent, module_paths=Windows().modules(), emit=emit, candidate_bundle=candidate_bundle)
        emit('xp1_adapter_receipt', receipt=host.context_init_receipt)
        host.context_teardown_receipt = install_xp1_teardown_callbacks(core, context, host, host.context_init_receipt, project_root=root, module_paths=Windows().modules(), emit=emit, candidate_bundle=candidate_bundle)
        if host.context_teardown_receipt.get('installed') is not True:
            raise RuntimeError('XP1 teardown binding did not complete')
        return host
    setter = virtual(core, context, 96, 4387968, None, C.c_void_p)
    initializer = virtual(core, context, 40, 4383536, C.c_bool)
    initialized = virtual(core, context, 56, 4383648, C.c_bool)
    emit('before_host_install', adapter_scope='diagnostic; unsupported calls abort')
    setter(context, host.pointer)
    emit('host_installed', declared_events=len(host.filters.entries))
    emit('before_native_initialize')
    started = time.perf_counter()
    result = initializer(context)
    emit('native_initialized', return_value=result, game_initialized=initialized(context), game_created=False, simulation_ready=False, native_turns_executed=0, operation_seconds=time.perf_counter() - started)
    inner = C.c_void_p.from_address(context + 8).value
    connections = {'configuration': bool(C.c_void_p.from_address(inner + 80).value), 'gameplay': bool(C.c_void_p.from_address(inner + 88).value)}
    emit('native_database_connections', **connections)
    if not result or not initialized(context) or (not all(connections.values())):
        raise RuntimeError('Native bootstrap initialization was incomplete')
    return host

def finish_database(host, emit):
    host.log_writers.close()
    if getattr(host, 'localization_initialized', False):
        from civ6_host.runtime.native.native_localization import finish_localization
        finish_localization(host, shared_dependency_profile=getattr(
            host, '_civ6_host_shared_dependencies', None))
    shutdown = getattr(host.database, '?Shutdown@Database@@YA_NXZ')
    shutdown.argtypes, shutdown.restype = ([], C.c_bool)
    result = shutdown()
    emit('database_shutdown', return_value=result)
    if not result:
        raise RuntimeError('Native Database::Shutdown returned false')
    if getattr(host, 'event_recorder', None) is not None:
        host.event_recorder.close()
    unchanged = {name: sha256(_resolve_resource_path(Path(entry['path']))) == entry['sha256'] for name, entry in host.manifest['databases'].items()}
    emit('fixture_unchanged', databases=unchanged)
    if not all(unchanged.values()):
        raise RuntimeError('Native initialization changed a fixture database')
    return result

def prepare_context(core, context, emit, *, saved_load_abi=None, context_profile=None, null_tuner_diagnostic=False):
    """Enter the native service/cache construction path, not map generation.

    Outer +40 forwards to inner +50, FUN_18003ca90. All services it requests
    still go through the diagnostic host, which terminates on unknown methods.
    """
    if context_profile is not None:
        if saved_load_abi is not None:
            raise ValueError('Context-only preparation cannot claim saved Load admission')
        from civ6_host.runtime.xp1_prepare import prepare as prepare_xp1
        return prepare_xp1(core, context, core._diagnostic_host, context_profile, emit, null_tuner_diagnostic=null_tuner_diagnostic)
    if null_tuner_diagnostic:
        raise ValueError('Explicit NULL Tuner diagnostic requires an XP1 context profile')
    from civ6_host.runtime.native.native_localization import initialize_localization
    from civ6_host.runtime.saved_load_profiles import BASE_CORE_SHA256
    from civ6_host.runtime.saved_load_profiles import profile_for_sha
    from civ6_host.runtime.saved_load_profiles import require_saved_load_admission
    abi = require_saved_load_admission(profile_for_sha(BASE_CORE_SHA256) if saved_load_abi is None else saved_load_abi)
    host = core._diagnostic_host
    initialize_localization(host, host.dll_directory)
    prepare = virtual(core, context, 64, abi.prepare_rva, None)
    emit('before_game_services', scope='native context services; no map or turn')
    started = time.perf_counter()
    prepare(context)
    inner = C.c_void_p.from_address(context + 8).value
    emit('game_services', operation_seconds=time.perf_counter() - started, core_game_object_nonnull=bool(C.c_void_p.from_address(inner + 96).value), diagnostic_faults=['GameCore_Tuner unavailable'] if getattr(host, 'tuner_unavailable_probe', False) else [], script_service_reproduced=False, game_created=False, simulation_ready=False, native_turns_executed=0)

def release_game_services(core, context, emit, *, loaded_lifetime=None):
    """Outer+48 unloads a live game before general context destruction.

    Source: native-shutdown-service.json. Inner+58 shuts down the game while
    Rules_Manager is still alive; general Uninit alone clears that service
    first and is not the live-game unload path.
    """
    if loaded_lifetime is not None:
        from civ6_host.runtime.xp1_loaded_lifetime import require_lifetime
        token = require_lifetime(loaded_lifetime)
        rva = token.before_unload(core, context)
        C.WINFUNCTYPE(None, C.c_void_p)(core._handle + rva)(context)
        token.after_unload()
        return
    from civ6_host.runtime.native.native_setup import local_reader
    from civ6_host.runtime.native.native_setup import inspect_setup
    read = local_reader()
    inspect_setup(core._handle, context, read)
    inner = int.from_bytes(read(context + 8, 8), 'little')
    inner_vtable = int.from_bytes(read(inner, 8), 'little')
    if int.from_bytes(read(inner_vtable + 88, 8), 'little') != core._handle + 248000:
        raise ValueError('Unverified native live-game release slot')
    release = virtual(core, context, 72, 4388240, None)
    emit('before_native_game_services_release', slot='0x48', inner_target_rva='0x3c8c0')
    release(context)
    if int.from_bytes(read(inner + 96, 8), 'little') or int.from_bytes(read(core._handle + 9158520, 8), 'little'):
        raise RuntimeError('Native live-game release did not clear owned services')
    emit('native_game_services_released', game_object_null=True, rules_manager_null=True)
