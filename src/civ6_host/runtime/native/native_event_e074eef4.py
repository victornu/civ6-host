"""Proof-gated diagnostic adapter for EXE event 0xE074EEF4.

The callback queries a live Core plot and queues an A8 record. This module
reproduces only that exact native query and the source-initialized record
fields. Stack bytes that the writer copies but the empty A8 receiver does not
read are zeroed only under an explicit empty-receiver diagnostic policy.
"""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import ctypes as C
import hashlib
import struct
from contextlib import contextmanager
from pathlib import Path
from typing import Mapping
from civ6_host.runtime.native.native_application_mirror import decode_scalar
from civ6_host.runtime.native.native_host_events import copy_eight_byte_variant
from civ6_host.runtime.native.native_source_cache import load_pinned_json
EVENT_KIND = 3765759732
CALLBACK_VA = 5370022528
WRITER_VA = 5369979200
RECORD_TYPE = 168
RECORD_SIZE = 128
SELECTOR_KEY = 2716180809
SCALAR_KEY = 3606901732
POSITION_KEY = 2353434172
_FIELD_KEYS = frozenset((SELECTOR_KEY, SCALAR_KEY, POSITION_KEY))
EXE_SHA256 = 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63'
CORE_SHA256 = 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'
PINNED_EVIDENCE_SHA256 = '8e5ac02bc193fcfb38449354887283b4ca4dcdaee6567c4d7430fa4fb7dbac9b'
_PROOF = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_event_e074eef4.py')))).resolve().parents[1] / 'evidence' / 'native-event-e074eef4' / f'{PINNED_EVIDENCE_SHA256}.json'
PADDING_POLICY = 'zero-unread-empty-receiver-payload'
_BODY_HASHES = {'callback': 'cbeeeb036fbf2175d4a44eab674e055487ccfa33d5b48b5e15ac7630ea9a625f', 'normalizer': 'c757d2f0c927f36e058ff5e57350a80beac1db2a89d3940fcb5e89c05545f23e', 'queue_append_a8': 'c8d459bdad84e733db7d1647b3f576f53d2dd68101b50da0625c418ac8661dfe', 'host_event_emitter': '636775c1a4983f9a817c24705bf91ec90732cfc646caa121e209510e9ca6fc60', 'probe_stack_bff53_containing_function': '727a7c3a572065d187bd9358410e074f46c2521064e7475c62548aea1b61bde7', 'outer_map_getter': '23e0832060be0ff30d62fdbae9a5c2ab6ccdd04e88507b4dccb93be9e6c43c38', 'map_plot_getter': 'a3508af0fa1464502403c318efaf970db6678eb2d20c19005235990cd379f70b', 'plot_slot_0x178_tail': '7cf4be1451186311c72ab518fc541a4d7b1b46fe41b7688658b7d5aaf3ea5903', 'plot_slot_0x148_tail': 'a62d05772a19e6b2493ad037fed68d857c668fc3a6db7841149c388c4440cb79'}
_LEAF_HASHES = {'plot_slot_0x178': 'af3c1a3bbe9df9206e3a9c8b9824700e96c36331a75a4ef585169dba6597f72c', 'plot_slot_0x148': '347f2c9d7085b48c13e8210ce9cbf83511526c097b9d6da1eb8667086be13273'}
_CORE_VTABLES = {'outer': (7987232, ((168, 4382784),)), 'map': (7991792, ((8, 4416608), (64, 4418176))), 'plot': (7994424, ((8, 4435728), (328, 4437344), (376, 4435760)))}

def _flatten_body(body: Mapping) -> list[dict]:
    return [ins for fragment in body.get('fragments', ()) for ins in fragment.get('instructions', ())]

