"""Source-scoped E23B112D FoundCity-adjacent unit event adapter.

The module validates callback fields, queries the native Unit through Core's
source-matched parameter-map layout, and encodes the EXE queue record with an
explicit zero-padding policy. It does not dispatch the event consumer.
"""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import struct
import ctypes as C
import hashlib
from pathlib import Path
from civ6_host.runtime.native.native_source_cache import load_pinned_json
from civ6_host.runtime.native.native_application_mirror import decode_scalar
from civ6_host.runtime.native.native_host_events import copy_eight_byte_variant
EVENT_KIND = 3795521837
SELECTOR_KEY = 2716180809
SELECTOR_VALUE = 3606901732
ENTITY_KEY = 4032072631
SELECTOR = 1225574625
SELECTOR_PROOF_SHA256 = '89586a31ea27f7ad882b5bbad44fee0c0915328a8ba1010600d904ecca4a0850'
_SELECTOR_PROOF_PATH = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_found_city_event.py')))).resolve().parents[1] / 'evidence/native-e23b-selectors' / f'{SELECTOR_PROOF_SHA256}.json'
SOURCE_PROOF_SHA256 = 'a24ffc52b8c654c49efd7c1679f9d2fb44dc8d28dda6092da2b2d6e70fd74c00'
_SOURCE_PROOF_PATH = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_found_city_event.py')))).resolve().parents[1] / 'evidence/native-event-e23b112d.json'
UNIT_VTABLE_SLOTS = {168: 4441552, 176: 4441504}
PARAMETER_KEYS = (1914727735, 3419107253, 4141723702, 658064137)
CORE_PARAMETER_CTOR = 7621504
CORE_PARAMETER_DTOR = 7621792
CORE_PARAMETER_LOOKUP = 7625984
CORE_PARAMETER_VTABLE = 8507296
CORE_UNIT_A8 = 4441552
CORE_UNIT_B0 = 4441504
PINNED_CORE_SHA256 = 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'
CORE_CODE_PINS = {(CORE_PARAMETER_CTOR, 164): 'bfd0c4a367ecaa8a1e9007f41dcf84cb8f645ac6b894f774ef463315adb26ea5', (CORE_PARAMETER_DTOR, 183): '3cf8985f616148800977da94da8d0862230d475831ccbda5cd92c3a5efa884ab', (CORE_PARAMETER_LOOKUP, 66): '5ad2fd83afca2d7c94e3d208d1de3dfa839cbf9a52066778acadc09bcf724de8', (CORE_UNIT_A8, 91): '92a8c628c23b1c22daa096d160acb6551d8969b059530477735a1501eed8a81f', (CORE_UNIT_B0, 46): 'f8992129be5e5addad0176b89db6c736fb3e676777b176181f8e64a26d07000c', (4441550, 1): 'ae3f4619b0413d70d3004b9131c3752153074e45725be13b9a148978895e359e'}

