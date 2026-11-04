"""Source-bounded unit descriptor normalization before an absent EXE callback.

Core has already performed its internal dispatch. This adapter copies borrowed
input, checks the closed host profile and follows the original absent lookup.
"""
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
from pathlib import Path
import struct
from civ6_host.runtime.native.native_application_mirror import decode_scalar
from civ6_host.runtime.native.native_host_event_registry import EXE_EVENT_CALLBACKS
from civ6_host.runtime.native.native_host_event_registry import EXE_EVENT_REGISTRAR_SHA256
from civ6_host.runtime.native.native_source_cache import load_pinned_json
EVENT_KIND = 3607864607
SELECTOR_KEY, DESCRIPTOR_KEY = (2716180809, 4032072631)
FIELD_KEYS = frozenset((SELECTOR_KEY, DESCRIPTOR_KEY))
REGISTRY_PROFILE = 'pinned-base-317-static-registrar-only'
PINNED_EVIDENCE_SHA256 = '8e221c6ff8a02f77293ef9ce8f62d38cc9b39a545bde8e1740199a630318dd3e'
_PROOF = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_absent_d70ba51f.py')))).resolve().parents[1] / 'evidence/native-absent-d70ba51f' / (PINNED_EVIDENCE_SHA256 + '.json')

def verify_source_evidence():
    proof = load_pinned_json(_PROOF, PINNED_EVIDENCE_SHA256)
    registrar = proof.get('registrar', {})
    if proof.get('schema') != 'civ6rl.native_absent_d70ba51f.static.v1' or proof.get('kind') != EVENT_KIND or proof.get('images', {}).get('exe_sha256') != 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63' or (proof.get('images', {}).get('core_sha256') != 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3') or (proof.get('host_a0_slot', {}).get('target') != '0x1401ca2d0') or (registrar.get('body_sha256') != EXE_EVENT_REGISTRAR_SHA256) or (registrar.get('candidate_absent') is not True) or (tuple(registrar.get('registered_kinds', ())) != tuple(sorted(EXE_EVENT_CALLBACKS))) or (EVENT_KIND in EXE_EVENT_CALLBACKS) or (proof.get('contract', {}).get('registry_profile') != REGISTRY_PROFILE):
        raise RuntimeError('D70BA51F normalizer or closed callback registry changed')
    for name, digest in {'normalizer': 'c757d2f0c927f36e058ff5e57350a80beac1db2a89d3940fcb5e89c05545f23e', 'resolver': '5d0c3c7557f18ad896d84bb83b4c43b6fd47bbee1b25e73967ee78f1fe583d89'}.items():
        if proof.get('captures', {}).get(name, {}).get('code_sha256') != digest:
            raise RuntimeError('D70BA51F source body changed: ' + name)
    return proof

def _validate_profile_event(kind, raw_fields, read, *, normalizer_transform_present, registry_profile, dynamic_registration_present, entity_listener_count):
    """Normalize the two witnessed fields without replaying Core work.

    A missing callback alone does not exclude entity lists or dynamic entries.
    The host must attest its actual closed registry and empty listener profile.
    RDI may still identify an empty list container; zero active lists means
    1CB0E0 cannot collect the descriptor into any listener's list. The legacy
    normalizer_transform_present flag remains a conservative profile guard,
    not an assertion about the original RDI pointer.
    """
    verify_source_evidence()
    if type(kind) is not int or not 0 <= kind <= 4294967295 or kind in EXE_EVENT_CALLBACKS:
        raise ValueError('Only uint32 kinds absent from the captured registry are admitted')
    if type(registry_profile) is not str or registry_profile != REGISTRY_PROFILE or dynamic_registration_present is not False:
        raise ValueError('D70BA51F requires the explicit closed callback registry')
    if normalizer_transform_present is not False:
        raise ValueError('D70BA51F requires an explicitly absent normalizer transform')
    if type(entity_listener_count) is not int or entity_listener_count != 0:
        raise ValueError('D70BA51F requires the host empty entity-listener profile')
    if type(raw_fields) is not dict or set(raw_fields) != FIELD_KEYS or any((type(raw) is not bytes or len(raw) != 24 for raw in raw_fields.values())):
        raise ValueError('D70BA51F requires exactly two complete typed fields')
    selector = decode_scalar(raw_fields[SELECTOR_KEY], 3)
    if selector != 0:
        raise ValueError('D70BA51F producer supplies selector zero')
    variant = raw_fields[DESCRIPTOR_KEY]
    pointer, size, flags = struct.unpack_from('<QII', variant, 8)
    if struct.unpack_from('<H', variant)[0] != 1024 or not pointer or size != 8 or (flags != 553648129):
        raise ValueError('D70BA51F descriptor envelope is outside the source profile')
    copied = read(pointer, 8)
    if not isinstance(copied, (bytes, bytearray, memoryview)) or len(copied) != 8:
        raise ValueError('D70BA51F descriptor copy is incomplete')
    owner, _input_type_ignored, identifier = struct.unpack('<HHI', copied)
    normalized = struct.pack('<HHI', owner, 1, identifier)
    return {'kind': kind, 'selector': selector, 'normalized_descriptor_hex': normalized.hex(), 'callback_registered': False, 'callback_invoked': False, 'normalizer_result': 0, 'normalizer_transform_present': False, 'normalizer_fields_read': True, 'registry_profile': registry_profile, 'dynamic_registration_present': False, 'entity_listener_count': 0, 'entity_list_writes': 0, 'queue_records_produced': 0, 'gameplay_success_asserted': False, 'source_sha256': PINNED_EVIDENCE_SHA256}

def validate_absent_event(kind, raw_fields, read, *, normalizer_transform_present, registry_profile, dynamic_registration_present, entity_listener_count):
    """Normalize the two witnessed fields without replaying Core work.

    A missing callback alone does not exclude entity lists or dynamic entries.
    The host must attest its actual closed registry and empty listener profile.
    RDI may still identify an empty list container; zero active lists means
    1CB0E0 cannot collect the descriptor into any listener's list. The legacy
    normalizer_transform_present flag remains a conservative profile guard,
    not an assertion about the original RDI pointer.
    """
    verify_source_evidence()
    if type(kind) is not int or kind != EVENT_KIND or kind in EXE_EVENT_CALLBACKS:
        raise ValueError('Only the source-backed absent D70BA51F kind is admitted')
    return _validate_profile_event(kind, raw_fields, read, normalizer_transform_present=normalizer_transform_present, registry_profile=registry_profile, dynamic_registration_present=dynamic_registration_present, entity_listener_count=entity_listener_count)
