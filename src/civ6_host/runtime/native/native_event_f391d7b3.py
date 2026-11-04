"""Source-bounded ImprovementVisibilityChanged; no gameplay replacement.

The mandatory 1477A0 queries release their component and plot before the
optional 147F10 map query. All acquired facades are released before enqueue.
"""
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
from dataclasses import dataclass
from pathlib import Path
import struct
from civ6_host.runtime.native import native_event_a625c726 as shared
from civ6_host.runtime.native.native_application_mirror import decode_scalar
from civ6_host.runtime.native.native_deferred_empty_profile import validate_empty_profile_record
from civ6_host.runtime.native.native_event_827289e6 import query_optional_position
from civ6_host.runtime.native.native_host_events import copy_eight_byte_variant
from civ6_host.runtime.native.native_source_cache import load_pinned_json
EVENT_KIND, RECORD_TYPE, RECORD_SIZE = (4086421427, 145, 160)
POSITION_KEY, SELECTOR_KEY, VALUE_KEY = (2353434172, 2716180809, 3606901732)
INDEX_KEY, PAIR_KEY, SCALAR_KEY, PLAYER_KEY = (2717631346, 1532339015, 955421384, 4033489650)
_BASIC_KEYS = {POSITION_KEY, SELECTOR_KEY, VALUE_KEY}
_EXTENDED_KEYS = _BASIC_KEYS | {INDEX_KEY, PAIR_KEY, SCALAR_KEY, PLAYER_KEY}
PROOF_SHA256 = 'd4d74903f64c7579fcece750f4d2d8323c0b8dd9c7cac35a32a87a58431365b1'
TYPED_POSITION_PROOF_SHA256 = '7c8114248a127b13fc0745ef3c3c0a4ff442ae93c03e00df78ad8fd29a3a789a'
PINNED_EVIDENCE_SHA256 = PROOF_SHA256
SCOPE_PROOF_SHA256 = 'a8c68d0467fa5c2348bca9a097dc7a6a31442bf05b4d476e2895092be4d0278b'
PADDING_POLICY = shared.PADDING_POLICY
NativeValues = shared.NativeValues

def verify_scoped_source_evidence():
    root = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_event_f391d7b3.py')))).resolve().parents[1]
    proof = load_pinned_json(root / 'evidence/native-f391d7b3-positive-scope' / (SCOPE_PROOF_SHA256 + '.json'), SCOPE_PROOF_SHA256)
    contract = proof['source_contract']
    if proof['schema'] != 'civ6rl.native_f391d7b3_positive_scope.static.v1' or proof['parents']['producer']['sha256'] != PROOF_SHA256 or proof['parents']['typed_position']['sha256'] != TYPED_POSITION_PROOF_SHA256 or (contract['kind'] != hex(EVENT_KIND)) or (contract['record_type'] != RECORD_TYPE) or (contract['record_size'] != RECORD_SIZE) or (contract['record_metadata_flag_offset'] != 72) or (contract['n_global']['va'] != '0x1422d7c6c') or (contract['m_global']['va'] != '0x1422d7c68') or (contract['cache_gate'] is not False) or (proof['captures']['callback']['code_sha256'] != '98422eeb6c1446075bb696a5a8f1f524071180518584bcba39c8f03b9cce7037') or (proof['captures']['writer']['code_sha256'] != 'd7b2cdb0e8b3f1e0d79f5db59c6cb7a4ab2787d8bcdcde2f613a9bcee56908a7'):
        raise RuntimeError('F391 notification metadata source differs')
    verify_source_evidence()
    return proof

