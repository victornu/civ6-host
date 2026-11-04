"""Source-pinned XP2 Game wrapper queries used by the Storm event path.

This module forwards the official Core getters. It does not recreate their
query rules. Returned DWORDs are copied before temporary Core storage and
borrowed interfaces are released.
"""
from __future__ import annotations

import ctypes as C
import hashlib
import struct
from dataclasses import dataclass

from .configuration_profiles import XP2_CORE_SHA256
from .foundation_facade_profiles import query_abi
from .native.native_source_cache import load_pinned_json
from .paths import resource_root
from .a0_family_source import _path, verify_pinned_files

SOURCE = (
    'work/host-extensions/xp2-turn-event-family/accessor-source-profile-v2.json',
    'b39623a6a17ffd5b148625d133dbcad46a8f8c2290c704449912b4032c41b66b',
)
PARENT_SOURCE = (
    'work/host-extensions/xp2-turn-event-family/accessor-source-profile-v1.json',
    '4d67cc72a8bc8499334b0368c591e5120776c63e8089a5f83bddf881165619a2',
)
CALLER_SOURCE = (
    'work/host-extensions/xp2-turn-event-family/source-profile-v1.json',
    '21180213a91f5292da14fac2cf37ecb21a76bdd26a75b7ecccc7921b355aa844',
)
GENERATOR_SOURCES = (
    ('work/host-extensions/xp2-turn-event-family/capture_accessors_v2.py',
     'abda47beea8ccd76b2a8e0e724d9f143e11a5f5838b9eee70b8f9f24db35dbb6'),
    ('work/host-extensions/xp2-turn-event-family/capture_accessors.py',
     '2620ee5838c7a19b500bc14a3fda4e647b28786042ae0577dcc6aecf1f703a12'),
    ('work/host-extensions/xp2-turn-event-family/capture_profile.py',
     '0aad5cabff7eeb39f7eff8c5e80f977c6e41ffc2d77735da89296051ae252acd'),
    ('work/host-extensions/xp2-turn-event-family/source-profile-v1.json',
     '21180213a91f5292da14fac2cf37ecb21a76bdd26a75b7ecccc7921b355aa844'),
)
SERVICE_IID = bytes.fromhex('4f85c4393751b540aca81bd9f7d7fe89')
SERVICE_IID_RVA = 0xA10EB8
GAME_VTABLE_RVA = 0xA10EE8
GAME_SERVICE_SLOT = 0x28
GAME_SERVICE_FACTORY_RVA = 0x596EE0
SERVICE_WRAPPER_VTABLE_RVA = 0xA110F0
SERVICE_LIST_SLOT = 0xF8
SERVICE_LIST_RVA = 0x598D00
SERVICE_PAIR_SLOT = 0x110
SERVICE_PAIR_RVA = 0x598C50
SERVICE_WRAPPER_RELEASE_SLOT = 8
SERVICE_WRAPPER_RELEASE_RVA = 0x597B90
VECTOR_GROW_RVA = 0x34E680
VECTOR_FREE_RVA = 0x36E20
MAX_VECTOR_ITEMS = 65536
_CODE = {
    # RVA: (length, exact normalized-code SHA-256)
    0x596EE0: (849, 'cb7810fa4e52238117f64a59fc836311511e8d9b6944271f8961bf985694801c'),
    0x597B50: (26, '23cd981b114c0a0da2391be6deaa597007251b6e57f2453e92b4b874eba84c0c'),
    0x598D00: (209, 'd193dd86f35ce580cfd466ef1581510cd9fa8798e885d6cb51a0f7f7e586c8f1'),
    0x598C50: (176, '9d3585b93ade702b5f27261c7328c0fdcbb00fe107c5e82b2d160eb2dfb37ec7'),
    0x1BEFF0: (77, '79e29e20c72d742a9a48db2d99b0deee037939c68fae1e27b8cc42cdbf75d564'),
    0x1BE890: (62, '7dac1f0214945aaf3b39bc327211aacd72a58839df8db2d0e2adc7c7ef162931'),
    0x1BED10: (724, '280b2af8d7b6ead39d1e150a5df508e8550bfee105b51e28632c13d76811b344'),
    0x34E680: (399, '338bde50f2fbcf49ef0b2bfc8d0e653b2bee7b80c79fd9273125a9786357ce14'),
    0x597B90: (23, 'c9fda055d3ab23701fa59acf1b43e96ced835ea193ac61f628319db137cf9ce2'),
    0x58FF80: (25, '8037312239ed7704522c2b26a99f3b23c0df745e7f63fdc3d94c5f49b9c36a8b'),
    0x36E20: (8, '80f82ae6935a9258b88f365deeaec9f4a1367be3f73f13fbbcee7fffc9b6aace'),
    0x994970: (29, 'c64b398cd47e15a0ede9d3dd0946521e87b7bc1693166cb281bd1383c713dddd'),
    0x990900: (20, 'd4add3ae596b86aaa2155a67408c109b56597fbfa3dfc2a047fed8cb4f87352c'),
    0x9908F0: (7, '7d3c98984ace7ad7ce6fa069c6c1e66985a12eba3f464f373aa7bfbaa09d020e'),
}


