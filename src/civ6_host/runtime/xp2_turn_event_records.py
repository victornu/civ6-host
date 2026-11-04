"""Exact EXE random/climate records; no Core calls or queue ownership.

The caller supplies the one native position-query result when required. The
undefined random-event DWORD is admitted only under the explicit empty-receiver
storage policy; it is never described as a native value or public observation.
"""
from dataclasses import dataclass
from functools import lru_cache
import hashlib
import struct
from types import MappingProxyType

from .configuration_profiles import _source

RECEIVER_SOURCE = (
    'work/host-extensions/xp2-turn-event-family/receiver-source-profile-v2.json',
    '2c5955a7d613afe14555513f5fecd90ee52b55df146106abfcff838cc781aee1')
TYPED_EMITTER_SOURCE = (
    'work/host-extensions/xp2-turn-event-family/typed-emitter-source-v1.json',
    '294306affa4ede3af581b34c80cb2354da5f26586d383bc2d50a0660a167a680')
CLIMATE_KIND, STARTED_KIND, OCCURRED_KIND = 0x2bea7bcb, 0xd109a8fc, 0xe869c8ff
STORM_KIND, VALUE_KEY = 0x13b135e4, 0xd6fcf3e4
DROUGHT_KIND = 0x07f2abd3
SELECTOR_KEY, IDENTIFIER_KEY = 0xa1e5a149, 0x0057c6ed
POSITION_KEY, EVENT_KEY, CLIMATE_DATA_KEY = 0x8c468e3c, 0x5a38d38c, 0x0b7da8da
UNDEFINED_PAYLOAD_POLICY = 'zero-unread-empty-random-event-word-not-native-value'
CALLBACKS = MappingProxyType({CLIMATE_KIND: 0x142d30, STARTED_KIND: 0x14d550,
                             OCCURRED_KIND: 0x14d290})
RECORD_TYPES = MappingProxyType({CLIMATE_KIND: (0x145,), STARTED_KIND: (0x135,),
                                OCCURRED_KIND: (0x136, 0x137)})
WRITERS = MappingProxyType({0x145: 0x1269e0, 0x135: 0x124ab0,
                           0x136: 0x124cc0, 0x137: 0x124ed0})
EMPTY_RECEIVER_STATE = MappingProxyType(dict(observer_registered=False,
    state_pointer_nonnull=True, pre_hook=None, post_hook=None,
    subscriber_count=0, state_flags=0))


TERRAIN_KIND, TERRAIN_RECORD = 0xfc5eac6e, 0x97
TERRAIN_SOURCE = (
    'evidence/host-xp2-turn36-terrain-state-refusal.json',
    '4d9ea349412fbeeba357c9c60c4e1e3d1546ae9f3bddd646dab702124f296c74')
TERRAIN_NORMALIZER = (
    'evidence/native-scalar-event-callback-candidates.json',
    '783130b57f8f1dd03159ec3f0d96a0bcedd70d3e57f87d5208f86c22e22fd433')
TERRAIN_SHORT_SOURCE = (
    'evidence/host-xp2-turn37-terrain-short-refusal.json',
    'f04068c3b52d2922073679b129962a2594c0805c25ccbc924cc9588cfc821d08')
TERRAIN_OPTIONAL_KEY = 0x892b274a
TERRAIN_OCCURRED_SOURCE = (
    'evidence/host-xp2-turn36-terrain-dispatch-native.json',
    '553874b113d40c1f04b5bbc5f90eda0af3fcf6e70920b01028ae26b9c9034aa5')
TERRAIN_OCCURRED_VALUE_KEY = 0x892b274a
TERRAIN_VALUES = ((0x15808e44, 1), (0xf36f4928, 2), (0x892b274a, 2))


