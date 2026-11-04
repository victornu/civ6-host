"""Source-backed ResourceVisibilityChanged producer for the witnessed shape."""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import struct
from pathlib import Path
from civ6_host.runtime.native.native_application_mirror import decode_scalar
from civ6_host.runtime.native.native_feature_visibility_event import _copy_blob
from civ6_host.runtime.native.native_feature_visibility_event import _encode_plot_visibility_record
from civ6_host.runtime.native.native_feature_visibility_event import _query_plot_snapshot_word
from civ6_host.runtime.native.native_event_827289e6 import query_optional_position
from civ6_host.runtime.native.native_source_cache import load_pinned_json
EVENT_KIND, RECORD_TYPE, RECORD_SIZE = (2599060777, 140, 128)
BLOB_KEY, SELECTOR_KEY, TAIL_KEY = (2353434172, 2716180809, 3606901732)
_PROOF_SHA = 'c43b86b6839394f04ef25533b9f6d9a27257a20371da77b952820edb376a358d'
_PROOF = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_event_9aea8529.py')))).resolve().parents[1] / 'evidence/native-event-9aea8529' / f'{_PROOF_SHA}.json'
_DEFAULT_PAIR = struct.pack('<HHI', 65535, 0, 4294967295)
OPTIONAL_VALUE_KEY, OPTIONAL_PAIR_KEY = (2717631346, 1532339015)
OPTIONAL_SCALAR_KEY, IGNORED_PLAYER_KEY = (955421384, 4033489650)
SCOPE_PROOF_SHA256 = '0204c913930ee00a0cdbb39e52f58e3141718bd0d2cdf30717b13ff269d35ee4'
_BASIC_KEYS = {BLOB_KEY, SELECTOR_KEY, TAIL_KEY}
_EXTENDED_KEYS = _BASIC_KEYS | {OPTIONAL_VALUE_KEY, OPTIONAL_PAIR_KEY, OPTIONAL_SCALAR_KEY, IGNORED_PLAYER_KEY}

