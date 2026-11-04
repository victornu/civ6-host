"""Diagnostic E66012A7/AA codec for the closed empty-receiver profile.

The codec follows the source-backed selector 0x51330671 route only. It does
not assert gameplay or UI semantics for GameCoreEvent::BuildingPillaged.
"""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
from contextlib import contextmanager
from dataclasses import dataclass
import hashlib
import struct
from pathlib import Path
from civ6_host.runtime.native import native_event_07c83dae as snapshot
from civ6_host.runtime.native.native_application_mirror import decode_scalar
from civ6_host.runtime.native.native_feature_visibility_event import _copy_blob
EVENT_KIND = 3865055911
SELECTOR = 1362298481
RECORD_TYPE, RECORD_SIZE, PAYLOAD_SIZE = (170, 128, 48)
CITY_DESCRIPTOR_TYPE, DISTRICT_DESCRIPTOR_TYPE = (2, 3)
PADDING_POLICY = 'zero-unread-empty-receiver-payload'
SOURCE_PROOF_SHA256 = 'e311488d5f7b53ee4f98b2d690577963c2ff8b3e093ee3801aa83c44de04b0ee'
DIAGNOSTIC_ONLY = True
EMPTY_STATE = dict(observer_registered=False, state_pointer_nonnull=True, pre_hook=None, post_hook=None, subscriber_count=0, state_flags=0)
SOURCE_UNINITIALIZED_LIVE_RANGES = ((4, 8), (33, 36), (41, 48))
SOURCE_UNINITIALIZED_NULL_PLOT_RANGES = ((4, 8), (32, 36), (41, 48))
_LAB = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_event_e660_building_pillaged.py')))).resolve().parents[1]
_PROOF = _LAB / 'evidence/native-event-e660-building-pillaged' / (SOURCE_PROOF_SHA256 + '.json')

@dataclass(frozen=True)
class Fields:
    position_bytes: bytes
    x: int
    y: int
    city_owner: int
    city_id: int
    selector: int
    d6_value: int
    a1fbc_value: int

@dataclass(frozen=True)
class Values:
    plot_owner: int
    district_id: int
    flag148: int

SNAPSHOT_SOURCE_ARCHIVE = (
    'work/event951/source-archive/629306721b2fa5f0c895ed6e0d0fe9bb6216ccd0c7294aa8ca7ee0b9c3c55464/native_event_07c83dae.py',
    '629306721b2fa5f0c895ed6e0d0fe9bb6216ccd0c7294aa8ca7ee0b9c3c55464',
)


def _source_path(path_from_lab: str, digest: str, kind: str) -> Path:
    if (path_from_lab, digest, kind) == ('civ6rl/native_event_07c83dae.py',
                                          SNAPSHOT_SOURCE_ARCHIVE[1], 'text'):
        path_from_lab = SNAPSHOT_SOURCE_ARCHIVE[0]
    path = _resolve_resource_path(Path(path_from_lab))
    if not path.is_absolute():
        path = _LAB / path
    return _resolve_resource_path(path).resolve()


def source_dependencies() -> dict[str, str]:
    from civ6_host.runtime.native.native_source_cache import load_pinned_json

    proof = load_pinned_json(_PROOF, SOURCE_PROOF_SHA256)
    pins = {str(_PROOF.resolve()): SOURCE_PROOF_SHA256}
    for ref in proof['sources'].values():
        digest = ref['sha256']
        path = str(_source_path(ref['path_from_lab'], digest, ref['kind']))
        if path in pins and pins[path] != digest:
            raise ValueError('Conflicting building-pillage codec source identity')
        pins[path] = digest
    return pins


def _load(path_from_lab: str, digest: str, kind: str):
    path = _source_path(path_from_lab, digest, kind)
    if kind == 'json':
        from civ6_host.runtime.native.native_source_cache import load_pinned_json
        return load_pinned_json(path, digest)
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual != digest:
        raise RuntimeError(f'AA source changed: {path_from_lab}')
    return path

