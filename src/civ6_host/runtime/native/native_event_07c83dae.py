"""Source-backed07C83DAE plot snapshot producer; no guessed query values."""
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import ctypes as C
import hashlib
from pathlib import Path
import struct
from collections.abc import Mapping
from contextlib import contextmanager
from civ6_host.runtime.native import native_event_5d0f4014 as snapshot_source
from civ6_host.runtime.native import native_event_fa5b1159 as shared
from civ6_host.runtime.native.native_source_cache import load_pinned_json
EVENT_KIND, RECORD_TYPE, RECORD_SIZE = (130563502, 165, 144)
PINNED_EVIDENCE_SHA256 = 'b30f717dc8970dd34f5c6ceedcbef18e3b98491282c6f30ac1a9730f5bfe4d8d'
_PROOF = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_event_07c83dae.py')))).resolve().parents[1] / 'evidence/native-event-07c83dae' / f'{PINNED_EVIDENCE_SHA256}.json'
_GUARD = b'\xd3' * 16
_SNAPSHOT_SIZE = 24

def verify_source_evidence():
    proof = load_pinned_json(_PROOF, PINNED_EVIDENCE_SHA256)
    if proof['schema'] != 'civ6rl.native_event_07c83dae.static.v1' or proof['registration']['callback_va'] != '0x14013fb30' or proof['images']['exe_sha256'] != shared.EXE_SHA256 or (proof['images']['core_sha256'] != shared.CORE_SHA256) or (proof['contract']['record']['type'] != '0xa5') or (proof['shared']['secondary_config']['sha256'] != shared.PINNED_EVIDENCE_SHA256):
        raise RuntimeError('07C83DAE source identity changed')
    callback = {i['va']: i['text'] for f in proof['captures']['callback']['fragments'] for i in f['instructions']}
    for va, text in {'0x14013fc16': 'call qword ptr [rax + 8]', '0x14013fc8e': 'cmp edi, -1', '0x14013fd1f': 'call 0x140135c70', '0x14013fd3c': 'call 0x1409898c0', '0x14013fd4c': 'call qword ptr [rax + 8]'}.items():
        if callback.get(va) != text:
            raise RuntimeError('07C83DAE owner gate or writer/release order changed')
    return proof

def _fields(fields):
    snapshot_source._check_position(fields)
    if set(fields) != {'position_bytes', 'x', 'y', 'selector', 'source_value', 'descriptor_tail'} or type(fields['selector']) is not int or (not 0 <= fields['selector'] <= 4294967295):
        raise ValueError('07C83DAE decoded fields are incomplete')

def decode_fields(raw_fields, read):
    verify_source_evidence()
    result = snapshot_source.decode_fields(raw_fields, read)
    _fields(result)
    return result

def _profile(sequence, fields, normalizer_transform_present, thread_hook_present, writer_metadata_callback_present, padding_policy):
    verify_source_evidence()
    _fields(fields)
    if normalizer_transform_present is not False or thread_hook_present is not False or writer_metadata_callback_present is not False:
        raise ValueError('07C83DAE requires explicitly absent transforms/hooks/metadata callbacks')
    if type(sequence) is not int or not 1 <= sequence <= 4294967295:
        raise ValueError('07C83DAE requires a nonzero uint32 sequence')
    if padding_policy != 'zero':
        raise ValueError('07C83DAE requires explicit zero source stack padding')

def encode_record(sequence, fields, values, *, normalizer_transform_present, thread_hook_present, writer_metadata_callback_present, padding_policy):
    _profile(sequence, fields, normalizer_transform_present, thread_hook_present, writer_metadata_callback_present, padding_policy)
    ranges = {'owner': (-1, 63), 'city_id': (0, 4294967295), 'district_id': (0, 4294967295), 'flag148': (0, 255), 'secondary': (-(1 << 31), (1 << 31) - 1), 'civilization': (-1, 4294967295)}
    if not isinstance(values, dict) or set(values) != set(ranges):
        raise ValueError('07C83DAE needs all native query values')
    for name, (low, high) in ranges.items():
        if type(values[name]) is not int or not low <= values[name] <= high:
            raise ValueError('Invalid07C83DAE native query value: ' + name)
    if values['owner'] == -1:
        if values['secondary'] != -1 or values['civilization'] != -1:
            raise ValueError('07C83DAE owner sentinel requires source query sentinels')
    elif values['civilization'] < 0:
        raise ValueError('07C83DAE owned plot requires native civilization DWORD')
    record = bytearray(RECORD_SIZE)
    struct.pack_into('<IIII', record, 0, RECORD_SIZE, RECORD_TYPE, sequence, 0)
    record[16:24] = b'\xff' * 8
    record[24:64] = bytes.fromhex('ffff0000ffffffff') * 5
    struct.pack_into('<I', record, 80, sequence)
    record[88:96] = fields['position_bytes']
    struct.pack_into('<HHI', record, 96, values['owner'] & 65535, 2, values['city_id'])
    struct.pack_into('<HHI', record, 104, values['owner'] & 65535, 3, values['district_id'])
    record[112] = values['flag148']
    struct.pack_into('<IiI', record, 116, fields['descriptor_tail'], values['owner'], fields['source_value'])
    struct.pack_into('<iI', record, 136, values['secondary'], values['civilization'] & 4294967295)
    return bytes(record)

