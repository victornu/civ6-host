"""Three source-qualified empty weather receivers; no gameplay or draw calls.

The native update/expiry producers and their internal dispatch remain native.
Only the EXE presentation work is omitted under the owned, empty receiver
contract. Administrative input values are copied synchronously, without keeping
borrowed addresses or inventing deferred records or native query outputs.
"""
from dataclasses import dataclass
from functools import lru_cache
import hashlib
from pathlib import Path
import struct
from types import MappingProxyType

from .configuration_profiles import XP2_CORE_SHA256, _source

SOURCE = ('work/host-extensions/xp2-storm-lifecycle-static/source-profile-v2.json',
          '4811cab7730f5502e5a36391ca0d28db2efc6850b2c382ecea11d1cfaa1397c2')
STORM_CHANGED, STORM_REMOVED, DROUGHT_REMOVED = 0x21e62149, 0xfee911d7, 0xa5168c8e
CALLBACKS = MappingProxyType({STORM_CHANGED: 0x153430, STORM_REMOVED: 0x1536b0,
                             DROUGHT_REMOVED: 0x1457e0})
KINDS = frozenset(CALLBACKS)
SELECTOR, IDENTIFIER, POSITION = 0xa1e5a149, 0x0057c6ed, 0x8c468e3c
STATUS, DROUGHT_STATUS, INPUT_INDICES = 0xd6fcf3e4, 0xf36f4928, 0x0b9e7c29
POLICY = 'source-qualified-empty-presentation-zero-records'
MAX_INPUT_INDICES = 65536
_EXE = 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63'
_RECORDS = {STORM_CHANGED: (0x13a, 144, 0x125500),
            STORM_REMOVED: (0x139, 128, 0x1252f0),
            DROUGHT_REMOVED: (0x13c, 112, 0x125910)}
_SHAPES = {
    STORM_CHANGED: {SELECTOR: 2, IDENTIFIER: 3, STATUS: 2, POSITION: 13, INPUT_INDICES: 2},
    STORM_REMOVED: {SELECTOR: 3, IDENTIFIER: 3, POSITION: 13},
    DROUGHT_REMOVED: {SELECTOR: 3, IDENTIFIER: 3, DROUGHT_STATUS: 2, POSITION: 13},
}


def _instructions(body):
    capture = body.get('capture', body)
    return {int(row['rva'], 16) if 'rva' in row else int(row['va'], 16) - 0x140000000:
            row for fragment in capture.get('fragments', (capture,))
            for row in fragment['instructions']}


