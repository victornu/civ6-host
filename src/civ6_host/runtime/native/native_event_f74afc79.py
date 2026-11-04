"""Pinned static contract and Core query lease for DistrictDamageChanged.

This adapter never calls EXE code. It uses only the source-pinned Core
facade methods and zeroes uninitialized bytes only for the explicit empty
receiver diagnostic profile.
"""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
from contextlib import contextmanager
from dataclasses import dataclass
import ctypes as C
import struct
from pathlib import Path
from civ6_host.runtime import district_damage_profile as _district_source
EVENT_KIND = 4148886649
RECORD_TYPE, RECORD_SIZE = (159, 144)
PADDING_POLICY = 'zero-unread-empty-receiver-payload'
SOURCE_PROOF_SHA256 = '6e95c2a6e290e5c27f19291ea97a206e432883a556d43a4870fba797ff18944b'
ITEM_VTABLE_RVA = 7990216
ITEM_METHODS = {8: 4406960, 32: 4372864, 48: 4407024, 56: 4407328, 88: 4407392}
SELECTOR = 1839557181
_GUARD = b'F74AFC79-position-guard'
_LAB = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_event_f74afc79.py')))).resolve().parents[1]
_PROOF = _LAB / 'evidence/native-event-f74afc79-source' / (SOURCE_PROOF_SHA256 + '.json')
_TABLES = {'outer': (7987232, ((184, 4382880),)), 'player': (7992320, ((8, 4421040), (304, 4422336))), 'collection': (7993256, ((8, 4427952), (16, 4427984))), 'item': (ITEM_VTABLE_RVA, tuple(ITEM_METHODS.items()))}

@dataclass(frozen=True)
class Fields:
    owner: int
    item_id: int
    selector: int
    current: int
    previous: int
    descriptor_type: int = 3

@dataclass(frozen=True)
class Values:
    item_present: bool
    position: bytes | None
    item_raw: int | None
    item_variant: bytes | None
    item_hash: int | None
EMPTY_STATE = dict(observer_registered=False, state_pointer_nonnull=True, pre_hook=None, post_hook=None, subscriber_count=0, state_flags=0)

def _pinned(path: str, digest: str):
    from civ6_host.runtime.native.native_source_cache import load_pinned_json
    return load_pinned_json(_LAB / path, digest)

def _body_rows(body: dict) -> dict[int, tuple[str, str]]:
    rows = {}
    for fragment in body['fragments']:
        for inst in fragment['instructions']:
            va = int(inst['va'], 16)
            if va in rows:
                raise ValueError('duplicate instruction address in pinned capture')
            rows[va] = (inst['bytes'], inst['text'])
    return rows