@contextmanager
def produce_record_lease(sequence, core, context, fields, *, expected_civilization_hashes, normalizer_transform_present, thread_hook_present, writer_metadata_callback_present, padding_policy='zero', read=None, native_api=None, secondary_query_api=None, config_record_lookup=None, config_value_lookup=None, key_hash=None, core_sha256='d7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'):
    """Query the native snapshot, raw AL, secondary value and civilization.

    The plot stays owned through the caller's enqueue. Snapshot178 writes24
    bytes; the source ignores RAX, which is not its output pointer. Owner comes
    from the signed snapshot byte14 and selects the configured hash mapping.
    Null map/plot and owners outside the 64 application records are refused.
    Expected hashes are optional cross-checks for the configured human slots;
    every owned plot still reads its native application civilization value.
    """
    if core_sha256 not in ('d7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3', '259b90a473a256aff6a7d621a4f3717e46f6921c59b9817475375c88b97e8c83', '324c51e9ea3531758842e16c69e6cddbefbb226c5b675c3d6e60111646c2e98c'):
        raise ValueError('Unqualified facade engine')
    profile = dict(normalizer_transform_present=normalizer_transform_present, thread_hook_present=thread_hook_present, writer_metadata_callback_present=writer_metadata_callback_present, padding_policy=padding_policy)
    _profile(sequence, fields, **profile)
    if not isinstance(expected_civilization_hashes, Mapping) or any((type(k) is not int or not 0 <= k < 64 or type(v) is not int or (not 0 <= v <= 4294967295) for k, v in expected_civilization_hashes.items())):
        raise ValueError('07C83DAE expected identities require 0..63 indices and uint32 hashes')
    identities = dict(expected_civilization_hashes)
    with plot_snapshot(core, context, fields, read=read, native_api=native_api, core_sha256=core_sha256) as values:
        owner = values['owner']
        if not -1 <= owner < 64:
            raise ValueError('07C83DAE snapshot owner is outside the configured profile')
        secondary = shared.query_secondary_value(core, context, owner, read=read, native_api=secondary_query_api, core_sha256=core_sha256)
        civilization = -1 if owner == -1 else shared.read_player_civilization_type_id(core, context, owner, expected_hash=identities.get(owner), read=read, record_lookup=config_record_lookup, value_lookup=config_value_lookup, key_hash=key_hash, core_sha256=core_sha256)
        yield encode_record(sequence, fields, dict(**values, secondary=secondary, civilization=civilization), **profile)

def produce_record(*args, **kwargs):
    """Standalone encoding convenience; a real producer must use the lease."""
    with produce_record_lease(*args, **kwargs) as record:
        return record

