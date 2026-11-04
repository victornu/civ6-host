"""City descriptor/value event with source-backed optional map lookup."""
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
from dataclasses import dataclass
from pathlib import Path
import struct
from civ6_host.runtime.native import native_event_51c84cba as descriptor_codec
from civ6_host.runtime.native.native_event_827289e6 import query_optional_position
from civ6_host.runtime.native.native_source_cache import load_pinned_json
EVENT_KIND, RECORD_TYPE, RECORD_SIZE = (490036867, 92, 128)
PIN = '947423e1650b46a30f1ce260424f29cea03bd0b82442ea844e2a2c8283012b2d'
POSITIVE_PROOF_SHA256 = '38453d9976ef7e6dbfa16ca64fbfc2cf1c04ab61229af57a01c448c28083eead'
PROOF = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_event_1d355e83.py')))).resolve().parents[1] / 'evidence/native-event-1d355e83' / f'{PIN}.json'
POSITIVE_PROOF = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_event_1d355e83.py')))).resolve().parents[1] / 'evidence/native-event-1d355e83-positive' / f'{POSITIVE_PROOF_SHA256}.json'
_BASIC_KEYS = {594779970, 2716180809, 3606901732}
_PAIR_KEYS = _BASIC_KEYS | {1532339015, 4033489650}
_EXTENDED_KEYS = _BASIC_KEYS | {2717631346, 1532339015, 955421384, 4033489650}
_DEFAULT_PAIR = bytes.fromhex('ffff0000ffffffff')

@dataclass(frozen=True)
class EventFields(descriptor_codec.EventFields):
    input_shape: str = 'basic-three-field'
    optional_index: int | None = None
    optional_scalar: int | None = None
    ignored_player: int | None = None
    metadata_pair_bytes: bytes = _DEFAULT_PAIR

    @property
    def optional_fields_absent(self):
        return self.input_shape == 'basic-three-field'

def verify_source_evidence():
    proof = load_pinned_json(PROOF, PIN)
    if proof['schema'] != 'civ6rl.native_event_1d355e83.static.v2' or proof['image']['sha256'] != 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63' or proof['registration_registry']['registration']['callback_va'] != '0x140142590' or (proof['writer_layout']['record_type'] != '0x5c'):
        raise RuntimeError('1D355E83 source identity changed')
    positive = load_pinned_json(POSITIVE_PROOF, POSITIVE_PROOF_SHA256)
    if positive['schema'] != 'civ6rl.native_event_1d355e83_positive.static.v1' or positive['images']['exe_sha256'] != 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63' or positive['images']['core_sha256'] != 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3' or (positive['registration']['registration']['callback_va'] != '0x140142590') or (positive['contract']['record_type'] != 92) or (positive['contract']['record_changes']['optional_position8_at_record'] != 100) or (positive['contract']['record_changes']['scalar38F_dword_at_record'] != 108) or (positive['contract']['reuse'] != 'Use query_optional_position from827 with a fresh native map acquisition for each positive callback. No separate item/plot query or lease exists in these two callbacks. Preserve each existing codec metadata, descriptor, mode,boolean and padding behavior; only replace optional coordinate/scalar outputs.'):
        raise RuntimeError('1D355E83 positive query proof identity changed')

def decode_fields(raw_fields, read):
    verify_source_evidence()
    if not isinstance(raw_fields, dict) or set(raw_fields) not in (_BASIC_KEYS, _PAIR_KEYS, _EXTENDED_KEYS):
        raise ValueError('1D355E83 requires exact three/five/seven fields; other optional input is refused')
    extended = set(raw_fields) == _EXTENDED_KEYS
    has_pair = set(raw_fields) != _BASIC_KEYS
    basic = descriptor_codec.decode_fields({key: raw_fields[key] for key in _BASIC_KEYS}, read)
    fields = EventFields(basic.selector, basic.value, basic.descriptor_bytes, basic.owner, basic.item_id, 'extended-seven-field' if extended else 'pair-five-field' if has_pair else 'basic-three-field', descriptor_codec.decode_scalar(raw_fields[2717631346], 2) if extended else None, descriptor_codec.decode_scalar(raw_fields[955421384], 2) if extended else None, descriptor_codec.decode_scalar(raw_fields[4033489650], 2) if has_pair else None, descriptor_codec.copy_eight_byte_variant(raw_fields[1532339015], read, expected_tag=1024) if has_pair else _DEFAULT_PAIR)
    _validate(fields)
    return fields

def _validate(fields):
    if not isinstance(fields, EventFields):
        raise ValueError('1D355E83 requires its decoded input profile')
    descriptor_codec._validate(fields)
    if type(fields.metadata_pair_bytes) is not bytes or len(fields.metadata_pair_bytes) != 8:
        raise ValueError('1D355E83 optional pair must be exactly eight bytes')
    optional = (fields.optional_index, fields.optional_scalar, fields.ignored_player)
    if fields.input_shape == 'basic-three-field':
        if fields.metadata_pair_bytes != _DEFAULT_PAIR or any((v is not None for v in optional)):
            raise ValueError('1D355E83 basic input cannot inject optional fields')
    elif fields.input_shape == 'pair-five-field':
        if fields.optional_index is not None or fields.optional_scalar is not None or type(fields.ignored_player) is not int or (not 0 <= fields.ignored_player <= 4294967295):
            raise ValueError('1D355E83 five-field input has no optional index/scalar')
    elif fields.input_shape == 'extended-seven-field':
        if any((type(v) is not int or not 0 <= v <= 4294967295 for v in optional)):
            raise ValueError('1D355E83 optional query values must be DWORDs')
    else:
        raise ValueError('1D355E83 input shape is not source-backed')

def encode_record(sequence, fields, *, notification_counter, notification_limit, normalizer_transform_present, per_thread_hook_present, writer_metadata_callback_present, padding_policy, core=None, context=None, read=None, optional_native_api=None, core_sha256='d7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'):
    verify_source_evidence()
    _validate(fields)
    if any((type(x) is not int or x != 0 for x in (notification_counter, notification_limit))):
        raise ValueError('1D355E83 admits only the zero notification-counter profile')
    record = bytearray(descriptor_codec.encode_record(sequence, fields, normalizer_transform_present=normalizer_transform_present, per_thread_hook_present=per_thread_hook_present, writer_metadata_callback_present=writer_metadata_callback_present, padding_policy=padding_policy))
    record.extend(bytes(16))
    struct.pack_into('<II', record, 0, RECORD_SIZE, RECORD_TYPE)
    struct.pack_into('<iiI', record, 100, -9999, -9999, 0)
    if fields.input_shape == 'extended-seven-field' and fields.optional_index < 2147483648:
        position = query_optional_position(core, context, fields.optional_index, read=read, native_api=optional_native_api, core_sha256=core_sha256)
        if type(position) is not bytes or len(position) != 8:
            raise ValueError('1D355E83 requires the complete native optional position')
        record[100:108] = position
        struct.pack_into('<I', record, 108, fields.optional_scalar)
    record[112:120] = fields.metadata_pair_bytes
    return bytes(record)