class _Vector(C.Structure):
    _fields_ = [('begin', C.c_void_p), ('end', C.c_void_p), ('capacity', C.c_void_p)]


@dataclass(frozen=True)
class StormQueryResult:
    """Copied native results; `position` is absent when +0x110 said false."""

    items: tuple[int, ...]
    positions: tuple[bytes, ...]
    position: tuple[int, int] | None


def _flatten(body):
    return body.get('instructions') or [row for fragment in body['fragments'] for row in fragment['instructions']]


def _body_bytes(body):
    return b''.join(bytes.fromhex(row['bytes']) for row in _flatten(body))


def source():
    profile = load_pinned_json(_path(SOURCE[0]), SOURCE[1])
    parent = load_pinned_json(_path(PARENT_SOURCE[0]), PARENT_SOURCE[1])
    caller_profile = load_pinned_json(_path(CALLER_SOURCE[0]), CALLER_SOURCE[1])
    if (profile.get('schema') != 'civ6-host.xp2-turn-event-accessors.static.v2'
            or profile.get('native_execution') is not False
            or profile.get('process_memory_read') is not False
            or profile.get('parent_profile') != {'path': PARENT_SOURCE[0], 'sha256': PARENT_SOURCE[1]}
            or profile.get('validation', {}).get('all_instruction_bytes_match_pinned_xp2_image') is not True
            or profile.get('validation', {}).get('complete_unwind_bodies') is not True
            or profile.get('images', {}).get('xp2', {}).get('sha256') != XP2_CORE_SHA256
            or profile.get('images', {}).get('exe', {}).get('sha256') != 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63'
            or SERVICE_IID.hex() != '4f85c4393751b540aca81bd9f7d7fe89'
            or profile.get('iid_evidence', {}).get('core_rva') != '0xa10eb8'
            or profile.get('iid_evidence', {}).get('exe_rva') != '0xfbf4b0'
            or profile.get('iid_evidence', {}).get('core_bytes') != SERVICE_IID.hex()
            or profile.get('iid_evidence', {}).get('exe_bytes') != SERVICE_IID.hex()
            or profile.get('iid_evidence', {}).get('exact_match') is not True
            or profile.get('contract', {}).get('vector_element_width') != 4
            or profile.get('contract', {}).get('vector_free') != {
                'target': '0x36e20',
                'abi': 'void(ptr vector_descriptor, ptr begin, size_t capacity_bytes)',
            }):
        raise RuntimeError('XP2 Storm accessor source contract differs')
    if (set(profile.get('functions', {})) != {hex(rva) for rva in (0x597B90, 0x58FF80, 0x36E20, 0x994970, 0x990900, 0x9908F0)}
            or profile.get('contract', {}).get('service_iid') != SERVICE_IID.hex()
            or profile.get('contract', {}).get('game_service_factory') != {
                'table': '0xa10ee8', 'slot': '0x28', 'target': '0x596ee0', 'abi': 'ptr(ptr game, ptr iid16)'}
            or profile.get('contract', {}).get('service_query_list') != {
                'slot': '0xf8', 'target': '0x598d00', 'abi': 'void(ptr wrapper, ptr request_key8, ptr vector24)'}
            or profile.get('contract', {}).get('service_query_pair') != {
                'slot': '0x110', 'target': '0x598c50', 'abi': 'uint8(ptr wrapper, ptr request_key8, ptr out_dword_pair8)'}
            or profile.get('contract', {}).get('service_wrapper_vtable') != '0xa110f0'
            or profile.get('contract', {}).get('game_acquire') != {
                'table': '0xa101e8', 'slot': '0x90', 'target': '0x5901a0', 'abi': 'ptr(ptr outer_context)'}
            or profile.get('contract', {}).get('game_release') != {
                'table': '0xa10ee8', 'slot': '0x8', 'target': '0x596dd0', 'abi': 'void(ptr game)'}):
        raise RuntimeError('XP2 Storm facade lifetime contract differs')
    if parent.get('schema') != 'civ6-host.xp2-turn-event-accessors.static.v1':
        raise RuntimeError('XP2 Storm parent accessor source schema differs')
    if profile.get('iid_evidence', {}).get('exe_caller') != parent.get('caller'):
        raise RuntimeError('XP2 Storm caller/IID source join differs')
    caller_name = parent.get('caller', {}).get('source_profile_function')
    caller_body = caller_profile.get('functions', {}).get(caller_name, {}).get('capture')
    caller_raw = _body_bytes(caller_body) if caller_body else b''
    caller_rows = _flatten(caller_body) if caller_body else ()
    caller_instructions = {row.get('va'): row for row in caller_rows}
    caller_contract = {
        '0x140146d94': 'call qword ptr [rax + 0x28]',
        '0x140146dcc': 'call qword ptr [rax + 0xf8]',
        '0x140146ecd': 'call qword ptr [rax + 0x110]',
        '0x140146ef9': 'call 0x14019d350',
        '0x140146f04': 'call qword ptr [rax + 8]',
        '0x140146f0d': 'call qword ptr [rax + 8]',
    }
    iid_load = caller_instructions.get('0x140146d7f', {})
    if (not caller_body
            or hashlib.sha256(caller_raw).hexdigest() != parent.get('caller', {}).get('source_sha256')
            or any(caller_instructions.get(address, {}).get('text') != text
                   for address, text in caller_contract.items())
            or tuple(iid_load.get('rip_targets', ())) != ('0x140fbf4b0',)):
        raise RuntimeError('XP2 Storm official EXE caller order or IID source differs')
    for rva, (length, digest) in _CODE.items():
        key = hex(rva)
        body = (parent.get('functions', {}).get(key, {}).get('body')
                if key in parent.get('functions', {}) else profile.get('functions', {}).get(key, {}).get('body'))
        if body is None:
            raise RuntimeError('XP2 Storm source body is absent: ' + key)
        raw = _body_bytes(body)
        if len(raw) != length or hashlib.sha256(raw).hexdigest() != digest:
            raise RuntimeError('XP2 Storm source code contract differs: ' + key)
    return profile


