"""Source-decoded B8515A41 producer, with explicit empty visual registry.

This is an EXE presentation record, not an observation for a player. Native
Core getters supply unit and civilization data. No record is consumed here.
The headless visual profile has no color/style registrations; its equivalence
to a populated EXE UI is not claimed. GAME_MODE is read from native config.
"""
from __future__ import annotations
from civ6_host.runtime import turn_unit_event_profile as _turn_units
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import ctypes as C
from contextlib import contextmanager
from pathlib import Path
import struct
from civ6_host.runtime.native.native_application_mirror import decode_scalar
from civ6_host.runtime.native import native_app_ownership
from civ6_host.runtime.native.native_host import type_name_hash
from civ6_host.runtime.native.native_setup import local_reader
from civ6_host.runtime.native.native_source_cache import load_pinned_json
KIND = 3092339265
CALLBACK = 1395808
VISUAL_PROFILE = 'empty-style-registry'
OWNER_PROOF_SHA256 = '8a37b98436dbe44452f5a564f76e2a9d584eaf5dc8d0816a23191b8b96348660'
SOURCE_PROOF_SHA256 = '7ef7e1566f35de287364aafaa692b9b7a0440a5c7156de00c157492e9e7adf50'
RECORDS_PROOF_SHA256 = '0421e7df0cc5152a987c25f8e8f8ce0562fbd1ec09328fb69045bf5c4805c1cf'
APPLICATION_MODE_PROOF_SHA256 = '271b025c3e906e6f11bc899d881a9a3aa6e762db4477b642db72616c69ae2466'
_ROOT = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_unit_created_event.py')))).resolve().parents[1]
TABLES = {'outer': (7987232, {184: 4382880, 256: 4382336, 144: 4382432}), 'player': (7992320, {8: 4421040, 272: 4423648, 24: 4422464, 40: 4422784}), 'units': (7994008, {8: 4432576, 16: 4432608}), 'unit': (7995536, {16: 4440784, 40: 4441824, 80: 4441376, 88: 4441216, 136: 4442096}), 'data': (7988512, {8: 4388560, 872: 4405616, 608: 4403344, 776: 4402704}), 'game': (7990488, {8: 4409168, 296: 4410112})}

def verify_source_evidence():
    mode = load_pinned_json(_ROOT / 'evidence/native-event-e5b20b82' / (APPLICATION_MODE_PROOF_SHA256 + '.json'), APPLICATION_MODE_PROOF_SHA256)
    if mode['schema'] != 'civ6rl.native_event_e5b20b82.static.v1' or mode['images']['exe_sha256'] != 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63':
        raise RuntimeError('UnitCreated application mode binding source changed')
    owner = load_pinned_json(_ROOT / 'evidence/native-unit-created-owner-domain' / (OWNER_PROOF_SHA256 + '.json'), OWNER_PROOF_SHA256)
    source = load_pinned_json(_ROOT / 'evidence/native-unit-created-event.json', SOURCE_PROOF_SHA256)
    records = load_pinned_json(_ROOT / 'evidence/native-application-mirror-records' / (RECORDS_PROOF_SHA256 + '.json'), RECORDS_PROOF_SHA256)
    if owner.get('schema') != 'civ6rl.native_unit_created_owner_domain.static.v1' or source.get('schema') != 'civ6rl.native_unit_created_event.v1' or owner.get('derived_from', {}).get('sha256') != SOURCE_PROOF_SHA256 or (source.get('sources') != {'exe': 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63', 'core': 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'}) or (records.get('contract', {}).get('record_count') != 64) or (records.get('contract', {}).get('exe_record_stride') != 64):
        raise RuntimeError('UnitCreated source/domain proof changed')

    def at(body):
        return {i['va']: i['text'] for f in body['fragments'] for i in f['instructions']}
    callback = at(source['exe']['0x154c60'])
    local = at(source['exe']['0x149560'])
    checks = {'0x140154c8d': 'movsx ecx, word ptr [rdx + 8]', '0x140154cfc': 'mov rax, qword ptr [rsi]', '0x140154d11': 'mov rax, qword ptr [rax]', '0x140154d1d': 'je 0x140154f40', '0x140154d66': 'mov rax, qword ptr [rbx]', '0x140154e6c': 'call qword ptr [rax + 0x28]', '0x140154e71': 'call 0x140149560', '0x140154f38': 'call qword ptr [rax + 8]', '0x140154f96': 'call 0x140127bd0', '0x140154fb3': 'call 0x1409898c0', '0x140154fc8': 'call qword ptr [rax + 0x10]', '0x140154fd1': 'call qword ptr [rax + 8]', '0x140154fda': 'call qword ptr [rax + 8]'}
    if any((callback.get(va) != text for va, text in checks.items())):
        raise RuntimeError('UnitCreated callback lifetime/branch changed')
    if local.get('0x140149570') != 'call 0x140100820' or local.get('0x1401495c9') != 'call qword ptr [rax + 0x128]' or local.get('0x1401495db') != 'call qword ptr [rdx + 8]' or (local.get('0x1401495ed') != 'xor al, al'):
        raise RuntimeError('UnitCreated local-team helper lifetime changed')
    return (owner, source)

