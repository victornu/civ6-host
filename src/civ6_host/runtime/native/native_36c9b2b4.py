"""Source-checked raw-input producer for the 36C9B2B4 two-record callback.

The host performs bounded preflight and calls this adapter only with the original
borrowed Core argument tree and the initialized cache facade publisher.
The +0x60 input getter's target and ignored return are source checked here; the
captured path preserves the host-owned N/M counters and does not claim native training readiness.
"""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import struct
from pathlib import Path
from typing import Callable
import ctypes as C
import hashlib
import json
from civ6_host.runtime.native import native_event_827289e6 as normalized_input
from civ6_host.runtime.native import native_wonder_application
from civ6_host.runtime.native import native_36c9b2b4_cache_position_query as cache_position_query
from civ6_host.runtime.native.native_36c9b2b4_cache_position_query import query_native_position_index
from civ6_host.runtime.native.native_36c9b2b4_pair_codec import EMPTY_RECEIVER_STATE
from civ6_host.runtime.native.native_36c9b2b4_pair_codec import ZERO_PADDING_POLICY
from civ6_host.runtime.native.native_36c9b2b4_pair_codec import _is_exact_empty_receiver
from civ6_host.runtime.native.native_36c9b2b4_pair_codec import encode_pair
CALLBACK_SHA256 = '346699c6c7b204d76d9c5ab1be690d3ee4fe4719119e60937641763e3f00aa03'
NORMALIZER_SHA256 = 'c757d2f0c927f36e058ff5e57350a80beac1db2a89d3940fcb5e89c05545f23e'
EXE_SHA256 = 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63'
CORE_SHA256 = 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'
SOURCE_CAPTURE = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_36c9b2b4.py')))).resolve().parents[1] / 'work' / 'native-36c9b2b4-source-capture.json'
SOURCE_CAPTURE_SHA256 = 'b72e6826a418e892246bdd506130a3020991656d3c2329d73301a159cbd5e20b'
_RAW_KEYS = frozenset((2716180809, 2353434172, 3606901732, 2717631346, 1532339015, 4033489650))
_UNSET = object()
CORE_PARAMETER_PROOF = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_36c9b2b4.py')))).resolve().parents[1] / 'evidence' / 'native-event-981a9186-short' / 'dea3dfa82a9924acb6d740d10d8de9d1c5b8a5f9f5caa6cec17f5aec201ab428.json'
CORE_PARAMETER_PROOF_SHA256 = 'dea3dfa82a9924acb6d740d10d8de9d1c5b8a5f9f5caa6cec17f5aec201ab428'
CORE_PARAMETER_LOOKUP_RVA = 7625984
CORE_PARAMETER_VTABLE_RVA = 8507296
CORE_PARAMETER_LOOKUP_SHA256 = 'fe63ac0e1d5244bfe8cc68938fa2d798084f305677682e9dd0e580354c2834a4'
ARGUMENT_PROVENANCE_PATH = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_36c9b2b4.py')))).resolve().parents[1] / 'work' / 'native-36c9b2b4-argument-provenance-review369.json'
ARGUMENT_PROVENANCE_SHA256 = 'd2ea314bfd071f147df73be2b9cce0efe94a0c56a92ae06e3a68f117207b8574'
PAIR_PROOF_SHA256 = 'fd13cd7420166e587746f062eec5fac1f96fdb52037b74aadfb9503f92bcc0cd'
SOURCE_PROOF_SHA256 = PAIR_PROOF_SHA256
E660_PROOF_SHA256 = '9f27a38ba65bbbbcc456d6c929304f76c7766c4941438a23540370aa794f3c33'
F26_SCOPE_PROOF_SHA256 = 'd11156485cd87f78643c9ed40447b3ea5ae97efd1bf7901e95d4afd84b586736'
PLAYER_VIEW_GATE_PATH = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_36c9b2b4.py')))).resolve().parents[1] / 'evidence/native-player-view-cache-gate.json'
PLAYER_VIEW_GATE_SHA256 = 'be958644aa931e3d499ef22704eafc21f26cd7a8bc13f1a1c7c3d16dcd2e3736'
PLAYER_VIEW_GATE_FILE_SHA256 = '2632e4cd0892fe60c6b9e8149edad8c12b9ad00564101d21a98a9a764d2ec6b6'

