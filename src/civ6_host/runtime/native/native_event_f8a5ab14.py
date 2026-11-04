"""UnitDamageChanged notification, following the Core's own combat effects.

No damage is computed here. The admitted profile copies three DWORDs and the
normalized unit descriptor into the original application record layout.
"""
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
from dataclasses import dataclass
from pathlib import Path
import struct
from civ6_host.runtime.native.native_application_mirror import decode_scalar
from civ6_host.runtime.native.native_host_events import copy_eight_byte_variant
from civ6_host.runtime.native.native_player_event_domains import validate_sequence
from civ6_host.runtime.native.native_source_cache import load_pinned_json
EVENT_KIND, RECORD_TYPE, RECORD_SIZE = (4171606804, 33, 112)
SELECTOR_KEY, D6_KEY, A1FBC_KEY = (2716180809, 3606901732, 2717631346)
VALUE_38F_KEY, DESCRIPTOR_KEY = (955421384, 4032072631)
PADDING_POLICY = 'zero-unread-unit-damage-stack-gaps-empty-receiver'
PROOF_SHA256 = '76fbbc97ae12a79799e828a832b7915fc39b555abcd4cd7b62ad74bf6722dd99'
ROOT = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_event_f8a5ab14.py')))).resolve().parents[1]

def verify_source_evidence():
    from civ6_host.runtime.native.native_deferred_empty_profile import UNIT_DAMAGE_RECEIVER_SHA256
    if not PROOF_SHA256:
        raise RuntimeError('UnitDamageChanged producer proof is not pinned')
    proof = load_pinned_json(ROOT / 'evidence/native-event-f8a5ab14' / (PROOF_SHA256 + '.json'), PROOF_SHA256)
    contract = proof['contract']
    if proof['schema'] != 'civ6rl.native_event_f8a5ab14.static.v1' or proof['images'] != {'exe_sha256': 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63', 'core_sha256': 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'} or proof['registry']['registration']['callback_va'] != '0x140155ad0' or (proof['registry']['registration']['kind'] != EVENT_KIND) or (proof['captures']['callback']['code_sha256'] != 'a43ac211dc959597a9e0b9546c531e0075fb9f8ceecc05f80e490666e684f564') or (proof['captures']['writer']['code_sha256'] != '35e55d32d8743945a6381cbc1a394bc817e933c9f2f86dede6457b24880b2a4d') or (proof['captures']['normalizer']['code_sha256'] != 'c757d2f0c927f36e058ff5e57350a80beac1db2a89d3940fcb5e89c05545f23e') or (proof['parents']['receiver']['sha256'] != UNIT_DAMAGE_RECEIVER_SHA256) or (contract['kind'] != EVENT_KIND) or (set(contract['field_keys']) != {SELECTOR_KEY, D6_KEY, A1FBC_KEY, VALUE_38F_KEY, DESCRIPTOR_KEY}) or (contract['tags'] != {'38F292C8': 2, 'A1E5A149': 3, 'A1FBC372': 2, 'D6FCF3E4': 2, 'F0548BB7': 1024}) or (contract['blob_envelope'] != {'size': 8, 'flags': 553648129, 'nonnull_pointer': True}) or (contract['record']['type'] != RECORD_TYPE) or (contract['record']['size'] != RECORD_SIZE) or (contract['record']['metadata_flag'] != 0) or (contract['record']['undefined_ranges'] != ((84, 88), (108, 112))):
        raise RuntimeError('UnitDamageChanged producer source changed')
    return proof

@dataclass(frozen=True)
class EventFields:
    selector: int
    d6_value: int
    a1fbc_value: int
    value_38f: int
    owner: int
    unit_id: int

def _validate_fields(fields):
    if not isinstance(fields, EventFields):
        raise ValueError('UnitDamageChanged requires its decoded fields')
    if any((type(v) is not int or not 0 <= v <= 4294967295 for v in (fields.selector, fields.d6_value, fields.a1fbc_value, fields.value_38f, fields.unit_id))):
        raise ValueError('UnitDamageChanged requires raw DWORD values')
    if type(fields.owner) is not int or not 0 <= fields.owner <= 65535:
        raise ValueError('UnitDamageChanged owner must preserve its WORD bits')

def decode_fields(raw_fields, read):
    verify_source_evidence()
    if type(raw_fields) is not dict or set(raw_fields) != {SELECTOR_KEY, D6_KEY, A1FBC_KEY, VALUE_38F_KEY, DESCRIPTOR_KEY}:
        raise ValueError('UnitDamageChanged requires the exact five-field envelope')
    selector = decode_scalar(raw_fields[SELECTOR_KEY], 3)
    d6 = decode_scalar(raw_fields[D6_KEY], 2)
    second = decode_scalar(raw_fields[A1FBC_KEY], 2)
    third = decode_scalar(raw_fields[VALUE_38F_KEY], 2)
    raw = copy_eight_byte_variant(raw_fields[DESCRIPTOR_KEY], read, expected_tag=1024)
    owner, unused_input_type, identifier = struct.unpack('<HHI', raw)
    return EventFields(selector, d6, second, third, owner, identifier)

def encode_record(sequence, fields, *, normalizer_transform_present, per_thread_hook_present, writer_metadata_callback_present, padding_policy, entity_listener_count, empty_receiver_state):
    from civ6_host.runtime.native.native_deferred_empty_profile import validate_empty_profile_record
    verify_source_evidence()
    _validate_fields(fields)
    validate_sequence(sequence)
    if any((v is not False for v in (normalizer_transform_present, per_thread_hook_present, writer_metadata_callback_present))):
        raise ValueError('UnitDamageChanged optional services are not implemented')
    if type(entity_listener_count) is not int or entity_listener_count != 0:
        raise ValueError('UnitDamageChanged requires the empty entity listener profile')
    if padding_policy != PADDING_POLICY:
        raise ValueError('UnitDamageChanged stack-padding policy must be explicit')
    if type(empty_receiver_state) is not dict or set(empty_receiver_state) != {'observer_registered', 'state_pointer_nonnull', 'pre_hook', 'post_hook', 'subscriber_count', 'state_flags'}:
        raise ValueError('UnitDamageChanged requires the complete receiver state')
    record = bytearray(RECORD_SIZE)
    struct.pack_into('<IIII', record, 0, RECORD_SIZE, RECORD_TYPE, sequence, 0)
    validate_empty_profile_record(record, **empty_receiver_state)
    struct.pack_into('<IIHHI', record, 16, 4294967295, 4294967295, fields.owner, 1, fields.unit_id)
    for offset in (32, 40, 48, 56):
        struct.pack_into('<HHI', record, offset, 65535, 0, 4294967295)
    struct.pack_into('<I', record, 80, sequence)
    struct.pack_into('<HHIIII', record, 88, fields.owner, 1, fields.unit_id, fields.d6_value, fields.a1fbc_value, fields.value_38f)
    validate_empty_profile_record(record, **empty_receiver_state)
    return bytes(record)
