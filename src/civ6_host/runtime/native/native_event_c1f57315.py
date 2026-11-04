"""DistrictUnitsChanged transport for the proven empty UI receiver only."""
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
from pathlib import Path
import struct
from civ6_host.runtime.native.native_application_mirror import decode_scalar
from civ6_host.runtime.native.native_host_events import copy_eight_byte_variant
from civ6_host.runtime.native.native_source_cache import load_pinned_json
EVENT_KIND, RECORD_TYPE, RECORD_SIZE = (3254088469, 164, 96)
EVENT_KINDS = (EVENT_KIND, 1289970298)
SELECTOR_KEY, UNIT_KEY, DISTRICT_KEY = (2716180809, 4032072631, 4081310810)
PINNED_EVIDENCE_SHA256 = 'bb398242c4471adb7337a95b433d237b05b6eda14f52eedf7d9a9554006b2b10'
_PROOF = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_event_c1f57315.py')))).resolve().parents[1] / 'evidence/native-event-c1f57315' / (PINNED_EVIDENCE_SHA256 + '.json')

def verify_source_evidence():
    proof = load_pinned_json(_PROOF, PINNED_EVIDENCE_SHA256)
    if proof['schema'] != 'civ6rl.native_event_c1f57315.static.v1' or proof['images']['exe']['sha256'] != 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63' or {r['kind']: r['callback_va'] for r in proof['registration']['rows']} != {kind: '0x140155370' for kind in EVENT_KINDS} or (proof['captures']['callback']['raw_sha256'] != 'd636a0589baa601a02349e842fbea2cc50c5b488e3c97de24236ffea7afa2cec') or (proof['captures']['writer']['raw_sha256'] != '90e7d29cad00ebf2591b0929ca1ac16a11b04d8cad252de026f4f685b2a6299d') or (proof['captures']['normalizer']['raw_sha256'] != 'c757d2f0c927f36e058ff5e57350a80beac1db2a89d3940fcb5e89c05545f23e') or (proof['empty_receiver_reference']['sha256'] != 'b1ffb35addd6cddbf66cf1cc1cc42ba547b1d021f2f0533ce1d6e3e8a0f4772d') or (proof['empty_receiver_reference']['row']['record_type'] != '0xa4') or (tuple(proof['adapter_admission']['event_kinds']) != EVENT_KINDS):
        raise RuntimeError('DistrictUnitsChanged source proof changed')
    return proof

def encode_record(sequence, raw_fields, read, *, normalizer_transform_present=False, thread_hook_present=False, writer_metadata_callback_present=False, empty_receiver_state, padding_policy):
    """Normalize exact descriptor fields, with an explicit unread-padding policy.

    The EXE callback leaves payload DWORD +4 uninitialized. Zeroing it is
    admitted solely for a source-proven empty receiver: it is not a native
    default, gameplay value or learner observation.
    """
    verify_source_evidence()
    if normalizer_transform_present is not False or thread_hook_present is not False or writer_metadata_callback_present is not False:
        raise ValueError('DistrictUnitsChanged hook-present paths are unsupported')
    if padding_policy != 'zero-unread-empty-receiver-payload':
        raise ValueError('DistrictUnitsChanged requires an explicit unread-padding policy')
    if type(sequence) is not int or not 1 <= sequence <= 4294967295:
        raise ValueError('DistrictUnitsChanged requires a nonzero uint32 sequence')
    if type(raw_fields) is not dict or set(raw_fields) != {SELECTOR_KEY, UNIT_KEY, DISTRICT_KEY}:
        raise ValueError('DistrictUnitsChanged requires its exact three fields')
    decode_scalar(raw_fields[SELECTOR_KEY], 3)
    copy_eight_byte_variant(raw_fields[UNIT_KEY], read, expected_tag=1024)
    district = copy_eight_byte_variant(raw_fields[DISTRICT_KEY], read, expected_tag=1024)
    owner, _input_type, identifier = struct.unpack('<HHI', district)
    record = bytearray(RECORD_SIZE)
    struct.pack_into('<IIII', record, 0, RECORD_SIZE, RECORD_TYPE, sequence, 0)
    struct.pack_into('<II', record, 16, 4294967295, 4294967295)
    for offset in (24, 32, 40, 48, 56):
        struct.pack_into('<HHI', record, offset, 65535, 0, 4294967295)
    struct.pack_into('<I', record, 80, sequence)
    struct.pack_into('<HHI', record, 88, owner, 3, identifier)
    from civ6_host.runtime.native.native_deferred_empty_profile import validate_empty_profile_record
    validate_empty_profile_record(record, **empty_receiver_state)
    return bytes(record)