def verify_source_evidence() -> dict:
    from civ6_host.runtime.native.native_source_cache import load_pinned_json
    proof = load_pinned_json(_PROOF, SOURCE_PROOF_SHA256)
    if proof.get('schema') != 'civ6rl.native_e660_building_pillaged.codec_static_proof.v2' or proof.get('event') != {'kind': EVENT_KIND, 'selector': SELECTOR, 'name': 'GameCoreEvent::BuildingPillaged', 'queue_type': RECORD_TYPE, 'record_size': RECORD_SIZE, 'payload_size': PAYLOAD_SIZE} or proof.get('images', {}).get('exe_sha256') != 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63' or (proof.get('images', {}).get('core_sha256') != 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'):
        raise RuntimeError('AA codec composite proof identity changed')
    header = proof.get('record_header_contract', {})
    if header.get('writer_va') != '0x140136400' or header.get('instruction_source_sha256') != '857f3ea9a3b6ba0accc50517306661d240577bd39f70ce642345693dad6a12ad' or header.get('source_bytes_rechecked') != 93 or (header.get('unwritten_tail') != '0x4c..0x4f is not assigned by writer body; canonical encoder leaves zero, and this is not asserted as a native store.'):
        raise RuntimeError('AA writer header contract changed')
    docs = {name: _load(ref['path_from_lab'], ref['sha256'], ref['kind']) for name, ref in proof['sources'].items()}
    witness = docs['witness399']
    failure = next((row for row in witness.get('failure_rows', []) if row.get('stage') == 'native_host_event_failed_input'), None)
    expected_raw = {'0x8c468e3c': '0000000000000000f0204fb5e80100000800000001000021', '0xa1e5a149': '030000000000000071063351000000000000000000000000', '0xa1fbc372': '0200000045575f5201000000000000000000000000000000', '0xd6fcf3e4': '020000000000000004000000000000000000000000000000'}
    if failure is None or failure.get('fields', {}).get('0x23739f42') != '00040000626f756e80214fb5e80100000800000001000021' or any((failure.get('fields', {}).get(k) != v for k, v in expected_raw.items())) or (failure.get('diagnostic_pointer_payloads', {}).get('0x8c468e3c', {}).get('bytes_hex') != '1b00000010000000') or (failure.get('diagnostic_pointer_payloads', {}).get('0x23739f42', {}).get('bytes_hex') != '0000020000000100'):
        raise RuntimeError('AA witness field envelopes or pointed values changed')
    receiver = docs['receiver552']
    writer_instructions = {ins['va']: (ins['bytes'], ins['text']) for fragment in receiver['writer_callee']['fragments'] for ins in fragment['instructions']}
    required_header_stores = {'0x1401364c2': ('83c9ff', 'or ecx, 0xffffffff'), '0x1401364c5': ('8908', 'mov dword ptr [rax], ecx'), '0x1401364c7': ('894804', 'mov dword ptr [rax + 4], ecx'), '0x1401364ca': ('66894808', 'mov word ptr [rax + 8], cx'), '0x1401364ce': ('6689700a', 'mov word ptr [rax + 0xa], si'), '0x1401364d2': ('c7400cffffffff', 'mov dword ptr [rax + 0xc], 0xffffffff'), '0x1401364d9': ('66894810', 'mov word ptr [rax + 0x10], cx'), '0x1401364dd': ('66897012', 'mov word ptr [rax + 0x12], si'), '0x1401364e1': ('c74014ffffffff', 'mov dword ptr [rax + 0x14], 0xffffffff'), '0x1401364e8': ('66894818', 'mov word ptr [rax + 0x18], cx'), '0x1401364ec': ('6689701a', 'mov word ptr [rax + 0x1a], si'), '0x1401364f0': ('c7401cffffffff', 'mov dword ptr [rax + 0x1c], 0xffffffff'), '0x1401364f7': ('66894820', 'mov word ptr [rax + 0x20], cx'), '0x1401364fb': ('66897022', 'mov word ptr [rax + 0x22], si'), '0x1401364ff': ('c74024ffffffff', 'mov dword ptr [rax + 0x24], 0xffffffff'), '0x140136506': ('66894828', 'mov word ptr [rax + 0x28], cx'), '0x14013650a': ('6689702a', 'mov word ptr [rax + 0x2a], si'), '0x14013650e': ('c7402cffffffff', 'mov dword ptr [rax + 0x2c], 0xffffffff'), '0x140136515': ('48897030', 'mov qword ptr [rax + 0x30], rsi'), '0x140136519': ('897038', 'mov dword ptr [rax + 0x38], esi')}
    if any((writer_instructions.get(va) != expected for va, expected in required_header_stores.items())):
        raise RuntimeError('AA writer metadata stores changed')
    consumer = docs['consumer555']
    producer_manifest = docs['producer551_manifest']
    producer_capture = docs['producer551_capture']
    if receiver.get('schema') != 'civ6rl.native_event_e66012a7_selector51330671_writer.static.v1' or receiver.get('branch', {}).get('selector') != '0x51330671' or receiver['branch'].get('wrapper_va') != '0x14014cdc0' or (receiver['branch'].get('writer_callee_va') != '0x140136400') or (receiver.get('instruction_bytes_rechecked') != 93) or (consumer.get('schema') != 'civ6rl.native_e660_aa_consumer.static.v1') or (consumer['receiver_row']['type'] != '0xaa') or (consumer['receiver_row']['name']['text'] != 'GameCoreEvent::BuildingPillaged') or (consumer['record_shape']['type'] != RECORD_TYPE) or (consumer['record_shape']['size'] != RECORD_SIZE) or (consumer['record_shape']['payload_offset'] != 80) or (consumer['record_shape']['payload_size'] != PAYLOAD_SIZE) or (consumer['record_shape']['writer_va'] != '0x140136400') or (tuple(consumer['record_shape']['source_writer_instruction_checks']) != ('mov dword ptr [rbx], 0x80', 'mov dword ptr [rbx + 4], 0xaa', 'movups xmmword ptr [rax], xmm0', 'movups xmmword ptr [rax + 0x10], xmm1', 'movups xmmword ptr [rax + 0x20], xmm0', 'mov dword ptr [rax], edi')) or (consumer['record_shape']['provenance'] != 'Pinned staged 552 writer body stores size/type, copies 3 x 16-byte vectors from callback payload to record+0x50, and overwrites payload DWORD 0 with sequence.') or (consumer['decision'] != 'The named AA row exists and matches typed record 0xAA/0x80. Existing empty-profile code does not admit AA. A separately reviewed admission may rely only on these exact empty-state checks; copied payload bytes are discarded/unread only under those checks. No universal padding-zero or gameplay-semantics claim.') or (producer_manifest.get('findings', {}).get('selector') != '0x51330671') or (producer_manifest.get('findings', {}).get('record_type') != '0xaa') or (producer_capture.get('validation', {}).get('native_executed') is not False) or (proof['consumer'].get('row_name') != 'GameCoreEvent::BuildingPillaged'):
        raise RuntimeError('AA receiver/consumer/producer source contract changed')
    if tuple((tuple(x) for x in proof.get('payload_contract', {}).get('source_uninitialized_live_ranges', ()))) != SOURCE_UNINITIALIZED_LIVE_RANGES or tuple((tuple(x) for x in proof['payload_contract'].get('source_uninitialized_null_plot_ranges', ()))) != SOURCE_UNINITIALIZED_NULL_PLOT_RANGES or proof['payload_contract'].get('zero_uninitialized_only_under_closed_empty_receiver') is not True or (proof['payload_contract'].get('admitted_plot_profile') != 'non-null map and plot only; snapshot helper refuses null and emits no replacement record'):
        raise RuntimeError('AA source padding/null-plot constraints changed')
    helper = docs['snapshot_helper']
    if hashlib.sha256(_resolve_resource_path(helper).read_bytes()).hexdigest() != proof['snapshot_helper']['sha256']:
        raise RuntimeError('AA snapshot helper pin changed')
    snapshot.verify_source_evidence()
    return {'proof_sha256': SOURCE_PROOF_SHA256, 'exe_sha256': proof['images']['exe_sha256'], 'core_sha256': proof['images']['core_sha256'], 'source_hashes': {name: ref['sha256'] for name, ref in proof['sources'].items()}}

