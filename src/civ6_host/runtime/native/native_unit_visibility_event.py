"""Source-bounded C1300EE7 producer for the empty EXE receiver profile."""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import struct
from pathlib import Path
from civ6_host.runtime.native.native_application_mirror import decode_scalar
from civ6_host.runtime.native.native_event_827289e6 import query_optional_position
from civ6_host.runtime.native.native_source_cache import load_pinned_json
EVENT_KIND = 3241152231
RECORD_TYPE, RECORD_SIZE = (36, 128)
ENTITY_KEY = 4032072631
METADATA_KEY = 1532339015
SELECTOR_KEY = 2716180809
VALUE_KEY = 3606901732
OPTIONAL_VALUE_KEY = 2717631346
IGNORED_SCALAR_KEY = 955421384
IGNORED_PLAYER_KEY = 4033489650
BOOLEAN_KEY = 115367927
_KEYS = frozenset((ENTITY_KEY, METADATA_KEY, SELECTOR_KEY, VALUE_KEY, OPTIONAL_VALUE_KEY, IGNORED_SCALAR_KEY, IGNORED_PLAYER_KEY))
_SHORT_KEYS = frozenset((ENTITY_KEY, SELECTOR_KEY, VALUE_KEY))
_BOOLEAN_KEYS = _SHORT_KEYS | {BOOLEAN_KEY}
_PROOF_SHA = '63b43ca010314b487415470e7e026198791820b73a85c6804a9edefb9ca105ac'
POSITIVE_PROOF_SHA256 = 'a27fe2a983fd0c2bca6fca62d68e4d7a85aa2e91f7869db381adcc3a5c9204ec'
SCOPE_PROOF_SHA256 = 'f7d4c02f5b39f9932ef3483793c64e97aca58edb14db61bf43a79999fb78fdad'
_PROOF = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_unit_visibility_event.py')))).resolve().parents[1] / 'evidence/native-event-c1300ee7' / f'{_PROOF_SHA}.json'
_POSITIVE_PROOF = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_unit_visibility_event.py')))).resolve().parents[1] / 'evidence/native-event-c1300ee7-positive' / f'{POSITIVE_PROOF_SHA256}.json'

def verify_source_evidence() -> None:
    proof = load_pinned_json(_PROOF, _PROOF_SHA)
    if proof.get('schema') != 'civ6rl.native_event_c1300ee7.static.v3' or proof['registration']['callback_va'] != '0x140159190' or proof['images']['exe_sha256'] != 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63' or (proof['captures']['callback']['raw_sha256'] != '01867bc25f698e48ac3d1a0bb5b6a17f70904d9a933ecefb0b408af4c4bd3ca6') or (proof['captures']['writer']['raw_sha256'] != 'a0c440e95633cea2b57378e5a4cc208d9a5e77cabc1b657d93a2b11ee5b11dc1') or (proof['source_instruction_guards']['optional_value_lookup']['0x140147f38'] != 'je 0x140147f68') or (proof['source_instruction_guards']['callback']['0x1401592c7'] != 'je 0x1401592f2') or (proof['captures']['optional_boolean_conversion']['reachable_bytes_sha256'] != 'b34992484176208cbb449f2b79c3320d50d867a8fc2318aea9cada02ac34c218') or (proof['source_instruction_guards']['callback']['0x1401592a2'] != 'mov byte ptr [rbp + 0xf], al'):
        raise RuntimeError('Pinned C1300EE7 source identity changed')
    positive = load_pinned_json(_POSITIVE_PROOF, POSITIVE_PROOF_SHA256)
    if positive.get('schema') != 'civ6rl.native_event_c1300ee7_positive.static.v1' or positive['images']['exe_sha256'] != 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63' or positive['images']['core_sha256'] != 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3' or (positive['registration']['callback_va'] != '0x140159190') or (positive['contract']['record_type'] != 36) or (positive['contract']['record_changes']['optional_position8_at_record'] != 100) or (positive['contract']['record_changes']['scalar38F_dword_at_record'] != 108) or (positive['contract']['reuse'] != 'Use query_optional_position from827 with a fresh native map acquisition for each positive callback. No separate item/plot query or lease exists in these two callbacks. Preserve each existing codec metadata, descriptor, mode,boolean and padding behavior; only replace optional coordinate/scalar outputs.'):
        raise RuntimeError('Pinned C1300EE7 positive-query proof identity changed')

