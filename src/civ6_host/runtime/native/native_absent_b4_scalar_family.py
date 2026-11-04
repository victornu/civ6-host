"""Source-proved absent callbacks with one ignored B4 field and two scalars.

Only the closed captured EXE registry is represented. The native Core has
already applied its own effects before calling the host. No native pointer is
followed here: the normalizer skips B4 and the absent resolver returns zero.
"""
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
from pathlib import Path
import struct
from civ6_host.runtime.native.native_application_mirror import decode_scalar
from civ6_host.runtime.native.native_host_event_registry import EXE_EVENT_CALLBACKS
from civ6_host.runtime.native.native_host_event_registry import EXE_EVENT_REGISTRAR_SHA256
from civ6_host.runtime.native.native_source_cache import load_pinned_json
SELECTOR_KEY, DESCRIPTOR_KEY, VALUE_KEY = (2716180809, 3036238893, 3606901732)
FIELD_KEYS = frozenset((SELECTOR_KEY, DESCRIPTOR_KEY, VALUE_KEY))
REGISTRY_PROFILE = 'pinned-base-317-static-registrar-only'
PROOF_SHA256 = 'a7db45eefe186cfe146bc29d28504ee7b4359ec4e5e9013311a3eb78b3e26de6'

def verify_source_evidence():
    if not PROOF_SHA256:
        raise RuntimeError('Absent B4 scalar family source proof has not been pinned')
    path = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_absent_b4_scalar_family.py')))).resolve().parents[1] / 'evidence/native-event-3d75b3ed' / (PROOF_SHA256 + '.json')
    proof = load_pinned_json(path, PROOF_SHA256)
    registrar = proof.get('registrar', {})
    if proof.get('schema') != 'civ6rl.native_event_3d75b3ed.static.v1' or proof.get('kind') != 1031123949 or proof.get('images') != {'exe_sha256': 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63', 'core_sha256': 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'} or (registrar.get('body_sha256') != EXE_EVENT_REGISTRAR_SHA256) or (registrar.get('candidate_absent') is not True) or (tuple(registrar.get('registered_kinds', ())) != tuple(sorted(EXE_EVENT_CALLBACKS))) or (len(EXE_EVENT_CALLBACKS) != 317) or (1031123949 in EXE_EVENT_CALLBACKS) or (proof['contract'].get('generic_absent_family_supported') is not True) or (proof['contract'].get('generic_kind_domain') != 'uint32-excluding-all-317-registered-kinds') or (set(proof['contract']['input_keys']) != FIELD_KEYS) or (proof['contract']['normalization']['D6_tag2_destination'] != 80) or (proof['contract']['normalization']['D6_tag4_destination'] != 92) or (proof['contract']['normalization']['ignored_key_payload_reads'] != 0) or (proof['contract']['normalization']['ignored_key_pointer_reads'] != 0) or (proof['contract']['normalization']['entity_list_calls_for_exact_shape'] != 0) or (proof['contract']['queue_records_produced'] != 0) or (proof['contract']['registry_profile'] != REGISTRY_PROFILE) or (proof['contract']['tags'] != {'A1E5A149': (3,), 'B4F9542D': (1024,), 'D6FCF3E4': (2, 4)}) or (proof['contract']['ignored_descriptor_envelope'] != {'size': 8, 'flags': 553648129}) or (proof['contract']['scalar_flags'] != 0) or (proof['validation']['all_captured_instructions_match_pinned_pe'] is not True) or (proof['parents']['integer_b4_absence']['sha256'] != 'b2e709e9d5de7e02c0a5792dfad8740da0fc6325ae972f448c535e0642d948a1'):
        raise RuntimeError('Absent B4 scalar family normalizer or closed registry changed')
    for name, digest in {'normalizer': 'c757d2f0c927f36e058ff5e57350a80beac1db2a89d3940fcb5e89c05545f23e', 'resolver': '5d0c3c7557f18ad896d84bb83b4c43b6fd47bbee1b25e73967ee78f1fe583d89'}.items():
        if proof['captures'][name]['code_sha256'] != digest:
            raise RuntimeError('Absent B4 scalar family source body changed: ' + name)
    return proof

def validate_absent_event(kind, raw_fields, *, normalizer_transform_present, registry_profile, dynamic_registration_present, entity_listener_count):
    verify_source_evidence()
    if type(kind) is not int or not 0 <= kind <= 4294967295 or kind in EXE_EVENT_CALLBACKS:
        raise ValueError('Only uint32 kinds absent from the captured registry are admitted')
    if type(registry_profile) is not str or registry_profile != REGISTRY_PROFILE or dynamic_registration_present is not False:
        raise ValueError('Absent B4 scalar family requires the explicit closed callback registry')
    if normalizer_transform_present is not False:
        raise ValueError('Absent B4 scalar family requires an absent normalizer transform')
    if type(entity_listener_count) is not int or entity_listener_count != 0:
        raise ValueError('Absent B4 scalar family requires actual empty entity listeners')
    if type(raw_fields) is not dict or set(raw_fields) != FIELD_KEYS or any((type(raw) is not bytes or len(raw) != 24 for raw in raw_fields.values())):
        raise ValueError('Absent B4 scalar family requires exactly three complete typed fields')
    selector = decode_scalar(raw_fields[SELECTOR_KEY], 3)
    scalar_tag = struct.unpack_from('<H', raw_fields[VALUE_KEY])[0]
    if scalar_tag not in (2, 4):
        raise ValueError('Absent B4 scalar family only covers the DWORD and raw float32 paths')
    scalar_bits = decode_scalar(raw_fields[VALUE_KEY], scalar_tag)
    variant = raw_fields[DESCRIPTOR_KEY]
    if struct.unpack_from('<H', variant)[0] != 1024 or struct.unpack_from('<II', variant, 16) != (8, 553648129):
        raise ValueError('Ignored B4 envelope is outside the source-backed profile')
    result = {'kind': kind, 'selector': selector, 'scalar_tag': scalar_tag, 'scalar_bits': scalar_bits, 'normalized_scalar_offset': 80 if scalar_tag == 2 else 92, 'ignored_field_key': DESCRIPTOR_KEY, 'descriptor_target_read': False, 'descriptor_normalized': False, 'callback_registered': False, 'callback_invoked': False, 'normalizer_result': 0, 'normalizer_transform_present': False, 'registry_profile': registry_profile, 'dynamic_registration_present': False, 'entity_listener_count': 0, 'entity_list_writes': 0, 'queue_records_produced': 0, 'gameplay_success_asserted': False, 'source_sha256': PROOF_SHA256}
    result['value' if scalar_tag == 2 else 'float32_bits'] = scalar_bits
    return result