@lru_cache(maxsize=1)
def terrain_source():
    from .configuration_profiles import XP2_CORE_SHA256
    from .native.native_host_event_registry import EXE_SHA256, EXE_EVENT_CALLBACKS

    proof = _source(TERRAIN_SOURCE)
    normalizer = _source(TERRAIN_NORMALIZER)['common_host_normalizer']
    if (proof['schema'] != 'civ6-host.xp2-turn36-terrain-state-refusal.v1'
            or proof['images'] != {'core_sha256': XP2_CORE_SHA256, 'exe_sha256': EXE_SHA256}
            or proof['native_fields']['dispatch_kind'] != hex(TERRAIN_KIND)
            or EXE_EVENT_CALLBACKS.get(TERRAIN_KIND) != 0x153ce0
            or dict(proof['record']) != dict(type=TERRAIN_RECORD, size=112,
                event_name='GameCoreEvent::TerrainStateChanged', row_va='0x1412c8500',
                setup_va='0x1400cf3a0', handler_va='0x1400d9790', producer_token_hook=False)):
        raise ValueError('XP2 terrain notification source changed')
    required = {'cmp ecx, 0x8c468e3c', 'mov qword ptr [rbp + 0xf], rcx'}
    instructions = {row['text'] for fragment in normalizer['body']['fragments']
                    for row in fragment['instructions']}
    if not required <= instructions:
        raise ValueError('XP2 terrain notification normalization changed')
    return proof


def terrain_receiver_row():
    proof = terrain_source()
    raw = b''.join(bytes.fromhex(row['bytes'])
                   for fragment in proof['source']['handler']['fragments']
                   for row in fragment['instructions'])
    return dict(record_sizes={112}, event_name=proof['record']['event_name'],
                handler_va=proof['record']['handler_va'],
                handler_body_sha256=hashlib.sha256(raw).hexdigest(),
                source_sha256=TERRAIN_SOURCE[1])


@lru_cache(maxsize=1)
def terrain_occurred_source():
    from .configuration_profiles import XP2_CORE_SHA256

    proof = _source(TERRAIN_OCCURRED_SOURCE)
    witness = proof['refusal']
    expected = {SELECTOR_KEY, EVENT_KEY, POSITION_KEY, TERRAIN_OCCURRED_VALUE_KEY}
    if (proof['schema'] != 'civ6-host.xp2-random-occurred-terrain-emitter.v1'
            or proof['core_sha256'] != XP2_CORE_SHA256
            or witness['dispatch_kind'] != hex(OCCURRED_KIND)
            or {int(key, 16) for key in witness['fields']} != expected
            or not {('0x72d6f8', 'mov edx, 0x892b274a'),
                    ('0x72d709', 'call 0x1805fd780'),
                    ('0x72d747', 'call 0x1805fc280')} <= {
                        tuple(row) for row in proof['caller_instructions']}):
        raise ValueError('XP2 terrain random-event producer changed')
    return proof


@lru_cache(maxsize=1)
def terrain_short_source():
    from .configuration_profiles import XP2_CORE_SHA256
    from .native.native_host_event_registry import EXE_SHA256

    proof = _source(TERRAIN_SHORT_SOURCE)
    witness = proof['witness']
    expected = {SELECTOR_KEY, POSITION_KEY, 0x15808e44, 0xf36f4928}
    if (proof['schema'] != 'civ6-host.xp2-terrain-state-short-emitter.v1'
            or proof['core_sha256'] != XP2_CORE_SHA256 or proof['exe_sha256'] != EXE_SHA256
            or witness['dispatch_kind'] != hex(TERRAIN_KIND)
            or {int(key, 16) for key in witness['fields']} != expected
            or not {('0x731e49', 'mov edx, 0xf36f4928'),
                    ('0x731e62', 'mov edx, 0x15808e44'),
                    ('0x731e77', 'mov edx, 0x8c468e3c'),
                    ('0x731e95', 'call 0x1805fc280')} <= {
                        tuple(row) for row in proof['producer']['instructions']}
            or not {('0x153d94', 'mov edx, 0x892b274a'),
                    ('0x153da0', 'call qword ptr [rax + 0x68]'),
                    ('0x153dbf', 'mov ebx, dword ptr [rax + 8]')} <= {
                        tuple(row) for row in proof['callback']['instructions']}):
        raise ValueError('XP2 short terrain notification source changed')
    return proof


