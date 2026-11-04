"""UnitGreatPersonActivated descriptor/two-DWORD record for an empty receiver.

The callback leaves payload+4..7 unwritten. These bytes are deliberately zeroed
only after explicit validation of the real empty row4D; they are not native
defaults. Core performs the activation and its subsequent work independently.
"""
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
from pathlib import Path
import struct
from civ6_host.runtime.native import native_event_a60328c5 as _analog
from civ6_host.runtime.native.native_application_mirror import decode_scalar
from civ6_host.runtime.native.native_host_events import copy_eight_byte_variant
from civ6_host.runtime.native.native_source_cache import load_pinned_json
EVENT_KIND = 58288157
CALLBACK_RVA = 1403344
QUEUE_WRITER_RVA = 1235680
RECORD_TYPE = 77
RECORD_SIZE = 112
SELECTOR_KEY, VALUE_KEY, SECOND_KEY, UNIT_KEY = (_analog.SELECTOR_KEY, _analog.VALUE_KEY, _analog.SECOND_KEY, _analog.UNIT_KEY)
EventFields = _analog.EventFields
EMPTY_RECEIVER_PROFILE = 'unit-great-person-activated-row-4d-empty'
PADDING_POLICY = 'zero-unread-empty-receiver-payload'
PINNED_EVIDENCE_SHA256 = 'f7b80900eb24e153c142adcf3bdd9d21b443ad38dfbfa93a3ea323ab9784f355'
_PROOF = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_event_0379681d.py')))).resolve().parents[1] / 'evidence/native-event-0379681d' / (PINNED_EVIDENCE_SHA256 + '.json')

def verify_source_evidence():
    proof = load_pinned_json(_PROOF, PINNED_EVIDENCE_SHA256)
    analog, receiver = (proof.get('analog', {}), proof.get('receiver', {}))
    if proof.get('schema') != 'civ6rl.native_event_0379681d.static.v1' or proof.get('exe_sha256') != 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63' or proof.get('core_sha256') != 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3' or (proof.get('registry', {}).get('registration', {}).get('callback_va') != '0x1401569d0') or (proof.get('targets', {}).get('writer') != '0x14012dae0') or (analog.get('sha256') != _analog.PINNED_EVIDENCE_SHA256) or (analog.get('callback_instruction_count') != 69) or (analog.get('writer_instruction_count') != 139) or tuple(analog.get('writer_differences_after_type_normalization', ())) or (receiver.get('record_type') != RECORD_TYPE) or (receiver.get('record_size') != RECORD_SIZE) or (receiver.get('event_name') != 'GameCoreEvent::UnitGreatPersonActivated') or (receiver.get('row_va') != '0x1412c7720') or (receiver.get('handler_va') != '0x1400d7c90'):
        raise RuntimeError('UnitGreatPersonActivated source identity changed')
    for name, expected in {'callback': 'b41c0fc0a422d7e1efe5db1576adb40ae3e72b0d22639a3786ad9ea6919cb8ca', 'writer': '17dd8bf86c97cb8d65dad869094255590ee0f77f2ba8c37c6eb31c6792d4c6c2', 'normalizer': 'c757d2f0c927f36e058ff5e57350a80beac1db2a89d3940fcb5e89c05545f23e', 'normalizer_dispatch': '5d0c3c7557f18ad896d84bb83b4c43b6fd47bbee1b25e73967ee78f1fe583d89', 'receiver_setup': '00dcbbed132f0e0f3ef496c3717a54682edfd9a6616b591a88ada64aa1402f68', 'handler': 'e05abf5c6f51c7ee56ef0d90e97e6b851e49f63c5c61e174248458455bd6ea0b', 'subscriber_dispatch': '326ad0582020365181be9ed3b3e0f595e1bf834ef24f5afdf167d9ae56292bca'}.items():
        if proof.get('captures', {}).get(name, {}).get('code_sha256') != expected:
            raise RuntimeError('UnitGreatPersonActivated body changed: ' + name)
    return proof

def decode_fields(raw_fields, read):
    """Copy the exact envelope once while its native descriptor is borrowed."""
    verify_source_evidence()
    if type(raw_fields) is not dict or set(raw_fields) != {SELECTOR_KEY, VALUE_KEY, SECOND_KEY, UNIT_KEY} or any((type(cell) is not bytes or len(cell) != 24 for cell in raw_fields.values())):
        raise ValueError('Unverified UnitGreatPersonActivated envelope')
    selector = decode_scalar(raw_fields[SELECTOR_KEY], 3)
    value = decode_scalar(raw_fields[VALUE_KEY], 2)
    second = decode_scalar(raw_fields[SECOND_KEY], 2)
    blob = copy_eight_byte_variant(raw_fields[UNIT_KEY], read, expected_tag=1024)
    owner, _ignored_input_type, unit_id = struct.unpack('<HHI', blob)
    return EventFields(selector, value, second, owner, unit_id)

def _validate_empty_receiver(state):
    expected = {'profile': EMPTY_RECEIVER_PROFILE, 'record_type': RECORD_TYPE, 'event_name': 'GameCoreEvent::UnitGreatPersonActivated', 'pre_hook': None, 'post_hook': None, 'subscriber_count': 0, 'subscriber_list_empty': True, 'deferred_flag': 0}
    if type(state) is not dict or state != expected or any((type(state[key]) is not type(value) for key, value in expected.items())):
        raise ValueError('UnitGreatPersonActivated requires the exact empty row4D')

def encode_record(sequence, fields, *, normalizer_transform_present, per_thread_hook_present, writer_metadata_callback_present, empty_receiver_state, padding_policy):
    """Encode after caller checks real row/capacity/sequence before decoding."""
    verify_source_evidence()
    _validate_empty_receiver(empty_receiver_state)
    if type(padding_policy) is not str or padding_policy != PADDING_POLICY:
        raise ValueError('UnitGreatPersonActivated requires explicit unread padding policy')
    record = bytearray(_analog.encode_record(sequence, fields, normalizer_transform_present=normalizer_transform_present, per_thread_hook_present=per_thread_hook_present, writer_metadata_callback_present=writer_metadata_callback_present, padding_policy='headless-zero-uninitialized-stack'))
    struct.pack_into('<I', record, 4, RECORD_TYPE)
    return bytes(record)