def _identity(owner, identifier):
    if type(owner) is not int or not 0 <= owner < 64:
        raise ValueError('Unit-created owner outside proven EXE configuration records 0..63')
    if type(identifier) is not int or not 0 <= identifier <= 4294967295:
        raise ValueError('Unverified native unit identifier')

def _blob(raw, read, tag):
    if len(raw) != 24 or struct.unpack_from('<H', raw)[0] != tag:
        raise ValueError('Unverified unit-created blob tag')
    pointer, size, flags = struct.unpack_from('<QII', raw, 8)
    if not pointer or size != 8 or flags != 553648129:
        raise ValueError('Unverified unit-created blob allocation')
    value = bytes(read(pointer, 8))
    if len(value) != 8:
        raise ValueError('Incomplete unit-created blob')
    return value

def decode_fields(fields, read):
    expected = {360746564, 1849331523, 2353434172, 2716180809, 2717631346, 3606901732, 4032072631}
    if set(fields) != expected or decode_scalar(fields[2716180809], 3) != 0:
        raise ValueError('Unverified unit-created argument set')
    owner, _, identifier = struct.unpack('<hHI', _blob(fields[4032072631], read, 1024))
    _identity(owner, identifier)
    position = _blob(fields[2353434172], read, 13)
    decode_scalar(fields[3606901732], 2)
    return {'owner': owner, 'identifier': identifier, 'position': position, 'descriptor_54': decode_scalar(fields[2717631346], 2), 'effect': decode_scalar(fields[360746564], 3), 'suppress_flag': bool(decode_scalar(fields[1849331523], 1))}