def verify_source_evidence():
    from civ6_host.runtime.native.native_deferred_empty_profile import F391_RECEIVER_SHA256
    from civ6_host.runtime.native.native_host_event_registry import EXE_EVENT_CALLBACKS
    root = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_event_f391d7b3.py')))).resolve().parents[1]
    proof = load_pinned_json(root / 'evidence/native-event-f391d7b3' / (PROOF_SHA256 + '.json'), PROOF_SHA256)
    if proof['schema'] != 'civ6rl.native_event_f391d7b3.static.v1' or proof['images'] != {'exe_sha256': 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63', 'core_sha256': 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'} or proof['parents']['shared_plot_query']['sha256'] != shared.PROOF_SHA256 or (proof['parents']['shared_optional_query']['sha256'] != '30a78ad61e21b0003de294a0fbd787402835d29a9a89e7bf441418087a39fab1') or (proof['parents']['positive_query_order']['sha256'] != '1881a3beb1d4e9038871d20905ee19b2dc1da6b67db06efc61a29bd961a84292') or (proof['parents']['receiver']['sha256'] != F391_RECEIVER_SHA256) or (EXE_EVENT_CALLBACKS.get(EVENT_KIND) != 1348112) or (proof['contract']['record']['type'] != RECORD_TYPE) or (proof['contract']['record']['size'] != RECORD_SIZE) or (set(proof['contract']['input_profiles']['witnessed_three_keys']) != _BASIC_KEYS) or (set(proof['contract']['input_profiles']['static_seven_keys']) != _EXTENDED_KEYS) or (proof['verification'] != {'all_captured_instructions_match_pinned_pe': True, 'instructions_rechecked': 8093, 'parent_instructions_rechecked': 13471, 'callback_scan_instructions_rechecked': 20696}):
        raise RuntimeError('F391D7B3 pinned source identity changed')
    shared.verify_source_evidence()
    return proof

def verify_typed_position_evidence():
    from civ6_host.runtime.native import native_event_827289e6 as normalized
    root = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_event_f391d7b3.py')))).resolve().parents[1]
    proof = load_pinned_json(root / 'evidence/native-event-f391d7b3-position-variant' / (TYPED_POSITION_PROOF_SHA256 + '.json'), TYPED_POSITION_PROOF_SHA256)
    contract = proof['contract']
    if proof['schema'] != 'civ6rl.native_event_f391d7b3.position_variant.static.v1' or proof['images'] != {'exe_sha256': 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63', 'core_sha256': 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'} or proof['parents']['f391']['sha256'] != PROOF_SHA256 or (proof['parents']['shared_tag13_normalizer']['sha256'] != normalized._EVIDENCE_SHA256) or (set(contract['input_keys']) != _EXTENDED_KEYS) or (contract['raw_position_tag'] != 13) or (contract['basic_three_field_tag13_admitted'] is not False) or (contract['scalar_flags'] != 0) or (contract['blob_envelope'] != {'size': 8, 'flags': 553648129, 'nonnull_pointer': True}) or (contract['tags'] != {'8C468E3C': 13, '5B55A347': 1024, 'A1E5A149': 3, '38F292C8': 2, 'A1FBC372': 2, 'D6FCF3E4': 2, 'F06A2AF2': 2}) or (contract['normalization_destination'] != 72) or (contract['retagging_performed'] is not False) or (contract['record_type'] != RECORD_TYPE) or (contract['record_size'] != RECORD_SIZE) or (contract['query_order_unchanged'] is not True) or (proof['verification']['normalizer_identical_to_827'] is not True) or (proof['verification']['callback_writer_identical_to_f391_parent'] is not True) or (proof['verification']['all_captured_instructions_match_pinned_pe'] is not True):
        raise RuntimeError('F391D7B3 typed-position source proof changed')
    verify_source_evidence()
    normalized.verify_source_evidence()
    return proof

@dataclass(frozen=True)
class EventFields:
    common: shared.EventFields
    optional_index: int | None = None
    optional_scalar: int | None = None
    ignored_player: int | None = None
    pair_bytes: bytes | None = None
    input_shape: str = 'basic-three-field'

def _fields(fields):
    if not isinstance(fields, EventFields):
        raise ValueError('F391D7B3 requires its decoded input fields')
    shared._fields(fields.common)
    optional = (fields.optional_index, fields.optional_scalar, fields.ignored_player)
    if fields.input_shape == 'basic-three-field':
        if any((v is not None for v in optional)) or fields.pair_bytes is not None:
            raise ValueError('F391D7B3 basic input cannot inject optional fields')
    elif fields.input_shape == 'extended-seven-field':
        if any((type(v) is not int or not 0 <= v <= 4294967295 for v in optional)) or type(fields.pair_bytes) is not bytes or len(fields.pair_bytes) != 8:
            raise ValueError('F391D7B3 extended input needs typed DWORDs and the actual pair')
    else:
        raise ValueError('F391D7B3 input shape is not source-backed')

