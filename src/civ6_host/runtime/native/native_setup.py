"""Pinned setup inspection and explicit configuration probes in disposable contexts."""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import ctypes as C
import struct
OUTER_VTABLE_RVA = 7987232
INNER_VTABLE_RVA = 8155256
INNER_SIZE = 6784
SETUP_OFFSET = 3456
MAP_SCRIPT_KEY = 1675134810
SETUP_FIELDS = {'configuration_descriptor': 128, 'normalized_configuration': 136, 'map_descriptor': 3112, 'normalized_map': 3120}

def local_reader():
    """Use an OS-checked copy, so an invalid pointer is an error, not a dereference."""
    kernel = C.WinDLL('kernel32', use_last_error=True)
    kernel.GetCurrentProcess.argtypes, kernel.GetCurrentProcess.restype = ([], C.c_void_p)
    kernel.ReadProcessMemory.argtypes = [C.c_void_p, C.c_void_p, C.c_void_p, C.c_size_t, C.POINTER(C.c_size_t)]
    kernel.ReadProcessMemory.restype = C.c_int
    process = kernel.GetCurrentProcess()

    def read(address, size):
        if not address or not 0 < size <= INNER_SIZE:
            raise ValueError('Invalid bounded native inspection request')
        buffer = C.create_string_buffer(size)
        count = C.c_size_t()
        if not kernel.ReadProcessMemory(process, address, buffer, size, C.byref(count)):
            raise C.WinError(C.get_last_error())
        if count.value != size:
            raise RuntimeError('Incomplete native memory copy')
        return buffer.raw
    return read

def inspect_setup(core_base, context, read):
    """Check object identities before reading bounded fields; never follow them."""
    outer = read(context, 16)
    outer_vtable, inner_address = struct.unpack('<QQ', outer)
    if outer_vtable != core_base + OUTER_VTABLE_RVA or not inner_address:
        raise ValueError('Unexpected GameCore outer context identity')
    inner = read(inner_address, INNER_SIZE)
    if struct.unpack_from('<Q', inner)[0] != core_base + INNER_VTABLE_RVA:
        raise ValueError('Unexpected GameCore inner context identity')
    fields = {name: struct.unpack_from('<Q', inner, SETUP_OFFSET + offset)[0] for name, offset in SETUP_FIELDS.items()}
    return {'outer_vtable_rva': hex(OUTER_VTABLE_RVA), 'inner_vtable_rva': hex(INNER_VTABLE_RVA), 'inner_size_bytes': INNER_SIZE, 'setup_offset': hex(SETUP_OFFSET), 'fields': {name: {'setup_offset': hex(SETUP_FIELDS[name]), 'raw_value': value, 'nonnull': bool(value)} for name, value in fields.items()}, 'interpretation': 'Raw descriptor fields, not strings or proof of valid game configuration', 'configuration_modified': False, 'game_created': False, 'native_turns_executed': 0}

def inspect_setup_interfaces(core_base, snapshot, read):
    """Read only known call slots, accepting tables located in the pinned image."""
    headers = read(core_base, 4096)
    pe_offset = struct.unpack_from('<I', headers, 60)[0]
    if headers[:2] != b'MZ' or not 0 < pe_offset < 3840 or headers[pe_offset:pe_offset + 4] != b'PE\x00\x00' or (struct.unpack_from('<H', headers, pe_offset + 24)[0] != 523):
        raise ValueError('Invalid pinned PE64 headers')
    image_size = struct.unpack_from('<I', headers, pe_offset + 24 + 56)[0]
    interfaces = {}
    for name, field in snapshot['fields'].items():
        address = field['raw_value']
        if not address:
            interfaces[name] = None
            continue
        vtable = struct.unpack('<Q', read(address, 8))[0]
        slots = (0, 8, 16, 88, 168, 312, 376, 464) if name.endswith('descriptor') else (0, 8, 16, 88, 312, 376)
        if not core_base <= vtable < core_base + image_size - max(slots) - 8:
            raise ValueError(f'{name} table is outside the pinned GameCore image')
        targets = {}
        for slot in slots:
            target = struct.unpack('<Q', read(vtable + slot, 8))[0]
            targets[hex(slot)] = {'raw_value': target, 'gamecore_rva': hex(target - core_base) if core_base <= target < core_base + image_size else None}
        interfaces[name] = {'vtable_rva': hex(vtable - core_base), 'sampled_slots': targets}
    return interfaces

def emit_setup_snapshot(core, context, emit, moment):
    read = local_reader()
    snapshot = inspect_setup(core._handle, context, read)
    snapshot['interfaces'] = inspect_setup_interfaces(core._handle, snapshot, read)
    emit('native_setup_snapshot', moment=moment, **snapshot)

def inspect_player_record_prefix(core, context, emit):
    """Read the source-backed fixed record vector; do not assign player meaning."""
    read = local_reader()
    inspect_setup(core._handle, context, read)
    inner = struct.unpack('<QQ', read(context, 16))[1]
    setup = inner + SETUP_OFFSET
    begin, end, capacity = struct.unpack('<QQQ', read(setup + 144, 24))
    if begin != setup + 184 or end - begin != 64 * 32 or capacity != end:
        raise ValueError('Unexpected native setup record vector layout')
    records = []
    for index in range(2):
        raw = read(begin + index * 32, 32)
        record_index = struct.unpack_from('<i', raw)[0]
        provider, value, owner = struct.unpack_from('<QQQ', raw, 8)
        value_vtable = struct.unpack('<Q', read(value, 8))[0] if value else None
        records.append({'vector_index': index, 'record_index': record_index, 'provider_nonnull': bool(provider), 'value_nonnull': bool(value), 'value_vtable_rva': hex(value_vtable - core._handle) if value_vtable else None, 'owner_is_setup': owner == setup})
    emit('native_setup_record_prefix', record_count=64, records=records, player_assignment_validated=False, configuration_modified=False)

