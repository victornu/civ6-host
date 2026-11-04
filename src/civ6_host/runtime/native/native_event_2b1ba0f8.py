"""Source-backed type58 descriptor/position producer with three native queries."""
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
from pathlib import Path
import struct
from civ6_host.runtime.native import native_event_fa5b1159 as shared
from civ6_host.runtime.native.native_source_cache import load_pinned_json
EVENT_KIND, RECORD_TYPE, RECORD_SIZE = (723230968, 88, 128)
EventFields = shared.EventFields
PINNED_EVIDENCE_SHA256 = '12a617afcb217a89b879b380c3e91a59d39f49e2710b94877bcd3992079de4e2'
_PROOF = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_event_2b1ba0f8.py')))).resolve().parents[1] / 'evidence/native-event-2b1ba0f8' / f'{PINNED_EVIDENCE_SHA256}.json'

def verify_source_evidence():
    proof = load_pinned_json(_PROOF, PINNED_EVIDENCE_SHA256)
    if proof['schema'] != 'civ6rl.native_event_2b1ba0f8.static.v2' or proof['image']['sha256'] != shared.EXE_SHA256 or proof['core_sha256'] != shared.CORE_SHA256 or (proof['registry']['registration']['callback_va'] != '0x140141430') or (proof['writer_layout']['record_type'] != '0x58') or (proof['shared_query_proofs']['fa5']['sha256'] != shared.PINNED_EVIDENCE_SHA256):
        raise RuntimeError('2B1BA0F8 callback/writer/shared query source changed')

def _validate(fields):
    if not isinstance(fields, EventFields) or type(fields.descriptor_bytes) is not bytes or len(fields.descriptor_bytes) != 8 or (type(fields.position_bytes) is not bytes) or (len(fields.position_bytes) != 8) or (type(fields.descriptor_word) is not int) or (type(fields.descriptor_dword) is not int) or (struct.unpack_from('<H', fields.descriptor_bytes)[0] != fields.descriptor_word) or (struct.unpack_from('<I', fields.descriptor_bytes, 4)[0] != fields.descriptor_dword) or (type(fields.x) is not int) or (type(fields.y) is not int) or (struct.unpack('<ii', fields.position_bytes) != (fields.x, fields.y)) or (type(fields.selector) is not int) or (not 0 <= fields.selector <= 4294967295):
        raise ValueError('2B1BA0F8 requires complete decoded native descriptor/position fields')

def decode_fields(raw_fields, read):
    verify_source_evidence()
    fields = shared.decode_fields(raw_fields, read)
    _validate(fields)
    return fields

def _profile(sequence, fields, normalizer_transform_present, producer_hook_present, queue_metadata_service_present, padding_policy):
    verify_source_evidence()
    _validate(fields)
    if normalizer_transform_present is not False or producer_hook_present is not False or queue_metadata_service_present is not False:
        raise ValueError('2B1BA0F8 requires explicitly absent EXE transforms/hooks/metadata callbacks')
    if type(sequence) is not int or not 1 <= sequence <= 4294967295:
        raise ValueError('2B1BA0F8 requires a nonzero uint32 sequence')
    if padding_policy != 'headless-zero-uninitialized-callback-stack':
        raise ValueError('2B1BA0F8 requires explicit zero padding')

def encode_record(sequence, fields, *, plot_value, secondary_value, civilization_id, normalizer_transform_present, producer_hook_present, queue_metadata_service_present, padding_policy):
    _profile(sequence, fields, normalizer_transform_present, producer_hook_present, queue_metadata_service_present, padding_policy)
    record = bytearray(shared.encode_record(sequence, fields, plot_value=plot_value, secondary_value=secondary_value, civilization_id=civilization_id, producer_hook_present=producer_hook_present, queue_metadata_service_present=queue_metadata_service_present, padding_policy=padding_policy))
    struct.pack_into('<I', record, 4, RECORD_TYPE)
    return bytes(record)

def produce_record(sequence, core, context, fields, *, expected_civilization_hash=None, expected_civilization_hashes=None, normalizer_transform_present, producer_hook_present, queue_metadata_service_present, padding_policy, read=None, query1_api=None, query2_api=None, config_record_lookup=None, config_value_lookup=None, key_hash=None, core_sha256='d7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'):
    """Run plot(position), secondary(plot result), configuration(plot result).

    The query/configuration player comes from the native plot result, not the
    incoming descriptor owner. The configured civilization hash is a check,
    never a substitute. The shared first-result=-1 path preserves all three
    source sentinels and does not query configuration.
    """
    if core_sha256 not in ('d7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3', '259b90a473a256aff6a7d621a4f3717e46f6921c59b9817475375c88b97e8c83', '324c51e9ea3531758842e16c69e6cddbefbb226c5b675c3d6e60111646c2e98c'):
        raise ValueError('Unqualified facade engine')
    profile = dict(normalizer_transform_present=normalizer_transform_present, producer_hook_present=producer_hook_present, queue_metadata_service_present=queue_metadata_service_present, padding_policy=padding_policy)
    _profile(sequence, fields, **profile)
    first, second, third = shared.query_callback_values(core, context, fields, expected_civilization_hash=expected_civilization_hash, expected_civilization_hashes=expected_civilization_hashes, read=read, query1_api=query1_api, query2_api=query2_api, config_record_lookup=config_record_lookup, config_value_lookup=config_value_lookup, key_hash=key_hash, core_sha256=core_sha256)
    return encode_record(sequence, fields, plot_value=first, secondary_value=second, civilization_id=third, **profile)