def verify_source_evidence() -> dict:
    """Hash-check the composite and all source captures before accepting fields."""
    proof = _pinned(str(_PROOF.relative_to(_LAB)), SOURCE_PROOF_SHA256)
    if proof['schema'] != 'civ6rl.native_f74afc79_codec_static_proof.v3' or proof['event'] != {'kind': EVENT_KIND, 'name': 'GameCoreEvent::DistrictDamageChanged', 'queue_type': RECORD_TYPE, 'record_size': RECORD_SIZE}:
        raise RuntimeError('F74AFC79 proof identity changed')
    docs = {name: _pinned(ref['path_from_lab'], ref['sha256']) for name, ref in proof['sources'].items()}
    producer, receiver, consumer = (docs['producer'], docs['receiver'], docs['consumer'])
    norm = docs['normalizer_supplement']
    paths = norm['normalizer']['field_paths']
    if norm['schema'] != 'civ6rl.native_f74afc79_normalizer_core_supplement.v2' or norm['images']['exe_sha256'] != proof['images']['exe_sha256'] or norm['images']['core_sha256'] != proof['images']['core_sha256'] or (norm['normalizer']['code_sha256'] != 'c757d2f0c927f36e058ff5e57350a80beac1db2a89d3940fcb5e89c05545f23e') or (paths['0xd6fcf3e4_type2']['normalized_offset'] != '0x50') or (paths['0xa1fbc372_type2']['normalized_offset'] != '0x54') or (paths['0xf343dc5a_pointer8']['normalized_offset_word0'] != '0x28') or (paths['0xf343dc5a_pointer8']['normalized_offset_dword4'] != '0x2c') or (paths['0xf343dc5a_pointer8']['normalized_type']['value'] != 3) or (norm['f74_callback_crosscheck']['code_sha256'] != '3e2b0963fd6136c9ab2f1e2fdf4a43e8a841d479c81cbbebe1baa584f24ac1a1'):
        raise RuntimeError('F74 normalizer/callback mapping supplement changed')
    if producer['schema'] != 'civ6rl.native_f74afc79_failed_a0_witness.static.v1' or producer['image']['sha256'] != proof['images']['core_sha256'] or producer['captures']['rva_133f21']['code_sha256'] != 'bf79d1080f7ff8b6df0f1f579b62dd4b90cbe5d88cab08d822a09810e9855ca9' or (producer['captures']['rva_485b50']['code_sha256'] != 'c76f0cd26d053e0e8b93195e202f142f2199336718b8cd1f2c2aa77600fd4311'):
        raise RuntimeError('F74 producer/Base capture changed')
    if receiver['schema'] != 'civ6rl.native_f74afc79_receiver_static.v1' or receiver['inputs']['exe']['sha256'] != proof['images']['exe_sha256'] or receiver['registration']['registry_row']['callback_va'] != '0x140145120' or (receiver['queue_record']['writer_va'] != '0x1401353f0') or (receiver['queue_record']['record_type'] != RECORD_TYPE) or (receiver['queue_record']['record_size_bytes'] != RECORD_SIZE):
        raise RuntimeError('F74 receiver/writer source changed')
    if consumer['schema'] != 'civ6rl.native_f74_consumer526.static.v1' or consumer['images']['exe_sha256'] != proof['images']['exe_sha256'] or consumer['table']['record_type'] != RECORD_TYPE or (consumer['table']['record_size'] != RECORD_SIZE) or (consumer['registration']['event_name']['text'] != 'GameCoreEvent::DistrictDamageChanged') or (consumer['registration']['handler_va'] != '0x1400d9a90'):
        raise RuntimeError('F74 consumer row source changed')
    cb = _body_rows(receiver['callback']['body'])
    expected_cb = {5370040625: ('813a3dc34764', 'cmp dword ptr [rdx], 0x6447c33d'), 5370040640: ('0fb75228', 'movzx edx, word ptr [rdx + 0x28]'), 5370040647: ('458b412c', 'mov r8d, dword ptr [r9 + 0x2c]'), 5370040668: ('410fb7492a', 'movzx ecx, word ptr [r9 + 0x2a]'), 5370040676: ('418b4150', 'mov eax, dword ptr [r9 + 0x50]'), 5370040683: ('418b4154', 'mov eax, dword ptr [r9 + 0x54]'), 5370040751: ('e88c240000', 'call 0x140147640'), 5370040775: ('ff5030', 'call qword ptr [rax + 0x30]'), 5370040809: ('ff5038', 'call qword ptr [rax + 0x38]'), 5370040825: ('ff5020', 'call qword ptr [rax + 0x20]'), 5370040840: ('ff5058', 'call qword ptr [rax + 0x58]'), 5370040916: ('e89701ffff', 'call 0x1401353f0')}
    if any((cb.get(va) != row for va, row in expected_cb.items())):
        raise RuntimeError('F74 callback fields/query/writer instructions changed')
    pos = docs['item_position']
    if pos['schema'] != 'civ6rl.native_event_28d6ebbe.static.v2' or pos['images']['core_sha256'] != proof['images']['core_sha256'] or pos['vtables']['item']['vtable_va'] != '0x18079ebc8' or (pos['vtables']['item']['entries']['0x20'] != '0x18042b980') or (pos['vtables']['item']['entries']['0x30'] != '0x180433ef0') or (pos['vtables']['item']['entries']['0x38'] != '0x180434020') or (pos['core_captures']['0x180434020']['code_sha256'] != 'bd09020e4f8c3c7f42d5317eacce81037c62e16c5ef0bee589a03c6849292610') or (pos['core_captures']['0x18042b980']['code_sha256'] != '6f4c953e8f0a70ab31f18a107662d9e08e9355d8139710f4c13ae92bf4218aea') or (pos['core_captures']['0x180433ef0']['code_sha256'] != '573273c800a954989ec9b534f4eed8bdbd804d869f150bdc4a4d492a64d19ba3'):
        raise RuntimeError('F74 item +0x38/Core position method pin changed')
    expected_tables = {'outer': (7987232, {184: 4382880}), 'player': (7992320, {8: 4421040, 304: 4422336}), 'collection': (7993256, {8: 4427952, 16: 4427984}), 'item': (7990216, {8: 4406960, 32: 4372864, 48: 4407024, 56: 4407328})}
    for label, (rva, expected_slots) in expected_tables.items():
        table = pos['vtables'][label]
        actual_slots = {int(slot, 16): int(target, 16) for slot, target in table['entries'].items()}
        if int(table['vtable_va'], 16) != 6442450944 + rva or actual_slots != {slot: 6442450944 + target for slot, target in expected_slots.items()}:
            raise RuntimeError(f'F74 {label} Core table/method pin changed')
    c318 = docs['item_hash']
    if c318['schema'] != 'civ6rl.native_event_c3183902.static.v1' or c318['images']['gamecore_sha256'] != proof['images']['core_sha256'] or c318['core_interface_captures']['vtables']['player_item']['address'] != '0x18079ebc8' or (c318['core_interface_captures']['vtables']['player_item']['entries']['0x58']['target_va'] != '0x180434060') or (c318['core_interface_captures']['bodies']['0x180434060']['code_sha256'] != '7672b9d4ff505fccb5d521a48d4ad8e9f55b872ca270361f6dfbc312ec79e027') or (norm['core_item_vtable']['entries'] != {'0x20': '0x18042b980', '0x30': '0x180433ef0', '0x38': '0x180434020', '0x58': '0x180434060'}) or (norm['core_item_vtable']['runtime_facades']['0x20']['signature'] != 'C.c_uint32(item)') or (norm['core_item_vtable']['runtime_facades']['0x30']['signature'] != 'C.c_void_p(item, output8)') or (norm['core_item_vtable']['runtime_facades']['0x38']['signature'] != 'C.c_void_p(item, output8)') or (norm['core_item_vtable']['runtime_facades']['0x58']['signature'] != 'C.c_uint32(item, uint32_key)') or ('A1FBC372 tag2 DWORD -> descriptor+0x54' not in c318['contract']['entry']) or ('D6FCF3E4 tag2 DWORD -> descriptor+0x50' not in c318['contract']['entry']):
        raise RuntimeError('F74 A0 scalar normalization mapping pin changed')
    _verify_selector_contract(proof, docs, cb)
    return {'proof_sha256': SOURCE_PROOF_SHA256, 'source_hashes': {name: ref['sha256'] for name, ref in proof['sources'].items()}, 'core_sha256': proof['images']['core_sha256'], 'exe_sha256': proof['images']['exe_sha256']}

