"""Source-pinned validator for closed nonzero-N event profiles.

This is an admission predicate for scope selection only. It does not encode or
patch record flags, submit events, or prove native N>0 execution. 30AE is
intentionally outside this API because its virtual query callees remain
unresolved in the source audit.
"""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import struct
from pathlib import Path
from typing import Any
from civ6_host.runtime.native.native_source_cache import load_pinned_json
from civ6_host.runtime.native.native_deferred_empty_profile import validate_empty_profile_record
PROOF_SHA256 = 'e88a057044382373efd46d554be1895196b062b8b50fa1802a3d7376d3e9528c'
PROOF_PATH = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_counter_neutral_scope.py')))).resolve().parents[1] / 'evidence' / 'native-nonzero-scope-b1-30ae' / f'{PROOF_SHA256}.json'
EXE_SHA256 = 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63'
REGISTRY_SHA256 = 'ec49b8df386e35cafc401986fb1512a89e19ebe7d94f8963684ac67505a1b0f5'
B1_FAMILY_SHA256 = '91d30e5e40b7a256eb979d9d832e9c83480bfd4b63a7f1fe5c4fd43a6dfa8b6a'
B1_RECEIVER_SHA256 = 'fbafe7f5ea650a3f63c10fe2524cacd5a052fc96628414b054f54011f8b6d20b'
METADATA_SCOPE_SHA256 = '3c94b6ebd43d394b5bfa86b8df491814d9ea7b76700c61e7d2284cd78ce08611'
RECORD_TYPE_BY_KIND = {2980214136: 146, 4152393721: 117, 330185301: 149, 643323895: 141, 3629625883: 147}
_KIND_NAMES = {2980214136: 'ImprovementRemovedFromMap', 4152393721: 'FeatureChanged', 330185301: 'TerrainTypeChanged', 643323895: 'ResourceRemovedFromMap', 3629625883: 'ImprovementActivated'}
_CLOSED_SCOPE_PROOFS = {643323895: ('evidence/native-nonzero-scope-closure/265857f7/8c4a7c05a8c7926d9e664b32f73fdfa624ac16e04d72865dc493f2a7422d069f.json', '8c4a7c05a8c7926d9e664b32f73fdfa624ac16e04d72865dc493f2a7422d069f', 96), 3629625883: ('evidence/native-nonzero-scope-closure/d857b21b/c87c733d8e3481c7e65db3ad04e838c998ebc083a2fc19785f944a2d2acfcaf2.json', 'c87c733d8e3481c7e65db3ad04e838c998ebc083a2fc19785f944a2d2acfcaf2', 128)}
_EMPTY_STATE_KEYS = frozenset({'observer_registered', 'state_pointer_nonnull', 'pre_hook', 'post_hook', 'subscriber_count', 'state_flags'})