def terrain_core_fragments():
    for rva, window in terrain_source()['source']['core_windows'].items():
        raw = bytes.fromhex(window['raw_hex'])
        if len(raw) != window['size'] or hashlib.sha256(raw).hexdigest() != window['sha256']:
            raise ValueError('XP2 terrain notification Core window changed')
        yield int(rva, 16), raw
    occurred = terrain_occurred_source()
    yield occurred['caller_rva'], bytes.fromhex(occurred['caller_raw_hex'])
    short = terrain_short_source()['producer']
    yield short['rva'], bytes.fromhex(short['raw_hex'])


def encode_terrain(raw_fields, sequence, read):
    terrain_source()
    expected = {SELECTOR_KEY, POSITION_KEY, *(key for key, _ in TERRAIN_VALUES)}
    if (type(raw_fields) is not dict or set(raw_fields) not in (expected, expected - {TERRAIN_OPTIONAL_KEY})
            or any(type(raw) is not bytes or len(raw) != 24 for raw in raw_fields.values())):
        raise ValueError('Unqualified terrain notification emitter fields')
    if TERRAIN_OPTIONAL_KEY not in raw_fields:
        terrain_short_source()
    selector = _scalar(raw_fields[SELECTOR_KEY], 3, 'terrain selector')
    position = _copy_position(raw_fields[POSITION_KEY], 13, read)
    # The callback starts EBX at zero and only replaces it for a numeric lookup.
    values = [_scalar(raw_fields[key], tag, 'terrain value') if key in raw_fields else 0
              for key, tag in TERRAIN_VALUES]
    row = make_header(112, TERRAIN_RECORD, sequence, 0)
    struct.pack_into('<IiiIIII', row, 80, sequence, *position, selector, *values)
    return bytes(row)


def _rows(body):
    return [row for fragment in body['capture']['fragments']
            for row in fragment['instructions']]


def _rva_rows(body):
    capture = body.get('capture', body)
    return {int(row['rva'], 16) if 'rva' in row else int(row['va'], 16) - 0x180000000: row
            for fragment in capture.get('fragments', (capture,)) for row in fragment['instructions']}


def _constructor_tag(rva, producer, supplement, primitives):
    body = producer['functions'].get('xp2_' + format(rva, 'x')) or supplement['functions'].get(hex(rva))
    if body is None:
        raise ValueError('Unknown typed emitter constructor')
    text = {address: row['text'] for address, row in _rva_rows(body).items()}
    writes = {0x5fd780: (0x5fd78b, 'mov dword ptr [rcx + 8], '),
              0x5fd7a0: (0x5fd7ab, 'mov dword ptr [rcx + 8], '),
              0x5fd7e0: (0x5fd803, 'mov dword ptr [rbx + 8], ')}
    if rva in writes:
        address, prefix = writes[rva]
        if not text.get(address, '').startswith(prefix):
            raise ValueError('Typed emitter constructor tag write changed')
        return int(text[address][len(prefix):], 0)
    if rva != 0x5fd680:
        raise ValueError('Unqualified typed emitter constructor')
    # This constructor forwards tag13 in R8W to the existing parameter helper.
    required = {0x5fd694: 'xor eax, eax', 0x5fd6a9: 'lea ebp, [rax + 0xd]',
                0x5fd6b9: 'lea rdx, [rsi + 8]', 0x5fd6d3: 'movzx r8d, bp',
                0x5fd6d7: 'call 0x18099dc00'}
    helper = {address: row['text'] for address, row in
              _rva_rows(primitives['functions']['0x99dc00']).items()}
    if (any(text.get(address) != instruction for address, instruction in required.items())
            or helper.get(0x99dc21) != 'movzx r14d, r8w'
            or helper.get(0x99dca5) != 'mov word ptr [rsi], r14w'
            or 'mov rsi, rdx' not in helper.values()):
        raise ValueError('Typed position constructor argument/tag assignment changed')
    return 13


