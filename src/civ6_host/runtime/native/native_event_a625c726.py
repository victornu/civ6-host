"""Source-backed ImprovementOwnershipChanged producer; native reads only.

The event's D6 value is not the owner used by the EXE query. The component's
native owner selects the secondary/configuration queries. No gameplay mutator
is replayed by this notification adapter.
"""
from __future__ import annotations
from civ6_host.runtime import turn_unit_event_profile as _turn_units
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import ctypes as C
from dataclasses import dataclass
from pathlib import Path
import struct
from civ6_host.runtime.native.native_application_mirror import decode_scalar
from civ6_host.runtime.native.native_deferred_empty_profile import validate_empty_profile_record
from civ6_host.runtime.native.native_event_c3183902 import _guarded
from civ6_host.runtime.native.native_event_c3183902 import _checked_buffer
from civ6_host.runtime.native.native_event_fa5b1159 import query_secondary_value
from civ6_host.runtime.native.native_event_fa5b1159 import read_player_civilization_type_id
from civ6_host.runtime.native.native_host_events import copy_eight_byte_variant
from civ6_host.runtime.native.native_source_cache import load_pinned_json
EVENT_KIND, RECORD_TYPE, RECORD_SIZE = (2787493670, 148, 144)
POSITION_KEY, SELECTOR_KEY, VALUE_KEY = (2353434172, 2716180809, 3606901732)
PROOF_SHA256 = '30f7abb2dadf857672e0f0e75c5f1cd9c732f809dbf4a5f7196b8e11f737fa36'
PADDING_POLICY = 'zero-unread-empty-receiver-payload'
_TABLES = {'outer': (7987232, ((168, 4382784),)), 'map': (7991792, ((8, 4416608), (64, 4418176))), 'plot': (7994424, ((8, 4435728), (96, 4436448), (384, 4435856), (376, 4435760), (48, 4435888), (200, 4437504), (192, 4437040), (224, 4437440))), 'component': (7736072, ((8, 77312), (16, 77504), (24, 77440), (48, 77344)))}

def verify_source_evidence():
    if not PROOF_SHA256:
        raise RuntimeError('A625C726 complete source proof has not been pinned')
    path = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_event_a625c726.py')))).resolve().parents[1] / 'evidence/native-event-a625c726' / (PROOF_SHA256 + '.json')
    proof = load_pinned_json(path, PROOF_SHA256)
    if proof.get('schema') != 'civ6rl.native_event_a625c726.static.v1' or dict(proof['images']) != {'exe_sha256': 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63', 'core_sha256': 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'}:
        raise RuntimeError('A625C726 pinned source identity changed')
    return proof

@dataclass(frozen=True)
class EventFields:
    position_bytes: bytes
    x: int
    y: int
    selector: int
    value: int

@dataclass(frozen=True)
class NativeValues:
    city_owner: int
    city_id: int
    component_value10: int
    component_owner18: int
    component_value30: int
    secondary_value: int
    civilization_id: int
    snapshot180_word4: int
    plot_value30: int
    plot_flagc8: int
    plot_valuec0: int
    plot_flage0: int

def _fields(fields):
    if not isinstance(fields, EventFields) or type(fields.position_bytes) is not bytes or len(fields.position_bytes) != 8 or (type(fields.x) is not int) or (type(fields.y) is not int) or (struct.unpack('<ii', fields.position_bytes) != (fields.x, fields.y)) or any((type(v) is not int or not 0 <= v <= 4294967295 for v in (fields.selector, fields.value))):
        raise ValueError('A625C726 requires consistent source position and DWORD fields')