def _scalar(raw, tag: int, label: str) -> int:
    if type(raw) is not bytes or len(raw) != 24:
        raise ValueError(f'AA {label} must be a complete 24-byte typed scalar')
    return decode_scalar(raw, tag)

def _check_fields(fields: Fields) -> None:
    if type(fields) is not Fields or type(fields.position_bytes) is not bytes or len(fields.position_bytes) != 8 or (type(fields.x) is not int) or (type(fields.y) is not int) or (struct.unpack('<ii', fields.position_bytes) != (fields.x, fields.y)):
        raise ValueError('AA requires an exact signed x/y position blob')
    for name, value, maximum in (('city_owner', fields.city_owner, 65535), ('city_id', fields.city_id, 4294967295), ('selector', fields.selector, 4294967295), ('D6', fields.d6_value, 4294967295), ('A1FBC', fields.a1fbc_value, 4294967295)):
        if type(value) is not int or not 0 <= value <= maximum:
            raise ValueError(f'AA {name} is outside its source field width')
    if fields.selector != SELECTOR:
        raise ValueError('AA codec admits only source-routed selector 0x51330671')

def decode_fields(raw_fields: dict, read) -> Fields:
    verify_source_evidence()
    keys = {594779970, 2353434172, 2716180809, 2717631346, 3606901732}
    if type(raw_fields) is not dict or set(raw_fields) != keys or any((type(raw_fields[k]) is not bytes for k in keys)):
        raise ValueError('AA requires exactly its five complete typed fields')
    selector = _scalar(raw_fields[2716180809], 3, 'A1E5A149 selector')
    a1fbc = _scalar(raw_fields[2717631346], 2, 'A1FBC372')
    d6 = _scalar(raw_fields[3606901732], 2, 'D6FCF3E4')
    position = _copy_blob(raw_fields[2353434172], read, 0)
    descriptor = _copy_blob(raw_fields[594779970], read, 1024)
    x, y = struct.unpack('<ii', position)
    city_owner = struct.unpack_from('<H', descriptor, 0)[0]
    city_id = struct.unpack_from('<I', descriptor, 4)[0]
    fields = Fields(position, x, y, city_owner, city_id, selector, d6, a1fbc)
    _check_fields(fields)
    return fields