def _verify_typed_routes(p, producer, primitives):
    """Join each actual caller key/argument to its constructor's tag write."""
    rows = _rva_rows(producer['functions']['xp2_1c2aa0'])
    addresses = sorted(rows)
    expected_calls = {int(item['call_rva'], 16) for item in producer['producer']['call_sites']}
    if {int(route['call_rva'], 16) for route in p['routes']} != expected_calls or len(p['routes']) != 9:
        raise ValueError('Typed emitter inventory does not cover all nine calls')
    setter = {address: row['text'] for address, row in
              _rva_rows(primitives['functions']['0x9a0000']).items()}
    if (setter.get(0x9a0079) != 'mov dword ptr [rbx], 3'
            or setter.get(0x9a008f) != 'mov dword ptr [rsp + 0x30], 3'):
        raise ValueError('Automatic selector setter tag changed')
    for route in p['routes']:
        emit, builder, kind = (int(route[k], 16) for k in ('call_rva', 'builder_rva', 'kind'))
        store = rows[int(route['kind_store_rva'], 16)]['text']
        address = store[store.index('['):store.index(']') + 1]
        if (not store.endswith(', ' + hex(kind))
                or rows[int(route['kind_load_rva'], 16)]['text'] != 'mov rcx, qword ptr ' + address
                or rows[emit]['text'] != 'call ' + hex(0x180000000 + builder)):
            raise ValueError('Typed emitter kind/call ownership changed')
        body = _rows(producer['functions']['xp2_' + format(builder, 'x')])
        body_text = [row['text'] for row in body]
        if (route['selector_key'] != hex(SELECTOR_KEY) or route['selector_tag'] != 3
                or body_text.index('mov edx, 0xa1e5a149') > body_text.index('call 0x1809a0000')
                or body_text.index('call 0x1809a0000') > body_text.index('call 0x18099fd70')):
            raise ValueError('Typed emitter automatic selector order changed')
        calls = {}
        for field in route['fields']:
            key, load, call, ctor = (int(field[k], 16) for k in
                                    ('key', 'key_load_rva', 'constructor_call_rva', 'constructor_rva'))
            if (rows[load]['text'] != 'mov edx, ' + hex(key)
                    or rows[call]['text'] != 'call ' + hex(0x180000000 + ctor)
                    or field['tag'] != _constructor_tag(ctor, producer, p, primitives)):
                raise ValueError('Typed emitter field key/constructor/tag mapping changed')
            between = [rows[a]['text'] for a in addresses if load < a < call]
            if any(t.startswith(('call ', 'mov edx, ', 'lea edx, ', 'xor edx, ', 'mov rdx, '))
                   or t == 'cdq' for t in between):
                raise ValueError('Typed emitter key register was overwritten before construction')
            calls[call] = key
        # Track only constructor-return pointers through the reviewed caller's
        # register moves. This checks the objects actually handed to the builder.
        pointers = {}
        aliases = {'eax': 'rax', 'ecx': 'rcx', 'edx': 'rdx', 'ebx': 'rbx',
                   'edi': 'rdi', 'esi': 'rsi', 'r8d': 'r8', 'r9d': 'r9'}
        start = min(int(f['key_load_rva'], 16) for f in route['fields'])
        for at in (a for a in addresses if start <= a < emit):
            text = rows[at]['text']
            if text.startswith('call '):
                for register in ('rax', 'rcx', 'rdx', 'r8', 'r9'):
                    pointers.pop(register, None)
                if at in calls:
                    pointers['rax'] = calls[at]
            elif ', ' in text and text.split(' ', 1)[0] in ('mov', 'movzx', 'movsx', 'lea', 'xor', 'add', 'sub', 'and', 'or'):
                operation, operands = text.split(' ', 1)
                destination, origin = operands.split(', ', 1)
                destination = aliases.get(destination, destination)
                if operation == 'mov' and origin in pointers:
                    pointers[destination] = pointers[origin]
                else:
                    pointers.pop(destination, None)
        if any(pointers.get(field['emitter_argument']) != int(field['key'], 16)
               for field in route['fields']):
            raise ValueError('Typed emitter constructor object is not the passed argument')
    return p