def source_dependencies():
    """Return the exact Core facade and accessor source closure for XP2."""
    selected = source()
    from .foundation_facade_profiles import source_dependencies as facade_dependencies
    pins = dict(facade_dependencies(core_sha256=XP2_CORE_SHA256))
    from .xp2_weather_position import source_dependencies as position_dependencies
    for path, digest in position_dependencies().items():
        if path in pins and pins[path] != digest:
            raise ValueError('Conflicting XP2 Storm position-query dependency')
        pins[path] = digest
    for relative, digest in (SOURCE, PARENT_SOURCE, CALLER_SOURCE, *GENERATOR_SOURCES):
        path = str(_path(relative))
        previous = pins.get(path)
        if previous is not None and previous != digest:
            raise ValueError('Conflicting XP2 Storm source dependency')
        pins[path] = digest
    verify_pinned_files(pins)
    return pins


def _read_exact(read, address, size, label):
    raw = read(address, size)
    if type(raw) is not bytes or len(raw) != size:
        raise ValueError('XP2 Storm query needs an exact read for ' + label)
    return raw


def _qword(read, address, label):
    return struct.unpack('<Q', _read_exact(read, address, 8, label))[0]


def _verify_live_code(base, read):
    profile = source()
    parent = load_pinned_json(_path(PARENT_SOURCE[0]), PARENT_SOURCE[1])
    bodies = {**{key: row['body'] for key, row in parent['functions'].items()},
              **{key: row['body'] for key, row in profile['functions'].items()}}
    for rva, (length, digest) in _CODE.items():
        body = bodies[hex(rva)]
        raw = _body_bytes(body)
        if len(raw) != length or hashlib.sha256(raw).hexdigest() != digest:
            raise RuntimeError('XP2 Storm code pin changed: ' + hex(rva))
        fragments = body.get('fragments')
        if fragments:
            for fragment in fragments:
                expected = bytes.fromhex(fragment['raw_hex'])
                if _read_exact(read, base + int(fragment['start_rva'], 16), len(expected), hex(rva)) != expected:
                    raise ValueError('XP2 Storm live code bytes differ: ' + hex(rva))
        else:
            rows = _flatten(body)
            for row in rows:
                if _read_exact(read, base + int(row['rva'], 16), len(bytes.fromhex(row['bytes'])), hex(rva)) != bytes.fromhex(row['bytes']):
                    raise ValueError('XP2 Storm live code bytes differ: ' + hex(rva))


