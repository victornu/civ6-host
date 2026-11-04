"""Source-bounded Unit descriptor/two-DWORD notification producer."""
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
from dataclasses import dataclass
from pathlib import Path
import struct
from civ6_host.runtime.native.native_source_cache import load_pinned_json
from civ6_host.runtime.native.native_application_mirror import decode_scalar
from civ6_host.runtime.native.native_host_events import copy_eight_byte_variant
from civ6_host.runtime.native.native_event_51c84cba import verify_source_evidence as verify_normalizer_profile
PINNED_EVIDENCE_SHA256 = 'aff3f977b0bd73de8205dbc1928738bd91910db5c095f7b546314e29bb78548c'
_PROOF = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_event_a60328c5.py')))).resolve().parents[1] / 'evidence/native-event-a60328c5' / f'{PINNED_EVIDENCE_SHA256}.json'
EVENT_KIND, RECORD_TYPE, RECORD_SIZE = (2785224901, 70, 112)
SELECTOR_KEY, VALUE_KEY, SECOND_KEY, UNIT_KEY = (2716180809, 3606901732, 2717631346, 4032072631)

def verify_source_evidence():
    p = load_pinned_json(_PROOF, PINNED_EVIDENCE_SHA256)
    if p['image']['sha256'] != 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63' or p['targets']['callback'] != '0x140158170' or p['targets']['writer'] != '0x14012cd00' or (p['captures']['callback']['code_sha256'] != 'a607a4251777a09ab527b41f427fb842848665d83dcdd7bbe4ad099f645f2d5c') or (p['captures']['writer']['code_sha256'] != 'b92d827a1b02c9105865efc8b71a079124b59a00a40429e7a5d2fc0edf9fa38b'):
        raise RuntimeError('A60328C5 source identity changed')
    verify_normalizer_profile()

@dataclass(frozen=True)
class EventFields:
    selector: int
    value: int
    second: int
    owner: int
    unit_id: int

def _validate(f):
    if not isinstance(f, EventFields):
        raise ValueError('Expected decoded A60328C5 fields')
    for value in (f.selector, f.value, f.second, f.unit_id):
        if type(value) is not int or not 0 <= value <= 4294967295:
            raise ValueError('A60328C5 requires raw DWORD values')
    if type(f.owner) is not int or not 0 <= f.owner <= 65535:
        raise ValueError('A60328C5 owner must be a WORD')

def decode_fields(fields, read):
    verify_source_evidence()
    if not isinstance(fields, dict) or set(fields) != {SELECTOR_KEY, VALUE_KEY, SECOND_KEY, UNIT_KEY}:
        raise ValueError('Unverified A60328C5 field envelope')
    blob = copy_eight_byte_variant(fields[UNIT_KEY], read, expected_tag=1024)
    owner, _, identifier = struct.unpack('<HHI', blob)
    f = EventFields(decode_scalar(fields[SELECTOR_KEY], 3), decode_scalar(fields[VALUE_KEY], 2), decode_scalar(fields[SECOND_KEY], 2), owner, identifier)
    _validate(f)
    return f

def encode_record(sequence, fields, *, normalizer_transform_present, per_thread_hook_present, writer_metadata_callback_present, padding_policy):
    verify_source_evidence()
    _validate(fields)
    if type(sequence) is not int or not 1 <= sequence <= 4294967295:
        raise ValueError('A60328C5 requires a nonzero DWORD sequence')
    if normalizer_transform_present is not False or per_thread_hook_present is not False or writer_metadata_callback_present is not False:
        raise ValueError('A60328C5 callback service is outside the source profile')
    if padding_policy != 'headless-zero-uninitialized-stack':
        raise ValueError('A60328C5 requires the explicit padding policy')
    record = bytearray(RECORD_SIZE)
    struct.pack_into('<IIII', record, 0, RECORD_SIZE, RECORD_TYPE, sequence, 0)
    struct.pack_into('<IIHHI', record, 16, 4294967295, 4294967295, fields.owner, 1, fields.unit_id)
    for offset in (32, 40, 48, 56):
        struct.pack_into('<HHI', record, offset, 65535, 0, 4294967295)
    struct.pack_into('<I', record, 80, sequence)
    struct.pack_into('<HHIII', record, 88, fields.owner, 1, fields.unit_id, fields.value, fields.second)
    return bytes(record)
