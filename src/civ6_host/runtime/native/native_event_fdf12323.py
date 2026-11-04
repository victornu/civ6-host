"""Source-bounded FDF12323 teardown producer with retained live item queries."""
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
from dataclasses import dataclass
from pathlib import Path
from contextlib import contextmanager
import ctypes as C
import struct
from civ6_host.runtime.native import native_event_28d6ebbe as shared
from civ6_host.runtime.native.native_application_mirror import decode_scalar
from civ6_host.runtime.native.native_host_events import copy_eight_byte_variant
from civ6_host.runtime.native.native_source_cache import load_pinned_json
EVENT_KIND, RECORD_TYPE, RECORD_SIZE = (4260438819, 160, 128)
PINNED_EVIDENCE_SHA256 = 'f7ea2e08123ed5741dce4104a882c87d200a76317652571f5fa27e5937d3757e'
_PROOF = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_event_fdf12323.py')))).resolve().parents[1] / 'evidence/native-event-fdf12323' / f'{PINNED_EVIDENCE_SHA256}.json'
_KEYS = {4081310810, 2353434172, 2716180809, 2717631346, 3606901732}
_TABLES = {'outer': (7987232, ((184, 4382880),)), 'player': (7992320, ((8, 4421040), (304, 4422336))), 'collection': (7993256, ((8, 4427952), (16, 4427984))), 'item': (7990216, ((8, 4406960), (32, 4372864), (48, 4407024)))}

def verify_source_evidence():
    proof = load_pinned_json(_PROOF, PINNED_EVIDENCE_SHA256)
    if proof['schema'] != 'civ6rl.native_event_fdf12323.static.v2' or proof['images'] != {'exe_sha256': shared._EXE_SHA, 'core_sha256': shared._CORE_SHA} or proof['registration']['callback_va'] != '0x1401452a0' or (proof['captures']['callback']['code_sha256'] != 'c07c12eaa2868ce506f7864e5c537782f40420748241fa0a9dd3dccdc7ae2a4d') or (proof['captures']['writer']['code_sha256'] != '5a02926a14387d376a6b2ece4f97288f2d1e58b57dda0043766eaf728e6c0d30') or (proof['captures']['lookup147640']['code_sha256'] != '37f97ea9ff7bd8ca4ab4ca2fdf8035d833473ce3074a81be6bcdb650b3b1b186') or (proof['captures']['normalizer']['code_sha256'] != 'c757d2f0c927f36e058ff5e57350a80beac1db2a89d3940fcb5e89c05545f23e') or (proof['empty_receiver']['sha256'] != '960a9f6026c2f2dfc3cc3c5d09dc3995b7e86d403fd328d7a56bc2e711007eea') or (proof['empty_receiver']['row']['handler_va'] != '0x1400d9af0') or (proof['contract']['record'] != {'type': RECORD_TYPE, 'size': RECORD_SIZE, 'payload_offset': 80, 'payload_size': 40, 'metadata_size': 60}):
        raise RuntimeError('FDF12323 pinned source identity changed')
    return proof

@dataclass(frozen=True)
class EventFields:
    owner: int
    item_id: int
    position_bytes: bytes
    x: int
    y: int
    selector: int
    source_value: int
    descriptor_tail: int
    descriptor_bytes: bytes

@dataclass(frozen=True)
class NativeValues:
    item_variant: bytes
    item_raw: int
    item_present: bool = True
    read_skipped_reason: str | None = None

def _fields(fields):
    if not isinstance(fields, EventFields) or type(fields.owner) is not int or (not 0 <= fields.owner <= 63) or (type(fields.descriptor_bytes) is not bytes) or (len(fields.descriptor_bytes) != 8) or (struct.unpack_from('<H', fields.descriptor_bytes)[0] != fields.owner) or (type(fields.item_id) is not int) or (not 0 <= fields.item_id <= 4294967295) or (struct.unpack_from('<I', fields.descriptor_bytes, 4)[0] != fields.item_id) or (type(fields.position_bytes) is not bytes) or (len(fields.position_bytes) != 8) or (type(fields.x) is not int) or (type(fields.y) is not int) or (struct.unpack('<ii', fields.position_bytes) != (fields.x, fields.y)) or any((type(value) is not int or not 0 <= value <= 4294967295 for value in (fields.selector, fields.source_value, fields.descriptor_tail))):
        raise ValueError('FDF12323 requires exact decoded live descriptor and position fields')

