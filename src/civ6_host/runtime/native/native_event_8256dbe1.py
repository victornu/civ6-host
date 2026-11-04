"""Source-decoded Combat payload, separate from callback lifecycle admission."""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
from dataclasses import dataclass
import struct
from civ6_host.runtime.native.native_application_mirror import decode_scalar
from civ6_host.runtime.native.native_combat_argument_snapshot import CHILD_KEYS
from civ6_host.runtime.native.native_combat_argument_snapshot import capture_borrowed_children
from civ6_host.runtime.native.native_combat_map_owner import PROOF_SHA256
from civ6_host.runtime.native.native_combat_map_owner import verify_source_evidence
from civ6_host.runtime.native.native_player_event_domains import validate_sequence
from civ6_host.runtime import xp1_combat_profile as _combat_source
EVENT_KIND, RECORD_TYPE, RECORD_SIZE = (2186730465, 248, 128)
EMPTY_DESCRIPTOR = struct.pack('<HHI', 65535, 0, 4294967295)
CHILD_SCALAR_KEYS = frozenset((126272016, 236175385, 853003252, 1116922831, 1838009406, 1930175143, 2772752662, 2943282943, 2988688941, 3031830991, 3336162054, 3548761475))

@dataclass(frozen=True)
class CombatFields:
    descriptors: tuple[bytes, bytes, bytes, bytes]
    scalar_82a7e998: int
    scalar_a7c79e07: int

def decode_fields(raw_fields, base, read, next_node, *, core_sha256='d7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'):
    verify_source_evidence()
    capture = capture_borrowed_children(EVENT_KIND, raw_fields, base, read, next_node, core_sha256=core_sha256)
    for child in capture['children'].values():
        values = {int(key, 16): bytes.fromhex(value) for key, value in child['fields'].items()}
        _combat_source.validate_child_fields(core_sha256, values, CHILD_SCALAR_KEYS)
    descriptors = tuple((bytes.fromhex(capture['children'][hex(key)]['diagnostic_pointer_payloads']['0x57c6ed30']['bytes_hex']) for key in CHILD_KEYS))
    return CombatFields(descriptors, decode_scalar(raw_fields[2192042392], 2), decode_scalar(raw_fields[2814877191], 2))

def _validate_fields(fields):
    if not isinstance(fields, CombatFields) or type(fields.descriptors) is not tuple or len(fields.descriptors) != 4:
        raise ValueError('Combat requires four copied native descriptors')
    if any((type(raw) is not bytes or len(raw) != 8 for raw in fields.descriptors)):
        raise ValueError('Combat descriptor must be exactly eight bytes')
    if any((type(value) is not int or not 0 <= value <= 4294967295 for value in (fields.scalar_82a7e998, fields.scalar_a7c79e07))):
        raise ValueError('Combat scalar must be uint32')

def query_inputs(fields):
    _validate_fields(fields)
    result = []
    for raw in fields.descriptors[:2]:
        owner, _, identifier = struct.unpack('<HHI', raw)
        result.append(None if owner == 65535 or identifier == 4294967295 else struct.unpack_from('<h', raw)[0])
    return tuple(result)

def encode_record(sequence, token, fields, query_results, *, padding_bytes, normalizer_transform_present, per_thread_hook_present, writer_metadata_callback_present):
    """Encode only; explicit stack-padding bytes confer no receiver admission.

    The caller must separately prove whether the receiver can read the two
    undefined DWORDs. There is intentionally no default zero-padding policy.
    """
    proof = verify_source_evidence()
    contract = proof['contract']
    if contract['record_type'] != RECORD_TYPE or contract['record_size'] != RECORD_SIZE or contract['undefined_record_ranges'] != ((84, 88), (124, 128)):
        raise RuntimeError('Combat writer layout source changed')
    validate_sequence(sequence)
    if type(token) is not int or not 1 <= token <= 4294967295:
        raise ValueError('Combat requires a native registry token')
    inputs = query_inputs(fields)
    if type(query_results) is not tuple or len(query_results) != 2:
        raise ValueError('Combat requires two ordered query dispositions')
    for owner, result in zip(inputs, query_results):
        if owner is None and result is not None or (owner is not None and type(result) is not bool):
            raise ValueError('Combat predicate result does not match the conditional native call')
    if any((value is not False for value in (normalizer_transform_present, per_thread_hook_present, writer_metadata_callback_present))):
        raise ValueError('Combat optional services are not implemented')
    if type(padding_bytes) is not bytes or len(padding_bytes) != 8:
        raise ValueError('Combat requires explicit bytes for both undefined DWORDs')
    record = bytearray(RECORD_SIZE)
    struct.pack_into('<IIIIii', record, 0, RECORD_SIZE, RECORD_TYPE, sequence, 0, -1, -1)
    for offset in (24, 32, 40, 48, 56):
        record[offset:offset + 8] = EMPTY_DESCRIPTOR
    for index, raw in enumerate(fields.descriptors):
        descriptor_type = struct.unpack_from('<H', raw, 2)[0]
        if descriptor_type == 1:
            record[24 + index * 8:32 + index * 8] = raw
        elif descriptor_type == 2:
            record[56:64] = raw
    selected = any((result is True for result in query_results))
    flag = 16 if selected else 0
    flag |= 1 if not selected and fields.scalar_82a7e998 != 1640240290 and (fields.scalar_a7c79e07 == 2787765495) else 2
    struct.pack_into('<I', record, 72, flag)
    struct.pack_into('<I', record, 80, sequence)
    record[84:88] = padding_bytes[:4]
    for index, raw in enumerate(fields.descriptors):
        record[88 + index * 8:96 + index * 8] = raw
    struct.pack_into('<I', record, 120, token)
    record[124:128] = padding_bytes[4:]
    return bytes(record)
