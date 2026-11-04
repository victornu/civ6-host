"""Thirteen exact EXE scalar callbacks, guarded by descriptor and hook shape."""
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import hashlib
import json
import struct
from pathlib import Path
from civ6_host.runtime.native.native_event_d35e import decode_fields
from civ6_host.runtime.native.native_event_d35e import encode_d35e571d_record
from civ6_host.runtime.native.native_host_event_registry import EXE_EVENT_CALLBACKS
_PROOF_SHA = '8df14d6e92de80d315b2d534d3f796468de63a03f8d6a6b3ca01cca2b7d44b78'
_raw = _resolve_resource_path(_resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_scalar_no_metadata_family.py')))).resolve().parents[1] / 'evidence/native-scalar-no-metadata-family.json').read_bytes()
if hashlib.sha256(_raw).hexdigest() != _PROOF_SHA:
    raise RuntimeError('Scalar no-metadata family proof changed')
_proof = json.loads(_raw)
SOURCES = {int(row['kind'], 16): row for row in _proof['candidates']}
if len(SOURCES) != 13 or any((EXE_EVENT_CALLBACKS.get(k) != int(v['callback_va'], 16) - 5368709120 for k, v in SOURCES.items())):
    raise RuntimeError('Scalar family and full EXE registry disagree')

def encode_fields(kind, fields, sequence, *, optional_callback_present, queue_hook_present):
    if kind not in SOURCES:
        raise ValueError('Unknown scalar no-metadata callback')
    if optional_callback_present is not False or queue_hook_present is not False:
        raise ValueError('Scalar family requires explicit absent optional hooks')
    value = decode_fields(fields)['callback_value']
    record = bytearray(encode_d35e571d_record(sequence, value, queue_metadata=0))
    struct.pack_into('<I', record, 4, SOURCES[kind]['record_type'])
    return bytes(record)
