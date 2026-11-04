"""Source-qualified XP2 feature-reveal A0 notifications.

Core performs the reveal work and its internal event dispatch before calling
the host. This module selects only the three EXE presentation callbacks whose
actual receiver rows and empty synchronous path are separately pinned. The
coordinate allocation belongs to the temporary event map. The callback borrows
that map, so decoding copies its eight payload bytes during the active callback
and never returns that pointer.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import hashlib
import struct
from types import MappingProxyType

from .configuration_profiles import XP2_CORE_SHA256, _source
from .a0_family_source import _path, verify_pinned_files

HISTORICAL_SOURCE = ('work/host-extensions/xp2-combat-notification-static/feature-reveal-arguments-source-v1.json',
                     '07a1a3615f79f6814ab652bc8a4392d9bb1b3d6eb8c892e9f8eca47171459a67')
SOURCE = ('work/host-extensions/xp2-combat-notification-static/feature-reveal-arguments-source-v2.json',
          'e4658a1bb64a32fc94e735b0f8ef47d94d75cf3ad8377f34973c9daa5e2e2c20')
PRODUCER_SOURCE = ('work/host-extensions/xp2-combat-notification-static/source-profile-v2.json',
                   '9d4a5105470fc058529d056a8486df118f5df19a2a4df7f0573bf026d161ac5a')
RECEIVER_SOURCE = ('work/host-extensions/xp2-combat-notification-static/receiver-source-profile-v1.json',
                   'b626d2adc40a35cf44b7871f2cbe1cc9dda0021f37c9d456a5403a4a86ce07a8')
POLICY = 'source-qualified-empty-presentation-zero-records'
FLOODPLAIN_REVEALED = 0xEE846031
VOLCANO_REVEALED = 0x7D35CA0C
GEOTHERMAL_FISSURE_REVEALED = 0x8BED8EC4
KINDS = frozenset((FLOODPLAIN_REVEALED, VOLCANO_REVEALED, GEOTHERMAL_FISSURE_REVEALED))
CALLBACKS = MappingProxyType({FLOODPLAIN_REVEALED: 0x1470B0,
                              VOLCANO_REVEALED: 0x159660,
                              GEOTHERMAL_FISSURE_REVEALED: 0x147490})
EVENT_NAMES = MappingProxyType({FLOODPLAIN_REVEALED: 'GameCoreEvent::FloodplainRevealed',
                                VOLCANO_REVEALED: 'GameCoreEvent::VolcanoRevealed',
                                GEOTHERMAL_FISSURE_REVEALED: 'GameCoreEvent::GeothermalFissureRevealed'})
SELECTOR_KEY, POSITION_KEY, VALUE_KEY = 0xA1E5A149, 0x8C468E3C, 0xD6FCF3E4
_CORE_SHA = XP2_CORE_SHA256
_EXE_SHA = 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63'
_OWNERSHIP_SLOTS = MappingProxyType(dict(
    pair_setter=(0xABF080, 0xB0, 0x9A0890),
    map_allocator=(0xABF080, 0x20, 0x989D0),
    pair_allocate=(0xABEFF8, 0x10, 0x9A1620),
    pair_reallocate=(0xABEFF8, 0x18, 0x9A16A0),
    pair_release=(0xABEFF8, 0x20, 0x9A1760)))
_ROUTES = MappingProxyType({
    FLOODPLAIN_REVEALED: (0x13D, 0x60, 0x125B10),
    VOLCANO_REVEALED: (0x13E, 0x60, 0x125D00),
    GEOTHERMAL_FISSURE_REVEALED: (0x13F, 0x60, 0x125EF0),
})
_EMPTY_STATE = MappingProxyType(dict(observer_registered=False, state_pointer_nonnull=True,
    pre_hook=None, post_hook=None, subscriber_count=0, state_flags=0))


def _capture(body):
    return body.get('capture', body)


def _rows(body):
    cap = _capture(body)
    return [row for fragment in cap.get('fragments', (cap,))
            for row in fragment['instructions']]


def _fragments(body):
    cap = _capture(body)
    for fragment in cap.get('fragments', (cap,)):
        raw = b''.join(bytes.fromhex(row['bytes']) for row in fragment['instructions'])
        start = int(fragment['start_rva'], 16)
        if (len(raw) != fragment['length']
                or hashlib.sha256(raw).hexdigest() != fragment['sha256']
                or fragment.get('raw_hex') != raw.hex()):
            raise ValueError('Feature-reveal instruction fragment changed')
        cursor = start
        for row in fragment['instructions']:
            if int(row['rva'], 16) != cursor:
                raise ValueError('Feature-reveal instruction boundaries changed')
            cursor += len(bytes.fromhex(row['bytes']))
        if cursor != int(fragment['end_rva_exclusive'], 16):
            raise ValueError('Feature-reveal function interval changed')
        yield start, raw


def _text(body):
    return {(int(row['rva'], 16) if 'rva' in row else int(row['va'], 16) - 0x140000000):
            row['text'] for row in _rows(body)}


def _verify_ref(ref):
    path = _path(ref['path'])
    if path.suffix.lower() == '.json':
        _source((str(path), ref['sha256']))
    elif hashlib.sha256(path.read_bytes()).hexdigest() != ref['sha256']:
        raise ValueError('Feature-reveal source reference changed: ' + str(path))


@lru_cache(maxsize=1)
def source():
    from .native.native_host_event_registry import EXE_EVENT_CALLBACKS
    p = _source(SOURCE)
    producer = _source(PRODUCER_SOURCE)
    receivers = _source(RECEIVER_SOURCE)
    if (p.get('schema') != 'civ6-host.xp2-feature-reveal-arguments.static.v2'
            or p.get('native_execution') is not False or p.get('process_memory_read') is not False
            or p.get('images', {}).get('xp2', {}).get('sha256') != _CORE_SHA
            or p.get('images', {}).get('exe', {}).get('sha256') != _EXE_SHA
            or p.get('references', {}).get('producer') != dict(path=PRODUCER_SOURCE[0], sha256=PRODUCER_SOURCE[1])
            or p.get('references', {}).get('receivers') != dict(path=RECEIVER_SOURCE[0], sha256=RECEIVER_SOURCE[1])
            or p.get('references', {}).get('historical_arguments') !=
               dict(path=HISTORICAL_SOURCE[0], sha256=HISTORICAL_SOURCE[1])
            or producer.get('schema') != 'civ6rl.xp2.combat_notification.static.v1'
            or producer['images']['xp2_core']['sha256'] != _CORE_SHA
            or producer['images']['shared_exe']['sha256'] != _EXE_SHA
            or receivers.get('schema') != 'civ6-host.xp2-terrain-reveal.receivers.v1'
            or receivers.get('native_execution') is not False
            or receivers.get('process_memory_read') is not False
            or receivers.get('images', {}).get('xp2_core', {}).get('sha256') != _CORE_SHA
            or receivers.get('images', {}).get('shared_exe', {}).get('sha256') != _EXE_SHA
            or receivers.get('references', {}).get('producer') !=
               dict(path=PRODUCER_SOURCE[0], sha256=PRODUCER_SOURCE[1])):
        raise ValueError('Feature-reveal source identities changed')
    generator = p.get('generator')
    if generator is None or set(generator) != {'path', 'sha256'}:
        raise ValueError('Feature-reveal source generator pin is missing')
    for ref in [generator, *p['references'].values(), *producer['references'].values(),
                *receivers['references'].values()]:
        _verify_ref(ref)
    for body in p['functions'].values():
        if body.get('image') != 'xp2':
            raise ValueError('Feature-reveal Core function image changed')
        raw = b''.join(data for _, data in _fragments(body))
        if hashlib.sha256(raw).hexdigest() != body['sha256']:
            raise ValueError('Feature-reveal Core body digest changed')
    if (p['map_pair_slot'] != dict(vtable_rva='0xabf080', slot='0xb0',
            slot_bytes='90089a8001000000', target_rva='0x9a0890')
            or p['typed_input_contract']['fields'] != {
                '0xa1e5a149': {'tag': 3, 'value': 'uint32 zero copied from high half of saved uint64 event kind', 'flags': 0},
                '0x8c468e3c': {'tag': 0, 'value': 'pointer to event-map-owned copy of 8-byte (int32 x,int32 y) pair; consumer copies during callback', 'size': 8, 'count': 1, 'flags': '0x21000001', 'input_flags': '0x01000000'},
                '0xd6fcf3e4': {'tag': 2, 'value': 'uint32 copied from producer r8d', 'flags': 0}}
            or set(p['typed_input_contract']['kind_values']) != {hex(k) for k in KINDS}
            or p['typed_input_contract']['borrowed_payload_rule'] !=
               'The 0x8c468e3c variant owns an allocated coordinate copy in the temporary event map. The callback borrows that map. Decode must copy exactly 8 bytes during the active A0 callback; never return or retain its pointer/header.'
            or p['typed_input_contract']['selector_zero_derivation'] !=
               'The emitter saves rcx at entry [rsp+8]; it reads [rsp+0xb4] as the high DWORD of that saved qword. Producer passes a zero-extended DWORD event kind.'):
        raise ValueError('Feature-reveal typed input contract changed')
    _verify_coordinate_ownership(p)
    pair = _text(p['functions']['xp2_event_argument_pair_setter'])
    if (p['functions']['xp2_event_argument_pair_setter']['start_rva'] != '0x9a0890'
            or pair.get(0x9A089F) != 'mov word ptr [rsp + 0x18], r8w'
            or pair.get(0x9A0917) != 'mov ebx, dword ptr [rsp + 0x110]'
            or pair.get(0x9A0922) != 'bt ebx, 0x18'
            or pair.get(0x9A0A61) != 'call 0x18099dc00'):
        raise ValueError('Feature-reveal pair setter slot body changed')
    parent = producer['functions']['xp2_core']
    emitter = _text(parent['host_a0_emitter'])
    emitter_expected = {
        0x5FAB85: 'xor r8d, r8d', 0x5FAB93: 'mov edx, 0x8c468e3c',
        0x5FAB7D: 'mov dword ptr [rsp + 0x30], 0x1000000',
        0x5FAB88: 'mov dword ptr [rsp + 0x28], 1',
        0x5FAB98: 'mov dword ptr [rsp + 0x20], 8',
        0x5FABA0: 'call qword ptr [rax + 0xb0]',
        0x5FABA6: 'mov r8d, ebx', 0x5FABAE: 'mov edx, 0xd6fcf3e4',
    }
    if any(emitter.get(address) != text for address, text in emitter_expected.items()):
        raise ValueError('Feature-reveal typed argument call signature changed')
    scalar_contracts = (
        ('xp2_selector_scalar_setter', 0x9A0000, 3, 0x9A008F, 0x9A00AB),
        ('xp2_status_scalar_setter', 0x99FEE0, 2, 0x99FF6F, 0x99FF8B),
    )
    for name, entry, tag, tag_store, value_store in scalar_contracts:
        body = p['functions'][name]
        code = _text(body)
        if (int(body['start_rva'], 16) != entry
                or code.get(tag_store) != f'mov dword ptr [rsp + 0x30], {tag}'
                or code.get(value_store) != 'mov dword ptr [rsp + 0x38], r8d'
                or not any(text == 'xor ecx, ecx' for text in code.values())
                or not any(text == 'mov qword ptr [rsp + 0x40], rcx' for text in code.values())):
            raise ValueError('Feature-reveal scalar argument setter changed: ' + name)
    copy_tail = p['functions']['xp2_temporary_payload_copy']
    if (copy_tail['start_rva'] != '0x990d00'
            or [r['text'] for r in _rows(copy_tail)] != [
                'push rbx', 'sub rsp, 0x20', 'mov rbx, rcx', 'call 0x1809b0f94',
                'mov rax, rbx', 'add rsp, 0x20', 'pop rbx', 'ret']):
        raise ValueError('Feature-reveal temporary payload copy tail changed')
    from .xp2_preload_source import body as preload_body
    for name, required in (
        ('set_hash', {0x9A008F: 'mov dword ptr [rsp + 0x30], 3',
                      0x9A00AB: 'mov dword ptr [rsp + 0x38], r8d'}),
        ('set_uint32', {0x99FF6F: 'mov dword ptr [rsp + 0x30], 2',
                        0x99FF8B: 'mov dword ptr [rsp + 0x38], r8d'})):
        actual = _text(preload_body(name))
        if any(actual.get(address) != text for address, text in required.items()):
            raise ValueError('Feature-reveal scalar setter tag/value changed: ' + name)
    required_emitter = {
        0x5FAB25: 'mov qword ptr [rsp + 8], rcx',
        0x5FAB5C: 'mov r8d, dword ptr [rsp + 0xb4]',
        0x5FAB69: 'mov edx, 0xa1e5a149', 0x5FAB6E: 'call 0x1809a0000',
        0x5FAB93: 'mov edx, 0x8c468e3c', 0x5FABA0: 'call qword ptr [rax + 0xb0]',
        0x5FABAE: 'mov edx, 0xd6fcf3e4', 0x5FABB3: 'call 0x18099fee0',
        0x5FABC4: 'call 0x18007c670', 0x5FABDF: 'call qword ptr [rax + 0xa0]',
        0x5FABEA: 'mov ebx, eax', 0x5FABEC: 'call 0x18099e5d0',
        0x5FABF1: 'mov eax, ebx', 0x5FAC03: 'ret'}
    if any(emitter.get(address) != text for address, text in required_emitter.items()):
        raise ValueError('Feature-reveal producer typed-key/callback order changed')
    core_producer = _text(parent['combat_notification_producer'])
    required_producer = {
        0x37BB27: 'call 0x180721d60', 0x37BB63: 'mov qword ptr [rbp - 0x18], 0x7d35ca0c',
        0x37BB51: 'movsx eax, word ptr [rdi + 0x28]', 0x37BB59: 'mov dword ptr [rbp + 0x38], eax',
        0x37BB5F: 'movsx eax, word ptr [rdi + 0x2a]', 0x37BB6F: 'mov dword ptr [rbp + 0x3c], eax',
        0x37BB72: 'call 0x1805fab20', 0x37BB77: 'lea rcx, [rip + 0x67797a]',
        0x37BB7E: 'call 0x180606270',
        0x37BADB: 'xor r13d, r13d',
        0x37BBA2: 'movsx eax, word ptr [rdi + 0x28]', 0x37BBA6: 'lea rdx, [rbp + 0x38]',
        0x37BBAA: 'mov dword ptr [rbp + 0x38], eax', 0x37BBAD: 'mov r8d, esi',
        0x37BC04: 'movsx eax, word ptr [rdi + 0x2a]', 0x37BC17: 'mov dword ptr [rbp + 0x3c], eax',
        0x37BBB4: 'mov dword ptr [rbp - 0x18], 0xee846031',
        0x37BBBB: 'mov dword ptr [rbp - 0x14], r13d',
        0x37BBBF: 'mov rcx, qword ptr [rbp - 0x18]',
        0x37BBC6: 'call 0x1805fab20', 0x37BBCB: 'lea rcx, [rip + 0x677946]',
        0x37BBD2: 'call 0x180606270',
        0x37BC1A: 'call 0x1805fab20', 0x37BC1F: 'lea rcx, [rip + 0x65303a]',
        0x37BC26: 'call 0x180606270',
        0x37BC6E: 'call 0x1805fab20', 0x37BC73: 'movsx eax, word ptr [rdi + 0x3c]',
        0x37BCA2: 'call 0x1805fab20', 0x37BCA7: 'lea rcx, [rip + 0x67788a]',
        0x37BCAE: 'call 0x180606270',
        0x37BCD2: 'movsx eax, word ptr [rdi + 0x28]', 0x37BCDA: 'mov dword ptr [rbp + 0x38], eax',
        0x37BCDD: 'mov r8d, esi', 0x37BCF3: 'mov dword ptr [rbp + 0x3c], eax',
        0x37BCEB: 'mov dword ptr [rbp - 0x14], r13d',
        0x37BCF6: 'call 0x1805fab20', 0x37BCFB: 'cmp byte ptr [rdi + 0x37], 0'}
    if any(core_producer.get(address) != text for address, text in required_producer.items()):
        raise ValueError('Feature-reveal Core producer source join changed')
    if (_text(parent['producer_caller']).get(0x3B42F8) != 'call 0x18037ba80'
            or _text(parent['producer_caller']).get(0x3B42FD) != 'mov rax, qword ptr [rip + 0x7d6764]'):
        raise ValueError('Feature-reveal outer caller no longer discards the Core return')
    if (core_producer.get(0x37BCFB) != 'cmp byte ptr [rdi + 0x37], 0'
            or core_producer.get(0x37BD09) != 'jle 0x18037bd1e'
            or core_producer.get(0x37BD0B) != 'call 0x18072d170'
            or core_producer.get(0x37BD19) != 'call 0x18072d080'
            or core_producer.get(0x37BD1E) != 'movsx eax, word ptr [rdi + 0x28]'):
        raise ValueError('Feature-reveal A0 return is no longer discarded on every path')
    for kind, callback in CALLBACKS.items():
        if EXE_EVENT_CALLBACKS.get(kind) != callback:
            raise ValueError('Feature-reveal callback registry differs')
        record_type, size, writer = _ROUTES[kind]
        row = receivers['receiver_rows'][hex(record_type)]
        route = receivers['routes'][hex(kind)]
        if (route['record_type'] != record_type or route['record_size'] != size
                or route['callback_rva'] != hex(callback)
                or route['writer_rva'] != hex(writer)
                or row['event_name'] != EVENT_NAMES[kind]
                or int(row['row_va'], 16) != 0x1412C68B0 + record_type * 48):
            raise ValueError('Feature-reveal callback/receiver route differs')
        handler = _text(receivers['functions']['exe_' + row['handler_rva']])
        if [text for text in handler.values() if text.startswith('call ')] != [
                'call 0x14098a780', 'call 0x1400dc0d0', 'call 0x14098a7b0']:
            raise ValueError('Feature-reveal empty receiver handler changed')
        ctor = _text(receivers['functions']['exe_' + row['constructor_rva']])
        if not {'mov qword ptr [rcx], rbx', 'mov qword ptr [rcx + 8], rbx',
                'mov qword ptr [rcx + 0x10], rbx', 'mov dword ptr [rax + 0x20], ebx',
                'and byte ptr [rax + 0x30], 0xfc'} <= set(ctor.values()):
            raise ValueError('Feature-reveal receiver constructor state changed')
        # The producer-v2 labels writer bodies by kind inconsistently. Bind by
        # body start RVA and validate the actual emitted type, never the label.
        writer_body = next((body for name, body in producer['functions']['shared_exe'].items()
                            if name.startswith('writer_') and int(body['start_rva'], 16) == writer), None)
        if writer_body is None:
            raise ValueError('Feature-reveal exact writer body is missing')
        writes = set(_text(writer_body).values())
        if (f'mov dword ptr [rbx], {hex(size)}' not in writes
                or f'mov dword ptr [rbx + 4], {hex(record_type)}' not in writes):
            raise ValueError('Feature-reveal writer identity changed')
        callback_body = next((body for name, body in producer['functions']['shared_exe'].items()
                              if name.endswith('_callback')
                              and int(body['start_rva'], 16) == callback), None)
        if callback_body is None:
            raise ValueError('Feature-reveal callback body is missing')
        callback_text = set(_text(callback_body).values())
        if ('mov edx, 0x8c468e3c' not in callback_text
                or 'call qword ptr [rax + 0x68]' not in callback_text
                or f'call 0x140{writer:05x}' not in callback_text):
            raise ValueError('Feature-reveal EXE callback-to-writer path changed')
    if (receivers['empty_contract'] != dict(_EMPTY_STATE)
            or receivers['empty_path']['receiver_payload_reads'] != 0
            or receivers['empty_path']['subscriber_calls'] != 0
            or receivers['empty_path']['pre_hook_calls'] != 0
            or receivers['empty_path']['post_hook_calls'] != 0
            or receivers['empty_path']['receiver_gameplay_effect'] is not False
            or receivers['omission_obligations']['preserve_native_producer_and_internal_dispatch'] is not True
            or receivers['omission_obligations']['synthesized_record_count'] != 0
            or receivers['omission_obligations']['fifo_sequence_increment'] != 0):
        raise ValueError('Feature-reveal empty receiver contract changed')
    return p


def _verify_coordinate_ownership(p):
    """Close the input request through allocator stores and header ownership move."""
    expected_contract = dict(input_flags=0x01000000, stored_flags=0x21000001,
        element_size=8, element_count=1, count_mask=0x00FFFFFF,
        allocated_bit=0x01000000, aligned_free_bit=0x20000000,
        allocator_object_rva='0xb90770', allocator_vtable_rva='0xabeff8',
        allocator_slot='0x10', allocator_target_rva='0x9a1620',
        header_move_retains_allocation=True, caller_local_pointer_retained=False,
        map_destructor_releases_allocation=True, callback_pointer_retained=False)
    if p['typed_input_contract'].get('coordinate_ownership') != expected_contract:
        raise ValueError('Feature-reveal coordinate ownership contract changed')
    if set(p.get('ownership_slots', {})) != set(_OWNERSHIP_SLOTS):
        raise ValueError('Feature-reveal coordinate ownership slots changed')
    for name, (table, offset, target) in _OWNERSHIP_SLOTS.items():
        if p['ownership_slots'][name] != dict(vtable_rva=hex(table), slot=hex(offset),
                target_rva=hex(target), slot_bytes=struct.pack('<Q', 0x180000000 + target).hex()):
            raise ValueError('Feature-reveal coordinate ownership slot changed: ' + name)
    required = {
        'xp2_map_constructor': {
            0x99E4C2: 'call 0x1809a1800',
            0x99E532: 'lea rdx, [rip + 0x1f2237]',
            0x99E53C: 'call 0x1809a4360'},
        'xp2_map_allocator_getter': {0x989D0: 'mov rax, qword ptr [rcx + 0x20]'},
        'xp2_map_allocator_bind': {0x9A436E: 'mov qword ptr [rcx + 0x20], rax'},
        'xp2_pair_variant_constructor': {
            0x99DC25: 'mov r8d, dword ptr [rsp + 0x58]',
            0x99DC35: 'mov edx, dword ptr [rsp + 0x50]',
            0x99DC43: 'test dword ptr [rsp + 0x60], 0x1000000',
            0x99DC50: 'lea r9, [rsi + 8]',
            0x99DC54: 'call qword ptr [rax + 0x10]',
            0x99DC6A: 'call 0x180990d00',
            0x99DCA5: 'mov word ptr [rsi], r14w'},
        'xp2_pair_allocator': {
            0x9A1639: 'imul ecx, r8d', 0x9A1640: 'mov ebx, r8d',
            0x9A1643: 'mov esi, edx', 0x9A1658: 'call 0x180990900',
            0x9A1662: 'or ebx, 0x21000000',
            0x9A1668: 'mov qword ptr [rdi], rax',
            0x9A166B: 'mov dword ptr [rdi + 0xc], ebx',
            0x9A1670: 'mov dword ptr [rdi + 8], esi'},
        'xp2_variant_move': {
            0x9A12F0: 'mov eax, dword ptr [rdx]',
            0x9A12F6: 'movups xmm0, xmmword ptr [rdx + 8]',
            0x9A12FA: 'movups xmmword ptr [rcx + 8], xmm0',
            0x9A12FE: 'mov dword ptr [rdx], eax',
            0x9A1300: 'mov qword ptr [rdx + 0x10], rax',
            0x9A1304: 'mov qword ptr [rdx + 8], rax'},
        'xp2_variant_temporary_destructor': {
            0x9A1281: 'test al, 1', 0x9A12C5: 'shr ecx, 0x1d',
            0x9A12CB: 'je 0x1809a12db', 0x9A12D6: 'call 0x1809908f0'},
        'xp2_pair_release': {0x9A1766: 'test byte ptr [rdx + 0xf], 1',
            0x9A1777: 'call 0x1809908f0'},
        'xp2_map_destructor': {
            0x99E610: 'mov rdx, qword ptr [rsi + 0x20]',
            0x99E614: 'lea rcx, [rdi + 0x28]',
            0x99E618: 'call 0x1809a1560', 0x99E63B: 'call 0x1809a1270'},
        'xp2_variant_release': {
            0x9A1574: 'test al, 1', 0x9A15B8: 'shr ecx, 0x1d',
            0x9A15D5: 'mov rcx, r8', 0x9A15D8: 'call qword ptr [rax + 0x20]',
            0x9A15DD: 'mov dword ptr [rbx], eax',
            0x9A15DF: 'mov qword ptr [rbx + 0x10], rax'},
    }
    for name, instructions in required.items():
        actual = _text(p['functions'][name])
        if any(actual.get(rva) != text for rva, text in instructions.items()):
            raise ValueError('Feature-reveal coordinate ownership body changed: ' + name)
    pair = _text(p['functions']['xp2_event_argument_pair_setter'])
    for rva, text in {0x9A0A61: 'call 0x18099dc00',
            0x9A0AD7: 'call 0x1809a12f0', 0x9A0AE1: 'call 0x1809a1270'}.items():
        if pair.get(rva) != text:
            raise ValueError('Feature-reveal coordinate construction/move chain changed')
    window = p['allocator_initializer_window']
    list(_fragments(window))
    instructions = _rows(window)
    if (window['start_rva'] != '0x90de' or window['end_rva_exclusive'] != '0x9127'
            or instructions[0]['text'] != 'lea rax, [rip + 0xab5f13]'
            or tuple(instructions[0]['rip_targets']) != ('0x180abeff8',)
            or instructions[-1]['text'] != 'mov qword ptr [rip + 0xb87649], rax'
            or tuple(instructions[-1]['rip_targets']) != ('0x180b90770',)
            or any(row['text'].split(',')[0].endswith((' rax', ' eax', ' ax', ' al'))
                   for row in instructions[1:])):
        raise ValueError('Feature-reveal allocator initializer dataflow changed')


def source_dependencies():
    p = source()
    refs = [dict(path=SOURCE[0], sha256=SOURCE[1]), p['generator'],
            *p['references'].values()]
    receiver = _source(RECEIVER_SOURCE)
    refs.extend(receiver['references'].values())
    producer = _source(PRODUCER_SOURCE)
    refs.extend(producer['references'].values())
    pins = {}
    for ref in refs:
        path = str(_path(ref['path']).resolve())
        if path in pins and pins[path] != ref['sha256']:
            raise ValueError('Feature-reveal source dependency conflict')
        pins[path] = ref['sha256']
    from .xp2_preload_source import source_pins
    for path, digest in source_pins().items():
        if path in pins and pins[path] != digest:
            raise ValueError('Feature-reveal source dependency conflict')
        pins[path] = digest
    verify_pinned_files(pins)
    return pins


def _core_fragments():
    p = source()
    parent = _source(PRODUCER_SOURCE)
    for key in ('combat_notification_producer', 'combat_state_mutator', 'host_a0_emitter',
                'producer_caller'):
        for rva, raw in _fragments(parent['functions']['xp2_core'][key]):
            yield rva, raw
    for body in p['functions'].values():
        for rva, raw in _fragments(body):
            yield rva, raw
    yield from _fragments(p['allocator_initializer_window'])


def _read_exact(read, address, size):
    if (not callable(read) or type(address) is not int or address <= 0
            or type(size) is not int or not 0 < size <= 4096 or address + size > 2**64):
        raise ValueError('Invalid feature-reveal live source read')
    data = read(address, size)
    if type(data) is not bytes or len(data) != size:
        raise ValueError('Incomplete feature-reveal live source read')
    return data


def bind_owner(backend, core, read):
    backend.check_thread()
    if (backend.core is not core or backend.load_abi.core_sha256 != _CORE_SHA
            or backend.stage != 'prepared' or backend.poisoned or backend.destroyed
            or type(core._handle) is not int or core._handle <= 0):
        raise ValueError('Feature-reveal source requires its exact prepared XP2 owner')
    source_dependencies()
    for rva, raw in _core_fragments():
        for offset in range(0, len(raw), 4096):
            chunk = raw[offset:offset + 4096]
            if _read_exact(read, core._handle + rva + offset, len(chunk)) != chunk:
                raise ValueError('Feature-reveal live Core source differs')
    for name, (table, offset, target) in _OWNERSHIP_SLOTS.items():
        actual = struct.unpack('<Q', _read_exact(read, core._handle + table + offset, 8))[0]
        if actual != core._handle + target:
            raise ValueError('Feature-reveal coordinate ownership virtual slot differs: ' + name)
    if struct.unpack('<Q', _read_exact(read, core._handle + 0xB90770, 8))[0] != core._handle + 0xABEFF8:
        raise ValueError('Feature-reveal coordinate allocator live identity differs')
    backend._xp2_feature_reveal_source_identity = (id(core), core._handle, _CORE_SHA, SOURCE[1])
    return SOURCE[1]


def validate_empty_owner(owner):
    from .a0_family_service import A0FamilyService
    from .a0_foundation_events import require_borrow
    if type(owner) is not A0FamilyService:
        raise ValueError('Feature-reveal omission requires the actual A0 owner')
    owner._check()
    token = require_borrow(owner)
    backend = token.owner
    if (owner.active_kind not in KINDS or backend.load_abi.core_sha256 != _CORE_SHA
            or owner.arguments.reader.core_sha256 != _CORE_SHA
            or owner.deferred.cache_core_sha256 != _CORE_SHA
            or owner._foundation_backend is not backend
            or backend.core is not owner.deferred.core
            or backend.host is not owner.arguments.host
            or owner.empty_receiver_state != dict(_EMPTY_STATE)
            or owner._receiver_profile != dict(_EMPTY_STATE)
            or any(type(owner.empty_receiver_state[k]) is not type(v) for k, v in _EMPTY_STATE.items())
            or owner.entity_listener_count != 0 or type(owner.entity_listener_count) is not int
            or owner.dynamic_event_registration_present is not False
            or owner.normalizer_transform_present is not False
            or owner.per_thread_hook_present is not False
            or owner.writer_metadata_callback_present is not False
            or getattr(backend, '_xp2_feature_reveal_source_identity', None) !=
               (id(backend.core), backend.core._handle, _CORE_SHA, SOURCE[1])):
        raise ValueError('Feature-reveal empty receiver or owner source changed')
    return POLICY


@dataclass(frozen=True)
class FeatureRevealFields:
    kind: int
    selector: int
    position: tuple[int, int]
    value: int

    def to_admin(self):
        return dict(kind=hex(self.kind), event_name=EVENT_NAMES[self.kind], selector=self.selector,
                    coordinate=list(self.position), value_key=hex(VALUE_KEY), value=self.value,
                    field_tags={hex(SELECTOR_KEY): 3, hex(POSITION_KEY): 0, hex(VALUE_KEY): 2},
                    borrowed_position_payload_copied=True, borrowed_pointer_retained=False)


def _copy_pair(read, pointer):
    if type(pointer) is not int or pointer <= 0 or pointer + 8 > 2**64:
        raise ValueError('Feature-reveal position pointer is invalid')
    raw = read(pointer, 8)
    if type(raw) is not bytes or len(raw) != 8:
        raise ValueError('Feature-reveal position payload copy is incomplete')
    return struct.unpack('<ii', raw)


def _uint32_variant(raw, tag, label):
    if (type(raw) is not bytes or len(raw) != 24 or struct.unpack_from('<H', raw)[0] != tag
            or raw[16:24] != b'\0' * 8):
        raise ValueError(f'Feature-reveal {label} scalar variant differs')
    return struct.unpack_from('<I', raw, 8)[0]


def decode_fields(kind, raw_fields, read):
    source()
    if (type(kind) is not int or kind not in KINDS or type(raw_fields) is not dict
            or set(raw_fields) != {SELECTOR_KEY, POSITION_KEY, VALUE_KEY}):
        raise ValueError('Feature-reveal argument keys differ from source')
    selector = _uint32_variant(raw_fields[SELECTOR_KEY], 3, 'selector')
    if selector != 0:
        raise ValueError('Feature-reveal selector differs from zero-extended producer kind')
    value = _uint32_variant(raw_fields[VALUE_KEY], 2, 'value')
    position_raw = raw_fields[POSITION_KEY]
    if type(position_raw) is not bytes or len(position_raw) != 24:
        raise ValueError('Feature-reveal borrowed coordinate variant differs: expected 24-byte header')
    tag = struct.unpack_from('<H', position_raw)[0]
    size, flags = struct.unpack_from('<II', position_raw, 16)
    if tag != 0 or size != 8 or flags != 0x21000001:
        raise ValueError('Feature-reveal borrowed coordinate variant differs: '
                         f'tag={tag}, element_size={size}, flags={flags:#010x}')
    pointer = struct.unpack_from('<Q', position_raw, 8)[0]
    return FeatureRevealFields(kind, selector, _copy_pair(read, pointer), value)


__all__ = ['SOURCE', 'HISTORICAL_SOURCE', 'PRODUCER_SOURCE', 'RECEIVER_SOURCE', 'POLICY', 'KINDS', 'CALLBACKS',
           'EVENT_NAMES', 'FLOODPLAIN_REVEALED', 'VOLCANO_REVEALED', 'GEOTHERMAL_FISSURE_REVEALED',
           'source', 'source_dependencies', 'bind_owner', 'validate_empty_owner',
           'FeatureRevealFields', 'decode_fields']