def verify_source_evidence(*, core_sha256='d7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'):
    if core_sha256 != 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3':
        from civ6_host.runtime.configuration_profiles import XP2_CORE_SHA256
        if core_sha256 != XP2_CORE_SHA256:
            raise ValueError('Unqualified natural-wonder source engine')
        from civ6_host.runtime.xp2_natural_wonder_source import source
        return source()
    proof = verify_source_pair_evidence()
    capture_raw = _resolve_resource_path(SOURCE_CAPTURE).read_bytes()
    if hashlib.sha256(capture_raw).hexdigest() != SOURCE_CAPTURE_SHA256:
        raise RuntimeError('36C9B2B4 source capture hash changed')
    capture = json.loads(capture_raw)
    if capture.get('image', {}).get('sha256') != EXE_SHA256 or capture.get('captures', {}).get('normalizer', {}).get('code_sha256') != NORMALIZER_SHA256 or capture.get('captures', {}).get('callback', {}).get('start_va') != '0x140149fd0' or (capture.get('captures', {}).get('callback', {}).get('length') != 63):
        raise RuntimeError('36C9B2B4 callback/normalizer capture mismatch')
    normalized_input.verify_source_evidence()
    from civ6_host.runtime.native.native_event_1d355e83 import verify_source_evidence as verify_shared_normalizer
    verify_shared_normalizer()
    if proof.get('callback', {}).get('code_sha256') != CALLBACK_SHA256:
        raise RuntimeError('36C9B2B4 pair proof callback body changed')
    native_wonder_application.verify_source_evidence()
    verify_argument_provenance_source()
    return proof

def verify_argument_provenance_source():
    raw = _resolve_resource_path(ARGUMENT_PROVENANCE_PATH).read_bytes()
    if hashlib.sha256(raw).hexdigest() != ARGUMENT_PROVENANCE_SHA256:
        raise RuntimeError('36C9 Core argument provenance review hash changed')
    doc = json.loads(raw)
    contract = doc.get('contract', {})
    abi = contract.get('a0_abi', {})
    lookup = contract.get('lookup_abi', {})
    order = contract.get('core_order', [])
    body = doc.get('captures', {}).get('five_variant_producer', {})
    ins = {row.get('va'): row.get('text') for row in body.get('instructions', [])}
    if doc.get('schema') != 'civ6rl.native_36c9b2b4_argument_provenance_review.work.v1' or doc.get('images') != {'core_sha256': CORE_SHA256, 'exe_sha256': EXE_SHA256} or abi.get('args') != ['this:void*', 'kind:uint32', 'argument:void* borrowed tree map'] or (abi.get('return') != 'int32 fromhost preserved inEBX acrossmapdtor') or (lookup.get('this') != 'same originalargument pointerVT81CFA0') or (lookup.get('slot') != 96) or (lookup.get('key_hex') != '0x5B55A347') or (order != ['262AA5 calls4860D0 with kind36C9B2B4/selector0 and5 namedvariants', '48610F constructor744B80 creates tree map at stackrsp20', '486126 setsA1 selector;486136/146/156/16E/186 assign fivevariants', '486197 calls internal06E010 already performed byCore', '4861A3 passes address of same map inR8 toHostA0 at4861B2', '4861BF destroys map only afterHostA0returns', 'caller262AAE..262AD3 destroys its five namedvariants']) or (ins.get('0x1804861a3') != 'lea r8, [rsp + 0x20]') or (ins.get('0x1804861b2') != 'call qword ptr [rax + 0xa0]') or (ins.get('0x1804861bf') != 'call 0x180744ca0'):
        raise RuntimeError('36C9 original-A0-argument lifetime/source contract changed')
    return doc

def verify_source_pair_evidence():
    return verify_source_evidence_base()

def verify_source_evidence_base():
    from civ6_host.runtime.native.native_36c9b2b4_pair_codec import verify_source_evidence as verify_pair
    return verify_pair()

