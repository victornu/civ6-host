"""Source-backed producer for EXE GameCoreEvent::FeatureVisibilityChanged."""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import ctypes as C
import hashlib
import struct
from pathlib import Path
from civ6_host.runtime.native.native_application_mirror import decode_scalar
from civ6_host.runtime.native.native_source_cache import load_pinned_json
_ROOT = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_feature_visibility_event.py')))).resolve().parents[1]
EVENT_KIND = 2274153042
BLOB_KEY = 2353434172
SELECTOR_KEY = 2716180809
TAIL_KEY = 3606901732
OPTIONAL_METADATA_KEY = 1532339015
IGNORED_PLAYER_KEY = 4033489650
RECORD_TYPE = 118
RECORD_SIZE = 128
PAYLOAD_SIZE = 48
METADATA_SIZE = 60
PINNED_CORE_SHA256 = 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'
PINNED_EXE_SHA256 = 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63'
PINNED_CALLBACK_BODY_SHA256 = '33e8a76bf64a791ff31bc178a17cc381378475341164a691fc7fa1a07ad47cdd'
PINNED_NORMALIZER_BODY_SHA256 = 'c757d2f0c927f36e058ff5e57350a80beac1db2a89d3940fcb5e89c05545f23e'
PINNED_EVIDENCE_SHA256 = '593d9250d456a9c601b51f29948f021fbc81a185f0d5831b94443ee94fafffad'
PINNED_QUERY_EVIDENCE_SHA256 = '883018db30f659723d537ec8c7c249590d72bcdd35ae78636c44d91864bd3361'
SCOPE_PROOF_SHA256 = 'd369807058cd61185733129a39ccd61c08fb5a8eb576122f175d4fcf42329f21'
CORE_CODE_PINS = {(4382784, 77): '23e0832060be0ff30d62fdbae9a5c2ab6ccdd04e88507b4dccb93be9e6c43c38', (4418176, 120): 'a3508af0fa1464502403c318efaf970db6678eb2d20c19005235990cd379f70b', (67648, 193): '4566fedd21ca22d445823ae54a2ae0a0c1ac61c2c9d19217cf1b97bbd433a1d2', (4416512, 33): '9f30251418f60e3c398dec5aa320801b3b07137b0394eb9cd26a5827aadf1050', (4435616, 33): '77cfe90725fefc2de40efef9d260942ec2bac0527558238e80afac8a0b83a796', (4435856, 29): 'f02fc638e1377f38b1f1e83d7503404a091fd0728a704e6f317d1edc74dc0d3a', (4416608, 29): 'd9bf8c162ecdf928e1e3b63ff723a24fa4fc28cfd46a6b0158b860fdf0ee665b', (4435728, 29): '51435bfd22e0f1966c3136b0e2e11a4e51c9f2c576c94b57fdd2fc28e1f1104f'}
OUTER_VTABLE = 7987232
OUTER_MAP_SLOT = 168
OUTER_MAP_GET = 4382784
MAP_VTABLE = 7991792
MAP_RELEASE_SLOT, MAP_RELEASE = (8, 4416608)
MAP_GET_PLOT_SLOT, MAP_GET_PLOT = (64, 4418176)
PLOT_VTABLE = 7994424
PLOT_RELEASE_SLOT, PLOT_RELEASE = (8, 4435728)
PLOT_SNAPSHOT_SLOT, PLOT_SNAPSHOT = (384, 4435856)
PLOT_SNAPSHOT_IMPL = 67648

