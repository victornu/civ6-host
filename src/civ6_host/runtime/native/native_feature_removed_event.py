"""Source-scoped diagnostic encoder for FeatureRemovedFromMap (0xDA20B653)."""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import hashlib
import json
import struct
from pathlib import Path
from civ6_host.runtime.native.native_application_mirror import decode_scalar
from civ6_host.runtime.native.native_host_events import copy_eight_byte_variant
from civ6_host.runtime.native.native_source_cache import load_pinned_json
EVENT_KIND = 3659576915
BLOB_KEY = 2353434172
SELECTOR_KEY = 2716180809
TAIL_KEY = 3606901732
RECORD_TYPE = 119
RECORD_SIZE = 96
POSITION_SIZE = 8
PINNED_EXE_SHA256 = 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63'
PINNED_CALLBACK_SHA256 = '695fbd7e6e5e5b0bb0190fb198c1ef670afb3d47caa801bfe3fe7708836f88aa'
PINNED_WRITER_SHA256 = 'f300b0ddec46a8f08fc2a18df6ec11fc824706cc7b829387149eeb1926b4953d'
PINNED_NORMALIZER_SHA256 = 'c757d2f0c927f36e058ff5e57350a80beac1db2a89d3940fcb5e89c05545f23e'
PINNED_ROW_EVIDENCE_SHA256 = '6d996669f56296676f7b04330e015f0d10f67678a459793b192c423e79fb3f38'
PINNED_EVIDENCE_SHA256 = 'c63a1280277bd77faf8506ec9d6106cdc998735199d7f98de2c33d93bd62d491'
SCALAR_DOMAIN_SHA256 = '4744db92daf09bb02dc3c6bec59be22b0ab17046498c0ec55920dedd667c89a4'

def verify_source_evidence() -> None:
    path = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_feature_removed_event.py')))).resolve().parents[1] / 'evidence/native-event-da20b653' / f'{PINNED_EVIDENCE_SHA256}.json'
    raw = _resolve_resource_path(path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != PINNED_EVIDENCE_SHA256:
        raise RuntimeError('Pinned FeatureRemovedFromMap evidence bytes changed')
    doc = json.loads(raw)
    bodies = doc.get('body_sha256', {})
    row = doc.get('writer_contract', {}).get('empty_handler_row', {})
    if doc.get('image', {}).get('exe_sha256') != PINNED_EXE_SHA256 or doc.get('callback_va') != '0x1401468b0' or bodies.get('callback') != PINNED_CALLBACK_SHA256 or (bodies.get('writer') != PINNED_WRITER_SHA256) or (bodies.get('normalizer') != PINNED_NORMALIZER_SHA256) or (row.get('row', {}).get('event_name') != 'GameCoreEvent::FeatureRemovedFromMap') or (row.get('sha256') != PINNED_ROW_EVIDENCE_SHA256):
        raise RuntimeError('Pinned FeatureRemovedFromMap source evidence changed')
    scalar_path = path.parents[1] / 'native-feature-removed-scalars' / (SCALAR_DOMAIN_SHA256 + '.json')
    scalar = load_pinned_json(scalar_path, SCALAR_DOMAIN_SHA256)
    if scalar.get('schema') != 'civ6rl.native_feature_removed_scalars.static.v1' or scalar['exe_sha256'] != PINNED_EXE_SHA256 or scalar['prior_callback_writer_proof_sha256'] != PINNED_EVIDENCE_SHA256 or (scalar['body_sha256'] != bodies) or (scalar['all_captured_bytes_reverified_in_original_pe'] is not True):
        raise RuntimeError('FeatureRemovedFromMap unused scalar contract changed')

def decode_feature_removed_fields(fields: dict[int, bytes], read) -> dict:
    """Copy the position and preserve scalars unused by the source callback."""
    verify_source_evidence()
    if set(fields) != {BLOB_KEY, SELECTOR_KEY, TAIL_KEY}:
        raise ValueError('Unverified 0xDA20B653 field set')
    selector = decode_scalar(fields[SELECTOR_KEY], 3)
    tail = decode_scalar(fields[TAIL_KEY], 2)
    position = copy_eight_byte_variant(fields[BLOB_KEY], read, expected_tag=0)
    x, y = struct.unpack('<ii', position)
    return {'position_bytes': position, 'x': x, 'y': y, 'selector': selector, 'tail': tail}

def encode_record(sequence: int, position: dict, *, thread_hook_present: bool=False, writer_metadata_callback_present: bool=False, padding_policy: str='zero') -> bytes:
    """Encode only the observed no-hook/no-writer-service diagnostic profile.

    Native writer defaults occupy record+0x10..+0x4b. The gaps at +0x4c..+0x4f
    and +0x5c..+0x5f are not initialized by the writer; zero is an explicit
    deterministic diagnostic padding policy.
    """
    verify_source_evidence()
    if type(sequence) is not int or not 1 <= sequence <= 4294967295:
        raise ValueError('Sequence must be a nonzero uint32')
    if thread_hook_present is not False or writer_metadata_callback_present is not False:
        raise ValueError('Optional native callbacks require their source-backed behavior')
    if padding_policy != 'zero':
        raise ValueError('Only explicit zero padding is supported')
    raw = position.get('position_bytes')
    if type(raw) is not bytes or len(raw) != POSITION_SIZE or type(position.get('x')) is not int or (type(position.get('y')) is not int) or (struct.unpack('<ii', raw) != (position['x'], position['y'])):
        raise ValueError('Unverified FeatureRemovedFromMap position descriptor')
    record = bytearray(RECORD_SIZE)
    struct.pack_into('<IIHHI', record, 16, 4294967295, 4294967295, 65535, 0, 4294967295)
    for offset in (32, 40, 48, 56):
        struct.pack_into('<HHI', record, offset, 65535, 0, 4294967295)
    struct.pack_into('<Q', record, 64, 0)
    struct.pack_into('<I', record, 72, 0)
    struct.pack_into('<IIII', record, 0, RECORD_SIZE, RECORD_TYPE, sequence, 0)
    record[84:92] = raw
    struct.pack_into('<I', record, 80, sequence)
    return bytes(record)
