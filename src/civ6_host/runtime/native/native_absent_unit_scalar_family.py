"""Native normalization of a unit and scalar before a proven absent callback.

The borrowed unit descriptor must be read even though no callback is present.
This profile produces no queue record and asserts no gameplay success.
"""
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
from pathlib import Path
import struct
from civ6_host.runtime.native.native_application_mirror import decode_scalar
from civ6_host.runtime.native.native_host_event_registry import EXE_EVENT_CALLBACKS
from civ6_host.runtime.native.native_host_event_registry import EXE_EVENT_REGISTRAR_SHA256
from civ6_host.runtime.native.native_host_events import copy_eight_byte_variant
from civ6_host.runtime.native.native_source_cache import load_pinned_json
SELECTOR_KEY, DESCRIPTOR_KEY, VALUE_KEY = (2716180809, 4032072631, 3606901732)
FIELD_KEYS = frozenset((SELECTOR_KEY, DESCRIPTOR_KEY, VALUE_KEY))
REGISTRY_PROFILE = 'pinned-base-317-static-registrar-only'
PROOF_SHA256 = '852cb8573800681b10e5941d68a67615ac663c40ef1624306f9101febaf1b321'

def verify_source_evidence():
    if not PROOF_SHA256:
        raise RuntimeError('Absent unit scalar family source proof has not been pinned')
    path = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_absent_unit_scalar_family.py')))).resolve().parents[1] / 'evidence/native-absent-unit-scalar-family' / (PROOF_SHA256 + '.json')
    proof = load_pinned_json(path, PROOF_SHA256)
    registrar = proof['registrar']
    contract = proof['contract']
    if proof['schema'] != 'civ6rl.native_absent_unit_scalar_family.static.v1' or proof['images'] != {'exe_sha256': 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63', 'core_sha256': 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'} or registrar['body_sha256'] != EXE_EVENT_REGISTRAR_SHA256 or (registrar['candidate_absent'] is not True) or (tuple(registrar['registered_kinds']) != tuple(sorted(EXE_EVENT_CALLBACKS))) or (len(EXE_EVENT_CALLBACKS) != 317) or (contract['generic_absent_family_supported'] is not True) or (contract['generic_kind_domain'] != 'uint32-excluding-all-317-registered-kinds') or (contract['registry_profile'] != REGISTRY_PROFILE) or (set(contract['input_keys']) != FIELD_KEYS) or (contract['tags'] != {'A1E5A149': (3,), 'D6FCF3E4': (2, 4), 'F0548BB7': (1024,)}) or (contract['descriptor_envelope'] != {'size': 8, 'flags': 553648129, 'nonnull_pointer': True}) or (contract['scalar_flags'] != 0) or (contract['normalization']['D6_tag2_destination'] != 80) or (contract['normalization']['D6_tag4_destination'] != 92) or (contract['normalization']['unit_owner_destination'] != 8) or (contract['normalization']['unit_type_destination'] != 10) or (contract['normalization']['unit_id_destination'] != 12) or (contract['normalization']['unit_type'] != 1) or (contract['normalization']['descriptor_checked_copy_size'] != 8) or (contract['normalization']['raw_descriptor_type_ignored'] is not True) or (contract['entity_list_writes'] != 0) or (contract['queue_records_produced'] != 0) or (contract['callback_va'] is not None) or (contract['writer_va'] is not None) or (contract['gameplay_success_asserted'] is not False) or (proof['validation']['all_captured_instructions_match_pinned_pe'] is not True) or (proof['parents']['unit_normalization']['sha256'] != '8e221c6ff8a02f77293ef9ce8f62d38cc9b39a545bde8e1740199a630318dd3e') or (proof['parents']['closed_absent_kind_dataflow']['sha256'] != 'a7db45eefe186cfe146bc29d28504ee7b4359ec4e5e9013311a3eb78b3e26de6'):
        raise RuntimeError('Absent unit scalar family normalizer or closed registry changed')
    for name, digest in {'normalizer': 'c757d2f0c927f36e058ff5e57350a80beac1db2a89d3940fcb5e89c05545f23e', 'resolver': '5d0c3c7557f18ad896d84bb83b4c43b6fd47bbee1b25e73967ee78f1fe583d89'}.items():
        if proof['captures'][name]['code_sha256'] != digest:
            raise RuntimeError('Absent unit scalar family source body changed: ' + name)
    return proof

def validate_absent_event(kind, raw_fields, read, *, normalizer_transform_present, registry_profile, dynamic_registration_present, entity_listener_count):
    verify_source_evidence()
    if type(kind) is not int or not 0 <= kind <= 4294967295 or kind in EXE_EVENT_CALLBACKS:
        raise ValueError('Only uint32 kinds absent from the captured registry are admitted')
    if type(registry_profile) is not str or registry_profile != REGISTRY_PROFILE or dynamic_registration_present is not False:
        raise ValueError('Absent unit scalar family requires the explicit closed callback registry')
    if normalizer_transform_present is not False:
        raise ValueError('Absent unit scalar family requires an absent normalizer transform')
    if type(entity_listener_count) is not int or entity_listener_count != 0:
        raise ValueError('Absent unit scalar family requires actual empty entity listeners')
    if type(raw_fields) is not dict or set(raw_fields) != FIELD_KEYS or any((type(raw) is not bytes or len(raw) != 24 for raw in raw_fields.values())):
        raise ValueError('Absent unit scalar family requires exactly three complete typed fields')
    selector = decode_scalar(raw_fields[SELECTOR_KEY], 3)
    scalar_tag = struct.unpack_from('<H', raw_fields[VALUE_KEY])[0]
    if scalar_tag not in (2, 4):
        raise ValueError('Absent unit scalar family only covers DWORD and raw float32 paths')
    scalar_bits = decode_scalar(raw_fields[VALUE_KEY], scalar_tag)
    copied = copy_eight_byte_variant(raw_fields[DESCRIPTOR_KEY], read, expected_tag=1024)
    owner, _ignored_input_type, identifier = struct.unpack('<HHI', copied)
    normalized = struct.pack('<HHI', owner, 1, identifier)
    result = {'kind': kind, 'selector': selector, 'scalar_tag': scalar_tag, 'scalar_bits': scalar_bits, 'normalized_scalar_offset': 80 if scalar_tag == 2 else 92, 'normalized_descriptor_hex': normalized.hex(), 'descriptor_target_read': True, 'descriptor_normalized': True, 'callback_registered': False, 'callback_invoked': False, 'normalizer_result': 0, 'normalizer_transform_present': False, 'normalizer_fields_read': True, 'registry_profile': registry_profile, 'dynamic_registration_present': False, 'entity_listener_count': 0, 'entity_list_writes': 0, 'queue_records_produced': 0, 'gameplay_success_asserted': False, 'source_sha256': PROOF_SHA256}
    result['value' if scalar_tag == 2 else 'float32_bits'] = scalar_bits
    return result