def decode_fields(raw_fields, read):
    verify_source_evidence()
    if type(raw_fields) is not dict or set(raw_fields) not in (_BASIC_KEYS, _EXTENDED_KEYS) or any((type(raw) is not bytes or len(raw) != 24 for raw in raw_fields.values())):
        raise ValueError('F391D7B3 requires exact three/seven typed fields')
    extended = set(raw_fields) == _EXTENDED_KEYS
    scalar_tags = {SELECTOR_KEY: 3, VALUE_KEY: 2}
    if extended:
        scalar_tags.update({INDEX_KEY: 2, SCALAR_KEY: 2, PLAYER_KEY: 2})
    scalars = {key: decode_scalar(raw_fields[key], tag) for key, tag in scalar_tags.items()}
    if extended and struct.unpack_from('<H', raw_fields[POSITION_KEY])[0] == 13:
        verify_typed_position_evidence()
        from civ6_host.runtime.native.native_event_827289e6 import decode_fields as decode_typed_position
        decoded = decode_typed_position(raw_fields, read)
        position = decoded['normalized_qword_48']
        pair = decoded['optional_metadata_bytes_5b55a347']
    else:
        position = copy_eight_byte_variant(raw_fields[POSITION_KEY], read, expected_tag=0)
        pair = copy_eight_byte_variant(raw_fields[PAIR_KEY], read, expected_tag=1024) if extended else None
    fields = EventFields(shared.EventFields(position, *struct.unpack('<ii', position), scalars[SELECTOR_KEY], scalars[VALUE_KEY]), scalars.get(INDEX_KEY), scalars.get(SCALAR_KEY), scalars.get(PLAYER_KEY), pair, 'extended-seven-field' if extended else 'basic-three-field')
    _fields(fields)
    return fields

def _profile(sequence, fields, *, notification_counter, entity_listener_count, normalizer_transform_present, thread_hook_present, writer_metadata_callback_present, padding_policy, empty_receiver_state):
    verify_source_evidence()
    _fields(fields)
    if type(sequence) is not int or not 1 <= sequence <= 2147483647:
        raise ValueError('F391D7B3 sequence exceeds the bounded native queue profile')
    if type(notification_counter) is not int or notification_counter != 0:
        raise ValueError('F391D7B3 active notification counter is not implemented')
    if type(entity_listener_count) is not int or entity_listener_count != 0:
        raise ValueError('F391D7B3 requires the closed empty entity-observer profile')
    if normalizer_transform_present is not False or thread_hook_present is not False or writer_metadata_callback_present is not False:
        raise ValueError('F391D7B3 requires absent optional hooks/services')
    if padding_policy != PADDING_POLICY:
        raise ValueError('F391D7B3 requires explicit unread-gap handling')
    if type(empty_receiver_state) is not dict or set(empty_receiver_state) != {'observer_registered', 'state_pointer_nonnull', 'pre_hook', 'post_hook', 'subscriber_count', 'state_flags'}:
        raise ValueError('F391D7B3 requires the actual complete empty receiver state')
    shape = bytearray(RECORD_SIZE)
    struct.pack_into('<II', shape, 0, RECORD_SIZE, RECORD_TYPE)
    validate_empty_profile_record(shape, **empty_receiver_state)

