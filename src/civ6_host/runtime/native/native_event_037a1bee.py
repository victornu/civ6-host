"""Source-bounded037A1BEE optional map query and retained plot snapshot."""
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
from contextlib import contextmanager
from pathlib import Path
import struct
from civ6_host.runtime.native import native_event_07c83dae as snapshot
from civ6_host.runtime.native.native_application_mirror import decode_scalar
from civ6_host.runtime.native.native_feature_visibility_event import _copy_blob
from civ6_host.runtime.native.native_source_cache import load_pinned_json
from civ6_host.runtime.native.native_event_827289e6 import query_optional_position
EVENT_KIND, RECORD_TYPE, RECORD_SIZE = (58334190, 167, 144)
_BASIC_KEYS = {2353434172, 2716180809, 3606901732}
_EXTENDED_KEYS = _BASIC_KEYS | {2717631346, 1532339015, 955421384, 4033489650}
_QUERY_FIELDS = {'position_bytes', 'x', 'y', 'selector', 'source_value', 'descriptor_tail'}
_OPTIONAL_FIELDS = {'input_shape', 'optional_index', 'optional_scalar', 'ignored_player', 'metadata_pair_bytes', 'optional_fields_absent'}
_DEFAULT_PAIR = bytes.fromhex('ffff0000ffffffff')
PINNED_EVIDENCE_SHA256 = 'ee659698dda0f3800d6fc433f5970493f374175adec54dcbeb388dd655f5877c'
_PROOF = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_event_037a1bee.py')))).resolve().parents[1] / 'evidence/native-event-037a1bee' / f'{PINNED_EVIDENCE_SHA256}.json'
POSITIVE_PROOF_SHA256 = '64b5d5ce36617509357b4faba034f6190eb1b9451cd798a9746e63e4a060489e'
_POSITIVE_PROOF = _PROOF.parents[1] / 'native-event-037a1bee-positive' / f'{POSITIVE_PROOF_SHA256}.json'

def verify_source_evidence():
    proof = load_pinned_json(_PROOF, PINNED_EVIDENCE_SHA256)
    if proof['schema'] != 'civ6rl.native_event_037a1bee.static.v2' or proof['registration']['callback_va'] != '0x140140c50' or proof['images']['exe_sha256'] != snapshot.shared.EXE_SHA256 or (proof['images']['core_sha256'] != snapshot.shared.CORE_SHA256) or (proof['shared_plot_snapshot']['sha256'] != snapshot.PINNED_EVIDENCE_SHA256) or (proof['contract']['record']['type'] != '0xa7'):
        raise RuntimeError('037A1BEE source identity changed')
    return proof

def verify_positive_source_evidence():
    """The addendum also pins the plot lifetime on every producer branch."""
    proof = load_pinned_json(_POSITIVE_PROOF, POSITIVE_PROOF_SHA256)
    if proof.get('schema') != 'civ6rl.native_event_037a1bee_positive.static.v1' or proof.get('images') != {'exe_sha256': snapshot.shared.EXE_SHA256, 'core_sha256': snapshot.shared.CORE_SHA256} or proof['sources']['037a_v2']['sha256'] != PINNED_EVIDENCE_SHA256 or (proof['sources']['positive_query']['sha256'] != '1881a3beb1d4e9038871d20905ee19b2dc1da6b67db06efc61a29bd961a84292') or (proof['contract']['record_changes'] != {'optional_position8_at_record': 124, 'pair5B55_8_at_record': 136, 'scalar38F_dword_at_record': 132}) or any((proof['callback_instruction_guards'].get(va) != text for va, text in {'0x140140d03': 'call 0x140147f10', '0x140140f00': 'call 0x140135f30', '0x140140f1d': 'call 0x1409898c0', '0x140140f2d': 'call qword ptr [rax + 8]'}.items())):
        raise RuntimeError('Pinned037A1BEE optional query or enqueue/plot-release order changed')

