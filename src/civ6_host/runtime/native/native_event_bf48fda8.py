"""TechBoostTriggered EXE transport; the Core retains every boost rule."""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
from pathlib import Path
import struct
from civ6_host.runtime.native import native_event_3feaad02 as _analog
from civ6_host.runtime.native.native_source_cache import load_pinned_json
PINNED_EVIDENCE_SHA256 = 'cd35472790524a1a043ffa261ed832617bd19ce1c1b5de8afbf6c4122f5c5063'
_PROOF = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_event_bf48fda8.py')))).resolve().parents[1] / 'evidence/native-event-bf48fda8' / (PINNED_EVIDENCE_SHA256 + '.json')
EVENT_KIND = 3209231784
RECORD_TYPE = 178
RECORD_SIZE = 112

def verify_source_evidence():
    proof = load_pinned_json(_PROOF, PINNED_EVIDENCE_SHA256)
    if proof.get('schema') != 'civ6rl.native_event_bf48fda8.static.v1' or proof.get('exe_sha256') != _analog.EXE_SHA256 or proof.get('core_sha256') != 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3' or (proof.get('targets', {}).get('callback') != '0x140153bc0') or (proof.get('targets', {}).get('writer') != '0x140137240') or (proof.get('analog', {}).get('sha256') != _analog.PINNED_EVIDENCE_SHA256):
        raise RuntimeError('TechBoostTriggered source identity changed')
    for name, digest in {'callback': '2e67c27f0fda294fba295c650cbbafb80a84926dbd9b9113bc7ecad38eb1d519', 'writer': '475e06c85a781b12a2699e316cd87d6eb9ee91addbc0e1b8cb9704990b70062a', 'normalizer': 'c757d2f0c927f36e058ff5e57350a80beac1db2a89d3940fcb5e89c05545f23e', 'receiver_setup': '2d43bc95b77578dfb0230d8082c28c067e8d4598325759ef7e995a8d5312ce3b', 'handler': 'a0428932b89a75a527a6a32b38604ef204b84e808adbcf16be9e010c1ab58161'}.items():
        if proof.get('captures', {}).get(name, {}).get('code_sha256') != digest:
            raise RuntimeError('TechBoostTriggered body changed: ' + name)
    receiver = proof['receiver']
    if receiver['record_type'] != RECORD_TYPE or receiver['record_size'] != RECORD_SIZE or receiver['event_name'] != 'GameCoreEvent::TechBoostTriggered' or (receiver['row_va'] != '0x1412c8a10') or (tuple(proof['contract']['payload']) != ('sequence', 'D6', 'A1E5', 'A1FBC', '38F')):
        raise RuntimeError('TechBoostTriggered layout changed')
    return proof

def encode_record(sequence, raw_fields, *, normalizer_transform_present, thread_hook_present, writer_metadata_callback_present):
    verify_source_evidence()
    record = bytearray(_analog.encode_record(sequence, raw_fields, normalizer_transform_present=normalizer_transform_present, thread_hook_present=thread_hook_present, writer_metadata_callback_present=writer_metadata_callback_present))
    if struct.unpack_from('<II', record) != (RECORD_SIZE, 179):
        raise ValueError('Checked analog record contract changed')
    struct.pack_into('<I', record, 4, RECORD_TYPE)
    return bytes(record)
