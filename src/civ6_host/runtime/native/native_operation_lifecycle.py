"""Recognize a consumed native MOVE_TO without inventing a combat result.

Only the isolated delivery window is considered. The notifications carry the
unit and operation, not the target coordinates or an operation success code.
"""
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
from dataclasses import dataclass
from pathlib import Path
import hashlib, struct
from civ6_host.runtime.native.native_source_cache import load_pinned_json
from civ6_host.runtime.native import native_event_15c35863 as added
from civ6_host.runtime.native import native_event_a60328c5 as deactivated
from civ6_host.runtime.native import native_event_383669f1 as cleared
SOURCE_SHA = '48a65a120b5351ab7d0cc474d526593c215961ed22b4027673497850fd120292'
LAYOUT_SHA = 'da924d6488971966b15233f0225142fcd11a062c2a1455cc82fc4e999cb394a3'
CORE_SHA = 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'

@dataclass(frozen=True)
class DeliveryWindow:
    archive: bytes
    records: tuple[bytes, ...]
    consumed_before: int
    consumed_after: int

def verify_source():
    base = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_operation_lifecycle.py')))).resolve().parents[1] / 'work/attack-boundary943'
    p = load_pinned_json(base / 'lifecycle-source.json', SOURCE_SHA)
    layout = load_pinned_json(base / 'request-layout-source.json', LAYOUT_SHA)
    if p['core_sha256'] != CORE_SHA or layout['core_sha256'] != CORE_SHA:
        raise ValueError('Operation lifecycle engine changed')
    return p['contract']

def completed_cycle(window, selected, player_id, queued_before, queued_after):
    """Return a separate disposition, or None when this narrow proof is absent.

    The caller must snapshot an initially empty event/command transport around
    exactly one delivery, then run its normal validated event consumers. Full
    record encoding is checked against the existing no-hook host profile.
    """
    contract = verify_source()
    if window is None:
        return None
    if type(window) is not DeliveryWindow:
        raise ValueError('Unverified operation delivery window')
    if selected['operation'] != 'MOVE_TO' or queued_before != {'unit_present': True, 'plot_id': None} or queued_after != {'unit_present': True, 'plot_id': None}:
        return None
    if type(window.archive) is not bytes or not 24 <= len(window.archive) <= 6784 or type(window.records) is not tuple or (not 1 <= len(window.records) <= 4096) or (type(window.consumed_before) is not int) or (type(window.consumed_after) is not int) or (not 0 <= window.consumed_before < window.consumed_after <= 4294967295):
        raise ValueError('Invalid operation delivery boundary')
    if window.consumed_after - window.consumed_before != len(window.records):
        raise ValueError('Operation event delivery was not isolated and fully consumed')
    message, owner, entity_type, unit, index = struct.unpack_from('<IHHII', window.archive)
    if message != contract['message_type'] or (owner, entity_type, unit) != (player_id, 1, selected['unit_id']) or index > 2047:
        raise ValueError('Native operation archive identity mismatch')
    lifecycle = []
    for offset, raw in enumerate(window.records, 1):
        if type(raw) is not bytes or len(raw) < 84:
            raise ValueError('Malformed native event record')
        size, kind, seq, metadata = struct.unpack_from('<IIII', raw)
        if size != len(raw) or metadata != 0 or seq != window.consumed_before + offset or (struct.unpack_from('<I', raw, 80)[0] != seq):
            raise ValueError('Stale, reordered or malformed native operation events')
        if kind not in (67, 70, 71, 35, 275):
            return None
        if kind == 275:
            continue
        descriptor = struct.pack('<HHI', player_id, 1, selected['unit_id'])
        if raw[24:32] != descriptor or raw[88:96] != descriptor:
            return None
        if kind == 35:
            continue
        if len(raw) != 112:
            raise ValueError('Wrong lifecycle record size')
        first, second = struct.unpack_from('<II', raw, 96)
        if kind == 67:
            if (first, second) != (0, index):
                return None
            fields = added.EventFields(0, index, 1, descriptor)
            expected = added.encode_queue_record(seq, added.encode_fields(fields), blob_contents=descriptor, padding_policy='headless-zero-initialization')
        else:
            if kind == 70 and (first != contract['operation_hash'] or second not in (0, 1)):
                return None
            if kind == 71 and (first, second) != (0, 0):
                return None
            fields = deactivated.EventFields(0, first, second, player_id, selected['unit_id'])
            codec = deactivated if kind == 70 else cleared
            expected = codec.encode_record(seq, fields, normalizer_transform_present=False, per_thread_hook_present=False, writer_metadata_callback_present=False, padding_policy='headless-zero-uninitialized-stack')
        if raw != expected:
            raise ValueError('Lifecycle record differs from the verified host encoding')
        lifecycle.append(dict(type=kind, sequence=seq, record_hex=raw.hex()))
    if [r['type'] for r in lifecycle] != [67, 70, 71]:
        return None
    return dict(status='MOVE_TO_added_deactivated_cleared', player_id=player_id, unit_id=unit, operation_index=index, operation_hash=contract['operation_hash'], records=lifecycle, archive_sha256=hashlib.sha256(window.archive).hexdigest(), consumed_before=window.consumed_before, consumed_after=window.consumed_after, source_sha256=SOURCE_SHA, layout_source_sha256=LAYOUT_SHA, operation_success=None, combat_resolution_inferred=False, path_failure_inferred=False, target_or_destination_proven_by_events=False)
