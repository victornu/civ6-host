"""Source-backed city descriptor plus position event (type6B)."""
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
from dataclasses import dataclass
from pathlib import Path
import struct
from civ6_host.runtime.native import native_event_99e85ec6 as descriptor_codec
from civ6_host.runtime.native.native_feature_visibility_event import _copy_blob
from civ6_host.runtime.native.native_source_cache import load_pinned_json
EVENT_KIND, RECORD_TYPE, RECORD_SIZE = (4217315035, 107, 112)
POSITION_KEY = 2353434172
PINNED_EVIDENCE_SHA256 = '5e2d307d15a46674745220b3ee11fb8f113348d85dbeb47cf63e5d0e846dff3b'
_PROOF = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_event_fb5f1edb.py')))).resolve().parents[1] / 'evidence/native-event-fb5f1edb' / f'{PINNED_EVIDENCE_SHA256}.json'

def verify_source_evidence():
    proof = load_pinned_json(_PROOF, PINNED_EVIDENCE_SHA256)
    if proof['schema'] != 'civ6rl.native_event_fb5f1edb.static.v1' or proof['registration']['callback_va'] != '0x1401423a0' or proof['contract']['record_type'] != RECORD_TYPE or (proof['contract']['record_size'] != RECORD_SIZE):
        raise RuntimeError('FB5F1EDB source contract changed')

@dataclass(frozen=True)
class EventFields:
    descriptor: descriptor_codec.EventFields
    position_bytes: bytes

    @property
    def owner(self):
        return self.descriptor.owner

def decode_fields(raw_fields, read):
    verify_source_evidence()
    if not isinstance(raw_fields, dict) or set(raw_fields) != {2716180809, 594779970, POSITION_KEY}:
        raise ValueError('FB5F1EDB requires exact three-key descriptor/position shape')
    position = _copy_blob(raw_fields[POSITION_KEY], read, 0)
    descriptor = descriptor_codec.decode_fields({k: v for k, v in raw_fields.items() if k != POSITION_KEY}, read)
    return EventFields(descriptor, position)

def encode_record(sequence, fields, *, normalizer_transform_present, per_thread_hook_present, writer_metadata_callback_present, padding_policy):
    verify_source_evidence()
    if not isinstance(fields, EventFields) or type(fields.position_bytes) is not bytes or len(fields.position_bytes) != 8:
        raise ValueError('FB5F1EDB requires a complete eight-byte position')
    record = bytearray(descriptor_codec.encode_record(sequence, fields.descriptor, normalizer_transform_present=normalizer_transform_present, per_thread_hook_present=per_thread_hook_present, writer_metadata_callback_present=writer_metadata_callback_present, padding_policy=padding_policy))
    record.extend(bytes(16))
    struct.pack_into('<II', record, 0, RECORD_SIZE, RECORD_TYPE)
    record[96:104] = fields.position_bytes
    return bytes(record)