def _verify(p):
    from .xp2_turn_event_profile import fragments
    from .native.native_host_event_registry import EXE_EVENT_CALLBACKS
    from .xp2_turn_event_records import EMPTY_RECEIVER_STATE
    if (p.get('schema') != 'civ6-host.xp2-weather-lifecycle.static.v2'
            or p.get('native_execution') is not False or p.get('process_memory_read') is not False
            or p['images']['core']['sha256'] != XP2_CORE_SHA256
            or p['images']['exe']['sha256'] != _EXE
            or p['empty_contract'] != dict(EMPTY_RECEIVER_STATE)
            or set(p['routes']) != {hex(kind) for kind in KINDS}
            or set(p['receiver_rows']) != {'0x139', '0x13a', '0x13c'}
            or p['omission']['policy'] != POLICY
            or p['omission']['fifo_sequence_increment'] != 0
            or p['omission']['synthetic_records'] is not False
            or p['omission']['receiver_payload_reads'] != 0
            or p['omission']['cache_update_presence_required_per_callback'] is not False):
        raise ValueError('Weather lifecycle source or omission contract changed')
    for body in p['functions'].values():
        raw = b''.join(raw for _, raw in fragments(body))
        if (len(raw) != body['bytes'] or hashlib.sha256(raw).hexdigest() != body['sha256']
                or body['complete_unwind_or_leaf'] is not True):
            raise ValueError('Weather lifecycle complete source bytes changed')
    def texts(name):
        return {rva: row['text'] for rva, row in _instructions(p['functions'][name]).items()}
    # Join the real emitter arguments and ignored-return callsites, rather than
    # relying on an event name or on a callback address alone.
    required = {
      'core_0x1c0090': {
        0x1c0451: 'mov edx, 0xa1e5a149', 0x1c0456: 'call 0x1809a64f0',
        0x1c0467: 'mov edx, 0x57c6ed', 0x1c046c: 'call 0x1809a6640',
        0x1c04cc: 'mov edx, 0xd6fcf3e4', 0x1c04d5: 'call 0x1809a64f0',
        0x1c04e6: 'mov edx, 0xb9e7c29', 0x1c04f2: 'call 0x1809a07f0',
        0x1c052e: 'mov edx, 0x8c468e3c', 0x1c053e: 'call qword ptr [rax + 0xb0]',
        0x1c0548: 'mov ecx, 0x21e62149', 0x1c054d: 'call 0x1805fa910',
        0x1c0583: 'call 0x1801c2990', 0x1c0591: 'mov dword ptr [rbp - 0x40], 0xfee911d7',
        0x1c05ac: 'mov edx, 0x8c468e3c', 0x1c05bb: 'call 0x1805fd680',
        0x1c05c7: 'mov edx, 0x57c6ed', 0x1c05cf: 'call 0x1805fd7a0',
        0x1c05de: 'call 0x1805fc360'},
      'core_0x1ba250': {
        0x1ba5c9: 'call 0x1801c2780', 0x1ba643: 'mov edx, 0xf36f4928',
        0x1ba648: 'mov dword ptr [rsp + 0x68], 0xa5168c8e',
        0x1ba65c: 'call 0x1805fd780', 0x1ba666: 'mov edx, 0x8c468e3c',
        0x1ba672: 'call 0x1805fd680', 0x1ba67e: 'mov edx, 0x57c6ed',
        0x1ba686: 'call 0x1805fd7a0', 0x1ba699: 'call 0x1805fc280'},
      'core_0x9a64f0': {0x9a658e: 'mov dword ptr [rbp - 0x50], 2'},
      'core_0x9a6640': {0x9a66de: 'mov dword ptr [rbp - 0x50], 3'},
      'core_0x9a07f0': {0x9a0802: 'mov r8d, 2', 0x9a0810: 'mov dword ptr [rsp + 0x20], 4',
                         0x9a0818: 'call qword ptr [rax + 0xb0]'},
      'core_0x1c2990': {0x1c29f4: 'mov byte ptr [rdx + 0x58], 0'},
      'core_0x1c2780': {0x1c27eb: 'mov byte ptr [rcx + 0x38], 0'},
      'exe_0x153430': {0x15355a: 'call 0x140146d30', 0x153587: 'call 0x1400f1c00',
                        0x153670: 'call 0x140125500', 0x1534ae: 'je 0x140153692',
                        0x1534ba: 'jle 0x140153692', 0x1534c6: 'jle 0x140153692'},
      'exe_0x1536b0': {0x1537cb: 'call 0x140146d30', 0x153876: 'call 0x1401252f0'},
      'exe_0x1457e0': {0x145869: 'call 0x140146b30', 0x145914: 'call 0x140125910'},
    }
    for name, instructions in required.items():
        actual = texts(name)
        if any(actual.get(address) != text for address, text in instructions.items()):
            raise ValueError('Weather lifecycle producer/callback source join changed')
    for kind, callback in CALLBACKS.items():
        route = p['routes'][hex(kind)]
        record, size, writer = _RECORDS[kind]
        if (EXE_EVENT_CALLBACKS.get(kind) != callback or route['callback_rva'] != hex(callback)
                or (route['record_type'], route['record_size'], int(route['writer_rva'], 16)) != (record, size, writer)
                or {int(k, 16): v for k, v in route['fields'].items()} != _SHAPES[kind]
                or route['return_consumed'] is not False):
            raise ValueError('Weather lifecycle registration or typed field mapping changed')
        producer = texts('core_' + route['core_producer_rva'])
        call = int(route['emitter_call_rva'], 16)
        following = producer[call + 5]
        discarded = {STORM_CHANGED: 'mov eax, dword ptr [rsp + 0x6c]',
                     STORM_REMOVED: 'lea rcx, [rbp - 0x30]',
                     DROUGHT_REMOVED: 'lea rcx, [rbp - 0x60]'}
        if following != discarded[kind] or (kind != STORM_CHANGED
                and producer[call + 9] != 'call 0x1805fd840'):
            raise ValueError('Weather lifecycle callback return is no longer discarded')
        receiver = p['receiver_rows'][hex(record)]
        handler = texts('exe_' + receiver['handler_rva'])
        if [t for t in handler.values() if t.startswith('call ')] != [
                'call 0x14098a780', 'call 0x1400dc0d0', 'call 0x14098a7b0']:
            raise ValueError('Weather lifecycle receiver has another effect')
        ctor = _instructions(p['functions']['exe_' + receiver['constructor_rva']])
        targets = {target for row in ctor.values() for target in row.get('rip_targets', ())}
        if not {receiver['row_va'], hex(0x140000000 + int(receiver['handler_rva'], 16)),
                '0x1400ea0e0'} <= targets or int(receiver['row_va'], 16) != 0x1412c68b0 + record * 48:
            raise ValueError('Weather lifecycle receiver constructor/row changed')
        if not {'mov qword ptr [rcx], rbx', 'mov qword ptr [rcx + 8], rbx',
                'mov dword ptr [rax + 0x20], ebx', 'and byte ptr [rax + 0x30], 0xfc',
                'xor ebx, ebx'} <= {row['text'] for row in ctor.values()}:
            raise ValueError('Weather lifecycle receiver initialization changed')
        writer_text = set(texts('exe_' + hex(writer)).values())
        if not {'mov dword ptr [rbx], ' + hex(size),
                'mov dword ptr [rbx + 4], ' + hex(record)} <= writer_text:
            raise ValueError('Weather lifecycle original writer identity changed')
    if p['functions']['exe_0xdc0d0']['sha256'] != '326ad0582020365181be9ed3b3e0f595e1bf834ef24f5afdf167d9ae56292bca':
        raise ValueError('Weather lifecycle shared empty dispatcher changed')
    return p


