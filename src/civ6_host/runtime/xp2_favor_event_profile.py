"""XP2 FavorChanged: exact scalar transport on the shared EXE FIFO.

The native producer changes Favor before notifying the host. This module only
copies that notification; it neither implements the mutation nor grants public
visibility to its administrative payload.
"""
from functools import lru_cache
import hashlib
import struct
from types import MappingProxyType

from .configuration_profiles import XP1_CORE_SHA256, XP2_CORE_SHA256, _source

SOURCE = ('work/host-extensions/xp2-favor-event-static/source-profile-v1.json',
          '1a93acccf6c84dc2dcf9c49c5715eb4b9c8542d3028ee50b6cb236cfec4bea1a')
EXE_SHA256 = 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63'
EVENT_KIND, RECORD_TYPE, RECORD_SIZE = 0x68e7d3da, 0x142, 96
CALLBACK_RVA, WRITER_RVA = 0x146600, 0x126570
SELECTOR_KEY = 0xa1e5a149
VALUE_KEYS = (0xd6fcf3e4, 0xa1fbc372, 0x38f292c8)
CALLBACKS = MappingProxyType({EVENT_KIND: CALLBACK_RVA})
RECORDS = MappingProxyType({EVENT_KIND: frozenset((RECORD_TYPE,))})
SIZES = MappingProxyType({RECORD_TYPE: RECORD_SIZE})
EMPTY_RECEIVER_STATE = MappingProxyType(dict(observer_registered=False,
    state_pointer_nonnull=True, pre_hook=None, post_hook=None,
    subscriber_count=0, state_flags=0))


def _capture(body):
    return body.get('capture', body)


def _rows(body):
    b = _capture(body)
    return [r for f in b.get('fragments', (b,)) for r in f['instructions']]


def _text(body, base=0):
    return {(int(r['rva'], 16) if 'rva' in r else int(r['va'], 16)-base): r['text']
            for r in _rows(body)}


def _fragments(body):
    b = _capture(body)
    for f in b.get('fragments', (b,)):
        start = int(f['start_va'], 16)
        raw = b''.join(bytes.fromhex(r['bytes']) for r in f['instructions'])
        if (len(raw) != f['length'] or hashlib.sha256(raw).hexdigest() != f['raw_sha256']
                or start + len(raw) != int(f['end_va_exclusive'], 16)):
            raise ValueError('Favor source fragment changed')
        cursor = start
        for r in f['instructions']:
            if int(r['va'], 16) != cursor:
                raise ValueError('Favor source instruction boundary changed')
            cursor += len(bytes.fromhex(r['bytes']))
        yield start, raw


def _require(actual, required, label):
    if any(actual.get(address) != text for address, text in required.items()):
        raise ValueError('Favor '+label+' source contract changed')