def verify_source_evidence() -> None:
    proof = load_pinned_json(_PROOF, PINNED_EVIDENCE_SHA256)
    if proof.get('schema') != 'civ6rl.native_event_e074eef4.static.v1' or proof.get('images', {}).get('exe_sha256') != EXE_SHA256 or proof.get('images', {}).get('core_sha256') != CORE_SHA256 or (proof.get('registration', {}).get('kind') != '0xe074eef4') or (proof.get('registration', {}).get('callback_va') != '0x140140a80'):
        raise RuntimeError('Pinned E074EEF4 image or registration changed')
    for group, names in (('exe_bodies', ('callback', 'normalizer', 'queue_append_a8')), ('core_bodies', ('outer_map_getter', 'map_plot_getter', 'plot_slot_0x178_tail', 'plot_slot_0x148_tail', 'host_event_emitter', 'probe_stack_bff53_containing_function'))):
        bodies = proof.get(group, {})
        for name in names:
            body = bodies.get(name, {})
            if body.get('raw_sha256') != _BODY_HASHES[name]:
                raise RuntimeError(f'Pinned E074EEF4 body changed: {name}')
    producer = proof['core_bodies']['probe_stack_bff53_containing_function']
    if producer.get('start_va') != '0x1800bfec0' or '0x1800bff53' not in {ins['va'] for ins in _flatten_body(producer)}:
        raise RuntimeError('E074EEF4 stack witness is no longer covered by producer 0x1800BFEC0')
    leaves = proof.get('core_leaf_flows', {})
    for name, expected in _LEAF_HASHES.items():
        leaf = leaves.get(name, {})
        if leaf.get('reachable_bytes_sha256') != expected:
            raise RuntimeError(f'Pinned E074EEF4 virtual wrapper changed: {name}')
    row = proof.get('receiver_a8', {}).get('match', {})
    if row.get('record_type') != '0xa8' or row.get('event_name', {}).get('text') != 'GameCoreEvent::BuildingRemovedFromMap' or row.get('handler_va') != '0x1400d9df0' or (row.get('common_subscriber_dispatch_va') != '0x1400dc0d0'):
        raise RuntimeError('Pinned E074EEF4 A8 receiver route changed')
    writer = _flatten_body(proof['exe_bodies']['queue_append_a8'])
    expected_stores = {'0x1401361e6': 'mov dword ptr [rbx], 0x80', '0x1401361ec': 'mov dword ptr [rbx + 4], 0xa8', '0x140136283': 'movsd qword ptr [rax + 0x20], xmm0', '0x140136288': 'mov dword ptr [rax], edi'}
    actual = {ins['va']: ins['text'] for ins in writer}
    if any((actual.get(address) != instruction for address, instruction in expected_stores.items())):
        raise RuntimeError('Pinned E074EEF4 queue writer layout changed')

def decode_fields(raw_fields: dict[int, bytes], read) -> dict:
    """Decode exactly the normalizer shape read by callback 0x140140A80."""
    verify_source_evidence()
    if not isinstance(raw_fields, dict) or set(raw_fields) != _FIELD_KEYS:
        raise ValueError('E074EEF4 requires exactly its three witnessed fields')
    selector = decode_scalar(raw_fields[SELECTOR_KEY], 3)
    scalar = decode_scalar(raw_fields[SCALAR_KEY], 2)
    position = copy_eight_byte_variant(raw_fields[POSITION_KEY], read, expected_tag=0)
    x, y = struct.unpack('<ii', position)
    return {'selector': selector, 'source_scalar': scalar, 'position_bytes': position, 'x': x, 'y': y}

def _validate_position(position: Mapping) -> None:
    if not isinstance(position, Mapping) or set(position) != {'selector', 'source_scalar', 'position_bytes', 'x', 'y'} or type(position['selector']) is not int or (not 0 <= position['selector'] <= 4294967295) or (type(position['source_scalar']) is not int) or (not 0 <= position['source_scalar'] <= 4294967295) or (type(position['position_bytes']) is not bytes) or (len(position['position_bytes']) != 8) or (type(position['x']) is not int) or (type(position['y']) is not int) or (struct.unpack('<ii', position['position_bytes']) != (position['x'], position['y'])):
        raise ValueError('Unverified E074EEF4 decoded input')

def _check_vtable(read, base: int, pointer: int, name: str) -> None:
    vtable_rva, slots = _CORE_VTABLES[name]
    if not pointer or int.from_bytes(read(pointer, 8), 'little') != base + vtable_rva:
        raise ValueError(f'Unexpected E074EEF4 {name} interface')
    for offset, target in slots:
        actual = int.from_bytes(read(base + vtable_rva + offset, 8), 'little')
        if actual != base + target:
            raise ValueError(f'Unexpected E074EEF4 {name} slot {offset:#x}')

def _check_core_code(read, base: int) -> None:
    proof = load_pinned_json(_PROOF, PINNED_EVIDENCE_SHA256)
    bodies = proof['core_bodies']
    named = {'outer_map_getter': bodies['outer_map_getter'], 'map_plot_getter': bodies['map_plot_getter'], 'plot_slot_0x178_tail': bodies['plot_slot_0x178_tail'], 'plot_slot_0x148_tail': bodies['plot_slot_0x148_tail']}
    instructions = {name: _flatten_body(body) for name, body in named.items()}
    for leaf_name, body in proof['core_leaf_flows'].items():
        instructions[leaf_name] = body['instructions']
    from civ6_host.runtime.native.native_feature_visibility_event import CORE_CODE_PINS
    from civ6_host.runtime.native.native_feature_visibility_event import verify_source_evidence
    verify_source_evidence()
    required_pins = {(4416512, 33), (4435616, 33), (4416608, 29), (4435728, 29)}
    if not required_pins.issubset(CORE_CODE_PINS):
        raise RuntimeError('E074EEF4 release/wrapper code pins are unavailable')
    for (rva, size), expected in CORE_CODE_PINS.items():
        if (rva, size) in required_pins and hashlib.sha256(bytes(read(base + rva, size))).hexdigest() != expected:
            raise ValueError(f'E074EEF4 Core release/wrapper code changed at {rva:#x}')
    for name, stream in instructions.items():
        for ins in stream:
            address = int(ins['va'], 16)
            if bytes(read(base + address - 6442450944, len(bytes.fromhex(ins['bytes'])))) != bytes.fromhex(ins['bytes']):
                raise ValueError(f"E074EEF4 Core code changed at {name}:{ins['va']}")