def verify_selector_source():
    doc = load_pinned_json(_SELECTOR_PROOF_PATH, SELECTOR_PROOF_SHA256)
    if doc['schema'] != 'civ6rl.native_e23b_selectors.v1' or doc['query_selector'] != SELECTOR or dict(doc['metadata_offsets']) != {'sequence': 0, 'owner': 8, 'type': 10, 'identifier': 12, 'selector': 16, 'a8_result': 20, 'cbcb6fb5': 24, 'f6ddb036': 28, '72206d37': 32, '27394309': 36}:
        raise RuntimeError('E23B selector/detail block source differs')
    source = load_pinned_json(_SOURCE_PROOF_PATH, SOURCE_PROOF_SHA256)
    if source['schema'] != 'civ6rl.native_event_e23b112d.v1' or source['images']['exe_sha256'] != 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63':
        raise RuntimeError('E23B query source identity differs')

    def at(body):
        return {i['va']: i['text'] for f in body['fragments'] for i in f['instructions']}
    callback = at(doc['callback'])
    lookup = at(source['lookup_contract']['exe_function'])
    required_callback = {'0x140154b04': 'call 0x140148030', '0x140154b10': 'je 0x140154bb6', '0x140154b1c': 'call qword ptr [rax + 0xa8]', '0x140154b29': 'call 0x1407a44a0', '0x140154b38': 'call qword ptr [rax + 0xb0]', '0x140154ba6': 'call 0x1407a45c0', '0x140154bb3': 'call qword ptr [rax + 0x10]', '0x140154c27': 'call 0x140128910'}
    required_lookup = {'0x14014805c': 'movsx edx, word ptr [rbp]', '0x140148060': 'call qword ptr [rax + 0xb8]', '0x14014806c': 'je 0x1401480af', '0x140148079': 'call qword ptr [rax + 0x110]', '0x14014808b': 'call qword ptr [rax + 0x10]', '0x140148097': 'call qword ptr [rax + 8]', '0x1401480a0': 'call qword ptr [rax + 8]', '0x1401480b4': 'mov qword ptr [rsi], 0'}
    if any((callback.get(k) != v for k, v in required_callback.items())) or any((lookup.get(k) != v for k, v in required_lookup.items())):
        raise RuntimeError('E23B owner domain or query/release order differs')
    return source

def _identity(identity):
    if not isinstance(identity, dict):
        raise ValueError('E23B requires a decoded Unit identity dictionary')
    owner, entity_type, identifier = (identity.get('owner'), identity.get('entity_type'), identity.get('identifier'))
    if type(owner) is not int or not 0 <= owner <= 65535 or type(entity_type) is not int or (entity_type != 1) or (type(identifier) is not int) or (not 0 <= identifier <= 4294967295):
        raise ValueError(f"E23B Unit identity outside transport profile: owner={owner!r}, type={entity_type!r}, identifier={identifier!r}, selector={identity.get('selector')!r}")
    return (owner, entity_type, identifier)

def decode_found_city_fields(fields: dict[int, bytes], read) -> dict[str, int | str]:
    """Validate the observed callback arguments and copy its 8-byte identity.

    ``read`` must copy from a caller-owned bounded address space, as required
    by ``copy_eight_byte_variant``. Pointer bytes are never interpreted as
    identity data. Entity type 1 is the only native Unit descriptor observed
    for this callback family.
    """
    verify_selector_source()
    if set(fields) != {SELECTOR_KEY, SELECTOR_VALUE, ENTITY_KEY}:
        raise ValueError('Unverified E23B112D field set')
    selector_kind = decode_scalar(fields[SELECTOR_KEY], 3)
    selector = decode_scalar(fields[SELECTOR_VALUE], 2)
    if selector_kind != 0:
        raise ValueError('Unverified E23B112D selector')
    blob = copy_eight_byte_variant(fields[ENTITY_KEY], read, expected_tag=1024)
    owner, entity_type, identifier = struct.unpack('<HHI', blob)
    result = {'owner': owner, 'entity_type': entity_type, 'identifier': identifier, 'selector': selector, 'source_blob_hex': blob.hex()}
    _identity(result)
    return result

def _query_source_identity(core_sha256, execution_image):
    if execution_image is None:
        return core_sha256
    reference = getattr(execution_image, 'reference_core_sha256', None)
    if (not isinstance(reference, str) or len(reference) != 64
            or core_sha256 not in (PINNED_CORE_SHA256, reference)):
        raise ValueError('FoundUnit query source ABI differs from its selected execution image')
    return reference