@lru_cache(maxsize=1)
def source():
    return _verify(_source(SOURCE))


def source_dependencies():
    from .a0_family_source import _path, verify_pinned_files
    from .xp2_storm_query import source_dependencies as storm_dependencies
    from .xp2_descriptor53_query import source_dependencies as drought_dependencies
    from .xp2_turn_event_records import source_dependencies as typed_dependencies
    p = source()
    pins = {}
    for dependencies in (storm_dependencies(), drought_dependencies(), typed_dependencies()):
        for path, digest in dependencies.items():
            path = str(Path(path).resolve())
            if path in pins and pins[path] != digest:
                raise ValueError('Weather lifecycle source dependency conflict')
            pins[path] = digest
    for ref in [dict(path=SOURCE[0], sha256=SOURCE[1]), p['generator'], *p['references'].values()]:
        path = str(_path(ref['path']).resolve())
        if path in pins and pins[path] != ref['sha256']:
            raise ValueError('Weather lifecycle source dependency conflict')
        pins[path] = ref['sha256']
    verify_pinned_files(pins)
    return pins


def core_fragments():
    from .xp2_turn_event_profile import fragments
    for body in source()['functions'].values():
        if body['image'] == 'xp2':
            for address, raw in fragments(body):
                yield address - 0x180000000, raw


def bind_owner(backend, core, read):
    backend.check_thread()
    if backend.core is not core or backend.load_abi.core_sha256 != XP2_CORE_SHA256:
        raise ValueError('Weather lifecycle needs its exact XP2 owner')
    source_dependencies()
    for rva, raw in core_fragments():
        for offset in range(0, len(raw), 4096):
            expected = raw[offset:offset + 4096]
            actual = read(core._handle + rva + offset, len(expected))
            if type(actual) is not bytes or actual != expected:
                raise ValueError('Weather lifecycle live producer source changed')
    backend._xp2_weather_lifecycle_source_identity = (id(core), core._handle, XP2_CORE_SHA256, SOURCE[1])
    return SOURCE[1]


def validate_empty_owner(owner):
    """Check actual service state while the existing continuation owns the call."""
    from .a0_family_service import A0FamilyService
    from .a0_foundation_events import require_borrow
    from .xp2_turn_event_records import EMPTY_RECEIVER_STATE
    if type(owner) is not A0FamilyService:
        raise ValueError('Weather omission requires the real A0 owner')
    owner._check()
    token = require_borrow(owner)
    backend = token.owner
    if (backend.load_abi.core_sha256 != XP2_CORE_SHA256 or owner.active_kind not in KINDS
            or owner.arguments.reader.core_sha256 != XP2_CORE_SHA256
            or owner.deferred.cache_core_sha256 != XP2_CORE_SHA256
            or owner.empty_receiver_state != dict(EMPTY_RECEIVER_STATE)
            or owner._receiver_profile != dict(EMPTY_RECEIVER_STATE)
            or any(type(owner.empty_receiver_state[k]) is not type(v)
                   for k, v in EMPTY_RECEIVER_STATE.items())
            or owner.entity_listener_count != 0 or type(owner.entity_listener_count) is not int
            or owner.dynamic_event_registration_present is not False
            or owner.normalizer_transform_present is not False
            or owner.per_thread_hook_present is not False
            or owner.writer_metadata_callback_present is not False
            or getattr(backend, '_xp2_weather_lifecycle_source_identity', None) !=
               (id(backend.core), backend.core._handle, XP2_CORE_SHA256, SOURCE[1])):
        raise ValueError('Weather omission empty receiver, hooks or bound source changed')
    source()
    return POLICY