def verify_counter_neutral_scope(*, core_sha256='d7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'):
    """Verify source-neutral N/M behavior for the closed receiver profile.

    This is not a native observation. It composes the pinned callback, shared
    normalizer/resolver closure, known UI effects, read-only cache query, and
    explicit absent-hook/listener profile. It refuses to infer neutrality from
    the callback's direct references alone.
    """
    if core_sha256 != 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3':
        verify_source_evidence(core_sha256=core_sha256)
        from civ6_host.runtime.xp2_natural_wonder_source import counter_scope
        return counter_scope()
    from civ6_host.runtime.native.native_source_cache import load_pinned_json
    pair = verify_source_pair_evidence()
    e660_path = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_36c9b2b4.py')))).resolve().parents[1] / 'evidence/native-e660-wonder-branch' / f'{E660_PROOF_SHA256}.json'
    f26_path = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_36c9b2b4.py')))).resolve().parents[1] / 'work/native-f26f3acf-counter-scope361' / f'{F26_SCOPE_PROOF_SHA256}.json'
    e660 = load_pinned_json(e660_path, E660_PROOF_SHA256)
    f26_raw = _resolve_resource_path(f26_path).read_bytes()
    if hashlib.sha256(f26_raw).hexdigest() != F26_SCOPE_PROOF_SHA256:
        raise RuntimeError('Shared normalizer/resolver counter-scope parent hash changed')
    f26 = json.loads(f26_raw)
    if f26.get('schema') != 'civ6rl.native_event_f26f3acf_counter_scope361.work.v1' or f26.get('source_recapture', {}).get('callback_counter_rip_targets', {}).get('direct_N_or_M_reference') is not False or f26['source_recapture']['captures']['normalizer']['code_sha256'] != NORMALIZER_SHA256:
        raise RuntimeError('Shared normalizer/resolver counter-scope parent changed')
    capture = json.loads(_resolve_resource_path(SOURCE_CAPTURE).read_text(encoding='utf-8'))
    callback = pair['callback']
    normalizer = capture['captures']['normalizer']

    def instructions(body):
        return [ins for fragment in body.get('fragments', []) for ins in fragment['instructions']]
    callback_ins = instructions(callback)
    normalizer_ins = instructions(normalizer)
    n_m = {'0x1422d7c6c', '0x1422d7c68'}
    for label, body_ins in (('36C9 callback', callback_ins), ('shared normalizer', normalizer_ins)):
        for ins in body_ins:
            if n_m.intersection(ins.get('rip_targets', [])):
                raise RuntimeError(f'{label} now directly accesses N/M')
    if not any((i.get('va') == '0x14014a0e6' and i.get('text') == 'mov dword ptr [rbp + 0x1f], 6' for i in callback_ins)):
        raise RuntimeError('36C9 constant metadata flag changed')
    if any(('0x14013ebd0' in i.get('text', '') for i in callback_ins)):
        raise RuntimeError('36C9 unexpectedly calls the N/M metadata builder')
    comparison = e660['exe_bodies']['comparison_effect']
    if comparison['code_sha256'] != 'e1571a5d102187be6ac36bd527978c35cd6732d0ec580ba024feb7a4cc251a6e':
        raise RuntimeError('151D70 effect proof changed')
    setter = e660['leaves']['UI_manager_bit6_setter']
    if setter['reachable_bytes_sha256'] != '1aa215bc0a1096ff21401e01f6852c0c11bc4e86174ee7fc1bdb6b0bfd98cf6c':
        raise RuntimeError('1B9C30 UI-bit setter proof changed')
    view_raw = _resolve_resource_path(PLAYER_VIEW_GATE_PATH).read_bytes()
    if hashlib.sha256(view_raw).hexdigest() != PLAYER_VIEW_GATE_FILE_SHA256:
        raise RuntimeError('Complete player-view cache-gate evidence hash changed')
    view = json.loads(view_raw)
    accessor = view['cache_functions']['cached_interface_accessor']
    if accessor.get('raw_sha256') != PLAYER_VIEW_GATE_SHA256 or accessor.get('instructions', [{}])[0].get('rip_targets') != ['0x1422d6018']:
        raise RuntimeError('0F14C0 must remain the read-only retained-cache accessor')
    query = cache_position_query.verify_source_evidence()
    if query['binding']['target_body']['code_sha256'] != cache_position_query.POSITION_METHOD_SHA256:
        raise RuntimeError('Cache +0x90 query body changed')
    profile = pair['closed_host_profile']
    if profile.get('host_entity_listener_count') != 0 or profile.get('writer_metadata_callback') != 'explicitly absent in dedicated host profile' or profile.get('host_pre_and_post_hooks') != 'explicitly absent in dedicated host profile':
        raise RuntimeError('36C9 optional observer/callback profile changed')
    return {'notification_counter': 'unchanged by captured path under the explicit closed profile', 'metadata_counter': 'unchanged by captured path under the explicit closed profile', 'direct_callback_N_M_references': False, 'metadata_builder_13EBD0_called': False, 'metadata_flag': 6, 'callback_sha256': CALLBACK_SHA256, 'normalizer_sha256': NORMALIZER_SHA256, 'shared_normalizer_scope_parent_sha256': F26_SCOPE_PROOF_SHA256, 'wonder_effect_parent_sha256': E660_PROOF_SHA256, 'query_proof_sha256': cache_position_query.PROOF_SHA256, 'native_N_M_observation': False}