def _verify_selector_contract(proof: dict, docs: dict, callback_rows: dict) -> None:
    contract = proof['selector_admissibility']
    wire = contract['contract']
    if contract['schema'] != 'civ6rl.native_f74_selector_uint32_contract.v1' or wire['field_hash'] != '0xA1E5A149' or wire['tag'] != 3 or (wire['width_bits'] != 32) or (wire['unsigned_min'] != 0) or (wire['unsigned_max'] != 4294967295) or (wire['normalized_offset'] != '+0x04/u32') or (wire['core_method'] != 'item vtable +0x58') or (wire['core_method_signature'] != 'C.c_uint32(item, uint32_key)') or (wire['record_payload_offset'] != '+0x28/u32') or (wire['record_payload_width'] != 4):
        raise RuntimeError('F74 selector wire contract changed')
    if docs['codec528_parent'].get('schema') != 'civ6rl.native_f74afc79_codec_static_proof.v2':
        raise RuntimeError('F74 selector parent proof changed')
    norm = docs['normalizer_supplement']['normalizer']
    norm_rows = _body_rows(norm['capture'])
    for va, row in {5370586750: ('8b4330', 'mov eax, dword ptr [rbx + 0x30]'), 5370586753: ('8945cb', 'mov dword ptr [rbp - 0x35], eax')}.items():
        if norm_rows.get(va) != row:
            raise RuntimeError('F74 selector normalizer copy changed')
    for va, row in {5370040657: ('418b4104', 'mov eax, dword ptr [r9 + 4]'), 5370040673: ('8945e8', 'mov dword ptr [rbp - 0x18], eax'), 5370040828: ('8b55e8', 'mov edx, dword ptr [rbp - 0x18]'), 5370040840: ('ff5058', 'call qword ptr [rax + 0x58]'), 5370040843: ('8945f4', 'mov dword ptr [rbp - 0xc], eax')}.items():
        if callback_rows.get(va) != row:
            raise RuntimeError('F74 selector callback route changed')
    producer = docs['producer']
    producer_rows = _body_rows(producer['captures']['rva_133f21'])
    for va, row in {6443712123: ('81fd29d6975e', 'cmp ebp, 0x5e97d629'), 6443712131: ('81fd3d6aa56d', 'cmp ebp, 0x6da56a3d'), 6443712137: ('0f8592000000', 'jne 0x180133f21')}.items():
        if producer_rows.get(va) != row:
            raise RuntimeError('F74 producer selector-domain capture changed')
    tail = docs['native398_f74_tail']
    if tail.get('source_sha256') != contract['raw398_observation']['report_sha256'] or len(tail.get('rows', [])) != 2 or tail['rows'][0].get('stage') != 'native_district_damage_change_query_completed' or (tail['rows'][1].get('stage') != 'native_host_event_failed_input'):
        raise RuntimeError('F74 raw398 selector tail changed')
    raw = bytes.fromhex(tail['rows'][1]['fields']['0xa1e5a149'])
    observed = struct.unpack_from('<I', raw, 8)[0]
    if len(raw) != 24 or struct.unpack_from('<H', raw)[0] != 3 or observed != 1587009065 or ('selector is outside the source-proven diagnostic profile' not in tail['rows'][1].get('error', '')):
        raise RuntimeError('F74 selector failure witness changed')