def decode_fields(raw_fields, read):
    verify_source_evidence()
    if not isinstance(raw_fields, dict) or set(raw_fields) not in (_BASIC_KEYS, _EXTENDED_KEYS):
        raise ValueError('037A1BEE admits exact three/seven fields; partial optional fields are refused')
    extended = set(raw_fields) == _EXTENDED_KEYS
    selector = decode_scalar(raw_fields[2716180809], 3)
    value = decode_scalar(raw_fields[3606901732], 2)
    raw_position = raw_fields[2353434172]
    if type(raw_position) is not bytes or len(raw_position) != 24 or struct.unpack_from('<H', raw_position)[0] not in (0, 13):
        raise ValueError('037A1BEE position requires the source tag0/tagD blob envelope')
    position = _copy_blob(raw_position, read, struct.unpack_from('<H', raw_position)[0])
    x, y = struct.unpack('<ii', position)
    result = dict(position_bytes=position, x=x, y=y, selector=selector, source_value=0, descriptor_tail=value, input_shape='extended-seven-field' if extended else 'basic-three-field', optional_fields_absent=not extended, optional_index=decode_scalar(raw_fields[2717631346], 2) if extended else None, optional_scalar=decode_scalar(raw_fields[955421384], 2) if extended else None, ignored_player=decode_scalar(raw_fields[4033489650], 2) if extended else None, metadata_pair_bytes=_copy_blob(raw_fields[1532339015], read, 1024) if extended else _DEFAULT_PAIR)
    _query_fields(result)
    return result

def _query_fields(fields):
    if not isinstance(fields, dict) or set(fields) != _QUERY_FIELDS | _OPTIONAL_FIELDS:
        raise ValueError('037A1BEE decoded fields are incomplete')
    query = {key: fields[key] for key in _QUERY_FIELDS}
    snapshot._fields(query)
    if fields['source_value'] != 0 or type(fields['metadata_pair_bytes']) is not bytes or len(fields['metadata_pair_bytes']) != 8:
        raise ValueError('037A1BEE internal placeholder or optional pair changed')
    optional = [fields[key] for key in ('optional_index', 'optional_scalar', 'ignored_player')]
    if fields['input_shape'] == 'basic-three-field':
        if fields['optional_fields_absent'] is not True or fields['metadata_pair_bytes'] != _DEFAULT_PAIR or any((v is not None for v in optional)):
            raise ValueError('037A1BEE basic input cannot inject optional fields')
    elif fields['input_shape'] == 'extended-seven-field':
        if fields['optional_fields_absent'] is not False or any((type(v) is not int or not 0 <= v <= 4294967295 for v in optional)):
            raise ValueError('037A1BEE extended input requires typed optional DWORDs')
    else:
        raise ValueError('037A1BEE input shape is not source-backed')
    return query

def _profile(sequence, fields, notification_counter, normalizer_transform_present, thread_hook_present, writer_metadata_callback_present, padding_policy):
    verify_source_evidence()
    verify_positive_source_evidence()
    _query_fields(fields)
    if type(notification_counter) is not int or notification_counter != 0:
        raise ValueError('037A1BEE nonzero notification counter metadata state is not modeled')
    if normalizer_transform_present is not False or thread_hook_present is not False or writer_metadata_callback_present is not False:
        raise ValueError('037A1BEE requires explicitly absent transforms/hooks/metadata callbacks')
    if type(sequence) is not int or not 1 <= sequence <= 4294967295:
        raise ValueError('037A1BEE requires a nonzero uint32 sequence')
    if padding_policy != 'zero':
        raise ValueError('037A1BEE requires explicit zero source stack padding')

