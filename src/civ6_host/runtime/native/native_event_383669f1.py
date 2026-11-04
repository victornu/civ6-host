"""Source-bounded Unit descriptor notification with absent DWORD defaults."""
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
from pathlib import Path
import struct
from civ6_host.runtime.native.native_source_cache import load_pinned_json
from civ6_host.runtime.native.native_application_mirror import decode_scalar
from civ6_host.runtime.native.native_host_events import copy_eight_byte_variant
from civ6_host.runtime.native import native_event_a60328c5 as paired
PINNED_EVIDENCE_SHA256 = 'e3a93458d4089ac00d8471cd559611c7755603004f2e9af4fc3cbadb4ab84ecc'
_PROOF = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_event_383669f1.py')))).resolve().parents[1] / 'evidence/native-event-383669f1' / f'{PINNED_EVIDENCE_SHA256}.json'
EVENT_KIND, RECORD_TYPE, RECORD_SIZE = (943090161, 71, 112)

def verify_source_evidence():
    p = load_pinned_json(_PROOF, PINNED_EVIDENCE_SHA256)
    if p['image']['sha256'] != 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63' or p['targets']['callback'] != '0x1401584d0' or p['targets']['writer'] != '0x14012cf00' or (p['captures']['callback']['code_sha256'] != '8642edeef3aac4028c36b8274da9b141ca784d23aae7259c84f931884bcd50ac') or (p['captures']['writer']['code_sha256'] != '85bd18b67645063fe11299b2f5bfd2ce1a5ef15d09ceb68c0a05fc0ff2dc10e8'):
        raise RuntimeError('383669F1 source identity differs')
    ins = {i['va']: i['text'] for f in p['captures']['normalizer']['fragments'] for i in f['instructions']}
    if ins.get('0x1401ca3b6') != 'mov qword ptr [rbp + 0x17], r13':
        raise RuntimeError('383669F1 absent DWORD initialization differs')

def decode_fields(fields, read):
    verify_source_evidence()
    if not isinstance(fields, dict) or set(fields) != {paired.SELECTOR_KEY, paired.UNIT_KEY}:
        raise ValueError('383669F1 requires two keys and absence of optional scalar keys')
    blob = copy_eight_byte_variant(fields[paired.UNIT_KEY], read, expected_tag=1024)
    owner, _, uid = struct.unpack('<HHI', blob)
    return paired.EventFields(decode_scalar(fields[paired.SELECTOR_KEY], 3), 0, 0, owner, uid)

def encode_record(sequence, fields, *, normalizer_transform_present, per_thread_hook_present, writer_metadata_callback_present, padding_policy):
    verify_source_evidence()
    if not isinstance(fields, paired.EventFields) or fields.value != 0 or fields.second != 0:
        raise ValueError('383669F1 requires the absent-scalar source defaults')
    record = bytearray(paired.encode_record(sequence, fields, normalizer_transform_present=normalizer_transform_present, per_thread_hook_present=per_thread_hook_present, writer_metadata_callback_present=writer_metadata_callback_present, padding_policy=padding_policy))
    struct.pack_into('<I', record, 4, RECORD_TYPE)
    return bytes(record)
