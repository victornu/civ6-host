"""2842CE14 callback, including undefined38F only under a proven empty receiver."""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
from dataclasses import dataclass
from pathlib import Path
import struct
from civ6_host.runtime.native.native_application_mirror import decode_scalar
from civ6_host.runtime.native.native_host_events import copy_eight_byte_variant
from civ6_host.runtime.native.native_source_cache import load_pinned_json
EVENT_KIND, RECORD_TYPE, RECORD_SIZE = (675466772, 95, 112)
SELECTOR_KEY, DESCRIPTOR_KEY = (2716180809, 594779970)
D6_KEY, A1FBC_KEY, SCALAR_38F_KEY = (3606901732, 2717631346, 955421384)
PINNED_EVIDENCE_SHA256 = 'bf605385bba96f490faf6fabb8710ab344722dede73fa993a5b3364f204fa186'
_PROOF = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_event_2842ce14.py')))).resolve().parents[1] / 'evidence/native-event-2842ce14' / f'{PINNED_EVIDENCE_SHA256}.json'

def verify_source_evidence():
    proof = load_pinned_json(_PROOF, PINNED_EVIDENCE_SHA256)
    if proof.get('schema') != 'civ6rl.native_event_2842ce14.static.v2' or proof['parent']['sha256'] != '32a287701ed04375eebb20c2ef9a73adf0d66331acf5fd9d28929e0d25d1b00b' or proof['exe_sha256'] != 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63' or (proof['registration']['callback_va'] != '0x140141a40') or (proof['registration']['kind'] != EVENT_KIND) or (proof['captures']['callback']['code_sha256'] != '6e2f7442b5a050f1f678b8ec52031474c3fcf721b0cfb497e0404f93ad7b7834') or (proof['captures']['writer']['code_sha256'] != '52b74b4707438e78e51ceae87b60567fcc7d7b10b2dc677c5e3b462f22d49a95') or (proof['captures']['normalizer']['code_sha256'] != 'c757d2f0c927f36e058ff5e57350a80beac1db2a89d3940fcb5e89c05545f23e') or (proof['empty_receiver_source']['row']['record_type'] != '0x5f') or (proof['empty_receiver_source']['row']['handler_body_sha256'] != '864bf77f68b8a4e5de1e3e57d618a67496ad960201c67ae08f251ecddce77709'):
        raise RuntimeError('Pinned 2842CE14 source identity changed')

@dataclass(frozen=True)
class EventFields:
    selector: int
    descriptor_bytes: bytes
    owner: int
    item_id: int
    d6_value: int
    a1fbc_value: int
    scalar_38f_value: int | None

def _validate(fields):
    if not isinstance(fields, EventFields) or type(fields.selector) is not int or (not 0 <= fields.selector <= 4294967295) or (type(fields.descriptor_bytes) is not bytes) or (len(fields.descriptor_bytes) != 8) or (type(fields.owner) is not int) or (not 0 <= fields.owner <= 65535) or (type(fields.item_id) is not int) or (not 0 <= fields.item_id <= 4294967295) or (struct.unpack_from('<H', fields.descriptor_bytes)[0] != fields.owner) or (struct.unpack_from('<I', fields.descriptor_bytes, 4)[0] != fields.item_id) or any((type(value) is not int or not 0 <= value <= 4294967295 for value in (fields.d6_value, fields.a1fbc_value))) or (fields.scalar_38f_value is not None and (type(fields.scalar_38f_value) is not int or not 0 <= fields.scalar_38f_value <= 4294967295)):
        raise ValueError('2842CE14 requires exact decoded descriptor and selector fields')

def decode_fields(fields, read) -> EventFields:
    verify_source_evidence()
    required = {SELECTOR_KEY, DESCRIPTOR_KEY, D6_KEY, A1FBC_KEY}
    if not isinstance(fields, dict) or set(fields) not in (required, required | {SCALAR_38F_KEY}):
        raise ValueError('2842CE14 requires its exact four/five-key shape')
    descriptor = copy_eight_byte_variant(fields[DESCRIPTOR_KEY], read, expected_tag=1024)
    result = EventFields(decode_scalar(fields[SELECTOR_KEY], 3), descriptor, struct.unpack_from('<H', descriptor)[0], struct.unpack_from('<I', descriptor, 4)[0], decode_scalar(fields[D6_KEY], 2), decode_scalar(fields[A1FBC_KEY], 2), decode_scalar(fields[SCALAR_38F_KEY], 2) if SCALAR_38F_KEY in fields else None)
    _validate(result)
    return result

def encode_record(sequence, fields, *, normalizer_transform_present, per_thread_hook_present, writer_metadata_callback_present, padding_policy, undefined_normalized_value_policy='refuse', empty_receiver_state=None) -> bytes:
    """Copy city identity and three raw DWORDs; keep writer default metadata.

    A1 is normalized but unread by this callback. Positive A1FBC is copied
    without a Core query. Missing38F leaves normalized+58 uninitialized and
    requires a validated empty receiver before diagnostic zero filling.
    No notification counter or cache gate is read.
    """
    verify_source_evidence()
    _validate(fields)
    if normalizer_transform_present is not False or per_thread_hook_present is not False or writer_metadata_callback_present is not False:
        raise ValueError('2842CE14 EXE transformation or registered callbacks are unsupported')
    if type(sequence) is not int or not 1 <= sequence <= 4294967295:
        raise ValueError('2842CE14 requires a nonzero uint32 sequence')
    if padding_policy != 'headless-zero-uninitialized-stack':
        raise ValueError('2842CE14 requires an explicit zero policy for stack padding')
    if fields.scalar_38f_value is None:
        if undefined_normalized_value_policy != 'zero-unread-empty-receiver-payload':
            raise ValueError('2842CE14 normalized+58 is uninitialized; explicit empty-receiver policy required')
        if not isinstance(empty_receiver_state, dict) or set(empty_receiver_state) != {'observer_registered', 'state_pointer_nonnull', 'pre_hook', 'post_hook', 'subscriber_count', 'state_flags'}:
            raise ValueError('2842CE14 missing38F requires complete empty receiver state')
    elif undefined_normalized_value_policy != 'refuse' or empty_receiver_state is not None:
        raise ValueError('2842CE14 undefined-value policy is only valid when38F is absent')
    record = bytearray(RECORD_SIZE)
    struct.pack_into('<IIII', record, 0, RECORD_SIZE, RECORD_TYPE, sequence, 0)
    struct.pack_into('<II', record, 16, 4294967295, 4294967295)
    for offset in (24, 32, 40, 48, 56):
        struct.pack_into('<HHI', record, offset, 65535, 0, 4294967295)
    struct.pack_into('<I', record, 80, sequence)
    struct.pack_into('<HHI', record, 88, fields.owner, 2, fields.item_id)
    struct.pack_into('<III', record, 96, fields.d6_value, fields.a1fbc_value, 0 if fields.scalar_38f_value is None else fields.scalar_38f_value)
    if fields.scalar_38f_value is None:
        from civ6_host.runtime.native.native_deferred_empty_profile import validate_empty_profile_record
        validate_empty_profile_record(record, **empty_receiver_state)
    return bytes(record)