def verify_source_evidence() -> None:
    """Require the exact EXE callback and host-normalizer instruction proofs."""
    evidence_path = _ROOT / 'evidence' / 'native-event-878cd252' / f'{PINNED_EVIDENCE_SHA256}.json'
    doc = load_pinned_json(evidence_path, PINNED_EVIDENCE_SHA256)
    bodies = doc.get('body_sha256', {})
    if doc.get('schema') != 'civ6rl.native_event_878cd252.v2' or doc.get('image', {}).get('exe_sha256') != PINNED_EXE_SHA256 or doc.get('event', {}).get('kind') != '0x878cd252' or (doc.get('event', {}).get('callback_va') != '0x140146950') or (bodies.get('callback') != PINNED_CALLBACK_BODY_SHA256) or (bodies.get('host_a0_normalizer') != PINNED_NORMALIZER_BODY_SHA256):
        raise RuntimeError('Pinned FeatureVisibilityChanged callback/normalizer proof changed')
    query_path = _ROOT / 'evidence/native-feature-visibility-query' / f'{PINNED_QUERY_EVIDENCE_SHA256}.json'
    query = load_pinned_json(query_path, PINNED_QUERY_EVIDENCE_SHA256)
    if query.get('schema') != 'civ6rl.native_feature_visibility_query.v2' or query.get('images', {}).get('core_sha256') != PINNED_CORE_SHA256:
        raise RuntimeError('Pinned FeatureVisibilityChanged Core query identity changed')

def verify_scoped_source_evidence() -> None:
    proof = load_pinned_json(_ROOT / 'evidence/native-feature-visibility-scope' / (SCOPE_PROOF_SHA256 + '.json'), SCOPE_PROOF_SHA256)
    if proof['schema'] != 'civ6rl.native_feature_visibility_scope.static.v1' or proof['kind'] != EVENT_KIND or proof['images']['exe_sha256'] != PINNED_EXE_SHA256 or (proof['images']['core_sha256'] != PINNED_CORE_SHA256) or (proof['callback_sha256'] != PINNED_CALLBACK_BODY_SHA256) or (tuple(proof['contract']['supported_event_kinds']) != (EVENT_KIND,)) or (proof['contract']['record_type'] != RECORD_TYPE) or (proof['contract']['record_flag_offset'] != 72) or (proof['contract']['no_cache_gate'] is not True):
        raise RuntimeError('FeatureVisibilityChanged notification scope proof changed')

def _copy_blob(raw, read, tag):
    if not isinstance(raw, (bytes, bytearray, memoryview)) or len(raw) != 24:
        raise ValueError('Incomplete FeatureVisibilityChanged blob variant')
    actual_tag = struct.unpack_from('<H', raw)[0]
    pointer, size, flags = struct.unpack_from('<QII', raw, 8)
    if actual_tag != tag or not pointer or size != 8 or (flags != 553648129):
        raise ValueError('Unverified FeatureVisibilityChanged blob envelope')
    copied = read(pointer, 8)
    if not isinstance(copied, (bytes, bytearray, memoryview)) or len(copied) != 8:
        raise ValueError('Incomplete FeatureVisibilityChanged pointed value')
    return bytes(copied)

def decode_feature_visibility_fields(fields: dict[int, bytes], read) -> dict:
    """Decode the witnessed three- or five-field input without guessed values.

    Source callback 0x140146950 copies the blob's eight bytes to descriptor
    offsets 0..7, then copies D6's uint32 at offset 8. Its lookup helper uses
    only the first two signed DWORDs as x/y. Prefix115 adds the copied 5B55
    metadata pair and an ignored player scalar. A1FBC372 remains absent in
    both admitted sets, so helper147F10 returns without querying Core.
    """
    verify_source_evidence()
    basic = {BLOB_KEY, SELECTOR_KEY, TAIL_KEY}
    extended = basic | {OPTIONAL_METADATA_KEY, IGNORED_PLAYER_KEY}
    if not isinstance(fields, dict) or set(fields) not in (basic, extended):
        raise ValueError('Unverified 0x878CD252 field set or optional callback keys present')
    if decode_scalar(fields[SELECTOR_KEY], 3) != 0:
        raise ValueError('Unverified 0x878CD252 selector')
    tail = decode_scalar(fields[TAIL_KEY], 2)
    has_pair = set(fields) == extended
    position = _copy_blob(fields[BLOB_KEY], read, 13 if has_pair else 0)
    metadata_pair = _copy_blob(fields[OPTIONAL_METADATA_KEY], read, 1024) if has_pair else struct.pack('<HHI', 65535, 0, 4294967295)
    player = decode_scalar(fields[IGNORED_PLAYER_KEY], 2) if has_pair else None
    x, y = struct.unpack('<ii', position)
    return {'x': x, 'y': y, 'position_bytes': position, 'descriptor_tail': tail, 'selector': 0, 'metadata_pair_bytes': metadata_pair, 'ignored_player': player, 'input_profile': 'prefix115-five-fields' if has_pair else 'prefix95-three-fields'}