def decode_fields(raw_fields, read):
    verify_source_evidence()
    if type(raw_fields) is not dict or set(raw_fields) != {POSITION_KEY, SELECTOR_KEY, VALUE_KEY}:
        raise ValueError('A625C726 requires exactly position, selector and D6 fields')
    position = copy_eight_byte_variant(raw_fields[POSITION_KEY], read, expected_tag=0)
    fields = EventFields(position, *struct.unpack('<ii', position), decode_scalar(raw_fields[SELECTOR_KEY], 3), decode_scalar(raw_fields[VALUE_KEY], 2))
    _fields(fields)
    return fields

def _profile(sequence, fields, normalizer_transform_present, thread_hook_present, writer_metadata_callback_present, padding_policy, empty_receiver_state):
    verify_source_evidence()
    _fields(fields)
    if type(sequence) is not int or not 1 <= sequence <= 2147483647:
        raise ValueError('A625C726 sequence exceeds the bounded native queue profile')
    if normalizer_transform_present is not False or thread_hook_present is not False or writer_metadata_callback_present is not False:
        raise ValueError('A625C726 requires absent optional hook/services')
    if padding_policy != PADDING_POLICY:
        raise ValueError('A625C726 requires an explicit unread-payload padding policy')
    if type(empty_receiver_state) is not dict or set(empty_receiver_state) != {'observer_registered', 'state_pointer_nonnull', 'pre_hook', 'post_hook', 'subscriber_count', 'state_flags'} or type(empty_receiver_state['state_flags']) is not int or (empty_receiver_state['state_flags'] != 0):
        raise ValueError('A625C726 requires the complete empty receiver profile')
    header = bytearray(RECORD_SIZE)
    struct.pack_into('<II', header, 0, RECORD_SIZE, RECORD_TYPE)
    validate_empty_profile_record(header, **empty_receiver_state)

def _int_range(value, low, high, name):
    if type(value) is not int or not low <= value <= high:
        raise ValueError('A625C726 invalid native ' + name)
    return value

def encode_record(sequence, fields, values, *, normalizer_transform_present, thread_hook_present, writer_metadata_callback_present, padding_policy, empty_receiver_state):
    _profile(sequence, fields, normalizer_transform_present, thread_hook_present, writer_metadata_callback_present, padding_policy, empty_receiver_state)
    record = pack_plot_snapshot_record(RECORD_TYPE, sequence, fields.position_bytes, values)
    validate_empty_profile_record(record, **empty_receiver_state)
    return record

def _position(position_bytes):
    if type(position_bytes) is not bytes or len(position_bytes) != 8:
        raise ValueError('Native plot query requires exactly eight position bytes')
    return struct.unpack('<ii', position_bytes)

def pack_plot_snapshot_record(record_type, sequence, position_bytes, values):
    """Pure common writer layout; the caller must prove its own receiver/type.

    No raw event fields, optional hooks, receiver profile or native interface
    are created here. A625 validates its profile before this packer and the
    independently proved 30AE callback does the same for its actual row.
    """
    verify_source_evidence()
    _position(position_bytes)
    _int_range(record_type, 0, 4294967295, 'record type')
    _int_range(sequence, 1, 2147483647, 'bounded record sequence')
    if not isinstance(values, NativeValues):
        raise ValueError('A625C726 requires all native query results')
    for name in ('city_id', 'civilization_id', 'plot_value30'):
        _int_range(getattr(values, name), 0, 4294967295, name)
    for name in ('component_value10', 'component_value30'):
        _int_range(getattr(values, name), -(1 << 31), 4294967295, name)
    for name in ('secondary_value', 'plot_valuec0'):
        _int_range(getattr(values, name), -(1 << 31), (1 << 31) - 1, name)
    _int_range(values.component_owner18, -1, 63, 'component owner')
    _int_range(values.city_owner, -128, 127, 'snapshot178 owner')
    _int_range(values.snapshot180_word4, -32768, 32767, 'snapshot180 WORD')
    for name in ('plot_flagc8', 'plot_flage0'):
        _int_range(getattr(values, name), 0, 255, name)
    if values.component_owner18 == -1 and (values.secondary_value != -1 or values.civilization_id != 4294967295):
        raise ValueError('A625C726 absent component owner must preserve both source sentinels')
    record = bytearray(RECORD_SIZE)
    struct.pack_into('<IIII', record, 0, RECORD_SIZE, record_type, sequence, 0)
    record[16:24] = b'\xff' * 8
    record[24:64] = bytes.fromhex('ffff0000ffffffff') * 5
    struct.pack_into('<I', record, 80, sequence)
    record[88:96] = position_bytes
    struct.pack_into('<HHI', record, 96, values.city_owner & 65535, 2, values.city_id)
    struct.pack_into('<IIIIIII', record, 104, values.component_value10 & 4294967295, values.component_owner18 & 4294967295, values.component_value30 & 4294967295, values.secondary_value & 4294967295, values.civilization_id, values.snapshot180_word4 & 4294967295, values.plot_value30)
    record[132:136] = bytes((values.plot_flagc8, int(values.plot_valuec0 > 0), 0, values.plot_flage0))
    return bytes(record)

