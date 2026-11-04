"""Source-bounded codec for the FBADA2C8 normalized-descriptor callback."""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
from dataclasses import dataclass
from pathlib import Path
import struct
from civ6_host.runtime.native.native_event_51c84cba import DESCRIPTOR_KEY
from civ6_host.runtime.native.native_event_51c84cba import SELECTOR_KEY
from civ6_host.runtime.native.native_event_51c84cba import VALUE_KEY
from civ6_host.runtime.native.native_event_51c84cba import decode_fields as decode_51_fields
from civ6_host.runtime.native.native_source_cache import load_pinned_json
EVENT_KIND, CALLBACK_VA, WRITER_VA = (4222460616, '0x1401422e0', '0x140130f40')
RECORD_TYPE, RECORD_SIZE = (113, 112)
CITY_CANDIDATE_PROOF_SHA256 = 'cee35d28ae1ea5c9a34d8c00067c09619b887804a093b06340680ae29117b7ea'
NORMALIZER_PROOF_SHA256 = '5737bd679a0eb0ca70a955e9f1b571e7f4dd79f3d0b8991e6f0ba4bcd8c2e294'
_CITY_PROOF = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_event_fbada2c8.py')))).resolve().parents[1] / 'evidence/native-city-descriptor-candidates' / f'{CITY_CANDIDATE_PROOF_SHA256}.json'
_NORMALIZER_PROOF = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_event_fbada2c8.py')))).resolve().parents[1] / 'evidence/native-event-51c84cba' / f'{NORMALIZER_PROOF_SHA256}.json'
_EXE_SHA256 = 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63'
_STACK_POLICY = 'headless-zero-uninitialized-stack'

def verify_source_evidence() -> None:
    city = load_pinned_json(_CITY_PROOF, CITY_CANDIDATE_PROOF_SHA256)
    row = next((c for c in city['captures'] if int(c['registration']['kind']) == EVENT_KIND), None)
    if city.get('schema') != 'civ6rl.native-city-descriptor-candidates.static.v1' or city.get('exe_sha256') != _EXE_SHA256 or row is None or (row['registration']['callback_va'] != CALLBACK_VA) or (row['writer_va'] != WRITER_VA) or (row['callback']['code_sha256'] != 'de171214c7f205903488957b09cff94d206d87d3d5330ca0bd612ac8a52e5441') or (row['writer']['code_sha256'] != '78e1295288bf884fd3c540397664f89dc757f9169461bddafc5c40ae7e466a62') or (row['writer_record_header'] != {'size': RECORD_SIZE, 'type': RECORD_TYPE}) or (row['direct_call_targets'] != ('call qword ptr [rax + 8]', 'call 0x140130f40', 'call 0x1409898c0')):
        raise RuntimeError('Pinned FBADA2C8 callback/writer evidence changed')
    callback_text = tuple((i['text'] for f in row['callback']['fragments'] for i in f['instructions']))
    if 'cmp dword ptr [rdx + 0x50], 0' not in callback_text or 'setne byte ptr [rsp + 0x30]' not in callback_text or 'call 0x140130f40' not in callback_text:
        raise RuntimeError('FBADA2C8 zero/nonzero conversion or unconditional writer path changed')
    normalizer = load_pinned_json(_NORMALIZER_PROOF, NORMALIZER_PROOF_SHA256)
    if normalizer.get('schema') != 'civ6rl.native_event_51c84cba.static.v1' or normalizer.get('exe_sha256') != _EXE_SHA256 or normalizer['captures']['normalizer']['code_sha256'] != 'c757d2f0c927f36e058ff5e57350a80beac1db2a89d3940fcb5e89c05545f23e' or (normalizer['instruction_guards']['normalizer'].get('0x1401ca6c7') != 'cmp ecx, 0xd6fcf3e4') or (normalizer['instruction_guards']['normalizer'].get('0x1401ca6ec') != 'mov dword ptr [rbp + 0x17], eax'):
        raise RuntimeError('Pinned shared 51C84CBA normalizer evidence changed')

@dataclass(frozen=True)
class EventFields:
    selector: int
    owner: int
    item_id: int
    enabled: bool

def decode_event_fields(fields: dict, read) -> EventFields:
    """Accept only 51C84CBA's exact raw keys/tags and derive the callback gate.

    D6FCF3E4/tag2 becomes normalized DWORD+0x50 in the shared normalizer;
    this callback always writes a record and stores whether that DWORD is
    nonzero as a boolean byte. A1E5A149/tag3 is validated by the reused parser
    but is not used as a thread selector.
    Descriptor key 23739F42/tag0x400 is copied by that parser under its exact
    pointer/size/flags checks; callback consumes normalized WORD +18,+1A and
    DWORD +1C, with +1A initialized by the normalizer to2.
    """
    verify_source_evidence()
    decoded = decode_51_fields(fields, read)
    if type(decoded.selector) is not int or type(decoded.value) is not int:
        raise ValueError('invalid source-decoded scalar fields')
    return EventFields(decoded.selector, decoded.owner, decoded.item_id, decoded.value != 0)

def encode_record(sequence: int, fields: EventFields, *, normalizer_transform_present: bool, per_thread_hook_present: bool, writer_metadata_callback_present: bool, padding_policy: str) -> bytes:
    """Encode type0x71; source D6 zero/nonzero becomes a payload boolean.

    The callback compares normalized DWORD+0x50 with zero, writes SETNE as a
    byte at local+0x10, and calls the writer unconditionally for a valid
    marker. The writer copies 16 bytes plus a QWORD tail.
    Stack bytes local+4..7 and local+0x11..0x17 have no source value, so the
    explicit diagnostic policy is mandatory for the zero-filled encoding.
    """
    verify_source_evidence()
    if not isinstance(fields, EventFields) or type(fields.selector) is not int or (not 0 <= fields.selector <= 4294967295) or (type(fields.owner) is not int) or (not 0 <= fields.owner <= 65535) or (type(fields.item_id) is not int) or (not 0 <= fields.item_id <= 4294967295) or (type(fields.enabled) is not bool):
        raise ValueError('invalid FBADA2C8 decoded fields')
    if normalizer_transform_present is not False or per_thread_hook_present is not False or writer_metadata_callback_present is not False:
        raise ValueError('EXE transform, per-thread hook, or writer callback is unsupported')
    if type(sequence) is not int or not 1 <= sequence <= 4294967295:
        raise ValueError('sequence must be a nonzero uint32')
    if padding_policy != _STACK_POLICY:
        raise ValueError('explicit policy required for uninitialized stack bytes')
    record = bytearray(RECORD_SIZE)
    struct.pack_into('<IIII', record, 0, RECORD_SIZE, RECORD_TYPE, sequence, 0)
    struct.pack_into('<II', record, 16, 4294967295, 4294967295)
    for offset in (24, 32, 40, 48, 56):
        struct.pack_into('<HHI', record, offset, 65535, 0, 4294967295)
    struct.pack_into('<IIHHI', record, 80, sequence, 0, fields.owner, 2, fields.item_id)
    struct.pack_into('<B', record, 96, int(fields.enabled))
    return bytes(record)
