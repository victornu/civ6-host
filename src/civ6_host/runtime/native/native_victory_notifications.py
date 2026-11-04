"""Exact TeamVictory/PlayerDefeat producers for explicit empty EXE receivers.

These callbacks serialize an existing native result. They neither choose a
winner nor eliminate a player. The Core producer's prior native06E010 call is
outside this adapter and must remain executed by Core.
"""
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
from dataclasses import dataclass
from pathlib import Path
import struct
from types import MappingProxyType
from civ6_host.runtime.native.native_application_mirror import decode_scalar
from civ6_host.runtime.native.native_source_cache import load_pinned_json
PROOF_SHA256 = '315e46c32fdea478dbec62d253759639a4366d231556f1520e4dd90fa6b57c8a'
_PROOF = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_victory_notifications.py')))).resolve().parents[1] / 'evidence/native-victory-notifications' / (PROOF_SHA256 + '.json')
TEAM_VICTORY = 477734356
PLAYER_DEFEAT = 2175010909
RECORD_SIZE = 96
PADDING_POLICY = 'source-zero-allocation'
SELECTOR_KEY, SUBJECT_KEY, RESULT_KEY = (2716180809, 3606901732, 2717631346)

@dataclass(frozen=True)
class EventSpec:
    record_type: int
    name: str
    callback_rva: int
    writer_rva: int
    row_va: int
    handler_va: int
    empty_receiver_profile: str
EVENT_SPECS = MappingProxyType({TEAM_VICTORY: EventSpec(18, 'TeamVictory', 1391296, 1188848, 5388397584, 5369583472, 'team-victory-row-12-empty'), PLAYER_DEFEAT: EventSpec(14, 'PlayerDefeat', 1357056, 1292176, 5388397392, 5369607184, 'player-defeat-row-0e-empty')})

def verify_source_evidence():
    proof = load_pinned_json(_PROOF, PROOF_SHA256)
    comparison = proof.get('family_comparison', {})
    layout = proof.get('layout', {})
    if proof.get('schema') != 'civ6rl.native_victory_notifications.static.v1' or proof.get('core_sha256') != 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3' or proof.get('exe_sha256') != 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63' or (comparison.get('callback_instruction_count') != 61) or (comparison.get('writer_instruction_count') != 139) or tuple(comparison.get('writer_differences_after_header_type_normalization', ())) or (layout.get('record_size') != RECORD_SIZE) or (layout.get('metadata_flag') != 6) or (layout.get('payload_size') != 12) or (tuple(layout.get('payload_dwords', ())) != ('sequence', 'D6FCF3E4', 'A1FBC372')) or tuple(layout.get('source_uninitialized_copied_ranges', ())):
        raise RuntimeError('Victory notification family source identity changed')
    rows = proof.get('events', ())
    if len(rows) != 2:
        raise RuntimeError('Victory notification family coverage changed')
    for kind, spec in EVENT_SPECS.items():
        row = next((r for r in rows if r.get('kind') == kind), {})
        if row.get('registry', {}).get('callback_va') != hex(5368709120 + spec.callback_rva) or row.get('writer_va') != hex(5368709120 + spec.writer_rva) or row.get('record_type') != spec.record_type or (row.get('record_size') != RECORD_SIZE) or (row.get('name') != spec.name) or (row.get('row_va') != hex(spec.row_va)) or (row.get('handler_va') != hex(spec.handler_va)):
            raise RuntimeError('Victory notification producer/receiver identity changed')
    return proof

@dataclass(frozen=True)
class EventFields:
    event_kind: int
    selector: int
    subject: int
    result_type: int

def _spec(kind):
    if type(kind) is not int or kind not in EVENT_SPECS:
        raise ValueError('Unsupported victory notification kind')
    return EVENT_SPECS[kind]

def _validate_fields(fields):
    if type(fields) is not EventFields:
        raise ValueError('Expected decoded victory notification fields')
    spec = _spec(fields.event_kind)
    if type(fields.selector) is not int or fields.selector != 0:
        raise ValueError('Only the source-produced zero selector is admitted')
    for value in (fields.subject, fields.result_type):
        if type(value) is not int or not 0 <= value <= 4294967295:
            raise ValueError('Native notification values must be exact raw DWORDs')
    return spec

def decode_fields(event_kind, raw_fields):
    verify_source_evidence()
    _spec(event_kind)
    if type(raw_fields) is not dict or set(raw_fields) != {SELECTOR_KEY, SUBJECT_KEY, RESULT_KEY} or any((type(raw) is not bytes or len(raw) != 24 for raw in raw_fields.values())):
        raise ValueError('Unverified victory notification field envelope')
    fields = EventFields(event_kind, decode_scalar(raw_fields[SELECTOR_KEY], 3), decode_scalar(raw_fields[SUBJECT_KEY], 2), decode_scalar(raw_fields[RESULT_KEY], 2))
    _validate_fields(fields)
    return fields

def _validate_empty_receiver(spec, state):
    expected = {'profile': spec.empty_receiver_profile, 'record_type': spec.record_type, 'event_name': 'GameCoreEvent::' + spec.name, 'pre_hook': None, 'post_hook': None, 'subscriber_count': 0, 'subscriber_list_empty': True, 'deferred_flag': 0}
    if type(state) is not dict or state != expected or any((type(state[key]) is not type(value) for key, value in expected.items())):
        raise ValueError('Victory notification requires its exact initialized-empty receiver')

def encode_record(sequence, fields, *, normalizer_transform_present, thread_hook_present, writer_metadata_callback_present, empty_receiver_state, padding_policy=PADDING_POLICY):
    """Serialize one record; caller owns capacity/sequence and real-row checks.

    Both scalar DWORDs are copied unchanged. The entire 12-byte copied payload
    is initialized in source. Bytes+4C..4F/+5C..5F remain zero from the writer's
    bytewise allocation loop; they are not uninitialized callback values.
    """
    verify_source_evidence()
    spec = _validate_fields(fields)
    if type(sequence) is not int or not 1 <= sequence <= 4294967295:
        raise ValueError('Victory notification sequence must be a nonzero DWORD')
    if normalizer_transform_present is not False or thread_hook_present is not False or writer_metadata_callback_present is not False:
        raise ValueError('Victory notification optional service is unsupported')
    _validate_empty_receiver(spec, empty_receiver_state)
    if type(padding_policy) is not str or padding_policy != PADDING_POLICY:
        raise ValueError('Victory notification requires source zero-allocation layout')
    record = bytearray(RECORD_SIZE)
    struct.pack_into('<IIII', record, 0, RECORD_SIZE, spec.record_type, sequence, 0)
    struct.pack_into('<II', record, 16, 4294967295, 4294967295)
    for offset in (24, 32, 40, 48, 56):
        struct.pack_into('<HHI', record, offset, 65535, 0, 4294967295)
    struct.pack_into('<I', record, 72, 6)
    struct.pack_into('<III', record, 80, sequence, fields.subject, fields.result_type)
    return bytes(record)