def unit_query_contract(*, core_sha256=PINNED_CORE_SHA256, execution_image=None) -> dict:
    """Return the statically verified query route; performs no native calls."""
    from civ6_host.runtime.found_unit_event_profiles import query_abi
    core_sha256 = _query_source_identity(core_sha256, execution_image)
    abi = query_abi(core_sha256, execution_image=execution_image)
    return {'exe_unit_lookup_va': 5370052656, 'core_unit_vtable_va': 6442450944 + abi.tables['unit'][0], 'core_unit_slots': dict(abi.tables['unit'][1]), 'selector_gate': SELECTOR, 'parameter_keys': PARAMETER_KEYS, 'parameter_container_exe_ctor_va': 5376722080, 'parameter_container_exe_dtor_va': 5376722368, 'parameter_lookup_exe_va': 5376726528, 'native_b0_query_implemented': True, 'core_parameter_ctor_rva': abi.constants['CORE_PARAMETER_CTOR'], 'core_parameter_dtor_rva': abi.constants['CORE_PARAMETER_DTOR'], 'core_parameter_lookup_rva': abi.constants['CORE_PARAMETER_LOOKUP'], 'core_parameter_vtable_rva': abi.constants['CORE_PARAMETER_VTABLE'], 'pinned_core_sha256': abi.core_sha256, 'source_proof_sha256': SOURCE_PROOF_SHA256, 'owner_transport': 'uint16; the query sign-extends this WORD to the native +B8 DWORD', 'query_null_policy': 'refuse; no substituted native values', 'query_lifetime': 'units/player release before A8; A8 then parameter ctor/B0/lookups/dtor; unit release before hook/writer/enqueue', 'core_code_pins': {f'{rva:x}:{size}': digest for (rva, size), digest in abi.code_pins.items()}}

