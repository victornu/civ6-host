"""No-EXE-record contract for Core event 0x80F1366D.

Core performs its own internal listener dispatch before calling the host A0
event resolver.  The pinned EXE has no A0 callback registered for this kind;
its resolver returns zero for a missing key.  Consequently this adapter
validates the observed Core descriptor and intentionally emits no deferred
record.  It does not emulate Core's internal listeners.
"""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import struct
from dataclasses import dataclass
from civ6_host.runtime.native.native_absent_scalar_a0 import validate_absent_scalar_a0
EVENT_KIND = 2163291757
CORE_PRODUCER = 6444264736
CORE_BUILDER = 6447195472
EXE_CALLBACK_RESOLVER = 5370037744
EXE_REGISTRATION_COUNT = 317
FIELD_A1 = 2716180809
FIELD_D6 = 3606901732

@dataclass(frozen=True)
class ValidatedNoHostRecord:
    event_kind: int
    selector: int
    value: int
    host_record: None = None

def decode_fields(raw_fields: dict[int, bytes]) -> ValidatedNoHostRecord:
    """Validate the exact observed two-field Core descriptor.

    Bytes 4..7 in each 24-byte variant are deliberately ignored: the Core
    setters write tag, payload and flags but leave that padding unspecified.
    """
    if not isinstance(raw_fields, dict) or set(raw_fields) != {FIELD_A1, FIELD_D6}:
        raise ValueError('Unverified 0x80F1366D descriptor keys')
    validate_absent_scalar_a0(EVENT_KIND, raw_fields)
    selector = struct.unpack_from('<I', raw_fields[FIELD_A1], 8)[0]
    value = struct.unpack_from('<I', raw_fields[FIELD_D6], 8)[0]
    return ValidatedNoHostRecord(EVENT_KIND, selector, value)