@lru_cache(maxsize=1)
def typed_emitter_source():
    from .xp2_turn_event_profile import source, fragments, SOURCE
    from .configuration_profiles import XP2_CORE_SHA256
    p = _source(TYPED_EMITTER_SOURCE)
    if (p['schema'] != 'civ6-host.xp2-turn-event-typed-emitters.static.v1'
            or p['core_sha256'] != XP2_CORE_SHA256 or p['native_execution'] is not False
            or p['references']['producer'] != dict(path=SOURCE[0], sha256=SOURCE[1])):
        raise ValueError('Typed emitter source identity changed')
    for body in p['functions'].values():
        raw = b''.join(raw for _, raw in fragments(body))
        if hashlib.sha256(raw).hexdigest() != body['sha256']:
            raise ValueError('Typed emitter constructor bytes changed')
    reference = p['references']['parameter_primitives']
    primitives = _source((reference['path'], reference['sha256']))
    return _verify_typed_routes(p, source(), primitives)


def field_shapes(kind):
    """Typed source inventory; this does not admit the kind's EXE callback."""
    if type(kind) is not int:
        raise ValueError('Typed emitter kind must be an exact integer')
    result = []
    for route in typed_emitter_source()['routes']:
        if int(route['kind'], 16) == kind:
            shape = {SELECTOR_KEY: 3, **{int(f['key'], 16): f['tag'] for f in route['fields']}}
            if shape not in result:
                result.append(shape)
    if not result:
        raise ValueError('No source-qualified typed emitter shape')
    return tuple(MappingProxyType(shape) for shape in result)


@lru_cache(maxsize=1)
def receiver_source():
    from .xp2_turn_event_profile import source, fragments, EXE_SHA256, SOURCE
    source()
    p = _source(RECEIVER_SOURCE)
    if (p['schema'] != 'civ6-host.xp2-turn-event-receivers.static.v2'
            or p['exe_sha256'] != EXE_SHA256 or p['native_execution'] is not False
            or p['process_memory_read'] is not False
            or p['references']['callbacks'] != dict(path=SOURCE[0], sha256=SOURCE[1])
            or dict(p['empty_contract']) != dict(EMPTY_RECEIVER_STATE)
            or set(p['rows']) != {'0x135', '0x136', '0x137', '0x138', '0x13b', '0x145'}):
        raise ValueError('XP2 turn-event receiver source identity changed')
    parent = _source(tuple(p['references']['initializer'][k] for k in ('path', 'sha256')))
    initializer = {row['va']: row['text']
                   for f in parent['captures']['initializer']['fragments']
                   for row in f['instructions']}
    for body in p['functions'].values():
        raw = b''.join(raw for _, raw in fragments(body))
        if (len(raw) != body['bytes'] or hashlib.sha256(raw).hexdigest() != body['sha256']
                or body['all_conditional_successors_captured'] is not True):
            raise ValueError('XP2 turn-event receiver body changed')
    if p['functions']['0xdc0d0']['sha256'] != '326ad0582020365181be9ed3b3e0f595e1bf834ef24f5afdf167d9ae56292bca':
        raise ValueError('Shared empty receiver dispatcher changed')
    for key, row in p['rows'].items():
        if (int(row['row_va'], 16) != 0x1412c68b0 + int(key, 16) * 48
                or initializer[row['initializer_call_va']] !=
                   'call ' + hex(0x140000000 + int(row['constructor_rva'], 16))):
            raise ValueError('XP2 turn-event receiver registration changed')
        handler = p['functions'][row['handler_rva']]
        calls = [i['text'] for i in _rows(handler) if i['text'].startswith('call ')]
        if (handler['sha256'] != row['handler_sha256'] or calls !=
                ['call 0x14098a780', 'call 0x1400dc0d0', 'call 0x14098a7b0']):
            raise ValueError('XP2 turn-event receiver has unqualified effects')
        constructor = _rows(p['functions'][row['constructor_rva']])
        targets = {target for instruction in constructor for target in instruction.get('rip_targets', ())}
        texts = {instruction['text'] for instruction in constructor}
        if (not {row['row_va'], hex(0x140000000 + int(row['handler_rva'], 16)),
                 '0x1412c6804', '0x1400ea0e0'} <= targets
                or not {'xor ebx, ebx', 'lea ecx, [rbx + 0x38]',
                    'mov qword ptr [rcx], rbx', 'mov qword ptr [rcx + 8], rbx',
                    'mov qword ptr [rcx + 0x10], rbx', 'mov qword ptr [rcx + 0x18], rdx',
                    'mov qword ptr [rcx + 0x20], rax', 'mov qword ptr [rax + 8], rbx',
                    'mov dword ptr [rax + 0x20], ebx', 'and byte ptr [rax + 0x30], 0xfc'} <= texts):
            raise ValueError('XP2 turn-event empty receiver constructor changed')
    # The retained normalizer copies A1E5's DWORD into normalized+4. The two
    # random callbacks consume that word, not the ignored 5A38 field.
    normalizer = {i['va']: i['text'] for f in parent['captures']['normalizer']['fragments']
                  for i in f['instructions']}
    if (normalizer.get('0x1401ca681') != 'mov dword ptr [rbp - 0x35], eax'
            or normalizer.get('0x1401ca649') != 'cmp ecx, 0xa1e5a149'):
        raise ValueError('Random-event selector normalization changed')
    return p


