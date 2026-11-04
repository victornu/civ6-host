"""Direct raw-descriptor notification, including the source metadata flag4."""
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
from dataclasses import dataclass
from pathlib import Path
import struct
from civ6_host.runtime.native.native_application_mirror import decode_scalar
from civ6_host.runtime.native.native_host_events import copy_eight_byte_variant
from civ6_host.runtime.native.native_source_cache import load_pinned_json
PINNED_EVIDENCE_SHA256 = 'dab3e4c2c753a35187786dfad780738cac581b627028492f818b33fe3e7de069'
_PROOF = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_event_9ad1c020.py')))).resolve().parents[1] / 'evidence/native-event-9ad1c020' / f'{PINNED_EVIDENCE_SHA256}.json'
EVENT_KIND, RECORD_TYPE, RECORD_SIZE = (2597437472, 258, 96)
SELECTOR_KEY, DESCRIPTOR_KEY = (2716180809, 3937836634)

def verify_source_evidence():
    p = load_pinned_json(_PROOF, PINNED_EVIDENCE_SHA256)
    if p['image']['sha256'] != 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63' or p['targets']['callback'] != '0x14014a4f0' or p['targets']['writer'] != '0x14011f0f0' or (p['captures']['callback']['code_sha256'] != '7e05f0e6f712b5e9ae4ae4129e057b2162750385c872bdc6c5433277d2a3c02e') or (p['captures']['writer']['code_sha256'] != '42a9bec50f71fff99ca8850f20d5816a9fe3d2c5b016da850dcfaa9f5755ff90'):
        raise RuntimeError('9AD1C020 source identity differs')

@dataclass(frozen=True)
class EventFields:
    selector: int
    descriptor: bytes

def _validate(f):
    if not isinstance(f, EventFields) or type(f.selector) is not int or (not 0 <= f.selector <= 4294967295) or (type(f.descriptor) is not bytes) or (len(f.descriptor) != 8):
        raise ValueError('9AD1C020 requires a typed selector and exact eight-byte descriptor')

def decode_fields(fields, read):
    verify_source_evidence()
    if not isinstance(fields, dict) or set(fields) != {SELECTOR_KEY, DESCRIPTOR_KEY}:
        raise ValueError('Unverified 9AD1C020 argument set')
    f = EventFields(decode_scalar(fields[SELECTOR_KEY], 3), copy_eight_byte_variant(fields[DESCRIPTOR_KEY], read, expected_tag=1024))
    _validate(f)
    return f

def encode_record(sequence, fields, *, per_thread_hook_present, writer_metadata_callback_present, padding_policy):
    verify_source_evidence()
    _validate(fields)
    if type(sequence) is not int or not 1 <= sequence <= 4294967295:
        raise ValueError('9AD1C020 requires a nonzero DWORD sequence')
    if per_thread_hook_present is not False or writer_metadata_callback_present is not False:
        raise ValueError('9AD1C020 registered callbacks are not covered')
    if padding_policy != 'headless-zero-uninitialized-stack':
        raise ValueError('9AD1C020 requires the explicit stack-padding policy')
    r = bytearray(RECORD_SIZE)
    struct.pack_into('<IIII', r, 0, RECORD_SIZE, RECORD_TYPE, sequence, 0)
    struct.pack_into('<II', r, 16, 4294967295, 4294967295)
    for offset in (24, 32, 40, 48, 56):
        struct.pack_into('<HHI', r, offset, 65535, 0, 4294967295)
    struct.pack_into('<I', r, 72, 4)
    struct.pack_into('<I', r, 80, sequence)
    r[88:96] = fields.descriptor
    return bytes(r)