def _check(read, base, pointer, label, *, core_sha256='d7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'):
    if type(pointer) is not int or not 0 < pointer < 1 << 63:
        raise ValueError('A625C726 null/invalid ' + label + ' facade')
    table, slots = _turn_units.select_tables(core_sha256, _TABLES)[label]
    for address, expected in [(pointer, base + table)] + [(base + table + slot, base + target) for slot, target in slots]:
        raw = read(address, 8)
        if type(raw) is not bytes or len(raw) != 8 or struct.unpack('<Q', raw)[0] != expected:
            raise ValueError('A625C726 unexpected ' + label + ' interface/method')

def _api(base, provided, *, core_sha256='d7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'):
    specs = {'outer_map': (4382784, C.c_void_p, (C.c_void_p,)), 'get_plot': (4418176, C.c_void_p, (C.c_void_p, C.c_int32, C.c_int32)), 'release_map': (4416608, None, (C.c_void_p,)), 'release_plot': (4435728, None, (C.c_void_p,)), 'plot_component': (4436448, C.c_void_p, (C.c_void_p,)), 'release_component': (77312, None, (C.c_void_p,)), 'snapshot180': (4435856, C.c_uint64, (C.c_void_p, C.c_void_p, C.c_uint32)), 'snapshot178': (4435760, C.c_uint64, (C.c_void_p, C.c_void_p, C.c_uint32)), 'component10': (77504, C.c_uint32, (C.c_void_p,)), 'component18': (77440, C.c_int32, (C.c_void_p,)), 'component30': (77344, C.c_uint32, (C.c_void_p,)), 'plot30': (4435888, C.c_uint32, (C.c_void_p,)), 'plotc8': (4437504, C.c_uint8, (C.c_void_p,)), 'plotc0': (4437040, C.c_int32, (C.c_void_p,)), 'plote0': (4437440, C.c_uint8, (C.c_void_p,))}
    specs = _turn_units.select_specs(core_sha256, specs)
    if provided is not None:
        if type(provided) is not dict or set(provided) != set(specs) or any((not callable(fn) for fn in provided.values())):
            raise ValueError('A625C726 test seam requires all fifteen native operations')
        return provided
    return {name: C.WINFUNCTYPE(restype, *args)(base + rva) for name, (rva, restype, args) in specs.items()}

def _snapshot(function, plot):
    storage, output = _guarded(24)
    C.memset(output, 165, 24)
    function(plot, output, 0)
    return _checked_buffer(storage, 24)

def query_native_values(core, context, fields, *, expected_civilization_hashes=None, read=None, native_api=None, secondary_query_api=None, config_record_lookup=None, config_value_lookup=None, key_hash=None, core_sha256='d7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'):
    """Mirror 1477A0, releasing component/plot before callback record encoding."""
    verify_source_evidence()
    _fields(fields)
    return query_native_values_at_position(core, context, fields.position_bytes, expected_civilization_hashes=expected_civilization_hashes, read=read, native_api=native_api, secondary_query_api=secondary_query_api, config_record_lookup=config_record_lookup, config_value_lookup=config_value_lookup, key_hash=key_hash, core_sha256=core_sha256)