def _uint32(value, label):
    if type(value) is not int or not 0 <= value <= 4294967295:
        raise ValueError(f'{label} must be an exact uint32')
    return value

def _validate_variant_blob(raw, expected_tag, label):
    if type(raw) is not bytes or len(raw) != 24:
        raise ValueError(f'{label} envelope must be exactly 24 bytes')
    tag = struct.unpack_from('<H', raw)[0]
    pointer, size, flags = struct.unpack_from('<QII', raw, 8)
    if tag != expected_tag or pointer == 0 or size != 8 or (flags != 553648129):
        raise ValueError(f'{label} envelope is outside the source profile')
    return pointer

def _copy_variant_blob(pointer, read, label):
    data = read(pointer, 8)
    if type(data) is not bytes or len(data) != 8:
        raise ValueError(f'{label} native bytes were not copied completely')
    return data

def _decode_captured_raw_fields(raw_fields, read):
    """Decode exactly the six fields present in the 36C9 source witness.

    The separate 827289E6 adapter has a seven-field profile including 38F292C8;
    that key is absent from this 36C9 witness and is deliberately not invented.
    """
    if type(raw_fields) is not dict or frozenset(raw_fields) != _RAW_KEYS:
        raise ValueError('36C9B2B4 requires the exact six witnessed input keys')
    selector = normalized_input.decode_scalar(raw_fields[2716180809], 3)
    value = normalized_input.decode_scalar(raw_fields[3606901732], 2)
    a1fbc = normalized_input.decode_scalar(raw_fields[2717631346], 2)
    ignored_player = normalized_input.decode_scalar(raw_fields[4033489650], 2)
    position_pointer = _validate_variant_blob(raw_fields[2353434172], 13, 'position')
    position = _copy_variant_blob(position_pointer, read, 'position')
    return {'selector': selector, 'normalized_qword_48': position, 'callback_value': value, 'optional_value_a1fbc372': a1fbc, 'ignored_player_f06a2af2': ignored_player}

def validate_closed_gate_input(raw_fields, read):
    """Validate/copy the upstream normalizer input even when F16D0 is closed.

    The gate skips callback effects, queries and record construction; it does
    not skip the source normalizer's six-field validation and position copy.
    """
    verify_source_evidence()
    return _decode_captured_raw_fields(raw_fields, read)