def verify_scoped_source_evidence() -> None:
    proof = load_pinned_json(_resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_event_9aea8529.py')))).resolve().parents[1] / 'evidence/native-resource-visibility-positive-scope-v2' / (SCOPE_PROOF_SHA256 + '.json'), SCOPE_PROOF_SHA256)
    if proof.get('schema') != 'civ6rl.native_resource_visibility_scope_positive.static.v1' or proof['receiver_profile']['record_type'] != RECORD_TYPE or proof['receiver_profile']['size'] != RECORD_SIZE or (proof['captures']['callback']['raw_sha256'] != '1efd35a4c0ec437310e0b13f98e3cf4ad4fb2f1a499711249204da6c7701ec63') or (proof['contract']['N_address'] != '0x1422d7c6c') or (proof['contract']['M_address'] != '0x1422d7c68') or (proof['contract']['N_and_M_unsigned_uint32'] is not True):
        raise RuntimeError('Pinned ResourceVisibilityChanged scope changed')

def verify_source_evidence() -> None:
    proof = load_pinned_json(_PROOF, _PROOF_SHA)
    if proof.get('schema') != 'civ6rl.native_event_9aea8529.static.v2' or proof['images']['exe_sha256'] != 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63' or proof['images']['core_sha256'] != 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3' or (proof['registration']['callback_va'] != '0x140152300') or (proof['captures']['callback']['raw_sha256'] != '1efd35a4c0ec437310e0b13f98e3cf4ad4fb2f1a499711249204da6c7701ec63') or (proof['captures']['writer']['raw_sha256'] != 'a708e7376ec98914798c9ebd4de515f996f5b742af6bbba08da530cf10c5b462') or (proof['captures']['query']['raw_sha256'] != '7a937a6e0b18883da97b99ea7f44ef58370cfe38e1428a093d392e3b9abf5acd'):
        raise RuntimeError('Pinned 9AEA8529 callback/writer/query identity changed')
    if proof['optional_query_extension']['shared_map_query_pin'] != '30a78ad61e21b0003de294a0fbd787402835d29a9a89e7bf441418087a39fab1':
        raise RuntimeError('Pinned9AEA8529 optional query source changed')

def decode_fields(fields: dict[int, bytes], read) -> dict:
    """Decode exactly the source-backed three-key or seven-key envelopes."""
    verify_source_evidence()
    if not isinstance(fields, dict) or set(fields) not in (_BASIC_KEYS, _EXTENDED_KEYS):
        raise ValueError('Unverified 9AEA8529 field set or partial optional fields')
    extended = set(fields) == _EXTENDED_KEYS
    selector = decode_scalar(fields[SELECTOR_KEY], 3)
    tail = decode_scalar(fields[TAIL_KEY], 2)
    position = _copy_blob(fields[BLOB_KEY], read, 13 if extended else 0)
    x, y = struct.unpack('<ii', position)
    return {'position_bytes': position, 'x': x, 'y': y, 'selector': selector, 'descriptor_tail': tail, 'metadata_pair_bytes': _copy_blob(fields[OPTIONAL_PAIR_KEY], read, 1024) if extended else _DEFAULT_PAIR, 'input_shape': 'extended-seven-field' if extended else 'basic-three-field', 'optional_index': decode_scalar(fields[OPTIONAL_VALUE_KEY], 2) if extended else None, 'optional_scalar': decode_scalar(fields[OPTIONAL_SCALAR_KEY], 2) if extended else 0, 'ignored_player': decode_scalar(fields[IGNORED_PLAYER_KEY], 2) if extended else None}

def _validate_position(position: dict) -> None:
    if not isinstance(position, dict) or type(position.get('position_bytes')) is not bytes or len(position['position_bytes']) != 8 or (type(position.get('x')) is not int) or (type(position.get('y')) is not int) or (struct.unpack('<ii', position['position_bytes']) != (position['x'], position['y'])) or (type(position.get('selector')) is not int) or (not 0 <= position['selector'] <= 4294967295) or (type(position.get('metadata_pair_bytes')) is not bytes) or (len(position['metadata_pair_bytes']) != 8):
        raise ValueError('Unverified 9AEA8529 decoded position or metadata pair')
    if position.get('input_shape') == 'basic-three-field':
        if position['metadata_pair_bytes'] != _DEFAULT_PAIR or position.get('optional_index') is not None or position.get('ignored_player') is not None or (type(position.get('optional_scalar')) is not int) or (position['optional_scalar'] != 0):
            raise ValueError('9AEA8529 basic shape cannot inject optional values')
    elif position.get('input_shape') == 'extended-seven-field':
        if any((type(position.get(key)) is not int or not 0 <= position[key] <= 4294967295 for key in ('optional_index', 'optional_scalar', 'ignored_player'))):
            raise ValueError('9AEA8529 extended shape requires all typed optional DWORDs')
    else:
        raise ValueError('9AEA8529 input shape is not source-backed')

def query_plot_word(core, context, position: dict, *, read=None, native_api=None, core_sha256='d7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3') -> int:
    """Use EXE147C10's signed snapshot WORD+4 through owned Core wrappers."""
    if core_sha256 not in ('d7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3', '259b90a473a256aff6a7d621a4f3717e46f6921c59b9817475375c88b97e8c83', '324c51e9ea3531758842e16c69e6cddbefbb226c5b675c3d6e60111646c2e98c'):
        raise ValueError('Unqualified facade engine')
    verify_source_evidence()
    _validate_position(position)
    return _query_plot_snapshot_word(core, context, position, word_offset=4, read=read, native_api=native_api, core_sha256=core_sha256)

def encode_record(sequence: int, position: dict, plot_word: int, *, notification_counter: int, thread_hook_present: bool, writer_metadata_callback_present: bool, padding_policy: str, core=None, context=None, read=None, optional_native_api=None, core_sha256='d7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3') -> bytes:
    """Encode only the counter-zero profile with explicitly absent callbacks.

    The exact source writes match the shared type76 byte layout. This API fixes
    type8C and requires the producer-specific decoded input and native result.
    Source padding is zeroed only under the explicit ``zero`` policy. The caller
    obtains plot_word first through query_plot_word, matching147C10 before147F10.
    Positive optional indices require live Core/context and invoke the same
    guarded map+68 query as827289E6; negative/absent indices make no such call.
    """
    if core_sha256 not in ('d7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3', '259b90a473a256aff6a7d621a4f3717e46f6921c59b9817475375c88b97e8c83', '324c51e9ea3531758842e16c69e6cddbefbb226c5b675c3d6e60111646c2e98c'):
        raise ValueError('Unqualified facade engine')
    verify_source_evidence()
    _validate_position(position)
    record = _encode_plot_visibility_record(sequence, position, plot_word, record_type=RECORD_TYPE, notification_counter=notification_counter, thread_hook_present=thread_hook_present, writer_metadata_callback_present=writer_metadata_callback_present, queue_callback_result=0, padding_policy=padding_policy)
    index = position['optional_index']
    if index is None or index >= 2147483648:
        return record
    queried = query_optional_position(core, context, index, read=read, native_api=optional_native_api, core_sha256=core_sha256)
    record = bytearray(record)
    record[100:108] = queried
    struct.pack_into('<I', record, 108, position['optional_scalar'])
    return bytes(record)

def encode_scoped_record(sequence: int, position: dict, plot_word: int, *, notification_counter: int, metadata_counter: int, thread_hook_present: bool, writer_metadata_callback_present: bool, padding_policy: str, core=None, context=None, read=None, optional_native_api=None, core_sha256='d7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3') -> tuple[bytes, int]:
    """Preserve the proven layout/query path, then apply this producer's flag.

    The zero below selects the existing default byte formatter, not an assumed
    live counter value. Only record+48 changes; live N/M govern that source-proven
    transformation. Query lifetimes and optional data remain unchanged.
    """
    if core_sha256 not in ('d7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3', '259b90a473a256aff6a7d621a4f3717e46f6921c59b9817475375c88b97e8c83', '324c51e9ea3531758842e16c69e6cddbefbb226c5b675c3d6e60111646c2e98c'):
        raise ValueError('Unqualified facade engine')
    verify_scoped_source_evidence()
    from civ6_host.runtime.native.native_notification_metadata import metadata_scope_transition
    flag, after = metadata_scope_transition(notification_counter, metadata_counter)
    record = bytearray(encode_record(sequence, position, plot_word, notification_counter=0, thread_hook_present=thread_hook_present, writer_metadata_callback_present=writer_metadata_callback_present, padding_policy=padding_policy, core=core, context=context, read=read, optional_native_api=optional_native_api, core_sha256=core_sha256))
    struct.pack_into('<I', record, 72, flag)
    return (bytes(record), after)
__all__ = ['EVENT_KIND', 'RECORD_TYPE', 'decode_fields', 'query_plot_word', 'encode_record', 'verify_source_evidence', 'encode_scoped_record', 'verify_scoped_source_evidence', 'SCOPE_PROOF_SHA256']