def _scalar(raw: bytes, tag: int, label: str) -> int:
    if type(raw) is not bytes or len(raw) != 24:
        raise ValueError(f'{label} scalar must be a complete 24-byte value')
    actual_tag = struct.unpack_from('<H', raw)[0]
    flags = struct.unpack_from('<I', raw, 20)[0]
    value = struct.unpack_from('<I', raw, 8)[0]
    if actual_tag != tag or flags != 0:
        raise ValueError(f'{label} scalar tag/flags/padding changed')
    return value

def decode_descriptor(raw: bytes) -> tuple[int, int, int]:
    if type(raw) is not bytes or len(raw) != 8:
        raise ValueError('F74 descriptor must contain exactly eight copied bytes')
    owner_u16, descriptor_type, item_id = struct.unpack('<HHI', raw)
    owner = owner_u16 - 65536 if owner_u16 & 32768 else owner_u16
    validate_descriptor_parts(owner, descriptor_type, item_id)
    return (owner, descriptor_type, item_id)

def validate_descriptor_parts(owner: int, descriptor_type: int, item_id: int) -> None:
    if type(owner) is not int or not 0 <= owner < 64:
        raise ValueError('F74 diagnostic profile admits owners 0..63 only')
    if type(descriptor_type) is not int or descriptor_type != 3:
        raise ValueError('F74 normalizer initializes descriptor type to 3')
    if type(item_id) is not int or not 0 <= item_id <= 4294967295:
        raise ValueError('F74 item index must be uint32')

def check_fields(fields: Fields) -> None:
    if type(fields) is not Fields or type(fields.selector) is not int or (not 0 <= fields.selector <= 4294967295) or (type(fields.current) is not int) or (not 0 <= fields.current <= 4294967295) or (type(fields.previous) is not int) or (not 0 <= fields.previous <= 4294967295):
        raise ValueError('F74 requires a uint32 selector and two uint32 scalar fields')
    validate_descriptor_parts(fields.owner, fields.descriptor_type, fields.item_id)

def decode_fields(raw_fields: dict, read) -> Fields:
    verify_source_evidence()
    keys = {2716180809, 2717631346, 3606901732, 4081310810}
    if type(raw_fields) is not dict or set(raw_fields) != keys or any((type(v) is not bytes or len(v) != 24 for v in raw_fields.values())):
        raise ValueError('F74 requires exactly its four complete typed fields')
    selector = _scalar(raw_fields[2716180809], 3, 'A1E5A149')
    previous = _scalar(raw_fields[2717631346], 2, 'A1FBC372')
    current = _scalar(raw_fields[3606901732], 2, 'D6FCF3E4')
    from civ6_host.runtime.native.native_host_events import copy_eight_byte_variant
    borrowed = copy_eight_byte_variant(raw_fields[4081310810], read, expected_tag=1024)
    owner = struct.unpack_from('<h', borrowed, 0)[0]
    item_id = struct.unpack_from('<I', borrowed, 4)[0]
    fields = Fields(owner, item_id, selector, current, previous, 3)
    check_fields(fields)
    return fields