def verify_scoped_source_evidence() -> None:
    proof = load_pinned_json(_resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_unit_visibility_event.py')))).resolve().parents[1] / 'evidence/native-unit-visibility-scope' / (SCOPE_PROOF_SHA256 + '.json'), SCOPE_PROOF_SHA256)
    if proof['schema'] != 'civ6rl.native_unit_visibility_scope.static.v1' or proof['kind'] != EVENT_KIND or proof['contract']['record_type'] != RECORD_TYPE or (proof['contract']['record_size'] != RECORD_SIZE) or (proof['contract']['record_flag_offset'] != 72) or (proof['contract']['state_domain'] != 'uint32-exact-int') or (proof['contract']['N_address'] != '0x1422d7c6c') or (proof['contract']['M_address'] != '0x1422d7c68') or (proof['captures']['callback']['raw_sha256'] != '01867bc25f698e48ac3d1a0bb5b6a17f70904d9a933ecefb0b408af4c4bd3ca6'):
        raise RuntimeError('UnitVisibilityChanged metadata scope source changed')

def _blob8(raw, read):
    if not isinstance(raw, (bytes, bytearray, memoryview)) or len(raw) != 24:
        raise ValueError('Incomplete C1300EE7 blob variant')
    tag = struct.unpack_from('<H', raw)[0]
    pointer, size, flags = struct.unpack_from('<QII', raw, 8)
    if tag != 1024 or not pointer or size != 8 or (flags != 553648129):
        raise ValueError('Unverified C1300EE7 blob envelope')
    result = read(pointer, 8)
    if not isinstance(result, (bytes, bytearray, memoryview)) or len(result) != 8:
        raise ValueError('Incomplete C1300EE7 pointed value')
    return bytes(result)

def decode_fields(raw_fields: dict[int, bytes], read) -> dict:
    """Preserve native owner/id and metadata pair under exact typed input keys."""
    verify_source_evidence()
    if not isinstance(raw_fields, dict) or set(raw_fields) not in (_KEYS, _SHORT_KEYS, _BOOLEAN_KEYS):
        raise ValueError('Unverified C1300EE7 input keys or optional boolean query present')
    selector = decode_scalar(raw_fields[SELECTOR_KEY], 3)
    value = decode_scalar(raw_fields[VALUE_KEY], 2)
    optional = ignored_scalar = ignored_player = None
    raw_boolean_byte = 0
    boolean_present = BOOLEAN_KEY in raw_fields
    if boolean_present:
        raw = raw_fields[BOOLEAN_KEY]
        if not isinstance(raw, (bytes, bytearray, memoryview)) or len(raw) != 24 or struct.unpack_from('<H', raw)[0] != 1 or (struct.unpack_from('<I', raw, 20)[0] != 0):
            raise ValueError('C1300EE7 optional boolean requires direct tag1 with zero flags')
        raw_boolean_byte = raw[8]
    if OPTIONAL_VALUE_KEY in raw_fields:
        optional = decode_scalar(raw_fields[OPTIONAL_VALUE_KEY], 2)
        ignored_scalar = decode_scalar(raw_fields[IGNORED_SCALAR_KEY], 2)
        ignored_player = decode_scalar(raw_fields[IGNORED_PLAYER_KEY], 2)
    entity = _blob8(raw_fields[ENTITY_KEY], read)
    owner, source_type, identifier = struct.unpack('<HHI', entity)
    pair = _blob8(raw_fields[METADATA_KEY], read) if METADATA_KEY in raw_fields else struct.pack('<HHI', 65535, 0, 4294967295)
    return {'owner': owner, 'identifier': identifier, 'normalized_type': 1, 'source_entity_type': source_type, 'source_entity_bytes': entity, 'metadata_pair_bytes': pair, 'selector': selector, 'source_value': value, 'callback_mode': 2 if value == 2 else 0, 'optional_value': optional, 'ignored_scalar': ignored_scalar, 'ignored_player': ignored_player, 'raw_boolean_byte': raw_boolean_byte, 'optional_boolean_present': boolean_present, 'input_profile': 'four-key-direct-boolean' if boolean_present else 'seven-key-positive-optional' if optional is not None and optional < 2147483648 else 'seven-key-negative-optional' if optional is not None else 'three-key-absent-optional'}

def encode_record(sequence: int, raw_fields: dict[int, bytes], read, *, notification_counter: int, entity_listener_count: int, thread_hook_present: bool, writer_metadata_callback_present: bool, padding_policy: str, core=None, context=None, optional_native_api=None, core_sha256='d7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3') -> bytes:
    """Produce type0x24 with explicitly absent callbacks and counter zero.

    Empty entity listeners are needed before the callback, in the normalizer.
    Key06E05FF7 is either absent, retaining initialized zero, or an explicit
    direct tag1 byte in the four-key profile. Metadata counter effects and all
    registered callback paths are refused. Short profiles bypass147F10 through
    its missing-raw-A1FBC exit. Seven-key profiles call the source map query
    only for nonnegative A1FBC values; negative values retain native defaults.
    """
    verify_source_evidence()
    if type(notification_counter) is not int or notification_counter != 0:
        raise ValueError('C1300EE7 nonzero notification counter is not modeled')
    if type(entity_listener_count) is not int or entity_listener_count != 0:
        raise ValueError('C1300EE7 requires the explicit empty entity-listener profile')
    if thread_hook_present is not False or writer_metadata_callback_present is not False:
        raise ValueError('C1300EE7 registered native callbacks are not modeled')
    if type(sequence) is not int or not 1 <= sequence <= 2147483647:
        raise ValueError('C1300EE7 sequence must be a bounded positive integer')
    if padding_policy != 'headless-zero-initialization':
        raise ValueError('C1300EE7 requires an explicit source-stack padding policy')
    fields = decode_fields(raw_fields, read)
    record = bytearray(RECORD_SIZE)
    struct.pack_into('<IIII', record, 0, RECORD_SIZE, RECORD_TYPE, sequence, 0)
    struct.pack_into('<II', record, 16, 4294967295, 4294967295)
    struct.pack_into('<HHI', record, 24, fields['owner'], 1, fields['identifier'])
    for offset in (32, 40, 48, 56):
        struct.pack_into('<HHI', record, offset, 65535, 0, 4294967295)
    struct.pack_into('<I', record, 80, sequence)
    struct.pack_into('<HHI', record, 88, fields['owner'], 1, fields['identifier'])
    struct.pack_into('<IIII', record, 96, fields['callback_mode'], 4294957297, 4294957297, 0)
    if fields['optional_value'] is not None and fields['optional_value'] < 2147483648:
        position = query_optional_position(core, context, fields['optional_value'], read=read, native_api=optional_native_api, core_sha256=core_sha256)
        if type(position) is not bytes or len(position) != 8:
            raise ValueError('C1300EE7 requires the complete native optional position')
        record[100:108] = position
        struct.pack_into('<I', record, 108, fields['ignored_scalar'])
    record[112:120] = fields['metadata_pair_bytes']
    record[120] = fields['raw_boolean_byte']
    return bytes(record)

def encode_scoped_record(sequence, raw_fields, read, *, notification_counter, metadata_counter, entity_listener_count, thread_hook_present, writer_metadata_callback_present, padding_policy, core=None, context=None, optional_native_api=None, core_sha256='d7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'):
    """Apply this callback's proven N/M flag to its existing byte/query path.

    The formatter's zero selects default metadata bytes; it is not the live N.
    Actual N/M determine flag and next M before query, as in the native callback.
    The owner commits M after enqueue only in the nonreentrant fatal-on-failure
    diagnostic profile. No hook or native query behavior is replaced.
    """
    verify_scoped_source_evidence()
    from civ6_host.runtime.native.native_notification_metadata import metadata_scope_transition
    flag, after = metadata_scope_transition(notification_counter, metadata_counter)
    record = bytearray(encode_record(sequence, raw_fields, read, notification_counter=0, entity_listener_count=entity_listener_count, thread_hook_present=thread_hook_present, writer_metadata_callback_present=writer_metadata_callback_present, padding_policy=padding_policy, core=core, context=context, optional_native_api=optional_native_api, core_sha256=core_sha256))
    struct.pack_into('<I', record, 72, flag)
    return (bytes(record), after)
__all__ = ['EVENT_KIND', 'RECORD_TYPE', 'POSITIVE_PROOF_SHA256', 'decode_fields', 'encode_record', 'query_optional_position', 'verify_source_evidence', 'encode_scoped_record', 'verify_scoped_source_evidence', 'SCOPE_PROOF_SHA256']