def encode_record(sequence, fields, values, *, notification_counter, normalizer_transform_present, thread_hook_present, writer_metadata_callback_present, padding_policy, optional_position_bytes=None):
    _profile(sequence, fields, notification_counter, normalizer_transform_present, thread_hook_present, writer_metadata_callback_present, padding_policy)
    ranges = {'owner': (-128, 127), 'city_id': (0, 4294967295), 'district_id': (0, 4294967295), 'flag148': (0, 255)}
    if not isinstance(values, dict) or set(values) != set(ranges):
        raise ValueError('037A1BEE needs all native snapshot/flag values')
    for name, (low, high) in ranges.items():
        if type(values[name]) is not int or not low <= values[name] <= high:
            raise ValueError('Invalid037A1BEE native query value: ' + name)
    positive = fields['optional_index'] is not None and fields['optional_index'] < 2147483648
    if positive:
        if type(optional_position_bytes) is not bytes or len(optional_position_bytes) != 8:
            raise ValueError('037A1BEE positive index requires the exact native optional position')
        optional_scalar = fields['optional_scalar']
    else:
        if optional_position_bytes is not None:
            raise ValueError('037A1BEE absent or negative index cannot inject optional position')
        optional_position_bytes = struct.pack('<ii', -9999, -9999)
        optional_scalar = 0
    record = bytearray(RECORD_SIZE)
    struct.pack_into('<IIII', record, 0, RECORD_SIZE, RECORD_TYPE, sequence, 0)
    record[16:24] = b'\xff' * 8
    record[24:64] = bytes.fromhex('ffff0000ffffffff') * 5
    struct.pack_into('<I', record, 80, sequence)
    record[88:96] = fields['position_bytes']
    struct.pack_into('<HHI', record, 96, values['owner'] & 65535, 2, values['city_id'])
    struct.pack_into('<HHI', record, 104, values['owner'] & 65535, 3, values['district_id'])
    record[112] = values['flag148']
    struct.pack_into('<II', record, 116, fields['selector'], fields['descriptor_tail'])
    record[124:132] = optional_position_bytes
    struct.pack_into('<I', record, 132, optional_scalar)
    record[136:144] = fields['metadata_pair_bytes']
    return bytes(record)

@contextmanager
def produce_record_lease(sequence, core, context, fields, *, notification_counter, normalizer_transform_present, thread_hook_present, writer_metadata_callback_present, padding_policy='zero', read=None, native_api=None, optional_native_api=None, core_sha256='d7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'):
    """Run the optional query before178/148; retain the plot through enqueue.

    Absent or signed-negative A1FBC retains position/scalar sentinels without
    an optional native query; a present5B55 pair is copied independently. The
    positive helper completes its own map lease before the shared plot route.
    EXE140F00/140F1D append and unlock before plot release140F2D.
    """
    if core_sha256 not in ('d7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3', '259b90a473a256aff6a7d621a4f3717e46f6921c59b9817475375c88b97e8c83', '324c51e9ea3531758842e16c69e6cddbefbb226c5b675c3d6e60111646c2e98c'):
        raise ValueError('Unqualified facade engine')
    profile = dict(notification_counter=notification_counter, normalizer_transform_present=normalizer_transform_present, thread_hook_present=thread_hook_present, writer_metadata_callback_present=writer_metadata_callback_present, padding_policy=padding_policy)
    _profile(sequence, fields, **profile)
    optional_position = None
    index = fields['optional_index']
    if index is not None and index < 2147483648:
        optional_position = query_optional_position(core, context, index, read=read, native_api=optional_native_api, core_sha256=core_sha256)
        if type(optional_position) is not bytes or len(optional_position) != 8:
            raise ValueError('037A1BEE requires the complete native optional position')
    with snapshot.plot_snapshot(core, context, _query_fields(fields), read=read, native_api=native_api, core_sha256=core_sha256) as values:
        yield encode_record(sequence, fields, values, optional_position_bytes=optional_position, **profile)

def produce_record(*args, **kwargs):
    """Standalone diagnostic wrapper; dispatchers must use the retained lease."""
    with produce_record_lease(*args, **kwargs) as record:
        return record