def _verify_live_once(core, base, read):
    key = (base, XP2_CORE_SHA256, SOURCE[1], PARENT_SOURCE[1])
    if getattr(core, '_civ6_host_xp2_storm_source_verification', None) == key:
        return
    source_dependencies()
    _verify_live_code(base, read)
    from .foundation_facade_profiles import verify_xp1_once as verify_facades_once
    verify_facades_once(core, base, read, resource_root(), core_sha256=XP2_CORE_SHA256)
    core._civ6_host_xp2_storm_source_verification = key


def _native_calls(native_calls, *, include_pair=True):
    names = {'get_game', 'release_game', 'get_service', 'query_values', 'query_pair', 'release_service', 'free_vector'}
    if not include_pair:
        names.remove('query_pair')
    if native_calls is not None:
        if (type(native_calls) is not dict or set(native_calls) != names
                or any(not callable(value) for value in native_calls.values())):
            raise ValueError('XP2 Storm native-call seam must provide the exact reviewed operations')
        return native_calls
    if C.sizeof(C.c_void_p) != 8:
        raise RuntimeError('XP2 Storm adapter requires the native 64-bit ABI')
    def bind(target, result, *args):
        return C.WINFUNCTYPE(result, *args)(target)
    calls = {
        'get_game': lambda target, outer: bind(target, C.c_void_p, C.c_void_p)(outer),
        'release_game': lambda target, game: bind(target, None, C.c_void_p)(game),
        'get_service': lambda target, game, iid: bind(target, C.c_void_p, C.c_void_p, C.c_void_p)(game, iid),
        'query_values': lambda target, service, key, vector: bind(target, None, C.c_void_p, C.c_void_p, C.c_void_p)(service, key, vector),
        'query_pair': lambda target, service, key, out: bind(target, C.c_uint8, C.c_void_p, C.c_void_p, C.c_void_p)(service, key, out),
        'release_service': lambda target, service: bind(target, None, C.c_void_p)(service),
        'free_vector': lambda target, vector, begin, capacity_bytes: bind(target, None, C.c_void_p, C.c_void_p, C.c_size_t)(vector, begin, capacity_bytes),
    }
    return {name: calls[name] for name in names}


def _vector_values(vector, read):
    begin = int(vector.begin or 0)
    end = int(vector.end or 0)
    capacity = int(vector.capacity or 0)
    if (begin, end, capacity) == (0, 0, 0):
        return (), 0, 0
    if not begin or not end or not capacity or not (0x10000 <= begin < end <= capacity < (1 << 47)):
        raise ValueError('XP2 Storm list getter returned an invalid vector extent')
    if any(value % 4 for value in (begin, end, capacity)):
        raise ValueError('XP2 Storm list vector is not DWORD aligned')
    count = (end - begin) // 4
    capacity_bytes = capacity - begin
    if count > MAX_VECTOR_ITEMS or capacity_bytes > MAX_VECTOR_ITEMS * 4 or capacity_bytes < count * 4:
        raise ValueError('XP2 Storm list vector exceeds the bounded copy profile')
    raw = _read_exact(read, begin, count * 4, 'Core vector data')
    return tuple(struct.unpack('<' + 'I' * count, raw)) if count else (), begin, capacity_bytes


