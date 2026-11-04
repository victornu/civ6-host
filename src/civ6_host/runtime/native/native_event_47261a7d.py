"""Source-backed DistrictCombatChanged queries and empty-receiver record.

The callback keeps its district facade alive through synchronous enqueue.
Uninitialized stack bytes are zeroed only in the explicit empty-receiver
profile and never exposed as native game values or learner observations.
"""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import ctypes as C
import hashlib
import json
import struct
from contextlib import contextmanager
from pathlib import Path
from civ6_host.runtime import district_damage_profile as _district_source
SOURCE_PROOF_SHA256 = '7235aef643256a213bc137e56a70e15ae83fbe65a61254d33b1e46d2093326c8'
NORMALIZER_PROOF_SHA256 = 'f7ea2e08123ed5741dce4104a882c87d200a76317652571f5fa27e5937d3757e'
LOOKUP_BODY_SHA256 = '37f97ea9ff7bd8ca4ab4ca2fdf8035d833473ce3074a81be6bcdb650b3b1b186'
NORMALIZER_BODY_SHA256 = 'c757d2f0c927f36e058ff5e57350a80beac1db2a89d3940fcb5e89c05545f23e'
CORE_BUILDER_BODY_SHA256 = 'a89c65434907a0abed104623cb377ba0bc5dd4364c441b2e18485c1614311bdb'
ITEM_VTABLE_RVA = 7990216
ITEM_METHODS = {8: 4406960, 32: 4372864, 48: 4407024}
_GUARD = b'47261A7D-query-guard'
_TABLES = {'outer': (7987232, ((184, 4382880),)), 'player': (7992320, ((8, 4421040), (304, 4422336))), 'collection': (7993256, ((8, 4427952), (16, 4427984))), 'item': (ITEM_VTABLE_RVA, tuple(ITEM_METHODS.items()))}
_LAB = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_event_47261a7d.py')))).resolve().parents[1]

def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()

def _proof_body(proof: dict, capture: str) -> dict:
    return proof['captured_bodies'][capture]

def _instruction_index(body: dict) -> dict[int, str]:
    result = {}
    for fragment in body['fragments']:
        for inst in fragment['instructions']:
            result[int(inst['va'], 0)] = inst['text']
    return result

