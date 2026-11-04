"""Source-backed selector partition and DistrictPillaged notification.

The A3 writer copies three bytes left by the preceding 9D civilization query.
Its district query is independent: only those three payload bytes are reused.
"""
from civ6_host.runtime import placement_event_profile as _placement_events
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
from dataclasses import dataclass
from pathlib import Path
import struct
from civ6_host.runtime.native.native_source_cache import load_pinned_json
PROOF_SHA256 = '1afec6235ee0e8096f7aa5bc9112b27dbea2814b51098703783ae5c86d7074e8'
AUX_SELECTOR = 1362298481
RECORD_TYPE, RECORD_SIZE = (163, 128)

def verify_source_evidence():
    from civ6_host.runtime.native import native_event_6d7163b0 as base
    from civ6_host.runtime.native.native_deferred_empty_profile import SIX_D_SELECTOR_RECEIVER_SHA256
    root = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_event_6d7163b0_selector.py')))).resolve().parents[1]
    proof = load_pinned_json(root / 'evidence/native-event-6d7163b0-selector' / (PROOF_SHA256 + '.json'), PROOF_SHA256)
    contract = proof['contract']
    if proof['schema'] != 'civ6rl.native_event_6d7163b0.selector.static.v1' or proof['images'] != {'exe_sha256': 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63', 'core_sha256': 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'} or proof['parents']['existing_two_pass_producer']['sha256'] != base.PROOF_SHA256 or (proof['parents']['auxiliary_receiver']['sha256'] != SIX_D_SELECTOR_RECEIVER_SHA256) or (SIX_D_SELECTOR_RECEIVER_SHA256 != '6db4ee267e64ab27c542037b6b9352567af369b7e08c246078c5e92d7f591cc7') or (contract['selector_domain'] != (0, 4294967295)) or (contract['owner_profile'] != (0, 63)) or (contract['id_domain'] != (0, 4294967295)) or (set(contract['input_keys']) != {base.POSITION_KEY, base.SELECTOR_KEY, base.A1FBC_KEY, base.D6_KEY, base.DESCRIPTOR_KEY}) or (contract['tags'] != {'8C468E3C': 0, 'A1E5A149': 3, 'A1FBC372': 2, 'D6FCF3E4': 2, 'F343DC5A': 1024}) or (contract['blob_envelope'] != {'size': 8, 'flags': 553648129, 'nonnull_pointer': True}) or (contract['scalar_flags'] != 0) or (contract['selector_partition'] != ({'condition': 'equal', 'selector': 3434534334, 'paths': ('optional_initial_9d', 'common_9d'), 'records': ((157, 144), (157, 144))}, {'condition': 'equal', 'selector': AUX_SELECTOR, 'paths': ('common_9d', 'auxiliary_a3'), 'records': ((157, 144), (163, 128))}, {'condition': 'all_other_uint32', 'excluded': (3434534334, AUX_SELECTOR), 'paths': ('common_9d',), 'records': ((157, 144),)})) or (contract['a3_record'] != {'type': RECORD_TYPE, 'size': RECORD_SIZE, 'payload_offset': 80, 'payload_size': 48, 'metadata_flag': 0, 'undefined_ranges': ((84, 88), (108, 112)), 'allocation_zero_ranges': ((76, 80),), 'inherited_initialized_range': (125, 128)}) or (contract['inherited_stack_proof']['not_padding_or_default'] is not True) or (contract['inherited_stack_proof']['previous_store_va'] != '0x140144d30') or (contract['inherited_stack_proof']['current_store_va'] != '0x140144f8b') or (proof['verification']['all_captured_instructions_match_pinned_pe'] is not True):
        raise RuntimeError('6D7163B0 selector source identity changed')
    base.verify_source_evidence()
    return proof

def record_plan(selector):
    verify_source_evidence()
    if type(selector) is not int or not 0 <= selector <= 4294967295:
        raise ValueError('6D7163B0 selector must be an exact uint32')
    if selector == 3434534334:
        return ((157, 144), (157, 144))
    if selector == AUX_SELECTOR:
        return ((157, 144), (RECORD_TYPE, RECORD_SIZE))
    return ((157, 144),)

@dataclass(frozen=True)
class AuxiliaryNativeValues:
    item_raw: int
    item_variant: bytes
    snapshot_flag29: int
    vector_count: int
    vector_capacity: int

def _values(values):
    from civ6_host.runtime.native import native_event_6d7163b0 as base
    if not isinstance(values, AuxiliaryNativeValues) or type(values.item_raw) is not int or (not 0 <= values.item_raw <= 4294967295) or (type(values.item_variant) is not bytes) or (len(values.item_variant) != 8) or (type(values.snapshot_flag29) is not int) or (not 0 <= values.snapshot_flag29 <= 255) or (type(values.vector_count) is not int) or (type(values.vector_capacity) is not int) or (not 0 <= values.vector_count <= values.vector_capacity <= base.MAX_VECTOR_ENTRIES):
        raise ValueError('DistrictPillaged needs its actual bounded native query results')