def source_dependencies():
    """Private source pins only; never call the parent's dependency aggregator."""
    from .a0_family_source import _path
    p = receiver_source()
    refs = [dict(path=RECEIVER_SOURCE[0], sha256=RECEIVER_SOURCE[1]),
            *p['references'].values()]
    typed = typed_emitter_source()
    refs.extend((dict(path=TYPED_EMITTER_SOURCE[0], sha256=TYPED_EMITTER_SOURCE[1]),
                 *typed['references'].values()))
    pins = {str(_path(r['path']).resolve()): r['sha256'] for r in refs}
    from .native.native_scalar_event_encoder import _EVIDENCE, _CANDIDATE_EVIDENCE_SHA256
    from .resource_resolution import resolve_path
    pins[str(resolve_path(_EVIDENCE).resolve())] = _CANDIDATE_EVIDENCE_SHA256
    return pins


def receiver_rows():
    return {int(key, 16): dict(record_sizes=set(row['record_sizes']),
            event_name=row['event_name'],
            handler_va=hex(0x140000000 + int(row['handler_rva'], 16)),
            handler_body_sha256=row['handler_sha256'], source_sha256=RECEIVER_SOURCE[1])
            for key, row in receiver_source()['rows'].items()}


def receiver_row(record_type):
    if type(record_type) is not int:
        raise ValueError('Receiver type must be an exact integer')
    return receiver_rows().get(record_type)


def registration_metadata(kind):
    from .xp2_turn_event_profile import source, SOURCE
    source()
    typed_emitter_source()
    if type(kind) is not int or kind not in CALLBACKS:
        raise ValueError('Unqualified random/climate codec kind')
    random = kind != CLIMATE_KIND
    return dict(kind=kind, callback_rva=CALLBACKS[kind], record_types=RECORD_TYPES[kind],
        writer_rvas=tuple(WRITERS[k] for k in RECORD_TYPES[kind]),
        record_sizes=tuple(112 if random else 96 for _ in RECORD_TYPES[kind]),
        metadata_flag=6 if random else 0,
        undefined_record_ranges=((92, 96),) if random else (),
        allocation_zero_ranges=((76, 80), (108, 112)) if random else ((76, 80), (88, 96)),
        native_position_query_call_rva={STARTED_KIND: 0x14d70a,
            OCCURRED_KIND: 0x14d43a}.get(kind),
        source_sha256=SOURCE[1], receiver_source_sha256=RECEIVER_SOURCE[1],
        typed_emitter_source_sha256=TYPED_EMITTER_SOURCE[1])


@dataclass(frozen=True)
class Fields:
    kind: int
    selector: int
    identifier: int | None
    position: tuple[int, int] | None
    # Immutable original variants preserve fields ignored by the EXE callback.
    raw_fields: tuple[tuple[int, bytes], ...]
    occurred_value: int = 0


@dataclass(frozen=True)
class StormFields:
    kind: int
    selector: int
    value: int
    identifier: int
    position: tuple[int, int]
    raw_fields: tuple[tuple[int, bytes], ...]


def _uint32(value, label):
    if type(value) is not int or not 0 <= value <= 0xffffffff:
        raise ValueError(label + ' must be an exact DWORD')
    return value