def verify_source_evidence() -> dict:
    """Verify the callback/dispatcher capture and the pinned common A0 normalizer."""
    producer_path = _LAB / 'evidence/native-event-47261a7d-source' / f'{SOURCE_PROOF_SHA256}.json'
    normalizer_path = _LAB / 'evidence/native-event-fdf12323' / f'{NORMALIZER_PROOF_SHA256}.json'
    producer_raw = _resolve_resource_path(producer_path).read_bytes()
    normalizer_raw = _resolve_resource_path(normalizer_path).read_bytes()
    if _sha(producer_raw) != SOURCE_PROOF_SHA256 or _sha(normalizer_raw) != NORMALIZER_PROOF_SHA256:
        raise ValueError('47261A7D or A0 normalizer evidence hash mismatch')
    producer = json.loads(producer_raw)
    normalizer = json.loads(normalizer_raw)
    if producer.get('schema') != 'civ6rl.native_event_47261a7d_source.static.v1' or producer['sources']['exe_sha256'] != 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63' or producer['sources']['core_sha256'] != 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3' or (int(producer['registration']['kind']) != 1193679485) or (int(producer['registration']['callback_va'], 16) != 5370040272):
        raise ValueError('47261A7D producer pin or registration changed')
    cb = _proof_body(producer, 'exe_callback_144fd0')
    core_builder = _proof_body(producer, 'core_event_map_builder_485060')
    if cb['raw_code_sha256'] != '59b5c051af973601f09b7652dfa4e2652149cdc6df7e1cf1efd016925c82aa72':
        raise ValueError('47261A7D callback capture changed')
    if core_builder['raw_code_sha256'] != CORE_BUILDER_BODY_SHA256:
        raise ValueError('Core 0xA0 dispatcher capture changed')
    core_inst = _instruction_index(core_builder)
    expected_core = {6447190339: 'mov rax, qword ptr [rcx]', 6447190342: 'call qword ptr [rax + 0xa0]', 6447190353: 'mov ebx, eax', 6447190355: 'call 0x180744ca0', 6447190360: 'mov eax, ebx'}
    if any((core_inst.get(va) != text for va, text in expected_core.items())):
        raise ValueError('Core A0 call/return forwarding instructions changed')
    if normalizer.get('schema') != 'civ6rl.native_event_fdf12323.static.v2' or normalizer['images'] != {'exe_sha256': 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63', 'core_sha256': 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'} or normalizer['captures']['normalizer']['code_sha256'] != NORMALIZER_BODY_SHA256 or (normalizer['captures']['lookup147640']['code_sha256'] != LOOKUP_BODY_SHA256) or (normalizer['contract']['fields'].find('F343/tag400 descriptor8') < 0):
        raise ValueError('pinned A0 normalizer/lookup contract changed')
    expected_vtables = {'outer': ('0x79e020', {'0xb8': '0x18042e0a0'}), 'player': ('0x79f400', {'0x8': '0x1804375b0', '0x130': '0x180437ac0'}), 'collection': ('0x79f7a8', {'0x8': '0x1804390b0', '0x10': '0x1804390d0'}), 'item': ('0x79ebc8', {'0x8': '0x180433eb0', '0x20': '0x18042b980', '0x30': '0x180433ef0'})}
    for label, (rva, slots) in expected_vtables.items():
        row = normalizer['vtables'][label]
        actual_slots = {slot: data['va'] for slot, data in row['slots'].items()}
        if row['rva'] != rva or actual_slots != slots:
            raise ValueError(f'FDF-pinned Core {label} vtable differs')
    norm_inst = _instruction_index(normalizer['captures']['normalizer'])
    expected_norm = {5370585943: 'mov word ptr [rbp - 0xf], ax', 5370586955: 'cmp ecx, 0xf343dc5a', 5370586997: 'mov rcx, qword ptr [rbx + 0x30]', 5370587001: 'mov edx, dword ptr [rcx + 4]', 5370587004: 'movzx ecx, word ptr [rcx]', 5370587007: 'mov word ptr [rbp - 0x11], cx', 5370587011: 'mov dword ptr [rbp - 0xd], edx', 5370587069: 'call 0x1401445f0', 5370587082: 'xor eax, eax', 5370587108: 'ret'}
    if any((norm_inst.get(va) != text for va, text in expected_norm.items())):
        raise ValueError('A0 F343 descriptor normalization instructions changed')
    return {'producer_sha256': SOURCE_PROOF_SHA256, 'normalizer_sha256': NORMALIZER_PROOF_SHA256, 'normalizer_body_sha256': NORMALIZER_BODY_SHA256, 'lookup_body_sha256': LOOKUP_BODY_SHA256, 'normalized_descriptor': {'key': '0xF343DC5A', 'tag': 1024, 'owner': 'signed WORD at descriptor+0', 'type': 3, 'index': 'DWORD at descriptor+4'}, 'host_return': "The A0 normalizer at 0x1401CA7BD calls dispatcher 0x1401445F0, then 0x1401CA7CA zeroes EAX and 0x1401CA7E4 returns that zero. Separately, Core 0x180485060 forwards the host slot +0xA0 EAX after destroying its local map; that forwarding does not make the callback 0x140144FD0's epilogue a status result."}

def decode_descriptor(raw: bytes) -> tuple[int, int, int]:
    """Decode the exact 8-byte descriptor constructed by the common A0 path."""
    if type(raw) is not bytes or len(raw) != 8:
        raise ValueError('47261A7D descriptor must be exactly eight copied bytes')
    owner_u16, descriptor_type, item_id = struct.unpack('<HHI', raw)
    owner = owner_u16 - 65536 if owner_u16 & 32768 else owner_u16
    validate_descriptor_parts(owner, descriptor_type, item_id)
    return (owner, descriptor_type, item_id)

def validate_descriptor_parts(owner: int, descriptor_type: int, item_id: int) -> None:
    if type(owner) is not int or not 0 <= owner <= 63:
        raise ValueError('47261A7D diagnostic profile admits owners 0..63 only')
    if type(descriptor_type) is not int or descriptor_type != 3:
        raise ValueError('A0 F343 normalizer supplies descriptor type 3')
    if type(item_id) is not int or not 0 <= item_id <= 4294967295:
        raise ValueError('descriptor index must be uint32')