@contextmanager
def query_descriptor_lease(core, context: int, position: Mapping, *, read=None, normalizer_transform_present: bool, thread_hook_present: bool, writer_metadata_callback_present: bool, padding_policy: str, empty_receiver_state: Mapping, native_api: Mapping | None=None):
    """Yield query scalars while retaining the plot lease until context exit.

    Production callers must encode/append the record and release their queue
    lock inside this context; then plot release occurs after append and unlock,
    matching the source callback. Core release can run the destructor at
    refcount one, so preserving lease lifetime matters for ordering.
    """
    verify_source_evidence()
    _validate_profile(normalizer_transform_present, thread_hook_present, writer_metadata_callback_present, padding_policy, empty_receiver_state, header=None)
    _validate_position(position)
    base = int(core._handle)
    if read is None:
        from civ6_host.runtime.native.native_setup import local_reader
        read = local_reader()
    if native_api is None:
        _check_core_code(read, base)
    _check_vtable(read, base, int(context), 'outer')
    if native_api is None:
        api = {'outer_map': C.WINFUNCTYPE(C.c_void_p, C.c_void_p)(base + 4382784), 'get_plot': C.WINFUNCTYPE(C.c_void_p, C.c_void_p, C.c_int32, C.c_int32)(base + 4418176), 'release_map': C.WINFUNCTYPE(None, C.c_void_p)(base + 4416608), 'release_plot': C.WINFUNCTYPE(None, C.c_void_p)(base + 4435728), 'snapshot178': C.WINFUNCTYPE(C.c_uint64, C.c_void_p, C.c_void_p, C.c_uint32)(base + 4435760), 'plot_flag': C.WINFUNCTYPE(C.c_uint8, C.c_void_p)(base + 4437344)}
    else:
        api = dict(native_api)
        if set(api) != {'outer_map', 'get_plot', 'release_map', 'release_plot', 'snapshot178', 'plot_flag'}:
            raise ValueError('E074EEF4 test seam must provide exactly six native entrypoints')
    map_obj = api['outer_map'](context)
    if not map_obj:
        raise ValueError('E074EEF4 null map is not an admissible query result')
    try:
        _check_vtable(read, base, int(map_obj), 'map')
        plot = api['get_plot'](map_obj, position['x'], position['y'])
    finally:
        api['release_map'](map_obj)
    if not plot:
        raise ValueError('E074EEF4 null plot is not an admissible query result')
    try:
        _check_vtable(read, base, int(plot), 'plot')
        guard = b'\xa5' * 16
        output = C.create_string_buffer(24 + len(guard))
        C.memset(C.addressof(output), 165, 24)
        C.memmove(C.addressof(output) + 24, guard, len(guard))
        api['snapshot178'](plot, C.addressof(output), 0)
        if output.raw[24:] != guard:
            raise ValueError('E074EEF4 plot snapshot exceeded its 24-byte output')
        flag = api['plot_flag'](plot)
        if type(flag) is not int or flag not in (0, 1):
            raise ValueError('E074EEF4 plot slot +0x148 did not return canonical bool')
        descriptor = {'snapshot_dword_4': struct.unpack_from('<I', output.raw, 4)[0], 'snapshot_dword_8': struct.unpack_from('<I', output.raw, 8)[0], 'snapshot_sbyte_20': struct.unpack_from('<b', output.raw, 20)[0], 'plot_flag': flag}
        yield descriptor
    finally:
        api['release_plot'](plot)

def query_descriptor(core, context: int, position: Mapping, *, read=None, normalizer_transform_present: bool, thread_hook_present: bool, writer_metadata_callback_present: bool, padding_policy: str, empty_receiver_state: Mapping, native_api: Mapping | None=None) -> dict:
    """Compatibility wrapper; production integrations should use the lease."""
    with query_descriptor_lease(core, context, position, read=read, normalizer_transform_present=normalizer_transform_present, thread_hook_present=thread_hook_present, writer_metadata_callback_present=writer_metadata_callback_present, padding_policy=padding_policy, empty_receiver_state=empty_receiver_state, native_api=native_api) as descriptor:
        return descriptor

