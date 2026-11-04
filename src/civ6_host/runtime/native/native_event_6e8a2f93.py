"""Source-pinned unit descriptor plus float-packed DWORD notification."""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
from dataclasses import dataclass
from pathlib import Path
import struct
from civ6_host.runtime.native.native_application_mirror import decode_scalar
from civ6_host.runtime.native.native_host_events import copy_eight_byte_variant
from civ6_host.runtime.native.native_source_cache import load_pinned_json
EVENT_KIND, RECORD_TYPE, RECORD_SIZE = (1854549907, 27, 112)
SELECTOR_KEY, DESCRIPTOR_KEY, VALUE_KEY = (2716180809, 4032072631, 3606901732)
PINNED_EVIDENCE_SHA256 = '210a41c09bc9382704d8a93e98e919b8b043130f7b4b7d3100d3b87ecb2188d0'
_PROOF = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_event_6e8a2f93.py')))).resolve().parents[1] / 'evidence/native-event-6e8a2f93' / f'{PINNED_EVIDENCE_SHA256}.json'

def verify_source_evidence():
    proof = load_pinned_json(_PROOF, PINNED_EVIDENCE_SHA256)
    if proof['schema'] != 'civ6rl.native_event_6e8a2f93.static.v1' or proof['exe_sha256'] != 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63' or proof['registration']['kind'] != EVENT_KIND or (proof['registration']['callback_va'] != '0x140157dc0') or (proof['captures']['callback']['code_sha256'] != '795c885a1242887c0e4bbb884aa23db7e77c906153b90d22a148318d47ba06d2') or (proof['captures']['writer']['code_sha256'] != '575a4fe786d5412ecbbc6bc4c5999eb8eb2f0bd026330b944d21aad3921c5cc6') or (proof['captures']['normalizer']['code_sha256'] != 'c757d2f0c927f36e058ff5e57350a80beac1db2a89d3940fcb5e89c05545f23e') or (proof['float_multiplier']['raw_hex'] != '00008043') or (proof['float_multiplier']['va'] != '0x140fbf530'):
        raise RuntimeError('6E8A2F93 producer source identity changed')
    return proof

@dataclass(frozen=True)
class EventFields:
    selector: int
    descriptor_bytes: bytes
    owner: int
    item_id: int
    value_bits: int

def pack_float32_bits(value_bits: int) -> int:
    """Translate the source CVTTSS2SI/AL/SHL path in its verified domain.

    The input is its native float32 bit pattern, never a Python float rounded
    back to float32. For nonnegative normal inputs below2^31, subtraction of
    the integer part and multiplication by256 are exactly representable.
    Negative/nonfinite/subnormal/out-of-range paths remain unimplemented;
    neither their exception behavior nor MXCSR denormal state is assumed.
    Both signed zero patterns follow the source result zero.
    """
    if type(value_bits) is not int or not 0 <= value_bits <= 4294967295:
        raise ValueError('6E8A2F93 requires exact uint32 float bits')
    magnitude = value_bits & 2147483647
    if magnitude == 0:
        return 0
    exponent = value_bits >> 23 & 255
    if value_bits >> 31 or exponent == 0 or magnitude >= 1325400064:
        raise ValueError('6E8A2F93 float lies outside the source-verified numeric profile')
    value = struct.unpack('<f', struct.pack('<I', value_bits))[0]
    integral = int(value)
    fraction_byte = int((value - integral) * 256.0) & 255
    return integral << 8 & 4294967295 | fraction_byte

def _validate(fields):
    if not isinstance(fields, EventFields) or type(fields.selector) is not int or (not 0 <= fields.selector <= 4294967295) or (type(fields.descriptor_bytes) is not bytes) or (len(fields.descriptor_bytes) != 8) or (type(fields.owner) is not int) or (not 0 <= fields.owner <= 65535) or (type(fields.item_id) is not int) or (not 0 <= fields.item_id <= 4294967295) or (struct.unpack_from('<H', fields.descriptor_bytes)[0] != fields.owner) or (struct.unpack_from('<I', fields.descriptor_bytes, 4)[0] != fields.item_id):
        raise ValueError('6E8A2F93 requires consistent decoded unit identity and selector')
    pack_float32_bits(fields.value_bits)

def decode_fields(raw_fields, read) -> EventFields:
    verify_source_evidence()
    if not isinstance(raw_fields, dict) or set(raw_fields) != {SELECTOR_KEY, DESCRIPTOR_KEY, VALUE_KEY}:
        raise ValueError('6E8A2F93 requires exactly three source-backed keys')
    if any((type(raw) is not bytes or len(raw) != 24 for raw in raw_fields.values())):
        raise ValueError('6E8A2F93 requires complete byte variants')
    descriptor = copy_eight_byte_variant(raw_fields[DESCRIPTOR_KEY], read, expected_tag=1024)
    fields = EventFields(decode_scalar(raw_fields[SELECTOR_KEY], 3), descriptor, struct.unpack_from('<H', descriptor)[0], struct.unpack_from('<I', descriptor, 4)[0], decode_scalar(raw_fields[VALUE_KEY], 4))
    _validate(fields)
    return fields

def encode_record(sequence, fields, *, normalizer_transform_present, per_thread_hook_present, writer_metadata_callback_present, padding_policy) -> bytes:
    verify_source_evidence()
    _validate(fields)
    if normalizer_transform_present is not False or per_thread_hook_present is not False or writer_metadata_callback_present is not False:
        raise ValueError('6E8A2F93 transformations or registered callbacks are unsupported')
    if type(sequence) is not int or not 1 <= sequence <= 4294967295:
        raise ValueError('6E8A2F93 requires a nonzero uint32 sequence')
    if padding_policy != 'headless-zero-uninitialized-stack':
        raise ValueError('6E8A2F93 requires an explicit zero policy for source stack gaps')
    record = bytearray(RECORD_SIZE)
    struct.pack_into('<IIII', record, 0, RECORD_SIZE, RECORD_TYPE, sequence, 0)
    struct.pack_into('<II', record, 16, 4294967295, 4294967295)
    struct.pack_into('<HHI', record, 24, fields.owner, 1, fields.item_id)
    for offset in (32, 40, 48, 56):
        struct.pack_into('<HHI', record, offset, 65535, 0, 4294967295)
    struct.pack_into('<I', record, 80, sequence)
    struct.pack_into('<HHI', record, 88, fields.owner, 1, fields.item_id)
    struct.pack_into('<I', record, 96, pack_float32_bits(fields.value_bits))
    return bytes(record)