def _scalar(raw, tag, label):
    from .native.native_scalar_event_encoder import _read_u32_variant
    return _read_u32_variant(raw, tag, label)


def _copy_position(raw, tag, read):
    pointer, size, flags = struct.unpack_from('<QII', raw, 8)
    if (struct.unpack_from('<H', raw)[0] != tag or size != 8
            or flags != 0x21000001 or not pointer or not callable(read)):
        raise ValueError('Random-event typed position envelope changed')
    value = read(pointer, 8)
    if type(value) is not bytes or len(value) != 8:
        raise ValueError('Incomplete random-event position copy')
    return struct.unpack('<ii', value)


def decode_fields(kind, raw_fields, read):
    """Copy only the exact retained XP2 emitter shapes, without Core queries."""
    storm = type(kind) is int and kind in (STORM_KIND, DROUGHT_KIND)
    if storm:
        from .xp2_turn_event_profile import source
        source()
    else:
        registration_metadata(kind)
    if (type(raw_fields) is not dict or any(type(k) is not int for k in raw_fields)
            or any(type(v) is not bytes or len(v) != 24 for v in raw_fields.values())):
        raise ValueError('Random/climate fields require complete immutable variants')
    climate = kind == CLIMATE_KIND
    shapes = [shape for shape in field_shapes(kind) if set(raw_fields) == set(shape)]
    if kind == OCCURRED_KIND and set(raw_fields) == {
            SELECTOR_KEY, EVENT_KEY, POSITION_KEY, TERRAIN_OCCURRED_VALUE_KEY}:
        terrain_occurred_source()
        shapes = [{SELECTOR_KEY: 3, EVENT_KEY: 2, POSITION_KEY: 13,
                   TERRAIN_OCCURRED_VALUE_KEY: 2}]
    if len(shapes) != 1:
        raise ValueError('Unqualified random/climate emitter field shape')
    tags = shapes[0]
    selector = _scalar(raw_fields[SELECTOR_KEY], tags[SELECTOR_KEY], 'selector')
    identifier, position = None, None
    if climate:
        if struct.unpack_from('<H', raw_fields[CLIMATE_DATA_KEY])[0] != tags[CLIMATE_DATA_KEY]:
            raise ValueError('Climate ignored text tag differs from its actual constructor')
    else:
        _scalar(raw_fields[VALUE_KEY if storm else EVENT_KEY], tags[VALUE_KEY if storm else EVENT_KEY],
                'storm value' if storm else 'ignored event value')
        identifier = (_scalar(raw_fields[IDENTIFIER_KEY], tags[IDENTIFIER_KEY], 'identifier')
                      if IDENTIFIER_KEY in raw_fields else 0xffffffff)
        position = _copy_position(raw_fields[POSITION_KEY], tags[POSITION_KEY], read)
    if storm:
        return StormFields(kind, selector, _scalar(raw_fields[VALUE_KEY], tags[VALUE_KEY], 'storm value'),
                           identifier, position, tuple(sorted(raw_fields.items())))
    occurred_value = (_scalar(raw_fields[TERRAIN_OCCURRED_VALUE_KEY], 2, 'terrain occurred value')
                      if TERRAIN_OCCURRED_VALUE_KEY in tags else 0)
    return Fields(kind, selector, identifier, position, tuple(sorted(raw_fields.items())), occurred_value)


def _fields(fields):
    if type(fields) is not Fields or type(fields.kind) is not int or fields.kind not in CALLBACKS:
        raise ValueError('Expected decoded random/climate fields')
    _uint32(fields.selector, 'selector')
    _uint32(fields.occurred_value, 'random event value')
    if fields.kind != OCCURRED_KIND and fields.occurred_value:
        raise ValueError('Random event value belongs to another callback')
    if fields.kind == CLIMATE_KIND:
        if fields.identifier is not None or fields.position is not None:
            raise ValueError('Climate fields contain an unrelated native query')
    elif (type(fields.position) is not tuple or len(fields.position) != 2
          or any(type(v) is not int or not -0x80000000 <= v <= 0x7fffffff
                 for v in fields.position)):
        raise ValueError('Random event requires a copied signed coordinate pair')
    else:
        _uint32(fields.identifier, 'identifier')
    return fields