def _qword(read, address: int) -> int:
    raw = read(address, 8)
    if type(raw) is not bytes or len(raw) != 8:
        raise ValueError('47261A7D memory read must return exactly eight bytes')
    return struct.unpack('<Q', raw)[0]

def _check_object(read, core_base: int, pointer: int, label: str, *, core_sha256='d7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3') -> None:
    _district_source.ensure_source(core_sha256)
    table, slots = _district_source.select_tables(core_sha256, _TABLES)[label]
    if not pointer or _qword(read, pointer) != core_base + table:
        raise ValueError(f'47261A7D {label} facade has an unexpected vtable')
    for slot, target in slots:
        if _qword(read, core_base + table + slot) != core_base + target:
            raise ValueError(f'47261A7D {label} method +{slot:#x} changed')

def _read_variant8(function, item: int) -> bytes:
    buf = C.create_string_buffer(_GUARD + bytes(8) + _GUARD, len(_GUARD) * 2 + 8)
    output = C.addressof(buf) + len(_GUARD)
    returned = function(item, output)
    raw = buf.raw
    if raw[:len(_GUARD)] != _GUARD or raw[len(_GUARD) + 8:] != _GUARD:
        raise RuntimeError('item +0x30 wrote beyond the observed 8-byte variant')
    if returned != output:
        raise ValueError('item +0x30 did not return the supplied descriptor buffer')
    return raw[len(_GUARD):len(_GUARD) + 8]

def build_native_api(core_base: int, *, core_sha256='d7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3') -> dict:
    """Build only Core entry points; deliberately never binds EXE functions."""
    _district_source.ensure_source(core_sha256)
    if type(core_base) is not int or core_base <= 0:
        raise ValueError('Core module base must be a positive integer')
    entries = {'get_player': (4382880, C.c_void_p, (C.c_void_p, C.c_int32)), 'release_player': (4421040, None, (C.c_void_p,)), 'player_collection': (4422336, C.c_void_p, (C.c_void_p,)), 'release_collection': (4427952, None, (C.c_void_p,)), 'collection_index': (4427984, C.c_void_p, (C.c_void_p, C.c_uint32)), 'release_item': (4406960, None, (C.c_void_p,)), 'item_variant': (4407024, C.c_void_p, (C.c_void_p, C.c_void_p)), 'item_raw': (4372864, C.c_uint32, (C.c_void_p,))}
    entries = _district_source.select_specs(core_sha256, entries)
    factory = C.WINFUNCTYPE
    return {name: factory(restype, *args)(core_base + rva) for name, (rva, restype, args) in entries.items()}

@contextmanager
def lookup_item_lease(descriptor: bytes, *, context: int, core_base: int, read, api: dict | None=None, core_sha256='d7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'):
    """Resolve through the source-equivalent facade/player/collection chain.

    EXE147640 performs the signed-owner -> player -> collection -> index
    traversal internally. This WORK adapter uses the already pinned Core
    methods and vtables captured in FDF/C318, without calling EXE. The source
    call order and retained item lifetime are modeled; A1 consumer behavior is
    not claimed.
    """
    _district_source.ensure_source(core_sha256)
    verify_source_evidence()
    owner, _descriptor_type, item_id = decode_descriptor(descriptor)
    if type(core_base) is not int or core_base <= 0 or (not callable(read)):
        raise ValueError('a live Core base and bounded reader are required')
    if type(context) is not int or context <= 0:
        raise ValueError('a live Core context is required')
    required = {'get_player', 'release_player', 'player_collection', 'release_collection', 'collection_index', 'item_variant', 'item_raw', 'release_item'}
    if api is None:
        api = build_native_api(core_base, core_sha256=core_sha256)
    elif type(api) is not dict or set(api) != required or (not all((callable(v) for v in api.values()))):
        raise ValueError('query seam must match the eight source operations')
    _check_object(read, core_base, context, 'outer', core_sha256=core_sha256)
    player = api['get_player'](context, owner)
    if not player:
        yield None
        return
    _check_object(read, core_base, player, 'player', core_sha256=core_sha256)
    item = 0
    try:
        collection = api['player_collection'](player)
        _check_object(read, core_base, collection, 'collection', core_sha256=core_sha256)
        try:
            item = api['collection_index'](collection, item_id)
        finally:
            api['release_collection'](collection)
    finally:
        api['release_player'](player)
    if not item:
        yield None
        return
    _check_object(read, core_base, item, 'item', core_sha256=core_sha256)
    try:
        if not _qword(read, item + 8):
            raise ValueError('47261A7D requires a live item owner at item+8')
        variant = _read_variant8(api['item_variant'], item)
        raw_value = api['item_raw'](item)
        if type(raw_value) is not int or not 0 <= raw_value <= 4294967295:
            raise ValueError('item +0x20 must return a DWORD')
        yield {'item_variant': variant, 'item_raw': raw_value}
    finally:
        api['release_item'](item)