def _release_vector(calls, target, descriptor, begin, capacity_bytes, read):
    if not begin:
        return
    if (type(begin) is not int or not 0x10000 <= begin < (1 << 47)
            or type(capacity_bytes) is not int or not 0 < capacity_bytes <= MAX_VECTOR_ITEMS * 4):
        raise RuntimeError('XP2 Storm vector extent is unsafe to release')
    _read_exact(read, begin, 1, 'Core vector release buffer')
    calls['free_vector'](target, descriptor, begin, capacity_bytes)


def query_storm_objects(core, context, request_key, *, read=None, native_calls=None,
                        index_to_position=None,
                        core_sha256=XP2_CORE_SHA256):
    """Query the official XP2 Storm service through its Game and wrapper APIs.

    `context` is a borrowed Core outer interface. `request_key` is the exact
    8-byte `<HHI` key consumed by the selected Core methods. The returned
    values are copied DWORDs. Each value is passed to the official XP2
    map-position query before +0x110, preserving the EXE caller order. False
    +0x110 means its output pair is undefined and is represented by
    `position=None`.
    """
    return _query_objects(core, context, request_key, read=read,
        native_calls=native_calls, index_to_position=index_to_position,
        core_sha256=core_sha256, family='storm')


def _query_objects(core, context, request_key, *, read, native_calls,
                   index_to_position, core_sha256, family):
    """Shared lifetime, with only two independently source-selected getters."""
    if family not in ('storm', 'descriptor53'):
        raise ValueError('Unqualified XP2 object-list query family')
    include_pair = family == 'storm'
    if core_sha256 != XP2_CORE_SHA256:
        raise ValueError('Storm query has an XP2-only Core profile')
    if type(request_key) is not bytes or len(request_key) != 8:
        raise ValueError('Storm request key must be the exact eight-byte native key')
    base = getattr(core, '_handle', None)
    if type(base) is not int or base <= 0:
        raise ValueError('Storm query requires a live XP2 Core handle')
    if type(context) is not int or context <= 0:
        raise ValueError('Storm query requires the borrowed outer Core interface')
    if read is None or not callable(read):
        raise ValueError('Storm query requires the active checked native reader')
    _verify_live_once(core, base, read)
    list_slot, list_rva = SERVICE_LIST_SLOT, SERVICE_LIST_RVA
    if not include_pair:
        from .xp2_descriptor53_query import verify_live, SERVICE_LIST_SLOT as selected_slot, SERVICE_LIST_RVA as selected_rva
        # Do not inherit the storm-only verification cache for this new slot.
        verify_live(base, read)
        list_slot, list_rva = selected_slot, selected_rva
    abi = query_abi(core_sha256, resource_root())

    def qword(address, label):
        return _qword(read, address, label)

    outer_table = abi.table('outer')
    if qword(context, 'outer interface vtable') != base + outer_table:
        raise ValueError('Storm query outer interface belongs to another Core profile')
    outer_game_target = base + abi.rva('outer_game')
    if qword(base + outer_table + abi.slot('outer_game'), 'outer +0x90 slot') != outer_game_target:
        raise ValueError('Storm query outer +0x90 target changed')
    game_table = abi.table('game')
    game_service_target = base + GAME_SERVICE_FACTORY_RVA
    if qword(base + game_table + GAME_SERVICE_SLOT, 'Game +0x28 slot') != game_service_target:
        raise ValueError('Storm query Game +0x28 target changed')
    if _read_exact(read, base + SERVICE_IID_RVA, len(SERVICE_IID), 'service IID') != SERVICE_IID:
        raise ValueError('Storm service IID differs from the pinned XP2 interface')
    wrapper_table = base + SERVICE_WRAPPER_VTABLE_RVA
    pair_target = base + SERVICE_PAIR_RVA
    list_target = base + list_rva
    wrapper_release_target = base + SERVICE_WRAPPER_RELEASE_RVA

    calls = _native_calls(native_calls, include_pair=include_pair)
    game = service = 0
    vector = _Vector()
    vector_address = C.addressof(vector)
    key_buffer = C.create_string_buffer(request_key, len(request_key))
    key_address = C.addressof(key_buffer)
    pair = (C.c_uint32 * 2)(0, 0)
    vector_begin = 0
    vector_capacity_bytes = 0
    values: tuple[int, ...] = ()
    positions: tuple[bytes, ...] = ()
    position: tuple[int, int] | None = None
    try:
        acquired_game = calls['get_game'](outer_game_target, context)
        if type(acquired_game) is not int or acquired_game <= 0:
            raise ValueError('Storm query did not acquire the live XP2 Game interface')
        if qword(acquired_game, 'Game vtable') != base + game_table:
            raise ValueError('Storm query acquired a Game from another Core profile')
        game = acquired_game
        if qword(base + game_table + 8, 'Game release slot') != base + abi.rva('release_game'):
            raise ValueError('Storm query Game release target changed')
        if qword(base + game_table + GAME_SERVICE_SLOT, 'Game +0x28 target') != game_service_target:
            raise ValueError('Storm query Game service factory changed')

        iid_buffer = C.create_string_buffer(SERVICE_IID, len(SERVICE_IID))
        acquired_service = calls['get_service'](game_service_target, game, C.addressof(iid_buffer))
        if type(acquired_service) is not int or acquired_service <= 0:
            raise ValueError('Storm query returned an unexpected XP2 service wrapper')
        if qword(acquired_service, 'service wrapper vtable') != wrapper_table:
            raise ValueError('Storm query returned a wrapper from another Core profile')
        service = acquired_service
        if qword(wrapper_table + list_slot, 'selected list getter slot') != list_target:
            raise ValueError('XP2 service selected list getter target changed')
        if include_pair and qword(wrapper_table + SERVICE_PAIR_SLOT, 'wrapper +0x110 slot') != pair_target:
            raise ValueError('Storm service wrapper +0x110 target changed')
        if qword(wrapper_table + SERVICE_WRAPPER_RELEASE_SLOT, 'wrapper release slot') != wrapper_release_target:
            raise ValueError('Storm service wrapper release target changed')

        calls['query_values'](list_target, service, key_address, vector_address)
        vector_begin = int(vector.begin or 0)
        capacity = int(vector.capacity or 0)
        if vector_begin and capacity >= vector_begin:
            vector_capacity_bytes = capacity - vector_begin
        values, vector_begin, vector_capacity_bytes = _vector_values(vector, read)
        if index_to_position is None:
            from .xp2_weather_position import query_native_index_to_position
            index_query = query_native_index_to_position
        elif not callable(index_to_position):
            raise ValueError('Storm index-to-position query must be callable')
        else:
            index_query = index_to_position
        copied_positions: list[bytes] = []
        for value in values:
            raw_position = index_query(core, context, value, read=read)
            if type(raw_position) is not bytes or len(raw_position) != 8:
                raise ValueError('XP2 native index-to-position query must return exactly two DWORDs')
            copied_positions.append(bytes(raw_position))
        positions = tuple(copied_positions)
        if include_pair:
            pair_written = calls['query_pair'](pair_target, service, key_address, C.addressof(pair))
            if type(pair_written) is not int or pair_written not in (0, 1):
                raise ValueError('Storm +0x110 must return its exact BOOL byte')
            if pair_written:
                position = (int(pair[0]), int(pair[1]))
        if getattr(core, '_handle', None) != base:
            raise RuntimeError('XP2 Core identity changed during Storm query')
        if (qword(context, 'outer interface after query') != base + outer_table
                or qword(base + outer_table + abi.slot('outer_game'), 'outer +0x90 after query') != outer_game_target
                or qword(game, 'Game interface after query') != base + game_table
                or qword(base + game_table + GAME_SERVICE_SLOT, 'Game +0x28 after query') != game_service_target
                or qword(service, 'service wrapper after query') != wrapper_table
                or qword(wrapper_table + list_slot, 'selected list getter after query') != list_target
                or (include_pair and qword(wrapper_table + SERVICE_PAIR_SLOT, 'wrapper +0x110 after query') != pair_target)):
            raise RuntimeError('XP2 Storm facade ownership changed during query')
        return StormQueryResult(values, positions, position)
    finally:
        if not vector_begin and vector.begin:
            vector_begin = int(vector.begin)
            capacity = int(vector.capacity or 0)
            if capacity >= vector_begin:
                vector_capacity_bytes = capacity - vector_begin
        try:
            _release_vector(calls, base + VECTOR_FREE_RVA, vector_address, vector_begin, vector_capacity_bytes, read)
        finally:
            try:
                if service:
                    calls['release_service'](wrapper_release_target, service)
            finally:
                if game:
                    calls['release_game'](base + abi.rva('release_game'), game)