def requires_position_query(fields):
    _fields(fields)
    return fields.position is not None and all(v > -9999 for v in fields.position)


def make_header(size, record_type, sequence, flag, index=0xffffffff):
    """Allocate a zeroed record and its exact common EXE metadata header."""
    expected = {TERRAIN_RECORD: (112, 0), 0x135: (112, 6), 0x136: (112, 6), 0x137: (112, 6),
                0x138: (128, 4), 0x13b: (112, 4), 0x145: (96, 0)}
    if (any(type(v) is not int for v in (size, record_type, flag))
            or expected.get(record_type) != (size, flag)):
        raise ValueError('Unqualified random/climate record header')
    _uint32(sequence, 'sequence')
    _uint32(index, 'native metadata index')
    if sequence == 0:
        raise ValueError('Record sequence must be nonzero')
    record = bytearray(size)
    struct.pack_into('<IIIIII', record, 0, size, record_type, sequence, 0, index, 0xffffffff)
    for at in (24, 32, 40, 48, 56):
        struct.pack_into('<HHI', record, at, 0xffff, 0, 0xffffffff)
    struct.pack_into('<QI', record, 64, 0, flag)
    return record


def encode_records(kind, first_sequence, fields, *, position_index=None,
                   empty_receiver_state, normalizer_transform_present,
                   per_thread_hook_present, writer_metadata_callback_present,
                   undefined_payload_policy=None):
    """Return ordered immutable FIFO bytes. This does not authenticate a query.

    The native query owner must supply the exact +90 EAX value when requested;
    mutated query coordinates are not used by these EXE callbacks. The caller
    remains responsible for owner/engine/source guards and atomic queue admission.
    """
    spec = registration_metadata(kind)
    receiver_source()
    _fields(fields)
    if fields.kind != kind:
        raise ValueError('Random/climate fields belong to another callback')
    if (normalizer_transform_present is not False or per_thread_hook_present is not False
            or writer_metadata_callback_present is not False):
        raise ValueError('Unqualified random/climate optional service')
    if (type(empty_receiver_state) is not dict or set(empty_receiver_state) != set(EMPTY_RECEIVER_STATE)
            or any(type(empty_receiver_state[k]) is not type(v) or empty_receiver_state[k] != v
                   for k, v in EMPTY_RECEIVER_STATE.items())):
        raise ValueError('Random/climate records require the exact empty receiver')
    _uint32(first_sequence, 'sequence')
    if not 1 <= first_sequence <= 0x100000000 - len(spec['record_types']):
        raise ValueError('Random/climate sequence range is exhausted')
    query = requires_position_query(fields)
    if query:
        _uint32(position_index, 'native position query result')
    elif position_index is not None:
        raise ValueError('Native position result supplied for an uncalled branch')
    if kind == CLIMATE_KIND:
        if undefined_payload_policy is not None:
            raise ValueError('Climate payload has no undefined word policy')
        from .native.native_scalar_event_encoder import _encode_profile_record
        row = dict(callback_shape_group='one_value_two_key', payload_value_count=1,
                   writer_record_type='0x145')
        return (_encode_profile_record(row, first_sequence, (fields.selector,), queue_metadata=0),)
    if undefined_payload_policy != UNDEFINED_PAYLOAD_POLICY:
        raise ValueError('Random-event undefined word requires its explicit unread policy')
    result = []
    for offset, record_type in enumerate(spec['record_types']):
        sequence = first_sequence + offset
        record = make_header(112, record_type, sequence, 6,
                             position_index if query else 0xffffffff)
        struct.pack_into('<III', record, 80, sequence, fields.identifier, fields.selector)
        # +92 is copied but never initialized by 14D550/14D290. The pinned
        # empty receiver cannot read it; zero is explicitly host storage policy.
        # Lookup+68 yields zero when 892B274A is absent. The terrain emitter
        # supplies it explicitly. 5A38D38C remains in Fields.raw_fields.
        struct.pack_into('<Iii', record, 96, fields.occurred_value, *fields.position)
        result.append(bytes(record))
    return tuple(result)