def validate_profile(sequence: int, fields: Fields, *, padding_policy: str, empty_receiver_state: dict, notification_counter: int, metadata_counter: int, per_thread_hook_present: bool, writer_metadata_callback_present: bool, normalizer_transform_present: bool=False) -> None:
    _check_fields(fields)
    if type(sequence) is not int or not 1 <= sequence <= 4294967295:
        raise ValueError('AA sequence must be a nonzero uint32')
    if normalizer_transform_present is not False or padding_policy != PADDING_POLICY or type(empty_receiver_state) is not dict or (empty_receiver_state != EMPTY_STATE) or ({k: type(v) for k, v in empty_receiver_state.items()} != {k: type(v) for k, v in EMPTY_STATE.items()}) or (type(notification_counter) is not int) or (notification_counter != 0) or (type(metadata_counter) is not int) or (metadata_counter != 0) or (per_thread_hook_present is not False) or (writer_metadata_callback_present is not False):
        raise ValueError('AA padding is admitted only for the exact empty-receiver profile')

def _encode(sequence: int, fields: Fields, values: Values) -> bytes:
    if type(values) is not Values or type(values.plot_owner) is not int or (not -128 <= values.plot_owner <= 127) or (type(values.district_id) is not int) or (not 0 <= values.district_id <= 4294967295) or (type(values.flag148) is not int) or (not 0 <= values.flag148 <= 255):
        raise ValueError('AA requires a source snapshot from a non-null plot')
    record = bytearray(RECORD_SIZE)
    struct.pack_into('<IIII', record, 0, RECORD_SIZE, RECORD_TYPE, sequence, 0)
    record[16:24] = b'\xff' * 8
    record[24:64] = bytes.fromhex('ffff0000ffffffff') * 5
    record[64:76] = bytes(12)
    p = 80
    struct.pack_into('<I', record, p, sequence)
    record[p + 8:p + 16] = fields.position_bytes
    struct.pack_into('<HHI', record, p + 16, fields.city_owner, CITY_DESCRIPTOR_TYPE, fields.city_id)
    struct.pack_into('<hHI', record, p + 24, values.plot_owner, DISTRICT_DESCRIPTOR_TYPE, values.district_id)
    record[p + 32] = values.flag148
    struct.pack_into('<I', record, p + 36, fields.d6_value)
    record[p + 40] = int(fields.a1fbc_value != 0)
    return bytes(record)

@contextmanager
def produce_record_lease(sequence: int, fields: Fields, *, core, context: int, read, profile: dict, normalizer_transform_present: bool=False, native_api: dict | None=None, core_sha256=None):
    """Yield (record, diagnostic) while retaining the one queried plot lease.

    The helper performs exactly one outer-map/map-plot lookup. Null map/plot
    conditions raise before yielding; no sentinel or replacement bytes are
    synthesized for that source branch.
    """
    verify_source_evidence()
    if type(profile) is not dict:
        raise ValueError('AA requires the exact host empty-receiver profile')
    validate_profile(sequence, fields, normalizer_transform_present=normalizer_transform_present, **profile)
    helper_fields = {'position_bytes': fields.position_bytes, 'x': fields.x, 'y': fields.y, 'selector': fields.selector, 'source_value': fields.a1fbc_value, 'descriptor_tail': fields.d6_value}
    options = {} if core_sha256 is None else {'core_sha256': core_sha256}
    with snapshot.plot_snapshot(core, context, helper_fields, read=read,
                                native_api=native_api, **options) as raw_values:
        values = Values(raw_values['owner'], raw_values['district_id'], raw_values['flag148'])
        record = _encode(sequence, fields, values)
        diagnostic = {'record_type': RECORD_TYPE, 'record_size': RECORD_SIZE, 'plot_present': True, 'native_plot_queries_executed': True, 'payload_exposed_to_learner': False, 'source_uninitialized_payload_ranges': [list(r) for r in SOURCE_UNINITIALIZED_LIVE_RANGES], 'padding_policy': PADDING_POLICY, 'empty_receiver_state_verified': True}
        yield (record, diagnostic)