def known_payload_writes(descriptor: bytes, values: dict | None) -> dict:
    """Return only fields proven written by the callback, never a full record."""
    owner, descriptor_type, item_id = decode_descriptor(descriptor)
    result = {'payload_size': 48, 'known_dwords': {0: 0, 8: 0, 16: None, 20: None, 24: 4294957297, 28: 4294957297}, 'descriptor': {'owner_u16': owner & 65535, 'owner_signed_i16': owner, 'type_u16': descriptor_type, 'index_u32': item_id}, 'undefined_ranges': [[4, 8], [12, 16], [36, 40]], 'full_payload_admissible': False}
    if values is None:
        result['null_lookup'] = True
        result['known_dwords'][16] = owner & 65535 | descriptor_type << 16
        result['known_dwords'][20] = item_id
        result['known_dwords'][32] = None
        result['undefined_ranges'].append([32, 36])
        result['variant_bytes_at_0x28'] = 'ffff0000ffffffff'
        return result
    if type(values) is not dict or set(values) != {'item_variant', 'item_raw'}:
        raise ValueError('live lookup values require exactly variant and raw DWORD')
    variant = values['item_variant']
    raw = values['item_raw']
    if type(variant) is not bytes or len(variant) != 8:
        raise ValueError('item variant must be exactly eight bytes')
    if type(raw) is not int or not 0 <= raw <= 4294967295:
        raise ValueError('item raw value must be a DWORD')
    result['known_dwords'][16] = owner & 65535 | descriptor_type << 16
    result['known_dwords'][20] = item_id
    result['known_dwords'][32] = raw
    result['variant_bytes_at_0x28'] = variant.hex()
    return result
from dataclasses import dataclass
import struct
EVENT_KIND = 1193679485
RECORD_TYPE, RECORD_SIZE = (161, 128)
PADDING_POLICY = 'zero-unread-empty-receiver-payload'
SELECTOR = 1503653588
EMPTY_STATE = dict(observer_registered=False, state_pointer_nonnull=True, pre_hook=None, post_hook=None, subscriber_count=0, state_flags=0)

@dataclass(frozen=True)
class Fields:
    owner: int
    item_id: int
    selector: int = SELECTOR
    descriptor_type: int = 3

@dataclass(frozen=True)
class Values:
    item_present: bool
    item_variant: bytes | None
    item_raw: int | None

def check_fields(fields):
    if type(fields) is not Fields or type(fields.owner) is not int or (not 0 <= fields.owner < 64) or (type(fields.item_id) is not int) or (not 0 <= fields.item_id <= 4294967295) or (type(fields.selector) is not int) or (fields.selector != SELECTOR) or (type(fields.descriptor_type) is not int) or (fields.descriptor_type != 3):
        raise ValueError('47261A7D requires a normalized district descriptor and the witnessed selector')

def validate_profile(sequence, fields, *, padding_policy, empty_receiver_state, notification_counter, metadata_counter, per_thread_hook_present, writer_metadata_callback_present):
    check_fields(fields)
    if type(sequence) is not int or not 1 <= sequence <= 4294967295:
        raise ValueError('47261A7D sequence must be a nonzero uint32')
    if padding_policy != PADDING_POLICY or type(empty_receiver_state) is not dict or empty_receiver_state != EMPTY_STATE or ({k: type(v) for k, v in empty_receiver_state.items()} != {k: type(v) for k, v in EMPTY_STATE.items()}) or (type(notification_counter) is not int) or (notification_counter != 0) or (type(metadata_counter) is not int) or (metadata_counter != 0) or (per_thread_hook_present is not False) or (writer_metadata_callback_present is not False):
        raise ValueError('47261A7D only supports the checked empty-receiver and zero-counter profile')

