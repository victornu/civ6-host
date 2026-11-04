"""Source-bounded descriptor/owner-query producer for EXE event10419F1F."""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
from dataclasses import dataclass
from dataclasses import replace
from pathlib import Path
import struct
from civ6_host.runtime.native.native_event_51c84cba import EventFields
from civ6_host.runtime.native.native_event_51c84cba import decode_fields as _decode_descriptor_fields
from civ6_host.runtime.native.native_event_fa5b1159 import query_secondary_value
from civ6_host.runtime.native.native_event_fa5b1159 import read_player_civilization_type_id
from civ6_host.runtime.native.native_source_cache import load_pinned_json
EVENT_KIND, RECORD_TYPE, RECORD_SIZE = (272736031, 102, 112)
SELECTOR_KEY, VALUE_KEY, DESCRIPTOR_KEY = (2716180809, 3606901732, 594779970)
PINNED_EVIDENCE_SHA256 = '0eef1259fb1516f0ea3a0861e9880e6dc51f2a767230deeea8070f98999c8661'
_PROOF = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_event_10419f1f.py')))).resolve().parents[1] / 'evidence/native-event-10419f1f' / f'{PINNED_EVIDENCE_SHA256}.json'

def verify_source_evidence():
    proof = load_pinned_json(_PROOF, PINNED_EVIDENCE_SHA256)
    if proof.get('schema') != 'civ6rl.native_event_10419f1f.static.v1' or dict(proof['images']) != {'exe_sha256': 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63', 'core_sha256': 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'} or proof['registration']['callback_va'] != '0x1401418b0' or (proof['captures']['callback']['code_sha256'] != 'cff99a48d7766dbe23e21e5ca0c82fdf0d122c6169b88e02906f8edf3168e695') or (proof['captures']['writer']['code_sha256'] != '88a8d11f40e170b90d2c78a439f88bfd476dd1874f88a3aee9297bc8f921d842'):
        raise RuntimeError('Pinned10419F1F source identity changed')

@dataclass(frozen=True)
class NativeValues:
    secondary_value: int
    civilization_id: int

def _validate(fields):
    if not isinstance(fields, EventFields) or type(fields.descriptor_bytes) is not bytes or len(fields.descriptor_bytes) != 8 or (type(fields.owner) is not int) or (not -1 <= fields.owner < 64) or (struct.unpack_from('<h', fields.descriptor_bytes)[0] != fields.owner) or (type(fields.item_id) is not int) or (not 0 <= fields.item_id <= 4294967295) or (struct.unpack_from('<I', fields.descriptor_bytes, 4)[0] != fields.item_id) or (type(fields.value) is not int) or (not 0 <= fields.value <= 4294967295) or (type(fields.selector) is not int) or (not 0 <= fields.selector <= 4294967295):
        raise ValueError('10419F1F requires exact descriptor/DWORD fields and configuration owner -1..63')

def decode_fields(fields, read) -> EventFields:
    """Decode the exact shared 23739F42/A1/D6 envelope, then bound its owner."""
    verify_source_evidence()
    result = _decode_descriptor_fields(fields, read)
    result = replace(result, owner=struct.unpack_from('<h', result.descriptor_bytes)[0])
    _validate(result)
    return result

def _profile(sequence, fields, normalizer_transform_present, per_thread_hook_present, writer_metadata_callback_present, padding_policy):
    verify_source_evidence()
    _validate(fields)
    if normalizer_transform_present is not False or per_thread_hook_present is not False or writer_metadata_callback_present is not False:
        raise ValueError('10419F1F EXE transformation or registered callbacks are unsupported')
    if type(sequence) is not int or not 1 <= sequence <= 4294967295:
        raise ValueError('10419F1F requires a nonzero uint32 sequence')
    if padding_policy != 'headless-zero-uninitialized-stack':
        raise ValueError('10419F1F requires an explicit zero policy for stack padding')

def encode_record(sequence, fields, values, *, normalizer_transform_present, per_thread_hook_present, writer_metadata_callback_present, padding_policy) -> bytes:
    """Encode exact query results; no result is substituted from a witness."""
    _profile(sequence, fields, normalizer_transform_present, per_thread_hook_present, writer_metadata_callback_present, padding_policy)
    if not isinstance(values, NativeValues) or type(values.secondary_value) is not int or (not -(1 << 31) <= values.secondary_value < 1 << 31) or (type(values.civilization_id) is not int) or (not 0 <= values.civilization_id <= 4294967295):
        raise ValueError('10419F1F requires the signed secondary result and uint32 civilization hash')
    record = bytearray(RECORD_SIZE)
    struct.pack_into('<IIII', record, 0, RECORD_SIZE, RECORD_TYPE, sequence, 0)
    struct.pack_into('<II', record, 16, 4294967295, 4294967295)
    for offset in (24, 32, 40, 48, 56):
        struct.pack_into('<HHI', record, offset, 65535, 0, 4294967295)
    struct.pack_into('<I', record, 80, sequence)
    struct.pack_into('<HHIIII', record, 88, fields.owner & 65535, 2, fields.item_id, fields.value, values.civilization_id, values.secondary_value & 4294967295)
    return bytes(record)

def produce_record(sequence, core, context, fields, *, expected_civilization_hash, normalizer_transform_present, per_thread_hook_present, writer_metadata_callback_present, padding_policy, read=None, secondary_query_api=None, config_record_lookup=None, config_value_lookup=None, key_hash=None, core_sha256='d7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'):
    """Run secondary(owner), then configuration(owner), in source order.

    The secondary result never selects the configuration record. Both calls use
    the already-pinned public Core interface helpers, including their releases,
    configuration-key checks and comparison with the configured civilization.
    """
    if core_sha256 not in ('d7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3', '259b90a473a256aff6a7d621a4f3717e46f6921c59b9817475375c88b97e8c83', '324c51e9ea3531758842e16c69e6cddbefbb226c5b675c3d6e60111646c2e98c'):
        raise ValueError('Unqualified facade engine')
    profile = dict(normalizer_transform_present=normalizer_transform_present, per_thread_hook_present=per_thread_hook_present, writer_metadata_callback_present=writer_metadata_callback_present, padding_policy=padding_policy)
    _profile(sequence, fields, **profile)
    if expected_civilization_hash is not None and (type(expected_civilization_hash) is not int or not 0 <= expected_civilization_hash <= 4294967295):
        raise ValueError('10419F1F expected civilization hash must be uint32 or absent')
    if fields.owner == -1:
        return encode_record(sequence, fields, NativeValues(-1, 4294967295), **profile)
    if read is None:
        from civ6_host.runtime.native.native_setup import local_reader
        read = local_reader()
    secondary = query_secondary_value(core, context, fields.owner, read=read, native_api=secondary_query_api, core_sha256=core_sha256)
    civilization = read_player_civilization_type_id(core, context, fields.owner, expected_hash=expected_civilization_hash, read=read, record_lookup=config_record_lookup, value_lookup=config_value_lookup, key_hash=key_hash, core_sha256=core_sha256)
    return encode_record(sequence, fields, NativeValues(secondary, civilization), **profile)