def query_native_values_at_position(core, context, position_bytes, *, expected_civilization_hashes=None, read=None, native_api=None, secondary_query_api=None, config_record_lookup=None, config_value_lookup=None, key_hash=None, core_sha256='d7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'):
    """1477A0 takes only a position; no selector or extra D6 value is invented."""
    verify_source_evidence()
    x, y = _position(position_bytes)
    identities = {} if expected_civilization_hashes is None else expected_civilization_hashes
    if type(identities) is not dict or any((type(k) is not int or not 0 <= k < 64 or type(v) is not int or (not 0 <= v <= 4294967295) for k, v in identities.items())):
        raise ValueError('A625C726 expected civilization map must use uint32 hashes for slots0..63')
    base = int(core._handle)
    if not 0 < base < 1 << 63 or type(context) is not int or (not 0 < context < 1 << 63):
        raise ValueError('A625C726 needs a live relocated Core context')
    if read is None:
        from civ6_host.runtime.native.native_setup import local_reader
        read = local_reader()
    _check(read, base, context, 'outer', core_sha256=core_sha256)
    api = _api(base, native_api, core_sha256=core_sha256)
    map_object = api['outer_map'](context)
    _check(read, base, map_object, 'map', core_sha256=core_sha256)
    try:
        plot = api['get_plot'](map_object, x, y)
    finally:
        api['release_map'](map_object)
    _check(read, base, plot, 'plot', core_sha256=core_sha256)
    component = None
    component_validated = False
    try:
        component = api['plot_component'](plot)
        _check(read, base, component, 'component', core_sha256=core_sha256)
        component_validated = True
        snap180 = _snapshot(api['snapshot180'], plot)
        value10 = api['component10'](component)
        owner18 = _int_range(api['component18'](component), -1, 63, 'component owner')
        value30 = api['component30'](component)
        secondary = query_secondary_value(core, context, owner18, read=read, native_api=secondary_query_api, core_sha256=core_sha256)
        civilization = 4294967295 if owner18 == -1 else read_player_civilization_type_id(core, context, owner18, expected_hash=identities.get(owner18), read=read, record_lookup=config_record_lookup, value_lookup=config_value_lookup, key_hash=key_hash, core_sha256=core_sha256)
        word4 = struct.unpack_from('<h', snap180, 4)[0]
        plot30 = api['plot30'](plot)
        flagc8 = api['plotc8'](plot)
        valuec0 = api['plotc0'](plot)
        flage0 = api['plote0'](plot)
        snap178 = _snapshot(api['snapshot178'], plot)
        return NativeValues(struct.unpack_from('<b', snap178, 20)[0], struct.unpack_from('<I', snap178, 4)[0], value10, owner18, value30, secondary, civilization, word4, plot30, flagc8, valuec0, flage0)
    finally:
        try:
            if component_validated:
                api['release_component'](component)
        finally:
            api['release_plot'](plot)

def produce_record(sequence, core, context, fields, *, expected_civilization_hashes=None, normalizer_transform_present, thread_hook_present, writer_metadata_callback_present, padding_policy, empty_receiver_state, core_sha256='d7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3', **query_options):
    profile = dict(normalizer_transform_present=normalizer_transform_present, thread_hook_present=thread_hook_present, writer_metadata_callback_present=writer_metadata_callback_present, padding_policy=padding_policy, empty_receiver_state=empty_receiver_state)
    _profile(sequence, fields, **profile)
    values = query_native_values(core, context, fields, expected_civilization_hashes=expected_civilization_hashes, **query_options, core_sha256=core_sha256)
    return encode_record(sequence, fields, values, **profile)
