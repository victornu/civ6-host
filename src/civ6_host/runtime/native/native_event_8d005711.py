"""Source-pinned CityChanged notification in the explicit empty-receiver profile."""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
from dataclasses import dataclass
from pathlib import Path
import struct
from civ6_host.runtime.native.native_application_mirror import decode_scalar
from civ6_host.runtime.native.native_host_events import copy_eight_byte_variant
from civ6_host.runtime.native.native_source_cache import load_pinned_json
EVENT_KIND, RECORD_TYPE, RECORD_SIZE = (2365609745, 91, 112)
EVENT_NAME = 'GameCoreEvent::CityChanged'
SELECTOR_KEY, DESCRIPTOR_KEY, D6_KEY = (2716180809, 594779970, 3606901732)
PADDING_POLICY = 'zero-unread-empty-receiver-payload'
PINNED_EVIDENCE_SHA256 = '2b5699c7316debe290e881e62e2a1ee47eadabdbc8966e5a6661a3b783d5606b'
_PROOF = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_event_8d005711.py')))).resolve().parents[1] / 'evidence/native-event-8d005711' / f'{PINNED_EVIDENCE_SHA256}.json'
_RECEIVER_KEYS = frozenset({'observer_registered', 'state_pointer_nonnull', 'pre_hook', 'post_hook', 'subscriber_count', 'state_flags'})

def verify_source_evidence():
    proof = load_pinned_json(_PROOF, PINNED_EVIDENCE_SHA256)
    hashes = {'callback': '3ee030d622056887e4cfd42054f86de704a1c5b73ccbac647fdb3afe8b6e590a', 'writer': '9161f757642fb9b535fe0086ac9d2eb50cf20af09dafe6e0c46584df7dbb35e5', 'normalizer': 'c757d2f0c927f36e058ff5e57350a80beac1db2a89d3940fcb5e89c05545f23e', 'handler': '08f47c80c29737e161012a9676dc82e3b3c52183b4896a69591b8b23141a5c49', 'subscriber_dispatch': '326ad0582020365181be9ed3b3e0f595e1bf834ef24f5afdf167d9ae56292bca'}
    if proof.get('schema') != 'civ6rl.native_event_8d005711.static.v1' or proof['exe_sha256'] != 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63' or proof['core_sha256'] != 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3' or (proof['registration']['kind'] != EVENT_KIND) or (proof['registration']['callback_va'] != '0x1401410f0') or (proof['receiver']['record_type'] != '0x5b') or (proof['receiver']['record_size'] != '0x70') or (proof['receiver']['event_name'] != EVENT_NAME) or any((proof['captures'][name]['code_sha256'] != value for name, value in hashes.items())):
        raise RuntimeError('Pinned 8D005711 source identity changed')

@dataclass(frozen=True)
class EventFields:
    selector: int
    descriptor_bytes: bytes
    owner: int
    item_id: int
    d6_value: int

def _validate(fields):
    if not isinstance(fields, EventFields) or type(fields.descriptor_bytes) is not bytes or len(fields.descriptor_bytes) != 8 or (type(fields.owner) is not int) or (not 0 <= fields.owner <= 65535) or any((type(v) is not int or not 0 <= v <= 4294967295 for v in (fields.selector, fields.item_id, fields.d6_value))) or (struct.unpack_from('<H', fields.descriptor_bytes)[0] != fields.owner) or (struct.unpack_from('<I', fields.descriptor_bytes, 4)[0] != fields.item_id):
        raise ValueError('8D005711 requires exact decoded city and scalar fields')

def decode_fields(fields, read) -> EventFields:
    """Copy the borrowed eight-byte descriptor once; never retain its pointer."""
    verify_source_evidence()
    if not isinstance(fields, dict) or set(fields) != {SELECTOR_KEY, DESCRIPTOR_KEY, D6_KEY}:
        raise ValueError('8D005711 requires exactly city, selector and D6 fields')
    selector = decode_scalar(fields[SELECTOR_KEY], 3)
    value = decode_scalar(fields[D6_KEY], 2)
    descriptor = copy_eight_byte_variant(fields[DESCRIPTOR_KEY], read, expected_tag=1024)
    result = EventFields(selector, descriptor, struct.unpack_from('<H', descriptor)[0], struct.unpack_from('<I', descriptor, 4)[0], value)
    _validate(result)
    return result

def encode_record(sequence, fields, *, normalizer_transform_present, per_thread_hook_present, writer_metadata_callback_present, padding_policy, empty_receiver_state, record_profile=None) -> bytes:
    """Encode writer12F260, requiring that its undefined stack bytes stay unread.

    Normalization copies the city owner/id, initializes type2 independently of
    descriptor WORD2 and reads the raw D6 DWORD. Selector is preserved in
    EventFields but unread by the callback. There is no Core query or metadata
    notification-counter dependency. Record54..57 and64..67 are unspecified
    native stack bytes; zeros here are an explicit diagnostic policy, never a
    claim of a native default. The dispatcher owns queue reservation/enqueue.
    """
    _selected_record_type = RECORD_TYPE
    if record_profile is not None:
        from civ6_host.runtime.city_scalar_event_profiles import require_record_profile
        _selected_record_type = require_record_profile(record_profile).record_type
    verify_source_evidence()
    _validate(fields)
    if normalizer_transform_present is not False or per_thread_hook_present is not False or writer_metadata_callback_present is not False:
        raise ValueError('8D005711 transformation or registered callbacks are unsupported')
    if type(sequence) is not int or not 1 <= sequence <= 4294967295:
        raise ValueError('8D005711 requires a nonzero uint32 sequence')
    if padding_policy != PADDING_POLICY:
        raise ValueError('8D005711 requires explicit zero-unread-empty-receiver-payload policy')
    if not isinstance(empty_receiver_state, dict) or set(empty_receiver_state) != _RECEIVER_KEYS:
        raise ValueError('8D005711 requires complete explicit empty receiver state')
    record = bytearray(RECORD_SIZE)
    struct.pack_into('<IIII', record, 0, RECORD_SIZE, _selected_record_type, sequence, 0)
    from civ6_host.runtime.native.native_deferred_empty_profile import validate_empty_profile_record
    validate_empty_profile_record(record, **empty_receiver_state)
    struct.pack_into('<II', record, 16, 4294967295, 4294967295)
    for offset in (24, 32, 40, 48, 56):
        struct.pack_into('<HHI', record, offset, 65535, 0, 4294967295)
    struct.pack_into('<I', record, 80, sequence)
    struct.pack_into('<HHII', record, 88, fields.owner, 2, fields.item_id, fields.d6_value)
    return bytes(record)