def _lookup_ignored_input_field(core, input_parameter_map, read, native_api=None, *, core_sha256='d7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'):
    """Perform callback's input-map vtable+0x60 lookup; caller discards result."""
    if core_sha256 != 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3':
        verify_source_evidence(core_sha256=core_sha256)
        from civ6_host.runtime.xp2_natural_wonder_source import lookup_ignored_input_field
        return lookup_ignored_input_field(core, input_parameter_map, read, native_api)
    if input_parameter_map is None:
        return {'called': False, 'returned_nonnull': False, 'forced_value': 4294967295}
    if type(input_parameter_map) is not int or input_parameter_map <= 0:
        raise ValueError('Callback R8 input-map argument must be an exact nonzero pointer or None')
    base = getattr(core, '_handle', None)
    if type(base) is not int or base <= 0:
        raise ValueError('Input parameter lookup requires a live Core handle')
    if not callable(read):
        raise ValueError('Input parameter lookup requires checked native reads')

    def qword(address):
        raw = read(address, 8)
        if type(raw) is not bytes or len(raw) != 8:
            raise ValueError('Input parameter lookup requires exact qword reads')
        return struct.unpack('<Q', raw)[0]
    import json
    proof_raw = _resolve_resource_path(CORE_PARAMETER_PROOF).read_bytes()
    if hashlib.sha256(proof_raw).hexdigest() != CORE_PARAMETER_PROOF_SHA256:
        raise RuntimeError('Core tree-map lookup proof hash changed')
    proof = json.loads(proof_raw)
    body = proof['leaves']['core_parameter_map_lookup']
    code = b''.join((bytes.fromhex(i['bytes']) for i in body['instructions']))
    slot = proof.get('map_lookup_slot', {})
    if proof.get('schema') != 'civ6rl.native_event_981a9186_short.static.v1' or proof.get('core_sha256') != CORE_SHA256 or slot.get('table') != '0x18081cfa0' or (slot.get('offset') != 96) or (slot.get('raw_hex') != '005d748001000000') or (slot.get('target') != '0x180745d00') or (body.get('entry_va') != '0x180745d00') or (hashlib.sha256(code).hexdigest() != CORE_PARAMETER_LOOKUP_SHA256):
        raise RuntimeError('Core tree-map +0x60 source contract changed')
    if qword(input_parameter_map) != base + CORE_PARAMETER_VTABLE_RVA:
        raise ValueError('Input parameter object has an unexpected Core vtable')
    if qword(base + CORE_PARAMETER_VTABLE_RVA + 96) != base + CORE_PARAMETER_LOOKUP_RVA:
        raise ValueError('Input parameter +0x60 target changed')
    live_code = read(base + CORE_PARAMETER_LOOKUP_RVA, len(code))
    if type(live_code) is not bytes or live_code != code:
        raise ValueError('Live Core input-map lookup differs from the pinned method')
    if native_api is None:
        lookup = C.WINFUNCTYPE(C.c_void_p, C.c_void_p, C.c_uint32)(base + CORE_PARAMETER_LOOKUP_RVA)
    else:
        if type(native_api) is not dict or set(native_api) != {'lookup'} or (not callable(native_api['lookup'])):
            raise ValueError('Input-map seam must expose only lookup')
        lookup = native_api['lookup']
    result = lookup(input_parameter_map, 1532339015)
    if getattr(core, '_handle', None) != base or qword(input_parameter_map) != base + CORE_PARAMETER_VTABLE_RVA or qword(base + CORE_PARAMETER_VTABLE_RVA + 96) != base + CORE_PARAMETER_LOOKUP_RVA:
        raise RuntimeError('Core input-map identity changed during the +0x60 call')
    return {'called': True, 'returned_nonnull': bool(result), 'forced_value': 4294967295}

def _record_components(index, position, d6_value, a1fbc_value):
    """Recreate the callback's initialized 60-byte metadata and 20-byte payloads."""
    index = _uint32(index, 'native position index')
    if type(position) is not bytes or len(position) != 8:
        raise ValueError('normalized 0x8C position must be exactly eight bytes')
    d6_value = _uint32(d6_value, 'D6 callback DWORD')
    a1fbc_value = _uint32(a1fbc_value, 'A1FBC callback DWORD')
    metadata = bytearray(60)
    struct.pack_into('<II', metadata, 0, index, 4294967295)
    for off, value, fmt in ((8, 65535, '<H'), (10, 0, '<H'), (12, 4294967295, '<I'), (16, 65535, '<H'), (18, 0, '<H'), (20, 4294967295, '<I'), (24, 65535, '<H'), (26, 0, '<H'), (28, 4294967295, '<I'), (32, 65535, '<H'), (34, 0, '<H'), (36, 4294967295, '<I'), (40, 65535, '<H'), (42, 0, '<H'), (44, 4294967295, '<I'), (48, 0, '<Q'), (56, 6, '<I')):
        struct.pack_into(fmt, metadata, off, value)
    first_payload = bytearray(20)
    struct.pack_into('<I', first_payload, 0, 0)
    first_payload[4:12] = position
    struct.pack_into('<I', first_payload, 12, d6_value)
    first_payload[16] = int(a1fbc_value != 0)
    second_payload = b'\x00\x00\x00\x00' + bytes(first_payload[4:20])
    return (bytes(metadata), bytes(first_payload), second_payload)