def _validate_contract(p, primitives, normalizer, receiver):
    functions = p['functions']
    _require(_text(functions['xp2_26c410'], 0x180000000), {
        0x26c4a7: 'mov r9d, ebp',
        0x26c4aa: 'mov qword ptr [rsp + 0x20], 0x68e7d3da',
        0x26c4b3: 'mov r8d, edi', 0x26c4b6: 'mov rcx, qword ptr [rsp + 0x20]',
        0x26c4bb: 'mov edx, dword ptr [rax + 0xd8]',
        0x26c4d5: 'jmp 0x1805fc680'}, 'producer')
    _require(_text(functions['xp2_5fc680'], 0x180000000), {
        0x5fc6d0: 'mov edx, 0xa1e5a149', 0x5fc6d5: 'call 0x1809a0000',
        0x5fc6e2: 'mov edx, 0xd6fcf3e4', 0x5fc6e7: 'call 0x18099fee0',
        0x5fc6f4: 'mov edx, 0xa1fbc372', 0x5fc6f9: 'call 0x18099fee0',
        0x5fc706: 'mov edx, 0x38f292c8', 0x5fc70b: 'call 0x18099fee0',
        0x5fc71c: 'call 0x18007c670', 0x5fc737: 'call qword ptr [rax + 0xa0]'}, 'builder')
    for key, writes in (('0x99fee0', {0x99ff59: 'mov dword ptr [rbx], 2',
                                    0x99ff6f: 'mov dword ptr [rsp + 0x30], 2'}),
                        ('0x9a0000', {0x9a0079: 'mov dword ptr [rbx], 3',
                                     0x9a008f: 'mov dword ptr [rsp + 0x30], 3'})):
        _require(_text(primitives['functions'][key], 0x180000000), writes, 'setter tag')
    if tuple((int(f['key'], 16), f['tag']) for f in p['fields']) != (
            (SELECTOR_KEY, 3), *((key, 2) for key in VALUE_KEYS)):
        raise ValueError('Favor field/tag mapping changed')
    _require(_text(normalizer['common_host_normalizer']['body'], 0x140000000), {
        0x1ca430: 'cmp ecx, 0x38f292c8', 0x1ca455: 'mov dword ptr [rbp + 0x1f], eax',
        0x1ca651: 'cmp ecx, 0xa1fbc372', 0x1ca676: 'mov dword ptr [rbp + 0x1b], eax',
        0x1ca6c7: 'cmp ecx, 0xd6fcf3e4', 0x1ca6ec: 'mov dword ptr [rbp + 0x17], eax',
        0x1ca7b6: 'lea rdx, [rbp - 0x39]'}, 'normalizer')
    _require(_text(functions['exe_146600'], 0x140000000), {
        0x146604: 'mov eax, dword ptr [rdx + 0x50]',
        0x14660b: 'mov eax, dword ptr [rdx + 0x54]',
        0x146612: 'mov eax, dword ptr [rdx + 0x58]',
        0x146669: 'call 0x140126570'}, 'callback')
    _require(_text(functions['exe_126570'], 0x140000000), {
        0x1265f2: 'lock xadd dword ptr [rsi + 0x38], edi',
        0x126612: 'mov dword ptr [rbx], 0x60',
        0x126618: 'mov dword ptr [rbx + 4], 0x142',
        0x126685: 'mov dword ptr [rax + 0x38], esi',
        0x126688: 'movups xmm0, xmmword ptr [r14]',
        0x12669f: 'movups xmmword ptr [rax], xmm0',
        0x1266a2: 'mov dword ptr [rax], edi'}, 'writer')
    setup = _rows(functions['exe_c8f20'])
    if (not any('0x1412ca510' in r.get('rip_targets', ()) for r in setup)
            or not any('0x1400d6550' in r.get('rip_targets', ()) for r in setup)
            or [r['text'] for r in _rows(functions['exe_d6550']) if r['text'].startswith('call ')]
            != ['call 0x14098a780', 'call 0x1400dc0d0', 'call 0x14098a7b0']):
        raise ValueError('Favor receiver registration changed')
    expected_window = [r for r in _rows(receiver['captures']['initializer'])
                       if 0x1400ddfaa <= int(r['va'], 16) <= 0x1400ddfb4]
    if (tuple(p['receiver']['initializer_window']) != tuple(expected_window)
            or p['receiver']['event_name'] != 'GameCoreEvent::FavorChanged'
            or p['receiver']['row_va'] != '0x1412ca510'):
        raise ValueError('Favor receiver initializer/name changed')


@lru_cache(maxsize=1)
def source():
    p = _source(SOURCE)
    if (p['schema'] != 'civ6-host.xp2-favor-event.static.v1' or p['native_execution'] is not False
            or p['images']['xp2']['sha256'] != XP2_CORE_SHA256
            or p['images']['exe']['sha256'] != EXE_SHA256):
        raise ValueError('Favor engine/source identity changed')
    for body in p['functions'].values():
        if hashlib.sha256(b''.join(raw for _, raw in _fragments(body))).hexdigest() != body['sha256']:
            raise ValueError('Favor complete source body changed')
    refs = {key: _source((ref['path'], ref['sha256'])) for key, ref in p['references'].items()}
    _validate_contract(p, refs['parameter_primitives'], refs['normalizer'], refs['receiver_dispatch'])
    from .native.native_host_event_registry import EXE_EVENT_CALLBACKS
    if EXE_EVENT_CALLBACKS.get(EVENT_KIND) != CALLBACK_RVA:
        raise ValueError('Favor EXE callback registration changed')
    return p