def query_unit_parameters(core, context, identity: dict, *, incoming_selector: int, read=None, invoke=None, native_api=None, core_sha256=PINNED_CORE_SHA256, execution_image=None) -> dict:
    """Read the callback's A8 result and four B0 parameters from native Core.

    The incoming selector is checked before any lookup, as in EXE callback
    0x140154A30. A8's return is preserved as payload data and is not compared
    with that selector. ``invoke`` is an optional test seam; production calls
    the pinned Core virtual targets directly. Unlike UnitCreated, every owned
    query object is released BEFORE this callback's hook/writer/enqueue. This
    function deliberately is not a lease spanning the caller's enqueue.
    """
    from civ6_host.runtime.found_unit_event_profiles import query_abi
    attached_image = getattr(core, '_civ6_host_execution_image', None)
    if execution_image is not None and execution_image is not attached_image:
        raise ValueError('FoundUnit query image is not owned by its Core')
    execution_image = attached_image
    core_sha256 = _query_source_identity(core_sha256, execution_image)
    abi = query_abi(core_sha256, execution_image=execution_image)
    verify_selector_source()
    if type(incoming_selector) is not int or incoming_selector != SELECTOR:
        raise ValueError('E23B112D selector does not enter the native query path')
    owner, entity_type, identifier = _identity(identity)
    if 'selector' in identity and (type(identity['selector']) is not int or identity['selector'] != incoming_selector):
        raise ValueError('E23B native query selector disagrees with decoded fields')
    lookup_owner = owner if owner < 32768 else owner | 4294901760
    base = int(core._handle)
    if read is None:
        from civ6_host.runtime.native.native_setup import local_reader
        read = local_reader()
    original_read = read

    def read(address, size):
        raw = original_read(address, size)
        if not isinstance(raw, (bytes, bytearray)) or len(raw) != size:
            raise ValueError(f'E23B truncated native read: address={address:#x}, size={size}')
        return bytes(raw)
    if native_api is None:
        for (rva, size), expected in abi.code_pins.items():
            actual = hashlib.sha256(read(base + rva, size)).hexdigest()
            if actual != expected:
                raise ValueError(f'Pinned Core code changed at RVA {rva:#x}')
    TABLES = abi.tables

    def verify(pointer, table):
        vt, slots = TABLES[table]
        if not pointer or int.from_bytes(read(pointer, 8), 'little') != base + vt:
            raise ValueError(f'E23B unexpected {table} interface: pointer={pointer or 0:#x}, owner={owner}, type={entity_type}, selector={incoming_selector:#x}')
        for offset, rva in slots.items():
            if int.from_bytes(read(base + vt + offset, 8), 'little') != base + rva:
                raise ValueError('Unexpected ' + table + ' callback')

    def call(table, slot, result, pointer, *args):
        if invoke is not None:
            return invoke(table, slot, pointer, *args)
        rva = TABLES[table][1][slot]
        fn = C.WINFUNCTYPE(result, C.c_void_p, *[C.c_uint32] * len(args))(base + rva)
        return fn(pointer, *args)
    verify(context, 'outer')
    inner = int.from_bytes(read(context + 8, 8), 'little')
    if not inner or int.from_bytes(read(inner, 8), 'little') != base + abi.inner_vtable_rva:
        raise ValueError('Unexpected inner native context')
    if native_api is None:
        ctor = C.WINFUNCTYPE(C.c_void_p, C.c_void_p)(base + abi.constants['CORE_PARAMETER_CTOR'])
        dtor = C.WINFUNCTYPE(None, C.c_void_p)(base + abi.constants['CORE_PARAMETER_DTOR'])
        lookup = C.WINFUNCTYPE(C.c_void_p, C.c_void_p, C.c_uint32)(base + abi.constants['CORE_PARAMETER_LOOKUP'])
        unit_a8 = C.WINFUNCTYPE(C.c_uint32, C.c_void_p)(base + abi.constants['CORE_UNIT_A8'])
        unit_b0 = C.WINFUNCTYPE(None, C.c_void_p, C.c_void_p)(base + abi.constants['CORE_UNIT_B0'])
    else:
        required = {'parameter_ctor', 'parameter_dtor', 'parameter_lookup', 'unit_a8', 'unit_b0'}
        if set(native_api) != required:
            raise ValueError('Native query test seam must supply every called entry point')
        ctor = native_api['parameter_ctor']
        dtor = native_api['parameter_dtor']
        lookup = native_api['parameter_lookup']
        unit_a8 = native_api['unit_a8']
        unit_b0 = native_api['unit_b0']
    unit = None
    try:
        player = call('outer', 184, C.c_void_p, context, lookup_owner)
        verify(player, 'player')
        try:
            units = call('player', 272, C.c_void_p, player)
            verify(units, 'units')
            try:
                candidate = call('units', 16, C.c_void_p, units, identifier)
                verify(candidate, 'unit')
                unit = candidate
            finally:
                call('units', 8, None, units)
        finally:
            call('player', 8, None, player)
        unit_vt = int.from_bytes(read(unit, 8), 'little')
        if unit_vt != base + TABLES['unit'][0]:
            raise ValueError('Unexpected native Unit vtable')
        if int.from_bytes(read(unit_vt + 168, 8), 'little') != base + abi.constants['CORE_UNIT_A8'] or int.from_bytes(read(unit_vt + 176, 8), 'little') != base + abi.constants['CORE_UNIT_B0']:
            raise ValueError('Native Unit parameter-query vtable slots changed')
        a8 = unit_a8(unit)
        if type(a8) is not int or not 0 <= a8 <= 4294967295:
            raise ValueError('E23B native Unit +A8 did not return a uint32')
        storage = C.create_string_buffer(176)
        ptr = C.addressof(storage)
        C.memset(ptr + 160, 165, 16)
        if ctor(ptr) != ptr:
            raise RuntimeError('Native parameter-map constructor changed its result')
        try:
            if int.from_bytes(read(ptr, 8), 'little') != base + abi.constants['CORE_PARAMETER_VTABLE']:
                raise ValueError('Unexpected native parameter-map vtable')
            lookup_address = int.from_bytes(read(base + abi.constants['CORE_PARAMETER_VTABLE'] + 96, 8), 'little')
            if lookup_address != base + abi.constants['CORE_PARAMETER_LOOKUP']:
                raise ValueError('Native parameter-map hash lookup slot changed')
            if native_api is None:
                lookup = C.WINFUNCTYPE(C.c_void_p, C.c_void_p, C.c_uint32)(lookup_address)
            unit_b0(unit, ptr)
            values, present = ({}, [])
            for key in PARAMETER_KEYS:
                variant = lookup(ptr, key)
                if variant:
                    values[key] = int.from_bytes(read(variant + 8, 4), 'little')
                    present.append(key)
                else:
                    values[key] = 4294967295
            return {'a8_result': a8, 'parameters': values, 'present_parameter_keys': tuple(present), 'parameter_vtable_rva': abi.constants['CORE_PARAMETER_VTABLE']}
        finally:
            dtor(ptr)
            if read(ptr + 160, 16) != b'\xa5' * 16:
                raise RuntimeError('Native parameter-map destructor exceeded its verified storage')
    finally:
        if unit is not None:
            call('unit', 16, C.c_void_p, unit, 1)