def produce_pair_from_raw_fields(raw_fields, read, *, sequence_78, core, facades, context, turn_state, retained_getter, notification_counter, metadata_counter, original_argument, position_native_api=None, input_lookup_native_api=None, effect_native_api=None, ui_cache_callbacks_enabled, empty_receiver_state_78, empty_receiver_state_79, normalizer_transform_present, per_thread_hook_present, writer_metadata_callback_present, entity_listener_count, padding_policy, core_sha256='d7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'):
    """Return the two source-ordered records from exact raw event fields.

    The callback's input-object vtable+0x60 lookup is source checked and its
    result discarded as the native ``OR EAX, -1`` does. N/M are validated and
    returned unchanged: the callback writes fixed metadata DWORD 6, not an
    N/M transition. The captured profile still does not claim training-ready
    status or native enqueue success.
    """
    verify_source_evidence(core_sha256=core_sha256)
    counter_scope = verify_counter_neutral_scope(core_sha256=core_sha256)
    if type(raw_fields) is not dict or frozenset(raw_fields) != _RAW_KEYS:
        raise ValueError('36C9B2B4 requires the exact six-key witnessed input')
    if type(ui_cache_callbacks_enabled) is not bool:
        raise ValueError('ui_cache_callbacks_enabled must be an exact bool')
    n = _uint32(notification_counter, 'notification_counter')
    m = _uint32(metadata_counter, 'metadata_counter')
    if type(normalizer_transform_present) is not bool or normalizer_transform_present:
        raise ValueError('36C9B2B4 normalizer transform must be explicitly absent')
    if type(entity_listener_count) is not int or entity_listener_count != 0:
        raise ValueError('36C9B2B4 requires the dedicated zero-listener profile')
    if not callable(read):
        raise ValueError('A checked raw-memory reader is required')
    if not ui_cache_callbacks_enabled:
        decoded = _decode_captured_raw_fields(raw_fields, read)
        return {'records': (), 'callback_gate_open': False, 'normalized_fields': decoded, 'notification_counter_before': n, 'notification_counter_after': n, 'metadata_counter_before': m, 'metadata_counter_after': m, 'native_gameplay_written': False, 'eligible_for_training': False}
    if type(original_argument) is not int or original_argument <= 0:
        raise ValueError('the original callback argument tree map must be preserved')
    sequence_78 = _uint32(sequence_78, 'sequence_78')
    if sequence_78 == 4294967295:
        raise ValueError('the second same-queue sequence would overflow uint32')
    if type(per_thread_hook_present) is not bool or per_thread_hook_present:
        raise ValueError('36C9B2B4 per-thread hooks must be explicitly absent')
    if type(writer_metadata_callback_present) is not bool or writer_metadata_callback_present:
        raise ValueError('36C9B2B4 writer metadata callbacks must be explicitly absent')
    if padding_policy != ZERO_PADDING_POLICY:
        raise ValueError('36C9B2B4 uninitialized stack bytes require the explicit empty policy')
    if not _is_exact_empty_receiver(empty_receiver_state_78) or not _is_exact_empty_receiver(empty_receiver_state_79):
        raise ValueError('36C9B2B4 requires exact empty 0x78 and 0x79 receivers')
    decoded = _decode_captured_raw_fields(raw_fields, read)
    position = decoded['normalized_qword_48']
    x, y = struct.unpack('<ii', position)
    effects = native_wonder_application.apply_wonder_application_effects(core, context, read, turn_state, retained_getter, native_api=effect_native_api, core_sha256=core_sha256)
    input_lookup = _lookup_ignored_input_field(core, original_argument, read, native_api=input_lookup_native_api, core_sha256=core_sha256)
    index, _normalized_x, _normalized_y = _selected_position_index(core, facades, (x, y), read=read, native_api=position_native_api, core_sha256=core_sha256)
    metadata, payload_78, payload_79 = _record_components(index, position, decoded['callback_value'], decoded['optional_value_a1fbc372'])
    record_78, record_79 = encode_pair(sequence_78=sequence_78, metadata_payload=metadata, payload_78=payload_78, payload_79=payload_79, normalizer_transform_present=False, per_thread_hook_present=False, writer_metadata_callback_present=False, entity_listener_count=entity_listener_count, empty_receiver_state_78=empty_receiver_state_78, empty_receiver_state_79=empty_receiver_state_79, padding_policy=padding_policy)
    return {'records': ((120, record_78), (121, record_79)), 'callback_gate_open': True, 'native_position_index': index, 'native_position_before': (x, y), 'native_position_after_query': (_normalized_x, _normalized_y), 'metadata_flag': 6, 'notification_counter_before': n, 'notification_counter_after': n, 'metadata_counter_before': m, 'metadata_counter_after': m, 'counter_scope_source_verified': True, 'counter_neutrality_scope': counter_scope, 'counter_state_observed_natively': False, 'input_getter': input_lookup, 'effects': effects, 'native_gameplay_written': False, 'eligible_for_training': False}

def _selected_position_index(core, facades, position, *, read, native_api=None, core_sha256='d7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'):
    if core_sha256 == 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3':
        return query_native_position_index(core, facades, position, read=read, native_api=native_api)
    verify_source_evidence(core_sha256=core_sha256)
    from civ6_host.runtime.xp2_natural_wonder_source import position_index
    return position_index(core, facades, position, read=read, native_api=native_api)