def source_dependencies(*, core_sha256=XP2_CORE_SHA256):
    if core_sha256 == XP1_CORE_SHA256:
        return {}
    if core_sha256 != XP2_CORE_SHA256:
        raise ValueError('Unqualified Favor engine')
    from .a0_family_source import _path, verify_pinned_files
    p = source()
    pins = {str(_path(SOURCE[0]).resolve()): SOURCE[1]}
    pins.update({str(_path(r['path']).resolve()): r['sha256'] for r in p['references'].values()})
    verify_pinned_files(pins)
    return pins


def core_fragments():
    for body in source()['functions'].values():
        if body['image'] == 'xp2':
            for va, raw in _fragments(body):
                yield va-0x180000000, raw


def bind_owner(backend, core, read):
    backend.check_thread()
    if backend.core is not core or backend.load_abi.core_sha256 != XP2_CORE_SHA256:
        raise ValueError('Favor owner/engine mismatch')
    for rva, raw in core_fragments():
        for offset in range(0, len(raw), 4096):
            chunk = raw[offset:offset+4096]
            if read(core._handle+rva+offset, len(chunk)) != chunk:
                raise ValueError('Favor live producer bytes changed')
    return SOURCE[1]


def receiver_rows():
    row = source()['receiver']
    return {RECORD_TYPE: dict(event_name=row['event_name'],
        handler_va=hex(0x140000000+int(row['handler_rva'], 16)),
        handler_body_sha256=row['handler_sha256'], record_sizes={RECORD_SIZE},
        source_sha256=SOURCE[1])}


def receiver_row(record_type):
    return receiver_rows().get(record_type) if type(record_type) is int else None


def event_profile(*, core_sha256):
    if core_sha256 != XP2_CORE_SHA256:
        raise ValueError('Unqualified Favor engine')
    source_dependencies()
    from .a0_family_source import A0FamilyProfile
    return A0FamilyProfile(RECORDS, SIZES, SOURCE[1])


def registration_metadata(kind):
    if type(kind) is not int or kind != EVENT_KIND:
        raise ValueError('Unqualified Favor event kind')
    source()
    return dict(callback_rva=CALLBACK_RVA, writer_rva=WRITER_RVA,
                record_type=RECORD_TYPE, record_size=RECORD_SIZE, callback_flag=0,
                source_sha256=SOURCE[1], event_name='GameCoreEvent::FavorChanged')


def encode(kind, fields, sequence, *, empty_receiver_state,
           normalizer_transform_present, per_thread_hook_present,
           writer_metadata_callback_present):
    """Return one immutable 96-byte record; the existing owner admits/enqueues it."""
    registration_metadata(kind)
    if (normalizer_transform_present is not False or per_thread_hook_present is not False
            or writer_metadata_callback_present is not False):
        raise ValueError('Unqualified Favor optional service')
    if (type(empty_receiver_state) is not dict or set(empty_receiver_state) != set(EMPTY_RECEIVER_STATE)
            or any(type(empty_receiver_state[k]) is not type(v) or empty_receiver_state[k] != v
                   for k, v in EMPTY_RECEIVER_STATE.items())):
        raise ValueError('Favor requires the exact empty receiver state')
    if (type(fields) is not dict or set(fields) != {SELECTOR_KEY, *VALUE_KEYS}
            or any(type(k) is not int or type(v) is not bytes or len(v) != 24
                   for k, v in fields.items())):
        raise ValueError('Favor requires its exact four scalar fields')
    from .native.native_scalar_event_encoder import _read_u32_variant, _encode_profile_record
    selector = _read_u32_variant(fields[SELECTOR_KEY], 3, 'Favor selector')
    if selector != 0:
        raise ValueError('Favor producer selector must be zero')
    values = tuple(_read_u32_variant(fields[key], 2, 'Favor value') for key in VALUE_KEYS)
    return _encode_profile_record(dict(payload_value_count=3, writer_record_type='0x142'),
                                  sequence, values, queue_metadata=0)