@contextmanager
def plot_snapshot(core, context, fields, *, read=None, native_api=None, include_flag148=True, core_sha256='d7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'):
    """Yield source snapshot values while retaining the owned native plot.

    This common178/148 route has no civilization/configuration restriction.
    Callers needing only178 must explicitly disable the148 query.
    Event-specific callers validate their own fields/profile before entering.
    """
    if core_sha256 not in ('d7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3', '259b90a473a256aff6a7d621a4f3717e46f6921c59b9817475375c88b97e8c83', '324c51e9ea3531758842e16c69e6cddbefbb226c5b675c3d6e60111646c2e98c'):
        raise ValueError('Unqualified facade engine')
    from civ6_host.runtime.foundation_facade_profiles import query_abi, verify_xp1_once, select_tables
    from civ6_host.runtime.provenance import resource_root
    _foundation_abi = query_abi(core_sha256, None if core_sha256 == 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3' else resource_root())
    _fields(fields)
    if type(include_flag148) is not bool:
        raise ValueError('Snapshot flag query selection must be explicit Boolean')
    if type(context) is not int or context <= 0:
        raise ValueError('07C83DAE requires a borrowed live Core context')
    base = int(core._handle)
    if base <= 0:
        raise ValueError('07C83DAE Core base is invalid')
    if read is None:
        from civ6_host.runtime.native.native_setup import local_reader
        read = local_reader()
    proof = verify_source_evidence()
    if native_api is None:
        if core_sha256 == 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3':
            for pin in proof['runtime_code_pins']:
                if hashlib.sha256(read(base + int(pin['rva'], 16), pin['size'])).hexdigest() != pin['sha256']:
                    raise ValueError('07C83DAE Core code changed')
        else:
            verify_xp1_once(core, base, read, resource_root(), core_sha256=core_sha256)
        api = {'outer_map': C.WINFUNCTYPE(C.c_void_p, C.c_void_p)(base + _foundation_abi.rva('outer_map')), 'get_plot': C.WINFUNCTYPE(C.c_void_p, C.c_void_p, C.c_int32, C.c_int32)(base + _foundation_abi.rva('get_plot')), 'release_map': C.WINFUNCTYPE(None, C.c_void_p)(base + _foundation_abi.rva('release_map')), 'release_plot': C.WINFUNCTYPE(None, C.c_void_p)(base + _foundation_abi.rva('release_plot')), 'snapshot178': C.WINFUNCTYPE(C.c_uint64, C.c_void_p, C.c_void_p, C.c_uint32)(base + _foundation_abi.rva('plot_snapshot178')), 'plot_flag148': C.WINFUNCTYPE(C.c_uint8, C.c_void_p)(base + _foundation_abi.rva('plot_flag148'))}
    else:
        api = native_api
        if not isinstance(api, dict) or set(api) != {'outer_map', 'get_plot', 'release_map', 'release_plot', 'snapshot178', 'plot_flag148'} or any((not callable(f) for f in api.values())):
            raise ValueError('07C83DAE test seam requires exactly six native operations')

    def check(pointer, table, slots):
        if not pointer or int.from_bytes(read(pointer, 8), 'little') != base + table:
            raise ValueError('Unexpected07C83DAE Core interface')
        for offset, target in slots:
            if int.from_bytes(read(base + table + offset, 8), 'little') != base + target:
                raise ValueError('07C83DAE Core virtual slot changed')
    check(context, _foundation_abi.table('outer'), ((168, _foundation_abi.rva('outer_map')),))
    map_object = api['outer_map'](context)
    if not map_object:
        raise ValueError('07C83DAE null map leaves source payload uninitialized')
    try:
        check(map_object, _foundation_abi.table('map'), ((8, _foundation_abi.rva('release_map')), (64, _foundation_abi.rva('get_plot'))))
        plot = api['get_plot'](map_object, fields['x'], fields['y'])
    finally:
        api['release_map'](map_object)
    if not plot:
        raise ValueError('07C83DAE null plot leaves source payload uninitialized')
    try:
        check(plot, _foundation_abi.table('plot'), ((8, _foundation_abi.rva('release_plot')), (376, _foundation_abi.rva('plot_snapshot178')), (328, _foundation_abi.rva('plot_flag148'))))
        if not int.from_bytes(read(plot + 8, 8), 'little') and (not int.from_bytes(read(plot + 16, 8), 'little')):
            raise ValueError('07C83DAE plot has neither live nor cached native source')
        storage = C.create_string_buffer(2 * len(_GUARD) + _SNAPSHOT_SIZE)
        output = C.addressof(storage) + len(_GUARD)
        C.memmove(C.addressof(storage), _GUARD, len(_GUARD))
        C.memset(output, 165, _SNAPSHOT_SIZE)
        C.memmove(output + _SNAPSHOT_SIZE, _GUARD, len(_GUARD))
        api['snapshot178'](plot, output, 0)
        if storage.raw[:len(_GUARD)] != _GUARD or storage.raw[-len(_GUARD):] != _GUARD:
            raise ValueError('07C83DAE snapshot178 exceeded its24-byte output')
        snapshot = C.string_at(output, _SNAPSHOT_SIZE)
        owner = struct.unpack_from('<b', snapshot, 20)[0]
        values = dict(owner=owner, city_id=struct.unpack_from('<I', snapshot, 4)[0], district_id=struct.unpack_from('<I', snapshot, 8)[0])
        if include_flag148:
            flag = api['plot_flag148'](plot)
            if type(flag) is not int or not 0 <= flag <= 255:
                raise ValueError('07C83DAE plot flag must be the raw native AL byte')
            values['flag148'] = flag
        yield values
    finally:
        api['release_plot'](plot)
