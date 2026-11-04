"""The source-bounded absent 67001FE1 callback after five-field normalization."""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
from pathlib import Path
import struct
from civ6_host.runtime.native.native_application_mirror import decode_scalar
from civ6_host.runtime.native.native_feature_visibility_event import _copy_blob
from civ6_host.runtime.native.native_host_event_registry import EXE_EVENT_CALLBACKS
from civ6_host.runtime.native.native_host_event_registry import EXE_EVENT_REGISTRAR_SHA256
from civ6_host.runtime.native.native_source_cache import load_pinned_json
EVENT_KIND = 1728061409
SELECTOR_KEY, VALUE_KEY, SECOND_VALUE_KEY = (2716180809, 3606901732, 2717631346)
DESCRIPTOR_KEY, POSITION_KEY = (594779970, 2353434172)
FIELD_KEYS = frozenset((SELECTOR_KEY, VALUE_KEY, SECOND_VALUE_KEY, DESCRIPTOR_KEY, POSITION_KEY))
PINNED_EVIDENCE_SHA256 = '4ea398e552d1e78b17cf6835a7774f82cd00da6416a74f6e9b98001c26fbef26'
_PROOF = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_absent_city_position_event.py')))).resolve().parents[1] / 'evidence/native-absent-city-position-event' / f'{PINNED_EVIDENCE_SHA256}.json'

def verify_source_evidence():
    proof = load_pinned_json(_PROOF, PINNED_EVIDENCE_SHA256)
    if proof.get('schema') != 'civ6rl.native_absent_city_position_event.static.v1' or proof['kind'] != hex(EVENT_KIND) or proof['images']['exe_sha256'] != 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63' or (proof['images']['core_sha256'] != 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3') or (proof['registrar']['candidate_absent'] is not True) or (proof['registrar']['body_sha256'] != EXE_EVENT_REGISTRAR_SHA256) or (tuple(proof['registrar']['registered_kinds']) != tuple(sorted(EXE_EVENT_CALLBACKS))) or (EVENT_KIND in EXE_EVENT_CALLBACKS):
        raise RuntimeError('Absent city/position source or complete callback registry changed')

def validate_absent_city_position_event(kind, raw_fields, read, *, normalizer_transform_present):
    """Copy both borrowed blobs and validate the explicitly absent transform.

    The result reports the EXE normalizer/resolver outcome and copied fields,
    not the success of the Core action that generated this notification.
    Neither input WORD2 nor the source pointer addresses select a callback.
    """
    verify_source_evidence()
    if type(kind) is not int or kind != EVENT_KIND:
        raise ValueError('Only the source-backed absent 67001FE1 event is admitted')
    if normalizer_transform_present is not False:
        raise ValueError('Absent city/position event requires explicitly absent normalizer transform')
    if not isinstance(raw_fields, dict) or set(raw_fields) != FIELD_KEYS:
        raise ValueError('Absent city/position event requires exactly five source-backed keys')
    for raw in raw_fields.values():
        if not isinstance(raw, (bytes, bytearray, memoryview)) or len(raw) != 24:
            raise ValueError('Absent city/position event requires complete variants')
    selector = decode_scalar(raw_fields[SELECTOR_KEY], 3)
    if selector != 0:
        raise ValueError('Absent city/position event requires selector zero')
    value = decode_scalar(raw_fields[VALUE_KEY], 2)
    second = decode_scalar(raw_fields[SECOND_VALUE_KEY], 2)
    for key, expected_tag in ((DESCRIPTOR_KEY, 1024), (POSITION_KEY, 0)):
        raw = raw_fields[key]
        pointer, size, flags = struct.unpack_from('<QII', raw, 8)
        if struct.unpack_from('<H', raw)[0] != expected_tag or not pointer or size != 8 or (flags != 553648129):
            raise ValueError('Absent city/position event has an unverified blob envelope')
    descriptor = _copy_blob(raw_fields[DESCRIPTOR_KEY], read, 1024)
    position = _copy_blob(raw_fields[POSITION_KEY], read, 0)
    owner, _, identifier = struct.unpack('<HHI', descriptor)
    normalized = struct.pack('<HHI', owner, 2, identifier)
    return {'kind': kind, 'callback_registered': False, 'callback_invoked': False, 'normalizer_result': 0, 'normalizer_transform_present': False, 'normalized_descriptor_hex': normalized.hex(), 'position_hex': position.hex(), 'selector': selector, 'value': value, 'second_value': second, 'proof': 'native-absent-city-position-event', 'source_sha256': PINNED_EVIDENCE_SHA256}