def validate_profile(sequence: int, fields: Fields, *, padding_policy: str, empty_receiver_state: dict, notification_counter: int, metadata_counter: int, per_thread_hook_present: bool, writer_metadata_callback_present: bool) -> None:
    check_fields(fields)
    if type(sequence) is not int or not 1 <= sequence <= 4294967295:
        raise ValueError('F74 sequence must be a nonzero uint32')
    if padding_policy != PADDING_POLICY or type(empty_receiver_state) is not dict or empty_receiver_state != EMPTY_STATE or ({k: type(v) for k, v in empty_receiver_state.items()} != {k: type(v) for k, v in EMPTY_STATE.items()}) or (type(notification_counter) is not int) or (notification_counter != 0) or (type(metadata_counter) is not int) or (metadata_counter != 0) or (per_thread_hook_present is not False) or (writer_metadata_callback_present is not False):
        raise ValueError('F74 only admits the checked empty receiver/zero-hook profile')

def _qword(read, address: int) -> int:
    raw = read(address, 8)
    if type(raw) is not bytes or len(raw) != 8:
        raise ValueError('F74 reader must return exactly eight bytes')
    return struct.unpack('<Q', raw)[0]

def _check_object(read, core_base: int, pointer: int, label: str, *, core_sha256='d7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3') -> None:
    _district_source.ensure_source(core_sha256)
    table, slots = _district_source.select_tables(core_sha256, _TABLES)[label]
    if not pointer or _qword(read, pointer) != core_base + table:
        raise ValueError(f'F74 {label} object has an unexpected Core vtable')
    for slot, target in slots:
        if _qword(read, core_base + table + slot) != core_base + target:
            raise ValueError(f'F74 {label} method +{slot:#x} changed')

def _read_bytes8(function, item: int, label: str) -> bytes:
    buf = C.create_string_buffer(_GUARD + bytes(8) + _GUARD, len(_GUARD) * 2 + 8)
    output = C.addressof(buf) + len(_GUARD)
    returned = function(item, output)
    raw = buf.raw
    if raw[:len(_GUARD)] != _GUARD or raw[len(_GUARD) + 8:] != _GUARD:
        raise RuntimeError(f'item {label} wrote beyond its observed 8-byte output')
    if returned != output:
        raise ValueError(f'item {label} did not return the supplied output buffer')
    return raw[len(_GUARD):len(_GUARD) + 8]

def build_native_api(core_base: int, *, core_sha256='d7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3') -> dict:
    _district_source.ensure_source(core_sha256)
    verify_source_evidence()
    if type(core_base) is not int or core_base <= 0:
        raise ValueError('Core module base must be a positive integer')
    entries = {'get_player': (4382880, C.c_void_p, (C.c_void_p, C.c_int32)), 'release_player': (4421040, None, (C.c_void_p,)), 'player_collection': (4422336, C.c_void_p, (C.c_void_p,)), 'release_collection': (4427952, None, (C.c_void_p,)), 'collection_index': (4427984, C.c_void_p, (C.c_void_p, C.c_uint32)), 'release_item': (4406960, None, (C.c_void_p,)), 'item_raw': (4372864, C.c_uint32, (C.c_void_p,)), 'item_variant': (4407024, C.c_void_p, (C.c_void_p, C.c_void_p)), 'item_position': (4407328, C.c_void_p, (C.c_void_p, C.c_void_p)), 'item_hash': (4407392, C.c_uint32, (C.c_void_p, C.c_uint32))}
    entries = _district_source.select_specs(core_sha256, entries)
    return {name: C.WINFUNCTYPE(restype, *args)(core_base + rva) for name, (rva, restype, args) in entries.items()}