def _profile(sequence, fields, previous_values, **profile):
    from civ6_host.runtime.native import native_event_6d7163b0 as base
    verify_source_evidence()
    base._profile(sequence, fields, **profile)
    base._values(previous_values)
    if fields.selector != AUX_SELECTOR:
        raise ValueError('DistrictPillaged is emitted only by selector51330671')
    shape = bytearray(RECORD_SIZE)
    struct.pack_into('<II', shape, 0, RECORD_SIZE, RECORD_TYPE)
    base._empty(shape, profile['empty_receiver_state'])

def encode_auxiliary_record(sequence, fields, values, previous_values, **profile):
    from civ6_host.runtime.native import native_event_6d7163b0 as base
    _profile(sequence, fields, previous_values, **profile)
    _values(values)
    record = bytearray(RECORD_SIZE)
    struct.pack_into('<IIII', record, 0, RECORD_SIZE, RECORD_TYPE, sequence, 0)
    record[16:24] = b'\xff' * 8
    record[24:64] = bytes.fromhex('ffff0000ffffffff') * 5
    struct.pack_into('<I', record, 80, sequence)
    struct.pack_into('<HHI', record, 88, fields.owner, 3, fields.item_id)
    record[96:104] = fields.position_bytes
    struct.pack_into('<I', record, 104, values.item_raw)
    record[112:120] = values.item_variant
    struct.pack_into('<I', record, 120, fields.a1fbc_value)
    record[124] = values.snapshot_flag29
    record[125:128] = struct.pack('<I', previous_values.civilization_id & 4294967295)[1:]
    base._empty(record, profile['empty_receiver_state'])
    return bytes(record)

def produce_auxiliary_record(sequence, core, context, fields, previous_values, *, enqueue_record, normalizer_transform_present, per_thread_hook_present, writer_metadata_callback_present, padding_policy, empty_receiver_state, read=None, native_api=None, core_sha256='d7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'):
    from civ6_host.runtime.native import native_event_6d7163b0 as base
    profile = dict(normalizer_transform_present=normalizer_transform_present, per_thread_hook_present=per_thread_hook_present, writer_metadata_callback_present=writer_metadata_callback_present, padding_policy=padding_policy, empty_receiver_state=empty_receiver_state)
    _profile(sequence, fields, previous_values, **profile)
    if not callable(enqueue_record):
        raise ValueError('DistrictPillaged requires synchronous publication while the district is live')
    image_base = int(core._handle)
    if not 0 < image_base < 1 << 63 or type(context) is not int or context <= 0:
        raise ValueError('DistrictPillaged requires the live relocated Core context')
    if read is None:
        from civ6_host.runtime.native.native_setup import local_reader
        read = local_reader()
    _placement_events.verify_once(core, read, core_sha256)
    base._check_object(read, image_base, context, 'outer', core_sha256=core_sha256)
    api = base._api(image_base, native_api, core_sha256=core_sha256)
    item, item_checked = (0, False)
    try:
        player = api['get_player'](context, fields.owner)
        base._check_object(read, image_base, player, 'player', core_sha256=core_sha256)
        try:
            collection = api['player_collection'](player)
            base._check_object(read, image_base, collection, 'collection', core_sha256=core_sha256)
            try:
                item = api['collection_index'](collection, fields.item_id)
            finally:
                api['release_collection'](collection)
        finally:
            api['release_player'](player)
        base._check_object(read, image_base, item, 'item', core_sha256=core_sha256)
        item_checked = True
        if not base._qword(read, item + 8):
            raise ValueError('DistrictPillaged requires a nonnull native district owner')
        snapshot, output = base._guarded(base.SNAPSHOT_SIZE)
        vector = None
        try:
            api['item_snapshot'](item, output, 0)
            snap = base._checked_buffer(snapshot, base.SNAPSHOT_SIZE)
            vector, capacity, count = base._snapshot_vector(snap)
            variant, variant_out = base._guarded(8)
            returned = api['item_variant'](item, variant_out)
            descriptor = base._checked_buffer(variant, 8)
            if returned != variant_out:
                raise ValueError('DistrictPillaged descriptor returned a different output pointer')
            raw = api['item_raw'](item)
            flag = snap[29]
        finally:
            if vector is None:
                try:
                    vector, _, _ = base._snapshot_vector(base._checked_buffer(snapshot, base.SNAPSHOT_SIZE))
                except (ValueError, RuntimeError):
                    pass
            if vector is not None:
                api['free_vector'](vector)
        values = AuxiliaryNativeValues(raw, descriptor, flag, count, capacity)
        record = encode_auxiliary_record(sequence, fields, values, previous_values, **profile)
        enqueue_record(record, 1, values)
        return values
    finally:
        if item_checked:
            api['release_item'](item)
