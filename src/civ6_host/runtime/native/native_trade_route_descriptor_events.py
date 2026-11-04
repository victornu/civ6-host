"""Exact absent-registrar path for one native two-descriptor event kind.

Core's internal dispatch has already run. The adapter validates/copies the
borrowed descriptor pair and returns the source-proven absent-callback value 0;
it does not enqueue a D7 record or claim a trade-route gameplay effect.
"""
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
from pathlib import Path
from civ6_host.runtime.native.native_host_event_registry import EXE_EVENT_CALLBACKS
from civ6_host.runtime.native.native_host_event_registry import EXE_EVENT_REGISTRAR_SHA256
from civ6_host.runtime.native.native_source_cache import load_pinned_json
EVENT_KIND = 350149210
FIRST_KEY, SECOND_KEY, SELECTOR_KEY = (594779970, 1416933332, 2716180809)
FIELD_KEYS = frozenset((FIRST_KEY, SECOND_KEY, SELECTOR_KEY))
REGISTRY_PROFILE = 'pinned-base-317-static-registrar-only'
PROOF_SHA256 = 'a1885e77d95f1eec856a72e1eb32696afb0a68b12545123c88d34fba76395d3e'
_ROOT = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_trade_route_descriptor_events.py')))).resolve().parents[1]
_PROOF = _ROOT / 'evidence/native-trade-route-descriptor-events' / (PROOF_SHA256 + '.json')

def verify_source_evidence():
    proof = load_pinned_json(_PROOF, PROOF_SHA256)
    registry = proof.get('registry', {})
    if proof.get('schema') != 'civ6rl.native_trade_route_descriptor_events.absent.v1' or proof.get('native_execution') is not False or proof.get('images') != {'exe_sha256': 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63', 'core_sha256': 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'} or (proof.get('kind') != EVENT_KIND) or (registry.get('sha256') != 'ec49b8df386e35cafc401986fb1512a89e19ebe7d94f8963684ac67505a1b0f5') or (registry.get('registration_function_sha256') != EXE_EVENT_REGISTRAR_SHA256) or (registry.get('registered_count') != 317) or (registry.get('candidate_absent') is not True) or (EVENT_KIND in EXE_EVENT_CALLBACKS) or (proof.get('host_a0') != {'vtable_va': '0x140fc79d0', 'target_va': '0x1401ca2d0'}) or (proof.get('contract', {}).get('record') is not None) or (proof.get('contract', {}).get('registry_profile') != REGISTRY_PROFILE) or (proof.get('contract', {}).get('normalizer_result') != 0):
        raise RuntimeError('Absent descriptor event source contract changed')
    captures = proof.get('captures', {})
    if captures.get('host_normalizer', {}).get('code_sha256') != 'c757d2f0c927f36e058ff5e57350a80beac1db2a89d3940fcb5e89c05545f23e' or captures.get('host_absent_resolver', {}).get('code_sha256') != '5d0c3c7557f18ad896d84bb83b4c43b6fd47bbee1b25e73967ee78f1fe583d89' or captures.get('core_descriptor_builder', {}).get('code_sha256') != '9318d8219200e4595fc0f76ee9e0a839863ad72f5fbe404b86e60608c4c6e41d' or (captures.get('core_dispatcher', {}).get('code_sha256') != '05947d1784ce1a8897426bb3cf0d06fc66328465d99333496548df703f381c8a'):
        raise RuntimeError('Absent descriptor event code identity changed')
    return proof

def validate_absent_event(kind, raw_fields, read, *, normalizer_transform_present, registry_profile, dynamic_registration_present, entity_listener_count):
    """Validate only the witnessed absent-kind envelope and return native zero."""
    verify_source_evidence()
    if type(kind) is not int or kind != EVENT_KIND or kind in EXE_EVENT_CALLBACKS:
        raise ValueError('Only the exact source-backed absent event kind is admitted')
    if type(registry_profile) is not str or registry_profile != REGISTRY_PROFILE or dynamic_registration_present is not False:
        raise ValueError('Descriptor event requires the closed static callback registry')
    if normalizer_transform_present is not False:
        raise ValueError('Descriptor event requires the explicit absent transform profile')
    if type(entity_listener_count) is not int or entity_listener_count != 0:
        raise ValueError('Descriptor event requires zero entity listeners')
    if type(raw_fields) is not dict or set(raw_fields) != FIELD_KEYS:
        raise ValueError('Descriptor event has an unrecognized field set')
    from civ6_host.runtime.native.native_event_5d706996 import decode_fields
    fields = decode_fields(raw_fields, read)
    return {'kind': kind, 'selector': fields.selector, 'first_descriptor': {'owner': fields.first_owner, 'input_variant_tag': 1024, 'normalized_type': 2, 'identifier': fields.first_id}, 'second_descriptor': {'owner': fields.second_owner, 'input_variant_tag': 1024, 'normalized_type': 2, 'identifier': fields.second_id}, 'callback_registered': False, 'callback_invoked': False, 'normalizer_transform_present': False, 'registry_profile': registry_profile, 'dynamic_registration_present': False, 'entity_listener_count': 0, 'native_dispatch_return': 0, 'queue_records_produced': 0, 'gameplay_success_asserted': False, 'source_sha256': PROOF_SHA256}