def _receiver_state(value: Mapping) -> dict:
    required = {'observer_registered', 'state_pointer_nonnull', 'pre_hook', 'post_hook', 'subscriber_count', 'state_flags'}
    if not isinstance(value, Mapping) or set(value) != required:
        raise ValueError('E074EEF4 requires complete empty A8 receiver state')
    return dict(value)

def _validate_profile(normalizer_transform_present, thread_hook_present, writer_metadata_callback_present, padding_policy, empty_receiver_state, header: bytes | None) -> dict:
    verify_source_evidence()
    if normalizer_transform_present is not False or thread_hook_present is not False or writer_metadata_callback_present is not False:
        raise ValueError('E074EEF4 transform, per-thread hook, or metadata callback is unsupported')
    if padding_policy != PADDING_POLICY:
        raise ValueError('E074EEF4 requires explicit empty-receiver unread-payload zeroing')
    state = _receiver_state(empty_receiver_state)
    if header is None:
        from civ6_host.runtime.native.native_deferred_empty_profile import validate_empty_profile_record
        header_buf = bytearray(RECORD_SIZE)
        struct.pack_into('<IIII', header_buf, 0, RECORD_SIZE, RECORD_TYPE, 1, 0)
        header = bytes(header_buf)
        return validate_empty_profile_record(header, **state)
    from civ6_host.runtime.native.native_deferred_empty_profile import validate_empty_profile_record
    return validate_empty_profile_record(header, **state)

def _pack_record(sequence: int, position: Mapping, descriptor: Mapping) -> bytes:
    _validate_position(position)
    expected = {'snapshot_dword_4', 'snapshot_dword_8', 'snapshot_sbyte_20', 'plot_flag'}
    if not isinstance(descriptor, Mapping) or set(descriptor) != expected:
        raise ValueError('E074EEF4 requires the exact native plot query result')
    for key in ('snapshot_dword_4', 'snapshot_dword_8'):
        if type(descriptor[key]) is not int or not 0 <= descriptor[key] <= 4294967295:
            raise ValueError('Invalid E074EEF4 snapshot DWORD')
    if type(descriptor['snapshot_sbyte_20']) is not int or not -128 <= descriptor['snapshot_sbyte_20'] <= 127:
        raise ValueError('Invalid E074EEF4 signed snapshot byte')
    if type(descriptor['plot_flag']) is not int or descriptor['plot_flag'] not in (0, 1):
        raise ValueError('Invalid E074EEF4 native bool')
    if type(sequence) is not int or not 1 <= sequence <= 2147483647:
        raise ValueError('E074EEF4 queue sequence must be a positive bounded integer')
    payload = bytearray(40)
    payload[8:16] = position['position_bytes']
    struct.pack_into('<hHI', payload, 16, descriptor['snapshot_sbyte_20'], 2, descriptor['snapshot_dword_4'])
    struct.pack_into('<hHI', payload, 24, descriptor['snapshot_sbyte_20'], 3, descriptor['snapshot_dword_8'])
    payload[32] = descriptor['plot_flag']
    struct.pack_into('<I', payload, 36, position['source_scalar'])
    record = bytearray(RECORD_SIZE)
    struct.pack_into('<IIII', record, 0, RECORD_SIZE, RECORD_TYPE, sequence, 0)
    struct.pack_into('<IIHHI', record, 16, 4294967295, 4294967295, 65535, 0, 4294967295)
    for offset in (32, 40, 48, 56):
        struct.pack_into('<HHI', record, offset, 65535, 0, 4294967295)
    struct.pack_into('<QII', record, 64, 0, 0, 0)
    struct.pack_into('<I', payload, 0, sequence)
    record[80:120] = payload
    return bytes(record)

def validate_profile(**profile) -> dict:
    """Refuse unknown receivers before copying borrowed fields or querying Core."""
    return _validate_profile(**profile, header=None)

def encode_record(sequence: int, position: Mapping, descriptor: Mapping, *, normalizer_transform_present: bool, thread_hook_present: bool, writer_metadata_callback_present: bool, padding_policy: str, empty_receiver_state: Mapping) -> bytes:
    """Encode A8 only after validating the actual source-derived empty row."""
    verify_source_evidence()
    record = _pack_record(sequence, position, descriptor)
    _validate_profile(normalizer_transform_present, thread_hook_present, writer_metadata_callback_present, padding_policy, empty_receiver_state, header=record)
    return record
__all__ = ['EVENT_KIND', 'RECORD_TYPE', 'RECORD_SIZE', 'decode_fields', 'query_descriptor', 'query_descriptor_lease', 'encode_record', 'validate_profile', 'verify_source_evidence']