def probe_map_path_roundtrip(core, context, emit, paths=('Maps/Continents.lua', 'Test/Été.lua')):
    """Set two diagnostic paths in this disposable context using native copies.

    +100 copies UTF-16 through +B0 (747050); 111860/111970 are the getters
    consumed by native new-game map resolution. No game is started here.
    """
    read = local_reader()
    snapshot = inspect_setup(core._handle, context, read)
    inner = struct.unpack('<QQ', read(context, 16))[1]
    descriptor = inner + SETUP_OFFSET + 3112
    target = snapshot['fields']['normalized_map']['raw_value']
    if not target:
        raise RuntimeError('Native normalized map object is absent')
    vtable = struct.unpack('<Q', read(target, 8))[0]
    if vtable != core._handle + 8507296:
        raise ValueError('Unknown configuration object vtable')
    setter_address = struct.unpack('<Q', read(vtable + 256, 8))[0]
    if setter_address != core._handle + 7630688:
        raise ValueError('Unverified UTF-16 setter')
    setter = C.WINFUNCTYPE(C.c_void_p, C.c_void_p, C.c_uint32, C.c_void_p)(setter_address)
    copy_path = C.WINFUNCTYPE(C.c_bool, C.c_void_p, C.c_void_p, C.c_uint32)(core._handle + 1120352)
    has_path = C.WINFUNCTYPE(C.c_bool, C.c_void_p)(core._handle + 1120624)
    key = struct.unpack('<I', read(core._handle + 9162016, 4))[0]
    if key != MAP_SCRIPT_KEY:
        raise ValueError('Native MAP_SCRIPT key disagrees with pinned initializer')

    def get_path():
        output = (C.c_uint16 * 260)()
        copied = bool(copy_path(descriptor, output, 260))
        units = list(output)
        if 0 not in units:
            raise RuntimeError('Native path did not terminate inside destination buffer')
        text = bytes(output)[:units.index(0) * 2].decode('utf-16-le')
        return {'has_path': bool(has_path(descriptor)), 'copy_returned': copied, 'path': text}
    observed = get_path()
    emit('native_map_path_before', key=key, key_global_rva='0x8bcd20', **observed)
    for text in paths:
        if not isinstance(text, str) or not text or '\x00' in text or (len(text.encode('utf-16-le')) >= 518):
            raise ValueError('Diagnostic map path must fit the native 260-unit buffer')
        encoded = text.encode('utf-16-le') + b'\x00\x00'
        source = C.create_string_buffer(encoded, len(encoded))
        returned = setter(target, key, C.addressof(source))
        C.memset(C.addressof(source), 88, len(encoded))
        observed = get_path()
        emit('native_map_path_roundtrip', key=key, requested=text, setter_return_raw=returned, setter_return_semantics='not used as success flag', caller_buffer_overwritten=True, **observed, game_created=False, native_turns_executed=0)
        if not observed['has_path'] or not observed['copy_returned'] or observed['path'] != text:
            raise RuntimeError('Native map path roundtrip mismatch')
    return observed

def probe_new_game_boundary(core, context, dll_path, emit, *, map_path_prepared=False, application_configuration=None):
    """Enter NewGame with the current map config, observing the next missing service.

    This diagnostic supplies no complete player/game configuration and does not
    validate a returned success as a playable game. No descriptor is fabricated.
    """
    from pathlib import Path
    import hashlib
    from civ6_host.runtime.native.native_host import virtual
    if type(map_path_prepared) is not bool:
        raise ValueError('Map path lifecycle must be an explicit Boolean')
    path = _resolve_resource_path(Path(dll_path)).parents[2] / 'Assets/Maps/Continents.lua'
    if not _resolve_resource_path(path).is_file():
        raise FileNotFoundError(path)
    observed = probe_map_path_roundtrip(core, context, emit, paths=() if map_path_prepared else (str(path),))
    if not observed['has_path'] or not observed['copy_returned'] or observed['path'] != str(path):
        raise RuntimeError('Prepared native MAP_SCRIPT differs before NewGame')
    if map_path_prepared:
        emit('native_map_path_finalization_readback_verified', path=observed['path'], native_path_modified=False, eligible_for_training=False)
    new_game = virtual(core, context, 304, 4383568, C.c_bool, C.c_void_p, C.c_void_p)
    descriptor = None
    if application_configuration is not None:
        application_configuration.require_context(core._handle, context)
        if application_configuration.new_game_entered:
            raise ValueError('This application configuration has already entered NewGame')
        descriptor = application_configuration.snapshot()['descriptor']
        core_descriptor = inspect_setup(core._handle, context, local_reader())['fields']['configuration_descriptor']['raw_value']
        if descriptor == core_descriptor:
            raise ValueError('NewGame source cannot alias its destination provider')
        application_configuration.new_game_entered = True
    emit('before_native_new_game', script_path=str(path), script_sha256=hashlib.sha256(_resolve_resource_path(path).read_bytes()).hexdigest(), source_descriptor_null=descriptor is None, error_reporter_null=True, source_descriptor_profile='separate-application-provider' if descriptor else 'existing-core-provider-diagnostic', player_configuration_complete=False, training_ready=False)
    returned = new_game(context, descriptor, None)
    emit('native_new_game_returned', return_value=bool(returned), game_validated=False, player_configuration_complete=False, training_ready=False, native_turns_executed=0)
    return bool(returned)