def encode_record(sequence, fields, values, **profile):
    validate_profile(sequence, fields, **profile)
    if type(values) is not Values or type(values.item_present) is not bool:
        raise ValueError('47261A7D requires an explicit native lookup outcome')
    if values.item_present:
        if type(values.item_variant) is not bytes or len(values.item_variant) != 8 or type(values.item_raw) is not int or (not 0 <= values.item_raw <= 4294967295):
            raise ValueError('47261A7D live item requires its native 8-byte variant and DWORD')
        variant, raw_value = (values.item_variant, values.item_raw)
    else:
        if values.item_variant is not None or values.item_raw is not None:
            raise ValueError('47261A7D null lookup must not supply invented native values')
        variant = bytes.fromhex('ffff0000ffffffff')
        raw_value = 0
    record = bytearray(RECORD_SIZE)
    struct.pack_into('<IIII', record, 0, RECORD_SIZE, RECORD_TYPE, sequence, 0)
    struct.pack_into('<II', record, 16, 4294967295, 4294967295)
    for offset in (24, 32, 40, 48, 56):
        struct.pack_into('<HHI', record, offset, 65535, 0, 4294967295)
    struct.pack_into('<I', record, 80, sequence)
    struct.pack_into('<HHI', record, 96, fields.owner, fields.descriptor_type, fields.item_id)
    struct.pack_into('<iiI', record, 104, -9999, -9999, raw_value)
    record[120:128] = variant
    return bytes(record)

def decode_fields(raw_fields, read):
    from civ6_host.runtime.native.native_application_mirror import decode_scalar
    from civ6_host.runtime.native.native_host_events import copy_eight_byte_variant
    verify_source_evidence()
    if type(raw_fields) is not dict or set(raw_fields) != {2716180809, 4081310810} or any((type(raw) is not bytes or len(raw) != 24 for raw in raw_fields.values())):
        raise ValueError('47261A7D requires its exact two complete native fields')
    selector = decode_scalar(raw_fields[2716180809], 3)
    if selector != SELECTOR:
        raise ValueError('47261A7D selector is outside the witnessed diagnostic profile')
    blob = copy_eight_byte_variant(raw_fields[4081310810], read, expected_tag=1024)
    owner = struct.unpack_from('<h', blob)[0]
    item_id = struct.unpack_from('<I', blob, 4)[0]
    fields = Fields(owner=owner, item_id=item_id, selector=selector)
    check_fields(fields)
    return fields

@contextmanager
def produce_record_lease(sequence, fields, *, core, context, read, normalizer_transform_present, profile, native_api=None, core_sha256='d7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'):
    _district_source.ensure_source(core_sha256)
    if core_sha256 != 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3':
        _district_source.verify_once(core, read, core_sha256=core_sha256)
    from civ6_host.runtime.native.native_deferred_empty_profile import validate_empty_profile_record
    verify_source_evidence()
    if normalizer_transform_present is not False:
        raise ValueError('47261A7D normalizer-transform hooks are outside the admitted profile')
    validate_profile(sequence, fields, **profile)
    shape = bytearray(RECORD_SIZE)
    struct.pack_into('<II', shape, 0, RECORD_SIZE, RECORD_TYPE)
    validate_empty_profile_record(shape, **profile['empty_receiver_state'])
    descriptor = struct.pack('<HHI', fields.owner, 3, fields.item_id)
    with lookup_item_lease(descriptor, context=context, core_base=int(core._handle), read=read, api=native_api, core_sha256=core_sha256) as native:
        values = Values(False, None, None) if native is None else Values(True, native['item_variant'], native['item_raw'])
        record = encode_record(sequence, fields, values, **profile)
        validate_empty_profile_record(record, **profile['empty_receiver_state'])
        yield (record, {'item_present': values.item_present, 'native_item_queries_executed': values.item_present, 'raw_dword_origin': 'native-query' if values.item_present else 'uninitialized-stack-zero-unread-policy', 'source_uninitialized_payload_ranges': [[4, 8], [12, 16], [36, 40]] if values.item_present else [[4, 8], [12, 16], [32, 40]], 'payload_exposed_to_learner': False})