def verify_source() -> dict[str, Any]:
    """Validate the immutable evidence and all source pins used by this draft."""
    doc = load_pinned_json(PROOF_PATH, PROOF_SHA256)
    if doc.get('schema') != 'civ6rl.native_nonzero_scope_b1_30ae.static.v1' or doc.get('images', {}).get('CivilizationVI.exe') != EXE_SHA256:
        raise RuntimeError('B1 nonzero-scope evidence identity changed')
    parents = doc.get('parents', {})
    expected = {'event_registry': REGISTRY_SHA256, 'b1_family': B1_FAMILY_SHA256, 'b1_receivers': B1_RECEIVER_SHA256, 'metadata_scope': METADATA_SCOPE_SHA256}
    for key, digest in expected.items():
        if parents.get(key, {}).get('sha256') != digest:
            raise RuntimeError(f'B1 nonzero-scope parent pin changed: {key}')
    candidates = doc.get('candidate_results')
    if not isinstance(candidates, (list, tuple)) or len(candidates) != 2:
        raise RuntimeError('B1 nonzero-scope candidate set changed')
    b1, other = candidates
    b1_kinds = (2980214136, 4152393721, 330185301)
    if tuple(b1.get('kinds', ())) != tuple((hex(k) for k in b1_kinds)) or tuple(b1.get('record_types', ())) != (146, 117, 149) or b1.get('source_scope_result') != 'N/M neutral under the closed profile' or (other.get('kind') != '0x30ae2a3d') or (other.get('source_scope_result') != 'UNRESOLVED: do not admit at N>0 from this audit'):
        raise RuntimeError('B1 source scope or explicit 30AE exclusion changed')
    closed = b1.get('closed_profile', {})
    if closed.get('normalizer_transform') is not False or closed.get('thread_hook') is not False or closed.get('writer_metadata_service') is not False or (tuple(closed.get('receiver_rows', ())) != (146, 117, 149)) or (closed.get('entity_listener_count') != 0) or (closed.get('no_F054_descriptor_input') is not True):
        raise RuntimeError('B1 closed profile changed')
    receiver_rows = b1.get('empty_receivers')
    if not isinstance(receiver_rows, (list, tuple)) or tuple((r.get('record_type') for r in receiver_rows)) != (146, 117, 149) or any((r.get('record_size') != 96 for r in receiver_rows)):
        raise RuntimeError('B1 receiver row proof changed')
    closed_scope_results = {}
    for kind, (relative_path, digest, expected_size) in _CLOSED_SCOPE_PROOFS.items():
        source = load_pinned_json(_resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_counter_neutral_scope.py')))).resolve().parents[1] / relative_path, digest)
        result = source.get('counter_result_under_closed_profile', {})
        profile = source.get('closed_profile', {})
        if source.get('schema') != 'civ6rl.native_nonzero_scope_closed_profile.static.v1' or source.get('images', {}).get('exe_sha256') != EXE_SHA256 or source.get('kind') != hex(kind) or (source.get('record') != {'type': hex(RECORD_TYPE_BY_KIND[kind]), 'size': hex(expected_size)}) or (profile.get('empty_receiver_record_type') != hex(RECORD_TYPE_BY_KIND[kind])) or (profile.get('entity_listener_count') != 0) or (profile.get('normalizer_transform_present') is not False) or (profile.get('per_thread_hook_present') is not False) or (profile.get('writer_metadata_callback_present') is not False) or (result.get('N') != 'unchanged by this callback path') or (result.get('M') != 'unchanged by this callback path') or (result.get('metadata_flag') != 0) or (source.get('verification', {}).get('native_execution') is not False):
            raise RuntimeError(f'Closed N/M proof changed for {kind:#x}')
        edges = source.get('captured_helper_edges', {})
        limitations = tuple(result.get('not_claimed', ()))
        if 'queue_allocation_path' not in edges or 'tree_iterator' not in edges or '_aligned_malloc' not in edges['queue_allocation_path'].get('allocator', '') or ('external imports' not in edges['queue_allocation_path'].get('limit', '')) or ('does not claim the whole containing function is closed' not in edges.get('tree_iterator', '')) or ('no universal behavior for callees outside the captured closed path' not in limitations) or ('no native N>0 successful enqueue/drain witness' not in limitations):
            raise RuntimeError(f'Closed N/M proof limits changed for {kind:#x}')
        verified = source.get('verification', {})
        direct_calls = verified.get('direct_13ebd0_calls_in_active_bodies', {})
        rip_refs = verified.get('n_m_rip_references_in_active_bodies', {})
        required_bodies = {'callback', 'normalizer', 'resolver', 'writer', 'queue_growth', 'queue_malloc_sized_window', 'queue_free_import_thunk'}
        if not required_bodies.issubset(direct_calls) or not required_bodies.issubset(rip_refs) or any((tuple(direct_calls[name]) for name in required_bodies)) or any((tuple(rip_refs[name]) for name in required_bodies)):
            raise RuntimeError(f'Captured counter-reference inventory changed for {kind:#x}')
        builder_boundary = source.get('known_counter_builder_not_on_active_path', {})
        if builder_boundary.get('complete_function_boundary_claim') is not False:
            raise RuntimeError(f'Counter-builder boundary limit changed for {kind:#x}')
        closed_scope_results[kind] = {'proof_sha256': digest, 'record_type': RECORD_TYPE_BY_KIND[kind], 'record_size': expected_size, 'counter_result': 'N and M unchanged; record metadata flag 0', 'limits': limitations, 'queue_allocation_limit': edges['queue_allocation_path']['limit'], 'tree_iterator_limit': edges['tree_iterator'], 'counter_builder_boundary_complete': False}
    return {'proof_sha256': PROOF_SHA256, 'supported_kinds': tuple(RECORD_TYPE_BY_KIND), 'record_type_by_kind': dict(RECORD_TYPE_BY_KIND), 'closed_scope_proofs': closed_scope_results, 'profile': 'closed no-hook/no-writer-metadata/no-entity-listener', 'native_nonzero_witness': False, 'other_kind_30ae_admitted': False}

def _validate_empty_row(kind: int, state: Any) -> None:
    """Require the exact host-owned empty receiver state before scope admission."""
    if type(kind) is not int or kind not in RECORD_TYPE_BY_KIND:
        raise ValueError('Event kind is outside the proven B1 family')
    if not isinstance(state, dict) or frozenset(state) != _EMPTY_STATE_KEYS:
        raise ValueError('Receiver state has a missing or unexpected field')
    if state['observer_registered'] is not False or state['state_pointer_nonnull'] is not True or state['pre_hook'] is not None or (state['post_hook'] is not None) or (type(state['subscriber_count']) is not int) or (state['subscriber_count'] != 0) or (type(state['state_flags']) is not int) or (state['state_flags'] != 0):
        raise ValueError('Selected B1 receiver is not in the pinned empty state')
    size = 128 if kind == 3629625883 else 96
    shape = bytearray(size)
    struct.pack_into('<II', shape, 0, size, RECORD_TYPE_BY_KIND[kind])
    validate_empty_profile_record(shape, **state)

def validate_scope(kind: int, N: int, M: int, entity_listener_count: int, empty_receiver_state: Any) -> int:
    """Validate the only source-closed nonzero-N profile and preserve M exactly.

    N and M are unsigned 32-bit counters. The function never changes record
    bytes or derives a metadata flag; existing formatters remain authoritative.
    """
    verify_source()
    _validate_empty_row(kind, empty_receiver_state)
    if type(N) is not int or not 0 <= N <= 4294967295:
        raise ValueError('N must be an exact uint32')
    if type(M) is not int or not 0 <= M <= 4294967295:
        raise ValueError('M must be an exact uint32')
    if type(entity_listener_count) is not int or entity_listener_count != 0:
        raise ValueError('The closed B1 profile requires zero entity listeners')
    return M