@dataclass(frozen=True)
class LifecycleFields:
    kind: int
    selector: int
    identifier: int
    status: int | None
    position: tuple[int, int]
    input_plot_indices: tuple[int, ...] | None

    def to_admin(self):
        """JSON values only, with no borrowed address or purported query result."""
        return dict(selector=self.selector, identifier=self.identifier, status=self.status,
            status_key=hex(STATUS if self.kind == STORM_CHANGED else DROUGHT_STATUS)
                if self.status is not None else None,
            input_position=list(self.position),
            input_plot_indices=list(self.input_plot_indices) if self.input_plot_indices is not None else None,
            field_tags={hex(k): v for k, v in _SHAPES[self.kind].items()},
            pointer_payloads_copied=True, borrowed_pointer_addresses_retained=False)


def _copy(read, pointer, size):
    if not callable(read) or type(pointer) is not int or pointer <= 0 or pointer + size > 2**64:
        raise ValueError('Weather lifecycle pointer is outside its bounded copy domain')
    parts = []
    for offset in range(0, size, 4096):
        count = min(4096, size - offset)
        part = read(pointer + offset, count)
        if type(part) is not bytes or len(part) != count:
            raise ValueError('Weather lifecycle pointer payload copy is incomplete')
        parts.append(part)
    return b''.join(parts)


def decode_fields(kind, raw_fields, read):
    """Copy source-typed inputs during the caller's synchronous native borrow."""
    source()
    if (type(kind) is not int or kind not in KINDS or type(raw_fields) is not dict
            or set(raw_fields) != set(_SHAPES[kind])
            or any(type(key) is not int or type(raw) is not bytes or len(raw) != 24
                   for key, raw in raw_fields.items())):
        raise ValueError('Weather lifecycle argument shape is not source qualified')
    from .native.native_scalar_event_encoder import _read_u32_variant
    values = {}
    for key, tag in _SHAPES[kind].items():
        raw = raw_fields[key]
        if struct.unpack_from('<H', raw)[0] != tag:
            raise ValueError('Weather lifecycle argument tag differs')
        if key not in (POSITION, INPUT_INDICES):
            values[key] = _read_u32_variant(raw, tag, hex(key))
    pointer, size, flags = struct.unpack_from('<QII', raw_fields[POSITION], 8)
    if size != 8 or flags != 0x21000001:
        raise ValueError('Weather lifecycle position envelope differs')
    position = struct.unpack('<ii', _copy(read, pointer, 8))
    indices = None
    if kind == STORM_CHANGED:
        pointer, size, flags = struct.unpack_from('<QII', raw_fields[INPUT_INDICES], 8)
        count = flags & 0xffffff
        if size != 4 or count > MAX_INPUT_INDICES:
            raise ValueError('Weather lifecycle DWORD array width/count differs')
        if count == 0:
            if pointer != 0 or flags != 0x20000000:
                raise ValueError('Weather lifecycle empty array envelope differs')
            indices = ()
        else:
            if flags & 0xff000000 != 0x21000000:
                raise ValueError('Weather lifecycle DWORD array flags differ')
            indices = struct.unpack('<' + str(count) + 'I', _copy(read, pointer, count * 4))
    return LifecycleFields(kind, values[SELECTOR], values[IDENTIFIER],
        values.get(STATUS if kind == STORM_CHANGED else DROUGHT_STATUS), position, indices)


__all__ = ['SOURCE', 'KINDS', 'CALLBACKS', 'POLICY', 'STORM_CHANGED', 'STORM_REMOVED',
           'DROUGHT_REMOVED', 'LifecycleFields', 'source', 'source_dependencies',
           'core_fragments', 'bind_owner', 'validate_empty_owner', 'decode_fields']