def encode_record(sequence, fields, values, *, optional_position_bytes=None, **profile):
    _profile(sequence, fields, **profile)
    if not isinstance(values, NativeValues):
        raise ValueError('F391D7B3 requires all native query results')
    for name in ('city_id', 'civilization_id', 'plot_value30'):
        shared._int_range(getattr(values, name), 0, 4294967295, name)
    for name in ('component_value10', 'component_value30'):
        shared._int_range(getattr(values, name), -(1 << 31), 4294967295, name)
    for name in ('secondary_value', 'plot_valuec0'):
        shared._int_range(getattr(values, name), -(1 << 31), (1 << 31) - 1, name)
    shared._int_range(values.component_owner18, -1, 63, 'component owner')
    shared._int_range(values.city_owner, -128, 127, 'snapshot178 owner')
    shared._int_range(values.snapshot180_word4, -32768, 32767, 'snapshot180 WORD')
    for name in ('plot_flagc8', 'plot_flage0'):
        shared._int_range(getattr(values, name), 0, 255, name)
    if values.component_owner18 == -1 and (values.secondary_value != -1 or values.civilization_id != 4294967295):
        raise ValueError('F391D7B3 absent component owner must preserve source sentinels')
    positive = fields.optional_index is not None and fields.optional_index < 2147483648
    if positive:
        if type(optional_position_bytes) is not bytes or len(optional_position_bytes) != 8:
            raise ValueError('F391D7B3 positive index requires the native optional position')
        optional_scalar = fields.optional_scalar
    else:
        if optional_position_bytes is not None:
            raise ValueError('F391D7B3 absent/negative index cannot inject a position')
        optional_position_bytes = struct.pack('<ii', -9999, -9999)
        optional_scalar = 0
    record = bytearray(RECORD_SIZE)
    struct.pack_into('<IIII', record, 0, RECORD_SIZE, RECORD_TYPE, sequence, 0)
    record[16:24] = b'\xff' * 8
    record[24:64] = bytes.fromhex('ffff0000ffffffff') * 5
    struct.pack_into('<I', record, 80, sequence)
    record[88:96] = fields.common.position_bytes
    struct.pack_into('<HHI', record, 96, values.city_owner & 65535, 2, values.city_id)
    struct.pack_into('<IIIIIII', record, 104, values.component_value10 & 4294967295, values.component_owner18 & 4294967295, values.component_value30 & 4294967295, values.secondary_value & 4294967295, values.civilization_id, values.snapshot180_word4 & 4294967295, values.plot_value30)
    record[132:136] = bytes((values.plot_flagc8, int(values.plot_valuec0 > 0), 0, values.plot_flage0))
    struct.pack_into('<I', record, 136, fields.common.value)
    record[140:148] = optional_position_bytes
    struct.pack_into('<I', record, 148, optional_scalar)
    record[152:160] = fields.pair_bytes if fields.pair_bytes is not None else bytes.fromhex('ffff0000ffffffff')
    validate_empty_profile_record(record, **profile['empty_receiver_state'])
    return bytes(record)

def produce_record(sequence, core, context, fields, *, notification_counter, entity_listener_count, normalizer_transform_present, thread_hook_present, writer_metadata_callback_present, padding_policy, empty_receiver_state, expected_civilization_hashes=None, read=None, optional_native_api=None, core_sha256='d7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3', **query_options):
    profile = dict(notification_counter=notification_counter, entity_listener_count=entity_listener_count, normalizer_transform_present=normalizer_transform_present, thread_hook_present=thread_hook_present, writer_metadata_callback_present=writer_metadata_callback_present, padding_policy=padding_policy, empty_receiver_state=empty_receiver_state)
    _profile(sequence, fields, **profile)
    values = shared.query_native_values(core, context, fields.common, expected_civilization_hashes=expected_civilization_hashes, read=read, **query_options, core_sha256=core_sha256)
    optional_position = None
    if fields.optional_index is not None and fields.optional_index < 2147483648:
        optional_position = query_optional_position(core, context, fields.optional_index, read=read, native_api=optional_native_api, core_sha256=core_sha256)
    return encode_record(sequence, fields, values, optional_position_bytes=optional_position, **profile)

def produce_scoped_record(sequence, core, context, fields, *, notification_counter, metadata_counter, core_sha256='d7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3', **profile):
    """Preserve native query order, then apply this callback's N/M metadata.

    Zero passed to the old formatter selects its default metadata only. The
    live N/M pair is never changed here. The owning synchronous host commits
    staged M after successful enqueue; any query/enqueue failure is fatal.
    """
    verify_scoped_source_evidence()
    from civ6_host.runtime.native.native_notification_metadata import metadata_scope_transition
    metadata_scope_transition(notification_counter, metadata_counter)
    record = bytearray(produce_record(sequence, core, context, fields, notification_counter=0, **profile, core_sha256=core_sha256))
    flag, after = metadata_scope_transition(notification_counter, metadata_counter)
    struct.pack_into('<I', record, 72, flag)
    validate_empty_profile_record(record, **profile['empty_receiver_state'])
    return (bytes(record), after)
