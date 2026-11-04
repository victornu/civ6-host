"""ImprovementAddedToMap notification: native1477A0 then native149560 reads."""
from __future__ import annotations
from civ6_host.runtime import turn_unit_event_profile as _turn_units
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import ctypes as C
from dataclasses import dataclass
from pathlib import Path
import struct
from civ6_host.runtime.native import native_event_a625c726 as shared
from civ6_host.runtime.native.native_deferred_empty_profile import validate_empty_profile_record
from civ6_host.runtime.native.native_source_cache import load_pinned_json
EVENT_KIND, RECORD_TYPE, RECORD_SIZE = (3853650818, 143, 144)
PROOF_SHA256 = '271b025c3e906e6f11bc899d881a9a3aa6e762db4477b642db72616c69ae2466'
PADDING_POLICY = shared.PADDING_POLICY
EventFields = shared.EventFields

def verify_source_evidence():
    if not PROOF_SHA256:
        raise RuntimeError('E5B20B82 complete source proof has not been pinned')
    path = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_event_e5b20b82.py')))).resolve().parents[1] / 'evidence/native-event-e5b20b82' / (PROOF_SHA256 + '.json')
    proof = load_pinned_json(path, PROOF_SHA256)
    if proof.get('schema') != 'civ6rl.native_event_e5b20b82.static.v1' or dict(proof['images']) != {'exe_sha256': 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63', 'core_sha256': 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'}:
        raise RuntimeError('E5B20B82 source identity changed')
    return proof

@dataclass(frozen=True)
class NativeValues:
    improvement: shared.NativeValues
    local_flag: bool

def decode_fields(raw_fields, read):
    verify_source_evidence()
    return shared.decode_fields(raw_fields, read)

def _profile(sequence, fields, **profile):
    verify_source_evidence()
    shared._profile(sequence, fields, **profile)
    header = bytearray(RECORD_SIZE)
    struct.pack_into('<II', header, 0, RECORD_SIZE, RECORD_TYPE)
    validate_empty_profile_record(header, **profile['empty_receiver_state'])

def encode_record(sequence, fields, values, **profile):
    _profile(sequence, fields, **profile)
    if not isinstance(values, NativeValues) or type(values.local_flag) is not bool:
        raise ValueError('E5B20B82 requires native improvement values and the149560 Boolean')
    record = bytearray(shared.encode_record(sequence, fields, values.improvement, **profile))
    struct.pack_into('<I', record, 4, RECORD_TYPE)
    record[134] = int(values.local_flag)
    validate_empty_profile_record(record, **profile['empty_receiver_state'])
    return bytes(record)

def query_local_flag(core, context, component_owner, *, read=None, native_api=None, application_mode_reader=None, core_sha256='d7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3', candidate_backend=None):
    """149560: read B mode first, then acquire a fresh Game facade if required."""
    _turn_tables = _turn_units.select_tables(core_sha256, {'outer': (7987232, ((144, 4382432),)), 'game': (7990488, ((8, 4409168), (296, 4410112)))})
    verify_source_evidence()
    if type(component_owner) is not int or not -1 <= component_owner <= 63:
        raise ValueError('E5B20B82 component owner is outside the established profile')
    base = int(core._handle)
    if not 0 < base < 1 << 63 or type(context) is not int or (not 0 < context < 1 << 63):
        raise ValueError('E5B20B82 requires a borrowed live Core context')
    if read is None:
        from civ6_host.runtime.native.native_setup import local_reader
        read = local_reader()
    if application_mode_reader is None:
        application = getattr(core, '_civ6rl_application_configuration', None)
        if application is None:
            raise ValueError('E5B20B82 requires the separate native application configuration B')
        application.require_context(base, context)
        from civ6_host.runtime.native.native_app_ownership import read_application_mode
        mode = _turn_units.read_application_mode(application, core_sha256=core_sha256, candidate_backend=candidate_backend)
    else:
        if native_api is None or not callable(application_mode_reader):
            raise ValueError('E5B20B82 mode-reader seam requires explicit native API seam')
        mode = application_mode_reader()
    if type(mode) is not int or not 0 <= mode <= 4294967295:
        raise ValueError('E5B20B82 mode must be the source DWORD result')
    if mode == 3915931367:
        return True
    if component_owner == -1:
        return False
    specs = {'get_game': (4382432, C.c_void_p, (C.c_void_p,)), 'get_local_team': (4410112, C.c_uint32, (C.c_void_p,)), 'release_game': (4409168, None, (C.c_void_p,))}
    specs = _turn_units.select_specs(core_sha256, specs)
    if native_api is None:
        api = {name: C.WINFUNCTYPE(result, *args)(base + rva) for name, (rva, result, args) in specs.items()}
    else:
        if type(native_api) is not dict or set(native_api) != set(specs) or any((not callable(fn) for fn in native_api.values())):
            raise ValueError('E5B20B82 local query seam needs all three native methods')
        api = native_api

    def check(pointer, table, slots):
        if type(pointer) is not int or not 0 < pointer < 1 << 63:
            raise ValueError('E5B20B82 invalid native interface pointer')
        for address, value in [(pointer, base + table)] + [(base + table + slot, base + rva) for slot, rva in slots]:
            raw = read(address, 8)
            if type(raw) is not bytes or len(raw) != 8 or struct.unpack('<Q', raw)[0] != value:
                raise ValueError('E5B20B82 local query ABI differs')
    check(context, *_turn_tables['outer'])
    game = api['get_game'](context)
    if not game:
        return False
    check(game, *_turn_tables['game'])
    try:
        local_team = api['get_local_team'](game)
        if type(local_team) is not int or not 0 <= local_team <= 4294967295:
            raise ValueError('E5B20B82 local team result must be a DWORD')
        return local_team == component_owner
    finally:
        api['release_game'](game)

def produce_record(sequence, core, context, fields, *, expected_civilization_hashes=None, normalizer_transform_present, thread_hook_present, writer_metadata_callback_present, padding_policy, empty_receiver_state, read=None, local_native_api=None, application_mode_reader=None, core_sha256='d7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3', candidate_backend=None, **query_options):
    profile = dict(normalizer_transform_present=normalizer_transform_present, thread_hook_present=thread_hook_present, writer_metadata_callback_present=writer_metadata_callback_present, padding_policy=padding_policy, empty_receiver_state=empty_receiver_state)
    _profile(sequence, fields, **profile)
    improvement = shared.query_native_values(core, context, fields, expected_civilization_hashes=expected_civilization_hashes, read=read, **query_options, core_sha256=core_sha256)
    local = query_local_flag(core, context, improvement.component_owner18, read=read, native_api=local_native_api, application_mode_reader=application_mode_reader, core_sha256=core_sha256, candidate_backend=candidate_backend)
    return encode_record(sequence, fields, NativeValues(improvement, local), **profile)