@contextmanager
def query_native_values(base, context, owner, identifier, *, application=None, application_mode_reader=None, read=None, invoke=None, core_sha256='d7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3', candidate_backend=None):
    """Lease native values through the caller's encode/enqueue operation.

    Source order is game release, data release, yield for hook/writer/unlock,
    then unit(+10,1), collection(+8), player(+8). The persistent outer context
    replaces the EXE's independently acquired/released temporary references.
    Null player/collection/data are not source-success branches. Null unit
    would write partially uninitialized data, so remains explicitly refused.
    """
    _turn_tables = _turn_units.select_tables(core_sha256, TABLES)
    _identity(owner, identifier)
    if any((type(p) is not int or not 0 < p <= 18446744073709551615 for p in (base, context))):
        raise ValueError('Invalid native unit-created base/context')
    if application is not None:
        if application_mode_reader is not None:
            raise ValueError('Application mode reader seam cannot replace the native application provider')
        application.require_context(base, context)
    elif invoke is None or not callable(application_mode_reader):
        raise ValueError('UnitCreated requires its native application configuration for GAME_MODE')
    read = read or local_reader()

    def checked_read(pointer, size):
        value = read(pointer, size)
        if not isinstance(value, (bytes, bytearray, memoryview)) or len(value) != size:
            raise ValueError('Incomplete unit-created native read')
        return bytes(value)

    def verify(pointer, table, *, release_only=False):
        vt, slots = _turn_tables[table]
        if type(pointer) is not int or not 0 < pointer <= 18446744073709551615:
            raise ValueError('Absent or invalid ' + table + ' interface; native fields unavailable')
        if int.from_bytes(checked_read(pointer, 8), 'little') != base + vt:
            raise ValueError('Unexpected ' + table + ' interface')
        for offset, rva in slots.items():
            if release_only and offset != (16 if table == 'unit' else 8):
                continue
            if int.from_bytes(checked_read(base + vt + offset, 8), 'little') != base + rva:
                raise ValueError('Unexpected ' + table + ' callback')

    def call(table, slot, result, pointer, *args):
        rva = _turn_tables[table][1][slot]
        if invoke is not None:
            return invoke(table, slot, pointer, *args)
        fn = C.WINFUNCTYPE(result, C.c_void_p, *[C.c_uint32] * len(args))(base + rva)
        return fn(pointer, *args)

    def text_hash(pointer):
        if not pointer:
            raise ValueError('Native graphic string absent; payload would be unspecified')
        raw = bytearray()
        for offset in range(512):
            byte = checked_read(pointer + offset, 1)
            if byte == b'\x00':
                return type_name_hash(raw.decode('ascii'))
            raw.extend(byte)
        raise ValueError('Unbounded native graphic string')
    verify(context, 'outer')

    def read_application_game_mode():
        mode = application_mode_reader(application) if application is None else _turn_units.read_application_mode(application, core_sha256=core_sha256, candidate_backend=candidate_backend)
        if type(mode) is not int or not 0 <= mode <= 4294967295:
            raise ValueError('Application GAME_MODE must be an exact uint32')
        return mode
    acquired = []

    def acquire(table, pointer):
        verify(pointer, table, release_only=True)
        acquired.append((table, pointer))
        verify(pointer, table)
        return pointer

    def release_last(table):
        current, pointer = acquired.pop()
        if current != table:
            raise RuntimeError('Unexpected UnitCreated release order')
        if table == 'unit':
            call(table, 16, C.c_void_p, pointer, 1)
        else:
            call(table, 8, None, pointer)
    try:
        player = acquire('player', call('outer', 184, C.c_void_p, context, owner))
        units = acquire('units', call('player', 272, C.c_void_p, player))
        unit = acquire('unit', call('units', 16, C.c_void_p, units, identifier))
        unit_type = call('unit', 40, C.c_uint32, unit)
        data = acquire('data', call('outer', 256, C.c_void_p, context))
        original_hash = text_hash(call('data', 872, C.c_void_p, data, unit_type))
        display_hash = original_hash
        alternate = call('unit', 80, C.c_uint32, unit)
        if alternate != 4294967295:
            alt_string = call('data', 608, C.c_void_p, data, alternate)
            if alt_string:
                display_hash = text_hash(alt_string)
        civilization = call('player', 24, C.c_uint32, player)
        civ_hash = text_hash(call('data', 776, C.c_void_p, data, civilization))
        field_58 = call('unit', 88, C.c_uint32, unit)
        special = bool(call('unit', 136, C.c_bool, unit))
        team = call('player', 40, C.c_uint32, player)
        game_mode = read_application_game_mode()
        local = game_mode == 3915931367
        if not local and team != 4294967295:
            game = call('outer', 144, C.c_void_p, context)
            if game:
                game = acquire('game', game)
                local = team == call('game', 296, C.c_uint32, game)
                release_last('game')
        release_last('data')
        yield {'unit_type': unit_type, 'graphic_hash': display_hash, 'original_graphic_hash': original_hash, 'civilization_graphic_hash': civ_hash, 'field_58': field_58, 'special': special, 'local_team': local, 'native_game_mode': game_mode}
    finally:
        while acquired:
            release_last(acquired[-1][0])

def native_values(base, context, owner, identifier, *, application=None, application_mode_reader=None, read=None, invoke=None, core_sha256='d7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3', candidate_backend=None):
    """Standalone read compatibility; enqueue callers must use the lease above."""
    with query_native_values(base, context, owner, identifier, application=application, application_mode_reader=application_mode_reader, read=read, invoke=invoke, core_sha256=core_sha256, candidate_backend=candidate_backend) as values:
        return values

def encode_record(sequence, fields, values, *, visual_profile):
    if visual_profile != VISUAL_PROFILE:
        raise ValueError('Visual configuration registry not implemented')
    _identity(fields['owner'], fields['identifier'])
    from civ6_host.runtime.native.native_host_events import encode_player_event
    record = bytearray(encode_player_event(sequence, fields['owner'], False))
    record.extend(b'\x00' * 64)
    struct.pack_into('<II', record, 0, 160, 28)
    struct.pack_into('<I', record, 72, 0)
    record[80:] = b'\x00' * 80
    struct.pack_into('<I', record, 80, sequence)
    struct.pack_into('<hHI', record, 88, fields['owner'], 1, fields['identifier'])
    record[96:104] = fields['position']
    struct.pack_into('<I', record, 104, values['unit_type'])
    effect = 263933793 if values['special'] or fields['effect'] == 263933793 else 4294967295
    struct.pack_into('<8I', record, 112, values['graphic_hash'], values['original_graphic_hash'], type_name_hash('default'), 0, values['civilization_graphic_hash'], values['field_58'], fields['descriptor_54'], effect)
    struct.pack_into('<??', record, 144, not fields['suppress_flag'], values['local_team'])
    return bytes(record)
verify_source_evidence()