@contextmanager
def lookup_item_lease(descriptor: bytes, selector: int, *, context: int, core_base: int, read, api: dict | None=None, core_sha256='d7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'):
    _district_source.ensure_source(core_sha256)
    verify_source_evidence()
    owner, _kind, item_id = decode_descriptor(descriptor)
    if type(selector) is not int or not 0 <= selector <= 4294967295:
        raise ValueError('F74 lookup selector must be an unsigned uint32')
    if type(core_base) is not int or core_base <= 0 or (not callable(read)):
        raise ValueError('a live Core base and bounded reader are required')
    if type(context) is not int or context <= 0:
        raise ValueError('a live Core context is required')
    required = {'get_player', 'release_player', 'player_collection', 'release_collection', 'collection_index', 'release_item', 'item_raw', 'item_variant', 'item_position', 'item_hash'}
    if api is None:
        api = build_native_api(core_base, core_sha256=core_sha256)
    elif type(api) is not dict or set(api) != required or (not all((callable(v) for v in api.values()))):
        raise ValueError('F74 query seam must match the ten source operations')
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
        variant = _read_bytes8(api['item_variant'], item, '+0x30')
        position = _read_bytes8(api['item_position'], item, '+0x38')
        raw_value = api['item_raw'](item)
        item_hash = api['item_hash'](item, selector)
        for value, label in ((raw_value, 'item +0x20'), (item_hash, 'item +0x58')):
            if type(value) is not int or not 0 <= value <= 4294967295:
                raise ValueError(f'{label} must return a uint32')
        yield {'item_variant': variant, 'position': position, 'item_raw': raw_value, 'item_hash': item_hash}
    finally:
        api['release_item'](item)

def encode_record(sequence: int, fields: Fields, values: Values, **profile) -> bytes:
    validate_profile(sequence, fields, **profile)
    if type(values) is not Values or type(values.item_present) is not bool:
        raise ValueError('F74 requires an explicit native query outcome')
    if values.item_present:
        if type(values.position) is not bytes or len(values.position) != 8 or type(values.item_variant) is not bytes or (len(values.item_variant) != 8) or (type(values.item_raw) is not int) or (not 0 <= values.item_raw <= 4294967295) or (type(values.item_hash) is not int) or (not 0 <= values.item_hash <= 4294967295):
            raise ValueError('F74 live item requires position, variant, raw value and hash')
        position, raw_value, variant, item_hash = (values.position, values.item_raw, values.item_variant, values.item_hash)
    else:
        if any((v is not None for v in (values.position, values.item_raw, values.item_variant, values.item_hash))):
            raise ValueError('F74 null lookup cannot supply invented item values')
        position = struct.pack('<ii', -9999, -9999)
        raw_value = item_hash = 0
        variant = bytes.fromhex('ffff0000ffffffff')
    record = bytearray(RECORD_SIZE)
    struct.pack_into('<IIII', record, 0, RECORD_SIZE, RECORD_TYPE, sequence, 0)
    struct.pack_into('<iiHHIHHIHHIHHIHHI', record, 16, -1, -1, 65535, 0, 4294967295, 65535, 0, 4294967295, 65535, 0, 4294967295, 65535, 0, 4294967295, 65535, 0, 4294967295)
    struct.pack_into('<QI', record, 64, 0, 0)
    payload = 80
    struct.pack_into('<I', record, payload, sequence)
    struct.pack_into('<HHI', record, payload + 8, fields.owner & 65535, fields.descriptor_type, fields.item_id)
    record[payload + 16:payload + 24] = position
    struct.pack_into('<I', record, payload + 24, raw_value)
    record[payload + 32:payload + 40] = variant
    struct.pack_into('<IIII', record, payload + 40, fields.selector, fields.current, fields.previous, item_hash)
    return bytes(record)

@contextmanager
def produce_record_lease(sequence: int, fields: Fields, *, core, context: int, read, normalizer_transform_present: bool=False, profile: dict, native_api: dict | None=None, core_sha256='d7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'):
    _district_source.ensure_source(core_sha256)
    if core_sha256 != 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3':
        _district_source.verify_once(core, read, core_sha256=core_sha256)
    verify_source_evidence()
    if normalizer_transform_present is not False:
        raise ValueError('F74 normalizer transforms are outside the admitted profile')
    validate_profile(sequence, fields, **profile)
    descriptor = struct.pack('<HHI', fields.owner & 65535, fields.descriptor_type, fields.item_id)
    with lookup_item_lease(descriptor, fields.selector, context=context, core_base=int(core._handle), read=read, api=native_api, core_sha256=core_sha256) as native:
        values = Values(False, None, None, None, None) if native is None else Values(True, native['position'], native['item_raw'], native['item_variant'], native['item_hash'])
        record = encode_record(sequence, fields, values, **profile)
        yield (record, {'item_present': values.item_present, 'native_item_queries_executed': values.item_present, 'payload_exposed_to_learner': False, 'source_uninitialized_payload_ranges': [[4, 8], [28, 32], [56, 64]] if values.item_present else [[4, 8], [24, 32], [52, 64]], 'padding_policy': PADDING_POLICY})