def decode_fields(raw_fields, read):
    verify_source_evidence()
    if not isinstance(raw_fields, dict) or set(raw_fields) != _KEYS:
        raise ValueError('FDF12323 requires exactly descriptor,position,A1,A1FBC,D6')
    descriptor = copy_eight_byte_variant(raw_fields[4081310810], read, expected_tag=1024)
    position = copy_eight_byte_variant(raw_fields[2353434172], read, expected_tag=0)
    fields = EventFields(struct.unpack_from('<H', descriptor)[0], struct.unpack_from('<I', descriptor, 4)[0], position, *struct.unpack('<ii', position), decode_scalar(raw_fields[2716180809], 3), decode_scalar(raw_fields[2717631346], 2), decode_scalar(raw_fields[3606901732], 2), descriptor)
    _fields(fields)
    return fields

def _profile(sequence, fields, normalizer_transform_present, per_thread_hook_present, writer_metadata_callback_present, padding_policy):
    verify_source_evidence()
    _fields(fields)
    if type(sequence) is not int or not 1 <= sequence <= 4294967295:
        raise ValueError('FDF12323 requires a nonzero uint32 sequence')
    if normalizer_transform_present is not False or per_thread_hook_present is not False or writer_metadata_callback_present is not False:
        raise ValueError('FDF12323 requires explicitly absent transform/hook/writer callbacks')
    if padding_policy != 'headless-zero-uninitialized-stack':
        raise ValueError('FDF12323 requires explicit zero source stack padding')

def encode_record(sequence, fields, values, *, normalizer_transform_present, per_thread_hook_present, writer_metadata_callback_present, padding_policy='headless-zero-uninitialized-stack', empty_receiver_state=None, missing_item_policy='refuse'):
    _profile(sequence, fields, normalizer_transform_present, per_thread_hook_present, writer_metadata_callback_present, padding_policy)
    if not isinstance(values, NativeValues) or type(values.item_variant) is not bytes or len(values.item_variant) != 8 or (type(values.item_raw) is not int) or (not 0 <= values.item_raw <= 4294967295) or (type(values.item_present) is not bool):
        raise ValueError('FDF12323 requires both exact native item query results')
    if values.item_present:
        if values.read_skipped_reason is not None:
            raise ValueError('Present item cannot skip native reads')
    elif missing_item_policy != 'zero-unread-item-DWORD' or values.read_skipped_reason not in ('player-null', 'item-null') or values.item_variant != bytes.fromhex('ffff0000ffffffff') or (values.item_raw != 0):
        raise ValueError('FDF12323 missing item requires explicit unread-DWORD policy and source sentinel')
    record = bytearray(RECORD_SIZE)
    struct.pack_into('<IIII', record, 0, RECORD_SIZE, RECORD_TYPE, sequence, 0)
    record[16:24] = b'\xff' * 8
    record[24:64] = bytes.fromhex('ffff0000ffffffff') * 5
    struct.pack_into('<I', record, 80, sequence)
    struct.pack_into('<HHI', record, 88, fields.owner, 3, fields.item_id)
    record[96:104] = fields.position_bytes
    struct.pack_into('<I', record, 104, values.item_raw)
    record[112:120] = values.item_variant
    result = bytes(record)
    if not values.item_present:
        from civ6_host.runtime.native.native_deferred_empty_profile import validate_empty_profile_record
        if not isinstance(empty_receiver_state, dict) or set(empty_receiver_state) != {'observer_registered', 'state_pointer_nonnull', 'pre_hook', 'post_hook', 'subscriber_count', 'state_flags'}:
            raise ValueError('FDF12323 missing item requires the complete empty receiver state')
        validate_empty_profile_record(result, **empty_receiver_state)
    return result

def _check(read, base, pointer, label):
    table, slots = _TABLES[label]
    actual = shared._qword(read, pointer) if pointer else 0
    if not pointer or actual != base + table:
        raise ValueError(f'Unexpected FDF12323 {label} facade: pointer={pointer or 0:#x}, vtable={actual:#x}, expected_vtable={base + table:#x}')
    for slot, target in slots:
        if shared._qword(read, base + table + slot) != base + target:
            raise ValueError('Unexpected FDF12323 ' + label + ' method')

