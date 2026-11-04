"""UnitAbilityLost: exact UnitAbilityGained packing with a separate receiver.

The copied stack gaps are not native zero values. They are zeroed only under
the explicit initialized-empty row42 profile, after the caller checks the real
receiver state. Core's prior native event processing is never replaced here.
"""
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
from pathlib import Path
import struct
from civ6_host.runtime.native import native_event_a96df790 as _analog
from civ6_host.runtime.native.native_source_cache import load_pinned_json
EVENT_KIND = 1920266315
CALLBACK_RVA = 1394640
QUEUE_WRITER_RVA = 1230080
RECORD_TYPE = 66
RECORD_SIZE = 112
SELECTOR_KEY, VALUE_KEY, UNIT_KEY = (_analog.SELECTOR_KEY, _analog.VALUE_KEY, _analog.UNIT_KEY)
EventFields = _analog.EventFields
EMPTY_RECEIVER_PROFILE = 'unit-ability-lost-row-42-empty'
PADDING_POLICY = 'zero-unread-empty-receiver-payload'
PINNED_EVIDENCE_SHA256 = '74d9cdba801d26cc52205181b5105ef51ea17136661d18539387c4fb0a4e2201'
_PROOF = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_event_7274f04b.py')))).resolve().parents[1] / 'evidence/native-event-7274f04b' / (PINNED_EVIDENCE_SHA256 + '.json')

def verify_source_evidence():
    proof = load_pinned_json(_PROOF, PINNED_EVIDENCE_SHA256)
    analog = proof.get('analog', {})
    receiver = proof.get('receiver', {})
    if proof.get('schema') != 'civ6rl.native_event_7274f04b.static.v1' or proof.get('exe_sha256') != 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63' or proof.get('core_sha256') != 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3' or (proof.get('registry', {}).get('registration', {}).get('callback_va') != '0x1401547d0') or (analog.get('sha256') != _analog.PINNED_EVIDENCE_SHA256) or (analog.get('callback_instruction_count') != 67) or (analog.get('writer_instruction_count') != 139) or tuple(analog.get('writer_differences_after_type_normalization', ())) or (receiver.get('record_type') != RECORD_TYPE) or (receiver.get('record_size') != RECORD_SIZE) or (receiver.get('event_name') != 'GameCoreEvent::UnitAbilityLost') or (receiver.get('row_va') != '0x1412c7510') or (receiver.get('handler_va') != '0x1400d7870'):
        raise RuntimeError('UnitAbilityLost source/packing/receiver identity changed')
    for name, digest in {'callback': '6d764688d36e5d820bc94ab0ca7c52d4bea00a334f43471570afda1fe2c2ea9d', 'writer': '978ff5cad3d094dfd9202ea50d086904ed0e59b404f216c025c96584d0439874', 'normalizer': 'c757d2f0c927f36e058ff5e57350a80beac1db2a89d3940fcb5e89c05545f23e', 'normalizer_dispatch': '5d0c3c7557f18ad896d84bb83b4c43b6fd47bbee1b25e73967ee78f1fe583d89', 'receiver_setup': '6ca13a00949731c32fa301c53569532ff75395dfcc4f5cc6618167a9e41bf165', 'handler': '77e6cb7e2d2aaccb29e20574903b77284440519c122752495071c9f226347baa'}.items():
        if proof.get('captures', {}).get(name, {}).get('code_sha256') != digest:
            raise RuntimeError('UnitAbilityLost complete source body changed: ' + name)
    return proof

def decode_fields(raw_fields, read):
    """Read the borrowed descriptor exactly once under the shared typed contract."""
    verify_source_evidence()
    return _analog.decode_fields(raw_fields, read)

def _validate_empty_receiver(state):
    expected = {'profile': EMPTY_RECEIVER_PROFILE, 'record_type': RECORD_TYPE, 'event_name': 'GameCoreEvent::UnitAbilityLost', 'pre_hook': None, 'post_hook': None, 'subscriber_count': 0, 'subscriber_list_empty': True, 'deferred_flag': 0}
    if type(state) is not dict or state != expected or any((type(state[key]) is not type(value) for key, value in expected.items())):
        raise ValueError('UnitAbilityLost requires the exact initialized-empty row42')

def encode_record(sequence, fields, *, normalizer_transform_present, per_thread_hook_present, writer_metadata_callback_present, empty_receiver_state, padding_policy):
    verify_source_evidence()
    _validate_empty_receiver(empty_receiver_state)
    if type(padding_policy) is not str or padding_policy != PADDING_POLICY:
        raise ValueError('UnitAbilityLost requires explicit unread payload padding policy')
    packer_state = dict(empty_receiver_state)
    packer_state.update(profile=_analog.EMPTY_RECEIVER_PROFILE, record_type=_analog.RECORD_TYPE, event_name='GameCoreEvent::UnitAbilityGained')
    record = bytearray(_analog.encode_record(sequence, fields, normalizer_transform_present=normalizer_transform_present, per_thread_hook_present=per_thread_hook_present, writer_metadata_callback_present=writer_metadata_callback_present, empty_receiver_state=packer_state, padding_policy=padding_policy))
    struct.pack_into('<I', record, 4, RECORD_TYPE)
    return bytes(record)
