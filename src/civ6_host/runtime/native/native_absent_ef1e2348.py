"""EF1E2348 EXE normalization with no registered EXE callback.

The native producer has already dispatched Core-internal listeners before
entering host+A0. This helper neither calls nor substitutes that dispatch.
"""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
from pathlib import Path
import struct
from civ6_host.runtime.native.native_application_mirror import decode_scalar
from civ6_host.runtime.native.native_host_event_registry import EXE_EVENT_CALLBACKS
from civ6_host.runtime.native.native_host_event_registry import EXE_EVENT_REGISTRAR_SHA256
from civ6_host.runtime.native.native_source_cache import load_pinned_json
EVENT_KIND = 4011729736
SELECTOR_KEY, VALUE_KEY, DESCRIPTOR_KEY = (2716180809, 3606901732, 594779970)
FIELD_KEYS = frozenset((SELECTOR_KEY, VALUE_KEY, DESCRIPTOR_KEY))
PINNED_EVIDENCE_SHA256 = 'd00cbd792b2285b6185aeb8606c6fd991885344a810e871592faabee3b3874ba'
_PROOF = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_absent_ef1e2348.py')))).resolve().parents[1] / 'evidence/native-absent-ef1e2348' / f'{PINNED_EVIDENCE_SHA256}.json'

def verify_source_evidence():
    proof = load_pinned_json(_PROOF, PINNED_EVIDENCE_SHA256)
    if proof['schema'] != 'civ6rl.native_absent_ef1e2348.static.v1' or proof['kind'] != hex(EVENT_KIND) or proof['images']['exe_sha256'] != 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63' or (proof['images']['core_sha256'] != 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3') or (proof['registrar']['candidate_absent'] is not True) or (proof['registrar']['body_sha256'] != EXE_EVENT_REGISTRAR_SHA256) or (tuple(proof['registrar']['registered_kinds']) != tuple(sorted(EXE_EVENT_CALLBACKS))) or (EVENT_KIND in EXE_EVENT_CALLBACKS) or (proof['captures']['normalizer']['code_sha256'] != 'c757d2f0c927f36e058ff5e57350a80beac1db2a89d3940fcb5e89c05545f23e') or (proof['captures']['resolver']['code_sha256'] != '5d0c3c7557f18ad896d84bb83b4c43b6fd47bbee1b25e73967ee78f1fe583d89') or (proof['captures']['core_producer']['code_sha256'] != '380fe3a4191a55d5d791861e3165b8e08172e7b78e680a199051f37bb8ff1ed1') or (proof['captures']['core_internal_dispatch']['code_sha256'] != 'e0d18d16db0419608fe2fe96d5f08f1170c60bbd09c6df32bb02ae7edad057e4'):
        raise RuntimeError('EF1E2348 absent-callback source or complete registry changed')
    return proof

def validate_absent_event(kind, raw_fields, read, *, normalizer_transform_present):
    """Validate this EXE-side no-callback path, without a gameplay result.

    Only typed scalar values and the owned copy of the borrowed city descriptor
    are reported. All native producer work and its internal dispatch remain the
    caller's existing execution; no operation or native query is replayed here.
    """
    verify_source_evidence()
    if type(kind) is not int or kind != EVENT_KIND:
        raise ValueError('Only the pinned absent EF1E2348 callback is admitted')
    if normalizer_transform_present is not False:
        raise ValueError('EF1E2348 requires an explicitly absent normalizer transform')
    if not isinstance(raw_fields, dict) or set(raw_fields) != FIELD_KEYS:
        raise ValueError('EF1E2348 requires exactly three source-backed keys')
    if any((type(raw) is not bytes or len(raw) != 24 for raw in raw_fields.values())):
        raise ValueError('EF1E2348 requires complete byte variants')
    selector = decode_scalar(raw_fields[SELECTOR_KEY], 3)
    value = decode_scalar(raw_fields[VALUE_KEY], 2)
    if selector != 0:
        raise ValueError('EF1E2348 captured producer requires selector zero')
    descriptor_variant = raw_fields[DESCRIPTOR_KEY]
    pointer, size, flags = struct.unpack_from('<QII', descriptor_variant, 8)
    if struct.unpack_from('<H', descriptor_variant)[0] != 1024 or pointer == 0 or size != 8 or (flags != 553648129):
        raise ValueError('EF1E2348 city descriptor envelope is unverified')
    descriptor = read(pointer, 8)
    if not isinstance(descriptor, (bytes, bytearray, memoryview)) or len(descriptor) != 8:
        raise ValueError('EF1E2348 city descriptor copy is incomplete')
    owner, _, identifier = struct.unpack('<HHI', descriptor)
    normalized = struct.pack('<HHI', owner, 2, identifier)
    return {'kind': kind, 'callback_registered': False, 'callback_invoked': False, 'normalizer_result': 0, 'normalizer_transform_present': False, 'normalized_descriptor_hex': normalized.hex(), 'selector': selector, 'value': value, 'queue_records_produced': 0, 'gameplay_success_asserted': False, 'proof': 'native-absent-ef1e2348', 'source_sha256': PINNED_EVIDENCE_SHA256}