def _api(base, api):
    entries = {'get_player': (4382880, C.c_void_p, (C.c_void_p, C.c_int32)), 'release_player': (4421040, None, (C.c_void_p,)), 'player_collection': (4422336, C.c_void_p, (C.c_void_p,)), 'release_collection': (4427952, None, (C.c_void_p,)), 'collection_index': (4427984, C.c_void_p, (C.c_void_p, C.c_uint32)), 'release_item': (4406960, None, (C.c_void_p,)), 'item_variant': (4407024, C.c_void_p, (C.c_void_p, C.c_void_p)), 'item_raw': (4372864, C.c_uint32, (C.c_void_p,))}
    if api is not None:
        if not isinstance(api, dict) or set(api) != set(entries):
            raise ValueError('FDF12323 test seam requires the exact eight source operations')
        return api
    return {name: C.WINFUNCTYPE(restype, *args)(base + rva) for name, (rva, restype, args) in entries.items()}

@contextmanager
def produce_record_lease(sequence, core, context, fields, *, normalizer_transform_present, per_thread_hook_present, writer_metadata_callback_present, padding_policy='headless-zero-uninitialized-stack', read=None, native_api=None, empty_receiver_state=None, missing_item_policy='refuse', query_diagnostic=None):
    """Yield the record while retaining a resolved item until context exit.

    Lookup147640; release collection/player; query retained item30 then20.
    Player/item null follows source skip paths only with explicit
    empty-receiver policy: raw DWORD remains source-uninitialized, zero bytes
    are never a game value. Null collection, unknown facade and cached-only
    owner remain refused.
    """
    profile = dict(normalizer_transform_present=normalizer_transform_present, per_thread_hook_present=per_thread_hook_present, writer_metadata_callback_present=writer_metadata_callback_present, padding_policy=padding_policy)
    _profile(sequence, fields, **profile)
    if query_diagnostic is not None and (not isinstance(query_diagnostic, dict)):
        raise ValueError('FDF12323 query diagnostic must be a dictionary')

    def encode(values):
        result = encode_record(sequence, fields, values, **profile, empty_receiver_state=empty_receiver_state, missing_item_policy=missing_item_policy)
        if query_diagnostic is not None:
            query_diagnostic.update(item_present=values.item_present, read_skipped_reason=values.read_skipped_reason, native_item_queries_executed=values.item_present, raw_dword_origin='native-query' if values.item_present else 'uninitialized-stack-zero-unread-policy')
        return result

    def missing(reason):
        return encode(NativeValues(bytes.fromhex('ffff0000ffffffff'), 0, False, reason))
    base = int(core._handle)
    if base <= 0 or type(context) is not int or context <= 0:
        raise ValueError('Live Core context required')
    if read is None:
        from civ6_host.runtime.native.native_setup import local_reader
        read = local_reader()
    _check(read, base, context, 'outer')
    api = _api(base, native_api)
    item = 0
    checked = False
    try:
        player = api['get_player'](context, fields.owner)
        if not player:
            yield missing('player-null')
            return
        _check(read, base, player, 'player')
        try:
            collection = api['player_collection'](player)
            _check(read, base, collection, 'collection')
            try:
                item = api['collection_index'](collection, fields.item_id)
            finally:
                api['release_collection'](collection)
        finally:
            api['release_player'](player)
        if not item:
            yield missing('item-null')
            return
        _check(read, base, item, 'item')
        checked = True
        if not shared._qword(read, item + 8):
            raise ValueError('FDF12323 requires a live item owner')
        variant = shared._out8(api['item_variant'], item)
        raw = api['item_raw'](item)
        yield encode(NativeValues(variant, raw))
    finally:
        if checked:
            api['release_item'](item)

def produce_record(sequence, core, context, fields, *, normalizer_transform_present, per_thread_hook_present, writer_metadata_callback_present, padding_policy='headless-zero-uninitialized-stack', read=None, native_api=None, empty_receiver_state=None, missing_item_policy='refuse', query_diagnostic=None):
    """Compatibility wrapper returning bytes after closing the native item lease.

    For source-order lifetime through a synchronous writer/enqueue, use
    ``produce_record_lease`` and perform the enqueue inside the ``with`` block.
    """
    with produce_record_lease(sequence, core, context, fields, normalizer_transform_present=normalizer_transform_present, per_thread_hook_present=per_thread_hook_present, writer_metadata_callback_present=writer_metadata_callback_present, padding_policy=padding_policy, read=read, native_api=native_api, empty_receiver_state=empty_receiver_state, missing_item_policy=missing_item_policy, query_diagnostic=query_diagnostic) as record:
        return record