def encode_record(sequence: int, identity: dict, query: dict | None, *, queue_callback_result: int=0, padding_policy: str='zero') -> bytes:
    """Encode the EXE type-0x23 / 0x80-byte row with explicit zero padding.

    This mirrors the source-initialized callback payload and metadata fields.
    The queue callback result is explicit; its empty headless value is zero.
    """
    verify_selector_source()
    if type(sequence) is not int or not 1 <= sequence <= 4294967295:
        raise ValueError('Sequence must be a nonzero uint32')
    if padding_policy != 'zero':
        raise ValueError('Only the explicit zero-padding diagnostic policy is implemented')
    if type(queue_callback_result) is not int or not 0 <= queue_callback_result <= 4294967295:
        raise ValueError('Queue callback result must be uint32')
    owner, entity_type, identifier = _identity(identity)
    selector = identity.get('selector')
    if type(selector) is not int or not 0 <= selector <= 4294967295:
        raise ValueError('E23B requires the incoming DWORD selector')
    if selector != SELECTOR:
        if query is not None:
            raise ValueError('E23B nonmatching selector must not query the native Unit')
        query = {'a8_result': 0, 'parameters': {key: 4294967295 for key in PARAMETER_KEYS}}
    elif not isinstance(query, dict):
        raise ValueError('E23B matching selector requires the native Unit query')
    if type(query.get('a8_result')) is not int or not 0 <= query['a8_result'] <= 4294967295:
        raise ValueError('Unverified Unit +A8 result')
    params = query.get('parameters')
    if not isinstance(params, dict) or set(params) != set(PARAMETER_KEYS):
        raise ValueError('Unverified native Unit parameter set')
    if any((type(params[k]) is not int or not 0 <= params[k] <= 4294967295 for k in PARAMETER_KEYS)):
        raise ValueError('Native Unit parameters must be raw uint32 values')
    payload = bytearray(60)
    struct.pack_into('<IIHHI', payload, 0, 4294967295, 4294967295, owner, entity_type, identifier)
    for offset, pair in ((16, (65535, 0)), (24, (65535, 0)), (32, (65535, 0)), (40, (65535, 0))):
        struct.pack_into('<HHI', payload, offset, pair[0], pair[1], 4294967295)
    struct.pack_into('<Q', payload, 48, 0)
    struct.pack_into('<I', payload, 56, 0)
    metadata = bytearray(40)
    struct.pack_into('<I', metadata, 0, sequence)
    struct.pack_into('<HHIII', metadata, 8, owner, entity_type, identifier, selector, query['a8_result'])
    for offset, key in ((24, PARAMETER_KEYS[1]), (28, PARAMETER_KEYS[2]), (32, PARAMETER_KEYS[0]), (36, PARAMETER_KEYS[3])):
        struct.pack_into('<I', metadata, offset, params[key])
    record = bytearray(128)
    struct.pack_into('<IIII', record, 0, 128, 35, sequence, queue_callback_result)
    record[16:76] = payload
    record[80:120] = metadata
    return bytes(record)