def query_plot_word(core, context, position: dict, *, read=None, native_api=None, core_sha256='d7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3') -> int:
    """Match EXE helper 0x1476F0 through Core's owned map/plot wrappers.

    Returns -1 when the Core map or plot getter returns null, matching the
    EXE helper's initialized failure value. For a live plot it returns the
    sign-extended first int16 written by the plot snapshot API.
    """
    return _query_plot_snapshot_word(core, context, position, word_offset=0, read=read, native_api=native_api, core_sha256=core_sha256)

def _query_plot_snapshot_word(core, context, position: dict, *, word_offset: int, read=None, native_api=None, core_sha256='d7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3') -> int:
    """Shared owned-wrapper route; producer proofs fix each selected word.

    Only offsets zero (EXE1476F0) and four (EXE147C10) are admitted. The
    ResourceAddedToMap caller verifies its additional source proof first.
    The outer context is borrowed from the host; only the newly returned map
    and plot references are released here.
    """
    if core_sha256 not in ('d7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3', '259b90a473a256aff6a7d621a4f3717e46f6921c59b9817475375c88b97e8c83', '324c51e9ea3531758842e16c69e6cddbefbb226c5b675c3d6e60111646c2e98c'):
        raise ValueError('Unqualified facade engine')
    from civ6_host.runtime.foundation_facade_profiles import query_abi, verify_xp1_once, select_tables
    from civ6_host.runtime.provenance import resource_root
    _foundation_abi = query_abi(core_sha256, None if core_sha256 == 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3' else resource_root())
    verify_source_evidence()
    if type(word_offset) is not int or word_offset not in (0, 4):
        raise ValueError('Unverified plot snapshot word offset')
    if type(position.get('x')) is not int or type(position.get('y')) is not int or (not -(1 << 31) <= position['x'] < 1 << 31) or (not -(1 << 31) <= position['y'] < 1 << 31):
        raise ValueError('Unverified signed plot coordinates')
    base = int(core._handle)
    if read is None:
        from civ6_host.runtime.native.native_setup import local_reader
        read = local_reader()
    if native_api is None:
        if core_sha256 == 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3':
            for (rva, size), expected in CORE_CODE_PINS.items():
                if hashlib.sha256(read(base + rva, size)).hexdigest() != expected:
                    raise ValueError(f'Pinned Core map/plot query code changed at RVA {rva:#x}')
        else:
            verify_xp1_once(core, base, read, resource_root(), core_sha256=core_sha256)

    def check_slot(vtable, offset, target):
        actual = int.from_bytes(read(base + vtable + offset, 8), 'little')
        if actual != base + target:
            raise ValueError(f'Core virtual slot {vtable:#x}+{offset:#x} changed')

    def check_object(pointer, vtable, slots):
        if not pointer or int.from_bytes(read(pointer, 8), 'little') != base + vtable:
            raise ValueError('Unexpected Core map/plot wrapper')
        for offset, target in slots:
            check_slot(vtable, offset, target)
    check_object(context, _foundation_abi.table('outer'), ((_foundation_abi.slot('outer_map'), _foundation_abi.rva('outer_map')),))
    if native_api is None:
        outer_map = C.WINFUNCTYPE(C.c_void_p, C.c_void_p)(base + _foundation_abi.rva('outer_map'))
        release_map = C.WINFUNCTYPE(None, C.c_void_p)(base + _foundation_abi.rva('release_map'))
        get_plot = C.WINFUNCTYPE(C.c_void_p, C.c_void_p, C.c_int32, C.c_int32)(base + _foundation_abi.rva('get_plot'))
        release_plot = C.WINFUNCTYPE(None, C.c_void_p)(base + _foundation_abi.rva('release_plot'))
        snapshot = C.WINFUNCTYPE(C.c_uint64, C.c_void_p, C.c_void_p, C.c_uint32)(base + _foundation_abi.rva('plot_snapshot180'))
    else:
        required = {'outer_map', 'release_map', 'get_plot', 'release_plot', 'snapshot'}
        if set(native_api) != required:
            raise ValueError('Native map/plot test seam must supply all five entrypoints')
        outer_map, release_map, get_plot = (native_api[k] for k in ('outer_map', 'release_map', 'get_plot'))
        release_plot, snapshot = (native_api['release_plot'], native_api['snapshot'])
    map_obj = outer_map(context)
    if not map_obj:
        return -1
    try:
        check_object(map_obj, _foundation_abi.table('map'), ((_foundation_abi.slot('release_map'), _foundation_abi.rva('release_map')), (_foundation_abi.slot('get_plot'), _foundation_abi.rva('get_plot'))))
        plot = get_plot(map_obj, position['x'], position['y'])
    finally:
        release_map(map_obj)
    if not plot:
        return -1
    try:
        check_object(plot, _foundation_abi.table('plot'), ((_foundation_abi.slot('release_plot'), _foundation_abi.rva('release_plot')), (PLOT_SNAPSHOT_SLOT, _foundation_abi.rva('plot_snapshot180'))))
        output = C.create_string_buffer(24)
        C.memset(C.addressof(output), 165, C.sizeof(output))
        snapshot(plot, C.addressof(output), 0)
        return struct.unpack_from('<h', output.raw, word_offset)[0]
    finally:
        release_plot(plot)

def encode_record(sequence: int, position: dict, plot_word: int, *, notification_counter: int, thread_hook_present: bool, writer_metadata_callback_present: bool, queue_callback_result: int=0, padding_policy: str='zero') -> bytes:
    """Encode type0x76 with source metadata and the native-query payload.

    Bytes +4..+7 and +0x2c..+0x2f in payload are not source-initialized; the
    explicit zero policy is diagnostic padding. Plot values are required
    from the native Core plot query, never replaced by a guessed constant.
    """
    return _encode_plot_visibility_record(sequence, position, plot_word, record_type=RECORD_TYPE, notification_counter=notification_counter, thread_hook_present=thread_hook_present, writer_metadata_callback_present=writer_metadata_callback_present, queue_callback_result=queue_callback_result, padding_policy=padding_policy)

def encode_scoped_record(sequence: int, position: dict, plot_word: int, *, notification_counter: int, metadata_counter: int, thread_hook_present: bool, writer_metadata_callback_present: bool, queue_callback_result: int=0, padding_policy: str='zero') -> tuple[bytes, int]:
    """Explicit76-only N/M state; the original zero-scope APIs stay bounded."""
    verify_scoped_source_evidence()
    from civ6_host.runtime.native.native_notification_metadata import metadata_scope_transition
    flag, after = metadata_scope_transition(notification_counter, metadata_counter)
    record = _encode_plot_visibility_record_metadata(sequence, position, plot_word, record_type=RECORD_TYPE, metadata_flag=flag, thread_hook_present=thread_hook_present, writer_metadata_callback_present=writer_metadata_callback_present, queue_callback_result=queue_callback_result, padding_policy=padding_policy)
    return (record, after)

def _encode_plot_visibility_record(sequence: int, position: dict, plot_word: int, *, record_type: int, notification_counter: int, thread_hook_present: bool, writer_metadata_callback_present: bool, queue_callback_result: int, padding_policy: str) -> bytes:
    """Shared byte layout for the separately proven writers 1315B0/133770.

    Only record types76 and8C are admitted. Their producer-specific decoders
    and source proofs remain responsible for the different input/query paths.
    """
    if type(notification_counter) is not int or notification_counter != 0:
        raise ValueError('FeatureVisibilityChanged nonzero notification counter is not modeled')
    return _encode_plot_visibility_record_metadata(sequence, position, plot_word, record_type=record_type, metadata_flag=0, thread_hook_present=thread_hook_present, writer_metadata_callback_present=writer_metadata_callback_present, queue_callback_result=queue_callback_result, padding_policy=padding_policy)

def _encode_plot_visibility_record_metadata(sequence, position, plot_word, *, record_type, metadata_flag, thread_hook_present, writer_metadata_callback_present, queue_callback_result, padding_policy):
    verify_source_evidence()
    if type(record_type) is not int or record_type not in (118, 140):
        raise ValueError('Unverified plot visibility record type')
    if type(metadata_flag) is not int or metadata_flag not in (0, 32, 64) or (record_type != 118 and metadata_flag != 0):
        raise ValueError('Scoped metadata is verified only for FeatureVisibilityChanged')
    if thread_hook_present is not False or writer_metadata_callback_present is not False:
        raise ValueError('FeatureVisibilityChanged registered callbacks are not modeled')
    if type(sequence) is not int or not 1 <= sequence <= 4294967295:
        raise ValueError('Sequence must be a nonzero uint32')
    if padding_policy != 'zero':
        raise ValueError('Only explicit zero padding is supported')
    if type(queue_callback_result) is not int or queue_callback_result != 0:
        raise ValueError('Only the source-proven null queue-callback result is supported')
    if type(position.get('x')) is not int or type(position.get('y')) is not int or type(position.get('descriptor_tail')) is not int or (type(position.get('position_bytes')) is not bytes) or (len(position['position_bytes']) != 8):
        raise ValueError('Unverified 0x878CD252 descriptor')
    if struct.unpack('<ii', position['position_bytes']) != (position['x'], position['y']):
        raise ValueError('Position bytes disagree with decoded coordinates')
    if not 0 <= position['descriptor_tail'] <= 4294967295:
        raise ValueError('Unverified descriptor-tail value')
    if type(position.get('metadata_pair_bytes')) is not bytes or len(position['metadata_pair_bytes']) != 8:
        raise ValueError('Unverified FeatureVisibilityChanged metadata pair')
    if type(plot_word) is not int or not -32768 <= plot_word <= 32767:
        raise ValueError('Plot query result must be a signed native int16')
    metadata = bytearray(METADATA_SIZE)
    struct.pack_into('<IIHHI', metadata, 0, 4294967295, 4294967295, 65535, 0, 4294967295)
    for offset in (16, 24, 32, 40):
        struct.pack_into('<HHI', metadata, offset, 65535, 0, 4294967295)
    struct.pack_into('<Q', metadata, 48, 0)
    struct.pack_into('<I', metadata, 56, metadata_flag)
    payload = bytearray(PAYLOAD_SIZE)
    payload[8:16] = position['position_bytes']
    struct.pack_into('<I', payload, 16, position['descriptor_tail'])
    struct.pack_into('<II', payload, 20, 4294957297, 4294957297)
    struct.pack_into('<I', payload, 28, 0)
    payload[32:40] = position['metadata_pair_bytes']
    struct.pack_into('<i', payload, 40, plot_word)
    record = bytearray(RECORD_SIZE)
    struct.pack_into('<IIII', record, 0, RECORD_SIZE, record_type, sequence, queue_callback_result)
    record[16:16 + METADATA_SIZE] = metadata
    record[80:80 + PAYLOAD_SIZE] = payload
    struct.pack_into('<I', record, 80, sequence)
    return bytes(record)
